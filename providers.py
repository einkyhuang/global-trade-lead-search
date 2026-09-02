"""External provider adapters with bounded, explicit failure behavior."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .normalize import load_records


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderStatus:
    available: bool
    reason: str


def redact_secrets(value: Any) -> str:
    """Remove configured provider keys and obvious key assignments from diagnostics."""
    text = str(value)
    for name in ("FIRECRAWL_API_KEY", "ANYSEARCH_API_KEY"):
        secret = os.environ.get(name, "")
        if secret:
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(rf"(?i)({name}\s*[=:]\s*)[^\s,;]+", rf"\1[REDACTED]", text)
    text = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    return text


def _extract_result_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("web", "results", "items"):
        if isinstance(payload.get(key), list):
            return [item for item in payload[key] if isinstance(item, dict)]
    data = payload.get("data")
    if data is not None:
        return _extract_result_list(data)
    result = payload.get("result")
    if result is not None:
        return _extract_result_list(result)
    return []


class FirecrawlProvider:
    name = "firecrawl"

    def __init__(self, api_url: str | None = None, api_key: str | None = None, timeout: float = 20.0):
        configured_url = api_url or os.environ.get("FIRECRAWL_API_URL") or "https://api.firecrawl.dev/v2"
        self.api_url = configured_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("FIRECRAWL_API_KEY", "")
        self.timeout = timeout

    def _parsed_url(self):
        return urlsplit(self.api_url)

    def public_api_url(self) -> str:
        parsed = self._parsed_url()
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))

    def _v2_url(self, path: str) -> str:
        base = self.api_url.rstrip("/")
        if not urlsplit(base).path.rstrip("/").endswith("/v2"):
            base += "/v2"
        return f"{base}/{path.lstrip('/')}"

    def status(self) -> ProviderStatus:
        parsed = self._parsed_url()
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ProviderStatus(False, "FIRECRAWL_API_URL must use http or https")
        if parsed.username or parsed.password:
            return ProviderStatus(False, "FIRECRAWL_API_URL must not contain username or password")
        if parsed.hostname.casefold() == "api.firecrawl.dev" and not self.api_key:
            return ProviderStatus(False, "FIRECRAWL_API_KEY missing for official cloud endpoint")
        return ProviderStatus(True, "configured")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        status = self.status()
        if not status.available:
            raise ProviderError(status.reason)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self._v2_url(path), data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ProviderError(f"Firecrawl HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            reason = exc.reason if isinstance(exc, URLError) else "timeout"
            raise ProviderError(f"Firecrawl request failed: {redact_secrets(reason)}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("Firecrawl returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ProviderError("Firecrawl returned an unexpected response")
        return result

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 100))
        payload = self._post("search", {"query": query, "limit": bounded})
        results = _extract_result_list(payload)[:bounded]
        for item in results:
            item.setdefault("source_provider", self.name)
        return results

    def scrape(self, url: str) -> dict[str, Any]:
        payload = self._post("scrape", {"url": url, "formats": ["markdown"]})
        data = payload.get("data", payload)
        return data if isinstance(data, dict) else {}


def find_anysearch_runtime(explicit: str | None = None) -> Path | None:
    candidates = []
    if explicit or os.environ.get("ANYSEARCH_RUNTIME_CONF"):
        candidates.append(Path(explicit or os.environ["ANYSEARCH_RUNTIME_CONF"]).expanduser())
    candidates.extend(
        [
            Path.home() / ".agents/skills/anysearch/runtime.conf",
            Path.home() / ".codex/skills/anysearch/runtime.conf",
        ]
    )
    return next((path for path in candidates if path.is_file()), None)


def read_anysearch_command(path: Path) -> list[str]:
    command = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.casefold().startswith("command:"):
            command = line.split(":", 1)[1].strip()
            break
    if not command:
        raise ProviderError(f"{path}: Command entry missing")
    parts = shlex.split(command)
    if not parts:
        raise ProviderError(f"{path}: Command entry is empty")
    return parts


class AnySearchProvider:
    name = "anysearch"

    def __init__(self, runtime_conf: str | None = None, timeout: float = 30.0):
        self.runtime_conf = find_anysearch_runtime(runtime_conf)
        self.timeout = timeout

    def status(self) -> ProviderStatus:
        if not self.runtime_conf:
            return ProviderStatus(False, "runtime.conf not found")
        try:
            command = read_anysearch_command(self.runtime_conf)
        except (OSError, ProviderError) as exc:
            return ProviderStatus(False, str(exc))
        executable = command[0]
        if not (shutil.which(executable) or Path(executable).is_file()):
            return ProviderStatus(False, f"runtime executable not found: {executable}")
        for part in command[1:]:
            if part.endswith((".py", ".js", ".sh", ".ps1")) and not Path(part).is_file():
                return ProviderStatus(False, f"runtime script not found: {part}")
        return ProviderStatus(True, f"runtime configured at {self.runtime_conf}")

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        status = self.status()
        if not status.available or not self.runtime_conf:
            raise ProviderError(status.reason)
        bounded = max(1, min(int(limit), 10))
        command = read_anysearch_command(self.runtime_conf) + ["search", query, "--max_results", str(bounded)]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("AnySearch timed out") from exc
        except OSError as exc:
            raise ProviderError(f"AnySearch could not start: {exc}") from exc
        if completed.returncode != 0:
            message = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else f"exit {completed.returncode}"
            message = redact_secrets(message)
            raise ProviderError(f"AnySearch failed: {message[:300]}")
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError("AnySearch returned invalid JSON") from exc
        results = _extract_result_list(payload)[:bounded]
        for item in results:
            item.setdefault("source_provider", self.name)
        return results


class SeedProvider:
    name = "seed"

    def __init__(self, files: list[str]):
        self.files = files

    def status(self) -> ProviderStatus:
        if not self.files:
            return ProviderStatus(False, "no --seed-file supplied")
        missing = [path for path in self.files if not Path(path).expanduser().is_file()]
        return ProviderStatus(False, f"seed file not found: {missing[0]}") if missing else ProviderStatus(True, "seed files readable")

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        del query
        status = self.status()
        if not status.available:
            raise ProviderError(status.reason)
        records: list[dict[str, Any]] = []
        for path in self.files:
            records.extend(load_records(path))
        records = records[: max(1, min(int(limit), 1000))]
        for item in records:
            item.setdefault("source_provider", self.name)
        return records
