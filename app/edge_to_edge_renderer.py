"""Edge-to-Edge Instagram Flyer Renderer for All Elite Roofing & Siding.

Renders all flyers at exact native Instagram 4:5 Feed Dimensions (1080 x 1350 px).
- 100% full bleed: zero blurry sidebars, zero pillarboxes.
- Grid safe zone (3:4, 1012 x 1350 px) respected for all content cards, buttons, and text.
- Authentic client job site photos from 'After' and 'Completed' project folders.
- GAF Master Elite certified standard: GAF Timberline HDZ / GAF FeltBuster (ZERO ABC Pro Guard).
- Anti-AI tell compliance: zero em dashes, zero emojis.
- Clean vector icons, stars, and checkmarks (zero missing unicode glyph boxes).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# -----------------------------------------------------------------------------
# Color Palette
# -----------------------------------------------------------------------------
MAROON = (107, 21, 40)          # #6B1528
DARK_MAROON = (75, 14, 28)     # #4B0E1C
GOLD = (212, 175, 55)           # #D4AF37
LIGHT_GOLD = (245, 215, 110)    # #F5D76E
DARK_BG = (14, 18, 24)          # #0E1218
CARD_BG = (22, 28, 36)
WHITE = (255, 255, 255)
OFF_WHITE = (238, 242, 246)
MUTED = (160, 170, 180)
RED_ACCENT = (215, 45, 45)

# -----------------------------------------------------------------------------
# Asset Paths
# -----------------------------------------------------------------------------
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

LOGO_LIGHT_PATH = WORKSPACE_ROOT / "clients/all-elite/assets/logo/logo-light@6x.png"
LOGO_COLOR_PATH = WORKSPACE_ROOT / "clients/all-elite/assets/logo/logo@6x.png"

DRIVE_BASE = Path(
    "/Users/johnpineda/Library/CloudStorage/GoogleDrive-engineeringwithjp@gmail.com/My Drive/NEDA Technologies/Clients/All Elite Construction"
)

# Project & Approved Photos
PHOTO_BERGENFIELD_OVER = (
    DRIVE_BASE / "Projects/89 Hillside Ave, Bergenfield/After/Images/DJI_0167.JPG"
    if (DRIVE_BASE / "Projects/89 Hillside Ave, Bergenfield/After/Images/DJI_0167.JPG").exists()
    else WORKSPACE_ROOT / "clients/all-elite/assets/approved/DJI_0167.JPG"
)
PHOTO_ROCHELLE_FRONT = (
    DRIVE_BASE / "Projects/Completed/107 James St, Rochelle Park/Images/DJI_20260701_130550_883.jpg"
    if (DRIVE_BASE / "Projects/Completed/107 James St, Rochelle Park/Images/DJI_20260701_130550_883.jpg").exists()
    else WORKSPACE_ROOT / "clients/all-elite/assets/approved/roof_cresskill_aerial_estate_004.jpg"
)
PHOTO_GAF_INSTALL = WORKSPACE_ROOT / "clients/all-elite/assets/approved/DJI_0074.JPG"
PHOTO_CLOSTER_LUXURY = WORKSPACE_ROOT / "clients/all-elite/assets/approved/DJI_0081.JPG"

# Fonts
FONT_DIR = WORKSPACE_ROOT / "assets/fonts"
FONT_OSWALD = str(FONT_DIR / "Oswald-Bold.ttf")
FONT_BARLOW = str(FONT_DIR / "BarlowCondensed-Bold.ttf")
FONT_INTER = str(FONT_DIR / "Inter-Regular.ttf")
FONT_PLAYFAIR = str(FONT_DIR / "PlayfairDisplay-Bold.ttf")
FONT_ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def get_font(path: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        # Fallback to standard font in assets if system font not available
        alt = FONT_DIR / "BarlowCondensed-Bold.ttf"
        if alt.exists():
            try:
                return ImageFont.truetype(str(alt), size)
            except Exception:
                pass
        return ImageFont.load_default()


def get_cropped_logo(light: bool = True) -> Image.Image:
    path = LOGO_LIGHT_PATH if light else LOGO_COLOR_PATH
    if not path.exists():
        path = WORKSPACE_ROOT / "clients/all-elite/assets/logo/logo-light@6x.png"
    im = Image.open(path).convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    return im


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill,
    canvas_w: int = 1080,
) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (canvas_w - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return tw, bbox[3] - bbox[1]


def draw_centered_in_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    x1: int,
    x2: int,
    y: int,
    font: ImageFont.ImageFont,
    fill,
) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = x1 + (x2 - x1 - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return tw, bbox[3] - bbox[1]


def draw_gradient(
    im: Image.Image,
    start_y: int,
    end_y: int,
    start_alpha: int = 0,
    end_alpha: int = 240,
    color=(10, 14, 20),
) -> Image.Image:
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    h = end_y - start_y
    for i in range(h):
        y = start_y + i
        alpha = int(start_alpha + (end_alpha - start_alpha) * (i / max(1, h)))
        odraw.line([(0, y), (im.size[0], y)], fill=(color[0], color[1], color[2], alpha))
    return Image.alpha_composite(im.convert("RGBA"), overlay)


def crop_center_fill(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    ratio = max(target_w / img.width, target_h / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    scaled = img.resize(new_size, Image.Resampling.LANCZOS)
    x_off = (scaled.width - target_w) // 2
    y_off = (scaled.height - target_h) // 2
    return scaled.crop((x_off, y_off, x_off + target_w, y_off + target_h))


def draw_vector_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r_outer: int, r_inner: int, fill: tuple):
    points = []
    for i in range(10):
        r = r_outer if i % 2 == 0 else r_inner
        angle = i * math.pi / 5 - math.pi / 2
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=fill)


def draw_vector_checkmark(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill: tuple, width: int = 3):
    draw.line([(cx - 7, cy), (cx - 2, cy + 6), (cx + 8, cy - 5)], fill=fill, width=width)


# =============================================================================
# 1. Promo - September Savings ($1,000 Replacement Bundle Offer)
# =============================================================================
def render_promo_september_savings(bg_photo: Path | None = None) -> Image.Image:
    W, H = 1080, 1350
    # Background photo
    photo_path = bg_photo or PHOTO_BERGENFIELD_OVER
    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))
    if photo_path and photo_path.exists():
        raw = Image.open(photo_path).convert("RGBA")
        im.paste(crop_center_fill(raw, W, H), (0, 0))

    # Dark overlay gradient
    im = draw_gradient(im, 0, 360, start_alpha=230, end_alpha=120, color=(14, 18, 24))
    im = draw_gradient(im, 360, H, start_alpha=120, end_alpha=245, color=(14, 18, 24))

    draw = ImageDraw.Draw(im)

    # Header Logo
    logo = get_cropped_logo(light=True)
    lh = 85
    lw = int(logo.width * (lh / logo.height))
    im.paste(logo.resize((lw, lh), Image.Resampling.LANCZOS), ((W - lw) // 2, 35), logo.resize((lw, lh), Image.Resampling.LANCZOS))

    draw = ImageDraw.Draw(im)
    # Badge
    draw.rounded_rectangle([(W - 420) // 2, 140, (W + 420) // 2, 185], radius=10, fill=MAROON, outline=GOLD, width=2)
    draw_centered_text(draw, "LIMITED TIME FALL EVENT", 148, get_font(FONT_BARLOW, 24), LIGHT_GOLD, W)

    # Headlines
    draw_centered_text(draw, "SEPTEMBER SAVINGS", 205, get_font(FONT_OSWALD, 66), WHITE, W)
    draw_centered_text(draw, "SAVE UP TO $1,000 ON EXTERIOR REPLACEMENTS", 285, get_font(FONT_BARLOW, 28), LIGHT_GOLD, W)

    # Offer Cards (Safe Grid 3:4)
    c_w = 460
    c1_x = 60
    c2_x = W - 60 - c_w
    cy = 345
    ch = 300

    # Card 1: $500 Off Single Project
    draw.rounded_rectangle([c1_x, cy, c1_x + c_w, cy + ch], radius=16, fill=(20, 26, 36, 235), outline=GOLD, width=2)
    draw_centered_in_box(draw, "SINGLE PROJECT", c1_x, c1_x + c_w, cy + 24, get_font(FONT_BARLOW, 24), LIGHT_GOLD)
    draw_centered_in_box(draw, "$500 OFF", c1_x, c1_x + c_w, cy + 60, get_font(FONT_OSWALD, 64), WHITE)
    draw_centered_in_box(draw, "Any Single Full Replacement Project", c1_x, c1_x + c_w, cy + 145, get_font(FONT_ARIAL_BOLD, 20), OFF_WHITE)
    draw_centered_in_box(draw, "• Full Roof Replacement OR\n• Full Siding Replacement", c1_x, c1_x + c_w, cy + 185, get_font(FONT_INTER, 19), MUTED)
    draw_centered_in_box(draw, "GAF Master Elite Installation", c1_x, c1_x + c_w, cy + 250, get_font(FONT_INTER, 17), GOLD)

    # Card 2: Save $1,000 Total (Bundle)
    draw.rounded_rectangle([c2_x, cy, c2_x + c_w, cy + ch], radius=16, fill=(107, 21, 40, 240), outline=GOLD, width=3)
    draw_centered_in_box(draw, "BUNDLE & SAVE", c2_x, c2_x + c_w, cy + 24, get_font(FONT_BARLOW, 24), LIGHT_GOLD)
    draw_centered_in_box(draw, "SAVE $1,000", c2_x, c2_x + c_w, cy + 60, get_font(FONT_OSWALD, 64), GOLD)
    draw_centered_in_box(draw, "Pair 2 Full Replacement Projects", c2_x, c2_x + c_w, cy + 145, get_font(FONT_ARIAL_BOLD, 20), WHITE)
    draw_centered_in_box(draw, "• Full Roof Replacement AND\n• Full Siding Replacement", c2_x, c2_x + c_w, cy + 185, get_font(FONT_INTER, 19), OFF_WHITE)
    draw_centered_in_box(draw, "Maximum Protection & Curb Appeal", c2_x, c2_x + c_w, cy + 250, get_font(FONT_INTER, 17), LIGHT_GOLD)

    # Disclaimer Callout
    draw_centered_text(draw, "*Repairs are not eligible for this offer. Valid exclusively on full replacement projects through Sept 30.", 670, get_font(FONT_INTER, 17), MUTED, W)

    # Trust Pillars (3 columns)
    t_y = 715
    col_w = 300
    for i, (title, sub) in enumerate([
        ("GAF MASTER ELITE", "Top 2% Certified"),
        ("50-YEAR WARRANTY", "Non-Prorated Defense"),
        ("DAILY CLEAN-UP", "Zero Nails Left Behind"),
    ]):
        cx = 60 + i * (col_w + 30)
        draw.rounded_rectangle([cx, t_y, cx + col_w, t_y + 90], radius=12, fill=(16, 22, 30, 220), outline=(60, 75, 95), width=1)
        draw_centered_in_box(draw, title, cx, cx + col_w, t_y + 18, get_font(FONT_ARIAL_BOLD, 20), LIGHT_GOLD)
        draw_centered_in_box(draw, sub, cx, cx + col_w, t_y + 48, get_font(FONT_INTER, 17), OFF_WHITE)

    # CTA Button
    btn_y = 835
    btn_w = 640
    btn_h = 75
    btn_x = (W - btn_w) // 2
    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=38, fill=MAROON, outline=GOLD, width=2)
    draw_centered_text(draw, "CLAIM YOUR SEPTEMBER SAVINGS", btn_y + 16, get_font(FONT_ARIAL_BOLD, 25), WHITE, W)
    draw_centered_text(draw, "Schedule A Free On-Site Inspection", btn_y + 44, get_font(FONT_INTER, 18), LIGHT_GOLD, W)

    # Full Bleed Bottom Footer Bar
    foot_y = 1245
    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
    draw_centered_text(draw, "Website: alleliteconstructioncorpnj.com  |  Instagram: @alleliteroofing", foot_y + 20, get_font(FONT_ARIAL_BOLD, 21), WHITE, W)
    draw_centered_text(draw, "Phone: (551) 335-9235  |  131 Main St STE 122, Hackensack, NJ 07601", foot_y + 52, get_font(FONT_INTER, 19), OFF_WHITE, W)
    draw_centered_text(draw, "Licensed & Insured NJ HIC #13VH12314700", foot_y + 80, get_font(FONT_INTER, 17), MUTED, W)

    return im.convert("RGB")


# =============================================================================
# 2. Magazine Cover 1 - Roofing Contractor Magazine Cover
# =============================================================================
def render_magazine_contractor(bg_photo: Path | None = None) -> Image.Image:
    W, H = 1080, 1350
    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))

    photo_path = bg_photo or PHOTO_ROCHELLE_FRONT
    if photo_path and photo_path.exists():
        raw_photo = Image.open(photo_path).convert("RGBA")
        im.paste(crop_center_fill(raw_photo, W, H), (0, 0))

    im = draw_gradient(im, 0, 420, start_alpha=240, end_alpha=0, color=(12, 16, 22))
    im = draw_gradient(im, 640, H, start_alpha=0, end_alpha=250, color=(12, 16, 22))

    draw = ImageDraw.Draw(im)

    # Masthead Header (Deep Maroon #6B1528, Full Bleed)
    masthead_h = 165
    draw.rectangle([0, 0, W, masthead_h], fill=(107, 21, 40, 245))
    draw.line([(0, masthead_h), (W, masthead_h)], fill=GOLD, width=3)

    draw_centered_text(draw, "ROOFING CONTRACTOR", 22, get_font(FONT_OSWALD, 84), WHITE, W)
    draw_centered_text(draw, "2026 ISSUE 01  |  NEW JERSEY TRADE & ARCHITECTURAL EDITION", 125, get_font(FONT_BARLOW, 24), LIGHT_GOLD, W)

    # Issue Badge in upper right
    badge_x = W - 165
    draw.rounded_rectangle([badge_x, 15, badge_x + 135, 75], radius=8, fill=GOLD)
    draw.text((badge_x + 32, 22), "2026", font=get_font(FONT_ARIAL_BOLD, 20), fill=DARK_MAROON)
    draw.text((badge_x + 18, 45), "ISSUE 01", font=get_font(FONT_ARIAL_BOLD, 19), fill=DARK_MAROON)

    # Centered Authentic Logo in Sky
    logo = get_cropped_logo(light=True)
    lw = 280
    lh = int(logo.height * (lw / logo.width))
    im.paste(logo.resize((lw, lh), Image.Resampling.LANCZOS), ((W - lw) // 2, masthead_h + 30), logo.resize((lw, lh), Image.Resampling.LANCZOS))

    draw = ImageDraw.Draw(im)

    # Stacked Callout Cards on the Right
    c_w = 460
    c_x = W - 50 - c_w
    c1_y = 660
    draw.rounded_rectangle([c_x, c1_y, c_x + c_w, c1_y + 135], radius=12, fill=(107, 21, 40, 240), outline=GOLD, width=2)
    draw.text((c_x + 25, c1_y + 18), "PREMIUM ROOF REPLACEMENT", font=get_font(FONT_ARIAL_BOLD, 22), fill=WHITE)
    draw.text((c_x + 25, c1_y + 52), "• Built to Last. Backed by Experience.", font=get_font(FONT_INTER, 19), fill=OFF_WHITE)
    draw.text((c_x + 25, c1_y + 85), "• 50-Year Non-Prorated GAF Protection", font=get_font(FONT_INTER, 18), fill=LIGHT_GOLD)

    c2_y = 815
    draw.rounded_rectangle([c_x, c2_y, c_x + c_w, c2_y + 135], radius=12, fill=(107, 21, 40, 240), outline=GOLD, width=2)
    draw.text((c_x + 25, c2_y + 18), "HIGH-PERFORMANCE SHINGLES", font=get_font(FONT_ARIAL_BOLD, 22), fill=WHITE)
    draw.text((c_x + 25, c2_y + 52), "• Advanced Weather Defense & Wind Resistance", font=get_font(FONT_INTER, 19), fill=OFF_WHITE)
    draw.text((c_x + 25, c2_y + 85), "• GAF Master Elite Certified Craftsmanship", font=get_font(FONT_INTER, 18), fill=LIGHT_GOLD)

    # Editorial Feature on Left Side
    e_x = 55
    e_w = 480
    e_y = 660
    draw.rounded_rectangle([e_x, e_y, e_x + e_w, e_y + 290], radius=14, fill=(16, 22, 30, 235), outline=(50, 62, 78), width=2)
    draw.text((e_x + 30, e_y + 25), "NEW JERSEY", font=get_font(FONT_BARLOW, 26), fill=GOLD)
    draw.text((e_x + 30, e_y + 60), "ROOFING EXCELLENCE", font=get_font(FONT_OSWALD, 40), fill=WHITE)
    draw.text((e_x + 30, e_y + 120), "Trusted by Homeowners\nAcross Bergen County", font=get_font(FONT_ARIAL_BOLD, 24), fill=LIGHT_GOLD)
    draw.text(
        (e_x + 30, e_y + 190),
        "Precision GAF Master Elite installation\ndelivering unmatched curb appeal and\nlifelong storm defense.",
        font=get_font(FONT_INTER, 19),
        fill=OFF_WHITE,
    )

    # Free Inspection CTA Button
    btn_y = 985
    btn_w = 580
    btn_h = 72
    btn_x = (W - btn_w) // 2
    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=36, fill=MAROON, outline=GOLD, width=2)
    draw_centered_text(draw, "SCHEDULE YOUR FREE ON-SITE INSPECTION", btn_y + 14, get_font(FONT_ARIAL_BOLD, 24), WHITE, W)
    draw_centered_text(draw, "Call (551) 335-9235  |  GAF Master Elite Certified", btn_y + 42, get_font(FONT_INTER, 17), LIGHT_GOLD, W)

    # Full Bleed Bottom Footer Bar
    foot_y = 1245
    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
    draw_centered_text(draw, "Website: alleliteconstructioncorpnj.com  |  Instagram: @alleliteroofing", foot_y + 20, get_font(FONT_ARIAL_BOLD, 21), WHITE, W)
    draw_centered_text(draw, "Phone: (551) 335-9235  |  131 Main St STE 122, Hackensack, NJ 07601", foot_y + 52, get_font(FONT_INTER, 19), OFF_WHITE, W)
    draw_centered_text(draw, "Licensed & Insured NJ HIC #13VH12314700", foot_y + 80, get_font(FONT_INTER, 17), MUTED, W)

    return im.convert("RGB")


# =============================================================================
# 3. Magazine Cover 2 - Roofing Excellence Magazine Cover
# =============================================================================
def render_magazine_excellence(bg_photo: Path | None = None) -> Image.Image:
    W, H = 1080, 1350
    photo_path = bg_photo or PHOTO_CLOSTER_LUXURY
    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))
    if photo_path and photo_path.exists():
        raw_photo = Image.open(photo_path).convert("RGBA")
        im.paste(crop_center_fill(raw_photo, W, H), (0, 0))

    im = draw_gradient(im, 0, 380, start_alpha=235, end_alpha=20, color=(14, 18, 24))
    im = draw_gradient(im, 600, H, start_alpha=0, end_alpha=245, color=(14, 18, 24))

    draw = ImageDraw.Draw(im)

    # Header Logo
    logo = get_cropped_logo(light=True)
    lw = 290
    lh = int(logo.height * (lw / logo.width))
    im.paste(logo.resize((lw, lh), Image.Resampling.LANCZOS), ((W - lw) // 2, 35), logo.resize((lw, lh), Image.Resampling.LANCZOS))

    draw = ImageDraw.Draw(im)

    # Masthead Typography
    draw_centered_text(draw, "ROOFING EXCELLENCE", 145, get_font(FONT_OSWALD, 68), WHITE, W)
    draw_centered_text(draw, "INSIGHT  •  INDUSTRY  •  CRAFTSMANSHIP", 225, get_font(FONT_BARLOW, 24), LIGHT_GOLD, W)

    # Edition Badge
    badge_x = W - 165
    draw.rounded_rectangle([badge_x, 25, badge_x + 130, 80], radius=8, fill=GOLD)
    draw.text((badge_x + 30, 32), "2026", font=get_font(FONT_ARIAL_BOLD, 20), fill=DARK_MAROON)
    draw.text((badge_x + 18, 54), "EDITION", font=get_font(FONT_ARIAL_BOLD, 18), fill=DARK_MAROON)

    # Main Feature Headlines
    draw.text((65, 760), "CRAFTSMANSHIP, PROTECTION", font=get_font(FONT_OSWALD, 54), fill=WHITE)
    draw.text((65, 825), "AND UNMATCHED CURB APPEAL", font=get_font(FONT_OSWALD, 54), fill=GOLD)
    draw.text(
        (65, 895),
        "Certified GAF Master Elite installations engineered to protect\nNew Jersey homeowners through every season.",
        font=get_font(FONT_INTER, 22),
        fill=OFF_WHITE,
    )

    # Trust Features
    f_y = 985
    for i, feat in enumerate(["Full Roof Replacement", "50-Year Golden Pledge", "Seamless Gutters"]):
        fx = 65 + i * 320
        draw.rounded_rectangle([fx, f_y, fx + 300, f_y + 60], radius=10, fill=(107, 21, 40, 220), outline=GOLD, width=1)
        draw_centered_in_box(draw, feat, fx, fx + 300, f_y + 16, get_font(FONT_ARIAL_BOLD, 19), WHITE)

    # Footer
    foot_y = 1245
    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
    draw_centered_text(draw, "Website: alleliteconstructioncorpnj.com  |  Instagram: @alleliteroofing", foot_y + 20, get_font(FONT_ARIAL_BOLD, 21), WHITE, W)
    draw_centered_text(draw, "Phone: (551) 335-9235  |  131 Main St STE 122, Hackensack, NJ 07601", foot_y + 52, get_font(FONT_INTER, 19), OFF_WHITE, W)
    draw_centered_text(draw, "Licensed & Insured NJ HIC #13VH12314700", foot_y + 80, get_font(FONT_INTER, 17), MUTED, W)

    return im.convert("RGB")


# =============================================================================
# 4. Price Comparison Offer Flyer (4:5, 1080 x 1350)
# =============================================================================
def render_price_comparison(bg_photo: Path | None = None) -> Image.Image:
    W, H = 1080, 1350
    im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(im)

    # 1. Top White Header with Logo
    logo = get_cropped_logo(light=False)
    lh = 95
    lw = int(logo.width * (lh / logo.height))
    logo_scaled = logo.resize((lw, lh), Image.Resampling.LANCZOS)
    im.paste(logo_scaled, ((W - lw) // 2, 25), logo_scaled)

    # Three Gold Vector Stars
    draw.line([(180, 142), (460, 142)], fill=GOLD, width=1)
    draw.line([(620, 142), (900, 142)], fill=GOLD, width=1)
    draw_vector_star(draw, 500, 142, 11, 5, GOLD)
    draw_vector_star(draw, 540, 142, 14, 6, GOLD)
    draw_vector_star(draw, 580, 142, 11, 5, GOLD)

    # Headline
    draw_centered_text(draw, "Premium Roofing, Unbeatable Price.", 168, get_font(FONT_PLAYFAIR, 46), (20, 26, 32), W)
    draw_centered_text(draw, "Top quality. Honest pricing. Every time.", 228, get_font(FONT_INTER, 21), (80, 90, 100), W)

    # 2. Photo Section (Full Bleed across W=1080, y=268 to 640)
    photo_path = bg_photo or PHOTO_BERGENFIELD_OVER
    if photo_path and photo_path.exists():
        raw_photo = Image.open(photo_path).convert("RGBA")
        im.paste(crop_center_fill(raw_photo, W, 372), (0, 268))
        draw.line([(0, 268), (W, 268)], fill=(210, 215, 220), width=1)
        draw.line([(0, 640), (W, 640)], fill=(210, 215, 220), width=1)

    draw = ImageDraw.Draw(im)

    # 3. Price Comparison Badge (Overlapping photo and lower section, y=590 to 720)
    badge_w = 780
    badge_h = 130
    badge_x = (W - badge_w) // 2
    badge_y = 590

    # Left half: Competitor NJ Average
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w // 2, badge_y + badge_h], radius=16, fill=(255, 255, 255, 255), outline=(210, 215, 225), width=2)
    draw_centered_in_box(draw, "Competitor NJ Average", badge_x, badge_x + badge_w // 2, badge_y + 20, get_font(FONT_ARIAL_BOLD, 21), (70, 80, 90))
    draw_centered_in_box(draw, "$14,800", badge_x, badge_x + badge_w // 2, badge_y + 52, get_font(FONT_ARIAL_BOLD, 52), (30, 36, 44))
    # Red Strikethrough Line
    draw.line([(badge_x + 75, badge_y + 88), (badge_x + badge_w // 2 - 75, badge_y + 76)], fill=RED_ACCENT, width=4)

    # Right half: All Elite Direct
    draw.rounded_rectangle([badge_x + badge_w // 2, badge_y, badge_x + badge_w, badge_y + badge_h], radius=16, fill=MAROON, outline=GOLD, width=3)
    draw_centered_in_box(draw, "All Elite Direct", badge_x + badge_w // 2, badge_x + badge_w, badge_y + 20, get_font(FONT_ARIAL_BOLD, 22), LIGHT_GOLD)
    draw_centered_in_box(draw, "$6,499", badge_x + badge_w // 2, badge_x + badge_w, badge_y + 50, get_font(FONT_ARIAL_BOLD, 56), GOLD)

    # Center VS Badge Circle
    vs_cx = badge_x + badge_w // 2
    vs_cy = badge_y + badge_h // 2
    vs_r = 34
    draw.ellipse([vs_cx - vs_r, vs_cy - vs_r, vs_cx + vs_r, vs_cy + vs_r], fill=(255, 255, 255, 255), outline=GOLD, width=3)
    draw.text((vs_cx - 15, vs_cy - 12), "VS", font=get_font(FONT_ARIAL_BOLD, 20), fill=(20, 26, 32))

    # 4. Three Trust Columns
    col_y = 750
    col_w = 280
    cols = [
        ("GAF Master Elite", "Certified contractor status\nheld by top 2% nationwide."),
        ("50-Yr Protection", "Golden Pledge non-prorated\nwarranty on materials & labor."),
        ("Direct Pricing", "Zero middleman markups.\nStarting at $6,499."),
    ]
    for i, (ctitle, cdesc) in enumerate(cols):
        cx = 70 + i * (col_w + 50)
        draw_vector_star(draw, cx + col_w // 2, col_y + 14, 15, 7, GOLD)
        draw_centered_in_box(draw, ctitle, cx, cx + col_w, col_y + 40, get_font(FONT_ARIAL_BOLD, 22), (20, 26, 32))
        draw_centered_in_box(draw, cdesc, cx, cx + col_w, col_y + 70, get_font(FONT_INTER, 17), (90, 100, 110))

    # 5. Free Inspection Callout Box
    cbox_y = 890
    cbox_w = 760
    cbox_h = 74
    cbox_x = (W - cbox_w) // 2
    draw.rounded_rectangle([cbox_x, cbox_y, cbox_x + cbox_w, cbox_y + cbox_h], radius=12, fill=(245, 248, 252), outline=(210, 220, 230), width=1)
    draw_centered_text(draw, "FREE SAME-DAY ON-SITE ROOF INSPECTION", cbox_y + 14, get_font(FONT_ARIAL_BOLD, 22), MAROON, W)
    draw_centered_text(draw, "Complete itemized digital estimate with zero obligation", cbox_y + 42, get_font(FONT_INTER, 17), (70, 80, 90), W)

    # 6. Big CTA Button
    btn_y = 990
    btn_w = 580
    btn_h = 75
    btn_x = (W - btn_w) // 2
    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=38, fill=MAROON, outline=GOLD, width=2)
    draw_centered_text(draw, "GET YOUR FREE ESTIMATE TODAY", btn_y + 16, get_font(FONT_ARIAL_BOLD, 24), WHITE, W)
    draw_centered_text(draw, "Call (551) 335-9235  |  GAF Master Elite Certified", btn_y + 44, get_font(FONT_INTER, 17), LIGHT_GOLD, W)

    # 7. Clean Editorial Footer
    draw.line([(60, 1100), (W - 60, 1100)], fill=(225, 230, 235), width=1)
    draw_centered_text(draw, "All Elite Roofing & Siding  •  131 Main St STE 122, Hackensack, NJ 07601", 1125, get_font(FONT_ARIAL_BOLD, 20), (40, 50, 60), W)
    draw_centered_text(draw, "Phone: (551) 335-9235  •  alleliteconstructioncorpnj.com  •  @alleliteroofing", 1160, get_font(FONT_INTER, 19), (70, 80, 90), W)
    draw_centered_text(draw, "Licensed & Insured NJ HIC #13VH12314700", 1195, get_font(FONT_INTER, 17), (120, 130, 140), W)

    return im.convert("RGB")


# =============================================================================
# 5. Roof Warning Signs Inspection Flyer (4:5, 1080 x 1350)
# =============================================================================
def render_warning_signs(bg_photo: Path | None = None) -> Image.Image:
    W, H = 1080, 1350
    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))

    photo_path = bg_photo or PHOTO_ROCHELLE_FRONT
    if photo_path and photo_path.exists():
        raw_photo = Image.open(photo_path).convert("RGBA")
        im.paste(crop_center_fill(raw_photo, W, H), (0, 0))

    im = draw_gradient(im, 0, 360, start_alpha=230, end_alpha=30, color=(12, 16, 22))
    im = draw_gradient(im, 360, H, start_alpha=30, end_alpha=250, color=(12, 16, 22))

    draw = ImageDraw.Draw(im)

    # Header Logo
    logo = get_cropped_logo(light=True)
    lh = 85
    lw = int(logo.width * (lh / logo.height))
    im.paste(logo.resize((lw, lh), Image.Resampling.LANCZOS), ((W - lw) // 2, 35), logo.resize((lw, lh), Image.Resampling.LANCZOS))

    draw = ImageDraw.Draw(im)

    # Top Alert Badge
    draw.rounded_rectangle([(W - 460) // 2, 140, (W + 460) // 2, 185], radius=10, fill=MAROON, outline=GOLD, width=2)
    draw_centered_text(draw, "ATTENTION NEW JERSEY HOMEOWNERS", 148, get_font(FONT_BARLOW, 24), LIGHT_GOLD, W)

    # Headline
    draw_centered_text(draw, "5 SIGNS YOUR ROOF NEEDS ATTENTION", 205, get_font(FONT_OSWALD, 54), WHITE, W)
    draw_centered_text(draw, "Catch small leaks before they turn into costly water damage.", 275, get_font(FONT_INTER, 20), LIGHT_GOLD, W)

    # 5 Warning Sign Cards
    signs = [
        ("Missing, Curling, or Cracked Shingles", "Damaged shingles expose your underlayment directly to wind-driven rain."),
        ("Excessive Granule Loss in Gutters", "Granules protect shingles from UV rays. Bare patches lead to premature roof failure."),
        ("Water Stains on Ceilings or Walls", "Interior stains indicate active moisture infiltration into your attic insulation."),
        ("Damaged or Rusted Valley Flashing", "Valleys channel water away. Corroded flashing is the #1 leak culprit in North Jersey."),
        ("Your Roof Is Over 15-20 Years Old", "Architectural asphalt shingles near end of life require immediate evaluation."),
    ]

    card_w = 940
    card_x = (W - card_w) // 2
    card_start_y = 330
    card_h = 95
    card_gap = 16

    for i, (stitle, sdesc) in enumerate(signs):
        cy = card_start_y + i * (card_h + card_gap)
        draw.rounded_rectangle([card_x, cy, card_x + card_w, cy + card_h], radius=12, fill=(16, 22, 30, 235), outline=(50, 65, 82), width=2)
        # Vector Gold Checkmark Circle
        draw.ellipse([card_x + 22, cy + 24, card_x + 68, cy + 70], fill=MAROON, outline=GOLD, width=2)
        draw_vector_checkmark(draw, card_x + 45, cy + 47, GOLD, width=3)
        # Text
        draw.text((card_x + 85, cy + 18), stitle, font=get_font(FONT_ARIAL_BOLD, 22), fill=WHITE)
        draw.text((card_x + 85, cy + 50), sdesc, font=get_font(FONT_INTER, 18), fill=OFF_WHITE)

    # Free Inspection Badge
    ibadge_y = 900
    draw.rounded_rectangle([card_x, ibadge_y, card_x + card_w, ibadge_y + 80], radius=14, fill=MAROON, outline=GOLD, width=2)
    draw_centered_text(draw, "FREE SAME-DAY ON-SITE ROOF INSPECTION", ibadge_y + 16, get_font(FONT_ARIAL_BOLD, 24), WHITE, W)
    draw_centered_text(draw, "100% Free • Comprehensive Digital Report • Zero Obligation", ibadge_y + 46, get_font(FONT_INTER, 18), LIGHT_GOLD, W)

    # CTA Button
    btn_y = 1005
    btn_w = 580
    btn_h = 75
    btn_x = (W - btn_w) // 2
    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=38, fill=GOLD)
    draw_centered_text(draw, "SCHEDULE YOUR FREE INSPECTION", btn_y + 16, get_font(FONT_ARIAL_BOLD, 24), DARK_MAROON, W)
    draw_centered_text(draw, "Call (551) 335-9235  |  24/7 Rapid Response", btn_y + 44, get_font(FONT_INTER, 18), DARK_MAROON, W)

    # Full Bleed Footer
    foot_y = 1245
    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
    draw_centered_text(draw, "Website: alleliteconstructioncorpnj.com  |  Instagram: @alleliteroofing", foot_y + 20, get_font(FONT_ARIAL_BOLD, 21), WHITE, W)
    draw_centered_text(draw, "Phone: (551) 335-9235  |  131 Main St STE 122, Hackensack, NJ 07601", foot_y + 52, get_font(FONT_INTER, 19), OFF_WHITE, W)
    draw_centered_text(draw, "Licensed & Insured NJ HIC #13VH12314700", foot_y + 80, get_font(FONT_INTER, 17), MUTED, W)

    return im.convert("RGB")


# =============================================================================
# 6. Instagram Educational Carousel Post (4 Slides, 1080 x 1350 px)
# =============================================================================
def render_carousel_slides(dest_dir: Path | None = None) -> list[tuple[str, Image.Image]]:
    W, H = 1080, 1350
    rendered_slides: list[tuple[str, Image.Image]] = []

    # Slide 1 (Hook): Pristine overhead roof
    im1 = Image.new("RGBA", (W, H), (14, 18, 24, 255))
    if PHOTO_BERGENFIELD_OVER.exists():
        raw_photo = Image.open(PHOTO_BERGENFIELD_OVER).convert("RGBA")
        im1.paste(crop_center_fill(raw_photo, W, H), (0, 0))
    im1 = draw_gradient(im1, 620, H, start_alpha=0, end_alpha=245, color=(10, 14, 20))
    d1 = ImageDraw.Draw(im1)
    d1.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
    d1.text((W - 120, 44), "1/4", font=get_font(FONT_ARIAL_BOLD, 24), fill=WHITE)
    ty = 830
    d1.line([(70, ty), (135, ty)], fill=GOLD, width=4)
    d1.text((70, ty + 16), "ROOFING SYSTEM BREAKDOWN", font=get_font(FONT_BARLOW, 24), fill=LIGHT_GOLD)
    d1.text((70, ty + 54), "THE PART YOU NEVER SEE", font=get_font(FONT_ARIAL_BOLD, 52), fill=WHITE)
    d1.text((70, ty + 120), "A 50-year roof starts long before shingles are laid.\nSwipe to see the complete engineered system.", font=get_font(FONT_INTER, 22), fill=OFF_WHITE)
    d1.text((70, ty + 200), "Swipe to begin ->", font=get_font(FONT_BARLOW, 24), fill=LIGHT_GOLD)
    draw_centered_text(d1, "All Elite Roofing & Siding  |  @alleliteroofing  |  (551) 335-9235", H - 45, get_font(FONT_INTER, 17), MUTED, W)
    rendered_slides.append(("Slide 1 - The Hook.jpg", im1.convert("RGB")))

    # Slide 2 (Foundation): Synthetic underlayment & solid decking
    im2 = Image.new("RGBA", (W, H), (14, 18, 24, 255))
    underlayment_photo = WORKSPACE_ROOT / "clients/all-elite/assets/approved/roof_aerial_during_underlayment_001.jpg"
    if underlayment_photo.exists():
        raw_photo = Image.open(underlayment_photo).convert("RGBA")
        im2.paste(crop_center_fill(raw_photo, W, H), (0, 0))
    im2 = draw_gradient(im2, 620, H, start_alpha=0, end_alpha=245, color=(10, 14, 20))
    d2 = ImageDraw.Draw(im2)
    d2.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
    d2.text((W - 120, 44), "2/4", font=get_font(FONT_ARIAL_BOLD, 24), fill=WHITE)
    ty = 830
    d2.line([(70, ty), (135, ty)], fill=GOLD, width=4)
    d2.text((70, ty + 16), "THE FOUNDATION", font=get_font(FONT_BARLOW, 24), fill=LIGHT_GOLD)
    d2.text((70, ty + 54), "IT STARTS AT THE DECK", font=get_font(FONT_ARIAL_BOLD, 52), fill=WHITE)
    d2.text(
        (70, ty + 120),
        "We inspect 100% of plywood decking, replacing damaged wood.\nFollowed by high-performance synthetic underlayment & ice shield.",
        font=get_font(FONT_INTER, 22),
        fill=OFF_WHITE,
    )
    d2.text((70, ty + 200), "Swipe to outer defense ->", font=get_font(FONT_BARLOW, 24), fill=LIGHT_GOLD)
    draw_centered_text(d2, "All Elite Roofing & Siding  |  @alleliteroofing  |  (551) 335-9235", H - 45, get_font(FONT_INTER, 17), MUTED, W)
    rendered_slides.append(("Slide 2 - The Foundation.jpg", im2.convert("RGB")))

    # Slide 3 (Outer Armor): GAF Timberline HDZ install (Zero ABC Pro Guard)
    im3 = Image.new("RGBA", (W, H), (14, 18, 24, 255))
    if PHOTO_GAF_INSTALL.exists():
        raw_photo = Image.open(PHOTO_GAF_INSTALL).convert("RGBA")
        im3.paste(crop_center_fill(raw_photo, W, H), (0, 0))

    im3 = draw_gradient(im3, 620, H, start_alpha=0, end_alpha=245, color=(10, 14, 20))
    d3 = ImageDraw.Draw(im3)
    d3.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
    d3.text((W - 120, 44), "3/4", font=get_font(FONT_ARIAL_BOLD, 24), fill=WHITE)
    ty = 830
    d3.line([(70, ty), (135, ty)], fill=GOLD, width=4)
    d3.text((70, ty + 16), "THE CRAFT", font=get_font(FONT_BARLOW, 24), fill=LIGHT_GOLD)
    d3.text((70, ty + 54), "LAID BY HAND. LINE BY LINE.", font=get_font(FONT_ARIAL_BOLD, 52), fill=WHITE)
    d3.text(
        (70, ty + 120),
        "GAF Timberline HDZ shingles set course by course.\nPrecision LayerLock fastening with zero rushing or shortcuts.",
        font=get_font(FONT_INTER, 22),
        fill=OFF_WHITE,
    )
    d3.text((70, ty + 200), "Swipe for the standard ->", font=get_font(FONT_BARLOW, 24), fill=LIGHT_GOLD)
    draw_centered_text(d3, "All Elite Roofing & Siding  |  @alleliteroofing  |  (551) 335-9235", H - 45, get_font(FONT_INTER, 17), MUTED, W)
    rendered_slides.append(("Slide 3 - The Outer Armor.jpg", im3.convert("RGB")))

    # Slide 4 (Call To Action): Completed luxury estate in Closter
    im4 = Image.new("RGBA", (W, H), (14, 18, 24, 255))
    if PHOTO_CLOSTER_LUXURY.exists():
        raw_photo = Image.open(PHOTO_CLOSTER_LUXURY).convert("RGBA")
        im4.paste(crop_center_fill(raw_photo, W, H), (0, 0))

    dim = Image.new("RGBA", (W, H), (12, 16, 22, 215))
    im4 = Image.alpha_composite(im4, dim)
    d4 = ImageDraw.Draw(im4)
    d4.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
    d4.text((W - 120, 44), "4/4", font=get_font(FONT_ARIAL_BOLD, 24), fill=WHITE)

    logo = get_cropped_logo(light=True)
    lw = 320
    lh = int(logo.height * (lw / logo.width))
    im4.paste(logo.resize((lw, lh), Image.Resampling.LANCZOS), ((W - lw) // 2, 240), logo.resize((lw, lh), Image.Resampling.LANCZOS))

    d4 = ImageDraw.Draw(im4)
    draw_centered_text(d4, "YOUR ROOF DESERVES", 480, get_font(FONT_ARIAL_BOLD, 54), WHITE, W)
    draw_centered_text(d4, "THIS STANDARD", 545, get_font(FONT_ARIAL_BOLD, 54), WHITE, W)
    draw_centered_text(
        d4,
        "GAF Master Elite certified craftsmanship backed by our\n50-year Golden Pledge warranty.",
        640,
        get_font(FONT_INTER, 24),
        OFF_WHITE,
        W,
    )

    btn_y = 760
    btn_w = 640
    btn_h = 80
    btn_x = (W - btn_w) // 2
    d4.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=40, fill=MAROON, outline=GOLD, width=2)
    draw_centered_text(d4, "SCHEDULE A FREE ON-SITE INSPECTION", btn_y + 24, get_font(FONT_ARIAL_BOLD, 26), WHITE, W)

    draw_centered_text(d4, "Phone: (551) 335-9235  •  alleliteconstructioncorpnj.com  •  @alleliteroofing", 890, get_font(FONT_ARIAL_BOLD, 22), LIGHT_GOLD, W)
    draw_centered_text(d4, "131 Main St STE 122, Hackensack, NJ 07601", 935, get_font(FONT_INTER, 20), MUTED, W)
    rendered_slides.append(("Slide 4 - Call To Action.jpg", im4.convert("RGB")))

    if dest_dir:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for sname, sim in rendered_slides:
            sim.save(dest_dir / sname, quality=95)

    return rendered_slides
