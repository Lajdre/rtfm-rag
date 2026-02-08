from __future__ import annotations
from functools import lru_cache
from typing import AsyncGenerator, TYPE_CHECKING

from fastapi import HTTPException, Request, status
import psycopg
from result import Err, Ok, Result

from ..core.config import config

if TYPE_CHECKING:
  from psycopg import AsyncConnection


@lru_cache(maxsize=5)
def get_db_connection_string(
  host: str | None = None,
  port: int | None = None,
  database: str | None = None,
  user: str | None = None,
  password: str | None = None,
) -> str:
  return (
    f"host={host or config.DB_HOST} "
    f"port={port or config.DB_PORT} "
    f"dbname={database or config.DB_NAME} "
    f"user={user or config.DB_USER} "
    f"password={password or config.DB_PASSWORD}"
  )


# Request is used (ment to be used with Depends()) so that
# "from ..main import app" import is not needed
async def get_db_conn(request: Request) -> AsyncGenerator[AsyncConnection]:
  try:
    async with request.app.state.db_pool.connection() as conn:
      yield conn
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
      detail=f"Database connection error: {e}",
    )


def get_database_connection() -> Result[psycopg.Connection, str]:
  try:
    conn = psycopg.connect(get_db_connection_string())
    return Ok(conn)
  except Exception as e:
    return Err(f"Failed to connect to database: {e}")
