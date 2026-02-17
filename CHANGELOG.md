# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Placeholder for upcoming changes.

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
