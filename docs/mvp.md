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

サーバー上の保存場所を参照情報として残す場合は、入力動画、`--output`、`--frames-dir` にサーバー上のパスを渡し、`--storage-mode server` を指定する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli /mnt/storage/videos/input.mp4 --output /mnt/storage/timelines/input.json --frames-dir /mnt/storage/frames --storage-mode server
```

実運用のサーバー格納場所は `\\192.168.10.112\video-timeline` とする。共有配下は `videos`、`frames`、`timelines`、`clips` に分ける。Windows共有パスから実行する場合は、次のように動画、timeline、framesの保存先を同じ共有配下に置く。

```powershell
python -m video_timeline.cli "\\192.168.10.112\video-timeline\videos\input.mp4" --output "\\192.168.10.112\video-timeline\timelines\input.json" --frames-dir "\\192.168.10.112\video-timeline\frames" --storage-mode server
```

複数動画をまとめて解析する場合は、入力ディレクトリと出力ディレクトリを指定する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli --input-dir recordings --output-dir timelines
```

生成済み `timeline.json` の指定区間を切り出す場合は `clip` サブコマンドを使う。

```bash
PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --index 3 --output clip.mp4
```

`storage` 情報を持つサーバー保存済み `timeline.json` では、`--output` を省略すると `storage.timeline_path` から共有配下の `clips/` を推定して保存する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli clip /mnt/video-timeline/timelines/sample.json --index 3
```

複数の連続した `timeline` 区間を個別に切り出す場合は、index範囲と出力ディレクトリを指定する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --start-index 3 --end-index 7 --output clips
```

