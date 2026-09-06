"""Real-media ingestion: drives and SD cards into a production asset library.

    DISCOVER -> PROBE -> SAMPLE -> SCORE -> DEDUPE -> EXTRACT -> CLASSIFY -> INDEX

Deliberately a separate, explicit step rather than something the daily flyer run
does. Rescanning 50 GB of drone footage every morning would be slow, expensive
and pointless; you run this when a new card or project folder arrives.

Nothing this module produces is production-eligible on its own. Extracted
frames land as ``client_frame`` / unapproved and need review, exactly like any
other real-but-unvetted media.
"""

from .frames import FrameCandidate, score_frame
from .ingest import MediaReport, ingest_media
from .probe import MediaItem, probe_video, scan_directory

__all__ = [
    "FrameCandidate",
    "MediaItem",
    "MediaReport",
    "ingest_media",
    "probe_video",
    "scan_directory",
    "score_frame",
]
