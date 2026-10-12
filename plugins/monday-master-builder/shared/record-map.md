# Record map

The one home for the client record: its files, owners, budgets, schemas, vocabularies and every string the scripts look for. It carries A§7 of the architecture as amended (A12 to A17), the report and status shapes of A§5.4 and the type vocabulary of A§8.3. Skills, templates and scripts link here and never restate it; `record.py check` looks for the strings spelled here; `tools/lint_plugin.py` asserts the three pinned sections agree with the scripts that embed them. Paths are relative to the record unless said otherwise; every example value is fictional and every owner is a role.

## Kinds, budgets and the two levels

Kinds: **current** (rewritten under the sha guard), **history** (only grows, newest first), **snapshot** (frozen when written; corrections appended as dated notes), **raw** (saved once, never edited), **machine** (JSON, script-only), **scratch** (`.work/`, never archived). Budgets are `record.py check` warnings unless marked blocking. One record per client (A14): the folder `<MMB_HOME>/clients/<slug>/` holds the client — research, calls, documents, the meeting register, the account binding and what was read from the account, the live map, the lease and the record-level close-out. Each piece of work is a strand under `strands/<id>/` and holds what dies with it. Calls and documents stay at record level because one input routinely serves two strands and is never copied; `discovery.md` is strand level because each strand is graded on its own evidence, with carry-over between strands through `SUMMARY.md` only.

### Record level

| Path | Kind | Written by | Budget | Client-facing | Archived |
|---|---|---|---|---|---|
| `CLIENT.md` | current | engagement, plus one block per skill (owners below) | 160 lines, 10 KB | no | yes |
| `log.md` | history | all skills, through `record.py log`; every entry carries a strand position | live part 300 lines; rolls at each release and each strand close | no | yes |
| `meetings.md` | history | call-intake; engagement for a meeting never ingested | 150 lines | no | yes |
| `account.json` | machine, current | `ledger.py` only, except `guard_index.lease` (the lease primitives) | passes `ledger.py check` | no | yes |
| `research/sources.md` | history | engagement | none | no | yes |
| `research/<date>-brief.md`, `-deep-dive.md` | snapshot | engagement | 80 / 200 lines | no | yes |
| `research/updates.md` | history | engagement | live part 150 lines | no | yes |
| `calls/<date>-<type>.transcript.txt` | raw, sha recorded | call-intake, through `record.py add-transcript` | none | no | per `transcripts_at_close`, open with no default [A11-3] |
| `calls/<date>-<type>.md` | snapshot | call-intake | 120 lines | the marked client-safe block only | yes |
| `calls/<date>-<type>-prep.md` | snapshot | discovery-check | 80 lines | no | yes |
| `inputs/<date>-<title>.<ext>` | raw, sha recorded | call-intake, through `record.py add-document` (A16) | none | no | per `transcripts_at_close`, open with no default [A11-3]; the question covers documents |
| `inputs/<date>-<title>.md` | snapshot | call-intake, from the `document-summary.md` template | 120 lines | the marked client-safe block only | yes |
| `live/live-map.md` | current | `ledger.py live-map` at the end of a run; client-closeout at a strand close, through `ledger.py live-map set` | 250 lines, 16 KB; blocking at 400, which means grouping by strand | no | yes |
| `live/snapshots/<date>-<strand>.json` | machine | `ledger.py` | none | no | yes |
| `client-card.md`, `archive-handoff.md` | current, snapshot | client-closeout, record level | 1 page, 60 lines | no | yes |
| `.work/` | scratch | scripts | none | no | never |
| `.gitignore` | current | engagement at init | none | no | yes |

### Strand level, under `strands/<id>/`

| Path | Kind | Written by | Budget | Client-facing | Archived |
|---|---|---|---|---|---|
| `STRAND.md` | current | engagement, plus one block per skill (owners below) | 120 lines | no | yes |
| `SUMMARY.md` | current | `record.py strand summary`, with the user's yes | 80 lines; blocking at 120 | no | yes |
| `readiness.md` | current | build-readiness | 200 lines | no | yes |
| `discovery.md` (v2) | current | discovery-check (v2) | 300 lines | no | yes |
| `solution/blueprint.md` | current | solution-blueprint | 400 lines | sections 1 to 15 feed the bundle | yes; absent on a `non-platform` strand |
| `solution/scope.md` | current | solution-blueprint, on `non-platform` and `hybrid` strands only | 200 lines | the sections marked hand-off feed the package | yes |
| `solution/backlog.md` | current | solution-blueprint; call-intake inserts under Incoming | 150 lines | no | yes |
| `solution/allowlist.md` | current | solution-blueprint, with the user's OK per row | 80 lines | no | yes |
| `solution/build.json` | machine, current | `ledger.py` only | passes `ledger.py check` | no | yes; absent on a `non-platform` strand |
| `solution/open-questions.md` | current | discovery-check; call-intake inserts; solution-blueprint inserts a fork and marks `bypassed` | 150 lines | no | yes |
| `solution/dependencies.md` | current | solution-blueprint; call-intake inserts on a scoping or working-session call | 120 lines | no | yes |
| `solution/gaps.md` (v2) | current | call-intake after a demo; demo-script (v2) reads it | 150 lines | no | yes |
| `solution/structure-inventory.md` | current | call-intake after a reverse demo, a prototype review or a document; discovery-check grades its read-back | 200 lines | no | yes |
| `versions/<v>/version.md` | current while open, snapshot at release | engagement, account-build, solution-audit, call-intake, each its own sections | 150 lines | no | yes |
| `versions/<v>/blueprint-r<N>.md` | snapshot at approval | `record.py freeze --strand` | none | no | yes |
| `versions/<v>/audit.md`, `audit-2.md` | snapshot | solution-audit | 200 lines | no | yes |
| `versions/<v>/demo-script.md` (v2) | current until the demo, then snapshot | demo-script (v2) | 150 lines | no | yes |
| `versions/<v>/export.md` (v2-or-v3) | snapshot | client-sop (v2-or-v3) | 60 lines | no | yes |
| `versions/<v>/build.json`, `backlog.md`, `log.md`, `updates.md` | snapshot at release | `record.py version release --strand` | none | no | yes |
| `sop/SOP.md` (v2-or-v3) | current | client-sop (v2-or-v3) | table of contents | yes | yes |
| `sop/diagrams/<id>.flow.json`, `.mmd`, `.png`, `<id>-steps.md` (v2-or-v3) | current and derived | client-sop (v2-or-v3), `sop_tools.py` | 25 steps per flow | yes | yes |
| `drafts/<date>-recap.md` (v2), `<date>-admin-prerequisites.md` | snapshot | call-intake (the recap, v2), engagement (the prerequisites) | 40 / 60 lines | yes, as drafts the user sends | yes |
| `deliverables/<v>/*` (v2-or-v3) | snapshot | client-sop (v2-or-v3) | none | yes | yes |
| `deliverables/handoff/*` | snapshot | solution-blueprint, on a `non-platform` strand only, from the hand-off sections of `scope.md`, through the lint | none | yes | yes |
| `close-out.md` | snapshot | client-closeout, strand level | 60 lines | no | yes |
| `log.md` | snapshot | `record.py strand close`, the strand's rolled history | none | no | yes |

