# KnowledgeGraph

KnowledgeGraph converts unstructured text/PDF input into structured relationship data and optional graph inserts.

Outputs per run:
- `output/<title>_extracted.json`
- `output/<title>_falkordb.cypher`

The pipeline now supports OPORD-focused extraction (enemy/friendly sections, commander's intent, key tasks, timelines, concept of operations, and scheme of fires) and an HTTP API for UI retrieval.

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
- Run HTTP API for UI integration: `uv run api`

## Recent Behavior Updates

- `uv run pipeline` now publishes an ingest event to Redis after each FalkorDB load attempt when `PUBLISH_REDIS_ON_INGEST=true`.
- Files are now marked as processed only when FalkorDB writes succeed (or there are zero generated queries). Failed graph writes are retried on the next pipeline run.
- Empty files are marked as processed so they do not repeatedly show up as new work.
- Extraction-to-graph conversion now enforces non-empty required relation fields (`actor_a`, `actor_b`, `relation_type`).
- For missing actor types, the pipeline now attempts lightweight inference (including common abbreviations such as `sqd`, `wpn`, `obj`, `eny`) before deciding to skip.
- OPORD extraction now captures section-aware content including enemy/friendly sections, commander's intent, key tasks, timelines, concept of operations, and scheme of fires.
- Graph writes now include `Document-[:MENTIONS]->Actor` links so UI queries can scope actors to a specific OPORD/document title.
- API endpoints are available for direct UI retrieval from FalkorDB (no Redis required for reads).

## Which mode should I use?

| Need | Use | Why |
|---|---|---|
| Process files dropped into a folder, then exit | `uv run pipeline` | Simple batch workflow for local runs, cron jobs, or CI tasks |
| Keep a long-running endpoint your app can send text to | `uv run service` | Runs continuously and processes Redis messages in real time |
| Manually test Redis requests/responses from terminal | `uv run publisher` | Lightweight interactive test client for service mode |
| Let a UI retrieve graph data over HTTP | `uv run api` | Exposes mission-focused GET endpoints backed by FalkorDB |

Most users only need **one** mode:
- Use **pipeline mode** for file-based workflows.
- Use **service mode** for product integrations that already use Redis messaging.
- Use **api mode** when a frontend/UI needs direct JSON access to OPORD data in FalkorDB.

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
FALKORDB_BROWSER_URL=http://localhost:3000

# Input processing
INPUT_DIR=input
WATCH_INPUT_FILES=false

# Pipeline ingest event publishing (after FalkorDB writes)
PUBLISH_REDIS_ON_INGEST=true
REDIS_PUBLISH_CHANNEL=ie_response

# API server (HTTP)
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=*
```

Notes:
- `INPUT_DIR` defaults to repo-root `input/`.
- `AUTO_LOAD_FALKORDB` only affects Redis service mode.
- `USE_FALKORDB=true` makes `uv run pipeline` automatically load generated queries into FalkorDB.
- The pipeline tracks previously processed files with `input/.processed`.
- `FALKORDB_PORT` is the graph query port (Redis/Falkor protocol), not the browser UI port.
- If a file contains content but graph writes fail, it remains eligible for retry on the next run.
- `API_HOST=0.0.0.0` allows other machines to connect when network/firewall rules permit.
- Set `API_CORS_ORIGINS` to your frontend origin in shared/prod environments (for example, `http://ares.westpoint.edu:3000`).

Optional link output:
- Set `FALKORDB_BROWSER_URL` to print a clickable graph link in terminal output after successful loads.
- Supported placeholders: `{host}`, `{port}`, `{graph}`
- Example: `FALKORDB_BROWSER_URL=http://localhost:3000/graph/{graph}`

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

3. **API integration (HTTP for UI)**
   - Run `uv run api`.
   - Point your frontend to `http://<host>:<port>`.
   - Retrieve OPORD data through REST endpoints (examples below).

## OPORD extraction output schema

`output/<title>_extracted.json` now includes:
- `title`
- `commanders_intent`
- `concept_of_operations`
- `scheme_of_fires`
- `key_tasks` (list)
- `timelines` (list)
- `sections` (header + key points)
- `actors` and `relations`

This allows both graph queries and direct JSON consumers to access section context and mission details.

## API endpoints

Health:
- `GET /health`

Mission-focused endpoints:
- `GET /api/opord-summary?title=<opord title>`
- `GET /api/commanders-guidance?title=<opord title>`
- `GET /api/enemy?title=<opord title>`
- `GET /api/key-tasks?title=<opord title>`
- `GET /api/timelines?title=<opord title>`
- `GET /api/concept-of-operations?title=<opord title>`
- `GET /api/scheme-of-fires?title=<opord title>`
- `GET /api/sections?title=<opord title>&header=<optional filter>`
- `GET /api/actors?actor_type=<optional type filter>`

Quick test examples (PowerShell):
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/opord-summary?title=operation%20bobcat%20lightning" | ConvertTo-Json -Depth 7
```

Interactive docs:
- Swagger UI: `http://127.0.0.1:8000/docs`

## Running API on ARES (shared access)

If other machines need access, run API on ARES and open the API port:

1. On ARES, set:
```env
API_HOST=0.0.0.0
API_PORT=8000
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_GRAPH=KnowledgeGraphTest
```

2. Start API:
```bash
uv run api
```

3. From another machine:
- `http://ares.westpoint.edu:8000/health`
- `http://ares.westpoint.edu:8000/api/opord-summary?title=operation%20bobcat%20lightning`

4. Ensure inbound TCP `8000` is allowed by host/network firewall rules.

## Files that matter

- `src/main_pipeline/run_pipeline.py` — one-shot processing entrypoint
- `src/main_pipeline/app.py` — Redis service entrypoint
- `src/main_pipeline/api.py` — HTTP API entrypoint for UI queries
- `src/main_pipeline/dspy_extractor.py` — extraction + normalization logic
- `src/main_pipeline/input_processor.py` — file watching/change detection
- `src/main_pipeline/falkordb_client.py` — graph write/query wrapper

## Troubleshooting

- No files processed: check `INPUT_DIR` and supported extensions.
- Model errors: validate `OLLAMA_API_BASE` and `OLLAMA_MODEL`.
- Redis connection errors: check `REDIS_HOST`/`REDIS_PORT`.
- FalkorDB errors: check host/port/graph and disable with `USE_FALKORDB=false` if not needed.

## Release notes

See `CHANGELOG.md` for release history and implementation notes.
