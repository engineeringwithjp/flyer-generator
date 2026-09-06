#!/usr/bin/env python3
"""Unified Command Line Interface for the Flyer Generator system."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.audit_system import run_system_audit
from scripts.generate_flyers import generate_daily_flyers
from scripts.generate_sample_assets import main as generate_assets_main
from scripts.ingest_reference import ingest_inbox_references
from src.services.feedback_learner import FeedbackLearner


def main():
    parser = argparse.ArgumentParser(
        description="Flyer Generator: AI-powered construction flyer generation and automation system."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: generate
    gen_parser = subparsers.add_parser("generate", help="Generate marketing flyers")
    gen_parser.add_argument("--client", default="all-elite", help="Client ID (default: all-elite)")
    gen_parser.add_argument("--count", type=int, default=2, help="Number of flyers (default: 2)")
    gen_parser.add_argument("--campaign", default=None, help="Campaign topic (e.g. 'Composite Siding')")
    gen_parser.add_argument("--focus", default=None, help="Campaign focus (e.g. 'Built-in insulation')")
    gen_parser.add_argument("--cta", default=None, help="Custom CTA override")
    gen_parser.add_argument("--style", default=None, help="Archetype layout style")
    gen_parser.add_argument("--no-upload", action="store_true", help="Skip Google Drive upload")
    gen_parser.add_argument("--force-canva", action="store_true", help="Force Canva workflow")
    gen_parser.add_argument("--force-unsplash", action="store_true", help="Force Unsplash stock")
    gen_parser.add_argument("--internal-only", action="store_true", help="Disallow external tools")

    # Command: ingest
    subparsers.add_parser("ingest", help="Ingest reference images dropped into references/inbox/")

    # Command: approve
    appr_parser = subparsers.add_parser("approve", help="Mark a generated flyer as approved")
    appr_parser.add_argument("--file", required=True, help="Path to flyer PNG")
    appr_parser.add_argument("--archetype", default="hero_image", help="Archetype style")
    appr_parser.add_argument("--note", default=None, help="Optional approval notes")

    # Command: reject
    rej_parser = subparsers.add_parser("reject", help="Mark a generated flyer as rejected")
    rej_parser.add_argument("--file", required=True, help="Path to flyer PNG")
    rej_parser.add_argument("--archetype", default="hero_image", help="Archetype style")
    rej_parser.add_argument("--reason", required=True, help="Reason for rejection")

    # Command: audit
    subparsers.add_parser("audit", help="Run Master System Audit")

    # Command: sample-assets
    subparsers.add_parser("sample-assets", help="Re-generate starter photorealistic assets & logos")

    args = parser.parse_args()

    if args.command == "generate":
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
    elif args.command == "ingest":
        ingest_inbox_references()
    elif args.command == "approve":
        learner = FeedbackLearner()
        learner.record_approval(args.file, args.archetype, notes=args.note)
        print(f"✓ Recorded approval for {args.file}")
    elif args.command == "reject":
        learner = FeedbackLearner()
        learner.record_rejection(args.file, args.archetype, reason=args.reason)
        print(f"✗ Recorded rejection for {args.file}: {args.reason}")
    elif args.command == "audit":
        success = run_system_audit()
        sys.exit(0 if success else 1)
    elif args.command == "sample-assets":
        generate_assets_main()

if __name__ == "__main__":
    main()
