# Changelog

All notable changes to this project are documented in this file.

## [v2.0] — current

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
- Scheduled posting fields (platform targets and date) — ready for future API integration
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
