"""Encapsulation, composition and inheritance in the domain classes."""

import unittest

from fitness_analyzer.exceptions import InvalidRecordError
from fitness_analyzer.models import Observation, Participant, Person, Session, SessionCollection


def make_participant(person_id="P001"):
    return Participant("Test Person", person_id, 68, 1.2, 32.4)


def make_observation(timestamp=0, signal_quality=0.9):
    return Observation(timestamp, 70, 1.2, 32.4, 0.1, signal_quality, "test.csv", timestamp + 2)


class TestModels(unittest.TestCase):
    def test_participant_inherits_and_overrides_str(self):
        participant = make_participant()
        self.assertIsInstance(participant, Person)
        self.assertIn("baseline heart rate", str(participant))
        self.assertNotEqual(str(participant), Person.__str__(participant))

    def test_signal_quality_boundary_for_usable_windows(self):
        self.assertTrue(make_observation(signal_quality=0.5).is_usable)
        self.assertFalse(make_observation(signal_quality=0.49).is_usable)

    def test_private_attribute_is_not_directly_reachable(self):
        observation = make_observation()
        with self.assertRaises(AttributeError):
            getattr(observation, "__usable")

    def test_observations_are_ordered_by_timestamp(self):
        session = Session("FIT-2026-001", make_participant())
        for timestamp in [3, 0, 2, 1]:
            session.add_observation(make_observation(timestamp))
        self.assertEqual([obs.timestamp for obs in session.observations], [0, 1, 2, 3])

    def test_duplicate_timestamp_is_rejected(self):
        session = Session("FIT-2026-001", make_participant())
        session.add_observation(make_observation(0))
        with self.assertRaises(InvalidRecordError):
            session.add_observation(make_observation(0))

    def test_session_cannot_switch_participant(self):
        collection = SessionCollection()
        collection.add("FIT-2026-001", make_participant("P001"), make_observation(0))
        with self.assertRaises(InvalidRecordError):
            collection.add("FIT-2026-001", make_participant("P002"), make_observation(1))
        self.assertEqual(len(collection), 1)


if __name__ == "__main__":
    unittest.main()
