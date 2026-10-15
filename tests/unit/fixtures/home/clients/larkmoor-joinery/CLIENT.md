---
schema: "client/2"
slug: "larkmoor-joinery"
name: "Larkmoor Joinery"
account_kind: "own"                    # own | client | sandbox
build_target: "own-account"            # own-account | client-account | none
monday_account_id: "10000001"
monday_account_slug: "example-account"
monday_bound_user_id: "20000001"
monday_bound_at: "2026-10-19T10:05:00Z"
monday_tier: "standard"
monday_tier_read_at: "2026-10-28"
monday_tier_source: "preflight"
products_in_scope: "core"
client_workspaces: "core:40000001"
record_state: "active"
strands_open: "2"
strands_total: "2"
current_strand: "001"
live_build: "yes"
lease: "001 v0.1 (20261105-1405-r2d6)"   # mirrors .work/lock.json
last_input: "2026-10-21-timber-orders"
last_researched: "never"
# The three A11 fields stay open: each is asked once per client, at the moment it first matters.
transcripts_at_close: "unanswered"
transcript_redaction: "unanswered"
sample_data_in_account: "unanswered"
ai_notice: "not-yet"
updated: "2026-11-05T14:05"
---
Internal: never client-facing

# Larkmoor Joinery

## Folder map

- [Log](log.md), [account ledger](account.json), [live map](live/live-map.md)
- [Strand 001](strands/001-job-tracking/STRAND.md), [strand 002](strands/002-timber-orders/STRAND.md)

## Strand index

| strand | title | kind | state | version | version state | clearance | live objects | last activity |
|---|---|---|---|---|---|---|---|---|
| 001 | Job tracking | platform | active | v0.1 | audited | cleared to build | 3 | 2026-11-05 |
| 002 | Timber orders | platform | active | none | none | none | 0 | 2026-10-23 |

## Prior builds

None yet: no strand has closed.

## Stakeholders and decision roles

- The owner: approves spend and signs off.
- The workshop lead: runs the jobs from day to day.
- The office administrator: places the timber orders.

## Recent research

None.
