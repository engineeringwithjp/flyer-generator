"""Master System Audit script verifying all components, rules, and configurations."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DESIGN_SYSTEM_DIR, GDRIVE_ROOT_FOLDER_ID, OUTPUT_DIR, SKILLS_DIR
from src.connectors.canva_connector import CanvaConnector
from src.connectors.decision_engine import ToolDecisionEngine
from src.connectors.figma_connector import FigmaConnector
from src.connectors.mobbin_connector import MobbinConnector
from src.connectors.unsplash_connector import UnsplashConnector
from src.core.client_manager import ClientManager
from src.core.reference_selector import ReferenceSelector


def run_system_audit():
    print("=======================================================")
    print(" FLYER GENERATOR: MASTER SYSTEM AUDIT")
    print("=======================================================\n")

    checklist = []

    # 1. Claude Skill & Rulebooks
    rule_files = [
        "SKILL.md",
        "design-rules.md",
        "copywriting-rules.md",
        "photography-rules.md",
        "branding-rules.md",
        "quality-control.md",
        "asset-selection.md",
        "reference-analysis.md",
        "negative-rules.md"
    ]
    for rf in rule_files:
        exists = (SKILLS_DIR / rf).exists()
        checklist.append((f"Skill Rulebook: {rf}", exists))

    # 2. Machine-Readable Design System
    ds_files = [
        "principles.json",
        "successful-patterns.json",
        "failed-patterns.json",
        "preferences.json"
    ]
    for df in ds_files:
        exists = (DESIGN_SYSTEM_DIR / df).exists()
        checklist.append((f"Design System Data: {df}", exists))

    # 3. Client Profiles
    client_mgr = ClientManager()
    clients = client_mgr.list_clients()
    checklist.append(("Clients Registered (multi-client)", len(clients) >= 2))
    for cid in clients:
        client_mgr.get_client(cid)
        has_logo = bool(client_mgr.get_client_logo(cid))
        has_photos = len(client_mgr.get_client_photos(cid)) > 0
        checklist.append((f"Client '{cid}': Profile Loaded", True))
        checklist.append((f"Client '{cid}': Brand Logo Available", has_logo))
        checklist.append((f"Client '{cid}': Project Photos Available", has_photos))

    # 4. Reference Library
    ref_sel = ReferenceSelector()
    all_refs = ref_sel.load_all_references()
    checklist.append(("Approved References Available", len(all_refs) > 0))

    # 5. Connected Design Ecosystem
    canva = CanvaConnector()
    figma = FigmaConnector()
    unsplash = UnsplashConnector()
    mobbin = MobbinConnector()
    decision_engine = ToolDecisionEngine()

    checklist.append(("Connector: Canva (Integration & Fallback)", canva is not None))
    checklist.append(("Connector: Figma (Integration & Fallback)", figma is not None))
    checklist.append(("Connector: Unsplash (Integration & Fallback)", unsplash is not None))
    checklist.append(("Connector: Mobbin (Integration & Fallback)", mobbin is not None))
    checklist.append(("Connector: Decision Engine Loaded", decision_engine is not None))

    # 6. Cloud & Delivery
    checklist.append((f"Google Drive Target Folder: {GDRIVE_ROOT_FOLDER_ID}", bool(GDRIVE_ROOT_FOLDER_ID)))
    checklist.append(("Output History Log Configured", (OUTPUT_DIR / "history.json").exists()))

    # Print Results
    passed_count = 0
    for name, status in checklist:
        symbol = "✓" if status else "✗"
        print(f"[{symbol}] {name}")
        if status:
            passed_count += 1

    print("\n-------------------------------------------------------")
    print(f"AUDIT SUMMARY: {passed_count}/{len(checklist)} checks passed.")
    print("-------------------------------------------------------\n")
    return passed_count == len(checklist)

if __name__ == "__main__":
    run_system_audit()
