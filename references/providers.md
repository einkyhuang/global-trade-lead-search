# Provider roles and routing

Providers have different evidentiary roles. Use the smallest combination that can meet the requested coverage and verification standard.

## Dragon Guide

Role: seed directory.

Use Dragon Guide to discover foreign yellow pages, B2B platforms, chambers of commerce, trade associations, local search engines, trade databases, and other country-specific research routes. Store useful platform links in the source registry with their country, language, source type, access requirements, health status, origin URL, and last-checked date.

Do not treat inclusion in Dragon Guide as evidence that an end company is real, relevant, active, or a buyer. Do not copy Dragon Guide's entire page content into the Skill. Preserve its URL as catalog provenance and verify destination links independently.

`scripts/query_source_catalog.py` returns research platforms from this registry. It does not search for or return customer leads. `health_status: discovered` on an external link means only that the link was extracted from a Dragon Guide page; the destination itself has not been directly health-checked. Do not translate `discovered` into `active` or `verified`.

When refreshing the catalog, prefer incremental updates: discover current directory pages, normalize destinations, retain historical records, and mark dead, redirected, login-gated, or blocked sources instead of silently deleting them.

## General and Google-like search

Role: broad discovery and gap filling.

Use a configured search engine, Google-compatible interface, browser search, or another permitted general search provider to:

- find companies absent from seed directories;
- locate official websites and specific product/contact pages;
- search local-language terms;
- corroborate company identity and relationships;
- discover current associations, exhibitions, tenders, or announcements.

Search snippets and generated summaries are navigational hints, not verified evidence. Open the result page before extracting a fact. Follow the provider's terms and do not automate around CAPTCHA or authentication barriers.

## AnySearch

Role: available search adapter.

Use AnySearch when installed and suitable for web discovery, parallel query execution, vertical search, or URL extraction. Keep the query, returned URL, provider, and observation time. Verify material fields against the underlying page, preferably an official source.

AnySearch is optional: absence or failure should produce a transparent fallback to another available search path, not fabricated or silently reduced coverage.

The first-version adapter looks for `runtime.conf` under the installed AnySearch Skill or at `ANYSEARCH_RUNTIME_CONF`. To use another location, set the environment variable before `doctor.py` or `trade_lead_search.py`:

```bash
export ANYSEARCH_RUNTIME_CONF="/path/to/anysearch/runtime.conf"
```

Do not place credentials directly in reusable commands or reports.

## Firecrawl

Role: bounded web discovery, page mapping, extraction, and crawl collection.

Use Firecrawl through a configured cloud endpoint or self-hosted endpoint. Never assume credentials or connectivity. Choose operations deliberately:

- `search`: discover URLs when Firecrawl's search capability is configured;
- `scrape`: extract a known page;
- `map`: enumerate useful pages within a known domain;
- `crawl`: collect a limited set of pages when single-page extraction is insufficient.

Escalate from `scrape` to `map` or `crawl` only when the narrower action cannot answer the research question. Bound domain, depth, page count, timeout, and rate. Remove tracking parameters and repeated URLs. Respect robots directives, access controls, and terms. Record partial results and the exact blocker when an operation fails.

Firecrawl output is extracted source material, not an automatic truth judgment. Keep the final page URL and observation time, and apply verification and scoring separately.

### First-version Firecrawl configuration

The Agent must set `SKILL_ROOT` to the absolute directory containing the currently loaded `global-trade-lead-search/SKILL.md`:

```bash
export SKILL_ROOT="/absolute/path/to/the-loaded/global-trade-lead-search"
test -f "$SKILL_ROOT/SKILL.md"
```

Replace the placeholder using the loaded Skill path. Use `SKILL_ROOT="$(pwd)"` only after verifying that the shell is already in this Skill's root.

For Firecrawl Cloud, supply the API key in the process environment and use the adapter's default `/v2` API base:

```bash
export FIRECRAWL_API_KEY="<secret-from-your-environment>"
unset FIRECRAWL_API_URL
python3 "$SKILL_ROOT/scripts/doctor.py"
```

For a self-hosted Firecrawl deployment, provide its API base. Set a bearer token only when that deployment requires one. Replace the example URL with the deployment's actual setting:

```bash
export FIRECRAWL_API_URL="http://127.0.0.1:3002"
unset FIRECRAWL_API_KEY
python3 "$SKILL_ROOT/scripts/doctor.py"
```

