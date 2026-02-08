from pydantic_settings import BaseSettings, SettingsConfigDict

from .enums import GeneratorModelProvider


class Config(BaseSettings):
  PROJECT_NAME: str = "RTFM RAG"
  API_VERSION: str = "0.1.0"
  API_V1_STR: str = "/api/v1"

  SERVER_HOST: str = "0.0.0.0"
  SERVER_PORT: int = 8032
  SERVER_DEBUG_MODE: bool = False

  DB_HOST: str = "localhost"
  DB_PORT: int = 5432
  DB_NAME: str = "rtfm-rag"
  DB_USER: str = "developer"
  DB_PASSWORD: str = "password"

  LOG_LEVEL: str = "INFO"
  LOG_FILE: str | None = None
  LOG_FORMAT: str = "console"  # "json" or "console"

  GENERATOR_MODEL_PROVIDER: GeneratorModelProvider = GeneratorModelProvider.openai
  OLLAMA_BASE_URL: str = "http://localhost:11434"
  OLLAMA_MODEL: str = "gemma3:270m"

  OPENAI_API_KEY: str = ""

  AWS_ACCESS_KEY_ID: str = ""
  AWS_SECRET_ACCESS_KEY: str = ""
  AWS_S3_BUCKET_NAME: str = ""
  AWS_REGION: str = ""

  model_config = SettingsConfigDict(env_file=".env")


config = Config()
