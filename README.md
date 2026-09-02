# Global Trade Lead Search

Auditable public B2B lead discovery for foreign-trade research.

This Skill combines directory and yellow-page discovery, web search, official-site verification, public LinkedIn company/contact matching, recent signals, evidence-based scoring, deduplication, and CSV/JSONL/Markdown export.

## Scope

- Research and local artifact creation only.
- No LinkedIn login, CAPTCHA or anti-bot bypass.
- No guessed personal email, phone, purchasing authority, or consent.
- No outreach, CRM import, form submission, or payment operation.
- Missing facts are labeled `待验证` or `公开渠道未找到`.

## Install from GitHub

```bash
git clone https://github.com/einkyhuang/global-trade-lead-search.git \
  ~/.codex/skills/global-trade-lead-search
```

Update an existing installation:

```bash
git -C ~/.codex/skills/global-trade-lead-search pull --ff-only origin main
```

## Verify the installation

```bash
python3 ~/.codex/skills/global-trade-lead-search/scripts/doctor.py
python3 -m unittest discover \
  -s ~/.codex/skills/global-trade-lead-search/tests -v
```

## Basic run

```bash
python3 scripts/trade_lead_search.py \
  --query "commercial lighting distributor Germany" \
  --country Germany \
  --limit 20 \
  --out-dir runs/lighting
```

Add public contact evidence after the company candidate set has been collected:

```bash
python3 scripts/trade_lead_search.py \
  --seed-file leads.jsonl \
  --contacts-file linkedin-contacts.jsonl \
  --out-dir runs/lighting-contacts
```

## Repository layout

`SKILL.md` contains the operating contract. `references/` contains provider, workflow, scoring, compliance, and contact-research rules. `scripts/` contains the CLI and catalog utilities. `data/` contains the source registry. `tests/` contains the regression suite. `docs/introduction.html` is the full Chinese product introduction.

## Future licensing and credits

The Skill is intentionally research-only and stateless. A future commercial edition can add a separate service repository for serial-number licensing, account authorization, usage metering, recharge, and provider secrets. The Skill should call that service through a narrow API; it should not store customer balances, payment credentials, or master keys in this repository.

Suggested future repositories:

1. This repository: public research Skill and adapters.
2. Optional private service: license/credits API, ledger, quotas, and admin controls.
3. Optional customer portal: only when a separate dashboard is actually needed.

Do not create the second or third repository until the billing workflow and data-retention requirements are defined.
