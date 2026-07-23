"""Bounded, non-sensitive operational metrics with restart-safe local history."""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from performance_timing import http_performance_metrics
from realtime_performance import realtime_performance_metrics


SCHEMA_VERSION = 1
_ALLOWED_RESOLUTIONS = {"auto", "raw", "downsampled"}


def _number(value: Any, default: float | int = 0) -> float | int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    return default


def _optional_number(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _state(value: Any, default: str = "unknown") -> str:
    normalized = str(value or default).strip().lower().replace(" ", "_")
    return normalized[:40] if normalized else default


def _utc(value: datetime | None = None) -> datetime:
    reference = value or datetime.now(timezone.utc)
    return reference.astimezone(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bucket_start(reference: datetime, minutes: int) -> datetime:
    minute = reference.minute - reference.minute % minutes
    return reference.replace(minute=minute, second=0, microsecond=0)


def _process_metrics() -> dict[str, int | None]:
    """Read only aggregate process usage; return nulls on unsupported platforms."""

    rss_bytes: int | None = None
    private_bytes: int | None = None
    handle_count: int | None = None
    if sys.platform == "win32":
        try:
            from ctypes import wintypes

            class ProcessMemoryCountersEx(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            counters = ProcessMemoryCountersEx()
            counters.cb = ctypes.sizeof(counters)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCountersEx),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            kernel32.GetProcessHandleCount.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.GetProcessHandleCount.restype = wintypes.BOOL
            process = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(
                process,
                ctypes.byref(counters),
                counters.cb,
            ):
                rss_bytes = int(counters.WorkingSetSize)
                private_bytes = int(counters.PrivateUsage)
            handles = wintypes.DWORD()
            if kernel32.GetProcessHandleCount(process, ctypes.byref(handles)):
                handle_count = int(handles.value)
        except (AttributeError, OSError, TypeError, ValueError):
            pass
    else:
        try:
            import resource

            maximum_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            rss_bytes = maximum_rss if sys.platform == "darwin" else maximum_rss * 1024
        except (ImportError, OSError, ValueError):
            pass
    return {
        "rss_bytes": rss_bytes,
        "private_bytes": private_bytes,
        "handle_count": handle_count,
    }


def build_operational_snapshot(
    *,
    database: Any = None,
    scheduler: Any = None,
    quote_persistence_buffer: Any = None,
    provider_pool: Any = None,
    quality_snapshot: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a strict allow-list snapshot; never serialize source payloads or account details."""

    reference = _utc(now)
    db_status = (
        database.get_performance_status()
        if database is not None and hasattr(database, "get_performance_status")
        else {}
    )
    pool = db_status.get("pool") or {}
    wait = db_status.get("wait") or {}
    query = db_status.get("query") or {}
    realtime = realtime_performance_metrics.snapshot()
    counters = realtime.get("counters") or {}
    broadcast = realtime.get("broadcast_latency") or {}
    queue_age = realtime.get("persistence_queue_age") or {}
    queue_depth = realtime.get("queue_depth") or {}
    persistence = (
        quote_persistence_buffer.status()
        if quote_persistence_buffer is not None and hasattr(quote_persistence_buffer, "status")
        else {}
    )
    scheduler_status = (
        scheduler.health_summary()
        if scheduler is not None and hasattr(scheduler, "health_summary")
        else {}
    )
    warmup = (
        provider_pool.get_warmup_status()
        if provider_pool is not None and hasattr(provider_pool, "get_warmup_status")
        else {}
    )
    quality = quality_snapshot or {}
    quality_components = quality.get("components") or {}
    fubon_quality = quality_components.get("fubon") or {}
    watchlist_quality = quality_components.get("watchlist") or {}
    futures_quality = quality_components.get("futures_recorder") or {}
    try:
        active_background_tasks = len([
            task for task in asyncio.all_tasks()
            if not task.done()
        ])
    except RuntimeError:
        active_background_tasks = 0

    provider_state = warmup.get("state") or fubon_quality.get("status") or (
        "connected" if bool(getattr(provider_pool, "connected", False)) else "disconnected"
    )
    provider_error_category = "none"
    if warmup.get("last_error_category"):
        provider_error_category = warmup["last_error_category"]
    elif fubon_quality.get("error"):
        provider_error_category = "status_check"
    elif _state(provider_state) in {"failed", "error", "disconnected"}:
        provider_error_category = "connection"

    return {
        "timestamp": reference.isoformat(),
        "api": {
            **http_performance_metrics.snapshot(),
        },
        "database": {
            "configured": bool(db_status.get("configured")),
            "pool_size": int(_number(pool.get("size"))),
            "pool_free": int(_number(pool.get("free"))),
            "pool_max": int(_number(pool.get("maxsize"))),
            "wait_p50_ms": _optional_number(wait.get("p50_ms")),
            "wait_p95_ms": _optional_number(wait.get("p95_ms")),
            "wait_max_ms": _optional_number(wait.get("max_ms")),
            "query_p50_ms": _optional_number(query.get("p50_ms")),
            "query_p95_ms": _optional_number(query.get("p95_ms")),
            "query_max_ms": _optional_number(query.get("max_ms")),
        },
        "realtime": {
            "ingress_count": int(_number(counters.get("ingress"))),
            "broadcast_count": int(_number(counters.get("broadcast"))),
            "dropped_count": int(_number(counters.get("dropped"))),
            "broadcast_p95_ms": _optional_number(broadcast.get("p95_ms")),
            "broadcast_max_ms": _optional_number(broadcast.get("max_ms")),
            "queue_age_p95_ms": _optional_number(queue_age.get("p95_ms")),
            "queue_age_max_ms": _optional_number(queue_age.get("max_ms")),
            "queue_depth_max": _optional_number(queue_depth.get("max_ms")),
        },
        "persistence": {
            "running": bool(persistence.get("running")),
            "pending": int(_number(persistence.get("pending"))),
            "capacity": int(_number(persistence.get("capacity"))),
            "persisted_count": int(_number(persistence.get("persisted"))),
            "failure_count": int(_number(persistence.get("failures"))),
            "error_category": "persistence" if persistence.get("last_error") else "none",
        },
        "provider": {
            "state": _state(provider_state),
            "connected": bool(
                fubon_quality.get("connected", getattr(provider_pool, "connected", False))
            ),
            "configured_account_count": int(_number(
                warmup.get("configured_account_count", fubon_quality.get("account_count"))
            )),
            "connected_account_count": int(_number(
                warmup.get("connected_account_count", fubon_quality.get("connected_account_count"))
            )),
            "reconnect_attempts": int(_number(fubon_quality.get("reconnect_attempts"))),
            "error_category": _state(provider_error_category, "none"),
        },
        "freshness": {
            "stale_ticker_count": int(_number(watchlist_quality.get("stale_count"))),
            "stale_futures_count": int(_number(futures_quality.get("stale_symbol_count"))),
        },
        "scheduler": {
            "running": bool(scheduler_status.get("running")),
            "task_count": int(_number(scheduler_status.get("task_count"))),
            "active_count": int(_number(scheduler_status.get("active_count"))),
            "failed_count": int(_number(scheduler_status.get("failed_count"))),
            "unexpected_stopped_count": int(_number(
                scheduler_status.get("unexpected_stopped_count")
            )),
        },
        "process": _process_metrics(),
        "background": {
            "active_task_count": active_background_tasks,
        },
        "health": {
            "status": _state(quality.get("status"), "unknown"),
            "warning_count": int(_number((quality.get("summary") or {}).get("warning_count"))),
            "error_count": int(_number((quality.get("summary") or {}).get("error_count"))),
            "last_success_at": (
                quality.get("generated_at")
                if quality and not (quality.get("summary") or {}).get("error_count")
                else None
            ),
        },
    }


def _valid_snapshot(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and _parse_timestamp(item.get("timestamp")) is not None
        and isinstance(item.get("database"), dict)
        and isinstance(item.get("realtime"), dict)
        and isinstance(item.get("health"), dict)
    )


class OperationalMetricStore:
    """Atomic JSON store with minute and 15-minute bounded series."""

    def __init__(
        self,
        path: Path,
        *,
        raw_retention_hours: int = 24,
        downsample_retention_days: int = 30,
    ) -> None:
        self.path = Path(path)
        self.raw_retention = timedelta(hours=max(1, int(raw_retention_hours)))
        self.downsample_retention = timedelta(days=max(1, int(downsample_retention_days)))
        self._lock = Lock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        empty = {"schema_version": SCHEMA_VERSION, "raw": [], "downsampled": []}
        if not self.path.is_file():
            return empty
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return empty
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
            return empty
        return {
            "schema_version": SCHEMA_VERSION,
            "raw": [item for item in payload.get("raw", []) if _valid_snapshot(item)],
            "downsampled": [
                item for item in payload.get("downsampled", []) if _valid_snapshot(item)
            ],
        }

    @staticmethod
    def _upsert(items: list[dict[str, Any]], snapshot: dict[str, Any], minutes: int) -> None:
        reference = _parse_timestamp(snapshot["timestamp"])
        if reference is None:
            return
        bucket = _bucket_start(reference, minutes)
        normalized = {**snapshot, "timestamp": bucket.isoformat()}
        for index in range(len(items) - 1, -1, -1):
            item_time = _parse_timestamp(items[index].get("timestamp"))
            if item_time is not None and _bucket_start(item_time, minutes) == bucket:
                items[index] = normalized
                return
        items.append(normalized)
        items.sort(key=lambda item: item["timestamp"])

    def _prune(self, reference: datetime) -> None:
        raw_cutoff = reference - self.raw_retention
        downsample_cutoff = reference - self.downsample_retention
        self._data["raw"] = [
            item for item in self._data["raw"]
            if (_parse_timestamp(item.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
            >= raw_cutoff
        ]
        self._data["downsampled"] = [
            item for item in self._data["downsampled"]
            if (_parse_timestamp(item.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
            >= downsample_cutoff
        ]

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def record(self, snapshot: dict[str, Any]) -> None:
        if not _valid_snapshot(snapshot):
            raise ValueError("Invalid operational metric snapshot")
        reference = _parse_timestamp(snapshot["timestamp"]) or _utc()
        with self._lock:
            self._upsert(self._data["raw"], snapshot, 1)
            self._upsert(self._data["downsampled"], snapshot, 15)
            self._prune(reference)
            self._write()

    def history(
        self,
        *,
        hours: int = 24,
        resolution: str = "auto",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_resolution = str(resolution or "auto").strip().lower()
        if normalized_resolution not in _ALLOWED_RESOLUTIONS:
            raise ValueError("resolution must be auto, raw, or downsampled")
        bounded_hours = max(1, min(int(hours), int(self.downsample_retention.total_seconds() // 3600)))
        selected = (
            "raw"
            if normalized_resolution == "raw"
            or (normalized_resolution == "auto" and bounded_hours <= 24)
            else "downsampled"
        )
        cutoff = _utc(now) - timedelta(hours=bounded_hours)
        with self._lock:
            points = [
                dict(item) for item in self._data[selected]
                if (_parse_timestamp(item.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
                >= cutoff
            ]
            last_updated_at = None
            all_points = self._data["raw"] or self._data["downsampled"]
            if all_points:
                last_updated_at = all_points[-1].get("timestamp")
        return {
            "schema_version": SCHEMA_VERSION,
            "resolution": selected,
            "bucket_minutes": 1 if selected == "raw" else 15,
            "hours": bounded_hours,
            "point_count": len(points),
            "last_updated_at": last_updated_at,
            "points": points,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "configured": True,
                "raw_point_count": len(self._data["raw"]),
                "downsampled_point_count": len(self._data["downsampled"]),
                "last_updated_at": (
                    self._data["raw"][-1]["timestamp"] if self._data["raw"] else None
                ),
                "raw_retention_hours": int(self.raw_retention.total_seconds() // 3600),
                "downsample_retention_days": self.downsample_retention.days,
            }


class OperationalMetricsService:
    """Collect lightweight metrics every minute and refresh data quality less often."""

    def __init__(
        self,
        store: OperationalMetricStore,
        *,
        database: Any = None,
        scheduler: Any = None,
        quote_persistence_buffer: Any = None,
        provider_pool: Any = None,
        data_quality_service: Any = None,
        interval_seconds: float = 60,
        quality_interval_seconds: float = 300,
        startup_delay_seconds: float = 15,
        logger: logging.Logger | None = None,
    ) -> None:
        self.store = store
        self.database = database
        self.scheduler = scheduler
        self.quote_persistence_buffer = quote_persistence_buffer
        self.provider_pool = provider_pool
        self.data_quality_service = data_quality_service
        self.interval_seconds = max(5.0, float(interval_seconds))
        self.quality_interval_seconds = max(self.interval_seconds, float(quality_interval_seconds))
        self.startup_delay_seconds = max(0.0, float(startup_delay_seconds))
        self._log = logger or logging.getLogger(__name__)
        self._task: asyncio.Task | None = None
        self._last_quality: dict[str, Any] | None = None
        self._last_quality_at: datetime | None = None
        self._last_error_category: str | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="quantvision:operational-metrics")

    async def shutdown(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def collect_once(self, *, now: datetime | None = None, refresh_quality: bool = False) -> dict[str, Any]:
        reference = _utc(now)
        quality_due = (
            refresh_quality
            or self._last_quality_at is None
            or reference - self._last_quality_at >= timedelta(seconds=self.quality_interval_seconds)
        )
        if quality_due and self.data_quality_service is not None:
            try:
                self._last_quality = await self.data_quality_service.build_snapshot(now=reference)
                self._last_quality_at = reference
                self._last_error_category = None
            except Exception:
                self._last_error_category = "quality_collection"
                self._log.warning("Operational quality collection failed", exc_info=True)
        snapshot = build_operational_snapshot(
            database=self.database,
            scheduler=self.scheduler,
            quote_persistence_buffer=self.quote_persistence_buffer,
            provider_pool=self.provider_pool,
            quality_snapshot=self._last_quality,
            now=reference,
        )
        try:
            await asyncio.to_thread(self.store.record, snapshot)
            self._last_error_category = None
        except Exception:
            self._last_error_category = "history_persistence"
            self._log.warning("Operational metric persistence failed", exc_info=True)
        return snapshot

    def history(self, *, hours: int = 24, resolution: str = "auto") -> dict[str, Any]:
        return self.store.history(hours=hours, resolution=resolution)

    def status(self) -> dict[str, Any]:
        return {
            **self.store.status(),
            "running": bool(self._task and not self._task.done()),
            "last_error_category": self._last_error_category,
        }

    async def _run(self) -> None:
        if self.startup_delay_seconds:
            await asyncio.sleep(self.startup_delay_seconds)
        while True:
            try:
                await self.collect_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._last_error_category = "collection"
                self._log.warning("Operational metric collection failed", exc_info=True)
            await asyncio.sleep(self.interval_seconds)
