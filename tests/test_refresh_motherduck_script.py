from __future__ import annotations

from pathlib import Path

import scripts.refresh_motherduck as refresh_motherduck


def test_refresh_script_prefers_workspace_python() -> None:
    preferred = refresh_motherduck._preferred_workspace_python()

    assert preferred.name in {"python", "python.exe"}
    assert preferred.parent.name in {"bin", "Scripts"}
    assert preferred.parent.parent.name == ".venv311"


def test_running_preferred_python_returns_false_for_different_path(tmp_path, monkeypatch) -> None:
    preferred = tmp_path / "python.exe"
    preferred.write_text("", encoding="utf-8")
    monkeypatch.setattr(refresh_motherduck.sys, "executable", str(tmp_path / "other.exe"))

    assert refresh_motherduck._running_preferred_python(preferred) is False
