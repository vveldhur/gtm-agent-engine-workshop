import json
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from gtm_agent import data_service
from gtm_agent.gtm_agent import build_prospect_profile, score_prospect, update_prospect_info


class RecordingScorer:
    def __init__(self, required_technology):
        self.required_technology = required_technology
        self.calls = []

    def invoke(self, messages):
        profile = json.loads(messages[1]["content"].split("\n\nProspect profile:\n", 1)[1])
        self.calls.append(profile)
        has_technology = self.required_technology in profile["tech_stack"]
        score = 100.0 if has_technology else 75.0
        return SimpleNamespace(
            model_dump=lambda: {
                "score": score,
                "max_score": 100,
                "justification": "The prospect has the required technology."
                if has_technology else "The prospect is missing the required technology.",
                "rubric_breakdown": {
                    "revenue_fit": 100.0,
                    "tech_stack_match": score,
                    "segment_fit": 100.0,
                    "component_max": 100,
                },
            }
        )


class ScoringConsistencyTests(unittest.TestCase):
    prospect_id = "LEAD-39002"
    technology = "Terraform"

    def setUp(self):
        self.original_record = data_service.PROSPECTS[self.prospect_id].copy()
        data_service._PROFILES.clear()
        data_service._LAST_SUCCESSFUL_UPDATES.clear()

    def tearDown(self):
        data_service.PROSPECTS[self.prospect_id] = self.original_record
        data_service._PROFILES.clear()
        data_service._LAST_SUCCESSFUL_UPDATES.clear()

    def test_update_profile_and_score_use_new_technology(self):
        offering = {
            "description": "Cloud automation",
            "min_annual_revenue": 1,
            "required_tech_stack": [self.technology],
        }
        scorer = RecordingScorer(self.technology)

        old_scorer = __import__("gtm_agent.gtm_agent", fromlist=["_scoring_llm"])._scoring_llm
        module = __import__("gtm_agent.gtm_agent", fromlist=["_scoring_llm"])
        module._scoring_llm = scorer
        try:
            baseline = score_prospect.invoke({
                "prospect_profile": {
                    "prospect_id": self.prospect_id,
                    "tech_stack": list(self.original_record["tech_stack"]),
                },
                "offering": offering,
            })
            update = update_prospect_info.invoke({
                "prospect_id": self.prospect_id,
                "technology": self.technology,
            })
            profile_result = build_prospect_profile.invoke({"prospect_id": self.prospect_id})
            scored = score_prospect.invoke({
                "prospect_profile": profile_result["prospect_profile"],
                "offering": offering,
            })
        finally:
            module._scoring_llm = old_scorer

        self.assertTrue(update["updated"])
        self.assertTrue(update["visible"])
        self.assertIn(self.technology, profile_result["prospect_profile"]["tech_stack"])
        self.assertIn(self.technology, scorer.calls[-1]["tech_stack"])
        self.assertNotIn("missing", scored["justification"])
        self.assertNotEqual(scored["score"], baseline["score"])

    def test_stale_supplied_profile_returns_conflict(self):
        update_prospect_info.invoke({
            "prospect_id": self.prospect_id,
            "technology": self.technology,
        })
        result = score_prospect.invoke({
            "prospect_profile": {
                "prospect_id": self.prospect_id,
                "tech_stack": list(self.original_record["tech_stack"]),
            },
            "offering": {
                "description": "Cloud automation",
                "min_annual_revenue": 1,
                "required_tech_stack": [self.technology],
            },
        })

        self.assertTrue(result["stale_data"])
        self.assertEqual(result["conflict"]["technology"], self.technology)
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
