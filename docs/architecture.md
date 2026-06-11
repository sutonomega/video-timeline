# Architecture

MVPの入出力契約は[mvp.md](mvp.md)を正とする。

Input
- Video File

Analysis
- Frame Extraction
- Frame Summary
- Summary Grouping

Output
- Frame Summary JSON
- Timeline

Storage
- JSON
- Markdown

Main Modules
- video_loader
- frame_extractor
- frame_summarizer
- timeline_generator
