"""The deterministic flyer renderer.

``FlyerRenderer`` owns the canvas and exposes reusable design components
(background, overlay, headline, CTA, logo, badge, contact bar). Layout modules
in ``templates.py`` compose those components - they never draw raw pixels, so
every flyer shares the same margins, contrast handling and text fitting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from ..config import get_settings
from ..errors import RenderError
from ..logging_setup import get_logger
from ..models import Client, FlyerSpecification
from .composition import (
    Grid,
    contrast_ratio,
    darken,
    diagonal_panel,
    hex_to_rgb,
    lighten,
    mix,
    radial_vignette,
    rounded_rect,
    vertical_gradient,
)
from .typography import FontLibrary, draw_lines, fit_text, measure, tracked_width

log = get_logger(__name__)

# Minimum WCAG contrast we will ship text at.
MIN_TEXT_CONTRAST = 4.5


@dataclass
class RenderContext:
    """Everything the renderer needs that is not in the specification."""

    client: Client
    asset_paths: dict[str, Path] = field(default_factory=dict)
    logo_path: Path | None = None
    fonts: FontLibrary | None = None


class FlyerRenderer:
    def __init__(self, spec: FlyerSpecification, context: RenderContext) -> None:
        self.spec = spec
        self.context = context
        self.client = context.client
        # The type pairing is part of the specification, so the same spec always
        # renders with the same type system.
        self.fonts = FontLibrary(
            fonts_dir=(context.fonts.fonts_dir if context.fonts else None),
            pairing=spec.layout.type_pairing,
        )

        self.width = spec.canvas.width
        self.height = spec.canvas.height
        self.grid = Grid(self.width, self.height)

        self.image = Image.new(
            "RGB", (self.width, self.height), hex_to_rgb(spec.palette.get("paper", "#FFFFFF"))
        )
        self.draw = ImageDraw.Draw(self.image)

        self.primary = hex_to_rgb(spec.palette.get("primary", "#0F1B2B"))
        self.accent = hex_to_rgb(spec.palette.get("accent", "#E8B03A"))
        self.ink = hex_to_rgb(spec.palette.get("ink", "#101418"))
        self.paper = hex_to_rgb(spec.palette.get("paper", "#FFFFFF"))
        self.on_image = hex_to_rgb(spec.palette.get("on_image", "#FFFFFF"))

        self.warnings: list[str] = []
        self._footer_band: tuple[int, int] | None = None
        # Boxes other components have claimed. The logo relocates around them
        # rather than being drawn underneath the copy stack.
        self.reserved: list[tuple[int, int, int, int]] = []

    def reserve(self, box: tuple[int, int, int, int]) -> None:
        self.reserved.append(box)

    @staticmethod
    def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int], pad: int = 0) -> bool:
        return not (
            a[2] + pad <= b[0] or a[0] >= b[2] + pad or a[3] + pad <= b[1] or a[1] >= b[3] + pad
        )

    # ------------------------------------------------------------ primitives

    def s(self, value: float) -> int:
        """Scale a value authored against a 1080px-wide canvas."""
        return self.grid.scale(value)

    def paste(self, layer: Image.Image, box: tuple[int, int]) -> None:
        self.image.paste(layer, box, layer if layer.mode == "RGBA" else None)

    # ----------------------------------------------------------- backgrounds

    def photo_panel(
        self,
        box: tuple[int, int, int, int],
        asset_id: str | None,
        crop: str = "focal",
        grayscale: bool = False,
    ) -> bool:
        """Fill ``box`` with a photograph. Returns False if no photo was used."""
        from ..assets.image_utils import crop_to_aspect, load_rgb
        from ..models import FocalPoint

        left, top, right, bottom = box
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            raise RenderError(f"Invalid photo panel box {box}")

        path = self.context.asset_paths.get(asset_id or "")
        if path is None or not path.exists():
            self.procedural_panel(box)
            return False

        try:
            source = load_rgb(path)
        except Exception as exc:
            log.warning("Falling back to a procedural panel; %s is unusable: %s", path, exc)
            self.warnings.append(f"asset {asset_id} unreadable")
            self.procedural_panel(box)
            return False

        focal = FocalPoint()
        cropped = crop_to_aspect(source, width, height, mode=crop, focal=focal)
        if grayscale:
            cropped = ImageOps.grayscale(cropped).convert("RGB")
        self.image.paste(cropped, (left, top))
        return True

    def procedural_panel(self, box: tuple[int, int, int, int]) -> None:
        """Brand-coloured background used when no photograph is available.

        This is a first-class output, not a placeholder: a clean brand gradient
        with a soft geometric accent reads as intentional design.
        """
        left, top, right, bottom = box
        width, height = right - left, bottom - top

        deep = darken(self.primary, 0.35)
        light = mix(self.primary, self.accent, 0.22)
        gradient = vertical_gradient((width, height), (*light, 255), (*deep, 255))
        self.image.paste(gradient.convert("RGB"), (left, top))

        # Subtle diagonal banding - texture without noise.
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        stripe = max(self.s(120), 8)
        for index, offset in enumerate(range(-height, width + height, stripe)):
            alpha = 16 if index % 2 == 0 else 8
            odraw.polygon(
                [
                    (offset, height),
                    (offset + stripe // 2, height),
                    (offset + stripe // 2 + height, 0),
                    (offset + height, 0),
                ],
                fill=(*lighten(self.primary, 0.5), alpha),
            )
        self.paste(overlay, (left, top))

    def overlay_panel(
        self,
        box: tuple[int, int, int, int],
        kind: str,
        strength: float,
    ) -> None:
        """Darken or tint a region so text placed on it stays readable."""
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0 or kind == "none":
            return

        alpha = int(round(min(max(strength, 0.0), 1.0) * 255))

        if kind == "dark_flat":
            layer = Image.new("RGBA", (width, height), (0, 0, 0, alpha))
        elif kind == "light_flat":
            layer = Image.new("RGBA", (width, height), (255, 255, 255, alpha))
        elif kind == "brand_gradient":
            layer = vertical_gradient(
                (width, height),
                (*self.primary, int(alpha * 0.25)),
                (*darken(self.primary, 0.3), alpha),
            )
        elif kind == "vignette":
            layer = radial_vignette((width, height), strength)
        else:  # dark_gradient - the default scrim
            layer = vertical_gradient(
                (width, height),
                (0, 0, 0, int(alpha * 0.16)),
                (0, 0, 0, alpha),
                stops=(0.15, 0.92),
            )
        self.paste(layer, (left, top))

    def diagonal_band(self, split: float, color: tuple[int, int, int], top: bool = False) -> None:
        panel = diagonal_panel((self.width, self.height), (*color, 255), split, top=top)
        self.paste(panel, (0, 0))

    def solid_band(self, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
        left, top, right, bottom = box
        self.draw.rectangle((left, top, right, bottom), fill=color)

    # -------------------------------------------------------------- branding

    def logo(self, position: str, force: bool = False) -> tuple[int, int, int, int] | None:
        """Draw the client logo, or a typographic wordmark when none exists.

        If the requested corner is already occupied by copy, the logo moves to
        the best free corner instead of being drawn on top of it.
        """
        if position == "none":
            return None

        max_width = self.s(300)
        max_height = self.s(96)

        path = self.context.logo_path
        artwork: Image.Image | None = None
        if path and path.exists():
            try:
                artwork = Image.open(path).convert("RGBA")
                artwork.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            except Exception as exc:
                log.warning("Logo %s could not be drawn: %s", path, exc)
                self.warnings.append("logo unreadable")
                artwork = None

        if artwork is not None:
            width, height = artwork.size
        else:
            fitted = fit_text(
                self.client.company_name.upper(),
                self.fonts,
                "headline",
                max_width,
                max_height,
                self.s(40),
                self.s(18),
                max_lines=2,
            )
            width, height = max(fitted.width, 1), max(fitted.height, 1)

        if not force:
            position = self._free_corner(position, width, height)
        x, y = self._corner(position, width, height)
        box = (x, y, x + width, y + height)

        if artwork is not None:
            self.paste(artwork, (x, y))
        else:
            ink = self._legible_ink(box)
            draw_lines(self.draw, fitted, x, y, ink)

        self.reserve(box)
        return box

    def _legible_ink(self, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
        """Pick whichever ink genuinely reads against what is behind it.

        A light/dark threshold is not enough: mid-tone foliage reads as "light"
        yet still swallows dark text.
        """
        from PIL import ImageStat

        left, top, right, bottom = box
        left, top = max(left, 0), max(top, 0)
        right, bottom = min(right, self.width), min(bottom, self.height)
        if right <= left or bottom <= top:
            return self.on_image

        patch = self.image.crop((left, top, right, bottom)).convert("RGB")
        channels = ImageStat.Stat(patch).mean
        mean: tuple[int, int, int] = (
            int(channels[0]),
            int(channels[1]),
            int(channels[2]),
        )
        light, dark = self.on_image, self.ink
        return light if contrast_ratio(light, mean) >= contrast_ratio(dark, mean) else dark

    def _free_corner(self, preferred: str, width: int, height: int) -> str:
        """First corner that does not collide with already-drawn content."""
        pad = self.s(16)
        order = [preferred, "top-left", "top-right", "bottom-right", "bottom-left"]
        seen: set[str] = set()
        for corner in order:
            if corner in seen:
                continue
            seen.add(corner)
            x, y = self._corner(corner, width, height)
            box = (x, y, x + width, y + height)
            if not any(self._overlaps(box, other, pad) for other in self.reserved):
                return corner
        log.debug("No free corner for the logo; keeping %s", preferred)
        return preferred

    @property
    def contact_bar_height(self) -> int:
        """Height reserved at the base, or 0 when no contact bar is drawn."""
        if not (self.spec.layout.show_contact_bar and self.client.contact.has_any):
            return 0
        return self.s(86)

    def _corner(self, position: str, width: int, height: int) -> tuple[int, int]:
        x = self.grid.left if position.endswith("left") else self.grid.right - width
        if position.startswith("top"):
            y = self.grid.top
        else:
            # Bottom-anchored elements must sit clear of the contact bar,
            # otherwise the logo is drawn underneath it and clipped.
            y = self.height - self.contact_bar_height - self.s(28) - height
        return x, y

    def _region_is_dark(self, position: str) -> bool:
        """Sample the canvas where an element will sit to choose its ink."""
        probe = self.s(160)
        if position.endswith("left"):
            x0, x1 = self.grid.left, self.grid.left + probe
        else:
            x0, x1 = self.grid.right - probe, self.grid.right
        if position.startswith("top"):
            y0, y1 = self.grid.top, self.grid.top + probe // 2
        else:
            y0, y1 = self.grid.bottom - probe // 2, self.grid.bottom
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, self.width), min(y1, self.height)
        if x1 <= x0 or y1 <= y0:
            return True
        from PIL import ImageStat

        patch = self.image.crop((x0, y0, x1, y1)).convert("L")
        return ImageStat.Stat(patch).mean[0] < 128

    # ------------------------------------------------------------------ type

    def eyebrow(
        self, text: str, x: int, y: int, width: int, on_dark: bool, align: str = "left"
    ) -> int:
        if not text:
            return y
        # Light on photography, ink on paper. The accent belongs to the
        # headline word and the pills, not to a small tracked-out label.
        color = self.on_image if on_dark else self.ink
        size = self.s(26)
        font = self.fonts.get("bold", size)
        label = text.upper()
        tracking = self.s(3)
        line_width = tracked_width(label, font, tracking)
        start_x = x + (width - line_width) // 2 if align == "center" else x
        from .typography import _draw_tracked

        _draw_tracked(self.draw, label, start_x, y, font, color, tracking)
        # Clear the cap height plus breathing room so a following accent
        # rule or headline never collides with the label.
        return y + int(size * 1.75)

    def headline(
        self,
        text: str,
        x: int,
        y: int,
        width: int,
        max_height: int,
        on_dark: bool,
        align: str = "left",
        max_size: int | None = None,
    ) -> int:
        color = self.on_image if on_dark else self.ink
        fitted = fit_text(
            text.upper(),
            self.fonts,
            "display",
            width,
            max_height,
            max_size or self.s(116),
            self.s(44),
            line_spacing=0.98,
            max_lines=3,
        )
        if fitted.size < self.s(56):
            self.warnings.append(
                f"headline rendered at {fitted.size}px - it may not survive thumbnail scaling"
            )
        self.reserve((x, y, x + width, y + fitted.height))
        return draw_lines(self.draw, fitted, x, y, color, align=align, box_width=width)

    def headline_two_tone(
        self,
        text: str,
        accent_word: str,
        x: int,
        y: int,
        width: int,
        max_height: int,
        on_dark: bool,
        align: str = "left",
        max_size: int | None = None,
    ) -> int:
        """Headline with one word in the accent colour.

        The device that appears in almost every reference flyer the operator
        supplied. Falls back to a flat headline when the accent word is absent
        from the text or the accent has too little contrast to read.
        """
        label = text.upper()
        target = accent_word.upper().strip()
        base = self.on_image if on_dark else self.ink

        if not target or target not in label:
            return self.headline(text, x, y, width, max_height, on_dark, align, max_size)

        # A saturated accent word is read by hue against the surrounding white
        # words, not by luminance against the photograph. WCAG contrast is the
        # wrong test here: pure red on a dark scrim scores ~2.5 yet is exactly
        # what the approved references do. Only intervene when the accent would
        # genuinely disappear into the background.
        probe = (x, y, x + width, min(y + max_height, self.height))
        background = self._mean_of(probe)
        accent_ink = self.accent
        if contrast_ratio(accent_ink, background) < 1.9:
            # Nudge, do not bleach: keep the hue, lift the value just enough.
            accent_ink = lighten(self.accent, 0.22)
            if contrast_ratio(accent_ink, background) < 1.5:
                return self.headline(text, x, y, width, max_height, on_dark, align, max_size)

        fitted = fit_text(
            label,
            self.fonts,
            "display",
            width,
            max_height,
            max_size or self.s(116),
            self.s(44),
            line_spacing=0.98,
            max_lines=3,
        )
        if fitted.size < self.s(56):
            self.warnings.append(
                f"headline rendered at {fitted.size}px - it may not survive thumbnail scaling"
            )

        cursor = y
        for line in fitted.lines:
            line_width = measure(line, fitted.font)[0]
            start_x = x + (width - line_width) // 2 if align == "center" else x
            self._draw_line_two_tone(line, target, start_x, cursor, fitted.font, base, accent_ink)
            cursor += fitted.line_height

        self.reserve((x, y, x + width, y + fitted.height))
        return cursor

    def _draw_line_two_tone(
        self,
        line: str,
        target: str,
        x: int,
        y: int,
        font,
        base: tuple[int, int, int],
        accent: tuple[int, int, int],
    ) -> None:
        """Draw one line, colouring only whole words that match ``target``."""
        cursor = x
        space = measure(" ", font)[0]
        for index, word in enumerate(line.split(" ")):
            if index:
                cursor += space
            stripped = word.strip(".,:;!?\u2019'\"")
            colour = accent if stripped == target else base
            self.draw.text((cursor, y), word, font=font, fill=colour)
            cursor += measure(word, font)[0]

    def _mean_of(self, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
        from PIL import ImageStat

        left, top, right, bottom = box
        left, top = max(left, 0), max(top, 0)
        right, bottom = min(right, self.width), min(bottom, self.height)
        if right <= left or bottom <= top:
            return (0, 0, 0)
        channels = ImageStat.Stat(self.image.crop((left, top, right, bottom)).convert("RGB")).mean
        return (int(channels[0]), int(channels[1]), int(channels[2]))

    def lead_pill(self, text: str, x: int, y: int, max_width: int) -> int:
        """Solid accent pill carrying the supporting line.

        The Arruda reference renders its support line this way rather than as
        plain text: it separates the hook from the proof row and gives the
        accent colour a second, deliberate appearance.
        """
        if not text:
            return y

        label = text
        size = self.s(30)
        font = self.fonts.get("bold", size)
        pad_x, pad_y = self.s(30), self.s(16)

        while measure(label, font)[0] + pad_x * 2 > max_width and size > self.s(18):
            size -= 2
            font = self.fonts.get("bold", size)

        text_width = measure(label, font)[0]
        width = min(text_width + pad_x * 2, max_width)
        height = size + pad_y * 2

        from .composition import best_text_color

        ink = hex_to_rgb(best_text_color(self.accent))
        pill = rounded_rect((width, height), height // 2, (*self.accent, 255))
        self.paste(pill, (x, y))
        self.draw.text(
            (x + (width - text_width) // 2, y + pad_y - self.s(4)), label, font=font, fill=ink
        )
        self.reserve((x, y, x + width, y + height))
        return y + height

    def contact_footer(self, extra: list[str] | None = None, mark_width: int = 0) -> int:
        """Small contact line bottom-left, logo bottom-right.

        The base treatment in the reference flyers: the phone number is legible
        but restrained, and the mark sits opposite it rather than competing
        with the headline.
        """
        contact = self.client.contact
        primary_parts = [p for p in (contact.phone, contact.website) if p]
        if not primary_parts and not extra:
            return self.grid.bottom

        line_one = "   |   ".join(primary_parts)
        line_two = "   |   ".join([self.client.company_name, *(extra or [])])

        size_one = self.s(31)
        size_two = self.s(23)
        available = self.grid.content_width - mark_width - (self.s(40) if mark_width else 0)
        font_one = self.fonts.get("bold", size_one)
        font_two = self.fonts.get("body", size_two)

        # Shrink rather than overrun the mark.
        while mark_width and measure(line_one, font_one)[0] > available and size_one > self.s(20):
            size_one -= 1
            font_one = self.fonts.get("bold", size_one)
        while mark_width and measure(line_two, font_two)[0] > available and size_two > self.s(15):
            size_two -= 1
            font_two = self.fonts.get("body", size_two)

        gap = self.s(8)
        block_height = size_one + gap + size_two
        y = self.grid.bottom - block_height

        self.draw.text((self.grid.left, y), line_one, font=font_one, fill=self.on_image)
        self.draw.text(
            (self.grid.left, y + size_one + gap),
            line_two,
            font=font_two,
            fill=mix(self.on_image, self.primary, 0.22),
        )
        used = max(measure(line_one, font_one)[0], measure(line_two, font_two)[0])
        self.reserve((self.grid.left, y, self.grid.left + used + self.s(24), self.grid.bottom))

        # The mark sits opposite the contact line, vertically centred against
        # it, exactly as the reference flyers place it.
        if mark_width:
            self._footer_band = (y, self.grid.bottom)
        return y

    def footer_mark(self, max_width: int | None = None) -> tuple[int, int, int, int] | None:
        """Draw the mark right-aligned inside the contact footer band."""
        band = self._footer_band
        if band is None:
            return self.logo("bottom-right")

        width_cap = max_width or self.s(280)
        artwork = None
        path = self.context.logo_path
        if path and path.exists():
            try:
                artwork = Image.open(path).convert("RGBA")
                artwork.thumbnail((width_cap, self.s(80)), Image.Resampling.LANCZOS)
            except Exception:
                artwork = None

        top, bottom = band
        if artwork is not None:
            x = self.grid.right - artwork.width
            y = top + (bottom - top - artwork.height) // 2
            self.paste(artwork, (x, y))
            return (x, y, x + artwork.width, y + artwork.height)

        fitted = fit_text(
            self.client.company_name.upper(),
            self.fonts,
            "headline",
            width_cap,
            bottom - top,
            self.s(30),
            self.s(16),
            max_lines=2,
        )
        x = self.grid.right - fitted.width
        y = top + (bottom - top - fitted.height) // 2
        draw_lines(self.draw, fitted, x, y, self.on_image)
        return (x, y, x + fitted.width, y + fitted.height)

    def chip_row(
        self,
        labels: list[str],
        x: int,
        y: int,
        width: int,
        style: str = "glass",
    ) -> int:
        """A row of rounded pill labels.

        ``glass`` is the translucent treatment used over photography;
        ``accent`` is a solid brand pill. Wraps onto a second row rather than
        shrinking the type past legibility.
        """
        if not labels:
            return y

        size = self.s(24)
        font = self.fonts.get("bold", size)
        pad_x, pad_y = self.s(22), self.s(14)
        gap = self.s(12)
        radius = self.s(12)

        rows: list[list[tuple[str, int]]] = [[]]
        used = 0
        for label in labels[:4]:
            text = label.upper()
            chip_width = measure(text, font)[0] + pad_x * 2
            if used + chip_width > width and rows[-1]:
                rows.append([])
                used = 0
            rows[-1].append((text, chip_width))
            used += chip_width + gap

        cursor_y = y
        height = size + pad_y * 2
        for row in rows:
            cursor_x = x
            for text, chip_width in row:
                if style == "accent":
                    fill = (*self.accent, 255)
                    from .composition import best_text_color

                    ink = hex_to_rgb(best_text_color(self.accent))
                else:
                    fill = (255, 255, 255, 64)
                    ink = self.on_image
                pill = rounded_rect((chip_width, height), radius, fill)
                self.paste(pill, (cursor_x, cursor_y))
                if style == "glass":
                    outline = Image.new("RGBA", (chip_width, height), (0, 0, 0, 0))
                    ImageDraw.Draw(outline).rounded_rectangle(
                        (0, 0, chip_width - 1, height - 1),
                        radius=radius,
                        outline=(255, 255, 255, 90),
                        width=max(self.s(2), 1),
                    )
                    self.paste(outline, (cursor_x, cursor_y))
                text_width = measure(text, font)[0]
                self.draw.text(
                    (cursor_x + (chip_width - text_width) // 2, cursor_y + pad_y - self.s(3)),
                    text,
                    font=font,
                    fill=ink,
                )
                cursor_x += chip_width + gap
            self.reserve((x, cursor_y, x + width, cursor_y + height))
            cursor_y += height + gap

        return cursor_y

    def cta_phone_bar(self, cta: str, y: int) -> tuple[int, int, int, int]:
        """CTA and phone number together in one accent pill.

        The base treatment in the operator's references: the action and the way
        to take it sit in the same object, at readable size.
        """
        phone = self.client.contact.phone
        label = cta.upper()
        size = self.s(32)
        font = self.fonts.get("bold", size)
        phone_font = self.fonts.get("bold", self.s(34))

        pad_x, pad_y = self.s(40), self.s(24)
        gap = self.s(28)
        text_width = measure(label, font)[0]
        phone_width = measure(phone, phone_font)[0] if phone else 0
        inner = text_width + (gap + phone_width if phone else 0)

        bar_width = min(inner + pad_x * 2, self.grid.content_width)
        bar_height = max(size, self.s(34)) + pad_y * 2
        x = self.grid.left + (self.grid.content_width - bar_width) // 2

        from .composition import best_text_color

        ink = hex_to_rgb(best_text_color(self.accent))
        pill = rounded_rect((bar_width, bar_height), bar_height // 2, (*self.accent, 255))
        self.paste(pill, (x, y))

        cursor = x + (bar_width - inner) // 2
        self.draw.text((cursor, y + pad_y - self.s(2)), label, font=font, fill=ink)
        if phone:
            cursor += text_width + gap
            self.draw.text((cursor, y + pad_y - self.s(4)), phone, font=phone_font, fill=ink)

        box = (x, y, x + bar_width, y + bar_height)
        self.reserve(box)
        return box

    def headline_staggered(
        self,
        text: str,
        x: int,
        y: int,
        width: int,
        max_height: int,
        max_size: int | None = None,
        stagger: float = 0.16,
    ) -> int:
        """Large white headline whose lines step progressively to the right.

        The device in the Harford reference. Each line starts further in than
        the last, which gives a plain white headline movement without needing a
        scrim, an accent or any other furniture.
        """
        # The stagger eats into the usable width: the last line starts furthest
        # right, so fit the type to what is left or it runs off the edge.
        usable = int(width * (1.0 - stagger))
        fitted = fit_text(
            text.upper(),
            self.fonts,
            "display",
            usable,
            max_height,
            max_size or self.s(150),
            self.s(56),
            line_spacing=1.02,
            max_lines=3,
        )
        if not fitted.lines:
            return y

        step = int(width * stagger / max(len(fitted.lines) - 1, 1))
        cursor = y
        for index, line in enumerate(fitted.lines):
            self._draw_soft_shadow(line, x + step * index, cursor, fitted.font)
            self.draw.text((x + step * index, cursor), line, font=fitted.font, fill=self.on_image)
            cursor += fitted.line_height

        self.reserve((x, y, x + width, cursor))
        return cursor

    def _draw_soft_shadow(self, text: str, x: int, y: int, font) -> None:
        """A faint drop shadow so white type survives an unscrimmed photo.

        The `statement` layout deliberately has no scrim, so the type needs its
        own separation from whatever is behind it.
        """
        offset = max(self.s(3), 1)
        shadow = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).text((x + offset, y + offset), text, font=font, fill=(0, 0, 0, 90))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=self.s(6)))
        self.image.paste(
            Image.alpha_composite(self.image.convert("RGBA"), shadow).convert("RGB"), (0, 0)
        )

    def support(
        self,
        text: str,
        x: int,
        y: int,
        width: int,
        max_height: int,
        on_dark: bool,
        align: str = "left",
    ) -> int:
        if not text:
            return y
        color = lighten(self.on_image, 0.0) if on_dark else mix(self.ink, self.paper, 0.25)
        fitted = fit_text(
            text,
            self.fonts,
            "subhead",
            width,
            max_height,
            self.s(38),
            self.s(20),
            line_spacing=1.28,
            max_lines=3,
        )
        return draw_lines(self.draw, fitted, x, y, color, align=align, box_width=width)

    def bullets(
        self,
        items: list[str],
        x: int,
        y: int,
        width: int,
        on_dark: bool,
        align: str = "left",
    ) -> int:
        if not items:
            return y
        color = self.on_image if on_dark else self.ink
        size = self.s(28)
        font = self.fonts.get("body", size)
        marker = self.s(11)
        gap = self.s(22)
        cursor = y
        for item in items[:3]:
            text_x = x + marker * 3
            if align == "center":
                text_width = measure(item, font)[0]
                text_x = x + (width - text_width) // 2
            else:
                self.draw.ellipse(
                    (x, cursor + size * 0.35, x + marker, cursor + size * 0.35 + marker),
                    fill=self.accent,
                )
            self.draw.text((text_x, cursor), item, font=font, fill=color)
            cursor += size + gap
        return cursor

    # -------------------------------------------------------------- elements

    def cta_button(
        self,
        text: str,
        x: int,
        y: int,
        max_width: int,
        align: str = "left",
    ) -> tuple[int, int, int, int]:
        """Pill CTA in the accent colour with automatically contrasting ink."""
        label = text.upper()
        size = self.s(34)
        font = self.fonts.get("bold", size)
        tracking = self.s(2)

        while tracked_width(label, font, tracking) > max_width - self.s(80) and size > self.s(20):
            size -= 2
            font = self.fonts.get("bold", size)

        text_width = tracked_width(label, font, tracking)
        pad_x, pad_y = self.s(46), self.s(26)
        button_width = min(text_width + pad_x * 2, max_width)
        button_height = size + pad_y * 2

        if align == "center":
            x = x + (max_width - button_width) // 2

        from .composition import best_text_color

        ink_hex = best_text_color(self.accent)
        pill = rounded_rect((button_width, button_height), button_height // 2, (*self.accent, 255))
        self.paste(pill, (x, y))

        from .typography import _draw_tracked

        _draw_tracked(
            self.draw,
            label,
            x + (button_width - text_width) // 2,
            y + pad_y - self.s(3),
            font,
            hex_to_rgb(ink_hex),
            tracking,
        )
        box = (x, y, x + button_width, y + button_height)
        self.reserve(box)
        return box

    def offer_badge(self, text: str, center: tuple[int, int]) -> None:
        if not text:
            return
        diameter = self.s(300)
        cx, cy = center
        badge = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(badge)
        bdraw.ellipse((0, 0, diameter - 1, diameter - 1), fill=(*self.accent, 255))
        bdraw.ellipse(
            (self.s(14), self.s(14), diameter - self.s(15), diameter - self.s(15)),
            outline=(*darken(self.accent, 0.35), 255),
            width=max(self.s(3), 2),
        )
        self.paste(badge, (cx - diameter // 2, cy - diameter // 2))

        from .composition import best_text_color

        ink = hex_to_rgb(best_text_color(self.accent))
        fitted = fit_text(
            text.upper(),
            self.fonts,
            "display",
            int(diameter * 0.72),
            int(diameter * 0.6),
            self.s(58),
            self.s(20),
            line_spacing=1.02,
            max_lines=3,
        )
        draw_lines(
            self.draw,
            fitted,
            cx - int(diameter * 0.36),
            cy - fitted.height // 2,
            ink,
            align="center",
            box_width=int(diameter * 0.72),
        )

    def accent_rule(
        self,
        x: int,
        y: int,
        width: int | None = None,
        align: str = "left",
        box_width: int | None = None,
    ) -> int:
        rule_width = width or self.s(120)
        thickness = self.s(9)
        if align == "center" and box_width:
            x = x + (box_width - rule_width) // 2
        self.draw.rectangle((x, y, x + rule_width, y + thickness), fill=self.accent)
        return y + thickness

    def contact_bar(self, on_dark: bool = True) -> None:
        """Phone / website strip pinned to the bottom edge."""
        contact = self.client.contact
        parts = [p for p in (contact.phone, contact.website) if p]
        if not parts:
            return

        height = self.s(86)
        top = self.height - height
        color = darken(self.primary, 0.15)
        self.draw.rectangle((0, top, self.width, self.height), fill=color)

        size = self.s(30)
        font = self.fonts.get("bold", size)
        ink = hex_to_rgb("#FFFFFF") if contrast_ratio("#FFFFFF", color) >= 4.5 else self.ink

        y = top + (height - size) // 2 - self.s(4)
        if len(parts) == 1:
            width = measure(parts[0], font)[0]
            self.draw.text(((self.width - width) // 2, y), parts[0], font=font, fill=ink)
        else:
            self.draw.text((self.grid.left, y), parts[0], font=font, fill=ink)
            right_width = measure(parts[1], font)[0]
            self.draw.text((self.grid.right - right_width, y), parts[1], font=font, fill=ink)
            divider_x = self.width // 2
            self.draw.rectangle(
                (divider_x - 1, top + self.s(24), divider_x + 1, self.height - self.s(24)),
                fill=lighten(color, 0.25),
            )

    def disclaimer(self, text: str, y: int, on_dark: bool) -> None:
        if not text:
            return
        size = self.s(18)
        color = mix(self.on_image if on_dark else self.ink, self.primary, 0.35)
        fitted = fit_text(
            text, self.fonts, "body", self.grid.content_width, size * 3, size, self.s(13)
        )
        draw_lines(self.draw, fitted, self.grid.left, y, color)

    def panel_label(self, text: str, box: tuple[int, int, int, int]) -> None:
        """BEFORE / AFTER style tag pinned to a panel corner."""
        left, top, right, bottom = box
        size = self.s(26)
        font = self.fonts.get("bold", size)
        tracking = self.s(3)
        label = text.upper()
        text_width = tracked_width(label, font, tracking)
        pad = self.s(20)
        tag_width, tag_height = text_width + pad * 2, size + pad
        tag = rounded_rect((tag_width, tag_height), self.s(6), (*self.primary, 235))
        x, y = left + self.s(24), bottom - tag_height - self.s(24)
        self.paste(tag, (x, y))
        from .typography import _draw_tracked

        _draw_tracked(
            self.draw, label, x + pad, y + pad // 2 - self.s(2), font, self.on_image, tracking
        )

    # ------------------------------------------------------------- utilities

    def _bg_at(self, y: int) -> tuple[int, int, int]:
        from PIL import ImageStat

        y = min(max(y, 0), self.height - 2)
        patch = self.image.crop(
            (self.grid.left, y, min(self.grid.left + self.s(200), self.width), y + 2)
        )
        stat = ImageStat.Stat(patch.convert("RGB"))
        return tuple(int(v) for v in stat.mean)  # type: ignore[return-value]

    def region_is_dark(self, box: tuple[int, int, int, int]) -> bool:
        from PIL import ImageStat

        left, top, right, bottom = box
        left, top = max(left, 0), max(top, 0)
        right, bottom = min(right, self.width), min(bottom, self.height)
        if right <= left or bottom <= top:
            return True
        patch = self.image.crop((left, top, right, bottom)).convert("L")
        return ImageStat.Stat(patch).mean[0] < 130

    def finish(self) -> Image.Image:
        return self.image


def render_flyer(spec: FlyerSpecification, context: RenderContext) -> tuple[Image.Image, list[str]]:
    """Render one specification into an image plus any renderer warnings."""
    from .templates import LAYOUT_BUILDERS

    builder = LAYOUT_BUILDERS.get(spec.layout.name)
    if builder is None:
        available = ", ".join(sorted(LAYOUT_BUILDERS))
        raise RenderError(f"Unknown layout {spec.layout.name!r}. Available: {available}")

    renderer = FlyerRenderer(spec, context)
    builder(renderer)
    image = renderer.finish()

    if image.size != (spec.canvas.width, spec.canvas.height):  # pragma: no cover - guard
        raise RenderError(
            f"Renderer produced {image.size}, expected {(spec.canvas.width, spec.canvas.height)}"
        )
    return image, renderer.warnings


def resolve_render_context(client: Client, asset_paths: dict[str, Path]) -> RenderContext:
    from ..clients.loader import resolve_client_path

    settings = get_settings()
    logo = resolve_client_path(client, client.brand.logo_path)
    return RenderContext(
        client=client,
        asset_paths=asset_paths,
        logo_path=logo,
        fonts=FontLibrary(settings.paths.fonts),
    )
