# Stage-1 acceptance: WP1 (`shared/`)

Run on 2026-09-20 against `plugins/monday-master-builder/shared/` at the state of the working tree, checked bullet by bullet against BUILD-PLAN.md WP1's acceptance list and its size budgets. Nothing was changed. Every mechanical check ran on the Mac's Python 3.9.6 (`/usr/bin/python3`) with the standard library only. Line numbers below are from `cat -n` of the files as they stand.

Verdict in one line: nine of the twelve checks pass with evidence; three do not, and one standing rule is broken in one place. Four of the five fixes are one-line edits. The fifth needs a decision above WP1 on which spelling of the call-type header values is the pinned one, because the design and the fixtures agree with each other and `record-map.md` differs from both.

## 1. Summary

| # | Acceptance bullet (short form) | Result |
|---|---|---|
| 1 | R-names, per-pain checks, gates and status values agree with the keys; calibration values pinned against the keys that carry them; `sales-method.md` carries the support instrument, the non-evidence list with its carve-outs, the scope matrix as a table, the A16 document rules and the narrowed conflict rule | Must fix (two items; every listed name agrees, one objection-type string and one status pin do not) |
| 2 | `record-map.md` is the one home for the record model, including the call-type header vocabulary and the thirteen-label list | Must fix (one item; everything else in the bullet is present and agrees with A§7) |
| 3 | `monday-gotchas.md`: Tools relied on, all ninety, G-91 onward, eight fields per entry, the never-say block | Pass |
| 4 | `native-objects.md`: the detection finding, the CRM catalogues, the Service catalogues at the same depth | Pass |
| 5 | `native-objects.md`: the guard rule as the live run proved it, the weak spots named | Pass |
| 6 | `native-objects.md`: portfolio and project roles, the planner fingerprint, both halves | Pass |
| 7 | `safety.md`: A1 as written, the contended lease as A§9.8 states it, the delivery-exposure rules of A§9.11 | Pass |
| 8 | `house-style.md`: targets, DO, DON'T as links, shapes with placeholders, profiles per speaker and seat, provisional marks, the empty credential slot | Pass |
| 9 | `read-back.md`: a read per write kind including portfolio and project, the permissions row | Pass |
| 10 | `sandbox-accounts.txt` under [A11-1] with `never-demo` rows; `safety.md` states A11-3 as open with the moment it is asked | Pass |
| 11 | `cleanroom_scan.py` finds no eight-word run shared with the learn files; no real-call content | Must fix (one finding, one line) |
| 12 | Size budgets | Pass |
| — | Standing rules: no personal names, no "consultant", no all-caps emphasis, calm prose | Must fix (one all-caps word the release lint reports as an error) |

### The must-fix list

| # | File and line | What is wrong | Owner of the fix |
|---|---|---|---|
| F1 | `shared/record-map.md` lines 192 to 197, the `Pinned: call-type-vocabulary` table | Five of the six header fields pin hyphenated tokens that neither ARCHITECTURE 8.3 step 5 nor any calibration key uses. The design and all fifteen keys spell the dimension values with spaces: `new logo`, `existing client of ours`, `a third party's account where we are the stranger`; `we show`, `they show their current state`, `they show a candidate solution they built`, `nobody shows`; `configured structure`, `bespoke code`, `hybrid`. `record-map.md` pins `new-logo`, `existing-client`, `third-party-account`; `we-show`, `they-show-current`, `they-show-candidate`, `no-show`; `configured-structure`, `bespoke-code`, `hybrid`. The two modifier value sets (`one-to-one`, `small-group`, `large-room`; `not-live`, `live-approver-present`, `live-approver-absent`) have no source at all: A§8.3 step 5 names the modifiers without values, and the keys write free prose for them (`small group: three client speakers…`, `not live: no price, tier…`). Only `seat` and the thirteen labels agree in all three places | WP1, once the token form is decided. The decision is not WP1's to make alone: A§7.7 spells the strand's `output_class` as `configured-structure` while A§8.3 spells the call header's as `configured structure`, so whichever form is pinned, one of the two architecture sections or the fifteen keys has to move with it |
| F2 | `shared/sales-method.md` line 240 (and the reference on line 243) | The 5.2 row reads `Outside the map: changing what you built for us costs us`. The key that exercises this objection (s21) types it `Changing what you built for us costs us (embedded: …)`, and line 227 of the same file says the first column is the exact `type` string the keys use and that `Outside the map: ` is reserved for objections with no home in the map. This one has a home: it is a row of the map (C81). The row's first column should read `Changing what you built for us costs us`; line 243's `→ changing what you built costs us` should follow | WP1 |
| F3 | `shared/safety.md` line 51, row IR-03 | `cleanroom_scan.py` reports an eight-word run shared with `dossier/learn-api-errors.md:642`: "first subitem on a classic board adds a". Release check 8 exits 1 on it. The sentence states a fact the live run proved (G-44) and is not a copy, but the criterion is mechanical; any rewording of the row's first two cells clears it | WP1 |
| F4 | `shared/monday-gotchas.md` line 104, entry G-26 | `tools/lint_plugin.py` reports `error: all-caps: all-caps emphasis word NOT`. The word sits inside the quoted API message `"data/settings must NOT have additional properties"`, which is verbatim platform text, not emphasis; the lint reads double quotes as prose and backticks as code, so putting the message in a code span clears the error | WP1 |
| F5 | The `advisory` pin (bullet 1) | `advisory` is spelled in `sales-method.md` 2.1 (line 36) and `record-map.md` (line 184), but no calibration key s11 to s25 carries it anywhere, as a rubric status, a numbers status or any other value, so the bullet's statement that the keys "exist in stage 1 so the pin is checkable here" does not hold for this one value. The other three pins (`met-with-residual`, `not-obtainable`, `asked`) check out against fifteen, twelve and fifteen keys. Either a key gains an `advisory` row (s24's package, whose seat header names candidates, is the natural carrier) or the bullet is narrowed | WP18, not `shared/` |

