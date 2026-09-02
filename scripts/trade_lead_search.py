#!/usr/bin/env python3
"""Search, normalize, score, and export public foreign-trade lead evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from lib.exporters import export_all
from lib.normalize import attach_contacts, attach_signals, deduplicate_leads, load_records, normalize_lead
from lib.providers import AnySearchProvider, FirecrawlProvider, ProviderError, SeedProvider
from lib.scoring import annotate_score


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search public sources for evidence-backed foreign-trade leads.")
    parser.add_argument("--product", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--buyer-type", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output-dir", default="lead-search-output")
    parser.add_argument("--provider", choices=("auto", "firecrawl", "anysearch", "seed", "all"), default="auto")
    parser.add_argument("--seed-file", action="append", default=[], help="JSON/JSONL/Markdown results from Google, an agent, or another tool.")
    parser.add_argument("--signals-file", action="append", default=[], help="Previously generated last30days JSON/JSONL/Markdown evidence.")
    parser.add_argument("--contacts-file", action="append", default=[], help="Public key-contact evidence from LinkedIn/search as JSON, JSONL, or Markdown.")
    parser.add_argument("--scrape", action="store_true", help="With Firecrawl, scrape returned pages for stronger page evidence.")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true", help="Print the bounded plan without network calls or file writes.")
    return parser


def query_for(product: str, country: str, buyer_type: str) -> str:
    return f'{product} {buyer_type} {country} company official website'.strip()


def _select_providers(args: argparse.Namespace) -> list[Any]:
    firecrawl = FirecrawlProvider(timeout=args.timeout)
    anysearch = AnySearchProvider(timeout=args.timeout)
    seed = SeedProvider(args.seed_file)
    if args.provider == "firecrawl":
        return [firecrawl]
    if args.provider == "anysearch":
        return [anysearch]
    if args.provider == "seed":
        return [seed]
    if args.provider == "all":
        return [seed, firecrawl, anysearch]
    if args.seed_file:
        providers: list[Any] = [seed]
        providers.extend(provider for provider in (firecrawl, anysearch) if provider.status().available)
        return providers[:2]
    for provider in (firecrawl, anysearch):
        if provider.status().available:
            return [provider]
    return [seed]


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    if not 1 <= args.limit <= 100:
        raise ValueError("--limit must be between 1 and 100")
    if not 1 <= args.timeout <= 120:
        raise ValueError("--timeout must be between 1 and 120 seconds")
    query = query_for(args.product, args.country, args.buyer_type)
    providers = _select_providers(args)
    if args.dry_run:
        plan = {
            "query": query,
            "limit": args.limit,
            "providers": [{"name": provider.name, "status": provider.status().reason} for provider in providers],
            "contacts_files": list(args.contacts_file),
            "network_calls": False,
            "writes": False,
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return [], [], {"attached_contacts": 0, "unmatched_contacts": 0}

    raw: list[dict[str, Any]] = []
    warnings: list[str] = []
    for provider in providers:
        status = provider.status()
        if not status.available:
            warnings.append(f"{provider.name}: {status.reason}")
            continue
        try:
            results = provider.search(query, args.limit)
            if args.scrape and isinstance(provider, FirecrawlProvider):
                for result in results[: args.limit]:
                    url = result.get("url") or result.get("website")
                    if not url:
                        continue
                    try:
                        page = provider.scrape(str(url))
                    except ProviderError as exc:
                        warnings.append(f"firecrawl scrape {url}: {exc}")
                        continue
                    result.setdefault("evidence", page.get("markdown") or page.get("content") or "")
                    result.setdefault("verification_url", str(url))
            raw.extend(results)
        except ProviderError as exc:
            warnings.append(f"{provider.name}: {exc}")

    defaults = {
        "product": args.product,
        "country": args.country,
        "buyer_type": args.buyer_type,
        "observed_at": date.today().isoformat(),
    }
    leads = deduplicate_leads(normalize_lead(item, defaults) for item in raw)
    signals: list[dict[str, Any]] = []
    for path in args.signals_file:
        try:
            signals.extend(load_records(path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"signals {path}: {exc}")
    attach_signals(leads, signals)
    contacts: list[dict[str, Any]] = []
    for path in args.contacts_file:
        try:
            contacts.extend(load_records(path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"contacts {path}: {exc}")
    attached_contacts, unmatched_contacts = attach_contacts(leads, contacts, defaults["observed_at"])
    if unmatched_contacts:
        warnings.append(f"contacts: {len(unmatched_contacts)} unmatched records not attached")
    scored = sorted((annotate_score(lead) for lead in leads), key=lambda item: (-item["confidence_score"], item["company_name"].casefold()))
    return scored[: args.limit], warnings, {"attached_contacts": attached_contacts, "unmatched_contacts": len(unmatched_contacts)}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        leads, warnings, contact_summary = run(args)
    except ValueError as exc:
        parser.error(str(exc))
    if args.dry_run:
        return 0
    paths = export_all(
        leads,
        args.output_dir,
        {"product": args.product, "country": args.country, "buyer_type": args.buyer_type},
    )
    summary = {
        "results": len(leads),
        "leads_with_verified_contacts": sum(bool(lead.get("verified_contact_count")) for lead in leads),
        **contact_summary,
        "outputs": {key: str(path.resolve()) for key, path in paths.items()},
        "warnings": warnings,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if leads or not warnings else 2


if __name__ == "__main__":
    sys.exit(main())
