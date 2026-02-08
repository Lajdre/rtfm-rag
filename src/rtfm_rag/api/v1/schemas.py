from pydantic import BaseModel


class MessageSchema(BaseModel):
  text: str
  indexName: str
  userId: str


class MessageResponseSchema(BaseModel):
  text: str
  links: list[str]
