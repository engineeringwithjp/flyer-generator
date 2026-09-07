"""Photo finishing - the grade that separates raw drone capture from a flyer.

Nothing here invents pixels. The source photography already out-resolves the
canvas (drone stills are 4056x3040 against a 2160x2700 flyer), so the problem
was never resolution, it was *finishing*: straight-out-of-camera drone frames
are deliberately flat. DJI records a low-contrast, low-saturation image so
there is room to grade later, and if you never grade it, the flyer looks
washed out no matter how many pixels it has.

So this module does what a colourist does, in the same order:

1. **Black and white point** - stretch the histogram so the darkest and
   brightest few tenths of a percent land near the ends of the range. This is
   the single biggest improvement; it removes atmospheric haze, which every
   aerial shot has.
2. **Shadow recovery** - roofs are dark, and shingle texture lives in the
   shadows. Step 1 deepens blacks, so a little is given back to keep the
   product visible.
3. **Contrast** - a tapered S-curve, which adds punch through the midtones
   without clipping either end.
4. **Clarity** - a wide-radius unsharp mask. This is local contrast, not
   sharpening; it is what makes shingle courses and siding lines read.
5. **Vibrance** - saturation weighted so muted colours gain the most and
   already-vivid ones (a blue sky, the brand red) are left alone.
6. **Output sharpening** - a narrow-radius pass applied *after* the photo has
   been resized into its panel, because sharpening is only correct at final
   size.

Every operation is a pure function of the pixels, so the same asset always
finishes to the same bytes and the renderer stays deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from PIL import Image, ImageFilter, ImageStat

from ..logging_setup import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class Grade:
    """A finishing recipe. Amounts are 0..1 unless noted."""

    black_point: float = 0.004  # fraction of pixels allowed to clip to black
    white_point: float = 0.002  # fraction allowed to clip to white
    shadow_recovery: float = 0.16
    highlight_rolloff: float = 0.06
    contrast: float = 0.16
    clarity: float = 0.34
    clarity_radius: float = 0.012  # fraction of the long edge
    vibrance: float = 0.22
    warmth: float = 0.0  # >0 warms, <0 cools; in 0..1 of a full channel step
    output_sharpen: float = 0.55


#: The house grade. Measured against All Elite's own drone footage rather than
#: chosen from taste: these amounts take a typical DJI frame to roughly the
#: contrast and saturation of the client-approved reference flyers without
#: tipping into the over-processed HDR look that reads as amateur.
HOUSE = Grade()

#: A restrained grade for photography that is already finished - phone photos,
#: anything a client has edited - where the house grade would double-process.
LIGHT = Grade(
    black_point=0.001,
    white_point=0.0005,
    shadow_recovery=0.08,
    contrast=0.06,
    clarity=0.16,
    vibrance=0.10,
    output_sharpen=0.40,
)

GRADES: dict[str, Grade] = {
    "house": HOUSE,
    "light": LIGHT,
    "none": Grade(
        black_point=0.0,
        white_point=0.0,
        shadow_recovery=0.0,
        highlight_rolloff=0.0,
        contrast=0.0,
        clarity=0.0,
        vibrance=0.0,
        output_sharpen=0.0,
    ),
}


# ----------------------------------------------------------------- measuring


@dataclass(frozen=True)
class Stats:
    """What the image is currently doing, before anything is applied."""

    mean: float  # 0..1 luma
    spread: float  # 0..1 luma standard deviation
    black_level: float  # 0..1, where the shadows actually start
    white_level: float  # 0..1, where the highlights actually end
    saturation: float  # 0..1 mean saturation

    @property
    def is_flat(self) -> bool:
        """A hazy, ungraded capture: narrow range and low separation."""
        return (self.white_level - self.black_level) < 0.80 or self.spread < 0.20


def measure(image: Image.Image) -> Stats:
    """Read the histogram. Sampling a thumbnail keeps this cheap and stable."""
    sample = image.convert("RGB")
    sample.thumbnail((512, 512), Image.Resampling.BILINEAR)
    luma = sample.convert("L")

    histogram = luma.histogram()
    total = sum(histogram) or 1
    black = _percentile(histogram, total, 0.004)
    white = _percentile(histogram, total, 1.0 - 0.002)

    stat = ImageStat.Stat(luma)
    saturation = ImageStat.Stat(sample.convert("HSV").getchannel("S")).mean[0] / 255.0

    return Stats(
        mean=stat.mean[0] / 255.0,
        spread=stat.stddev[0] / 255.0,
        black_level=black / 255.0,
        white_level=white / 255.0,
        saturation=saturation,
    )


def _percentile(histogram: list[int], total: int, fraction: float) -> int:
    """The intensity below which ``fraction`` of the pixels fall."""
    target = total * fraction
    running = 0
    for value, count in enumerate(histogram):
        running += count
        if running >= target:
            return value
    return 255


def adapt(grade: Grade, stats: Stats) -> Grade:
    """Scale a grade to the individual frame.

    A uniform recipe over-processes an image that was already contrasty and
    under-processes a hazy one. Amounts are therefore scaled by how much
    headroom the frame actually has, which is why two shots of the same roof on
    different days come out looking like the same flyer.
    """
    if grade is GRADES["none"]:
        return grade

    # Headroom: 1.0 for a completely flat frame, 0.0 for one already using the
    # full range with strong separation.
    range_used = max(stats.white_level - stats.black_level, 0.0)
    headroom = _clamp(1.0 - range_used, 0.0, 1.0)
    flatness = _clamp((0.26 - stats.spread) / 0.26, 0.0, 1.0)
    push = _clamp(0.45 + 0.85 * max(headroom, flatness), 0.45, 1.35)

    # Saturated frames need less vibrance; muted ones need more.
    sat_push = _clamp((0.42 - stats.saturation) / 0.42, -0.4, 1.0)

    # An underexposed frame needs more shadow recovery, an bright one less.
    exposure_gap = _clamp((0.46 - stats.mean) / 0.46, -0.5, 1.0)

    return replace(
        grade,
        shadow_recovery=_clamp(grade.shadow_recovery * (1.0 + exposure_gap), 0.0, 0.42),
        contrast=_clamp(grade.contrast * push, 0.0, 0.34),
        clarity=_clamp(grade.clarity * push, 0.0, 0.60),
        vibrance=_clamp(grade.vibrance * (1.0 + sat_push), 0.0, 0.45),
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


# ------------------------------------------------------------------ the pass


def finish(image: Image.Image, grade: Grade | str = HOUSE, adaptive: bool = True) -> Image.Image:
    """Grade a photograph. Call this before the photo is resized into a panel.

    Returns a new RGB image; the input is not modified.
    """
    recipe = GRADES.get(grade, HOUSE) if isinstance(grade, str) else grade
    result = image.convert("RGB")

    if adaptive:
        recipe = adapt(recipe, measure(result))

    result = _apply_tone(result, recipe)
    result = _apply_clarity(result, recipe)
    result = _apply_vibrance(result, recipe)
    result = _apply_warmth(result, recipe)
    return result


def sharpen_output(image: Image.Image, grade: Grade | str = HOUSE) -> Image.Image:
    """Sharpen at final size. Sharpening before a resize throws the work away."""
    recipe = GRADES.get(grade, HOUSE) if isinstance(grade, str) else grade
    if recipe.output_sharpen <= 0:
        return image
    # Radius stays at one pixel: this is acutance for the viewer's screen, not
    # local contrast, which step 4 already handled at source resolution.
    return image.filter(
        ImageFilter.UnsharpMask(
            radius=1.0, percent=int(round(recipe.output_sharpen * 100)), threshold=3
        )
    )


# ----------------------------------------------------------------- the steps


def _apply_tone(image: Image.Image, grade: Grade) -> Image.Image:
    """Black/white point, shadow recovery, highlight rolloff and the S-curve.

    All four collapse into a single 256-entry lookup table applied identically
    to every channel, which is what keeps colour neutral. Doing them as
    separate passes would quantise the image three extra times.
    """
    luma = image.convert("L")
    luma.thumbnail((512, 512), Image.Resampling.BILINEAR)
    histogram = luma.histogram()
    total = sum(histogram) or 1

    lo = _percentile(histogram, total, grade.black_point) if grade.black_point > 0 else 0
    hi = _percentile(histogram, total, 1.0 - grade.white_point) if grade.white_point > 0 else 255
    # Never stretch so hard that a legitimately low-contrast frame is destroyed.
    if hi - lo < 32:
        lo, hi = 0, 255

    table: list[int] = []
    span = float(hi - lo)
    for value in range(256):
        x = _clamp((value - lo) / span, 0.0, 1.0)

        # Give back some of the shadow detail the stretch just crushed. The
        # weight peaks in the low midtones so true blacks stay black.
        x += grade.shadow_recovery * (1.0 - x) ** 3 * (x**0.5)
        # Ease the shoulder so bright siding holds detail instead of clipping.
        # The term is zero at both ends and peaks around three-quarter tone, so
        # it softens the approach to white without lowering white itself - a
        # rolloff that dims the white point just makes the photo look grey.
        x -= grade.highlight_rolloff * (x**3 * (1.0 - x)) / 0.1055

        # Tapered S-curve: strongest at the midpoint, zero at both ends, so it
        # adds punch without ever pushing a value out of range.
        x += grade.contrast * (x - 0.5) * (1.0 - abs(2.0 * x - 1.0))

        table.append(int(round(_clamp(x, 0.0, 1.0) * 255)))

    return image.point(table * 3)


def _apply_clarity(image: Image.Image, grade: Grade) -> Image.Image:
    """Wide-radius unsharp: local contrast, which reads as texture and depth."""
    if grade.clarity <= 0:
        return image
    radius = max(2.0, max(image.size) * grade.clarity_radius)
    # Applied to luminance only. Running it on RGB pushes coloured halos into
    # the roofline against the sky, which is exactly where they are visible.
    graded = image.convert("YCbCr")
    y, cb, cr = graded.split()
    y = y.filter(
        ImageFilter.UnsharpMask(radius=radius, percent=int(round(grade.clarity * 100)), threshold=2)
    )
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")


def _apply_vibrance(image: Image.Image, grade: Grade) -> Image.Image:
    """Saturation weighted toward muted colours.

    A flat multiply on saturation blows out whatever was already vivid - the
    sky, the brand red - while barely touching the grey-green of a weathered
    roof. Weighting the gain by how unsaturated a pixel already is fixes both
    ends at once.
    """
    if grade.vibrance <= 0:
        return image
    hsv = image.convert("HSV")
    h, s, v = hsv.split()

    table = []
    for value in range(256):
        current = value / 255.0
        # Gain falls off as the pixel approaches full saturation.
        gain = 1.0 + grade.vibrance * (1.0 - current) ** 1.5
        table.append(int(round(_clamp(current * gain, 0.0, 1.0) * 255)))

    return Image.merge("HSV", (h, s.point(table), v)).convert("RGB")


def _apply_warmth(image: Image.Image, grade: Grade) -> Image.Image:
    """A small colour-temperature nudge, off by default."""
    if abs(grade.warmth) < 1e-6:
        return image
    shift = int(round(grade.warmth * 18))
    r, g, b = image.split()
    up = [min(255, i + shift) for i in range(256)]
    down = [max(0, i - shift) for i in range(256)]
    return Image.merge("RGB", (r.point(up), g, b.point(down)))
