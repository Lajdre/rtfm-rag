from fastapi import APIRouter

from ...core.config import config
from .endpoints.health import router as health_router
from .endpoints.info import router as info_router
from .endpoints.ingest import router as ingest_router
from .endpoints.query import router as query_router

rounter = APIRouter(prefix=config.API_V1_STR)

rounter.include_router(query_router, tags=["Query Operations"])
rounter.include_router(ingest_router, tags=["Ingest Operations"])
rounter.include_router(info_router, tags=["Info Operations"])
rounter.include_router(health_router, tags=["Health Operations"])
