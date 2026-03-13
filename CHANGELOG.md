# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- OPORD-focused extraction fields in `dspy_extractor.py` output JSON:
  - `commanders_intent`
  - `concept_of_operations`
  - `scheme_of_fires`
  - `key_tasks`
  - `timelines`
  - section-aware `sections` payload with key points.
- New HTTP API service in `src/main_pipeline/api.py` using FastAPI + Uvicorn.
- New API script alias in `pyproject.toml`: `uv run api`.
- Mission-focused read endpoints for UI integration:
  - `/health`
  - `/api/opord-summary`
  - `/api/commanders-guidance`
  - `/api/enemy`
  - `/api/key-tasks`
  - `/api/timelines`
  - `/api/concept-of-operations`
  - `/api/scheme-of-fires`
  - `/api/sections`
  - `/api/actors`
- New API runtime dependencies in `pyproject.toml`:
  - `fastapi`
  - `uvicorn`

### Changed
- Extraction prompt updated to improve OPORD coverage of enemy/friendly context, timelines, key tasks, concept of operations, and scheme of fires while preserving stable model response behavior.
- Graph write behavior updated to add document scoping links for actors:
  - `(:Document)-[:MENTIONS]->(:Actor)`
- Section writes now persist joined section key points into `Section.content` instead of placeholder values.
- README updated with API workflow, endpoint catalog, OPORD schema notes, and ARES deployment guidance.

### Validation
- `uv sync` succeeds after dependency updates.
- `uv run pipeline` succeeds with OPORD PDF input and writes expanded extraction output.
- FalkorDB ingest succeeds for full generated query set in latest OPORD run.
- API smoke tests succeed for:
  - `/health`
  - `/api/commanders-guidance`
  - `/api/enemy`
  - `/api/key-tasks`
  - `/api/opord-summary`

## [2026-02-17] - Simplify onboarding and streamline runtime workflow

### Added
- User-friendly script aliases in `pyproject.toml`:
  - `uv run pipeline`
  - `uv run service`
  - `uv run publisher`
  - `uv run load-graph`
- Quickstart-first documentation with clearer integration guidance.
- Runtime artifact ignore rules for cleaner local development (`input/`, `output/`, `*.processed`).

### Changed
- Improved project description and onboarding flow.
- Updated README to focus on fastest successful path and larger-product integration patterns.
- Added synchronous wrappers for async entrypoints so command aliases run reliably.

### Removed
- Empty legacy artifact file `src/main_pipeline/infoOutput.json`.
- Redundant empty package subfolders and cached artifacts from tracked source layout.

### Validation
- `uv sync` succeeds.
- `uv run python -m compileall src` succeeds.
- `uv run pipeline` executes successfully (clean no-new-files behavior and prior smoke-tested processing).
