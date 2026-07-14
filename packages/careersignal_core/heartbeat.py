"""Optional file heartbeat for long-running CareerSignals processes."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import threading
import time
from typing import Sequence


LOGGER = logging.getLogger(__name__)
HEARTBEAT_PATH_ENV = "CAREERSIGNAL_HEARTBEAT_PATH"
DEFAULT_INTERVAL_SECONDS = 10.0
DEFAULT_MAX_AGE_SECONDS = 60.0


class FileHeartbeat:
    """Touch a configured file periodically from a daemon thread."""

    def __init__(
        self,
        path: str | Path | None,
        *,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self.path = Path(path) if path else None
        self.interval_seconds = max(float(interval_seconds), 0.01)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def from_environment(cls) -> "FileHeartbeat":
        configured_path = os.getenv(HEARTBEAT_PATH_ENV, "").strip()
        return cls(configured_path or None)

    def beat(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            try:
                self.beat()
            except OSError as exc:
                LOGGER.error(
                    "Unable to update process heartbeat at %s (%s)",
                    self.path,
                    type(exc).__name__,
                )

    def start(self) -> None:
        if self.path is None or self._thread is not None:
            return
        self.beat()
        self._thread = threading.Thread(
            target=self._run,
            name="careersignals-file-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def __enter__(self) -> "FileHeartbeat":
        self.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.stop()


def heartbeat_is_fresh(
    path: str | Path,
    *,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    now: float | None = None,
) -> bool:
    """Return whether a heartbeat file exists and has a recent modification time."""

    try:
        modified_at = Path(path).stat().st_mtime
    except OSError:
        return False
    current_time = time.time() if now is None else now
    return current_time - modified_at <= max(float(max_age_seconds), 0.0)


def main(argv: Sequence[str] | None = None) -> int:
    """Check heartbeat freshness for a container health command."""

    parser = argparse.ArgumentParser(description="Check a CareerSignals process heartbeat file.")
    parser.add_argument("--path", default=os.getenv(HEARTBEAT_PATH_ENV, ""))
    parser.add_argument(
        "--max-age-seconds",
        type=float,
        default=DEFAULT_MAX_AGE_SECONDS,
    )
    args = parser.parse_args(argv)
    if not args.path:
        return 1
    return 0 if heartbeat_is_fresh(args.path, max_age_seconds=args.max_age_seconds) else 1


if __name__ == "__main__":
    raise SystemExit(main())
