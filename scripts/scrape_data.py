#!/usr/bin/env python3
"""
Script for scraping documentation pages and printing structured extraction results.
Usage: PYTHONPATH=src python -m scripts.scrape_data <url> <index_name> [--debug] [--max-depth N] [--max-pages N]
"""

import argparse
import asyncio
import sys
from typing import Any

from result import Err, Result

from rtfm_rag.services.documentation_scraper import DocumentationScraper, ScraperConfig


async def scrape_and_print(
  url: str, index_name: str, debug: bool, max_depth: int, max_pages: int
):
  config = ScraperConfig(
    max_depth=max_depth,
    max_pages=max_pages,
    enable_structured_extraction=True,
    clean_code_blocks=False,
    remove_line_numbers=False,
  )

  scraper = DocumentationScraper(config)

  print(f"Starting scrape for: {url}")
  if debug:
    print(f"Running in DEBUG mode (max_depth={max_depth}, max_pages={max_pages})")

  scrape_result: Result[dict[Any, Any], str] = await scraper.scrape_website(
    url, index_name
  )
  if isinstance(scrape_result, Err):
    print(f"Error occured: {scrape_result.err()}")
    sys.exit(1)

  print("Summary:")
  print(scrape_result.ok())

  if debug:
    pages = scraper.get_scraped_data()
    if not pages:
      print("No pages were scraped.")
      sys.exit(1)

    print("\nStructured extraction results:")
    for page in pages[:2]:
      print(f"\nPage: {page.title}")
      print(f"Sections: {len(page.structured_content)}")
      for section in page.structured_content[:3]:
        print(f"  - {section.type}: {section.title[:50]}...")
        print(f"    Content length: {len(section.content)} chars")
        print(f"    Code blocks: {len(section.code_blocks)}")


def main():
  parser = argparse.ArgumentParser(description="Scrape documentation from a url")
  parser.add_argument("url", help="URL of the documentation to scrape")
  parser.add_argument("index_name", help="Index name for the documentation")
  parser.add_argument(
    "--debug", action="store_true", help="Run in debug mode, print preview"
  )
  parser.add_argument("--max-depth", type=int, default=1, help="Max depth for scraping")
  parser.add_argument(
    "--max-pages", type=int, default=7, help="Max number of pages to scrape"
  )

  args = parser.parse_args()

  try:
    asyncio.run(
      scrape_and_print(
        args.url, args.index_name, args.debug, args.max_depth, args.max_pages
      )
    )
  except KeyboardInterrupt:
    print("\nScraping interrupted by user.")
    sys.exit(1)


if __name__ == "__main__":
  main()
