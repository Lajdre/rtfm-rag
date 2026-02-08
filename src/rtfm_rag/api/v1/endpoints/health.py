from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from ....core.config import config
from ....services.database_service import get_db_conn

if TYPE_CHECKING:
  from psycopg import AsyncConnection

router = APIRouter()


@router.get("/healthz")
async def healthz(conn: AsyncConnection = Depends(get_db_conn)):
  async with conn.cursor() as cursor:
    await cursor.execute("SELECT 1")
    result = await cursor.fetchone()
  return {"status": "ok", "result": result}


@router.get("/")
async def read_root():
  return {f"{config.PROJECT_NAME}": "it is"}
