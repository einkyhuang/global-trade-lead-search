"""Stable CSV, JSONL, and Markdown exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


CSV_FIELDS = [
    "company_name",
    "website",
    "domain",
    "country",
    "city",
    "buyer_type",
    "product",
    "source_url",
    "source_provider",
    "evidence",
    "verification_url",
    "observed_at",
    "email",
    "contact_name",
    "contact_title",
    "contact_url",
    "contacts_json",
    "confidence_score",
    "verification_status",
    "confidence_band",
    "signal_count",
    "verified_contact_count",
]


def export_all(leads: list[dict[str, Any]], output_dir: str | Path, metadata: dict[str, Any]) -> dict[str, Path]:
    target = Path(output_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    csv_path = target / "leads.csv"
    jsonl_path = target / "leads.jsonl"
    markdown_path = target / "report.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            contacts = lead.get("contacts") or []
            primary = contacts[0] if contacts else {}
            row = {
                field: lead.get(field, "") for field in CSV_FIELDS if field not in {"contact_name", "contact_title", "contact_url", "contacts_json"}
            }
            row.update(
                {
                    "contact_name": primary.get("contact_name", ""),
                    "contact_title": primary.get("contact_title", ""),
                    "contact_url": primary.get("contact_url") or primary.get("source_url", ""),
                    "contacts_json": json.dumps(contacts, ensure_ascii=False, separators=(",", ":")),
                }
            )
            writer.writerow(row)

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for lead in leads:
            handle.write(json.dumps(lead, ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        "# Global Trade Lead Search",
        "",
        f"- Product: {metadata.get('product', '')}",
        f"- Country: {metadata.get('country', '')}",
        f"- Buyer type: {metadata.get('buyer_type', '')}",
        f"- Results: {len(leads)}",
        "- Scope: public research only; no outreach, login, or form submission was performed.",
        "",
    ]
    for index, lead in enumerate(leads, start=1):
        lines.extend(
            [
                f"## {index}. {lead.get('company_name') or '待验证'}",
                "",
                f"- Website: {lead.get('website') or '待验证'}",
                f"- Country: {lead.get('country') or '待验证'}",
                f"- Buyer type: {lead.get('buyer_type') or '待验证'}",
                f"- Source: {lead.get('source_url') or '待验证'}",
                f"- Verification URL: {lead.get('verification_url') or '待验证'}",
                f"- Observed: {lead.get('observed_at') or '待验证'}",
                f"- Provider: {lead.get('source_provider') or '待验证'}",
                f"- Confidence: {lead.get('confidence_score', 0)}/100 ({lead.get('confidence_band', 'low')})",
                f"- Recent signals: {lead.get('signal_count', 0)}",
                f"- Verified key contacts: {lead.get('verified_contact_count', 0)}",
                "",
                lead.get("evidence") or "公开渠道未找到可验证的业务证据。",
                "",
            ]
        )
        contacts = lead.get("contacts") or []
        if contacts:
            lines.extend(["### Key contacts", ""])
            for contact in contacts:
                lines.extend(
                    [
                        f"- {contact.get('contact_name') or '待验证'} — {contact.get('contact_title') or '待验证'}",
                        f"  - Platform: {contact.get('source_provider') or '待验证'}",
                        f"  - Profile: {contact.get('contact_url') or contact.get('source_url') or '待验证'}",
                        f"  - Match: {contact.get('match_method') or '待验证'} ({contact.get('match_status') or 'unmatched'})",
                        f"  - Evidence: {contact.get('evidence') or '待验证'}",
                    ]
                )
        else:
            lines.extend(["- Key contacts: 公开渠道未找到", ""])
        lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return {"csv": csv_path, "jsonl": jsonl_path, "markdown": markdown_path}
