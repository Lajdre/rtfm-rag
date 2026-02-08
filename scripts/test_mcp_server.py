#!/usr/bin/env python3
"""
Quick-and-dirty MCP client for testing the server.
Usage: python -m scripts.test_mcp_server
"""

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


async def main():
  params = StdioServerParameters(
    command="python",
    args=["-m", "src.rtfm_rag.mcp.mcp_server"],
    env={"PYTHONPATH": "src"},
  )

  async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
      await session.initialize()

      tools = await session.list_tools()
      print("Tools:", [t.name for t in tools.tools])

      result = await session.call_tool(
        "fetch_docs_candidate_context",
        arguments={
          "query": "How do I create a simple model in tinygrad?",
          "index_name": "docs_tinygrad_org",
        },
      )
      print("Tool result:\n")
      content = result.content[0]
      if isinstance(content, TextContent):
        print(content.text)
      else:
        print("Non-text result:", content)


if __name__ == "__main__":
  asyncio.run(main())
