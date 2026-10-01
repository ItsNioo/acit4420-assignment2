# Smart Fitness Session Analyzer, Assignment II (Option A)

Student name: Nihat Ali
Student number: 2785
Course: ACIT4420, Problem-Solving with Scripting

## Description

This is a continuation of my Assignment I project (Option A). In Assignment I the program analysed simulated fitness data that came straight from the instructor's data generator as Python lists and dictionaries. In this version the program works with files instead:

- it reads participant profiles and training sessions from the official CSV files
- it validates every row, including the identifiers, which are checked with regular expressions
- it rejects bad rows with a clear reason and carries on with the rest of the file
- it groups the accepted rows into sessions, classifies each session against the participant's own baseline values and explains the result
- it writes three report files to an `output/` folder and prints a short summary when it is done

## Project structure

```
acit4420-assignment2/
├── main.py                      starts the program
├── fitness_analyzer/            the package
│   ├── __init__.py
│   ├── exceptions.py            custom exception classes
│   ├── validation.py            regex checks and row validation rules
│   ├── models.py                Person, Participant, Observation, Session, SessionCollection, RejectedRecord
│   ├── data_loader.py           reading the CSV files
│   ├── analysis.py              summaries, baseline comparison and classification
│   ├── reporting.py             writing the output files and the console summary
│   └── app.py                   command line arguments and the overall program flow
├── data/                        the official CSV files, unchanged
│   ├── participants.csv
│   ├── fitness_sessions.csv
│   └── fitness_sessions_invalid.csv
├── tests/                       unit tests
├── output/                      created by the program
├── README.md
└── requirements.txt
```

Each module has one job. `app.py` is the only module that knows about the command line, and it is the only place that decides whether an error should stop the program or just be reported.

## Class design

| Class | Module | Responsibility |
|---|---|---|
| `Person` | models | Base class with name and ID. |
| `Participant(Person)` | models | Adds the three baseline values from `participants.csv`. Built with the `from_profile` classmethod. |
| `Observation` | models | One accepted measurement window, plus the file and line it came from. Knows if it is usable based on signal quality. Built with the `from_record` classmethod. |
| `Session` | models | One participant and all accepted windows for that session ID. Rejects duplicate timestamps. |
| `SessionCollection` | models | Groups rows into sessions by session ID and makes sure a session ID always belongs to the same participant. |
| `RejectedRecord` | models | A rejected row: file name, line number, the raw row and every (field, reason) problem found in it. |
| `SessionAnalyzer` | analysis | Turns a `Session` into one structured result dictionary with its `analyze` staticmethod. |
| `InvalidIdentifierError`, `InvalidRecordError`, `DataFileError` | exceptions | Custom exceptions, see Error handling below. |

## OOP concepts used

- **Composition:** a `Session` is built from one `Participant` and many `Observation` objects. A `SessionCollection` is built from `Session` objects.
- **Encapsulation:** `Observation.__usable` is set once in the constructor and only read through the `is_usable` property. `Session.__observations` and `SessionCollection.__sessions` are private, so windows can only be added through `add_observation` and `add`, which is where duplicate and participant checks happen. The `observations` property hands out a sorted list instead of the internal dictionary.
- **Inheritance and overriding:** `Participant` inherits from `Person` and overrides `__str__` to include the baseline values.
- **Classmethods and staticmethods:** `Participant.from_profile` and `Observation.from_record` build objects from validated rows. `SessionAnalyzer.analyze` is a staticmethod because it only transforms a session into a result and needs no stored state.

## Input data

The three CSV files in `data/` are the official files from `Assignment_II_Pack.zip`, copied without any changes. The program reads the profiles file and both session files by default.

- `participants.csv`: `participant_id, name, baseline_heart_rate, baseline_skin_response, baseline_temperature`
- `fitness_sessions.csv` and `fitness_sessions_invalid.csv`: `session_id, participant_id, timestamp, heart_rate, skin_response, temperature, activity_level, signal_quality`

All files are opened with `open(path, encoding="utf-8", newline="")` and read with the `csv` module. Numbers are converted to `int` (timestamp) or `float` (measurements and baselines). Spaces around values are removed before validation.

## Validation rules

**Identifiers** are checked with `re.fullmatch`, so the whole value has to match:

| Value | Pattern |
|---|---|
| Participant ID | `P\d{3}` |
| Session ID | `FIT-\d{4}-\d{3}` |
| Input file name | `[A-Za-z0-9_\-]+\.csv` |

Regular expressions are only used for these text formats. Number ranges are checked with normal comparisons.

**A session row is rejected if:**

- it does not have the same number of fields as the header
- a required value is missing (empty)
- a value cannot be converted to a number
- a value is outside these limits (inclusive):

