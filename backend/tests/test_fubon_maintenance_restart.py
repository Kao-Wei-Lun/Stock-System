from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from scheduler import (
    BackgroundScheduler,
    SchedulerDependencies,
    SchedulerSettings,
    fubon_maintenance_restart_loop,
    next_fubon_maintenance_window,
)


TAIPEI = ZoneInfo("Asia/Taipei")


class AdvancingClock:
    def __init__(self, current: datetime, *, cancel_at: datetime | None = None):
        self.current = current
        self.cancel_at = cancel_at

    def now(self) -> datetime:
        return self.current

    async def sleep(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)
        await asyncio.sleep(0)
        if self.cancel_at is not None and self.current >= self.cancel_at:
            raise asyncio.CancelledError


def test_maintenance_window_uses_same_day_before_0800_and_next_day_afterward():
    before = datetime(2026, 7, 27, 7, 30, tzinfo=TAIPEI)
    after = datetime(2026, 7, 27, 10, 0, tzinfo=TAIPEI)

    assert next_fubon_maintenance_window(
        before,
        app_tz=TAIPEI,
        maintenance_time=time(8, 0),
        weekdays_only=True,
    ) == datetime(2026, 7, 27, 8, 0, tzinfo=TAIPEI)
    assert next_fubon_maintenance_window(
        after,
        app_tz=TAIPEI,
        maintenance_time=time(8, 0),
        weekdays_only=True,
    ) == datetime(2026, 7, 28, 8, 0, tzinfo=TAIPEI)


def test_maintenance_window_skips_weekend():
    friday_after_window = datetime(2026, 7, 31, 10, 0, tzinfo=TAIPEI)

    assert next_fubon_maintenance_window(
        friday_after_window,
        app_tz=TAIPEI,
        maintenance_time=time(8, 0),
        weekdays_only=True,
    ) == datetime(2026, 8, 3, 8, 0, tzinfo=TAIPEI)


@pytest.mark.anyio
async def test_persistent_subscribed_channel_requests_restart_after_grace_at_window():
    clock = AdvancingClock(datetime(2026, 7, 27, 7, 55, tzinfo=TAIPEI))
    requested = []
    request_event = asyncio.Event()
    state = {}
    records = []

    def request_restart(**payload):
        requested.append(payload)
        request_event.set()
        return {"accepted": True}

    task = asyncio.create_task(
        fubon_maintenance_restart_loop(
            get_unhealthy_channels=lambda: [
                {
                    "market_type": "futopt",
                    "state": "disconnected",
                    "desired_subscription_count": 3,
                }
            ],
            request_service_restart=request_restart,
            app_tz=TAIPEI,
            maintenance_time=time(8, 0),
            unhealthy_grace_seconds=300,
            check_interval_seconds=60,
            weekdays_only=True,
            state=state,
            record_result=lambda name, **result: records.append((name, result)),
            now_provider=clock.now,
            sleep=clock.sleep,
        )
    )
    await asyncio.wait_for(request_event.wait(), timeout=1)

    assert requested == [
        {
            "reason_code": "fubon_ws_maintenance",
            "source": "scheduler",
        }
    ]
    assert state["state"] == "restart_requested"
    assert state["unhealthy_channel_count"] == 1
    assert state["market_types"] == ["futopt"]
    assert records[0][0] == "fubon-maintenance-restart"
    assert records[0][1]["success"] is True

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.anyio
async def test_recovery_before_window_clears_episode_and_does_not_restart():
    start = datetime(2026, 7, 27, 7, 55, tzinfo=TAIPEI)
    clock = AdvancingClock(
        start,
        cancel_at=datetime(2026, 7, 27, 8, 2, tzinfo=TAIPEI),
    )
    requested = []
    state = {}

    def get_unhealthy():
        if clock.current < datetime(2026, 7, 27, 7, 58, tzinfo=TAIPEI):
            return [{"market_type": "stock", "desired_subscription_count": 18}]
        return []

    with pytest.raises(asyncio.CancelledError):
        await fubon_maintenance_restart_loop(
            get_unhealthy_channels=get_unhealthy,
            request_service_restart=lambda **payload: requested.append(payload),
            app_tz=TAIPEI,
            maintenance_time=time(8, 0),
            unhealthy_grace_seconds=300,
            check_interval_seconds=60,
            weekdays_only=True,
            state=state,
            now_provider=clock.now,
            sleep=clock.sleep,
        )

    assert requested == []
    assert state["state"] == "monitoring"
    assert state["unhealthy_channel_count"] == 0
    assert state["unhealthy_since"] is None
    assert state["next_window"] is None


@pytest.mark.anyio
async def test_unhealthy_observation_failure_never_requests_restart():
    clock = AdvancingClock(
        datetime(2026, 7, 27, 7, 55, tzinfo=TAIPEI),
        cancel_at=datetime(2026, 7, 27, 8, 1, tzinfo=TAIPEI),
    )
    state = {}
    requested = []

    def fail_observation():
        raise RuntimeError("status unavailable")

    with pytest.raises(asyncio.CancelledError):
        await fubon_maintenance_restart_loop(
            get_unhealthy_channels=fail_observation,
            request_service_restart=lambda **payload: requested.append(payload),
            app_tz=TAIPEI,
            maintenance_time=time(8, 0),
            check_interval_seconds=60,
            state=state,
            now_provider=clock.now,
            sleep=clock.sleep,
        )

    assert requested == []
    assert state["state"] == "observation_error"
    assert state["last_error"] == "status unavailable"


@pytest.mark.anyio
async def test_background_scheduler_starts_maintenance_monitor_only_when_enabled():
    async def noop_async(*_args, **_kwargs):
        await asyncio.sleep(0)
        return {}

    scheduler = BackgroundScheduler(
        settings=SchedulerSettings(
            startup_download_enabled=False,
            institutional_auto_sync_enabled=False,
            taiwan_chip_auto_sync_enabled=False,
            latest_data_sync_on_startup=False,
            alert_evaluator_enabled=False,
            market_intelligence_sync_enabled=False,
            market_intelligence_startup_sync=False,
            alert_poll_interval_seconds=3600,
            app_tz=TAIPEI,
            daily_latest_sync_time=time(23, 59),
            fubon_maintenance_restart_enabled=True,
        ),
        dependencies=SchedulerDependencies(
            startup_download_tickers=[],
            fetch_history_for_ticker=noop_async,
            sync_institutional_snapshot=noop_async,
            sync_taiwan_chip_snapshot=noop_async,
            sync_tracked_market_data=noop_async,
            fetch_and_store_quote_snapshot=noop_async,
            evaluate_active_alerts=noop_async,
            sync_market_intelligence_snapshot=noop_async,
            get_subscribed_tickers=lambda: [],
            broadcast_to_ticker=noop_async,
            get_fubon_unhealthy_channels=lambda: [],
            request_service_restart=lambda **_kwargs: {},
        ),
    )

    scheduler.start()
    await asyncio.sleep(0)
    health = scheduler.health_summary()

    assert health["fubon_maintenance_restart"]["enabled"] is True
    assert any(
        task["name"] == "fubon-maintenance-restart"
        for task in health["tasks"]
    )

    await scheduler.shutdown()
