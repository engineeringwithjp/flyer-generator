#!/usr/bin/env python3
"""Measure frame-score distributions across real footage.

The constants in ``app/media/frames.py`` were derived from this. Re-run it if
the camera changes or the footage starts looking different, and update the
constants so the ranking keeps discriminating instead of saturating at 1.0.

    python scripts/calibrate_frames.py /Volumes/Untitled/DCIM/101MEDIA --clips 20
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from app.media.frames import centre_crop_to_flyer, sample_times
from app.media.probe import probe_video, scan_directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--clips", type=int, default=14)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()

    videos = [i for i in scan_directory(args.source) if i.kind == "video"][: args.clips]
    scratch = Path(tempfile.mkdtemp())
    measures: dict[str, list[float]] = {
        "edge stddev": [],
        "luminance": [],
        "global stddev": [],
        "calmest band": [],
    }

    for item in videos:
        probe_video(item)
        if item.duration_s <= 0:
            continue
        for time_s in sample_times(item.duration_s, args.samples):
            out = scratch / f"{item.path.stem}_{time_s:.1f}.jpg"
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-y",
                    "-ss",
                    str(time_s),
                    "-i",
                    str(item.path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=1280:-2",
                    "-q:v",
                    "2",
                    str(out),
                ],
                capture_output=True,
                timeout=60,
            )
            if not out.exists():
                continue
            with Image.open(out) as image:
                grey = centre_crop_to_flyer(image.convert("RGB")).convert("L")
            measures["edge stddev"].append(
                ImageStat.Stat(grey.filter(ImageFilter.FIND_EDGES)).stddev[0]
            )
            measures["luminance"].append(ImageStat.Stat(grey).mean[0] / 255)
            measures["global stddev"].append(ImageStat.Stat(grey).stddev[0])
            width, height = grey.size
            measures["calmest band"].append(
                min(
                    ImageStat.Stat(grey.crop((0, int(a * height), width, int(b * height)))).stddev[
                        0
                    ]
                    for a, b in ((0, 0.34), (0.62, 1.0))
                )
            )
            out.unlink(missing_ok=True)

    for name, values in measures.items():
        if not values:
            continue
        values.sort()
        print(
            f"{name:<16} n={len(values):<4} min={values[0]:7.2f} "
            f"p25={values[len(values) // 4]:7.2f} med={statistics.median(values):7.2f} "
            f"p75={values[3 * len(values) // 4]:7.2f} max={values[-1]:7.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
