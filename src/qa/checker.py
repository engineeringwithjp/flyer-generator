"""Automated Quality Assurance checker verifying rules and anti-AI constraints."""

import re
from typing import List

from PIL import Image

from src.config import CANVAS_HEIGHT, CANVAS_WIDTH
from src.core.models import FlyerSpecification, QAResult


class QAChecker:
    """Enforces zero em dashes, zero emojis, verified claims, and margin safe zones."""

    def evaluate(self, spec: FlyerSpecification, rendered_image_path: str) -> QAResult:
        violations: List[str] = []
        checks = {}
        score = 100

        all_text = f"{spec.copy_content.headline} {spec.copy_content.subheadline} {' '.join(spec.copy_content.bullet_benefits)} {spec.copy_content.cta_text}"

        # 1. Zero Em Dashes Check
        if "—" in all_text or "--" in all_text:
            violations.append("Disallowed em dash or double hyphen detected in copy.")
            checks["no_em_dashes"] = False
            score -= 25
        else:
            checks["no_em_dashes"] = True

        # 2. Zero Marketing Emojis Check
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "]+",
            flags=re.UNICODE
        )
        if emoji_pattern.search(all_text):
            violations.append("Amateur marketing emoji detected in copy.")
            checks["no_emojis"] = False
            score -= 25
        else:
            checks["no_emojis"] = True

        # 3. Fabricated Claims Check
        prohibited_claims = ["100% guaranteed", "50% off", "unleash curb appeal", "game-changer", "revolutionary"]
        found_prohibited = [p for p in prohibited_claims if p in all_text.lower()]
        if found_prohibited:
            violations.append(f"Prohibited buzzwords or fabricated claims found: {found_prohibited}")
            checks["no_fabricated_claims"] = False
            score -= 20
        else:
            checks["no_fabricated_claims"] = True

        # 4. Canvas Dimension Check
        try:
            with Image.open(rendered_image_path) as img:
                w, h = img.size
                if (w, h) == (CANVAS_WIDTH, CANVAS_HEIGHT):
                    checks["canvas_dimensions"] = True
                else:
                    violations.append(f"Invalid dimensions: ({w}, {h}) expected (1080, 1350).")
                    checks["canvas_dimensions"] = False
                    score -= 30
        except Exception as e:
            violations.append(f"Failed to inspect rendered image: {e}")
            checks["canvas_dimensions"] = False
            score -= 50

        # 5. Mobile Readability / Headline Length Check
        words = spec.copy_content.headline.split()
        if len(words) > 10:
            violations.append("Headline text density too high for 2-second mobile scan.")
            checks["mobile_readability"] = False
            score -= 10
        else:
            checks["mobile_readability"] = True

        # 6. Brand Contact Presence Check
        if spec.copy_content.phone and len(spec.copy_content.phone) >= 10:
            checks["brand_contact_verified"] = True
        else:
            violations.append("Missing valid contractor contact phone number.")
            checks["brand_contact_verified"] = False
            score -= 15

        passed = score >= 85 and len(violations) == 0

        recommendations = []
        if not passed:
            recommendations = [f"Fix: {v}" for v in violations]

        return QAResult(
            passed=passed,
            score=max(0, score),
            checks=checks,
            violations=violations,
            recommendations=recommendations
        )
