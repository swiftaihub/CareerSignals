from __future__ import annotations

from types import SimpleNamespace

from apps.scheduler import main as scheduler_main


def test_global_refresh_scheduler_uses_eastern_three_times_daily(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler_main,
        "get_settings",
        lambda: SimpleNamespace(
            connector_refresh_trigger_mode="scheduled",
            connector_refresh_cron="0 7,16,21 * * *",
            connector_refresh_timezone="America/New_York",
        ),
    )

    scheduler = scheduler_main.build_scheduler()
    job = scheduler.get_job("global-connector-refresh")

    assert job is not None
    assert str(job.trigger.timezone) == "America/New_York"
    assert str(job.trigger.fields[5]) == "7,16,21"
