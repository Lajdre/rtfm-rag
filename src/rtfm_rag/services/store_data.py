from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from pydantic import BaseModel
from result import Err, Ok, Result

from ..models.models import ChunkData
from ..repositories.chunk_repository import insert_chunks
from ..repositories.index_repository import check_index_exists, create_index
from ..services.openai_service import get_openai_client
from ..utils.utils import get_embed_token_count

if TYPE_CHECKING:
  from openai import OpenAI
  from psycopg import AsyncConnection


class StorageStatistics(BaseModel):
  chunks_inserted: int
  chunks_failed: int
  average_chunk_length_chars: float
  mode_chunk_length_chars: int
  average_chunk_length_tokens: float
  mode_chunk_length_tokens: int
  total_files_processed: int
  index_name: str
  source_url: str


def _chunk_content(content: str, max_chars: int = 2000) -> List[str]:
  """Split content into smaller chunks if needed."""
  # TODO: make this better
  if len(content) <= max_chars:
    return [content]

  chunks = []
  words = content.split()
  current_chunk = []
  current_length = 0

  for word in words:
    word_length = len(word) + 1  # +1 for space
    if current_length + word_length > max_chars and current_chunk:
      chunks.append(" ".join(current_chunk))
      current_chunk = [word]
      current_length = word_length
    else:
      current_chunk.append(word)
      current_length += word_length

  if current_chunk:
    chunks.append(" ".join(current_chunk))

  return chunks


def _process_json_file(file_path: Path) -> Result[List[ChunkData], str]:
  """Process a single JSON file and return chunk data."""
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      data = json.load(f)

    chunks = []
    page_title = data.get("title", "")
    structured_content = data.get("structured_content", [])
    url = data.get("url", str(file_path))

    for item in structured_content:
      # Disable this for now
      # if item.get("type") != "heading":
      #   continue

      title = item.get("title", "").strip()
      content = item.get("content", "").strip()

      if not content:
        continue

      # Base chunk schema
      base_content = f"{page_title}\n{title}\n{content}"

      # Check if content needs further chunking
      content_chunks = _chunk_content(base_content)

      if len(content_chunks) == 1:
        chunk_data = ChunkData(
          content=base_content,
          url=url,
          char_length=len(base_content),
          tokens=get_embed_token_count(base_content),
        )
        chunks.append(chunk_data)
      else:
        # Multiple chunks needed
        for i, chunk_content in enumerate(content_chunks, 1):
          # Replace title with numbered title
          # TODO: this does not account for page_title and tile being present
          # only in the first splitted chunk
          lines = chunk_content.split("\n", 2)
          if len(lines) >= 2:
            numbered_title = f"{title} ({i}/{len(content_chunks)})"
            final_content = (
              f"{lines[0]}\n{numbered_title}\n{lines[2] if len(lines) > 2 else ''}"
            )
          else:
            final_content = chunk_content

          chunk_data = ChunkData(
            content=final_content,
            url=url,
            char_length=len(final_content),
            tokens=get_embed_token_count(final_content),
          )
          chunks.append(chunk_data)

    return Ok(chunks)

  except Exception as e:
    return Err(f"Failed to process file {file_path}: {e}")


def _find_json_files(data_dir: Path) -> List[Path]:
  """Recursively find all JSON files except settings.json."""
  json_files = []
  for file_path in data_dir.rglob("*.json"):
    if file_path.name != "settings.json":
      json_files.append(file_path)
  return json_files


def _calculate_mode(values: List[int]) -> int:
  if not values:
    return 0
  return max(set(values), key=values.count)


def _write_debug_chunks(chunks: List[ChunkData], index_name: str) -> None:
  debug_dir = Path("logs")
  debug_dir.mkdir(exist_ok=True)

  debug_file = debug_dir / f"{index_name}_chunks_debug.txt"

  with open(debug_file, "w", encoding="utf-8") as f:
    f.write(f"Debug chunks for index: {index_name}\n")
    f.write("=" * 50 + "\n\n")

    for i, chunk in enumerate(chunks, 1):
      f.write(f"CHUNK {i}\n")
      f.write(f"URL: {chunk.url}\n")
      f.write(f"Length (chars): {chunk.char_length}\n")
      f.write(f"Length (tokens): {chunk.tokens}\n")
      f.write("-" * 30 + "\n")
      f.write(f"{chunk.content}\n")
      f.write("=" * 50 + "\n\n")


