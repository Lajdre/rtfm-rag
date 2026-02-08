from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from result import Err, Ok, Result

from ....core.config import config
from ....rag.pipeline import rag_pipeline
from ....services.database_service import get_db_conn
from ..schemas import MessageResponseSchema, MessageSchema

if TYPE_CHECKING:
  from psycopg import AsyncConnection


router = APIRouter()


@router.post("/query", response_model=MessageResponseSchema)
async def query(
  message_schema: MessageSchema, conn: AsyncConnection = Depends(get_db_conn)
):
  try:
    result: Result[MessageResponseSchema, str] = await rag_pipeline(
      message_schema, config.GENERATOR_MODEL_PROVIDER, conn
    )
    match result:
      case Ok(response):
        return response
      case Err(e):
        raise HTTPException(status_code=400, detail=(e))
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
