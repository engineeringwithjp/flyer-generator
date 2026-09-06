"""The end-to-end generation pipeline.

    client -> plan -> reference -> assets -> copy -> design spec
           -> render -> QA (-> one retry) -> disk -> Drive -> history

Every stage degrades rather than crashing: no Claude key falls back to the
deterministic planner and copywriter; no photographs fall back to procedural
brand backgrounds; no Drive credentials leave the flyers in ``output/``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import references as reference_lib
from ..ai.campaign_planner import load_catalog, plan_campaigns
from ..ai.claude_client import get_claude
from ..ai.copywriter import write_copy
from ..ai.design_director import direct_design
from ..ai.qa_agent import vision_qa
from ..assets.catalog import AssetCatalog
from ..assets.selector import select_asset, select_pair
from ..clients.loader import load_client
from ..config import Settings, get_settings, load_json_config
from ..connectors import ConnectorOverrides, decide, parse_overrides
from ..errors import FlyerError, RenderError
from ..logging_setup import get_logger, set_run_id
from ..models import (
    Brief,
    CanvasSpec,
    Client,
    FlyerResult,
    FlyerSpecification,
    GenerationRun,
    PlannedFlyer,
    QAResult,
)
from ..rendering.export import export_flyer, thumbnail
from ..rendering.renderer import render_flyer, resolve_render_context
from ..rendering.templates import layout_description
from . import history
from .validate import qa_flyer

log = get_logger(__name__)


def today_in(timezone: str) -> date:
    """The current date in the business timezone, not the runner's UTC."""
    try:
        return datetime.now(ZoneInfo(timezone)).date()
    except Exception:
        log.warning("Unknown timezone %r; falling back to system local time", timezone)
        return date.today()


def generate_flyers(
    client_id: str | None = None,
    count: int | None = None,
    campaign: str | None = None,
    upload: bool = True,
    when: date | None = None,
    settings: Settings | None = None,
    output_dir: Path | None = None,
    message: str | None = None,
    archetype: str | None = None,
    product: str | None = None,
    cta: str | None = None,
    tools: str | None = None,
) -> GenerationRun:
    settings = settings or get_settings()
    settings.paths.ensure()

    client_id = client_id or settings.default_client
    count = count or settings.default_flyer_count
    when = when or today_in(settings.schedule_timezone)

    run_id = f"run_{when.isoformat()}_{uuid.uuid4().hex[:6]}"
    set_run_id(run_id)

    client = load_client(client_id)
    log.info(
        "Generating %d flyer(s) for %s on %s | %s",
        count,
        client.company_name,
        when,
        settings.describe(),
    )

    run = GenerationRun(
        run_id=run_id,
        client_id=client.id,
        date=when.isoformat(),
        requested_count=count,
        model=settings.anthropic_model if settings.claude_enabled else "offline",
        offline=not settings.claude_enabled,
    )

    catalog = load_catalog()
    assets = AssetCatalog.load()
    if assets.is_empty:
        log.warning(
            "No photographs in assets/ or clients/*/assets/ - flyers will use "
            "procedural brand backgrounds. Drop JPG/PNG files in and re-run to use them."
        )

    overrides = parse_overrides(tools)
    if not overrides.is_empty:
        log.info("Connector overrides: %s", overrides.model_dump(exclude_defaults=True))

    past = history.for_client(client.id, limit=40)

    try:
        plan = plan_campaigns(
            client=client,
            count=count,
            today=when,
            history=past,
            forced_campaign=campaign,
            brief=Brief(
                message=message or "", archetype=archetype or "", product_id=product, cta=cta or ""
            ),
        )
    except Exception as exc:
        run.errors.append(f"planning failed: {exc}")
        run.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
        log.error("Campaign planning failed: %s", exc)
        raise

    run.plan = plan.model_dump()
    log.info("Plan: %s", ", ".join(f"{f.campaign_id}/{f.layout}" for f in plan.flyers))

    base_dir = output_dir or (settings.paths.output / when.isoformat() / client.id)
    base_dir.mkdir(parents=True, exist_ok=True)

    canvas = CanvasSpec(width=settings.output_width, height=settings.output_height)
    used_assets: set[str] = set()

    for planned in plan.flyers[:count]:
        try:
            result = _produce_flyer(
                client=client,
                planned=planned,
                catalog=catalog,
                assets=assets,
                canvas=canvas,
                base_dir=base_dir,
                run_id=run_id,
                settings=settings,
                used_assets=used_assets,
                cta_override=cta or "",
                overrides=overrides,
            )
            run.results.append(result)
        except FlyerError as exc:
            message = f"flyer {planned.slot} ({planned.campaign_id}): {exc}"
            run.errors.append(message)
            log.error("%s", message)
        except Exception as exc:  # pragma: no cover - unexpected
            message = f"flyer {planned.slot} ({planned.campaign_id}) crashed: {exc}"
            run.errors.append(message)
            log.exception("%s", message)

    run.tools_used = sorted(
        {"claude" if settings.claude_enabled else "offline-fallback"}
        | {tool for r in run.results for tool in r.spec.tool_decision.get("tools_used", [])}
    )

    if upload and run.results:
        _upload(run, client, when, settings)

    run.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
    history.record_run(run)
    _write_run_summary(run, base_dir)

    log.info(
        "Run %s complete: %d/%d flyer(s) passed QA",
        run_id,
        run.succeeded,
        len(run.results),
    )
    return run


