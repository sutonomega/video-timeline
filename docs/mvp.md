# MVP仕様

このドキュメントは、Video Timeline のMVP完了条件と、MVP時点のCLI仕様を固定するための仕様です。

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

- 音声認識の実行
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

共有ストレージ運用では、リポジトリ直下または作業ディレクトリの親ディレクトリに `video_timeline.toml` を置き、保存先をTOMLで管理する。実運用では `/mnt/video-timeline` を共有ストレージのマウント先とし、共有配下は `videos`、`frames`、`timelines`、`clips`、`html` に分ける。

```toml
[storage]
root = "/mnt/video-timeline"
videos_dir = "videos"
frames_dir = "frames"
timelines_dir = "timelines"
clips_dir = "clips"
html_dir = "html"
```

現在のMVPでは、動画解析CLI、`search`、`clip`、`export-html`、batch CLI の短縮指定が設定ファイルを参照する。

CLI引数とTOML設定の優先順位は次の通りとする。

1. ディレクトリを含む明示パス、絶対パス、通常の相対パスは設定より優先し、そのまま使う。
2. ファイル名だけの指定で `video_timeline.toml` が見つかる場合は、`storage.root` と各ディレクトリ設定から解決する。
3. ファイル名だけの指定で `video_timeline.toml` がない場合は、従来通りカレントディレクトリ基準の通常パスとして扱う。ただし動画解析で `--output` を省略できるのは設定ファイルがある場合だけとする。
4. CLI引数とTOMLが同じ種類の値を指定できる場合は、CLI引数を優先する。
5. batch CLIは `--batch` または `--input-dir` で明示する。`video_timeline.toml` がある場合、`--batch` だけで `<storage.root>/<storage.videos_dir>` を入力、`<storage.root>/<storage.timelines_dir>` を出力にする。短い `--input-dir` と `--output-dir` も `storage.root` 配下へ解決する。設定ファイルがない場合は従来通り `--input-dir` と `--output-dir` を必須にする。

動画解析とHTML出力は別コマンドとして実行する。1つ目のコマンドで `timelines/` にJSONを生成し、2つ目の `export-html` でそのJSONをHTMLへ変換する。`input` がファイル名だけで `--output` を省略した場合、入力動画は `<storage.root>/<videos_dir>/`、出力JSONは動画ファイル名のstemを使って `<storage.root>/<timelines_dir>/` に解決する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli sample1.mp4
PYTHONPATH=src python3 -m video_timeline.cli export-html sample1
```

この場合、入力動画は `/mnt/video-timeline/videos/sample1.mp4`、出力JSONは `/mnt/video-timeline/timelines/sample1.json`、フレーム保存先は `/mnt/video-timeline/frames` として扱う。HTML出力は `/mnt/video-timeline/html/sample1.html` として扱う。

出力JSON名を明示したい場合は、`--output timeline-sample1.json` のようにファイル名だけを指定すると `/mnt/video-timeline/timelines/timeline-sample1.json` に保存する。

複数動画をまとめて解析する場合は、入力ディレクトリと出力ディレクトリを指定する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli --input-dir recordings --output-dir timelines
```

`video_timeline.toml` がある共有ストレージ運用では、短いディレクトリ名を `storage.root` 配下へ解決する。次の例では入力ディレクトリを `/mnt/video-timeline/videos`、出力ベースディレクトリを `/mnt/video-timeline/timelines` として扱う。

```bash
PYTHONPATH=src python3 -m video_timeline.cli --batch
```

`--input-dir videos` のように短いディレクトリ名を明示することもできる。batchの出力は通常CLIの `timelines/sample1.json` には寄せず、同名動画の衝突を避けるため `/mnt/video-timeline/timelines/<video_stem>_<path_hash>/timeline.json` と `/mnt/video-timeline/timelines/<video_stem>_<path_hash>/frames/` に保存する。

生成済み `timeline.json` の指定区間を切り出す場合は `clip` サブコマンドを使う。

```bash
PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --index 3 --output clip.mp4
```

共有ストレージ運用では、ファイル名だけで `timelines/` の入力JSONと `clips/` の出力MP4を解決できる。

```bash
PYTHONPATH=src python3 -m video_timeline.cli clip sample1.json --index 3 --output clip1.mp4
```

