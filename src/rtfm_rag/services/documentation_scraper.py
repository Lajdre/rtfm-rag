import asyncio
from datetime import datetime
import json
from pathlib import Path
import re
import time
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
import html2text
from pydantic import BaseModel, HttpUrl
from result import Err, Ok, Result

from .s3_uploader import upload_to_s3


class ContentSection(BaseModel):
  type: str  # 'function', 'class', 'example', 'description', 'heading', etc.
  title: str
  content: str
  code_blocks: List[str] = []
  metadata: Dict = {}


class ScrapedPage(BaseModel):
  url: str
  title: str
  raw_content: str  # Original markdown for fallback
  structured_content: List[ContentSection] = []
  scraped_at: str
  depth: int
  parent_url: Optional[str] = None
  word_count: int = 0
  estimated_tokens: int = 0


class ScraperConfig(BaseModel):
  max_depth: int = 3
  max_pages: int = 100
  delay_between_requests: float = 1.0
  timeout: int = 30
  follow_external_links: bool = False
  enable_structured_extraction: bool = True
  clean_code_blocks: bool = False
  remove_line_numbers: bool = False
  include_patterns: List[str] = []
  exclude_patterns: List[str] = [
    r".*\.(pdf|jpg|jpeg|png|gif|zip|tar|gz)$",
    r".*/api/.*",
    r".*/search.*",
    r".*/login.*",
    r".*/register.*",
  ]


