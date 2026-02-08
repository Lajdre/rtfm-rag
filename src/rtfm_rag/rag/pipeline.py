from __future__ import annotations
from typing import List, TYPE_CHECKING

from result import Err, Ok, Result, UnwrapError

from ..api.v1.schemas import MessageResponseSchema, MessageSchema
from ..core.constants import rag
from ..core.enums import GeneratorModelProvider
from ..repositories.chunk_repository import ChunkRetriveData, find_closest_chunks
from ..repositories.index_repository import get_index_id_by_name
from ..services.openai_service import get_openai_client
from .embedder import embed_data
from .generator import generate_response

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

    embedding: List[float] = (await embed_data(openai_client, message.text)).unwrap()

    retrived_chunks: List[ChunkRetriveData] = (
      await find_closest_chunks(conn, embedding, index_id)
    ).unwrap()

    filtered_chunks: List[ChunkRetriveData] = [
      chunk_data
      for chunk_data in retrived_chunks
      if chunk_data.distance < rag.MAX_RELEVANT_DISTANCE
    ]

    response: str = (
      await generate_response(message.text, filtered_chunks, generator_model_provider)
    ).unwrap()

    links: List[str] = list(set(chunk_data.url for chunk_data in filtered_chunks))

    return Ok(MessageResponseSchema(text=response, links=links))
  except UnwrapError as e:
    return Err(str(e))
