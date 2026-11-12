from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    col: int
    code: str
    message: str
    severity: Severity = Severity.WARNING

    def to_dict(self) -> dict:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data

    def __str__(self) -> str:
        return f"{self.path}:{self.line}:{self.col + 1}: {self.code} [{self.severity.value}] {self.message}"
