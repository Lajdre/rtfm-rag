from ollama import AsyncClient
from result import Err, Ok, Result

from ..core.config import config
from ..core.constants import rag


async def generate_with_ollama(prompt: str) -> Result[str, str]:
  try:
    client = AsyncClient(host=config.OLLAMA_BASE_URL)
    response = await client.chat(
      model=config.OLLAMA_MODEL,
      messages=[
        {"role": "system", "content": rag.GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
      ],
    )
    return Ok(str(response.message.content))
  except Exception as e:
    return Err(f"Ollama request failed: {e}")
