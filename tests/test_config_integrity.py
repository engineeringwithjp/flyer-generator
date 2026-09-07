"""The config files are data, and data can point at things that do not exist."""

from __future__ import annotations

from app.config import load_json_config


def test_every_preferred_layout_actually_exists():
    """A campaign pointing at a layout that was never built drops a flyer.

    ``premium-roofing`` referenced a "minimal" layout that does not exist, and
    the only symptom was one fewer flyer in the batch plus a warning at the
    bottom of the run summary.
    """
    campaigns = load_json_config("campaigns.json")["campaigns"]
    layouts = set(load_json_config("layouts.json")["layouts"])

    for campaign in campaigns:
        for layout in campaign.get("preferred_layouts", []):
            assert layout in layouts, f"{campaign['id']} prefers unknown layout {layout!r}"


def test_the_copy_bank_covers_every_angle_a_campaign_can_have():
    """Every campaign falls back to its angle, so no angle may be missing."""
    campaigns = load_json_config("campaigns.json")["campaigns"]
    bank = load_json_config("copy-bank.json")

    angles = {c["angle"] for c in campaigns}
    covered = set(bank["by_angle"])
    assert angles <= covered, f"copy bank has no lines for {sorted(angles - covered)}"


def test_banked_copy_never_uses_the_retired_company_name():
    """The business renamed; nothing written may carry the old name."""
    from app.house_rules import RETIRED_NAMES

    bank = load_json_config("copy-bank.json")
    blob = repr(bank).lower()
    for retired in RETIRED_NAMES:
        assert retired not in blob, f"copy bank contains the retired name {retired!r}"


def test_banked_copy_is_not_itself_filler():
    """The bank exists to replace filler, so it must pass the filler check."""
    from app.house_rules import GENERIC_PHRASES

    bank = load_json_config("copy-bank.json")
    for scope in ("by_campaign", "by_angle"):
        for key, entry in bank[scope].items():
            for field, options in entry.items():
                for line in options:
                    lowered = line.lower()
                    hits = [p for p in GENERIC_PHRASES if p in lowered]
                    assert not hits, f"{scope}/{key}/{field}: {line!r} contains {hits}"


def test_banked_copy_fits_the_flyer_copy_model():
    """A line longer than the model allows crashes the flyer, not the check.

    Pydantic rejects an over-length ``support`` string, which took out a whole
    flyer mid-batch with a validation error rather than a QA failure.
    """
    from app.models.flyer import FlyerCopy

    limits = {
        name: field.metadata[0].max_length
        for name, field in FlyerCopy.model_fields.items()
        if field.metadata and getattr(field.metadata[0], "max_length", None)
    }
    bank = load_json_config("copy-bank.json")

    for scope in ("by_campaign", "by_angle"):
        for key, entry in bank[scope].items():
            for field_name, options in entry.items():
                cap = limits.get(field_name)
                if cap is None:
                    continue
                for line in options:
                    assert len(line) <= cap, (
                        f"{scope}/{key}/{field_name}: {len(line)} chars exceeds {cap}: {line!r}"
                    )


def test_banked_headlines_survive_the_eight_word_rule():
    """The flyer model caps a headline at eight words; the bank must too.

    A ninth word is a Pydantic ``ValueError``, which kills the flyer before QA
    ever sees it - a crash in the run log instead of a held flyer.
    """
    bank = load_json_config("copy-bank.json")
    for scope in ("by_campaign", "by_angle"):
        for key, entry in bank[scope].items():
            for line in entry.get("headline", []):
                assert len(line.split()) <= 8, f"{scope}/{key}: {line!r} is too long"
