"""Deterministic quality control and environment validation.

These checks need no API and no credentials, so they run in CI on every push
and gate every Drive upload.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageStat

from ..config import Settings, get_settings
from ..copy_rules import (
    AI_PUNCTUATION,
    DUPLICATE_WORD,
    EMOJI,
    PLACEHOLDER_PATTERNS,
    RISKY_CLAIM,
    filler_hits,
)
from ..logging_setup import get_logger
from ..models import Client, FlyerSpecification, QAIssue, QAResult, Severity

log = get_logger(__name__)


def _issue(check: str, severity: Severity, message: str, detail: str = "") -> QAIssue:
    return QAIssue(check=check, severity=severity, message=message, detail=detail)


# ------------------------------------------------------------------ flyer QA


def qa_flyer(
    image_path: Path,
    spec: FlyerSpecification,
    client: Client,
    renderer_warnings: list[str] | None = None,
    asset_stage: str = "",
) -> QAResult:
    """Every check that can be made without a model."""
    from ..house_rules import check as house_rules

    issues: list[QAIssue] = []
    technical = _technical_checks(image_path, spec)
    issues += technical
    issues += _text_checks(spec, client)
    issues += _branding_checks(spec, client)

    # The account owner's standing instructions. These are the checks that
    # encode "what I intended", as opposed to "this file is a valid image".
    logo_drawn = not any("no client mark was drawn" in w.lower() for w in (renderer_warnings or []))
    issues += house_rules(spec, client, asset_stage=asset_stage, logo_drawn=logo_drawn)

    # Pixel checks only make sense on a file that decoded. Running them on a
    # rejected file turns a clean QA failure into a crash.
    decodable = not any(
        i.severity is Severity.ERROR and i.check in {"file_exists", "file_size", "image_readable"}
        for i in technical
    )
    if decodable and image_path.exists():
        try:
            issues += _visual_checks(image_path, spec)
        except Exception as exc:  # defensive: never let QA itself crash a run
            issues.append(
                _issue("visual_checks", Severity.ERROR, f"Visual inspection failed: {exc}")
            )

    for warning in renderer_warnings or []:
        issues.append(_issue("renderer", _renderer_severity(warning), warning))

    result = QAResult.from_issues(issues)
    log.info(
        "Deterministic QA for %s: %s (score %d, %d error(s), %d warning(s))",
        spec.id,
        "PASS" if result.passed else "FAIL",
        result.score,
        len(result.issues),
        len(result.warnings),
    )
    return result


BLOCKING_RENDERER_WARNINGS = (
    "no client mark was drawn",
    "logo unreadable",
    "overflowed",
    "overlap by",
    "does not read against",
)


def _renderer_severity(warning: str) -> Severity:
    """A flyer without the logo cannot ship; a soft logo can.

    Matching on the substring "logo" alone was too blunt - it promoted the
    advisory "logo upscaled 2.3x" note to a blocking error and held back every
    flyer in the batch. Only the specific failures listed above block.
    """
    lowered = warning.lower()
    if any(phrase in lowered for phrase in BLOCKING_RENDERER_WARNINGS):
        return Severity.ERROR
    return Severity.WARNING


def _technical_checks(path: Path, spec: FlyerSpecification) -> list[QAIssue]:
    issues: list[QAIssue] = []
    if not path.exists():
        return [_issue("file_exists", Severity.ERROR, f"Rendered file missing: {path}")]

    size = path.stat().st_size
    if size == 0:
        return [_issue("file_size", Severity.ERROR, "Rendered file is empty")]
    if size < 20_000:
        issues.append(
            _issue("file_size", Severity.WARNING, f"Suspiciously small output ({size} bytes)")
        )
    if size > 8_000_000:
        issues.append(
            _issue("file_size", Severity.WARNING, f"Large output ({size // 1_000_000} MB)")
        )

    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            fmt = image.format
    except Exception as exc:
        return [_issue("image_readable", Severity.ERROR, f"Output is not a valid image: {exc}")]

    if (width, height) != (spec.canvas.width, spec.canvas.height):
        issues.append(
            _issue(
                "dimensions",
                Severity.ERROR,
                f"Expected {spec.canvas.width}x{spec.canvas.height}, got {width}x{height}",
            )
        )
    if fmt not in {"PNG", "JPEG"}:
        issues.append(_issue("format", Severity.ERROR, f"Unexpected image format {fmt}"))
    return issues


def _text_checks(spec: FlyerSpecification, client: Client) -> list[QAIssue]:
    issues: list[QAIssue] = []
    copy = spec.text
    fields = {
        "eyebrow": copy.eyebrow,
        "headline": copy.headline,
        "support": copy.support,
        "cta": copy.cta,
        "offer_badge": copy.offer_badge,
        "disclaimer": copy.disclaimer,
    }

    if not copy.cta.strip():
        issues.append(_issue("cta_present", Severity.ERROR, "Flyer has no call to action"))

    for name, value in fields.items():
        if not value:
            continue
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(value):
                issues.append(
                    _issue("placeholder_text", Severity.ERROR, f"Placeholder text in {name}", value)
                )
                break
        if DUPLICATE_WORD.search(value):
            issues.append(
                _issue("duplicate_words", Severity.WARNING, f"Repeated word in {name}", value)
            )
        if RISKY_CLAIM.search(value):
            issues.append(
                _issue("risky_claim", Severity.ERROR, f"Legally risky claim in {name}", value)
            )

    for name, value in fields.items():
        if value and value.strip() != value:
            issues.append(_issue("whitespace", Severity.WARNING, f"Untrimmed whitespace in {name}"))

    # Anti-AI-tell gate. These are hard failures: a single em dash or emoji is
    # enough for a homeowner to clock the flyer as machine-made.
    for name, value in fields.items():
        if not value:
            continue
        if AI_PUNCTUATION.search(value):
            issues.append(
                _issue(
                    "ai_punctuation",
                    Severity.ERROR,
                    f"Em/en dash in {name} - use a comma, a full stop or a colon",
                    value,
                )
            )
        if EMOJI.search(value):
            issues.append(_issue("emoji", Severity.ERROR, f"Emoji in {name}", value))
    for bullet in copy.bullets:
        if AI_PUNCTUATION.search(bullet):
            issues.append(
                _issue("ai_punctuation", Severity.ERROR, "Em/en dash in a bullet", bullet)
            )
        if EMOJI.search(bullet):
            issues.append(_issue("emoji", Severity.ERROR, "Emoji in a bullet", bullet))

    hits = filler_hits(" ".join(v for v in fields.values() if v))
    if len(hits) == 1:
        issues.append(
            _issue("ai_filler", Severity.WARNING, f"Generic marketing filler: {hits[0]!r}")
        )
    elif len(hits) > 1:
        issues.append(
            _issue(
                "ai_filler",
                Severity.ERROR,
                "Copy reads as generated marketing filler",
                ", ".join(hits),
            )
        )

    total_words = sum(len(v.split()) for v in fields.values() if v) + sum(
        len(b.split()) for b in copy.bullets
    )
    if total_words > 40:
        issues.append(
            _issue(
                "text_volume",
                Severity.ERROR,
                f"{total_words} words on the flyer - well past the 25-word target",
            )
        )
    elif total_words > 25:
        issues.append(
            _issue(
                "text_volume",
                Severity.WARNING,
                f"{total_words} words on the flyer - aim for under 25",
            )
        )

    if copy.offer_badge and not any(o.id == _offer_hint(spec) for o in client.offers):
        # Offer text present but no authorised offer on file for this flyer.
        authorised = {o.text.lower() for o in client.offers}
        if copy.offer_badge.lower() not in authorised:
            issues.append(
                _issue(
                    "unauthorised_offer",
                    Severity.ERROR,
                    "Offer badge text is not an authorised offer",
                    copy.offer_badge,
                )
            )

    # Any number in a claim must be traceable to the client profile.
    proof_blob = " ".join(client.proof_points).lower()
    for bullet in copy.bullets:
        numbers = re.findall(r"\b\d[\d,\.]*\+?\b", bullet)
        for number in numbers:
            if number.lower() not in proof_blob:
                issues.append(
                    _issue(
                        "unverified_number",
                        Severity.WARNING,
                        f"Number {number!r} is not in the client's proof points",
                        bullet,
                    )
                )
    return issues


def _offer_hint(spec: FlyerSpecification) -> str:
    return spec.campaign_id


def _branding_checks(spec: FlyerSpecification, client: Client) -> list[QAIssue]:
    issues: list[QAIssue] = []
    if spec.client_id != client.id:
        issues.append(
            _issue(
                "client_match",
                Severity.ERROR,
                f"Spec is for {spec.client_id!r} but was rendered against {client.id!r}",
            )
        )

    blob = " ".join(
        [spec.text.eyebrow, spec.text.headline, spec.text.support, spec.text.cta]
    ).lower()

    # A competitor's name should never appear in our copy.
    for word in ("call now for a free", "www."):
        if word in blob and client.contact.website and client.contact.website.lower() not in blob:
            issues.append(
                _issue("stray_url", Severity.WARNING, "Copy contains a URL fragment", blob)
            )
            break

    phone = client.contact.phone
    if phone:
        digits = re.sub(r"\D", "", phone)
        if len(digits) not in (10, 11):
            issues.append(
                _issue(
                    "phone_format",
                    Severity.WARNING,
                    f"Client phone {phone!r} does not look like a US number",
                )
            )
    return issues


def _visual_checks(path: Path, spec: FlyerSpecification) -> list[QAIssue]:
    """Cheap pixel checks: blank output, dead margins, edge bleed."""
    issues: list[QAIssue] = []
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        grey = rgb.convert("L")

        stat = ImageStat.Stat(grey)
        if stat.stddev[0] < 6:
            issues.append(
                _issue(
                    "blank_output",
                    Severity.ERROR,
                    "Flyer is almost uniform - the render probably failed",
                )
            )

        width, height = rgb.size
        margin = max(int(width * 0.018), 6)

        # Clipped text shows up as an edge strip that is *much* busier than the
        # band just inside it. Comparing the two avoids firing on legitimate
        # full-bleed photography, which is busy everywhere.
        for name, edge_box, inner_box in (
            ("left", (0, 0, margin, height), (margin, 0, margin * 4, height)),
            (
                "right",
                (width - margin, 0, width, height),
                (width - margin * 4, 0, width - margin, height),
            ),
            ("top", (0, 0, width, margin), (0, margin, width, margin * 4)),
        ):
            edge_var = ImageStat.Stat(grey.crop(edge_box)).stddev[0]
            inner_var = ImageStat.Stat(grey.crop(inner_box)).stddev[0]
            if edge_var > 55 and edge_var > inner_var * 1.6:
                issues.append(
                    _issue(
                        "edge_bleed",
                        Severity.WARNING,
                        f"Detail against the {name} edge is far busier than just inside it "
                        f"({edge_var:.0f} vs {inner_var:.0f}) - possible clipping",
                    )
                )

        # The bottom edge legitimately carries the contact bar, so it is exempt.
        if spec.canvas.height >= 600:
            band = grey.crop((0, int(height * 0.30), width, int(height * 0.34)))
            if ImageStat.Stat(band).mean[0] > 250:
                issues.append(
                    _issue("dead_space", Severity.INFO, "Large empty band in the upper third")
                )
    return issues


# ------------------------------------------------------- environment / config


def validate_environment(settings: Settings | None = None) -> QAResult:
    """Pre-flight check run by ``flyer validate`` and by CI before generating."""
    settings = settings or get_settings()
    issues: list[QAIssue] = []

    if not settings.anthropic_api_key:
        issues.append(
            _issue(
                "ANTHROPIC_API_KEY",
                Severity.WARNING,
                "Not set - the pipeline will run in deterministic fallback mode",
            )
        )
    if settings.offline:
        issues.append(
            _issue("FLYER_OFFLINE", Severity.INFO, "Offline mode is on; Claude will not be called")
        )
    if not settings.drive_enabled:
        issues.append(
            _issue(
                "google_drive",
                Severity.WARNING,
                "Drive is not configured - flyers stay in output/ and CI artifacts",
            )
        )

    if settings.output_width < 320 or settings.output_height < 320:
        issues.append(
            _issue(
                "canvas",
                Severity.ERROR,
                f"Canvas {settings.output_width}x{settings.output_height} is too small",
            )
        )
    if settings.output_format not in {"PNG", "JPEG", "JPG"}:
        issues.append(
            _issue(
                "OUTPUT_FORMAT",
                Severity.ERROR,
                f"Unsupported OUTPUT_FORMAT {settings.output_format!r}",
            )
        )

    if not re.match(r"^\d{1,2}:\d{2}$", settings.schedule_time):
        issues.append(
            _issue(
                "SCHEDULE_TIME",
                Severity.ERROR,
                f"SCHEDULE_TIME {settings.schedule_time!r} must be HH:MM",
            )
        )

    from ..rendering.templates import assert_layouts_registered

    try:
        assert_layouts_registered()
    except ValueError as exc:
        issues.append(_issue("layouts", Severity.ERROR, str(exc)))

    from ..rendering.typography import FontLibrary

    if not FontLibrary(settings.paths.fonts).available():
        issues.append(
            _issue(
                "fonts",
                Severity.WARNING,
                "No fonts in assets/fonts - run `python scripts/fetch_fonts.py` "
                "for production-quality typography",
            )
        )

    return QAResult.from_issues(issues, checked_by="environment")


def has_photo_library(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    from ..assets.image_utils import SUPPORTED_SUFFIXES

    for root in (settings.paths.assets, settings.paths.clients):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() in SUPPORTED_SUFFIXES and "logo" not in path.parts:
                return True
    return False
