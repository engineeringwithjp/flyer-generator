"""Quality-control result models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    ERROR = "error"  # blocks delivery
    WARNING = "warning"  # logged, does not block
    INFO = "info"


class QAIssue(BaseModel):
    check: str
    severity: Severity
    message: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{self.severity}] {self.check}: {self.message}"


class QAResult(BaseModel):
    passed: bool = True
    score: int = Field(default=100, ge=0, le=100)
    issues: list[QAIssue] = Field(default_factory=list)
    warnings: list[QAIssue] = Field(default_factory=list)
    checked_by: str = "deterministic"

    @classmethod
    def from_issues(cls, issues: list[QAIssue], checked_by: str = "deterministic") -> QAResult:
        errors = [i for i in issues if i.severity is Severity.ERROR]
        warnings = [i for i in issues if i.severity is Severity.WARNING]
        score = max(0, 100 - 25 * len(errors) - 5 * len(warnings))
        return cls(
            passed=not errors,
            score=score,
            issues=errors,
            warnings=warnings,
            checked_by=checked_by,
        )

    def merge(self, other: QAResult) -> QAResult:
        return QAResult(
            passed=self.passed and other.passed,
            score=min(self.score, other.score),
            issues=[*self.issues, *other.issues],
            warnings=[*self.warnings, *other.warnings],
            checked_by=f"{self.checked_by}+{other.checked_by}",
        )
