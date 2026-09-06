"""Layout builders.

Each builder composes the reusable components on ``FlyerRenderer``. Adding a
layout means adding one function here and one entry in ``config/layouts.json``
- no other file changes.
"""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image

from ..config import load_json_config
from .composition import darken
from .renderer import FlyerRenderer

Builder = Callable[[FlyerRenderer], None]


def _layout_config() -> dict:
    return load_json_config("layouts.json")["layouts"]


def list_layouts() -> list[str]:
    return sorted(_layout_config())


def layout_description(name: str) -> str:
    entry = _layout_config().get(name, {})
    return entry.get("description", "")


# --------------------------------------------------------------- hero-full


def build_hero_full(r: FlyerRenderer) -> None:
    """Full-bleed photograph, gradient scrim, copy stacked in the lower half."""
    r.photo_panel(
        (0, 0, r.width, r.height), r.spec.image.asset_id, r.spec.image.crop, r.spec.image.grayscale
    )
    r.overlay_panel((0, 0, r.width, r.height), r.spec.image.overlay, r.spec.image.overlay_strength)

    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    align = r.spec.layout.text_align
    x, width = r.grid.left, r.grid.content_width

    # Build bottom-up so the stack always clears the contact bar.
    cta_height = r.s(86)
    bottom = r.height - bar - r.s(56)
    cta_y = bottom - cta_height

    copy = r.spec.text
    support_height = r.s(120) if copy.support else 0
    bullet_height = r.s(78) * len(copy.bullets)
    headline_top = r.grid.y(0.42)
    headline_space = cta_y - headline_top - support_height - bullet_height - r.s(56)

    y = headline_top
    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=True, align=align)
    if r.spec.layout.accent_shape:
        y = r.accent_rule(x, y, align=align, box_width=width) + r.s(34)

    y = r.headline(
        copy.headline, x, y, width, max(headline_space, r.s(160)), on_dark=True, align=align
    )
    y += r.s(24)
    if copy.support:
        y = r.support(copy.support, x, y, width, support_height, on_dark=True, align=align) + r.s(
            18
        )
    if copy.bullets:
        y = r.bullets(copy.bullets, x, y, width, on_dark=True, align=align)

    r.cta_button(copy.cta, x, cta_y, width, align=align)
    r.logo(r.spec.layout.logo_position)
    if copy.offer_badge:
        r.offer_badge(copy.offer_badge, (r.grid.right - r.s(150), r.grid.y(0.22)))
    if copy.disclaimer:
        r.disclaimer(copy.disclaimer, r.height - bar - r.s(34), on_dark=True)
    if bar:
        r.contact_bar()


# ------------------------------------------------------- banner-lower-third


def build_banner_lower_third(r: FlyerRenderer) -> None:
    """Photo on top, solid brand band carrying the copy below."""
    split = r.grid.y(0.52)
    r.photo_panel(
        (0, 0, r.width, split), r.spec.image.asset_id, r.spec.image.crop, r.spec.image.grayscale
    )
    if r.spec.image.overlay != "none":
        r.overlay_panel(
            (0, 0, r.width, split), r.spec.image.overlay, min(r.spec.image.overlay_strength, 0.45)
        )

    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    r.solid_band((0, split, r.width, r.height), r.primary)

    align = r.spec.layout.text_align
    x, width = r.grid.left, r.grid.content_width

    if r.spec.layout.accent_shape:
        r.solid_band((0, split, r.width, split + r.s(12)), r.accent)

    y = split + r.s(52)
    copy = r.spec.text
    cta_y = r.height - bar - r.s(56) - r.s(86)

    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=True, align=align)
    headline_space = (
        cta_y - y - (r.s(110) if copy.support else 0) - r.s(96) * len(copy.bullets) - r.s(40)
    )
    y = r.headline(
        copy.headline,
        x,
        y,
        width,
        max(headline_space, r.s(140)),
        on_dark=True,
        align=align,
        max_size=r.s(96),
    )
    y += r.s(20)
    if copy.support:
        y = r.support(copy.support, x, y, width, r.s(110), on_dark=True, align=align) + r.s(14)
    if copy.bullets:
        r.bullets(copy.bullets, x, y, width, on_dark=True, align=align)

    r.cta_button(copy.cta, x, cta_y, width, align=align)
    r.logo(r.spec.layout.logo_position)
    if copy.offer_badge:
        r.offer_badge(copy.offer_badge, (r.grid.right - r.s(140), split - r.s(120)))
    if bar:
        r.contact_bar()


# ----------------------------------------------------------- split-diagonal


