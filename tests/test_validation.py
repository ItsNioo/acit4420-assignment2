"""Identifier patterns, type conversion and range checks, including boundaries."""

import unittest
from pathlib import Path

from fitness_analyzer.exceptions import DataFileError, InvalidIdentifierError, InvalidRecordError
from fitness_analyzer.validation import (
    validate_csv_filename,
    validate_participant_id,
    validate_profile_row,
    validate_session_id,
    validate_session_row,
)
from tests.helpers import session_values

KNOWN = {"P001", "P002"}


class TestIdentifiers(unittest.TestCase):
    def test_valid_identifiers(self):
        self.assertEqual(validate_participant_id("P001"), "P001")
        self.assertEqual(validate_session_id("FIT-2026-001"), "FIT-2026-001")

    def test_invalid_participant_ids(self):
        for value in ["001", "P01", "P0001", "p001", "P00A", "XP001", "P001X"]:
            with self.subTest(value=value):
                with self.assertRaises(InvalidIdentifierError):
                    validate_participant_id(value)

    def test_invalid_session_ids(self):
        for value in ["FIT-26-102", "FIT-2026-1", "FIT-2026-0001", "fit-2026-001", "FIT_2026_001", "FIT-2026-001 extra"]:
            with self.subTest(value=value):
                with self.assertRaises(InvalidIdentifierError):
                    validate_session_id(value)

    def test_csv_filename(self):
        validate_csv_filename(Path("fitness_sessions.csv"))
        for name in ["notes.txt", "data.csv.bak", "my data.csv"]:
            with self.subTest(name=name):
                with self.assertRaises(DataFileError):
                    validate_csv_filename(Path(name))


class TestSessionRow(unittest.TestCase):
    def test_valid_row_is_converted_to_numbers(self):
        record = validate_session_row(session_values(), KNOWN)
        self.assertIsInstance(record["timestamp"], int)
        self.assertIsInstance(record["heart_rate"], float)
        self.assertEqual(record["heart_rate"], 70.0)

    def assert_rejected(self, values, field):
        with self.assertRaises(InvalidRecordError) as context:
            validate_session_row(values, KNOWN)
        fields = [problem[0] for problem in context.exception.problems]
        self.assertIn(field, fields)
        return context.exception

    def test_text_instead_of_number(self):
        self.assert_rejected(session_values(heart_rate="fast"), "heart_rate")
        self.assert_rejected(session_values(timestamp="two"), "timestamp")
        self.assert_rejected(session_values(timestamp="1.5"), "timestamp")

    def test_missing_value(self):
        error = self.assert_rejected(session_values(activity_level=""), "activity_level")
        self.assertIn("missing", str(error))

    def test_unknown_participant(self):
        error = self.assert_rejected(session_values(participant_id="P999"), "participant_id")
        self.assertIn("unknown participant", str(error))

    def test_all_problems_in_a_row_are_reported(self):
        error = self.assert_rejected(
            session_values(skin_response="-0.5", temperature="55", activity_level="1.3"),
            "temperature",
        )
        fields = {problem[0] for problem in error.problems}
        self.assertEqual(fields, {"skin_response", "temperature", "activity_level"})

    def test_nan_is_rejected(self):
        self.assert_rejected(session_values(heart_rate="nan"), "heart_rate")


class TestBoundaries(unittest.TestCase):
    def test_values_exactly_on_the_limits_are_accepted(self):
        cases = [
            {"heart_rate": "30"}, {"heart_rate": "220"},
            {"activity_level": "0"}, {"activity_level": "1"},
            {"signal_quality": "0"}, {"signal_quality": "1"},
            {"temperature": "25"}, {"temperature": "42"},
            {"skin_response": "0"}, {"timestamp": "0"},
        ]
        for change in cases:
            with self.subTest(change=change):
                validate_session_row(session_values(**change), KNOWN)

    def test_values_just_outside_the_limits_are_rejected(self):
        cases = [
            ("heart_rate", "29.9"), ("heart_rate", "220.1"),
            ("activity_level", "-0.01"), ("activity_level", "1.01"),
            ("signal_quality", "1.01"), ("temperature", "24.9"),
            ("temperature", "42.1"), ("skin_response", "-0.01"),
            ("timestamp", "-1"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaises(InvalidRecordError):
                    validate_session_row(session_values(**{field: value}), KNOWN)


class TestProfileRow(unittest.TestCase):
    def test_valid_profile(self):
        profile = validate_profile_row({
            "participant_id": "P001", "name": "Amina Noor", "baseline_heart_rate": "68",
            "baseline_skin_response": "1.20", "baseline_temperature": "32.4",
        })
        self.assertEqual(profile["baseline_heart_rate"], 68.0)

    def test_invalid_profile(self):
        with self.assertRaises(InvalidRecordError) as context:
            validate_profile_row({
                "participant_id": "X1", "name": "", "baseline_heart_rate": "abc",
                "baseline_skin_response": "1.2", "baseline_temperature": "99",
            })
        fields = {problem[0] for problem in context.exception.problems}
        self.assertEqual(fields, {"participant_id", "name", "baseline_heart_rate", "baseline_temperature"})


if __name__ == "__main__":
    unittest.main()
