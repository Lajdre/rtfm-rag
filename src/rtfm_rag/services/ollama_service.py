from collections.abc import Awaitable
from typing import Callable, cast

from ollama import AsyncClient, ChatResponse
from result import Err, Ok, Result

from rtfm_rag.core.config import config
from rtfm_rag.core.constants import rag


async def generate_with_ollama(prompt: str) -> Result[str, str]:
  try:
    client = AsyncClient(host=config.OLLAMA_BASE_URL)
    chat = cast(
      Callable[..., Awaitable[ChatResponse]],
      client.chat,
    )
    response: ChatResponse = await chat(
      model=config.OLLAMA_MODEL,
      messages=[
        {"role": "system", "content": rag.GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
      ],
    )
    return Ok(str(response.message.content))
  except Exception as e:
    return Err(f"Ollama request failed: {e}")
