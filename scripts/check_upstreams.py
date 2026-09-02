#!/usr/bin/env python3
"""Read-only release checks for optional upstream projects."""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPOSITORIES = {
    "firecrawl": "firecrawl/firecrawl",
    "last30days": "mvanhorn/last30days-skill",
}
USER_AGENT = "global-trade-lead-search-upstream-check/1.0"


class UpstreamError(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def parse_version(value: str | None) -> tuple[tuple[int, ...], tuple[tuple[int, Any], ...]] | None:
    """Parse common v-prefixed SemVer-like tags without third-party packages."""
    text = str(value or "").strip()
    match = re.search(r"(?i)(?:^|[^0-9])v?(\d+(?:\.\d+)*)(?:-([0-9a-z.-]+))?", text)
    if not match:
        return None
    numeric = tuple(int(part) for part in match.group(1).split("."))
    prerelease: list[tuple[int, Any]] = []
    if match.group(2):
        for part in match.group(2).split("."):
            prerelease.append((0, int(part)) if part.isdigit() else (1, part.casefold()))
    return numeric, tuple(prerelease)


def compare_versions(left: str, right: str) -> int | None:
    """Return -1, 0, 1 for left versus right, or None if either is unparseable."""
    parsed_left = parse_version(left)
    parsed_right = parse_version(right)
    if parsed_left is None or parsed_right is None:
        return None
    left_numbers, left_pre = parsed_left
    right_numbers, right_pre = parsed_right
    width = max(len(left_numbers), len(right_numbers))
    left_numbers += (0,) * (width - len(left_numbers))
    right_numbers += (0,) * (width - len(right_numbers))
    if left_numbers != right_numbers:
        return -1 if left_numbers < right_numbers else 1
    if left_pre == right_pre:
        return 0
    if not left_pre:
        return 1
    if not right_pre:
        return -1
    return -1 if left_pre < right_pre else 1


def find_last30days_skill() -> Path | None:
    candidates = [
        Path.home() / ".agents/skills/last30days/SKILL.md",
        Path.home() / ".codex/skills/last30days/SKILL.md",
    ]
    return next((path for path in candidates if path.is_file()), None)


def read_skill_version(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\Z)", text, flags=re.DOTALL)
    if not frontmatter:
        return None
    match = re.search(r"(?mi)^version\s*:\s*['\"]?([^'\"#\s]+)", frontmatter.group(1))
    return match.group(1).strip() if match else None


def fetch_latest_release(repo: str, timeout: float) -> str:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise UpstreamError("no_release", "GitHub reports no latest release") from exc
        if exc.code in {403, 429}:
            remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
            detail = "GitHub API rate limit reached" if remaining == "0" else f"GitHub API rejected request with HTTP {exc.code}"
            raise UpstreamError("rate_limited", detail) from exc
        raise UpstreamError("http_error", f"GitHub API returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        reason = getattr(exc, "reason", None)
        detail = "timeout" if isinstance(exc, (TimeoutError, socket.timeout)) else str(reason or "network unavailable")
        raise UpstreamError("network_error", f"GitHub API request failed: {detail}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstreamError("invalid_response", "GitHub API returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise UpstreamError("invalid_response", "GitHub API returned an unexpected response")
    version = payload.get("tag_name") or payload.get("name")
    if not isinstance(version, str) or not version.strip():
        raise UpstreamError("invalid_response", "latest release has no tag_name or name")
    return version.strip()


def check_project(project: str, timeout: float, checked_at: str) -> dict[str, Any]:
    repo = REPOSITORIES[project]
    local_version = read_skill_version(find_last30days_skill()) if project == "last30days" else None
    result: dict[str, Any] = {
        "checked_at": checked_at,
        "repo": repo,
        "latest_version": None,
        "local_version": local_version,
        "update_available": None,
        "status": "checking",
    }
    try:
        latest = fetch_latest_release(repo, timeout)
    except UpstreamError as exc:
        result["status"] = exc.status
        result["message"] = str(exc)
        return result
    result["latest_version"] = latest
    if project == "firecrawl":
        result["status"] = "upstream_only"
        result["message"] = "latest upstream release only; no local Firecrawl core installation is asserted"
        return result
    if not local_version:
        result["status"] = "local_version_missing"
        result["message"] = "installed last30days SKILL.md version was not found"
        return result
    comparison = compare_versions(local_version, latest)
    if comparison is None:
        result["status"] = "version_unparseable"
        result["message"] = "local or upstream version could not be compared"
        return result
    result["update_available"] = comparison < 0
    result["status"] = "update_available" if comparison < 0 else "current" if comparison == 0 else "local_newer"
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only GitHub release check; never downloads, installs, executes, or overwrites upstream code."
    )
    parser.add_argument("--project", choices=("all", "firecrawl", "last30days"), default="all")
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    projects = list(REPOSITORIES) if args.project == "all" else [args.project]
    results = [check_project(project, args.timeout, checked_at) for project in projects]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

