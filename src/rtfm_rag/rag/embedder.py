from __future__ import annotations

from typing import TYPE_CHECKING

from result import Err, Ok, Result

from rtfm_rag.core.constants import rag
from rtfm_rag.utils.utils import get_embed_token_count

if TYPE_CHECKING:
  from openai import OpenAI


async def embed_data(openai_client: OpenAI, text: str) -> Result[list[float], str]:
  if (n_tokens := get_embed_token_count(text)) > rag.EMBEDDING_TOKEN_LIMIT:
    return Err(
      f"Input text is too long to embed: {n_tokens} tokens (limit is {rag.EMBEDDING_TOKEN_LIMIT})"
    )
  try:
    response = openai_client.embeddings.create(model=rag.EMBEDDING_MODEL, input=text)
    return Ok(response.data[0].embedding)
  except Exception as e:
    return Err(f"Failed to generate an embedding: {e}")