## 2. Bullet by bullet

### Bullet 1: names, checks, gates, status values, and what `sales-method.md` carries

**Method.** The script in appendix A reads the names out of `sales-method.md` and `record-map.md` by parsing the tables and sentences that define them, walks all 25 `answer-key.json` files, and prints every disagreement. Its full output is transcribed in section 3.

**Criterion names.** `sales-method.md` 2.3 (lines 66 to 79) spells `R1 Current state mapped` through `R12 Scope agreed verbally`. All 25 keys use those twelve strings and no other R-string: each appears exactly 25 times across the set. Pass.

**Per-pain checks.** Line 58 spells `Stated`, `Concrete`, `Workaround`, `Reach`, `Cost inputs`, `Trajectory`, written `P1 Stated` and so on. Every `P# <check>` row in every key uses one of the six; 81 rows per check across the set, no other check string. Pass.

**Gates.** The 2.4 table (lines 109 to 115) spells `Solution blueprint`, `Build`, `First demo (v0.1)`, `Pricing or proposal prep`, `v1.0 sign-off`. Every key's `gates_met` plus `gates_not_met` holds exactly five entries, each starting with one of those five, each gate once. Pass.

**Status values.** The 2.1 table (lines 29 to 37) writes `met`, `met-with-residual`, `partial`, `missing`, `not-obtainable`, `advisory`, `not-applicable`. Every rubric and numbers status in every key is one of these. The reviewed keys s1 to s10 carry only `met`, `partial` and `missing`, no `asked` flag, and their counts match COVERAGE.md's 323 rows (229, 60, 34). The calibration keys carry `met-with-residual` (all fifteen), `not-obtainable` (twelve: s12 to s16, s18 to s23, s25) and the `asked` flag (all fifteen, on every rubric row). `advisory` is carried by none: see F5. `record-map.md` line 184 lists the same grades and the flag. Partial pass; F5.

**Verdicts.** `Discovery complete`, `Nearly ready`, `Not ready` as written on line 103; every key's verdict is one of the three. Pass.

**Objection types.** Section 5.2 (lines 229 to 240) spells ten type strings; 5.2's rule (line 227) is that a key's `type` leads with one of them or with `Outside the map: `. 23 of the 25 keys obey it. s21 leads with `Changing what you built for us costs us`, which 5.2 spells `Outside the map: changing what you built for us costs us`: F2. s11 has one type written `Outside the map (…)` without the colon, a deviation inside the fixture rather than in `shared/` (note 2).

**Support instrument.** 6.2 (lines 253 to 259) writes the five rows; s10's five `Support check` rows match them character for character. Pass.

**Non-evidence list with both carve-outs where the list is written.** Line 42, in the 2.1 grading rules: the list, then "Two carve-outs, stated here so no grader has to find them", the closed-factual-yes carve-out and the R10 asymmetry, citing C14. Pass.

