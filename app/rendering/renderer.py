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
from . import finishing
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
        self.logo_drawn = False
        # Grading a 4056px drone still costs real time, and a layout can use
        # the same photograph in two places, so the finished source is cached
        # per render rather than re-graded per panel.
        self._finished: dict[Path, Image.Image] = {}
        self._footer_band: tuple[int, int] | None = None
        # Boxes other components have claimed. The logo relocates around them
        # rather than being drawn underneath the copy stack.
        self.reserved: list[tuple[int, int, int, int]] = []
        # Every block of copy actually drawn, checked for collisions once the
        # layout finishes. A layout that miscalculates its vertical budget
        # draws the button on top of the body text and nothing downstream can
        # see it - the pixels are valid, the flyer is not.
        self.copy_boxes: list[tuple[str, tuple[int, int, int, int]]] = []

    def reserve(self, box: tuple[int, int, int, int]) -> None:
        self.reserved.append(box)

    def note_copy(self, name: str, box: tuple[int, int, int, int]) -> None:
        """Record where a block of copy was actually drawn."""
        if box[2] > box[0] and box[3] > box[1]:
            self.copy_boxes.append((name, box))

    def check_collisions(self) -> None:
        """Warn when two blocks of copy were drawn over each other.

        Tolerates a few pixels of overlap: tightly stacked type often shares a
        row of descender space, and flagging that would make the check noise.
        Anything larger is a layout arithmetic error.
        """
        tolerance = self.s(6)
        for index, (name_a, box_a) in enumerate(self.copy_boxes):
            for name_b, box_b in self.copy_boxes[index + 1 :]:
                overlap_x = min(box_a[2], box_b[2]) - max(box_a[0], box_b[0])
                overlap_y = min(box_a[3], box_b[3]) - max(box_a[1], box_b[1])
                if overlap_x > tolerance and overlap_y > tolerance:
                    self.warnings.append(
                        f"{name_a} and {name_b} overlap by {overlap_x}x{overlap_y}px"
                    )

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
        from ..assets.image_utils import crop_to_aspect
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
            source = self.finished_source(path)
        except Exception as exc:
            log.warning("Falling back to a procedural panel; %s is unusable: %s", path, exc)
            self.warnings.append(f"asset {asset_id} unreadable")
            self.procedural_panel(box)
            return False

        focal = FocalPoint()
        cropped = crop_to_aspect(source, width, height, mode=crop, focal=focal)
        if grayscale:
            cropped = ImageOps.grayscale(cropped).convert("RGB")
        # Sharpening is only meaningful once the photo is at its final pixel
        # size, so it happens here rather than in the grade.
        cropped = finishing.sharpen_output(cropped, get_settings().photo_grade)
        self.image.paste(cropped, (left, top))
        return True

    def finished_source(self, path: Path) -> Image.Image:
        """Load a photograph and apply the house grade, once per render.

        Grading happens at source resolution and before any crop, because
        black point and local contrast are properties of the whole frame; if
        you grade a crop, two panels cut from one photo come out looking like
        two different photos.
        """
        from ..assets.image_utils import load_rgb

        cached = self._finished.get(path)
        if cached is not None:
            return cached

        source = load_rgb(path)
        grade = get_settings().photo_grade
        if grade != "none":
            source = finishing.finish(source, grade)
        self._finished[path] = source
        return source

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

    def solid_band(
        self,
        box: tuple[int, int, int, int],
        color: tuple[int, int, int],
        alpha: float = 1.0,
    ) -> None:
        """A flat block. ``alpha`` below 1 lets the photograph read through it."""
        left, top, right, bottom = box
        if alpha >= 1.0:
            self.draw.rectangle((left, top, right, bottom), fill=color)
            return
        width, height = max(right - left, 1), max(bottom - top, 1)
        layer = Image.new("RGBA", (width, height), (*color, int(round(alpha * 255))))
        self.paste(layer, (left, top))

    # -------------------------------------------------------------- branding

    def logo(self, position: str, force: bool = False) -> tuple[int, int, int, int] | None:
        """Draw the client logo, or a typographic wordmark when none exists.

        If the requested corner is already occupied by copy, the logo moves to
        the best free corner instead of being drawn on top of it.
        """
        if position == "none":
            return None

        # The mark has two lines of type in it ("ALL ELITE" over "ROOFING &
        # SIDING"), so a box sized for a single-line wordmark renders the
        # second line as an unreadable smear. These are the smallest values at
        # which the lower line still reads on a phone.
        max_width = self.s(380)
        max_height = self.s(132)

        path = self.context.logo_path
        artwork: Image.Image | None = None
        if path and path.exists():
            try:
                artwork = Image.open(path).convert("RGBA")
                artwork = self.fit_logo(artwork, max_width, max_height)
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
        self.logo_drawn = True
        return box

    def fit_logo(self, artwork: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Scale the mark to fill its reserved box in either direction.

        ``Image.thumbnail`` only ever shrinks, so on a 2160px canvas a small
        logo file would quietly render at its native size - roughly half as
        wide as the layout reserved for it, which reads as a mistake rather
        than as restraint. Enlarging is the lesser evil, but it costs
        sharpness, so anything past a modest stretch is recorded as a warning
        for the quality gate to pick up.
        """
        ratio = min(max_width / artwork.width, max_height / artwork.height)
        if ratio > 1.15:
            self.warnings.append(
                f"logo upscaled {ratio:.1f}x from {artwork.width}px - supply a larger file"
            )
        size = (
            max(int(round(artwork.width * ratio)), 1),
            max(int(round(artwork.height * ratio)), 1),
        )
        if size == artwork.size:
            return artwork
        return artwork.resize(size, Image.Resampling.LANCZOS)

    def assess_legibility(
        self,
        box: tuple[int, int, int, int],
        ink: tuple[int, int, int],
        what: str,
        minimum: float = 3.0,
    ) -> None:
        """Warn when type is about to be set on a background it cannot beat.

        Call this *before* drawing. A mean-luminance test is not enough: a busy
        neighbourhood aerial averages to a comfortable mid-grey while half its
        pixels are bright sky and half are dark foliage, so the type reads
        against neither. Sampling a grid and counting how many individual
        samples fail the contrast threshold catches exactly that case, which
        is the one that keeps producing flyers nobody can read.

        ``minimum`` follows WCAG: 3:1 is enough behind a headline set 100px
        tall, but a 40px support line needs 4.5:1. Holding both to the headline
        figure passed a support line printed over a sunlit driveway.
        """
        left, top = max(box[0], 0), max(box[1], 0)
        right, bottom = min(box[2], self.width), min(box[3], self.height)
        if right - left < 8 or bottom - top < 8:
            return

        patch = self.image.crop((left, top, right, bottom)).convert("RGB")
        # 24x24 samples is enough to characterise a background and costs
        # nothing next to the render itself.
        patch = patch.resize((24, 24), Image.Resampling.BILINEAR)
        samples = list(patch.getdata())
        failing = sum(1 for pixel in samples if contrast_ratio(ink, pixel) < minimum)
        share = failing / len(samples)
        if share > 0.25:
            self.warnings.append(
                f"{what} sits on a background it does not read against "
                f"({share:.0%} of it below {minimum:g}:1 contrast)"
            )

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
        self.note_copy("eyebrow", (start_x, y, start_x + line_width, y + size))
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
        box = (x, y, x + width, y + fitted.height)
        if on_dark:
            self.assess_legibility(box, color, "headline")
        self.reserve(box)
        self.note_copy("headline", box)
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
                artwork = self.fit_logo(artwork, width_cap, self.s(80))
            except Exception:
                artwork = None

        top, bottom = band
        if artwork is not None:
            x = self.grid.right - artwork.width
            y = top + (bottom - top - artwork.height) // 2
            self.paste(artwork, (x, y))
            self.logo_drawn = True
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
        self.logo_drawn = True
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

    def headline_blocks(
        self,
        text: str,
        x: int,
        y: int,
        width: int,
        max_height: int,
        block_color: tuple[int, int, int] | None = None,
        ink: tuple[int, int, int] | None = None,
        max_size: int | None = None,
    ) -> int:
        """Headline set on solid colour blocks that hug each line.

        The device in All Elite's approved flyers. The block is what makes the
        type legible, so the photograph underneath stays at full brightness
        instead of being flattened by a scrim. Each line gets its own block
        sized to that line, which is why the right edge is ragged.
        """
        fill = block_color or self.primary
        letter = ink or hex_to_rgb("#EFE6DA")

        fitted = fit_text(
            text.upper(),
            self.fonts,
            "display",
            width,
            max_height,
            max_size or self.s(104),
            self.s(46),
            line_spacing=1.16,
            max_lines=3,
        )
        if not fitted.lines:
            return y

        from .typography import _draw_tracked

        pad_x, pad_y = self.s(22), self.s(12)
        block_h = fitted.size + pad_y * 2
        cursor = y

        # The approved flyers letter-space the longest line so it fills the
        # measure, and let its block bleed off the right edge. Shorter lines
        # keep a tight block, which is what gives the ragged right edge.
        widths = [measure(line, fitted.font)[0] for line in fitted.lines]
        longest = max(widths) if widths else 0
        target = width - pad_x * 2

        for line, line_width in zip(fitted.lines, widths, strict=False):
            is_longest = line_width == longest
            tracking = 0
            if is_longest and len(line) > 1 and line_width < target:
                tracking = min((target - line_width) // (len(line) - 1), self.s(14))

            drawn = line_width + tracking * max(len(line) - 1, 0)
            block_w = drawn + pad_x * 2
            if is_longest:
                block_w = min(block_w + self.s(18), self.width - x)  # bleed past the margin

            block = Image.new("RGBA", (block_w, block_h), (*fill, 235))
            self.paste(block, (x, cursor))

            text_y = cursor + pad_y - self.s(4)
            if tracking:
                _draw_tracked(self.draw, line, x + pad_x, text_y, fitted.font, letter, tracking)
            else:
                self._draw_soft_shadow(line, x + pad_x, text_y, fitted.font)
                self.draw.text((x + pad_x, text_y), line, font=fitted.font, fill=letter)

            self.reserve((x, cursor, x + block_w, cursor + block_h))
            cursor += block_h + self.s(4)

        return cursor

    def numbered_callout(
        self, numeral: str, lead: str, body: str, x: int, y: int, width: int
    ) -> int:
        """Oversized numeral beside a short stack of text, drawn on the photo.

        The device the approved carousels use to number a series:
        "3  LOOK OUT FOR THESE / SIGNS TO PREVENT A TOTAL STRUCTURAL MELTDOWN".
        Drawn directly on the photograph with a soft shadow, no panel.
        """
        if not (numeral or lead or body):
            return y

        cursor_x = x
        if numeral:
            size = self.s(118)
            font = self.fonts.get("display", size)
            self._draw_soft_shadow(numeral, x, y, font)
            self.draw.text((x, y), numeral, font=font, fill=self.on_image)
            cursor_x = x + measure(numeral, font)[0] + self.s(24)

        text_width = width - (cursor_x - x)
        lead_size = self.s(44)
        lead_font = self.fonts.get("display", lead_size)
        cursor_y = y + self.s(10)
        if lead:
            head = lead.upper()
            self._draw_soft_shadow(head, cursor_x, cursor_y, lead_font)
            self.draw.text((cursor_x, cursor_y), head, font=lead_font, fill=self.on_image)
            cursor_y += int(lead_size * 1.12)

        rest = body.upper()
        if rest:
            fitted = fit_text(
                rest,
                self.fonts,
                "subhead",
                text_width + self.s(40),
                self.s(150),
                self.s(36),
                self.s(20),
                line_spacing=1.2,
                max_lines=3,
            )
            for line in fitted.lines:
                self._draw_soft_shadow(line, cursor_x, cursor_y, fitted.font)
                self.draw.text((cursor_x, cursor_y), line, font=fitted.font, fill=self.on_image)
                cursor_y += fitted.line_height

        self.reserve((x, y, x + width, cursor_y))
        return cursor_y

    def blurred_backdrop(self, asset_id: str | None, crop: str = "focal") -> None:
        """Fill the canvas with a heavily blurred copy of the photograph.

        The approved educational cards float a sharp detail strip over a blurred
        version of the same image. It fills the frame without competing with the
        body copy, and it means a 16:9 frame can sit in a 4:5 canvas without
        letterboxing.
        """
        from ..assets.image_utils import crop_to_aspect

        path = self.context.asset_paths.get(asset_id or "")
        if path is None or not path.exists():
            self.procedural_panel((0, 0, self.width, self.height))
            return
        try:
            source = self.finished_source(path)
        except Exception:
            self.procedural_panel((0, 0, self.width, self.height))
            return
        filled = crop_to_aspect(source, self.width, self.height, mode=crop)
        self.image.paste(filled.filter(ImageFilter.GaussianBlur(radius=self.s(26))), (0, 0))

    def detail_strip(self, asset_id: str | None, top: float, bottom: float) -> None:
        """A sharp, full-width band of the photograph over the blurred backdrop."""
        y0, y1 = self.grid.y(top), self.grid.y(bottom)
        self.photo_panel((0, y0, self.width, y1), asset_id, "center", False)

    def body_band(
        self,
        title: str,
        blocks: list[tuple[str, str]],
        top: float = 0.60,
        bottom: float = 0.88,
    ) -> None:
        """Translucent brand band carrying a title and labelled paragraphs.

        The signature element of the client's approved carousels, and the reason
        those flyers feel substantial rather than sparse.
        """
        y0, y1 = self.grid.y(top), self.grid.y(bottom)
        band = Image.new("RGBA", (self.width, y1 - y0), (*self.primary, 214))
        self.paste(band, (0, y0))

        cream = hex_to_rgb("#F2E9DC")
        x = self.grid.left
        width = self.grid.content_width

        cursor = y0 + self.s(30)
        if title:
            size = self.s(38)
            font = self.fonts.get("display", size)
            tracking = self.s(6)
            from .typography import _draw_tracked, tracked_width

            label = title.upper()
            text_width = tracked_width(label, font, tracking)
            _draw_tracked(
                self.draw, label, x + (width - text_width) // 2, cursor, font, cream, tracking
            )
            cursor += int(size * 1.9)

        # Share the remaining height between the blocks that actually have copy,
        # so the type is sized to the space rather than truncated to fit it.
        live = [(label, text) for label, text in blocks if text]
        remaining = (y1 - self.s(24)) - cursor
        available_per_block = max(remaining // max(len(live), 1), self.s(60))

        # Fonts are built per block at the fitted size, so only the starting
        # size is needed here.
        label_size = self.s(29)

        for label, text in live:
            if not text:
                continue

            # Wrap the label and the body as ONE string at ONE width, then
            # overdraw the label in bold. Tracking two widths - a narrower first
            # line for the label, a wider one after - is what let copy run off
            # the canvas, and it silently truncated sentences when the line
            # budget ran out.
            lead = f"{label}: " if label else ""
            paragraph = f"{lead}{text}"

            # Wrap using the BOLD metrics even though most of the paragraph is
            # set in the body weight. Bold is the wider face, so wrapping to it
            # is conservative and the drawn line can only ever be shorter.
            fitted = fit_text(
                paragraph,
                self.fonts,
                "bold",
                width,
                available_per_block,
                label_size,
                self.s(16),
                line_spacing=1.30,
                max_lines=8,
            )
            body_at_size = self.fonts.get("body", fitted.size)
            label_at_size = self.fonts.get("bold", fitted.size)

            line_y = cursor
            for index, line in enumerate(fitted.lines):
                if index == 0 and lead and line.startswith(lead):
                    # Label in bold, the rest of the line in the body weight.
                    self.draw.text((x, line_y), lead, font=label_at_size, fill=cream)
                    offset = measure(lead, label_at_size)[0]
                    remainder = line[len(lead) :]
                    if remainder:
                        self.draw.text(
                            (x + offset, line_y), remainder, font=body_at_size, fill=cream
                        )
                else:
                    self.draw.text((x, line_y), line, font=body_at_size, fill=cream)
                line_y += fitted.line_height
            cursor = line_y + self.s(16)

        if cursor > y1:
            self.warnings.append("body band copy overflowed its band")
        self.reserve((0, y0, self.width, y1))

    def tagline(self, text: str = "STAY ELITE") -> None:
        """The gold tagline the approved cards sign off with."""
        size = self.s(34)
        font = self.fonts.get("display", size)
        gold = hex_to_rgb("#D9A62E")
        width = measure(text, font)[0]
        self.draw.text(
            (self.grid.right - width, self.grid.bottom - size), text, font=font, fill=gold
        )

    def brand_eyebrow(self, x: int, y: int) -> int:
        """The small company line above the headline, in brand colour."""
        label = self.client.company_name.upper()
        size = self.s(27)
        font = self.fonts.get("bold", size)
        tracking = self.s(3)
        from .typography import _draw_tracked

        colour = (
            self.primary
            if not self.region_is_dark((x, y, x + self.s(500), y + size))
            else lighten(self.primary, 0.55)
        )
        _draw_tracked(self.draw, label, x, y, font, colour, tracking)
        return y + int(size * 1.6)

    def mark_centered(self, y_bottom: int, max_width: int | None = None) -> None:
        """The full logo lockup, centred near the base, as the approved flyers place it."""
        width_cap = max_width or self.s(300)
        path = self._mark_for_background(y_bottom, width_cap)
        if path is None:
            return
        try:
            with Image.open(path) as handle:
                artwork = handle.convert("RGBA")
        except Exception as exc:
            log.warning("Logo %s could not be drawn: %s", path, exc)
            return
        artwork = self.fit_logo(artwork, width_cap, self.s(230))
        x = (self.width - artwork.width) // 2
        y = y_bottom - artwork.height

        # The mark is line art with transparent counters, so on a busy
        # photograph the driveway shows through the letterforms and it stops
        # reading as a logo. A soft plate fixes that - but the plate has to
        # agree with which mark was picked. Choosing them from the same probe
        # independently produced a white logo on a white plate.
        pad_x, pad_y = self.s(34), self.s(22)
        plate = (x - pad_x, y - pad_y, x + artwork.width + pad_x, y + artwork.height + pad_y)
        using_light_mark = "light" in path.stem.lower()
        if using_light_mark:
            self.solid_band(plate, darken(self.primary, 0.25), alpha=0.62)
        else:
            self.solid_band(plate, self.paper, alpha=0.82)

        self.paste(artwork, (x, y))
        self.reserve((x, y, x + artwork.width, y + artwork.height))
        self.logo_drawn = True

    def _mark_for_background(self, y_bottom: int, width_cap: int):
        """Pick the dark or light mark depending on what sits behind it."""
        from ..clients.loader import resolve_client_path

        probe = (
            (self.width - width_cap) // 2,
            max(y_bottom - self.s(190), 0),
            (self.width + width_cap) // 2,
            y_bottom,
        )
        if self.region_is_dark(probe) and self.client.brand.logo_dark_path:
            light = best_logo(resolve_client_path(self.client, self.client.brand.logo_dark_path))
            if light is not None:
                return light
        return self.context.logo_path

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
        box = (x, y, x + width, y + fitted.height)
        if on_dark:
            self.assess_legibility(box, color, "support line", minimum=4.5)
        self.note_copy("support", box)
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
        box = (x, y, x + width, cursor - gap)
        if on_dark:
            # Bullets are the smallest type on the flyer and were the one text
            # component with no contrast check, so a proof point could vanish
            # into a sunlit wall while the headline above it read perfectly.
            self.assess_legibility(box, color, "bullets", minimum=4.5)
        self.note_copy("bullets", box)
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
        self.note_copy("cta button", box)
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
    renderer.check_collisions()
    image = renderer.finish()

    # The client's mark goes on every flyer, without exception. A flyer that
    # cannot be traced back to the business is wasted spend.
    if not renderer.logo_drawn:
        renderer.warnings.append("no client mark was drawn - every flyer must carry the logo")

    if image.size != (spec.canvas.width, spec.canvas.height):  # pragma: no cover - guard
        raise RenderError(
            f"Renderer produced {image.size}, expected {(spec.canvas.width, spec.canvas.height)}"
        )
    return image, renderer.warnings


def best_logo(path: Path | None) -> Path | None:
    """Prefer a higher-resolution sibling of the configured logo.

    ``scripts/upscale_logo.py`` writes ``logo@6x.png`` next to ``logo.png``,
    and a proper vector export would drop in the same way. Resolving by
    pixel width rather than by filename means whichever file is actually
    largest wins, so replacing the upscale with a real export needs no config
    change.
    """
    if path is None or not path.exists():
        return path

    # Only resolution variants of *this* mark: logo.png, logo@2x.png,
    # logo@6x.png. A prefix glob also matches logo-light.png, which is the
    # white version - and since the upscales are all the same width, the light
    # one won on ties and got drawn wherever the dark one was asked for. The
    # brand colours disappeared from every flyer and nothing reported it.
    variants = [path]
    for candidate in sorted(path.parent.glob(f"{path.stem}@*{path.suffix}")):
        suffix = candidate.stem[len(path.stem) + 1 :]
        if suffix.endswith("x") and suffix[:-1].isdigit():
            variants.append(candidate)

    best, best_width = path, 0
    for candidate in variants:
        try:
            with Image.open(candidate) as handle:
                width = handle.width
        except Exception:
            continue
        if width > best_width:
            best, best_width = candidate, width
    return best


def resolve_render_context(client: Client, asset_paths: dict[str, Path]) -> RenderContext:
    from ..clients.loader import resolve_client_path

    settings = get_settings()
    logo = best_logo(resolve_client_path(client, client.brand.logo_path))
    return RenderContext(
        client=client,
        asset_paths=asset_paths,
        logo_path=logo,
        fonts=FontLibrary(settings.paths.fonts),
    )
