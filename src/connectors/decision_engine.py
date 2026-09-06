"""Decision engine determining when external design/asset connectors should be invoked."""

from typing import Any, Dict, Optional


class EcosystemDecision:
    def __init__(
        self,
        need_external_reference: bool = False,
        need_stock_photo: bool = False,
        use_canva: bool = False,
        use_figma: bool = False,
        use_mobbin: bool = False,
        reason: str = "Internal assets and approved references fully satisfy design requirements."
    ):
        self.need_external_reference = need_external_reference
        self.need_stock_photo = need_stock_photo
        self.use_canva = use_canva
        self.use_figma = use_figma
        self.use_mobbin = use_mobbin
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "need_external_reference": self.need_external_reference,
            "need_stock_photo": self.need_stock_photo,
            "use_canva": self.use_canva,
            "use_figma": self.use_figma,
            "use_mobbin": self.use_mobbin,
            "reason": self.reason
        }

class ToolDecisionEngine:
    """Evaluates whether Canva, Figma, Unsplash, or Mobbin should be consulted."""

    def evaluate(
        self,
        has_client_photos: bool,
        has_internal_background: bool,
        has_approved_references: bool,
        user_overrides: Optional[Dict[str, Any]] = None
    ) -> EcosystemDecision:
        overrides = user_overrides or {}

        # Handle explicit user instructions first
        if overrides.get("force_canva"):
            return EcosystemDecision(
                use_canva=True,
                reason="User explicitly requested Canva template workflow."
            )
        if overrides.get("force_unsplash"):
            return EcosystemDecision(
                need_stock_photo=True,
                reason="User explicitly requested Unsplash background photography."
            )
        if overrides.get("internal_only") or overrides.get("no_stock"):
            return EcosystemDecision(
                need_stock_photo=False,
                need_external_reference=False,
                reason="User explicitly requested internal assets only."
            )

        # Automatic evaluation
        need_stock = False
        stock_reason = ""
        if not has_client_photos and not has_internal_background:
            need_stock = True
            stock_reason = "No client photos or approved internal backgrounds available; querying Unsplash."

        need_ext_ref = False
        use_mobbin = False
        ref_reason = ""
        if not has_approved_references:
            need_ext_ref = True
            use_mobbin = True
            ref_reason = "No approved references found; querying Mobbin for modern layout patterns."

        if need_stock or need_ext_ref:
            combined_reason = f"{stock_reason} {ref_reason}".strip()
            return EcosystemDecision(
                need_external_reference=need_ext_ref,
                need_stock_photo=need_stock,
                use_mobbin=use_mobbin,
                reason=combined_reason
            )

        return EcosystemDecision(
            need_external_reference=False,
            need_stock_photo=False,
            use_canva=False,
            use_figma=False,
            use_mobbin=False,
            reason="Approved client photography and internal reference system fully satisfy design constraints."
        )
