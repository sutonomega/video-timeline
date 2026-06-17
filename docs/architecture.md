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
- scene_detector
- transcript_loader
- frame_summarizer
- timeline_generator
- event_detector
- video_clipper
- timeline_searcher
- timeline_html_exporter
- app_config

## configuration and storage policy

設定ファイルはTOML、生成物はJSONに固定する。TOMLは人が編集するアプリケーション設定に使い、JSONは解析結果、APIレスポンス、検索インデックスなど機械処理とデータ交換を優先する生成物に使う。`timeline` 出力、`frame_summaries`、APIレスポンスをTOML化することは非目標とする。

`video_timeline.toml` は、ローカルSSD、外付けSSD、NAS、SMB共有、NFSなどの媒体差を意識せず、指定された `storage.root` 配下の標準ディレクトリを使うための既定値を管理する。プログラムは保存先種別を判定しない。明示されたパスは通常のファイルパスとして扱い、TOMLはファイル名だけを指定したときの解決規則として使う。

現在実装する設定は `[storage]` のみとする。

```toml
[storage]
root = "/mnt/video-timeline"
videos_dir = "videos"
frames_dir = "frames"
timelines_dir = "timelines"
clips_dir = "clips"
html_dir = "html"
```

将来の設定は `AppConfig` の下にセクションを追加する。方向性は次の形にする。

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

`videos/`、`frames/`、`timelines/`、`clips/`、`html/` は `storage.root` 直下の標準ディレクトリとして扱う。短いファイル名を指定した場合、動画入力は `videos/`、timeline JSONは `timelines/`、clip出力は `clips/`、HTML出力は `html/` に解決する。フレーム画像は `frames/` をベースディレクトリとし、動画ごとに `<video_stem>_<path_hash>/` を作る。

CLI引数とTOML設定の優先順位は次の通りとする。

1. ディレクトリを含む明示パス、絶対パス、通常の相対パスは設定より優先し、そのまま使う。
2. ファイル名だけの指定で `video_timeline.toml` が見つかる場合は、`storage.root` と各ディレクトリ設定から解決する。
3. ファイル名だけの指定で `video_timeline.toml` がない場合は、従来通りカレントディレクトリ基準の通常パスとして扱う。ただし動画解析で `--output` を省略できるのは設定ファイルがある場合だけとする。
4. CLI引数とTOMLが同じ種類の値を指定できる場合は、CLI引数を優先する。
5. batch CLIは `--batch` または `--input-dir` で明示する。`video_timeline.toml` がある場合、`--batch` だけで `<storage.root>/<storage.videos_dir>` を入力、`<storage.root>/<storage.timelines_dir>` を出力にする。ファイル名だけの `--input-dir` と `--output-dir` も `storage.root` 配下へ解決する。設定ファイルがない場合は従来通り `--input-dir` と `--output-dir` を必須にする。

生成JSONの `storage` は、実際に参照した動画、フレーム保存先、timeline保存先を記録するメタデータとする。現時点では即時利用を優先し、解決後のパスを `storage.video_path`、`storage.frames_dir`、`storage.timeline_path` に保存する。`storage.mode` は保存しない。別PCや別マウント先での移動性が必要になった段階で、`storage.root` と `videos/sample.mp4`、`timelines/sample.json` のような相対パスを組み合わせる形式へ拡張する。

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
- 長い動画でも停止して見えないよう、抽出予定枚数、抽出中の番号、対象時刻をCLI進捗として通知する

CLIから使う場合は、`--frames-dir`をベースディレクトリとして扱い、動画ごとに`<frames-dir>/<video_stem>_<path_hash>/`へ保存する。`path_hash`は解決済み入力パスから作る短いhashで、`videos/a/sample.mp4`と`videos/b/sample.mp4`のような同名動画を連続実行してもフレーム画像が同じディレクトリに混ざらないようにする。

## scene_detector

責務:

- `ffmpeg` の scene detection を使い、画面の大きな変化時刻を `scene_boundaries` として抽出する
- `time_seconds`、`score`、`source` を持つ境界情報を生成する
- `scene_boundaries` は timeline 生成の主判断には使わず、品質確認や後続の区間調整に使う補助情報として保存する
- 長い動画でも停止して見えないよう、全フレームの `scene_score` を読みながら `ffmpeg -progress pipe:1` の処理済み時刻をCLI進捗として通知する
- 検出失敗時は動画解析全体を止めず、空の `scene_boundaries` として扱えるようにする

