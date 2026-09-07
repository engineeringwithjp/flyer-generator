"""Command-line interface.

    python -m app.cli generate --client all-elite --count 2
    python -m app.cli ingest-reference references/inbox/example.jpg
    python -m app.cli validate
    python -m app.cli list-references
    python -m app.cli list-clients

Installed as ``flyer`` by ``pip install -e .``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from . import references as reference_lib
from .config import get_settings
from .errors import FlyerError
from .logging_setup import configure_logging, get_logger
from .models import ReferenceStatus

log = get_logger(__name__)

BOLD, DIM, GREEN, RED, YELLOW, RESET = (
    ("\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[0m")
    if sys.stdout.isatty()
    else ("", "", "", "", "", "")
)


# --------------------------------------------------------------------- utils


def _print_qa(title: str, result) -> bool:
    mark = f"{GREEN}PASS{RESET}" if result.passed else f"{RED}FAIL{RESET}"
    print(f"\n{BOLD}{title}{RESET}  {mark}  (score {result.score})")
    for issue in result.issues:
        print(f"  {RED}error{RESET}   {issue.check}: {issue.message}")
        if issue.detail:
            print(f"          {DIM}{issue.detail}{RESET}")
    for issue in result.warnings:
        print(f"  {YELLOW}warning{RESET} {issue.check}: {issue.message}")
    if not result.issues and not result.warnings:
        print(f"  {DIM}no issues{RESET}")
    return result.passed


def _write_step_summary(markdown: str) -> None:
    """Append to the GitHub Actions job summary when running in CI."""
    target = os.getenv("GITHUB_STEP_SUMMARY")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(markdown + "\n")


def _set_output(name: str, value: str) -> None:
    target = os.getenv("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


# ------------------------------------------------------------------ commands


def cmd_generate(args: argparse.Namespace) -> int:
    from .pipeline.generate import generate_flyers, today_in

    settings = get_settings()
    when = date.fromisoformat(args.date) if args.date else today_in(settings.schedule_timezone)

    run = generate_flyers(
        client_id=args.client,
        count=args.count,
        campaign=args.campaign,
        upload=not args.no_upload,
        when=when,
        message=args.message,
        archetype=args.archetype,
        product=args.product,
        cta=args.cta,
        tools=args.tools,
    )

    print(f"\n{BOLD}Run {run.run_id}{RESET}")
    for index, result in enumerate(run.results, start=1):
        status = f"{GREEN}PASS{RESET}" if result.qa_passed else f"{RED}FAIL{RESET}"
        print(f"  {index}. {status} {result.spec.text.headline}")
        print(f"     {DIM}{result.spec.campaign_id} / {result.spec.layout.name}{RESET}")
        print(f"     {result.image_path}")
        if result.drive_url:
            print(f"     Drive: {result.drive_url}")
    for error in run.errors:
        print(f"  {RED}!{RESET} {error}")

    summary_path = Path(run.results[0].image_path).parent / "SUMMARY.md" if run.results else None
    if summary_path and summary_path.exists():
        _write_step_summary(summary_path.read_text(encoding="utf-8"))
    _set_output("run_id", run.run_id)
    _set_output("flyers_generated", str(len(run.results)))
    _set_output("flyers_passed", str(run.succeeded))
    if run.results:
        _set_output("output_dir", str(Path(run.results[0].image_path).parent))

    if not run.results:
        return 1
    return 0 if run.succeeded == len(run.results) and not run.errors else 2


def cmd_ingest(args: argparse.Namespace) -> int:
    from .pipeline.ingest import ingest_directory, ingest_reference

    settings = get_settings()
    status = ReferenceStatus(args.status)
    target = Path(args.path) if args.path else settings.paths.reference_inbox

    if target.is_dir():
        results = ingest_directory(target, status=status, move=not args.copy)
    else:
        results = [ingest_reference(target, status=status, move=not args.copy, force=args.force)]

    if not results:
        print("Nothing to ingest.")
        return 0

    print(f"\n{BOLD}Ingested {len(results)} reference(s){RESET}")
    rows = []
    for reference in results:
        print(f"  {reference.id}  {reference.category:<12} {reference.style:<18} {reference.path}")
        print(f"    {DIM}{reference.description}{RESET}")
        rows.append(
            f"| `{reference.id}` | {reference.category} | {reference.style} | "
            f"{reference.layout} | {reference.text_density} | {reference.status} |"
        )
    _write_step_summary(
        "## Reference ingestion\n\n"
        "| ID | Category | Style | Layout | Density | Status |\n"
        "|----|----------|-------|--------|---------|--------|\n" + "\n".join(rows)
    )
    _set_output("ingested_count", str(len(results)))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .clients.loader import list_clients
    from .pipeline.validate import has_photo_library, validate_environment

    settings = get_settings()
    ok = True

    print(f"{BOLD}Configuration{RESET}")
    for key, value in settings.describe().items():
        print(f"  {key:<18} {value}")

    ok &= _print_qa("Environment", validate_environment(settings))

    clients = list_clients(include_disabled=True)
    if not clients:
        print(f"\n{RED}No client profiles found in clients/{RESET}")
        ok = False
    for client in clients:
        from .clients.validator import validate_client

        ok &= _print_qa(f"Client: {client.id}", validate_client(client))

    print(f"\n{BOLD}Libraries{RESET}")
    summary = reference_lib.summarise_library()
    print(
        f"  references        {summary.get('total', 0)} "
        f"(approved {summary.get('approved', 0)}, experimental {summary.get('experimental', 0)}, "
        f"rejected {summary.get('rejected', 0)})"
    )
    print(
        f"  photo library     {'present' if has_photo_library(settings) else 'empty (procedural backgrounds will be used)'}"
    )

    from .rendering.typography import FontLibrary

    fonts = FontLibrary(settings.paths.fonts).available()
    print(
        f"  fonts             {len(fonts)} in assets/fonts"
        + (f" ({', '.join(fonts[:4])}...)" if fonts else "")
    )

    print()
    if ok:
        print(f"{GREEN}Validation passed.{RESET}")
        return 0
    print(f"{RED}Validation failed - fix the errors above.{RESET}")
    return 1


def cmd_list_clients(args: argparse.Namespace) -> int:
    from .clients.loader import list_clients

    clients = list_clients(include_disabled=True)
    if not clients:
        print("No clients configured. Copy clients/_template/ to clients/<your-slug>/.")
        return 1
    if args.json:
        print(json.dumps([c.model_dump() for c in clients], indent=2))
        return 0
    print(f"{BOLD}{'ID':<16} {'Company':<34} {'Services':<40} Enabled{RESET}")
    for client in clients:
        services = ", ".join(client.services)[:38]
        print(
            f"{client.id:<16} {client.company_name[:33]:<34} {services:<40} "
            f"{'yes' if client.enabled else 'no'}"
        )
    return 0


def cmd_list_references(args: argparse.Namespace) -> int:
    index = reference_lib.load_index()
    references = index.references
    if args.status:
        references = [r for r in references if r.status.value == args.status]
    if args.category:
        references = [r for r in references if r.category == args.category]

    if args.json:
        print(json.dumps([r.model_dump() for r in references], indent=2))
        return 0

    if not references:
        print(
            "No references yet. Drop images into references/inbox/ and run "
            "`python -m app.cli ingest-reference`."
        )
        return 0

    print(
        f"{BOLD}{'ID':<12} {'Status':<14} {'Category':<12} {'Style':<20} "
        f"{'Layouts':<28} Path{RESET}"
    )
    for reference in references:
        layouts = ",".join(reference.suggested_layouts)[:26]
        print(
            f"{reference.id:<12} {reference.status.value:<14} {reference.category:<12} "
            f"{reference.style:<20} {layouts:<28} {reference.path}"
        )
    print(f"\n{DIM}{len(references)} reference(s){RESET}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    reference = reference_lib.promote(args.reference_id, ReferenceStatus(args.status))
    print(f"{reference.id} is now {reference.status} at {reference.path}")
    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    """Record a human approve/reject decision and feed it back into scoring."""
    from .pipeline import history

    entry = history.find_entry(args.flyer_id)
    if entry is None:
        print(f"{RED}No history entry for flyer {args.flyer_id!r}{RESET}")
        return 1

    approved = args.decision == "approve"
    history.set_outcome(args.flyer_id, approved, args.reason)
    reference_lib.record_outcome(entry.get("reference_ids", []), approved)

    verdict = f"{GREEN}approved{RESET}" if approved else f"{RED}rejected{RESET}"
    print(f"Flyer {args.flyer_id} {verdict}")
    if args.reason:
        print("  reasons: " + ", ".join(args.reason))
    print(
        f"  {DIM}campaign {entry.get('campaign')} | references "
        f"{', '.join(entry.get('reference_ids') or ['none'])}{RESET}"
    )
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    from .pipeline import history

    entries = history.for_client(args.client or get_settings().default_client, limit=args.limit)
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    if not entries:
        print("No generation history yet.")
        return 0
    print(
        f"{BOLD}{'Date':<12} {'Campaign':<24} {'Layout':<20} {'QA':<5} "
        f"{'Approved':<9} Headline{RESET}"
    )
    for entry in entries:
        approved = entry.get("approved")
        flag = "-" if approved is None else ("yes" if approved else "no")
        print(
            f"{entry.get('date', ''):<12} {entry.get('campaign', ''):<24} "
            f"{entry.get('layout', ''):<20} {entry.get('qa_score', 0):<5} {flag:<9} "
            f"{entry.get('headline', '')}"
        )
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    from .assets.catalog import AssetCatalog

    catalog = AssetCatalog.load(refresh=True, deep=not args.fast)
    assets = catalog.index.assets
    if args.json:
        print(json.dumps([a.model_dump() for a in assets], indent=2))
        return 0
    if not assets:
        print(
            "Photo library is empty. Add JPG/PNG files under assets/<service>/ "
            "or clients/<slug>/assets/approved/."
        )
        return 0
    eligible = [a for a in assets if a.production_eligible]
    blocked = [a for a in assets if not a.production_eligible]

    print(f"{BOLD}{'ID':<42} {'Service':<10} {'Source':<16} {'Prod':<5} Project{RESET}")
    for asset in assets:
        mark = f"{GREEN}yes{RESET}  " if asset.production_eligible else f"{RED}NO{RESET}   "
        print(
            f"{asset.id[:41]:<42} {asset.service:<10} "
            f"{asset.provenance.source_type.value:<16} {mark} "
            f"{asset.provenance.address_label or '-'}"
        )

    print(f"\n{DIM}{len(assets)} asset(s) indexed{RESET}")
    print(f"  {GREEN}{len(eligible)}{RESET} production-eligible")
    if blocked:
        reasons: dict[str, int] = {}
        for asset in blocked:
            key = asset.provenance.source_type.value
            reasons[key] = reasons.get(key, 0) + 1
        detail = ", ".join(f"{count} {kind}" for kind, count in sorted(reasons.items()))
        print(f"  {YELLOW}{len(blocked)}{RESET} blocked from production ({detail})")
    return 0


def cmd_layouts(args: argparse.Namespace) -> int:
    from .rendering.templates import layout_description, list_layouts

    for name in list_layouts():
        print(f"{BOLD}{name}{RESET}\n  {layout_description(name)}")
    return 0


def cmd_schedule_check(args: argparse.Namespace) -> int:
    """Is *now* the configured run time in the business timezone?

    GitHub Actions cron is UTC-only, so the workflow fires on both possible UTC
    hours and this command decides which one is the real 10:07 locally.
    """
    from .schedule import decide

    settings = get_settings()
    result = decide(tolerance_minutes=args.tolerance)

    print(f"Timezone   {settings.schedule_timezone}")
    print(f"Now        {result.local_time}")
    if result.mode == "interval":
        print(
            f"Schedule   every {settings.schedule_interval_hours}h within "
            f"{settings.schedule_window} on {settings.schedule_days}"
        )
    else:
        print(f"Schedule   {settings.schedule_time} on {settings.schedule_days}")
    verdict = f"{GREEN}yes{RESET}" if result.should_run else f"{DIM}no{RESET}"
    print(f"Should run {verdict}  ({result.reason})")

    _set_output("should_run", "true" if result.should_run else "false")
    _set_output("local_date", result.local_date)
    return 0 if result.should_run else 1


def cmd_assets(args: argparse.Namespace) -> int:
    """Review, promote and reject media. The human gate before production."""
    from .assets.catalog import AssetCatalog
    from .assets.review import pending, promote, reject

    catalog = AssetCatalog.load(refresh=args.refresh)

    if args.stage and args.set_stage_for:
        from .assets.review import set_stage

        for asset in set_stage(catalog, list(args.set_stage_for), args.stage):
            print(f"  {GREEN}{args.stage}{RESET}  {asset.path.split('/')[-1]}")
        return 0

    if args.unclassified:
        from .assets.review import unclassified

        waiting = unclassified(catalog, args.client)
        if not waiting:
            print(f"{GREEN}Every production asset has a work state recorded.{RESET}")
            return 0
        print(f"{BOLD}{len(waiting)} production asset(s) with no work state{RESET}")
        print(f"{DIM}These cannot illustrate premium, upgrade, proof, emotional or offer")
        print(f"messages, because an unknown state might be a tear-off.{RESET}\n")
        for asset in waiting:
            print(f"  {asset.id}")
        print(f"\n{DIM}Tag them with:  flyer assets --stage after --set-stage-for <id> <id>{RESET}")
        return 0

    if args.promote or args.reject or args.promote_top:
        ids = list(args.promote or [])
        if args.promote_top:
            ids += [a.id for a in pending(catalog, args.client)[: args.promote_top]]
        if ids:
            for asset in promote(catalog, ids):
                print(f"  {GREEN}approved{RESET}  {asset.path}")
        if args.reject:
            for asset in reject(catalog, list(args.reject)):
                print(f"  {RED}rejected{RESET}  {asset.id}")
        return 0

    waiting = pending(catalog, args.client)
    eligible = [a for a in catalog.index.assets if a.production_eligible]

    print(f"{BOLD}Asset library{RESET}")
    print(f"  {GREEN}{len(eligible)}{RESET} production-eligible")
    print(f"  {YELLOW}{len(waiting)}{RESET} real media awaiting review")
    blocked = [a for a in catalog.index.assets if a.is_synthetic]
    if blocked:
        print(f"  {DIM}{len(blocked)} synthetic, permanently barred{RESET}")

    if waiting:
        print(f"\n{BOLD}{'Score':<8}{'Source':<16}{'Asset'}{RESET}")
        for asset in waiting[: args.show]:
            print(
                f"  {asset.quality_score:<6.3f}{asset.provenance.source_type.value:<16}"
                f"{asset.id[:62]}"
            )
        if len(waiting) > args.show:
            print(f"  {DIM}... and {len(waiting) - args.show} more{RESET}")
        print(
            f"\n{DIM}Promote with:  flyer assets --promote-top 10{RESET}\n"
            f"{DIM}Or by id:      flyer assets --promote <id> <id>{RESET}"
        )
    return 0


def cmd_ingest_media(args: argparse.Namespace) -> int:
    """Scan a drive or SD card and extract the best flyer-usable frames."""
    from .media import ingest_media

    report = ingest_media(
        source=Path(args.source).expanduser(),
        client_id=args.client or get_settings().default_client,
        per_video=args.per_video,
        samples=args.samples,
        limit=args.limit,
        copy_photos=not args.no_photos,
        dry_run=args.dry_run,
        project=args.project or "",
    )

    print(f"\n{BOLD}Media ingestion{RESET}  {report.summary()}")
    if report.kept:
        print(f"\n{BOLD}{'Score':<8}{'Frame':<30}{'sharp expo cont neg  bal'}{RESET}")
        for candidate in sorted(report.kept, key=lambda c: -c.total)[: args.show]:
            scores = candidate.scores
            print(
                f"  {candidate.total:<6.3f}{candidate.label:<30}"
                f"{scores['sharpness']:.2f}  {scores['exposure']:.2f} "
                f"{scores['contrast']:.2f} {scores['negative_space']:.2f} "
                f"{scores['detail_balance']:.2f}"
            )
    for error in report.errors[:8]:
        print(f"  {YELLOW}!{RESET} {error}")
    if len(report.errors) > 8:
        print(f"  {DIM}... and {len(report.errors) - 8} more{RESET}")

    if not args.dry_run and report.frames_kept:
        print(
            f"\n{DIM}Frames written as client_frame / unapproved. They are real media "
            f"but NOT production-eligible until you review them.{RESET}"
        )
        print(f"{DIM}Run `flyer catalog` to index, then promote what you want to use.{RESET}")
    _set_output("frames_kept", str(report.frames_kept))
    return 0 if not report.errors or report.frames_kept else 1


def cmd_connectors(args: argparse.Namespace) -> int:
    """What external design tools are actually reachable right now."""
    from .connectors import status_report

    report = status_report()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    labels = {
        "available": f"{GREEN}available{RESET}",
        "config_required": f"{YELLOW}needs authorisation{RESET}",
        "not_installed": f"{DIM}not connected here{RESET}",
        "disabled": f"{DIM}disabled in config{RESET}",
        "failed": f"{RED}failed{RESET}",
    }
    print(f"{BOLD}Connected design ecosystem{RESET}\n")
    for name, info in report.items():
        print(
            f"  {BOLD}{name:<10}{RESET} {labels.get(info['status'], info['status'])}"
            f"   {DIM}({info['role']}){RESET}"
        )
        print(f"             {info['description']}")
        print(f"             {DIM}use when: {info['use_when']}{RESET}")
        print(f"             {DIM}fallback: {info['fallback']}{RESET}\n")
    print(f"{DIM}Every one of these can be unavailable; the daily run still completes.{RESET}")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    """Dry-run the connector decision engine."""
    from .connectors import decide, parse_overrides

    decision = decide(
        has_suitable_asset=not args.no_asset,
        internal_reference_count=args.references,
        best_reference_score=args.reference_score,
        editable_deliverable_requested=args.editable,
        building_template_system=args.template_work,
        overrides=parse_overrides(args.tools),
    )
    if args.json:
        print(decision.model_dump_json(indent=2))
        return 0
    print(f"{BOLD}Decision{RESET}  {decision.explain()}\n")
    for name, why in decision.skipped.items():
        print(f"  {DIM}skipped {name}: {why}{RESET}")
    if decision.overrides_applied:
        print(f"\n  overrides: {', '.join(decision.overrides_applied)}")
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    """Prompt-to-Skill: turn the historical prompt corpus into a proposal."""
    from .ai.prompt_distiller import distill, write_proposal

    payload = distill()
    path = write_proposal(payload)

    rules = payload.get("extracted_rules", [])
    hard = sum(1 for r in rules if r.get("class") == "hard")
    conflicts = payload.get("conflicts", [])
    needs_call = sum(1 for c in conflicts if c.get("needs_operator_decision"))

    print(f"\n{BOLD}Distillation complete{RESET}")
    print(f"  rules extracted   {len(rules)} ({hard} hard)")
    print(f"  never rules       {len(payload.get('never_rules', []))}")
    print(f"  conflicts         {len(conflicts)} ({needs_call} need your decision)")
    print(f"  not promoted      {len(payload.get('not_promoted', []))}")
    print(f"\n  proposal: {path}")
    print(f"  {DIM}Nothing was applied. Review the proposal and merge what you agree with.{RESET}")
    _write_step_summary(path.read_text(encoding="utf-8"))
    _set_output("proposal_path", str(path))
    return 0


def cmd_design_system(args: argparse.Namespace) -> int:
    from . import design_system

    if args.json:
        print(json.dumps(design_system.principles(), indent=2))
        return 0
    if args.stage:
        print(design_system.compile_for_stage(args.stage, args.client))
        return 0
    print(f"{BOLD}Design system{RESET}")
    for key, value in design_system.summary().items():
        print(f"  {key:<22} {value}")
    print(f"\n{BOLD}Composition archetypes{RESET}")
    for item in design_system.archetypes():
        print(f"  {item['id']:<22} -> {item['layout']:<20} {item['use_case']}")
    return 0


def cmd_intake(args: argparse.Namespace) -> int:
    """Import whatever is sitting in the DROP HERE folders."""
    from .intake import DROP_ROOT, run_intake

    report = run_intake(client_id=args.client)
    print(f"{BOLD}Intake{RESET}  {report.summary()}")
    if report.converted:
        print(f"  {DIM}converted {report.converted} HEIC file(s) to JPEG{RESET}")
    for note in report.notes:
        print(f"  {DIM}{note}{RESET}")
    for skipped in report.skipped:
        print(f"  {YELLOW}skipped{RESET} {skipped}")
    if not report.total:
        print(f"  {DIM}Drop files into '{DROP_ROOT}' and run this again.{RESET}")
    _set_output("imported", str(report.total))
    return 0


def cmd_drive_setup(args: argparse.Namespace) -> int:
    """Point the flyer output at your Google Drive folder.

    With Drive for Desktop running there is nothing to authorise: flyers are
    written into the mounted folder and Drive syncs them.
    """
    from .drive.local import describe, find_folder, suggest_env_line

    settings = get_settings()
    info = describe(settings)

    print(f"{BOLD}Google Drive for Desktop{RESET}")
    if not info["mounts_found"]:
        print(f"  {RED}No Drive mount found.{RESET}")
        print(f"  {DIM}Install Google Drive for Desktop and sign in, then re-run.{RESET}")
        return 1
    mounts = info["mounts_found"] if isinstance(info["mounts_found"], list) else []
    for mount in mounts:
        print(f"  {GREEN}mounted{RESET}  {mount}")

    if info["configured_exists"]:
        print(f"\n  {GREEN}configured{RESET}  {info['configured_path']}")
        print(f"  {DIM}Flyers are written straight into Drive.{RESET}")
        return 0

    folder = find_folder(args.folder)
    if folder is None:
        print(f"\n  {YELLOW}Could not find a folder named {args.folder!r}.{RESET}")
        print(f'  {DIM}Pass --folder "Your Folder Name", or set DRIVE_LOCAL_PATH by hand.{RESET}')
        return 1

    print(f"\n  {GREEN}found{RESET}  {folder}")
    line = suggest_env_line(folder)

    env = settings.paths.root / ".env"
    if args.write:
        existing = env.read_text(encoding="utf-8") if env.exists() else ""
        if "DRIVE_LOCAL_PATH" in existing:
            print(f"  {DIM}.env already sets DRIVE_LOCAL_PATH; leaving it alone.{RESET}")
        else:
            with env.open("a", encoding="utf-8") as handle:
                handle.write(f"\n# Flyers are written here instead of output/\n{line}\n")
            print(f"  {GREEN}written to .env{RESET}")
    else:
        print(f"\n  Add this to .env:\n      {line}")
        print(f"  {DIM}Or re-run with --write to do it automatically.{RESET}")

    print(f"\n  {DIM}{info['streaming_hint']}{RESET}")
    return 0


def cmd_deliver(args: argparse.Namespace) -> int:
    """Promote an already-rendered, already-reviewed batch into Google Drive.

    ``flyer generate --no-upload`` leaves the batch in ``output/`` so it can be
    looked at. This is the second half: it re-reads the QA sidecars, applies the
    batch checks, and moves only what passed. It exists because reviewing one
    batch and then re-running ``generate`` delivers a *different* batch - the
    planner picks fresh campaigns every run - so the flyers that reach the
    client are not the ones anybody looked at.
    """
    import json
    from datetime import date as date_type

    from .clients.loader import load_client
    from .models import FlyerResult, GenerationRun
    from .pipeline.deliver import deliver
    from .pipeline.generate import today_in

    settings = get_settings()
    client = load_client(args.client or settings.default_client)
    when = date_type.fromisoformat(args.date) if args.date else today_in(settings.schedule_timezone)

    staged = settings.paths.output / when.isoformat() / client.id
    sidecars = sorted(staged.glob("flyer-*.json"))
    if not sidecars:
        print(f"{YELLOW}Nothing staged for {when} - run `flyer generate --no-upload` first.{RESET}")
        return 1

    # A retried flyer leaves two sidecars behind - flyer-02.json and
    # flyer-02-retry2.json - for the same flyer. Loading both makes the batch
    # check see a flyer as a duplicate of itself and hold the pair. Keep the
    # last attempt per flyer id, which is the one the run actually kept.
    by_id: dict[str, FlyerResult] = {}
    skipped = 0
    for sidecar in sidecars:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if payload.get("delivered_path"):
            skipped += 1
            continue
        result = FlyerResult.model_validate(
            {k: v for k, v in payload.items() if k in FlyerResult.model_fields}
        )
        result.metadata_path = str(sidecar)
        previous = by_id.get(result.spec.id)
        if previous is None or result.attempts >= previous.attempts:
            by_id[result.spec.id] = result
    results = sorted(by_id.values(), key=lambda r: r.spec.id)

    if not results:
        print(f"{DIM}Everything staged for {when} has already been delivered.{RESET}")
        return 0

    run = GenerationRun(
        run_id=f"deliver_{when.isoformat()}",
        client_id=client.id,
        date=when.isoformat(),
        results=results,
    )
    report = deliver(run, client, when, settings)

    for flyer_id in report.delivered:
        print(f"  {GREEN}delivered{RESET}  {flyer_id}")
    for flyer_id, reason in report.held:
        print(f"  {RED}held{RESET}       {flyer_id}  {DIM}{reason}{RESET}")
    if skipped:
        print(f"  {DIM}{skipped} already delivered, left alone{RESET}")
    print(f"\n{report.summary()}")
    return 0 if report.delivered else 1


def cmd_coverage(args: argparse.Namespace) -> int:
    """Which services actually have photography behind them.

    A campaign for a service with no photographs still renders - it just gets
    a generic exterior aerial, and the reader sees a roof under a headline
    about gutters. This is the report that surfaces that before the flyer does.
    """
    from .assets.catalog import AssetCatalog
    from .assets.selector import photo_coverage
    from .clients.loader import load_client

    client = load_client(args.client or get_settings().default_client)
    counts = photo_coverage(AssetCatalog.load(), client.id, client.services)
    general = counts.pop("general", 0)

    print(f"{BOLD}Photo coverage{RESET}  {client.company_name}\n")
    thin = []
    for service in client.services:
        count = counts.get(service.lower(), 0)
        if count == 0:
            mark, note = f"{RED}none{RESET}", "campaigns fall back to a generic exterior"
            thin.append(service)
        elif count < 3:
            mark, note = f"{YELLOW}{count}{RESET}", "every flyer reuses the same shot"
            thin.append(service)
        else:
            mark, note = f"{GREEN}{count}{RESET}", ""
        print(f"  {service:<12} {mark:>16}  {DIM}{note}{RESET}")
    print(f"  {'general':<12} {general:>7}  {DIM}exterior aerials, usable by any campaign{RESET}")

    if thin:
        print(
            f"\n{YELLOW}Thin:{RESET} {', '.join(thin)}. Drop photographs into "
            f"{DIM}'DROP HERE/2 client photos'{RESET} named for the service "
            f"({DIM}gutters-guards-hillsdale-01.jpg{RESET}) and run {DIM}flyer intake{RESET}."
        )
    return 0


def cmd_storage(args: argparse.Namespace) -> int:
    """Where the disk is going, and what can safely go."""
    from .storage import human, stale_worktrees, usage

    areas = usage()
    total = sum(areas.values())
    print(f"{BOLD}Disk usage{RESET}  {human(total)} total\n")
    for name, size in sorted(areas.items(), key=lambda kv: -kv[1]):
        if not size:
            continue
        share = size / total * 100 if total else 0
        bar = "#" * max(int(share / 3), 0)
        print(f"  {human(size):>9}  {share:4.1f}%  {bar:<34} {name}")

    worktrees = stale_worktrees()
    if worktrees:
        waste = sum(size for _, size in worktrees)
        print(
            f"\n  {YELLOW}{human(waste)}{RESET} is Claude Code worktrees - a complete "
            f"duplicate of this project."
        )
        print(f"  {DIM}Safe to delete once your work is committed:{RESET}")
        print("      rm -rf .claude/worktrees")

    print(f"\n{DIM}Reclaim space with:  flyer clean{RESET}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Reclaim disk. Nothing that is not safely reproducible is removed."""
    from .storage import (
        StorageReport,
        downscale_library,
        human,
        prune_output,
        prune_unreviewed_frames,
    )

    combined = StorageReport()
    steps = []
    if not args.only or args.only == "output":
        steps.append(prune_output(keep_days=args.keep_days, dry_run=args.dry_run))
    if not args.only or args.only == "frames":
        steps.append(prune_unreviewed_frames(keep_top=args.keep_frames, dry_run=args.dry_run))
    if not args.only or args.only == "photos":
        steps.append(downscale_library(max_edge=args.max_edge, dry_run=args.dry_run))

    for step in steps:
        combined.freed_bytes += step.freed_bytes
        combined.output_runs_removed += step.output_runs_removed
        combined.frames_removed += step.frames_removed
        combined.assets_downscaled += step.assets_downscaled
        combined.details += step.details

    label = f"{BOLD}Would free{RESET}" if args.dry_run else f"{BOLD}Freed{RESET}"
    print(f"{label}  {human(combined.freed_bytes)}")
    for detail in combined.details:
        print(f"  {DIM}{detail}{RESET}")
    if args.dry_run:
        print(f"\n{DIM}Nothing was changed. Re-run without --dry-run to apply.{RESET}")
    return 0


