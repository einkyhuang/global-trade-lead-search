"""Auditable lead-confidence scoring."""

from __future__ import annotations

import re
from typing import Any

from .normalize import primary_domain


def _terms(value: Any) -> set[str]:
    return {token for token in re.findall(r"[\w]+", str(value or "").casefold()) if len(token) > 2}


def dimension_scores(lead: dict[str, Any]) -> dict[str, int]:
    """Apply the documented 100-point model conservatively."""
    evidence = str(lead.get("evidence") or "").casefold()
    evidence_terms = _terms(evidence)
    website_domain = primary_domain(lead.get("website"))
    evidence_domain = primary_domain(lead.get("verification_url") or lead.get("source_url"))
    official_evidence = bool(evidence and website_domain and website_domain == evidence_domain)

    identity = (5 if lead.get("company_name") else 0) + (15 if website_domain else 0)
    product_match = bool(_terms(lead.get("product")) & evidence_terms)
    buyer_match = bool(_terms(lead.get("buyer_type")) & evidence_terms)
    country_terms = _terms(lead.get("country"))
    country_match = bool(country_terms and country_terms.issubset(evidence_terms))
    email = str(lead.get("email") or "").casefold().strip()
    public_email = bool(email and email in evidence)
    verified_named_contact = bool(_verified_contacts(lead))

    return {
        "company_identity": identity,
        "product_fit": 30 if product_match and official_evidence else 15 if product_match else 0,
        "customer_type_fit": 20 if buyer_match and official_evidence else 10 if buyer_match else 0,
        "target_market_fit": 10 if country_match else 0,
        "contactability": 10 if (public_email and official_evidence) or verified_named_contact else 0,
        "freshness_activity": min(10, 2 * len(lead.get("signals") or [])),
    }


def score_lead(lead: dict[str, Any]) -> int:
    """Score evidence completeness, never inferred commercial performance."""
    return min(sum(dimension_scores(lead).values()), 100)


def annotate_score(lead: dict[str, Any]) -> dict[str, Any]:
    result = dict(lead)
    verified_contacts = _verified_contacts(result)
    result["verified_contacts"] = verified_contacts
    result["verified_contact_count"] = len(verified_contacts)
    dimensions = dimension_scores(result)
    score = sum(dimensions.values())
    result["dimension_scores"] = dimensions
    result["confidence_score"] = score
    result["confidence_band"] = "high" if score >= 80 else "medium" if score >= 60 else "low"
    result["verification_status"] = "已验证" if score >= 80 else "待验证"
    result["signal_count"] = len(result.get("signals") or [])
    return result


def _verified_contacts(lead: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        contact
        for contact in (lead.get("contacts") or [])
        if isinstance(contact, dict)
        and contact.get("contact_name")
        and contact.get("contact_title")
        and contact.get("source_url")
        and contact.get("evidence")
        and contact.get("match_status") == "verified"
    ]
