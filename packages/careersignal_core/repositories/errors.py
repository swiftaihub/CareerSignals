"""Domain-level repository errors translated to stable API error codes."""

from __future__ import annotations


class RepositoryError(RuntimeError):
    error_code = "REPOSITORY_ERROR"


class NotFoundError(RepositoryError):
    error_code = "NOT_FOUND"


class ConflictError(RepositoryError):
    error_code = "CONFLICT"


class PipelineAlreadyActiveError(ConflictError):
    error_code = "PIPELINE_ALREADY_ACTIVE"


class PipelineDailyLimitError(RepositoryError):
    error_code = "PIPELINE_DAILY_LIMIT_REACHED"


class InvalidStateTransitionError(ConflictError):
    error_code = "INVALID_STATE_TRANSITION"
