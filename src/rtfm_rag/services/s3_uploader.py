from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from result import Err, Ok, Result

from ..core.config import config


async def upload_to_s3(target_dir: Path) -> Result[None, str]:
  """
  Recursively uploads all .json files in target_dir to S3.
  The name (key) of the stored object its relative path to target_dir without its last directory
  "data/index/file.json" -> "index/file.json"
  """
  target_dir = Path(target_dir)
  if not target_dir.is_dir():
    return Err(
      f"Err in upload_to_s3: target dir should be a valid directory: {target_dir}"
    )

  try:
    s3 = boto3.client(
      "s3",
      aws_access_key_id=config.AWS_ACCESS_KEY_ID,
      aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
      region_name=config.AWS_REGION,
    )
  except Exception as e:
    return Err(f"Failed to create S3 client: {e}")

  bucket = config.AWS_S3_BUCKET_NAME
  target_dir_no_last_dir: Path = target_dir.parent

  try:
    for file_path in target_dir.rglob("*.json"):
      if file_path.is_file():
        try:
          s3.upload_file(
            str(file_path), bucket, str(file_path.relative_to(target_dir_no_last_dir))
          )
        except NoCredentialsError:
          return Err("Err in upload_to_s3: credentials not available for aws")
        except ClientError as e:
          return Err(f"Err in upload_to_s3: client error occurred: {e}")
  except Exception as e:
    return Err(f"Error walking directory: {e}")

  return Ok(None)
