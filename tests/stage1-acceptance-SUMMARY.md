# Stage-1 acceptance: summary

Written on 2026-09-20 after the fix pass over the three acceptance reports beside this file (`stage1-acceptance-shared.md`, `stage1-acceptance-fixtures.md`, `stage1-acceptance-skeleton.md`). Every must-fix item those reports raised is applied; every mechanical check they describe was re-run afterwards on the Mac's Python 3.9.6 and the results are recorded in section 3. Nothing was committed. The one rule applied where two files disagreed on a string that must match character for character: the reviewed keys s1 to s10 win, then `shared/record-map.md`, then everything else.

## 1. What passed, before and after

Everything the three reports marked as passing still passes and was not touched: the two manifests, `.gitignore`, the fifteen stage-0 blocks and their defaults, the lint's own tests, the R-names, per-pain checks, gates and verdicts, the scope matrix, the A16 document rules, the narrowed conflict rule, `monday-gotchas.md`'s 108 entries and never-say block, `native-objects.md`, `house-style.md`, `read-back.md`, `sandbox-accounts.txt`, the field order of all 25 keys, the 2,074 located quotes, the README counts, the planted defects, and the identity sweeps.

The four checks that failed now pass:

| Report | Check | Before | After |
|---|---|---|---|
| shared, skeleton | `tools/lint_plugin.py` clean | 1 error (`monday-gotchas.md:104`) | 0 errors, 1 warning (the personal-name list is absent, as before) |
| shared | `tools/cleanroom_scan.py` over `shared/` (release check 8) | 1 eight-word run (`safety.md:51`) | 0 findings; 0 over the whole plugin tree; 0 over each of the fifteen fixture folders |
| shared | header vocabulary and objection types agree with the keys | 113 disagreements (111 header values, 2 objection types) | 0 disagreements |
| fixtures | every key under 400 lines | s24 at 400 | s24 at 397; the largest key is now s11 and s19 at 398 |
| fixtures | conventions consistent with the reviewed set | s24 `portfolio_expected: null` | `false`, the s2 convention; s1 is again the only key with `null` |
| skeleton | C7, each probe exercises the mechanism the design relies on | S0-1 and S0-6b did not | both re-shaped (section 2) |
| skeleton | C10, every `not-run` row carries a reason | three rows without one | all rows carry one |

## 2. What was fixed

Numbered as in the task's must-fix list. Line numbers are of the files as they stand now.

**1. F1, the call-type header vocabulary (`record-map.md` lines 192 to 197 against A§8.3 and the fifteen keys).** Decided under the precedence rule: `record-map.md` is the pinned home and wins over the calibration keys and over the design's prose, so its hyphenated tokens stand (`new-logo`, `no-show`, `configured-structure`, `small-group`, `live-approver-present` and the rest; the seat values and the thirteen labels were already the same three ways). Every `intake.type_header` in s11 to s25 was re-spelled to those tokens: the six dimension and modifier fields, the per-segment `direction_of_show` values (s15, s19, s21), both calls of s22 and all five files of s24. Each value's prose moved to a `<field>_note` beside it, the convention s20 and s21 already used, so no reasoning was lost; the three prose fields of s19 that stated the value (`purpose_of_this_fixture`, `accepted_behaviours[0]`, the header's `proposal`) now name the token. The modifier mapping was by the authors' own prefixes: `small group:` and `small:` to `small-group`, `large group:` to `large-room`, `not live:` and `no:` to `not-live`, the approver-present and approver-absent phrasings to `live-approver-present` and `live-approver-absent`; s24's client-free call review is `one-to-one` (two speakers, both seller side) with money `live-approver-absent` (price and tier decided, no client). `record-map.md` gained one sentence after the table (line 199) recording that A§8.3 names the same values as prose, that the token is the machine form the header, the scripts and the keys carry (and, for the output class, the spelling A§7.7 already gives the strand), and where the two modifiers' values come from; it adds no backticked span, so the pinned token set is unchanged (55 tokens). The fifteen READMEs and `COVERAGE.md` now describe the header as the pinned tokens rather than "the vocabulary of 8.3 step 5 verbatim", and each README's review section carries a dated line saying what changed and that no quote, location, grade or count did.

**2. F2, the 5.2 row.** `sales-method.md` line 240 now reads `Changing what you built for us costs us`, the string s21 types; line 243's short form reads `changing what you built for us costs us`. The 5.2 rule on line 227 (`Outside the map: ` only for objections with no home in the map) is now true of the table.

**3. F3, `safety.md` line 51.** Row IR-03 reworded: `The first subitem created on a classic board | the board gains a permanent subtasks column and a root-level subitems board`. The scan reports nothing; the longest run now shared with `learn-api-errors.md:642` is four words.

**4 and 11. F4, `monday-gotchas.md` line 104.** The quoted platform message in G-26 is in a code span, which the lint's contract exempts; G-25's quoted message two lines above was put in a code span too, so the two adjacent entries follow one convention and G-25 does not depend on its text happening to carry no all-caps word. WP16's lint was not loosened.

**5 and 7. F5, the `advisory` pin.** Decided the second way the fixtures report offered: no fixture gains an unresolved type dimension, because the plan already records the position. `BUILD-PLAN.md` section 4.3, item 8, says "Every fixture resolves; none exercises the conservative fallback" and assigns the positive `advisory` case to a constructed unresolvable fragment (H50); making s24's seat unresolved would contradict that and turn a proposed-with-candidates header (which is what s24 has, and what `record-map.md` distinguishes from `unresolved`) into a re-grade with knock-on effects on R10, R12 and the gates. So: the eight README sentences that said another calibration fixture carries the case (s11, s12, s13, s16, s17, s19, s21, s22; the report counted seven, s17's "carry those" covers both values) now say no calibration fixture carries a positive `advisory` row and where the positive case lives; `COVERAGE.md`'s statuses paragraph says the same instead of leaving it open; and `sales-method.md` line 27, which had said the four calibration values "appear only in the calibration keys", now states which keys carry which value and that `advisory` is carried by none, with the H50 fragment and s25's document-only assertion named. The WP1 acceptance bullet in `BUILD-PLAN.md` (line 107) still says all four values are pinned against keys "which exist in stage 1"; that one clause is the design owner's to narrow (section 4).

