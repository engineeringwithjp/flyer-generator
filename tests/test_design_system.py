"""The design system is the answer to prompt bloat - verify it is machine-usable."""

from __future__ import annotations

import pytest

from app import design_system
from app.ai.skill import system_prompt

REQUIRED_SECTIONS = [
    "global",
    "photography",
    "composition_archetypes",
    "typography",
    "color",
    "branding",
    "copywriting",
    "iconography",
    "product_presentation",
    "social",
]


def test_every_required_section_exists(repo):
    principles = design_system.principles()
    for section in REQUIRED_SECTIONS:
        assert section in principles, f"missing design-system section: {section}"
        assert principles[section], f"empty design-system section: {section}"


def test_every_rule_is_classified(repo):
    principles = design_system.principles()
    for section in REQUIRED_SECTIONS:
        if section == "composition_archetypes":
            continue
        for rule in principles[section]:
            assert rule.get("class") in {"hard", "soft", "optional"}, rule
            assert rule.get("rule"), rule
            assert rule.get("id"), rule


def test_rule_ids_are_unique(repo):
    seen = set()
    for section in design_system.principles().values():
        if not isinstance(section, list):
            continue
        for rule in section:
            if isinstance(rule, dict) and "id" in rule:
                assert rule["id"] not in seen, f"duplicate rule id {rule['id']}"
                seen.add(rule["id"])


def test_the_house_is_the_hero_is_a_hard_rule(repo):
    hard = design_system.hard_rules("photography")
    assert any("HOUSE IS THE HERO" in rule.upper() for rule in hard)


def test_never_list_covers_the_stated_failures(repo):
    never = " ".join(design_system.never_list()).lower()
    for expected in (
        "excessive text",
        "banner",
        "card",
        "infographic",
        "fake-looking",
        "gradient",
        "icon",
        "manufacturer",
        "canva",
    ):
        assert expected in never, f"NEVER list does not cover {expected!r}"


def test_every_archetype_maps_to_a_real_layout(repo):
    from app.rendering.templates import LAYOUT_BUILDERS

    for item in design_system.archetypes():
        assert item["layout"] in LAYOUT_BUILDERS, item
        for field in ("use_case", "image_hierarchy", "text_density", "cta", "treatment"):
            assert item.get(field), f"archetype {item['id']} missing {field}"


def test_all_named_archetypes_are_present(repo):
    ids = {a["id"] for a in design_system.archetypes()}
    for required in (
        "hero-image",
        "editorial-overlay",
        "before-after",
        "product-education",
        "promotional",
        "seasonal",
        "storm-emergency",
        "architectural-detail",
    ):
        assert required in ids, f"missing archetype {required}"


@pytest.mark.parametrize("stage", ["planner", "copywriter", "designer", "qa", "reference"])
def test_compiled_block_is_non_trivial(repo, stage):
    block = design_system.compile_for_stage(stage, "testco")
    assert "<design_system>" in block
    assert len(block) > 400


def test_designer_stage_gets_photography_and_the_human_test(repo):
    block = design_system.compile_for_stage("designer", "testco")
    assert "HOUSE IS THE HERO" in block.upper()
    assert "human design test" in block.lower()


def test_stages_receive_only_what_they_need(repo):
    """Cost control: the copywriter should not be paying for iconography rules."""
    copywriter = design_system.compile_for_stage("copywriter")
    designer = design_system.compile_for_stage("designer")
    assert len(copywriter) < len(designer)


def test_system_prompt_includes_skill_and_design_system(repo):
    prompt = system_prompt("designer", "testco")
    assert "skill_document" in prompt
    assert "<design_system>" in prompt
    assert "SKILL.md" in prompt


def test_prompt_minimisation_the_rules_are_not_in_the_request(repo):
    """SUCCESS CRITERION 4: standing rules live in the system prompt, not the ask."""
    prompt = system_prompt("copywriter", "testco")
    for standing_rule in ("Never invent", "one idea", "1080"):
        assert standing_rule.lower() in prompt.lower()
