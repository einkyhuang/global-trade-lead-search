"""Bounded, auditable source-catalog discovery for Dragon Guide.

The crawler intentionally follows only a small allow-list of public directory
pages on dragon-guide.net.  External links are recorded as sources; they are
never crawled for content by this module.
"""

from __future__ import annotations

import html
import json
import re
import socket
from collections import deque
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener
from urllib.robotparser import RobotFileParser


DRAGON_HOSTS = {"dragon-guide.net", "www.dragon-guide.net"}
DEFAULT_SEEDS = (
    "https://www.dragon-guide.net/",
    "https://www.dragon-guide.net/wuzhousjie.htm",
    "https://www.dragon-guide.net/index5.htm",
    "https://www.dragon-guide.net/hangye/Customs.htm",
)
DEFAULT_USER_AGENT = "global-trade-lead-search/0.1 (+public source catalog)"

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
}

CONTINENT_ALIASES = {
    "asia": "Asia",
    "yazhou": "Asia",
    "europe": "Europe",
    "ouzhou": "Europe",
    "americas": "Americas",
    "america": "Americas",
    "meizhou": "Americas",
    "ocean": "Oceania",
    "oceania": "Oceania",
    "dayangzhou": "Oceania",
    "africa": "Africa",
    "feizhou": "Africa",
}

COUNTRY_ALIASES = {
    "america": "United States",
    "england": "United Kingdom",
    "german": "Germany",
    "south africa": "South Africa",
    "united arab emirates": "United Arab Emirates",
}

EXCLUDED_SOURCE_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "youtube.com",
}

MEDIA_LABEL_PATTERNS = (
    "news",
    "newspaper",
    "media",
    "television",
    "radio",
    "新闻",
    "媒体",
    "报纸",
    "日报",
    "电视",
    "广播",
)

NON_SOURCE_SECTION_PATTERNS = (
    "bank securities",
    "bank website",
    "news and information",
    "news website",
    "information website",
    "business etiquette",
    "tourism website",
    "email service",
    "foreign trade forum",
    "forum",
    "social platform",
    "银行证券",
    "论坛",
    "社交平台",
    "新闻资讯",
    "新闻信息",
    "新闻网站",
    "国家概况",
    "商务礼仪",
    "外贸邮箱",
    "外贸论坛",
    "外贸工具",
    "外语学习",
    "国际新闻",
)

SECTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "search_engine",
        (
            "search engine",
            "searchengine",
            "search catalog",
            "搜索引擎",
        ),
    ),
    (
        "b2b_marketplace",
        (
            "b2b website",
            "b2b websites",
            "b2b directory",
            "b2b网站",
            "b2b 网站",
        ),
    ),
    (
        "yellow_pages",
        (
            "yellow page",
            "yellowpage",
            "yellowpages",
            "business directory",
            "黄页",
            "商业名录",
            "购物网站",
        ),
    ),
    (
        "chamber_association",
        (
            "chamber",
            "association",
            "商会",
            "协会",
        ),
    ),
    (
        "customs_trade",
        (
            "customs",
            "custom clearance",
            "import export",
            "foreign trade related",
            "trade database",
            "trade statistics",
            "海关",
            "进出口",
            "外贸信息",
            "贸易数据",
        ),
    ),
    (
        "government_trade",
        (
            "official government",
            "official foreign trade",
            "commercial counsellor",
            "economic and commercial",
            "government site",
            "政府网站",
            "官方对外经贸",
            "经济商务参赞",
            "驻外使馆",
        ),
    ),
    (
        "chamber_association",
        (
            "civil foreign trade related",
            "民间对外经贸",
        ),
    ),
    (
        "trade_directory",
        (
            "trade guide",
            "trade site",
            "trade website",
            "trade information",
            "外贸网站",
            "外贸信息网站",
        ),
    ),
)


@dataclass(frozen=True)
class Link:
    url: str
    text: str
    section_type: str | None


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int | None
    body: bytes | None
    content_type: str | None
    error: str | None = None
    blocked_by_robots: bool = False


