"""Main automated flyer generation script."""

import argparse
import datetime
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.connectors.decision_engine import ToolDecisionEngine
from src.core.asset_selector import AssetSelector
from src.core.campaign_planner import CampaignPlanner
from src.core.client_manager import ClientManager
from src.core.copywriter import Copywriter
from src.core.history_tracker import HistoryTracker
from src.core.models import FlyerSpecification, GenerationRecord
from src.core.reference_selector import ReferenceSelector
from src.qa.checker import QAChecker
from src.renderer.engine import FlyerRenderer
from src.services.google_drive import GoogleDriveUploader


def generate_daily_flyers(
    client_id: str = "all-elite",
    count: int = 2,
    campaign_name: str = None,
    focus_topic: str = None,
    cta_override: str = None,
    style_override: str = None,
    upload_drive: bool = True,
    user_overrides: dict = None
):
    print("\n=======================================================")
    print(" FLYER GENERATOR PIPELINE")
    print(f" Client: {client_id} | Count: {count}")
    print("=======================================================")

    # 1. Load Client
    client_mgr = ClientManager()
    client = client_mgr.get_client(client_id)
    print(f"[1/7] Client Loaded: {client.company_name} ({client.service_area})")

    # 2. Plan Campaigns
    history_tracker = HistoryTracker()
    planner = CampaignPlanner(history_tracker)
    campaign_plans = planner.plan_campaigns(
        client=client,
        count=count,
        requested_campaign=campaign_name,
        requested_focus=focus_topic,
        requested_style=style_override
    )

    asset_selector = AssetSelector(client_manager=client_mgr)
    ref_selector = ReferenceSelector()
    copywriter = Copywriter(client)
    decision_engine = ToolDecisionEngine()
    renderer = FlyerRenderer()
    qa_checker = QAChecker()
    gdrive = GoogleDriveUploader()

    generated_flyers = []

    for i, plan in enumerate(campaign_plans, start=1):
        print("\n-------------------------------------------------------")
        print(f" GENERATING FLYER #{i}: {plan['service']} ({plan['focus']})")
        print("-------------------------------------------------------")

        # 3. Decision Engine: Evaluate connected tools
        client_photos = client_mgr.get_client_photos(client_id)
        decision = decision_engine.evaluate(
            has_client_photos=bool(client_photos),
            has_internal_background=True,
            has_approved_references=True,
            user_overrides=user_overrides
        )
        print(f"[Decision Engine] {decision.reason}")

        # 4. Select Reference & Asset
        ref = ref_selector.select_reference(plan["service"], preferred_archetype=plan["archetype"])
        bg_asset = asset_selector.select_background(client_id, plan["service"], photo_index=i - 1)
        logo_path = client_mgr.get_client_logo(client_id)

        print(f"[Reference] Selected: {ref.id} ({ref.name}) - Archetype: {ref.archetype}")
        print(f"[Asset] Source: {bg_asset.source.upper()} ({bg_asset.file_path})")

        # 5. Generate Copywriting (Strict Anti-AI Rules)
        copy = copywriter.generate_copy(
            service=plan["service"],
            focus_topic=plan["focus"],
            custom_cta=cta_override,
            archetype=ref.archetype
        )
        print(f"[Copy] Headline: \"{copy.headline}\"")
        print(f"[Copy] Subhead: \"{copy.subheadline}\"")
        print(f"[Copy] CTA: \"{copy.cta_text}\"")

        # 6. Build Flyer Specification & Render
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        spec_id = f"{client_id}_{plan['service'].lower().replace(' ', '_')}_{now_str}_{i}"

        spec = FlyerSpecification(
            specification_id=spec_id,
            client=client,
            archetype=ref.archetype,
            copy_content=copy,
            background_asset=bg_asset,
            logo_path=logo_path,
            references_used=[ref.id],
            tools_used=["internal_renderer", "claude_skill"],
            created_at=datetime.datetime.now().isoformat()
        )

        rendered_path = renderer.render_flyer(spec)
        print(f"[Render] Output saved: {rendered_path}")

        # 7. Quality Assurance Gate (Human Design Test)
        qa = qa_checker.evaluate(spec, rendered_path)
        print(f"[QA Gate] Score: {qa.score}/100 | Passed: {qa.passed}")
        if not qa.passed:
            print(f"[QA Gate] Violations flagged: {qa.violations}")

        # 8. Google Drive Upload
        drive_file_id = None
        if upload_drive and qa.passed:
            upload_res = gdrive.upload_flyer(rendered_path, client.company_name)
            drive_file_id = upload_res.get("file_id")
            print(f"[Google Drive] Status: {upload_res.get('status')} | File ID: {drive_file_id}")

        # 9. Record in Generation History
        record = GenerationRecord(
            generation_id=spec_id,
            timestamp=datetime.datetime.now().isoformat(),
            client_id=client_id,
            campaign=plan["service"],
            service=plan["service"],
            archetype=ref.archetype,
            headline=copy.headline,
            reference_ids=[ref.id],
            asset_ids=[bg_asset.asset_id],
            tools_used=spec.tools_used,
            renderer="deterministic_pillow",
            qa_score=qa.score,
            output_path=rendered_path,
            drive_file_id=drive_file_id
        )
        history_tracker.add_record(record)
        generated_flyers.append(record)

    print("\n=======================================================")
    print(f" PIPELINE COMPLETE: {len(generated_flyers)} flyers successfully produced.")
    print("=======================================================\n")
    return generated_flyers

def main():
    parser = argparse.ArgumentParser(description="Generate residential construction marketing flyers.")
    parser.add_argument("--client", default="all-elite", help="Client ID (e.g. all-elite)")
    parser.add_argument("--count", type=int, default=2, help="Number of flyers to produce")
    parser.add_argument("--campaign", default=None, help="Campaign topic (e.g. 'Composite Siding')")
    parser.add_argument("--focus", default=None, help="Specific focus angle (e.g. 'Built-in insulation')")
    parser.add_argument("--cta", default=None, help="Call to action override")
    parser.add_argument("--style", default=None, help="Archetype layout style")
    parser.add_argument("--no-upload", action="store_true", help="Skip Google Drive upload")
    parser.add_argument("--force-canva", action="store_true", help="Force Canva workflow")
    parser.add_argument("--force-unsplash", action="store_true", help="Force Unsplash search")
    parser.add_argument("--internal-only", action="store_true", help="Disallow external tools")

    args = parser.parse_args()

    user_overrides = {
        "force_canva": args.force_canva,
        "force_unsplash": args.force_unsplash,
        "internal_only": args.internal_only
    }

    generate_daily_flyers(
        client_id=args.client,
        count=args.count,
        campaign_name=args.campaign,
        focus_topic=args.focus,
        cta_override=args.cta,
        style_override=args.style,
        upload_drive=not args.no_upload,
        user_overrides=user_overrides
    )

if __name__ == "__main__":
    main()
