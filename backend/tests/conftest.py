from contextlib import asynccontextmanager
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.app.router, "lifespan_context", _noop_lifespan)
    with TestClient(main.app) as test_client:
        yield test_client
