"""Classification of the official sessions and the edges of each rule."""

import unittest

from fitness_analyzer import analysis
from fitness_analyzer.analysis import SessionAnalyzer, summarize_values
from fitness_analyzer.data_loader import load_participants, load_session_file
from fitness_analyzer.models import Observation, Participant, Session, SessionCollection
from tests.helpers import INVALID_SESSIONS, PROFILES, VALID_SESSIONS


def build_session(heart_rates, activity=0.1, signal_quality=0.9, baseline=68):
    participant = Participant("Test Person", "P001", baseline, 1.2, 32.4)
    session = Session("FIT-2026-900", participant)
    levels = activity if isinstance(activity, list) else [activity] * len(heart_rates)
    for timestamp, (heart_rate, level) in enumerate(zip(heart_rates, levels)):
        session.add_observation(Observation(timestamp, heart_rate, 1.2, 32.4, level, signal_quality))
    return session


class TestOfficialSessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        participants, _ = load_participants(PROFILES)
        collection = SessionCollection()
        load_session_file(VALID_SESSIONS, participants, collection)
        load_session_file(INVALID_SESSIONS, participants, collection)
        cls.results = {s.session_id: SessionAnalyzer.analyze(s) for s in collection.sessions}

    def test_classifications(self):
        expected = {
            "FIT-2026-001": "resting",
            "FIT-2026-002": "moderate activity",
            "FIT-2026-003": "high activity",
            "FIT-2026-004": "recovering",
            "FIT-2026-005": "insufficient data",
            "FIT-2026-101": "insufficient data",
        }
        actual = {key: result["classification"] for key, result in self.results.items()}
        self.assertEqual(actual, expected)

    def test_every_result_has_reasons(self):
        for result in self.results.values():
            self.assertTrue(result["reasons"])

    def test_insufficient_data_is_separate_from_real_results(self):
        self.assertFalse(self.results["FIT-2026-005"]["has_enough_data"])
        self.assertTrue(self.results["FIT-2026-001"]["has_enough_data"])
        self.assertEqual(self.results["FIT-2026-005"]["low_quality_windows"], 5)
        self.assertIsNone(self.results["FIT-2026-005"]["heart_rate"]["average"])

    def test_result_compares_with_baseline(self):
        result = self.results["FIT-2026-002"]
        self.assertEqual(result["heart_rate"]["average"], 102)
        self.assertEqual(result["heart_rate_vs_baseline"], 28)


class TestRuleBoundaries(unittest.TestCase):
    def classify(self, *args, **kwargs):
        return SessionAnalyzer.analyze(build_session(*args, **kwargs))["classification"]

    def test_minimum_number_of_usable_windows(self):
        self.assertEqual(self.classify([68] * analysis.MIN_USABLE_WINDOWS), "resting")
        self.assertEqual(self.classify([68] * (analysis.MIN_USABLE_WINDOWS - 1)), "insufficient data")

    def test_resting_and_moderate_heart_rate_limits(self):
        self.assertEqual(self.classify([68 + 15] * 3), "resting")
        self.assertEqual(self.classify([68 + 15.5] * 3), "moderate activity")
        self.assertEqual(self.classify([68 + 45] * 3, activity=0.5), "moderate activity")
        self.assertEqual(self.classify([68 + 45.5] * 3, activity=0.5), "high activity")

    def test_activity_ceiling_for_resting(self):
        self.assertEqual(self.classify([70] * 3, activity=0.30), "resting")
        self.assertEqual(self.classify([70] * 3, activity=0.31), "moderate activity")

    def test_low_quality_windows_are_not_counted(self):
        self.assertEqual(self.classify([70] * 6, signal_quality=0.49), "insufficient data")

    def test_recovery_after_activity(self):
        result = self.classify([150, 150, 120, 120], activity=[0.9, 0.9, 0.5, 0.5])
        self.assertEqual(result, "recovering")

    def test_small_dip_while_resting_is_not_recovery(self):
        # Heart rate drops more than 10%, but the session never left the resting zone.
        result = self.classify([80, 80, 70, 70], activity=[0.2, 0.2, 0.1, 0.1])
        self.assertEqual(result, "resting")

    def test_summarize_empty_list(self):
        self.assertEqual(summarize_values([]), {"average": None, "minimum": None, "maximum": None})


if __name__ == "__main__":
    unittest.main()