def build_split_diagonal(r: FlyerRenderer) -> None:
    """Angled split between photograph and brand colour."""
    r.photo_panel(
        (0, 0, r.width, r.height), r.spec.image.asset_id, r.spec.image.crop, r.spec.image.grayscale
    )
    r.overlay_panel(
        (0, 0, r.width, r.grid.y(0.6)), r.spec.image.overlay, r.spec.image.overlay_strength
    )

    r.diagonal_band(0.56, r.primary)
    if r.spec.layout.accent_shape:
        r.diagonal_band(0.545, r.accent)
        r.diagonal_band(0.56, r.primary)

    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    align = r.spec.layout.text_align
    x, width = r.grid.left, r.grid.content_width

    copy = r.spec.text
    y = r.grid.y(0.62)
    cta_y = r.height - bar - r.s(52) - r.s(86)

    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=True, align=align)
    headline_space = cta_y - y - (r.s(104) if copy.support else 0) - r.s(40)
    y = r.headline(
        copy.headline,
        x,
        y,
        width,
        max(headline_space, r.s(130)),
        on_dark=True,
        align=align,
        max_size=r.s(100),
    )
    y += r.s(18)
    if copy.support:
        r.support(copy.support, x, y, width, r.s(104), on_dark=True, align=align)

    r.cta_button(copy.cta, x, cta_y, width, align=align)
    r.logo(r.spec.layout.logo_position)
    if copy.offer_badge:
        r.offer_badge(copy.offer_badge, (r.grid.right - r.s(150), r.grid.y(0.26)))
    if bar:
        r.contact_bar()


# --------------------------------------------------------------- offer-badge


def build_offer_badge(r: FlyerRenderer) -> None:
    """Heavily darkened photo, centred copy stack, circular offer badge."""
    r.photo_panel(
        (0, 0, r.width, r.height), r.spec.image.asset_id, r.spec.image.crop, r.spec.image.grayscale
    )
    r.overlay_panel(
        (0, 0, r.width, r.height),
        r.spec.image.overlay or "dark_flat",
        max(r.spec.image.overlay_strength, 0.6),
    )

    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    x, width = r.grid.left, r.grid.content_width
    copy = r.spec.text

    has_badge = bool(copy.offer_badge)
    if has_badge:
        r.offer_badge(copy.offer_badge, (r.width // 2, r.grid.y(0.29)))

    y = r.grid.y(0.46) if has_badge else r.grid.y(0.34)
    cta_y = r.height - bar - r.s(64) - r.s(86)

    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=True, align="center")
    headline_space = cta_y - y - (r.s(120) if copy.support else 0) - r.s(48)
    y = r.headline(
        copy.headline,
        x,
        y,
        width,
        max(headline_space, r.s(140)),
        on_dark=True,
        align="center",
        max_size=r.s(104),
    )
    y += r.s(22)
    if copy.support:
        y = r.support(copy.support, x, y, width, r.s(120), on_dark=True, align="center")

    r.cta_button(copy.cta, x, cta_y, width, align="center")
    r.logo(r.spec.layout.logo_position)
    if copy.disclaimer:
        r.disclaimer(copy.disclaimer, r.height - bar - r.s(34), on_dark=True)
    if bar:
        r.contact_bar()


# --------------------------------------------------------------- before-after


def build_before_after(r: FlyerRenderer) -> None:
    """Two stacked panels labelled BEFORE / AFTER with the copy beneath."""
    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    header = r.grid.y(0.14)
    panels_bottom = r.grid.y(0.66)
    gutter = r.s(10)
    panel_height = (panels_bottom - header - gutter) // 2

    r.solid_band((0, 0, r.width, header), r.primary)
    r.logo(r.spec.layout.logo_position)

    top_box = (0, header, r.width, header + panel_height)
    bottom_box = (0, header + panel_height + gutter, r.width, panels_bottom)

    primary_id = r.spec.image.asset_id
    secondary_id = r.spec.image.secondary_asset_id or primary_id

    r.photo_panel(top_box, primary_id, "top", grayscale=True)
    r.photo_panel(bottom_box, secondary_id, "bottom", r.spec.image.grayscale)
    r.panel_label("Before", top_box)
    r.panel_label("After", bottom_box)

    r.solid_band((0, panels_bottom, r.width, r.height), r.paper)
    if r.spec.layout.accent_shape:
        r.solid_band((0, panels_bottom, r.width, panels_bottom + r.s(10)), r.accent)

    x, width = r.grid.left, r.grid.content_width
    copy = r.spec.text
    y = panels_bottom + r.s(46)
    cta_y = r.height - bar - r.s(48) - r.s(86)

    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=False, align="center")
    headline_space = cta_y - y - (r.s(90) if copy.support else 0) - r.s(36)
    y = r.headline(
        copy.headline,
        x,
        y,
        width,
        max(headline_space, r.s(110)),
        on_dark=False,
        align="center",
        max_size=r.s(84),
    )
    y += r.s(14)
    if copy.support:
        r.support(copy.support, x, y, width, r.s(90), on_dark=False, align="center")

    r.cta_button(copy.cta, x, cta_y, width, align="center")
    if bar:
        r.contact_bar()


# ----------------------------------------------------------------- stat-stack