| Field | Allowed range |
|---|---|
| timestamp | 0 or greater, whole number |
| heart_rate | 30 to 220 bpm |
| skin_response | 0 to 60 |
| temperature | 25 to 42 C |
| activity_level | 0 to 1 |
| signal_quality | 0 to 1 |

- the participant ID does not exist in `participants.csv`
- the same session already has a row with that timestamp
- the session ID already belongs to a different participant

Every problem in a row is reported, not just the first one. For example line 11 of the invalid file is reported with three problems (skin response, temperature and activity level).

A profile row is rejected for a bad ID, a missing name, non-numeric baselines, baselines outside sensible limits, or a duplicate participant ID. If no profile row is valid at all, the program stops, since no session could be linked to anyone.

**Signal quality rule:** a window with `signal_quality` below 0.5 is a valid record, so it is accepted and counted, but the reading cannot be trusted, so it is left out of every calculation. These windows are listed separately at the bottom of `rejected_records.txt` and counted in the summary as `low_quality_windows`. Exactly 0.5 counts as usable.

## Error handling

There are three custom exceptions, and all of them are raised and handled:

- `InvalidIdentifierError(ValueError)`: raised by the regex check when an ID has the wrong format. It is caught while validating the row and turned into a problem for that row.
- `InvalidRecordError(ValueError)`: raised when a row cannot be accepted. It carries a list of all (field, reason) problems. The loader catches it per row, stores a `RejectedRecord` and continues with the next row.
- `DataFileError`: raised when a whole file cannot be used. `app.py` catches it and decides what to do: a broken profiles file stops the program, a broken session file is skipped with a warning and the other files are still analysed, and a problem writing the output stops the program with a clear message.

Built-in errors are only caught where something useful can be done with them:

| Error | Where | What happens |
|---|---|---|
| `FileNotFoundError` | opening an input file | becomes `DataFileError` with "file not found" |
| `PermissionError` | opening input, creating the output folder, writing reports | becomes `DataFileError` with the path |
| `IsADirectoryError`, `FileExistsError` | paths that point to the wrong kind of thing | becomes `DataFileError` |
| `UnicodeDecodeError` | file that is not UTF-8 | becomes `DataFileError` |
| `csv.Error` | malformed CSV | becomes `DataFileError` with the line number |
| `KeyError` | a required column is missing from the header | becomes `DataFileError` naming the column |
| `ValueError` | converting text to a number | becomes `InvalidRecordError` for that field |

There are no empty `except` blocks and no `except Exception`. Programming mistakes are not hidden and will still show a normal traceback.

## Classification rules

The analysis from Assignment I is reused, with some improvements. Only usable windows are analysed. For each session the program calculates average, minimum and maximum heart rate, activity level, skin response and temperature, and the difference between each average and the participant's baseline.

The rules are checked in this order:

1. **insufficient data:** fewer than 3 usable windows. This is kept separate from real results, and the reason says how many windows were usable and how many had low signal quality.
2. **recovering:** the first half of the session had an average heart rate above the resting zone (baseline + 15 bpm), and in the second half heart rate dropped by at least 10% and activity by at least 20%. At least 4 usable windows are needed to look for a trend.
3. **resting:** average heart rate at most baseline + 15 bpm and average activity at most 0.30.
4. **moderate activity:** average heart rate at most baseline + 45 bpm.
5. **high activity:** anything above that.

Heart rate limits are offsets above each participant's own baseline, since the data only gives a resting baseline and no maximum heart rate. The thresholds are my own choices and are not taken from a medical source.

**Improvements compared with Assignment I:**

- every result now comes with reasons that show the actual numbers behind the decision
- skin response and temperature are also compared with the participant's baselines
- recovery now also requires that the session actually started above the resting zone. Before, a resting session with a small dip in heart rate could in theory be reported as recovery.
- windows are sorted by timestamp before analysis, so the order of rows in the file does not matter

## Output files

The program creates the output folder if it does not exist and always overwrites these files completely. Nothing time-dependent is written to them, so running the program again gives exactly the same files.

| File | Content |
|---|---|
| `analysis_summary.csv` | one row per analysed session: participant, window counts, classification, recovery, summaries, baseline differences and reasons |
| `analysis_report.txt` | a readable report: input files, counts, the rules used, sessions that could not be analysed, and a section per session explaining the result |
| `rejected_records.txt` | every rejected row with file name, line number, the raw row and each field and reason, followed by the windows excluded for low signal quality |

Line numbers are real line numbers in the CSV file, so the header is line 1.

## Installation and running

Only the Python standard library is used, so nothing needs to be installed. Python 3.8 or newer is needed.

