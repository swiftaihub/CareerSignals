"""CLI for discovering public Greenhouse board tokens and Lever site names."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
from typing import Iterable

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.discovery.ats_boards import ATSBoardDiscoverer, BoardDiscoveryResult
from src.ingestion.persistence import write_json_snapshot


def _parse_target(value: str) -> tuple[str, str]:
    if "=" in value:
        company, url = value.split("=", 1)
        return company.strip(), url.strip()
    return "", value.strip()


def _read_targets_file(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Target file not found: {path}")

    if path.suffix.casefold() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            return [
                (
                    (row.get("company") or row.get("company_name") or "").strip(),
                    (row.get("url") or row.get("career_url") or row.get("careers_url") or "").strip(),
                )
                for row in reader
                if (row.get("url") or row.get("career_url") or row.get("careers_url") or "").strip()
            ]

    targets: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            targets.append(_parse_target(text))
    return targets


def _collect_targets(args: argparse.Namespace) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for value in args.url or []:
        targets.append(_parse_target(value))
    if args.input:
        targets.extend(_read_targets_file(Path(args.input)))

    seen: set[tuple[str, str]] = set()
    unique_targets: list[tuple[str, str]] = []
    for company, url in targets:
        key = (company.casefold(), url.casefold())
        if key not in seen:
            seen.add(key)
            unique_targets.append((company, url))
    return unique_targets


def _env_lines(results: Iterable[BoardDiscoveryResult], valid_only: bool) -> list[str]:
    valid_greenhouse = {
        validation.identifier
        for result in results
        for validation in result.validations
        if validation.source == "greenhouse" and validation.is_valid
    }
    valid_lever = {
        validation.identifier
        for result in results
        for validation in result.validations
        if validation.source == "lever" and validation.is_valid
    }

    all_greenhouse = {
        token for result in results for token in result.greenhouse_tokens
    }
    all_lever = {site for result in results for site in result.lever_sites}

    greenhouse = valid_greenhouse if valid_only else all_greenhouse
    lever = valid_lever if valid_only else all_lever

    return [
        f"GREENHOUSE_COMPANY_TOKENS={','.join(sorted(greenhouse, key=str.casefold))}",
        f"LEVER_COMPANY_SITES={','.join(sorted(lever, key=str.casefold))}",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover public Greenhouse board tokens and Lever site names."
    )
    parser.add_argument(
        "--url",
        action="append",
        help=(
            "Careers URL to inspect. Use 'Company=https://...' to label it. "
            "Can be passed multiple times."
        ),
    )
    parser.add_argument(
        "--input",
        help=(
            "Optional .txt or .csv file of targets. CSV columns: company,url. "
            "TXT lines may be URL or Company=https://..."
        ),
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Extract identifiers without calling public Greenhouse/Lever API endpoints.",
    )
    parser.add_argument(
        "--include-unvalidated",
        action="store_true",
        help="Include extracted identifiers in env output even when validation fails.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/discovery/ats_board_discovery.json",
        help="Base JSON output path. A timestamp is added automatically.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = _collect_targets(args)
    if not targets:
        raise SystemExit(
            "Provide at least one --url or --input target. "
            "Example: py scripts/discover_ats_boards.py --url https://jobs.lever.co/leverdemo"
        )

    discoverer = ATSBoardDiscoverer(validate=not args.no_validate)
    results = [discoverer.discover(url, company_name=company) for company, url in targets]

    output_path = write_json_snapshot(
        {
            "metadata": {
                "target_count": len(targets),
                "validated": not args.no_validate,
            },
            "results": [result.to_dict() for result in results],
        },
        args.output,
    )

    print(f"Discovery results written to: {output_path}")
    print()
    print("Paste these into .env:")
    for line in _env_lines(results, valid_only=not args.include_unvalidated and not args.no_validate):
        print(line)


if __name__ == "__main__":
    main()
