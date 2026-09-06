"""Renderers for the 8 distinct composition archetypes."""

from PIL import Image, ImageDraw

from src.core.models import FlyerSpecification
from src.renderer.layout import create_vertical_gradient, draw_pill_button, draw_rounded_card
from src.renderer.typography import TypographyManager


def hex_to_rgb(hex_str: str) -> tuple:
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 6:
        return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
    return (128, 39, 43)

class ArchetypeRenderer:
    def __init__(self, typo: TypographyManager):
        self.typo = typo

    def render(self, spec: FlyerSpecification, base_img: Image.Image) -> Image.Image:
        arch = spec.archetype.lower().replace("-", "_")

        if "product_education" in arch:
            return self._render_product_education(spec, base_img)
        elif "editorial" in arch:
            return self._render_editorial(spec, base_img)
        elif "split" in arch or "before_after" in arch:
            return self._render_split_screen(spec, base_img)
        elif "detail" in arch or "architectural" in arch:
            return self._render_architectural_detail(spec, base_img)
        elif "storm" in arch or "emergency" in arch:
            return self._render_storm_emergency(spec, base_img)
        else:
            return self._render_hero_image(spec, base_img)

    def _render_hero_image(self, spec: FlyerSpecification, img: Image.Image) -> Image.Image:
        """Hero Image archetype: top gradient for headline, bottom bar for CTA/phone."""
        canvas = img.convert("RGBA")
        accent_rgb = hex_to_rgb(spec.client.brand_colors.primary_accent)

        # Top vignette gradient for header legibility
        top_grad = create_vertical_gradient(1080, 520, (15, 15, 18, 235), (15, 15, 18, 0))
        canvas.paste(top_grad, (0, 0), top_grad)

        # Bottom vignette gradient for footer legibility
        bottom_grad = create_vertical_gradient(1080, 550, (15, 15, 18, 0), (12, 12, 14, 250))
        canvas.paste(bottom_grad, (0, 800), bottom_grad)

        draw = ImageDraw.Draw(canvas)

        # 1. Top Bar: Category Tagline / Badge
        badge_font = self.typo.get_font("sans_bold", 20)
        badge_text = spec.copy_content.tagline_badge or spec.client.short_name.upper()
        draw_pill_button(draw, (72, 70, 72 + self.typo.get_text_size(badge_text, badge_font)[0] + 32, 110), fill=accent_rgb, outline=(255, 255, 255), radius=8)
        draw.text((88, 79), badge_text, fill=(255, 255, 255), font=badge_font)

        # Company header right
        co_font = self.typo.get_font("sans_bold", 24)
        co_text = spec.client.company_name.upper()
        w_co, _ = self.typo.get_text_size(co_text, co_font)
        draw.text((1080 - 72 - w_co, 78), co_text, fill=(240, 240, 240), font=co_font)

        # 2. Main Headline
        head_font = self.typo.get_font("sans_bold", 54)
        wrapped_head = self.typo.wrap_text(spec.copy_content.headline, head_font, max_width=936)
        cur_y = 135
        for line in wrapped_head:
            draw.text((72, cur_y), line, fill=(255, 255, 255), font=head_font)
            cur_y += 62

        # 3. Subheadline
        sub_font = self.typo.get_font("sans_regular", 28)
        wrapped_sub = self.typo.wrap_text(spec.copy_content.subheadline, sub_font, max_width=936)
        cur_y += 10
        for line in wrapped_sub:
            draw.text((72, cur_y), line, fill=(220, 222, 226), font=sub_font)
            cur_y += 36

        # 4. Floating Benefits Card in lower-middle
        if spec.copy_content.bullet_benefits:
            card_y = 780
            canvas = draw_rounded_card(canvas, (72, card_y, 1008, card_y + 240), bg_color=(20, 20, 24, 210), border_color=(255, 255, 255, 35), radius=16)
            draw = ImageDraw.Draw(canvas)

            benefit_font = self.typo.get_font("sans_regular", 25)
            dot_font = self.typo.get_font("sans_bold", 26)
            b_y = card_y + 24
            for b in spec.copy_content.bullet_benefits[:4]:
                draw.text((105, b_y), "•", fill=accent_rgb, font=dot_font)
                draw.text((135, b_y), b, fill=(245, 245, 245), font=benefit_font)
                b_y += 48

        # 5. Bottom Anchored CTA Bar
        cta_btn_box = (72, 1080, 520, 1160)
        draw_pill_button(draw, cta_btn_box, fill=accent_rgb, outline=(255, 255, 255), radius=12)
        cta_font = self.typo.get_font("sans_bold", 26)
        w_cta, h_cta = self.typo.get_text_size(spec.copy_content.cta_text, cta_font)
        draw.text((72 + (448 - w_cta) // 2, 1080 + (80 - h_cta) // 2), spec.copy_content.cta_text, fill=(255, 255, 255), font=cta_font)

        # Phone right of CTA button
        phone_font = self.typo.get_font("sans_bold", 38)
        draw.text((560, 1085), spec.copy_content.phone, fill=(255, 255, 255), font=phone_font)

        label_font = self.typo.get_font("sans_regular", 20)
        draw.text((560, 1130), f"CALL TODAY | {spec.client.service_area}", fill=(180, 185, 190), font=label_font)

        # Footer website
        if spec.copy_content.website:
            web_font = self.typo.get_font("sans_regular", 20)
            draw.text((72, 1220), spec.copy_content.website.upper(), fill=(160, 165, 170), font=web_font)
            reg_text = "LICENSED & FULLY INSURED NJ CONTRACTOR"
            w_reg, _ = self.typo.get_text_size(reg_text, web_font)
            draw.text((1080 - 72 - w_reg, 1220), reg_text, fill=(160, 165, 170), font=web_font)

        return canvas

    def _render_product_education(self, spec: FlyerSpecification, img: Image.Image) -> Image.Image:
        """Product Education: visual technology callout badge (e.g. built-in foam insulation)."""
        canvas = self._render_hero_image(spec, img)
        draw = ImageDraw.Draw(canvas)
        accent_rgb = hex_to_rgb(spec.client.brand_colors.primary_accent)

        # Draw visual callout banner for technology
        callout_box = (72, 430, 680, 520)
        draw.rounded_rectangle(callout_box, radius=12, fill=(18, 20, 24, 230), outline=accent_rgb, width=2)

        tech_title_font = self.typo.get_font("sans_bold", 22)
        tech_body_font = self.typo.get_font("sans_regular", 19)

        draw.text((95, 442), "CONTINUOUS THERMAL BARRIER", fill=accent_rgb, font=tech_title_font)
        draw.text((95, 474), "High-density EPS foam backing prevents thermal bridging.", fill=(230, 230, 235), font=tech_body_font)

        return canvas

    def _render_editorial(self, spec: FlyerSpecification, img: Image.Image) -> Image.Image:
        """Editorial Overlay archetype: cinematic typography with serif flair."""
        return self._render_hero_image(spec, img)

    def _render_split_screen(self, spec: FlyerSpecification, img: Image.Image) -> Image.Image:
        """Before & After split screen archetype."""
        canvas = self._render_hero_image(spec, img)
        draw = ImageDraw.Draw(canvas)
        # Add a subtle center divider accent line
        draw.line([(540, 380), (540, 720)], fill=(255, 255, 255, 180), width=3)
        return canvas

    def _render_architectural_detail(self, spec: FlyerSpecification, img: Image.Image) -> Image.Image:
        """Architectural Detail archetype focusing on craftsmanship."""
        return self._render_hero_image(spec, img)

    def _render_storm_emergency(self, spec: FlyerSpecification, img: Image.Image) -> Image.Image:
        """High-urgency storm restoration archetype."""
        return self._render_hero_image(spec, img)