```bash
git clone https://github.com/ItsNioo/acit4420-assignment2.git
cd acit4420-assignment2
python3 main.py
```

That uses the official files in `data/` and writes to `output/`. The same thing with every argument written out:

```bash
python3 main.py --profiles data/participants.csv --sessions data/fitness_sessions.csv data/fitness_sessions_invalid.csv --output output
```

`--sessions` takes one or more files. `python3 main.py --help` shows all options. On systems where the command is `python` instead of `python3`, use `python` in all commands.

Running the tests from the project folder:

```bash
python3 -m unittest -v
```

## Tests

There are 54 tests in `tests/`:

| File | What it covers |
|---|---|
| `test_validation.py` | valid and invalid IDs, type conversion, missing values, unknown participants, several problems in one row, and boundary values exactly on and just outside every limit |
| `test_models.py` | the signal quality boundary (0.5 usable, 0.49 not), the private attribute, timestamp ordering, duplicate timestamps, a session switching participant, inheritance and overriding |
| `test_loading.py` | the official files (29 accepted, then 1 accepted and 10 rejected with the right field for each line), missing file, folder instead of file, empty file, missing column, non-UTF-8 file, duplicate participant, blank lines, spaces and correct line numbers |
| `test_analysis.py` | the expected classification of all six sessions, reasons, baseline comparison, and the edges of each rule (3 vs 2 usable windows, baseline + 15 and + 45, activity 0.30 vs 0.31, recovery vs a small dip while resting) |
| `test_app.py` | the whole program: output folder created, all three files written, one summary row per session, identical output on a second run, missing profiles file, one missing session file skipped, all session files missing, and an output path that is a file |

## Example output

Console:

```text
Analysis complete.
  Participants loaded:   3 (0 profile row(s) rejected)
  Session rows accepted: 30
  Session rows rejected: 10
  Sessions analysed:     6
  Report files created:
    output/analysis_summary.csv
    output/analysis_report.txt
    output/rejected_records.txt
```

Results for the official data:

| Session | Participant | Classification |
|---|---|---|
| FIT-2026-001 | P001 Amina Noor | resting |
| FIT-2026-002 | P002 Jonas Berg | moderate activity |
| FIT-2026-003 | P003 Maya Chen | high activity |
| FIT-2026-004 | P001 Amina Noor | recovering |
| FIT-2026-005 | P002 Jonas Berg | insufficient data (all 5 windows have signal quality below 0.5) |
| FIT-2026-101 | P001 Amina Noor | insufficient data (only 1 row accepted, 4 rejected) |

FIT-2026-102 and FIT-2026-103 have no accepted rows at all, so they are listed in the report as not analysed.

Part of `analysis_report.txt`:

```text
FIT-2026-004: Amina Noor (P001)
----------------------------------------------------------------------
Classification: recovering
Windows: 6 accepted, 6 usable, 0 with low signal quality
Rejected rows with this session id: 0
Source file(s): fitness_sessions.csv
Measurements (usable windows only):
  Heart rate: avg 113.17 bpm, min 72 bpm, max 151 bpm (baseline 68 bpm, difference +45.17)
  Activity level: avg 0.55, min 0.18, max 0.92
  Skin response: avg 2.58, min 1.35, max 3.9 (baseline 1.2, difference +1.38)
  Temperature: avg 33.28 C, min 32.6 C, max 33.9 C (baseline 32.4 C, difference +0.88)
Recovery detected: yes
Why:
  - heart rate fell 12% and activity fell 34% from the first to the second half of the session
  - first half average heart rate 120.33 bpm was above the resting zone (baseline 68 + 15)
```

Part of `rejected_records.txt`:

```text
fitness_sessions_invalid.csv, line 11
  row: FIT-2026-102,P002,4,126,-0.50,55.0,1.30,0.91
  - field 'skin_response': -0.5 is outside the allowed range 0 to 60
  - field 'temperature': 55 is outside the allowed range 25 to 42
  - field 'activity_level': 1.3 is outside the allowed range 0 to 1

fitness_sessions_invalid.csv, line 12
  row: FIT-2026-103,P003,0,70,1.20,32.4,0.12
  - whole row: expected 8 fields but found 7
```

## Known limitations

- Recovery is found by comparing the averages of the two halves of a session, not by fitting a real trend over time.
- The classification thresholds are my own choices and are not calibrated against real wearable data.
- Because there is no maximum heart rate in the data, "high activity" only means far above the participant's resting baseline.
- A session ID with a wrong format (for example `FIT-26-102`) cannot be linked to any real session, so its rows are only reported as rejected.
- A `PermissionError` is handled in the code, but there is no automated test for it, because file permissions behave differently between operating systems.
- This is a learning project with simulated data, not a medical tool.
