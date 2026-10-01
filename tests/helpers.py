"""Shared helpers for the tests."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES = DATA_DIR / "participants.csv"
VALID_SESSIONS = DATA_DIR / "fitness_sessions.csv"
INVALID_SESSIONS = DATA_DIR / "fitness_sessions_invalid.csv"

SESSION_HEADER = (
    "session_id,participant_id,timestamp,heart_rate,skin_response,"
    "temperature,activity_level,signal_quality"
)
PROFILE_HEADER = (
    "participant_id,name,baseline_heart_rate,baseline_skin_response,baseline_temperature"
)


def write_csv(folder, name, lines):
    """Write a small CSV test file and return its path."""
    path = Path(folder) / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def session_values(**changes):
    """A valid session row as a dict of strings, with optional changes."""
    values = {
        "session_id": "FIT-2026-001",
        "participant_id": "P001",
        "timestamp": "0",
        "heart_rate": "70",
        "skin_response": "1.2",
        "temperature": "32.4",
        "activity_level": "0.1",
        "signal_quality": "0.9",
    }
    values.update(changes)
    return values