A row tagged v2 or v2-or-v3 belongs to a deferred layer (A19, plan decision D5): no v1 skill writes or reads the file, the row stays so the shape is kept, and the deferred files behind it live under `deferred/` in the repository, outside the shipped plugin. `readiness.md` takes the place of `discovery.md` in v1 wherever this file lists the strand files a chat reads or a strand holds (plan decision D1).

A `non-platform` strand has `STRAND.md`, `SUMMARY.md`, `discovery.md`, `solution/scope.md`, `solution/open-questions.md`, `solution/dependencies.md`, `drafts/`, `deliverables/handoff/` and `close-out.md`, and nothing under `versions/`, no `blueprint.md`, no `build.json` and no `sop/`; `record.py check` blocks on any of those appearing. Whole record: soft 4 MB excluding `calls/*.transcript.txt` and `.work/`, reported with the largest strands named.

`.work/` holds `lock.json` (the lease, `lock/2`), `history.json`, `cards-index.json` (hashed names only), `intake/` (the intake reports and set files), `migration-sources/` (source files for data migrations, which are not client documents and never enter `inputs/`), `claims-queue/`, `backup/`, `tools/<plugin-version>/`, and per strand `strands/<id>/` with `backup/`, `live-inventory.json`, `audit/`, `sop-inputs/`, `doc-chunks/`, `render/` and `build.json.bak`.

Outside the record, every path is resolved by `mmb_common.py` under one root, `MMB_HOME` (default `~/monday-builder`, overridden by the environment variable of that name, which the first-run walkthrough sets; this user's value is set locally and never written into the plugin, A22): `clients/<slug>/`, `cards/<slug>.md`, `clients-index.json` (sha256 of normalised client names only), `monday-knowledge/` (the overlay), `sandbox/`, `leases.json` (the best-effort cross-client lease line: hashed slug, strand, chat label, heartbeat), `claims/<slug>.md` (the per-account claims store, created by engagement at binding and written by call-intake and demo-script) and `personal-names-index.json` (the lint's name list). The user's own entries live under `local/` (A22, plan decision D11): `settings.json`; `sandbox-accounts.txt`, moved out of `shared/` with its syntax unchanged, one entry per line, `#` starting a comment, the fields separated by ` | ` in the order `kind | account_id | account_slug | workspace_id | label | note`, `kind` one of `sandbox` and `never-demo`, `workspace_id` one workspace id or `*` for the whole account, and the account host `<account_slug>.monday.com`, so a match is on the slug as well as the id; and `leak-terms.txt`, the per-user additions to the shipped list, where the user's firm name and its renderings live. Nothing user-specific ships in `shared/`. Probe S0-15 says whether a Cowork device shell reaches them; the working answer recorded in `tests/stage0/results.md` is no on every path, so each consumer applies its own fallback: the build chat asks the one cross-client question before its first write and logs the answer, the bundled knowledge applies and the briefing says so, the lint uses `.work/cards-index.json`, cards are written on the Mac, and a prep says the store was not read, drops every figure not approved in this chat and queues entries in `.work/claims-queue/`. Within-record contention depends on none of them.

## Naming and references

- **Slug**: lowercase ASCII with hyphens, at most 40 characters, legal suffixes dropped, never renamed; it is the folder, the Cowork Project and the archive repo name `client-<slug>` under the user's GitHub account.
- **Strand id**: `NNN-<topic>`, a zero-padded ordinal assigned by `record.py strand open`, monotonic per record, never reused and never renamed, plus a topic slug of at most 24 lowercase ASCII characters. The ordinal alone (`001`) is the **short id** used in log entries, lease records, element keys and version references; the full id is the folder name.
- **Dated files**: `YYYY-MM-DD-<topic>`, with `-2` for a second the same day. A transcript and its summary share one stem; a document and its snapshot share one stem. A package id is `pkg-YYYY-MM-DD`, with `-2` likewise.
- **Versions** are quoted strings (`"v0.1"`), unambiguous inside a strand. Every reference that leaves a strand folder — the live map, `account.json`, a log entry, another strand's change table, `SUMMARY.md` — is **fully qualified**: a version as `001/v0.1`, an element as `001:B1`, a frozen revision as `001/v0.1r4`; inside the strand's own ledger a frozen element reads `v0.1r4#B1`. `record.py check` blocks on a qualified reference that does not resolve.
- **Element keys**, bare inside a strand's own blueprint and ledger: `W1` workspace, `F1` folder, `B1` board, `B1.G2` group, `B1.C3` column, `B1.V1` view, `B1.FM1` form, `B1.SUB` subitems companion, `D1` doc, `DB1` dashboard, `DB1.W2` widget, `A1` automation, `PF1` portfolio, `PJ1` project, `SOP.doc` the doc copy, `U1` a UI step. A17 (2026-09-13) makes AI agents, AI columns and Vibe apps platform elements; their keys, templates and build stage arrive with the A17 design pass after the current stages and are not listed here yet.
- **Chat label**: minted by `record.py lease take` as `<surface>-<YYYYMMDD-HHMM>-<four random characters>`, surface `cowork` or `claude-code`, for example `cowork-20260915-1330-k7q2`; two takes on one day never collide. Links inside the record are relative only.