**6. s24 at 400 lines.** `account_context.products_enabled` (two entries) is printed on one line, as every other entry in the key is; 397 lines. The README's file table says 397.

**8. s24 `portfolio_expected`.** `null` became `false` with `portfolio_reason` reworded to the s2 convention (no account and no tier, the previous seller's Pro held as her claim, the tier read at preflight and the portfolio question asked then if it is Enterprise). The README's products line, its review section and `COVERAGE.md`'s convention line agree; the 4.2 row and s25's README, which say s1 is the only `null`, are true again.

**9. S0-1.** A `probe-root` skill was added to the probe plugin (`tests/stage0/probe-plugin/skills/probe-root/SKILL.md`). Its body carries `${CLAUDE_PLUGIN_ROOT}` three times in the form a shipped skill uses (A§5.2 rung 1): a Read of `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`, then `echo` and `ls` of `${CLAUDE_PLUGIN_ROOT}/hooks` in the device shell and in the cloud shell, and it tells the model not to supply a path of its own. The README's S0-1 block now says `Use the probe-root skill`, on Cowork and then on Claude Code, explains why a typed path cannot test the mechanism, and its yes condition asks for a path that exists with `dump.sh` listed rather than one ending in `probe-plugin` (the skeleton report's note 2). The `results.md` row names the new question and surfaces.

**10. S0-6b.** A `probe-agent-wildcard` agent was added (`tests/stage0/probe-plugin/agents/probe-agent-wildcard.md`): no `tools` line, `disallowedTools: mcp__*` alone, the instruction to try the monday tool once and write nothing. The S0-6b block launches it and says why `probe-agent` is not used (its allowlist hides the connector on both branches); `probe-agent` is unchanged for S0-5. The plugin's inventory line in the README counts a root skill and three agents.

**Also done, beyond the list.** The three `not-run` rows without a reason (S0-4, S0-6b, S0-7) carry one, so `results.md` follows its own rule and C10 passes; a dated history line records the two probe changes. s11's one objection typed `Outside the map (…)` now uses the `Outside the map: ` colon form of section 5.2 (the shared report's note 2), with its README count unchanged.

## 3. Checks re-run, with results

From the repo root, Python 3.9.6, standard library only:

