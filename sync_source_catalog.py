#!/usr/bin/env python3
"""Synchronize the Dragon Guide source registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lib.catalog import (  # noqa: E402
    DEFAULT_SEEDS,
    DEFAULT_USER_AGENT,
    PublicFetcher,
    crawl_catalog,
    load_registry,
    write_json,
    write_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "source-registry.jsonl"
DEFAULT_HEALTH_OUTPUT = PROJECT_ROOT / "data" / "source-health.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize public trade-source links from Dragon Guide")
    parser.add_argument("--dry-run", action="store_true", help="crawl and summarize without writing files")
    parser.add_argument("--max-pages", type=int, default=40, help="maximum Dragon Guide pages to fetch (default: 40)")
    parser.add_argument("--max-depth", type=int, default=2, help="maximum internal-link depth (default: 2)")
    parser.add_argument("--timeout", type=float, default=12.0, help="per-request timeout in seconds")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="registry JSONL output path")
    parser.add_argument("--health-output", type=Path, default=None, help="crawl audit JSON path")
    parser.add_argument("--seed", action="append", dest="seeds", help="replace default seed URLs; repeatable")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_pages < 1:
        raise SystemExit("--max-pages must be at least 1")
    if args.max_depth < 0:
        raise SystemExit("--max-depth cannot be negative")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")

    output = args.output.expanduser().resolve()
    health_output = (
        args.health_output.expanduser().resolve()
        if args.health_output
        else (DEFAULT_HEALTH_OUTPUT if output == DEFAULT_OUTPUT else output.with_name("source-health.json"))
    )
    previous = load_registry(output)
    fetcher = PublicFetcher(timeout=args.timeout, user_agent=DEFAULT_USER_AGENT)
    catalog, health = crawl_catalog(
        fetcher.fetch,
        seeds=tuple(args.seeds or DEFAULT_SEEDS),
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        previous=previous,
    )

    summary = {
        "dry_run": args.dry_run,
        "output": str(output),
        "health_output": str(health_output),
        "sources": len(catalog),
        "pages_attempted": health["pages_attempted"],
        "pages_succeeded": health["pages_succeeded"],
        "pages_failed": health["pages_failed"],
    }
    if not args.dry_run:
        write_jsonl(output, catalog)
        write_json(health_output, health)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
