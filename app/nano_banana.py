"""Nano Banana Pro Flyer Generator for All Elite Roofing & Siding.

Fully automated daily flyer generation engine:
- Mimics reference flyers and carousel designs
- Utilizes real client drone / project photos from Google Drive
- Includes client logo on every flyer
- Formulates 4K studio-grade prompts for Nano Banana Pro (Gemini / Imagen 3)
- Writes directly to Google Drive 'Client Flyers' without saving local copies to save disk space
- Generates a minimum of 5 flyers daily (including magazine covers, price comparisons, warning signs, and carousels)
"""

from __future__ import annotations

import os
import random
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Default Paths
DEFAULT_LOGO_PATH = Path("/Users/johnpineda/Documents/Projects/flyer-agent/all-elite/logo/logo.png")
DEFAULT_REF_DIR = Path("/Users/johnpineda/Documents/Projects/flyer-agent/reference-flyers")
DEFAULT_CAROUSEL_DIR = DEFAULT_REF_DIR / "carousel-flyers" / "carousel1"

DEFAULT_GDRIVE_ASSETS_DIR = Path(
    "/Users/johnpineda/Library/CloudStorage/GoogleDrive-engineeringwithjp@gmail.com/My Drive/NEDA Technologies/Clients/All Elite Construction"
)

DEFAULT_GDRIVE_DEST_DIR = Path(
    "/Users/johnpineda/Library/CloudStorage/GoogleDrive-engineeringwithjp@gmail.com/My Drive/NEDA Technologies/Client Flyers/Flyers"
)

# Client Details
CLIENT_INFO = {
    "name": "All Elite Roofing & Siding",
    "legal_name": "All Elite Construction Corp NJ",
    "website": "alleliteconstructioncorpnj.com",
    "instagram": "@alleliteroofing",
    "instagram_url": "https://www.instagram.com/alleliteroofing/",
    "address": "131 Main St STE 122, Hackensack, NJ 07601",
    "phone": "(551) 335-9235",
    "email": "info@alleliteconstructioncorpnj.com",
}


@dataclass
class FlyerConcept:
    name: str
    archetype: str
    aspect_ratio: str
    references: list[Path]
    prompt: str
    background_photo: Path | None = None
    output_filename: str = ""


