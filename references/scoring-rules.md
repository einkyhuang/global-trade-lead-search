# Qualification and scoring rules

Scoring ranks evidence-backed leads; it must not turn missing evidence into a fact. Keep the underlying evidence and status visible so a user can audit every score.

## Gates before scoring

A record can enter the qualified set only when:

- it represents an identifiable business or organization;
- its country or target-market relationship is supported;
- a canonical domain or credible registry/directory identity is available;
- it does not match an explicit exclusion;
- there is at least one source URL and observation date.

A record with identity conflicts stays `待验证` and should not outrank a verified record. A source listing alone does not establish that the company buys the user's product.

## Default 100-point model

Use this model only when the user has not supplied their own criteria. Scores are aids to ordering, not probability estimates.

| Dimension | Points | Evidence expected |
|---|---:|---|
| Company identity | 0-20 | Canonical domain, consistent name, location, registry or credible corroboration |
| Product fit | 0-30 | Official product/category/service evidence tied to the requested offer |
| Customer-type fit | 0-20 | Explicit importer, distributor, wholesaler, retailer, contractor, buyer, or end-user role |
| Target-market fit | 0-10 | Supported operation, sales area, office, registration, or market coverage |
| Contactability | 0-10 | Public official business email, phone, contact page, or a verified named contact with an evidence-backed relevant role; no inferred address |
| Freshness and activity | 0-10 | Recent official update or properly matched imported signal |

Award zero when the dimension has no evidence. Do not assign midpoint points merely because a value seems likely.

## Confidence bands

- `high` / 80-100: verified identity, direct product fit, supported customer type, and strong sources.
- `medium` / 60-79: identifiable and relevant, but one important qualification field needs stronger evidence.
- `low` / below 60: discovery candidate, weak fit, incomplete identity, or material unresolved conflict.

Keep low-confidence candidates outside the main qualified set unless the user explicitly asks for exploratory leads. Never pad a requested count with low-confidence records without labeling them.

## Evidence adjustments

Apply points field by field:

- Prefer a directly relevant official page over a homepage or generic directory category.
- Treat multiple copies of one syndicated claim as one source.
- Reduce confidence for stale pages, unexplained redirects, mismatched legal names, or conflicting locations.
- Do not award product-fit or customer-type points for keyword presence alone when the page context is unclear.
- Do not award buyer-intent points merely because a company sells adjacent products.

Recent signals from `last30days` may contribute only to the freshness and activity dimension unless another primary source independently verifies the underlying fact. A post or discussion does not establish sales, procurement volume, or willingness to buy.

## Deduplication

Use canonical domain plus normalized company name as the primary identity key. Normalize common legal suffixes and URL variants, but preserve the original display name.

Before merging, check:

- canonical and redirected domains;
- legal name, trading name, and local-language name;
- official address and country;
- parent, subsidiary, brand, and distributor relationships.

Keep separate records when organizational identity remains ambiguous. Record aliases and merge rationale. Never merge only because two names are similar or a directory reuses an address.

## Status and missing values

Scoring does not replace status labels:

- `已验证`: direct, credible evidence supports the field;
- `待验证`: evidence is incomplete, ambiguous, stale, or conflicting;
- `公开渠道未找到`: the requested field was not found after a reasonable public search.

Unknown contact details, sales, rankings, purchasing volume, and personal roles always score zero. A named person can receive contact evidence points only when name, relevant role, employer, and source evidence are present and the company match is explicit. Never estimate or synthesize them.

## Reporting

For each scored lead, retain the dimension scores, total, confidence band, disqualifiers, and evidence URLs. Report the cutoff used and how many candidates fell below it. If coverage is weak, return fewer qualified leads and explain the shortfall.
