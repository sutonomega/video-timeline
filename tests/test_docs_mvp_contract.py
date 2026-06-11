from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocsMvpContractTest(unittest.TestCase):
    def test_mvp_doc_defines_cli_and_json_contract(self):
        text = (ROOT / "docs" / "mvp.md").read_text(encoding="utf-8")

        required_terms = [
            "PYTHONPATH=src python3 -m video_timeline.cli input.mp4 --output timeline.json",
            "`input`",
            "`--output`",
            "`--interval-seconds`",
            "`--frames-dir`",
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
            "`index`",
            "`time_seconds`",
            "`image`",
            "`analysis.interval_seconds`",
            "`analysis.vl_provider`",
            "`analysis.vl_model`",
            "`ollama`",
            "`qwen2.5vl:7b`",
            "`frame_summaries[].index`",
            "`frame_summaries[].time_seconds`",
            "`frame_summaries[].image`",
            "`frame_summaries[].summary`",
        ]

        missing_terms = [term for term in required_terms if term not in text]
        self.assertEqual(missing_terms, [])

    def test_existing_docs_link_to_mvp_spec(self):
        for relative_path in [
            "README.md",
            "docs/roadmap.md",
            "docs/architecture.md",
            "docs/acceptance.md",
        ]:
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("mvp.md", text)

    def test_docs_record_mvp_acceptance(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        acceptance = (ROOT / "docs" / "acceptance.md").read_text(encoding="utf-8")

        self.assertIn("MVP accepted", readme)
        self.assertIn("docs/acceptance.md", readme)
        self.assertIn("[x] 短い検証用MP4とOllamaでのMVP受け入れ確認", roadmap)
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

    def test_architecture_defines_event_detector_contract(self):
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

        self.assertIn("event_detector", architecture)
        self.assertIn("events", architecture)
        self.assertIn("timeline_index", architecture)
        self.assertIn("activity", architecture)
        self.assertIn("検索UI", architecture)

    def test_roadmap_prioritizes_real_video_quality_review_before_event_importance(self):
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        quality_review = roadmap.index("実動画でframe_summaryからtimelineまでの品質を確認する")
        event_importance = roadmap.index("イベント重要度判定")
        self.assertLess(quality_review, event_importance)


if __name__ == "__main__":
    unittest.main()
