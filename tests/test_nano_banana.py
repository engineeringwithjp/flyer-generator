"""Unit tests for Nano Banana Pro flyer generation engine and edge-to-edge rendering."""

from __future__ import annotations

from pathlib import Path
from PIL import Image
import pytest

from app.nano_banana import NanoBananaEngine, FlyerConcept


def test_batch_aspect_ratios_and_dimensions():
    """All daily concepts and carousel slides must default to 4:5 (1080 x 1350 px)."""
    engine = NanoBananaEngine()
    concepts = engine.build_daily_batch(count=5)

    assert len(concepts) == 5
    for concept in concepts:
        assert concept.aspect_ratio == "4:5"
        assert concept.width == 1080
        assert concept.height == 1350
        if concept.is_carousel_folder:
            assert len(concept.carousel_slides) == 4
            for slide in concept.carousel_slides:
                assert slide.aspect_ratio == "4:5"
                assert slide.width == 1080
                assert slide.height == 1350


def test_prompts_have_zero_em_dashes_or_emojis():
    """Prompts must adhere to anti-AI tell standards: zero em dashes and zero emojis."""
    engine = NanoBananaEngine()
    concepts = engine.build_daily_batch(count=5)

    for concept in concepts:
        assert "—" not in concept.prompt, f"Em dash found in {concept.name}"
        assert "–" not in concept.prompt, f"En dash found in {concept.name}"
        if concept.is_carousel_folder:
            for slide in concept.carousel_slides:
                assert "—" not in slide.prompt, f"Em dash found in slide {slide.name}"
                assert "–" not in slide.prompt, f"En dash found in slide {slide.name}"


def test_carousel_strictly_forbids_abc_pro_guard():
    """Carousel prompts must never reference ABC Pro Guard and must enforce GAF or ZIP System."""
    engine = NanoBananaEngine()
    concepts = engine.build_daily_batch(count=5)

    carousel = next(c for c in concepts if c.is_carousel_folder)
    for slide in carousel.carousel_slides:
        assert "ABC Pro Guard" not in slide.prompt
        assert "abc pro guard" not in slide.prompt.lower()

    # Slide 2 and Slide 3 specifically reference GAF or ZIP
    slide2 = carousel.carousel_slides[1]
    slide3 = carousel.carousel_slides[2]
    assert "GAF" in slide2.prompt or "ZIP" in slide2.prompt
    assert "GAF" in slide3.prompt


def test_local_edge_to_edge_renderer_dimensions(tmp_path: Path):
    """The local edge-to-edge rendering engine must output exact 1080x1350 images with zero blurry borders."""
    engine = NanoBananaEngine()
    concepts = engine.build_daily_batch(count=5)

    rendered_paths = engine.render_concepts_locally(concepts, tmp_path)
    assert len(rendered_paths) >= 5

    for p in rendered_paths:
        assert p.exists()
        with Image.open(p) as img:
            assert img.size == (1080, 1350), f"{p.name} was not 1080x1350, got {img.size}"
            # Aspect ratio check
            aspect = img.width / img.height
            assert abs(aspect - 0.800) < 0.001
