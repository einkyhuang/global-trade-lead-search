# Key-contact and LinkedIn research

Use this reference when the deliverable must identify named business contacts. Contacts are a separate evidence layer: they are attached only after the company record has an identifiable business identity and the person is explicitly tied to that business.

## Required outcome

For every retained key contact, preserve:

- person name;
- job title or role relevant to the request;
- company name and canonical domain, when available;
- employer/company evidence URL;
- public profile URL, preferably a LinkedIn profile or official biography;
- source URL and observation date;
- source platform, normally `linkedin`, `official_company`, `association`, `news_press`, or `trade_show`;
- match method and status;
- short evidence text showing the name, role, and employer together;
- missing fields as `待验证` or `公开渠道未找到`.

Do not infer a personal email address, direct phone number, messenger handle, purchasing authority, buying intent, or consent. Do not treat a job title alone as proof that the person can make purchasing decisions.

## Company-first matching gate

Attach a contact only after one of these passes:

1. **Domain match:** the contact artifact gives the lead's canonical company domain, and that domain equals the lead domain.
2. **LinkedIn company-page match:** the contact artifact gives a public LinkedIn company page whose displayed company name normalizes exactly to the lead company name, plus a public profile/biography explicitly showing the person at that company.
3. **Official-source match:** an official company page, announcement, annual report, association record, or credible independent source explicitly names the person and role at the company.

Record the matching rule used. A similar company name, shared city, keyword overlap, or a search snippet is not a match. If two companies may share a name, require the domain or another independent identity check.

## LinkedIn public-page workflow

LinkedIn is a useful public source for company employees and titles, but it is not an authorization to log in or evade limits.

1. Search public pages without authentication, for example `site:linkedin.com/company "<company>"` and then `site:linkedin.com/in "<company>" "<role>"`.
2. Open the public company page and verify the normalized company name, geography, industry, website, or other identity signal against the lead.
3. Find public person/profile pages or public People results that explicitly connect the person to that company and role.
4. Record the public company URL and profile URL. Do not claim content that was visible only after logging in.
5. If LinkedIn blocks the page or shows only a partial profile, stop for that page and use an official biography, press release, association page, exhibition page, or other public source.
6. Store unmatched or blocked searches in the coverage report rather than padding results.

Never automate around authentication walls, CAPTCHAs, robot controls, rate limits, or LinkedIn prohibitions. If using an authorized LinkedIn API or another licensed data provider, that provider must already be configured explicitly by the user; this Skill does not create credentials or accept new commercial terms on the user's behalf.

## Contact artifact format

Save contacts as JSON/JSONL when possible. A useful record is:

```json
{
  "contact_name": "Jane Doe",
  "contact_title": "Purchasing Manager",
  "company_name": "Acme GmbH",
  "company_domain": "acme.example",
  "linkedin_company_url": "https://www.linkedin.com/company/acme",
  "contact_url": "https://www.linkedin.com/in/jane-doe",
  "source_url": "https://www.linkedin.com/in/jane-doe",
  "source_provider": "linkedin",
  "evidence": "Jane Doe — Purchasing Manager at Acme GmbH",
  "observed_at": "2026-08-31"
}
```

Markdown contact artifacts are supported as fallback, but must use a person or company-identifying heading and include a URL. A Markdown heading alone does not establish the person-company relationship.

## Pipeline import

After saving permitted LinkedIn/search artifacts, import them alongside lead seeds:

```bash
python3 "$SKILL_ROOT/scripts/trade_lead_search.py" \
  --product "commercial lighting" \
  --country "Germany" \
  --buyer-type "distributor" \
  --provider seed \
  --seed-file "$SEED_DIR/companies.jsonl" \
  --contacts-file "$CONTACT_DIR/linkedin-contacts.jsonl" \
  --output-dir "$OUTPUT_DIR"
```

The importer normalizes records and attaches a contact only through the matching gate above. It preserves unmatched records in warnings/coverage rather than silently assigning them. Exported JSONL contains the full `contacts` array; CSV contains the primary contact and a compact JSON column for all contacts; Markdown lists each contact with evidence and source URL.

## Reporting

Report `verified_contacts` separately from company confidence. A high-confidence company can still have `公开渠道未找到` for key contacts. Never replace a missing named contact with a generic email address and describe the requirement as satisfied.
