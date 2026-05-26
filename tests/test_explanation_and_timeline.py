import unittest

from src.explanation_planner import validate_explanation_plan
from src.gemini_speech import build_segment_timeline


class TestExplanationPlanValidation(unittest.TestCase):
    def test_validation_catches_duplicates_empty_text_and_unknown_highlight(self):
        plan = {
            "lesson_title": "Demo",
            "segments": [
                {"seg_id": "seg_01", "text": "Hello", "highlights": ["node_a"]},
                {"seg_id": "seg_01", "text": "  ", "highlights": ["missing_id"]},
            ],
        }
        errors = validate_explanation_plan(plan, ["node_a"])
        self.assertTrue(any("Segment IDs must be unique." in e for e in errors))
        self.assertTrue(any("segments[1].text must be non-empty." in e for e in errors))
        self.assertTrue(
            any("references unknown id 'missing_id'" in e for e in errors),
            errors,
        )


class TestTimelineGeneration(unittest.TestCase):
    def test_build_segment_timeline_uses_cumulative_ranges(self):
        explanation_plan = {
            "lesson_title": "Demo",
            "learning_goals": [],
            "segments": [
                {"seg_id": "seg_01", "text": "First", "highlights": ["node_a"]},
                {"seg_id": "seg_02", "text": "Second", "highlights": ["node_b"]},
            ],
        }
        timeline = build_segment_timeline(explanation_plan, [1.25, 2.5])
        self.assertEqual(timeline["segments"][0]["t0"], 0.0)
        self.assertEqual(timeline["segments"][0]["t1"], 1.25)
        self.assertEqual(timeline["segments"][1]["t0"], 1.25)
        self.assertEqual(timeline["segments"][1]["t1"], 3.75)
        self.assertEqual(timeline["segments"][1]["highlights"], ["node_b"])


if __name__ == "__main__":
    unittest.main()
