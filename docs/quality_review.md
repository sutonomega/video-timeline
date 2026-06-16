# 品質確認

## 2026-06-11 frame_summary to timeline

Issue #20 の確認として、実利用に近い画面録画風の検証MP4を3本生成し、既定の `interval_seconds=10` でCLIを実行した。

生成物は `/tmp/video-timeline-quality` に置き、リポジトリにはコミットしない。

MVPの基本仕様は[mvp.md](mvp.md)に従う。

## 環境

- Python: `python3`
- 動画処理: `ffmpeg` / `ffprobe`
- VLプロバイダー: `ollama`
- VLモデル: `qwen2.5vl:7b`
- CLI進捗表示: `frame summarization started: N/M (..., remaining: ...)`

## 実行コマンド

例:

```bash
PYTHONPATH=src python3 -m video_timeline.cli /tmp/video-timeline-quality/workflow_chat_coding.mp4 --output /tmp/video-timeline-quality/workflow_timeline.json --frames-dir /tmp/video-timeline-quality/workflow_frames
```

確認した動画:

- `workflow_chat_coding.mp4`: ChatGPT仕様相談、VSCode実装、Terminalテスト
- `browser_docs_pr.mp4`: GitHub Issue確認、README編集、PR作成
- `repeated_chat_then_test.mp4`: ChatGPT仕様相談、ChatGPT要件相談、Terminalテスト

## 良かった点

`frame_summaries` は、画面上の主要な作業内容を十分に拾えていた。

良い例:

```json
{
  "time_seconds": 0.0,
  "summary": "ユーザーはChatGPTの仕様について議論している。"
}
```

```json
{
  "time_seconds": 10.0,
  "summary": "ユーザーはREADMEドキュメントの編集を行っている。"
}
```

```json
{
  "time_seconds": 20.0,
  "summary": "ユーザーはプルリクエストの作成を行っている。"
}
```

`workflow_chat_coding.mp4` と `browser_docs_pr.mp4` では、10秒ごとの異なる作業がそれぞれ別の `timeline` 区間になり、期待どおりだった。

良いtimeline例:

```json
{
  "start_seconds": 10.0,
  "end_seconds": 20.0,
  "summary": "ユーザーはREADMEドキュメントの編集を行っている。",
  "frame_indices": [1]
}
```

## 気になった点

`timeline` は正規化した `summary` の完全一致だけで統合しているため、意味的には近い連続区間でも、要約文が少し違うと別区間になる。

過分割の例:

```json
[
  {
    "start_seconds": 0.0,
    "end_seconds": 10.0,
    "summary": "ユーザーはChatGPTの仕様について議論しているようです。",
    "frame_indices": [0]
  },
  {
    "start_seconds": 10.0,
    "end_seconds": 20.0,
    "summary": "ユーザーはChatGPTの要件について議論しているようです。",
    "frame_indices": [1]
  }
]
```

この2区間はどちらも「ChatGPTで仕様・要件を相談している」活動として扱える可能性が高い。検索や振り返りでは1つの区間にまとまった方が使いやすい。

## 判定

- `frame_summaries` の品質は、画面上のテキストが明確な動画ではMVP後続機能の土台として十分に使える。
- `timeline` は異なる活動の切り分けには使える。
- ただし、同じ活動が近い表現で続く場合は過分割しやすい。
- 完全一致だけでなく、近い要約を統合する仕組みが必要。

## 改善候補

- 類似要約の意味的な区間統合を追加する（#25）
- 類似統合の閾値を実データで比較して調整する
- `timeline` 区間ごとに代表summaryを生成する
- `events.kind` の分類は、timeline統合品質を改善した後に進める

## 2026-06-11 類似統合閾値の比較

Issue #28 の確認として、Issue #20 で使った3本の検証動画の `frame_summaries` から、完全一致のみの `timeline` と軽量類似統合ありの `timeline` を比較した。

軽量類似統合の閾値:

```text
SUMMARY_SIMILARITY_THRESHOLD = 0.6
```

比較結果:

| 検証動画 | 完全一致のみ | 類似統合あり | 判定 |
| --- | ---: | ---: | --- |
| `workflow_chat_coding.mp4` | 3区間 | 3区間 | 過統合なし |
| `browser_docs_pr.mp4` | 3区間 | 3区間 | 過統合なし |
| `repeated_chat_then_test.mp4` | 3区間 | 2区間 | ChatGPT相談の過分割が改善 |

`workflow_chat_coding.mp4` では、ChatGPT相談、VSCode実装、Terminalテストが別区間のままだった。

`browser_docs_pr.mp4` では、GitHub Issue確認、README編集、PR作成が別区間のままだった。

`repeated_chat_then_test.mp4` では、次の2区間が1つにまとまった。

Before:

```json
[
  {
    "start_seconds": 0.0,
    "end_seconds": 10.0,
    "summary": "ユーザーはChatGPTの仕様について議論しているようです。",
    "frame_indices": [0]
  },
  {
    "start_seconds": 10.0,
    "end_seconds": 20.0,
    "summary": "ユーザーはChatGPTの要件について議論しているようです。",
    "frame_indices": [1]
  }
]
```

After:

```json
{
  "start_seconds": 0.0,
  "end_seconds": 20.0,
  "summary": "ユーザーはChatGPTの仕様について議論しているようです。",
  "frame_indices": [0, 1]
}
```

判定:

- 閾値 `0.6` は、今回の3本では維持でよい。
- 明確に異なる作業を結合する過統合は確認されなかった。
- Issue #20 で見つかったChatGPT相談の過分割は改善した。
- ただし検証動画は短く、画面上の文字も明確なため、実録画での継続確認は必要。

次に確認したいこと:

