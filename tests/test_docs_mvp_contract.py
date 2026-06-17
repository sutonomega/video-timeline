from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocsMvpContractTest(unittest.TestCase):
    def test_mvp_doc_defines_cli_and_json_contract(self):
        text = (ROOT / "docs" / "mvp.md").read_text(encoding="utf-8")

        required_terms = [
            "PYTHONPATH=src python3 -m video_timeline.cli input.mp4 --output timeline.json",
            "PYTHONPATH=src python3 -m video_timeline.cli sample1.mp4",
            "PYTHONPATH=src python3 -m video_timeline.cli --input-dir recordings --output-dir timelines",
            "PYTHONPATH=src python3 -m video_timeline.cli --batch",
            "PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --index 3 --output clip.mp4",
            "PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --start-index 3 --end-index 7 --output clips",
            "PYTHONPATH=src python3 -m video_timeline.cli clip timeline.json --tag github --output clips",
            "PYTHONPATH=src python3 -m video_timeline.cli search sample1.json chatgpt",
            "PYTHONPATH=src python3 -m video_timeline.cli export-html timeline",
            "PYTHONPATH=src python3 -m video_timeline.cli export-html sample1",
            "/mnt/video-timeline/timelines/sample1.json",
            "/mnt/video-timeline/html/sample1.html",
            "`video_timeline.toml`",
            "`storage.root`",
            "`storage.timelines_dir`",
            "`storage.html_dir`",
            "[storage]",
            "[vl]",
            "[timeline]",
            "[html]",
            "[search]",
            'root = "/mnt/video-timeline"',
            "設定ファイルはTOML、生成物はJSON",
            "TOMLは設定専用、JSONはデータ交換形式",
            "動画解析とHTML出力は別コマンド",
            "CLI引数とTOML設定の優先順位",
            "明示パス",
            "ファイル名だけ",
            "CLI引数を優先",
            "batch CLIは `--batch` または `--input-dir` で明示",
            "`--batch` だけで `<storage.root>/<storage.videos_dir>` を入力",
            "設定ファイルがない場合は従来通り `--input-dir` と `--output-dir` を必須",
            "`AppConfig`",
            "`StoragePathConfig`",
            "カレントディレクトリから親ディレクトリへ向かって探索",
            "`input`",
            "`--output`",
            "`--batch`",
            "`--input-dir`",
            "`--output-dir`",
            "`clip timeline.json`",
            "`clip --index`",
            "`clip --start-index`",
            "`clip --end-index`",
            "`clip --tag`",
            "`clip --padding-seconds`",
            "`clip --accurate`",
            "`clip --crf`",
            "`clip --preset`",
            "`storage.timeline_path`",
            "`search timeline.json query`",
            "`export-html timeline.json`",
            "`export-html --output`",
            "`ffmpeg -c copy`",
            "`--accurate`",
            "`--crf`",
            "`--preset`",
            "`--interval-seconds`",
            "`--frames-dir`",
            "`--vl-model`",
            "`--transcript-json`",
            "`--vl-provider`",
            "`version`",
            "`generated_at`",
            "`video.path`",
            "`video.duration_seconds`",
            "`video.fps`",
            "`video.frame_count`",
            "`video.width`",
            "`video.height`",
            "`ffprobe`",
            "`ffmpeg`",
            "`frame_extractor`",
            "`frame_summarizer`",
            "`/api/generate`",
            "`frames/<video_stem>_<path_hash>/000010000.jpg`",
            "`custom_frames/<video_stem>_<path_hash>/`",
            "`index`",
            "`time_seconds`",
            "`image`",
            "`analysis.interval_seconds`",
            "`analysis.vl_provider`",
            "`analysis.vl_model`",
            "`storage.video_path`",
            "`storage.frames_dir`",
            "`storage.timeline_path`",
            "`storage.mode` は保存しない",
            "`scene_boundaries`",
            "`transcripts`",
            "`transcripts[].start_seconds`",
            "`transcripts[].end_seconds`",
            "`transcripts[].text`",
            "`transcripts[].source`",
            "`external_asr`",
            "`ffmpeg -progress pipe:1`",
            "scene detection progress: 01:20/10:00 (13%)",
            "Whisper 系",
            "faster-whisper",
            "whisper.cpp",
            "timeline生成の主判断には使わない",
            "`ollama`",
            "`gemma3:12b`",
            "`frame_summaries[].index`",
            "`frame_summaries[].time_seconds`",
            "`frame_summaries[].image`",
            "`frame_summaries[].summary`",
            "`frame_summaries[].primary_tag`",
            "`frame_summaries[].secondary_tags`",
            "`frame_summaries[].tags`",
            "`secondary_tags` は必ず `secondary_tags` という配列キーで返す",
            "JSONオブジェクトを切り出してから読み取る",
            "`secondary_tags[]` のような誤記は `secondary_tags` として救済する",
            "`summary` の中にJSON文字列が埋まっている場合",
            "JSONが閉じていない場合は `summary` と `primary_tag` だけを正規表現で拾い",
            "再問い合わせはせず",
            "`timeline[].tags`",
            "`<output-dir>/<video_stem>_<path_hash>/`",
            "`timeline.json`",
            "`timeline_000003.mp4`",
            "`timeline[].summary`",
            "`events[].kind`",
            "`events[].tags`",
            "`no matches`",
        ]

        missing_terms = [term for term in required_terms if term not in text]
        self.assertEqual(missing_terms, [])

    def test_existing_docs_link_to_mvp_spec(self):
        for relative_path in [
            "README.md",
            "docs/roadmap.md",
            "docs/architecture.md",
            "docs/acceptance.md",
            "docs/quality_review.md",
        ]:
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("mvp.md", text)

    def test_repository_includes_default_toml_config(self):
        config = (ROOT / "video_timeline.toml").read_text(encoding="utf-8")

        self.assertIn("[storage]", config)
        self.assertIn('root = "/mnt/video-timeline"', config)
        self.assertIn('timelines_dir = "timelines"', config)
        self.assertIn('html_dir = "html"', config)
        self.assertIn("# [vl]", config)
        self.assertIn("# [timeline]", config)
        self.assertIn("# [html]", config)
        self.assertIn("# [search]", config)

    def test_docs_record_mvp_acceptance(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        mvp = (ROOT / "docs" / "mvp.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        acceptance = (ROOT / "docs" / "acceptance.md").read_text(encoding="utf-8")

        self.assertIn("MVP accepted", readme)
        self.assertIn("docs/acceptance.md", readme)
        self.assertIn("[x] 短い検証用MP4とOllamaでのMVP受け入れ確認", roadmap)
        self.assertIn("`docs/mvp.md` の手順でCLIを実行できる", mvp)
        self.assertIn("MVPの受け入れ確認結果を `docs/acceptance.md` に記録している", mvp)
        self.assertNotIn("READMEの手順だけでCLIを実行できる", mvp)
        self.assertNotIn("docs/roadmap.mdでMVP完了として扱える", mvp)
        self.assertIn("docs/mvp.md の手順でCLIを実行し", acceptance)
        self.assertIn("qwen2.5vl:7b", acceptance)
        self.assertIn("PYTHONPATH=src python3 -m video_timeline.cli", acceptance)

    def test_readme_mentions_cli_progress_output(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("frame summarization started: 3/120", readme)
        self.assertIn("remaining: 12m 30s", readme)

    def test_architecture_defines_timeline_generator_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("timeline_generator", architecture)
        self.assertIn("start_seconds", architecture)
        self.assertIn("end_seconds", architecture)
        self.assertIn("frame_indices", architecture)
        self.assertIn("連続する近い`summary`", architecture)
        self.assertIn("代表summary", architecture)
        self.assertIn("軽量な類似判定", architecture)
        self.assertIn("summary の語彙がまったく重ならない場合はタグ一致だけで結合しない", architecture)
        self.assertIn("連続する近い`tags`", architecture)
        self.assertIn("timelineの`tags`", architecture)
        self.assertIn("過統合", architecture)
        self.assertIn("タグ類似統合の類似度計算から除外", architecture)
        self.assertIn("タグ統合あり/なし", architecture)
        self.assertIn("閾値は実データで調整", architecture)

    def test_architecture_defines_scene_detector_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("scene_detector", architecture)
        self.assertIn("scene_boundaries", architecture)
        self.assertIn("time_seconds", architecture)
        self.assertIn("score", architecture)
        self.assertIn("source", architecture)
        self.assertIn("timeline 生成の主判断には使わず", architecture)
        self.assertIn("品質確認や後続の区間調整", architecture)
        self.assertIn("ffmpeg -progress pipe:1", architecture)
        self.assertIn("CLI進捗", architecture)
        self.assertIn("保存する `scene_boundaries` の形式は変えない", architecture)
        self.assertIn("シーン境界をイベントと同一視すること", architecture)

    def test_architecture_defines_transcript_loader_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("transcript_loader", architecture)
        self.assertIn("transcripts", architecture)
        self.assertIn("start_seconds", architecture)
        self.assertIn("end_seconds", architecture)
        self.assertIn("text", architecture)
        self.assertIn("source", architecture)
        self.assertIn("speaker", architecture)
        self.assertIn("--transcript-json", architecture)
        self.assertIn("timeline 生成の主判断には使わず", architecture)
        self.assertIn("時刻の重なり", architecture)
        self.assertIn("ローカルASRモデルの実行", architecture)
        self.assertIn("Whisper 系", architecture)
        self.assertIn("faster-whisper", architecture)
        self.assertIn("whisper.cpp", architecture)

    def test_architecture_defines_per_video_frame_directory(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("<frames-dir>/<video_stem>_<path_hash>/", architecture)
        self.assertIn("同名動画", architecture)

    def test_architecture_defines_batch_cli_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("cli batch mode", architecture)
        self.assertIn("<output-dir>/<video_stem>_<path_hash>/", architecture)
        self.assertIn("timeline.json", architecture)
        self.assertIn("全件保持せず順次処理", architecture)
        self.assertIn("1本の動画で失敗しても残りの動画を続行", architecture)

    def test_architecture_defines_video_clipper_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("video_clipper", architecture)
        self.assertIn("video.path", architecture)
        self.assertIn("storage.video_path", architecture)
        self.assertIn("storage.timeline_path", architecture)
        self.assertIn("--padding-seconds", architecture)
        self.assertIn("ffmpeg", architecture)
        self.assertIn("キーフレーム単位", architecture)
        self.assertIn("--crf 18", architecture)
        self.assertIn("--preset veryfast", architecture)
        self.assertIn("--start-index", architecture)
        self.assertIn("--tag", architecture)
        self.assertIn("timeline_000003.mp4", architecture)
        self.assertIn("/mnt/video-timeline/clips/", architecture)
        self.assertIn("常駐プロセス", architecture)
        self.assertIn("storage.clips_dir", architecture)
        self.assertIn("storage.root", architecture)
        self.assertIn("完全一致", architecture)
        self.assertIn("複数index", architecture)

    def test_architecture_defines_timeline_searcher_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("timeline_searcher", architecture)
        self.assertIn("timeline[].summary", architecture)
        self.assertIn("timeline[].tags", architecture)
        self.assertIn("events[].kind", architecture)
        self.assertIn("events[].tags", architecture)
        self.assertIn("切り捨て", architecture)
        self.assertIn("no matches", architecture)
        self.assertIn("01:20-04:10", architecture)

    def test_architecture_defines_timeline_html_exporter_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("timeline_html_exporter", architecture)
        self.assertIn("video", architecture)
        self.assertIn("analysis", architecture)
        self.assertIn("timeline", architecture)
        self.assertIn("events", architecture)
        self.assertIn("静的HTML", architecture)
        self.assertIn("エスケープ", architecture)
        self.assertIn("01:20-04:10", architecture)
        self.assertIn("app_config", architecture)
        self.assertIn("AppConfig", architecture)
        self.assertIn("StoragePathConfig", architecture)
        self.assertIn("timeline_json_path()", architecture)
        self.assertIn("html_output_path()", architecture)
        self.assertIn("親ディレクトリへ向かって", architecture)

    def test_architecture_defines_storage_metadata_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("storage metadata", architecture)
        self.assertIn("storage.video_path", architecture)
        self.assertIn("storage.frames_dir", architecture)
        self.assertIn("storage.timeline_path", architecture)
        self.assertIn("保存先種別を判定するためのものではなく", architecture)
        self.assertIn("`storage.mode` は保存しない", architecture)
        self.assertIn("\\\\192.168.10.112\\video-timeline", architecture)
        self.assertIn("clips", architecture)
        self.assertIn("`storage.root` 配下のパス", architecture)
        self.assertIn("相対パス", architecture)

    def test_video_clipper_fixtures_do_not_use_storage_type(self):
        test_video_clipper = (ROOT / "tests" / "test_video_clipper.py").read_text(encoding="utf-8")

        self.assertNotIn('"mode": ' + '"server"', test_video_clipper)
        self.assertNotIn('"mode": ' + '"local"', test_video_clipper)

    def test_architecture_defines_config_storage_cli_policy(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("configuration and storage policy", architecture)
        self.assertIn("設定ファイルはTOML、生成物はJSON", architecture)
        self.assertIn("プログラムは保存先種別を判定しない", architecture)
        self.assertIn("ファイル名だけを指定したときの解決規則", architecture)
        self.assertIn("[storage]", architecture)
        self.assertIn("[vl]", architecture)
        self.assertIn("[timeline]", architecture)
        self.assertIn("[html]", architecture)
        self.assertIn("[search]", architecture)
        self.assertIn("CLI引数とTOML設定の優先順位", architecture)
        self.assertIn("明示パス", architecture)
        self.assertIn("CLI引数を優先", architecture)
        self.assertIn("batch CLIは `--batch` または `--input-dir` で明示", architecture)
        self.assertIn("`--batch` だけで `<storage.root>/<storage.videos_dir>`", architecture)
        self.assertIn("短い `--input-dir videos`", architecture)
        self.assertIn("短い `--output-dir timelines`", architecture)
        self.assertIn("動画別ディレクトリを維持", architecture)
        self.assertIn("通常CLIは1本の動画を対象", architecture)
        self.assertIn("batch CLIは複数動画を対象", architecture)
        self.assertIn("即時利用を優先", architecture)
        self.assertIn("`storage.root` と `videos/sample.mp4`", architecture)
        self.assertIn("StoragePathConfig` は `[storage]` だけを表す値オブジェクト", architecture)

    def test_architecture_defines_frame_summary_tags(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
        mvp = (ROOT / "docs" / "mvp.md").read_text(encoding="utf-8")

        self.assertIn("フレームごとの検索用タグ", architecture)
        self.assertIn("primary_tag", architecture)
        self.assertIn("secondary_tags", architecture)
        self.assertIn("事前定義タグ", architecture)
        self.assertIn("短い自由タグ", architecture)
        self.assertIn("PCやスマホの画面が主対象のとき", architecture)
        self.assertIn("料理、食事、家事、外出、移動などの生活動画", architecture)
        self.assertIn("other", architecture)
        self.assertIn("タグ類似統合から除外", architecture)
        self.assertIn("summary の補助条件として扱い", mvp)
        self.assertIn("小文字英数字", architecture)
        self.assertIn("日本語タグ", architecture)
        self.assertIn("保持する", architecture)
        self.assertIn("`secondary_tags` は必ず `secondary_tags` という配列キーで返す", architecture)
        self.assertIn("`secondary_tags[]` のような誤記は `secondary_tags` として救済する", architecture)
        self.assertIn("`summary` の中にJSON文字列が埋まっている場合", architecture)
        self.assertIn("JSONが閉じていない場合は `summary` と `primary_tag` だけを正規表現で拾い", architecture)
        self.assertIn("JSONコードブロックや前後の説明文が混入した場合", architecture)
        self.assertIn("完全には復元できない場合だけ", architecture)

    def test_architecture_defines_event_detector_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
        mvp = (ROOT / "docs" / "mvp.md").read_text(encoding="utf-8")

        self.assertIn("event_detector", architecture)
        self.assertIn("events", architecture)
        self.assertIn("timeline_index", architecture)
        self.assertIn("importance_score", architecture)
        self.assertIn("activity", architecture)
        self.assertIn("`review`、`terminal`、`coding`、`chat`、`cooking`、`browser`、`activity`へ分類", architecture)
        self.assertIn("検索UI", architecture)
        self.assertIn("区間の長さ", architecture)
        self.assertIn("duration score", architecture)
        self.assertIn("区間の長さと`kind`から`importance_score`を計算", architecture)
        self.assertIn("`browser`と`activity`は補正しない", architecture)
        self.assertIn("`timeline`は動画を時系列の区間へ分けた一次構造", architecture)
        self.assertIn("`events`は`timeline`から派生する二次構造", architecture)
        self.assertIn("重要イベント抽出", architecture)
        self.assertIn("`kind`分類", architecture)
        self.assertIn("timelineの完全な複製として育てない", architecture)
        self.assertIn("`events`の非目標", architecture)
        self.assertIn("clipの基本単位をeventsへ移すこと", architecture)
        self.assertIn("重要イベントだけを保存する形へ縮小", architecture)
        self.assertIn("`events` は `timeline_index` で元の `timeline` 区間へ戻れる派生イベント候補", mvp)
        self.assertIn("`events` を timeline の代替構造にはしない", mvp)

    def test_roadmap_prioritizes_real_video_quality_review_before_event_importance(self):
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        quality_review = roadmap.index("実動画でframe_summaryからtimelineまでの品質を確認する")
        event_importance = roadmap.index("イベント重要度判定")
        self.assertLess(quality_review, event_importance)

    def test_roadmap_marks_lightweight_event_importance_done(self):
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("[x] イベント候補に軽量な重要度スコアを追加する（#30）", roadmap)
        self.assertIn("[x] summary/tagsを使ったイベントkind分類と重要度補正（#90）", roadmap)
        self.assertIn("[x] シーン分割をtimeline生成の補助情報として追加する（#88）", roadmap)
        self.assertIn("[x] 音声認識結果をtimeline補助情報として保存する（#89）", roadmap)
        self.assertIn("[x] シーン境界検出中の進捗表示を追加する（#98）", roadmap)
        self.assertIn("[ ] LLMを使ったイベント重要度判定と分類理由生成", roadmap)
        self.assertIn("[ ] ローカルASR実行とtranscript品質確認", roadmap)

    def test_roadmap_tracks_per_video_frame_directory(self):
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("[x] フレーム出力先を動画単位で分離する（#32）", roadmap)

    def test_roadmap_tracks_batch_cli(self):
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("[x] 複数動画を一括解析できるCLIを追加する（#33）", roadmap)

    def test_roadmap_tracks_frame_summary_tags(self):
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("## MVP後に実装済み", roadmap)
        self.assertIn("## 次にやること", roadmap)
        self.assertIn("MVP完了後の拡張として", roadmap)
        self.assertIn("[x] フレーム要約にタグ付けを追加する（#34）", roadmap)
        self.assertIn("[x] タグを使ったtimeline統合ロジックを実装する（#35）", roadmap)
        self.assertIn("[x] 実録画でタグ統合品質を確認する（#43）", roadmap)
        self.assertIn("[x] timeline区間から動画を切り出すCLIを追加する（#36）", roadmap)
        self.assertIn("[x] accurateなtimeline切り出しモードを追加する（#46）", roadmap)
        self.assertIn("[x] accurate切り出しの画質と速度を指定できるようにする（#53）", roadmap)
        self.assertIn("[x] timeline index範囲をまとめて切り出せるようにする（#47）", roadmap)
        self.assertIn("[x] 動画とフレーム画像の保存先を共有ストレージ対応にする（#37）", roadmap)
        self.assertIn("[x] 共有ストレージ上でtimeline区間の動画切り出しを実行できるようにする（#38）", roadmap)
        self.assertIn("[x] VLタグを事前定義タグとprimary_tagへ寄せる（#48）", roadmap)
        self.assertIn("[x] timeline検索CLIを追加する（#49）", roadmap)
        self.assertIn("[x] タグ別クリップ生成CLIを追加する（#50）", roadmap)
        self.assertIn("[x] タイムラインHTML出力CLIを追加する（#51）", roadmap)
        self.assertIn("[x] 設定ファイルで共有ストレージの保存先を管理する（#77）", roadmap)
        self.assertIn("[x] 設定・ストレージ・CLI UXの責務を整理する（#79）", roadmap)
        self.assertIn("[x] storage mode 概念の残骸を削除する（#81）", roadmap)
        self.assertIn("[x] events の責務を再定義する（#83）", roadmap)
        self.assertIn("[x] batch CLI と通常CLIのストレージ解決を揃える（#82）", roadmap)

    def test_quality_review_records_frame_summary_to_timeline_findings(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        quality_review = (ROOT / "docs" / "quality_review.md").read_text(encoding="utf-8")

        self.assertIn("docs/quality_review.md", readme)
        self.assertIn("[x] 実動画でframe_summaryからtimelineまでの品質を確認する（#20）", roadmap)
        self.assertIn("workflow_chat_coding.mp4", quality_review)
        self.assertIn("browser_docs_pr.mp4", quality_review)
        self.assertIn("repeated_chat_then_test.mp4", quality_review)
        self.assertIn("過分割", quality_review)
        self.assertIn("類似要約の意味的な区間統合", quality_review)

    def test_roadmap_marks_semantic_summary_grouping_done(self):
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("[x] 類似要約の軽量な区間統合（#25）", roadmap)
        self.assertIn("[x] 類似統合の閾値を実データで比較する（#28）", roadmap)

    def test_quality_review_records_similarity_threshold_comparison(self):
        quality_review = (ROOT / "docs" / "quality_review.md").read_text(encoding="utf-8")

        self.assertIn("SUMMARY_SIMILARITY_THRESHOLD = 0.6", quality_review)
        self.assertIn("完全一致のみ", quality_review)
        self.assertIn("類似統合あり", quality_review)
        self.assertIn("workflow_chat_coding.mp4", quality_review)
        self.assertIn("browser_docs_pr.mp4", quality_review)
        self.assertIn("repeated_chat_then_test.mp4", quality_review)
        self.assertIn("閾値 `0.6` は、今回の3本では維持でよい。", quality_review)

    def test_quality_review_records_tag_grouping_comparison(self):
        quality_review = (ROOT / "docs" / "quality_review.md").read_text(encoding="utf-8")

        self.assertIn("TAG_SIMILARITY_THRESHOLD = 0.5", quality_review)
        self.assertIn("use_tag_similarity=False", quality_review)
        self.assertIn("use_tag_similarity=True", quality_review)
        self.assertIn("タグ統合なし", quality_review)
        self.assertIn("タグ統合あり", quality_review)
        self.assertIn("過統合", quality_review)
        self.assertIn("実際のOBS録画では引き続き確認が必要", quality_review)


if __name__ == "__main__":
    unittest.main()