def cmd_gallery(args: argparse.Namespace) -> int:
    from .publish import build_gallery

    path = build_gallery(Path(args.out))
    print(f"Gallery written to {path}")
    return 0


# ----------------------------------------------------------------- argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flyer",
        description="AI-powered construction marketing flyer automation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  flyer generate --client all-elite --count 2
  flyer generate --campaign siding --message "built-in insulation" --cta "Free Estimate"
  flyer distill
  flyer ingest-media /Volumes/Untitled/DCIM/101MEDIA --project bergenfield
  flyer ingest-reference references/inbox/nice-roofing-ad.jpg
  flyer promote ref_000001 approved
  flyer feedback run_2026-09-05_ab12cd_01 reject --reason "headline too small"
  flyer validate
""",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="generate today's flyers")
    gen.add_argument("--client", help="client slug (default: DEFAULT_CLIENT)")
    gen.add_argument("--count", type=int, help="how many flyers (default: DEFAULT_FLYER_COUNT)")
    gen.add_argument("--campaign", help="force a campaign id or a service name")
    gen.add_argument(
        "--message", help="the one thing this flyer is about, e.g. 'built-in insulation'"
    )
    gen.add_argument("--archetype", help="composition archetype id (see `flyer design-system`)")
    gen.add_argument("--product", help="manufacturer product id to feature")
    gen.add_argument("--cta", help="override the call to action")
    gen.add_argument(
        "--tools",
        help='plain-language connector override, e.g. "use canva", "no stock photography", '
        '"internal only". Omit it and the system decides.',
    )
    gen.add_argument("--date", help="ISO date to generate for (default: today, business timezone)")
    gen.add_argument("--no-upload", action="store_true", help="skip the Google Drive upload")
    gen.set_defaults(func=cmd_generate)

    ing = subparsers.add_parser("ingest-reference", help="analyse and file reference images")
    ing.add_argument("path", nargs="?", help="image or directory (default: references/inbox)")
    ing.add_argument(
        "--status", default="experimental", choices=["experimental", "approved", "rejected"]
    )
    ing.add_argument("--copy", action="store_true", help="copy instead of moving the file")
    ing.add_argument("--force", action="store_true", help="re-analyse a duplicate")
    ing.set_defaults(func=cmd_ingest)

    val = subparsers.add_parser("validate", help="check configuration, clients and libraries")
    val.set_defaults(func=cmd_validate)

    lc = subparsers.add_parser("list-clients", help="list configured clients")
    lc.add_argument("--json", action="store_true")
    lc.set_defaults(func=cmd_list_clients)

    lr = subparsers.add_parser("list-references", help="list the design-reference library")
    lr.add_argument("--status", choices=["approved", "experimental", "rejected", "inbox"])
    lr.add_argument("--category")
    lr.add_argument("--json", action="store_true")
    lr.set_defaults(func=cmd_list_references)

    pro = subparsers.add_parser("promote", help="move a reference between libraries")
    pro.add_argument("reference_id")
    pro.add_argument("status", choices=["approved", "experimental", "rejected"])
    pro.set_defaults(func=cmd_promote)

    fb = subparsers.add_parser("feedback", help="approve or reject a generated flyer")
    fb.add_argument("flyer_id")
    fb.add_argument("decision", choices=["approve", "reject"])
    fb.add_argument("--reason", action="append", default=[], help="repeatable")
    fb.set_defaults(func=cmd_feedback)

    his = subparsers.add_parser("history", help="show generation history")
    his.add_argument("--client")
    his.add_argument("--limit", type=int, default=20)
    his.add_argument("--json", action="store_true")
    his.set_defaults(func=cmd_history)

    cat = subparsers.add_parser("catalog", help="rebuild and show the photo index")
    cat.add_argument("--fast", action="store_true", help="skip Pillow analysis")
    cat.add_argument("--json", action="store_true")
    cat.set_defaults(func=cmd_catalog)

    lay = subparsers.add_parser("layouts", help="list the available flyer layouts")
    lay.set_defaults(func=cmd_layouts)

    sch = subparsers.add_parser(
        "schedule-check", help="exit 0 only if now is the configured local run time"
    )
    sch.add_argument("--tolerance", type=int, default=45, help="minutes either side")
    sch.set_defaults(func=cmd_schedule_check)

    ast = subparsers.add_parser("assets", help="review, promote and reject media")
    ast.add_argument("--client", help="limit to one client")
    ast.add_argument("--promote", nargs="+", metavar="ID", help="approve these asset ids")
    ast.add_argument(
        "--promote-top",
        type=int,
        metavar="N",
        help="approve the N highest-scoring candidates awaiting review",
    )
    ast.add_argument("--reject", nargs="+", metavar="ID", help="reject these asset ids")
    ast.add_argument("--refresh", action="store_true", help="rebuild the index first")
    ast.add_argument(
        "--unclassified",
        action="store_true",
        help="list production assets with no work state recorded",
    )
    ast.add_argument(
        "--stage",
        choices=["before", "during", "after", "neutral"],
        help="work state to record (use with --set-stage-for)",
    )
    ast.add_argument(
        "--set-stage-for", nargs="+", metavar="ID", help="asset ids to apply --stage to"
    )
    ast.add_argument("--show", type=int, default=25)
    ast.set_defaults(func=cmd_assets)

    med = subparsers.add_parser(
        "ingest-media", help="scan a drive/SD card and extract the best flyer frames"
    )
    med.add_argument("source", help="folder to scan, e.g. /Volumes/Untitled/DCIM/101MEDIA")
    med.add_argument("--client", help="client slug (default: DEFAULT_CLIENT)")
    med.add_argument("--per-video", type=int, default=1, help="frames to keep per clip")
    med.add_argument("--samples", type=int, default=4, help="frames to consider per clip")
    med.add_argument("--limit", type=int, help="only process the first N clips")
    med.add_argument("--project", help="project label, e.g. bergenfield")
    med.add_argument("--no-photos", action="store_true", help="skip copying stills")
    med.add_argument("--dry-run", action="store_true", help="score without writing")
    med.add_argument("--show", type=int, default=20, help="how many results to print")
    med.set_defaults(func=cmd_ingest_media)

    con = subparsers.add_parser("connectors", help="show external connector status")
    con.add_argument("--json", action="store_true")
    con.set_defaults(func=cmd_connectors)

    dec = subparsers.add_parser("decide", help="dry-run the connector decision engine")
    dec.add_argument("--no-asset", action="store_true", help="pretend no suitable photo exists")
    dec.add_argument("--references", type=int, default=5, help="internal references available")
    dec.add_argument("--reference-score", type=float, default=0.8, help="best internal match 0..1")
    dec.add_argument("--editable", action="store_true", help="client wants an editable file")
    dec.add_argument("--template-work", action="store_true", help="building the master system")
    dec.add_argument("--tools", help='override phrase, e.g. "use canva"')
    dec.add_argument("--json", action="store_true")
    dec.set_defaults(func=cmd_decide)

    dis = subparsers.add_parser(
        "distill", help="Prompt-to-Skill: distil historical prompts into a design-system proposal"
    )
    dis.set_defaults(func=cmd_distill)

    dsy = subparsers.add_parser("design-system", help="inspect the compiled design system")
    dsy.add_argument(
        "--stage",
        choices=["planner", "copywriter", "designer", "qa", "reference"],
        help="print the exact block injected into this stage's prompt",
    )
    dsy.add_argument("--client", help="include this client's stored preferences")
    dsy.add_argument("--json", action="store_true")
    dsy.set_defaults(func=cmd_design_system)

    itk = subparsers.add_parser("intake", help="import pictures from the DROP HERE folders")
    itk.add_argument("--client", help="client slug (default: DEFAULT_CLIENT)")
    itk.set_defaults(func=cmd_intake)

    drv = subparsers.add_parser(
        "drive-setup", help="write flyers straight into your Google Drive folder"
    )
    drv.add_argument("--folder", default="Client Flyers", help="folder name to look for in Drive")
    drv.add_argument("--write", action="store_true", help="append the setting to .env")
    drv.set_defaults(func=cmd_drive_setup)

    dlv = subparsers.add_parser(
        "deliver",
        help="move an already-reviewed staged batch into Google Drive",
    )
    dlv.add_argument("--client", help="client slug (default: DEFAULT_CLIENT)")
    dlv.add_argument("--date", help="ISO date of the staged batch (default: today)")
    dlv.set_defaults(func=cmd_deliver)

    cov = subparsers.add_parser("coverage", help="which services have photography and which do not")
    cov.add_argument("--client", help="client slug (default: DEFAULT_CLIENT)")
    cov.set_defaults(func=cmd_coverage)

    sto = subparsers.add_parser("storage", help="show where disk space is going")
    sto.set_defaults(func=cmd_storage)

    cln = subparsers.add_parser("clean", help="reclaim disk space safely")
    cln.add_argument(
        "--keep-days",
        type=int,
        default=7,
        help="keep rendered flyers this many days (uploaded ones only)",
    )
    cln.add_argument(
        "--keep-frames",
        type=int,
        default=40,
        help="keep this many top-scoring unreviewed candidates",
    )
    cln.add_argument(
        "--max-edge",
        type=int,
        help="downscale stored photos to this long edge (default ASSET_MAX_EDGE)",
    )
    cln.add_argument("--only", choices=["output", "frames", "photos"], help="run just one step")
    cln.add_argument("--dry-run", action="store_true", help="report without deleting")
    cln.set_defaults(func=cmd_clean)

    gal = subparsers.add_parser("gallery", help="build the static approved-flyer gallery")
    gal.add_argument("--out", default="site", help="output directory")
    gal.set_defaults(func=cmd_gallery)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging("DEBUG" if args.verbose else None)
    try:
        return int(args.func(args))
    except FlyerError as exc:
        print(f"\n{RED}{type(exc).__name__}:{RESET} {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