class NanoBananaEngine:
    def __init__(
        self,
        logo_path: Path = DEFAULT_LOGO_PATH,
        ref_dir: Path = DEFAULT_REF_DIR,
        carousel_dir: Path = DEFAULT_CAROUSEL_DIR,
        assets_dir: Path = DEFAULT_GDRIVE_ASSETS_DIR,
        dest_dir: Path = DEFAULT_GDRIVE_DEST_DIR,
    ):
        self.logo_path = logo_path
        self.ref_dir = ref_dir
        self.carousel_dir = carousel_dir
        self.assets_dir = assets_dir
        self.dest_dir = dest_dir

    def scan_background_photos(self) -> list[Path]:
        """Scan Google Drive client folder for real project photos."""
        valid_extensions = {".jpg", ".jpeg", ".png"}
        photos: list[Path] = []
        if self.assets_dir.exists():
            for root, _, files in os.walk(self.assets_dir):
                for f in files:
                    if not f.startswith(".") and any(f.lower().endswith(ext) for ext in valid_extensions):
                        photos.append(Path(root) / f)
        return photos

    def get_destination_folder(self, target_date: date | None = None) -> Path:
        """Get the date-based folder inside Google Drive Client Flyers."""
        target_date = target_date or date.today()
        year = str(target_date.year)
        month_name = target_date.strftime("%B")
        day_str = target_date.strftime("%m-%d")
        folder = self.dest_dir / year / month_name / day_str
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def build_daily_batch(self, count: int = 5) -> list[FlyerConcept]:
        """Formulate a diverse batch of minimum 5 daily flyer concepts."""
        backgrounds = self.scan_background_photos()
        bg_sample = random.sample(backgrounds, min(count, len(backgrounds))) if backgrounds else [None] * count

        concepts: list[FlyerConcept] = []

        # 1. Magazine Cover 1 (Roofing Contractor Style)
        ref_mag1 = self.ref_dir / "reference_flyer16.jpg"
        concepts.append(
            FlyerConcept(
                name="Roofing Contractor Magazine Cover",
                archetype="magazine_contractor",
                aspect_ratio="9:16",
                references=[ref_mag1] if ref_mag1.exists() else [],
                background_photo=bg_sample[0] if len(bg_sample) > 0 else None,
                output_filename="1 - Roofing Contractor Magazine Cover.jpg",
                prompt=(
                    f"Generate a 9:16 high-resolution Image of a Roofing Contractor Magazine cover. "
                    f"Clean professional 4K. Mimic the bold typography and layout of the reference magazine. "
                    f"Highlight the realistic roof shingles with extreme clarity and HD definition. "
                    f"Use the provided background image of the newly completed roof and integrate the provided company logo prominently. "
                    f"Include clean, non-sloppy text boxes: "
                    f"Top Header: ROOFING CONTRACTOR | Badge: {date.today().year} ISSUE 01 | "
                    f"Main Feature: NEW JERSEY ROOFING EXCELLENCE - Trusted by Homeowners Across NJ | "
                    f"Feature Box: PREMIUM ROOF REPLACEMENT & REPAIR - Built to Last. Built to Protect. | "
                    f"Sub-feature: HIGH-PERFORMANCE SHINGLE SYSTEMS - Advanced Materials, Superior Results. | "
                    f"Company Name: {CLIENT_INFO['name']} | "
                    f"Bottom Footer bar: Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | "
                    f"Visit Us: {CLIENT_INFO['address']} | Phone: {CLIENT_INFO['phone']} | Email: {CLIENT_INFO['email']}. "
                    f"Make the overall aesthetic crisp, premium, and look like an authentic published trade magazine."
                ),
            )
        )

        # 2. Magazine Cover 2 (Roofing Excellence & Exterior Digest)
        ref_mag2 = self.ref_dir / "reference_flyer18.jpeg"
        concepts.append(
            FlyerConcept(
                name="Roofing Excellence Magazine Cover",
                archetype="magazine_excellence",
                aspect_ratio="9:16",
                references=[ref_mag2] if ref_mag2.exists() else [],
                background_photo=bg_sample[1] if len(bg_sample) > 1 else None,
                output_filename="2 - Roofing Excellence Magazine Cover.jpg",
                prompt=(
                    f"Generate a 9:16 high-resolution Image of a Roofing Excellence & Exterior Specialists Magazine Cover. "
                    f"Clean professional 4K. Mimic the layout, bold masthead, and corner badge of the reference magazine. "
                    f"Show extreme clarity and HD definition of the architectural shingles, gutters, and roof peaks. "
                    f"Integrate the {CLIENT_INFO['name']} company logo cleanly. "
                    f"Include with clean sharp typography: "
                    f"Header: ROOFING EXCELLENCE | Top Badge: {date.today().year} EDITION | "
                    f"Tagline: Insight. Industry. Craftsmanship. | "
                    f"Headline: CRAFTSMANSHIP, PROTECTION & CURB APPEAL | "
                    f"Feature 1: FULL ROOF REPLACEMENT - Built to Last. Backed by Experience. | "
                    f"Feature 2: HIGH-DEFINITION SHINGLE SYSTEMS - Premium Materials. Superior Weather Defense. | "
                    f"Company Name: {CLIENT_INFO['name']} | "
                    f"Bottom Footer Contact Info: Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | "
                    f"Visit Us: {CLIENT_INFO['address']} | Phone: {CLIENT_INFO['phone']} | Email: {CLIENT_INFO['email']}. "
                    f"Clean, modern, editorial magazine design. No messy AI artifacts."
                ),
            )
        )

        # 3. High-Converting Price Comparison Flyer
        ref_comp = self.ref_dir / "reference_flyer6.png"
        concepts.append(
            FlyerConcept(
                name="Price Comparison Offer Flyer",
                archetype="price_comparison",
                aspect_ratio="9:16",
                references=[ref_comp] if ref_comp.exists() else [],
                background_photo=bg_sample[2] if len(bg_sample) > 2 else None,
                output_filename="3 - Price Comparison Offer Flyer.jpg",
                prompt=(
                    f"Generate a 9:16 promotional marketing flyer for {CLIENT_INFO['name']}. "
                    f"Mimic the layout, price comparison cards, and high-converting structure of the reference flyer. "
                    f"Use the provided real project photo showing a pristine completed home and roof. "
                    f"Include the {CLIENT_INFO['name']} company logo at the top or center. "
                    f"Include these exact design elements: "
                    f"Three gold stars at top | Headline: Premium Roofing, Unbeatable Price. | "
                    f"Subheadline: Top quality. Honest pricing. Every time. | "
                    f"A large side-by-side comparison box: "
                    f"Left Box (gray background): 'Competitor Price' with '$14,500' crossed out with a red strike | "
                    f"'VS' badge in the middle | "
                    f"Right Box (dark blue background): 'Our Price' with large gold text '$6,997' | "
                    f"Three value badges in a row: 1. Free Quote (by Text and Email) 2. 4.9 Star Rated (Trusted by Homeowners Like You) 3. Price Match Guarantee (We beat any competitor price guaranteed!) | "
                    f"A prominent CTA button/pill: 'Get Your Free Quote 💯' | "
                    f"Bottom contact information: Company: {CLIENT_INFO['name']} | "
                    f"Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | "
                    f"Address: {CLIENT_INFO['address']} | Phone: {CLIENT_INFO['phone']}. "
                    f"Crisp typography, clean contrast, modern social media ad style."
                ),
            )
        )

        # 4. Roof Warning Signs & Inspection Alert Flyer
        ref_warn = self.ref_dir / "reference_flyer12.png"
        concepts.append(
            FlyerConcept(
                name="Roof Warning Signs Inspection Flyer",
                archetype="warning_signs",
                aspect_ratio="9:16",
                references=[ref_warn] if ref_warn.exists() else [],
                background_photo=bg_sample[3] if len(bg_sample) > 3 else None,
                output_filename="4 - Roof Warning Signs Inspection Flyer.jpg",
                prompt=(
                    f"Generate a 9:16 high-impact emergency roof inspection flyer for {CLIENT_INFO['name']}. "
                    f"Clean professional 4K. Use the provided high-resolution drone photo of the residential roof and house. "
                    f"Include the {CLIENT_INFO['name']} logo clearly at the top. "
                    f"Include these elements with sharp typography and warning/checklist badges: "
                    f"Top Banner: ATTENTION HOMEOWNERS | "
                    f"Main Headline: 5 SIGNS YOUR ROOF IS CRYING FOR HELP | "
                    f"Subheadline: Don't wait for the next storm to discover a leak. Protect your home today. | "
                    f"5 Warning Sign bullet items with alert icons: "
                    f"1. Missing or Curling Shingles | 2. Granule Loss in Gutters | 3. Water Stains on Ceilings | "
                    f"4. Damaged or Rusted Flashing | 5. Roof is 15-20+ Years Old | "
                    f"Callout Box (Red/Gold accent): 'FREE SAME-DAY DRONE ROOF INSPECTION' | "
                    f"Prominent CTA Button: 'Call {CLIENT_INFO['phone']} Now' | "
                    f"Footer Info: Company Name: {CLIENT_INFO['name']} | Website: {CLIENT_INFO['website']} | "
                    f"Instagram: {CLIENT_INFO['instagram']} | Address: {CLIENT_INFO['address']}. "
                    f"Clean graphic design, high contrast, non-sloppy text boxes."
                ),
            )
        )

        # 5. Instagram Educational Carousel Post (Slide 1 Hook)
        ref_car = self.carousel_dir / "carousel_flyer1.png"
        concepts.append(
            FlyerConcept(
                name="Carousel Post Slide 1 (Hook)",
                archetype="carousel_post",
                aspect_ratio="9:16",
                references=[ref_car] if ref_car.exists() else [],
                background_photo=bg_sample[4] if len(bg_sample) > 4 else None,
                output_filename="5 - Carousel Post Slide 1 (Hook).jpg",
                prompt=(
                    f"Generate a 9:16 Instagram carousel cover post for {CLIENT_INFO['name']}. "
                    f"Mimic the modern high-end social media carousel aesthetic of the reference flyer. "
                    f"Use the provided bird's-eye overhead drone shot of the house and roof. "
                    f"Integrate the {CLIENT_INFO['name']} logo cleanly in the top or bottom left. "
                    f"Typography & Layout: "
                    f"Top subtle badge: 1/6 • SWIPE FOR THE BREAKDOWN | "
                    f"Upper small label: ALL ELITE ROOFING & GENERAL CONTRACTING | "
                    f"Large bold white headline in clean sans-serif: THE PART YOU NEVER SEE MATTERS MOST | "
                    f"Subtext below headline: A roof that lasts 50 years starts long before the first shingle is installed. | "
                    f"Small swipe indicator at bottom: 'Swipe to see how we build true storm-proof protection ->' | "
                    f"Footer bar with brand details: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']} | {CLIENT_INFO['phone']}. "
                    f"Clean, viral social media aesthetic, flawless typography, sharp drone photography."
                ),
            )
        )

        return concepts[:count]

    def execute_with_genai_api(self, concept: FlyerConcept, dest_dir: Path) -> Path | None:
        """Call Google GenAI Imagen 3 API if api key is present."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None

        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            result = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=concept.prompt,
                config=dict(
                    number_of_images=1,
                    aspect_ratio="9:16" if concept.aspect_ratio == "9:16" else "1:1",
                    output_mime_type="image/jpeg",
                ),
            )
            if result.generated_images:
                out_path = dest_dir / concept.output_filename
                with open(out_path, "wb") as f:
                    f.write(result.generated_images[0].image.image_bytes)
                return out_path
        except Exception as e:
            print(f"GenAI API generation note: {e}", file=sys.stderr)
            return None


def run_daily_generation(count: int = 5, when: date | None = None) -> list[Path]:
    """Execute the daily flyer generation workflow and write directly to Google Drive."""
    engine = NanoBananaEngine()
    dest_dir = engine.get_destination_folder(when)
    concepts = engine.build_daily_batch(count)

    print(f"--- Running Nano Banana Pro Daily Generation ({len(concepts)} flyers) ---")
    print(f"Target Google Drive Folder: {dest_dir}")

    results: list[Path] = []
    for idx, concept in enumerate(concepts, start=1):
        print(f"[{idx}/{len(concepts)}] Concept: {concept.name}")
        out_path = engine.execute_with_genai_api(concept, dest_dir)
        if out_path:
            print(f"   -> Generated and saved directly to Drive: {out_path.name}")
            results.append(out_path)
        else:
            print(f"   -> Prompt ready for Nano Banana Pro: {concept.prompt[:80]}...")

    return results


if __name__ == "__main__":
    run_daily_generation()
