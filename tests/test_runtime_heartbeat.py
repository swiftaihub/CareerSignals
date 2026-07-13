from __future__ import annotations

import os
import time

from packages.careersignal_core.heartbeat import (
    FileHeartbeat,
    heartbeat_is_fresh,
    main,
)


def test_unconfigured_heartbeat_is_a_noop(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("CAREERSIGNAL_HEARTBEAT_PATH", raising=False)
    heartbeat = FileHeartbeat.from_environment()

    with heartbeat:
        heartbeat.beat()

    assert heartbeat.path is None
    assert list(tmp_path.iterdir()) == []


def test_file_heartbeat_updates_in_background(tmp_path) -> None:
    path = tmp_path / "worker" / "heartbeat"
    heartbeat = FileHeartbeat(path, interval_seconds=0.01)

    with heartbeat:
        first_modified_at = path.stat().st_mtime_ns
        deadline = time.monotonic() + 1.0
        while path.stat().st_mtime_ns == first_modified_at and time.monotonic() < deadline:
            time.sleep(0.01)

        assert path.stat().st_mtime_ns > first_modified_at
        assert heartbeat_is_fresh(path, max_age_seconds=1.0)


def test_heartbeat_freshness_check_rejects_missing_and_stale_files(tmp_path) -> None:
    path = tmp_path / "heartbeat"
    assert heartbeat_is_fresh(path, max_age_seconds=60.0) is False

    path.touch()
    old_time = time.time() - 120.0
    os.utime(path, (old_time, old_time))

    assert heartbeat_is_fresh(path, max_age_seconds=60.0) is False
    assert main(["--path", str(path), "--max-age-seconds", "60"]) == 1


def test_heartbeat_cli_uses_environment_path(monkeypatch, tmp_path) -> None:
    path = tmp_path / "heartbeat"
    path.touch()
    monkeypatch.setenv("CAREERSIGNAL_HEARTBEAT_PATH", str(path))

    assert main(["--max-age-seconds", "60"]) == 0
