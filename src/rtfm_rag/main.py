from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import AsyncConnectionPool

from rtfm_rag.api.v1.master_router import rounter
from rtfm_rag.core.config import config
from rtfm_rag.services.database_service import get_db_connection_string


@asynccontextmanager
async def lifespan(app: FastAPI):
  pool = AsyncConnectionPool(
    conninfo=get_db_connection_string(),
    min_size=1,
    max_size=10,
    timeout=10,
    max_idle=60,
  )
  await pool.open()
  app.state.db_pool = pool

  async def connection_reaping():
    while True:
      await asyncio.sleep(600)
      await pool.check()

  task = asyncio.create_task(connection_reaping())

  yield

  task.cancel()
  try:
    await task
  except asyncio.CancelledError:
    pass
  await pool.close()


app = FastAPI(
  title=config.PROJECT_NAME,
  version=config.API_VERSION,
  openapi_url=f"{config.API_V1_STR}/openapi.json",
  lifespan=lifespan,
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
  ],
  allow_credentials=True,
  allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allow_headers=["*"],
)

app.include_router(rounter)


if __name__ == "__main__":
  import uvicorn

  uvicorn.run(
    "src.main:app",
    host=config.SERVER_HOST,
    port=config.SERVER_PORT,
    reload=config.SERVER_DEBUG_MODE,
  )
