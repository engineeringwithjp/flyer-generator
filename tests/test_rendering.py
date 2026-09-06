"""Renderer determinism, text fitting, contrast and every layout."""

from __future__ import annotations

import pytest
from PIL import Image, ImageStat

from app.models import CanvasSpec, FlyerCopy, FlyerSpecification, ImageSpec, LayoutSpec
from app.rendering.composition import (
    Grid,
    contrast_ratio,
    hex_to_rgb,
    relative_luminance,
    rgb_to_hex,
)
from app.rendering.export import export_flyer, thumbnail
from app.rendering.renderer import render_flyer, resolve_render_context
from app.rendering.templates import LAYOUT_BUILDERS, assert_layouts_registered, list_layouts
from app.rendering.typography import FontLibrary, fit_text, list_pairings, wrap_text

LAYOUTS = sorted(LAYOUT_BUILDERS)


def _spec(layout: str = "hero-full", **overrides) -> FlyerSpecification:
    payload = {
        "id": f"test_{layout}",
        "client_id": "testco",
        "campaign_id": "roof-replacement",
        "service": "roofing",
        "canvas": CanvasSpec(),
        "layout": LayoutSpec(name=layout),
        "image": ImageSpec(),
        "text": FlyerCopy(
            eyebrow="Bergen County",
            headline="Your Roof Deserves Better",
            support="Roof replacement for Bergen County homeowners",
            bullets=["Licensed & insured New Jersey contractor"],
            cta="Get A Free Estimate",
        ),
        "palette": {
            "primary": "#12243A",
            "accent": "#E0A62F",
            "ink": "#111111",
            "paper": "#FFFFFF",
            "on_image": "#FFFFFF",
        },
    }
    payload.update(overrides)
    return FlyerSpecification.model_validate(payload)


# ------------------------------------------------------------------- colour


def test_hex_round_trip():
    assert rgb_to_hex(hex_to_rgb("#1A2B3C")) == "#1A2B3C"


def test_short_hex_expands():
    assert hex_to_rgb("#abc") == hex_to_rgb("#aabbcc")


def test_invalid_hex_raises():
    with pytest.raises(ValueError):
        hex_to_rgb("#12345")


def test_luminance_bounds():
    assert relative_luminance("#000000") == pytest.approx(0.0, abs=1e-6)
    assert relative_luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-6)


def test_contrast_extremes():
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#808080", "#808080") == pytest.approx(1.0, abs=0.01)


# --------------------------------------------------------------------- grid


def test_grid_margins_are_inside_the_canvas():
    grid = Grid(1080, 1350)
    assert 0 < grid.left < grid.right < 1080
    assert 0 < grid.top < grid.bottom < 1350
    assert grid.content_width > 800


def test_grid_scales_with_the_canvas():
    assert Grid(2160, 2700).scale(100) == 200


# --------------------------------------------------------------- typography


def test_text_always_fits_its_box(repo):
    fonts = FontLibrary()
    fitted = fit_text(
        "A deliberately very long headline that could never fit on one line",
        fonts,
        "display",
        800,
        300,
        120,
        20,
    )
    assert fitted.width <= 800
    assert fitted.height <= 300


def test_a_single_unbreakable_word_is_hard_wrapped(repo):
    fonts = FontLibrary()
    font = fonts.get("body", 40)
    lines = wrap_text("Supercalifragilisticexpialidocious" * 3, font, 200)
    assert len(lines) > 1


def test_empty_text_produces_no_lines(repo):
    assert fit_text("", FontLibrary(), "body", 500, 100, 40).lines == []


def test_max_lines_is_respected(repo):
    fitted = fit_text(
        "one two three four five six seven eight nine ten",
        FontLibrary(),
        "body",
        260,
        900,
        40,
        12,
        max_lines=2,
    )
    assert len(fitted.lines) <= 2


def test_every_pairing_resolves_a_font(repo):
    for pairing in list_pairings():
        library = FontLibrary(pairing=pairing)
        assert library.get("display", 60) is not None
        assert library.get("body", 24) is not None


def test_pairings_differ_when_the_fonts_are_present(repo):
    library = FontLibrary()
    if not library.available():
        pytest.skip("no fonts installed; run scripts/fetch_fonts.py")
    a = FontLibrary(pairing="condensed-editorial")._resolve_path("display", True)
    b = FontLibrary(pairing="serif-editorial")._resolve_path("display", True)
    assert a != b


# ------------------------------------------------------------------ layouts


def test_config_and_code_agree_on_the_layout_set(repo):
    assert_layouts_registered()
    assert set(list_layouts()) == set(LAYOUTS)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_layout_renders_at_the_exact_canvas_size(repo, client, layout):
    image, _ = render_flyer(_spec(layout), resolve_render_context(client, {}))
    assert image.size == (1080, 1350)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_layout_produces_a_non_blank_flyer(repo, client, layout):
    image, _ = render_flyer(_spec(layout), resolve_render_context(client, {}))
    assert ImageStat.Stat(image.convert("L")).stddev[0] > 10


