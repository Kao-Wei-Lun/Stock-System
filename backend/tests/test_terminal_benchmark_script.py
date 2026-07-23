import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
import threading


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "benchmark-terminal.ps1"


class _BenchmarkHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps({"data": [{"close": 1}, {"close": 2}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Server-Timing", "total;dur=1.25")
        self.send_header("X-Request-ID", "benchmark-test")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        return


def _run_script(*args):
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            *map(str, args),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def test_benchmark_writes_cold_warm_summary_without_unapproved_frontend_fields(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BenchmarkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = tmp_path / "benchmark.json"
    frontend = tmp_path / "frontend.json"
    frontend.write_text(
        json.dumps(
            {
                "marks": {
                    "qv:app-mounted": {"start_time_ms": 25.5, "detail": {"account": "private"}},
                    "qv:terminal-visible": {"start_time_ms": 100},
                    "qv:chart-data-ready": {"start_time_ms": 200},
                    "qv:chart-painted": {"start_time_ms": 225},
                },
                "api_key": "must-not-leak",
            }
        ),
        encoding="utf-8",
    )

    try:
        result = _run_script(
            "-BaseUrl", f"http://127.0.0.1:{server.server_port}",
            "-ColdRuns", "1",
            "-WarmRuns", "1",
            "-FrontendMetricsPath", frontend,
            "-OutputPath", output,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8-sig"))
    assert payload["summary"]["cold"]["count"] == 1
    assert payload["summary"]["warm"]["count"] == 1
    assert payload["runs"]["cold"][0]["response_bytes"] > 0
    assert payload["runs"]["warm"][0]["data_count"] == 2
    assert payload["frontend"]["marks"]["qv:app-mounted"] == {"start_time_ms": 25.5}
    assert "must-not-leak" not in output.read_text(encoding="utf-8-sig")
    assert "private" not in output.read_text(encoding="utf-8-sig")


def test_benchmark_fails_clearly_when_api_is_unavailable(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        unavailable_port = sock.getsockname()[1]

    output = tmp_path / "unavailable.json"
    result = _run_script(
        "-BaseUrl", f"http://127.0.0.1:{unavailable_port}",
        "-ColdRuns", "1",
        "-WarmRuns", "1",
        "-TimeoutSeconds", "1",
        "-OutputPath", output,
    )

    assert result.returncode != 0
    assert "Benchmark request failed" in (result.stderr + result.stdout)
    assert not output.exists()

