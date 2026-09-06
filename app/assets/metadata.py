"""Filesystem conventions that turn a folder layout into asset metadata.

Assets are catalogued from their path, so dropping a photo into
``assets/roofing/`` is all the "tagging" that is required to make it usable.
Optional ``<image>.json`` sidecars override anything derived here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import get_settings

SERVICE_FOLDERS = {
    "roofing",
    "siding",
    "gutters",
    "windows",
    "hvac",
    "plumbing",
    "electrical",
    "remodeling",
    "construction",
    "general",
    "backgrounds",
}

# Folder name -> canonical service. Anything unlisted becomes "general".
FOLDER_TO_SERVICE = {
    "backgrounds": "general",
    "construction": "general",
    "houses": "general",
    "interiors": "remodeling",
    "team": "general",
}


def derive_service_from_path(path: Path) -> str:
    """Infer the service from the folder, then from the filename.

    Client photography usually lives in one flat ``assets/approved/`` folder, so
    the documented convention is to name files by service
    (``roofing-shingle-replacement-01.jpg``). Folder wins when both are present.
    """
    settings = get_settings()
    try:
        parts = path.resolve().relative_to(settings.paths.root).parts
    except ValueError:
        parts = path.parts

    for part in parts[:-1]:
        key = part.lower()
        if key in FOLDER_TO_SERVICE:
            return FOLDER_TO_SERVICE[key]
        if key in SERVICE_FOLDERS:
            return key

    for token in path.stem.lower().replace("_", "-").split("-"):
        if token in FOLDER_TO_SERVICE:
            return FOLDER_TO_SERVICE[token]
        if token in SERVICE_FOLDERS:
            return token
        # Tolerate the singular form: "roof-01.jpg" is roofing.
        if f"{token}ing" in SERVICE_FOLDERS:
            return f"{token}ing"
        if f"{token}s" in SERVICE_FOLDERS:
            return f"{token}s"

    return "general"


def derive_tags_from_path(path: Path) -> list[str]:
    """Every path segment plus filename tokens becomes a searchable tag."""
    settings = get_settings()
    try:
        parts = list(path.resolve().relative_to(settings.paths.root).parts[:-1])
    except ValueError:
        parts = list(path.parts[:-1])
    stem_tokens = [t for t in path.stem.replace("_", "-").split("-") if t and not t.isdigit()]
    tags = {p.lower() for p in parts if p not in {"assets", "clients"}}
    tags.update(t.lower() for t in stem_tokens)
    return sorted(tags)


def load_sidecar(path: Path) -> dict:
    """Read an optional ``<image>.json`` metadata override."""
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def derive_client_id(path: Path) -> str | None:
    """Assets under ``clients/<slug>/assets/`` belong to that client."""
    settings = get_settings()
    try:
        parts = path.resolve().relative_to(settings.paths.root).parts
    except ValueError:
        return None
    if len(parts) >= 2 and parts[0] == "clients":
        return parts[1]
    return None


# ---------------------------------------------------------------- provenance

# Folder conventions that establish provenance. Being committed to one of these
# directories IS the act of approval; there is no separate approval file.
#
#   clients/<slug>/assets/approved/**   real, approved client photography
#   clients/<slug>/assets/raw/**        real client media, NOT yet approved
#   assets/placeholders/**              synthetic scaffolding, never production
#   assets/<service>/**                 approved internal background library
#
# Anything outside these is UNKNOWN, which fails the production gate closed.


def derive_provenance(path: Path) -> dict:
    """Establish provenance from location, then refine with EXIF.

    Deliberately conservative: an image whose origin cannot be established
    stays ``unknown`` and is therefore barred from production.
    """
    from ..models import ApprovalStatus, Provenance, SourceType

    settings = get_settings()
    try:
        parts = path.resolve().relative_to(settings.paths.root).parts
    except ValueError:
        parts = path.parts
    lowered = [p.lower() for p in parts]

    source_type = SourceType.UNKNOWN
    approval = ApprovalStatus.UNAPPROVED

    if "placeholders" in lowered or path.stem.lower().startswith("placeholder"):
        source_type = SourceType.PLACEHOLDER
    elif lowered and lowered[0] == "clients":
        if "raw" in lowered or "inbox" in lowered:
            source_type = SourceType.CLIENT_PHOTO  # real, but not yet approved
        elif "approved" in lowered or "photos" in lowered:
            source_type = SourceType.CLIENT_PHOTO
            approval = ApprovalStatus.APPROVED
        if "extracted_frames" in lowered or "_frame_" in path.stem.lower():
            source_type = SourceType.CLIENT_VIDEO_FRAME
        elif "drone" in " ".join(lowered) or path.stem.upper().startswith("DJI_"):
            source_type = SourceType.CLIENT_DRONE
    elif lowered and lowered[0] == "assets":
        source_type = SourceType.INTERNAL_BACKGROUND
        approval = ApprovalStatus.APPROVED

    provenance = Provenance(
        source_type=source_type,
        approval_status=approval,
        origin_path=str(path),
        verified_by="folder-convention",
    )

    # Folder convention is not enough on its own: a synthetic image dropped into
    # assets/roofing/ would inherit "approved internal background". Colour
    # complexity separates a photograph from flat vector art by a wide margin,
    # so it acts as a content-based backstop.
    if source_type in (SourceType.INTERNAL_BACKGROUND, SourceType.STOCK) and _looks_synthetic(path):
        provenance.source_type = SourceType.GENERATED_SAMPLE
        provenance.approval_status = ApprovalStatus.UNAPPROVED
        provenance.verified_by = "colour-complexity"
        provenance.notes = "Too few distinct colours to be a photograph."

    _apply_exif(path, provenance)
    _apply_project_label(parts, provenance)
    return provenance.model_dump()


# Measured on this project's own library: flat vector art sits around 0.02
# unique colours per pixel, real photographs around 0.43. The threshold is set
# well clear of both.
SYNTHETIC_COLOUR_RATIO = 0.12


def _looks_synthetic(path: Path) -> bool:
    """Is this flat vector art rather than a photograph?

    A photograph has tens of thousands of distinct colours from sensor noise and
    natural gradients. Generated or drawn images have very few.
    """
    try:
        from PIL import Image

        with Image.open(path) as handle:
            image = handle.convert("RGB")
            image.thumbnail((400, 400))
            reader = getattr(image, "get_flattened_data", None)
            pixels = list(reader()) if callable(reader) else list(image.getdata())
            width, height = image.size
    except Exception:
        return False

    total = width * height
    if total < 2000:
        return False  # too small to judge
    return (len(set(pixels)) / total) < SYNTHETIC_COLOUR_RATIO


def _apply_exif(path: Path, provenance) -> None:
    """Camera metadata is the strongest evidence an image is a real photograph."""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        with Image.open(path) as image:
            exif: dict = dict(image.getexif() or {})
        tags = {TAGS.get(k, k): v for k, v in exif.items()}
    except Exception:
        return

    make = str(tags.get("Make", "")).strip()
    model = str(tags.get("Model", "")).strip()
    captured = str(tags.get("DateTime", "")).strip()

    if make or model:
        provenance.camera = f"{make} {model}".strip()
        provenance.verified_by = "exif-camera"
    if captured:
        provenance.captured_at = captured


# Real All Elite project locations, from the client's own media drives. A
# filename token matching one of these establishes which job a photo is of.
# Add a location here when a new project folder appears.
KNOWN_PROJECTS: dict[str, str] = {
    "bergenfield": "Bergenfield",
    "cresskill": "Cresskill",
    "hawthorne": "Hawthorne",
    "elmwood": "Elmwood Park",
    "elmwoodpark": "Elmwood Park",
    "forestpl": "Forest Pl, Rochelle Park",
    "rochelle": "Forest Pl, Rochelle Park",
    "washington": "Washington Township",
    "hillsdale": "Hillsdale",
    "kinderkamack": "Hillsdale",
    "totowa": "Totowa",
    "dotyrd": "Doty Road",
    "james": "James, Rochelle Park",
    "hillside": "Bergenfield",
    "cornell": "Hawthorne",
    "mountain": "Washington Township",
    "stone": "Elmwood Park",
    "columbus": "Totowa",
}


def _apply_project_label(parts: tuple, provenance) -> None:
    """Identify which real job a photograph is of.

    This matters beyond labelling: the before/after layout pairs images by
    project, and pairing one house's "before" with another's "after" would
    present two different homes as a single job. So the project is taken from
    a recognised location token, and left blank when none is found rather than
    guessed from a parent folder.
    """
    from ..models import SourceType

    if provenance.source_type not in (
        SourceType.CLIENT_PHOTO,
        SourceType.CLIENT_DRONE,
        SourceType.CLIENT_VIDEO_FRAME,
    ):
        return

    stem = Path(parts[-1]).stem.lower() if parts else ""
    tokens = [t for t in re.split(r"[_\W]+", stem) if t]

    for token in tokens:
        if token in KNOWN_PROJECTS:
            provenance.project = token
            provenance.address_label = KNOWN_PROJECTS[token]
            break
    else:
        # Fall back to a folder name, but never to the client slug itself.
        skip = {
            "clients",
            "assets",
            "approved",
            "raw",
            "photos",
            "inbox",
            "drone",
            "frames",
            "drone_media",
            "extracted_frames",
            "high_res_photos",
        }
        # The client slug is never a project. Labelling every photo with it
        # collapses all projects into one, which lets the before/after layout
        # pair two different houses as though they were one job.
        candidates = parts[2:-1] if parts and parts[0].lower() == "clients" else parts[1:-1]
        for part in candidates:
            key = part.lower()
            if key in KNOWN_PROJECTS:
                provenance.project = key
                provenance.address_label = KNOWN_PROJECTS[key]
                break
            if key not in skip and not part.startswith("."):
                provenance.project = key.replace(" ", "-")
                provenance.address_label = part.replace("-", " ").replace("_", " ").title()
                break

    provenance.stage = infer_stage(tokens)


def infer_stage(tokens: list[str]) -> str:
    """Work out whether a photo shows before, during, after or neutral work.

    Ordered deliberately: an explicit 'before'/'during'/'after' token wins, then
    stronger descriptive words, and only then the weak neutral hints. A file
    called 'roof_bergenfield_after_architectural' must not be read as neutral
    just because it also says 'roof'.
    """
    from ..config import load_json_config

    try:
        keywords = load_json_config("stage-policy.json")["keywords"]
    except Exception:
        keywords = {}

    present = set(tokens)
    for stage in ("before", "during", "after"):
        if stage in present:
            return stage
    for stage in ("after", "during", "before", "neutral"):
        for word in keywords.get(stage, []):
            if word in present:
                return stage
    return ""
