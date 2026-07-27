from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import service_supervisor as supervisor_module
from service_supervisor import (
    PREFLIGHT_COLLISION,
    PREFLIGHT_EXPECTED,
    LocalServiceSupervisor,
    SupervisorError,
    SupervisorSettings,
    request_supervised_restart,
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

    def poll(self):
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


def test_preflight_recognizes_listener_descended_from_managed_venv_launcher(tmp_path):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    (runtime / "backend-service.json").write_text(
        json.dumps({"process_pid": 42, "port": 8001}),
        encoding="utf-8",
    )
    parents = {99: 77, 77: 42}
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=runtime,
        port_probe=lambda _port: 99,
        command_line_probe=lambda _pid: (
            f'"{settings(tmp_path).python_path}" -X utf8 -m uvicorn main:app --port 8001'
        ),
        parent_pid_probe=lambda pid: parents.get(pid),
    )

    result = supervisor.preflight()

    assert result["status"] == PREFLIGHT_EXPECTED
    assert result["process_pid"] == 99
    assert result["managed"] is True


def test_windows_tree_termination_falls_back_to_confirmed_listener(
    tmp_path,
    monkeypatch,
):
    commands = []
    process = FakeProcess(42, 0)
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=tmp_path / ".runtime",
        port_probe=lambda _port: 99,
        command_line_probe=lambda _pid: (
            f'"{settings(tmp_path).python_path}" -X utf8 -m uvicorn main:app --port 8001'
        ),
    )
    monkeypatch.setattr(supervisor_module.sys, "platform", "win32")
    monkeypatch.setattr(supervisor_module.os, "kill", lambda *_args: None)
    monkeypatch.setattr(
        supervisor_module.subprocess,
        "run",
        lambda command, **_kwargs: (
            commands.append(command) or SimpleNamespace(returncode=0)
        ),
    )

    supervisor._terminate_started_process(process)

    assert commands == [["taskkill", "/PID", "99", "/T", "/F"]]


def test_windows_stop_waits_for_supervisor_marker_before_direct_kill(
    tmp_path,
    monkeypatch,
):
    clock = FakeClock()
    observations = iter([99, 99, None])
    commands = []
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=tmp_path / ".runtime",
        port_probe=lambda _port: next(observations),
        command_line_probe=lambda _pid: (
            f'"{settings(tmp_path).python_path}" -X utf8 -m uvicorn main:app --port 8001'
        ),
        clock=clock,
        sleep=clock.sleep,
    )
    monkeypatch.setattr(supervisor_module.sys, "platform", "win32")
    monkeypatch.setattr(
        supervisor_module.subprocess,
        "run",
        lambda command, **_kwargs: (
            commands.append(command) or SimpleNamespace(returncode=0)
        ),
    )

    result = supervisor.request_stop()

    assert result["status"] == "stop_requested"
    assert commands == []
    assert clock.sleeps == [0.25]


def test_stop_does_not_publish_marker_for_unconfirmed_port_owner(tmp_path):
    runtime = tmp_path / ".runtime"
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=runtime,
        port_probe=lambda _port: 99,
        command_line_probe=lambda _pid: "other-server --port 8001",
    )

    with pytest.raises(SupervisorError, match="unconfirmed process"):
        supervisor.request_stop()

    assert not supervisor.stop_marker.exists()


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


def test_restart_request_marker_contains_only_safe_versioned_fields(tmp_path):
    runtime = tmp_path / ".runtime"

    payload = request_supervised_restart(
        runtime,
        reason_code="fubon_ws_maintenance",
        source="scheduler",
    )
    serialized = (runtime / "backend-service.restart").read_text(encoding="utf-8")

    assert set(payload) == {"schema_version", "requested_at", "reason_code", "source"}
    assert payload["reason_code"] == "fubon_ws_maintenance"
    assert "password" not in serialized.lower()
    assert "ticker" not in serialized.lower()
    with pytest.raises(ValueError, match="reason_code"):
        request_supervised_restart(runtime, reason_code="contains account 123")


def test_planned_restart_recycles_child_without_crash_backoff(tmp_path, monkeypatch):
    runtime = tmp_path / ".runtime"
    clock = FakeClock()

    class RunningProcess(FakeProcess):
        def __init__(self, pid):
            super().__init__(pid, 0)
            self.running = True

        def poll(self):
            return None if self.running else self.exit_code

    class RestartFactory:
        def __init__(self):
            self.processes = []

        def __call__(self, _command, **_kwargs):
            if not self.processes:
                process = RunningProcess(2201)
                request_supervised_restart(
                    runtime,
                    reason_code="fubon_ws_maintenance",
                    source="scheduler",
                )
            else:
                process = FakeProcess(2202, 0)
            self.processes.append(process)
            return process

    factory = RestartFactory()
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=runtime,
        port_probe=lambda _port: None,
        popen_factory=factory,
        clock=clock,
        sleep=clock.sleep,
    )

    def terminate(process):
        process.running = False
        process.killed = True

    monkeypatch.setattr(supervisor, "_terminate_started_process", terminate)

    assert supervisor.run() == 0
    assert len(factory.processes) == 2
    assert factory.processes[0].killed is True
    assert clock.sleeps == []
    assert not supervisor.breaker_path.exists()
    assert not supervisor.restart_marker.exists()
    last_restart = json.loads(supervisor.last_restart_path.read_text(encoding="utf-8"))
    assert last_restart["status"] == "completed"
    assert last_restart["reason_code"] == "fubon_ws_maintenance"


def test_planned_stop_takes_priority_over_restart_request(tmp_path, monkeypatch):
    runtime = tmp_path / ".runtime"

    class RunningProcess(FakeProcess):
        def poll(self):
            return None

    class StopFactory:
        def __init__(self):
            self.processes = []

        def __call__(self, _command, **_kwargs):
            process = RunningProcess(3301, 0)
            self.processes.append(process)
            request_supervised_restart(
                runtime,
                reason_code="fubon_ws_maintenance",
                source="scheduler",
            )
            (runtime / "backend-service.stop").write_text("planned\n", encoding="utf-8")
            return process

    factory = StopFactory()
    supervisor = LocalServiceSupervisor(
        settings(tmp_path),
        runtime_dir=runtime,
        port_probe=lambda _port: None,
        popen_factory=factory,
    )
    monkeypatch.setattr(
        supervisor,
        "_terminate_started_process",
        lambda process: setattr(process, "killed", True),
    )

    assert supervisor.run() == 0
    assert len(factory.processes) == 1
    assert factory.processes[0].killed is True
    assert not supervisor.restart_marker.exists()
    assert not supervisor.last_restart_path.exists()