- 実際の画面録画で、エディタ操作やブラウザ操作が長く続く場合の統合具合を見る。
- 閾値を設定値化するかは、実録画で過統合・過分割が見えてから判断する。

## 2026-06-12 タグ統合品質の比較

Issue #43 の確認として、Issue #20 / #28 と同じ3本の画面録画風検証動画を再生成し、Ollama `qwen2.5vl:7b` で `summary` と `tags` を生成した。生成物は `/tmp/video-timeline-quality` に置き、リポジトリにはコミットしない。

今回の比較では、同じ `frame_summaries` から次の2種類の `timeline` を生成した。

- タグ統合なし: `build_timeline(..., use_tag_similarity=False)`
- タグ統合あり: `build_timeline(..., use_tag_similarity=True)`

タグ類似統合の閾値:

```text
TAG_SIMILARITY_THRESHOLD = 0.5
```

比較結果:

| 検証動画 | タグ統合なし | タグ統合あり | 判定 |
| --- | ---: | ---: | --- |
| `workflow_chat_coding.mp4` | 3区間 | 3区間 | 過統合なし |
| `browser_docs_pr.mp4` | 3区間 | 3区間 | 過統合なし |
| `repeated_chat_then_test.mp4` | 3区間 | 3区間 | 過統合なし。ただし過分割改善もなし |

`workflow_chat_coding.mp4` では、ChatGPT計画、VSCode実装、Terminalテストが別区間のままだった。タグはそれぞれ `chatgpt/video_production`、`vscode/python`、`pytest/terminal` となり、期待どおり結合されなかった。

`browser_docs_pr.mp4` では、GitHubレビュー、README編集、PR作成が別区間のままだった。先頭と末尾に `github` が含まれたが、連続していないため結合されなかった。

`repeated_chat_then_test.mp4` では、最初の2フレームがどちらも `chatgpt` を含んだが、Jaccard類似度は `1/4 = 0.25` で閾値 `0.5` 未満だったため結合されなかった。3フレーム目はTerminalテスト画面にもかかわらず `chatgpt` タグが混じったが、`chatgpt/coding` として扱われ、前区間とは結合されなかった。

代表的な `frame_summaries`:

```json
[
  {
    "time_seconds": 0.0,
    "summary": "ChatGPTを使用してビデオのタイムラインを計画している。",
    "tags": ["chatgpt", "video_production"]
  },
  {
    "time_seconds": 10.0,
    "summary": "ChatGPTを使用して計画書を作成するための要件とタグを設定している。",
    "tags": ["chatgpt", "planning_requirements", "tags"]
  },
  {
    "time_seconds": 20.0,
    "summary": "ターミナルでpytestテストを実行しているユーザーがいます。",
    "tags": ["chatgpt", "coding"]
  }
]
```

判定:

- 閾値 `0.5` は、今回の3本では明確な過統合を起こさなかった。
- 一方で、`chatgpt` だけが共通する程度では過分割改善につながらなかった。
- タグ統合は維持してよいが、過分割改善を狙うには `planning` 系タグの揺れを減らすプロンプト改善や、主要タグと補助タグを分ける設計が必要になる可能性がある。
- 今回は画面録画風の検証動画であり、実際のOBS録画では引き続き確認が必要。

## 2026-06-14 VLモデル比較: qwen2.5vl:7b と gemma3:12b

料理動画 `sample1.mp4` を使い、OllamaのVLモデルを `qwen2.5vl:7b` から `gemma3:12b` に変えて品質を比較した。

確認観点:

- `summary` が料理工程を説明できているか
- `primary_tag` / `secondary_tags` が工程の違いを残せているか
- JSON応答が壊れにくいか
- `frame_summaries` から生成される `timeline` が自然に分かれるか

### qwen2.5vl:7b

確認された課題:

- `secondary_tags[]` のキー名が途中で崩れ、JSONとして閉じない応答が多く、`primary_tag=other` へのフォールバックが発生した
- `other` が多いため、timeline統合やタグ別clipの判断材料として弱かった
- 料理動画にもかかわらず `browser` や `youtube` が出る誤認識があった
- `oatmeal`、`rice_cooker`、`eating` など、料理工程を区別するタグが十分に出なかった

代表的な問題例:

```text
{"summary":"お粥を混ぜる","primary_tag":"cooking","secondary_tags[]}
```

この形式はJSONとして閉じていないため、単純な `json.loads()` では救えない。現行実装では `summary` と `primary_tag` を正規表現で拾う部分復元を入れているが、モデル応答自体の安定性は低い。

### gemma3:12b

改善された点:

- `summary` が料理工程をより具体的に説明した
- `secondary_tags` が豊富になり、`rice_cooker`、`oatmeal`、`eating` などが出た
- 料理動画の工程分割が自然になった
- 確認した範囲ではJSON破損が目立たなかった

代表的な改善:

- オートミール投入
- 加熱
- 炊き上がり
- お粥を混ぜる
- 食べる、すくう

これらが `summary` とタグに残り、後続の `timeline` 品質を評価できる状態になった。

### 判定

料理動画の確認では `gemma3:12b` の方が `qwen2.5vl:7b` より安定していたため、既定VLモデルを `gemma3:12b` に変更する判断は妥当とする。

一方で、`gemma3:12b` は `qwen2.5vl:7b` より重いため、軽量に試す場合はCLIの `--vl-model qwen2.5vl:7b` を使える状態を維持する。

### 今後の確認

- `sample1.mp4` 以外の生活動画で `gemma3:12b` の安定性を確認する
- 画面録画系動画でも `qwen2.5vl:7b` と `gemma3:12b` を比較する
- `export-html` で `timeline`、`summary`、`tags` を見やすくし、JSONを直接読まずに品質確認できるようにする
