from __future__ import annotations

import json

import pytest

from service_supervisor import (
    PREFLIGHT_COLLISION,
    PREFLIGHT_EXPECTED,
    LocalServiceSupervisor,
    SupervisorError,
    SupervisorSettings,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class FakeProcess:
    def __init__(self, pid: int, exit_code: int) -> None:
        self.pid = pid
        self.exit_code = exit_code
        self.killed = False

    def wait(self, timeout=None):
        return self.exit_code

    def kill(self):
        self.killed = True

    def terminate(self):
        self.killed = True


class ProcessFactory:
    def __init__(self, exit_codes: list[int]) -> None:
        self.exit_codes = list(exit_codes)
        self.processes: list[FakeProcess] = []
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        process = FakeProcess(1200 + len(self.processes), self.exit_codes.pop(0))
        self.processes.append(process)
        return process


def settings(tmp_path, **overrides) -> SupervisorSettings:
    values = {
        "python_path": tmp_path / "python.exe",
        "working_directory": tmp_path / "backend",
        "port": 8001,
        "max_crashes": 3,
        "initial_backoff_seconds": 1,
        "max_backoff_seconds": 4,
    }
    values.update(overrides)
    return SupervisorSettings(**values)


def test_preflight_reuses_only_confirmed_quantvision_process(tmp_path):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    (runtime / "backend-service.json").write_text(
        json.dumps({"process_pid": 42, "port": 8001}),
        encoding="utf-8",
    )
    confirmed = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=runtime,
        port_probe=lambda _port: 42,
        command_line_probe=lambda _pid: (
            f'"{settings(tmp_path).python_path}" -m uvicorn main:app --port 8001'
        ),
    )
    collision = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=runtime,
        port_probe=lambda _port: 99,
        command_line_probe=lambda _pid: "other-server --port 8001",
    )

    assert confirmed.preflight()["status"] == PREFLIGHT_EXPECTED
    assert collision.preflight()["status"] == PREFLIGHT_COLLISION
    with pytest.raises(SupervisorError, match="unconfirmed process"):
        collision.run()


def test_preflight_can_reuse_exact_legacy_launcher_signature_without_state(tmp_path):
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=tmp_path / ".runtime",
        port_probe=lambda _port: 55,
        command_line_probe=lambda _pid: (
            f'"{settings(tmp_path).python_path}" -X utf8 -m uvicorn main:app --port 8001'
        ),
    )

    result = supervisor.preflight()

    assert result["status"] == PREFLIGHT_EXPECTED
    assert result["managed"] is False


def test_crash_restarts_with_backoff_then_planned_exit_does_not_restart(tmp_path):
    clock = FakeClock()
    factory = ProcessFactory([1, 0])
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=tmp_path / ".runtime",
        port_probe=lambda _port: None,
        popen_factory=factory,
        clock=clock,
        sleep=clock.sleep,
    )

    result = supervisor.run()

    assert result == 0
    assert len(factory.processes) == 2
    assert sum(clock.sleeps) == pytest.approx(1)
    assert not supervisor.state_path.exists()
    assert not supervisor.breaker_path.exists()
    assert factory.commands[0][-3:] == ["--port", "8001", "--no-use-colors"]


def test_restart_storm_opens_breaker_and_stops_spawning(tmp_path):
    clock = FakeClock()
    factory = ProcessFactory([1, 2, 3, 0])
    supervisor = LocalServiceSupervisor(
        settings(tmp_path, max_crashes=3),
        runtime_dir=tmp_path / ".runtime",
        port_probe=lambda _port: None,
        popen_factory=factory,
        clock=clock,
        sleep=clock.sleep,
    )

    result = supervisor.run()
    breaker = json.loads(supervisor.breaker_path.read_text(encoding="utf-8"))

    assert result == 70
    assert len(factory.processes) == 3
    assert breaker["status"] == "restart_breaker_open"
    assert breaker["crash_count"] == 3
    assert "command" not in breaker
    assert "python_path" not in breaker


def test_running_state_contains_no_command_arguments_or_secrets(tmp_path):
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=tmp_path / ".runtime",
        port_probe=lambda _port: None,
    )

    supervisor._write_running_state(123, 2)
    serialized = supervisor.state_path.read_text(encoding="utf-8")

    assert '"signature": "uvicorn main:app"' in serialized
    assert "password" not in serialized.lower()
    assert "api_key" not in serialized.lower()
    assert str(settings(tmp_path).python_path) not in serialized
