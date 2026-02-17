# KnowledgeGraph

KnowledgeGraph extracts structured relationship data from text (and PDFs), saves normalized JSON + Cypher output files, and can optionally load that data into FalkorDB.

It supports two ways to run:

1. **Batch pipeline mode**: process files in an input directory one time.
2. **Redis listener mode**: listen on Redis pub/sub, process incoming requests, and publish responses.

---

## What it does

- Uses DSPy + an Ollama-compatible chat endpoint to extract:
	- `title`
	- `actor_types`, `role_types`, `relation_types`
	- `actors` and `relations`
- Normalizes and deduplicates extraction output.
- Writes:
	- `output/<title>_extracted.json`
	- `output/<title>_falkordb.cypher`
- Optionally executes generated Cypher directly in FalkorDB.

---

## Project layout

- `src/london_project/run_pipeline.py` — one-shot file processing pipeline.
- `src/london_project/app.py` — Redis pub/sub listener service (`ie_request` -> `ie_response`).
- `src/london_project/publish.py` — simple interactive Redis publisher/listener.
- `src/london_project/load_to_falkordb.py` — load previously generated JSON into FalkorDB.
- `src/london_project/input/` — drop files here for file-based processing.
- `src/london_project/output/` — generated output artifacts.

---

## Prerequisites

- Python 3.11+
- `uv` package manager
- Access to an Ollama-compatible API endpoint
- Optional:
	- Redis server (for Redis listener mode)
	- FalkorDB (for graph loading)

Install `uv` (Windows):

```powershell
winget install Astral.uv
```

---

## Setup

From the `KnowledgeGraph` directory:

```bash
uv sync
```

Update your `.env` values (example keys used by this project):

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

> `AUTO_LOAD_FALKORDB` controls whether Redis mode writes to FalkorDB automatically.

---

## How to use

### Option A: Batch pipeline mode (recommended for local file processing)

1. Add `.txt`, `.md`, `.json`, or `.pdf` files to your input folder (default: `input`).
2. Run:

```bash
uv run -m london_project.run_pipeline
```

3. Check generated outputs in `output/`.

The pipeline tracks processed files with a `.processed` marker and only reprocesses files that are new or changed.

### Option B: Redis listener mode (service/integration workflow)

Start the service:

```bash
uv run main
```

In a second terminal, send requests and receive responses interactively:

```bash
uv run -m london_project.publish
```

Channels used:

- Request: `ie_request`
- Response: `ie_response`

If `WATCH_INPUT_FILES=true`, the service also watches the input folder continuously.

---

## Manual loading into FalkorDB

If you already have extracted JSON files in `output/`, you can load one manually:

```bash
uv run -m london_project.load_to_falkordb
```

---

## Docker

A Dockerfile is included. It installs dependencies with `uv` and starts:

```bash
uv run main
```

Build and run example:

```bash
docker build -t knowledgegraph .
docker run --env-file .env knowledgegraph
```

---

## Common issues

- **No files processed**: verify files are in `INPUT_DIR` and have supported extensions.
- **PDF parsing skipped**: ensure `docling` is installed (included in dependencies).
- **Redis connection errors**: verify `REDIS_HOST`/`REDIS_PORT`.
- **FalkorDB errors**: verify `FALKORDB_HOST`/`FALKORDB_PORT` and graph permissions.
- **Model/API errors**: verify `OLLAMA_API_BASE`, `OLLAMA_MODEL`, and endpoint availability.