- `python3 tools/lint_plugin.py`: `0 error(s), 1 warning(s), 6 not present yet, 10 file(s)`, exit 0. The warning is the absent personal-name list, as before.
- `python3 tools/cleanroom_scan.py --tree plugins/monday-master-builder/shared <the five dossier/learn-*.md files>`: `0 finding(s)`, exit 0. The same over the default tree (the whole plugin): 0. The same over each of the fifteen fixture folders: 0 each.
- `python3 -m unittest discover -s tests/unit`: 31 tests, OK.
- `claude plugin validate --strict` on `plugins/monday-master-builder`, on `.` (the marketplace) and on `tests/stage0/probe-plugin` (with the new skill and agent): validation passed, three times.
- The shared report's appendix A script: labels equal three ways; the three record-map-versus-A§8.3 comparisons print `equal: False` for relationship, direction and output class, which is the recorded decision; `DISAGREEMENTS (0)` across the 25 keys on statuses, criteria, gates, verdicts, objection types and header values.
- The fixtures report's appendix A script: `field_order_check: 25 key(s), 0 failure(s)`, `intake` last on s11 to s25.
- The fixtures report's appendix B script: `TOTAL located quotes: 2074 at location, 1 image labels, 0 failures`.
- s24 re-measured against its README: 36 rubric rows (25 met, 7 partial, 2 missing, 2 met-with-residual; `asked` 31 true, 5 false), 9 pain entries, 12 objections, 29 traps and 8 look-alikes, 19 leak entries, 3/5/1 requested changes, 13 commitments, 11 questions, 14 vocabulary, 9 entities, 6 integrations, 6 signals, 17 accepted behaviours, Nearly ready with 3 gates met and 2 not, build true; all 262 quote strings verbatim in the five recordings. Unchanged.
- Every calibration key parses, keeps its top-level field order, and is under 400 lines (s11 398, s12 393, s13 351, s14 350, s15 392, s16 378, s17 389, s18 381, s19 398, s20 392, s21 274, s22 333, s23 349, s24 397, s25 371); every header value in the fifteen is one of the pinned tokens.
- Size budgets: `record-map.md` 254 of 300, `sales-method.md` 286 of 340, `safety.md` 183 of 300, `monday-gotchas.md` 413 of 460, the other shared files unchanged; `tests/stage0/README.md` 86 of 95, `results.md` 40 of 130; every file ends with a newline.
- Sweeps over every new and edited file: no "consultant", no he/she/his/her, no all-caps emphasis word, no personal name for the user.

## 4. What remains, and why

1. **`BUILD-PLAN.md` line 107.** The WP1 bullet says `advisory` is pinned against calibration keys that carry it and that they exist in stage 1. No key carries it; the plan's own 4.3 item 8 says why. The one-clause narrowing (the positive case is the constructed fragment, H50) is an edit to design text, which this pass does not own.
2. **A§8.3 step 5 and H50 spell the header values as prose.** `record-map.md` pins the hyphenated tokens and the keys now carry them; the design's prose form (`they show their current state`, quoted again in H50's row) is recorded in `record-map.md` as the human description of the same values. Whether A§8.3 should also show the token form is the design owner's call; nothing in the plugin reads A§8.3 for these strings.
3. **The header field name.** `record-map.md` pins the field as `direction`; the keys write `direction_of_show` (and a `direction_of_show_note`). The reports treated that mapping as given and it was not in the must-fix list; WP14's grader will read the key's field, and every README documents the key's field names. Left as is, recorded here.
4. **Two client attendees and the room-shape token.** s22's first call and s24's pricing call have two client speakers; their authors wrote "small group", so they carry `small-group`. The design defines a group as more than two client attendees (C27), and the token set has no separate two-attendee value; the new sentence in `record-map.md` states C27's definition, and whether `small-group` switches on the group measures for a two-attendee call is for WP5's detector and WP8's `call-types.md` to settle.
5. **The user's review of s11 to s25.** WP18's acceptance requires it before the fixtures are used; every `COVERAGE.md` row still says "user review pending". This pass added to what there is to review: the header re-spelling, s24's `false`, s11's colon.
6. **Python 3.11.** Not installed on this Mac; the tests ran on 3.9.6 (and, in the skeleton pass, 3.13). Release check 2's 3.11 run is still owed and needs a download the user decides on.
7. **The personal-name lint check** is inert until `~/DelOps/personal-names-index.json` exists; the hand sweeps stand in for it.
8. **`leak_lint.py --terms`** over `shared/` and the fixtures is WP4's, stage 2, as the plan places it.
9. **Stage 0** is still the user's to run by hand; S0-1 and S0-6b are now shaped to answer their questions. The skeleton report's note 3 (S0-14's dump lands beside the installed copy) was left as a note.

## 5. Is stage 1 complete?

Mechanically, yes: every must-fix item is applied, every check the three reports describe passes, and no acceptance line of WP0, WP-S0, WP16, WP1 or WP18 fails on anything a script can check. It is not formally closed, for two reasons that this pass could not remove: WP18's acceptance needs the user's review of the fifteen calibration fixtures, and two one-line amendments sit in design text outside this pass's ownership (items 1 and 2 above). Neither blocks the stage-2 packages from starting against `shared/` as it now stands.