class LinkExtractor(HTMLParser):
    """Extract links while retaining the most recent directory section."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[Link] = []
        self.page_language: str | None = None
        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self._heading_parts: list[str] | None = None
        self._section_type: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        if tag.lower() == "html" and values.get("lang"):
            self.page_language = values["lang"].split("-", 1)[0].lower()
        if tag.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_parts = []
        if tag.lower() == "a" and values.get("href"):
            self._href = html.unescape(values["href"].strip())
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if not clean:
            return
        if self._heading_parts is not None:
            self._heading_parts.append(clean)
            return
        if self._href is not None:
            self._anchor_parts.append(clean)
            return
        return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading_parts is not None:
            heading = " ".join(self._heading_parts).strip()
            self._heading_parts = None
            if not heading:
                return
            if any(pattern in heading.lower() for pattern in NON_SOURCE_SECTION_PATTERNS):
                self._section_type = None
                return
            detected = classify_source_type(heading)
            if detected:
                self._section_type = detected
            return
        if tag != "a" or self._href is None:
            return
        self._append_link()

    def _append_link(self) -> None:
        if self._href is None:
            return
        self.links.append(
            Link(
                url=self._href,
                text=" ".join(self._anchor_parts).strip(),
                section_type=self._section_type,
            )
        )
        self._href = None
        self._anchor_parts = []


def classify_source_type(text: str) -> str | None:
    value = unquote(text).lower().replace("_", "-")
    for source_type, patterns in SECTION_PATTERNS:
        if any(pattern in value for pattern in patterns):
            return source_type
    return None


def canonical_domain(url: str) -> str:
    """Return a stable registrable-ish host key without using a PSL package."""

    try:
        host = (urlsplit(url).hostname or "").rstrip(".").lower()
        host = host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def normalize_url(raw_url: str, base_url: str | None = None) -> str | None:
    """Normalize an HTTP(S) URL and remove common tracking parameters."""

    raw_url = html.unescape(raw_url.strip())
    if not raw_url or raw_url.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
        return None
    absolute = urljoin(base_url, raw_url) if base_url else raw_url
    try:
        parts = urlsplit(absolute)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return None
        host = parts.hostname.rstrip(".").lower().encode("idna").decode("ascii")
        if parts.username or parts.password:
            return None
        port = parts.port
    except (UnicodeError, ValueError):
        return None
    if host.startswith("www."):
        host = host[4:]
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = quote(unquote(parts.path or "/"), safe="/%:@!$&'()*+,;=-._~")
    path = re.sub(r"/{2,}", "/", path)
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    query.sort()
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query, doseq=True), ""))


def is_dragon_url(url: str) -> bool:
    return canonical_domain(url) == "dragon-guide.net"


def is_allowed_directory_page(url: str, *, is_seed: bool = False) -> bool:
    """Allow only known public country and trade-directory HTML paths."""

    normalized = normalize_url(url)
    if not normalized or not is_dragon_url(normalized):
        return False
    path = unquote(urlsplit(normalized).path).lower()
    if is_seed and path in {"/", "/index5.htm", "/wuzhousjie.htm", "/hangye/customs.htm"}:
        return True
    if not path.endswith((".htm", ".html")):
        return False
    if path.startswith(("/guobie/", "/guobie-en/")):
        return True
    if path.startswith(("/hangye/", "/hangye-en/")):
        tokens = (
            "b2b",
            "yellow",
            "search",
            "custom",
            "zuihaowaimao",
            "quanqiujinchukou",
            "canzanzhu",
            "trade",
        )
        return any(token in path for token in tokens)
    return False


def infer_location(origin_page: str) -> tuple[str | None, str | None]:
    path = unquote(urlsplit(origin_page).path).strip("/")
    parts = path.split("/") if path else []
    continent = None
    country = None
    for part in parts:
        key = Path(part).stem.lower()
        continent_key = key.split("-", 1)[0].split("_", 1)[0]
        if continent_key in CONTINENT_ALIASES:
            continent = CONTINENT_ALIASES[continent_key]
    if len(parts) >= 3 and parts[0].lower() in {"guobie", "guobie-en"}:
        stem = Path(parts[-1]).stem
        raw_country = stem.replace("%20", " ").replace("-", " ").strip()
        country = COUNTRY_ALIASES.get(raw_country.lower(), raw_country) or None
    return continent, country


def infer_language(origin_page: str, page_language: str | None = None) -> list[str]:
    path = urlsplit(origin_page).path.lower()
    if "/guobie-en/" in path or "/hangye-en/" in path:
        return ["en"]
    if path == "/" or path.startswith(("/guobie/", "/hangye/")):
        return ["zh"]
    return [page_language] if page_language else ["zh"]


def trust_level(source_type: str) -> str:
    return {
        "government_trade": "official",
        "customs_trade": "authoritative",
        "chamber_association": "industry",
        "yellow_pages": "directory",
        "b2b_marketplace": "platform",
        "search_engine": "discovery",
        "trade_directory": "directory",
    }.get(source_type, "unclassified")


def _domain_matches(domain: str, candidate: str) -> bool:
    return domain == candidate or domain.endswith(f".{candidate}")


def _is_known_search_engine(domain: str) -> bool:
    providers = (
        "google.",
        "yahoo.",
        "bing.com",
        "yandex.",
        "baidu.com",
        "ask.com",
        "aol.com",
        "duckduckgo.com",
    )
    return any(provider in domain for provider in providers)


def is_non_directory_source(link: Link, source_type: str) -> bool:
    """Reject social/footer and obvious media leakage from legacy pages."""

    domain = canonical_domain(link.url)
    if any(_domain_matches(domain, excluded) for excluded in EXCLUDED_SOURCE_DOMAINS):
        return True
    text = f"{link.text} {domain} {unquote(urlsplit(link.url).path)}".lower()
    if any(pattern in text for pattern in MEDIA_LABEL_PATTERNS):
        return not (source_type == "search_engine" and _is_known_search_engine(domain))
    return False


def extract_links(document: str, base_url: str) -> tuple[list[Link], str | None]:
    parser = LinkExtractor()
    parser.feed(document)
    links: list[Link] = []
    for link in parser.links:
        normalized = normalize_url(link.url, base_url)
        if normalized:
            links.append(Link(normalized, link.text, link.section_type))
    return links, parser.page_language


def decode_html(body: bytes, content_type: str | None) -> str:
    encodings: list[str] = []
    if content_type:
        match = re.search(r"charset\s*=\s*([\w-]+)", content_type, flags=re.I)
        if match:
            encodings.append(match.group(1))
    head = body[:4096].decode("ascii", errors="ignore")
    match = re.search(r"charset\s*=\s*[\"']?([\w-]+)", head, flags=re.I)
    if match:
        encodings.append(match.group(1))
    encodings.extend(("utf-8", "gb18030", "latin-1"))
    for encoding in dict.fromkeys(encodings):
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


class PublicFetcher:
    """HTTP fetcher with robots enforcement and bounded response sizes."""

    def __init__(self, timeout: float = 12.0, user_agent: str = DEFAULT_USER_AGENT, max_bytes: int = 2_000_000):
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_bytes = max_bytes
        self.opener = build_opener()
        self._robots: dict[str, RobotFileParser] = {}

    def _robot_parser(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(origin)
        if cached:
            return cached
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser(robots_url)
        request = Request(robots_url, headers={"User-Agent": self.user_agent})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(512_000)
            parser.parse(raw.decode("utf-8", errors="replace").splitlines())
        except HTTPError as error:
            if error.code in {401, 403}:
                parser.disallow_all = True
            else:
                parser.allow_all = True
        except (URLError, TimeoutError, socket.timeout, OSError):
            # A missing/unreachable robots file does not imply permission to
            # expand beyond our hard-coded public-directory allow-list.
            parser.allow_all = True
        self._robots[origin] = parser
        return parser

    def fetch(self, url: str) -> FetchResult:
        parser = self._robot_parser(url)
        if not parser.can_fetch(self.user_agent, url):
            return FetchResult(url, None, None, None, "blocked by robots.txt", True)
        request = Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = getattr(response, "status", response.getcode())
                content_type = response.headers.get("Content-Type")
                body = response.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                return FetchResult(url, status, None, content_type, "response exceeds size limit")
            if "html" not in (content_type or "").lower():
                return FetchResult(url, status, None, content_type, "non-HTML response")
            return FetchResult(url, status, body, content_type)
        except HTTPError as error:
            return FetchResult(url, error.code, None, error.headers.get("Content-Type"), f"HTTP {error.code}")
        except (URLError, TimeoutError, socket.timeout, OSError) as error:
            return FetchResult(url, None, None, None, f"{type(error).__name__}: {error}")


FetchCallable = Callable[[str], FetchResult]


def _candidate_entry(link: Link, origin_page: str, page_language: str | None, checked_at: str) -> dict[str, object] | None:
    source_type = link.section_type or classify_source_type(f"{origin_page} {link.text}")
    if not source_type:
        return None
    domain = canonical_domain(link.url)
    if not domain or domain == "dragon-guide.net" or is_non_directory_source(link, source_type):
        return None
    continent, country = infer_location(origin_page)
    return {
        "name": link.text or domain,
        "url": link.url,
        "canonical_domain": domain,
        "source_type": source_type,
        "continent": continent,
        "country": country,
        "language": infer_language(origin_page, page_language),
        "origin": "dragon-guide",
        "origin_page": origin_page,
        "health_status": "discovered",
        "http_status": None,
        "last_checked_at": checked_at,
        "trust_level": trust_level(source_type),
    }


def _preference(entry: Mapping[str, object]) -> tuple[int, int, str, str]:
    trust_rank = {
        "official": 6,
        "authoritative": 5,
        "industry": 4,
        "platform": 3,
        "directory": 2,
        "discovery": 1,
    }
    return (
        trust_rank.get(str(entry.get("trust_level")), 0),
        int(str(entry.get("url", "")).startswith("https://")),
        str(entry.get("origin_page", "")),
        str(entry.get("url", "")),
    )


def deduplicate_entries(entries: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Keep one stable, highest-value record per normalized domain."""

    chosen: dict[str, dict[str, object]] = {}
    for raw in entries:
        entry = dict(raw)
        domain = str(entry.get("canonical_domain") or canonical_domain(str(entry.get("url", ""))))
        if not domain:
            continue
        entry["canonical_domain"] = domain
        current = chosen.get(domain)
        if current is None or _preference(entry) > _preference(current):
            chosen[domain] = entry
    return sorted(
        chosen.values(),
        key=lambda item: (
            str(item.get("continent") or ""),
            str(item.get("country") or ""),
            str(item.get("source_type") or ""),
            str(item.get("canonical_domain") or ""),
        ),
    )


