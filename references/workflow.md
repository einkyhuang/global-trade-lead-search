# Research workflow

Use this workflow for a full lead-research run. Scale the breadth to the requested result count and stop when additional discovery no longer produces qualified, non-duplicate companies.

## First-version CLI

Before running commands, the Agent must set `SKILL_ROOT` to the absolute directory containing the currently loaded `global-trade-lead-search/SKILL.md`:

```bash
export SKILL_ROOT="/absolute/path/to/the-loaded/global-trade-lead-search"
test -f "$SKILL_ROOT/SKILL.md"
```

Replace the placeholder using the loaded Skill path; do not hardcode a user-specific absolute path in reusable prompts, scripts, or reports. Use `SKILL_ROOT="$(pwd)"` only when the Agent has first verified that the current directory is this Skill's root, not merely because it is the shell's current directory.

### Check readiness

Run the local readiness report before a live search:

```bash
python3 "$SKILL_ROOT/scripts/doctor.py"
```

If AnySearch uses a non-default `runtime.conf`, pass it to the check:

```bash
python3 "$SKILL_ROOT/scripts/doctor.py" \
  --anysearch-runtime-conf "$ANYSEARCH_RUNTIME_CONF"
```

The report checks configuration without printing the Firecrawl API key. An unavailable optional provider is a coverage limitation, not permission to invent results.

### Check upstream releases without upgrading

Check the latest published GitHub releases for both optional upstream projects:

```bash
python3 "$SKILL_ROOT/scripts/check_upstreams.py" \
  --project all \
  --timeout 10
```

Use `--project firecrawl` or `--project last30days` for one upstream. The timeout must be between 1 and 60 seconds.

This command is inspection-only. It makes unauthenticated read requests to GitHub's latest-release endpoint and prints JSON; it does not download, install, execute, update, or overwrite upstream code or local Skill files. `update_available: true` is only a review signal, not authorization to upgrade. Review release notes, compatibility, licenses, local changes, and tests separately before any explicitly authorized update.

Each JSON record includes `checked_at`, `repo`, `latest_version`, `local_version`, `update_available`, and `status`, with `message` on relevant limitations or failures. For Firecrawl, `upstream_only` does not assert that a local Firecrawl core installation exists. For `last30days`, `local_version_missing` means the installed `SKILL.md` did not expose a comparable version; it does not mean an update was installed or is safe. Network, rate-limit, missing-release, or parse errors should be reported as unknown rather than interpreted as current.

### Query research platforms

Query the checked-in source registry by exact, case-insensitive filters:

```bash
python3 "$SKILL_ROOT/scripts/query_source_catalog.py" \
  --country "Germany" \
  --source-type "yellow_pages" \
  --health-status "discovered" \
  --limit 10 \
  --format jsonl
```

Available filters are `--country`, `--continent`, `--source-type`, and `--health-status`; use `--registry` for another registry file. The output is a list of research platforms, not companies or customer leads. Use the returned platforms to plan discovery queries, then verify the companies found on them.

`health_status: discovered` means an external URL was discovered on a Dragon Guide page. The sync process did not directly request that external destination, so this status does not establish that the platform is online, safe, current, or accessible.

### Refresh the Dragon Guide catalog

Preview a bounded refresh without writing files:

```bash
python3 "$SKILL_ROOT/scripts/sync_source_catalog.py" \
  --dry-run \
  --max-pages 10 \
  --max-depth 1
```

After reviewing the plan and when a catalog update is authorized, apply a bounded refresh by omitting `--dry-run`:

```bash
python3 "$SKILL_ROOT/scripts/sync_source_catalog.py" \
  --max-pages 40 \
  --max-depth 2
```

By default, apply mode writes `data/source-registry.jsonl` and `data/source-health.json` under the Skill root. Use `--output` and `--health-output` for an isolated destination. This sync visits permitted Dragon Guide catalog pages; it records external links but does not health-check each external site.

### Preview a lead search

Before network calls or output writes, inspect the bounded provider plan:

```bash
python3 "$SKILL_ROOT/scripts/trade_lead_search.py" \
  --product "commercial ice machine" \
  --country "Germany" \
  --buyer-type "distributor" \
  --limit 20 \
  --provider auto \
  --dry-run
```

The dry run prints the query and selected providers with `network_calls: false` and `writes: false`. It does not prove that those providers will return sufficient verified leads.

### Import Google or agent discovery results

Save permitted Google-like search or research-agent results as JSON or JSONL, retaining source URLs and evidence. Then import one or more files without executing their contents:

```bash
python3 "$SKILL_ROOT/scripts/trade_lead_search.py" \
  --product "commercial ice machine" \
  --country "Germany" \
  --buyer-type "distributor" \
  --provider seed \
  --seed-file "$SEED_DIR/google-results.jsonl" \
  --seed-file "$SEED_DIR/agent-results.json" \
  --output-dir "$OUTPUT_DIR"
```

JSON may be a record, an array, or an object containing `results`, `leads`, or `data`; JSONL must contain one object per non-empty line. Useful fields include `company_name`, `website`, `country`, `buyer_type`, `product`, `source_url`, `evidence`, `verification_url`, and `observed_at`. Imported search snippets remain discovery evidence until their underlying pages are opened and verified.

