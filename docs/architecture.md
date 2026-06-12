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

## frame_summarizer

責務:

- 抽出済みフレームをVLで要約
- フレームごとの検索用タグを生成する
- タグを小文字英数字、`_`、日本語中心に正規化する
- 日本語タグは検索やtimeline統合に使えるよう保持する
- Ollama HTTP API呼び出しの境界を提供
- video、analysis、frame_summariesを持つJSON構造の生成
- UTF-8 JSONファイルへの保存

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
- `video.path`から元動画を参照する
- 指定された`timeline` indexの`start_seconds`と`end_seconds`を取得する
- `--padding-seconds`を前後に足し、開始時刻は`0`未満にならないようにする
- `ffmpeg`で指定区間をMP4として保存する
- 存在しないindexや不正な区間はエラーにする
