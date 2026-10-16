# Synthetic monday reads for `ledger.py`

Internal test data: never client-facing. These files are the reads that `ledger.py classify`, `native-map`, `snapshot`, `compare` and `reconcile` are graded against in stage 2 (WP3). They are **synthetic** (amendment A29): built from the probe findings in `plugins/monday-master-builder/shared/` (`native-objects.md`, `monday-gotchas.md`), from monday's published GraphQL schema for API version 2026-10 (read with no account on 2026-10-16), and, for the agent, Vibe app and workflow shapes, from the connector probes P-19 to P-21. No monday account was read or written to make them. Every reads file says so in its `fixture` header: `synthetic: true`, the ring it models (`release_candidate 2026-10`), its sources, and `confirmed_by_capture: null`.

`tests/unit/test_snapshots.py` is their self-test. It imports nothing from `ledger.py`.

## Files

| File | What it is |
|---|---|
| `identification.reads.json` | the identification sweep: two core workspaces, 22 boards, every page of NO 2.6 plus the side reads (workspaces, account products, docs, workflow objects, the portfolio's items) |
| `identification.expected.json` | its answer key: one entry per board, the totals per class, the projects (C1 to C4) |
| `native.reads.json` | the native sweep: CRM, Service, core and test workspaces, 59 boards, two lineage-hop pages, one of which drops three ids |
| `native.expected.json` | its answer key, with `native_board_index` and `portal_object_ids` as `native-map` stores them |
| `compare/before.read.json`, `compare/after.read.json` | two snapshot reads in the shape `snapshot --read` takes (W74) |
| `compare/ledger-state.json` | strand 001's rows and the record's `live_objects` the snapshots are scoped against |
| `compare/appendix.md` | an audit file whose `## Documents appendix` holds seven planted documents |
| `compare/expected.json` | the scope, the flags, the changed-outside row, the controls that must not flag, the document verdicts, the exit code |
| `reconcile/live-inventory.json` | a `live-inventory/1` file (W70) |
| `reconcile/ledger-state.json` | the holder strand's rows, runs, lock and the account fields `reconcile` reads |
| `reconcile/expected.json` | the full run's elements in output order, and the classify-only run from sibling strand 002 |
| `schema-fields.json` | every response path the reads carry, mapped to the schema `Type.field` it resolves to, and the connector shapes the schema cannot describe |
| `.gitattributes` | keeps every file here LF on every system |

## Shapes

A reads file is `{"fixture", "captured_at", "pages"}`; each page is `{"page", "kind", "request": {"document", "variables"}, "response": {"data"}, "requested_ids", "returned_ids", "missing_ids"}` (W01). `missing_ids` is always the requested ids minus the returned ids, in request order (G-92). Page kinds: `boards_sweep` (NO 2.6 by workspace, `requested_ids` empty; each swept workspace ends on a page with `boards: []`), `boards_ids` (NO 2.6 by ids, for lineage hops), `workspaces`, `account_products`, `docs`, `workflow_objects` (one page per state, W79) and `portfolio_items` (W80). For the side reads that are not read by id (`account_products`, `docs`, `workflow_objects`), `requested_ids` is empty and `returned_ids` holds the ids returned, as for a sweep.

An answer key is W01's: `board_count`, `boards`, `totals`, `limits`, `projects`, `reports`, `sweep_complete`, `unreadable_ids`. A board entry holds `case`, `class`, `rule`, `attributes`, `confidence`, `signals` (a set), `lineage`, `review`, `limits` and `models`. `totals` counts every board not in `limits`; `board_count` is the sum of `totals` plus the length of `limits`. A `projects` entry also carries `note`, which names the overview of an unconnected project (NO 7.3).

The answer keys are written by hand from NO 5's rules, in W81's order; the derivation of every board is in the build notes. No answer appears in a reads file, so a scrubbed capture can replace a reads file one for one without touching its key.

### Signal tokens

`signals` lists the facts the rules read, compared as a set:

| Token | When it is present |
|---|---|
| `type:<type>` | `type` is not `board` |
| `key:<key>` | `object_type_unique_key` is not null |
| `N0:<kind>` | always: the workspace's `account_product.kind` (`none` when null) |
| `lineage:<template id>` | the lineage walk ends `RESOLVED_TEMPLATE`, in any catalogue (NO 3.1, 4.1, 7.2) |
| `view:<template view id>` | a view's `source_view_id` is a template view id (NO 3.2, 4.2) |
| `reserved:<product>/<entity>` | that entity's reserved ids meet its threshold; Quotes & Invoices only with lineage, a template view or terminology `Document #` |
| `CRM_RELATION_MARK`, `CRM_FEATURE_MARK`, `CRM_MIRROR_MARK`, `V2_OPPS_FINGERPRINT`, `SERVICE_SLA_MARK` | the marks of NO 2.4 |
| `portal_objects:<state>` | the board is in the `portal_active` or `portal_archived` alias |
| `workflow_objects:in`, `workflow_objects:out` | on a `custom_object` board: in a `workflow_objects` page or not |
| `parent:<board id>` | on a `sub_items_board`: the board whose subtasks column names it |
| `doc:<doc id>` | on a `document` board: its `docs[].id` |
| `rp_ids:<n>`, `project_ids:<n>`, `portfolio_project_ids:<n>` | the count of column ids with that prefix, when at least one |
| `hierarchy:multi_level` | `hierarchy_type` is `multi_level` |
| `imitation:name`, `imitation:terminology` | on an N7 or N8 result: the name or the terminology equals a NO 5:158 default exactly |
| `relation_target:<board id>` | on an N7 result: the native Tickets board whose relation targets it |
| `N11` | the board was handed back to R8 to R11 |

### Attributes (N12)

`state` and `items_count` are given on every board. `family`, `version`, `install_kind` and `sla_mark` are given on a `native_` class and on a `doc_container` whose lineage resolves to a native template (NO 4.1:104); they are null elsewhere. CRM: `family` `sales_crm` with `version` `v2`, `crm_core` with `v1`, or null with `unknown`, read from the types first (W84), then the lineage's catalogue row. Service: `family` is the template family (`A` to `D`, `Portal`) of the lineage or template view; a Tickets board with neither has `B or C` with the extended ids and `A or D` without them; `version` is null. `install_kind` is `direct_install`, `descendant_copy(n)`, `descendant_fingerprint`, `lineage_unresolved` (an N6 or N7 board whose chain ends unresolved) or null. An N10 board adds `fingerprint`, the product and entity its fingerprint names.

### Monday default ids (L3)

For W83's L3, a column id is a monday default when it is `name`, a blank-board default (`person`, `status`, `date4`, `date0`) or one of the default-shaped ids NO 4.3 lists for Incidents, CSAT Survey and Service Contacts: `board_relation`, `color`, `monday_doc`, `rating`, `long_text`, `date`, `color__1`, `color2__1`, `email`, `phone`, `connect_boards5`.

### The client workspaces each key assumes

`reports` depends on `account.json`'s `client_workspace_ids`, which no monday read carries. The identification key assumes `90100000101` and `90100000102`; the native key assumes `90100000201`, `90100000203` and `90100000207` (an empty CRM workspace, reported "product boards not installed here"). The Service product's default workspace `90100000209` is empty and is not a client workspace, so it is not reported.

### Digests

Every digest is W73's: `prefix + ":" +` the first eight hex digits of the sha256 of `json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, with no prefix for an `intent_digest`. Each ledger-state file lists, under `digest_fields`, the place of every digest it holds (`at`, a key path), its prefix and the fields it was computed over. A snapshot's `columns` digest is taken over the board's column list sorted by `id`, and its `plan` digest over the plan text. The ledger and account hashes of K302 come from the record the test builds and are not in these reads.

## Ids

Every id is a string. Template ids and template view ids are monday's own constants, from `shared/native-objects.md`. Every other numeric id is invented, eleven digits long, in one range per type; no range holds a catalogue id or an id of WP2's unit fixture:

| Type | Range, inclusive |
|---|---|
| workspace | `90100000001` to `90100009999` |
| folder | `90200000001` to `90200009999` |
| board, and every board-backed object (doc containers, subitems boards, custom objects, Portals, workflow objects) | `90300000001` to `90300999999` |
| view | `90400000001` to `90400999999` |
| item | `90500000001` to `90509999999` |
| user | `90600000001` to `90600009999` |
| object that is not board-backed (none is used) | `90700000001` to `90700009999` |
| agent | `90800000001` to `90800009999` |
| Vibe app | `90900000001` to `90900009999` |
| workflow draft (none is used) | `91000000001` to `91000009999` |
| automation | `91100000001` to `91100999999` |
| dashboard | `91200000001` to `91200009999` |
| doc (`docs[].id`) | `91300000001` to `91300009999` |
| account; product | `91400000001` to `91400000099`; `91500000001` to `91500000099` |
| widget; team | `91600000001` to `91600099999`; `91700000001` to `91700000999` |

Board ids run `903000001nn` in the identification reads, `903000002nn` in the native reads (with `90300000901` to `90300000903` the unreadable intermediates), `903000003nn` in the compare reads and `903000004nn` in the reconcile reads. A view id is `904000` plus the board's last three digits plus a two-digit index. An agent's `version_id` (`vid-000001`) and a Vibe app's `code_version` (`1`) are invented strings, because P-19 and P-20 give no form.

## Allowed name stems

Every `name`, `title`, `item_terminology` and `name_at_build` in these files is made of the words below, case aside, and none matches the shipped leak list. They are neutral invented words, plain descriptive words, the words of monday's own native default names and terminologies (NO 5:158, needed by the look-alike and renamed-native cases) and the words of the automation phrases:

`account`, `accounts`, `activities`, `activity`, `aide`, `ambrel`, `an`, `approval`, `archive`, `asset`, `assign`, `assistant`, `billing`, `board`, `call`, `calls`, `capacity`, `cases`, `catalogue`, `changes`, `client`, `collections`, `column`, `contact`, `contacts`, `corvane`, `count`, `created`, `csat`, `date`, `deal`, `deals`, `delivery`, `delvarr`, `desk`, `directory`, `document`, `done`, `drafts`, `due`, `elvaine`, `employee`, `escalation`, `escalations`, `feedback`, `fenmark`, `files`, `finance`, `flow`, `followups`, `form`, `garvenn`, `gorvanth`, `guide`, `halvenn`, `handbook`, `harrowin`, `helper`, `here`, `hub`, `ilsby`, `in`, `incident`, `incidents`, `intake`, `invoices`, `is`, `item`, `ivrel`, `jobs`, `kelmoss`, `launch`, `lead`, `leads`, `ledger`, `lifecycle`, `log`, `lundrask`, `main`, `management`, `migration`, `mossery`, `name`, `nolvane`, `notes`, `notify`, `number`, `of`, `old`, `open`, `operations`, `opportunities`, `opportunity`, `orders`, `org`, `overview`, `owner`, `partners`, `pellarn`, `person`, `pilot`, `pipeline`, `plan`, `planner`, `planning`, `plans`, `portal`, `portfolio`, `products`, `project`, `projects`, `prospects`, `quarne`, `quotes`, `refresh`, `register`, `request`, `requests`, `review`, `rollout`, `roster`, `rota`, `rushel`, `sales`, `sallowen`, `sandbox`, `schedule`, `scout`, `scratch`, `serial`, `service`, `services`, `stage`, `start`, `status`, `stock`, `studio`, `subitems`, `supplier`, `support`, `survey`, `table`, `targets`, `tarnovel`, `task`, `tasks`, `the`, `ticket`, `tickets`, `to`, `totals`, `tracker`, `triage`, `umbrisk`, `upgrade`, `vessick`, `view`, `wendrel`, `when`, `works`, `yarlow`

## Cases

### Identification

| Case | Board | Class | Rule |
|---|---|---|---|
| `R1-doc-container` | `90300000101` | `doc_container` | R1 |
| `R10-multi-level` | `90300000122` | `multi_level_board_not_project` | R10 |
| `R11-archived` | `90300000124` | `normal_classic_board` | R11 |
| `R11-deleted` | `90300000125` | `normal_classic_board` | R11 |
| `R11-normal` | `90300000123` | `normal_classic_board` | R11 |
| `R2-parent-board` | `90300000102` | `normal_classic_board` | R11 |
| `R2-subitems` | `90300000103` | `subitems_board` | R2 |
| `R3-custom-object-other` | `90300000105` | `custom_object_other` | R3 |
| `R3-workflow-object` | `90300000104` | `workflow_object` | R3 |
| `R3-workflow-object-archived` | `90300000106` | `workflow_object` | R3 |
| `R4-portfolio` | `90300000110` | `portfolio_board` | R4 |
| `R5-converted` | `90300000113` | `converted_project_board` | R5 |
| `R5-created-connected` | `90300000111` | `project_tasks_board` | R5 |
| `R5-created-folder-shared` | `90300000115` | `project_tasks_board` | R5 |
| `R5-created-transient-key` | `90300000112` | `project_tasks_board` | R5 |
| `R5-origin-unknown` | `90300000114` | `project_board_origin_unknown` | R5 |
| `R6-overview-deleted` | `90300000117` | `project_overview_companion` | R6 |
| `R6-overview-live` | `90300000116` | `project_overview_companion` | R6 |
| `R7-unrecognised-key` | `90300000121` | `keyed_board_unrecognized_key` | R7 |
| `R8-near-miss` | `90300000119` | `normal_classic_board` | R11 |
| `R8-planner` | `90300000118` | `resource_planner_companion` | R8 |
| `R9-portfolio-shaped` | `90300000120` | `portfolio_shaped_board_without_key` | R9 |

Projects: `90300000111` connected (C1, C2, C3); `90300000112` partial on C1; `90300000113` partial on C2; `90300000114` unconnected; `90300000115` unconnected with C4 listed and its overview named.

### Native

| Case | Board | Class | Rule |
|---|---|---|---|
| `crm-companion-marks` | `90300000208` | `native_crm_companion_board` | N6 |
| `crm-companion-unresolved` | `90300000209` | `native_crm_companion_board` | N6 |
| `crm-products-services` | `90300000207` | `native_crm_products_services` | N4 |
| `crm-qi-generic-ids-only` | `90300000218` | `ordinary_board_in_product_workspace` | N9 |
| `crm-qi-line-items` | `90300000217` | `native_crm_quotes_invoices_subitems` | N5 |
| `crm-quotes-invoices` | `90300000216` | `native_crm_quotes_invoices` | N2 |
| `crm-v1-accounts` | `90300000214` | `native_crm_accounts` | N2 |
| `crm-v1-activities` | `90300000215` | `native_crm_activities` | N2 |
| `crm-v1-contacts` | `90300000212` | `native_crm_contacts` | N2 |
| `crm-v1-deals` | `90300000210` | `native_crm_opportunities_or_deals` | N2 |
| `crm-v1-deals-copy-1hop` | `90300000211` | `native_crm_opportunities_or_deals` | N2 |
| `crm-v1-deals-subitems` | `90300000219` | `native_crm_opportunities_or_deals_subitems` | N5 |
| `crm-v1-leads` | `90300000213` | `native_crm_leads` | N2 |
| `crm-v2-accounts-renamed` | `90300000204` | `native_crm_accounts` | N2 |
| `crm-v2-activities` | `90300000205` | `native_crm_activities` | N2 |
| `crm-v2-contacts` | `90300000203` | `native_crm_contacts` | N2 |
| `crm-v2-leads` | `90300000201` | `native_crm_leads` | N2 |
| `crm-v2-opportunities` | `90300000202` | `native_crm_opportunities_or_deals` | N2 |
| `crm-v2-sales-targets-chain-broken` | `90300000206` | `native_crm_sales_targets` | N4 |
| `custom-object-other` | `90300000233` | `custom_object_other` | R3 |
| `default-shaped-satellite` | `90300000255` | `ordinary_board_in_product_workspace` | N9 |
| `deleted-native-lineage-only` | `90300000262` | `native_crm_contacts` | N2 |
| `keyed-board-with-native-signals` | `90300000261` | `keyed_board_unrecognized_key` | R7 |
| `lookalike-name` | `90300000250` | `lookalike_board` | N8 |
| `lookalike-terminology` | `90300000251` | `lookalike_board` | N8 |
| `native-moved-to-core` | `90300000260` | `native_descendant_misplaced` | N10 |
| `ordinary-links-into-native` | `90300000254` | `ordinary_board_in_product_workspace` | N9 |
| `ordinary-terminology-call` | `90300000252` | `ordinary_board_in_product_workspace` | N9 |
| `ordinary-terminology-client` | `90300000253` | `ordinary_board_in_product_workspace` | N9 |
| `ordinary-test-blank-defaults` | `90300000258` | `normal_classic_board` | R11 |
| `ordinary-test-suffixed-ids` | `90300000259` | `normal_classic_board` | R11 |
| `planted-ids` | `90300000257` | `native_crm_leads` | N4 |
| `portal-active` | `90300000229` | `native_service_portal` | N1a |
| `portal-archived-alias` | `90300000230` | `native_service_portal` | N1a |
| `portal-archived-lineage` | `90300000231` | `native_service_portal` | N1b |
| `portfolio-cursor` | `90300000263` | `portfolio_board` | R4 |
| `project-incomplete-read` | `90300000264` | `project_tasks_board` | R5 |
| `service-a-tickets-sla` | `90300000223` | `native_service_tickets` | N2 |
| `service-a-tickets-subitems` | `90300000224` | `native_service_tickets_subitems` | N5 |
| `service-b-contacts` | `90300000226` | `native_service_service_contacts` | N2 |
| `service-b-csat` | `90300000225` | `native_service_csat_survey` | N2 |
| `service-b-start-here-doc` | `90300000228` | `doc_container` | R1 |
| `service-b-tickets` | `90300000220` | `native_service_tickets` | N2 |
| `service-b-tickets-copy-1hop` | `90300000221` | `native_service_tickets` | N2 |
| `service-b-tickets-copy-2hop` | `90300000222` | `native_service_tickets` | N2 |
| `service-c-asset-management` | `90300000238` | `native_service_asset_management` | N2 |
| `service-c-csat-view-only` | `90300000234` | `native_service_csat_survey` | N3 |
| `service-c-employee-directory` | `90300000240` | `native_service_employee_directory` | N2 |
| `service-c-employee-lifecycle` | `90300000239` | `native_service_employee_lifecycle` | N2 |
| `service-c-incidents` | `90300000236` | `native_service_incidents` | N2 |
| `service-c-lifecycle-subitems` | `90300000244` | `native_service_employee_lifecycle_subitems` | N5 |
| `service-c-tickets` | `90300000235` | `native_service_tickets` | N2 |
| `service-c-tickets-chain-broken` | `90300000237` | `native_service_tickets` | N4 |
| `service-c-tickets-subitems` | `90300000241` | `native_service_tickets_subitems` | N5 |
| `service-d-incidents` | `90300000243` | `native_service_incidents` | N2 |
| `service-d-tickets` | `90300000242` | `native_service_tickets` | N2 |
| `service-satellite` | `90300000227` | `native_service_satellite_probable` | N7 |
| `stripped-native` | `90300000256` | `lookalike_board` | N8 |
| `workflow-object-not-portal` | `90300000232` | `workflow_object` | R3 |

Project: `90300000264`, an incomplete read (its portfolio's items page ends on a cursor).

### Compare

- `agent-state-moved`
- `agent-version-id-moved`
- `appendix-clean-query`
- `appendix-json-query-string`
- `appendix-mutation`
- `appendix-subscription`
- `appendix-two-operations`
- `appendix-word-in-comment`
- `appendix-word-in-string`
- `archived-board`
- `column-digest-change`
- `control-dropped-from-scope`
- `control-protected-row-unmoved`
- `control-unchanged-automation`
- `control-unchanged-board`
- `control-unchanged-dashboard`
- `control-unchanged-doc`
- `control-unchanged-form`
- `control-unchanged-vibe-app`
- `control-updated-at-only`
- `description-change`
- `owner-change`
- `protected-row-moved-before`
- `workflow-state-moved`

### Reconcile

The full run yields every one of the seven classes (`cases` in `reconcile/expected.json` names the rows of each); automations are listed first, then agents, Vibe apps and workflows, then the other kinds in key order, a kind's unrecorded extras after its rows. The classify-only run from strand 002 marks run `run-2026-10-16-1` interrupted with the same counts.

## When a capture arrives (A11-1)

When the user names a test workspace, a scrubbed capture of the same reads is taken and its ids are mapped into these ranges. Each captured page replaces the synthetic page of the same kind one for one; the answer key stays. The capture is then compared with these files shape for shape, field for field against `schema-fields.json`, and `confirmed_by_capture` is set to the capture's date only where the shapes agree. Until then the reads are the specification, and a shape they do not model is not graded.
