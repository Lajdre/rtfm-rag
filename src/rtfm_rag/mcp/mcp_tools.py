from __future__ import annotations

from typing import TYPE_CHECKING

from result import Err, Ok, Result, UnwrapError

from rtfm_rag.core.constants import rag
from rtfm_rag.rag.embedder import embed_data
from rtfm_rag.repositories.chunk_repository import ChunkRetriveData, find_closest_chunks
from rtfm_rag.repositories.index_repository import get_index_id_by_name
from rtfm_rag.services.openai_service import get_openai_client

if TYPE_CHECKING:
  from openai import OpenAI
  from psycopg import AsyncConnection


async def fetch_docs_candidate_context_impl(
  query: str, index_name: str, conn: AsyncConnection
) -> Result[str, str]:
  try:
    index_id: int | None = (await get_index_id_by_name(conn, index_name)).unwrap()
    if index_id is None:
      return Err("This index name is not present in the database")

    openai_client: OpenAI = get_openai_client().unwrap()

    embedding: list[float] = (await embed_data(openai_client, query)).unwrap()

    retrived_chunks: list[ChunkRetriveData] = (
      await find_closest_chunks(conn, embedding, index_id)
    ).unwrap()

    filtered_chunks: list[ChunkRetriveData] = [
      chunk_data
      for chunk_data in retrived_chunks
      if chunk_data.distance < rag.MAX_RELEVANT_DISTANCE
    ]
    context = "\n\n".join(filtered_chunk.content for filtered_chunk in filtered_chunks)
    return Ok(
      "<Candidate Additional Context>\n" + context + "\n</Candidate Additional Context>"
    )
  except UnwrapError as e:
    return Err(str(e))
