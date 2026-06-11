# Video Timeline

A tool for extracting events from videos and turning them into readable timelines.

## Goal

Turn video scenes into structured timeline logs that can be used for review, commentary, or AI context.

## Features

- Video metadata loading
- Fixed-interval frame extraction
- VL frame summarization with Ollama
- Timeline grouping from frame summaries
- Event candidate generation from timeline segments
- JSON export

## Usage

Requirements:

- Python 3.12+
- ffmpeg / ffprobe
- Ollama
- qwen2.5vl:7b

Prepare the VL model:

```bash
ollama pull qwen2.5vl:7b
```

Run:

```bash
PYTHONPATH=src python3 -m video_timeline.cli input.mp4 --output timeline.json
```

The command extracts frames into `frames/`, summarizes them with Ollama, and writes a frame summary JSON file.

While running, the CLI prints the current processing stage and the frame currently being summarized, such as `frame summarization started: 3/120 (20s, remaining: 12m 30s)`.

## MVP Spec

The MVP scope and completion criteria are defined in [docs/mvp.md](docs/mvp.md).

## Status

MVP accepted with a generated sample MP4 and Ollama.

Acceptance details are recorded in [docs/acceptance.md](docs/acceptance.md).
