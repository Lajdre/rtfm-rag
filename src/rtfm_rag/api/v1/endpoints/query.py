from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from result import Err, Ok, Result

from rtfm_rag.api.v1.schemas import MessageResponseSchema, MessageSchema
from rtfm_rag.core.config import config
from rtfm_rag.rag.pipeline import rag_pipeline
from rtfm_rag.services.database_service import get_db_conn

if TYPE_CHECKING:
  from psycopg import AsyncConnection


router = APIRouter()


@router.post("/query", response_model=MessageResponseSchema)
async def query(
  message_schema: MessageSchema, conn: Annotated[AsyncConnection, Depends(get_db_conn)]
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
