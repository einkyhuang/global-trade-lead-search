from __future__ import annotations

import unittest
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.catalog import (  # noqa: E402
    FetchResult,
    canonical_domain,
    classify_source_type,
    crawl_catalog,
    deduplicate_entries,
    extract_links,
    infer_location,
    is_non_directory_source,
    Link,
    merge_failed_origins,
    normalize_url,
)
from query_source_catalog import query_records  # noqa: E402


class UrlNormalizationTests(unittest.TestCase):
    def test_normalizes_host_port_path_and_tracking(self) -> None:
        actual = normalize_url("HTTPS://WWW.Example.COM:443/a//b/?utm_source=x&b=2&a=1#part")
        self.assertEqual(actual, "https://example.com/a/b?a=1&b=2")
        self.assertEqual(canonical_domain(actual or ""), "example.com")

    def test_rejects_non_http_and_credentials(self) -> None:
        self.assertIsNone(normalize_url("mailto:sales@example.com"))
        self.assertIsNone(normalize_url("https://user:secret@example.com/"))


class ClassificationTests(unittest.TestCase):
    def test_classifies_supported_sections(self) -> None:
        cases = {
            "Germany most influential search engine": "search_engine",
            "European B2B Websites": "b2b_marketplace",
            "National Yellow Pages Web": "yellow_pages",
            "Chamber and trade association": "chamber_association",
            "Global Customs and import export database": "customs_trade",
            "official government website": "government_trade",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify_source_type(text), expected)

    def test_infers_continent_from_specialized_directory_filename(self) -> None:
        cases = {
            "https://dragon-guide.net/hangye/ouzhou-B2B.htm": "Europe",
            "https://dragon-guide.net/hangye/yazhou-yellowpages.htm": "Asia",
            "https://dragon-guide.net/hangye/feizhou-search.htm": "Africa",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(infer_location(url), (expected, None))

    def test_country_named_like_continent_is_not_lost(self) -> None:
        self.assertEqual(
            infer_location("https://dragon-guide.net/guobie/meizhou/America.htm"),
            ("Americas", "United States"),
        )

    def test_rejects_social_and_media_but_keeps_search_provider(self) -> None:
        for url in (
            "https://facebook.com/company",
            "https://instagram.com/company",
            "https://linkedin.com/company/example",
            "https://x.com/example",
            "https://youtube.com/@example",
        ):
            with self.subTest(url=url):
                self.assertTrue(is_non_directory_source(Link(url, "Company", "yellow_pages"), "yellow_pages"))
        self.assertTrue(
            is_non_directory_source(Link("https://press.example/news", "Daily News", "yellow_pages"), "yellow_pages")
        )
        self.assertTrue(
            is_non_directory_source(Link("https://antaranews.example/", "Antara", "yellow_pages"), "yellow_pages")
        )
        self.assertFalse(
            is_non_directory_source(Link("https://news.google.com/", "Google News", "search_engine"), "search_engine")
        )


class ExtractionTests(unittest.TestCase):
    def test_extracts_links_with_persistent_section(self) -> None:
        document = """
        <html lang="en"><body>
          <h2>Germany most influential B2B website</h2>
          <a href="https://WWW.Example.com/list?utm_source=guide">Example</a>
          <a href="/guobie/ouzhou/France.htm">France</a>
        </body></html>
        """
        links, language = extract_links(document, "https://www.dragon-guide.net/guobie/ouzhou/German.htm")
        self.assertEqual(language, "en")
        self.assertEqual(links[0].url, "https://example.com/list")
        self.assertEqual(links[0].section_type, "b2b_marketplace")
        self.assertEqual(links[1].url, "https://dragon-guide.net/guobie/ouzhou/France.htm")

    def test_resets_section_before_news_and_bank_links(self) -> None:
        document = """
        <h2>National Yellow Pages Web</h2>
        <a href="https://directory.test">Directory</a>
        <h2>News and information Website</h2>
        <a href="https://news.test">News</a>
        <h2>Bank Securities website</h2>
        <a href="https://bank.test">Bank</a>
        """
        links, _ = extract_links(document, "https://dragon-guide.net/guobie/ouzhou/German.htm")
        self.assertEqual(links[0].section_type, "yellow_pages")
        self.assertIsNone(links[1].section_type)
        self.assertIsNone(links[2].section_type)

    def test_real_country_page_sections_do_not_leak_across_panels(self) -> None:
        document = """
        <h4> 德国搜索引擎</h4><a href="https://search.test">Search</a>
        <h4> 德国黄页网站</h4><a href="https://directory.test">Directory</a>
        <h4> 德国购物网站</h4><a href="https://retail.test">Retail</a>
        <h4> 德国官方对外经贸网站</h4><a href="https://government.test">Government</a>
        <h4> 德国民间对外经贸相关网站</h4><a href="https://association.test">Association</a>
        <h4> 德国论坛网站</h4><a href="https://forum.test">Forum</a>
        """
        links, _ = extract_links(document, "https://dragon-guide.net/guobie/ouzhou/German.htm")
        expected = [
            ("search.test", "search_engine"),
            ("directory.test", "yellow_pages"),
            ("retail.test", "yellow_pages"),
            ("government.test", "government_trade"),
            ("association.test", "chamber_association"),
            ("forum.test", None),
        ]
        self.assertEqual([(canonical_domain(link.url), link.section_type) for link in links], expected)

    def test_real_finland_sections_reset_news_and_social_panels(self) -> None:
        document = """
        <h4> 芬兰搜索引擎</h4><a href="https://search.test">Search</a>
        <h4> 芬兰民间对外经贸相关网站</h4><a href="https://association.test">Association</a>
        <h4> 芬兰新闻网站</h4><a href="https://news.test">News</a>
        <h4> 芬兰论坛网站</h4><a href="https://forum.test">Forum</a>
        <h4> 芬兰社交平台</h4><a href="https://social.test">Social</a>
        """
        links, _ = extract_links(document, "https://dragon-guide.net/guobie/ouzhou/Finland.htm")
        expected = [
            ("search.test", "search_engine"),
            ("association.test", "chamber_association"),
            ("news.test", None),
            ("forum.test", None),
            ("social.test", None),
        ]
        self.assertEqual([(canonical_domain(link.url), link.section_type) for link in links], expected)


class DeduplicationTests(unittest.TestCase):
    def test_deduplicates_by_normalized_domain_and_prefers_official(self) -> None:
        common = {
            "name": "Example",
            "canonical_domain": "example.com",
            "continent": "Europe",
            "country": "German",
            "language": ["en"],
            "origin": "dragon-guide",
            "health_status": "discovered",
            "http_status": None,
            "last_checked_at": "2026-08-30",
        }
        entries = [
            {**common, "url": "http://example.com/dir", "origin_page": "https://dragon-guide.net/a", "source_type": "yellow_pages", "trust_level": "directory"},
            {**common, "url": "https://example.com/trade", "origin_page": "https://dragon-guide.net/b", "source_type": "government_trade", "trust_level": "official"},
        ]
        result = deduplicate_entries(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://example.com/trade")


class CrawlTests(unittest.TestCase):
    def test_bounded_crawl_extracts_external_directory_only(self) -> None:
        root = "https://dragon-guide.net/"
        country = "https://dragon-guide.net/guobie/ouzhou/German.htm"
        responses = {
            root: FetchResult(root, 200, b'<a href="/guobie/ouzhou/German.htm">Germany</a><a href="https://ads.test">Ad</a>', "text/html; charset=utf-8"),
            country: FetchResult(
                country,
                200,
                b'<h2>National Yellow Pages Web</h2><a href="https://www.directory.test/a">Directory</a>',
                "text/html; charset=utf-8",
            ),
        }
        catalog, health = crawl_catalog(responses.__getitem__, seeds=(root,), max_pages=2, max_depth=1, checked_at="2026-08-30")
        self.assertEqual([entry["canonical_domain"] for entry in catalog], ["directory.test"])
        self.assertEqual(catalog[0]["country"], "Germany")
        self.assertEqual(catalog[0]["continent"], "Europe")
        self.assertEqual(health["pages_succeeded"], 2)

    def test_failed_origin_retains_previous_entry_with_marker(self) -> None:
        origin = "https://dragon-guide.net/hangye/Customs.htm"
        previous = [{
            "name": "Trade Data",
            "url": "https://trade.example/",
            "canonical_domain": "trade.example",
            "source_type": "customs_trade",
            "continent": None,
            "country": None,
            "language": ["zh"],
            "origin": "dragon-guide",
            "origin_page": origin,
            "health_status": "discovered",
            "http_status": None,
            "last_checked_at": "2026-08-29",
            "trust_level": "authoritative",
        }]
        failure = FetchResult(origin, 503, None, "text/html", "HTTP 503")
        merged = merge_failed_origins([], previous, {origin: failure}, "2026-08-30")
        self.assertEqual(merged[0]["health_status"], "origin_unavailable")
        self.assertEqual(merged[0]["http_status"], 503)
        self.assertEqual(merged[0]["last_checked_at"], "2026-08-30")


class QueryTests(unittest.TestCase):
    def test_filters_platform_registry_and_honors_limit(self) -> None:
        records = [
            {"name": "A", "country": "Germany", "continent": "Europe", "source_type": "yellow_pages", "health_status": "discovered"},
            {"name": "B", "country": "Germany", "continent": "Europe", "source_type": "b2b_marketplace", "health_status": "discovered"},
            {"name": "C", "country": "France", "continent": "Europe", "source_type": "yellow_pages", "health_status": "discovered"},
        ]
        result = query_records(records, country="germany", health_status="DISCOVERED", limit=1)
        self.assertEqual([item["name"] for item in result], ["A"])

    def test_rejects_nonpositive_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            query_records([], limit=0)

if __name__ == "__main__":
    unittest.main()