`scene_boundaries` は `frame_summaries`、`timeline`、`events` と同じJSON内のトップレベル配列として保存する。`timeline` は引き続き summary / tags の類似度で生成し、scene boundary は「この時刻で画面が大きく変わった可能性がある」という補助情報に留める。scene boundary 検出中の進捗表示はCLI UXのための副作用であり、保存する `scene_boundaries` の形式は変えない。scene boundary だけで timeline を分割すること、シーン境界をイベントと同一視すること、VL要約なしで動画内容を理解した扱いにすることは非目標とする。

## transcript_loader

責務:

- 外部ASRや手動生成されたtranscript JSONを読み込む
- `start_seconds`、`end_seconds`、`text`、`source`、任意の`speaker`を持つ `transcripts` を生成する
- `transcripts` は timeline 生成の主判断には使わず、発話や環境音の補助情報として保存する
- `timeline` や `events` とは時刻の重なりで後から紐づけられる形にする
- 読み込めないJSON、必須項目がないsegment、不正な時刻範囲はエラーにする

`transcripts` は `scene_boundaries` と同じ補助情報として、JSON内のトップレベル配列に保存する。現時点ではローカルASRモデルの実行、音声抽出、transcriptを使ったtimeline分割、transcriptからのイベント重要度判定は行わない。MVP後の拡張として、`--transcript-json` で外部ASR結果を読み込み、既存のVLフレーム要約、timeline、eventsと同じ生成JSONに同梱する。ローカルASR候補は Whisper 系、faster-whisper、whisper.cpp のような単体実行可能なものを後続で検討する。

入力JSONは、トップレベル配列、`{"transcripts":[...]}`、またはWhisper系に多い `{"segments":[...]}` を受け入れる。標準形では `start_seconds` / `end_seconds` を使い、`segments` 互換では `start` / `end` も読み取る。`source` がない場合は `external_asr` として保存する。

## storage metadata

責務:

- CLIで生成したJSONに `storage` を保存する
- `storage.video_path` に元動画の参照先を保存する
- `storage.frames_dir` に抽出フレームの保存ディレクトリを保存する
- `storage.timeline_path` にtimeline JSONの保存先を保存する

`storage` は保存先種別を判定するためのものではなく、実際に参照したパスを記録するためのメタデータとする。明示パスを渡した場合はそのパスを保存し、`video_timeline.toml` の短縮解決を使った場合は解決後の `storage.root` 配下のパスを保存する。clipを実行する場合は、この `storage` 情報と従来の `video.path` を使って元動画とフレーム保存先を解決する。

共有ストレージの例は `\\192.168.10.112\video-timeline` とする。Windows共有パスを使う場合も、CLIには通常のパス文字列として渡し、JSONの `storage.video_path`、`storage.frames_dir`、`storage.timeline_path` に同じ参照先を記録する。

共有ストレージ設定は、ローカルSSD、外付けSSD、NAS、SMB共有、NFSなど、媒体を問わず `root` 配下の `videos/`、`frames/`、`timelines/`、`clips/`、`html/` を使うための土台とする。将来は `storage.root` と相対パスを使い、`video_path`、`frames_dir`、`timeline_path` を `videos/a.mp4` や `timelines/a.json` のように保存する方式へ寄せる。

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

VLプロンプトでは、自由なタグ列ではなく`primary_tag`と`secondary_tags`を返すように指定する。`secondary_tags` は必ず `secondary_tags` という配列キーで返す。`secondary_tags[]` というキー名は使わない。PCやスマホの画面が主対象のときは`chatgpt`、`github`、`vscode`、`terminal`、`browser`、`youtube`、`discord`、`game`、`document`、`other`を優先し、料理、食事、家事、外出、移動などの生活動画では`cooking`、`oatmeal`、`rice_cooker`、`eating`、`shopping`、`walking`、`exercise`、`cleaning`、`travel`、`study`を優先する。適切な候補がない場合は、将棋、音楽制作、動画編集、Blender、通院のような短い自由タグも許可する。`tags`は後方互換のため残し、保存時は`primary_tag`と`secondary_tags`を結合した配列として扱う。古い`tags`のみのVL応答は先頭タグを`primary_tag`、残りを`secondary_tags`として扱う。