class DocumentationScraper:
  def __init__(self, config: ScraperConfig | None = None):
    self.config = config or ScraperConfig()
    self.visited_urls: Set[str] = set()
    self.scraped_pages: List[ScrapedPage] = []
    self.base_domain = ""
    self.session: aiohttp.ClientSession | None = None

    self.html_converter = html2text.HTML2Text()
    self.html_converter.ignore_links = False
    self.html_converter.ignore_images = True
    self.html_converter.ignore_emphasis = False
    self.html_converter.body_width = 0
    self.html_converter.unicode_snob = True

  def _clean_text(self, text: str) -> str:
    if not text:
      return ""

    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove line numbers
    if self.config.remove_line_numbers:
      text = re.sub(r"^\s*\d+\s*\|?\s*", "", text, flags=re.MULTILINE)
      text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    text = re.sub(r'\[\s*\]\([^)]*"[^"]*"\)', "", text)  # Empty links with titles
    text = re.sub(r"\s*¤\s*", "", text)  # Documentation anchors

    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single
    text = re.sub(r"\n\s+\n", "\n\n", text)  # Remove spaces between paragraphs

    return text.strip()

  def _extract_code_blocks(self, content: str) -> tuple[str, List[str]]:
    code_blocks = []

    # Find code blocks
    # Match an optional "language hint" right after the opening backticks
    # Matches the shortest possible (?) group (())
    code_pattern = r"```[\w]*\n(.*?)\n```"
    # Find all non-overlapping matches
    # re.DOTALL -> make . also mach new lines
    matches = re.finditer(code_pattern, content, re.DOTALL)

    for match in matches:
      code_content = match.group(1)
      if self.config.clean_code_blocks:
        # Remove line numbers from code
        code_content = re.sub(r"^\s*\d+\s*", "", code_content, flags=re.MULTILINE)
        code_content = code_content.strip()

      if code_content:
        code_blocks.append(code_content)

    # Replace code blocks with placeholders in main content
    content_without_code = re.sub(
      code_pattern, "[CODE_BLOCK]", content, flags=re.DOTALL
    )

    return content_without_code, code_blocks

  def _detect_function_sections(self, soup: BeautifulSoup) -> List[ContentSection]:
    """Detect and extract function/method documentation sections"""
    sections = []

    # Common selectors for API documentation
    function_selectors = [
      ".doc-heading",
      ".api-item",
      ".method",
      ".function",
      "h3, h4, h5",  # Function headings
      ".field-list",  # Sphinx documentation
    ]

    # Try to find function/method sections
    for selector in function_selectors:
      elements = soup.select(selector)

      for element in elements:
        # Check if this looks like a function definition
        text = element.get_text()

        # Look for function patterns
        if any(
          pattern in text.lower()
          for pattern in ["def ", "()", "function", "method", "class "]
        ):
          # Extract the section content
          section_content = []
          current = element

          # Collect content until next heading or function
          while current and current.next_sibling:
            current = current.next_sibling
            if isinstance(current, Tag):
              if current.name in ["h1", "h2", "h3", "h4", "h5"] or any(
                cls in current.get("class", [])
                for cls in ["doc-heading", "api-item", "method", "function"]
              ):
                break
              section_content.append(str(current))
            elif isinstance(current, NavigableString):
              section_content.append(str(current))

          if section_content:
            content_html = "".join(section_content)
            content_md = self.html_converter.handle(content_html)
            content_md = self._clean_text(content_md)

            content_without_code, code_blocks = self._extract_code_blocks(content_md)

            if content_without_code.strip():
              sections.append(
                ContentSection(
                  type="function",
                  title=text.strip()[:100],  # Limit title length
                  content=content_without_code,
                  code_blocks=code_blocks,
                  metadata={"selector": selector},
                )
              )

    return sections

  def _extract_structured_content(self, soup: BeautifulSoup) -> List[ContentSection]:
    sections = []

    if not self.config.enable_structured_extraction:
      # Fallback to simple extraction
      content = self.html_converter.handle(str(soup))
      content = self._clean_text(content)
      content_without_code, code_blocks = self._extract_code_blocks(content)

      return [
        ContentSection(
          type="content",
          title="Main Content",
          content=content_without_code,
          code_blocks=code_blocks,
        )
      ]

    for element in soup(
      [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        ".sidebar",
        ".toc",
        ".breadcrumb",
      ]
    ):
      element.decompose()

    # Try to detect function sections first
    function_sections = self._detect_function_sections(soup)
    if function_sections:
      return function_sections

    # Fallback: Extract by headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    if not headings:
      # No structure found, return as single section
      content = self.html_converter.handle(str(soup))
      content = self._clean_text(content)
      content_without_code, code_blocks = self._extract_code_blocks(content)

      return [
        ContentSection(
          type="content",
          title="Main Content",
          content=content_without_code,
          code_blocks=code_blocks,
        )
      ]

    # Extract content by sections between headings
    for _, heading in enumerate(headings):
      title = heading.get_text().strip()

      # Collect content until next heading
      content_elements = []
      current = heading.next_sibling

      while current:
        if isinstance(current, Tag) and current.name in [
          "h1",
          "h2",
          "h3",
          "h4",
          "h5",
          "h6",
        ]:
          break
        content_elements.append(str(current))
        current = current.next_sibling

      if content_elements:
        content_html = "".join(content_elements)
        content_md = self.html_converter.handle(content_html)
        content_md = self._clean_text(content_md)

        content_without_code, code_blocks = self._extract_code_blocks(content_md)

        if content_without_code.strip():
          section_type = "heading"
          if any(
            keyword in title.lower() for keyword in ["example", "usage", "tutorial"]
          ):
            section_type = "example"
          elif any(
            keyword in title.lower()
            for keyword in ["api", "reference", "function", "method"]
          ):
            section_type = "api"

          sections.append(
            ContentSection(
              type=section_type,
              title=title,
              content=content_without_code,
              code_blocks=code_blocks,
              metadata={"heading_level": heading.name},
            )
          )

    return (
      sections
      if sections
      else [
        ContentSection(
          type="content",
          title="Main Content",
          content=self._clean_text(self.html_converter.handle(str(soup))),
          code_blocks=[],
        )
      ]
    )

  def _estimate_tokens(self, text: str) -> int:
    return len(text) // 4

  def _clean_url_for_filename(self, url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    clean_path = re.sub(r"[^a-zA-Z0-9/_-]", "_", path)
    clean_path = re.sub(r"_+", "_", clean_path)
    clean_path = clean_path.strip("_")

    if not clean_path:
      clean_path = "index"

    return clean_path

  def _should_follow_url(self, url: str, base_url: str) -> bool:
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)

    if not self.config.follow_external_links:
      if parsed_url.netloc != parsed_base.netloc:
        return False

    for pattern in self.config.exclude_patterns:
      if re.search(pattern, url, re.IGNORECASE):
        return False

    if self.config.include_patterns:
      for pattern in self.config.include_patterns:
        if re.search(pattern, url, re.IGNORECASE):
          return True
      return False

    return True

  def _extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
    """Extract and structure content from HTML"""

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
      title = title_tag.get_text().strip()

    if not title:
      h1_tag = soup.find("h1")
      if h1_tag:
        title = h1_tag.get_text().strip()

    # Find main content area
    main_content = None
    content_selectors = [
      "main",
      ".content",
      ".documentation",
      ".docs",
      "#content",
      "#main",
      ".main-content",
      "article",
      ".article-content",
    ]

    for selector in content_selectors:
      main_content = soup.select_one(selector)
      if main_content:
        break

    if not main_content:
      main_content = soup.find("body") or soup

    structured_content = self._extract_structured_content(main_content)

    # Create raw content for fallback
    raw_content = self.html_converter.handle(str(main_content))
    raw_content = self._clean_text(raw_content)

    # Statistics
    total_text = raw_content + " ".join([s.content for s in structured_content])
    word_count = len(total_text.split())
    estimated_tokens = self._estimate_tokens(total_text)

    return {
      "title": title,
      "raw_content": raw_content,
      "structured_content": structured_content,
      "word_count": word_count,
      "estimated_tokens": estimated_tokens,
    }

  def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
    """Extract valid links from the page"""
    links = []

    for link in soup.find_all("a", href=True):
      href = link["href"]
      absolute_url = urljoin(base_url, href)
      parsed = urlparse(absolute_url)
      clean_url = urlunparse(parsed._replace(fragment=""))

      if self._should_follow_url(clean_url, base_url):
        links.append(clean_url)

    return list(set(links))

  async def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
    try:
      async with self.session.get(
        url, timeout=aiohttp.ClientTimeout(total=self.config.timeout)
      ) as response:
        if response.status == 200:
          content = await response.text()
          return BeautifulSoup(content, "html.parser")
        else:
          print(f"Failed to fetch {url}: HTTP {response.status}")
          return None
    except Exception as e:
      print(f"Error fetching {url}: {str(e)}")
      return None

  async def _scrape_page(
    self, url: str, depth: int = 0, parent_url: Optional[str] = None
  ) -> Optional[ScrapedPage]:
    if url in self.visited_urls:
      return None

    if depth > self.config.max_depth:
      return None

    if len(self.scraped_pages) >= self.config.max_pages:
      return None

    self.visited_urls.add(url)
    print(f"Scraping (depth {depth}): {url}")

    soup = await self._fetch_page(url)
    if not soup:
      return None

    extracted = self._extract_content(soup, url)

    scraped_page = ScrapedPage(
      url=url,
      title=extracted["title"],
      raw_content=extracted["raw_content"],
      structured_content=extracted["structured_content"],
      scraped_at=datetime.now().isoformat(),
      depth=depth,
      parent_url=parent_url,
      word_count=extracted["word_count"],
      estimated_tokens=extracted["estimated_tokens"],
    )

    self.scraped_pages.append(scraped_page)

    print(
      f"Extracted {len(extracted['structured_content'])} sections"
      f"{extracted['word_count']} words"
      f"~{extracted['estimated_tokens']} tokens"
    )

    await asyncio.sleep(self.config.delay_between_requests)
    return scraped_page

  async def _scrape_recursively(
    self, url: str, depth: int = 0, parent_url: Optional[str] = None
  ):
    scraped_page = await self._scrape_page(url, depth, parent_url)
    if not scraped_page:
      return

    if (
      depth < self.config.max_depth and len(self.scraped_pages) < self.config.max_pages
    ):
      soup = await self._fetch_page(url)
      if soup:
        links = self._extract_links(soup, url)

        semaphore = asyncio.Semaphore(3)

        async def limited_scrape(link):
          async with semaphore:
            await self._scrape_recursively(link, depth + 1, url)

        tasks = [
          limited_scrape(link) for link in links if link not in self.visited_urls
        ]

        await asyncio.gather(*tasks)

  def _save_to_disk(self, output_path: Path, base_url: str) -> Dict:
    output_path.mkdir(parents=True, exist_ok=True)

    summary = {
      "base_url": base_url,
      "total_pages": len(self.scraped_pages),
      "total_sections": sum(
        len(page.structured_content) for page in self.scraped_pages
      ),
      "total_words": sum(page.word_count for page in self.scraped_pages),
      "estimated_tokens": sum(page.estimated_tokens for page in self.scraped_pages),
      "scraped_at": datetime.now().isoformat(),
      "config": self.config.model_dump(),
    }

    with open(output_path / "summary.json", "w", encoding="utf-8") as f:
      json.dump(summary, f, indent=2, ensure_ascii=False)

    # Save pages
    for page in self.scraped_pages:
      relative_path = self._clean_url_for_filename(page.url)

      if "/" in relative_path:
        parts = relative_path.split("/")
        file_name = parts[-1] if parts[-1] else "index"
        dir_path = output_path / "/".join(parts[:-1]) if len(parts) > 1 else output_path
      else:
        file_name = relative_path if relative_path else "index"
        dir_path = output_path

      dir_path.mkdir(parents=True, exist_ok=True)

      file_path = dir_path / f"{file_name}.json"
      counter = 1
      original_file_path = file_path
      while file_path.exists():
        name = original_file_path.stem
        file_path = dir_path / f"{name}_{counter}.json"
        counter += 1

      with open(file_path, "w", encoding="utf-8") as f:
        json.dump(page.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"Saved {len(self.scraped_pages)} pages to {output_path}")
    print(f"Total sections: {summary['total_sections']}")
    print(f"Total estimated tokens: {summary['estimated_tokens']}")

    return summary

  async def scrape_website(
    self,
    base_url: str | HttpUrl,
    index_name: str,
    send_to_bucket: bool = False,
    output_dir: str = "data",
  ) -> Result[Dict, str]:
    base_url = str(base_url)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    summary = {}

    connector = aiohttp.TCPConnector(limit=10, limit_per_host=3)
    self.session = aiohttp.ClientSession(
      connector=connector, headers={"User-Agent": "Documentation Scraper"}
    )

    if not index_name:
      return Err("Index name cannot be empty")

    try:
      output_path = Path(index_name) / Path(output_dir)

      self.base_domain = urlparse(base_url).netloc

      print(f"Scraping {base_url}. Base domain: {self.base_domain}")
      start_time = time.time()

      await self._scrape_recursively(base_url)

      end_time = time.time()
      print(
        f"Scraped {len(self.scraped_pages)} pages in {end_time - start_time:.2f} seconds"
      )

      summary: Dict = self._save_to_disk(output_path, base_url)
      if send_to_bucket:
        upload_result: Result[None, str] = await upload_to_s3(output_path)
        if isinstance(upload_result, Err):
          print(f"Error: S3 upload failed: {upload_result.err()}")  # TODO:

    finally:
      await self.session.close()
      return Ok(summary)

  def get_scraped_data(self) -> List[ScrapedPage]:
    return self.scraped_pages
