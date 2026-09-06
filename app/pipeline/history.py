"""Generation history.

History drives variety: the planner reads it to avoid repeating a campaign, the
copywriter reads it to avoid rewording a recent headline, and the selectors read
it to avoid reusing the same photo two days running.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from ..config import get_settings
from ..logging_setup import get_logger
from ..models import GenerationRun

log = get_logger(__name__)

MAX_ENTRIES = 400


def _index_path() -> Path:
    return get_settings().paths.history_index


def load_history() -> list[dict]:
    """Flat, newest-first list of per-flyer history entries."""
    path = _index_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warning("History index is corrupt (%s); starting fresh", exc)
        return []
    entries = data.get("entries", []) if isinstance(data, dict) else data
    return entries if isinstance(entries, list) else []


def save_history(entries: list[dict]) -> Path:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "entries": entries[:MAX_ENTRIES],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def for_client(client_id: str, limit: int = 40) -> list[dict]:
    return [e for e in load_history() if e.get("client") == client_id][:limit]


def recent_within(client_id: str, days: int) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    out = []
    for entry in for_client(client_id, limit=200):
        try:
            when = date.fromisoformat(entry.get("date", ""))
        except ValueError:
            continue
        if when >= cutoff:
            out.append(entry)
    return out


def recent_headlines(client_id: str, limit: int = 20) -> list[str]:
    return [e["headline"] for e in for_client(client_id, 200) if e.get("headline")][:limit]


def recent_asset_ids(client_id: str, limit: int = 12) -> list[str]:
    seen: list[str] = []
    for entry in for_client(client_id, 200):
        for asset_id in entry.get("asset_ids", []) or []:
            if asset_id and asset_id not in seen:
                seen.append(asset_id)
        if len(seen) >= limit:
            break
    return seen[:limit]


def recent_reference_ids(client_id: str, limit: int = 12) -> list[str]:
    seen: list[str] = []
    for entry in for_client(client_id, 200):
        for ref_id in entry.get("reference_ids", []) or []:
            if ref_id and ref_id not in seen:
                seen.append(ref_id)
        if len(seen) >= limit:
            break
    return seen[:limit]


def record_run(run: GenerationRun) -> Path:
    """Append one entry per flyer and persist the full run document."""
    entries = load_history()
    for result in run.results:
        entries.insert(
            0,
            {
                "run_id": run.run_id,
                "flyer_id": result.spec.id,
                "date": run.date,
                "client": run.client_id,
                "campaign": result.spec.campaign_id,
                "service": result.spec.service,
                "layout": result.spec.layout.name,
                "style": result.spec.style,
                "headline": result.spec.text.headline,
                "cta": result.spec.text.cta,
                "reference_ids": result.spec.reference_ids,
                "asset_ids": [
                    a
                    for a in (result.spec.image.asset_id, result.spec.image.secondary_asset_id)
                    if a
                ],
                "tools_used": result.spec.tool_decision.get("tools_used", []),
                "renderer": run.renderer,
                "qa_passed": result.qa_passed,
                "qa_score": result.qa_score,
                "drive_file_id": result.drive_file_id,
                "status": "generated",
                "approved": result.approved,
            },
        )
    save_history(entries)

    run_path = get_settings().paths.history_dir / f"{run.run_id}.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    log.info("Recorded run %s (%d flyer(s))", run.run_id, len(run.results))
    return run_path


def set_outcome(flyer_id: str, approved: bool, reasons: list[str] | None = None) -> bool:
    """Record a human approve/reject decision. Returns True when found."""
    entries = load_history()
    updated = False
    for entry in entries:
        if entry.get("flyer_id") == flyer_id:
            entry["approved"] = approved
            entry["status"] = "approved" if approved else "rejected"
            if reasons:
                entry["rejection_reasons"] = reasons
            updated = True
    if updated:
        save_history(entries)
    return updated


def find_entry(flyer_id: str) -> dict | None:
    return next((e for e in load_history() if e.get("flyer_id") == flyer_id), None)
