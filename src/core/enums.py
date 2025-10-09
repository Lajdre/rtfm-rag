from enum import Enum


class GeneratorModelProvider(str, Enum):
  """Available model backends for answer generation"""

  openai = "openai"
  ollama = "ollama"
