# Native CRM and Service objects, portfolios and projects

This is the one home for how the plugin recognises, maps and protects monday's native CRM and Service boards, and how it recognises portfolios and projects (ARCHITECTURE §11, amendments A5, A6, A7). Skills and scripts link here and do not restate it. `ledger.py classify` implements section 5; `hooks/guard.py` and `account-build` implement section 6; `solution-audit` implements 6.4.

Sources, all read-only: the 2026-09-11 structure pass over 67 boards in 19 workspaces (0 misclassified, plus ten adversarial cases), the 2026-09-11 workspace classification over 33 boards (rules `R0`-`R11` and `C1`-`C4`, 0 misclassified), the 2026-09-12 raw recapture of the nine classification boards the two structure passes lacked (all nine returned, `missing_ids` empty) and probes P-13, P-14 and P-18 of 2026-09-12. API ring 2026-10 release candidate throughout. Template ids and template view ids below are monday-owned constants, the same in every account; no account-specific id appears in this file.

## 1. The finding

Nothing in the API flags a native board. On all 43 natives read, `object_type_unique_key` was null, `type` was `board`, `hierarchy_type` was `classic`, `board_kind` was `public`, and `inferred_metadata.item_type` and `manual_metadata.board_md` were both null. A native looks exactly like a board made by hand a minute ago, and a from-scratch look-alike is indistinguishable on those fields.

P-13 (2026-09-12) closed the last two candidates. `Board.columns_namespace` returns the board's own id on a native and on an ordinary board alike; it is a namespace handle, not a marker. `Column.capabilities` has exactly two fields, `visibility` (null on every column read, reserved `deal_*` columns included) and `calculated`, which describes multi-level roll-up behaviour, not provenance. Rules `N0`-`N11` therefore stand as written, and detection is inferred from structure in four descending strengths: template lineage, template view ids, reserved column ids, corroborating marks. Product kind is a soft gate over all four. Names, item terminology, view names and status labels are user-editable and decide nothing.

## 2. Detection: four axes and a soft gate

**2.1 Lineage, walked hop by hop.** `created_from_board_id` is a one-hop pointer: a clean install points at the template, a duplicate points at the board it was copied from, a copy of a copy chains further. The walk: `chain = [created_from_board_id]`; at each hop, an id in a template catalogue is `RESOLVED_TEMPLATE` (entity and family known, hop count is the distance); a null id is `NO_LINEAGE`; an id `boards(ids:)` does not return is `UNRESOLVED`; otherwise read that board's `created_from_board_id` and repeat, capped at 5 hops. Verified on a live account: 0 hops `<board> → 5678953932` (v2 Leads); 1 hop `<board> → <board> → 2658101899` (v1 Deals, the parent itself a native install); 2 hops `<board> → <board> → <board> → 5727048235` (Service family B). Chains also dead-end: all six natives in a CRM default workspace, plus Sales Targets, a finance companion and two Tickets copies, pointed at intermediate ids the API will not return. Such ids are specific to the account read, so none is listed here; like the template ids they are terminal (matchable, never readable), and preflight stores each account's own as `unreadable_intermediate_ids`. `N2` is the strongest single signal and the only one that names family and version; it fired on 36 of 67 boards and it still works on a deleted board, where columns and views come back empty.

**2.2 Template view ids.** `views[].source_view_id` chains exactly like lineage, one hop at a time: a direct install shows the template's view ids, its copy shows the install's own view ids, and the copy's copy shows the copy's. A `source_view_id` matching a template view id therefore proves a direct install, and it survives a cleared `created_from_board_id` (`N3`). Three independent family-A Tickets installs all showed `176205535`; two Quotes & Invoices installs both showed `174990912` and `174990913`; all three Portals showed `200776197`. Absence proves nothing: views get deleted, and a user-created view has `source_view_id` null.

