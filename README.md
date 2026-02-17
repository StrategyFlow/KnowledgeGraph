# KnowledgeGraph

KnowledgeGraph converts unstructured text/PDF input into structured relationship data and optional graph inserts.

Outputs per run:
- `output/<title>_extracted.json`
- `output/<title>_falkordb.cypher`

## Quick start (2 minutes)

1. Install dependencies:
```bash
uv sync
```

2. Create local config:
```powershell
Copy-Item example.env .env
```

3. Edit `.env` (set your model endpoint at minimum):
```env
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=gemma3:latest
USE_FALKORDB=false
```

4. Drop a `.txt`, `.md`, `.json`, or `.pdf` file into `input/`.

5. Run the pipeline:
```bash
uv run pipeline
```

6. Inspect generated files in `output/`.

## One-command workflows

- Run file pipeline once: `uv run pipeline`
- Run Redis listener service: `uv run service` (same as `uv run main`)
- Open local pub/sub test client: `uv run publisher`
- Load extracted JSON into FalkorDB: `uv run load-graph`

## Environment variables

Start with `example.env`, then adjust as needed:

```env
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Ollama-compatible endpoint
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_API_KEY=
OLLAMA_MODEL=gemma3:latest

# FalkorDB
USE_FALKORDB=true
AUTO_LOAD_FALKORDB=true
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_GRAPH=KnowledgeGraph

# Input processing
INPUT_DIR=input
WATCH_INPUT_FILES=false
```

Notes:
- `INPUT_DIR` defaults to repo-root `input/`.
- `AUTO_LOAD_FALKORDB` only affects Redis service mode.
- The pipeline tracks previously processed files with `input/.processed`.

## Integration guide (larger product)

Use one of these integration patterns:

1. **Batch integration**
   - Write files into `input/` (or your configured `INPUT_DIR`).
   - Trigger `uv run pipeline` from your job runner.
   - Consume `output/*_extracted.json` as your structured payload.

2. **Service integration (Redis)**
   - Run `uv run service` as a background service.
   - Publish text payloads to channel `ie_request`.
   - Read structured responses from channel `ie_response`.

## Files that matter

- `src/london_project/run_pipeline.py` — one-shot processing entrypoint
- `src/london_project/app.py` — Redis service entrypoint
- `src/london_project/dspy_extractor.py` — extraction + normalization logic
- `src/london_project/input_processor.py` — file watching/change detection
- `src/london_project/falkordb_client.py` — graph write/query wrapper

## Troubleshooting

- No files processed: check `INPUT_DIR` and supported extensions.
- Model errors: validate `OLLAMA_API_BASE` and `OLLAMA_MODEL`.
- Redis connection errors: check `REDIS_HOST`/`REDIS_PORT`.
- FalkorDB errors: check host/port/graph and disable with `USE_FALKORDB=false` if not needed.
