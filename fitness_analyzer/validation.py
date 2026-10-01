"""Validation rules for identifiers, file names and CSV rows.

Regular expressions are only used for text formats (identifiers and
file names). Numeric limits are checked with normal comparisons.
"""

import re

from fitness_analyzer.exceptions import DataFileError, InvalidIdentifierError, InvalidRecordError

PARTICIPANT_ID_PATTERN = re.compile(r"P\d{3}")
SESSION_ID_PATTERN = re.compile(r"FIT-\d{4}-\d{3}")
CSV_FILENAME_PATTERN = re.compile(r"[A-Za-z0-9_\-]+\.csv")

PROFILE_COLUMNS = (
    "participant_id",
    "name",
    "baseline_heart_rate",
    "baseline_skin_response",
    "baseline_temperature",
)

SESSION_COLUMNS = (
    "session_id",
    "participant_id",
    "timestamp",
    "heart_rate",
    "skin_response",
    "temperature",
    "activity_level",
    "signal_quality",
)

# Inclusive (minimum, maximum) limits. Anything outside these is treated as
# an impossible reading and the whole row is rejected.
MEASUREMENT_LIMITS = {
    "heart_rate": (30, 220),
    "skin_response": (0, 60),
    "temperature": (25, 42),
    "activity_level": (0, 1),
    "signal_quality": (0, 1),
}

BASELINE_LIMITS = {
    "baseline_heart_rate": (30, 120),
    "baseline_skin_response": (0, 60),
    "baseline_temperature": (25, 42),
}


def validate_identifier(field, value, pattern, expected):
    """Return value if the whole string matches pattern, otherwise raise."""
    if pattern.fullmatch(value) is None:
        raise InvalidIdentifierError(field, value, expected)
    return value


def validate_participant_id(value):
    return validate_identifier(
        "participant_id", value, PARTICIPANT_ID_PATTERN, "P followed by three digits, e.g. P001"
    )


def validate_session_id(value):
    return validate_identifier(
        "session_id", value, SESSION_ID_PATTERN, "FIT-YYYY-NNN, e.g. FIT-2026-001"
    )


def validate_csv_filename(path):
    """Make sure an input file at least looks like a CSV file before opening it."""
    if CSV_FILENAME_PATTERN.fullmatch(path.name) is None:
        raise DataFileError(
            path, "file name must only use letters, digits, _ or - and end in .csv"
        )


def parse_number(field, text, number_type):
    """Convert text to int or float, raising InvalidRecordError if that is impossible."""
    try:
        return number_type(text)
    except ValueError:
        type_name = "whole number" if number_type is int else "number"
        raise InvalidRecordError([(field, f"'{text}' is not a valid {type_name}")]) from None


def check_limits(field, value, minimum, maximum):
    # The "not" form also rejects NaN, since every comparison with NaN is False.
    if not (minimum <= value <= maximum):
        if maximum == float("inf"):
            raise InvalidRecordError([(field, f"{value:g} must be {minimum:g} or greater")])
        raise InvalidRecordError(
            [(field, f"{value:g} is outside the allowed range {minimum:g} to {maximum:g}")]
        )
    return value


def check_identifier_field(values, field, validator, problems, cleaned):
    text = values[field]
    if text == "":
        problems.append((field, "missing value"))
        return
    try:
        cleaned[field] = validator(text)
    except InvalidIdentifierError as error:
        problems.append((field, error.reason))


def check_number_field(values, field, number_type, limits, problems, cleaned):
    text = values[field]
    if text == "":
        problems.append((field, "missing value"))
        return
    try:
        number = parse_number(field, text, number_type)
        cleaned[field] = check_limits(field, number, *limits)
    except InvalidRecordError as error:
        problems.extend(error.problems)


def validate_profile_row(values):
    """Validate one participants.csv row and return it with proper types."""
    problems = []
    cleaned = {}

    check_identifier_field(values, "participant_id", validate_participant_id, problems, cleaned)

    if values["name"] == "":
        problems.append(("name", "missing value"))
    else:
        cleaned["name"] = values["name"]

    for field, limits in BASELINE_LIMITS.items():
        check_number_field(values, field, float, limits, problems, cleaned)

    if problems:
        raise InvalidRecordError(problems)
    return cleaned


def validate_session_row(values, known_participant_ids):
    """Validate one session row and return it with proper types.

    Every field is checked so that a rejected row lists all of its
    problems, not just the first one found.
    """
    problems = []
    cleaned = {}

    check_identifier_field(values, "session_id", validate_session_id, problems, cleaned)
    check_identifier_field(values, "participant_id", validate_participant_id, problems, cleaned)

    participant_id = cleaned.get("participant_id")
    if participant_id is not None and participant_id not in known_participant_ids:
        problems.append(("participant_id", f"unknown participant '{participant_id}', not in the profiles file"))

    # The timestamp is an observation index, so it only needs a lower limit.
    check_number_field(values, "timestamp", int, (0, float("inf")), problems, cleaned)

    for field, limits in MEASUREMENT_LIMITS.items():
        check_number_field(values, field, float, limits, problems, cleaned)

    if problems:
        raise InvalidRecordError(problems)
    return cleaned
