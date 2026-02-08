import pytest
from fastapi.testclient import TestClient

from rtfm_rag.main import app

client = TestClient(app)


@pytest.fixture
def get_client() -> TestClient:
  return client


# @pytest.fixture(autouse=True)
# def clear_overrides():
#   app.dependency_overrides.clear()
#   yield
#   app.dependency_overrides.clear()
