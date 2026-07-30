"""Safe local uvicorn supervisor used by the Windows production launcher."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / ".runtime"
PREFLIGHT_FREE = "free"
PREFLIGHT_EXPECTED = "expected"
PREFLIGHT_COLLISION = "collision"
RESTART_REASON_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class SupervisorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SupervisorSettings:
    python_path: Path
    working_directory: Path
    host: str = "127.0.0.1"
    port: int = 8001
    max_crashes: int = 5
    crash_window_seconds: float = 300
    stable_runtime_seconds: float = 300
    initial_backoff_seconds: float = 1
    max_backoff_seconds: float = 30
    health_check_enabled: bool = True
    health_startup_grace_seconds: float = 120
    health_check_interval_seconds: float = 10
    health_timeout_seconds: float = 3
    health_failure_threshold: int = 3


def probe_ready_endpoint(host: str, port: int, timeout_seconds: float) -> tuple[bool, str]:
    """Probe readiness without returning response bodies or network details."""
    normalized_host = str(host).strip()
    probe_host = (
        "127.0.0.1"
        if normalized_host in {"", "0.0.0.0", "::"}
        else normalized_host
    )
    url_host = (
        f"[{probe_host}]"
        if ":" in probe_host and not probe_host.startswith("[")
        else probe_host
    )
    url = f"http://{url_host}:{int(port)}/api/ready"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=max(0.1, float(timeout_seconds))) as response:
            if int(getattr(response, "status", 0) or 0) != 200:
                return False, "http_status"
            payload = json.loads(response.read(65_536).decode("utf-8"))
    except urllib.error.HTTPError:
        return False, "http_status"
    except (TimeoutError, urllib.error.URLError, OSError):
        return False, "connection_error"
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return False, "invalid_response"
    if not isinstance(payload, dict) or payload.get("ready") is not True:
        return False, "not_ready"
    return True, "ready"


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def request_supervised_restart(
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    *,
    reason_code: str,
    source: str = "scheduler",
) -> dict[str, Any]:
    """Request a local supervised recycle without exposing runtime secrets."""
    normalized_reason = str(reason_code or "").strip().lower()
    normalized_source = str(source or "").strip().lower()
    if not RESTART_REASON_PATTERN.fullmatch(normalized_reason):
        raise ValueError("reason_code must contain only lowercase letters, digits, hyphens, or underscores")
    if not RESTART_REASON_PATTERN.fullmatch(normalized_source):
        raise ValueError("source must contain only lowercase letters, digits, hyphens, or underscores")
    payload = {
        "schema_version": 1,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "reason_code": normalized_reason,
        "source": normalized_source,
    }
    _atomic_json_write(Path(runtime_dir) / "backend-service.restart", payload)
    return payload


def find_listening_pid(port: int) -> int | None:
    """Return the Windows listening PID without changing process state."""

    if sys.platform != "win32":
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.1)
            return -1 if probe.connect_ex(("127.0.0.1", int(port))) == 0 else None
    result = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    port_pattern = re.compile(rf":{int(port)}$")
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 5 or columns[0].upper() != "TCP":
            continue
        if columns[-2].upper() != "LISTENING" or not port_pattern.search(columns[1]):
            continue
        try:
            return int(columns[-1])
        except ValueError:
            continue
    return None


def read_process_command_line(pid: int) -> str:
    if sys.platform != "win32" or pid <= 0:
        return ""
    command = (
        f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\" "
        "-ErrorAction SilentlyContinue; if($p){$p.CommandLine}"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    return result.stdout.strip()


def read_process_parent_pid(pid: int) -> int | None:
    """Return a Windows process parent PID for managed descendant checks."""
    if sys.platform != "win32" or pid <= 0:
        return None
    command = (
        f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\" "
        "-ErrorAction SilentlyContinue; if($p){$p.ParentProcessId}"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    try:
        parent_pid = int(result.stdout.strip())
    except ValueError:
        return None
    return parent_pid if parent_pid > 0 else None


class LocalServiceSupervisor:
    def __init__(
        self,
        settings: SupervisorSettings,
        *,
        runtime_dir: Path = DEFAULT_RUNTIME_DIR,
        port_probe: Callable[[int], int | None] = find_listening_pid,
        command_line_probe: Callable[[int], str] = read_process_command_line,
        parent_pid_probe: Callable[[int], int | None] = read_process_parent_pid,
        health_probe: Callable[[str, int, float], tuple[bool, str]] = probe_ready_endpoint,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.runtime_dir = Path(runtime_dir)
        self.state_path = self.runtime_dir / "backend-service.json"
        self.stop_marker = self.runtime_dir / "backend-service.stop"
        self.restart_marker = self.runtime_dir / "backend-service.restart"
        self.last_restart_path = self.runtime_dir / "backend-service-last-restart.json"
        self.last_health_recycle_path = (
            self.runtime_dir / "backend-service-last-health-recycle.json"
        )
        self.breaker_path = self.runtime_dir / "backend-service-breaker.json"
        self._port_probe = port_probe
        self._command_line_probe = command_line_probe
        self._parent_pid_probe = parent_pid_probe
        self._health_probe = health_probe
        self._popen_factory = popen_factory
        self._clock = clock
        self._sleep = sleep

    def _command_matches_expected_process(self, pid: int) -> bool:
        command_line = self._command_line_probe(pid).lower()
        expected_python = str(self.settings.python_path.resolve()).lower()
        return (
            expected_python in command_line
            and "uvicorn" in command_line
            and "main:app" in command_line
            and f"--port {self.settings.port}" in command_line
        )

    def _is_managed_process(self, pid: int) -> bool:
        state = _read_json(self.state_path)
        launcher_pid = int(state.get("process_pid") or 0)
        if launcher_pid <= 0:
            return False
        if int(state.get("port") or 0) != self.settings.port:
            return False
        if int(pid) != launcher_pid and not self._is_descendant_of(pid, launcher_pid):
            return False
        return self._command_matches_expected_process(pid)

    def _is_descendant_of(self, pid: int, ancestor_pid: int) -> bool:
        """Follow a bounded parent chain to handle the Windows venv launcher."""
        current_pid = int(pid)
        target_pid = int(ancestor_pid)
        visited: set[int] = set()
        for _ in range(16):
            if current_pid <= 0 or current_pid in visited:
                return False
            visited.add(current_pid)
            parent_pid = self._parent_pid_probe(current_pid)
            if parent_pid is None:
                return False
            if int(parent_pid) == target_pid:
                return True
            current_pid = int(parent_pid)
        return False

    def _is_expected_process(self, pid: int) -> bool:
        # The command signature allows a one-time handover from the pre-supervisor
        # launcher, but still binds confirmation to this project's exact venv.
        return self._is_managed_process(pid) or self._command_matches_expected_process(pid)

    def preflight(self) -> dict[str, Any]:
        pid = self._port_probe(self.settings.port)
        if pid is None:
            return {"status": PREFLIGHT_FREE, "port": self.settings.port}
        if pid > 0 and self._is_expected_process(pid):
            return {
                "status": PREFLIGHT_EXPECTED,
                "port": self.settings.port,
                "process_pid": pid,
                "managed": self._is_managed_process(pid),
            }
        return {
            "status": PREFLIGHT_COLLISION,
            "port": self.settings.port,
            "process_pid": pid if pid and pid > 0 else None,
        }

    def _command(self) -> list[str]:
        return [
            str(self.settings.python_path),
            "-X",
            "utf8",
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            self.settings.host,
            "--port",
            str(self.settings.port),
            "--no-use-colors",
        ]

    def _write_running_state(self, process_pid: int, restart_count: int) -> None:
        _atomic_json_write(
            self.state_path,
            {
                "schema_version": 1,
                "status": "running",
                "service": "quantvision-backend",
                "signature": "uvicorn main:app",
                "port": self.settings.port,
                "supervisor_pid": os.getpid(),
                "process_pid": int(process_pid),
                "restart_count": int(restart_count),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "health": {
                    "enabled": bool(self.settings.health_check_enabled),
                    "status": "startup_grace" if self.settings.health_check_enabled else "disabled",
                    "last_checked_at": None,
                    "consecutive_failures": 0,
                    "last_reason_code": None,
                },
            },
        )

    def _write_health_state(
        self,
        process_pid: int,
        *,
        healthy: bool,
        reason_code: str,
        consecutive_failures: int,
    ) -> None:
        state = _read_json(self.state_path)
        if int(state.get("process_pid") or 0) != int(process_pid):
            return
        state["health"] = {
            "enabled": True,
            "status": "healthy" if healthy else "unhealthy",
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": max(0, int(consecutive_failures)),
            "last_reason_code": str(reason_code or "unknown")[:64],
        }
        _atomic_json_write(self.state_path, state)

    def _clear_state_for(self, process_pid: int) -> None:
        state = _read_json(self.state_path)
        if int(state.get("process_pid") or 0) != int(process_pid):
            return
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            pass

    def _planned_stop_requested(self) -> bool:
        return self.stop_marker.is_file()

    def _read_restart_request(self) -> dict[str, Any] | None:
        if not self.restart_marker.is_file():
            return None
        payload = _read_json(self.restart_marker)
        reason_code = str(payload.get("reason_code") or "")
        source = str(payload.get("source") or "")
        if (
            int(payload.get("schema_version") or 0) != 1
            or not RESTART_REASON_PATTERN.fullmatch(reason_code)
            or not RESTART_REASON_PATTERN.fullmatch(source)
        ):
            try:
                self.restart_marker.unlink()
            except FileNotFoundError:
                pass
            return None
        return {
            "schema_version": 1,
            "requested_at": payload.get("requested_at"),
            "reason_code": reason_code,
            "source": source,
        }

    def _clear_restart_marker(self) -> None:
        try:
            self.restart_marker.unlink()
        except FileNotFoundError:
            pass

    def _wait_for_child(self, process: Any) -> tuple[int, str, dict[str, Any] | None]:
        health_enabled = bool(self.settings.health_check_enabled)
        next_health_check = (
            self._clock() + max(0.0, self.settings.health_startup_grace_seconds)
        )
        consecutive_health_failures = 0
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                return int(exit_code), "exited", None
            if self._planned_stop_requested():
                self._terminate_started_process(process)
                return 0, "stop", None
            restart_request = self._read_restart_request()
            if restart_request is not None:
                self._terminate_started_process(process)
                self._clear_restart_marker()
                return 0, "restart", restart_request

            now = self._clock()
            if health_enabled and now >= next_health_check:
                healthy, reason_code = self._health_probe(
                    self.settings.host,
                    self.settings.port,
                    self.settings.health_timeout_seconds,
                )
                consecutive_health_failures = (
                    0 if healthy else consecutive_health_failures + 1
                )
                self._write_health_state(
                    process.pid,
                    healthy=healthy,
                    reason_code=reason_code,
                    consecutive_failures=consecutive_health_failures,
                )
                next_health_check = (
                    now + max(0.5, self.settings.health_check_interval_seconds)
                )
                if (
                    not healthy
                    and consecutive_health_failures
                    >= max(1, self.settings.health_failure_threshold)
                ):
                    event = {
                        "schema_version": 1,
                        "status": "recycled",
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "reason_code": str(reason_code or "unknown")[:64],
                        "consecutive_failures": consecutive_health_failures,
                    }
                    _atomic_json_write(self.last_health_recycle_path, event)
                    print(
                        "[WARNING] Backend readiness remained unhealthy; "
                        f"recycling managed process reason={event['reason_code']} "
                        f"failures={consecutive_health_failures}."
                    )
                    self._terminate_started_process(process)
                    return 1, "unhealthy", event
            self._sleep(0.5)

    def _wait_backoff(self, delay_seconds: float) -> bool:
        deadline = self._clock() + max(0.0, delay_seconds)
        while self._clock() < deadline:
            if self._planned_stop_requested():
                return False
            self._sleep(min(0.1, max(0.0, deadline - self._clock())))
        return not self._planned_stop_requested()

    def run(self) -> int:
        preflight = self.preflight()
        if preflight["status"] == PREFLIGHT_EXPECTED:
            print(f"[INFO] QuantVision backend is already running on port {self.settings.port}.")
            return 0
        if preflight["status"] == PREFLIGHT_COLLISION:
            raise SupervisorError(
                f"Port {self.settings.port} is occupied by an unconfirmed process; no process was stopped."
            )
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        for marker in (self.stop_marker, self.restart_marker, self.breaker_path):
            try:
                marker.unlink()
            except FileNotFoundError:
                pass

        crash_times: deque[float] = deque()
        restart_count = 0
        pending_restart_result: dict[str, Any] | None = None
        while True:
            if self._planned_stop_requested():
                return 0
            process = self._popen_factory(
                self._command(),
                cwd=str(self.settings.working_directory),
                shell=False,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
            )
            self._write_running_state(process.pid, restart_count)
            if pending_restart_result is not None:
                _atomic_json_write(
                    self.last_restart_path,
                    {
                        "schema_version": 1,
                        "status": "completed",
                        "requested_at": pending_restart_result.get("requested_at"),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "reason_code": pending_restart_result["reason_code"],
                        "source": pending_restart_result["source"],
                    },
                )
                print(
                    "[INFO] Planned backend restart completed "
                    f"reason={pending_restart_result['reason_code']} "
                    f"source={pending_restart_result['source']}."
                )
                pending_restart_result = None
            started_at = self._clock()
            exit_reason = "exited"
            restart_request = None
            try:
                exit_code, exit_reason, restart_request = self._wait_for_child(process)
            except KeyboardInterrupt:
                self.stop_marker.write_text("planned\n", encoding="utf-8")
                self._terminate_started_process(process)
                exit_code = 0
                exit_reason = "stop"
            finally:
                self._clear_state_for(process.pid)

            runtime = max(0.0, self._clock() - started_at)
            if exit_reason == "restart" and restart_request is not None:
                pending_restart_result = restart_request
                restart_count = 0
                continue
            if self._planned_stop_requested() or exit_reason == "stop" or exit_code == 0:
                self._clear_restart_marker()
                try:
                    self.stop_marker.unlink()
                except FileNotFoundError:
                    pass
                return 0
            if runtime >= self.settings.stable_runtime_seconds:
                crash_times.clear()

            now = self._clock()
            crash_times.append(now)
            while crash_times and now - crash_times[0] > self.settings.crash_window_seconds:
                crash_times.popleft()
            if len(crash_times) >= self.settings.max_crashes:
                _atomic_json_write(
                    self.breaker_path,
                    {
                        "schema_version": 1,
                        "status": "restart_breaker_open",
                        "service": "quantvision-backend",
                        "port": self.settings.port,
                        "crash_count": len(crash_times),
                        "opened_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                print(
                    f"[ERROR] Backend crashed {len(crash_times)} times; restart breaker is open."
                )
                return 70

            delay = min(
                self.settings.max_backoff_seconds,
                self.settings.initial_backoff_seconds * (2 ** restart_count),
            )
            restart_count += 1
            print(
                f"[WARNING] Backend exited with code {exit_code}; "
                f"retrying in {delay:g} seconds ({restart_count}/{self.settings.max_crashes})."
            )
            if not self._wait_backoff(delay):
                return 0

    def _terminate_started_process(self, process: Any) -> None:
        try:
            if sys.platform == "win32":
                os.kill(int(process.pid), signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            process.wait(timeout=10)
            if sys.platform != "win32" or self._port_probe(self.settings.port) is None:
                return
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            pass
        if sys.platform == "win32":
            # A Windows venv python.exe can be a launcher whose child owns the
            # listening socket. Terminate the confirmed launcher's whole tree
            # so a planned recycle cannot leave an orphaned uvicorn process.
            try:
                target_pid = int(process.pid)
                listening_pid = self._port_probe(self.settings.port)
                if (
                    listening_pid is not None
                    and listening_pid > 0
                    and self._is_expected_process(listening_pid)
                ):
                    target_pid = int(listening_pid)
                subprocess.run(
                    ["taskkill", "/PID", str(target_pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    timeout=15,
                )
                process.wait(timeout=5)
                return
            except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
                pass
        try:
            process.kill()
            process.wait(timeout=5)
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            pass

    def request_stop(self) -> dict[str, Any]:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._clear_restart_marker()
        pid = self._port_probe(self.settings.port)
        if pid is None:
            try:
                self.stop_marker.unlink()
            except FileNotFoundError:
                pass
            return {"status": "already_stopped", "port": self.settings.port}
        if pid <= 0 or not self._is_expected_process(pid):
            raise SupervisorError(
                f"Port {self.settings.port} is occupied by an unconfirmed process; no process was stopped."
            )
        # Confirm ownership before publishing the marker. The supervisor may
        # consume it immediately, so checking identity afterward can race with
        # a successful shutdown and incorrectly report an unconfirmed process.
        self.stop_marker.write_text("planned\n", encoding="utf-8")
        if sys.platform == "win32":
            # Give the running supervisor first chance to perform its graceful
            # tree shutdown. This avoids racing its marker polling loop.
            deadline = self._clock() + 15
            while self._clock() < deadline:
                if self._port_probe(self.settings.port) is None:
                    return {
                        "status": "stop_requested",
                        "port": self.settings.port,
                        "process_pid": pid,
                    }
                self._sleep(0.25)
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=15,
            )
            if result.returncode != 0 and self._port_probe(self.settings.port) is not None:
                raise SupervisorError("Confirmed backend did not accept the planned stop request.")
        else:
            os.kill(pid, signal.SIGTERM)
        return {"status": "stop_requested", "port": self.settings.port, "process_pid": pid}

    def status(self) -> dict[str, Any]:
        preflight = self.preflight()
        return {
            **preflight,
            "state": _read_json(self.state_path),
            "restart_breaker": _read_json(self.breaker_path),
            "planned_stop_pending": self._planned_stop_requested(),
            "planned_restart_pending": self._read_restart_request() is not None,
            "last_planned_restart": _read_json(self.last_restart_path),
            "last_health_recycle": _read_json(self.last_health_recycle_path),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run", "stop", "status"))
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--working-directory", type=Path, default=PROJECT_ROOT / "backend")
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--max-crashes", type=int, default=5)
    parser.add_argument(
        "--health-check",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--health-startup-grace", type=float, default=120)
    parser.add_argument("--health-check-interval", type=float, default=10)
    parser.add_argument("--health-timeout", type=float, default=3)
    parser.add_argument("--health-failure-threshold", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    supervisor = LocalServiceSupervisor(
        SupervisorSettings(
            python_path=args.python.resolve(),
            working_directory=args.working_directory.resolve(),
            host=args.host,
            port=max(1, min(65535, args.port)),
            max_crashes=max(1, args.max_crashes),
            health_check_enabled=bool(args.health_check),
            health_startup_grace_seconds=max(0.0, args.health_startup_grace),
            health_check_interval_seconds=max(0.5, args.health_check_interval),
            health_timeout_seconds=max(0.1, args.health_timeout),
            health_failure_threshold=max(1, args.health_failure_threshold),
        ),
        runtime_dir=args.runtime_dir.resolve(),
    )
    try:
        if args.action == "check":
            result = supervisor.preflight()
            print(json.dumps(result, ensure_ascii=False))
            return {
                PREFLIGHT_FREE: 0,
                PREFLIGHT_EXPECTED: 10,
                PREFLIGHT_COLLISION: 20,
            }[result["status"]]
        if args.action == "run":
            return supervisor.run()
        if args.action == "stop":
            print(json.dumps(supervisor.request_stop(), ensure_ascii=False))
            return 0
        print(json.dumps(supervisor.status(), ensure_ascii=False, indent=2))
        return 0
    except SupervisorError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
