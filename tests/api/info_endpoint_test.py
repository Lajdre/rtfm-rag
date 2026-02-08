from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from rtfm_rag.main import app
from rtfm_rag.services.database_service import get_db_conn


async def override_get_db_conn():
  mock_cursor = AsyncMock()

  mock_cursor.__aenter__.return_value = mock_cursor
  mock_cursor.__aexit__.return_value = None

  mock_cursor.fetchall.return_value = [
    ("docs_tinygrad_org",),
    ("pytorch",),
    ("fastapi",),
  ]
  mock_cursor.execute.return_value = None

  mock_conn = MagicMock()  # cannot be AsyncMock(), conn itself is never awaited
  mock_conn.cursor.return_value = mock_cursor

  yield mock_conn  # <-- async generator


def test_info_indexes_endpoint(get_client: TestClient):
  app.dependency_overrides[get_db_conn] = override_get_db_conn

  response = get_client.get("/api/v1/info/indexes")

  assert response.status_code == 200
  data = response.json()

  assert data["numberOfIndexes"] == 3
  assert data["indexesNames"] == ["docs_tinygrad_org", "pytorch", "fastapi"]
