"""Command line entry point: load, validate, analyse and write the reports."""

import argparse
import sys
from pathlib import Path

from fitness_analyzer.analysis import SessionAnalyzer
from fitness_analyzer.data_loader import load_participants, load_session_file
from fitness_analyzer.exceptions import DataFileError
from fitness_analyzer.models import SessionCollection
from fitness_analyzer.reporting import format_completion_summary, write_reports
from fitness_analyzer.validation import SESSION_ID_PATTERN

# Defaults are based on where the project is, not on hard-coded absolute paths.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_PROFILES = DATA_DIR / "participants.csv"
DEFAULT_SESSIONS = [DATA_DIR / "fitness_sessions.csv", DATA_DIR / "fitness_sessions_invalid.csv"]
DEFAULT_OUTPUT = PROJECT_ROOT / "output"


def display_path(path):
    """Show paths relative to the current folder when possible, so output stays short."""
    path = Path(path)
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Analyse wearable fitness sessions from CSV files and write reports."
    )
    parser.add_argument(
        "--profiles", type=Path, default=DEFAULT_PROFILES,
        help="participants CSV file (default: data/participants.csv)",
    )
    parser.add_argument(
        "--sessions", type=Path, nargs="+", default=DEFAULT_SESSIONS,
        help="one or more session CSV files "
             "(default: data/fitness_sessions.csv data/fitness_sessions_invalid.csv)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="folder for the report files, created if missing (default: output)",
    )
    return parser


def run(argv=None) -> int:
    """Run the whole program. Returns 0 on success and 1 if nothing useful could be produced."""
    args = build_parser().parse_args(argv)

    try:
        participants, profile_rejected = load_participants(args.profiles)
    except DataFileError as error:
        print(f"Error: cannot load participants from {display_path(error.path)}: {error.reason}",
              file=sys.stderr)
        return 1

    collection = SessionCollection()
    rejected = list(profile_rejected)
    rows_accepted = 0
    rows_rejected = 0
    files_read = []
    files_skipped = []

    for path in args.sessions:
        try:
            accepted, file_rejected = load_session_file(path, participants, collection)
        except DataFileError as error:
            # One unreadable session file should not stop the others from being analysed.
            print(f"Warning: skipping {display_path(error.path)}: {error.reason}", file=sys.stderr)
            files_skipped.append(f"{Path(error.path).name} ({error.reason})")
            continue
        rows_accepted += accepted
        rows_rejected += len(file_rejected)
        rejected.extend(file_rejected)
        files_read.append(path.name)

    if not files_read:
        print("Error: none of the session files could be read, so there is nothing to analyse.",
              file=sys.stderr)
        return 1

    sessions = collection.sessions
    results = [SessionAnalyzer.analyze(session) for session in sessions]

    rejected_counts = {}
    for record in rejected:
        if record.session_id:
            rejected_counts[record.session_id] = rejected_counts.get(record.session_id, 0) + 1

    analysed_ids = {session.session_id for session in sessions}
    unanalysed = sorted({
        record.session_id for record in rejected
        if record.session_id and record.session_id not in analysed_ids
        and SESSION_ID_PATTERN.fullmatch(record.session_id)
    })

    run_info = {
        "profiles_file": args.profiles.name,
        "session_files_read": files_read,
        "session_files_skipped": files_skipped,
        "participants_loaded": len(participants),
        "profile_rows_rejected": len(profile_rejected),
        "session_rows_accepted": rows_accepted,
        "session_rows_rejected": rows_rejected,
        "sessions_analysed": len(results),
        "unanalysed_sessions": unanalysed,
        "rejected_rows_by_session": rejected_counts,
    }

    try:
        written = write_reports(args.output, results, rejected, sessions, run_info)
    except DataFileError as error:
        print(f"Error: could not write reports to {display_path(error.path)}: {error.reason}",
              file=sys.stderr)
        return 1

    print(format_completion_summary(run_info, written, display_path))
    return 0
