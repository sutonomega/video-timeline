# MVP仕様

このドキュメントは、Video TimelineのMVP完了条件を固定するための仕様です。

## 目的

動画ファイルから固定間隔でフレームを抽出し、各フレームをVLで要約して、後からタイムライン化できるJSONとして保存できる状態をMVP完了とする。

最初のMVPでは、映像の物理的な切れ目よりも「何をしている場面か」を残すことを優先する。シーン分割は後続機能とし、フレーム要約が連続して得られる状態を先に作る。

## 対象範囲

MVPで実装すること:

- 動画ファイル入力
- 動画メタデータ取得
- 固定間隔フレーム抽出
- 抽出フレームの画像保存
- VLによるフレーム要約
- フレーム要約JSON生成
- JSON保存
- CLIからの実行

MVPで実装しないこと:

- 音声認識
- 類似要約の自動区間統合
- シーン境界検出
- AIによる実況文生成
- WebUI
- SNS投稿
- 動画編集

## CLI仕様

最小CLIは次の形にする。

```bash
PYTHONPATH=src python3 -m video_timeline.cli input.mp4 --output timeline.json
```

複数動画をまとめて解析する場合は、入力ディレクトリと出力ディレクトリを指定する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli --input-dir recordings --output-dir timelines
```

生成済み `timeline.json` の指定区間を切り出す場合は `clip` サブコマンドを使う。

```bash
PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --index 3 --output clip.mp4
```

引数:

- `input`: 入力動画ファイルのパス
- `--output`: 出力JSONファイルのパス
- `--input-dir`: 一括解析する入力ディレクトリ。配下の`mp4`を再帰的に検出する
- `--output-dir`: 一括解析結果の保存先ベースディレクトリ
- `--interval-seconds`: フレーム抽出間隔。既定値は`10`
- `--frames-dir`: 抽出フレームの保存先ベースディレクトリ。既定値は`frames`
- `clip timeline.json`: `timeline` の指定区間を元動画から切り出す
- `clip --index`: 切り出す `timeline` 配列の0始まりindex
- `clip --output`: 切り出しMP4の保存先
- `clip --padding-seconds`: 切り出し範囲の前後に足す余白秒数。既定値は`0`
- `clip --accurate`: 再エンコードして開始位置の正確さを優先する。既定は高速なcopy切り出し
- `clip --crf`: `--accurate`時のx264画質。既定値は`18`
- `clip --preset`: `--accurate`時のx264エンコード速度。既定値は`veryfast`

`clip` は既定では高速な `ffmpeg -c copy` で切り出す。キーフレーム位置の影響で開始位置が指定秒から少しずれる可能性がある。厳密な切り出しが必要な場合は `--accurate` を使う。`--crf`と`--preset`は`--accurate`時だけ有効で、copy切り出しでは指定できない。

将来拡張する任意引数:

- `--vl-provider`: フレーム要約に使うVLプロバイダー。MVP後に切り替え可能にする
- `--format`: 出力形式。MVPでは`json`を既定値とする

## VL仕様

MVPではVLプロバイダーとモデルを固定する。

- 既定プロバイダー: `ollama`
- 既定モデル: `qwen2.5vl:7b`

プロバイダーやモデルの切り替えはMVP後の拡張とする。

## 入力仕様

対応する入力:

- ローカル動画ファイル
- `mp4`を最初の対応形式とする

入力検証:

- ファイルが存在しない場合はエラーにする
- `mp4`以外の拡張子はMVPではエラーにする
- 動画として読み込めない場合はエラーにする
- duration、fps、frame_count、width、heightを取得する
- メタデータ取得には`ffprobe`を使う

## 動画メタデータ仕様

`video_loader`は入力動画を検証し、後続のフレーム抽出で使うメタデータを返す。

返す項目:

- `path`
- `duration_seconds`
- `fps`
- `frame_count`
- `width`
- `height`

`path`は同じ入力動画を安定して参照できるよう、絶対パスとして保存する。

MVPでは`mp4`のみ対応する。CLIから入力動画を受け取る処理は、MVP CLI統合のIssueで接続する。

## フレーム抽出仕様

`frame_extractor`は動画メタデータを受け取り、固定間隔でフレーム画像を保存する。

MVPの既定値:

- 抽出間隔: 10秒
- 画像形式: `jpg`
- 保存先: `frames`
- フレーム抽出には`ffmpeg`を使う

抽出時刻:

- 先頭の`0`秒から抽出する
- `interval_seconds`ごとに抽出する
- `duration_seconds`以上の時刻は抽出しない
- 動画が10秒未満でも`0`秒の1枚は抽出する

抽出結果の項目:

- `index`
- `time_seconds`
- `image`

`image`は保存したフレーム画像のパスとして扱う。ファイル名はミリ秒ベースの9桁連番にする。CLIでは異なる動画のフレームが混ざらないよう、保存先を`frames/<video_stem>_<path_hash>/000010000.jpg`のように動画ファイル名と入力パスhashで分離する。`--frames-dir custom_frames`を指定した場合は、`custom_frames/<video_stem>_<path_hash>/`を保存先にする。相対パスを指定した場合、出力JSONの`image`も相対パスになる。`path_hash`は解決済み入力パスから作る短いhashで、`videos/a/sample.mp4`と`videos/b/sample.mp4`のような同名動画の衝突を避けるために使う。

一括解析では動画ごとに`<output-dir>/<video_stem>_<path_hash>/`を作り、その中に`timeline.json`と`frames/`を保存する。1本の動画で失敗しても残りの動画は続行し、最後に成功件数と失敗件数を表示する。

## 処理仕様

MVPの処理は次の順に行う。

1. MP4を読み込む
2. 10秒ごとにフレームを抽出する
3. 抽出したフレームを画像として保存する
4. 各フレームをVLで要約する
5. フレーム要約の一覧をJSONとして保存する

後続機能では、似た要約が続くフレームを1つの区間にまとめ、タイムライン化する。

## 出力JSON仕様

MVPのJSONは次の構造にする。

```json
{
  "version": 1,
  "generated_at": "2026-06-11T00:00:00Z",
  "video": {
    "path": "input.mp4",
    "duration_seconds": 12.34,
    "fps": 30.0,
    "frame_count": 370,
    "width": 1920,
    "height": 1080
  },
  "analysis": {
    "interval_seconds": 10,
    "vl_provider": "ollama",
    "vl_model": "qwen2.5vl:7b"
  },
  "frame_summaries": [
    {
      "index": 0,
      "time_seconds": 120.0,
      "image": "frames/000120000.jpg",
      "summary": "ChatGPTで動画タイムライン生成ツールの仕様を相談している",
      "tags": ["chatgpt", "planning"]
    }
  ],
  "timeline": [
    {
      "start_seconds": 120.0,
      "end_seconds": 180.0,
      "summary": "ChatGPTで動画タイムライン生成ツールの仕様を相談している",
      "frame_indices": [0],
      "tags": ["chatgpt", "planning"]
    }
  ]
}
```

必須項目:

- `version`
- `generated_at`
- `video.path`
- `video.duration_seconds`
- `video.fps`
- `video.frame_count`
- `video.width`
- `video.height`
- `analysis.interval_seconds`
- `analysis.vl_provider`
- `analysis.vl_model`
- `frame_summaries[].index`
- `frame_summaries[].time_seconds`
- `frame_summaries[].image`
- `frame_summaries[].summary`
- `frame_summaries[].tags`
- `timeline[].tags`

## フレーム要約JSON生成仕様

`frame_summarizer`は抽出済みフレームをVLで要約し、MVPの出力JSONを生成する。

MVPの既定値:

- VLプロバイダー: `ollama`
- VLモデル: `qwen2.5vl:7b`
- フレーム抽出間隔: 10秒
- タグ形式: 小文字英数字、`_`、日本語を基本にする
- 英語タグは小文字化し、空白や記号は`_`へ正規化する。日本語タグは検索やtimeline統合に使えるよう保存する

責務:

- 抽出済みフレームごとに要約文とタグを生成する
- video、analysis、frame_summariesを持つJSON構造を生成する
- frame_summariesをtime_seconds昇順で保存する
- JSONをUTF-8で保存する

Ollama呼び出し:

- ローカルのOllama HTTP APIを使う
- 画像はbase64にして`/api/generate`へ渡す
- `response`は`summary`と`tags`を持つJSON文字列を優先して読み取る
- 自動テストではOllama呼び出し境界を差し替えて検証する

## 完了条件

MVPは次の条件を満たした時点で完了とする。

- READMEの手順だけでCLIを実行できる
- 入力動画からフレーム要約JSONを生成できる
- フレーム要約が時系列順に並ぶ
- 各フレーム要約の時刻、画像パス、要約文がJSONに保存される
- 正常系と異常系の自動テストがある
- docs/roadmap.mdでMVP完了として扱える

## Issue分割

MVP完遂までの実装は次のIssueで進める。

- #1 MVP完遂条件とCLI仕様をdocsに固定する
- #2 動画ファイル入力とメタデータ取得を実装する
- #3 固定間隔フレーム抽出を実装する
- #4 フレーム要約JSON生成を実装する
- #5 MVP CLIを統合してフレーム要約JSONを生成できるようにする