## The reading contract

A chat working strand N reads `CLIENT.md`, the newest `log.md` entries, its own `STRAND.md` and strand files, `live/live-map.md`, and the `SUMMARY.md` of any strand its work touches. It never reads another strand's `discovery.md`, `blueprint.md`, `build.json`, versions or calls unless the user names one, and the front door does not offer them. A new strand may also read `CLIENT.md` with `prior_builds`, `account.json`, `meetings.md`, `research/`, every call and document snapshot, and the account live, read-only. It does not write into another strand's folder, re-open another strand's version, edit a live-map row it did not build, or adopt another strand's unverified objects during recovery.

## Section owners and the strand index

`CLIENT.md` body blocks, one owner each: folder map (engagement); strand index (engagement); `prior_builds` (engagement, appended by a strand close: per strand the archive location inside the record, the live objects we own with fully qualified keys, the allowance they consume, the client's quoted change-cost expectation and the quoted do-not-disturb list, kept even when transcripts are not); stakeholders and decision roles in the client's words (discovery-check, record-wide); recent research (engagement); links. `STRAND.md` body blocks: headline and top pains in the client's words (call-intake); verdict and top gaps (discovery-check); version and state with the approved revision's short sha (account-build and solution-audit); next step (whichever skill set it); open commitments (call-intake); open overrides (any skill, append-only); open UI steps (account-build); links. A meeting chat rewrites its own block only, through `record.py guard`.

The strand index is one table with this header line and one row per strand; `record.py check` compares it with the folders on disk and blocks on a difference:

```
| strand | title | kind | state | version | version state | verdict | SOP behind | live objects | last activity |
| 001 | Service desk intake | platform | active | v0.1 | approved | nearly-ready | no | 0 | 2026-09-12 |
```

## Schemas

Front matter is flat `key: "value"` lines, every value quoted, parsed without PyYAML, with `schema` as the first field. A skill or script that meets a schema newer than its own refuses to write. Counts and flags in front matter are strings (`"1"`, `"yes"`); in JSON they are JSON types, and every monday id is a string.

### `client/2`, the front matter of `CLIENT.md`

Identity: `slug`, `name`, `account_kind` (`client` | `sandbox`). Binding, each `"unbound"` until `ledger.py bind` writes `account.json.account` and mirrors it here, a difference being blocking: `monday_account_id`, `monday_account_slug`, `monday_bound_user_id`, `monday_bound_at`. Tier: `monday_tier` (`"unknown"` until read), `monday_tier_read_at` (`"never"` until read), `monday_tier_source` (`preflight` | `client statement` | `unread`). Scope and state: `products_in_scope` (comma-joined from `core`, `crm`, `service`, the union across open strands), `record_state` (`active` | `closing` | `closed`), `strands_open`, `strands_total`, `current_strand` (a short id or `"none"`), `live_build` (`"no"` until anything of ours is live), `lease` (`"none"`, or `<strand> <version> (<chat label>)` mirroring the lock; a disagreement is blocking). Activity: `last_call` (`"none"` or a date), `last_researched` (`"never"` or a date), `updated` (ISO minute). The three open A11 fields stay at record level, asked once per client at the moment each first matters and never at setup: `transcripts_at_close` (`unanswered` | `exclude` | `archive`) and `transcript_redaction` (`unanswered` | `none` | `offered-per-call` | `always`), asked before the first real transcript or document is saved [A11-3]; `sample_data_in_account` (`unanswered` | `allowed` | `not-allowed`), asked before the first revision in any strand plans sample rows [A11-2]. Then `page_size` (`unset` | `letter` | `a4`, asked at the first export) and `ai_notice` (`not-yet` | `not-needed` | `given YYYY-MM-DD`). `record.py check` blocks on an A11 field left `unanswered` at the moment it matters — a build proposed in any strand, the first non-fixture transcript or document, a record bound for write probes [A11-1] — and is silent otherwise; it never fills one in.

### `strand/1`, the front matter of `STRAND.md`

`strand` (short id), `slug` (full id), `title`, `kind` (`platform` | `non-platform` | `hybrid`), `output_class` (`configured-structure` | `bespoke-code` | `hybrid`), `opened`, `opened_reason`, `state` (`active` | `paused` | `closed`), `stage` (platform and hybrid: `new` | `discovery` | `blueprint` | `building` | `demo` | `signed-off` | `expanding` | `closing` | `closed`; non-platform: `new` | `scoping` | `handed-off` | `closed`), `version` (`"none"` or `"v0.1"`), `version_state` (`none` or a state of the table below; always `none` on a non-platform strand), `discovery_verdict` (`not-graded` | `not-ready` | `nearly-ready` | `complete`; a v2 grading list, kept for the shape, while in v1 the clearance is `readiness.md`'s `verdict.cleared_for`, pinned below), `sop_behind` (`yes` | `no`), `next_step` (date, time, what, and `(owner: the user)` or another role), `depends_on` (`none` or short ids), `summary_current_to` (`none` or a version), `closed` (`none` or a date), `updated`. Kind is set at `record.py strand open` from the user's answer and recorded with its reason, and changed only through `record.py strand kind` while the strand has no versions, with a `strand` log entry. `non-platform` means work outside monday — an application, a script, an integration against a third-party system — recorded and handed off, never designed or built (A13 as narrowed by A17). `hybrid` carries both `blueprint.md` and `scope.md`, the boundary line in each and no element in both.

### `summary/1`, `scope/1`, `version/1` and the rest

`SUMMARY.md` (`summary/1`): `strand`, `title`, `kind`, `versions`, `closed`, `summary_current_to`, `budget_lines`; then nine blocks in order — what the work was and why it opened; the pains it served, one line each, no quote over seven words; what was built, as qualified keys to monday ids grouped by board, each pointing at its live-map row; what the client confirmed, as pointers to the call summaries; what must not be broken and where that came from; the client's words on our cost of change; ownership and switch-off status at close; backlog seeds carried forward; dates opened, released and closed. On a non-platform strand the built block reads "nothing built inside the product". `scope.md` (`scope/1`): `strand`, `kind`, `boundary` (hybrid only), `updated`; seven parts in order — what exists and who built it; the scope as a delta (inherited, in scope, client-side change, access unlock); open technical questions as pointers into `open-questions.md`; external dependencies as pointers into `dependencies.md`; access needed, an owner each side and a state per item; next steps with owners and dates; process rows for human-in-the-loop work (system, owner, mode, acceptance check), never promoted into a flow spec — and then the fixed final section, which `record.py check` and `tools/lint_plugin.py` look for verbatim:

> Building this work happens outside this product. This record holds its scope, open questions, dependencies, access needs and next steps; it does not design or build it.

`version.md` (`version/1`): `strand`, `version`, `qualified_version`, `state`, `revision`, `sha256`, `demo_script_ready`, `sop_sections_confirmed`, `opened`, `released`. Every other Markdown file under the record opens with `schema: "<file-stem>/1"` — `call-summary/1`, `document-summary/1`, `discovery/1`, `blueprint/1`, `meetings/1`, `log/1` and so on — and every internal template opens with the line "Internal: never client-facing".

### `account/1`, `account.json` (record level, `ledger.py` only)

`schema`, `client_slug`, `updated_at`, and these blocks. **`account`**: `id`, `slug`, `name`, `kind` (`client` | `sandbox`), `tier`, `bound_user_id`, `builder_role`, `products[]` of `{id, kind}` with kinds `core`, `crm`, `service`; each `"unbound"` from the template until `ledger.py bind`. **`api`**: `connector_ring` and `execute_code_ring` as `"<kind> <version>"` strings, for example `"release_candidate 2026-10"`, and `read_at`. **`change_check`**: `at`, `for_strand`, `ring`, `versions_seen[]`, `release_notes_since` (`"<date> (read)"` | `"not-read"`), `roster_diff {added, removed, renamed}`, `schema_diff[]`, `verdict`, `approved_by_user` (null or a log reference). **`native_map`**: `crm.<entity>`, `service.<entity>` and `portfolio.<key>`, each `{board_id, rule, confidence, signals[], lineage {chain[], resolved, note}, confirmed_by_user}`, with `family` on a Service entity and `projects[]` of `{tasks_board_id, overview_board_id, overview_state, planner_board_id, folder_id, connected}` on a portfolio. `rule` is one of the classifying rules `N0`, `N1a`, `N1b`, `N2` to `N11` (with `N12` recording attributes beside them), `R0` to `R11` and `C1` to `C4`; `confidence` is `high` | `medium` | `low`, and nothing below `high` is ever `confirmed_by_user: true`. Probe P-13 (2026-09-12) found no native flag on `Board.columns_namespace` or `Column.capabilities`, so these rules stand as written. **`guard_index`**: `captured_at`, `ring`, `product_workspaces {workspace id: kind}`, `account_products[]` of `{id, kind, default_workspace_id}`, `native_board_index {board id: "product/entity"}`, `native_board_ids_by_entity`, `template_source_ids[]`, `unreadable_intermediate_ids[]`, `template_view_ids[]`, `reserved_column_ids {entity: {ids[], threshold}, blank_default_exclusions[]}`, `native_default_names_and_terminology[]`, `portal_object_ids {active[], archived[]}`, `build_targets_by_strand {short id: {workspace_ids[], folder_ids[]}}`, `lease {strand, epoch, chat_label, heartbeat_at}` (the mirror the lease primitives write; `strand` null when none is held), `record_provenance {coverage, staleness_budget_days}`. Reserved ids and names detect and never protect: raw `create_column` honours any explicit id, a reserved CRM id on an ordinary board included, with no error (P-14, 2026-09-12), so protection is by `native_board_index` and lineage alone. **`live_objects`**: keyed by qualified element key, `{monday_id, kind, name_at_build, owner_strand, introduced_in, state, constraint, constraint_source, digest, last_verified, dependants[]}`, the machine half of the live map, written in the same step. **`prior_builds[]`**: `{strand, closed, summary}`.

### `build/2`, `strands/<id>/solution/build.json` (platform and hybrid strands, `ledger.py` only)

`schema`, `client_slug`, `strand`, `account_ref` (`"../../../account.json"`), `account_id_at_bind` (a difference from `account.json.account.id` is blocking), `lease_epoch_at_run`, `reads_live[]` (qualified keys), `updated_at`, and these blocks. **`approvals[]`**: `version`, `qualified_version`, `revision`, `frozen_file`, `sha256`, `approved_at`, `approved_words`, `approved_in_chat`, `element_count`, `irreversible_listed[]`, `automations_listed[]`, `live_objects_touched[]` of `{key, constraint}`. **`preflight`**: `at`, `version`, `daily_total`, `used_today`, `client_reserve`, `estimated_calls [low, high]`, `roster_ok`, `stale_gotchas[]`, `findings[]`. **`runs[]`**: `id` (`run-YYYY-MM-DD-N`), `version`, `kind` (`build` | `doc-copy`), `chat_label`, `lease_epoch`, `started_at`, `heartbeat_at`, `ended_at`, `state` (`running` | `ended` | `interrupted`), `calls_estimated`, `calls_used`, `account_checks[]` of `{at, before, result}`. **`objects`**, keyed by bare element key: `type`, `id`, `name`, `parent_key`, `parent_id`, `origin` (`created` | `pre-existing-modified` | `pre-existing-referenced` | `other-strand-modified`; the second and the fourth require `prior_state`, and the fourth also `source_strand`, an `approval_ref` and a live-map constraint other than `do-not-change`), `source_strand`, `introduced_in`, `changed_in[]`, `state`, `status` (`planned` → `attempting` → `written` → `verified` | `mismatch`, and from any state to `departed` | `removed`; other transitions refused), `attempt {run_id, started_at, intent_digest}`, `verify {read, at, result, digest, note}` with `result` `match` | `mismatch` | `not-checkable` | `needs-user` — board-level `permissions` reads back through the field [doc, P-18], column and item-level permissions are `not-checkable` — `creator_user_id`, `owner_user_ids[]`, `irreversible`, `sample_data`, `approval_ref` (required on an irreversible, automation or removed row), `notifies[]`, `companions {subitems_board_id, doc_container_board_id, form_board_id, overview_board_id, planner_board_id}`, `role`, `prior_state`, `url`, `blueprint_ref`. A widget keeps the id from its create response, because no read returns one. **`irreversible_yes[]`**: `{key, what, at, log_ref}`. **`departures[]`**: `{key, version, what, error_code, attempts[], decision}`. **`ui_steps[]`**: `{key, what, owner, target_version, status}` with `status` `open` | `done`.

### `live-map/1`, `live/live-map.md`

Front matter `schema`, `client`, `rows`, `updated`. One table with this header line and one row per verified live object, mirrored field for field by `account.json.live_objects`; a row present on one side and absent on the other is blocking:

```
| key | monday id | kind | built by | state | constraint | source | dependants | last verified |
| 001:B1 | 1234567890 | board | 001/v0.1 | active | change-with-own-yes | calls/2026-09-10-demo.md@00:41:12 | 001:A1, 001:B1.V1 | 2026-09-15 |
```

`kind` is any kind of the element-key list; `built by` is a qualified version, or `client` or `native`; `state` is `active` | `archived` | `removed-by-platform`; `constraint` is `do-not-change` | `change-with-own-yes` | `free`; `source` is a client quote with its call location, a user decision with its log reference, `pending strand close` (the interim value `ledger.py run end` writes) or `migration default, not confirmed with the client`.

### `lock/2`, `.work/lock.json`, the lease

Written only by the lease primitives in `mmb_common.py`, which `record.py lease` and `ledger.py` call; a take, a refresh, a release and a break are state changes and the file is never deleted. Fields: `schema`, `kind` (`build`), `epoch` (an integer, `0` before the first take, incremented on every take and every break), `strand`, `strand_title`, `version`, `run_id`, `chat_label`, `surface`, `taken_at`, `heartbeat_at`, `state` (`none` | `held` | `released` | `broken`), `history[]`. A heartbeat older than 60 minutes reads stale; nothing expires on its own. A history entry is appended on a take, a release, a break and a park, never on a refresh: `{event, at, epoch, strand, version, chat_label, run_id, by, choice, reconcile, note}` with `event` `taken` | `released` | `broken` | `parked`, `by` the chat label acting, `choice` `resume` | `park` on a break and null otherwise, and `reconcile` the classify-only summary on a break. The two mirrors, `lease` in `CLIENT.md` and `account.json.guard_index.lease`, are written in the same call, and `record.py check` blocks when either disagrees with the lock.

### `record.py status --json`

One JSON object, the front door's one read and the graders' too; front-matter values come back as the strings they are, computed values as JSON types:

```
{"schema": "status/1", "generated_at": "...", "plugin_version": "0.1.0", "record_schema": "client/2", "migration_needed": false,
 "record": {every client/2 field by name},
 "strands": [{every strand/1 field by name, "qualified_version": "001/v0.1", "open_versions": ["v0.1"], "live_objects": 0,
              "last_activity": "2026-09-12", "run": {"id": "...", "state": "running", "heartbeat_at": "...", "heartbeat_age_minutes": 4}}],
 "lease": {"held": true, "state": "held", "epoch": 7, "strand": "001", "strand_title": "...", "version": "v0.1", "chat_label": "...",
           "surface": "cowork", "run_id": "...", "taken_at": "...", "heartbeat_at": "...", "heartbeat_age_minutes": 22, "fresh": true},
 "interrupted": [{"strand": "001", "run_id": "...", "version": "v0.1"}],
 "findings": {"blocking": [{"file": "...", "field": "...", "problem": "...", "expected": "..."}], "warnings": []}}
```

`run` is null when the strand has no open run. `--strand <id>` returns the same object with one entry in `strands`. `lease.held` is false, with `state` `none`, `released` or `broken` and the last `epoch`, when nothing is held.

## Version states

Per strand; a `non-platform` strand has none. `planned` → `approved` → `building` → `built` → `audited` → `demoed` → `released`, with `fixing` between an audit that fails and the retry. The files `record.py check` requires, relative to the strand: `planned`, `solution/blueprint.md` and `versions/<v>/version.md` with scope and revision; `approved`, a `blueprint-r<N>.md` whose sha256 matches `version.md` and `build.json.approvals`, and an `approval` log entry; `building`, a `runs[]` entry in `running` carrying the lease epoch, the lock held by this strand, `change_check` in `account.json` for this strand and `preflight` present; `built`, the build section of `version.md` and a `build` log entry; `fixing`, `audit.md` with findings; `audited`, `audit.md` with the write-detection result and the documents appendix; `demoed`, the frozen `demo-script.md`, the demo call summary and the reactions in `version.md`; `released`, the frozen `build.json`, `backlog.md`, `log.md` and `updates.md`, the condensed current files and, for v1.0, a sign-off block. A missing file blocks the release; `presented` in `export.md` is accepted for a v0.x export and blocks v1.0.

## The log

`log.md` (`log/1`, front matter `schema` and `client`) is one record-wide history, newest first, entries never edited, written only by `record.py log`, which re-reads the file and inserts under the header. An entry is this header line, then at most five lines:

```
## YYYY-MM-DD HH:MM · <strand or -> · <type> · <version or -> · <key or chat label>
```

The strand position is the short id, or `-` for a record-level event (a binding, a research pass, a lease break, a record close); the version is bare because the strand position qualifies it. Types: `created`, `binding`, `research`, `call`, `document`, `conflict`, `discovery`, `override`, `superseded` (only the same commitment from the same speaker inside one call; any other pair is a `conflict`, with no arithmetic between the two), `scope`, `blueprint`, `approval`, `change-check`, `preflight`, `build`, `departure`, `irreversible`, `automation`, `write-failed`, `recovery`, `audit`, `write-detected`, `demo`, `sop`, `export`, `doc-copy`, `deliverable`, `sent`, `lint`, `version`, `release`, `strand`, `lease`, `live-map`, `summary`, `api-surprise`, `decision`, `commitment`, `migration`, `closeout`, `archive`. At a strand close that strand's entries below the live part move to `strands/<id>/log.md` with one pointer entry left behind, and `check` verifies the roll by hashing the moved entries.

## Evidence markers and the citation contract

| Marker | Meaning | Travels with it | Counts toward the rubric |
|---|---|---|---|
| `[Q]` | client quote, verbatim, never tidied; intake `certain`, or `probable` with the qualifier travelling with it | speaker name and role, side, location | yes, client side only |
| `[Q?]` | quote with an unclear speaker (intake `uncertain`) | as `[Q]`, plus a note | Partial until the user confirms |
| `[Q/side]` | side-only quote, speaker not resolvable (intake `unattributable`, or a segment of a composite block) | the side, the unit or block range, a note | Partial, never Missing |
| `[Q/recon]` | a sentence assembled from several units after boundary de-duplication | as `[Q]`, plus every unit number | as the weakest unit it rests on |
| `[Q/doc]` | a verbatim extract from a client document (A16) | the document, its section or page, the author by role where known, the document's date and status | yes for current-state and requirements criteria; cost, why-now, decision-process and next-step only where stated explicitly |
| `[X]` | quarantined: spoken inside a demonstration frame that is ours with a screen shared, or under a hypothetical marker | the frame's location and the reason | never |
| `[E]` | external fact from a dated source | source key `S#` from the register | no |
| `[I]` | inference | its basis and a confidence word | no; it can only shape a question |

Locations follow the file's own grammar: `@HH:MM:SS`, `cue 82`, `cues 82-85` for a merged run, `L142` or `L142-144`, `paragraph 75`; a document extract cites `inputs/<stem>.md §3.2` or `p.4`. Markers live in `research/`, `calls/`, `inputs/`, `discovery.md` and the internal parts of the blueprint; `leak_lint.py` blocks all eight in `sop/`, `drafts/`, `deliverables/` and every monday payload. Four tiers: attributed (`[Q]`), attributed with a qualifier (`probable`, or `[Q?]`), side-only (`[Q/side]`), refuse; a `[Q/doc]` whose author is known is attributed, otherwise "the client's document", one step below. Refusal is mandatory for a sub-clause fragment, a re-joined sentence whose load-bearing half changed speaker, a quote resting on an assembled figure, a second-hand re-quote of another call, and any quote whose first or last word sits under another speaker's label — the speaker boundary, never the turn boundary.

## Calls, documents and the strand files

A call summary's front matter carries the type-header fields of the pinned vocabulary below and the call-set fields: `sequence` (an integer string from date and internal evidence, never a file name; `"unordered"` until the user confirms a set's order), `call_type` (one of the thirteen labels), `package` (`none` or a package id), `provenance` (`first-hand` | `handed-over`), `handed_over_by` (a role, or `none`), `attendees` (roles by side, `"client: <role>, <role>; ours: the user"`), `strands` (short ids, comma-joined, or `unassigned` until the front door routes it). A document snapshot (`document-summary/1`) carries `input_kind: "document"`, `title`, `source` (the raw file's stem), `sha256`, `author`, `document_date` and `status` (`unknown` | `draft` | `approved` | `current-practice` | `desired-state`, each `unknown` until the document says), `sequence`, `provenance`, `handed_over_by`, `strands`, `updated`; a document carries no type header, adds no `meetings.md` line, and its intake is a `document` log entry. `meetings.md` holds one line per meeting, a package block with its `second-hand` figures, and the who-has-seen-what block. A conflict is kept as both statements in the serving strand's `open-questions.md` as kind `conflict`, with a `conflict` log entry and no recency rule.

Strand-file vocabularies the scripts and graders read: `open-questions.md` kinds `conflict` | `technical` | `access` | `commercial` | `policy` | `ask`, with the state `bypassed`; `gaps.md` states (v2) `shown` | `promised` | `answered-in-words` | `deferred` | `unaddressed`; `structure-inventory.md` source marks `spoken` | `observed` | `documented`, class `current state` | `current manual artefact` | `client-built prototype`, and the states `proposed-and-displaced` and `compound show`; `discovery.md` grades (v2) `met` | `partial` | `missing` | `advisory`, with `met-with-residual`, the `asked` flag and `not-obtainable`, whose definitions `sales-method.md`, now under `deferred/shared/`, owns; a recap draft's `status` (v2) is `draft` | `sent`. The v1 vocabulary of `readiness.md` is pinned below.

## Pinned: readiness

The v1 check's one output, `readiness/1`: the block `readiness`, kept in the strand as `readiness.md`, written by build-readiness, and the field of the same name that closes every fixture answer key. The field names and value sets below are final (build-readiness-spec §7; the brief of the fixture fix pass of 2026-10-13 fixed them and the twenty-five keys carry them). In a key the block is JSON; in `readiness.md` it opens with `schema: "readiness/1"` and carries the same parts, in this order, under the same names. No script embeds this section yet, so the lint does not check it against one; when build-readiness arrives, its script embeds the backticked tokens between pinned markers the way the two sections below are embedded.

| Field | Shape |
|---|---|
| `schema` | `readiness/1` |
| `note` | one or two sentences: what the block was derived from, and that structure assertions stay provisional until the user has seen a real build. Where a key's v2 verdict disagrees with the clearance, one more sentence says so; the v2 field is never changed |
| `pains[]` | `id` (the key's P-numbering; `P1.1`, `P1.2` where one theme holds several quotes), `quote`, `location`, `speaker_role`, `stated_or_excavated` (`stated` or `excavated`), `outcome` (the wanted outcome in the client's words, or null) |
| `signals[]` | `quote`, `location`, `pain` (a pain id), `not_confirmed` (what our side never confirmed); carried forward, never counted as evidence |
| `entities[]` | `name`, `parent` (an entity name or null), `moves_independently` (`yes`, `no` or `unknown`), `shared_resource` (true or false: booked or reused across jobs), `goes_stale` (true or false: produced from data that later changes), `source` (`spoken`, `observed`, `documented` or `assumed`), `evidence` (a location or null) |
| `structure` | `products[]` (`Work Management`, `CRM`, `Service`), `build_target` (`own-account` or `client-account`), `build_target_reason`, `workspaces[]` (one per product, named for the client, as `<Client> – CRM`), `native_reuse` (which native boards, or that there is no CRM or Service entity), `leanings[]`, `patterns[]`, `element_per_pain[]` |
| `structure.leanings[]` | `question`, `option`, `quotes[]`, `locations[]`, `condition` (the live condition that settles it), `pattern` (one of the seven sweep patterns, in prose, or `fork` for a disagreement between two client speakers) |
| `structure.patterns[]` | one line per pattern applied, in the form `parent-row-with-roll-up: <parent> with <children> as child rows, <roll-up> on the parent` |
| `structure.element_per_pain[]` | `pain` (a pain id), `element`, `verdict` (`fixes`, `copies-today's-tool` or `none`); one row per pain id, and `none` is a finding that stays visible |
| `existing` | `account` (what the record says exists, or `unknown, no account bound`), `incumbents[]` of `system`, `authority` (`stays system of record for: … ; follower for: …`), `evidence` (a location or null) |
| `assumptions[]` | `statement`, `question` (the question that would replace it) |
| `unmet_needs[]` | `need`, `clock` (or null), `why_not_met` |
| `ai_opportunities[]` | `pain_or_need` (a pain id or a need), `kind` (`agent`, `ai_column`, `workflow`, `vibe_app` or `sequence`), `round` (`1` only when the client asked for AI or workflows on the call, otherwise `2`), `probe_basis` (`P-19`, `P-20`, `P-21` or `unprobed`), `idea` (one sentence) |
| `verdict` | `cleared_for` (`build`, `build-generic` or `none`), `conditions[]` (always the approval stop, and the A11 question that first matters where one does), `reason` (one sentence) |
| `questions[]` | at most five, ordered: `text`, `kind` (`read-back` where a signal exists, `discovery` otherwise), `role` (who can answer), `known` (what the record already holds) |

`cleared_for` is the machine value; the check says it to the user as a human string, and `STRAND.md` and the approval card carry the string. `build` is `cleared to build`: at least one pain with an entity and a wanted outcome, the product chosen, the structure stated with its leanings, the build target named. `build-generic` is `cleared to build, generic`: the same, with the structure resting mostly on assumptions; the build goes ahead as a generalised version, the assumptions list is the agenda for the next contact, and the approval card's "what this build rests on" section is the user's yes to them. `none` is `not yet`: no pain or entity firm enough to build on; the questions are the next step. solution-blueprint reads the machine value, and `none` stops the blueprint unless the user overrides with a reason, logged as `override` (plan decisions D1 and D2). No grade, R-number, gate name or sales verdict appears in the block; those lists are v2 and are tagged so above.

## Pinned: call-type-vocabulary

The header on every call summary, proposed by transcript_prep.py, confirmed or dismissed by the user, read by discovery-check and the graders. Every backticked token in this section, and only these, is embedded between the pinned markers of scripts/transcript_prep.py, and tools/lint_plugin.py asserts the two agree; the intake skill's call-types.md links here for the signals' order and routing and restates nothing.

| Field | Values | Fallback when unresolved: fewest rights, most evidence |
|---|---|---|
| `seat` | `partner-led`, `co-sell`, `vendor-led`, `client-led` | `not-ours`, the seat is not ours to control |
| `relationship` | `new-logo`, `existing-client`, `third-party-account` | `new-logo` |
| `direction` (of show) | `we-show`, `they-show-current`, `they-show-candidate`, `no-show` | `no-show`, no screen |
| `output_class` | `configured-structure`, `bespoke-code`, `hybrid` | `bespoke-code`, so nothing may be claimed buildable |
| `room_shape` (modifier) | `one-to-one`, `small-group`, `large-room` | `large-room` |
| `money_live` (modifier) | `not-live`, `live-approver-present`, `live-approver-absent` | `live-approver-absent` |

A§8.3 step 5 names the same values as prose (new logo, nobody shows, configured structure); the hyphenated token is the machine form the header, the scripts and the calibration keys carry, and for the output class it is the spelling A§7.7 already gives the strand. The two modifiers' values are pinned here because the design names the modifiers without values: room shape counts the client attendees, and a group, the small-group value, is two or more client attendees, below the large-room threshold, so a call with two client attendees is small-group (widened from "more than two" by plan decision D3 in the fixture fix pass); money is live when a commercial marker is spoken, split by whether the person who approves spend is in the room (method §4.10).

Each field is written as its value followed by its state, `detected`, `proposed` or `confirmed`; an unresolved field is written `unresolved`, and the header lists its `candidates` and the fallback applied. A call whose type changes mid-way carries `segments`, each with its location, the `event` at it and the values after it. The five signals are recorded under `signals` in priority order, `screen-deixis`, `same-side-direction` (provisional on one observation), `agenda`, `output-markers` and `commercial-markers`, each with the `quote` and the unit that produced it. Detection proposes and never decides; an unresolved dimension demotes every type-specific rubric rule to advisory and never a door.

The thirteen labels, the `call_type` value, the type stem in a call's file names and the routing key of A§8.3 step 7: `intro`, `discovery`, `reverse-demo`, `prototype-review`, `demo`, `scoping`, `working-session`, `pricing`, `call-review`, `expansion`, `sign-off`, `check-in`, `support`.

## Pinned: permitted-constants

The only constants transcript_measure.py may hold. Every threshold it applies to a unit is derived from the file's own distribution at these ranks, floored by these absolutes and softened by these bands, so no constant expresses turn grammar directly: there is no word count that makes a fragment and no gap that makes a wedge. Every backticked token in this section is embedded between the script's pinned markers, and the lint asserts agreement; the values applied travel in the intake report.

| Constant | Value | Class | What it governs |
|---|---|---|---|
| `min_units` | `80` | minimum unit count | with fewer raw units than this nothing is derived: the floors apply alone and the report says so (the short reviewed fixture has 75) |
| `p_short` | `0.1` | percentile rank | words per unit at this rank of the file's distribution: the short-unit threshold |
| `p_long` | `0.9` | percentile rank | words per unit, and seconds per unit where end times exist, at this rank: the long-unit thresholds |
| `p_gap` | `0.9` | percentile rank | the inter-unit gap at this rank: the wide-gap threshold |
| `p_rate` | `0.95` | percentile rank | words per second at this rank, where end times exist: the implausible-rate threshold |
| `floor_short_words` | `3` | absolute floor | the short-unit threshold never falls below it |
| `floor_long_words` | `60` | absolute floor | the long-unit word threshold never falls below it |
| `floor_long_seconds` | `45` | absolute floor | the long-unit seconds threshold never falls below it |
| `floor_gap_seconds` | `2` | absolute floor | the wide-gap threshold never falls below it |
| `band_units` | `0.15` | no-action band width | the fraction either side of a derived word or seconds threshold inside which a unit is reported borderline and no detector fires on it |
| `band_gaps` | `0.15` | no-action band width | the same, around the wide-gap threshold |
| `composite_cutoff` | `0.03` | few-percent cutoff | the share of words inside composite blocks above which talk share is refused and the pass is marked cautious |

## `intake-report/1`

Written by `transcript_measure.py prep`, or by its `document` subcommand for a client document, to `.work/intake/<stem>.report.json`; every subcommand of `transcript_prep.py`, `call-intake` and the summariser read it and never the raw file; a field outside this list fails validation. Blocks, in order:

```
schema "intake-report/1" · input_kind transcript | document · stem · source (record-relative path) · sha256 · call_date ("unknown" when absent) · written_at · plugin_version
measurements: family cue | block · dialect · attribution voice-span | label-prefix | none · end_times · timestamp_shape · label_position · label_granularity · header_present · line_endings · unit_count · word_count · max_unit_seconds · max_unit_words · gaps {p10, p50, p90, max} · terminal_punctuation_share · defect_density {short_turn_share, lowercase_start_share, no_terminal_share, colliding_timestamps, adjacent_same_label} · below_min_units
constants: {each permitted constant by name, with the value applied} · derived: {short_unit_words, long_unit_words, long_unit_seconds, wide_gap_seconds, implausible_rate_wps}, or null below the minimum unit count
roster[]: label · name · side ours | client | third-party | unknown · role_claimed · role_observed · source header | narrated | observed · listed · spoke
aliases: state proposed | confirmed · map[]: {from, to, basis, unit}
units[]: n · start · end · label · speaker · side · text · location (the file's own grammar) · merged_from[] · confidence certain | probable | uncertain | unattributable · tier attributed | qualified | side-only | refuse · voice_bank · flags[]
detectors: composite fired | no-unit-qualified | nothing-found · wedge fired | no-unit-qualified | nothing-found
composite_blocks[]: units[] · signals[] · segments[]: {from_unit, to_unit, side, label_candidate}; a segment that cannot be split confidently is speaker-unresolved
wedges[]: {unit, reason} · colliding_timestamps[]: {units[]} · coerced_names[]: {unit, from, to, basis} · rejoined_numbers[]: {unit, from, to, confidence} · quarantined_spans[]: {units[], frame, reason} · name_noise[]: {text, unit}
document (a document only): format · pages · sections · author · document_date · status · section_map[]: {anchor, title, page, kind current-state | desired-state | unknown} · text_by_anchor {anchor: text} · diagrams[]: {page, note}
type_header (added by transcript_prep.py type; absent on a document): the pinned header fields, plus signals[]: {signal, quote, unit, provisional}
```

Unit flags: `fragment-head`, `fragment-tail`, `boundary-artifact`, `owner-unresolved`, `backchannel-stripped`, `qa-answer`, `composite-candidate`, `wedge`, `timestamp-collision`, `coerced-name`, `rejoined-number`, `unit-unresolved`, `hedged-number`, `asr-suspect`, `screen-narration`, `small-talk`, `quarantined`, `rate-implausible`, `speaker-unresolved`. `transcript_prep.py set` writes `.work/intake/<package>.set.json` (`intake-set/1`): `files[]` in date order with `ties[]`, `attendees` per file, `figure_pairs[]` across files and `second_hand[]`; the internal-evidence adjustments to that order are the intake skill's to propose with quotes and the user's to confirm.

## Scripts the record copies

`record.py tools-check` compares each script copied into `.work/tools/<plugin-version>/` against this table and refuses a mismatch. The version is the one in `plugin.json`; the release step (`tools/release.sh`) rewrites the rows at every release, and a row reading `pending` means the script is unreleased and only the version is compared.

| Plugin version | Script | sha256 |
|---|---|---|
| `0.1.0` | `mmb_common.py`, `record.py`, `ledger.py`, `leak_lint.py`, `transcript_measure.py`, `transcript_prep.py`, `demo_check.py`, `sop_tools.py`, `gql_guard.py`, `archive_check.py` | pending |

## Migration

`record.py migrate --dry-run` prints every move; `migrate` refuses unless `check` passes before and after. It creates `strands/001-<topic>/` (default topic `initial-engagement`, a better one asked for), moves `discovery.md`, `solution/`, `versions/`, `sop/`, `drafts/` and `deliverables/` into it unchanged so that `001/v0.1` is the old `v0.1`, splits `build.json` into `account.json` and the strand's `build/2` ledger stamping `strand` and `account_ref`, writes `STRAND.md` from the fields removed from `CLIENT.md`, rewrites `CLIENT.md` with the strand index and an empty `prior_builds`, builds the live map from every verified active object at `change-with-own-yes` with the migration-default source, and rewrites every log header to carry `001` in the strand position — the one edit to history, recorded as a `migration` entry with the count of rewritten headers and their hashes before and after. A record whose schema is newer than the plugin refuses writes.
