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
    """Photo on top, solid brand band carrying the copy below.

    The band is measured from the bottom up and the photograph takes the rest,
    for the same reason as ``before-after``: a fixed split plus a minimum
    headline height is not a budget, and when the copy is long the bullets end
    up printed through the CTA button.
    """
    copy = r.spec.text
    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    pad_top, pad_bottom = r.s(52), r.s(56)
    eyebrow_h = r.s(56) if copy.eyebrow else 0
    headline_h = r.s(170)
    support_h = r.s(110) if copy.support else 0
    bullet_h = r.s(50) * len(copy.bullets)
    cta_h = r.s(86)
    band = pad_top + eyebrow_h + headline_h + support_h + bullet_h + r.s(34) + pad_bottom + cta_h

    split = min(r.height - bar - band, r.grid.y(0.62))
    # Below this the photograph stops being a photograph, so the copy sheds its
    # bullets rather than the image losing the whole frame.
    if split < r.grid.y(0.34) and copy.bullets:
        copy.bullets = copy.bullets[:1]
        bullet_h = r.s(50) * len(copy.bullets)
        band = (
            pad_top + eyebrow_h + headline_h + support_h + bullet_h + r.s(34) + pad_bottom + cta_h
        )
        split = min(r.height - bar - band, r.grid.y(0.62))
    split = max(split, r.grid.y(0.30))

    r.photo_panel(
        (0, 0, r.width, split), r.spec.image.asset_id, r.spec.image.crop, r.spec.image.grayscale
    )
    if r.spec.image.overlay != "none":
        r.overlay_panel(
            (0, 0, r.width, split), r.spec.image.overlay, min(r.spec.image.overlay_strength, 0.45)
        )

    r.solid_band((0, split, r.width, r.height), r.primary)

    align = r.spec.layout.text_align
    x, width = r.grid.left, r.grid.content_width

    if r.spec.layout.accent_shape:
        r.solid_band((0, split, r.width, split + r.s(12)), r.accent)

    y = split + pad_top
    cta_y = r.height - bar - pad_bottom - cta_h

    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=True, align=align)
    # What is left after everything below the headline has been reserved. No
    # floor: an oversized headline is set smaller, never drawn over the rest.
    headline_space = max(cta_y - y - support_h - bullet_h - r.s(34), r.s(70))
    y = r.headline(
        copy.headline,
        x,
        y,
        width,
        headline_space,
        on_dark=True,
        align=align,
        max_size=r.s(96),
    )
    y += r.s(20)
    if copy.support:
        y = r.support(
            copy.support,
            x,
            y,
            width,
            min(support_h, max(cta_y - y, r.s(30))),
            on_dark=True,
            align=align,
        ) + r.s(14)
    if copy.bullets and y + bullet_h <= cta_y:
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
    """Two stacked panels labelled BEFORE / AFTER with the copy beneath.

    The copy block is measured from the bottom of the canvas upwards and the
    photographs take what is left. Sizing the panels first and hoping the copy
    fit underneath is what put the CTA button on top of the support line: the
    headline had a minimum height that was larger than the space remaining, so
    every element after it was pushed into the button.
    """
    bar = r.s(86) if r.spec.layout.show_contact_bar and r.client.contact.has_any else 0
    header = r.grid.y(0.14)
    gutter = r.s(10)

    copy = r.spec.text
    pad_top, pad_bottom = r.s(46), r.s(48)
    eyebrow_h = r.s(56) if copy.eyebrow else 0
    headline_h = r.s(150)
    support_h = r.s(96) if copy.support else 0
    cta_h = r.s(86)
    copy_block = pad_top + eyebrow_h + headline_h + support_h + r.s(28) + pad_bottom + cta_h

    panels_bottom = r.height - bar - copy_block
    # Never let the copy squeeze the photographs below half the canvas; if it
    # would, the copy loses its support line instead.
    floor = r.grid.y(0.52)
    if panels_bottom < floor and support_h:
        support_h = 0
        copy_block = pad_top + eyebrow_h + headline_h + r.s(28) + pad_bottom + cta_h
        panels_bottom = r.height - bar - copy_block
    panels_bottom = max(panels_bottom, floor)

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
    y = panels_bottom + pad_top
    cta_y = r.height - bar - pad_bottom - cta_h

    if copy.eyebrow:
        y = r.eyebrow(copy.eyebrow, x, y, width, on_dark=False, align="center")
    # The headline gets what is actually left after the support line and the
    # button, and no more. There is no minimum: a headline too big for its box
    # is set smaller, never drawn over what comes next.
    headline_space = max(cta_y - y - support_h - r.s(28), r.s(60))
    y = r.headline(
        copy.headline,
        x,
        y,
        width,
        headline_space,
        on_dark=False,
        align="center",
        max_size=r.s(84),
    )
    if support_h and copy.support:
        y += r.s(14)
        r.support(
            copy.support, x, y, width, min(support_h, cta_y - y), on_dark=False, align="center"
        )

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