### Import `last30days` signals

Run the independently installed `last30days` Skill first and save its output as JSON, JSONL, or Markdown. Then import it alongside a lead source:

```bash
python3 "$SKILL_ROOT/scripts/trade_lead_search.py" \
  --product "commercial ice machine" \
  --country "Germany" \
  --buyer-type "distributor" \
  --provider seed \
  --seed-file "$SEED_DIR/agent-results.jsonl" \
  --signals-file "$SIGNALS_DIR/last30days-signals.jsonl" \
  --output-dir "$OUTPUT_DIR"
```

For a reliable match, each signal should carry the company's canonical domain or explicit company name. A Markdown signal should use a company-identifying heading or URL. Imported signals enrich freshness only; they do not verify a company, contact, buyer relationship, purchase intent, sales, or ranking.

See [providers.md](providers.md) for Firecrawl cloud/self-hosted environment configuration and a live Firecrawl example.

## 1. Define the brief

Record:

- product or service and important synonyms;
- target countries or regions;
- desired customer types, such as importer, distributor, wholesaler, retailer, manufacturer, contractor, or end user;
- exclusions and disqualifiers;
- target count and required fields;
- search languages and freshness window.

Do not silently reinterpret a request for customers as a request for suppliers. If geography or customer type is absent but a narrow, reversible assumption is reasonable, state it in the report.

## 2. Build multilingual queries

Combine product terms, customer-type terms, geography, and source-specific operators. Include English and useful local-language equivalents. Keep a query log so another run can reproduce coverage.

Examples of query intent, not fixed templates:

- product + distributor/importer/wholesaler + country;
- local-language product + local-language customer type;
- product + association/member directory;
- product + official contact/about/products pages;
- domain-scoped searches against a selected yellow page or B2B platform.

## 3. Discover candidates

Select source classes using [source-types.md](source-types.md), then use the provider roles in [providers.md](providers.md):

1. Start with relevant Dragon Guide entries as routes into national directories, chambers, associations, B2B platforms, local search engines, and trade sources. The registry contains research platforms, not customer leads.
2. Run general or Google-like search, with AnySearch when available, to expand beyond the seed catalog.
3. Use Firecrawl `search` when its search endpoint is the suitable discovery adapter.
4. Preserve the discovery URL, query, source class, and observation time for each candidate.

Directory entries and search results are candidates, not verified leads.

## 4. Resolve and verify the entity

Find the canonical business domain. Use official pages first for identity, location, offerings, and contact channels. Cross-check ambiguous companies with registries, chambers, associations, credible directories, or other independent sources.

Use Firecrawl incrementally:

1. `scrape` a known page when one page is enough.
2. `map` a domain to locate product, about, contact, dealer, or distributor pages.
3. `crawl` only when several relevant pages must be collected and the crawl can be tightly bounded.

Record exact page URLs supporting each material field. A homepage URL alone is not product-fit evidence unless the needed statement is actually present there.

## 5. Extract public business facts

Capture only evidence-backed fields requested by the user. Typical fields include:

- company name and canonical domain;
- country and city;
- customer type;
- relevant products, brands, markets, or services;
- public business phone or email;
- named business contact and title, only when the source explicitly states both;
- evidence URLs, observation dates, verification status, and notes.

Use `待验证` for a plausible but unconfirmed value. Use `公开渠道未找到` when a requested field remains absent after a reasonable public-source search. Follow [compliance.md](compliance.md) for personal data and outreach boundaries.

## 6. Normalize and deduplicate

Normalize company suffixes, whitespace, casing, protocol, `www`, trailing slashes, and obvious tracking parameters. Use canonical domain plus normalized legal or trading name as the main identity key.

Keep subsidiaries, brands, distributors, and parent companies separate unless evidence proves they are the same operating entity. Preserve alternate names and the reason for any merge. Never merge solely on a similar name, address fragment, or shared directory listing.

## 7. Qualify and rank

Apply [scoring-rules.md](scoring-rules.md). Evidence strength and product/customer-type fit take priority over the number of populated fields. Disqualify or quarantine records that conflict with explicit exclusions, lack an identifiable business, or cannot be tied to a real domain or credible registry entry.

## 8. Add recent signals when useful

When freshness matters, invoke the independent `last30days` Skill. Save its output separately, for example as a dated JSON or JSONL signals artifact, then import it into the lead run using stable identifiers such as canonical domain and company name.

Each imported signal should retain its source URL, publication or observation date, platform, matched entity, match confidence, and short evidence note. Do not use a recent signal to manufacture buying intent, revenue, sales, company identity, or contact details.

## 9. Deliver and report coverage

Produce the requested tabular format and a machine-readable evidence artifact when the implementation supports it. Include:

- the final deduplicated leads;
- field-level or record-level evidence links;
- confidence and verification status;
- search date and freshness window;
- counts discovered, verified, deduplicated, excluded, and retained;
- sources or countries that were blocked, unavailable, or thinly covered;
- unresolved and `公开渠道未找到` fields.

Do not pad the result count. Report a shortfall with the exact coverage limitation.
