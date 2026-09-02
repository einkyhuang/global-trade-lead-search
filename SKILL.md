---
name: global-trade-lead-search
description: Research and verify public B2B companies, distributors, importers, wholesalers, buyers, key business contacts, and contact evidence across countries. Use for foreign-trade lead discovery, global yellow-pages research, company qualification, LinkedIn public-page contact matching, source-backed contact research, and recent buying or market signals; do not use it to send outreach or invent unavailable facts.
---

# Global Trade Lead Search

Build an auditable lead set from public business information. Treat discovery results as candidates until an official or otherwise credible source verifies them.

## Start with the request

Identify the product or service, target countries, desired customer types, result limit, exclusions, preferred languages, and freshness requirement. If a missing field would materially change the search, ask for it; otherwise state the assumption and continue.

Before a substantial run, read [references/workflow.md](references/workflow.md). Load only the other references needed:

- Read [references/providers.md](references/providers.md) when choosing Dragon Guide, general/Google-like search, AnySearch, Firecrawl, or `last30days`.
- Read [references/source-types.md](references/source-types.md) when selecting or updating source registries.
- Read [references/scoring-rules.md](references/scoring-rules.md) when ranking, qualifying, or deduplicating leads.
- Read [references/compliance.md](references/compliance.md) before collecting contact details or producing a deliverable that could support outreach.
- Read [references/contact-research.md](references/contact-research.md) whenever key contacts, named people, LinkedIn, executives, purchasing managers, or other role-based contacts are requested.

For the first-version CLI, resolve the directory containing this `SKILL.md` as the Skill root, run `scripts/doctor.py`, and use the commands in [references/workflow.md](references/workflow.md). Provider setup, including Firecrawl cloud/self-hosted configuration, is in [references/providers.md](references/providers.md).

## Required operating model

Use Dragon Guide as a seed directory of foreign yellow pages, B2B platforms, chambers, associations, local search engines, and trade-data sources. A listing there is a discovery route, not proof that a company is a qualified customer.

The source registry and `scripts/query_source_catalog.py` return research platforms to search. They do not return customer leads. In that registry, an external destination with `health_status: discovered` was found on a Dragon Guide page but has not been directly health-checked.

Use general or Google-like search, including AnySearch when available, to discover candidate companies and supporting pages. Open the underlying sources; do not promote a search snippet into a verified fact.

Use Firecrawl through its supported API, SDK, CLI, or configured adapter for bounded `search`, `map`, `scrape`, and `crawl` work. Respect access controls, robots directives, terms, rate limits, and crawl boundaries. Prefer the least expensive operation that can answer the question.

Use the separately installed `last30days` Skill only when recent discussion, company activity, demand, launches, hiring, events, or other time-sensitive signals matter. Invoke it as an independent Skill, save its result as a signals artifact, and import that artifact into this workflow. Do not copy or reimplement its long internal contract. Recent signals can change prioritization but cannot by themselves verify company identity, contact details, purchasing intent, or sales.

Use LinkedIn only through public pages, an already-authorized API, or another permitted source. Verify the employer/company identity before attaching a named person, and follow [references/contact-research.md](references/contact-research.md).

## Evidence contract

For each retained company, preserve the company name, canonical domain, geography, customer type, product-fit evidence, source URL, verification URL, observed date, verification status, and confidence. Keep directory evidence, official-site evidence, contact evidence, and recent signals distinguishable.

For key-contact requests, first verify the employer/company identity, then attach a person only when a public source explicitly connects the person's name, relevant role, and that company. Preserve the LinkedIn company/profile URLs (when used), observation date, match method, match status, and source evidence. A LinkedIn company-name match alone is not enough to invent an email address, phone number, purchasing authority, or consent status.

Normalize and deduplicate primarily by canonical domain plus normalized company name. Do not merge entities merely because their names resemble one another.

Never guess or manufacture companies, customers, sales, rankings, purchasing volume, people, job titles, phone numbers, or email addresses. When evidence is insufficient, write `待验证`; when a requested fact cannot be found in public sources after a reasonable search, write `公开渠道未找到`. Keep conflicting evidence visible instead of silently choosing a convenient value.

This Skill authorizes research and local artifact creation only. It does not authorize sending email, submitting forms, adding contacts to marketing systems, logging into LinkedIn, bypassing LinkedIn technical controls, purchasing data, or contacting any person. Require a separate explicit request and appropriate compliance checks for outreach.

## Finish

Return the requested lead table plus source-backed evidence and a concise coverage report: queries and source classes used, counts discovered/verified/deduplicated/retained, unresolved fields, blocked sources, and known coverage gaps. A smaller verified set is better than padded results.
