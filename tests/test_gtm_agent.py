import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from gtm_agent.gtm_agent import send_prospect_email


class SendProspectEmailTests(unittest.TestCase):
    runtime = SimpleNamespace(config={"metadata": {"user_id": "rep_oadeyemi"}})
    prospect = {
        "prospect_id": "LEAD-50002",
        "name": "Liam O'Brien",
        "email": "liam.obrien@meridiansystems.com",
    }

    def test_disqualified_prospect_is_blocked(self):
        with patch("gtm_agent.gtm_agent.data_service.get_prospect_record") as lookup:
            lookup.return_value = {"disqualified": True}

            result = send_prospect_email.func(
                self.prospect, "Subject", "Body", self.runtime
            )

        self.assertEqual(result, {"status": "blocked", "reason": "prospect_disqualified"})

    def test_disqualified_prospect_can_be_sent_with_override(self):
        with patch("gtm_agent.gtm_agent.data_service.get_prospect_record") as lookup:
            lookup.return_value = {"disqualified": True}

            result = send_prospect_email.func(
                self.prospect,
                "Subject",
                "Body",
                self.runtime,
                disqualified_override=True,
            )

        self.assertEqual(result["status"], "sent")

    def test_qualified_prospect_is_sent(self):
        prospect = {**self.prospect, "prospect_id": "LEAD-50001"}
        with patch("gtm_agent.gtm_agent.data_service.get_prospect_record") as lookup:
            lookup.return_value = {"disqualified": False}

            result = send_prospect_email.func(prospect, "Subject", "Body", self.runtime)

        self.assertEqual(result["status"], "sent")


if __name__ == "__main__":
    unittest.main()
