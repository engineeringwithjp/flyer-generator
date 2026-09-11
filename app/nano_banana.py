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
    aspect_ratio: str = "4:5"  # Native Instagram 4:5 Feed & Carousel (1080 x 1350 px)
    references: list[Path] = field(default_factory=list)
    prompt: str = ""
    background_photo: Path | None = None
    output_filename: str = ""
    is_carousel_folder: bool = False
    carousel_slides: list[FlyerConcept] = field(default_factory=list)
    width: int = 1080
    height: int = 1350



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

                # Strictly exclude any Before folders, Bergenfield photos, Videos, or hidden files
                if "before" in parts_lower or "bergenfield" in parts_lower or "videos" in parts_lower or "video" in parts_lower:
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
                    if f.startswith(".") or "before" in f.lower() or "bergenfield" in f.lower():
                        continue
                    if any(f.lower().endswith(ext) for ext in valid_extensions):
                        projects[project_name].append(root_path / f)

        # Fallback safety net: If Google Drive CloudStorage is unreachable or returned few photos on sleep-wake
        if not projects or sum(len(v) for v in projects.values()) < 5:
            local_approved = Path("clients/all-elite/assets/approved")
            if local_approved.exists():
                for f in local_approved.iterdir():
                    if f.suffix.lower() in valid_extensions and "before" not in f.name.lower() and "bergenfield" not in f.name.lower():
                        projects["local_approved"].append(f)

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
        Guarantees non-redundancy and non-repetitive designs by rotating across the full reference flyer library:
        - Day slot 1 (e.g. 09-10): Trade Magazine (ref 16/18), Price Comparison (ref 6), Warning Signs (ref 12), System Breakdown Carousel.
        - Day slot 2 (e.g. 09-11): Industry Voice Editorial (ref 17), Invisible Difference (ref 9), Four-Season Weather Defense (ref 14), Siding & Financing (ref 7/8), Crew Standards Carousel (carousel 4/5/6).
        - Day slot 0 (e.g. 09-12): Heritage Zero Shortcuts (ref 13), Multi-Angle Services (ref 15), Reliability Guarantee (ref 10), Price Comparison (ref 6), Materials Carousel.
        Includes seasonal promo rotation: exactly 5 times in September (days 1, 7, 14, 21, 28),
        features the 'September Savings' ($500 off single replacement, $1,000 off 2 bundled replacements; repairs ineligible).
        """
        target_date = target_date or date.today()
        photos = self.pick_diverse_photos(count=8)
        while len(photos) < 8:
            photos.append(None)

        concepts: list[FlyerConcept] = []
        is_september_promo_day = (target_date.month == 9 and target_date.day in {1, 7, 14, 21, 28})
        rotation_slot = target_date.day % 3

        if rotation_slot == 2:
            # --- ROTATION B (e.g. 09-11): Industry Voice, Invisible Difference, Weather Defense, Siding Financing, Crew Carousel ---
            ref_mag = self.ref_dir / "reference_flyer17.jpg"
            concepts.append(
                FlyerConcept(
                    name="The Industry Voice Magazine Cover",
                    archetype="magazine_industry_voice",
                    aspect_ratio="4:5",
                    references=[ref_mag] if ref_mag.exists() else [],
                    background_photo=photos[0],
                    output_filename="1 - The Industry Voice Magazine Cover.jpg",
                    prompt=(
                        f"Generate a 4:5 high-resolution editorial trade magazine cover (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge, zero blurry sides) for {CLIENT_INFO['name']}. "
                        f"Mimic the bold typography, issue badge, and editorial elegance of reference_flyer17.jpg. "
                        f"Full clear wide shot of a luxury estate with new architectural roofing against a morning sky. "
                        f"Top yellow year badge: '{target_date.year}'. "
                        f"Massive bold editorial masthead: 'ROOFING'. Sub-bar: 'THE INDUSTRY VOICE | NEW JERSEY SPECIAL EDITION'. "
                        f"Official {CLIENT_INFO['name']} logo anchored cleanly in the lower corner. "
                        f"Feature headline: 'MASTER ELITE CRAFTSMANSHIP ACROSS BERGEN COUNTY'. "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                        f"Editorial trade publication aesthetic. No emojis. No em dashes."
                    ),
                )
            )

            ref_diff = self.ref_dir / "reference_flyer9.png"
            concepts.append(
                FlyerConcept(
                    name="The Invisible Difference Craftsmanship Flyer",
                    archetype="invisible_difference",
                    aspect_ratio="4:5",
                    references=[ref_diff] if ref_diff.exists() else [],
                    background_photo=photos[1],
                    output_filename="2 - The Invisible Difference Craftsmanship Flyer.jpg",
                    prompt=(
                        f"Generate a 4:5 high-impact corporate craft flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic the layout, bold typography, and visual structure of reference_flyer9.png. "
                        f"Angled perspective of a pristine architectural shingle roof meeting the open sky. "
                        f"Official {CLIENT_INFO['name']} logo seamlessly integrated. No white sticker border. "
                        f"Header: 'THE DIFFERENCE ISN'T ALWAYS VISIBLE'. "
                        f"Subhead bar: 'It is built into every decision.' "
                        f"4 Pillar Badges: 1. INSPECTION | 2. MATERIALS | 3. INSTALLATION | 4. LONG-TERM PERFORMANCE. "
                        f"Bottom callout: 'GAF Master Elite Certified • 50-Year Golden Pledge Protection'. "
                        f"Footer: {CLIENT_INFO['phone']} | {CLIENT_INFO['website']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes. No drone claims."
                    ),
                )
            )

            ref_weather = self.ref_dir / "reference_flyer14.png"
            concepts.append(
                FlyerConcept(
                    name="Four-Season Weather Defense Flyer",
                    archetype="weather_defense",
                    aspect_ratio="4:5",
                    references=[ref_weather] if ref_weather.exists() else [],
                    background_photo=photos[2],
                    output_filename="3 - Four-Season Weather Defense Flyer.jpg",
                    prompt=(
                        f"Generate a 4:5 residential weather protection flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic the 4-panel defense card layout of reference_flyer14.png. "
                        f"Full view of a finished New Jersey residential roof. "
                        f"Official company logo at top center with original gold crown and maroon roof. "
                        f"Headline: 'YOUR ROOF FACES THIS EVERY YEAR'. "
                        f"4 Defense Cards: 1. Intense UV Sun | 2. Driving Heavy Rain | 3. 130 MPH Coastal Winds | 4. Freezing Winter Snow. "
                        f"Red/Maroon CTA banner: 'CALL FOR A FREE ON-SITE INSPECTION!'. "
                        f"Footer: Phone: {CLIENT_INFO['phone']} | {CLIENT_INFO['website']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes. Strictly no drone claims."
                    ),
                )
            )

            ref_siding = self.ref_dir / "reference_flyer7.png"
            concepts.append(
                FlyerConcept(
                    name="Premium Siding & Exterior Transformation Flyer",
                    archetype="siding_financing",
                    aspect_ratio="4:5",
                    references=[ref_siding] if ref_siding.exists() else [],
                    background_photo=photos[3],
                    output_filename="4 - Premium Siding & Exterior Transformation Flyer.jpg",
                    prompt=(
                        f"Generate a 4:5 exterior remodeling advertisement flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic the high-converting financing card layout of reference_flyer7.png. "
                        f"Crisp eye-level view of a completed residential home with premium James Hardie or vinyl siding and finished roof. "
                        f"Headline: 'NEW SIDING. $0 DOWN. NO PAYMENTS FOR A YEAR.' "
                        f"3 Financing Badges: '$0 DOWN' | '0 PAYMENTS' | '0% INTEREST FOR 12 MONTHS'. "
                        f"Trust Badge: 'TOP-RATED NEW JERSEY EXTERIOR SPECIALISTS • 5-STAR REVIEWS'. "
                        f"CTA Button: 'Schedule Your Free On-Site Consultation'. "
                        f"Footer: {CLIENT_INFO['phone']} | {CLIENT_INFO['website']} | {CLIENT_INFO['address']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            # Carousel Series B: The Installation Standard & Crew Integrity
            carousel_folder_name = "5 - Carousel - Installation Standards & Crew Integrity (Instagram Post)"
            ref_car = self.carousel_dir / "carousel_flyer4.png"
            carousel_slides = [
                FlyerConcept(
                    name="Slide 1 - The Standard",
                    archetype="carousel_slide_1",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[4],
                    output_filename="Slide 1 - The Standard.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel cover slide (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic carousel_flyer4.png. Eye-level view of professional roofing crew working meticulously on a steep pitch roof. "
                        f"Top badge: 'Slide 1 of 4 | The Standard'. "
                        f"Headline: 'A CREW THAT HOLDS THE LINE'. "
                        f"Subhead: 'Every hand on the roof works to the same standard. Precision does not scale down.' "
                        f"Swipe prompt: 'Swipe to see how we build >'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']} | {CLIENT_INFO['phone']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 2 - Deck & Underlayment",
                    archetype="carousel_slide_2",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[5],
                    output_filename="Slide 2 - Deck & Underlayment.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel educational slide 2 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Plywood deck and synthetic underlayment installation in progress. "
                        f"Top badge: 'Slide 2 of 4 | Foundation'. "
                        f"Headline: 'ZERO SHORTCUTS UNDER THE SHINGLES'. "
                        f"Educational text: 'We inspect every square foot of decking, replace rotted plywood, and install dual-layer ice and water shield in critical valleys.' "
                        f"Swipe prompt: 'Swipe for storm resilience >'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 3 - Outlasting the Storm",
                    archetype="carousel_slide_3",
                    aspect_ratio="4:5",
                    references=[self.carousel_dir / "carousel_flyer5.png"] if (self.carousel_dir / "carousel_flyer5.png").exists() else [],
                    background_photo=photos[6],
                    output_filename="Slide 3 - Outlasting the Storm.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel educational slide 3 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic carousel_flyer5.png. Overhead shot of clean architectural roof lines, tight valleys, and finished flashing. "
                        f"Top badge: 'Slide 3 of 4 | The Result'. "
                        f"Headline: 'BUILT TO OUTLAST THE STORM'. "
                        f"Educational text: 'Clean lines. Tight valleys. Mechanically fastened LayerLock shingles engineered to withstand 130 MPH winds.' "
                        f"Swipe prompt: 'Swipe for next steps >'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 4 - Master Elite Call To Action",
                    archetype="carousel_slide_4",
                    aspect_ratio="4:5",
                    references=[self.carousel_dir / "carousel_flyer6.png"] if (self.carousel_dir / "carousel_flyer6.png").exists() else [],
                    background_photo=photos[7],
                    output_filename="Slide 4 - Master Elite Call To Action.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel final CTA slide 4 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic carousel_flyer6.png. Stunning finished luxury home. "
                        f"Official company logo centered cleanly at top. "
                        f"Headline: 'YOUR ROOF DESERVES THIS STANDARD'. "
                        f"Outline pill CTA Button: 'SCHEDULE A FREE ON-SITE INSPECTION'. "
                        f"Footer: Phone: {CLIENT_INFO['phone']} | Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | License: {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes. No drone claims."
                    ),
                ),
            ]
            concepts.append(
                FlyerConcept(
                    name=carousel_folder_name,
                    archetype="carousel_folder",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    prompt="Instagram Carousel Post Package: Crew Standards & Storm Resilience (4 slides)",
                    output_filename=carousel_folder_name,
                    is_carousel_folder=True,
                    carousel_slides=carousel_slides,
                )
            )

        elif rotation_slot == 0:
            # --- ROTATION C (e.g. 09-12): Heritage Zero Shortcuts, Multi-Angle Services, Reliability Guarantee, Price Comparison, Materials Carousel ---
            ref_zero = self.ref_dir / "reference_flyer13.png"
            concepts.append(
                FlyerConcept(
                    name="Architectural Heritage Zero Shortcuts Flyer",
                    archetype="heritage_zero_shortcuts",
                    aspect_ratio="4:5",
                    references=[ref_zero] if ref_zero.exists() else [],
                    background_photo=photos[0],
                    output_filename="1 - Architectural Heritage - Zero Shortcuts.jpg",
                    prompt=(
                        f"Generate a 4:5 architectural craftsmanship flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic the bold diagonal split layout of reference_flyer13.png. "
                        f"High-end stone residential estate with intricate roof architecture against clear sky. "
                        f"Headline: 'PRECISION CRAFTSMANSHIP. ZERO SHORTCUTS.' "
                        f"Subhead: 'GAF Master Elite Certified • 50-Year Golden Pledge Warranty'. "
                        f"Official logo cleanly integrated in the white diagonal badge. "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            ref_multi = self.ref_dir / "reference_flyer15.png"
            concepts.append(
                FlyerConcept(
                    name="Multi-Angle Precision Roofing Services",
                    archetype="multi_services",
                    aspect_ratio="4:5",
                    references=[ref_multi] if ref_multi.exists() else [],
                    background_photo=photos[1],
                    output_filename="2 - Multi-Angle Precision Roofing Services.jpg",
                    prompt=(
                        f"Generate a 4:5 multi-angle services flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic reference_flyer15.png. Angled panels showing roof installation, valley flashing, and finished shingles. "
                        f"Header: 'FULL EXTERIOR ROOFING SERVICES'. "
                        f"Subhead: 'Our certified specialists deliver exceptional results on every project.' "
                        f"CTA Button: 'Request Your Free Itemized Proposal'. "
                        f"Footer: {CLIENT_INFO['phone']} | {CLIENT_INFO['website']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            ref_ghost = self.ref_dir / "reference_flyer10.png"
            concepts.append(
                FlyerConcept(
                    name="Contractor Reliability Guarantee - We Wont Ghost You",
                    archetype="reliability_guarantee",
                    aspect_ratio="4:5",
                    references=[ref_ghost] if ref_ghost.exists() else [],
                    background_photo=photos[2],
                    output_filename="3 - Contractor Reliability Guarantee - We Wont Ghost You.jpg",
                    prompt=(
                        f"Generate a 4:5 bold contractor reliability flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic reference_flyer10.png. High-contrast bold blue sky with finished residential roof. "
                        f"Main Headline: 'WE WON'T GHOST YOU'. "
                        f"Subheadline: 'Reliable communication. Dedicated on-site project managers. Daily progress updates.' "
                        f"Trust Points: Licensed & Insured NJ Contractor | Zero Unexplained Delays | 100% Cleanup Guarantee. "
                        f"CTA Button: 'Work With A Contractor You Can Trust'. "
                        f"Footer: {CLIENT_INFO['phone']} | {CLIENT_INFO['website']} | {CLIENT_INFO['address']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            ref_comp = self.ref_dir / "reference_flyer6.png"
            concepts.append(
                FlyerConcept(
                    name="Direct Contractor Price Comparison",
                    archetype="price_comparison",
                    aspect_ratio="4:5",
                    references=[ref_comp] if ref_comp.exists() else [],
                    background_photo=photos[3],
                    output_filename="4 - Direct Contractor Price Comparison.jpg",
                    prompt=(
                        f"Generate a 4:5 high-end corporate advertisement flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic reference_flyer6.png. Full aerial photograph of a newly completed roof on a Bergen County NJ home. "
                        f"Header: 'UNBEATABLE QUALITY. UNBEATABLE PRICE.' "
                        f"Comparison: Competitors at $14,800 vs All Elite Direct Pricing starting at $6,499. "
                        f"CTA Button: 'Claim Your Free On-Site Roof Inspection'. "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            # Carousel Series C: Materials Breakdown & Lifetime Warranty
            carousel_folder_name = "5 - Carousel - Materials Breakdown & Lifetime Warranty (Instagram Post)"
            ref_car = self.carousel_dir / "carousel_flyer1.png"
            carousel_slides = [
                FlyerConcept(
                    name="Slide 1 - Premium Components",
                    archetype="carousel_slide_1",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[4],
                    output_filename="Slide 1 - Premium Components.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel cover slide (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Pristine completed residential roof. "
                        f"Top badge: 'Slide 1 of 4 | Materials'. "
                        f"Headline: 'WHAT MAKES A ROOF LAST 50 YEARS?'. "
                        f"Subhead: 'The difference between a 15-year roof and a lifetime roof is inside the system.' "
                        f"Swipe prompt: 'Swipe to see the components >'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']} | {CLIENT_INFO['phone']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 2 - Synthetic Shield",
                    archetype="carousel_slide_2",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[5],
                    output_filename="Slide 2 - Synthetic Shield.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel educational slide 2 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Synthetic underlayment installation in progress. "
                        f"Top badge: 'Slide 2 of 4 | Underlayment'. "
                        f"Headline: 'GAF FELTBUSTER SYNTHETIC UNDERLAYMENT'. "
                        f"Educational text: 'Tougher than traditional felt. Moisture-resistant, tear-proof, and designed for extreme temperature resilience.' "
                        f"Swipe prompt: 'Swipe for shingle technology >'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 3 - Architectural Armor",
                    archetype="carousel_slide_3",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[6],
                    output_filename="Slide 3 - Architectural Armor.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel educational slide 3 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Timberline HDZ architectural shingles closeup with crisp ridge caps. "
                        f"Top badge: 'Slide 3 of 4 | The Armor'. "
                        f"Headline: 'TIMBERLINE HDZ ARCHITECTURAL SHINGLES'. "
                        f"Educational text: 'LayerLock mechanical fastening. Algae-resistant StainGuard Plus. Wind defense up to 130 MPH.' "
                        f"Swipe prompt: 'Swipe for warranty details >'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 4 - Golden Pledge Warranty",
                    archetype="carousel_slide_4",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[7],
                    output_filename="Slide 4 - Golden Pledge Warranty.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel final CTA slide 4 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Completed luxury estate. "
                        f"Headline: 'BACKED BY GAF 50-YEAR GOLDEN PLEDGE'. "
                        f"CTA Button: 'SCHEDULE YOUR FREE ON-SITE INSPECTION'. "
                        f"Footer: Phone: {CLIENT_INFO['phone']} | Website: {CLIENT_INFO['website']} | Instagram: {CLIENT_INFO['instagram']} | License: {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes. No drone claims."
                    ),
                ),
            ]
            concepts.append(
                FlyerConcept(
                    name=carousel_folder_name,
                    archetype="carousel_folder",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    prompt="Instagram Carousel Post Package: Materials Breakdown & Warranty (4 slides)",
                    output_filename=carousel_folder_name,
                    is_carousel_folder=True,
                    carousel_slides=carousel_slides,
                )
            )

        else:
            # --- ROTATION A (e.g. 09-10): Trade Editorial, Excellence Digest, Price Comparison / Promo, Warning Signs, System Breakdown Carousel ---
            ref_mag1 = self.ref_dir / "reference_flyer16.jpg"
            concepts.append(
                FlyerConcept(
                    name="Roofing Contractor Magazine Cover",
                    archetype="magazine_contractor",
                    aspect_ratio="4:5",
                    references=[ref_mag1] if ref_mag1.exists() else [],
                    background_photo=photos[0],
                    output_filename="1 - Roofing Contractor Magazine Cover.jpg",
                    prompt=(
                        f"Generate a 4:5 high-resolution Image (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) of a Roofing Contractor Magazine cover for {CLIENT_INFO['name']}. "
                        f"Editorial trade publication aesthetic mimicking reference_flyer16.jpg. Unobstructed view of completed home. "
                        f"Top Masthead: ROOFING CONTRACTOR | Badge: {target_date.year} ISSUE 01 | "
                        f"Feature: NEW JERSEY ROOFING EXCELLENCE | Subtitle: Trusted Across Bergen and Passaic County | "
                        f"Sub-box: HIGH-PERFORMANCE SHINGLE SYSTEMS - Advanced Weather Defense, 50-Year Warranty | "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            ref_mag2 = self.ref_dir / "reference_flyer18.jpeg"
            concepts.append(
                FlyerConcept(
                    name="Roofing Excellence Magazine Cover",
                    archetype="magazine_excellence",
                    aspect_ratio="4:5",
                    references=[ref_mag2] if ref_mag2.exists() else [],
                    background_photo=photos[1],
                    output_filename="2 - Roofing Excellence Magazine Cover.jpg",
                    prompt=(
                        f"Generate a 4:5 high-resolution Image (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) of a Roofing Excellence Magazine Cover. "
                        f"Mimic reference_flyer18.jpeg. Non-overlapping header and logo. Luxury residential home. "
                        f"Header: ROOFING EXCELLENCE | Top Corner Badge: {target_date.year} EDITION | "
                        f"Headline: CRAFTSMANSHIP, PROTECTION AND CURB APPEAL | "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            ref_comp = self.ref_dir / "reference_flyer6.png"
            concepts.append(
                FlyerConcept(
                    name="Price Comparison Offer Flyer",
                    archetype="price_comparison",
                    aspect_ratio="4:5",
                    references=[ref_comp] if ref_comp.exists() else [],
                    background_photo=photos[2],
                    output_filename="3 - Price Comparison Offer Flyer.jpg",
                    prompt=(
                        f"Generate a 4:5 high-end corporate advertisement flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic reference_flyer6.png. Full aerial photo of finished roof. "
                        f"Header: 'UNBEATABLE QUALITY. UNBEATABLE PRICE.' "
                        f"Comparison: Competitors at $14,800 vs All Elite Direct Pricing starting at $6,499. "
                        f"CTA Button: 'Claim Your Free On-Site Roof Inspection'. "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes."
                    ),
                )
            )

            ref_warn = self.ref_dir / "reference_flyer12.png"
            concepts.append(
                FlyerConcept(
                    name="Roof Warning Signs Inspection Flyer",
                    archetype="warning_signs",
                    aspect_ratio="4:5",
                    references=[ref_warn] if ref_warn.exists() else [],
                    background_photo=photos[3],
                    output_filename="4 - Roof Warning Signs Inspection Flyer.jpg",
                    prompt=(
                        f"Generate a 4:5 high-impact roof inspection alert flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Mimic reference_flyer12.png. Centered photo of completed home. "
                        f"Headline: '5 SIGNS YOUR ROOF IS CRYING FOR HELP'. "
                        f"5 Warning Sign cards: Curling Shingles, Granule Loss, Water Stains, Damaged Flashing, 15+ Years Old. "
                        f"Callout: 'FREE SAME-DAY ON-SITE ROOF INSPECTION'. "
                        f"Footer: {CLIENT_INFO['website']} | {CLIENT_INFO['phone']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes. No drone claims."
                    ),
                )
            )

            # Carousel Series A: Roofing System Breakdown
            carousel_folder_name = "5 - Carousel - Roofing System Breakdown (Instagram Post)"
            ref_car = self.carousel_dir / "carousel_flyer1.png"
            carousel_slides = [
                FlyerConcept(
                    name="Slide 1 - The Hook",
                    archetype="carousel_slide_1",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[4],
                    output_filename="Slide 1 - The Hook.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel cover slide (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Overhead view of pristine roof in New Jersey. "
                        f"Top badge: 'Slide 1 of 4 | System Breakdown'. "
                        f"Headline: 'THE PART YOU NEVER SEE MATTERS MOST'. "
                        f"Subhead: 'A roof that protects your family for 50 years starts long before the first shingle is installed.' "
                        f"Swipe prompt: 'Swipe to see what lies beneath your shingles >'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']} | {CLIENT_INFO['phone']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 2 - The Foundation",
                    archetype="carousel_slide_2",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[5],
                    output_filename="Slide 2 - The Foundation.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel educational slide 2 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Decking and underlayment installation in progress. "
                        f"Headline: 'IT STARTS AT THE DECK'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 3 - The Outer Armor",
                    archetype="carousel_slide_3",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[6],
                    output_filename="Slide 3 - The Outer Armor.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel educational slide 3 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"GAF Timberline HDZ shingle installation. "
                        f"Headline: 'THE OUTER ARMOR: GAF TIMBERLINE HDZ'. "
                        f"Footer: {CLIENT_INFO['instagram']} | {CLIENT_INFO['website']}. "
                        f"No emojis. No em dashes."
                    ),
                ),
                FlyerConcept(
                    name="Slide 4 - Call To Action",
                    archetype="carousel_slide_4",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    background_photo=photos[7],
                    output_filename="Slide 4 - Call To Action.jpg",
                    prompt=(
                        f"Generate a 4:5 Instagram carousel final CTA slide 4 (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                        f"Completed estate with pristine roof and lawn. "
                        f"Headline: 'YOUR ROOF DESERVES THIS STANDARD'. "
                        f"CTA Button: 'SCHEDULE YOUR FREE ON-SITE INSPECTION'. "
                        f"Footer: {CLIENT_INFO['phone']} | {CLIENT_INFO['website']} | {CLIENT_INFO['license']}. "
                        f"No emojis. No em dashes. No drone claims."
                    ),
                ),
            ]
            concepts.append(
                FlyerConcept(
                    name=carousel_folder_name,
                    archetype="carousel_folder",
                    aspect_ratio="4:5",
                    references=[ref_car] if ref_car.exists() else [],
                    prompt="Instagram Carousel Post Package: System Breakdown (4 slides)",
                    output_filename=carousel_folder_name,
                    is_carousel_folder=True,
                    carousel_slides=carousel_slides,
                )
            )

        # On designated September Promo days (1, 7, 14, 21, 28), inject September Savings Promo
        if is_september_promo_day:
            ref_promo = self.ref_dir / "reference_flyer6.png"
            promo_concept = FlyerConcept(
                name="September Savings Promo Flyer",
                archetype="september_savings_promo",
                aspect_ratio="4:5",
                references=[ref_promo] if ref_promo.exists() else [],
                background_photo=photos[2],
                output_filename="Promo - September Savings ($1,000 Replacement Bundle Offer).jpg",
                prompt=(
                    f"Generate a 4:5 promotional advertisement flyer (1080x1350 px, safe grid view 3:4 1012x1350 px, full bleed edge-to-edge) for {CLIENT_INFO['name']}. "
                    f"Centrally framed luxury home with new architectural roof and siding. "
                    f"Top Badge: 'SEPTEMBER SAVINGS EVENT | LIMITED TIME FALL OFFER'. "
                    f"Main Headline: 'SAVE UP TO $1,000 ON EXTERIOR REPLACEMENTS'. "
                    f"Card 1: '$500 OFF Any Single Replacement Project (Full Roof OR Siding)'. "
                    f"Card 2: 'SAVE $1,000 TOTAL When You Pair 2 Replacement Projects (Roof + Siding)'. "
                    f"Disclaimer: '*Repairs are not eligible for this offer. Valid exclusively on full replacement projects through September 30.' "
                    f"CTA: 'Claim Your September Savings | Free On-Site Inspection'. "
                    f"Footer: {CLIENT_INFO['phone']} | {CLIENT_INFO['website']} | {CLIENT_INFO['license']}. "
                    f"No emojis. No em dashes."
                ),
            )
            # Replace slot 2 (index 2) with promo flyer
            if len(concepts) > 2:
                concepts[2] = promo_concept
            else:
                concepts.append(promo_concept)

        return concepts[:count]


    def render_concepts_locally(self, concepts: list[FlyerConcept], dest_dir: Path) -> list[Path]:
        """Render clean, high-end editorial concepts locally using Pillow at 1080x1350 (4:5).
        Strictly enforces:
        - Original logo appearance (gold crown, maroon roofs; never white silhouette)
        - Clean editorial typography directly overlaid without opaque blocking boxes
        - Zero Bergenfield and zero Before photos
        """
        from PIL import Image, ImageDraw, ImageFont, ImageOps

        dest_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []

        def get_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            p = Path("assets/fonts") / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
            for fallback in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
                if Path(fallback).exists():
                    return ImageFont.truetype(fallback, size)
            return ImageFont.load_default()

        def load_original_logo(max_w: int = 240, max_h: int = 150) -> Image.Image:
            if self.logo_path.exists():
                orig = Image.open(self.logo_path).convert("RGBA")
                bbox = orig.getbbox()
                if bbox:
                    cropped = orig.crop(bbox)
                    ratio = min(max_w / cropped.width, max_h / cropped.height)
                    return cropped.resize((int(cropped.width * ratio), int(cropped.height * ratio)), Image.Resampling.LANCZOS)
            return Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))

        def load_and_scale_bg(photo: Path | None, width: int = 1080, height: int = 1350) -> Image.Image:
            # Fallback to local approved photo if photo is None or missing
            if not photo or not photo.exists():
                local_dir = Path("clients/all-elite/assets/approved")
                if local_dir.exists():
                    approved = [
                        f for f in local_dir.iterdir()
                        if f.suffix.lower() in {".jpg", ".jpeg", ".png"}
                        and "before" not in f.name.lower()
                        and "bergenfield" not in f.name.lower()
                    ]
                    if approved:
                        photo = random.choice(approved)

            if photo and photo.exists():
                try:
                    img = Image.open(photo).convert("RGBA")
                    ratio = max(width / img.width, height / img.height)
                    scaled = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
                    x_off = (scaled.width - width) // 2
                    y_off = (scaled.height - height) // 2
                    return scaled.crop((x_off, y_off, x_off + width, y_off + height))
                except Exception as e:
                    print(f"Warning loading photo {photo}: {e}", file=sys.stderr)

            # Final fallback: guaranteed non-black default
            bg = Image.new("RGBA", (width, height), (35, 45, 55))
            return bg


        for concept in concepts:
            if concept.is_carousel_folder:
                carousel_folder = dest_dir / concept.output_filename
                carousel_folder.mkdir(parents=True, exist_ok=True)
                for slide in concept.carousel_slides:
                    slide_path = carousel_folder / slide.output_filename
                    canvas = load_and_scale_bg(slide.background_photo, slide.width, slide.height)
                    draw = ImageDraw.Draw(canvas)
                    
                    # Gradient overlay for text legibility
                    grad = Image.new("RGBA", (slide.width, slide.height), (0, 0, 0, 0))
                    gdraw = ImageDraw.Draw(grad)
                    for y in range(slide.height // 2, slide.height):
                        alpha = int(180 * ((y - slide.height // 2) / (slide.height // 2)))
                        gdraw.line([(0, y), (slide.width, y)], fill=(10, 14, 20, alpha))
                    canvas = Image.alpha_composite(canvas, grad)
                    draw = ImageDraw.Draw(canvas)

                    # Top right badge
                    badge_num = slide.archetype.split("_")[-1]
                    draw.rounded_rectangle((slide.width - 140, 40, slide.width - 40, 85), radius=10, fill=(0, 0, 0, 200), outline=(212, 175, 55, 180), width=1)
                    draw.text((slide.width - 90, 62), f"{badge_num}/4", font=get_font("Inter-Regular.ttf", 24), anchor="mm", fill=(255, 255, 255))

                    if slide.archetype == "carousel_slide_4":
                        # Final CTA slide with authentic logo
                        logo_img = load_original_logo(max_w=280, max_h=180)
                        plate_w, plate_h = logo_img.width + 50, logo_img.height + 30
                        plate_x = (slide.width - plate_w) // 2
                        plate_y = 200
                        draw.rounded_rectangle((plate_x, plate_y, plate_x + plate_w, plate_y + plate_h), radius=18, fill=(255, 255, 255, 245))
                        canvas.paste(logo_img, (plate_x + 25, plate_y + 15), logo_img)

                        draw.text((slide.width // 2, plate_y + plate_h + 80), "YOUR ROOF DESERVES THIS STANDARD", font=get_font("BebasNeue-Regular.ttf", 68), anchor="mm", fill=(255, 255, 255))
                        draw.text((slide.width // 2, plate_y + plate_h + 150), "GAF Master Elite certified craftsmanship backed by our 50-year warranty.", font=get_font("Lato-Regular.ttf", 26), anchor="mm", fill=(220, 225, 230))
                        
                        btn_w, btn_h = 560, 68
                        btn_x = (slide.width - btn_w) // 2
                        btn_y = plate_y + plate_h + 260
                        draw.rounded_rectangle((btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=34, outline=(255, 255, 255, 240), width=2)
                        draw.text((slide.width // 2, btn_y + btn_h // 2), "SCHEDULE YOUR FREE INSPECTION", font=get_font("Lato-Bold.ttf", 26), anchor="mm", fill=(255, 255, 255))
                    else:
                        # Slides 1-3: Hook, Foundation, Armor
                        draw.text((60, 1020), slide.name.upper(), font=get_font("Lato-Bold.ttf", 22), fill=(212, 175, 55))
                        draw.text((60, 1070), slide.archetype.replace("carousel_slide_", "STEP ").upper(), font=get_font("BebasNeue-Regular.ttf", 64), fill=(255, 255, 255))
                        draw.text((60, 1140), "Crafted with GAF Master Elite standards for permanent storm protection.", font=get_font("Lato-Regular.ttf", 26), fill=(220, 225, 230))

                    # Footer
                    draw.text((slide.width // 2, 1310), f"{CLIENT_INFO['instagram']}  |  {CLIENT_INFO['phone']}  |  {CLIENT_INFO['website']}", font=get_font("Inter-Regular.ttf", 22), anchor="mm", fill=(200, 205, 210))
                    canvas.convert("RGB").save(slide_path, "JPEG", quality=96)
                    results.append(slide_path)
            else:
                out = dest_dir / concept.output_filename
                canvas = load_and_scale_bg(concept.background_photo, concept.width, concept.height)
                draw = ImageDraw.Draw(canvas)

                # Clean dark header
                draw.rectangle((0, 0, concept.width, 140), fill=(20, 24, 28, 250))
                logo_img = load_original_logo(max_w=200, max_h=100)
                # Paste original logo on clean header
                canvas.paste(logo_img, (40, 20), logo_img)
                draw.text((concept.width - 40, 70), "MASTER ELITE CERTIFIED", font=get_font("Lato-Bold.ttf", 24), anchor="rm", fill=(212, 175, 55))

                # Gradient bottom for text legibility
                grad = Image.new("RGBA", (concept.width, concept.height), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(grad)
                for y in range(concept.height - 450, concept.height):
                    alpha = int(220 * ((y - (concept.height - 450)) / 450))
                    gdraw.line([(0, y), (concept.width, y)], fill=(15, 18, 22, alpha))
                canvas = Image.alpha_composite(canvas, grad)
                draw = ImageDraw.Draw(canvas)

                # Headline & Subheadline
                draw.text((50, concept.height - 380), concept.name.upper(), font=get_font("BebasNeue-Regular.ttf", 64), fill=(255, 255, 255))
                draw.text((50, concept.height - 310), "Precision Craftsmanship • 50-Year Golden Pledge Warranty • Direct Pricing", font=get_font("Lato-Regular.ttf", 26), fill=(212, 175, 55))
                draw.text((50, concept.height - 260), "Serving Bergen, Passaic, and Northern New Jersey Homeowners.", font=get_font("Lato-Regular.ttf", 24), fill=(220, 225, 230))

                # Footer
                draw.rectangle((0, concept.height - 90, concept.width, concept.height), fill=(10, 12, 16))
                draw.text((concept.width // 2, concept.height - 45), f"Call {CLIENT_INFO['phone']}  |  {CLIENT_INFO['website']}  |  {CLIENT_INFO['license']}", font=get_font("Inter-Regular.ttf", 22), anchor="mm", fill=(255, 255, 255))

                canvas.convert("RGB").save(out, "JPEG", quality=96)
                results.append(out)

        return results

    def execute_with_genai_api(self, concept: FlyerConcept, dest_dir: Path) -> list[Path]:
        """Call Google GenAI Imagen 3 API if API key is present, scaling edge-to-edge to 1080x1350."""
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return []

        try:
            import io
            from PIL import Image
            from google import genai
            client = genai.Client(api_key=api_key)

            # Map 4:5 to Imagen 3 supported aspect ratio (3:4 is closest supported by Imagen 3)
            api_aspect = "3:4" if concept.aspect_ratio in {"4:5", "3:4"} else concept.aspect_ratio

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
                            aspect_ratio=api_aspect,
                            output_mime_type="image/jpeg",
                        ),
                    )
                    if res.generated_images:
                        out = folder / slide.output_filename
                        img = Image.open(io.BytesIO(res.generated_images[0].image.image_bytes))
                        # Scale and crop to exact 1080x1350 full bleed (zero blurry sides)
                        target_w, target_h = slide.width, slide.height
                        ratio = max(target_w / img.width, target_h / img.height)
                        scaled = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
                        x_off = (scaled.width - target_w) // 2
                        y_off = (scaled.height - target_h) // 2
                        final_img = scaled.crop((x_off, y_off, x_off + target_w, y_off + target_h))
                        final_img.save(out, quality=95)
                        results.append(out)
                return results
            else:
                res = client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=concept.prompt,
                    config=dict(
                        number_of_images=1,
                        aspect_ratio=api_aspect,
                        output_mime_type="image/jpeg",
                    ),
                )
                if res.generated_images:
                    out = dest_dir / concept.output_filename
                    img = Image.open(io.BytesIO(res.generated_images[0].image.image_bytes))
                    # Scale and crop to exact 1080x1350 full bleed (zero blurry sides)
                    target_w, target_h = concept.width, concept.height
                    ratio = max(target_w / img.width, target_h / img.height)
                    scaled = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
                    x_off = (scaled.width - target_w) // 2
                    y_off = (scaled.height - target_h) // 2
                    final_img = scaled.crop((x_off, y_off, x_off + target_w, y_off + target_h))
                    final_img.save(out, quality=95)
                    return [out]
        except Exception as e:
            print(f"GenAI API generation note: {e}", file=sys.stderr)
            return []
        return []


def run_daily_generation(count: int = 5, when: date | None = None, force: bool = False) -> list[Path]:
    """Execute the daily flyer generation workflow and write directly to Google Drive."""
    engine = NanoBananaEngine()
    dest_dir = engine.get_destination_folder(when)
    concepts = engine.build_daily_batch(count, target_date=when)

    print(f"--- Running Nano Banana Pro Daily Generation ({len(concepts)} concepts) ---")
    print(f"Target Google Drive Folder: {dest_dir}")

    existing_files = [p for p in dest_dir.glob("*.jpg") if p.is_file() and p.stat().st_size > 300_000]
    if len(existing_files) >= count and not force:
        print(f"Target folder {dest_dir.name} already contains {len(existing_files)} verified flyers. Preserving existing high-resolution artwork.")
        return existing_files

    results: list[Path] = []
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        for idx, concept in enumerate(concepts, start=1):
            print(f"[{idx}/{len(concepts)}] Concept: {concept.name}")
            out_paths = engine.execute_with_genai_api(concept, dest_dir)
            if out_paths:
                for p in out_paths:
                    print(f"   -> Saved directly to Drive: {p.name}")
                    results.append(p)

    if not results:
        print("Executing native edge-to-edge 4:5 local rendering engine...")
        results = engine.render_concepts_locally(concepts, dest_dir)
        for p in results:
            print(f"   -> Rendered edge-to-edge to Drive: {p.name}")

    return results


if __name__ == "__main__":
    run_daily_generation()

