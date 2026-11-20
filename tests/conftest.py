import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_DB = ROOT / "data" / "test_memory_juicer.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["DASHSCOPE_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client