def load_registry(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {error}") from error
    return records


def merge_failed_origins(
    discovered: Sequence[Mapping[str, object]],
    previous: Sequence[Mapping[str, object]],
    failures: Mapping[str, FetchResult],
    checked_at: str,
) -> list[dict[str, object]]:
    """Retain last-known sources if an origin page cannot be refreshed."""

    merged = [dict(entry) for entry in discovered]
    discovered_domains = {str(entry.get("canonical_domain")) for entry in merged}
    for raw in previous:
        origin_page = str(raw.get("origin_page", ""))
        failure = failures.get(origin_page)
        domain = str(raw.get("canonical_domain", ""))
        if not failure or not domain or domain in discovered_domains:
            continue
        entry = dict(raw)
        entry["health_status"] = "origin_blocked" if failure.blocked_by_robots else "origin_unavailable"
        entry["http_status"] = failure.status
        entry["last_checked_at"] = checked_at
        merged.append(entry)
    return deduplicate_entries(merged)


def crawl_catalog(
    fetch: FetchCallable,
    *,
    seeds: Sequence[str] = DEFAULT_SEEDS,
    max_pages: int = 40,
    max_depth: int = 2,
    checked_at: str | None = None,
    previous: Sequence[Mapping[str, object]] = (),
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Crawl permitted Dragon Guide pages and return catalog plus audit state."""

    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if max_depth < 0:
        raise ValueError("max_depth cannot be negative")
    checked_at = checked_at or date.today().isoformat()
    queue: deque[tuple[str, int]] = deque()
    seed_set: set[str] = set()
    for seed in seeds:
        normalized = normalize_url(seed)
        if normalized and is_allowed_directory_page(normalized, is_seed=True):
            queue.append((normalized, 0))
            seed_set.add(normalized)
    seen: set[str] = set()
    entries: list[dict[str, object]] = []
    page_results: list[dict[str, object]] = []
    failures: dict[str, FetchResult] = {}

    while queue and len(seen) < max_pages:
        page_url, depth = queue.popleft()
        if page_url in seen:
            continue
        seen.add(page_url)
        result = fetch(page_url)
        page_results.append(
            {
                "url": page_url,
                "depth": depth,
                "http_status": result.status,
                "status": (
                    "blocked_by_robots"
                    if result.blocked_by_robots
                    else "ok"
                    if result.body is not None and result.status and 200 <= result.status < 300
                    else "failed"
                ),
                "error": result.error,
            }
        )
        if result.body is None or not result.status or not 200 <= result.status < 300:
            failures[page_url] = result
            continue
        document = decode_html(result.body, result.content_type)
        if re.search(r"\b(captcha|access denied|sign in to continue)\b|验证码|请登录", document, re.I):
            blocked = FetchResult(page_url, result.status, None, result.content_type, "login or captcha gate detected")
            failures[page_url] = blocked
            page_results[-1]["status"] = "access_gate"
            page_results[-1]["error"] = blocked.error
            continue
        links, page_language = extract_links(document, page_url)
        for link in links:
            if is_dragon_url(link.url):
                if depth < max_depth and is_allowed_directory_page(link.url, is_seed=link.url in seed_set):
                    queue.append((link.url, depth + 1))
                continue
            candidate = _candidate_entry(link, page_url, page_language, checked_at)
            if candidate:
                entries.append(candidate)

    catalog = merge_failed_origins(deduplicate_entries(entries), previous, failures, checked_at)
    health: dict[str, object] = {
        "generated_at": checked_at,
        "origin": "dragon-guide",
        "pages_attempted": len(seen),
        "pages_succeeded": sum(item["status"] == "ok" for item in page_results),
        "pages_failed": sum(item["status"] != "ok" for item in page_results),
        "sources_discovered": len(catalog),
        "max_pages": max_pages,
        "max_depth": max_depth,
        "pages": sorted(page_results, key=lambda item: str(item["url"])),
    }
    return catalog, health


def write_jsonl(path: Path, entries: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(dict(entry), ensure_ascii=False, sort_keys=True) + "\n" for entry in entries)
    path.write_text(payload, encoding="utf-8")


def write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_jsonl(path: Path) -> Iterator[dict[str, object]]:
    yield from load_registry(path)