@pytest.mark.parametrize("layout", LAYOUTS)
def test_rendering_is_deterministic(repo, client, layout):
    context = resolve_render_context(client, {})
    first, _ = render_flyer(_spec(layout), context)
    second, _ = render_flyer(_spec(layout), context)
    assert first.tobytes() == second.tobytes()


def test_an_unknown_layout_raises(repo, client):
    from app.errors import RenderError

    with pytest.raises(RenderError, match="Unknown layout"):
        render_flyer(_spec("no-such-layout"), resolve_render_context(client, {}))


@pytest.mark.parametrize("size", [(1080, 1350), (1080, 1080), (1200, 628), (1080, 1920)])
def test_alternate_canvas_sizes_render(repo, client, size):
    spec = _spec("banner-lower-third", canvas=CanvasSpec(width=size[0], height=size[1]))
    image, _ = render_flyer(spec, resolve_render_context(client, {}))
    assert image.size == size


def test_missing_asset_falls_back_to_a_procedural_background(repo, client):
    spec = _spec("hero-full", image=ImageSpec(asset_id="does-not-exist"))
    image, _ = render_flyer(spec, resolve_render_context(client, {}))
    assert ImageStat.Stat(image.convert("L")).stddev[0] > 5


def test_a_real_photo_is_actually_used(repo, client):
    from app.assets.catalog import AssetCatalog

    catalog = AssetCatalog.load(refresh=True)
    asset = next(a for a in catalog.index.assets if a.service == "roofing")
    paths = {asset.id: repo / asset.path}
    with_photo, _ = render_flyer(
        _spec("hero-full", image=ImageSpec(asset_id=asset.id, overlay="none")),
        resolve_render_context(client, paths),
    )
    without, _ = render_flyer(
        _spec("hero-full", image=ImageSpec(overlay="none")),
        resolve_render_context(client, {}),
    )
    assert with_photo.tobytes() != without.tobytes()


def test_a_long_headline_never_overflows(repo, client):
    spec = _spec("hero-full")
    spec.text.headline = "Protect Your Home Before Winter Arrives"
    image, warnings = render_flyer(spec, resolve_render_context(client, {}))
    assert image.size == (1080, 1350)


def test_the_contact_bar_disappears_when_there_is_no_contact(repo, client):
    silent = client.model_copy(deep=True)
    silent.contact.phone = ""
    silent.contact.website = ""
    silent.contact.email = ""
    a, _ = render_flyer(_spec("hero-full"), resolve_render_context(client, {}))
    b, _ = render_flyer(_spec("hero-full"), resolve_render_context(silent, {}))
    assert a.tobytes() != b.tobytes()


def test_heavier_overlay_darkens_the_flyer(repo, client):
    light, _ = render_flyer(
        _spec("hero-full", image=ImageSpec(overlay="dark_flat", overlay_strength=0.2)),
        resolve_render_context(client, {}),
    )
    heavy, _ = render_flyer(
        _spec("hero-full", image=ImageSpec(overlay="dark_flat", overlay_strength=0.85)),
        resolve_render_context(client, {}),
    )
    assert ImageStat.Stat(heavy.convert("L")).mean[0] < ImageStat.Stat(light.convert("L")).mean[0]


# ------------------------------------------------------------------- export


def test_png_export_writes_a_valid_file(repo, client, tmp_path):
    image, _ = render_flyer(_spec(), resolve_render_context(client, {}))
    path = export_flyer(image, tmp_path / "out.png", "PNG")
    assert path.stat().st_size > 10_000
    with Image.open(path) as written:
        assert written.size == (1080, 1350) and written.format == "PNG"


def test_jpeg_export_works(repo, client, tmp_path):
    image, _ = render_flyer(_spec(), resolve_render_context(client, {}))
    path = export_flyer(image, tmp_path / "out.jpg", "JPEG")
    with Image.open(path) as written:
        assert written.format == "JPEG"


def test_unsupported_format_raises(repo, client, tmp_path):
    from app.errors import RenderError

    image, _ = render_flyer(_spec(), resolve_render_context(client, {}))
    with pytest.raises(RenderError):
        export_flyer(image, tmp_path / "out.gif", "GIF")


def test_thumbnail_is_smaller_and_proportional(repo, client, tmp_path):
    image, _ = render_flyer(_spec(), resolve_render_context(client, {}))
    full = export_flyer(image, tmp_path / "out.png", "PNG")
    thumb = thumbnail(full, tmp_path / "thumbs" / "out.jpg", width=480)
    with Image.open(thumb) as small:
        assert small.width == 480
        assert small.height == pytest.approx(600, abs=2)