**Scope matrix as a table.** Lines 140 to 174. Sixteen rows (four seat values, three relationship values, four direction values, three output classes, two modifiers) by thirteen columns (R1 to R12 and the P# checks): 208 cells, of which 14 read `Met-threshold`, one reads `advisory` and 193 read `unspecified`. Every specified cell carries a superscript to one of twelve numbered notes, each naming its C-number and, where the calibration saw only one observation, saying so; the client-led seat and the third-party relationship are wholly unspecified with the reason given in note 1. Line 140 names `REAL-CALL-LESSONS.md` §2 and §7 with method §2.6 as the source, and I checked the fifteen specified cells against those sections: the co-sell and vendor-led cells rest on C108 (§7), the expansion cells on C23 and C26 (§2), the reverse-demo and prototype cells on C22 (§2) and C110, the mechanism-confirmed cells on C76 (§2), the delta-scope cell on C113 and the bespoke cell on C114. Pass.

**A16 document rules.** 2.7 (line 178): what a document can satisfy (R1 and the current-state elements, R6's picture and R12's scope where stated, requirements) and what it cannot unless explicit (R3, R4, R7, R10), the `[Q/doc]` tier, `documented` inventory rows, no type header and nothing `advisory` for a document-only record, both kept on a conflict. Pass.

**The narrowed conflict rule.** Section 3 (line 182): latest wins only for the same proposition from the same speaker inside one call; every other pair is a conflict kept as both statements; a structural disagreement is a fork (C91); a requirement re-engineered by consensus is neither. Pass.

**`leak-terms.txt`** (lines 122 to 139) carries the twelve criterion names without their numbers and four of the five gate names, lowercased, as the fixtures spell them; `Build` is an ordinary word and is deliberately not listed. Pass.

### Bullet 2: `record-map.md` as the one home

Checked mechanically against ARCHITECTURE.md section 7 (script in appendix B, output in section 4) and by reading.

- **Two-level file map with a row and an owner per file.** The record-level and strand-level tables (lines 11 to 59) carry the same 42 `Path` cells as A§7.1's two tables, none missing and none added, including `inputs/<date>-<title>.<ext>`, `inputs/<date>-<title>.md`, every strand file and `deliverables/handoff/*`. Owner text differs in twelve rows by added detail only (note 10). Pass.
- **Schemas.** `client/2` (line 95), `strand/1` (99), `summary/1` and `scope/1` (103), `version/1` (109), `account/1` (111), `build/2` (115), `live-map/1` (119), `lock/2` (130), `intake-report/1` (222) and `intake-set/1` (240), each with its field list. Every one of the 26 `client/2` fields and 19 `strand/1` fields in A§7.2 and A§7.7 is named (the `schema` field is covered by the general rule on line 93); of the 167 JSON field names in A§7.3, every one appears in the `account/1` and `build/2` sections except the three example entity keys `leads`, `tickets`, `portal`, which the file generalises as `crm.<entity>`, `service.<entity>` and `portfolio.<key>`. Pass.
- **`record.py status --json` shape** (lines 134 to 149), **strand-index row** (84 to 89), **lock history entry** (132), **permitted-constants table** (203 to 220), **fully qualified naming** (72), **log header with the strand position** (160) and the **type list including `document`** (163: 42 types, identical in content and order to A§7.6), **reading contract** (76 to 78), **budgets** (in the tables), **call-set fields** (182: `sequence`, `call_type`, `package`, `provenance`, `handed_over_by`, `attendees`, `strands`), **document-summary front matter** (182). Pass.
- **Evidence markers.** Lines 167 to 176: the eight markers in A§7.5's order including `[Q/doc]`; the three source markers `spoken`, `observed`, `documented` on line 184. Pass.
- **The fixed hand-off sentence.** Line 107 is character for character the sentence A§7.9 quotes. Pass.
- **Thirteen labels.** Line 201 matches A§7.1's list and A§8.3 step 7's set exactly. Pass.
- **Call-type header vocabulary.** Lines 190 to 197. `seat` agrees with A§8.3 step 5 and with every key. `relationship`, `direction`, `output_class`, `room_shape` and `money_live` do not: F1. The conservative fallbacks (`not-ours`, `new-logo`, `no-show`, `bespoke-code`, `large-room`, `live-approver-absent`) match A§8.3's five fallbacks in meaning and add a sixth for room shape.
- **"Every string `record.py check` looks for is spelled here first."** Not checkable until WP2 lands (note 8).

### Bullet 3: `monday-gotchas.md`

Checked with a structural script (its checks are listed in appendix B; output in section 5).

- **Opens with the Tools relied on block.** Line 9, before the first entry at line 22; 54 base names; the two names the block itself declares absent from the roster (`get_board_schema`, `configure_ai_column`) are the only two not found in `dossier/live-mcp-roster.md`. The block says it is the WP1 seed and that the release step regenerates it. Pass.
- **All ninety and G-91 onward.** 108 entries, ids G-01 to G-108, contiguous, no duplicate, every G-01 to G-90 present in the gotchas draft under the same id; G-91 to G-108 are the native-identity entries, and every figure I spot-checked in them (43 natives, 67 boards, 19 workspaces, 0 misclassified, three board ids, template view ids `176205535`, `174990912`, `200776197`, the rule and field names `requested_but_silently_absent`, `create_column_id_honoured`, `terminology_caveats`, `blank_board_default_ids`, `not_separable`, `lineage_walk`, `view_lineage_axis`, `SERVICE_SLA_MARK`) is in the native structure report, its rules file, the recapture or the P-13/P-14/P-18 probe file. Seventeen titles are reworded from the draft (contractions expanded, "(disputed)" dropped in favour of the status field); the ids never moved. Pass.
- **Eight fields per entry.** Every one of the 108 carries Claim, Surface, Ring, Do instead, Evidence with a `20xx-xx-xx` date, Probe marked read-only or sandbox write with a `probe-catalog.md` recipe id, Impact and Status; every status is in the vocabulary (98 confirmed, 8 observed, 2 untested); all 21 high-impact entries carry the full block and all 87 others the compact form, which is the heading plus one line. Pass.
- **No entry written from a learn file.** The cleanroom scan finds no eight-word run in this file (section 6). Pass.
- **The never-say block.** Lines 395 to 413, beside the list in the same file, 15 numbered rows, 19 lines. Rows 1 to 12 are A§10.2's twelve in order; the block names rows 8 to 12 as the five the calibration added (C51) and rows 13 to 15 as its companions (C46, C92, C101). Every G- id cited in the block, and every G- id cited anywhere in the file, resolves to an entry. Rows 12 and 15 cite no G- id because no probe stands behind them, which A§10.2's own twelfth row already implies (note 4). The block says it is a claims block and not a gotcha, that `demo-script` reads it at generation and that the per-entry fields do not apply. Pass.

### Bullets 4 to 6: `native-objects.md`

Every string the three bullets name is present; the string check in appendix B lists them. In particular: "Nothing in the API flags a native board. On all 43 natives read, `object_type_unique_key` was null" (line 9); lineage walked hop by hop with the five-hop cap and the `RESOLVED_TEMPLATE` / `NO_LINEAGE` / `UNRESOLVED` outcomes (15); template view ids (17); reserved column ids (19); product kind as a soft gate (34). CRM catalogues: Sales CRM v2 and CRM core v1 (61), template ids per family (65 to 71), Quotes & Invoices with its `line_item_*` subitem board (85, 86), Products & Services under `product_and_service_*` (84). Service at the same depth: families A to D with their Tickets template ids (96 to 102), the legacy fingerprint as one pooled set of 24 that includes `status95`, `people0`, `long_text7`, `priority`, `request_type`, `date6`, `email`, `date`, `subitems`, `item_id_1`, `time_tracking3`, `formula9`, `formula13`, `formula17` and `status_163` with the threshold at 6 and the sentence saying why (112), the `__1` subitem set at 4 (113), the SLA helper's two stems and regex (29, 32), the Portal through `objects(object_type_unique_keys: ["service::portal-object"])` in both states with the lineage and template-view fallback for an archived one (121). The guard rule in the proved form heads section 6.1 (162): protect by board-id list and lineage, never by name and never by column shape, with the renamed Accounts board, the look-alikes named "Leads" and P-14's planted `deal_stage` as the evidence; the file says "spoofable" where the bullet says "forgeable". The weak spots are named as weak spots in 6.5 (188): Incidents, CSAT Survey and Service Contacts on monday defaults once lineage breaks; a chain-broken native indistinguishable from planted ids. Portfolio and project roles (192): the three keys, the transient `::project`, the nine `rp_*` ids (194), a connection proved from both halves with `C1` to `C4` (196). Pass on all three.

### Bullet 7: `safety.md`

A1 as written on line 5 and in section 5 (69 to 77): approved once as a list, re-confirmed as one grouped reply, cannot be switched off through the API, the switch-off handoff step. The lease in section 8 (99 to 125): one `build` lease per record in `lock/2` with its fields, the epoch fence with the three things it checks and the carry rule, who may hold it, the waiting message in full, release on a clean stop, "Nothing expires on its own", and the five numbered conditions for a break with resume-first as the recommended choice and the rule that parking is refused on a `duplicate` or `partial` class. Delivery exposure in section 11 (143 to 155): never the user's own live operational account, with the reason and the `never-demo` list; exactly one access-request shape; credentials never handled, "including as a hypothetical, and including while naming the risk"; the screen-driving etiquette marked provisional. Pass.

### Bullet 8: `house-style.md`

Register targets as checkable properties (11 to 20); profiles per speaker and per seat with the pooled-profile reason (26 to 28); the smaller-sample families marked provisional with the confirming observation stated (32); the DO list with a reason per item (38 to 54); the DON'T list as a link table to method §7, §7.1 and §4.10 and to A§9.11 and 9.12, plus its own two rules (60 to 83); the shapes bank (89 to 140) with bracket placeholders and no proper noun, brand, product or figure inside any quoted shape (the only capitalised words in the quotes are sentence starts and placeholders); the literal line `Credential: empty [L18]` on line 148 with the rule that the generator never fills it. Pass.

### Bullet 9: `read-back.md`

The table (20 to 53) names a read for every kind in A§8.6 step 16's build order (workspace, folder, board, groups, plain columns, relation, mirror, formula, items, links, views and board-first forms, docs, dashboards and widgets, automations last) and for the archive, owners, description and terminology, subitems companion, doc image, portfolio (49), project and its companions (50), project connect (51) and board conversion (52). The board-level permissions row reads `boards(ids){permissions}` marked `[doc, P-18 2026-09-12]` and says why the mark stays `[doc]`; the row below it records column, item and subitem permissions as `not-checkable` on the by-eye list. The A17 row honestly names no read yet. Pass.

### Bullet 10: `sandbox-accounts.txt` and A11-3

The sandbox and `never-demo` lists, their syntax and the comment on why the two kinds do not cancel are in place; both lists ship empty, because account entries belong in each user's local settings. `safety.md` section 13 (175) states transcript redaction and retention as open, gives the reason (only fictional fixtures exist), names the moment it is asked (before the first real transcript or document is written, at intake, never at setup, as one three-part question) and what refuses until then. Pass.

### Bullet 11: clean room and real-call content

`cleanroom_scan.py` over `shared/` against the five quarantined learn files reports one eight-word finding: F3. Nothing in `shared/` names an organisation, person, product, platform, brand, figure or date from a real call: the sweeps in section 7 found no personal name, no fixture company or place name, no client-side product name, and no figure that is not from the live runs (the test workspace and account, board ids and complexity costs from the results files). The calibration content in `house-style.md` and `sales-method.md` is generic by construction; `leak_lint.py --terms` cannot run yet (note 7). Must fix for the one finding.

### Bullet 12: size budgets

| File | Lines | Budget | Bytes |
|---|---|---|---|
| `record-map.md` | 252 | 300 | 43,612 |
| `sales-method.md` | 286 | 340 | 69,535 |
| `house-style.md` | 156 | 160 | 17,197 |
| `safety.md` | 183 | 300 | 51,256 |
| `monday-gotchas.md` | 413 | 460 | 106,169 |
| `read-back.md` | 61 | 150 | 22,107 |
| `native-objects.md` | 202 | 280 | 36,456 |
| `leak-terms.txt` | 210 | none stated | 6,275 |
| `sandbox-accounts.txt` | 30 | none stated | 2,410 |
| Total | 1,793 | about 2,000 | |

Every file is inside its budget and ends with a newline. Pass. The lines are long (note 5).

### Standing rules

- **A12 and personal names.** No personal name in any of the nine files; "the user" appears 74 times; no he/she/his/her refers to the user. The release lint's own personal-name check did not run because `~/DelOps/personal-names-index.json` does not exist (note 6).
- **"consultant".** Zero occurrences as a word in `shared/` (`consultancy` appears twice, in `safety.md` line 83 and `leak-terms.txt` line 3, naming the firm's name as a leak term).
- **All-caps emphasis.** The release lint reports one error, `monday-gotchas.md:104`: F4. My own sweep, excluding acronyms and enum values in code spans, found nothing else beyond `DON'T` (the design's own name for the list, used in A§3.12) and `ARCHITECTURE` (a document name).
- **Calm prose, standard library, one owner per file.** No shouting words; no scripts in this package; every file in `shared/` is on WP1's list.

## 3. Mechanical name agreement: the diff

Command: `/usr/bin/python3 wp1_names_diff.py` (appendix A). Names as the shared files spell them:

```
criteria (12):  R1 Current state mapped … R12 Scope agreed verbally
checks:         Stated, Concrete, Workaround, Reach, Cost inputs, Trajectory
gates:          Solution blueprint, Build, First demo (v0.1), Pricing or proposal prep, v1.0 sign-off
statuses:       met, met-with-residual, partial, missing, not-obtainable, advisory, not-applicable
verdicts:       Discovery complete, Nearly ready, Not ready
objection types (10): Price feels high; Needs to think it over; Must check with someone; Wrong time, next quarter;
                We'll build it ourselves; Talking to other partners; Just send a proposal or pricing;
                monday itself is the problem; Team won't adopt it; Outside the map: changing what you built for us costs us
support checks (5): Support check 1 Solved their issue first … Support check 5 Closed with a short note on what is worth keeping an eye on
labels (13):    intro, discovery, reverse-demo, prototype-review, demo, scoping, working-session, pricing,
                call-review, expansion, sign-off, check-in, support   (== ARCHITECTURE 7.1, == 8.3 step 7 as a set)
```

Header vocabulary, `record-map.md` against ARCHITECTURE 8.3 step 5:

```
seat          ARCH ['partner-led', 'co-sell', 'vendor-led', 'client-led']
              record-map ['partner-led', 'co-sell', 'vendor-led', 'client-led']  equal: True
relationship  ARCH ['new logo', 'existing client of ours', "a third party's account where we are the stranger"]
              record-map ['new-logo', 'existing-client', 'third-party-account']  equal: False
direction     ARCH ['we show', 'they show their current state', 'they show a candidate solution they built', 'nobody shows']
              record-map ['we-show', 'they-show-current', 'they-show-candidate', 'no-show']  equal: False
output_class  ARCH ['configured structure', 'bespoke code', 'hybrid']
              record-map ['configured-structure', 'bespoke-code', 'hybrid']  equal: False
```

Per key (rubric statuses, rows carrying `asked`, verdict):

```
s1   met 29, missing 3, partial 4                              asked 0   Discovery complete
s2   partial 13, missing 5, met 6                              asked 0   Nearly ready
s3   met 39, partial 3                                         asked 0   Discovery complete
s4   partial 5, met 18, missing 1                              asked 0   Nearly ready
s5   partial 7, missing 9, met 2                               asked 0   Not ready
s6   met 31, missing 1, partial 4                              asked 0   Discovery complete
s7   met 29, partial 7, missing 6                              asked 0   Nearly ready
s8   met 31, missing 6, partial 5                              asked 0   Discovery complete
s9   met 26, partial 8, missing 2                              asked 0   Nearly ready
s10  met 18, partial 4, missing 1                              asked 0   Discovery complete
s11  partial 13, met 9, met-with-residual 1, missing 1         asked 24  Nearly ready
s12  met 24, met-with-residual 2, missing 3, partial 6, not-obtainable 1   asked 36  Discovery complete
s13  met 22, met-with-residual 1, missing 2, partial 4, not-obtainable 1   asked 30  Discovery complete
s14  met 27, met-with-residual 2, missing 3, partial 3, not-obtainable 1   asked 36  Discovery complete
s15  met 18, met-with-residual 2, not-obtainable 1, missing 1, partial 2   asked 18  Discovery complete
s16  met 18, met-with-residual 1, not-obtainable 1, missing 2, partial 2   asked 24  Discovery complete
s17  met 21, met-with-residual 1, partial 6, missing 2         asked 30  Nearly ready
s18  met-with-residual 3, met 23, partial 7, missing 2, not-obtainable 1   asked 36  Discovery complete
s19  met-with-residual 3, met 22, not-obtainable 1, missing 3, partial 7   asked 36  Discovery complete
s20  met 27, met-with-residual 2, partial 5, missing 1, not-obtainable 1   asked 36  Discovery complete
s21  met 16, met-with-residual 1, partial 6, not-obtainable 1  asked 24  Nearly ready
s22  met 27, partial 5, met-with-residual 1, missing 2, not-obtainable 1   asked 36  Nearly ready
s23  met 27, partial 4, met-with-residual 1, missing 3, not-obtainable 1   asked 36  Nearly ready
s24  met 25, partial 7, met-with-residual 2, missing 2         asked 36  Nearly ready
s25  met 11, met-with-residual 3, partial 8, not-obtainable 1, missing 1   asked 24  Nearly ready
```

The numbers block adds `met-with-residual` on the bleed or upside of s13 to s18 and s23 and `not-obtainable` on the upside of s15 and s16. No key carries `advisory`.

Disagreements, 113 in all:

- 111 are type-header values. Every key from s11 to s25 writes `relationship`, `direction_of_show` and `output_class` with the ARCHITECTURE 8.3 step 5 strings (`new logo`, `nobody shows`, `configured structure`, and so on), and writes `room_shape` and `money_live` as prose beginning `small group: …`, `large group: …`, `not live: …`, `live in the room with the approver present: …`, `yes: …` or `no: …`; s24's five files write `seat` as `partner-led (…)` with the candidates in the parenthesis. Twenty-six of the 111 are direction values, because s11, s15, s19 and s21 carry per-segment values as well. The `label` field agrees in every key.
- 2 are objection-type strings: s11 `Outside the map (a capability question…)` (no colon) and s21 `Changing what you built for us costs us (embedded: …)`.

Everything else agrees character for character: 25 of 25 keys on the twelve R-names, the six check names, the five gate names, the three verdicts and the status set; s10 on the five support rows.

## 4. `record-map.md` against ARCHITECTURE section 7

Output of the comparison script (appendix B, part 2):

```
ARCH 7.1 rows: 42   record-map rows: 42   in ARCH not record-map: none   in record-map not ARCH: none
rows whose 'Written by' text differs: 12 (added detail only; listed in note 10)
rows whose Budget text differs: 3 ("must pass" versus "passes"; "the map needs grouping" versus "grouping")
log types: 42 in both, same order
client/2: all 26 fields of A§7.2 named; strand/1: all 19 fields of A§7.7 named
markers: [Q] [Q?] [Q/side] [Q/recon] [Q/doc] [X] [E] [I] in both, same order
A§7.3 json field names: 167; absent from the account/1 and build/2 sections: leads, tickets, portal (example entity keys)
schemas named: client/2 strand/1 summary/1 live-map/1 lock/2 account/1 build/2 scope/1 intake-report/1 version/1 intake-set/1; status/1 in the JSON block
hand-off sentence verbatim: True
```

## 5. `monday-gotchas.md` structure

```
entries: 108   first..last: G-01 G-108   missing in G-01..G-90: none   duplicate ids: none   contiguous 1..108: True
full-block entries: 21   compact entries: 87   (21 high-impact entries, all full block; no full block below high)
status counts: confirmed 98, observed 8, untested 2   impact counts: medium 60, low 27, high 21
every entry: Claim, Surface, Ring, Do instead, Evidence with a date, Probe read-only|sandbox write with a probe-catalog.md recipe, Impact, Status
Tools relied on heading at line 9; first entry at line 22
Never say heading at line 395; 15 rows; 19 lines; every G- id cited resolves; rows 12 and 15 cite no G- id
G- refs anywhere in the file that resolve to no entry: none
titles reworded from the draft: 17 (ids unchanged)
```

## 6. Clean-room scan

```
$ /usr/bin/python3 tools/cleanroom_scan.py --root <repo> --tree plugins/monday-master-builder/shared \
    rebuild-workspace/dossier/learn-api-data.md learn-api-errors.md learn-api-products.md learn-history.md learn-workflow.md
plugins/monday-master-builder/shared/safety.md:51: 8 words shared with .../dossier/learn-api-errors.md:642: "first subitem on a classic board adds a"
cleanroom_scan: 1 finding(s) over 5 quarantined file(s), 8-word runs
exit 1
```

At six words the scan reports nine runs (five in `monday-gotchas.md`, two in `native-objects.md`, two in `safety.md`), all short technical phrases such as "kanban calendar and gantt board views" and "a native crm or service board"; none is a finding under the eight-word rule and none reads as copied prose.

## 7. Sweeps

- `tools/lint_plugin.py --root <repo>`: one error (`shared/monday-gotchas.md:104: all-caps: all-caps emphasis word NOT`), one warning (personal-name list not found, check not run); every other check either passes or reports its input as not present yet.
- `grep -n -i -w "consultant\|consultants" shared/*`: no match.
- All-caps words of three or more letters outside code spans, with acronyms and enum values removed: `NOT` (line 104), `DON'T` (two headings), `ARCHITECTURE` (a document name), the rule ids `R-A` to `R-K`. Nothing else.
- Capitalised word pairs shaped like a personal name, outside code spans, after removing ordinary title-case pairs: one, `Submission Viewer`, which is part of the platform's own view name "WorkForms Submission Viewer" in G-52.
- A hand list of every organisation, person, place and product name in the 25 fixtures and in the design's examples, plus the user's name and the firm's names: the only hits are the firm's monday slug and account id in `sandbox-accounts.txt` and the firm's renderings in `leak-terms.txt`, both by design (note 9), and the user's GitHub handle as the archive repository owner in `record-map.md` line 69, since removed (D6, 2026-10-13).
- Pronouns: no `he`, `she`, `his`, `her` or `him` in any of the nine files.

## 8. Notes

Observations that are not acceptance failures, numbered so they can be picked up or dismissed one by one.

1. `advisory` is pinned against nothing (F5 carries it, because it changes what the bullet claims). The nearest carrier is s24, whose seat header names candidates on every file but still resolves every criterion.
2. s11's objection type `Outside the map (a capability question…)` lacks the colon of the `Outside the map: ` convention in COVERAGE.md and `sales-method.md` line 227; every other key that uses the prefix writes the colon. Fixture side.
3. The top-level `call_type` of s3 and s9 is `follow-up-demo-feedback` and of s10 `support-checkin`; neither is one of the thirteen labels. Those keys carry no type header, so the pin does not reach them, but a grader that reads `call_type` from a reviewed key will not find a label there. Fixture side, for WP14 to know.
4. Never-say rows 12 and 15 carry no G- id and say "no probe"; A§10.2's own twelfth row (a figure inherited from a colleague) has none by nature. The block is 19 lines against the roughly 40 the budget allows.
5. The compact gotcha form is two lines (the heading and one line), so the file's budget is met with 47 lines to spare, but 105 of its 413 lines exceed 400 characters and the longest is 1,262. The budgets are in lines and every file passes them; readers of the raw Markdown will find these files dense.
6. The release lint's personal-name check did not run: `~/DelOps/personal-names-index.json` does not exist on this Mac. My own sweeps found nothing, but the hashed check is the one the release depends on.
7. `leak_lint.py --terms` over `shared/` (bullet 11's second half) is WP4's and does not exist yet; `leak-terms.txt` was read by eye only.
8. "Every string `record.py check` looks for is spelled here first" is not checkable until WP2 lands; the strings a reader would expect (`unanswered`, the A11 field names, the hand-off sentence, the strand-index header, the fully qualified forms) are all present.
9. `sandbox-accounts.txt` carries the firm's monday slug and account id and `leak-terms.txt` carries the firm's renderings, the plugin's names and the assistant's names. Both are by design: the gate matches on the slug and the lint must know what to block. Handing the plugin to another firm means rewriting those rows and nothing else in `shared/`.
10. Twelve file-map rows add detail to A§7.1's owner column without changing the owner: `account.json` names the lease-mirror exception, the transcript and document rows name the `record.py` subcommand, `structure-inventory.md` adds "or a document" (A16), `version.md` names the four skills, `live-map.md` names `ledger.py live-map set`. No row is missing and no owner moved.
11. A§7.2 ships `monday_tier_source: "unknown"` while its own comment and `record-map.md` list only `preflight | client statement | unread`; `record-map.md` states no initial value for the field. Whichever is meant, the template (WP7) will have to pick one.
12. The `output_class` spelling differs inside the architecture itself: A§7.7's `strand/1` writes `configured-structure`, A§8.3 step 5's call header writes `configured structure`. F1 cannot be closed without settling this, and `record-map.md` today follows A§7.7's form for both fields.
13. Seventeen gotcha titles are reworded from the draft (contractions expanded, "(disputed)" moved into the status and evidence fields, a clause added where the entry grew). The ids are untouched, which is what A§10.2 requires.
14. The Tools relied on block is labelled a WP1 seed; the release step regenerates it from every skill and reference, so its 54 names will change when the skills exist.

## 9. Not checked, and why

- Agreement between the pinned sections and `transcript_prep.py` and `transcript_measure.py` (the lint's pinned-agreement check): the scripts are WP2 and WP5 and do not exist yet; the lint reports them as not present.
- Whether `demo_check.py gate` finds the credential line and the `never-demo` rows: WP17.
- Whether every fact in the 108 gotcha entries matches its results file line by line: I spot-checked the eighteen native-identity entries' figures (section 2, bullet 3) and read every entry for the eight fields; I did not re-derive the ninety live entries against the probe JSON.

## Appendix A: the name-agreement script

Standard library, Python 3.9; reads the shared files, the architecture and the 25 keys, prints the names as spelled and every disagreement. Paths are absolute for this Mac.

```python
#!/usr/bin/env python3
"""WP1 name agreement: shared/ against ARCHITECTURE 8.3/7.1 and the 25 keys. Stdlib, 3.9."""
import json, os, re
from collections import Counter
SH = "/Users/caramelm4/DelOps/monday-master-builder/plugins/monday-master-builder/shared"
FX = "/Users/caramelm4/DelOps/rebuild-workspace/fixtures"
AR = "/Users/caramelm4/DelOps/rebuild-workspace/design/ARCHITECTURE.md"
rd = lambda p: open(p, encoding="utf-8").read()
sm, rm, ar = rd(SH + "/sales-method.md"), rd(SH + "/record-map.md"), rd(AR)
def between(t, a, b):
    s = re.search(a, t, re.M); e = re.search(b, t[s.end():], re.M)
    return t[s.end():s.end() + e.start()]
R = re.findall(r"^\| (R\d{1,2} [^|]+?) \|", between(sm, r"^### 2\.3", r"^\*\*On R10"), re.M)
CHK = re.findall(r"`([^`]+)`", re.search(r"exactly (.+?); rows", sm).group(1))
G = [g.strip() for g in re.findall(r"^\| ([^|]+?) \| ", between(sm, r"^\*\*Stage gates", r"^A strand whose"), re.M)][1:]
ST = re.findall(r"^\| [^|]+ \| `([a-z-]+)` \|", between(sm, r"^### 2\.1", r"^### 2\.2"), re.M)
OBJ = [o.strip() for o in re.findall(r"^\| ([^|]+?) \| ", between(sm, r"^### 5\.2", r"^### 5\.3"), re.M)][1:]
SUP = re.findall(r"^\| `([^`]+)` \|", between(sm, r"^### 6\.2", r"^## 7\."), re.M)
LAB = re.findall(r"`([a-z-]+)`", re.search(r"The thirteen labels.*?: (.+?)\.\n", rm, re.S).group(1))
VOC = {m.group(1): re.findall(r"`([^`]+)`", m.group(2)) for m in
       re.finditer(r"^\| `([a-z_]+)`[^|]*\| ([^|]+) \|", between(rm, r"^## Pinned: call-type", r"^## Pinned: permitted"), re.M)}
s5 = between(ar, r"^5\. \*\*Run the pipeline", r"^6\. Write")
A = {k: [v.strip() for v in re.split(r", (?=(?:new|existing|a third|they|nobody|we|bespoke|hybrid|co-|vendor|client))", re.search(p, s5).group(1))]
     for k, p in [("seat", r"seat \(([^)]+)\)"), ("relationship", r"relationship \(([^)]+)\)"),
                  ("direction", r"direction of show \(([^)]+)\)"), ("output_class", r"output class \(([^)]+?), which is")]}
A71 = re.findall(r"`([a-z-]+)`", re.search(r"thirteen labels — (.+?) — pinned", ar).group(1))
print("labels record-map == ARCH 7.1:", LAB == A71, LAB)
for k in A: print("%-13s ARCH %r\n%14srecord-map %r  equal: %s" % (k, A[k], "", VOC[k], A[k] == VOC[k]))
keys = sorted(os.listdir(FX)); keys = [k for k in keys if re.match(r"s\d+-", k)]
crit, bad = Counter(), []
tok = {k: set(v) for k, v in VOC.items()}; fm = {"direction_of_show": "direction"}
for k in sorted(keys, key=lambda x: int(x.split("-")[0][1:])):
    key = json.load(open(os.path.join(FX, k, "answer-key.json")))
    st = Counter(); asked = 0
    for row in key["rubric"]:
        c = row["criterion"]; st[row["status"]] += 1; asked += "asked" in row
        ok = c in R or c in SUP or (re.match(r"P\d+ ", c) and c.split(" ", 1)[1] in CHK)
        if not ok: bad.append((k, "criterion", c))
        if row["status"] not in ST: bad.append((k, "status", row["status"]))
    for s in ("bleed", "upside"):
        if key["numbers"][s]["status"] not in ST: bad.append((k, "numbers." + s, key["numbers"][s]["status"]))
    ev = key["expected_verdict"]; gates = ev["gates_met"] + ev["gates_not_met"]
    lead = sorted(next((g for g in G if x.startswith(g)), "?") for x in gates)
    if lead != sorted(G): bad.append((k, "gates", gates))
    if ev["verdict"] not in ("Discovery complete", "Nearly ready", "Not ready"): bad.append((k, "verdict", ev["verdict"]))
    for o in key["objections"]:
        t = o["type"]
        if not (any(t.startswith(x) for x in OBJ) or t.startswith("Outside the map: ")): bad.append((k, "objection", t[:70]))
    def th(o, p=""):
        if isinstance(o, dict):
            for a, b in o.items(): yield from th(b, p + "/" + a)
        elif isinstance(o, list):
            for i, b in enumerate(o): yield from th(b, p + "[%d]" % i)
        elif "type_header" in p and "signals" not in p: yield p.rsplit("/", 1)[-1], o
    for f, v in th(key.get("intake", {})):
        f2 = fm.get(f, f)
        if f2 == "label" and v not in LAB: bad.append((k, "label", v))
        elif f2 in tok and v not in tok[f2]: bad.append((k, "header." + f, str(v)[:50]))
    print("%-36s statuses %s asked=%d verdict=%s" % (k, dict(st), asked, ev["verdict"]))
print("\nDISAGREEMENTS (%d):" % len(bad))
for b in bad: print("  ", b)
```

## Appendix B: the other checks, as run

1. **Gotcha structure.** Headings matched `^## (G-\d+) · (.+)$`; each entry's body (to the next heading) was required to contain `Claim:`, `Surface:`, `Ring:`, `Do instead:`, `Evidence:` followed by a `20\d\d-\d\d-\d\d` date before `Probe:`, `Probe: (read-only|sandbox write)` with `probe-catalog.md`, `Impact: (high|medium|low)` and `Status:` in the five-word vocabulary; a full block was any entry whose body starts `- Claim:`; ids were compared with `^### (G-\d+)\. (.+)$` in the gotchas draft; every `G-\d+` in the file was resolved against the heading set; the never-say rows were `^\d+\. ` lines after `## Never say`.
2. **`record-map.md` against section 7.** The `Path` cells of both file-map tables were compared as sets and in order; the `Written by` and `Budget` cells were diffed per row; the log types were the backticked tokens between `Types:` and the sentence end in both files; the `client/2` and `strand/1` fields were the `key: ` lines of the two YAML blocks in A§7.2 and A§7.7, each looked up in the matching record-map section; the A§7.3 field names were every `"name":` in that section, each looked up as a whole word in the `account/1` and `build/2` sections; the markers were the first cells of both marker tables; the hand-off sentence was the italic quotation in A§7.9 searched for verbatim.
3. **Acceptance strings.** Each string the bullets name for `native-objects.md`, `safety.md`, `house-style.md`, `read-back.md`, `sandbox-accounts.txt` and `sales-method.md` was searched for verbatim; the two misses were `two stems` (the file writes "Two stems:") and `forgeable` (the file writes "spoofable"), both wording only.
4. **Sweeps.** `grep -w -i` for consultant; a Python pass over each file with code spans and fenced blocks removed, collecting `\b[A-Z][A-Z'’-]{2,}\b` minus an acronym list, and `\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b` minus ordinary title-case words; `grep -i -E` over a hand list of every fixture organisation, person, place and product name, the design's example names, the user's name and the firm's names.
5. **Budgets.** `wc -l` and `wc -c` per file; the trailing byte checked for a newline.
