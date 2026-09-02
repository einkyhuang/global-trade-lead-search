"""Normalization and evidence import helpers for the lead-search pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


COMPANY_SUFFIXES = {
    "co",
    "company",
    "corp",
    "corporation",
    "gmbh",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
    "plc",
    "pte",
    "sa",
    "sarl",
    "spa",
}

MULTIPART_PUBLIC_SUFFIXES = {
    "co.jp",
    "co.kr",
    "co.nz",
    "co.uk",
    "com.au",
    "com.br",
    "com.cn",
    "com.hk",
    "com.mx",
    "com.sg",
    "com.tr",
    "com.tw",
}

URL_RE = re.compile(r"https?://[^\s)>\]}]+", re.IGNORECASE)


def normalize_company_name(value: Any) -> str:
    """Return a stable comparison form without inventing a display name."""
    text = str(value or "").casefold().strip()
    tokens = re.findall(r"[\w]+", text, flags=re.UNICODE)
    while tokens and tokens[-1] in COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    if parsed.scheme.casefold() not in {"http", "https"} or parsed.username or parsed.password:
        return ""
    host = (parsed.hostname or "").casefold().rstrip(".")
    if not host:
        return ""
    try:
        port_number = parsed.port
    except ValueError:
        return ""
    port = f":{port_number}" if port_number else ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.casefold() or 'https'}://{host}{port}{path}"


def primary_domain(value: Any) -> str:
    """Return a practical registrable-domain key using a small stdlib-only PSL subset."""
    normalized = normalize_url(value)
    if not normalized:
        return ""
    host = (urlparse(normalized).hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host) or ":" in host:
        return host
    labels = [part for part in host.split(".") if part]
    if len(labels) <= 2:
        return host
    suffix2 = ".".join(labels[-2:])
    return ".".join(labels[-3:]) if suffix2 in MULTIPART_PUBLIC_SUFFIXES else suffix2


def _first(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = mapping.get(name)
        if value not in (None, "", []):
            return value
    return ""


def normalize_lead(raw: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults = defaults or {}
    website = normalize_url(_first(raw, "website", "company_url", "official_website"))
    source_url = normalize_url(_first(raw, "source_url", "url", "link"))
    company_name = str(_first(raw, "company_name", "company", "name", "title") or "").strip()
    evidence = _first(raw, "evidence", "description", "snippet", "markdown", "content")
    if isinstance(evidence, list):
        evidence = "; ".join(str(item) for item in evidence if item)

    return {
        "company_name": company_name,
        "website": website,
        "domain": primary_domain(website or source_url),
        "country": str(_first(raw, "country") or defaults.get("country", "")).strip(),
        "city": str(_first(raw, "city") or "").strip(),
        "buyer_type": str(_first(raw, "buyer_type", "customer_type") or defaults.get("buyer_type", "")).strip(),
        "product": str(_first(raw, "product") or defaults.get("product", "")).strip(),
        "source_url": source_url,
        "source_title": str(_first(raw, "source_title", "title") or "").strip(),
        "source_provider": str(_first(raw, "source_provider", "provider") or defaults.get("source_provider", "seed")).strip(),
        "evidence": str(evidence or "").strip(),
        "verification_url": normalize_url(_first(raw, "verification_url")),
        "observed_at": str(_first(raw, "observed_at", "observed_date") or defaults.get("observed_at", "")).strip(),
        "email": str(_first(raw, "email") or "").strip(),
        "contact_name": str(_first(raw, "contact_name") or "").strip(),
        "contact_title": str(_first(raw, "contact_title") or "").strip(),
        "signals": list(raw.get("signals") or []),
    }


def normalize_contact(raw: dict[str, Any], observed_at: str = "") -> dict[str, Any]:
    """Normalize a public key-contact artifact without inferring missing facts."""
    company_domain = primary_domain(_first(raw, "company_domain", "company_website", "company_url"))
    return {
        "contact_name": str(_first(raw, "contact_name", "person_name", "name") or "").strip(),
        "contact_title": str(_first(raw, "contact_title", "job_title", "role", "title") or "").strip(),
        "company_name": str(_first(raw, "company_name", "company", "employer") or "").strip(),
        "company_domain": company_domain,
        "linkedin_company_url": normalize_url(_first(raw, "linkedin_company_url", "linkedin_company")),
        "contact_url": normalize_url(_first(raw, "contact_url", "linkedin_url", "profile_url")),
        "source_url": normalize_url(_first(raw, "source_url", "url", "link")),
        "source_provider": str(_first(raw, "source_provider", "provider", "platform") or "").strip(),
        "evidence": str(_first(raw, "evidence", "description", "snippet", "markdown", "content") or "").strip(),
        "observed_at": str(_first(raw, "observed_at", "observed_date") or observed_at or "").strip(),
        "match_method": "",
        "match_status": "unmatched",
    }


def contact_matches_lead(contact: dict[str, Any], lead: dict[str, Any]) -> tuple[bool, str]:
    """Return whether an already normalized contact passes a company identity gate."""
    lead_domain = str(lead.get("domain") or primary_domain(lead.get("website")) or "")
    contact_domain = str(contact.get("company_domain") or "")
    if lead_domain and contact_domain and contact_domain == lead_domain:
        return True, "domain"

    linkedin_company = normalize_url(contact.get("linkedin_company_url"))
    same_company = bool(
        contact.get("company_name")
        and normalize_company_name(contact.get("company_name")) == normalize_company_name(lead.get("company_name"))
    )
    if same_company and linkedin_company and primary_domain(linkedin_company) == "linkedin.com":
        return True, "linkedin_company"

    source_domain = primary_domain(contact.get("source_url"))
    if same_company and lead_domain and source_domain == lead_domain:
        return True, "official_source"
    return False, ""


def _verified_contact_fields(contact: dict[str, Any]) -> bool:
    return bool(
        contact.get("contact_name")
        and contact.get("contact_title")
        and contact.get("source_url")
        and contact.get("evidence")
    )


def attach_contacts(
    leads: list[dict[str, Any]],
    contacts: Iterable[dict[str, Any]],
    observed_at: str = "",
) -> tuple[int, list[dict[str, Any]]]:
    """Attach complete contacts only after an explicit company match and deduplicate evidence."""
    for lead in leads:
        lead["contacts"] = []

    attached = 0
    unmatched: list[dict[str, Any]] = []
    seen: dict[int, set[tuple[str, str, str]]] = {id(lead): set() for lead in leads}
    for raw in contacts:
        contact = normalize_contact(raw, observed_at)
        matched = False
        for lead in leads:
            passes_gate, method = contact_matches_lead(contact, lead)
            if not passes_gate or not _verified_contact_fields(contact):
                continue
            key = (
                str(contact.get("contact_name") or "").casefold().strip(),
                str(contact.get("contact_title") or "").casefold().strip(),
                str(contact.get("contact_url") or contact.get("source_url") or "").casefold().strip(),
            )
            if key in seen[id(lead)]:
                matched = True
                continue
            attached_contact = dict(contact)
            attached_contact["match_method"] = method
            attached_contact["match_status"] = "verified"
            lead["contacts"].append(attached_contact)
            seen[id(lead)].add(key)
            attached += 1
            matched = True
        if not matched:
            unmatched.append(contact)
    return attached, unmatched


def deduplicate_leads(leads: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by normalized company plus primary domain and retain all evidence."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for lead in leads:
        company_key = normalize_company_name(lead.get("company_name"))
        domain_key = primary_domain(lead.get("domain") or lead.get("website") or lead.get("source_url"))
        key = (company_key, domain_key)
        if not company_key and not domain_key:
            continue
        if key not in merged:
            current = dict(lead)
            current["domain"] = domain_key
            current["evidence_sources"] = []
            merged[key] = current
        current = merged[key]
        for field, value in lead.items():
            if field in {"signals", "evidence_sources"}:
                continue
            if not current.get(field) and value:
                current[field] = value
        source = {
            "url": lead.get("source_url", ""),
            "title": lead.get("source_title", ""),
            "provider": lead.get("source_provider", ""),
            "evidence": lead.get("evidence", ""),
        }
        if any(source.values()) and source not in current["evidence_sources"]:
            current["evidence_sources"].append(source)
        for signal in lead.get("signals") or []:
            if signal not in current.setdefault("signals", []):
                current["signals"].append(signal)
    return list(merged.values())


def _records_from_json(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("results", "leads", "data", "signals"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
        return [value]
    return []


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Read JSON, JSONL, or Markdown evidence without executing foreign code."""
    source = Path(path).expanduser()
    text = source.read_text(encoding="utf-8")
    suffix = source.suffix.casefold()
    if suffix == ".json":
        return _records_from_json(json.loads(text))
    if suffix in {".jsonl", ".ndjson"}:
        records = []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{source}:{number}: expected a JSON object")
            records.append(value)
        return records
    if suffix in {".md", ".markdown"}:
        records = []
        sections = re.split(r"(?m)^#{1,6}\s+", text)
        for section in sections:
            content = section.strip()
            if not content:
                continue
            lines = content.splitlines()
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip() or title
            url = (URL_RE.search(content).group(0).rstrip(".,;") if URL_RE.search(content) else "")
            records.append({"title": title, "evidence": body, "source_url": url})
        return records
    raise ValueError(f"unsupported evidence format: {source.suffix or '(none)'}")


def attach_signals(leads: list[dict[str, Any]], signals: Iterable[dict[str, Any]]) -> None:
    """Attach a signal only when its explicit company or domain matches a lead."""
    for signal in signals:
        signal_domain = primary_domain(_first(signal, "domain", "website", "url", "source_url"))
        signal_company = normalize_company_name(_first(signal, "company_name", "company", "name", "title"))
        for lead in leads:
            same_domain = bool(signal_domain and signal_domain == lead.get("domain"))
            same_company = bool(signal_company and signal_company == normalize_company_name(lead.get("company_name")))
            if same_domain or same_company:
                lead.setdefault("signals", []).append(signal)
