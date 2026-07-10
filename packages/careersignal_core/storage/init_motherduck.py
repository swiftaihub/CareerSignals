"""CLI entry point for initializing MotherDuck schemas."""

from __future__ import annotations

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from packages.careersignal_core.storage.schema import init_motherduck_schema


def main() -> None:
    init_motherduck_schema()
    print("MotherDuck schemas initialized.")


if __name__ == "__main__":
    main()
