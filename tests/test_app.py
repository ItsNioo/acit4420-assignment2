"""The whole program: output files, reruns, missing files and the command line."""

import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from fitness_analyzer.app import run
from tests.helpers import INVALID_SESSIONS, PROFILES, VALID_SESSIONS


def run_quietly(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = run([str(arg) for arg in args])
    return code, out.getvalue(), err.getvalue()


class TestApp(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.output = Path(self.folder.name) / "reports" / "nested"

    def full_run(self, sessions=(VALID_SESSIONS, INVALID_SESSIONS)):
        return run_quietly(["--profiles", PROFILES, "--sessions", *sessions, "--output", self.output])

    def test_creates_missing_output_folder_and_all_files(self):
        code, out, _ = self.full_run()
        self.assertEqual(code, 0)
        for name in ["analysis_summary.csv", "analysis_report.txt", "rejected_records.txt"]:
            self.assertTrue((self.output / name).is_file(), name)
        self.assertIn("Session rows accepted: 30", out)
        self.assertIn("Session rows rejected: 10", out)

    def test_summary_has_one_row_per_session(self):
        self.full_run()
        with open(self.output / "analysis_summary.csv", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual([row["session_id"] for row in rows], [
            "FIT-2026-001", "FIT-2026-002", "FIT-2026-003", "FIT-2026-004", "FIT-2026-005", "FIT-2026-101",
        ])

    def test_running_twice_gives_identical_output(self):
        self.full_run()
        first = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.full_run()
        second = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(first, second)

    def test_rejected_records_lists_every_invalid_line(self):
        self.full_run()
        text = (self.output / "rejected_records.txt").read_text(encoding="utf-8")
        for line in range(3, 13):
            self.assertIn(f"fitness_sessions_invalid.csv, line {line}\n", text)

    def test_missing_profiles_file_stops_with_error(self):
        code, _, err = run_quietly(["--profiles", Path(self.folder.name) / "nope.csv", "--output", self.output])
        self.assertEqual(code, 1)
        self.assertIn("file not found", err)
        self.assertFalse(self.output.exists())

    def test_one_missing_session_file_is_skipped(self):
        missing = Path(self.folder.name) / "missing_sessions.csv"
        code, out, err = self.full_run(sessions=(VALID_SESSIONS, missing))
        self.assertEqual(code, 0)
        self.assertIn("skipping", err)
        report = (self.output / "analysis_report.txt").read_text(encoding="utf-8")
        self.assertIn("missing_sessions.csv (file not found)", report)

    def test_all_session_files_missing(self):
        missing = Path(self.folder.name) / "missing_sessions.csv"
        code, _, err = self.full_run(sessions=(missing,))
        self.assertEqual(code, 1)
        self.assertIn("nothing to analyse", err)

    def test_output_path_is_a_file(self):
        blocker = Path(self.folder.name) / "blocker"
        blocker.write_text("not a folder", encoding="utf-8")
        code, _, err = run_quietly(["--output", blocker])
        self.assertEqual(code, 1)
        self.assertIn("could not write reports", err)

    def test_default_arguments_use_the_official_files(self):
        code, out, _ = run_quietly(["--output", self.output])
        self.assertEqual(code, 0)
        self.assertIn("Sessions analysed:     6", out)


if __name__ == "__main__":
    unittest.main()
