"""Run-time scheduling.

GitHub Actions cron is UTC-only and fires generously; this module makes the
real decision in the business timezone, so it is worth testing directly.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.config import reset_settings_cache
from app.schedule import _active_days, decide

NY = ZoneInfo("America/New_York")


def _at(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=NY)


@pytest.fixture()
def daily(repo, monkeypatch):
    monkeypatch.setenv("SCHEDULE_MODE", "daily")
    monkeypatch.setenv("SCHEDULE_TIME", "10:07")
    monkeypatch.setenv("SCHEDULE_DAYS", "mon-fri")
    reset_settings_cache()


@pytest.fixture()
def every_three_hours(repo, monkeypatch):
    monkeypatch.setenv("SCHEDULE_MODE", "interval")
    monkeypatch.setenv("SCHEDULE_INTERVAL_HOURS", "3")
    monkeypatch.setenv("SCHEDULE_WINDOW", "08:00-20:00")
    monkeypatch.setenv("SCHEDULE_DAYS", "mon-fri")
    reset_settings_cache()


# ------------------------------------------------------------------- day spec


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("mon-fri", {0, 1, 2, 3, 4}),
        ("all", set(range(7))),
        ("sat,sun", {5, 6}),
        ("mon,wed,fri", {0, 2, 4}),
        ("fri-mon", {4, 5, 6, 0}),
    ],
)
def test_day_specs(spec, expected):
    assert _active_days(spec) == expected


def test_an_unparseable_day_spec_falls_back_to_weekdays():
    assert _active_days("nonsense") == {0, 1, 2, 3, 4}


# ----------------------------------------------------------------- daily mode


def test_daily_runs_at_the_target_time(daily):
    # 2026-09-09 is a Wednesday.
    assert decide(_at(2026, 9, 9, 10, 7), tolerance_minutes=40).should_run


def test_daily_tolerates_a_late_runner(daily):
    """GitHub delays scheduled jobs under load; that must not skip the day."""
    assert decide(_at(2026, 9, 9, 10, 40), tolerance_minutes=40).should_run


def test_daily_rejects_the_wrong_utc_slot(daily):
    """The workflow fires twice for DST; only one slot is really 10:07."""
    assert not decide(_at(2026, 9, 9, 11, 7), tolerance_minutes=40).should_run


def test_daily_skips_the_weekend(daily):
    result = decide(_at(2026, 9, 12, 10, 7), tolerance_minutes=40)  # Saturday
    assert not result.should_run
    assert "sat" in result.reason


# -------------------------------------------------------------- interval mode


@pytest.mark.parametrize("hour", [8, 11, 14, 17, 20])
def test_interval_runs_on_each_slot(every_three_hours, hour):
    assert decide(_at(2026, 9, 9, hour, 0), tolerance_minutes=20).should_run


@pytest.mark.parametrize("hour", [9, 12, 15, 18])
def test_interval_skips_between_slots(every_three_hours, hour):
    assert not decide(_at(2026, 9, 9, hour, 30), tolerance_minutes=20).should_run


def test_interval_does_not_run_overnight(every_three_hours):
    """Nobody wants a flyer generated at 3am."""
    result = decide(_at(2026, 9, 9, 3, 0), tolerance_minutes=20)
    assert not result.should_run
    assert "window" in result.reason


def test_interval_respects_the_window_edges(every_three_hours):
    assert not decide(_at(2026, 9, 9, 7, 0), tolerance_minutes=20).should_run
    assert not decide(_at(2026, 9, 9, 21, 0), tolerance_minutes=20).should_run


def test_interval_still_honours_the_day_list(every_three_hours):
    assert not decide(_at(2026, 9, 13, 11, 0), tolerance_minutes=20).should_run  # Sunday


def test_interval_slot_count_matches_the_window(every_three_hours):
    """08:00-20:00 every 3h is five runs: 8, 11, 14, 17, 20."""
    runs = [
        h
        for h in range(24)
        if decide(_at(2026, 9, 9, h, 0), tolerance_minutes=20).should_run
    ]
    assert runs == [8, 11, 14, 17, 20]


def test_a_two_hour_interval_gives_more_slots(repo, monkeypatch):
    monkeypatch.setenv("SCHEDULE_MODE", "interval")
    monkeypatch.setenv("SCHEDULE_INTERVAL_HOURS", "2")
    monkeypatch.setenv("SCHEDULE_WINDOW", "08:00-20:00")
    monkeypatch.setenv("SCHEDULE_DAYS", "all")
    reset_settings_cache()
    runs = [
        h for h in range(24) if decide(_at(2026, 9, 9, h, 0), tolerance_minutes=15).should_run
    ]
    assert runs == [8, 10, 12, 14, 16, 18, 20]


# ------------------------------------------------------------------ resilience


def test_an_unknown_timezone_does_not_crash(repo, monkeypatch):
    monkeypatch.setenv("SCHEDULE_TIMEZONE", "Not/AZone")
    reset_settings_cache()
    assert decide() is not None


def test_a_malformed_time_falls_back(repo, monkeypatch):
    monkeypatch.setenv("SCHEDULE_MODE", "daily")
    monkeypatch.setenv("SCHEDULE_TIME", "not-a-time")
    monkeypatch.setenv("SCHEDULE_DAYS", "all")
    reset_settings_cache()
    assert decide(_at(2026, 9, 9, 10, 7), tolerance_minutes=40).should_run
