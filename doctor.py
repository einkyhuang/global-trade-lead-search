#!/usr/bin/env python3
"""Report local provider readiness without exposing credentials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lib.providers import AnySearchProvider, FirecrawlProvider


def last30days_status() -> dict[str, object]:
    candidates = [Path.home() / ".agents/skills/last30days", Path.home() / ".codex/skills/last30days"]
    installed = next((path for path in candidates if (path / "SKILL.md").is_file()), None)
    if installed:
        return {
            "available": True,
            "reason": f"skill installed at {installed}; import generated JSON/JSONL/Markdown with --signals-file",
        }
    return {
        "available": False,
        "reason": "skill not installed; only previously generated JSON/JSONL/Markdown signals can be imported",
    }


def report(runtime_conf: str | None = None) -> dict[str, object]:
    firecrawl = FirecrawlProvider()
    firecrawl_status = firecrawl.status()
    anysearch_status = AnySearchProvider(runtime_conf=runtime_conf).status()
    return {
        "firecrawl": {
            "available": firecrawl_status.available,
            "reason": firecrawl_status.reason,
            "api_key": "configured" if os.environ.get("FIRECRAWL_API_KEY") else "missing",
            "api_url": firecrawl.public_api_url(),
        },
        "anysearch": {"available": anysearch_status.available, "reason": anysearch_status.reason},
        "seed_import": {"available": True, "reason": "JSON, JSONL, and Markdown files supported"},
        "contact_import": {"available": True, "reason": "JSON, JSONL, and Markdown key-contact files supported"},
        "linkedin": {
            "available": True,
            "reason": "public-page research supported; login and bypass are not performed",
        },
        "last30days": last30days_status(),
        "safety": {"outreach": False, "login": False, "form_submission": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check global trade lead search provider readiness.")
    parser.add_argument("--anysearch-runtime-conf")
    args = parser.parse_args()
    print(json.dumps(report(args.anysearch_runtime_conf), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
