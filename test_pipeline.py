from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.exporters import export_all  # noqa: E402
from lib.normalize import (  # noqa: E402
    attach_contacts,
    attach_signals,
    deduplicate_leads,
    load_records,
    normalize_lead,
    primary_domain,
)
from lib.providers import FirecrawlProvider, ProviderError, redact_secrets  # noqa: E402
from lib.scoring import annotate_score, dimension_scores, score_lead  # noqa: E402
from trade_lead_search import _select_providers, build_parser, run  # noqa: E402
from check_upstreams import (  # noqa: E402
    UpstreamError,
    check_project,
    compare_versions,
    fetch_latest_release,
    read_skill_version,
)


class PipelineTests(unittest.TestCase):
    def test_primary_domain_and_company_domain_dedup(self):
        raw = [
            {"company_name": "Acme GmbH", "website": "https://www.acme.co.uk/about", "source_url": "https://directory.test/acme", "evidence": "Distributor"},
            {"company": "ACME", "url": "https://shop.acme.co.uk", "snippet": "Ice machine wholesaler"},
        ]
        leads = deduplicate_leads(normalize_lead(item) for item in raw)
        self.assertEqual(primary_domain(raw[0]["website"]), "acme.co.uk")
        self.assertEqual(len(leads), 1)
        self.assertEqual(len(leads[0]["evidence_sources"]), 2)
        self.assertEqual(primary_domain("https://user:secret@example.com"), "")

    def test_score_is_evidence_based_and_bounded(self):
        lead = normalize_lead(
            {
                "company_name": "Acme",
                "website": "https://acme.example",
                "source_url": "https://acme.example/products",
                "verification_url": "https://acme.example/products",
                "evidence": "Acme is a Germany distributor of ice machines.",
                "country": "Germany",
                "buyer_type": "Distributor",
                "product": "Ice machines",
                "signals": [{"evidence": "Trade fair announcement"}] * 20,
            }
        )
        self.assertEqual(score_lead(lead), 90)
        self.assertEqual(annotate_score(lead)["verification_status"], "已验证")

    def test_scoring_does_not_reward_unverified_defaults_or_email(self):
        lead = normalize_lead(
            {
                "company_name": "Acme",
                "website": "https://acme.example",
                "source_url": "https://directory.example/acme",
                "evidence": "A directory candidate with no geographic proof.",
                "email": "info@acme.example",
            },
            {"country": "Germany", "product": "Ice machines", "buyer_type": "Distributor"},
        )
        dimensions = dimension_scores(lead)
        self.assertEqual(dimensions["target_market_fit"], 0)
        self.assertEqual(dimensions["contactability"], 0)

        official_without_published_email = dict(lead)
        official_without_published_email["source_url"] = "https://acme.example/about"
        official_without_published_email["verification_url"] = "https://acme.example/about"
        self.assertEqual(dimension_scores(official_without_published_email)["contactability"], 0)
        official_without_published_email["evidence"] += " Public email: info@acme.example."
        self.assertEqual(dimension_scores(official_without_published_email)["contactability"], 10)

    def test_signals_jsonl_and_markdown_import(self):
        with tempfile.TemporaryDirectory() as directory:
            jsonl = Path(directory) / "signals.jsonl"
            jsonl.write_text(json.dumps({"company_name": "Acme", "evidence": "New catalog"}) + "\n", encoding="utf-8")
            markdown = Path(directory) / "signals.md"
            markdown.write_text("# Acme\nRecent fair: https://acme.example/news\n", encoding="utf-8")
            signals = load_records(jsonl) + load_records(markdown)
            leads = [normalize_lead({"company_name": "Acme", "website": "https://acme.example"})]
            attach_signals(leads, signals)
            self.assertEqual(len(leads[0]["signals"]), 2)

    def test_contact_domain_match_attaches_and_deduplicates(self):
        leads = [normalize_lead({"company_name": "Acme GmbH", "website": "https://acme.example"})]
        raw = {
            "contact_name": "Jane Doe",
            "contact_title": "Purchasing Manager",
            "company_domain": "acme.example",
            "contact_url": "https://www.linkedin.com/in/jane-doe",
            "source_url": "https://www.linkedin.com/in/jane-doe",
            "source_provider": "linkedin",
            "evidence": "Jane Doe — Purchasing Manager at Acme GmbH",
        }
        attached, unmatched = attach_contacts(leads, [raw, raw], "2026-08-31")
        self.assertEqual(attached, 1)
        self.assertEqual(unmatched, [])
        self.assertEqual(len(leads[0]["contacts"]), 1)
        self.assertEqual(leads[0]["contacts"][0]["match_method"], "domain")
        self.assertEqual(leads[0]["contacts"][0]["match_status"], "verified")

    def test_similar_company_name_does_not_attach_contact(self):
        leads = [normalize_lead({"company_name": "Acme GmbH", "website": "https://acme.example"})]
        raw = {
            "contact_name": "Jane Doe",
            "contact_title": "Purchasing Manager",
            "company_name": "Acme Trading GmbH",
            "source_url": "https://www.linkedin.com/in/jane-doe",
            "evidence": "Jane Doe — Purchasing Manager at Acme Trading GmbH",
        }
        attached, unmatched = attach_contacts(leads, [raw])
        self.assertEqual((attached, leads[0]["contacts"]), (0, []))
        self.assertEqual(len(unmatched), 1)

    def test_incomplete_markdown_contact_stays_out(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "contact.md"
            artifact.write_text(
                "# Jane Doe — Purchasing Manager\nhttps://www.linkedin.com/in/jane-doe\n",
                encoding="utf-8",
            )
            leads = [normalize_lead({"company_name": "Acme GmbH", "website": "https://acme.example"})]
            attached, unmatched = attach_contacts(leads, load_records(artifact), "2026-08-31")
        self.assertEqual((attached, leads[0]["contacts"]), (0, []))
        self.assertEqual(len(unmatched), 1)

    def test_verified_contact_scoring_requires_complete_evidence_and_is_not_double_counted(self):
        lead = normalize_lead(
            {
                "company_name": "Acme",
                "website": "https://acme.example",
                "source_url": "https://acme.example/about",
                "verification_url": "https://acme.example/about",
                "evidence": "Acme is a Germany distributor of ice machines. Public email: info@acme.example.",
                "country": "Germany",
                "buyer_type": "Distributor",
                "product": "Ice machines",
                "email": "info@acme.example",
            }
        )
        self.assertEqual(dimension_scores(lead)["contactability"], 10)
        contact = {
            "contact_name": "Jane Doe",
            "contact_title": "Purchasing Manager",
            "source_url": "https://www.linkedin.com/in/jane-doe",
            "evidence": "Jane Doe — Purchasing Manager at Acme",
            "match_status": "verified",
        }
        lead["contacts"] = [contact]
        lead = annotate_score(lead)
        self.assertEqual(lead["verified_contact_count"], 1)
        self.assertEqual(dimension_scores(lead)["contactability"], 10)
        for field in ("contact_name", "contact_title", "source_url", "match_status"):
            incomplete = dict(contact)
            incomplete[field] = ""
            lead["contacts"] = [incomplete]
            self.assertEqual(dimension_scores(lead)["contactability"], 10)
        lead["contacts"] = []
        self.assertEqual(dimension_scores(lead)["contactability"], 10)

    def test_export_csv_jsonl_markdown(self):
        lead = annotate_score(normalize_lead({"company_name": "Acme", "website": "https://acme.example"}))
        with tempfile.TemporaryDirectory() as directory:
            paths = export_all([lead], directory, {"product": "Ice machines", "country": "Germany", "buyer_type": "Distributor"})
            self.assertEqual(set(paths), {"csv", "jsonl", "markdown"})
            with paths["csv"].open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["company_name"], "Acme")
            self.assertEqual(json.loads(paths["jsonl"].read_text(encoding="utf-8"))["domain"], "acme.example")
            self.assertIn("public research only", paths["markdown"].read_text(encoding="utf-8"))

    def test_contact_export_and_missing_contact_label(self):
        lead = normalize_lead({"company_name": "Acme", "website": "https://acme.example"})
        attach_contacts(
            [lead],
            [
                {
                    "contact_name": "Jane Doe",
                    "contact_title": "Purchasing Manager",
                    "company_domain": "acme.example",
                    "contact_url": "https://www.linkedin.com/in/jane-doe",
                    "source_url": "https://www.linkedin.com/in/jane-doe",
                    "source_provider": "linkedin",
                    "evidence": "Jane Doe — Purchasing Manager at Acme GmbH",
                }
            ],
            "2026-08-31",
        )
        scored = annotate_score(lead)
        empty = annotate_score(normalize_lead({"company_name": "Beta", "website": "https://beta.example"}))
        with tempfile.TemporaryDirectory() as directory:
            paths = export_all([scored, empty], directory, {"product": "Ice machines", "country": "Germany", "buyer_type": "Distributor"})
            with paths["csv"].open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["contact_name"], "Jane Doe")
            self.assertIn("linkedin.com/in/jane-doe", rows[0]["contacts_json"])
            self.assertEqual(rows[0]["verified_contact_count"], "1")
            records = [json.loads(line) for line in paths["jsonl"].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records[0]["contacts"]), 1)
            markdown = paths["markdown"].read_text(encoding="utf-8")
            self.assertIn("linkedin.com/in/jane-doe", markdown)
            self.assertIn("Key contacts: 公开渠道未找到", markdown)

    def test_firecrawl_without_key_fails_safely(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = FirecrawlProvider(api_key="")
            self.assertFalse(provider.status().available)
            self.assertEqual(provider.status().reason, "FIRECRAWL_API_KEY missing for official cloud endpoint")
            with self.assertRaisesRegex(ProviderError, "FIRECRAWL_API_KEY missing"):
                provider.search("test", 5)

    def test_firecrawl_self_host_accepts_root_without_key_and_does_not_send_auth(self):
        response = Mock()
        response.read.return_value = b'{"data":{"web":[]}}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("lib.providers.urlopen", return_value=response) as mocked:
            provider = FirecrawlProvider(api_url="http://localhost:3002", api_key="")
            self.assertTrue(provider.status().available)
            provider.search("test", 3)
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:3002/v2/search")
        self.assertNotIn("Authorization", request.headers)

    def test_firecrawl_v2_is_not_duplicated_and_credentials_are_rejected(self):
        provider = FirecrawlProvider(api_url="http://localhost:3002/v2", api_key="")
        self.assertEqual(provider._v2_url("scrape"), "http://localhost:3002/v2/scrape")
        self.assertFalse(FirecrawlProvider(api_url="http://user:pass@localhost:3002", api_key="").status().available)

    def test_auto_always_includes_supplied_seed(self):
        args = build_parser().parse_args(
            ["--product", "ice", "--country", "Germany", "--buyer-type", "distributor", "--seed-file", __file__]
        )
        with patch("trade_lead_search.FirecrawlProvider.status", return_value=Mock(available=True, reason="configured")):
            self.assertEqual([provider.name for provider in _select_providers(args)], ["seed", "firecrawl"])

    def test_cli_parses_multiple_contact_files_and_dry_run_does_not_read_them(self):
        args = build_parser().parse_args(
            [
                "--product", "ice",
                "--country", "Germany",
                "--buyer-type", "distributor",
                "--contacts-file", "one.jsonl",
                "--contacts-file", "two.jsonl",
                "--dry-run",
            ]
        )
        self.assertEqual(args.contacts_file, ["one.jsonl", "two.jsonl"])

    def test_seed_and_contacts_pipeline_attaches_contact(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / "companies.jsonl"
            contacts = Path(directory) / "contacts.jsonl"
            seed.write_text(
                json.dumps({"company_name": "Acme GmbH", "website": "https://acme.example", "evidence": "distributor"})
                + "\n",
                encoding="utf-8",
            )
            contacts.write_text(
                json.dumps(
                    {
                        "contact_name": "Jane Doe",
                        "contact_title": "Purchasing Manager",
                        "company_domain": "acme.example",
                        "contact_url": "https://www.linkedin.com/in/jane-doe",
                        "source_url": "https://www.linkedin.com/in/jane-doe",
                        "source_provider": "linkedin",
                        "evidence": "Jane Doe — Purchasing Manager at Acme GmbH",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                [
                    "--product", "ice",
                    "--country", "Germany",
                    "--buyer-type", "distributor",
                    "--provider", "seed",
                    "--seed-file", str(seed),
                    "--contacts-file", str(contacts),
                    "--output-dir", str(Path(directory) / "output"),
                    "--limit", "5",
                ]
            )
            leads, warnings, summary = run(args)
            self.assertEqual(warnings, [])
            self.assertEqual(summary["attached_contacts"], 1)
            self.assertEqual(len(leads), 1)
            self.assertEqual(leads[0]["verified_contact_count"], 1)

    def test_provider_diagnostic_redacts_configured_keys(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-secret", "ANYSEARCH_API_KEY": "as-secret"}):
            diagnostic = redact_secrets("FIRECRAWL_API_KEY=fc-secret ANYSEARCH_API_KEY: as-secret")
        self.assertNotIn("fc-secret", diagnostic)
        self.assertNotIn("as-secret", diagnostic)

    def test_upstream_version_comparison_and_local_skill_version(self):
        self.assertEqual(compare_versions("v2.1.0", "2.2.0"), -1)
        self.assertEqual(compare_versions("2.1", "v2.1.0"), 0)
        self.assertEqual(compare_versions("2.1.0", "2.1.0-rc.1"), 1)
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "SKILL.md"
            skill.write_text("---\nname: last30days\nversion: 2.1.0\n---\n", encoding="utf-8")
            self.assertEqual(read_skill_version(skill), "2.1.0")

    def test_upstream_fetch_uses_public_api_headers_and_timeout(self):
        response = Mock()
        response.read.return_value = b'{"tag_name":"v3.0.0"}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("check_upstreams.urlopen", return_value=response) as mocked:
            self.assertEqual(fetch_latest_release("owner/repo", 4.5), "v3.0.0")
        request = mocked.call_args.args[0]
        self.assertEqual(mocked.call_args.kwargs["timeout"], 4.5)
        self.assertEqual(request.get_header("User-agent"), "global-trade-lead-search-upstream-check/1.0")
        self.assertIsNone(request.get_header("Authorization"))

    def test_upstream_check_compares_last30days_without_installing(self):
        with patch("check_upstreams.find_last30days_skill", return_value=Path("unused")), patch(
            "check_upstreams.read_skill_version", return_value="2.1.0"
        ), patch("check_upstreams.fetch_latest_release", return_value="v2.2.0"):
            result = check_project("last30days", 5, "2026-08-30T00:00:00Z")
        self.assertEqual(result["status"], "update_available")
        self.assertTrue(result["update_available"])
        self.assertEqual(result["repo"], "mvanhorn/last30days-skill")

    def test_upstream_failures_are_structured(self):
        with patch("check_upstreams.fetch_latest_release", side_effect=UpstreamError("rate_limited", "GitHub API rate limit reached")):
            result = check_project("firecrawl", 5, "2026-08-30T00:00:00Z")
        self.assertEqual(result["status"], "rate_limited")
        self.assertIsNone(result["latest_version"])
        self.assertIsNone(result["update_available"])

    def test_upstream_fetch_classifies_no_release_rate_limit_and_network(self):
        cases = [
            (HTTPError("https://api.github.test", 404, "Not Found", {}, None), "no_release"),
            (
                HTTPError("https://api.github.test", 403, "Forbidden", {"X-RateLimit-Remaining": "0"}, None),
                "rate_limited",
            ),
            (URLError("offline"), "network_error"),
        ]
        for error, expected in cases:
            with self.subTest(expected=expected), patch("check_upstreams.urlopen", side_effect=error):
                with self.assertRaises(UpstreamError) as raised:
                    fetch_latest_release("owner/repo", 3)
                self.assertEqual(raised.exception.status, expected)


if __name__ == "__main__":
    unittest.main()
