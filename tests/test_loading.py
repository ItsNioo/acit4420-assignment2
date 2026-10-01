"""Loading the official files, the intentionally invalid file, and broken or missing files."""

import tempfile
import unittest
from pathlib import Path

from fitness_analyzer.data_loader import load_participants, load_session_file
from fitness_analyzer.exceptions import DataFileError
from fitness_analyzer.models import SessionCollection
from tests.helpers import (
    INVALID_SESSIONS, PROFILE_HEADER, PROFILES, SESSION_HEADER, VALID_SESSIONS, write_csv,
)


class TestOfficialFiles(unittest.TestCase):
    def setUp(self):
        self.participants, self.profile_rejected = load_participants(PROFILES)

    def test_participants(self):
        self.assertEqual(sorted(self.participants), ["P001", "P002", "P003"])
        self.assertEqual(self.participants["P002"].name, "Jonas Berg")
        self.assertEqual(self.profile_rejected, [])

    def test_valid_session_file(self):
        collection = SessionCollection()
        accepted, rejected = load_session_file(VALID_SESSIONS, self.participants, collection)
        self.assertEqual(accepted, 29)
        self.assertEqual(rejected, [])
        self.assertEqual(len(collection), 5)

    def test_invalid_session_file(self):
        collection = SessionCollection()
        accepted, rejected = load_session_file(INVALID_SESSIONS, self.participants, collection)
        self.assertEqual(accepted, 1)
        self.assertEqual(len(rejected), 10)

        problems = {record.line_number: {field for field, _ in record.problems} for record in rejected}
        expected = {
            3: {"heart_rate"},
            4: {"participant_id"},
            5: {"activity_level"},
            6: {"signal_quality"},
            7: {"session_id"},
            8: {"participant_id"},
            9: {"timestamp"},
            10: {"heart_rate"},
            11: {"skin_response", "temperature", "activity_level"},
            12: {"row"},
        }
        self.assertEqual(problems, expected)
        for record in rejected:
            self.assertEqual(record.source_file, "fitness_sessions_invalid.csv")


class TestBrokenFiles(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.participants, _ = load_participants(PROFILES)

    def test_missing_profiles_file(self):
        with self.assertRaises(DataFileError) as context:
            load_participants(Path(self.folder.name) / "does_not_exist.csv")
        self.assertIn("not found", str(context.exception))

    def test_missing_session_file(self):
        with self.assertRaises(DataFileError):
            load_session_file(Path(self.folder.name) / "missing.csv", self.participants, SessionCollection())

    def test_directory_instead_of_file(self):
        folder = Path(self.folder.name) / "folder.csv"
        folder.mkdir()
        with self.assertRaises(DataFileError):
            load_participants(folder)

    def test_empty_file(self):
        path = write_csv(self.folder.name, "empty.csv", [])
        path.write_text("", encoding="utf-8")
        with self.assertRaises(DataFileError) as context:
            load_session_file(path, self.participants, SessionCollection())
        self.assertIn("empty", str(context.exception))

    def test_missing_column(self):
        path = write_csv(self.folder.name, "no_quality.csv", [
            "session_id,participant_id,timestamp,heart_rate,skin_response,temperature,activity_level",
            "FIT-2026-001,P001,0,70,1.2,32.4,0.1",
        ])
        with self.assertRaises(DataFileError) as context:
            load_session_file(path, self.participants, SessionCollection())
        self.assertIn("signal_quality", str(context.exception))

    def test_not_utf8(self):
        path = Path(self.folder.name) / "latin.csv"
        path.write_bytes((PROFILE_HEADER + "\nP001,J\xf8rgen,68,1.2,32.4\n").encode("latin-1"))
        with self.assertRaises(DataFileError):
            load_participants(path)

    def test_no_valid_participants(self):
        path = write_csv(self.folder.name, "bad_profiles.csv", [PROFILE_HEADER, "X1,,abc,1,1"])
        with self.assertRaises(DataFileError):
            load_participants(path)

    def test_duplicate_participant_is_rejected(self):
        path = write_csv(self.folder.name, "dupes.csv", [
            PROFILE_HEADER, "P001,Amina,68,1.2,32.4", "P001,Someone Else,70,1.3,32.5",
        ])
        participants, rejected = load_participants(path)
        self.assertEqual(participants["P001"].name, "Amina")
        self.assertEqual([record.line_number for record in rejected], [3])

    def test_blank_lines_and_spaces_are_handled(self):
        path = write_csv(self.folder.name, "spaces.csv", [
            SESSION_HEADER,
            "FIT-2026-001, P001 ,0,70,1.2,32.4,0.1,0.9",
            "",
            "FIT-2026-001,P001,1,71,1.2,32.4,0.1,0.9",
        ])
        collection = SessionCollection()
        accepted, rejected = load_session_file(path, self.participants, collection)
        self.assertEqual((accepted, len(rejected)), (2, 0))

    def test_line_numbers_match_the_file(self):
        path = write_csv(self.folder.name, "lines.csv", [
            SESSION_HEADER,
            "FIT-2026-001,P001,0,70,1.2,32.4,0.1,0.9",
            "",
            "FIT-2026-001,P001,1,oops,1.2,32.4,0.1,0.9",
        ])
        _, rejected = load_session_file(path, self.participants, SessionCollection())
        self.assertEqual(rejected[0].line_number, 4)

    def test_duplicate_timestamp_is_rejected(self):
        path = write_csv(self.folder.name, "dup_time.csv", [
            SESSION_HEADER,
            "FIT-2026-001,P001,0,70,1.2,32.4,0.1,0.9",
            "FIT-2026-001,P001,0,72,1.2,32.4,0.1,0.9",
        ])
        accepted, rejected = load_session_file(path, self.participants, SessionCollection())
        self.assertEqual((accepted, len(rejected)), (1, 1))
        self.assertEqual(rejected[0].problems[0][0], "timestamp")


if __name__ == "__main__":
    unittest.main()
