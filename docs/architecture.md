# Architecture

MVPの入出力契約は[mvp.md](mvp.md)を正とする。

Input
- Video File

Analysis
- Scene Detection
- Event Detection

Output
- Timeline

Storage
- JSON
- Markdown

Main Modules
- video_loader
- scene_detector
- event_detector
- timeline_generator
