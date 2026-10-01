"""Custom exceptions for the fitness analyzer.

InvalidIdentifierError and InvalidRecordError are raised for single rows
that cannot be accepted, so the program can record the problem and move
on to the next row. DataFileError is raised when a whole file cannot be
used, so the caller can decide whether to skip that file or stop.
"""


class InvalidIdentifierError(ValueError):
    """Raised when an identifier has an invalid format."""

    def __init__(self, field, value, expected):
        self.field = field
        self.value = value
        self.expected = expected
        super().__init__(f"{field} '{value}' does not match the required format {expected}")

    @property
    def reason(self) -> str:
        return f"'{self.value}' does not match the required format {self.expected}"


class InvalidRecordError(ValueError):
    """Raised when a CSV record cannot be accepted.

    problems is a list of (field, reason) tuples, so one rejected row can
    report every problem found in it instead of only the first one.
    """

    def __init__(self, problems):
        self.problems = list(problems)
        message = "; ".join(f"{field}: {reason}" for field, reason in self.problems)
        super().__init__(message)


class DataFileError(Exception):
    """Raised when an input or output file cannot be used at all."""

    def __init__(self, path, reason):
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")
