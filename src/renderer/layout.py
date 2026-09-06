"""Layout primitives: gradients, glass cards, rounded badges, and CTA buttons."""

from typing import Tuple

from PIL import Image, ImageDraw


def create_vertical_gradient(
    width: int,
    height: int,
    top_color: Tuple[int, int, int, int],
    bottom_color: Tuple[int, int, int, int]
) -> Image.Image:
    """Creates a vertical RGBA linear gradient."""
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)

    r1, g1, b1, a1 = top_color
    r2, g2, b2, a2 = bottom_color

    for y in range(height):
        factor = y / max(1, height - 1)
        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)
        a = int(a1 + (a2 - a1) * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b, a))

    return gradient

def draw_rounded_card(
    base_image: Image.Image,
    box: Tuple[int, int, int, int],
    bg_color: Tuple[int, int, int, int] = (28, 28, 30, 215),
    border_color: Tuple[int, int, int, int] = (255, 255, 255, 40),
    radius: int = 16,
    border_width: int = 1
) -> Image.Image:
    """Draws a semi-transparent glass card with rounded corners and subtle border."""
    overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=bg_color, outline=border_color, width=border_width)

    return Image.alpha_composite(base_image.convert("RGBA"), overlay)

def draw_pill_button(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int] = (128, 39, 43),
    outline: Tuple[int, int, int] = (255, 255, 255),
    radius: int = 24
) -> None:
    """Draws a high-contrast pill button."""
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1)
