set dotenv-load

PORT := env("SERVER_PORT", "8032")
ARGS_SERVE := env("_UV_RUN_ARGS_SERVE", "")
ARGS_TEST := env("_UV_RUN_ARGS_TEST", "")

@_:
  just --list



# Run development server
[group('run')]
serve:
  uv run {{ ARGS_SERVE }} -m fastapi dev src/rtfm_rag/main.py --port {{ PORT }}

# Open development server in web browser
[group('run')]
browser:
  uv run -m webbrowser -t http://127.0.0.1:{{ PORT }}



# Launch the database
[group('infra')]
db-up:
  devenv up -d

# Shut down the database
[group('infra')]
db-down:
  devenv down



# Run tests
[group('qa')]
test *args:
  PYTHONPATH=src uv run {{ ARGS_TEST }} -m pytest {{ args }}



# Scrape data from a website. Usage: scrape <url> <index_name> [--debug] [--max-depth N] [--max-pages N]
[group('scripts')]
scrape url index_name *args:
  PYTHONPATH=src uv run -m scripts.scrape_data {{url}} {{index_name}} {{args}}

# Send scraped data to S3
[group('scripts')]
send-s3 target_dir:
  PYTHONPATH=src uv run -m scripts.send_to_s3 {{target_dir}}

# Ingest the scraped data into the databse. Usage: store-scraped <index_name> [--debug] [--max-chunks N]
[group('scripts')]
store-scraped index_name *args:
  PYTHONPATH=src uv run -m scripts.store_scraped_data {{index_name}} {{args}}

# Test the MCP server/tool
[group('scripts')]
test-mcp:
  PYTHONPATH=src uv run -m scripts.test_mcp_server
