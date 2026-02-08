from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel, Field, HttpUrl, StringConstraints
from result import Err, Ok, Result

from rtfm_rag.services.database_service import get_db_conn
from rtfm_rag.services.documentation_scraper import DocumentationScraper, ScraperConfig
from rtfm_rag.services.store_data import store_data

router = APIRouter(prefix="/ingest")


class IngestLinkSchema(BaseModel):
  url: HttpUrl
  index_name: Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[A-Za-z0-9_]+$"),
  ]
  max_depth: Annotated[int, Field(strict=True, gt=0)]
  max_pages: Annotated[int, Field(strict=True, gt=0)]


class IngestLinkResponseSchema(BaseModel):
  scraping_summary: dict[str, Any]
  storage_summary: dict[str, Any]
  status: str


async def _ingest_link(
  ingest_link_data: IngestLinkSchema, conn: AsyncConnection
) -> Result[IngestLinkResponseSchema, str]:
  scraper_config = ScraperConfig(
    max_depth=ingest_link_data.max_depth, max_pages=ingest_link_data.max_pages
  )
  scraper = DocumentationScraper(scraper_config)

  scrape_result: Result[dict[Any, Any], str] = await scraper.scrape_website(
    ingest_link_data.url, ingest_link_data.index_name
  )
  if isinstance(scrape_result, Err):
    return Err(scrape_result.err())

  data_storage_result = await store_data(conn, ingest_link_data.index_name)
  if isinstance(data_storage_result, Err):
    return Err(data_storage_result.err())

  return Ok(
    IngestLinkResponseSchema(
      scraping_summary=scrape_result.ok(),
      storage_summary=data_storage_result.ok().model_dump(),
      status="complete",
    )
  )


@router.post("/link", response_model=IngestLinkResponseSchema)
async def ingest_link(
  ingest_link_data: IngestLinkSchema,
  conn: Annotated[AsyncConnection, Depends(get_db_conn)],
) -> IngestLinkResponseSchema:
  try:
    result: Result[IngestLinkResponseSchema, str] = await _ingest_link(
      ingest_link_data, conn
    )
    match result:
      case Ok(summary):
        return summary
      case Err(e):
        raise HTTPException(status_code=400, detail=(e))
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
