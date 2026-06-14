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
- Events
- Storage Metadata

Storage
- JSON
- Markdown

Main Modules
- video_loader
- frame_extractor
- frame_summarizer
- timeline_generator
- event_detector
- video_clipper
- timeline_searcher
- timeline_html_exporter

## video_loader

責務:

- 入力動画ファイルの存在確認
- MVP対応形式の検証
- `ffprobe`によるduration、fps、frame_count、width、heightの取得
- 後続モジュールへ渡す動画メタデータ構造の生成

## frame_extractor

責務:

- 動画メタデータから固定間隔の抽出時刻を生成
- `ffmpeg`によるフレーム画像の保存
- index、time_seconds、imageを持つ抽出結果の生成
- 短い動画や端数秒を含む動画でも決定的に動く抽出制御

CLIから使う場合は、`--frames-dir`をベースディレクトリとして扱い、動画ごとに`<frames-dir>/<video_stem>_<path_hash>/`へ保存する。`path_hash`は解決済み入力パスから作る短いhashで、`videos/a/sample.mp4`と`videos/b/sample.mp4`のような同名動画を連続実行してもフレーム画像が同じディレクトリに混ざらないようにする。

## storage metadata

責務:

- CLIで生成したJSONに `storage` を保存する
- `storage.mode` で `local` と `server` を区別する
- `storage.video_path` に元動画の参照先を保存する
- `storage.frames_dir` に抽出フレームの保存ディレクトリを保存する
- `storage.timeline_path` にtimeline JSONの保存先を保存する

`--storage-mode server` はファイル転送やコピーを行うものではなく、入力動画、`--frames-dir`、`--output` にサーバー上のパスを指定したとき、その参照先をJSONに明示するための設定とする。既存のローカル運用では `local` を既定値にし、`video.path` と `frame_summaries[].image` の参照を維持する。サーバー上でclipを実行する場合は、この `storage` 情報と従来の `video.path` を使って元動画とフレーム保存先を解決する。

共有保存先の例は `\\192.168.10.112\video-timeline` とし、配下に `videos`、`frames`、`timelines`、`clips` を置く想定にする。Windows共有パスを使う場合も、CLIには通常のパス文字列として渡し、JSONの `storage.video_path`、`storage.frames_dir`、`storage.timeline_path` に同じ参照先を記録する。

今回の外部ストレージ対応は、外部ストレージ上のパスをJSONから参照できるようにする土台とする。サーバー保存先から動画を解決してclipを生成する処理は後続のサーバーclip機能で扱う。将来は `storage_root` と相対パスを使い、`video_path`、`frames_dir`、`timeline_path` を `videos/a.mp4` や `timelines/a.json` のように保存する方式も検討する。

## frame_summarizer

責務:

- 抽出済みフレームをVLで要約
- フレームごとの検索用タグを生成する
- `primary_tag`と`secondary_tags`で主対象と補助タグを分ける
- タグを小文字英数字、`_`、日本語中心に正規化する
- 日本語タグは検索やtimeline統合に使えるよう保持する
- Ollama HTTP API呼び出しの境界を提供
- video、analysis、frame_summariesを持つJSON構造の生成
- UTF-8 JSONファイルへの保存

VLプロンプトでは、自由なタグ列ではなく`primary_tag`と`secondary_tags`を返すように指定する。事前定義タグは`chatgpt`、`github`、`vscode`、`terminal`、`browser`、`youtube`、`discord`、`game`、`document`、`other`を優先し、画面の主対象を`primary_tag`に置く。適切な候補がない場合は、将棋、音楽制作、動画編集、Blender、通院、食事のような短い自由タグも許可する。`tags`は後方互換のため残し、保存時は`primary_tag`と`secondary_tags`を結合した配列として扱う。古い`tags`のみのVL応答は先頭タグを`primary_tag`、残りを`secondary_tags`として扱う。

VLがJSON以外の文章を返した場合は、従来通り全文を`summary`として保存し、`primary_tag`は`other`、`secondary_tags`は空にする。`summary`にJSONコードブロックが混入した場合も壊さず保存するが、後続の品質レビューで検出対象にする。`other`は判定不能時の退避先なので、実データで多発する場合はtimelineのタグ類似統合から除外するか、自由タグや事前定義タグの追加で減らす。

## cli batch mode

責務:

- 入力ディレクトリ配下の`mp4`を再帰的に検出する
- 検出した`mp4`を全件保持せず順次処理する
- 動画ごとに`<output-dir>/<video_stem>_<path_hash>/`を作る
- 各動画の`timeline.json`と`frames/`を同じ動画専用ディレクトリに保存する
- 1本の動画で失敗しても残りの動画を続行する
- 最後に成功件数と失敗件数を表示する

## timeline_generator

責務:

- `frame_summaries`を時系列順に読み込む
- 連続する同一`summary`を1つの区間にまとめる
- 連続する近い`summary`を1つの区間にまとめる
- 連続する近い`tags`を1つの区間にまとめる
- 要約が変わった地点で区間を分ける
- `start_seconds`、`end_seconds`、`summary`、`frame_indices`、`tags`を持つ`timeline`を生成する
- 最後の区間の`end_seconds`は動画の`duration_seconds`を使う

軽量な類似判定の最小実装では、正規化した文字列の完全一致に加えて、要約文のトークン集合の重なりで近さを判定する。さらに、フレーム要約の`tags`集合の重なりが大きい場合も同一区間として扱う。代表summaryは区間先頭のsummaryを維持し、timelineの`tags`は区間内フレームのタグを出現順で重複なく統合する。タグ統合は`ChatGPT`と`review`のような共通タグで過分割を減らせる一方、画面や作業内容が変わっても同じタグが残る場合は過統合を起こす可能性がある。類似度の閾値は実データで調整する前提とし、embeddingやLLMによる高度な意味的統合は後続機能とする。

