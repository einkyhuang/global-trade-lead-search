# Licensing and credits design

The first release remains a stateless research Skill. Licensing and balances should be added as a separate private service when commercial distribution is ready.

## Recommended boundary

```text
Client Skill -> License/Credits API -> immutable ledger + provider metering
                                      -> admin/recharge controls
```

The client receives a short-lived access token after activating a serial number. It never receives the master secret, payment credentials, or the full customer ledger.

## Minimum data model

- `customers`: customer id, status, plan, created date, suspension reason.
- `licenses`: serial hash, customer id, status, expiry, activation limit, last-used date.
- `wallets`: customer id, available credits, reserved credits, currency metadata.
- `ledger_entries`: immutable debit/credit entry, amount, operation id, provider, timestamp, balance-after.
- `usage_events`: operation id, customer id, query class, result count, provider calls, cost, status.

## Search accounting

1. Create an idempotent `operation_id` before a search starts.
2. Ask the service to reserve the estimated credit cost.
3. Run the bounded search and collect actual provider usage.
4. Settle the reservation with the actual cost, or release it on a safe failure.
5. Return remaining balance and a receipt id in the local report.

Never debit only in the client and never trust a client-supplied balance. Replaying the same `operation_id` must not double-charge.

## Suggested cost classes

Keep costs explicit and versioned, for example: directory lookup, web search batch, page extraction, Firecrawl scrape, recent-signal run, and contact-evidence enrichment. A pricing-table version must be stored with every ledger entry so future price changes do not rewrite history.

## Controls

- Per-license and per-customer rate limits.
- Maximum query count, page count, crawl depth, and contact artifacts per operation.
- Server-side provider keys only.
- Audit log for activation, recharge, debit, refund, suspension, and administrator changes.
- Recharge through a payment provider or manual admin crediting; never store raw card data.
- Separate research data retention from billing retention.

The second repository should not be created until the payment provider, identity model, refund policy, and data-retention period are decided.
