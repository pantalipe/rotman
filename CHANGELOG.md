# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- `topic_queue.py` — topic queue module managing `db/queue.json` with full item
  lifecycle (pending → processing → done/error), batch input and process-next flow
- Queue tab in the web UI — batch topic textarea, stats bar (pending/processing/done/error),
  process-next button, per-item status and direct link to the pipeline project when processed
- Queue API endpoints: `GET/POST /api/queue`, `POST /api/queue/process`,
  `POST /api/queue/clear_done`, `DELETE /api/queue/<id>`
- `personas/` directory with per-channel tone and language instructions
- `personas/persona_bitcoinfacil.txt` — warm, educational, pt-BR tone for general Bitcoin audience
- `personas/persona_pandapoints.txt` — product-focused, semi-formal Web3 tone for PandaPoints content
- `core/llm.py` now auto-loads the persona for the selected channel and injects
  Tone + Language sections into the system prompt before script generation
- `_validate_scenes()` and `_fix_scenes()` in `core/llm.py` — validates required scene
  fields and attempts auto-repair before retrying
- `_repair_truncated_json()` in `core/llm.py` — fourth JSON extraction strategy that
  recovers partial responses by closing open brackets at the last complete scene
- `_get_image_prompt()` helper in `pipeline.py` — safe multi-key fallback for missing
  `image_prompt` fields; builds a narration-based default rather than crashing

### Changed
- `pipeline.py` imports renamed from `queue` to `topic_queue` to avoid shadowing
  the Python stdlib `queue` module (which caused `ImportError` in `edge_tts`)
- Scene count reduced from 8–12 to exactly 6 in `core/llm.py` — reduces JSON size
  and token pressure, sufficient for 60s videos
- `num_predict` increased to 4096 and `num_ctx` to 8192 in `ollama.chat()` calls —
  prevents truncated JSON responses on longer prompts
- Persona injection now uses only Tone + Language sections (not the full file) to
  keep prompt size compact
- `RETRY_PROMPT` updated to explicitly require `image_prompt` in every scene object

### Fixed
- `KeyError: 'image_prompt'` crash in `pipeline.py` when model omitted the field
- Truncated JSON responses causing all 3 generation attempts to fail
- `ImportError: cannot import name 'Queue' from 'queue'` — caused by `queue.py`
  filename shadowing the stdlib module; fixed by renaming to `topic_queue.py`

---

## [v2.0] — 2026-03

Complete rewrite with modular architecture, web UI and full pipeline automation.

### Added
- Web UI served at `http://localhost:7070` — project management, pipeline status and log in real time
- `pipeline.py` — pipeline orchestrator running in a background thread (non-blocking)
- `core/llm.py` — LLM script generation via Ollama with retry logic and multi-strategy JSON extraction
- `core/tts.py` — TTS narration via edge-tts (PT-BR and EN voices, free and unlimited)
- `core/imgen.py` — image generation with dual mode: HuggingFace SDXL API (fast) + diffusers CPU fallback (offline)
- `core/editor.py` — video assembly via MoviePy v2 with per-scene audio sync
- `server.py` — HTTP server using Python stdlib only (zero external server dependencies)
- `db/projects.json` — local JSON database for project state persistence
- Retry and recover: failed projects can be retried from scratch via UI
- `HF_TOKEN` environment variable for SDXL API fallback

### Architecture
- Modular `core/` layer: each pipeline step is an independent module
- Pipeline runs in a `daemon=True` thread — UI never blocks during generation
- All output isolated per project under `output/<project_id>/`

---

## [v1.0]

Initial prototype — linear script, no web interface.

### Features
- CLI-only workflow
- Basic Ollama integration for script generation
- Manual TTS and image generation steps
- MoviePy v1 for video assembly