この場合、入力JSONは `/mnt/video-timeline/timelines/sample1.json`、出力MP4は `/mnt/video-timeline/clips/clip1.mp4` として扱う。`--output` を省略した場合は、従来通り `storage.timeline_path` または読み込んだ `timeline.json` の場所から `clips/` を推定する。

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
PYTHONPATH=src python3 -m video_timeline.cli search sample1.json chatgpt
```

生成済み `timeline.json` をブラウザで確認するHTMLに出力する場合は `export-html` サブコマンドを使う。`video_timeline.toml` がある共有ストレージ運用では、ファイル名だけで `timelines/` の入力JSONと `html/` の出力HTMLを解決する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli export-html timeline
```

この場合、入力JSONは `/mnt/video-timeline/timelines/timeline.json`、出力HTMLは `/mnt/video-timeline/html/timeline.html` として扱う。

設定ファイルがない場合、または通常のパスを指定する場合は、従来通り `--output` で出力HTMLを明示する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli export-html timeline.json --output timeline.html
```

設定ファイルはTOML、解析結果やHTML出力の元になる生成物はJSONとし、MVP以降もTOMLは設定専用、JSONはデータ交換形式として使い分ける。

引数:

- `input`: 入力動画ファイルのパス
- `--output`: 出力JSONファイルのパス。明示した場合は指定したパスを優先する。`video_timeline.toml` があり、入力がファイル名だけの場合は省略できる
- `--batch`: 設定された入力ディレクトリ配下の`mp4`を一括解析する。`video_timeline.toml` がある場合は `--input-dir` と `--output-dir` を省略できる
- `--input-dir`: 一括解析する入力ディレクトリ。配下の`mp4`を再帰的に検出する
- `--output-dir`: 一括解析結果の保存先ベースディレクトリ
- `--interval-seconds`: フレーム抽出間隔。既定値は`10`
- `--frames-dir`: 抽出フレームの保存先ベースディレクトリ。既定値は`frames`
- `--vl-model`: フレーム要約に使うOllamaモデル。既定値は`gemma3:12b`
- `--transcript-json`: 外部ASR結果のJSONを読み込み、生成JSONの `transcripts` に補助情報として保存する。batch CLIでは指定できない
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

`export-html` は `video`、`analysis`、`timeline`、`events` を1つの静的HTMLに出力する。`timeline` はindex、時刻範囲、summary、tagsを表で表示する。`events` はkind、時刻範囲、summary、timeline_index、importance_score、tagsを表で表示する。HTML内の値はエスケープし、CSSやJavaScriptに依存しない最小表示にする。存在しないファイル、不正なJSON、`timeline`がないJSON、dictではない`timeline`/`events`要素はエラーにする。`video_timeline.toml` はカレントディレクトリから親ディレクトリへ向かって探索する。設定ファイルがあり、`export-html` の入力が `sample` または `sample.json` のようなファイル名だけの場合は、`storage.root`、`storage.timelines_dir`、`storage.html_dir` から入出力パスを解決する。既存の明示パス指定と `--output` 指定はそのまま優先する。

`timeline` は動画区間の一次構造とし、検索、clip、HTML表示の基本単位にする。`events` は `timeline_index` で元の `timeline` 区間へ戻れる派生イベント候補とし、将来の重要イベント抽出、`kind` 分類、検索UIでの強調表示に使う。現時点では `timeline` と近い情報を持つが、`events` を timeline の代替構造にはしない。

## 設定ファイル方針

設定ファイルはTOML、生成物はJSONとする。TOMLは人が編集する設定を読みやすく管理するために使い、JSONは解析結果、APIレスポンス、検索インデックスなど機械処理やWeb表示で扱うデータ交換形式として使う。

TOMLの対象:

- アプリケーション設定
- ストレージ設定
- 既定モデル設定
- HTML出力設定
- タイムライン生成設定
- 将来の検索設定

現在実装するTOMLは `[storage]` のみとする。`root` は標準ディレクトリを置く基点で、ローカルSSD、外付けSSD、NAS、SMB共有、NFSの違いは区別しない。

将来の設定セクションは次の方向にする。

```toml
[vl]
provider = "ollama"
model = "gemma3:12b"

[timeline]
interval_seconds = 10

[html]
# 表示形式やテンプレートなど、HTML出力の挙動を置く。

