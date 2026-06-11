# MVP仕様

このドキュメントは、Video TimelineのMVP完了条件を固定するための仕様です。

## 目的

動画ファイルを読み込み、シーン単位のタイムラインに変換し、JSONとして保存できる状態をMVP完了とする。

## 対象範囲

MVPで実装すること:

- 動画ファイル入力
- 動画メタデータ取得
- シーン分割
- タイムライン生成
- JSON保存
- CLIからの実行

MVPで実装しないこと:

- 音声認識
- AIによる要約生成
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

- `--threshold`: シーン境界検出のしきい値
- `--min-scene-seconds`: 最小シーン長
- `--format`: 出力形式。MVPでは`json`を既定値とする

## 入力仕様

対応する入力:

- ローカル動画ファイル
- `mp4`を最初の対応形式とする

入力検証:

- ファイルが存在しない場合はエラーにする
- 動画として読み込めない場合はエラーにする
- duration、fps、frame_count、width、heightを取得する

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
  "scenes": [
    {
      "index": 0,
      "start_seconds": 0.0,
      "end_seconds": 4.2,
      "duration_seconds": 4.2,
      "label": "scene_000"
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
- `scenes[].index`
- `scenes[].start_seconds`
- `scenes[].end_seconds`
- `scenes[].duration_seconds`
- `scenes[].label`

## 完了条件

MVPは次の条件を満たした時点で完了とする。

- READMEの手順だけでCLIを実行できる
- 入力動画からタイムラインJSONを生成できる
- シーンが時系列順に並ぶ
- 各シーンの開始時刻、終了時刻、長さがJSONに保存される
- 正常系と異常系の自動テストがある
- docs/roadmap.mdでMVP完了として扱える

## Issue分割

MVP完遂までの実装は次のIssueで進める。

- #1 MVP完遂条件とCLI仕様をdocsに固定する
- #2 動画ファイル入力とメタデータ取得を実装する
- #3 シーン分割を実装してタイムライン候補を作る
- #4 タイムライン生成とJSON保存を実装する
- #5 MVP CLIを統合してREADME手順で実行できるようにする
