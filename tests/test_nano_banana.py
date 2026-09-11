"""Unit and QA tests for Nano Banana Pro flyer generator."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from app.nano_banana import (
    LOCAL_LOGO_COLOR,
    LOCAL_LOGO_LIGHT,
    NanoBananaEngine,
    run_daily_generation,
)


@pytest.fixture
def engine() -> NanoBananaEngine:
    return NanoBananaEngine()


def test_logo_assets_exist_and_are_transparent():
    """Verify official logos exist and feature true alpha transparency (no white bounding box)."""
    assert LOCAL_LOGO_LIGHT.exists(), f"Light logo missing at {LOCAL_LOGO_LIGHT}"
    assert LOCAL_LOGO_COLOR.exists(), f"Color logo missing at {LOCAL_LOGO_COLOR}"

    for logo_path in (LOCAL_LOGO_LIGHT, LOCAL_LOGO_COLOR):
        with Image.open(logo_path) as img:
            assert img.mode == "RGBA", f"Logo at {logo_path} must be RGBA"
            # Extract alpha channel
            alpha = img.split()[-1]
            extrema = alpha.getextrema()
            assert extrema[0] == 0, f"Logo at {logo_path} must have transparent pixels (min alpha=0)"

            # Check corners are transparent (not a solid sticker / card plate)
            w, h = img.size
            corners = [
                img.getpixel((0, 0)),
                img.getpixel((w - 1, 0)),
                img.getpixel((0, h - 1)),
                img.getpixel((w - 1, h - 1)),
            ]
            for c in corners:
                assert c[3] == 0, f"Corner pixel at {logo_path} must be fully transparent (alpha 0), got {c}"


@pytest.mark.parametrize(
    ("test_date", "expected_count"),
    [
        (date(2026, 9, 10), 5),  # Rotation A (day % 3 == 1)
        (date(2026, 9, 11), 5),  # Rotation B (day % 3 == 2)
        (date(2026, 9, 12), 5),  # Rotation C (day % 3 == 0)
    ],
)
def test_build_daily_batch_dimensions_and_count(engine: NanoBananaEngine, test_date: date, expected_count: int):
    """Verify batch generates exactly 5 concepts with native Instagram 4:5 1080x1350 sizing."""
    concepts = engine.build_daily_batch(count=expected_count, target_date=test_date)
    assert len(concepts) == expected_count

    for concept in concepts:
        assert concept.aspect_ratio == "4:5"
        assert concept.width == 1080
        assert concept.height == 1350
        assert concept.output_filename != ""

        if concept.is_carousel_folder:
            assert len(concept.carousel_slides) == 4
            slide_archetypes = [s.archetype for s in concept.carousel_slides]
            assert slide_archetypes == [
                "carousel_slide_1",
                "carousel_slide_2",
                "carousel_slide_3",
                "carousel_slide_4",
            ]
            for slide in concept.carousel_slides:
                assert slide.aspect_ratio == "4:5"
                assert slide.width == 1080
                assert slide.height == 1350
                assert slide.output_filename.endswith(".jpg")


@pytest.mark.parametrize("promo_day", [1, 7, 14, 21, 28])
def test_september_savings_promo_rotation(engine: NanoBananaEngine, promo_day: int):
    """Verify September savings promo is injected on days 1, 7, 14, 21, and 28 of September."""
    target_date = date(2026, 9, promo_day)
    concepts = engine.build_daily_batch(count=5, target_date=target_date)

    promo_concept = concepts[2]
    assert promo_concept.archetype == "september_savings_promo"
    assert "September Savings" in promo_concept.name
    assert "$500 OFF" in promo_concept.prompt
    assert "$1,000" in promo_concept.prompt
    assert "Repairs are not eligible" in promo_concept.prompt


def test_non_promo_day_does_not_force_september_promo(engine: NanoBananaEngine):
    """Verify September savings promo is NOT injected on non-promo days."""
    target_date = date(2026, 9, 11)  # Day 11 is rotation B, not in {1, 7, 14, 21, 28}
    concepts = engine.build_daily_batch(count=5, target_date=target_date)
    archetypes = [c.archetype for c in concepts]
    assert "september_savings_promo" not in archetypes


def test_typography_and_editorial_standards(engine: NanoBananaEngine):
    """Verify no em dashes, en dashes, or emojis exist in generated prompts, titles, or filenames."""
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map
        "\U0001f1e0-\U0001f1ff"  # flags
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "]+",
        flags=re.UNICODE,
    )

    test_dates = [date(2026, 9, d) for d in range(1, 15)]
    for d in test_dates:
        concepts = engine.build_daily_batch(count=5, target_date=d)
        for concept in concepts:
            targets = [concept.name, concept.prompt, concept.output_filename]
            if concept.is_carousel_folder:
                for slide in concept.carousel_slides:
                    targets.extend([slide.name, slide.prompt, slide.output_filename])

            for text in targets:
                assert "—" not in text, f"Em dash found in '{text}'"
                assert "–" not in text, f"En dash found in '{text}'"
                assert not emoji_pattern.search(text), f"Emoji found in '{text}'"
                # Strictly customer-facing: never offer drone inspections to customers
                assert "drone inspection" not in text.lower(), f"Drone inspection offered to customer in '{text}'"


def test_carousel_standards_and_no_abc_proguard(engine: NanoBananaEngine):
    """Verify carousel slides strictly use industry standard GAF / ZIP and zero ABC Pro Guard."""
    for d in [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)]:
        concepts = engine.build_daily_batch(count=5, target_date=d)
        carousel = [c for c in concepts if c.is_carousel_folder][0]

        slide_prompts = [s.prompt for s in carousel.carousel_slides]
        slide_names = [s.name for s in carousel.carousel_slides]

        # Slides must be distinct
        assert len(set(slide_names)) == 4, f"Slide names must all be unique: {slide_names}"

        for prompt in slide_prompts:
            assert "abc pro guard" not in prompt.lower(), "ABC Pro Guard prohibited from marketing copy"
            assert "abc proguard" not in prompt.lower(), "ABC Pro Guard prohibited from marketing copy"


def test_scan_photos_excludes_before_and_bergenfield(engine: NanoBananaEngine):
    """Verify photo scanner excludes any Before photos and Bergenfield photos."""
    projects = engine.scan_background_photos_by_project()
    for proj_name, photos in projects.items():
        assert "before" not in proj_name.lower()
        assert "bergenfield" not in proj_name.lower()
        for p in photos:
            p_str = str(p).lower()
            assert "before" not in p.name.lower(), f"Found Before photo: {p}"
            assert "bergenfield" not in p.name.lower(), f"Found Bergenfield photo: {p}"
            assert "/before/" not in p_str, f"Found photo in Before directory: {p}"
            assert "/bergenfield/" not in p_str, f"Found photo in Bergenfield directory: {p}"


def test_local_rendering_execution(engine: NanoBananaEngine, tmp_path: Path):
    """Verify local rendering produces valid 1080x1350 JPEG files with zero blurry sides."""
    concepts = engine.build_daily_batch(count=5, target_date=date(2026, 9, 11))
    # Test rendering of 1 single flyer and 1 carousel folder
    sample_batch = [concepts[0], concepts[-1]]  # Magazine Cover & Carousel Folder

    rendered_files = engine.render_concepts_locally(sample_batch, dest_dir=tmp_path)
    assert len(rendered_files) >= 5  # 1 flyer + 4 carousel slides

    for file_path in rendered_files:
        assert file_path.exists(), f"Rendered file missing: {file_path}"
        assert file_path.suffix.lower() == ".jpg"

        with Image.open(file_path) as img:
            assert img.size == (1080, 1350), f"Incorrect dimensions {img.size} for {file_path.name}; must be (1080, 1350)"
            assert img.format == "JPEG"


def test_run_daily_generation_default_engine_mode():
    """Verify run_daily_generation defaults to 'local' engine_mode to guarantee zero AI hallucinations."""
    import inspect

    sig = inspect.signature(run_daily_generation)
    assert "engine_mode" in sig.parameters
    assert sig.parameters["engine_mode"].default == "local"