指定タグを含む `timeline` 区間をまとめて切り出す場合は、タグと出力ディレクトリを指定する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --tag github --output clips
```

生成済み `timeline.json` から作業区間を検索する場合は `search` サブコマンドを使う。

```bash
PYTHONPATH=src python3 -m video_timeline.cli search timeline.json chatgpt
```

生成済み `timeline.json` をブラウザで確認するHTMLに出力する場合は `export-html` サブコマンドを使う。

```bash
PYTHONPATH=src python3 -m video_timeline.cli export-html timeline.json --output timeline.html
```

共有ストレージ運用では、`video_timeline.toml` に保存先を定義すると、ファイル名だけで `timeline.json` とHTML出力先を解決できる。

```toml
[storage]
root = "/mnt/video-timeline"
videos_dir = "videos"
frames_dir = "frames"
timelines_dir = "timelines"
clips_dir = "clips"
html_dir = "html"
```

```bash
PYTHONPATH=src python3 -m video_timeline.cli export-html sample1-gemma312b
```

この場合、入力JSONは `/mnt/video-timeline/timelines/sample1-gemma312b.json`、出力HTMLは `/mnt/video-timeline/html/sample1-gemma312b.html` として扱う。設定ファイルがない場合、または通常のパスを指定する場合は、従来通り `--output` で出力HTMLを明示する。設定ファイルはTOML、解析結果やHTML出力の元になる生成物はJSONとし、MVP以降もTOMLは設定専用、JSONはデータ交換形式として使い分ける。

引数:

- `input`: 入力動画ファイルのパス
- `--output`: 出力JSONファイルのパス。ファイル名は自動生成せず、指定したパスをそのまま使う
- `--input-dir`: 一括解析する入力ディレクトリ。配下の`mp4`を再帰的に検出する
- `--output-dir`: 一括解析結果の保存先ベースディレクトリ
- `--interval-seconds`: フレーム抽出間隔。既定値は`10`
- `--frames-dir`: 抽出フレームの保存先ベースディレクトリ。既定値は`frames`
- `--storage-mode`: JSONに記録する保存先の種別。`local`または`server`。既定値は`local`
- `--vl-model`: フレーム要約に使うOllamaモデル。既定値は`gemma3:12b`
- `clip timeline.json`: `timeline` の指定区間を元動画から切り出す
- `clip --index`: 切り出す `timeline` 配列の0始まりindex
- `clip --start-index`: 連続切り出しの開始 `timeline` index
- `clip --end-index`: 連続切り出しの終了 `timeline` index。このindexも切り出し対象に含める
- `clip --tag`: 指定タグを含む `timeline` 区間を個別clipとして切り出す
- `clip --output`: `--index`では切り出しMP4の保存先、`--start-index`/`--end-index`または`--tag`では出力ディレクトリ。省略時は `storage.timeline_path` または `timeline.json` の場所から `clips/` を推定する
- `clip --padding-seconds`: 切り出し範囲の前後に足す余白秒数。既定値は`0`
- `clip --accurate`: 再エンコードして開始位置の正確さを優先する。既定は高速なcopy切り出し
- `clip --crf`: `--accurate`時のx264画質。既定値は`18`
- `clip --preset`: `--accurate`時のx264エンコード速度。既定値は`veryfast`
- `search timeline.json query`: `timeline` と `events` からqueryに一致する区間を検索する
- `export-html timeline.json`: `timeline.json` を静的HTMLに変換する
- `export-html --output`: 出力HTMLファイルのパス。`video_timeline.toml` があり、入力がファイル名だけの場合は省略できる

`clip` は既定では高速な `ffmpeg -c copy` で切り出す。キーフレーム位置の影響で開始位置が指定秒から少しずれる可能性がある。厳密な切り出しが必要な場合は `--accurate` を使う。`--crf`と`--preset`は`--accurate`時だけ有効で、copy切り出しでは指定できない。

範囲切り出しとタグ切り出しでは、出力ディレクトリに `timeline_000003.mp4` のような `timeline_<index6桁>.mp4` を保存する。`--output` 省略時の単一区間切り出しも同じファイル名を使う。存在しないindex、または `--start-index` が `--end-index` より大きい範囲はエラーにする。タグ切り出しは `timeline[].tags` と対応する `events[].tags` に対する大文字小文字を区別しない完全一致で判定する。タグに一致する区間がない場合はエラーにせず `no matches` を表示する。

`search` は `timeline[].summary`、`timeline[].tags`、対応する `events[].kind`、`events[].summary`、`events[].tags` を大文字小文字を区別せず検索する。結果は `3  01:20-04:10  ChatGPTで仕様相談` のように、timeline index、時刻範囲、summaryを1行ずつ表示する。小数秒は切り捨てて表示する。空結果はエラーにせず `no matches` を表示する。存在しないファイルや不正なJSONはエラーにする。

`export-html` は `video`、`analysis`、`timeline`、`events` を1つの静的HTMLに出力する。`timeline` はindex、時刻範囲、summary、tagsを表で表示する。`events` はkind、時刻範囲、summary、timeline_index、importance_score、tagsを表で表示する。HTML内の値はエスケープし、CSSやJavaScriptに依存しない最小表示にする。存在しないファイル、不正なJSON、`timeline`がないJSON、dictではない`timeline`/`events`要素はエラーにする。`video_timeline.toml` はカレントディレクトリまたはプロジェクトルートから読み込む。設定ファイルがあり、`export-html` の入力が `sample` または `sample.json` のようなファイル名だけの場合は、`storage.root`、`storage.timelines_dir`、`storage.html_dir` から入出力パスを解決する。既存のフルパス指定と `--output` 指定はそのまま優先する。

## 設定ファイル方針

設定ファイルはTOML、生成物はJSONとする。TOMLは人が編集する設定を読みやすく管理するために使い、JSONは解析結果、APIレスポンス、検索インデックスなど機械処理やWeb表示で扱うデータ交換形式として使う。

TOMLの対象:

- アプリケーション設定
- ストレージ設定
- 既定モデル設定
- HTML出力設定
- タイムライン生成設定
- 将来の検索設定

JSONの対象:

- `timeline.json`
- `frame_summaries`
- `analysis` 結果
- export用データ
- APIレスポンス
- 将来の検索インデックス

`timeline` 出力、`frame_summaries`、APIレスポンスはTOML化しない。CLIはまず `video_timeline.toml` を読み込み、設定が存在しない場合は現在の既定値と明示されたCLI引数を使う。

将来拡張する任意引数:

- `--vl-provider`: フレーム要約に使うVLプロバイダー。MVP後に切り替え可能にする
- `--format`: 出力形式。MVPでは`json`を既定値とする

## VL仕様

MVPではVLプロバイダーをOllamaに固定する。モデルは既定値を `gemma3:12b` とし、品質比較のためCLIの `--vl-model` で切り替えられる。

- 既定プロバイダー: `ollama`
- 既定モデル: `gemma3:12b`

プロバイダーの切り替えはMVP後の拡張とする。実行時に指定したモデル名は `analysis.vl_model` に保存する。

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

## 保存先メタデータ仕様

CLIで生成したJSONには、動画、フレーム画像、timeline JSONの参照先を `storage` として保存する。

```json
{
  "storage": {
    "mode": "server",
    "video_path": "/mnt/storage/videos/input.mp4",
    "frames_dir": "/mnt/storage/frames/input_abcd1234ef56",
    "timeline_path": "/mnt/storage/timelines/input.json"
  }
}
```

`mode` は `local` または `server` とする。`server` はファイルを自動転送する機能ではなく、入力動画、フレーム保存先、timeline保存先がサーバー上のパスであることをJSONに明示するためのメタデータとして扱う。既存のローカル運用では `mode` を `local` とし、従来通り `video.path` と `frame_summaries[].image` から参照できる状態を維持する。

将来、別PCやサーバー上で同じJSONを扱う場合は、絶対パスだけでなく `storage_root` と相対パスを組み合わせる方式も検討する。例として、`storage_root` を `/data/video-timeline`、`video_path` を `videos/a.mp4`、`frames_dir` を `frames/a_xxxx`、`timeline_path` を `timelines/a.json` のように保存すると、環境ごとの差を `storage_root` に寄せられる。

同じ考え方で、clipの保存先を明示したい場合は将来 `storage.clips_dir` を追加する。現時点では、共有ルート直下に `timelines` と `clips` を兄弟ディレクトリとして置くMVP運用を前提に、`storage.timeline_path` から `clips/` を推定する。

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
    "vl_model": "gemma3:12b"
  },
  "storage": {
    "mode": "local",
    "video_path": "input.mp4",
    "frames_dir": "frames/input_abcd1234ef56",
    "timeline_path": "timeline.json"
  },
  "frame_summaries": [
    {
      "index": 0,
      "time_seconds": 120.0,
      "image": "frames/000120000.jpg",
      "summary": "ChatGPTで動画タイムライン生成ツールの仕様を相談している",
      "primary_tag": "chatgpt",
      "secondary_tags": ["planning"],
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
- `storage.mode`
- `storage.video_path`
- `storage.frames_dir`
- `storage.timeline_path`
- `frame_summaries[].index`
- `frame_summaries[].time_seconds`
- `frame_summaries[].image`
- `frame_summaries[].summary`
- `frame_summaries[].primary_tag`
- `frame_summaries[].secondary_tags`
- `frame_summaries[].tags`
- `timeline[].tags`

## フレーム要約JSON生成仕様

`frame_summarizer`は抽出済みフレームをVLで要約し、MVPの出力JSONを生成する。

VLは `summary`、`primary_tag`、`secondary_tags` をJSONで返す。`primary_tag`は画面の主対象を1つだけ表すタグ、`secondary_tags`は補助的な作業や文脈を表すタグとする。`secondary_tags` は必ず `secondary_tags` という配列キーで返す。`secondary_tags[]` というキー名は使わない。MVP後の運用では、PCやスマホの画面が主対象のときは `chatgpt`、`github`、`vscode`、`terminal`、`browser`、`youtube`、`discord`、`game`、`document`、`other` を優先し、料理、食事、家事、外出、移動などの生活動画では `cooking`、`oatmeal`、`rice_cooker`、`eating`、`shopping`、`walking`、`exercise`、`cleaning`、`travel`、`study` を優先する。ただし、候補にない対象では短い自由タグも許可する。

既存JSONとの互換性のため、`tags` は引き続き保存する。新形式の応答では `tags` を `primary_tag + secondary_tags` から生成する。古い `{"summary":"...","tags":[...]}` 形式の応答では、先頭のタグを `primary_tag`、残りを `secondary_tags` として扱う。タグがない場合は `primary_tag` を `other`、`secondary_tags` を空配列にする。

VLの応答にJSONコードブロックや前後の説明文が混ざっている場合は、先頭のJSONオブジェクトを切り出してから読み取る。`secondary_tags[]` のような誤記は `secondary_tags` として救済する。`summary` の中にJSON文字列が埋まっている場合は、内側のJSONも再解釈する。JSONが閉じていない場合は `summary` と `primary_tag` だけを正規表現で拾い、`secondary_tags` は空配列にする。完全には復元できない場合だけ、再問い合わせはせず、従来通り全文を `summary` として保存する。

`other` は判定不能時の退避先として扱う。`other` が多い実データではtimeline統合やタグ別clipのノイズになるため、タグ類似統合の類似度計算では `other` を除外する。`tags` は summary の補助条件として扱い、summary の語彙がまったく重ならない場合はタグ一致だけで timeline を結合しない。`other` が大量発生する場合は、自由タグや事前定義タグを追加して減らす。

MVPの既定値:

- VLプロバイダー: `ollama`
- VLモデル: `gemma3:12b`
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
- `response`は`summary`、`primary_tag`、`secondary_tags`を持つJSON文字列を優先して読み取る
- 旧形式の`summary`と`tags`を持つJSON文字列も互換形式として読み取る
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
