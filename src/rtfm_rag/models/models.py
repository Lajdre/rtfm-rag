from dataclasses import dataclass


@dataclass
class ChunkData:
  content: str
  url: str
  char_length: int
  tokens: int
