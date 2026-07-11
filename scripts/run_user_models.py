"""Worker-oriented CLI for one immutable user dbt run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipelines.user_dbt_refresh import run_user_dbt_refresh
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage and build a queued user/run config snapshot without calling Connectors."
    )
    parser.add_argument("--user-uuid", required=True)
    parser.add_argument("--run-uuid", required=True)
    parser.add_argument(
        "--snapshot-json",
        required=True,
        type=Path,
        help="Path to the worker-owned immutable JSON snapshot.",
    )
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot_json.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise SystemExit("snapshot JSON must contain an object")
    configure_logging()
    summary = run_user_dbt_refresh(args.user_uuid, args.run_uuid, snapshot)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
