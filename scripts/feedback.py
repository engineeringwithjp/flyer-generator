"""CLI helper for recording flyer approvals and rejections."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.feedback_learner import FeedbackLearner


def main():
    parser = argparse.ArgumentParser(description="Record human approval or rejection of generated flyers.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Approve
    approve_parser = subparsers.add_parser("approve", help="Mark a flyer as approved")
    approve_parser.add_argument("--file", required=True, help="Path to flyer PNG")
    approve_parser.add_argument("--archetype", default="hero_image", help="Archetype of the approved flyer")
    approve_parser.add_argument("--note", default=None, help="Optional approval notes")

    # Reject
    reject_parser = subparsers.add_parser("reject", help="Mark a flyer as rejected")
    reject_parser.add_argument("--file", required=True, help="Path to flyer PNG")
    reject_parser.add_argument("--archetype", default="hero_image", help="Archetype of the rejected flyer")
    reject_parser.add_argument("--reason", required=True, help="Reason for rejection (e.g. 'Too much text')")

    args = parser.parse_args()
    learner = FeedbackLearner()

    if args.action == "approve":
        learner.record_approval(args.file, args.archetype, notes=args.note)
        print(f"✓ Flyer {args.file} marked as APPROVED. Archetype weight for '{args.archetype}' increased.")
    elif args.action == "reject":
        learner.record_rejection(args.file, args.archetype, reason=args.reason)
        print(f"✗ Flyer {args.file} marked as REJECTED. Archetype weight for '{args.archetype}' penalized.")

if __name__ == "__main__":
    main()