# ---------------------------------------------------------------- one flyer


def _produce_flyer(
    client: Client,
    planned: PlannedFlyer,
    catalog,
    assets: AssetCatalog,
    canvas: CanvasSpec,
    base_dir: Path,
    run_id: str,
    settings: Settings,
    used_assets: set[str],
    cta_override: str = "",
    overrides: ConnectorOverrides | None = None,
) -> FlyerResult:
    campaign = catalog.by_id(planned.campaign_id)
    if campaign is None:
        raise FlyerError(f"Campaign {planned.campaign_id!r} vanished from the catalogue")

    angle_guide = catalog.angles.get(planned.angle, "")
    layout_meta = load_json_config("layouts.json")["layouts"].get(planned.layout, {})
    text_density = layout_meta.get("text_density", "medium")

    recent_refs = history.recent_reference_ids(client.id)
    recent_assets = history.recent_asset_ids(client.id)

    reference = reference_lib.select_reference(
        service=planned.service,
        campaign_id=planned.campaign_id,
        layout=planned.layout,
        client=client,
        recent_reference_ids=recent_refs,
    )

    if planned.layout == "before-after":
        primary, secondary = select_pair(
            assets, client.id, planned.service, planned.layout, recent_assets
        )
    else:
        primary = select_asset(
            assets,
            client.id,
            planned.service,
            planned.layout,
            recent_assets,
            exclude=used_assets,
        )
        secondary = None

    for asset in (primary, secondary):
        if asset:
            used_assets.add(asset.id)

    # Decide whether any external connector earns its place for THIS flyer.
    # The bias is heavily toward doing nothing: internal work has to be
    # insufficient before a call is made, and every skip is recorded.
    usable_references = len(reference_lib.load_index().usable())
    best_score = (
        reference_lib.score_reference(
            reference, planned.service, planned.campaign_id, planned.layout, client, recent_refs
        )
        if reference
        else 0.0
    )
    decision = decide(
        has_suitable_asset=primary is not None and "placeholders" not in primary.path,
        internal_reference_count=usable_references,
        best_reference_score=best_score,
        overrides=overrides,
    )
    log.info("Tool decision: %s", decision.explain())

    copy = write_copy(
        client=client,
        planned=planned,
        campaign=campaign,
        angle_guide=angle_guide,
        text_density=text_density,
        recent_headlines=history.recent_headlines(client.id),
    )
    if cta_override:
        copy = copy.model_copy(update={"cta": cta_override[:32]})

    flyer_id = f"{run_id}_{planned.slot:02d}"
    spec = direct_design(
        client=client,
        planned=planned,
        copy=copy,
        asset=primary,
        secondary_asset=secondary,
        reference=reference,
        layout_description=layout_description(planned.layout),
        canvas=canvas,
        flyer_id=flyer_id,
    )
    spec.tool_decision = decision.model_dump()

    result = _render_and_check(spec, client, assets, base_dir, planned.slot, settings)

    # One automatic retry with a heavier scrim and a safer layout.
    if not result.qa_passed:
        log.warning("Flyer %s failed QA - retrying once with a safer treatment", flyer_id)
        retry_spec = spec.model_copy(deep=True)
        retry_spec.image.overlay = "dark_flat"
        retry_spec.image.overlay_strength = min(retry_spec.image.overlay_strength + 0.2, 0.88)
        retry_spec.layout.accent_shape = True
        if len(retry_spec.text.bullets) > 2:
            retry_spec.text.bullets = retry_spec.text.bullets[:2]
        retry = _render_and_check(
            retry_spec, client, assets, base_dir, planned.slot, settings, attempt=2
        )
        if retry.qa_score >= result.qa_score:
            retry.attempts = 2
            result = retry

    if primary:
        assets.mark_used(primary.id, datetime.now().astimezone().isoformat(timespec="seconds"))
    return result


