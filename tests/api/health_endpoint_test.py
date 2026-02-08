from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from rtfm_rag.main import app
from rtfm_rag.services.database_service import get_db_conn


async def override_get_db_conn():
  mock_cursor = AsyncMock()

  mock_cursor.__aenter__.return_value = mock_cursor
  mock_cursor.__aexit__.return_value = None

  mock_cursor.fetchall.return_value = None

  mock_cursor.fetchone.return_value = 1

  mock_cursor.execute.return_value = None

  mock_conn = MagicMock()
  mock_conn.cursor.return_value = mock_cursor

  yield mock_conn


def test_healthz_endpint(get_client: TestClient):
  app.dependency_overrides[get_db_conn] = override_get_db_conn

  response = get_client.get("/api/v1/healthz")

  assert response.status_code == 200
  data = response.json()

  assert data == {"status": "ok", "result": 1}

  # app.dependency_overrides.clear()
