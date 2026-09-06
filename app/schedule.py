"""Should a run happen right now?

GitHub Actions cron is UTC-only and fires more often than we want, so the
workflow triggers generously and this module makes the real decision in the
business timezone.

Two modes:

``daily``     one run at ``SCHEDULE_TIME`` on ``SCHEDULE_DAYS``
``interval``  a run every ``SCHEDULE_INTERVAL_HOURS`` inside ``SCHEDULE_WINDOW``

Interval mode exists so a batch can be built up through the day. It does not
mean "post every three hours": see docs/SCHEDULING.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Settings, get_settings
from .logging_setup import get_logger

log = get_logger(__name__)

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass
class ScheduleDecision:
    should_run: bool
    reason: str
    local_time: str
    local_date: str
    mode: str

    def explain(self) -> str:
        return f"{self.local_time} ({self.mode}): {self.reason}"


def _parse_hhmm(value: str, fallback: tuple[int, int]) -> tuple[int, int]:
    try:
        hour, _, minute = value.strip().partition(":")
        return int(hour), int(minute)
    except ValueError:
        return fallback


def _active_days(spec: str) -> set[int]:
    """``mon-fri``, ``mon,wed,fri`` or ``all`` -> weekday indexes."""
    spec = spec.strip().lower()
    if spec in ("all", "daily", "everyday", "*"):
        return set(range(7))
    days: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, _, end = part.partition("-")
            if start in DAY_NAMES and end in DAY_NAMES:
                a, b = DAY_NAMES.index(start), DAY_NAMES.index(end)
                days.update(range(a, b + 1) if a <= b else [*range(a, 7), *range(0, b + 1)])
        elif part in DAY_NAMES:
            days.add(DAY_NAMES.index(part))
    return days or set(range(5))


def decide(
    now: datetime | None = None,
    tolerance_minutes: int = 40,
    settings: Settings | None = None,
) -> ScheduleDecision:
    """Is now a scheduled run time in the business timezone?"""
    settings = settings or get_settings()
    try:
        zone = ZoneInfo(settings.schedule_timezone)
    except Exception:
        log.warning("Unknown timezone %r; using system local", settings.schedule_timezone)
        zone = None

    now = now or (datetime.now(zone) if zone else datetime.now())
    stamp = now.strftime("%Y-%m-%d %H:%M %Z").strip()

    active = _active_days(settings.schedule_days)
    if now.weekday() not in active:
        return ScheduleDecision(
            False,
            f"{DAY_NAMES[now.weekday()]} is not in {settings.schedule_days}",
            stamp,
            now.date().isoformat(),
            settings.schedule_mode,
        )

    minutes_now = now.hour * 60 + now.minute

    if settings.schedule_mode == "interval":
        start_h, start_m = _parse_hhmm(settings.schedule_window.split("-")[0], (8, 0))
        end_part = settings.schedule_window.split("-")[-1]
        end_h, end_m = _parse_hhmm(end_part, (20, 0))
        start, end = start_h * 60 + start_m, end_h * 60 + end_m

        if not (start <= minutes_now <= end):
            return ScheduleDecision(
                False,
                f"outside the {settings.schedule_window} window",
                stamp,
                now.date().isoformat(),
                "interval",
            )

        step = max(settings.schedule_interval_hours, 1) * 60
        offset = minutes_now - start
        distance = min(offset % step, step - (offset % step))
        if distance <= tolerance_minutes:
            return ScheduleDecision(
                True,
                f"on a {settings.schedule_interval_hours}h slot inside {settings.schedule_window}",
                stamp,
                now.date().isoformat(),
                "interval",
            )
        return ScheduleDecision(
            False,
            f"{distance} min from the nearest {settings.schedule_interval_hours}h slot",
            stamp,
            now.date().isoformat(),
            "interval",
        )

    target_h, target_m = _parse_hhmm(settings.schedule_time, (10, 7))
    target = target_h * 60 + target_m
    delta = abs(minutes_now - target)
    if delta <= tolerance_minutes:
        return ScheduleDecision(
            True,
            f"within {tolerance_minutes} min of {settings.schedule_time}",
            stamp,
            now.date().isoformat(),
            "daily",
        )
    return ScheduleDecision(
        False,
        f"{delta} min from {settings.schedule_time}",
        stamp,
        now.date().isoformat(),
        "daily",
    )
