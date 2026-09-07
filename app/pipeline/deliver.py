"""The gate between a rendered flyer and the client's Google Drive folder.

Flyers used to be rendered *straight into* the mounted Drive folder, which
meant QA ran on a file the client could already see. A flyer that failed its
checks was reported as a failure and left sitting in Drive anyway.

So rendering now happens in a local staging directory and this module is the
only thing that writes to Drive. A flyer crosses that line when, and only
when:

* its own deterministic QA passed, and
* the batch it belongs to passes the cross-flyer checks below, and
* the destination folder actually exists and is writable.

Anything else stays in staging with its QA report next to it, and the run
summary says which flyers were held and why. Holding a flyer back is always
recoverable; publishing a bad one to the client's folder is not.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..config import Settings, get_settings
from ..logging_setup import get_logger
from ..models import Client, FlyerResult, GenerationRun, QAIssue, Severity

log = get_logger(__name__)


# ------------------------------------------------------------------ location


def staging_dir(client: Client, when: date, settings: Settings) -> Path:
    """Where flyers are rendered. Always local, never the client's folder."""
    path = settings.paths.output / when.isoformat() / client.id
    path.mkdir(parents=True, exist_ok=True)
    return path


def delivery_dir(client: Client, when: date, settings: Settings) -> Path | None:
    """The mounted Drive folder for today, or None when Drive is unavailable."""
    from ..drive.local import resolve_output_dir

    try:
        return resolve_output_dir(client.company_name, when, settings)
    except Exception as exc:
        log.warning("Drive folder unavailable (%s); flyers stay in staging", exc)
        return None


# ------------------------------------------------------------- batch review


def batch_issues(results: list[FlyerResult]) -> dict[str, list[QAIssue]]:
    """Checks that only make sense across a whole batch.

    A flyer can be individually perfect and still be wrong as one of today's
    two: the same photograph twice reads as a mistake to anyone scrolling the
    client's folder, and so does the same layout with different words.
    """
    found: dict[str, list[QAIssue]] = {r.spec.id: [] for r in results}
    if len(results) < 2:
        return found

    def flag(result: FlyerResult, check: str, severity: Severity, message: str) -> None:
        found[result.spec.id].append(QAIssue(check=check, severity=severity, message=message))

    # Photograph reuse. The first flyer to use an image keeps it; later ones
    # are held, because re-rendering one flyer is cheaper than re-running the
    # batch and the earlier flyer is not the one at fault.
    seen_assets: set[str] = set()
    for result in results:
        asset_id = result.spec.image.asset_id
        if not asset_id:
            continue
        if asset_id in seen_assets:
            flag(
                result,
                "duplicate_photo",
                Severity.ERROR,
                f"photograph {asset_id} is already used by an earlier flyer in this batch",
            )
        seen_assets.add(asset_id)

    # Layout and type reuse is a warning, not a block: two cards in the same
    # template still look deliberate when the photography and copy differ.
    seen_layouts: set[str] = set()
    for result in results:
        key = f"{result.spec.layout.name}/{result.spec.layout.type_pairing}"
        if key in seen_layouts:
            flag(
                result,
                "duplicate_layout",
                Severity.WARNING,
                f"same layout and type pairing as an earlier flyer ({key})",
            )
        seen_layouts.add(key)

    # Identical headlines are always a bug.
    seen_headlines: set[str] = set()
    for result in results:
        headline = " ".join(result.spec.text.headline.lower().split())
        if headline and headline in seen_headlines:
            flag(result, "duplicate_headline", Severity.ERROR, "headline repeats an earlier flyer")
        seen_headlines.add(headline)

    return found


# ---------------------------------------------------------------- delivering


@dataclass
class DeliveryReport:
    destination: Path | None = None
    delivered: list[str] = field(default_factory=list)
    held: list[tuple[str, str]] = field(default_factory=list)  # (flyer id, reason)

    def summary(self) -> str:
        if self.destination is None:
            return f"held {len(self.held) + len(self.delivered)} flyer(s): Drive not available"
        parts = [f"{len(self.delivered)} delivered to {self.destination}"]
        if self.held:
            parts.append(f"{len(self.held)} held")
        return ", ".join(parts)


