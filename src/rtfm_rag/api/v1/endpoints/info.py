from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel
from result import Err, Ok, Result

from rtfm_rag.repositories.index_repository import get_indexes_state
from rtfm_rag.services.database_service import get_db_conn

router = APIRouter(prefix="/info")


class IndexesInfoResponseSchema(BaseModel):
  number_of_indexes: int
  indexes_names: list[str]


async def _get_indexes_info(
  conn: AsyncConnection,
) -> Result[IndexesInfoResponseSchema, str]:
  indexes_info_result: Result[tuple[int, list[str]], str] = await get_indexes_state(
    conn
  )

  match indexes_info_result:
    case Ok(indexes_info):
      return Ok(
        IndexesInfoResponseSchema(
          number_of_indexes=indexes_info[0], indexes_names=indexes_info[1]
        )
      )
    case Err(e):
      return Err(e)


@router.get("/indexes", response_model=IndexesInfoResponseSchema)
async def get_indexes_info(
  conn: Annotated[AsyncConnection, Depends(get_db_conn)],
) -> IndexesInfoResponseSchema:
  try:
    match await _get_indexes_info(conn):
      case Ok(result):
        return result
      case Err(e):
        raise HTTPException(status_code=400, detail=(e))
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


@router.get("/state")
async def get_state_info():
  # TODO: todo
  try:
    raise
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