def build_statement(r: FlyerRenderer) -> None:
    """One photograph, one idea, three lines of white type. Nothing else.

    Modelled on the Harford reference, the most confident piece in the operator's
    set. It has no scrim, no chips, no CTA and no accent colour, which is exactly
    why it works: the photograph is completely unobstructed.

    It only holds up when the image has somewhere calm for the type, so the
    layout leans on a soft shadow rather than a scrim, and the selector should
    be given an asset with real negative space.
    """
    copy = r.spec.text

    r.photo_panel(
        (0, 0, r.width, r.height),
        r.spec.image.asset_id,
        r.spec.image.crop,
        r.spec.image.grayscale,
    )
    # A whisper of a scrim only. Anything heavier and it stops being this layout.
    if r.spec.image.overlay != "none":
        r.overlay_panel(
            (0, 0, r.width, r.height), "dark_flat", min(r.spec.image.overlay_strength, 0.22)
        )

    r.logo("top-right")

    x, width = r.grid.left, r.grid.content_width
    y = r.grid.y(0.22)
    y = r.headline_staggered(copy.headline, x, y, width, r.s(620))

    # A single quiet line at the base, if there is one. No pill, no bar.
    if copy.support:
        r.support(
            copy.support,
            x,
            r.grid.bottom - r.s(70),
            width,
            r.s(70),
            on_dark=True,
            align="left",
        )


def build_house_approved(r: FlyerRenderer) -> None:
    """The client's own approved style, taken from their finalised flyers.

    The distinguishing move: the headline sits on solid maroon blocks rather than
    over a scrim, so the photograph underneath keeps its full brightness. The
    blocks hug each line, which gives the ragged right edge the approved set has.

    No CTA pill and no contact strip: in the approved series those live on a
    dedicated closing card rather than on every flyer.
    """
    copy = r.spec.text

    r.photo_panel(
        (0, 0, r.width, r.height),
        r.spec.image.asset_id,
        r.spec.image.crop,
        r.spec.image.grayscale,
    )
    x, width = r.grid.left, r.grid.content_width

    # No brand line at the top. The mark at the base is the brand statement in
    # this series, and a small tracked-out company name set over open
    # photography just went grey against the roof - two weak brand marks
    # instead of one strong one.
    y = r.headline_blocks(
        copy.headline,
        x - r.s(12),  # blocks bleed slightly past the type margin
        r.grid.y(0.055),
        width + r.s(24),
        r.s(430),
        block_color=r.primary,
        max_size=r.s(108),
    )

    # The callout sits below the headline blocks, never overlapping them. The
    # headline height varies with the number of lines, so anchor to where the
    # blocks actually finished rather than to a fixed fraction.
    if copy.callout_number or copy.callout_lead:
        callout_y = max(y + r.s(40), r.grid.y(0.56))
        r.numbered_callout(
            copy.callout_number,
            copy.callout_lead,
            copy.callout_body,
            x,
            callout_y,
            width,
        )
    elif copy.support:
        # The headline gets solid blocks behind it; the support line was left
        # bare over open photograph and disappeared into a sunlit roof. It gets
        # its own block, narrower and softer, in the same idiom.
        support_y = max(y + r.s(46), r.grid.y(0.58))
        r.solid_band(
            (x - r.s(12), support_y - r.s(16), x + width + r.s(12), support_y + r.s(120)),
            darken(r.primary, 0.15),
            alpha=0.86,
        )
        r.support(copy.support, x, support_y, width, r.s(104), on_dark=True, align="left")

    r.mark_centered(r.grid.bottom, max_width=r.s(360))


def build_house_educational(r: FlyerRenderer) -> None:
    """The approved carousel card: detail strip, brand band, two paragraphs.

    This is the template most of the client's finalised flyers use, and the
    reason they read as substantial rather than sparse. The band carries real
    information, so this is the one layout where high text density is correct.

    The blurred backdrop is the same photograph, which lets a 16:9 frame sit in
    a 4:5 canvas without letterboxing or an aggressive crop.
    """
    copy = r.spec.text

    r.blurred_backdrop(r.spec.image.asset_id, r.spec.image.crop)
    r.detail_strip(r.spec.image.asset_id, 0.0, 0.52)

    # These two fields only get written when Claude is doing the copy. Offline
    # they are empty, and the band rendered as a large blank rectangle with the
    # headline floating in it - the layout looked broken rather than sparse.
    # Fall back to the copy that always exists.
    blocks = [
        ("What it looks like", copy.looks_like),
        ("Why it matters", copy.harmful),
    ]
    blocks = [(label, body) for label, body in blocks if body.strip()]
    if not blocks:
        blocks = [("The short version", copy.support)] if copy.support else []
        blocks += [("What you get", " · ".join(copy.bullets))] if copy.bullets else []
    if not blocks:
        blocks = [("", copy.headline)]

    r.body_band(copy.card_title or copy.headline, blocks, top=0.56, bottom=0.90)

    r.tagline()
    # The mark goes on every flyer; bottom-left keeps it clear of the tagline.
    r.logo("bottom-left", force=True)


LAYOUT_BUILDERS: dict[str, Builder] = {
    "house-educational": build_house_educational,
    "house-approved": build_house_approved,
    "statement": build_statement,
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
