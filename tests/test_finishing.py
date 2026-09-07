"""The photo grade, and the properties it must hold."""

from __future__ import annotations

from PIL import Image, ImageDraw

from app.rendering import finishing


def _hazy(size=(400, 300)) -> Image.Image:
    """A flat, low-contrast frame - what an ungraded drone still looks like."""
    image = Image.new("RGB", size, (120, 128, 132))
    draw = ImageDraw.Draw(image)
    for i in range(0, size[0], 7):
        shade = 108 + (i // 7) % 24
        draw.line([(i, 0), (i, size[1])], fill=(shade, shade + 4, shade + 8))
    draw.rectangle([60, 60, 220, 190], fill=(96, 100, 104))
    draw.rectangle([240, 90, 340, 210], fill=(140, 144, 146))
    return image


def test_the_grade_opens_up_a_flat_frame():
    """Black point down, white point up: the point of the whole module."""
    source = _hazy()
    before = finishing.measure(source)
    after = finishing.measure(finishing.finish(source))

    assert after.black_level < before.black_level
    assert after.white_level > before.white_level
    assert after.spread > before.spread


def test_the_grade_does_not_grey_out_the_whites():
    """A highlight rolloff that lowers the white point just looks washed out.

    This is the regression guard for the first version, where the rolloff term
    was largest at pure white and pulled a 0.95 white point down to 0.92.
    """
    source = _hazy()
    after = finishing.measure(finishing.finish(source))
    assert after.white_level > 0.9


def test_grading_is_deterministic():
    """Same asset in, same bytes out - the renderer depends on this."""
    source = _hazy()
    assert finishing.finish(source).tobytes() == finishing.finish(source).tobytes()


def test_the_none_grade_leaves_the_image_alone():
    source = _hazy()
    assert finishing.finish(source, "none").tobytes() == source.convert("RGB").tobytes()


def test_an_already_punchy_frame_is_graded_less_than_a_flat_one():
    """Adaptive, or every graded photo ends up looking over-processed."""
    flat = finishing.measure(_hazy())

    punchy = _hazy()
    punchy = finishing.finish(punchy)  # already graded once
    punchy_stats = finishing.measure(punchy)

    flat_recipe = finishing.adapt(finishing.HOUSE, flat)
    punchy_recipe = finishing.adapt(finishing.HOUSE, punchy_stats)
    assert punchy_recipe.clarity <= flat_recipe.clarity
    assert punchy_recipe.vibrance <= flat_recipe.vibrance


def test_the_grade_never_produces_out_of_range_pixels():
    source = _hazy()
    graded = finishing.finish(source)
    extremes = graded.convert("L").getextrema()
    assert 0 <= extremes[0] <= extremes[1] <= 255
