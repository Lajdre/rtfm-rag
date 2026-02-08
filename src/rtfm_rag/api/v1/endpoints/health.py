from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from rtfm_rag.core.config import config
from rtfm_rag.services.database_service import get_db_conn

router = APIRouter()


@router.get("/healthz")
async def healthz(conn: Annotated[AsyncConnection, Depends(get_db_conn)]):
  async with conn.cursor() as cursor:
    await cursor.execute("SELECT 1")
    result = await cursor.fetchone()
  return {"status": "ok", "result": result}


@router.get("/")
async def read_root():
  return {f"{config.PROJECT_NAME}": "it is"}
