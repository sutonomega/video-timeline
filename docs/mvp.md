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
video-timeline input.mp4 --output timeline.json
```

引数:

- `input`: 入力動画ファイルのパス
- `--output`: 出力JSONファイルのパス

将来拡張する任意引数:

- `--interval-seconds`: フレーム抽出間隔。MVPでは`10`を既定値とする
- `--frames-dir`: 抽出フレームの保存先
- `--vl-provider`: フレーム要約に使うVLプロバイダー
- `--format`: 出力形式。MVPでは`json`を既定値とする

## 入力仕様

対応する入力:

- ローカル動画ファイル
- `mp4`を最初の対応形式とする

入力検証:

- ファイルが存在しない場合はエラーにする
- 動画として読み込めない場合はエラーにする
- duration、fps、frame_count、width、heightを取得する

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
  "frame_summaries": [
    {
      "index": 0,
      "time_seconds": 120.0,
      "image": "frames/000120.jpg",
      "summary": "ChatGPTで動画タイムライン生成ツールの仕様を相談している"
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
- `frame_summaries[].index`
- `frame_summaries[].time_seconds`
- `frame_summaries[].image`
- `frame_summaries[].summary`

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