実動画での品質確認では、まず`frame_summaries`から`timeline`へのまとまり方を確認する。要約品質が低い場合、その上に乗るイベント候補や検索の品質も下がるため、イベント分類より先にフレーム要約とタイムライン区間の妥当性を評価する。
タグ統合の品質確認では、同じ実録画に対してタグ統合あり/なしのtimelineを比較し、過分割が減るか、過統合が増えるかを記録する。

## event_detector

責務:

- `timeline`を時系列順に読み込む
- 各タイムライン区間をイベント候補に変換する
- `kind`、`start_seconds`、`end_seconds`、`summary`、`timeline_index`、`importance_score`を持つ`events`を生成する
- MVP直後の最小実装では`kind`を`activity`に固定する

現時点では`timeline`と`events`は近い構造だが、後続の検索UIや重要度判定で`kind`を使えるように、イベント候補として別配列に分けて保存する。`coding`、`chat`、`browser`などの詳細分類、重要度判定、音声認識やシーン分割との統合は後続機能とする。

軽量な重要度判定では、外部AIを使わず区間の長さから`importance_score`を計算する。現時点の値は実質的にはduration scoreだが、後続でLLMやイベント種別を加えて重要度として育てるため、出力名は`importance_score`のままにする。スコアは`0.0`から`1.0`の範囲に収める。

## video_clipper

責務:

- `timeline.json`を読み込む
- `storage.video_path`がある場合は元動画の参照先として優先し、ない場合は`video.path`を使う
- 指定された`timeline` indexの`start_seconds`と`end_seconds`を取得する
- `--padding-seconds`を前後に足し、開始時刻は`0`未満にならないようにする
- `ffmpeg`で指定区間をMP4として保存する
- 既定は高速なcopy切り出し、`--accurate`指定時は再エンコードして開始位置の正確さを優先する
- `--accurate`指定時は`--crf`と`--preset`でx264の画質と速度を指定できる
- `--start-index`/`--end-index`指定時は範囲内の各timeline区間を個別clipとして連番保存する
- `--tag`指定時は指定タグを含むtimeline区間を個別clipとして連番保存する
- `--output`省略時は`storage.timeline_path`または読み込んだ`timeline.json`の場所から`clips/`を推定する
- 存在しないindexや不正な区間はエラーにする

既定の切り出しは高速化を優先し、`ffmpeg -c copy`を使う。これはキーフレーム単位の切り出しになるため、開始位置が指定秒から少しずれる可能性がある。`--accurate`ではcopyを使わず再エンコードし、処理時間より開始位置の正確さを優先する。再エンコード時の既定値は`--crf 18`、`--preset veryfast`とする。`--crf`と`--preset`はcopy切り出しでは指定できない。複数indexとタグ別の連番切り出しでは、`--output`を出力ディレクトリとして扱い、`timeline_000003.mp4`のように`timeline_<index6桁>.mp4`を保存する。`--output`がない場合、`storage.timeline_path`が`/mnt/video-timeline/timelines/sample.json`なら`/mnt/video-timeline/clips/`を既定出力先にする。この推定は、共有ルート直下に`timelines`と`clips`を兄弟ディレクトリとして置くMVP運用向けの挙動とし、`archive/timelines`のような別構成では`--output`で明示する。タグ別切り出しは`timeline[].tags`と対応する`events[].tags`への大文字小文字を区別しない完全一致で対象indexを選ぶ。

#38の完了範囲は、サーバー共有上の`timeline.json`だけをCLIに渡し、`storage.video_path`から共有上の元動画を参照してclipを生成できる状態とする。HTTP APIや常駐サーバープロセス経由で切り出す機能は別の後続機能として扱う。将来、共有ディレクトリ構成を変える場合は、`storage.clips_dir`をJSONに持たせるか、`storage_root`と`videos/sample.mp4`、`timelines/sample.json`、`clips/`のような相対パスを組み合わせる方式に拡張する。

## timeline_searcher

責務:

- `timeline.json`を読み込む
- `timeline[].summary`と`timeline[].tags`を検索対象にする
- `events[].timeline_index`で対応するイベントを引き、`events[].kind`、`events[].summary`、`events[].tags`を検索対象に加える
- 大文字小文字を区別せずqueryを部分一致検索する
- マッチしたtimeline index、時刻範囲、summaryを表示用に整形する
- 空結果はエラーにせず、CLI側で`no matches`として表示する

検索CLIはブラウザUIやタグ別clip生成の前段階として扱う。検索結果の時刻表記は小数秒を切り捨て、`MM:SS`または`HH:MM:SS`に整形し、`3  01:20-04:10  ChatGPTで仕様相談`のように1行で確認できる形にする。

## timeline_html_exporter

責務:

- `timeline.json`を読み込む
- `video`と`analysis`のメタデータを表示する
- `timeline`のindex、時刻範囲、summary、tagsを表で表示する
- `events`のkind、時刻範囲、summary、timeline_index、importance_score、tagsを表で表示する
- HTML内の値をエスケープする
- CSSやJavaScriptに依存しない静的HTMLとして保存する

HTML出力CLIはWebUI前段の確認用とし、生成済み`timeline.json`をブラウザで素早く眺めるための最小表示にする。時刻表記は検索CLIと同じく小数秒を切り捨て、`01:20-04:10`のように表示する。`timeline`がないJSONはエラーにし、`events`がないJSONは空の一覧として扱う。dictではない`timeline`/`events`要素は不正なJSONとしてエラーにする。
