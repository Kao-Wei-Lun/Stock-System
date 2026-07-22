from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_local_launchers_bind_to_loopback_by_default():
    windows_launcher = (PROJECT_ROOT / "scripts" / "start.bat").read_text(encoding="utf-8")
    shell_launcher = (PROJECT_ROOT / "scripts" / "start.sh").read_text(encoding="utf-8")
    vite_config = (PROJECT_ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

    assert 'if not defined APP_BIND_HOST set "APP_BIND_HOST=127.0.0.1"' in windows_launcher
    assert 'if not defined FRONTEND_BIND_HOST set "FRONTEND_BIND_HOST=127.0.0.1"' in windows_launcher
    assert 'APP_BIND_HOST="${APP_BIND_HOST:-127.0.0.1}"' in shell_launcher
    assert 'FRONTEND_BIND_HOST="${FRONTEND_BIND_HOST:-127.0.0.1}"' in shell_launcher
    assert 'process.env.FRONTEND_BIND_HOST || "127.0.0.1"' in vite_config


def test_docker_ports_are_loopback_only_by_default():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert compose.count("${DOCKER_BIND_HOST:-127.0.0.1}") == 3
    assert "http://127.0.0.1:8001/api/ready" in compose
