"""Reading the participant and session CSV files.

File-level problems (missing file, no permission, broken CSV, missing
columns) raise DataFileError. Row-level problems are caught per row and
stored as RejectedRecord objects so loading continues with the next row.
"""

import csv

from fitness_analyzer.exceptions import DataFileError, InvalidRecordError
from fitness_analyzer.models import Participant, Observation, RejectedRecord
from fitness_analyzer.validation import (
    PROFILE_COLUMNS,
    SESSION_COLUMNS,
    validate_csv_filename,
    validate_profile_row,
    validate_session_row,
)


def read_csv_file(path, required_columns):
    """
    Read a CSV file and return (column_positions, header_length, rows).

    rows is a list of (line_number, list_of_values). Line numbers are the
    real line numbers in the file, so the header is line 1. Completely
    blank lines are skipped since they are not records.
    """
    validate_csv_filename(path)
    reader = None
    try:
        with open(path, encoding="utf-8", newline="") as file:
            reader = csv.reader(file)
            header = next(reader, None)
            rows = []
            for row in reader:
                if any(cell.strip() for cell in row):
                    rows.append((reader.line_num, row))
    except FileNotFoundError:
        raise DataFileError(path, "file not found") from None
    except IsADirectoryError:
        raise DataFileError(path, "expected a file but found a directory") from None
    except PermissionError:
        raise DataFileError(path, "permission denied when opening the file") from None
    except UnicodeDecodeError as error:
        raise DataFileError(path, f"file is not valid UTF-8 text ({error.reason})") from None
    except csv.Error as error:
        line = reader.line_num if reader is not None else "?"
        raise DataFileError(path, f"CSV format error near line {line}: {error}") from None

    if header is None:
        raise DataFileError(path, "file is empty, expected a header row")

    # Strip spaces and a possible byte order mark so column names match.
    names = [name.strip().lstrip("\ufeff") for name in header]
    positions = {name: index for index, name in enumerate(names)}
    try:
        column_positions = {column: positions[column] for column in required_columns}
    except KeyError as error:
        raise DataFileError(path, f"missing required column {error}") from None

    return column_positions, len(names), rows


def row_to_values(row, column_positions, header_length):
    """Map a raw row to {column: stripped text}, rejecting rows with the wrong length."""
    if len(row) != header_length:
        raise InvalidRecordError(
            [("row", f"expected {header_length} fields but found {len(row)}")]
        )
    return {column: row[index].strip() for column, index in column_positions.items()}


def load_participants(path):
    """Return ({participant_id: Participant}, [RejectedRecord])."""
    column_positions, header_length, rows = read_csv_file(path, PROFILE_COLUMNS)
    participants = {}
    rejected = []

    for line_number, row in rows:
        try:
            values = row_to_values(row, column_positions, header_length)
            profile = validate_profile_row(values)
            if profile["participant_id"] in participants:
                raise InvalidRecordError([(
                    "participant_id",
                    f"duplicate participant '{profile['participant_id']}', the first definition is kept",
                )])
            participants[profile["participant_id"]] = Participant.from_profile(profile)
        except InvalidRecordError as error:
            rejected.append(RejectedRecord(path.name, line_number, error.problems, row))

    if not participants:
        raise DataFileError(path, "no valid participant rows, so no session can be analysed")
    return participants, rejected


def load_session_file(path, participants, collection):
    """
    Add every valid row in one session file to collection.

    Returns (accepted_count, [RejectedRecord]).
    """
    column_positions, header_length, rows = read_csv_file(path, SESSION_COLUMNS)
    accepted = 0
    rejected = []

    for line_number, row in rows:
        try:
            values = row_to_values(row, column_positions, header_length)
            record = validate_session_row(values, participants)
            observation = Observation.from_record(record, path.name, line_number)
            collection.add(record["session_id"], participants[record["participant_id"]], observation)
        except InvalidRecordError as error:
            session_index = column_positions["session_id"]
            session_text = row[session_index].strip() if session_index < len(row) else ""
            rejected.append(RejectedRecord(path.name, line_number, error.problems, row, session_text))
        else:
            accepted += 1

    return accepted, rejected
