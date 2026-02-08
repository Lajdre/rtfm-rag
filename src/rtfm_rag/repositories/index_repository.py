from __future__ import annotations
from typing import List, TYPE_CHECKING, Tuple

from result import Err, Ok, Result

if TYPE_CHECKING:
  from psycopg import AsyncConnection


async def get_index_id_by_name(
  conn: AsyncConnection, index_name: str
) -> Result[int | None, str]:
  try:
    async with conn.cursor() as cur:
      await cur.execute(
        "SELECT id FROM indexes WHERE name = %s",
        (index_name,),
      )
      if not (row := await cur.fetchone()):
        return Ok(None)
      return Ok(row[0])
  except Exception as e:
    return Err(f"Exception in get_chunk_id_by_name: {e}")


async def get_indexes_state(
  conn: AsyncConnection,
) -> Result[Tuple[int, List[str]], str]:
  """Return a tuple: (number of indexes, list of index names)."""
  try:
    async with conn.cursor() as cur:
      await cur.execute("SELECT name FROM indexes")
      rows = await cur.fetchall()
      names = [row[0] for row in rows]
      return Ok((len(names), names))
  except Exception as e:
    return Err(f"Exception in get_indexes_info: {e}")


async def create_index(
  conn: AsyncConnection, index_name: str, source_url: str
) -> Result[int, str]:
  """Create new index in database and return its ID."""
  try:
    async with conn.cursor() as cur:
      await cur.execute(
        "INSERT INTO indexes (name, source_url) VALUES (%s, %s) RETURNING id",
        (index_name, source_url),
      )
      row = await cur.fetchone()
      if not row:
        await conn.rollback()
        return Err("Failed in create_index: No row returned")
      await conn.commit()
      return Ok(row[0])
  except Exception as e:
    await conn.rollback()
    return Err(f"Failed in create_index: {e}")


# Could just use get_index_id_by_name instead
async def check_index_exists(
  conn: AsyncConnection, index_name: str
) -> Result[bool, str]:
  try:
    async with conn.cursor() as cur:
      await cur.execute("SELECT COUNT(*) FROM indexes WHERE name = %s", (index_name,))
      row = await cur.fetchone()
      if not row:
        return Err("Failed in check_index_exists: No row returned")
      return Ok(row[0] > 0)
  except Exception as e:
    return Err(f"Failed in check_index_exists: {e}")
