"""Domain classes: participants, observation windows, sessions and rejected rows."""

from fitness_analyzer.exceptions import InvalidRecordError

# Readings with signal quality below this are kept as accepted records but
# left out of the analysis, since the sensor value cannot be trusted.
MIN_USABLE_SIGNAL_QUALITY = 0.5


class Person:
    """Basic identity shared by anyone tracked by the system."""

    def __init__(self, name: str, person_id: str):
        self.name = name
        self.person_id = person_id

    def __str__(self) -> str:
        return f"{self.name} ({self.person_id})"


class Participant(Person):
    """A person who trains, with the baseline values their sessions are compared against."""

    def __init__(
        self,
        name: str,
        person_id: str,
        baseline_heart_rate: float,
        baseline_skin_response: float,
        baseline_temperature: float,
    ):
        super().__init__(name, person_id)
        self.baseline_heart_rate = baseline_heart_rate
        self.baseline_skin_response = baseline_skin_response
        self.baseline_temperature = baseline_temperature

    def __str__(self) -> str:
        return (
            f"{self.name} ({self.person_id}), baseline heart rate "
            f"{self.baseline_heart_rate:g} bpm, skin response "
            f"{self.baseline_skin_response:g}, temperature {self.baseline_temperature:g} C"
        )

    @classmethod
    def from_profile(cls, profile: dict) -> "Participant":
        """Build a Participant from a validated participants.csv row."""
        return cls(
            name=profile["name"],
            person_id=profile["participant_id"],
            baseline_heart_rate=profile["baseline_heart_rate"],
            baseline_skin_response=profile["baseline_skin_response"],
            baseline_temperature=profile["baseline_temperature"],
        )

    def reference_summary(self) -> dict:
        return {
            "baseline_heart_rate": self.baseline_heart_rate,
            "baseline_skin_response": self.baseline_skin_response,
            "baseline_temperature": self.baseline_temperature,
        }


class Observation:
    """
    One accepted measurement window. Whether the window is usable for
    analysis is decided once from its signal quality and kept in
    __usable, which is only read through the is_usable property.
    """

    def __init__(
        self,
        timestamp: int,
        heart_rate: float,
        skin_response: float,
        temperature: float,
        activity_level: float,
        signal_quality: float,
        source_file: str = "",
        line_number: int = 0,
    ):
        self.timestamp = timestamp
        self.heart_rate = heart_rate
        self.skin_response = skin_response
        self.temperature = temperature
        self.activity_level = activity_level
        self.signal_quality = signal_quality
        self.source_file = source_file
        self.line_number = line_number
        self.__usable = signal_quality >= MIN_USABLE_SIGNAL_QUALITY

    @classmethod
    def from_record(cls, record: dict, source_file: str, line_number: int) -> "Observation":
        """Build an Observation from a validated session row."""
        return cls(
            timestamp=record["timestamp"],
            heart_rate=record["heart_rate"],
            skin_response=record["skin_response"],
            temperature=record["temperature"],
            activity_level=record["activity_level"],
            signal_quality=record["signal_quality"],
            source_file=source_file,
            line_number=line_number,
        )

    @property
    def is_usable(self) -> bool:
        return self.__usable

    @property
    def location(self) -> str:
        return f"{self.source_file}, line {self.line_number}"


class Session:
    """A training session: one participant plus the windows recorded during it."""

    def __init__(self, session_id: str, participant: Participant):
        self.session_id = session_id
        self.participant = participant
        self.__observations = {}  # timestamp -> Observation

    def add_observation(self, observation: Observation) -> None:
        existing = self.__observations.get(observation.timestamp)
        if existing is not None:
            raise InvalidRecordError([(
                "timestamp",
                f"duplicate timestamp {observation.timestamp} for session "
                f"{self.session_id}, first seen at {existing.location}",
            )])
        self.__observations[observation.timestamp] = observation

    @property
    def observations(self) -> list:
        """All accepted windows, ordered by timestamp."""
        return [self.__observations[key] for key in sorted(self.__observations)]

    @property
    def usable_observations(self) -> list:
        return [obs for obs in self.observations if obs.is_usable]

    @property
    def low_quality_observations(self) -> list:
        return [obs for obs in self.observations if not obs.is_usable]

    @property
    def source_files(self) -> list:
        return sorted({obs.source_file for obs in self.observations})

    @property
    def total_count(self) -> int:
        return len(self.__observations)


class SessionCollection:
    """Groups accepted rows into sessions using the session identifier."""

    def __init__(self):
        self.__sessions = {}  # session_id -> Session

    def add(self, session_id: str, participant: Participant, observation: Observation) -> None:
        session = self.__sessions.get(session_id)
        if session is None:
            session = Session(session_id, participant)
            self.__sessions[session_id] = session
        elif session.participant.person_id != participant.person_id:
            raise InvalidRecordError([(
                "participant_id",
                f"session {session_id} already belongs to participant "
                f"{session.participant.person_id}",
            )])
        session.add_observation(observation)

    @property
    def sessions(self) -> list:
        return [self.__sessions[key] for key in sorted(self.__sessions)]

    def __len__(self) -> int:
        return len(self.__sessions)


class RejectedRecord:
    """A CSV row that could not be accepted, with where it came from and why."""

    def __init__(self, source_file: str, line_number: int, problems: list, raw_values: list,
                 session_id: str = ""):
        self.source_file = source_file
        self.line_number = line_number
        self.problems = list(problems)
        self.raw_values = list(raw_values)
        self.session_id = session_id

    @property
    def raw_text(self) -> str:
        return ",".join(self.raw_values)

    def __str__(self) -> str:
        reasons = "; ".join(f"{field}: {reason}" for field, reason in self.problems)
        return f"{self.source_file}, line {self.line_number}: {reasons}"