**2.3 Reserved column ids.** Template columns carry suffix-free, hand-named ids (`deal_stage`, `lead_status`, `contact_account`, `product_and_service_*`, `line_item_*`, and Service's `status95`, `people0`, `long_text7`, `request_type`, `item_id_1`). API- and UI-created columns always get a generated id matching `^[a-z_0-9]+_(mk|mm)[a-z0-9]{6,8}$`; such an id never counts toward a signature and never disqualifies a board, because natives carry suffixed ids too (`request_category_mkmvd0p6`, `enrolled_sequences_mkmcsv7h`, `formula_mm3gb9sn`). The blank-board defaults `person`, `status`, `date4` and `date0` are excluded from every signature: the native Portal, a workflow object and an ordinary test board all carried exactly `name`/`person`/`status`/`date4`. Reserved ids are counted per entity against the thresholds in sections 3 and 4 (`N4`). They are the only axis that survives a broken chain, and they have to be, because broken chains are common in practice: one native Tickets board read live had a broken chain, no SLA columns and no template view, yet 12 core Tickets ids made it unambiguous. Match on column id, then read the type to pick the family; never assert a type for a reserved id (`deal_close_probability` is `numbers` in v1 and `formula` in v2; `account_deal` is a `mirror` in v1 and a `board_relation` in v2).

**2.4 Corroborating marks** raise confidence and are never requirements. Absence proves nothing for any of them.

| Mark | Test | Meaning and caveat |
|---|---|---|
| `CRM_RELATION_MARK` | any `board_relation` whose `settings.staticImage` is one of `leads`, `contacts`, `accounts`, `opportunities`, `activities` | the column came from a CRM template. `staticImage` does not name the target: Opportunities' relation to Sales Targets carries `contacts`. v1 `activity_item` carries no `staticImage` at all |
| `CRM_FEATURE_MARK` | any column of type `unsupported` whose id starts `custom_` or `enrolled_sequences_` | a CRM product feature column. Read from the unfiltered column list only: `columns(types: [unsupported])` returns `[]` even where they exist |
| `CRM_MIRROR_MARK` | any `mirror` whose `settings.displayed_linked_columns[].column_ids` intersect the CRM reserved sets | the board mirrors a native column; identifies companion boards with no reserved ids of their own |
| `V2_OPPS_FINGERPRINT` | mirror `deal_account` whose `settings.boardIds` contains `2673708477` or `1631647074` | Sales CRM v2 Opportunities specifically; stale template ids, seen on both independent v2 installs |
| `SERVICE_SLA_MARK` | the SLA helper regex below, four or more ids sharing a stem | the SLA feature is configured. Two stems: `_lst/_ewh/_itr/_ttp` drop the formula id's final character, `_tl/_ts` keep it (for `formula_mm3jtrd0`: `formula_mm3jtrd_lst`, `formula_mm3jtrd0_tl`). Present on 4 of 9 Tickets boards |
| `PORTAL_MARK` | `type == custom_object` and (id in `objects(object_type_unique_keys: ["service::portal-object"])`, or `created_from_board_id == 9449773054`, or a view `source_view_id == 200776197`) | definitive for the Service Portal, whose own key is null |

SLA helper regex, matched on the suffix and grouped by prefix, never on one stem: `^formula_[a-z0-9]{6,8}_(lst|ewh|tl|itr|ts|ttp)$`.

**2.5 Product kind is a soft gate.** `workspace { account_product { kind } }` (`crm`, `service`, `core`, `software`, `marketing_campaigns`) picks which catalogue to prefer and raises confidence, but signatures run against both catalogues regardless, so a native moved into a core workspace is flagged for review (`N10`) rather than silently downgraded. The Service product's default workspace was empty in the account read; natives are found across non-default workspaces and never assumed to sit in `account_product.default_workspace_id`.

**2.6 The query.** One read-only call per page, used unchanged for every validation run. Sweep a workspace with `boards(workspace_ids: $ws, state: all, limit: 50, page: $p)` in place of `ids`. It fetches no items, no titles and no labels.

```graphql
query DetectNativeBoards($ids: [ID!], $ws: [ID!]) {
  version { kind value }
  complexity { after }
  portal_active: objects(object_type_unique_keys: ["service::portal-object"], workspace_ids: $ws, state: ACTIVE, limit: 500) { id state }
  portal_archived: objects(object_type_unique_keys: ["service::portal-object"], workspace_ids: $ws, state: ARCHIVED, limit: 500) { id state }
  boards(ids: $ids, state: all, limit: 50) {
    id name type state hierarchy_type object_type_unique_key board_kind
    item_terminology created_from_board_id items_count workspace_id board_folder_id
    inferred_metadata { item_type }
    manual_metadata { board_md }
    workspace { id account_product { kind } }
    columns { id type }
    links: columns(types: [board_relation, subtasks, mirror]) { id type settings }
    views { id type name source_view_id }
  }
}
```

Cost: 25k to 90k complexity per run of 7 to 17 boards against a budget of about 20M, roughly a quarter of the portfolio query, which pays for `items_page` (167,022 for one page of 33 boards). Page in batches of 25 to 50; the default limit is 25 and one call returned 25 despite a limit of 200. `boards(ids:)` silently drops ids it cannot return, with no error and no null placeholder (17 asked, 16 returned; 7 asked, 6 returned): diff requested ids against returned ids on every call and treat a missing id as unreadable, never as deleted and never as non-native. `objects()` has no all state (`ACTIVE`, `ARCHIVED`, `DELETED`), which is why the Portal is read in two aliases.

## 3. CRM catalogues

The account runs two generations of the CRM template and a detector has to know the difference. **Sales CRM v2** (the default-workspace set and a clean install elsewhere): Leads, Opportunities, Contacts, Accounts, Sales Activities, Sales Targets, Products & Services and companions; `deal_close_probability` is a formula, `account_deal` a board relation, and Opportunities carries `V2_OPPS_FINGERPRINT`. **CRM core v1**: Deals, Contacts, Leads, Accounts, Activities, Quotes & Invoices; `deal_close_probability` is numbers, `account_deal` a mirror, the Activities terminology is `"Activity "` with a trailing space, and `activity_item` carries no `staticImage`. **Quotes & Invoices** is its own template with a line-item subitem board whose columns are all `line_item_*`; its terminology is `"Document #"`. **Products & Services** is fully native with the default terminology `item`, so only the `product_and_service_*` ids find it. **Companion boards** (finance, collections and account-management shapes) carry no reserved ids at all and are identified by `CRM_RELATION_MARK` or `CRM_MIRROR_MARK` alone (`N6`).

**3.1 Template source ids.**

| Family | Template id → entity |
|---|---|
| Sales CRM v2 | `5678953932` leads, `5678953956` opportunities_or_deals, `5678953938` contacts, `5678953942` accounts, `5678953951` activities, `5678953895` sales_targets |
| v2 companions | `5678953861`, `5678953867`, `5678953868`, `5678953871`, `5678953875`, `5678953876`, `5678953878`, `5678953894`, `5678953934`, `5678953967`, `8975252031` |
| v2 subitems | `5678954845`, `5678955164`, `8975252077`, `9396380271` |
| CRM core v1 | `2658101980` leads, `2658101923` contacts, `2658101956` accounts, `2658101899` opportunities_or_deals, `2658101993` activities, `8179060947` quotes_invoices, `2658102037` deals_subitems, `18393462843` qi_line_items, `10027024945` subitems (parent unconfirmed), `6131463946` project_companion, `6131463958` project_companion_subitems, `8615325260` companion |
| Smaller families | `5092627193` contacts, `5092627194` accounts, `5092627197` opportunities_or_deals, `5092627202` and `5092627206` subitems; `9031562048` leads, `9031562049` activities, `9031562051` contacts, `9031562062` project, `9031562066` accounts, `9031562081` opportunities_or_deals, `9031562339` and `9031562445` subitems |

**3.2 Template view ids.** v2 leads `124433515`, `124433523`, `124433528`; v2 opportunities `124433522`, `124433524`, `124433536`; v2 contacts `124433508`, `124433513`; v2 accounts `124433511`, `124433514`; v2 sales activities `124433520`; v2 sales targets `124433519`, `124433531`, `124433534`, `124433549`; quotes & invoices `174990912`, `174990913`; v1 deals `60638373`, `169248366`; v1 leads `121301932`; v1 accounts `124032534`.

**3.3 Column signatures.** A board only needs the stated threshold; native installs lose columns to deletion all the time.

| Entity | Threshold | Reserved ids |
|---|---|---|
| leads | 3 | `lead_status`, `lead_email`, `lead_company`, `lead_phone`, `lead_owner` |
| opportunities_or_deals | 3 | `deal_stage`, `deal_owner`, `deal_value`, `deal_contact`, `deal_account`, `deal_forecast_value`, `deal_expected_close_date`, `deal_close_probability`, `deal_close_date`, `deal_creation_date`, `deal_length`, `deal_actual_value`, `deal_jan_actual` … `deal_jul_actual`, `jul___actual`, `deal_sep_actual` … `deal_dec_actual` (24 ids) |
| contacts | 3 | `contact_email`, `contact_phone`, `contact_company`, `contact_account`, `contact_deal` |
| accounts | 3 | `account_contact`, `account_deal`, `company_domain`, `company_description`, `company_profile`, `employee_count`, `headquarters_loc`, `industry` |
| activities | 3 | `activity_item`, `activity_owner`, `activity_type`, `activity_start_time`, `activity_end_time`, `activity_status` |
| products_services | 2 | `product_and_service_description`, `product_and_service_price`, `product_and_service_sku`, `product_and_service_type` |
| quotes_invoices | 3 | `bill_to`, `amount`, `issue_date`, `type`, `file`, `creation_log__1` — generic enough to collide, so require lineage `8179060947`, a template view id or terminology `"Document #"` as corroboration |
| qi_line_items | 6 | `line_item_description`, `line_item_unit_price`, `line_item_quantity`, `line_item_total_multipliers`, `line_item_base_price`, `line_item_adjustment_rate`, `line_item_adjustment_value`, `line_item_fees_rate`, `line_item_fees_value`, `line_item_tax_rate`, `line_item_tax_value`, `line_item_final_price`, `line_item_currency`, `line_item_product`, `line_item_deal`, `line_item_contact`, `line_item_id` |
| sales_targets | 3 | `link_to___opportunities`, `jan___target` through `nov___target` (eleven months, no December form), `q1_target`, `q2_target`, `q2_actual`, `q4_target`, `target_to_date`, `target_to_date8` |
| deals_subitems | lineage only | a live instance carried only blank defaults plus suffixed ids; `2658102037` identifies it |

## 4. Service catalogues

Service natives come from four template families, none of them in the Service product's default workspace, which was empty. Family E (`7830923787` tickets, `7830923821` subitems) is unread (P-17).

**4.1 Families and template ids.**

| Family | Boards | Template ids |
|---|---|---|
| A base Tickets | Tickets + subitems | `7819831530` tickets, `7819831540` tickets_subitems |
| B customer service | Tickets, Contacts, CSAT Survey, subitems, Start here doc | `5727048235` tickets, `5727048230` contacts, `5727048234` csat_survey, `5727048483` tickets_subitems, `5765211778` start_here_doc |
| C IT service desk | Tickets, Incidents, Asset management, Employee directory, Employee lifecycle, CSAT, subitems, Start here doc | `5561655961` tickets, `5561655956` incidents, `5561655946` csat_survey, `5561655954` employee_lifecycle, `5561656011` employee_directory, `5561656015` asset_management, `5561656760` tickets_subitems, `5561656359` lifecycle_subitems, `5750119042` start_here_doc |
| D older IT service | Tickets, Incidents, subitems, Start here doc | `6410079972` tickets, `6410079951` incidents, `6410080630` subitems, `6573685095` start_here_doc |
| Portal | one custom object per install | `9449773054` portal_custom_object |

A Start here doc keeps class `doc_container` (`R1`); its template lineage is an attribute, not a class.

**4.2 Template view ids.** A tickets `176205535`; B tickets `125328754`, `125328758`; B csat `125328753`; C tickets `122226426`, `122606170`; C csat `122226423`; C employee lifecycle `122226427`; D tickets `139565036`, `176205700`; start here doc `126013264`; portal `200776197`.

**4.3 Column signatures.**

| Entity | Threshold | Reserved ids |
|---|---|---|
| tickets | 6 | one pooled set of 24: `status95`, `people0`, `long_text7`, `priority`, `request_type`, `date6`, `email`, `date`, `subitems`, `text`, `files`, `collaborators`, `item_id_1`, `time_tracking3`, `time_tracking`, `formula9`, `formula13`, `formula17`, `status_163`, `date2`, `date20`, `board_relation6`, `connect_boards2`, `board_relation21`. Families B and C carry the extended ids, family A does not. The richest board read carried 21, the thinnest genuine native carried 9 with no `request_type` at all, and a chain-broken native carried 12: the threshold of 6 stands alone |
| tickets_subitems | 4 | `agent__1`, `status__1`, `priority__1`, `request_type__1`, `creation_date__1`, `email9__1`, `description__1`, `requestor_name__1` |
| asset_management | 5 | `serial_number`, `recovery_key`, `mac_address`, `ip_address`, `computer_name`, `operating_system`, `jamf_intune_agent`, `released_from_abm`, `asset_tag`, `disabled_pre_stage`, `valid_data`, `last_check_in`, `dup_last_check_in`, `more_details`, `building`, `duplicate` |
| employee_lifecycle | 4, weak | `subitems_status`, `email1`, `email9`, `email95`, `color2`, `status_1` — all generic; prefer lineage `5561655954` |
| employee_directory | 2, weak | `site___itsm`, `connect_boards5` — prefer lineage `5561656011` |
| incidents | none | `person`, `board_relation`, `status`, `color`, `date4`, `monday_doc` — every id a monday default, byte-identical on three independent natives; identify by lineage (`5561655956`, `6410079951`) or as the relation target of a confirmed native Tickets board |
| csat_survey | none | `rating`, `long_text`, `date` — identical on three natives; identify by lineage (`5727048234`, `5561655946`) or the form view `125328753` / `122226423` |
| service_contacts | none | `status`, `color__1`, `color2__1`, `email`, `phone`, `connect_boards5` — only the `__1` pair is distinctive; prefer lineage `5727048230` or being a native Tickets relation target |

**4.4 The Portal** is the one Service entity with a real object type, found through `objects(object_type_unique_keys: ["service::portal-object"])` in both `ACTIVE` and `ARCHIVED` states (`N1a`). Its own `Board.object_type_unique_key` is still null and its columns are blank-board defaults, so it is never identified by columns. An archived Portal is invisible to a single `objects()` call; the fallback is Portal lineage `9449773054` or template view `200776197` (`N1b`), both Portal-specific, so a workflow object (`created_from_board_id` `105719650`, no template view) is not swallowed. The 2026-09-12 recapture listed seven active Portal objects account-wide and none archived.

**4.5 Service extras have no API surface.** Nothing links a Tickets board to its portal, email channel or SLA policy, which is why v1 builds Service structure and defers those three (A7). Where SLA is configured it leaves the helper set of 2.4; its absence means nothing.

## 5. The rules, in order

The identification rules `R0`-`R11` own the type and key gates; the native rules `N0`-`N11` slot in after the key gate `R4`-`R7` and before `R8`, because a native CRM or Service board carries no key and would otherwise fall through to `R11`. A board that fires any N rule is never reported as `normal_classic_board`. State is an attribute, never a role; a deleted board returns no columns, views or items, so only board-level fields and lineage apply to it.

| Rule | Condition | Class |
|---|---|---|
| R0 | page until `boards` is `[]`; classify every state | — |
| R1 | `type == document` | `doc_container` (doc id from `docs[].object_id`) |
| R2 | `type == sub_items_board` | `subitems_board` (parent: the board whose subtasks `settings.boardIds` names it) |
| R3 | `type == custom_object` | `workflow_object` if in the workflow `objects()` set, else `custom_object_other` |
| R4 | key `work-management::portfolio` | `portfolio_board` |
| R5 | key `work-management::portfolio-project` or `work-management::project` | `project_tasks_board` when at least 2 of `project_status`, `project_timeline`, `project_owner`, `project_priority` are present or `created_from_board_id == 9857787491`; else `converted_project_board`; with columns hidden and no template lineage, `project_board_origin_unknown` |
| R6 | key `work-management::standalone` | `project_overview_companion` (deleted means its project was connected) |
| R7 | any other non-null key | `keyed_board_unrecognized_key` — stop and review, never fall through |
| N0 | product = `workspace.account_product.kind` | context only; both catalogues still run |
| N1a | custom object in the Portal `objects()` set | `native_service_portal` (definitive) |
| N1b | custom object with Portal lineage or Portal template view | `native_service_portal` (strong) |
| N2 | lineage walk `RESOLVED_TEMPLATE` | `native_<product>_<entity>`, `direct_install` at 0 hops, else `descendant_copy(n)` |
| N3 | a view `source_view_id` in the template view ids | `native_<product>_<entity>`, `direct_install` |
| N4 | a reserved-id signature meets its threshold | `native_<product>_<entity>`, `descendant_fingerprint` when lineage is `UNRESOLVED` or `NO_LINEAGE` |
| N5 | subitems board with `qi_line_items` ≥ 6, `tickets_subitems` ≥ 4, or resolved lineage | `native_<product>_<entity>_subitems` |
| N6 | no signature, product `crm`, `CRM_RELATION_MARK` or `CRM_MIRROR_MARK` | `native_crm_companion_board` (moderate) |
| N7 | product `service`, native terminology, relation target of a classified native Tickets board, neither N2 nor N3 | `native_service_satellite_probable` (review only; no board needed it) |
| N8 | product `crm` or `service`, key null, lineage `NO_LINEAGE` or `UNRESOLVED`, zero reserved ids, zero marks, imitating a native name or terminology | `lookalike_board` — shape, never intent |
| N9 | product `crm` or `service`, no signals, no imitation | `ordinary_board_in_product_workspace` |
| N10 | any native fingerprint, product not `crm` or `service` | `native_descendant_misplaced` (review) |
| N11 | otherwise | `ordinary_board`, handed back to R8-R11 |
| N12 | attributes beside the class, never as the class | family and version, install kind (`direct_install`, `descendant_copy(n)`, `descendant_fingerprint`, `lineage_unresolved`), `SERVICE_SLA_MARK`, state, items count |
| R8 | key null and at least 5 of the 9 `rp_*` ids | `resource_planner_companion` |
| R9 | key null and at least 5 `portfolio_project_*` ids | `portfolio_shaped_board_without_key` (review) |
| R10 | `hierarchy_type == multi_level` | `multi_level_board_not_project` |
| R11 | otherwise | `normal_classic_board` |

The imitation test in N8 compares against the native default names (Leads, Contacts, Accounts, Opportunities, Deals, Activities, Sales Activities, Sales Targets, Products & Services, Quotes & Invoices, Tickets, Incidents, CSAT Survey, Asset management, Employee directory, Employee lifecycle, Portal, Subitems of Tickets, Start here) and terminologies (`Lead`, `Deal`, `Opportunity`, `Contact`, `Account`, `Activity`, `"Activity "` with its trailing space, `Document #`, `Sales Rep`, `Ticket`, `Incident`, `Ticket ID`, `Contact name`, `Employee name`, `employee`, `Serial Number`). `Org` and `Client` are excluded on purpose: `Org` was user-set on a native Accounts board and `Client` on an ordinary board, so either would both miss a native and flag an ordinary board. Results with each board's rule id, signals and confidence go into `account.json.native_map` (record level, paid once per record per staleness window and read by every strand) and the strand's `objects[].role`, and the user confirms the map before it is used, always for anything below high confidence.

## 6. The guard rule

**6.1 Protect natives by board-id list and by lineage, never by board name and never by column shape.** The live run proved both halves. Names and terminology: a native Accounts board had been renamed with its terminology set to `Org`, a native Deals descendant was named with an unrelated word, and both genuine look-alikes were named with the word "Leads". Column shape: P-14 (2026-09-12) ran raw `create_column(... column_type: status, id: "deal_stage")` against an ordinary board in the test workspace and the platform created it with the id exactly as requested, no error and no warning, as it did for `probe_p14_text`. Any board can be made to carry any reserved id, so a column signature is fully spoofable; the overlay flag is `create_column_id_honoured: true` (ring 2026-10 RC, 2026-09-12), and the "known limit" that planted ids inside a product workspace classify like a chain-broken native is a demonstrated behaviour, not a hypothesis. A duplicate of a native, by any of the three `DuplicateBoardType` values, keeps every column-level fingerprint and differs only in lineage. Column signatures are how a native is detected in preflight; they are never how one is protected.

**6.2 What preflight records** in `account.json.guard_index`, because a `PreToolUse` hook cannot call the API: `product_workspaces` (workspace id → `account_product.kind`, without which a CRM workspace cannot be told from a core one), `account_products` (id, kind, default workspace), `native_board_ids_by_entity`, the flat `native_board_index` keyed by board id (the load-bearing field: a `duplicate_board` names a board id, and membership here is the only way to know it is native), `template_source_ids`, `unreadable_intermediate_ids`, `template_view_ids`, `reserved_column_ids` with thresholds and `blank_default_exclusions`, `native_default_names_and_terminology` (the ask path only), `portal_object_ids` per state, `build_targets_by_strand`, the `lease` mirror, and `record_provenance` (capture date, ring, coverage, staleness budget). A stale index is this design's main failure mode.

**6.3 What the hook and `account-build` refuse, ask and never do.** Hooks are defence in depth; the same checks run inside `account-build`, so nothing changes if hooks do not run in Cowork (S0-12) or cannot read raw GraphQL text (S0-14). There is no `duplicate_board` MCP tool, so duplication always arrives as raw GraphQL; the raw `create_board` mutation accepts `template_id` and the raw `create_column` and `create_status_column` mutations accept `id`, none of which the MCP tools expose; there is no `move_board_to_workspace`, boards move only through `move_object`, which can change workspace, folder and account product in one call.

| Id | Action | When |
|---|---|---|
| R-A | block | `duplicate_board` whose `board_id` is in `native_board_index`, keyed on the id and never on the duplicate type |
| R-B | block | any structural or destructive verb naming a native id: `delete_board`, `archive_board`, `update_board` (how a native gets renamed), `create_column`, `delete_column`, `change_column_metadata`, `change_column_title`, `update_column`, `change_board_kind`, `update_board_hierarchy`, `connect_board_to_object_schema`, `convert_board_to_project` |
| R-C | block | `create_board` whose `workspaceId` resolves to `crm` or `service` unless that workspace is in the holding strand's `build_targets_by_strand` entry |
| R-D | block | a raw `create_board` naming a `template_id` in `template_source_ids` or an unreadable intermediate |
| R-E | block | raw `create_column` or `create_status_column` text whose `id` matches any reserved id, the reserved-stem regex below, or the Service legacy set (`status95`, `people0`, `long_text7`, `request_type`, `date6`, `item_id_1`); the platform will not refuse it (P-14), so the attempt is refused here |
| R-F | block, fail closed | any write to a board absent from the record inside a product workspace: the index is stale |
| R-G | block | `move_object` with `objectType: Board` on a native id, whatever changes |
| R-H | ask | `create_board` whose `boardName` matches a native default name case-insensitively or whose `creationPrompt` names a native entity word, even inside an allowed workspace; a demo build may legitimately need a board called Tickets |
| R-I | ask | `move_object` moving a build board into a `crm` or `service` workspace |
| R-J | ask | any guarded mutation while `record_provenance.captured_at` is past `staleness_budget_days` |
| R-K | never | infer nativeness from a name in `tool_input`; names are advisory, the record's id lists are authoritative |

Reserved-stem regex for R-E: `^(deal|lead|contact|account|activity|line_item|product_and_service|portfolio_project|project|rp)_`.

The blueprint refuses to plan a new board for an entity the map already resolves, and a change to a native board is a change-table row with prior state and its own yes, because a column added to a native cannot be removed again.

**6.4 What the audit re-derives live.** Re-run the query of 2.6 over every workspace the build touched, re-derive every class, and assert: nothing the build created classifies as anything but ordinary; no build board carries a reserved id, a `staticImage` relation, an `unsupported` feature column, an SLA helper, a `created_from_board_id` in the template, intermediate or native lists, or a view `source_view_id` in the template view ids; every CRM and Service entity in the blueprint lives on its mapped native board; every recorded native still returns with the same `created_from_board_id`, the same reserved-id count and the same null key (a non-null key means monday shipped CRM or Service keys and `R7` catches it, so the rule order is revisited); native relation `settings.boardIds` still point at the same natives and no native points at a build board; native workspace ids are unchanged; the Portal set matches `portal_object_ids` in both states; and every portfolio project is still connected on both halves. Diff requested ids against returned ids on every call.

**6.5 The weak spots, named as weak spots.** Incidents, CSAT Survey and Service Contacts carry only monday defaults; three independent instances of each were byte-identical, and they were identified only because lineage resolved. Once a copy loses its lineage and its template form view, nothing in the API separates it from an ordinary board (P-16). A chain-broken native cannot be told from a board wearing planted ids inside a product workspace, and the API exposes no column-creation provenance. An original cannot be told from its duplicate once the chain breaks (two boards read live were provably native in structure with provenance gone), so nothing says which is canonical; the default is to protect it as native and ask, since a wrong answer that protects is cheaper than one that overwrites. A native stripped of its template columns with a broken chain reads as a look-alike or as ordinary. Employee directory and Employee lifecycle need lineage or template views. N8 reports shape, never intent. Coverage of the read was partial: CRM and Service workspaces on pages 1 to 5 of more than 500, with 26 Service workspaces returning no visible boards, so `record_provenance.coverage` states it and R-F fails closed on anything unknown.

## 7. Portfolio and project roles

**7.1 Keys.** The portfolio family carries keys and they are reliable: `work-management::portfolio` (portfolio board), `work-management::portfolio-project` (a project's tasks board, created or converted) and `work-management::standalone` (an unconnected project's overview companion). A new tasks board reads `work-management::project` for about 40 seconds before settling at `::portfolio-project`; both mean the same role and cannot be told apart. All three are invisible to `objects()`, which returns `[]` for them even when matching boards exist, so portfolios and projects are enumerated through `boards(state: all)` and their keys [G-74]. Roles come from `type`, then the key, then the `rp_*` fingerprint — never from item terminology (`task` sat on a normal board, `project` on overviews and the portfolio, `item` on a real converted project), never from `hierarchy_type` alone, `board_kind`, either metadata field, `columns_namespace` or `capabilities.calculated`, which marks every multi-level board and was absent from a real converted project [G-81].

**7.2 Fingerprints and lineage.** The resource planner has no key; `R8` fires on at least 5 of its 9 ids: `rp_placeholder`, `rp_placeholder_index`, `rp_assignee`, `rp_assignee_mirror`, `rp_timeline`, `rp_effort_per_day`, `rp_total_effort`, `rp_selected_effort`, `rp_connected_project`. A created tasks board carries `project_status`, `project_timeline`, `project_owner`, `project_priority`; a converted board keeps its own arbitrary ids and is identified by key alone. Template lineage marks the roles: `5882692393` portfolio, `9857787491` tasks, `6667825632` overview, `9958257937` planner, `105719650` workflow object (also reported on blank boards, so never decisive alone). `created_from_board_id` is null on blank and converted boards. Spoofing `rp_*`, `project_*` or `portfolio_project_*` ids through raw `create_column` is untested but, after P-14, assumed possible, which is why R-E covers those stems.

**7.3 A connection is proved from both halves** (`C1`-`C4`). For a portfolio X, the link column L is the `board_relation` with id `portfolio_project_link`, falling back to `settings.type == "hierarchy"`; `targets(X) = L.settings.boardIds`; `rows(X)[B]` is the set of X's items whose L value links items on board B. A project tasks board P is connected to X only when `P.id` is in `targets(X)` **and** `rows(X)[P.id]` is non-empty. One half alone is reported as `partial link - review`, never as connected; neither half is `unconnected`, naming the overview if a relation column of P targets an R6 board. The project-side reflection column (a `board_relation` other than the link whose `settings.boardIds` contains X) is corroboration only; while a project is unconnected it points at the overview. A connection is never inferred from `board_folder_id`, folder, workspace or names. If a portfolio's `items_page.cursor` is non-null, fetch the rest before calling a project unconnected. Roll-ups fill within about 45 seconds, so the check waits before it fails.

**7.4 Not separable from the API.** A deleted overview and its project: after `connect_project_to_portfolio` the system deletes the overview and hides its columns and items, so only name equality or creation time relate them, and both are heuristics [G-77]. A planner and its project: `rp_connected_project` settings are `{}` and the planner's "Project" view settings are `{}`; only the name suffix and the shared folder relate them, and folder evidence is excluded (`C4`). Record tasks, overview, planner and folder ids as companions before connecting, because that is the only moment some of them are readable [G-71, G-72].

## 8. Open items and the defaults that ship

P-9: a freshly provisioned CRM or Service account may set object keys this older lineage lacks (`connect_board_to_object_schema` exists); default, confidence plus the user's confirmation, and `R7` stops any such key for review. P-15: whether CRM feature columns can be added to a non-template board through the UI; default, `CRM_FEATURE_MARK` stays a corroborating mark only. P-16: policy for a chain-broken native descendant; default, protect as native and ask. P-17: family E and CRM families beyond the two known sets are unread and coverage is partial; default, `record_provenance` states it and R-F fails closed. P-7: re-probe after the ring rolls. P-13 and P-14 are closed above; P-18 belongs to `read-back.md`.
