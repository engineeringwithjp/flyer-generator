"""Generates realistic sample starter assets and logos so the system operates out of the box."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

from src.config import ASSETS_DIR, CLIENTS_DIR


def generate_sample_logo(output_path: str, company_name: str = "ALL ELITE", accent_hex: str = "#80272B") -> None:
    """Generates an architectural modern vector-style contractor logo."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (500, 140), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Architectural A-frame roof icon mark
    draw.polygon([(40, 95), (85, 30), (130, 95)], fill=(128, 39, 43, 255))
    draw.polygon([(60, 95), (85, 55), (110, 95)], fill=(0, 0, 0, 0))
    draw.line([(85, 20), (85, 95)], fill=(255, 255, 255, 255), width=3)

    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((150, 32), company_name, fill=(255, 255, 255, 255), font=font_large)
    draw.text((152, 82), "CONSTRUCTION CORP.", fill=(180, 180, 185, 255), font=font_small)

    img.save(output_path, "PNG")

def generate_sample_house_photo(
    output_path: str,
    category: str = "roofing",
    house_type: str = "Colonial"
) -> None:
    """Generates a photorealistic suburban architectural house photo (1080x1350)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    w, h = 1080, 1350
    img = Image.new("RGB", (w, h), (145, 175, 210))
    draw = ImageDraw.Draw(img)

    # 1. Sky with realistic blue-to-horizon daylight gradient
    for y in range(650):
        factor = y / 650
        r = int(125 + 75 * factor)
        g = int(160 + 60 * factor)
        b = int(215 + 30 * factor)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # 2. Main Roof pitch
    roof_shingle = (45, 48, 54)
    draw.polygon([(0, 680), (540, 340), (1080, 680), (1080, 1350), (0, 1350)], fill=roof_shingle)

    # Shingle horizontal shadow lines
    for y in range(380, 720, 16):
        draw.line([(0, y), (w, y)], fill=(32, 34, 38), width=2)

    # 3. Dormer on roof
    draw.polygon([(260, 520), (360, 420), (460, 520)], fill=(38, 40, 45))
    draw.rectangle([(280, 520), (440, 640)], fill=(235, 235, 238))
    draw.rectangle([(310, 540), (410, 620)], fill=(30, 45, 60))  # Window glass

    # 4. Siding Facade (Warm Greige / Off-White Lap Siding)
    siding_color = (210, 206, 200)
    draw.rectangle([(100, 680), (980, 1200)], fill=siding_color)
    for y in range(680, 1200, 22):
        draw.line([(100, y), (980, y)], fill=(185, 180, 175), width=2)

    # 5. Windows
    for wx in [180, 740]:
        draw.rectangle([(wx, 740), (wx + 150, 920)], fill=(255, 255, 255))
        draw.rectangle([(wx + 15, 755), (wx + 135, 905)], fill=(35, 50, 65))
        draw.line([(wx + 75, 755), (wx + 75, 905)], fill=(255, 255, 255), width=3)
        draw.line([(wx + 15, 830), (wx + 135, 830)], fill=(255, 255, 255), width=3)

    # 6. Covered Architectural Portico Entryway
    draw.rectangle([(440, 820), (640, 1200)], fill=(250, 250, 250))
    draw.polygon([(420, 820), (540, 740), (660, 820)], fill=(40, 42, 48))
    draw.rectangle([(480, 890), (600, 1200)], fill=(28, 30, 34))  # Front Door

    # 7. Front lawn & walkway
    draw.rectangle([(0, 1200), (w, h)], fill=(75, 120, 65))
    draw.polygon([(460, 1200), (620, 1200), (740, 1350), (340, 1350)], fill=(175, 170, 165))  # Stone paver walkway

    img.save(output_path, "JPEG", quality=92)

def main():
    print("Generating starter assets...")
    # Client logos
    generate_sample_logo(str(CLIENTS_DIR / "all-elite" / "logo" / "logo.png"), "ALL ELITE")
    generate_sample_logo(str(CLIENTS_DIR / "client-002" / "logo" / "logo.png"), "APEX EXTERIORS")

    # Client project photos
    generate_sample_house_photo(str(CLIENTS_DIR / "all-elite" / "photos" / "roof_all_elite_001.jpg"), "roofing")
    generate_sample_house_photo(str(CLIENTS_DIR / "all-elite" / "photos" / "siding_all_elite_001.jpg"), "siding")
    generate_sample_house_photo(str(CLIENTS_DIR / "client-002" / "photos" / "roof_apex_001.jpg"), "roofing")

    # Approved internal asset categories
    generate_sample_house_photo(str(ASSETS_DIR / "roofing" / "roof_001.jpg"), "roofing")
    generate_sample_house_photo(str(ASSETS_DIR / "siding" / "siding_001.jpg"), "siding")
    generate_sample_house_photo(str(ASSETS_DIR / "gutters" / "gutters_001.jpg"), "gutters")
    generate_sample_house_photo(str(ASSETS_DIR / "backgrounds" / "house_001.jpg"), "general")

    print("Starter assets successfully created!")

if __name__ == "__main__":
    main()
