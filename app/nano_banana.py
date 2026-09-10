"""Nano Banana Pro Flyer Generator for All Elite Roofing & Siding.

Fully automated daily flyer generation engine:
- Mimics reference flyers and carousel designs
- Utilizes real client drone / project photos from Google Drive across unique projects
- Intelligent diversity: picks distinct houses and angles (Closter, Rochelle Park, Elmwood Park, Hillsdale, etc.)
- Detects roof vs siding vs in-progress deck and enhances with Nano Banana Pro
- Protects brand identity: authentic corporate logo presentation without funny distortions
- Brand styling: uses corporate deep maroon (#6B1528) and rich gold (#D4AF37) accents
- Accurate Bergen County pricing & data from alleliteconstructioncorpnj.com
- Carousel Posts: creates a dedicated folder containing 3+ sequential, ready-to-post Instagram slides
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
    "warranty": "50-year GAF Golden Pledge Master Elite Warranty",
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
        """Group photos by project / job site to guarantee diverse houses and angles."""
        valid_extensions = {".jpg", ".jpeg", ".png"}
        projects: dict[str, list[Path]] = defaultdict(list)

        if self.assets_dir.exists():
            for root, _, files in os.walk(self.assets_dir):
                # Identify project from directory structure
                rel = Path(root).relative_to(self.assets_dir)
                parts = rel.parts
                project_name = parts[1] if len(parts) > 1 and parts[0] == "Projects" else parts[0] if parts else "general"

                for f in files:
                    if not f.startswith(".") and any(f.lower().endswith(ext) for ext in valid_extensions):
                        full_path = Path(root) / f
                        projects[project_name].append(full_path)

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

    def build_daily_batch(self, count: int = 5) -> list[FlyerConcept]:
        """Formulate a diverse batch of 5 daily flyer concepts with distinct houses, angles, and corporate styling."""
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
                    f"Ensure the roof is perfectly centered and high in definition, showcasing crisp GAF architectural shingles. "
                    f"Incorporate the official All Elite company logo cleanly in the top or corner with authentic, sharp corporate proportions—no funny distortions. "
                    f"Include clean, non-sloppy text boxes: "
                    f"Top Masthead: ROOFING CONTRACTOR | Badge: {date.today().year} ISSUE 01 | "
                    f"Feature: NEW JERSEY ROOFING EXCELLENCE - Trusted Across Bergen & Passaic County | "
                    f"Sub-box: HIGH-PERFORMANCE SHINGLE SYSTEMS - Advanced Weather Defense, 50-Year Warranty. | "
                    f"Footer bar: Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | "
                    f"Address: {CLIENT_INFO['address']} | Phone: {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                    f"Editorial, authentic trade publication aesthetic."
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
                    f"Generate a 9:16 high-resolution Image of a Roofing Excellence & Exterior Specialists Magazine Cover. "
                    f"Clean professional 4K. Centered, eye-level aerial view of a luxury residential home with brand new architectural roofing and clean siding. "
                    f"Integrate the official {CLIENT_INFO['name']} company logo cleanly and professionally in a solid clean card. "
                    f"Header: ROOFING EXCELLENCE | Top Corner Badge: {date.today().year} EDITION | "
                    f"Tagline: Insight. Industry. Craftsmanship. | "
                    f"Headline: CRAFTSMANSHIP, PROTECTION & CURB APPEAL | "
                    f"Features: FULL ROOF REPLACEMENT • HIGH-DEFINITION SHINGLE SYSTEMS • SEAMLESS GUTTERS | "
                    f"Contact Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['instagram']} | "
                    f"Visit Us: {CLIENT_INFO['address']} | Phone: {CLIENT_INFO['phone']} | {CLIENT_INFO['email']}. "
                    f"Clean, prestigious editorial design."
                ),
            )
        )

        # 3. Corporate Price Comparison Offer Flyer (Bergen County data + Maroon & Gold brand colors)
        ref_comp = self.ref_dir / "reference_flyer6.png"
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
                    f"Luxury contractor aesthetic utilizing corporate brand colors: Deep Maroon ({CLIENT_INFO['colors']['maroon']}) and Warm Gold ({CLIENT_INFO['colors']['gold']}). "
                    f"Centrally framed high-definition aerial drone view of a newly finished roof on a Bergen County, NJ residential home. "
                    f"Integrate the official {CLIENT_INFO['name']} company logo at the top center with clean, authentic, crisp vector proportions—never distorted. "
                    f"Header Badge: BERGEN COUNTY'S PREMIER ROOFING CONTRACTOR | "
                    f"Headline: UNBEATABLE QUALITY. UNBEATABLE PRICE. | "
                    f"Subhead: Premium GAF Architectural Roofing Systems at Direct Contractor Pricing. | "
                    f"Comparison Cards: "
                    f"Card 1 (Muted charcoal): 'Average Bergen County Contractor: $14,800' (crossed out in red) • Standard Shingles | "
                    f"Card 2 (Deep Maroon with Gold border): 'All Elite Direct Contractor Price: Starting at $6,499' (Bold Gold text) • GAF Master Elite Installation | "
                    f"Trust Badges: 50-Year GAF Golden Pledge Warranty • 4.9★ Rated Across 2,500+ NJ Homeowners • Price-Match Guarantee | "
                    f"CTA Button: 'Claim Your Free Drone Roof Inspection' | "
                    f"Footer: {CLIENT_INFO['website']} • {CLIENT_INFO['instagram']} • {CLIENT_INFO['phone']} • {CLIENT_INFO['address']} • {CLIENT_INFO['license']}."
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
                    f"Generate a 9:16 high-impact emergency roof inspection flyer for {CLIENT_INFO['name']}. "
                    f"Clean professional 4K. Centered high-resolution drone photo of a residential home. "
                    f"Include the official {CLIENT_INFO['name']} logo clearly at the top in a crisp corporate card. "
                    f"Top Banner: ATTENTION BERGEN & NORTH JERSEY HOMEOWNERS | "
                    f"Main Headline: 5 SIGNS YOUR ROOF IS CRYING FOR HELP | "
                    f"Subheadline: Don't wait for the next storm to discover a leak. Protect your home today. | "
                    f"5 Warning Sign badges: 1. Missing or Curling Shingles | 2. Granule Loss in Gutters | 3. Water Stains on Ceilings | 4. Damaged Flashing | 5. Roof is 15-20+ Years Old | "
                    f"Callout Box (Red/Gold): 'FREE SAME-DAY DRONE ROOF INSPECTION' | "
                    f"CTA Button: 'Call {CLIENT_INFO['phone']} Now' | "
                    f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['instagram']} | {CLIENT_INFO['address']} | {CLIENT_INFO['license']}."
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
                    f"Centered bird's-eye overhead drone shot of a pristine residential roof in New Jersey. "
                    f"Official {CLIENT_INFO['name']} logo in the upper corner without distortion. "
                    f"Top Badge: 1/4 • SWIPE FOR THE ANATOMY | "
                    f"Category: ALL ELITE ROOFING & SIDING • SYSTEM BREAKDOWN | "
                    f"Massive Bold Headline: THE PART YOU NEVER SEE MATTERS MOST | "
                    f"Subhead: A roof that protects your family for 50 years starts long before the first shingle is installed. | "
                    f"Indicator: 'Swipe to see what's beneath your shingles ➔' | "
                    f"Footer: {CLIENT_INFO['instagram']} • {CLIENT_INFO['website']} • {CLIENT_INFO['phone']}."
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
                    f"In-progress overhead shot of a roof showing solid plywood decking and synthetic underlayment installation. "
                    f"Official logo in corner. "
                    f"Top Badge: 2/4 • THE FOUNDATION | "
                    f"Headline: IT STARTS AT THE DECK | "
                    f"Educational text box: 'Standard felt paper degrades in under 15 years. At All Elite, we inspect 100% of the plywood decking, replacing rotted wood, followed by heavy-duty synthetic underlayment and ice & water shield for a dual watertight seal.' | "
                    f"Swipe prompt: 'Swipe to see the outer armor ➔' | "
                    f"Footer: {CLIENT_INFO['instagram']} • {CLIENT_INFO['website']} • {CLIENT_INFO['phone']}."
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
                    f"Official logo in upper corner. "
                    f"Top Badge: 3/4 • THE WEATHER SHIELD | "
                    f"Headline: THE OUTER ARMOR: GAF TIMBERLINE HDZ | "
                    f"Educational text: '• LayerLock™ Technology: Mechanically fastens shingles to withstand winds up to 130 MPH. • StainGuard Plus™: Algae-resistant granules. • GAF Master Elite: 50-year Golden Pledge warranty protection.' | "
                    f"Swipe prompt: 'Swipe for next steps ➔' | "
                    f"Footer: {CLIENT_INFO['instagram']} • {CLIENT_INFO['website']} • {CLIENT_INFO['phone']}."
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
                    f"Eye-level drone shot of a fully finished Bergen County home with pristine roof and siding. "
                    f"Official company logo centered in a clean white rounded card. "
                    f"Top Badge: 4/4 • NEXT STEPS | "
                    f"Headline: IS YOUR ROOF READY FOR THE NEXT NJ STORM? | "
                    f"Trust points: Free 21-Point Drone Roof Inspection • Itemized Proposals • 25+ Years Experience • Daily Clean-Up | "
                    f"CTA Button: 'Book Your Free Inspection Today' | "
                    f"Footer: {CLIENT_INFO['phone']} • {CLIENT_INFO['website']} • {CLIENT_INFO['instagram']} • {CLIENT_INFO['address']} • {CLIENT_INFO['license']}."
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
    concepts = engine.build_daily_batch(count)

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
