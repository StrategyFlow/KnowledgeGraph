# KnowledgeGraph

KnowledgeGraph converts unstructured text and PDF inputs into structured OPORD data and optional FalkorDB graph inserts.

Each run generates:
- `output/<title>_extracted.json`
- `output/<title>_falkordb.cypher`

## Fastest path (copy/paste)

Use this if you just want extraction working in a few minutes.

1. Install dependencies:
```bash
uv sync
```

2. Create your local config:
```powershell
Copy-Item example.env .env
```

3. Set minimum `.env` values:
```env
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=gemma3:latest
USE_FALKORDB=false
```

4. Put a `.txt`, `.md`, `.json`, or `.pdf` in `input/`.

5. Run once:
```bash
uv run pipeline
```

6. Check output:
- `output/<title>_extracted.json`
- `output/<title>_falkordb.cypher`

## Choose your mode

Use one command based on your integration style:

- `uv run pipeline`
Purpose: process files in `input/` once and exit.

- `uv run service`
Purpose: run a long-lived Redis listener service.

- `uv run publisher`
Purpose: send local Redis test messages.

- `uv run load-graph`
Purpose: load extracted JSON output into FalkorDB.

- `uv run api`
Purpose: run REST API for frontend/UI reads.

## API quick start

1. Start API:
```bash
uv run api
```

2. Verify service health:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" | ConvertTo-Json -Depth 5
```

3. Try OPORD summary:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/opord-summary?title=operation%20bobcat%20lightning" | ConvertTo-Json -Depth 7
```

Interactive docs:
- Swagger UI: `http://127.0.0.1:8000/docs`

## API endpoints

Health:
- `GET /health`

Phase endpoints (title optional):
- `GET /api/situation?title=<optional opord title>`
- `GET /api/mission?title=<optional opord title>`
- `GET /api/execution?title=<optional opord title>`
- `GET /api/sustainment?title=<optional opord title>`
- `GET /api/command-and-signal?title=<optional opord title>`

Phase endpoint behavior:
- If `title` is omitted, results may include matching sections across documents.
- If `title` is provided, results are scoped to that OPORD.

Summary and detail endpoints:
- `GET /api/opord-summary?title=<opord title>`
- `GET /api/enemy?title=<opord title>`
- `GET /api/key-tasks?title=<opord title>`
- `GET /api/timelines?title=<opord title>`
- `GET /api/concept-of-operations?title=<opord title>`
- `GET /api/scheme-of-fires?title=<opord title>`
- `GET /api/sections?title=<opord title>&header=<optional filter>`
- `GET /api/actors?actor_type=<optional type filter>`

## Output schema (high level)

`output/<title>_extracted.json` includes:
- `title`
- `commanders_intent`
- `concept_of_operations`
- `scheme_of_fires`
- `key_tasks`
- `timelines`
- `sections`
- `actors`
- `relations`

## Environment variables

Start from `example.env` and adjust only what you need.

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
FALKORDB_BROWSER_URL=http://localhost:3000

# Input processing
INPUT_DIR=input
WATCH_INPUT_FILES=false

# Pipeline ingest event publishing (after FalkorDB writes)
PUBLISH_REDIS_ON_INGEST=true
REDIS_PUBLISH_CHANNEL=ie_response

# API server
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=*
```

Important notes:
- `INPUT_DIR` defaults to repo-root `input/`.
- `USE_FALKORDB=true` makes `uv run pipeline` attempt graph loading.
- `FALKORDB_PORT` is the query port, not the FalkorDB browser UI port.
- If graph writes fail, processed-file tracking keeps the file eligible for retry.
- For shared deployments, set a specific `API_CORS_ORIGINS` value (not `*`).

Optional graph link output:
- Set `FALKORDB_BROWSER_URL` to print a clickable graph URL after successful loads.
- Placeholders supported: `{host}`, `{port}`, `{graph}`
- Example: `FALKORDB_BROWSER_URL=http://localhost:3000/graph/{graph}`

## Deploying API for shared access (ARES example)

1. Set:
```env
API_HOST=0.0.0.0
API_PORT=8000
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_GRAPH=KnowledgeGraphTest
```

2. Run:
```bash
uv run api
```

3. Test from another machine:
- `http://ares.westpoint.edu:8000/health`
- `http://ares.westpoint.edu:8000/api/opord-summary?title=operation%20bobcat%20lightning`

4. Ensure inbound TCP 8000 is allowed by firewall/network policy.

## File map

- `src/main_pipeline/run_pipeline.py`: one-shot file pipeline entrypoint
- `src/main_pipeline/app.py`: Redis service entrypoint
- `src/main_pipeline/api.py`: HTTP API entrypoint
- `src/main_pipeline/dspy_extractor.py`: extraction and normalization
- `src/main_pipeline/input_processor.py`: input file detection and processing state
- `src/main_pipeline/falkordb_client.py`: FalkorDB wrapper

## Troubleshooting

- Nothing processed: verify `INPUT_DIR` and file extensions.
- Model failures: verify `OLLAMA_API_BASE` and `OLLAMA_MODEL`.
- Redis failures: verify `REDIS_HOST` and `REDIS_PORT`.
- FalkorDB failures: verify `FALKORDB_HOST`, `FALKORDB_PORT`, and `FALKORDB_GRAPH`.
- API start failures: check whether another process already uses `API_PORT`.

## Public repo safety checklist

Before publishing publicly:
- Keep `.env` private. Commit only `example.env` placeholders.
- Do not commit real OPORD source files in `input/`.
- Do not commit sensitive extracted outputs in `output/`.
- Rotate credentials if any real key/token was ever committed.
- Restrict `API_CORS_ORIGINS` in shared or production environments.

## Release notes

See `CHANGELOG.md` for full change history.
