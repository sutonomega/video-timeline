# 受け入れ確認

## MVP

Issue #13 の受け入れ確認として、短い検証用MP4とOllamaでMVP CLIを実行し、フレーム要約JSONを生成できることを確認した。完了条件は[mvp.md](mvp.md)に従う。

## 確認日

- 2026-06-11

## 環境

- Python: `python3`
- 動画処理: `ffmpeg` / `ffprobe`
- VLプロバイダー: `ollama`
- VLモデル: `qwen2.5vl:7b`

## 入力

検証用に2秒のMP4を生成した。

```bash
ffmpeg -y -f lavfi -i testsrc=size=640x360:rate=1:duration=2 -vf drawtext=text='Video Timeline MVP':x=40:y=40:fontsize=36:fontcolor=white:box=1:boxcolor=black@0.5 -pix_fmt yuv420p sample.mp4
```

生成物は一時ディレクトリに置き、リポジトリにはコミットしない。

## 実行コマンド

```bash
PYTHONPATH=/home/codex/work_git/video-timeline/src python3 -m video_timeline.cli sample.mp4 --output timeline.json --frames-dir frames
```

実行結果:

```text
wrote timeline.json
```

## 確認したJSON

`timeline.json` で次の内容を確認した。

- `video.path` が絶対パスで保存される
- `video.duration_seconds`、`video.fps`、`video.frame_count`、`video.width`、`video.height` が保存される
- `analysis.interval_seconds` が `10.0` で保存される
- `analysis.vl_provider` が `ollama` で保存される
- `analysis.vl_model` が `qwen2.5vl:7b` で保存される
- `frame_summaries` に `index`、`time_seconds`、`image`、`summary` が保存される
- `frames/000000000.jpg` が生成される

要約例:

```json
{
  "index": 0,
  "time_seconds": 0.0,
  "image": "frames/000000000.jpg",
  "summary": "この画像では、ビデオのタイムラインとMVP（最小限の機能付きプロダクト）について説明していることが示されています。"
}
```

## 判定

MVP仕様で定義した「READMEの手順でCLIを実行し、入力動画からフレーム要約JSONを生成できる」状態を満たした。
