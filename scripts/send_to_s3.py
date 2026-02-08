#!/usr/bin/env python3
"""Script for sending all json files in a specified dir to S3 bucket.

Usage: python -m scripts.send_to_s3 <target_dir>
"""

import argparse
import asyncio
from pathlib import Path

from result import Err, Result

from rtfm_rag.services.s3_uploader import upload_to_s3


async def main() -> None:
  parser = argparse.ArgumentParser(description="Upload scraped data to S3")
  parser.add_argument("target_dir", help="Target directory for upload")
  args = parser.parse_args()

  print(f"Starting upload for target_dir: {args.target_dir}")

  upload_result: Result[None, str] = await upload_to_s3(Path(args.target_dir))
  if isinstance(upload_result, Err):
    print(f"Error: S3 upload failed: {upload_result.err()}")
  else:
    print("S3 upload completed successfully")


if __name__ == "__main__":
  asyncio.run(main())
