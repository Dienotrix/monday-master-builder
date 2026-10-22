---
schema: "client/2"
slug: ""
name: ""
account_kind: "own"                    # own | client | sandbox
build_target: "own-account"            # own-account | client-account | none
monday_account_id: "unbound"
monday_account_slug: "unbound"
monday_bound_user_id: "unbound"
monday_bound_at: "unbound"
monday_tier: "unknown"
monday_tier_read_at: "never"
monday_tier_source: "unread"           # preflight | client statement | unread
products_in_scope: "core"              # core | crm | service, comma-joined
client_workspaces: "none"
record_state: "active"                 # active | closing | closed
strands_open: "0"
strands_total: "0"
current_strand: "none"
live_build: "no"
lease: "none"                          # mirrors .work/lock.json
last_input: "none"
last_researched: "never"
# The three A11 fields stay open: each is asked once per client, at the moment it first matters.
transcripts_at_close: "unanswered"     # unanswered | exclude | archive
transcript_redaction: "unanswered"     # unanswered | none | offered-per-call | always
sample_data_in_account: "unanswered"   # unanswered | allowed | not-allowed | not-needed
ai_notice: "not-yet"                   # not-yet | not-needed | given YYYY-MM-DD
updated: ""
---
Internal: never client-facing

## Strand index

| strand | title | kind | state | version | version state | clearance | live objects | last activity |
|---|---|---|---|---|---|---|---|---|

## Prior builds

None yet: no strand has closed.