VLがJSON以外の文章を返した場合は、従来通り全文を`summary`として保存し、`primary_tag`は`other`、`secondary_tags`は空にする。`summary`にJSONコードブロックや前後の説明文が混入した場合は、先頭のJSONオブジェクトを切り出してから読み取る。JSONが閉じていない場合は `summary` と `primary_tag` だけを正規表現で拾い、`secondary_tags` は空配列にする。`secondary_tags[]` のような誤記は `secondary_tags` として救済する。`summary` の中にJSON文字列が埋まっている場合は、その内側も再解釈する。完全には復元できない場合だけ、再問い合わせはせず、従来通り全文を`summary`として扱う。`other`は判定不能時の退避先なので、実データで多発する場合はtimelineのタグ類似統合から除外するか、自由タグや事前定義タグの追加で減らす。

## cli batch mode

責務:

- 入力ディレクトリ配下の`mp4`を再帰的に検出する
- 検出した`mp4`を全件保持せず順次処理する
- 動画ごとに`<output-dir>/<video_stem>_<path_hash>/`を作る
- 各動画の`timeline.json`と`frames/`を同じ動画専用ディレクトリに保存する
- `video_timeline.toml` がある場合、`--batch` だけで `<storage.root>/<storage.videos_dir>` を入力、`<storage.root>/<storage.timelines_dir>` を出力として扱う
- `video_timeline.toml` がある場合、短い `--input-dir videos` を `<storage.root>/<storage.videos_dir>`、短い `--output-dir timelines` を `<storage.root>/<storage.timelines_dir>` として扱う
- `video_timeline.toml` があり `--output-dir` を省略した場合は `<storage.root>/<storage.timelines_dir>` を使う
- batchの出力構造は通常CLIの `timelines/<video_stem>.json` には寄せず、同名動画の衝突を避けるため動画別ディレクトリを維持する
- 1本の動画で失敗しても残りの動画を続行する
- 最後に成功件数と失敗件数を表示する

通常CLIは1本の動画を対象にするため、短い `sample1.mp4` を `<storage.root>/<videos_dir>/sample1.mp4` として読み、出力JSONを `<storage.root>/<timelines_dir>/sample1.json` に置く。batch CLIは複数動画を対象にするため、入力と出力はディレクトリ単位で解決し、各動画の成果物は `<output-dir>/<video_stem>_<path_hash>/timeline.json` と `<output-dir>/<video_stem>_<path_hash>/frames/` にまとめる。

## timeline_generator

責務:

- `frame_summaries`を時系列順に読み込む
- 連続する同一`summary`を1つの区間にまとめる
- 連続する近い`summary`を1つの区間にまとめる
- 連続する近い`tags`を1つの区間にまとめる
- 要約が変わった地点で区間を分ける
- `start_seconds`、`end_seconds`、`summary`、`frame_indices`、`tags`を持つ`timeline`を生成する
- 最後の区間の`end_seconds`は動画の`duration_seconds`を使う

軽量な類似判定の最小実装では、正規化した文字列の完全一致に加えて、要約文のトークン集合の重なりで近さを判定する。`tags` の重なりは補助条件として扱い、summary の語彙がまったく重ならない場合はタグ一致だけで結合しない。代表summaryは区間先頭のsummaryを維持し、timelineの`tags`は区間内フレームのタグを出現順で重複なく統合する。タグ統合は`ChatGPT`と`review`のような共通タグで過分割を減らせる一方、画面や作業内容が変わっても同じタグが残る場合は過統合を起こす可能性がある。`other`は判定不能時の退避先なので、タグ類似統合の類似度計算から除外する。類似度の閾値は実データで調整する前提とし、embeddingやLLMによる高度な意味的統合は後続機能とする。

実動画での品質確認では、まず`frame_summaries`から`timeline`へのまとまり方を確認する。要約品質が低い場合、その上に乗るイベント候補や検索の品質も下がるため、イベント分類より先にフレーム要約とタイムライン区間の妥当性を評価する。
タグ統合の品質確認では、同じ実録画に対してタグ統合あり/なしのtimelineを比較し、過分割が減るか、過統合が増えるかを記録する。

## event_detector

責務:

- `timeline`を時系列順に読み込む
- 各タイムライン区間から派生イベント候補を生成する
- `kind`、`start_seconds`、`end_seconds`、`summary`、`timeline_index`、`importance_score`を持つ`events`を生成する
- `timeline_index`で元の`timeline`区間へ戻れる参照関係を保持する
- 最小の分類実装では`summary`と`tags`から`review`、`terminal`、`coding`、`chat`、`cooking`、`browser`、`activity`へ分類する