def _render_and_check(
    spec: FlyerSpecification,
    client: Client,
    assets: AssetCatalog,
    base_dir: Path,
    slot: int,
    settings: Settings,
    attempt: int = 1,
) -> FlyerResult:
    asset_paths: dict[str, Path] = {}
    for asset_id in (spec.image.asset_id, spec.image.secondary_asset_id):
        if not asset_id:
            continue
        asset = assets.index.by_id(asset_id)
        if asset:
            asset_paths[asset_id] = settings.paths.root / asset.path

    context = resolve_render_context(client, asset_paths)

    try:
        image, warnings = render_flyer(spec, context)
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(f"Renderer crashed on {spec.id}: {exc}") from exc

    suffix = "png" if settings.output_format == "PNG" else "jpg"
    name = f"flyer-{slot:02d}" + ("" if attempt == 1 else f"-retry{attempt}")
    image_path = base_dir / f"{name}.{suffix}"
    export_flyer(image, image_path, settings.output_format)

    try:
        thumbnail(image_path, base_dir / "thumbs" / f"{name}.jpg")
    except Exception as exc:  # never fail a run over a preview
        log.debug("Thumbnail generation skipped: %s", exc)

    qa = qa_flyer(image_path, spec, client, warnings)
    vision = vision_qa(image_path, spec, client) if get_claude().enabled else None
    if vision:
        qa = qa.merge(vision)

    metadata_path = base_dir / f"{name}.json"
    result = FlyerResult(
        spec=spec,
        image_path=str(image_path),
        metadata_path=str(metadata_path),
        width=spec.canvas.width,
        height=spec.canvas.height,
        bytes=image_path.stat().st_size,
        qa_passed=qa.passed,
        qa_score=qa.score,
        attempts=attempt,
    )
    _write_metadata(metadata_path, result, qa)
    return result


def _write_metadata(path: Path, result: FlyerResult, qa: QAResult) -> None:
    payload = result.model_dump()
    payload["qa"] = qa.model_dump()
    import json

    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _upload(run: GenerationRun, client: Client, when: date, settings: Settings) -> None:
    from ..drive.auth import drive_available

    if not drive_available(settings):
        log.info("Google Drive not configured - flyers remain in output/")
        return

    from ..drive.uploader import DriveUploader, upload_flyer_result

    try:
        uploader = DriveUploader(settings)
    except Exception as exc:
        run.errors.append(f"drive auth failed: {exc}")
        log.error("Google Drive authentication failed: %s", exc)
        return

    for result in run.results:
        if not result.qa_passed:
            log.warning(
                "Not uploading %s - it failed QA (score %d)", result.spec.id, result.qa_score
            )
            continue
        try:
            upload_flyer_result(result, client, when, uploader)
        except Exception as exc:
            run.errors.append(f"drive upload failed for {result.spec.id}: {exc}")
            log.error("Drive upload failed for %s: %s", result.spec.id, exc)


def _write_run_summary(run: GenerationRun, base_dir: Path) -> Path:
    """Human-readable Markdown summary; also used as the Actions job summary."""
    lines = [
        f"# Flyer run `{run.run_id}`",
        "",
        f"- **Client:** {run.client_id}",
        f"- **Date:** {run.date}",
        f"- **Model:** {run.model}",
        f"- **Flyers:** {len(run.results)} generated, {run.succeeded} passed QA",
        "",
    ]
    if run.plan.get("strategy_note"):
        lines += [f"> {run.plan['strategy_note']}", ""]

    if run.results:
        lines += [
            "| # | Campaign | Layout | Headline | CTA | QA | Drive |",
            "|---|----------|--------|----------|-----|----|-------|",
        ]
        for index, result in enumerate(run.results, start=1):
            spec = result.spec
            drive = f"[open]({result.drive_url})" if result.drive_url else "-"
            status = "PASS" if result.qa_passed else "FAIL"
            lines.append(
                f"| {index} | `{spec.campaign_id}` | `{spec.layout.name}` | "
                f"{spec.text.headline} | {spec.text.cta} | {status} {result.qa_score} | {drive} |"
            )
        lines.append("")

    if run.errors:
        lines += ["## Errors", ""] + [f"- {e}" for e in run.errors] + [""]

    path = base_dir / "SUMMARY.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
