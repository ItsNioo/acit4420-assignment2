"""Writing the output files and the console completion summary.

Files are always fully rewritten, and nothing time-dependent is written
into them, so running the program again on the same input gives
identical output without any manual cleanup.
"""

import csv

from fitness_analyzer import analysis
from fitness_analyzer.exceptions import DataFileError
from fitness_analyzer.models import MIN_USABLE_SIGNAL_QUALITY

SUMMARY_FILE = "analysis_summary.csv"
REPORT_FILE = "analysis_report.txt"
REJECTED_FILE = "rejected_records.txt"

SUMMARY_COLUMNS = [
    "session_id",
    "participant_id",
    "participant_name",
    "source_files",
    "total_windows",
    "usable_windows",
    "low_quality_windows",
    "classification",
    "recovery_detected",
    "avg_heart_rate",
    "min_heart_rate",
    "max_heart_rate",
    "baseline_heart_rate",
    "heart_rate_vs_baseline",
    "avg_activity_level",
    "min_activity_level",
    "max_activity_level",
    "avg_skin_response",
    "skin_response_vs_baseline",
    "avg_temperature",
    "temperature_vs_baseline",
    "reasons",
]


def format_number(value):
    """Print numbers without pointless trailing zeros, and None as an empty value."""
    if value is None:
        return ""
    return f"{value:g}"


def prepare_output_dir(output_dir):
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        raise DataFileError(output_dir, "a file with this name exists, expected a directory") from None
    except PermissionError:
        raise DataFileError(output_dir, "permission denied when creating the output directory") from None


def summary_row(result):
    return {
        "session_id": result["session_id"],
        "participant_id": result["participant_id"],
        "participant_name": result["participant_name"],
        "source_files": "; ".join(result["source_files"]),
        "total_windows": result["total_windows"],
        "usable_windows": result["usable_windows"],
        "low_quality_windows": result["low_quality_windows"],
        "classification": result["classification"],
        "recovery_detected": "yes" if result["recovery_detected"] else "no",
        "avg_heart_rate": format_number(result["heart_rate"]["average"]),
        "min_heart_rate": format_number(result["heart_rate"]["minimum"]),
        "max_heart_rate": format_number(result["heart_rate"]["maximum"]),
        "baseline_heart_rate": format_number(result["baseline"]["baseline_heart_rate"]),
        "heart_rate_vs_baseline": format_number(result["heart_rate_vs_baseline"]),
        "avg_activity_level": format_number(result["activity_level"]["average"]),
        "min_activity_level": format_number(result["activity_level"]["minimum"]),
        "max_activity_level": format_number(result["activity_level"]["maximum"]),
        "avg_skin_response": format_number(result["skin_response"]["average"]),
        "skin_response_vs_baseline": format_number(result["skin_response_vs_baseline"]),
        "avg_temperature": format_number(result["temperature"]["average"]),
        "temperature_vs_baseline": format_number(result["temperature_vs_baseline"]),
        "reasons": "; ".join(result["reasons"]),
    }


def write_summary_csv(path, results):
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(summary_row(result))


def measurement_line(label, summary, unit="", baseline=None, difference=None):
    if summary["average"] is None:
        return f"  {label}: no usable values"
    line = (
        f"  {label}: avg {format_number(summary['average'])}{unit}, "
        f"min {format_number(summary['minimum'])}{unit}, "
        f"max {format_number(summary['maximum'])}{unit}"
    )
    if baseline is not None:
        line += f" (baseline {format_number(baseline)}{unit}, difference {difference:+g})"
    return line


def format_session_block(result, rejected_rows=0):
    baseline = result["baseline"]
    lines = [
        "-" * 70,
        f"{result['session_id']}: {result['participant_name']} ({result['participant_id']})",
        "-" * 70,
        f"Classification: {result['classification']}",
        f"Windows: {result['total_windows']} accepted, {result['usable_windows']} usable, "
        f"{result['low_quality_windows']} with low signal quality",
        f"Rejected rows with this session id: {rejected_rows}",
        f"Source file(s): {', '.join(result['source_files'])}",
        "Measurements (usable windows only):",
        measurement_line("Heart rate", result["heart_rate"], " bpm",
                         baseline["baseline_heart_rate"], result["heart_rate_vs_baseline"]),
        measurement_line("Activity level", result["activity_level"]),
        measurement_line("Skin response", result["skin_response"], "",
                         baseline["baseline_skin_response"], result["skin_response_vs_baseline"]),
        measurement_line("Temperature", result["temperature"], " C",
                         baseline["baseline_temperature"], result["temperature_vs_baseline"]),
        f"Recovery detected: {'yes' if result['recovery_detected'] else 'no'}",
        "Why:",
    ]
    lines.extend(f"  - {reason}" for reason in result["reasons"])
    return "\n".join(lines)


