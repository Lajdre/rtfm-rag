from __future__ import annotations

from typing import TYPE_CHECKING

from result import Err, Ok, Result, UnwrapError

from rtfm_rag.api.v1.schemas import MessageResponseSchema, MessageSchema
from rtfm_rag.core.constants import rag
from rtfm_rag.core.enums import GeneratorModelProvider
from rtfm_rag.rag.embedder import embed_data
from rtfm_rag.rag.generator import generate_response
from rtfm_rag.repositories.chunk_repository import ChunkRetriveData, find_closest_chunks
from rtfm_rag.repositories.index_repository import get_index_id_by_name
from rtfm_rag.services.openai_service import get_openai_client

if TYPE_CHECKING:
  from openai import OpenAI
  from psycopg import AsyncConnection


async def rag_pipeline(
  message: MessageSchema,
  generator_model_provider: GeneratorModelProvider,
  conn: AsyncConnection,
) -> Result[MessageResponseSchema, str]:
  try:
    index_id: int | None = (
      await get_index_id_by_name(conn, message.indexName)
    ).unwrap()
    if index_id is None:
      return Err("This index name is not present in the database")

    openai_client: OpenAI = get_openai_client().unwrap()

    embedding: list[float] = (await embed_data(openai_client, message.text)).unwrap()

    retrived_chunks: list[ChunkRetriveData] = (
      await find_closest_chunks(conn, embedding, index_id)
    ).unwrap()

    filtered_chunks: list[ChunkRetriveData] = [
      chunk_data
      for chunk_data in retrived_chunks
      if chunk_data.distance < rag.MAX_RELEVANT_DISTANCE
    ]

    response: str = (
      await generate_response(message.text, filtered_chunks, generator_model_provider)
    ).unwrap()

    links: list[str] = list(set(chunk_data.url for chunk_data in filtered_chunks))

    return Ok(MessageResponseSchema(text=response, links=links))
  except UnwrapError as e:
    return Err(str(e))
