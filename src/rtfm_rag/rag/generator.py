from result import Err, Ok, Result

from rtfm_rag.core.constants import rag
from rtfm_rag.core.enums import GeneratorModelProvider
from rtfm_rag.repositories.chunk_repository import ChunkRetriveData
from rtfm_rag.services.ollama_service import generate_with_ollama
from rtfm_rag.services.openai_service import get_openai_client
from rtfm_rag.utils.utils import get_time_async


@get_time_async
async def generate_response(
  query: str, chunks: list[ChunkRetriveData], model_provider: GeneratorModelProvider
) -> Result[str, str]:
  context = "\n\n".join(chunk.content for chunk in chunks)

  full_prompt = rag.GENERATOR_USER_PROMPT_TEMPLATE.replace(
    "{context}", context
  ).replace("{user_query}", query)

  print(full_prompt)

  if model_provider == GeneratorModelProvider.ollama:
    return await generate_with_ollama(full_prompt)

  openai_clinet_result = get_openai_client()
  if isinstance(openai_clinet_result, Err):
    return openai_clinet_result

  try:
    response = openai_clinet_result.ok().responses.create(
      model=rag.GENERATOR_MODEL,
      temperature=0.2,
      instructions=rag.GENERATOR_SYSTEM_PROMPT,
      max_output_tokens=1500,
      input=[
        {
          "role": "user",
          "content": full_prompt,
        }
      ],
    )
    return Ok(response.output_text)
  except Exception as e:
    return Err(f"Exception occurred when trying to generate an llm answer: {e}")
