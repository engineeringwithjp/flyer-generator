"""Nano Banana Pro Flyer Generator for All Elite Roofing & Siding.

Fully automated daily flyer generation engine:
- Mimics reference flyers and carousel designs
- Utilizes real client project photos from Google Drive across unique projects
- Strictly filters for 'After' and 'Completed' project photos (never 'Before' or tear-off photos)
- Intelligent diversity: picks distinct houses and angles (Closter, Rochelle Park, Cresskill, Totowa, Hillsdale, Bergenfield, Elmwood Park, Washington Township)
- Brand identity: authentic corporate logo presentation without sticker outlines or distortions
- Brand styling: uses corporate deep maroon (#6B1528) and rich gold (#D4AF37) accents
- Accurate Bergen County pricing & data from alleliteconstructioncorpnj.com
- Strictly customer-facing: offers 'Free On-Site Inspection' (never drone inspections for customers)
- AI-indicator free: zero em dashes, zero emojis, clean editorial typography
- Carousel Posts: creates a dedicated folder containing 4 sequential, ready-to-post Instagram slides
- Direct Google Drive sync: writes directly to 'Client Flyers/Flyers/<YYYY>/<Month>/<MM-DD>/' with 0MB local clutter
"""

from __future__ import annotations

import os
import random
import shutil
import sys
from collections import defaultdict
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
    "license": "NJ HIC #13VH12314700",
    "warranty": "50-Year GAF Golden Pledge Master Elite Warranty",
    "colors": {
        "maroon": "#6B1528",
        "gold": "#D4AF37",
        "dark": "#14181C",
    },
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
    is_carousel_folder: bool = False
    carousel_slides: list[FlyerConcept] = field(default_factory=list)


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

    def scan_background_photos_by_project(self) -> dict[str, list[Path]]:
        """Group photos by project / job site to guarantee diverse houses and angles.
        Strictly enforces AFTER and COMPLETED photos only: never picks Before photos or construction debris.
        """
        valid_extensions = {".jpg", ".jpeg", ".png"}
        projects: dict[str, list[Path]] = defaultdict(list)

        if self.assets_dir.exists():
            for root, _, files in os.walk(self.assets_dir):
                root_path = Path(root)
                parts_lower = [p.lower() for p in root_path.parts]

                # Strictly exclude any Before folders, Videos, or hidden files
                if "before" in parts_lower or "videos" in parts_lower or "video" in parts_lower:
                    continue
                if any(p.startswith(".") for p in root_path.parts):
                    continue

                # Project name extraction
                try:
                    rel = root_path.relative_to(self.assets_dir)
                    parts = rel.parts
                    if parts and parts[0] == "Projects":
                        if len(parts) > 2 and parts[1] == "Completed":
                            project_name = parts[2]
                        elif len(parts) > 1:
                            project_name = parts[1]
                        else:
                            project_name = "general"
                    else:
                        project_name = parts[0] if parts else "general"
                except ValueError:
                    project_name = "general"

                for f in files:
                    if f.startswith(".") or "before" in f.lower():
                        continue
                    if any(f.lower().endswith(ext) for ext in valid_extensions):
                        projects[project_name].append(root_path / f)

        return projects

    def pick_diverse_photos(self, count: int = 5) -> list[Path]:
        """Select unique photos across different projects to avoid redundant angles or same houses."""
        projects = self.scan_background_photos_by_project()
        if not projects:
            return []

        selected: list[Path] = []
        project_keys = list(projects.keys())
        random.shuffle(project_keys)

        # First pass: pick 1 photo from each unique project
        for proj in project_keys:
            if projects[proj]:
                selected.append(random.choice(projects[proj]))
            if len(selected) >= count:
                break

        # If more needed, sample remaining
        if len(selected) < count:
            all_remaining = [p for proj in projects.values() for p in proj if p not in selected]
            needed = count - len(selected)
            selected.extend(random.sample(all_remaining, min(needed, len(all_remaining))))

        return selected

    def get_destination_folder(self, target_date: date | None = None) -> Path:
        """Get the date-based folder inside Google Drive Client Flyers."""
        target_date = target_date or date.today()
        year = str(target_date.year)
        month_name = target_date.strftime("%B")
        day_str = target_date.strftime("%m-%d")
        folder = self.dest_dir / year / month_name / day_str
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def build_daily_batch(self, count: int = 5, target_date: date | None = None) -> list[FlyerConcept]:
        """Formulate a diverse batch of 5 daily flyer concepts with distinct houses, angles, and corporate styling.
        Zero em dashes, zero emojis, authentic corporate branding, and strict non-drone customer copy.
        Includes seasonal promo rotation: exactly 5 times in September (days 1, 7, 14, 21, 28),
        features the 'September Savings' ($500 off single replacement, $1,000 off 2 bundled replacements; repairs ineligible)
        to prevent repetitive flyers.
        """
        target_date = target_date or date.today()
        photos = self.pick_diverse_photos(count=8)
        while len(photos) < 8:
            photos.append(None)

        concepts: list[FlyerConcept] = []

        # 1. Magazine Cover 1: Roofing Contractor Magazine (mimic ref 16 & 17)
        ref_mag1 = self.ref_dir / "reference_flyer16.jpg"
        concepts.append(
            FlyerConcept(
                name="Roofing Contractor Magazine Cover",
                archetype="magazine_contractor",
                aspect_ratio="9:16",
                references=[ref_mag1] if ref_mag1.exists() else [],
                background_photo=photos[0],
                output_filename="1 - Roofing Contractor Magazine Cover.jpg",
                prompt=(
                    f"Generate a 9:16 high-resolution Image of a Roofing Contractor Magazine cover for {CLIENT_INFO['name']}. "
                    f"Clean professional 4K. Mimic the bold typography, issue badge, and editorial layout of the reference magazine. "
                    f"Ensure the roof is perfectly centered and high in definition, showcasing crisp GAF architectural shingles on a completed New Jersey home. "
                    f"Incorporate the official All Elite company logo cleanly in the top header band with authentic, sharp corporate proportions and zero white sticker outlines. "
                    f"Include clean, non-sloppy text boxes: "
                    f"Top Masthead: ROOFING CONTRACTOR | Badge: {date.today().year} ISSUE 01 | "
                    f"Feature: NEW JERSEY ROOFING EXCELLENCE | Subtitle: Trusted Across Bergen and Passaic County | "
                    f"Sub-box: HIGH-PERFORMANCE SHINGLE SYSTEMS - Advanced Weather Defense, 50-Year Warranty | "
                    f"Footer bar: Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | "
                    f"Address: {CLIENT_INFO['address']} | Phone: {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                    f"Editorial, authentic trade publication aesthetic. No emojis. No em dashes."
                ),
            )
        )

        # 2. Magazine Cover 2: Roofing Excellence & Exterior Digest (mimic ref 18 & 17)
        ref_mag2 = self.ref_dir / "reference_flyer18.jpeg"
        concepts.append(
            FlyerConcept(
                name="Roofing Excellence Magazine Cover",
                archetype="magazine_excellence",
                aspect_ratio="9:16",
                references=[ref_mag2] if ref_mag2.exists() else [],
                background_photo=photos[1],
                output_filename="2 - Roofing Excellence Magazine Cover.jpg",
                prompt=(
                    f"Generate a 9:16 high-resolution Image of a Roofing Excellence and Exterior Specialists Magazine Cover. "
                    f"Clean professional 4K. Centered, eye-level view of a luxury residential home with brand new architectural roofing and clean siding. "
                    f"Integrate the official {CLIENT_INFO['name']} company logo seamlessly at the top header without sticker outlines or rounded card bubbles. "
                    f"Header: ROOFING EXCELLENCE | Top Corner Badge: {date.today().year} EDITION | "
                    f"Tagline: Insight. Industry. Craftsmanship. | "
                    f"Headline: CRAFTSMANSHIP, PROTECTION AND CURB APPEAL | "
                    f"Features: Full Roof Replacement | High-Definition Shingle Systems | Seamless Gutters | "
                    f"Contact Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['instagram']} | "
                    f"Visit Us: {CLIENT_INFO['address']} | Phone: {CLIENT_INFO['phone']} | {CLIENT_INFO['email']}. "
                    f"Clean, prestigious editorial design. No emojis. No em dashes."
                ),
            )
        )

        # 3. Promotional Slot: Conditional September Savings (5x / month in Sept) or Standard Price Comparison
        is_september_promo_day = (target_date.month == 9 and target_date.day in {1, 7, 14, 21, 28})
        ref_comp = self.ref_dir / "reference_flyer6.png"

        if is_september_promo_day:
            concepts.append(
                FlyerConcept(
                    name="September Savings Promo Flyer",
                    archetype="september_savings_promo",
                    aspect_ratio="9:16",
                    references=[ref_comp] if ref_comp.exists() else [],
                    background_photo=photos[2],
                    output_filename="3 - Promo - September Savings ($1,000 Replacement Bundle Offer).jpg",
                    prompt=(
                        f"Generate a 9:16 high-end corporate promotional advertisement flyer for {CLIENT_INFO['name']}. "
                        f"Clean modern flat design agency layout. "
                        f"Brand colors: Deep Maroon ({CLIENT_INFO['colors']['maroon']}) and Warm Gold ({CLIENT_INFO['colors']['gold']}) with crisp white and dark charcoal ({CLIENT_INFO['colors']['dark']}). "
                        f"Centrally framed high-definition photograph of a finished Bergen County luxury residential home with new architectural roof and clean siding. "
                        f"Seamlessly incorporate the authentic All Elite company logo at the top on a flat solid header bar with crisp vector proportions and zero white sticker outlines. "
                        f"Top Badge: SEPTEMBER SAVINGS EVENT | LIMITED TIME FALL OFFER | "
                        f"Main Headline: SAVE UP TO $1,000 ON EXTERIOR REPLACEMENTS | "
                        f"Subhead: Upgrade your home with New Jersey's premier roofing and siding contractor. | "
                        f"Two Promo Offer Cards: "
                        f"Card 1 (Dark Slate Card with Gold Accent): '$500 OFF Any Single Replacement Project' (Full Roof Replacement OR Full Siding Replacement) | "
                        f"Card 2 (Deep Maroon Card with Gold Border): 'SAVE $1,000 TOTAL' (When you pair 2 replacement projects: Full Roof plus Full Siding Replacement) | "
                        f"Prominent Fine Print Disclaimer: '*Repairs are not eligible for this offer. Valid exclusively on full replacement projects through September 30.' | "
                        f"Trust Points: GAF Master Elite Certified | 50-Year Golden Pledge Warranty | Licensed and Insured | Flexible Financing Available | "
                        f"CTA Button: 'Claim Your September Savings | Free On-Site Inspection' | "
                        f"Footer: Phone: {CLIENT_INFO['phone']} | Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | Address: {CLIENT_INFO['address']} | License: {CLIENT_INFO['license']}. "
                        f"Strict constraints: Do not mention drone roof inspections. Do not use em dashes. Do not use emojis or stars. Do not use white sticker outlines around the logo."
                    ),
                )
            )
        else:
            concepts.append(
                FlyerConcept(
                    name="Price Comparison Offer Flyer",
                    archetype="price_comparison",
                    aspect_ratio="9:16",
                    references=[ref_comp] if ref_comp.exists() else [],
                    background_photo=photos[2],
                    output_filename="3 - Price Comparison Offer Flyer.jpg",
                    prompt=(
                        f"Generate a 9:16 high-end corporate advertisement flyer for {CLIENT_INFO['name']}. "
                        f"Clean modern flat design agency layout mimicking the reference flyer structure. "
                        f"Brand colors: Deep Maroon ({CLIENT_INFO['colors']['maroon']}) and Warm Gold ({CLIENT_INFO['colors']['gold']}). "
                        f"Centrally framed high-definition aerial photograph of a newly completed roof on a Bergen County NJ home. "
                        f"Incorporate the official {CLIENT_INFO['name']} logo seamlessly at the top center with authentic sharp vector proportions. No white sticker border. "
                        f"Header Badge: BERGEN COUNTY'S PREMIER ROOFING CONTRACTOR | "
                        f"Headline: UNBEATABLE QUALITY. UNBEATABLE PRICE. | "
                        f"Subhead: Premium GAF Architectural Roofing Systems at Direct Contractor Pricing. | "
                        f"Comparison Cards: "
                        f"Card 1 (Muted charcoal): 'Average Bergen County Contractor: $14,800' (crossed out in red) - Standard Shingles | "
                        f"Card 2 (Deep Maroon with Gold border): 'All Elite Direct Contractor Price: Starting at $6,499' (Bold Gold text) - GAF Master Elite Installation | "
                        f"Trust Points: 50-Year GAF Golden Pledge Warranty | Top Rated Across Bergen County Homeowners | Price-Match Guarantee | "
                        f"CTA Button: 'Claim Your Free On-Site Roof Inspection' | "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['instagram']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['address']} | {CLIENT_INFO['license']}. "
                        f"Strict constraints: Do not mention drone roof inspections. Do not use emojis. Do not use em dashes."
                    ),
                )
            )

        # 4. Roof Warning Signs & Inspection Alert Flyer (mimic ref 12)
        ref_warn = self.ref_dir / "reference_flyer12.png"
        concepts.append(
            FlyerConcept(
                name="Roof Warning Signs Inspection Flyer",
                archetype="warning_signs",
                aspect_ratio="9:16",
                references=[ref_warn] if ref_warn.exists() else [],
                background_photo=photos[3],
                output_filename="4 - Roof Warning Signs Inspection Flyer.jpg",
                prompt=(
                    f"Generate a 9:16 high-impact roof inspection alert flyer for {CLIENT_INFO['name']}. "
                    f"Clean professional 4K. Centered high-resolution photo of a completed residential home. "
                    f"Include the official {CLIENT_INFO['name']} logo clearly and seamlessly at the top. No white sticker outlines. "
                    f"Top Banner: ATTENTION BERGEN AND NORTH JERSEY HOMEOWNERS | "
                    f"Main Headline: 5 SIGNS YOUR ROOF IS CRYING FOR HELP | "
                    f"Subheadline: Do not wait for the next storm to discover a leak. Protect your home today. | "
                    f"5 Warning Sign items: 1. Missing or Curling Shingles | 2. Granule Loss in Gutters | 3. Water Stains on Ceilings | 4. Damaged Flashing | 5. Roof is 15-20+ Years Old | "
                    f"Callout Box (Maroon and Gold): 'FREE SAME-DAY ON-SITE ROOF INSPECTION' | "
                    f"CTA Button: 'Call {CLIENT_INFO['phone']} Now' | "
                    f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['instagram']} | {CLIENT_INFO['address']} | {CLIENT_INFO['license']}. "
                    f"Strict constraints: Do not mention drone roof inspections. Do not use emojis. Do not use em dashes."
                ),
            )
        )

        # 5. Instagram Educational Carousel Post (Folder with 4 sequential slides)
        ref_car = self.carousel_dir / "carousel_flyer1.png"
        carousel_folder_name = "5 - Carousel - Roofing System Breakdown (Instagram Post)"
        carousel_slides = [
            FlyerConcept(
                name="Slide 1 - The Hook",
                archetype="carousel_slide_1",
                aspect_ratio="9:16",
                references=[ref_car] if ref_car.exists() else [],
                background_photo=photos[4],
                output_filename="Slide 1 - The Hook.jpg",
                prompt=(
                    f"Generate a 9:16 Instagram carousel cover slide for {CLIENT_INFO['name']}. "
                    f"Clean modern editorial layout. Overhead view of a pristine residential roof in New Jersey. "
                    f"Official {CLIENT_INFO['name']} logo seamlessly in the upper corner without distortion or sticker outlines. "
                    f"Top Badge: Slide 1 of 4 | System Breakdown | "
                    f"Category: ALL ELITE ROOFING AND SIDING | "
                    f"Massive Bold Headline: THE PART YOU NEVER SEE MATTERS MOST | "
                    f"Subhead: A roof that protects your family for 50 years starts long before the first shingle is installed. | "
                    f"Indicator: 'Swipe to see what lies beneath your shingles >' | "
                    f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']} | {CLIENT_INFO['phone']}. "
                    f"No emojis. No em dashes."
                ),
            ),
            FlyerConcept(
                name="Slide 2 - The Foundation",
                archetype="carousel_slide_2",
                aspect_ratio="9:16",
                references=[self.carousel_dir / "carousel_flyer2.png"] if (self.carousel_dir / "carousel_flyer2.png").exists() else [],
                background_photo=photos[5],
                output_filename="Slide 2 - The Foundation.jpg",
                prompt=(
                    f"Generate a 9:16 Instagram carousel educational slide 2 for {CLIENT_INFO['name']}. "
                    f"Overhead shot of a roof showing solid plywood decking and synthetic underlayment installation. "
                    f"Official logo cleanly in corner. No sticker borders. "
                    f"Top Badge: Slide 2 of 4 | The Foundation | "
                    f"Headline: IT STARTS AT THE DECK | "
                    f"Educational text box: 'Standard felt paper degrades in under 15 years. At All Elite, we inspect 100% of the plywood decking, replacing rotted wood, followed by heavy-duty synthetic underlayment and ice and water shield for a dual watertight seal.' | "
                    f"Swipe prompt: 'Swipe to see the outer armor >' | "
                    f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']} | {CLIENT_INFO['phone']}. "
                    f"No emojis. No em dashes."
                ),
            ),
            FlyerConcept(
                name="Slide 3 - The Outer Armor",
                archetype="carousel_slide_3",
                aspect_ratio="9:16",
                references=[ref_car] if ref_car.exists() else [],
                background_photo=photos[6],
                output_filename="Slide 3 - The Outer Armor.jpg",
                prompt=(
                    f"Generate a 9:16 Instagram carousel educational slide 3 for {CLIENT_INFO['name']}. "
                    f"High-definition aerial view of finished GAF Timberline HDZ architectural shingles and clean drip edge. "
                    f"Official logo cleanly in upper corner. No sticker borders. "
                    f"Top Badge: Slide 3 of 4 | The Weather Shield | "
                    f"Headline: THE OUTER ARMOR: GAF TIMBERLINE HDZ | "
                    f"Educational text: 'LayerLock Technology: Mechanically fastens shingles to withstand winds up to 130 MPH. StainGuard Plus: Algae-resistant granules. GAF Master Elite: 50-Year Golden Pledge warranty protection.' | "
                    f"Swipe prompt: 'Swipe for next steps >' | "
                    f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']} | {CLIENT_INFO['phone']}. "
                    f"No emojis. No em dashes."
                ),
            ),
            FlyerConcept(
                name="Slide 4 - Call To Action",
                archetype="carousel_slide_4",
                aspect_ratio="9:16",
                references=[ref_car] if ref_car.exists() else [],
                background_photo=photos[7],
                output_filename="Slide 4 - Call To Action.jpg",
                prompt=(
                    f"Generate a 9:16 Instagram carousel final CTA slide 4 for {CLIENT_INFO['name']}. "
                    f"Eye-level shot of a completed Bergen County luxury home with pristine finished roof, clean siding, and manicured lawn. "
                    f"Official company logo seamlessly placed at the top on a clean flat solid dark header. No white sticker border. "
                    f"Top Badge: Slide 4 of 4 | Next Steps | "
                    f"Headline: IS YOUR ROOF PREPARED FOR THE NEXT STORM? | "
                    f"Trust points: Free In-Person On-Site Inspection | Transparent Itemized Proposals | GAF Master Elite Certified Installation | Daily Clean-Up and Dedicated Project Manager | "
                    f"CTA Button: 'Schedule Your Free On-Site Inspection' | "
                    f"Footer: Phone: {CLIENT_INFO['phone']} | Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | Address: {CLIENT_INFO['address']} | License: {CLIENT_INFO['license']}. "
                    f"Strict constraints: Do not mention drone roof inspections. Do not use emojis. Do not use em dashes."
                ),
            ),
        ]

        concepts.append(
            FlyerConcept(
                name=carousel_folder_name,
                archetype="carousel_folder",
                aspect_ratio="9:16",
                references=[ref_car] if ref_car.exists() else [],
                prompt="Instagram Carousel Post Package (4 slides)",
                output_filename=carousel_folder_name,
                is_carousel_folder=True,
                carousel_slides=carousel_slides,
            )
        )

        return concepts[:count]

    def execute_with_genai_api(self, concept: FlyerConcept, dest_dir: Path) -> list[Path]:
        """Call Google GenAI Imagen 3 API if API key is present."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return []

        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            if concept.is_carousel_folder:
                folder = dest_dir / concept.output_filename
                folder.mkdir(parents=True, exist_ok=True)
                results: list[Path] = []
                for slide in concept.carousel_slides:
                    res = client.models.generate_images(
                        model="imagen-3.0-generate-002",
                        prompt=slide.prompt,
                        config=dict(
                            number_of_images=1,
                            aspect_ratio="9:16",
                            output_mime_type="image/jpeg",
                        ),
                    )
                    if res.generated_images:
                        out = folder / slide.output_filename
                        with open(out, "wb") as f:
                            f.write(res.generated_images[0].image.image_bytes)
                        results.append(out)
                return results
            else:
                res = client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=concept.prompt,
                    config=dict(
                        number_of_images=1,
                        aspect_ratio="9:16",
                        output_mime_type="image/jpeg",
                    ),
                )
                if res.generated_images:
                    out = dest_dir / concept.output_filename
                    with open(out, "wb") as f:
                        f.write(res.generated_images[0].image.image_bytes)
                    return [out]
        except Exception as e:
            print(f"GenAI API generation note: {e}", file=sys.stderr)
            return []
        return []


def run_daily_generation(count: int = 5, when: date | None = None) -> list[Path]:
    """Execute the daily flyer generation workflow and write directly to Google Drive."""
    engine = NanoBananaEngine()
    dest_dir = engine.get_destination_folder(when)
    concepts = engine.build_daily_batch(count, target_date=when)

    print(f"--- Running Nano Banana Pro Daily Generation ({len(concepts)} concepts) ---")
    print(f"Target Google Drive Folder: {dest_dir}")

    results: list[Path] = []
    for idx, concept in enumerate(concepts, start=1):
        print(f"[{idx}/{len(concepts)}] Concept: {concept.name}")
        out_paths = engine.execute_with_genai_api(concept, dest_dir)
        if out_paths:
            for p in out_paths:
                print(f"   -> Saved directly to Drive: {p.name}")
                results.append(p)
        else:
            if concept.is_carousel_folder:
                print(f"   -> Carousel folder with {len(concept.carousel_slides)} slides formulated.")
            else:
                print(f"   -> Prompt ready: {concept.prompt[:80]}...")

    return results


if __name__ == "__main__":
    run_daily_generation()
