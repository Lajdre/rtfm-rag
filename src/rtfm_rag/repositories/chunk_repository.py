from __future__ import annotations
from dataclasses import dataclass
from typing import List, TYPE_CHECKING, Tuple

from result import Err, Ok, Result

from ..models.models import ChunkData
from ..rag.embedder import embed_data

if TYPE_CHECKING:
  from psycopg import AsyncConnection
  from openai import OpenAI


@dataclass
class ChunkRetriveData:
  id: int
  distance: float
  content: str
  url: str


async def find_closest_chunks(
  conn: AsyncConnection,
  new_embedding: List[float],
  index_id: int,
  top_k: int = 10,
) -> Result[List[ChunkRetriveData], str]:
  """
  Returns a list of ChunkRetriveData (chunk_id, distance, content) for k closest chunks.
  """
  try:
    async with conn.cursor() as cur:
      await cur.execute(
        """
        SELECT id, embedding <=> %s::vector AS distance, content, url
        FROM (
            SELECT * FROM chunks WHERE index_id = %s
        ) AS filtered_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """,
        (new_embedding, index_id, new_embedding, top_k),
      )
      rows = await cur.fetchall()
      chunk_retrive_data_list: List[ChunkRetriveData] = [
        ChunkRetriveData(id=row[0], distance=row[1], content=row[2], url=row[3])
        for row in rows
      ]
      return Ok(chunk_retrive_data_list)
  except Exception as e:
    return Err(f"Exception in find_closest_chunks: {e}")


async def _bare_insert_chunk(
  conn: AsyncConnection,
  content: str,
  embedding: List[float],
  url: str,
  index_id: int,
) -> Result[None, str]:
  try:
    async with conn.cursor() as cur:
      await cur.execute(
        "INSERT INTO chunks (content, embedding, url, index_id) VALUES (%s, %s, %s, %s)",
        (content, embedding, url, index_id),
      )
    return Ok(None)
  except Exception as e:
    return Err(f"Exception in insert_chunk: {e}")


async def insert_chunks(
  conn: AsyncConnection,
  chunks: List[ChunkData],
  openai_client: OpenAI,
  index_id: int,
) -> Result[Tuple[int, int], str]:
  chunks_inserted = 0
  chunks_failed = 0

  try:
    for chunk in chunks:
      # TODO: batching
      embedding_result: Result[List[float], str] = await embed_data(
        openai_client, chunk.content
      )
      if isinstance(embedding_result, Err):
        chunks_failed += 1
        continue

      insert_result: Result[None, str] = await _bare_insert_chunk(
        conn, chunk.content, embedding_result.ok(), chunk.url, index_id
      )
      if isinstance(insert_result, Err):
        chunks_failed += 1
        continue

      chunks_inserted += 1

    await conn.commit()

    return Ok((chunks_inserted, chunks_failed))
  except Exception as e:
    await conn.rollback()
    return Err(f"Err in insert_chunks: {e}")
