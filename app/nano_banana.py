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
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Default Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_APPROVED_DIR = REPO_ROOT / "clients" / "all-elite" / "assets" / "approved"
LOCAL_LOGO_LIGHT = REPO_ROOT / "clients" / "all-elite" / "assets" / "logo" / "logo-light@6x.png"
LOCAL_LOGO_COLOR = REPO_ROOT / "clients" / "all-elite" / "assets" / "logo" / "logo@6x.png"

DEFAULT_LOGO_PATH = LOCAL_LOGO_COLOR if LOCAL_LOGO_COLOR.exists() else Path("/Users/johnpineda/Documents/Projects/flyer-agent/all-elite/logo/logo.png")
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

# Color constants
MAROON = (107, 21, 40)          # #6B1528
DARK_MAROON = (75, 14, 28)     # #4B0E1C
GOLD = (212, 175, 55)           # #D4AF37
LIGHT_GOLD = (245, 215, 110)    # #F5D76E
DARK_BG = (14, 18, 24)          # #0E1218
WHITE = (255, 255, 255)
OFF_WHITE = (238, 242, 246)
MUTED = (160, 170, 180)


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
                if any("before" in p or "bergenfield" in p or "video" in p for p in parts_lower):
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
        if (not projects or sum(len(v) for v in projects.values()) < 5) and LOCAL_APPROVED_DIR.exists():
            for f in LOCAL_APPROVED_DIR.iterdir():
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
        - Exact Instagram 4:5 (1080x1350 px) full bleed with zero blurry sides
        - Original vector logo appearance (transparent background; never white sticker boxes)
        - Clean editorial typography directly overlaid without opaque blocking boxes
        - GAF / green ZIP System standard (zero ABC Pro Guard)
        - Pristine slide 4 completed estate with transparent logo
        - Zero Bergenfield reused ridge caps and zero Before photos
        """
        from PIL import Image, ImageDraw, ImageFont

        dest_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []

        def get_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            p = REPO_ROOT / "assets" / "fonts" / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
            for fallback in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
                if Path(fallback).exists():
                    return ImageFont.truetype(fallback, size)
            return ImageFont.load_default()

        def load_clean_logo(light: bool = True, max_w: int = 240, max_h: int = 150) -> Image.Image:
            logo_p = LOCAL_LOGO_LIGHT if light else LOCAL_LOGO_COLOR
            if not logo_p.exists():
                logo_p = self.logo_path
            if logo_p.exists():
                orig = Image.open(logo_p).convert("RGBA")
                bbox = orig.getbbox()
                if bbox:
                    cropped = orig.crop(bbox)
                    ratio = min(max_w / cropped.width, max_h / cropped.height)
                    return cropped.resize((int(cropped.width * ratio), int(cropped.height * ratio)), Image.Resampling.LANCZOS)
            return Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))

        def load_and_scale_bg(photo: Path | None, width: int = 1080, height: int = 1350, anchor_y: float = 0.5, zoom: float = 1.0) -> Image.Image:
            # Fallback to local approved photo if photo is None or missing
            if (not photo or not photo.exists()) and LOCAL_APPROVED_DIR.exists():
                approved = [
                    f for f in LOCAL_APPROVED_DIR.iterdir()
                    if f.suffix.lower() in {".jpg", ".jpeg", ".png"}
                    and "before" not in f.name.lower()
                    and "bergenfield" not in f.name.lower()
                ]
                if approved:
                    photo = random.choice(approved)

            if photo and photo.exists():
                try:
                    img = Image.open(photo).convert("RGBA")
                    ratio = max(width / img.width, height / img.height) * zoom
                    scaled = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
                    x_off = int((scaled.width - width) * 0.5)
                    y_off = int((scaled.height - height) * anchor_y)
                    x_off = max(0, min(scaled.width - width, x_off))
                    y_off = max(0, min(scaled.height - height, y_off))
                    return scaled.crop((x_off, y_off, x_off + width, y_off + height))
                except Exception as e:
                    print(f"Warning loading photo {photo}: {e}", file=sys.stderr)

            # Final fallback: dark slate background
            return Image.new("RGBA", (width, height), (20, 26, 34, 255))

        def draw_gradient(im: Image.Image, start_y: int, end_y: int, start_alpha: int = 0, end_alpha: int = 240, color=(10, 14, 20)) -> Image.Image:
            overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            h = end_y - start_y
            for i in range(h):
                y = start_y + i
                alpha = int(start_alpha + (end_alpha - start_alpha) * (i / max(1, h)))
                odraw.line([(0, y), (im.size[0], y)], fill=(color[0], color[1], color[2], alpha))
            return Image.alpha_composite(im.convert("RGBA"), overlay)

        def draw_centered_text(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.ImageFont, fill, canvas_w: int = 1080) -> tuple[int, int]:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            x = (canvas_w - tw) // 2
            draw.text((x, y), text, font=font, fill=fill)
            return tw, bbox[3] - bbox[1]

        def draw_centered_in_box(draw: ImageDraw.ImageDraw, text: str, x1: int, x2: int, y: int, font: ImageFont.ImageFont, fill) -> tuple[int, int]:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            x = x1 + (x2 - x1 - tw) // 2
            draw.text((x, y), text, font=font, fill=fill)
            return tw, bbox[3] - bbox[1]

        for concept in concepts:
            if concept.is_carousel_folder:
                carousel_folder = dest_dir / concept.output_filename
                carousel_folder.mkdir(parents=True, exist_ok=True)
                for _idx, slide in enumerate(concept.carousel_slides, start=1):
                    slide_path = carousel_folder / slide.output_filename
                    W, H = slide.width, slide.height

                    if slide.archetype == "carousel_slide_4":
                        # Slide 4: Luxury estate overhead (DJI_0081) with transparent logo (NO white sticker box!)
                        s4_bg = LOCAL_APPROVED_DIR / "DJI_0081.JPG"
                        canvas = load_and_scale_bg(s4_bg if s4_bg.exists() else slide.background_photo, W, H)
                        dim = Image.new("RGBA", (W, H), (12, 16, 22, 215))
                        canvas = Image.alpha_composite(canvas, dim)
                        draw = ImageDraw.Draw(canvas)

                        # Top counter
                        draw.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
                        draw.text((W - 120, 44), "4/4", font=get_font("Arial Bold.ttf", 24), fill=WHITE)

                        # Transparent Logo
                        logo = load_clean_logo(light=True, max_w=300, max_h=190)
                        canvas.paste(logo, ((W - logo.width) // 2, 240), logo)

                        draw = ImageDraw.Draw(canvas)
                        draw_centered_text(draw, "YOUR ROOF DESERVES", 480, get_font("Arial Bold.ttf", 54), WHITE, W)
                        draw_centered_text(draw, "THIS STANDARD", 545, get_font("Arial Bold.ttf", 54), WHITE, W)
                        draw_centered_text(
                            draw,
                            "GAF Master Elite certified craftsmanship backed by our\n50-year Golden Pledge warranty.",
                            640,
                            get_font("Inter-Regular.ttf", 24),
                            OFF_WHITE,
                            W,
                        )

                        btn_y = 760
                        btn_w = 640
                        btn_h = 80
                        btn_x = (W - btn_w) // 2
                        draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=40, fill=MAROON, outline=GOLD, width=2)
                        draw_centered_text(draw, "SCHEDULE A FREE ON-SITE INSPECTION", btn_y + 24, get_font("Arial Bold.ttf", 26), WHITE, W)

                        draw_centered_text(draw, f"Phone: {CLIENT_INFO['phone']}  •  {CLIENT_INFO['website']}  •  {CLIENT_INFO['instagram']}", 890, get_font("Arial Bold.ttf", 22), LIGHT_GOLD, W)
                        draw_centered_text(draw, CLIENT_INFO['address'], 935, get_font("Inter-Regular.ttf", 20), MUTED, W)

                    elif slide.archetype == "carousel_slide_1":
                        # Slide 1: Hook - Crew integrity / System Breakdown
                        s1_bg = LOCAL_APPROVED_DIR / "roof_estate_during_crew_install_001.jpg"
                        canvas = load_and_scale_bg(s1_bg if s1_bg.exists() else slide.background_photo, W, H, anchor_y=0.08, zoom=1.45)
                        canvas = draw_gradient(canvas, 620, H, start_alpha=0, end_alpha=245, color=(10, 14, 20))
                        draw = ImageDraw.Draw(canvas)

                        draw.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
                        draw.text((W - 120, 44), "1/4", font=get_font("Arial Bold.ttf", 24), fill=WHITE)

                        ty = 830
                        draw.line([(70, ty), (135, ty)], fill=GOLD, width=4)
                        draw.text((70, ty + 16), "CREW INTEGRITY", font=get_font("BarlowCondensed-Bold.ttf", 24), fill=LIGHT_GOLD)
                        draw.text((70, ty + 54), "A CREW THAT HOLDS THE LINE", font=get_font("Arial Bold.ttf", 50), fill=WHITE)
                        draw.text((70, ty + 120), "Every hand on the roof works to the exact same standard.\nPrecision does not scale down on our job sites.", font=get_font("Inter-Regular.ttf", 22), fill=OFF_WHITE)
                        draw.text((70, ty + 200), "Swipe to see how we build ->", font=get_font("BarlowCondensed-Bold.ttf", 24), fill=LIGHT_GOLD)
                        draw_centered_text(draw, f"{CLIENT_INFO['name']}  |  {CLIENT_INFO['instagram']}  |  {CLIENT_INFO['phone']}", H - 45, get_font("Inter-Regular.ttf", 17), MUTED, W)

                    elif slide.archetype == "carousel_slide_2":
                        # Slide 2: Foundation - Deck & GAF FeltBuster underlayment (zero ABC pro guard)
                        s2_bg = LOCAL_APPROVED_DIR / "roof_aerial_during_underlayment_001.jpg"
                        canvas = load_and_scale_bg(s2_bg if s2_bg.exists() else slide.background_photo, W, H)
                        canvas = draw_gradient(canvas, 620, H, start_alpha=0, end_alpha=245, color=(10, 14, 20))
                        draw = ImageDraw.Draw(canvas)

                        draw.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
                        draw.text((W - 120, 44), "2/4", font=get_font("Arial Bold.ttf", 24), fill=WHITE)

                        ty = 830
                        draw.line([(70, ty), (135, ty)], fill=GOLD, width=4)
                        draw.text((70, ty + 16), "THE FOUNDATION", font=get_font("BarlowCondensed-Bold.ttf", 24), fill=LIGHT_GOLD)
                        draw.text((70, ty + 54), "ZERO SHORTCUTS UNDER THE SHINGLES", font=get_font("Arial Bold.ttf", 46), fill=WHITE)
                        draw.text((70, ty + 120), "We inspect 100% of plywood decking and replace damaged wood.\nFollowed by dual-layer ice & water shield and GAF synthetic underlayment.", font=get_font("Inter-Regular.ttf", 22), fill=OFF_WHITE)
                        draw.text((70, ty + 200), "Swipe to outer armor ->", font=get_font("BarlowCondensed-Bold.ttf", 24), fill=LIGHT_GOLD)
                        draw_centered_text(draw, f"{CLIENT_INFO['name']}  |  {CLIENT_INFO['instagram']}  |  {CLIENT_INFO['phone']}", H - 45, get_font("Inter-Regular.ttf", 17), MUTED, W)

                    elif slide.archetype == "carousel_slide_3":
                        # Slide 3: Storm resilience - GAF Timberline HDZ LayerLock shingles
                        s3_bg = LOCAL_APPROVED_DIR / "DJI_0074.JPG"
                        canvas = load_and_scale_bg(s3_bg if s3_bg.exists() else slide.background_photo, W, H)
                        canvas = draw_gradient(canvas, 620, H, start_alpha=0, end_alpha=245, color=(10, 14, 20))
                        draw = ImageDraw.Draw(canvas)

                        draw.rounded_rectangle([W - 145, 35, W - 45, 80], radius=10, fill=(0, 0, 0, 180), outline=GOLD, width=1)
                        draw.text((W - 120, 44), "3/4", font=get_font("Arial Bold.ttf", 24), fill=WHITE)

                        ty = 830
                        draw.line([(70, ty), (135, ty)], fill=GOLD, width=4)
                        draw.text((70, ty + 16), "STORM RESILIENCE", font=get_font("BarlowCondensed-Bold.ttf", 24), fill=LIGHT_GOLD)
                        draw.text((70, ty + 54), "BUILT TO OUTLAST THE STORM", font=get_font("Arial Bold.ttf", 50), fill=WHITE)
                        draw.text((70, ty + 120), "GAF Timberline HDZ shingles mechanically locked course by course.\nEngineered to withstand 130 MPH coastal winds with 50-year warranty.", font=get_font("Inter-Regular.ttf", 22), fill=OFF_WHITE)
                        draw.text((70, ty + 200), "Swipe for your roof ->", font=get_font("BarlowCondensed-Bold.ttf", 24), fill=LIGHT_GOLD)
                        draw_centered_text(draw, f"{CLIENT_INFO['name']}  |  {CLIENT_INFO['instagram']}  |  {CLIENT_INFO['phone']}", H - 45, get_font("Inter-Regular.ttf", 17), MUTED, W)

                    canvas.convert("RGB").save(slide_path, "JPEG", quality=96)
                    results.append(slide_path)

            else:
                out = dest_dir / concept.output_filename
                W, H = concept.width, concept.height

                # Dedicated Archetype Renderers
                if concept.archetype == "magazine_industry_voice":
                    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))
                    bg_photo = LOCAL_APPROVED_DIR / "DJI_0081.JPG"
                    im.paste(load_and_scale_bg(bg_photo, W, H), (0, 0))
                    im = draw_gradient(im, 0, 420, start_alpha=240, end_alpha=20, color=(12, 16, 22))
                    im = draw_gradient(im, 700, H, start_alpha=0, end_alpha=245, color=(12, 16, 22))
                    draw = ImageDraw.Draw(im)

                    draw_centered_text(draw, "ROOFING", 25, get_font("Oswald-Bold.ttf", 92), WHITE, W)
                    bar_y = 135
                    draw.rectangle([0, bar_y, W, bar_y + 42], fill=(107, 21, 40, 240))
                    draw_centered_text(draw, "THE INDUSTRY VOICE  |  NEW JERSEY SPECIAL EDITION", bar_y + 8, get_font("BarlowCondensed-Bold.ttf", 24), LIGHT_GOLD, W)

                    badge_x = W - 165
                    draw.rounded_rectangle([badge_x, 25, badge_x + 130, 85], radius=8, fill=GOLD)
                    draw_centered_in_box(draw, str(date.today().year), badge_x, badge_x + 130, 32, get_font("Arial Bold.ttf", 22), DARK_MAROON)
                    draw_centered_in_box(draw, "ANNUAL", badge_x, badge_x + 130, 56, get_font("Arial Bold.ttf", 17), DARK_MAROON)

                    draw.text((60, 210), "BERGEN COUNTY LUXURY:", font=get_font("BarlowCondensed-Bold.ttf", 28), fill=GOLD)
                    draw.text((60, 245), "The Roof That Defines An Estate", font=get_font("Oswald-Bold.ttf", 44), fill=WHITE)
                    draw.text((60, 305), "Elevating architectural curb appeal and weather defense across North Jersey.", font=get_font("Inter-Regular.ttf", 20), fill=OFF_WHITE)

                    draw.rounded_rectangle([60, 780, W - 60, 1060], radius=16, fill=(16, 22, 30, 235), outline=GOLD, width=2)
                    draw.text((95, 810), "INDUSTRY REPORT: MASTER ELITE CRAFTSMANSHIP", font=get_font("BarlowCondensed-Bold.ttf", 26), fill=LIGHT_GOLD)
                    draw.text((95, 848), "WHY CERTIFIED INSTALLATION OUTLASTS THE REST", font=get_font("Oswald-Bold.ttf", 38), fill=WHITE)
                    draw.text(
                        (95, 905),
                        "Full tear-off inspection, ice and water shield defense, and precision GAF LayerLock fastening.\nDelivering 50-year non-prorated Golden Pledge protection to New Jersey homeowners.",
                        font=get_font("Inter-Regular.ttf", 20),
                        fill=OFF_WHITE,
                    )

                    btn_y = 985
                    btn_w = 540
                    btn_h = 55
                    btn_x = (W - btn_w) // 2
                    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=28, fill=MAROON, outline=GOLD, width=2)
                    draw_centered_text(draw, "SCHEDULE YOUR FREE ON-SITE INSPECTION", btn_y + 14, get_font("Arial Bold.ttf", 21), WHITE, W)

                    logo = load_clean_logo(light=True, max_w=240, max_h=150)
                    im.paste(logo, ((W - logo.width) // 2, 1090), logo)

                    draw = ImageDraw.Draw(im)
                    foot_y = 1245
                    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
                    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
                    draw_centered_text(draw, f"Website: {CLIENT_INFO['website']}  |  Instagram: {CLIENT_INFO['instagram']}", foot_y + 20, get_font("Arial Bold.ttf", 21), WHITE, W)
                    draw_centered_text(draw, f"Phone: {CLIENT_INFO['phone']}  |  {CLIENT_INFO['address']}", foot_y + 52, get_font("Inter-Regular.ttf", 19), OFF_WHITE, W)
                    draw_centered_text(draw, f"Licensed & Insured {CLIENT_INFO['license']}", foot_y + 80, get_font("Inter-Regular.ttf", 17), MUTED, W)
                    canvas = im

                elif concept.archetype == "invisible_difference":
                    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))
                    bg_photo = LOCAL_APPROVED_DIR / "roof_dotyrd_suburban_estate_001.jpg"
                    if not bg_photo.exists():
                        bg_photo = LOCAL_APPROVED_DIR / "roof_cresskill_aerial_estate_004.jpg"
                    im.paste(load_and_scale_bg(bg_photo, W, H, anchor_y=0.4), (0, 0))
                    im = draw_gradient(im, 0, 480, start_alpha=240, end_alpha=30, color=(12, 16, 22))
                    im = draw_gradient(im, 680, H, start_alpha=0, end_alpha=250, color=(12, 16, 22))
                    draw = ImageDraw.Draw(im)

                    draw_centered_text(draw, "THE DIFFERENCE ISN'T", 60, get_font("Oswald-Bold.ttf", 66), WHITE, W)
                    draw_centered_text(draw, "ALWAYS VISIBLE", 135, get_font("Oswald-Bold.ttf", 66), WHITE, W)

                    bar_w = 640
                    bar_x = (W - bar_w) // 2
                    bar_y = 225
                    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 55], radius=28, fill=MAROON, outline=GOLD, width=2)
                    draw_centered_text(draw, "IT'S BUILT INTO EVERY DECISION", bar_y + 14, get_font("BarlowCondensed-Bold.ttf", 26), WHITE, W)

                    p_y = 320
                    p_w = 220
                    gap = 24
                    start_px = (W - (4 * p_w + 3 * gap)) // 2
                    pillars = ["1. INSPECTION", "2. MATERIALS", "3. INSTALLATION", "4. PERFORMANCE"]
                    for i, p in enumerate(pillars):
                        px = start_px + i * (p_w + gap)
                        draw.rounded_rectangle([px, p_y, px + p_w, p_y + 50], radius=10, fill=(20, 26, 36, 230), outline=GOLD, width=1)
                        draw_centered_in_box(draw, p, px, px + p_w, p_y + 14, get_font("Arial Bold.ttf", 17), LIGHT_GOLD)

                    card_y = 780
                    draw.rounded_rectangle([60, card_y, W - 60, 1050], radius=16, fill=(16, 22, 30, 235), outline=GOLD, width=2)
                    draw.text((95, card_y + 25), "GAF MASTER ELITE CERTIFIED INSTALLATION", font=get_font("BarlowCondensed-Bold.ttf", 26), fill=LIGHT_GOLD)
                    draw.text((95, card_y + 60), "50-YEAR GOLDEN PLEDGE PROTECTION", font=get_font("Oswald-Bold.ttf", 38), fill=WHITE)
                    draw.text(
                        (95, card_y + 115),
                        "• Decking: 100% inspection and replacement of damaged plywood.\n• Underlayment: High-performance synthetic shield & leak defense.\n• Shingles: GAF Timberline HDZ mechanically locked against 130 MPH winds.",
                        font=get_font("Inter-Regular.ttf", 20),
                        fill=OFF_WHITE,
                    )

                    btn_y = card_y + 195
                    btn_w = 560
                    btn_h = 55
                    btn_x = (W - btn_w) // 2
                    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=28, fill=MAROON, outline=GOLD, width=2)
                    draw_centered_text(draw, f"GET YOUR FREE ESTIMATE: {CLIENT_INFO['phone']}", btn_y + 14, get_font("Arial Bold.ttf", 22), WHITE, W)

                    logo = load_clean_logo(light=True, max_w=240, max_h=150)
                    im.paste(logo, ((W - logo.width) // 2, 1090), logo)

                    draw = ImageDraw.Draw(im)
                    foot_y = 1245
                    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
                    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
                    draw_centered_text(draw, f"{CLIENT_INFO['name']}  •  Hackensack, NJ  •  {CLIENT_INFO['license']}", foot_y + 22, get_font("Arial Bold.ttf", 21), WHITE, W)
                    draw_centered_text(draw, f"{CLIENT_INFO['website']}  •  {CLIENT_INFO['instagram']}  •  {CLIENT_INFO['phone']}", foot_y + 54, get_font("Inter-Regular.ttf", 19), OFF_WHITE, W)
                    canvas = im

                elif concept.archetype == "weather_defense":
                    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))
                    bg_photo = LOCAL_APPROVED_DIR / "roof_cresskill_aerial_estate_004.jpg"
                    im.paste(load_and_scale_bg(bg_photo, W, H), (0, 0))
                    im = draw_gradient(im, 0, 420, start_alpha=245, end_alpha=30, color=(12, 16, 22))
                    im = draw_gradient(im, 480, H, start_alpha=20, end_alpha=250, color=(12, 16, 22))

                    logo = load_clean_logo(light=True, max_w=140, max_h=110)
                    im.paste(logo, ((W - logo.width) // 2, 22), logo)

                    draw = ImageDraw.Draw(im)
                    draw_centered_text(draw, "YOUR ROOF FACES THIS EVERY YEAR", 155, get_font("Oswald-Bold.ttf", 52), WHITE, W)
                    draw_centered_text(draw, "North Jersey seasons demand an engineered roofing system built to endure.", 220, get_font("Inter-Regular.ttf", 20), LIGHT_GOLD, W)

                    card_w = 220
                    card_h = 320
                    card_y = 500
                    gap = 24
                    start_cx = (W - (4 * card_w + 3 * gap)) // 2
                    weather_items = [
                        ("SUMMER HEAT", "Intense UV Sun", "Algae-resistant granules prevent shingle blistering & thermal breakdown."),
                        ("HEAVY RAIN", "Driving Storms", "Dual-layer ice & water shield ensures watertight roof valley defense."),
                        ("COASTAL WINDS", "130 MPH Gusts", "GAF LayerLock technology mechanically fastens against blow-offs."),
                        ("WINTER FREEZE", "Snow & Ice Dams", "Proper attic ventilation and waterproof barriers stop leaks cold."),
                    ]

                    for i, (season, title, desc) in enumerate(weather_items):
                        cx = start_cx + i * (card_w + gap)
                        draw.rounded_rectangle([cx, card_y, cx + card_w, card_y + card_h], radius=14, fill=(16, 22, 30, 235), outline=GOLD, width=2)
                        draw.rounded_rectangle([cx, card_y, cx + card_w, card_y + 45], radius=14, fill=MAROON)
                        draw_centered_in_box(draw, season, cx, cx + card_w, card_y + 12, get_font("Arial Bold.ttf", 17), WHITE)
                        draw_centered_in_box(draw, title, cx, cx + card_w, card_y + 60, get_font("Arial Bold.ttf", 20), LIGHT_GOLD)
                        words = desc.split()
                        lines = []
                        cur = []
                        for w in words:
                            if len(" ".join(cur + [w])) <= 20:
                                cur.append(w)
                            else:
                                lines.append(" ".join(cur))
                                cur = [w]
                        if cur:
                            lines.append(" ".join(cur))
                        dy = card_y + 115
                        for line_txt in lines:
                            draw_centered_in_box(draw, line_txt, cx, cx + card_w, dy, get_font("Inter-Regular.ttf", 16), OFF_WHITE)
                            dy += 24

                    banner_y = 860
                    banner_w = 952
                    banner_x = (W - banner_w) // 2
                    draw.rounded_rectangle([banner_x, banner_y, banner_x + banner_w, banner_y + 85], radius=16, fill=MAROON, outline=GOLD, width=2)
                    draw_centered_text(draw, "FREE SAME-DAY ON-SITE ROOF INSPECTION", banner_y + 16, get_font("Arial Bold.ttf", 26), WHITE, W)
                    draw_centered_text(draw, f"Comprehensive digital analysis with zero obligation • Call {CLIENT_INFO['phone']}", banner_y + 48, get_font("Inter-Regular.ttf", 18), LIGHT_GOLD, W)

                    btn_y = 975
                    btn_w = 580
                    btn_h = 70
                    btn_x = (W - btn_w) // 2
                    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=35, fill=GOLD)
                    draw_centered_text(draw, f"CALL {CLIENT_INFO['phone']} NOW", btn_y + 14, get_font("Arial Bold.ttf", 24), DARK_MAROON, W)
                    draw_centered_text(draw, "GAF Master Elite Certified  •  Licensed & Insured", btn_y + 42, get_font("Inter-Regular.ttf", 17), DARK_MAROON, W)

                    foot_y = 1245
                    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
                    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
                    draw_centered_text(draw, f"Website: {CLIENT_INFO['website']}  |  Instagram: {CLIENT_INFO['instagram']}", foot_y + 20, get_font("Arial Bold.ttf", 21), WHITE, W)
                    draw_centered_text(draw, f"Phone: {CLIENT_INFO['phone']}  |  {CLIENT_INFO['address']}", foot_y + 52, get_font("Inter-Regular.ttf", 19), OFF_WHITE, W)
                    draw_centered_text(draw, f"Licensed & Insured {CLIENT_INFO['license']}", foot_y + 80, get_font("Inter-Regular.ttf", 17), MUTED, W)
                    canvas = im

                elif concept.archetype == "siding_financing":
                    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))
                    bg_photo = LOCAL_APPROVED_DIR / "siding_cresskill_luxury_curb_appeal_001.jpg"
                    im.paste(load_and_scale_bg(bg_photo, W, H), (0, 0))
                    im = draw_gradient(im, 0, 460, start_alpha=245, end_alpha=30, color=(14, 18, 24))
                    im = draw_gradient(im, 640, H, start_alpha=0, end_alpha=250, color=(14, 18, 24))

                    logo = load_clean_logo(light=True, max_w=140, max_h=110)
                    im.paste(logo, ((W - logo.width) // 2, 22), logo)

                    draw = ImageDraw.Draw(im)
                    draw_centered_text(draw, "NEW SIDING. $0 DOWN.", 155, get_font("Oswald-Bold.ttf", 60), WHITE, W)
                    draw_centered_text(draw, "NO PAYMENTS FOR A YEAR.", 225, get_font("Oswald-Bold.ttf", 60), GOLD, W)

                    b_y = 315
                    b_w = 290
                    b_h = 120
                    gap = 35
                    start_bx = (W - (3 * b_w + 2 * gap)) // 2
                    badges = [
                        ("$0", "DOWN"),
                        ("0", "PAYMENTS"),
                        ("0%", "INTEREST (12 MO)"),
                    ]
                    for i, (bval, blbl) in enumerate(badges):
                        bx = start_bx + i * (b_w + gap)
                        draw.rounded_rectangle([bx, b_y, bx + b_w, b_y + b_h], radius=14, fill=(107, 21, 40, 240), outline=GOLD, width=2)
                        draw_centered_in_box(draw, bval, bx, bx + b_w, b_y + 12, get_font("Oswald-Bold.ttf", 48), WHITE)
                        draw_centered_in_box(draw, blbl, bx, bx + b_w, b_y + 76, get_font("Arial Bold.ttf", 17), LIGHT_GOLD)

                    card_y = 790
                    draw.rounded_rectangle([60, card_y, W - 60, 1050], radius=16, fill=(16, 22, 30, 235), outline=GOLD, width=2)
                    draw.text((95, card_y + 25), "PREMIUM EXTERIOR SPECIALISTS • LICENSED & INSURED", font=get_font("BarlowCondensed-Bold.ttf", 26), fill=LIGHT_GOLD)
                    draw.text((95, card_y + 60), "TRANSFORM YOUR HOME'S CURB APPEAL & EFFICIENCY", font=get_font("Oswald-Bold.ttf", 38), fill=WHITE)
                    draw.text(
                        (95, card_y + 115),
                        "James Hardie fiber cement and premium insulated vinyl siding.\nEngineered moisture barriers, custom aluminum trim, and lifetime durability.",
                        font=get_font("Inter-Regular.ttf", 20),
                        fill=OFF_WHITE,
                    )

                    btn_y = card_y + 185
                    btn_w = 620
                    btn_h = 55
                    btn_x = (W - btn_w) // 2
                    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=28, fill=MAROON, outline=GOLD, width=2)
                    draw_centered_text(draw, "CLAIM YOUR $0 DOWN FINANCING TODAY", btn_y + 14, get_font("Arial Bold.ttf", 22), WHITE, W)

                    foot_y = 1245
                    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
                    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
                    draw_centered_text(draw, f"Website: {CLIENT_INFO['website']}  |  Instagram: {CLIENT_INFO['instagram']}", foot_y + 20, get_font("Arial Bold.ttf", 21), WHITE, W)
                    draw_centered_text(draw, f"Phone: {CLIENT_INFO['phone']}  |  {CLIENT_INFO['address']}", foot_y + 52, get_font("Inter-Regular.ttf", 19), OFF_WHITE, W)
                    draw_centered_text(draw, f"Licensed & Insured {CLIENT_INFO['license']}", foot_y + 80, get_font("Inter-Regular.ttf", 17), MUTED, W)
                    canvas = im

                elif concept.archetype == "september_savings_promo":
                    im = Image.new("RGBA", (W, H), (14, 18, 24, 255))
                    bg_photo = LOCAL_APPROVED_DIR / "DJI_0081.JPG"
                    im.paste(load_and_scale_bg(bg_photo, W, H), (0, 0))
                    im = draw_gradient(im, 0, 480, start_alpha=245, end_alpha=30, color=(14, 18, 24))
                    im = draw_gradient(im, 600, H, start_alpha=0, end_alpha=250, color=(14, 18, 24))

                    logo = load_clean_logo(light=True, max_w=150, max_h=110)
                    im.paste(logo, ((W - logo.width) // 2, 20), logo)

                    draw = ImageDraw.Draw(im)
                    draw_centered_text(draw, "SEPTEMBER SAVINGS EVENT", 155, get_font("Oswald-Bold.ttf", 52), GOLD, W)
                    draw_centered_text(draw, "LIMITED TIME FALL ROOF & SIDING INCENTIVE", 215, get_font("BarlowCondensed-Bold.ttf", 26), WHITE, W)

                    card_y = 300
                    card_w = 460
                    card_h = 240
                    # Left Promo Card: $500 OFF
                    draw.rounded_rectangle([60, card_y, 60 + card_w, card_y + card_h], radius=16, fill=(107, 21, 40, 240), outline=GOLD, width=2)
                    draw_centered_in_box(draw, "$500 OFF", 60, 60 + card_w, card_y + 20, get_font("Oswald-Bold.ttf", 54), WHITE)
                    draw_centered_in_box(draw, "SINGLE REPLACEMENT", 60, 60 + card_w, card_y + 85, get_font("Arial Bold.ttf", 20), LIGHT_GOLD)
                    draw_centered_in_box(draw, "Valid on any full roof or", 60, 60 + card_w, card_y + 130, get_font("Inter-Regular.ttf", 19), OFF_WHITE)
                    draw_centered_in_box(draw, "complete siding installation.", 60, 60 + card_w, card_y + 160, get_font("Inter-Regular.ttf", 19), OFF_WHITE)

                    # Right Promo Card: $1,000 OFF BUNDLE
                    rx = W - 60 - card_w
                    draw.rounded_rectangle([rx, card_y, rx + card_w, card_y + card_h], radius=16, fill=(16, 22, 30, 240), outline=GOLD, width=2)
                    draw_centered_in_box(draw, "$1,000 OFF", rx, rx + card_w, card_y + 20, get_font("Oswald-Bold.ttf", 54), GOLD)
                    draw_centered_in_box(draw, "2-PROJECT BUNDLE", rx, rx + card_w, card_y + 85, get_font("Arial Bold.ttf", 20), WHITE)
                    draw_centered_in_box(draw, "Pair roof replacement with", rx, rx + card_w, card_y + 130, get_font("Inter-Regular.ttf", 19), OFF_WHITE)
                    draw_centered_in_box(draw, "new siding for maximum savings.", rx, rx + card_w, card_y + 160, get_font("Inter-Regular.ttf", 19), OFF_WHITE)

                    # Info Box
                    info_y = 800
                    draw.rounded_rectangle([60, info_y, W - 60, 1050], radius=16, fill=(16, 22, 30, 235), outline=GOLD, width=2)
                    draw.text((95, info_y + 25), "EXCLUSIVELY FOR NORTH JERSEY HOMEOWNERS", font=get_font("BarlowCondensed-Bold.ttf", 26), fill=LIGHT_GOLD)
                    draw.text((95, info_y + 60), "50-YEAR GOLDEN PLEDGE PROTECTION INCLUDED", font=get_font("Oswald-Bold.ttf", 36), fill=WHITE)
                    draw.text(
                        (95, info_y + 115),
                        "*Repairs are not eligible for this offer. Valid exclusively on full replacement projects\nscheduled through September 30. GAF Master Elite certified workmanship.",
                        font=get_font("Inter-Regular.ttf", 20),
                        fill=OFF_WHITE,
                    )

                    btn_y = info_y + 185
                    btn_w = 580
                    btn_h = 55
                    btn_x = (W - btn_w) // 2
                    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=28, fill=MAROON, outline=GOLD, width=2)
                    draw_centered_text(draw, "CLAIM YOUR SEPTEMBER SAVINGS NOW", btn_y + 14, get_font("Arial Bold.ttf", 22), WHITE, W)

                    foot_y = 1245
                    draw.rectangle([0, foot_y, W, H], fill=(12, 16, 22, 255))
                    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
                    draw_centered_text(draw, f"Website: {CLIENT_INFO['website']}  |  Instagram: {CLIENT_INFO['instagram']}", foot_y + 20, get_font("Arial Bold.ttf", 21), WHITE, W)
                    draw_centered_text(draw, f"Phone: {CLIENT_INFO['phone']}  |  {CLIENT_INFO['address']}", foot_y + 52, get_font("Inter-Regular.ttf", 19), OFF_WHITE, W)
                    draw_centered_text(draw, f"Licensed & Insured {CLIENT_INFO['license']}", foot_y + 80, get_font("Inter-Regular.ttf", 17), MUTED, W)
                    canvas = im

                else:
                    # Clean generic fallback for any other archetype (e.g. magazine_contractor, price_comparison, warning_signs, etc.)
                    canvas = load_and_scale_bg(concept.background_photo, W, H)
                    canvas = draw_gradient(canvas, 0, 380, start_alpha=240, end_alpha=20, color=(14, 18, 24))
                    canvas = draw_gradient(canvas, H - 550, H, start_alpha=0, end_alpha=245, color=(14, 18, 24))
                    draw = ImageDraw.Draw(canvas)

                    # Clean top header with transparent logo
                    logo = load_clean_logo(light=True, max_w=200, max_h=100)
                    canvas.paste(logo, (50, 30), logo)
                    draw = ImageDraw.Draw(canvas)
                    draw.text((W - 50, 75), "GAF MASTER ELITE CERTIFIED", font=get_font("BarlowCondensed-Bold.ttf", 26), anchor="rm", fill=GOLD)

                    # Headline & body card at bottom safe area
                    card_y = H - 460
                    draw.rounded_rectangle([50, card_y, W - 50, H - 120], radius=16, fill=(16, 22, 30, 235), outline=GOLD, width=2)
                    draw.text((80, card_y + 30), concept.name.upper(), font=get_font("Oswald-Bold.ttf", 40), fill=WHITE)
                    draw.text((80, card_y + 85), "Precision Craftsmanship • 50-Year Golden Pledge Warranty • Direct Pricing", font=get_font("BarlowCondensed-Bold.ttf", 24), fill=LIGHT_GOLD)
                    draw.text((80, card_y + 130), "Serving Bergen, Passaic, and Northern New Jersey Homeowners with certified excellence.", font=get_font("Inter-Regular.ttf", 20), fill=OFF_WHITE)

                    btn_y = card_y + 185
                    btn_w = 560
                    btn_h = 55
                    btn_x = (W - btn_w) // 2
                    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=28, fill=MAROON, outline=GOLD, width=2)
                    draw_centered_text(draw, f"FREE ON-SITE ESTIMATE: {CLIENT_INFO['phone']}", btn_y + 14, get_font("Arial Bold.ttf", 22), WHITE, W)

                    # Footer
                    foot_y = H - 95
                    draw.rectangle((0, foot_y, W, H), fill=(10, 14, 20))
                    draw.line([(0, foot_y), (W, foot_y)], fill=GOLD, width=2)
                    draw.text((W // 2, foot_y + 45), f"{CLIENT_INFO['phone']}  |  {CLIENT_INFO['website']}  |  {CLIENT_INFO['license']}", font=get_font("Inter-Regular.ttf", 20), anchor="mm", fill=WHITE)

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

            from google import genai
            from PIL import Image
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


def run_daily_generation(
    count: int = 5,
    when: date | None = None,
    force: bool = False,
    engine_mode: str = "local",
) -> list[Path]:
    """Execute the daily flyer generation workflow and write directly to Google Drive.
    Defaults to engine_mode='local' to guarantee:
    - 100% adherence to authentic vector logo (no white sticker boxes)
    - Full-bleed native Instagram 4:5 1080x1350 px sizing with zero blurry sides
    - Strict GAF / green ZIP material standards (zero ABC Pro Guard)
    - High-contrast, publication-grade typography
    """
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
    if engine_mode == "ai":
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
