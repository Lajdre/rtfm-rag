from functools import lru_cache

from openai import OpenAI
from result import Err, Ok, Result

from ..core.config import config


@lru_cache(maxsize=1)
def get_openai_client() -> Result[OpenAI, str]:
  api_key = config.OPENAI_API_KEY
  if not api_key:
    return Err("OpenAI api key is missing.")
  client = OpenAI(api_key=api_key)
  return Ok(client)