def write_analysis_report(path, results, run_info):
    lines = [
        "SMART FITNESS SESSION ANALYZER: ANALYSIS REPORT",
        "=" * 70,
        f"Profiles file: {run_info['profiles_file']}",
        f"Session files read: {', '.join(run_info['session_files_read']) or 'none'}",
        f"Session files skipped: {', '.join(run_info['session_files_skipped']) or 'none'}",
        f"Participants loaded: {run_info['participants_loaded']} "
        f"({run_info['profile_rows_rejected']} profile row(s) rejected)",
        f"Session rows accepted: {run_info['session_rows_accepted']}",
        f"Session rows rejected: {run_info['session_rows_rejected']}",
        f"Sessions analysed: {len(results)}",
        "",
        "Rules used:",
        f"  - windows with signal quality below {MIN_USABLE_SIGNAL_QUALITY:g} are kept but not analysed",
        f"  - at least {analysis.MIN_USABLE_WINDOWS} usable windows are needed, "
        "otherwise the result is 'insufficient data'",
        f"  - resting: average heart rate at most baseline + {analysis.RESTING_HR_OFFSET} bpm "
        f"and average activity at most {analysis.RESTING_ACTIVITY_CEILING:.2f}",
        f"  - moderate activity: average heart rate at most baseline + {analysis.MODERATE_HR_OFFSET} bpm",
        f"  - high activity: average heart rate more than baseline + {analysis.MODERATE_HR_OFFSET} bpm",
        "  - recovering: first half above the resting zone, then heart rate drops at least "
        f"{analysis.RECOVERY_HR_DROP_FRACTION:.0%}",
        f"    and activity drops at least {analysis.RECOVERY_ACTIVITY_DROP_FRACTION:.0%} in the second half",
        "",
    ]
    counts = {}
    for result in results:
        counts[result["classification"]] = counts.get(result["classification"], 0) + 1
    lines.append("Results by classification:")
    lines.extend(f"  - {name}: {count}" for name, count in sorted(counts.items()))
    lines.append("")
    if run_info["unanalysed_sessions"]:
        lines.append("Sessions not analysed because none of their rows were accepted:")
        lines.extend(f"  - {session_id}" for session_id in run_info["unanalysed_sessions"])
        lines.append("  (see rejected_records.txt for the reasons)")
        lines.append("")
    rejected_counts = run_info["rejected_rows_by_session"]
    for result in results:
        lines.append(format_session_block(result, rejected_counts.get(result["session_id"], 0)))
        lines.append("")

    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def write_rejected_records(path, rejected, sessions):
    lines = [
        "REJECTED RECORDS",
        "=" * 70,
        f"{len(rejected)} row(s) were rejected and left out completely.",
        "",
    ]
    if not rejected:
        lines.append("No rows were rejected.")
    for record in rejected:
        lines.append(f"{record.source_file}, line {record.line_number}")
        lines.append(f"  row: {record.raw_text}")
        for field, reason in record.problems:
            if field == "row":
                lines.append(f"  - whole row: {reason}")
            else:
                lines.append(f"  - field '{field}': {reason}")
        lines.append("")

    low_quality = [obs for session in sessions for obs in session.low_quality_observations]
    lines.extend([
        "",
        "LOW SIGNAL QUALITY (accepted, but excluded from analysis)",
        "=" * 70,
        f"Rule: windows with signal_quality below {MIN_USABLE_SIGNAL_QUALITY:g} are valid records,",
        "but the readings cannot be trusted, so they are not used in any calculation.",
        f"{len(low_quality)} window(s) were excluded for this reason.",
        "",
    ])
    for session in sessions:
        for obs in session.low_quality_observations:
            lines.append(
                f"{obs.location}: session {session.session_id}, timestamp {obs.timestamp}, "
                f"signal_quality {obs.signal_quality:g}"
            )

    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def write_reports(output_dir, results, rejected, sessions, run_info):
    """Write all three output files and return their paths."""
    prepare_output_dir(output_dir)
    paths = [output_dir / SUMMARY_FILE, output_dir / REPORT_FILE, output_dir / REJECTED_FILE]
    try:
        write_summary_csv(paths[0], results)
        write_analysis_report(paths[1], results, run_info)
        write_rejected_records(paths[2], rejected, sessions)
    except PermissionError as error:
        raise DataFileError(error.filename, "permission denied when writing the report") from None
    except IsADirectoryError as error:
        raise DataFileError(error.filename, "expected a file name but found a directory") from None
    return paths


def format_completion_summary(run_info, written_paths, display):
    lines = [
        "Analysis complete.",
        f"  Participants loaded:   {run_info['participants_loaded']} "
        f"({run_info['profile_rows_rejected']} profile row(s) rejected)",
        f"  Session rows accepted: {run_info['session_rows_accepted']}",
        f"  Session rows rejected: {run_info['session_rows_rejected']}",
        f"  Sessions analysed:     {run_info['sessions_analysed']}",
    ]
    if run_info["session_files_skipped"]:
        lines.append(f"  Skipped files:         {', '.join(run_info['session_files_skipped'])}")
    lines.append("  Report files created:")
    lines.extend(f"    {display(path)}" for path in written_paths)
    return "\n".join(lines)