If the self-host requires a token, set `FIRECRAWL_API_KEY` instead of unsetting it. The official cloud endpoint requires a non-empty key; a self-hosted endpoint may run without one. The API base must use HTTP or HTTPS, must not contain embedded username/password credentials, and may include `/v2`; the adapter adds `/v2` when absent. Never commit or print a real key.

Preview selection first, then run a live Firecrawl search with optional page scraping only when network access and output creation are intended:

```bash
python3 "$SKILL_ROOT/scripts/trade_lead_search.py" \
  --product "commercial ice machine" \
  --country "Germany" \
  --buyer-type "distributor" \
  --limit 20 \
  --provider firecrawl \
  --scrape \
  --output-dir "$OUTPUT_DIR"
```

The first-version CLI exposes Firecrawl `search` and optional `scrape`. `map` and `crawl` remain valid Firecrawl roles for bounded site exploration, but are not CLI flags in this version; do not claim they ran unless another configured adapter actually executed and recorded them.

## `last30days`

Role: recent signal enrichment only.

Call the separately installed `last30days` Skill when the user requests recent activity or when recent signals materially improve prioritization. Do not vendor, copy, summarize into code, or reimplement its long contract inside this Skill.

Integration boundary:

1. Invoke `last30days` independently with the relevant company, product, market, and time window.
2. Save its output as a dated signals artifact.
3. Import the artifact into the lead workflow using canonical domain and normalized company name.
4. Preserve each signal's platform, URL, date, evidence note, and match confidence.

Signals may support freshness or activity scoring. They cannot alone verify company identity, contact details, customer status, purchasing intent, sales, or rankings.

If `last30days` is unavailable, continue without recent-signal enrichment and report that limitation.

The first-version import uses repeatable `--signals-file` arguments on `trade_lead_search.py`. It accepts JSON, JSONL/NDJSON, or Markdown generated by the independent Skill. Match signals using an explicit company name or canonical domain, retain the original URL and date, and keep the signals artifact separate from lead discovery inputs. See [workflow.md](workflow.md) for the executable import command.

## LinkedIn and key-contact sources

Role: key-contact discovery and employer/role evidence.

Use public LinkedIn company pages and public profile pages only, or an API/provider already explicitly authorized and configured by the user. Follow [contact-research.md](contact-research.md) for the company-first matching gate. LinkedIn results are especially useful for names and titles, but they do not by themselves provide consent, marketing eligibility, purchasing authority, personal email addresses, or direct phone numbers.

If LinkedIn requires login or blocks access, record that exact limitation and use official biographies, press releases, association/member pages, exhibition catalogs, or credible news pages instead. Do not automate around LinkedIn technical controls or terms.

## Fallback order

There is no universal provider order, but a normal run uses:

1. Dragon Guide-derived source registry for country and industry routes.
2. General/Google-like search or AnySearch for broad candidate discovery.
3. Official websites and credible registries for verification.
4. Firecrawl for efficient extraction and bounded site exploration.
5. `last30days` for optional recent-signal enrichment.

Provider failure must not change unknown facts into known facts. Report degraded coverage and continue with compliant alternatives when available.

## Controlled updates

Separate data refresh from code upgrades:

- A data refresh may revisit Dragon Guide and other registered seed pages, add newly discovered destinations, recheck source health, and emit a dated change report.
- A provider upgrade may check Firecrawl, AnySearch, `last30days`, or adapter compatibility, but it must not download and execute unreviewed code or overwrite the working Skill automatically.

Pin or record the tested dependency version when the implementation supports it. Review upstream changes, run the local validation suite, and keep the previous working configuration recoverable before adopting a new version. Report additions, changes, redirects, blocks, and removals; do not describe an unchecked upstream revision as installed or verified.

The Agent must first set `SKILL_ROOT` to the absolute directory containing the currently loaded `global-trade-lead-search/SKILL.md`, as described above. Then run the read-only upstream release check:

```bash
python3 "$SKILL_ROOT/scripts/check_upstreams.py" \
  --project all \
  --timeout 10
```

The checker only reads GitHub's public `/repos/{repo}/releases/latest` response for `firecrawl/firecrawl` and `mvanhorn/last30days-skill`; it uses no GitHub token and always emits JSON records. `--project` accepts `all`, `firecrawl`, or `last30days`, and `--timeout` accepts 1-60 seconds.

The checker never downloads, installs, executes, or overwrites upstream code. Its output must not trigger an automatic update. A reported version difference is evidence to begin a separate review, not permission to mutate the Skill, the Firecrawl deployment, or the installed `last30days` Skill. Treat network errors, rate limits, absent releases, unparseable versions, and missing local version metadata as unresolved checks, not proof that the local component is current.