[search]
# 既定の検索条件や表示件数を置く。
```

JSONの対象:

- `timeline.json`
- `frame_summaries`
- `analysis` 結果
- export用データ
- APIレスポンス
- 将来の検索インデックス

`timeline` 出力、`frame_summaries`、APIレスポンスはTOML化しない。CLIはまず `video_timeline.toml` を読み込み、設定が存在しない場合は現在の既定値と明示されたCLI引数を使う。`AppConfig` はアプリケーション設定全体を保持し、CLI向けのパス解決ヘルパーを公開する。`StoragePathConfig` は `[storage]` だけを表し、`storage.root` と標準ディレクトリ名の管理に責務を限定する。

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
    "video_path": "/mnt/storage/videos/input.mp4",
    "frames_dir": "/mnt/storage/frames/input_abcd1234ef56",
    "timeline_path": "/mnt/storage/timelines/input.json"
  }
}
```

`storage` は保存先種別を判定するためのものではなく、実際に参照した動画、フレーム保存先、timeline保存先のパスを記録する。保存するキーは `storage.video_path`、`storage.frames_dir`、`storage.timeline_path` とし、`storage.mode` は保存しない。明示パスを渡した場合はそのパスを保存し、`video_timeline.toml` の短縮解決を使った場合は解決後の `storage.root` 配下のパスを保存する。

将来、別PCや別マウント先で同じJSONを扱う場合は、絶対パスだけでなく `storage.root` と相対パスを組み合わせる方式も検討する。例として、`storage.root` を `/mnt/video-timeline`、`video_path` を `videos/a.mp4`、`frames_dir` を `frames/a_xxxx`、`timeline_path` を `timelines/a.json` のように保存すると、ローカルSSD、外付けSSD、NAS、SMB共有、NFSなどの違いを `storage.root` に寄せられる。

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
  "scene_boundaries": [],
  "transcripts": [
    {
      "start_seconds": 118.2,
      "end_seconds": 125.4,
      "text": "この仕様ならフレーム要約から始めるのがよさそうです",
      "source": "external_asr",
      "speaker": "user"
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
- `storage.video_path`
- `storage.frames_dir`
- `storage.timeline_path`
- `scene_boundaries`
- `transcripts`
- `transcripts[].start_seconds`
- `transcripts[].end_seconds`
- `transcripts[].text`
- `transcripts[].source`
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

## transcript補助情報仕様

音声認識はMVP本体には含めず、MVP後の拡張として扱う。現時点ではローカルASRを実行せず、外部ASRや手動生成されたJSONを `--transcript-json` で読み込み、生成JSONのトップレベル `transcripts` 配列へ保存する。

```bash
PYTHONPATH=src python3 -m video_timeline.cli input.mp4 --output timeline.json --transcript-json transcript.json
```

transcript segmentは次の形に正規化する。

```json
{
  "start_seconds": 12.0,
  "end_seconds": 18.5,
  "text": "次はHTML出力を確認します",
  "source": "external_asr",
  "speaker": "user"
}
```

`speaker` は任意とする。`source` が入力にない場合は `external_asr` を保存する。入力JSONはトップレベル配列、`{"transcripts":[...]}`、またはWhisper系の `{"segments":[...]}` を受け入れる。`segments` 互換では `start` / `end` も `start_seconds` / `end_seconds` として読み取る。

`transcripts` は `scene_boundaries` と同じ補助情報であり、timeline生成の主判断には使わない。`timeline` や `events` とは時刻の重なりで後から参照できるようにする。音声抽出、ローカルASRモデルの実行、transcriptを使ったtimeline分割、transcriptからの重要イベント判定は後続機能とする。ローカル実行可能なASR候補は Whisper 系、faster-whisper、whisper.cpp を後続で比較する。

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

- `docs/mvp.md` の手順でCLIを実行できる
- 入力動画からフレーム要約JSONを生成できる
- フレーム要約が時系列順に並ぶ
- 各フレーム要約の時刻、画像パス、要約文がJSONに保存される
- 正常系と異常系の自動テストがある
- MVPの受け入れ確認結果を `docs/acceptance.md` に記録している

## Issue分割

MVP完遂までの実装は次のIssueで進める。

- #1 MVP完遂条件とCLI仕様をdocsに固定する
- #2 動画ファイル入力とメタデータ取得を実装する
- #3 固定間隔フレーム抽出を実装する
- #4 フレーム要約JSON生成を実装する
- #5 MVP CLIを統合してフレーム要約JSONを生成できるようにする
