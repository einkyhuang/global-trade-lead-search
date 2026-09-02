#!/usr/bin/env python3
"""Query the research-platform registry; this does not return customer leads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lib.catalog import load_registry  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_ROOT / "data" / "source-registry.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query research platforms in the source registry")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY, help="source registry JSONL path")
    parser.add_argument("--country", help="exact country filter, case-insensitive")
    parser.add_argument("--continent", help="exact continent filter, case-insensitive")
    parser.add_argument("--source-type", help="exact source_type filter, case-insensitive")
    parser.add_argument("--health-status", help="exact health_status filter, case-insensitive")
    parser.add_argument("--limit", type=int, default=20, help="maximum records to return (default: 20)")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json", help="output encoding")
    return parser


def query_records(
    records: list[dict[str, object]],
    *,
    country: str | None = None,
    continent: str | None = None,
    source_type: str | None = None,
    health_status: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    filters = {
        "country": country,
        "continent": continent,
        "source_type": source_type,
        "health_status": health_status,
    }
    result: list[dict[str, object]] = []
    for record in records:
        if any(
            expected is not None and str(record.get(field) or "").casefold() != expected.casefold()
            for field, expected in filters.items()
        ):
            continue
        result.append(record)
        if len(result) >= limit:
            break
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    records = query_records(
        load_registry(args.registry.expanduser().resolve()),
        country=args.country,
        continent=args.continent,
        source_type=args.source_type,
        health_status=args.health_status,
        limit=args.limit,
    )
    if args.format == "jsonl":
        for record in records:
            print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
