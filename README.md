# Rotman

Local pipeline for automated short-form video generation. Given a topic, Rotman writes the script, generates narration audio, creates images for each scene and assembles the final video — all running on your own hardware, no cloud costs.

Built for the [bitcoinfacil](https://www.youtube.com/@bitcoinfacil) and [PandaPoints](https://pandapointscoin.com) channels.

---

## How it works

```
Topic (user input or queue)
      │
      ▼
  [Ollama]  →  structured script (JSON) + channel persona
      │
      ├──▶  [edge-tts]   →  narration audio per scene
      ├──▶  [diffusers]  →  image per scene (CPU)
      └──▶  [MoviePy]    →  final .mp4
```

Everything runs locally in a background thread. A web UI served at `http://localhost:7070` lets you manage projects, add topics to a queue and track pipeline progress in real time.

---

## Stack

| Layer | Library | Notes |
|---|---|---|
| LLM | [Ollama](https://ollama.com) | phi3 default, swap freely |
| TTS | [edge-tts](https://github.com/rany2/edge-tts) | PT-BR, free, unlimited |
| Text-to-Image | [diffusers](https://github.com/huggingface/diffusers) | CPU mode, SD 1.5 |
| Video editing | [MoviePy v2](https://github.com/Zulko/moviepy) | pure CPU |
| Server | Python stdlib `http.server` | zero dependencies |

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- A model pulled in Ollama (default: `phi3`)

---

## Setup

```bash
# 1. Clone
git clone https://github.com/pantalipe/rotman.git
cd rotman

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the default model (if you don't have it yet)
ollama pull phi3
```

---

## Running

```bash
python server.py
```

Open **http://localhost:7070** in your browser.

---

## Usage

### Single video

1. Click **+ New Video**
2. Select the channel and describe the video
3. Click **Generate** — the pipeline runs automatically:
   - Script is written by the LLM using the channel persona
   - Audio narration is synthesized for each scene
   - One image is generated per scene
   - Final video is assembled
4. Track progress in real time via the pipeline log

### Topic queue

1. Open the **Queue** tab
2. Enter one topic per line in the batch textarea and select the channel
3. Click **Add** — all topics are saved with status `pending`
4. Click **▶ Process Next** to start the next pending item
5. The item status updates to `processing` and a pipeline project is created automatically
6. Click **View →** on any processed item to open its pipeline project

> Scheduling and social media posting are handled by a separate tool — [conduler](https://github.com/pantalipe/conduler).

---

## Channel personas

Rotman supports per-channel tone and language configuration via persona files in `personas/`.

| File | Channel | Description |
|---|---|---|
| `persona_bitcoinfacil.txt` | bitcoinfacil | Warm, educational, pt-BR — Bitcoin for general audiences |
| `persona_pandapoints.txt` | PandaPoints | Product-focused, semi-formal Web3 tone |

To add a new channel persona, create `personas/persona_<channel_slug>.txt` following the same structure. The slug must match the channel name used in the UI (lowercase, spaces replaced with underscores).

---

## Environment variables

| Variable | Description |
|---|---|
| `HF_TOKEN` | HuggingFace token — enables SDXL API as a faster image generation fallback |

Without `HF_TOKEN`, images are generated locally via diffusers on CPU. Slower, but unlimited and fully offline.

---

## Project structure

```
rotman/
├── server.py           # HTTP server (stdlib only)
├── pipeline.py         # Pipeline orchestrator (background thread)
├── topic_queue.py      # Topic queue — batch input and process-next flow
├── requirements.txt
├── core/
│   ├── llm.py          # Script generation via Ollama + persona injection
│   ├── tts.py          # Audio narration via edge-tts
│   ├── imgen.py        # Image generation (diffusers CPU + HF API fallback)
│   └── editor.py       # Video assembly via MoviePy
├── personas/
│   ├── persona_bitcoinfacil.txt
│   └── persona_pandapoints.txt
├── ui/
│   └── index.html      # Web interface (Projects + Queue tabs)
├── db/                 # Local JSON database (gitignored)
└── output/             # Generated videos, images and audio (gitignored)
```

---

## Hardware

Developed and tested on:

| Component | Spec |
|---|---|
| CPU | Intel Xeon E3-1230 V2 |
| RAM | 8 GB |
| GPU | NVIDIA GT 730 (not used) |

All pipeline steps run on CPU. The GPU is not used — diffusers runs in float32 CPU mode with attention slicing enabled to reduce memory pressure.

**Expected times on similar hardware:**

| Step | Time |
|---|---|
| Script generation (Ollama/phi3) | ~30–60s |
| Audio narration per scene (edge-tts) | ~2–5s |
| Image generation per scene (diffusers CPU) | ~5–10 min |
| Video assembly (MoviePy) | ~1–2 min |

A 6-scene video takes roughly **1–2 hours** end-to-end on CPU-only hardware, dominated by image generation. Using `HF_TOKEN` for the SDXL API fallback reduces image generation to seconds.

16 GB RAM is recommended if running Ollama and diffusers simultaneously to avoid swap.

---

## Roadmap

- [x] Per-channel voice and tone configuration (personas)
- [x] Topic queue with batch input and process-next flow
- [x] conduler bridge — finished videos are automatically handed off to conduler for scheduling
- [ ] Scene image preview in UI
- [ ] GPU acceleration support (when hardware allows)
- [ ] Auto-process queue (process all pending items sequentially without manual trigger)
