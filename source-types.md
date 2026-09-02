# Source types

Classify every registry entry and evidence source by what it can reasonably establish. A source may have more than one role, but do not overstate its authority.

| Source type | Primary use | Typical evidentiary value | Main caution |
|---|---|---|---|
| `official_company` | Identity, products, locations, public contacts | Strong for the company's own claims | Self-published; not proof of purchasing or sales |
| `government_registry` | Legal identity, registration, status | Strong for registered facts | May be stale, paywalled, or limited by jurisdiction |
| `yellow_pages` | Candidate discovery and local categorization | Moderate for existence; weak for current fit | Duplicates, stale listings, resellers, paid placement |
| `b2b_marketplace` | Supplier/buyer discovery and product association | Moderate to weak unless independently verified | Profiles may be self-entered or inactive |
| `chamber` | Member discovery and business identity | Moderate to strong, depending on membership controls | Membership does not prove product demand |
| `trade_association` | Industry membership and specialization | Moderate to strong for sector relevance | Coverage is selective; dates matter |
| `local_search_engine` | Country-language discovery | Discovery only until the destination is opened | Snippets and rankings are not evidence |
| `general_search` | Broad discovery and corroboration | Discovery only until the destination is opened | Personalization, stale snippets, SEO spam |
| `trade_data` | Import/export or shipment evidence | Potentially strong for the represented period and field | Methodology, licensing, entity matching, and lag vary |
| `tender_procurement` | Published demand, award, or procurement activity | Strong for the exact notice or award | A tender is not proof of completed purchase unless stated |
| `trade_show` | Exhibitors, sponsors, speakers, event activity | Moderate for event participation and industry fit | Lists may be historic or promotional |
| `news_press` | Events, launches, expansion, partnerships | Variable; corroborate material claims | Syndication and company press releases can duplicate claims |
| `social_community` | Recent activity and market signals | Weak to moderate for the exact post | Identity ambiguity, opinion, deleted content, no buyer proof |
| `contact_directory` | Candidate business contact details | Variable | Personal-data, freshness, licensing, and inference risk |
| `professional_network` | Public company employees, names, titles, and role evidence | Moderate when the public page explicitly connects person and employer | Login walls, stale or partial profiles, name collisions, profile terms, and no outreach consent |

## Source registry fields

Keep at least:

- stable source identifier;
- name and normalized destination URL;
- source type;
- continent, country, and supported languages when applicable;
- access mode, login requirement, and cost indicator;
- provenance such as Dragon Guide page URL or manual addition;
- health status and last-checked timestamp;
- notes on scope, licensing, robots, or known limitations.

Suggested health states are `active`, `redirected`, `login_required`, `blocked`, `dead`, and `unchecked`. Do not delete a source merely because it becomes unavailable; retain history and update the state.

## Evidence hierarchy

Choose the source that directly supports the field rather than assigning one universal rank to an entire website. In general:

1. government or official registry for legal facts;
2. official company page for the company's stated products, locations, and public contacts;
3. primary tender, association, chamber, or event record for the event it records;
4. reputable independent trade, news, or directory source;
5. search result, marketplace profile, aggregator, or social/community signal as discovery or corroboration.

Two weak sources do not necessarily equal one strong source. Independence matters: syndicated copies of the same claim count as one origin.

## Selecting sources

Match source types to the brief. Country-specific yellow pages and local-language search improve discovery; government registries improve identity checks; official product pages improve fit checks; trade data or tenders may provide demand evidence; `last30days` signals improve freshness context.

Record coverage gaps. A source that blocks automated access, requires login, or is unavailable should be marked accordingly and replaced only with a compliant alternative.
