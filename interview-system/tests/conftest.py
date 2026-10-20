import os

os.environ["LLM_MODE"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ADMIN_API_KEY"] = "test-key"


import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
    if os.path.exists("test.db"):
        os.remove("test.db")
