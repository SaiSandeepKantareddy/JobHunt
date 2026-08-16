import unittest

from job_digest import acceptable_location, build_url, score_job, update_seen_ledger


CONFIG = {
    "api_filters": {"regions": "north_america", "posted_within_days": 14},
    "max_results_per_search": 100,
    "onsite_locations": ["Austin", "Texas"],
    "onsite_state_codes": ["TX", "CA", "WA"],
    "remote_regions": ["north_america", "global"],
    "title_terms": ["machine learning", "ai engineer", "applied scientist"],
    "strong_skills": ["generative ai", "rag", "agentic ai"],
    "supporting_skills": ["python", "pytorch", "databricks"],
    "excluded_title_terms": ["intern", "junior", "analyst"],
    "minimum_score": 36,
}


class JobDigestTests(unittest.TestCase):
    def test_url_uses_search_endpoint_and_filters(self):
        url = build_url("LLM engineer", CONFIG)
        self.assertIn("/agent/jobs/search?", url)
        self.assertIn("q=LLM+engineer", url)
        self.assertIn("posted_within_days=14", url)

    def test_accepts_austin_onsite(self):
        ok, _ = acceptable_location({"location": "Austin, Texas", "work_mode": "onsite"}, CONFIG)
        self.assertTrue(ok)

    def test_accepts_california_state_code_when_us_resolved(self):
        ok, _ = acceptable_location({"location": "Palo Alto, CA, United States", "work_mode": "onsite", "countries": ["us"]}, CONFIG)
        self.assertTrue(ok)

    def test_accepts_washington_state_city(self):
        config = {**CONFIG, "onsite_locations": [*CONFIG["onsite_locations"], "Seattle"]}
        ok, _ = acceptable_location({"location": "Seattle, Washington, United States", "work_mode": "hybrid", "countries": ["us"]}, config)
        self.assertTrue(ok)

    def test_accepts_north_america_remote(self):
        ok, _ = acceptable_location({"location": "Remote", "work_mode": "remote", "regions": ["north_america"]}, CONFIG)
        self.assertTrue(ok)

    def test_rejects_unrelated_onsite_location(self):
        ok, _ = acceptable_location({"location": "London", "work_mode": "onsite", "regions": ["uk"]}, CONFIG)
        self.assertFalse(ok)

    def test_rejects_canada_only_remote(self):
        ok, _ = acceptable_location({"location": "Toronto, Canada", "work_mode": "remote", "regions": ["north_america"], "countries": ["ca"]}, CONFIG)
        self.assertFalse(ok)

    def test_seen_ledger_never_relabels_returning_job_as_new(self):
        first, new = update_seen_ledger({"jobs": {}}, {"a"}, "2026-01-01T00:00:00Z")
        self.assertEqual(new, {"a"})
        second, new = update_seen_ledger(first, set(), "2026-01-02T00:00:00Z")
        third, new = update_seen_ledger(second, {"a"}, "2026-01-03T00:00:00Z")
        self.assertEqual(new, set())
        self.assertEqual(third["jobs"]["a"]["first_seen"], "2026-01-01T00:00:00Z")

    def test_scores_relevant_senior_role(self):
        job = {"public_slug":"one", "title":"Senior Machine Learning Engineer", "company":"Example", "location":"Austin, Texas", "work_mode":"hybrid", "description":"Build generative AI and RAG systems with Python, PyTorch, and Databricks.", "url":"https://example.com", "regions":["north_america"], "skills":["python"]}
        result = score_job(job, CONFIG)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["score"], 50)

    def test_rejects_internship(self):
        job = {"title":"Machine Learning Intern", "location":"Austin, Texas", "description":"Generative AI RAG Python"}
        self.assertIsNone(score_job(job, CONFIG))


if __name__ == "__main__":
    unittest.main()
