from __future__ import annotations

from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


ROOT = Path(__file__).parents[1]


def _requirements(path: Path) -> list[Requirement]:
    return [
        Requirement(line)
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    ]


def test_lock_is_exact_and_satisfies_every_direct_requirement() -> None:
    direct = _requirements(ROOT / "requirements.txt")
    locked = _requirements(ROOT / "requirements.lock")
    lock_versions: dict[str, Version] = {}

    for requirement in locked:
        assert len(requirement.specifier) == 1
        specifier = next(iter(requirement.specifier))
        assert specifier.operator == "=="
        name = canonicalize_name(requirement.name)
        assert name not in lock_versions
        lock_versions[name] = Version(specifier.version)

    for requirement in direct:
        name = canonicalize_name(requirement.name)
        assert name in lock_versions, f"{requirement.name} is absent from requirements.lock"
        assert lock_versions[name] in requirement.specifier
