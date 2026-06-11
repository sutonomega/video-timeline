from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocsMvpContractTest(unittest.TestCase):
    def test_mvp_doc_defines_cli_and_json_contract(self):
        text = (ROOT / "docs" / "mvp.md").read_text(encoding="utf-8")

        required_terms = [
            "video-timeline input.mp4 --output timeline.json",
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
        for relative_path in ["README.md", "docs/roadmap.md", "docs/architecture.md"]:
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("mvp.md", text)


if __name__ == "__main__":
    unittest.main()
