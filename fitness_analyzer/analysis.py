"""Summaries, baseline comparison and session classification.

Only usable windows (signal quality of at least 0.5) are analysed.
"""

from statistics import mean

from fitness_analyzer.models import MIN_USABLE_SIGNAL_QUALITY

MIN_USABLE_WINDOWS = 3
MIN_WINDOWS_FOR_RECOVERY = 4

# Heart rate limits are offsets above the participant's own baseline.
RESTING_HR_OFFSET = 15
RESTING_ACTIVITY_CEILING = 0.30
MODERATE_HR_OFFSET = 45

# Recovery: compare the first half of the session with the second half.
RECOVERY_HR_DROP_FRACTION = 0.10
RECOVERY_ACTIVITY_DROP_FRACTION = 0.20

INSUFFICIENT = "insufficient data"
RESTING = "resting"
MODERATE = "moderate activity"
HIGH = "high activity"
RECOVERING = "recovering"


def summarize_values(values):
    """Average, minimum and maximum of a list, or None values if it is empty."""
    if not values:
        return {"average": None, "minimum": None, "maximum": None}
    return {
        "average": round(mean(values), 2),
        "minimum": round(min(values), 2),
        "maximum": round(max(values), 2),
    }


def difference_from_baseline(average, baseline):
    if average is None:
        return None
    return round(average - baseline, 2)


def recovery_trend(usable_observations):
    """
    Compare the first and second half of the session.

    Returns None if there are too few windows to say anything about a trend.
    """
    if len(usable_observations) < MIN_WINDOWS_FOR_RECOVERY:
        return None
    split = len(usable_observations) // 2
    first, second = usable_observations[:split], usable_observations[split:]

    first_hr = mean(obs.heart_rate for obs in first)
    second_hr = mean(obs.heart_rate for obs in second)
    first_activity = mean(obs.activity_level for obs in first)
    second_activity = mean(obs.activity_level for obs in second)

    return {
        "first_half_heart_rate": round(first_hr, 2),
        "second_half_heart_rate": round(second_hr, 2),
        "heart_rate_drop": (first_hr - second_hr) / first_hr if first_hr else 0.0,
        "activity_drop": (first_activity - second_activity) / first_activity if first_activity else 0.0,
    }


def detect_recovery(trend, baseline_heart_rate):
    """
    Recovery means heart rate and activity both fall clearly in the second
    half, after a first half that was actually above the resting zone.
    The last condition stops a resting session with a small dip from being
    reported as recovery.
    """
    if trend is None:
        return False
    was_active = trend["first_half_heart_rate"] > baseline_heart_rate + RESTING_HR_OFFSET
    return (
        was_active
        and trend["heart_rate_drop"] >= RECOVERY_HR_DROP_FRACTION
        and trend["activity_drop"] >= RECOVERY_ACTIVITY_DROP_FRACTION
    )


def classify_session(usable_observations, total_windows, baseline_heart_rate):
    """Return (classification, list of reasons)."""
    usable_count = len(usable_observations)
    low_quality = total_windows - usable_count

    if usable_count < MIN_USABLE_WINDOWS:
        reasons = [
            f"only {usable_count} of {total_windows} accepted windows were usable, "
            f"at least {MIN_USABLE_WINDOWS} are needed for a classification"
        ]
        if low_quality:
            reasons.append(
                f"{low_quality} window(s) had signal quality below {MIN_USABLE_SIGNAL_QUALITY:g}"
            )
        return INSUFFICIENT, reasons

    trend = recovery_trend(usable_observations)
    if detect_recovery(trend, baseline_heart_rate):
        return RECOVERING, [
            f"heart rate fell {trend['heart_rate_drop']:.0%} and activity fell "
            f"{trend['activity_drop']:.0%} from the first to the second half of the session",
            f"first half average heart rate {trend['first_half_heart_rate']:g} bpm was above "
            f"the resting zone (baseline {baseline_heart_rate:g} + {RESTING_HR_OFFSET})",
        ]

    avg_hr = mean(obs.heart_rate for obs in usable_observations)
    avg_activity = mean(obs.activity_level for obs in usable_observations)
    above = avg_hr - baseline_heart_rate
    hr_text = f"average heart rate {avg_hr:.1f} bpm is {above:+.1f} bpm from baseline {baseline_heart_rate:g}"

    if above <= RESTING_HR_OFFSET and avg_activity <= RESTING_ACTIVITY_CEILING:
        return RESTING, [
            f"{hr_text}, within the resting limit of +{RESTING_HR_OFFSET}",
            f"average activity {avg_activity:.2f} is at or below {RESTING_ACTIVITY_CEILING:.2f}",
        ]
    if above <= MODERATE_HR_OFFSET:
        reasons = [f"{hr_text}, within the moderate limit of +{MODERATE_HR_OFFSET}"]
        if above <= RESTING_HR_OFFSET:
            reasons.append(
                f"heart rate is in the resting zone, but average activity {avg_activity:.2f} "
                f"is above {RESTING_ACTIVITY_CEILING:.2f}"
            )
        return MODERATE, reasons
    return HIGH, [f"{hr_text}, more than +{MODERATE_HR_OFFSET} above baseline"]


class SessionAnalyzer:
    """Turns a Session into one structured result dictionary."""

    @staticmethod
    def analyze(session) -> dict:
        participant = session.participant
        usable = session.usable_observations

        heart_rate = summarize_values([obs.heart_rate for obs in usable])
        activity = summarize_values([obs.activity_level for obs in usable])
        skin = summarize_values([obs.skin_response for obs in usable])
        temperature = summarize_values([obs.temperature for obs in usable])

        classification, reasons = classify_session(
            usable, session.total_count, participant.baseline_heart_rate
        )
        recovery = classification == RECOVERING

        return {
            "session_id": session.session_id,
            "participant_id": participant.person_id,
            "participant_name": participant.name,
            "source_files": session.source_files,
            "total_windows": session.total_count,
            "usable_windows": len(usable),
            "low_quality_windows": len(session.low_quality_observations),
            "classification": classification,
            "has_enough_data": classification != INSUFFICIENT,
            "recovery_detected": recovery,
            "reasons": reasons,
            "heart_rate": heart_rate,
            "activity_level": activity,
            "skin_response": skin,
            "temperature": temperature,
            "baseline": participant.reference_summary(),
            "heart_rate_vs_baseline": difference_from_baseline(
                heart_rate["average"], participant.baseline_heart_rate
            ),
            "skin_response_vs_baseline": difference_from_baseline(
                skin["average"], participant.baseline_skin_response
            ),
            "temperature_vs_baseline": difference_from_baseline(
                temperature["average"], participant.baseline_temperature
            ),
        }
