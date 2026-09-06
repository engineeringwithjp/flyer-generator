"""Frame sampling, quality scoring and near-duplicate rejection.

A flyer frame is not "the first frame". It has to survive a giant headline laid
over it at 1080x1350, so scoring targets exactly that: is it sharp, is it
correctly exposed, and is there somewhere calm to put type?

Everything here is deterministic and dependency-free beyond Pillow, so the same
footage always yields the same frames and CI can run it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from ..logging_setup import get_logger

log = get_logger(__name__)

# Weights for the composite score. Sharpness dominates: a blurred frame is
# unusable no matter how well composed it is.
WEIGHTS = {
    "sharpness": 0.34,
    "exposure": 0.22,
    "contrast": 0.18,
    "negative_space": 0.18,
    "detail_balance": 0.08,
}

# A 4:5 flyer crops hard from 16:9 footage, so score the region that will
# actually survive the crop rather than the whole frame.
FLYER_ASPECT = 1080 / 1350

# Calibration measured from 42 sampled frames of this client's own 4K drone
# footage, not guessed. Guessed constants made every frame score 1.00 and the
# ranking useless. Re-measure with scripts/calibrate_frames.py if the camera
# or the kind of footage changes.
#
#                    min    p25    med    p75    max
#   edge stddev     33.2   56.8   61.5   65.6   75.9
#   luminance       0.32   0.45   0.48   0.52   0.71
#   global stddev   22.8   55.5   63.1   68.2   80.1
#   calmest band    15.9   49.4   55.9   60.0   67.8
SHARPNESS_FLOOR, SHARPNESS_CEIL = 30.0, 76.0
CONTRAST_FLOOR, CONTRAST_CEIL = 25.0, 80.0
CALM_BEST, CALM_WORST = 16.0, 68.0
EXPOSURE_IDEAL, EXPOSURE_TOLERANCE = 0.47, 0.16


@dataclass
class FrameCandidate:
    source: Path
    time_s: float
    scores: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    phash: int = 0
    width: int = 0
    height: int = 0
    path: Path | None = None

    @property
    def label(self) -> str:
        return f"{self.source.stem}@{self.time_s:.1f}s"


def centre_crop_to_flyer(image: Image.Image) -> Image.Image:
    """The 4:5 region a flyer would actually use."""
    width, height = image.size
    target_width = int(height * FLYER_ASPECT)
    if target_width <= width:
        left = (width - target_width) // 2
        return image.crop((left, 0, left + target_width, height))
    target_height = int(width / FLYER_ASPECT)
    top = (height - target_height) // 2
    return image.crop((0, top, width, top + target_height))


def _normalise(value: float, floor: float, ceiling: float) -> float:
    """Map a measured value onto 0..1 across its observed useful range."""
    if ceiling <= floor:
        return 0.0
    return min(max((value - floor) / (ceiling - floor), 0.0), 1.0)


def _sharpness(grey: Image.Image) -> float:
    """Edge energy. The best cheap proxy for motion blur."""
    edges = grey.filter(ImageFilter.FIND_EDGES)
    return _normalise(ImageStat.Stat(edges).stddev[0], SHARPNESS_FLOOR, SHARPNESS_CEIL)


def _exposure(grey: Image.Image) -> float:
    """Penalise crushed shadows and blown highlights.

    A smooth falloff rather than a flat pass band, so two correctly exposed
    frames can still be ranked against each other.
    """
    mean = ImageStat.Stat(grey).mean[0] / 255.0
    return max(0.0, 1.0 - abs(mean - EXPOSURE_IDEAL) / EXPOSURE_TOLERANCE)


def _contrast(grey: Image.Image) -> float:
    return _normalise(ImageStat.Stat(grey).stddev[0], CONTRAST_FLOOR, CONTRAST_CEIL)


def _negative_space(grey: Image.Image) -> float:
    """Is there a calm band for the headline?

    Checks the upper and lower thirds, which is where every layout puts type.
    Aerial footage is busy everywhere, so this is scored relative to how calm
    such footage actually gets, not against an absolute ideal.
    """
    width, height = grey.size
    calmest = min(
        ImageStat.Stat(grey.crop((0, int(top * height), width, int(bottom * height)))).stddev[0]
        for top, bottom in ((0.0, 0.34), (0.62, 1.0))
    )
    # Inverted: a low standard deviation is a calm band.
    return _normalise(CALM_WORST - calmest, 0.0, CALM_WORST - CALM_BEST)


def _detail_balance(grey: Image.Image) -> float:
    """Reject frames that are almost entirely sky or almost entirely roof."""
    edges = grey.filter(ImageFilter.FIND_EDGES)
    width, height = edges.size
    thirds = [
        ImageStat.Stat(edges.crop((0, int(i * height / 3), width, int((i + 1) * height / 3)))).mean[
            0
        ]
        for i in range(3)
    ]
    total = sum(thirds) or 1.0
    shares = [t / total for t in thirds]
    # Perfectly even is 1/3 each; score falls off with imbalance.
    spread = sum(abs(share - 1 / 3) for share in shares)
    return max(0.0, 1.0 - spread)


def dhash(image: Image.Image, size: int = 8) -> int:
    """Perceptual hash for near-duplicate rejection.

    Drone footage hovers, so consecutive samples are often the same shot.
    """
    small = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    # get_flattened_data() replaces the deprecated getdata() in Pillow 11+.
    reader = getattr(small, "get_flattened_data", None)
    pixels = list(reader()) if callable(reader) else list(small.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = pixels[row * (size + 1) + col]
            right = pixels[row * (size + 1) + col + 1]
            bits = (bits << 1) | int(left > right)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def score_frame(image: Image.Image) -> tuple[float, dict[str, float]]:
    """Composite 0..1 suitability score for one frame, plus the breakdown."""
    cropped = centre_crop_to_flyer(image)
    grey = cropped.convert("L")

    scores = {
        "sharpness": _sharpness(grey),
        "exposure": _exposure(grey),
        "contrast": _contrast(grey),
        "negative_space": _negative_space(grey),
        "detail_balance": _detail_balance(grey),
    }
    total = sum(WEIGHTS[key] * value for key, value in scores.items())
    return round(total, 4), {k: round(v, 4) for k, v in scores.items()}


def extract_frame(
    video: Path,
    time_s: float,
    output: Path,
    width: int | None = None,
    timeout: int = 60,
) -> Path | None:
    """Pull a single frame. ``-ss`` before ``-i`` keeps the seek fast."""
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-ss",
        f"{time_s:.3f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
    ]
    if width:
        command += ["-vf", f"scale={width}:-2"]
    command += ["-q:v", "2", str(output)]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log.warning("Frame extraction timed out: %s @ %.1fs", video.name, time_s)
        return None
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        return None
    return output


def sample_times(duration_s: float, count: int) -> list[float]:
    """Evenly spaced sample points, avoiding the first and last moments.

    Drone clips almost always begin and end with takeoff, landing or a hand in
    frame, so the edges are skipped.
    """
    if duration_s <= 0:
        return [0.0]
    start = min(max(duration_s * 0.12, 0.5), duration_s / 2)
    end = max(duration_s * 0.88, start)
    if count <= 1:
        return [(start + end) / 2]
    step = (end - start) / (count - 1)
    return [round(start + step * i, 3) for i in range(count)]
