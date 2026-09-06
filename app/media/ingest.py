"""Orchestration: a drive of raw footage into catalogued candidate frames.

Two passes, because scoring 4K frames is wasteful:

  1. sample each clip at low resolution and score the candidates
  2. re-extract only the winners at full resolution

Extracted frames are written as ``client_frame`` / **unapproved**. They are real
media, so they outrank stock, but they are not production-eligible until a human
promotes them. That boundary is the whole point of the provenance system.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from ..config import get_settings
from ..logging_setup import get_logger
from .frames import (
    FrameCandidate,
    dhash,
    extract_frame,
    hamming,
    sample_times,
    score_frame,
)
from .probe import MediaItem, ffmpeg_available, probe_video, scan_directory

log = get_logger(__name__)

SCORE_WIDTH = 1280  # cheap pass
DUPLICATE_DISTANCE = 14  # dHash bits; below this two frames are the same shot.
# Raised from 10 after a real card scan let two clips of the same house
# through as separate frames.
MIN_SCORE = 0.42  # below this a frame is not worth keeping


@dataclass
class MediaReport:
    source: Path
    client_id: str
    videos_found: int = 0
    photos_found: int = 0
    videos_processed: int = 0
    frames_sampled: int = 0
    frames_kept: int = 0
    duplicates_rejected: int = 0
    low_quality_rejected: int = 0
    photos_copied: int = 0
    errors: list[str] = field(default_factory=list)
    kept: list[FrameCandidate] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def summary(self) -> str:
        return (
            f"{self.videos_processed}/{self.videos_found} video(s) processed, "
            f"{self.frames_sampled} frame(s) sampled, {self.frames_kept} kept "
            f"({self.duplicates_rejected} duplicate, "
            f"{self.low_quality_rejected} low quality), "
            f"{self.photos_copied} photo(s) copied"
        )


def _destination(client_id: str) -> Path:
    return get_settings().paths.clients / client_id / "assets" / "raw"


def ingest_media(
    source: Path,
    client_id: str,
    per_video: int = 1,
    samples: int = 5,
    limit: int | None = None,
    copy_photos: bool = True,
    dry_run: bool = False,
    project: str = "",
) -> MediaReport:
    """Scan ``source`` and extract the best flyer-usable frames.

    ``per_video`` is how many frames to keep from each clip; ``samples`` is how
    many to look at before choosing.
    """
    report = MediaReport(source=source, client_id=client_id)

    if not ffmpeg_available():
        report.errors.append("ffmpeg/ffprobe not found. Install with: brew install ffmpeg")
        log.error(report.errors[-1])
        return report

    items = scan_directory(source, recursive=True)
    videos = [i for i in items if i.kind == "video"]
    photos = [i for i in items if i.kind == "photo"]
    report.videos_found = len(videos)
    report.photos_found = len(photos)

    if limit:
        videos = videos[:limit]

    frames_dir = _destination(client_id) / "frames"
    photos_dir = _destination(client_id) / "drone"

    seen_hashes: list[int] = []
    scratch = Path(tempfile.mkdtemp(prefix="flyer-frames-"))

    try:
        for index, item in enumerate(videos, start=1):
            probe_video(item)
            if item.error:
                report.errors.append(f"{item.path.name}: {item.error}")
                continue
            if item.duration_s <= 0:
                report.errors.append(f"{item.path.name}: zero duration")
                continue

            log.info(
                "[%d/%d] %s  %dx%d  %.0fs",
                index,
                len(videos),
                item.path.name,
                item.width,
                item.height,
                item.duration_s,
            )

            candidates = _score_clip(item, samples, scratch, report)
            if not candidates:
                continue

            kept_for_clip = 0
            for candidate in sorted(candidates, key=lambda c: c.total, reverse=True):
                if kept_for_clip >= per_video:
                    break
                if candidate.total < MIN_SCORE:
                    report.low_quality_rejected += 1
                    continue
                if any(hamming(candidate.phash, h) < DUPLICATE_DISTANCE for h in seen_hashes):
                    report.duplicates_rejected += 1
                    continue

                if not dry_run:
                    final = frames_dir / _frame_name(item.path, candidate.time_s, project)
                    # Extract at the largest size a flyer can actually use, not
                    # at capture resolution. A 4K frame is ~2 MB; at 2400px it
                    # is ~400 KB and a 1080x1350 crop is pixel-identical.
                    written = extract_frame(
                        item.path,
                        candidate.time_s,
                        final,
                        width=get_settings().asset_max_edge,
                    )
                    if written is None:
                        report.errors.append(f"{item.path.name}: full-resolution extract failed")
                        continue
                    candidate.path = written
                    _write_sidecar(written, item, candidate, client_id, project)

                seen_hashes.append(candidate.phash)
                report.kept.append(candidate)
                report.frames_kept += 1
                kept_for_clip += 1

            report.videos_processed += 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if copy_photos and not dry_run:
        report.photos_copied = _copy_photos(photos, photos_dir, project)

    log.info("Media ingestion complete: %s", report.summary())
    return report


def _score_clip(
    item: MediaItem,
    samples: int,
    scratch: Path,
    report: MediaReport,
) -> list[FrameCandidate]:
    """Pass one: cheap, downscaled frames scored for flyer suitability."""
    candidates: list[FrameCandidate] = []
    for time_s in sample_times(item.duration_s, samples):
        temp = scratch / f"{item.path.stem}_{time_s:.2f}.jpg"
        if extract_frame(item.path, time_s, temp, width=SCORE_WIDTH) is None:
            continue
        report.frames_sampled += 1
        try:
            with Image.open(temp) as image:
                rgb = image.convert("RGB")
                total, breakdown = score_frame(rgb)
                candidate = FrameCandidate(
                    source=item.path,
                    time_s=time_s,
                    scores=breakdown,
                    total=total,
                    phash=dhash(rgb),
                    width=item.width,
                    height=item.height,
                )
        except Exception as exc:
            report.errors.append(f"{item.path.name}@{time_s:.1f}s: {exc}")
            continue
        finally:
            temp.unlink(missing_ok=True)
        candidates.append(candidate)
    return candidates


def _frame_name(video: Path, time_s: float, project: str) -> str:
    prefix = f"{project}-" if project else ""
    return f"{prefix}{video.stem.lower()}_frame_{time_s:.0f}s.jpg"


def _write_sidecar(
    frame: Path,
    item: MediaItem,
    candidate: FrameCandidate,
    client_id: str,
    project: str,
) -> None:
    """Provenance travels with the frame, so nothing has to be inferred later."""
    settings = get_settings()
    sidecar = frame.with_suffix(".json")
    payload = {
        "provenance": {
            "source_type": "client_frame",
            "approval_status": "unapproved",
            "origin_path": str(item.path),
            "project": project,
            "source_video": item.path.name,
            "frame_time_s": candidate.time_s,
            "verified_by": "media-ingest",
            "notes": (
                f"Extracted from {item.width}x{item.height} footage. Quality {candidate.total:.2f}."
            ),
        },
        "quality_score": candidate.total,
        "client_id": client_id,
    }
    try:
        sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        log.warning("Could not write sidecar for %s: %s", frame.name, exc)
    _ = settings


def _copy_photos(photos: list[MediaItem], destination: Path, project: str) -> int:
    """Real stills are copied verbatim; they need no extraction."""
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in photos:
        prefix = f"{project}-" if project else ""
        target = destination / f"{prefix}{item.path.name.lower()}"
        if target.exists():
            continue
        try:
            shutil.copy2(item.path, target)
            copied += 1
        except OSError as exc:
            log.warning("Could not copy %s: %s", item.path.name, exc)
    return copied