`timeline`は動画を時系列の区間へ分けた一次構造とする。検索、clip、HTML表示の基本単位は`timeline`であり、`start_seconds`、`end_seconds`、`summary`、`frame_indices`、`tags`を保持する。`events`は`timeline`から派生する二次構造で、重要イベント抽出、`kind`分類、検索UIでの強調表示、将来の音声認識やシーン分割との統合に使う候補として扱う。

現時点では`timeline`と`events`は近い構造で、`summary`、`start_seconds`、`end_seconds`はほぼ同じ情報を持つ。これは意図的な暫定形であり、今の実装では`events`を削除せず、後続でLLMによる重要イベント抽出を追加できる余地として残す。ただし、`events`をtimelineの完全な複製として育てない。`events`に追加する情報は、`kind`、`importance_score`、分類理由、検索UI向けの強調情報など、timeline区間そのものとは異なる判断結果に限定する。

`events`の非目標は、timelineの代替データ構造になること、全てのtimeline項目を無条件に複製し続けること、clipの基本単位をeventsへ移すこととする。もし実データで`events`が長期的に`timeline`の単純コピーに留まる場合は、後続Issueで`events`を省略可能にするか、重要イベントだけを保存する形へ縮小する。

軽量な重要度判定では、外部AIを使わず区間の長さと`kind`から`importance_score`を計算する。まず区間長を60秒で満点になるduration scoreに変換し、`review`、`terminal`、`coding`、`chat`、`cooking`には小さなkind補正を足す。`browser`と`activity`は補正しない。スコアは`0.0`から`1.0`の範囲に収める。LLMによる重要度判定や分類理由の生成は後続機能とする。

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

#38の完了範囲は、共有ストレージ上の`timeline.json`だけをCLIに渡し、`storage.video_path`から共有上の元動画を参照してclipを生成できる状態とする。HTTP APIや常駐プロセス経由で切り出す機能は別の後続機能として扱う。将来、共有ディレクトリ構成を変える場合は、`storage.clips_dir`をJSONに持たせるか、`storage.root`と`videos/sample.mp4`、`timelines/sample.json`、`clips/`のような相対パスを組み合わせる方式に拡張する。

## timeline_searcher

責務:

- `timeline.json`を読み込む
- `timeline[].summary`と`timeline[].tags`を検索対象にする
- `events[].timeline_index`で対応する派生イベント候補を引き、`events[].kind`、`events[].summary`、`events[].tags`を補助検索対象に加える
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

## app_config

責務:

- `video_timeline.toml` を読み込む
- `AppConfig` としてアプリケーション設定全体を保持する
- `[storage]` の `root` と `videos_dir`、`frames_dir`、`timelines_dir`、`clips_dir`、`html_dir` を保持する
- 動画解析、`search`、`clip`、`export-html` の短いファイル名指定を `storage.root` 配下の入出力パスへ解決する
- 設定ファイルがない場合は既存のフルパス指定と `--output` 指定の動作を維持する

`AppConfig` はアプリケーション設定全体の入口とし、CLIが使うパス解決ヘルパーを公開する。CLIからよく使う `timeline_json_path()`、`video_file_path()`、`frames_directory_path()`、`clip_file_path()`、`html_output_path()` は `AppConfig` のメソッドとして公開し、呼び出し側が毎回 `config.storage` の内部構造を辿らなくてよい形にする。

`StoragePathConfig` は `[storage]` だけを表す値オブジェクトとし、`storage.root` と標準ディレクトリ名の管理に責務を限定する。VLモデル、timeline生成、HTML表示、検索条件のような設定は `StoragePathConfig` には入れず、将来 `AppConfig` の別セクションとして追加する。

設定ファイルはカレントディレクトリから親ディレクトリへ向かって `video_timeline.toml` を探索する。共有ストレージ構成の例は `/mnt/video-timeline/videos`、`/mnt/video-timeline/frames`、`/mnt/video-timeline/timelines`、`/mnt/video-timeline/clips`、`/mnt/video-timeline/html` とする。`export-html timeline` のように入力がファイル名だけで、設定ファイルがある場合は、入力JSONを `<storage.root>/<storage.timelines_dir>/timeline.json`、出力HTMLを `<storage.root>/<storage.html_dir>/timeline.html` として解決する。`export-html /tmp/sample.json --output /tmp/sample.html` のような既存の通常パス指定は設定ファイルがあっても壊さない。