async def store_data(
  conn: AsyncConnection,
  index_name: str,
  debug_mode: bool = False,
  max_debug_chunks: int = 20,
) -> Result[StorageStatistics, str]:
  # Fail if index_name folder doesn't exist
  data_dir = Path("data") / index_name
  if not data_dir.exists():
    return Err(f"Data directory not found: {data_dir}")

  try:
    # Fail if index already exists in database
    index_exists_result: Result[bool, str] = await check_index_exists(conn, index_name)
    if isinstance(index_exists_result, Err):
      return index_exists_result

    if index_exists_result.ok():
      return Err(f"Index '{index_name}' already exists in database")

    json_files = _find_json_files(data_dir)
    if not json_files:
      return Err(f"No JSON files found in {data_dir}")

    # Process all files and collect chunks
    all_chunks: List[ChunkData] = []
    files_processed = 0

    for json_file in json_files:
      process_result: Result[List[ChunkData], str] = _process_json_file(json_file)
      if isinstance(process_result, Err):
        # logger.warning(f"Skipping file {json_file}: {process_result.err()}")
        continue

      all_chunks.extend(process_result.ok())
      files_processed += 1

      if debug_mode and len(all_chunks) >= max_debug_chunks:
        break

    if not all_chunks:
      return Err("No chunks generated from the processed files")

    # Retrieve source_url from summary.json
    source_url = ""
    scraper_summary = None
    summary_file_path = data_dir / "summary.json"
    if not summary_file_path.exists():
      ...
      # TODO: todo
      # logger.info(
      #   f"Summary.json file does not exist for index {index_name} ({summary_file_path})"
      # )

    try:
      with open(summary_file_path) as f:
        scraper_summary = json.load(f)
    except Exception as _:
      ...
      # TODO: todo
      # logger.error(f"Failed to access summary file {summary_file_path}: {e}")

    source_url: str = scraper_summary.get("base_url", "") if scraper_summary else ""

    char_lengths = [chunk.char_length for chunk in all_chunks]
    token_lengths = [chunk.tokens for chunk in all_chunks]

    average_chunk_length_chars = sum(char_lengths) / len(char_lengths)
    mode_chunk_length_chars = _calculate_mode(char_lengths)
    average_chunk_length_tokens = sum(token_lengths) / len(token_lengths)
    mode_chunk_length_tokens = _calculate_mode(token_lengths)

    if debug_mode:
      _write_debug_chunks(all_chunks, index_name)

      stats = StorageStatistics(
        chunks_inserted=0,
        chunks_failed=0,
        average_chunk_length_chars=average_chunk_length_chars,
        mode_chunk_length_chars=mode_chunk_length_chars,
        average_chunk_length_tokens=average_chunk_length_tokens,
        mode_chunk_length_tokens=mode_chunk_length_tokens,
        total_files_processed=files_processed,
        index_name=index_name,
        source_url=source_url,
      )
      return Ok(stats)

    openai_client_result: Result = get_openai_client()
    if isinstance(openai_client_result, Err):
      return openai_client_result
    openai_client: OpenAI = openai_client_result.ok()

    create_index_result: Result[int, str] = await create_index(
      conn, index_name, source_url
    )
    if isinstance(create_index_result, Err):
      return create_index_result

    index_id: int = create_index_result.ok()

    insert_chunks_res: Result[Tuple[int, int], str] = await insert_chunks(
      conn, all_chunks, openai_client, index_id
    )
    if isinstance(insert_chunks_res, Err):
      return insert_chunks_res

    chunks_inserted, chunks_failed = insert_chunks_res.ok()

    if not chunks_inserted:
      return Err("No chunks were successfully inserted")

    stats = StorageStatistics(
      chunks_inserted=chunks_inserted,
      chunks_failed=chunks_failed,
      average_chunk_length_chars=average_chunk_length_chars,
      mode_chunk_length_chars=mode_chunk_length_chars,
      average_chunk_length_tokens=average_chunk_length_tokens,
      mode_chunk_length_tokens=mode_chunk_length_tokens,
      total_files_processed=files_processed,
      index_name=index_name,
      source_url=source_url,
    )

    return Ok(stats)

  except Exception as e:
    return Err(f"Unexpected error during data storage: {e}")
