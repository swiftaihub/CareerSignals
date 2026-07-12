"""Queue claim facade kept separate for focused concurrency tests."""

from __future__ import annotations

from typing import Any

from packages.careersignal_core.repositories.pipeline_runs import PipelineRunRepository


def claim_next_user_pipeline_run(
    worker_id: str, repository: PipelineRunRepository | None = None
) -> dict[str, Any] | None:
    return (repository or PipelineRunRepository()).claim_next(worker_id)