def deliver(
    run: GenerationRun,
    client: Client,
    when: date,
    settings: Settings | None = None,
) -> DeliveryReport:
    """Move every flyer that earned it into the client's Drive folder."""
    settings = settings or get_settings()
    report = DeliveryReport()

    batch = batch_issues(run.results)
    for result in run.results:
        blockers = [i for i in batch.get(result.spec.id, []) if i.severity is Severity.ERROR]
        if blockers:
            _record_batch_issues(result, batch[result.spec.id])
            result.qa_passed = False
            result.rejection_reasons.extend(i.message for i in blockers)
        elif batch.get(result.spec.id):
            _record_batch_issues(result, batch[result.spec.id])

    destination = delivery_dir(client, when, settings)
    report.destination = destination

    for result in run.results:
        if not result.qa_passed:
            reason = "; ".join(result.rejection_reasons) or f"QA score {result.qa_score}"
            report.held.append((result.spec.id, reason))
            log.warning("Holding %s in staging - %s", result.spec.id, reason)
            continue
        if destination is None:
            report.held.append((result.spec.id, "Google Drive folder not reachable"))
            continue
        try:
            _move_flyer(result, destination, when)
        except Exception as exc:
            run.errors.append(f"delivery failed for {result.spec.id}: {exc}")
            report.held.append((result.spec.id, f"delivery failed: {exc}"))
            log.error("Delivery failed for %s: %s", result.spec.id, exc)
            continue
        report.delivered.append(result.spec.id)

    log.info("Delivery: %s", report.summary())
    return report


def _record_batch_issues(result: FlyerResult, issues: list[QAIssue]) -> None:
    """Fold batch findings into the flyer's own QA sidecar."""
    path = Path(result.metadata_path)
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    qa = payload.setdefault("qa", {})
    errors = [i for i in issues if i.severity is Severity.ERROR]
    qa.setdefault("issues", []).extend(i.model_dump() for i in errors)
    qa.setdefault("warnings", []).extend(
        i.model_dump() for i in issues if i.severity is not Severity.ERROR
    )
    if errors:
        qa["passed"] = False
        qa["score"] = max(0, int(qa.get("score", 100)) - 25 * len(errors))
    qa["checked_by"] = f"{qa.get('checked_by', 'deterministic')}+batch"
    payload["qa"] = qa
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def delivered_name(result: FlyerResult, suffix: str, when: date) -> str:
    """The filename the client sees.

    Staging names flyers ``flyer-01.jpg`` and re-renders ``flyer-01-retry2.jpg``,
    which is right for a working directory and wrong for the client's folder:
    the names carry no information and they collide with yesterday's batch,
    silently replacing files somebody may already have used.
    """
    campaign = result.spec.campaign_id or "flyer"
    # The run's own date, not ``created_at`` - that is a UTC timestamp, and an
    # evening run in New Jersey stamps tomorrow's date on a file sitting in
    # today's folder.
    return f"{when.isoformat()}-{campaign}{suffix}"


def _unique(target: Path) -> Path:
    """Never overwrite a file already in the client's folder."""
    if not target.exists():
        return target
    for index in range(2, 100):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many versions of {target.name}")


def _move_flyer(result: FlyerResult, destination: Path, when: date) -> None:
    """Move the image, its sidecar and its thumbnail into Drive.

    The sidecar records the delivered path before the move so ``flyer clean``
    can tell a flyer that reached the client from one that never left staging.
    """
    destination.mkdir(parents=True, exist_ok=True)
    image = Path(result.image_path)
    if not image.exists():
        raise FileNotFoundError(image)

    target = _unique(destination / delivered_name(result, image.suffix, when))
    metadata = Path(result.metadata_path)
    if metadata.exists():
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        payload["delivered_path"] = str(target)
        payload["image_path"] = str(target)
        metadata.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")

    shutil.move(str(image), target)
    result.image_path = str(target)
    result.drive_url = target.as_uri()

    thumb = Path(result.metadata_path).parent / "thumbs" / f"{image.stem}.jpg"
    if thumb.exists():
        thumb.unlink(missing_ok=True)