def build_stat_stack(r: FlyerRenderer) -> None:
    """Typographic credibility layout with up to three proof points."""
    r.photo_panel(
        (0, 0, r.width, r.height), r.spec.image.asset_id, r.spec.image.crop, r.spec.image.grayscale
    )
    r.overlay_panel(
        (0, 0, r.width, r.height),
        "brand_gradient" if r.spec.image.overlay == "none" else r.spec.image.overlay,
        max(r.spec.image.overlay_strength, 0.7),
    )

    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    align = r.spec.layout.text_align
    x, width = r.grid.left, r.grid.content_width
    copy = r.spec.text

    y = r.grid.y(0.24)
    cta_y = r.height - bar - r.s(56) - r.s(86)

    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=True, align=align)
    if r.spec.layout.accent_shape:
        y = r.accent_rule(x, y, align=align, box_width=width) + r.s(26)

    y = r.headline(
        copy.headline, x, y, width, r.s(280), on_dark=True, align=align, max_size=r.s(92)
    )
    y += r.s(26)
    if copy.support:
        y = r.support(copy.support, x, y, width, r.s(120), on_dark=True, align=align) + r.s(24)

    # Proof points in a bordered stack rather than plain bullets.
    items = copy.bullets or []
    if items:
        row_height = r.s(92)
        for index, item in enumerate(items[:3]):
            top = y + index * row_height
            # A hairline in the ink colour at low weight, not a tinted blend -
            # blending white into maroon reads as an unintended pink.
            rule = Image.new("RGBA", (width, max(r.s(2), 1)), (*r.on_image, 90))
            r.paste(rule, (x, top))
            fitted_y = top + r.s(22)
            font = r.fonts.get("bold", r.s(30))
            r.draw.text((x, fitted_y), item, font=font, fill=r.on_image)
        y += row_height * min(len(items), 3)

    r.cta_button(copy.cta, x, cta_y, width, align=align)
    r.logo(r.spec.layout.logo_position)
    if bar:
        r.contact_bar()


def build_hero_editorial(r: FlyerRenderer) -> None:
    """The house style, matched to the approved reference flyers.

    Full-bleed photography. An oversized two-tone headline in the upper half.
    The supporting line as a solid accent pill. A row of translucent chips
    carrying the proof. Small contact type bottom-left with the mark opposite.

    Deliberately no large colour panel and no full-width CTA slab: in the
    references the photograph is never boxed in.
    """
    copy = r.spec.text

    r.photo_panel(
        (0, 0, r.width, r.height),
        r.spec.image.asset_id,
        r.spec.image.crop,
        r.spec.image.grayscale,
    )
    # Heavy scrim across the top half where the headline lives, lighter at the
    # base for the contact line. The middle of the photograph stays clear.
    r.overlay_panel(
        (0, 0, r.width, r.grid.y(0.62)),
        "dark_gradient",
        min(r.spec.image.overlay_strength + 0.10, 0.92),
    )
    r.overlay_panel((0, r.grid.y(0.74), r.width, r.height), "dark_gradient", 0.72)

    x, width = r.grid.left, r.grid.content_width

    # --- base: contact line left, mark right --------------------------------
    credentials = [p for p in r.client.proof_points if "HIC" in p or "Licensed" in p][:1]
    mark_width = r.s(260)
    r.contact_footer(extra=credentials, mark_width=mark_width)
    r.footer_mark(max_width=mark_width)

    # --- top: the mark lives in the footer, so the copy owns the upper half --
    y = r.grid.y(0.10)
    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=True, align="left") + r.s(4)

    # The headline is the flyer. In the references it runs nearly edge to edge
    # and sets tight, so it is given a generous box and a large ceiling.
    y = r.headline_two_tone(
        copy.headline,
        copy.accent_word,
        x,
        y,
        width,
        r.s(520),
        on_dark=True,
        align="left",
        max_size=r.s(152),
    )
    y += r.s(26)

    # The supporting line becomes the accent pill.
    if copy.support:
        y = r.lead_pill(copy.support, x, y, width) + r.s(22)

    if copy.chips:
        r.chip_row(copy.chips, x, y, width, style="glass")
    elif copy.bullets:
        r.bullets(copy.bullets, x, y, width, on_dark=True, align="left")


LAYOUT_BUILDERS: dict[str, Builder] = {
    "hero-editorial": build_hero_editorial,
    "hero-full": build_hero_full,
    "banner-lower-third": build_banner_lower_third,
    "split-diagonal": build_split_diagonal,
    "offer-badge": build_offer_badge,
    "before-after": build_before_after,
    "stat-stack": build_stat_stack,
}


def assert_layouts_registered() -> None:
    """Config and code must agree - called by ``flyer validate``."""
    configured = set(_layout_config())
    implemented = set(LAYOUT_BUILDERS)
    missing = configured - implemented
    extra = implemented - configured
    problems = []
    if missing:
        problems.append(f"declared in layouts.json but not implemented: {sorted(missing)}")
    if extra:
        problems.append(f"implemented but not declared in layouts.json: {sorted(extra)}")
    if problems:
        raise ValueError("; ".join(problems))


_ = darken  # re-exported for layout authors
