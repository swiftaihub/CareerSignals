"""Progress helpers for long-running pipeline steps."""

from __future__ import annotations

from contextlib import AbstractContextManager
import os
import sys
from typing import Iterable, Iterator, TypeVar

T = TypeVar("T")

try:  # pragma: no cover - fallback only matters when rich is unavailable
    from rich.progress import (
        MofNCompleteColumn,
        Progress,
        ProgressColumn,
        Task,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Column
    from rich.text import Text
except ImportError:  # pragma: no cover
    Progress = None  # type: ignore[assignment]
    ProgressColumn = object  # type: ignore[assignment,misc]
    Task = object  # type: ignore[assignment,misc]
    Text = None  # type: ignore[assignment]
    Column = None  # type: ignore[assignment]


class AsciiBarColumn(ProgressColumn):
    """ASCII-only progress bar for Windows terminals with non-UTF encodings."""

    def __init__(self, width: int = 16) -> None:
        super().__init__()
        self.width = width

    def render(self, task: Task):
        if Text is None:
            return ""
        if task.total is None or task.total == 0:
            return Text("[" + "-" * self.width + "]")
        ratio = min(max(float(task.completed) / float(task.total), 0.0), 1.0)
        completed = int(self.width * ratio)
        return Text("[" + "#" * completed + "-" * (self.width - completed) + "]")


def _progress_enabled() -> bool:
    raw_value = os.getenv("CAREERSIGNAL_PROGRESS")
    if raw_value is not None:
        return raw_value.strip().casefold() in {"1", "true", "yes", "y", "on"}
    return sys.stderr.isatty()


class ProgressReporter(AbstractContextManager["ProgressReporter"]):
    """Small wrapper around Rich progress with a quiet no-op fallback."""

    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = _progress_enabled() if enabled is None else enabled
        self._progress = None

    def __enter__(self) -> "ProgressReporter":
        if self.enabled and Progress is not None:
            self._progress = Progress(
                TextColumn(
                    "[progress.description]{task.description}",
                    table_column=Column(width=40, overflow="crop") if Column else None,
                ),
                AsciiBarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                transient=False,
            )
            self._progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool | None:
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc_value, traceback)
        return None

    def iter(
        self,
        iterable: Iterable[T],
        description: str,
        *,
        total: int | None = None,
    ) -> Iterator[T]:
        """Yield items while advancing a progress task when enabled."""

        if self._progress is None:
            yield from iterable
            return

        task_id = self._progress.add_task(description, total=total)
        for item in iterable:
            yield item
            self._progress.advance(task_id)

    def add_task(self, description: str, *, total: int | None = None) -> int | None:
        if self._progress is None:
            return None
        return int(self._progress.add_task(description, total=total))

    def advance(self, task_id: int | None, amount: int = 1) -> None:
        if self._progress is not None and task_id is not None:
            self._progress.advance(task_id, amount)

    def complete(self, task_id: int | None) -> None:
        if self._progress is not None and task_id is not None:
            for task in self._progress.tasks:
                if task.id == task_id:
                    if task.total is not None:
                        self._progress.update(task_id, completed=task.total)
                    self._progress.stop_task(task_id)
                    break
