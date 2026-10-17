# Leak-trap fixture for `leak_lint.py`

Internal test data: never client-facing. This folder is the specification `scripts/leak_lint.py` is graded against (WP4, PLAN section 4, DECISIONS section 3). Each planted case carries one kind of leak and has one clean twin in the same shape, so the lint is graded on false positives as well as misses. Every name, figure, id, address and firm rendering in it is invented; the closed list is at the end of this file.

`manifest.json` lists every case in machine-readable form, and `tests/unit/test_leak_fixture.py` checks the fixture against it without running the lint. Step 6 adds the grading of the lint to that file. This README says the same as the manifest in words, so the cases can be checked by someone who reads no code.

Counts: 125 planted cases, 125 twins, 24 payload kinds, 290 files in this folder.

## How a case runs

Nothing here touches a real home. For each case the test builds a fresh temporary home:

1. Make an empty temporary folder and set MMB_HOME to it.
2. Copy settings and local_terms to their 'to' paths under the home.
3. Copy both records to their 'to' paths under the home.
4. If the case names an overlay, copy the overlay's files over record a, path for path.
5. Run leak_lint.py index from each record in index_from order (--record <home>/clients/<slug>).
6. Install the case's files: copy each 'from' to its record-relative 'to', creating folders; for a 'zip' entry, zip every file under that fixture folder with zipfile, member names relative to it in POSIX spelling, and write the archive to 'to'.
7. Run leak_lint.py --record <home>/clients/<slug of the case's record> <command> <args...>.
8. A planted case passes when the exit code equals 'exit', the printed verdict equals 'verdict' and every 'expect' entry is matched by a finding of the same rule and severity at the same 'where' (and the same class when 'class' is not null); other findings are reported, not failed.
9. A twin passes when the exit code equals 'exit', there is no finding of severity block, and every 'expect' entry (a warning the twin is known to carry) is matched.
10. A case with 'unchanged' also proves its installed file is byte-equal after the run.

Every case runs against record a, `wrenfold-joinery`. Record b, `marlbeck-freight`, is the other client the wall must keep out. Drafts go into `strands/001-quote-tracker/drafts/` (strand 002 for one case), payloads into `.work/strands/001-quote-tracker/`, a blueprint to `strands/001-quote-tracker/solution/blueprint.md`, a summary to `strands/001-quote-tracker/SUMMARY.md` and an intake case to `calls/2026-09-29-discovery.md`. A `.docx` case is a folder of XML text files that the test zips; no binary file is kept here.

## How to read an outcome

- **blocks**: exit 1, with at least the findings listed, each of severity block.
- **warns**: exit 2, the warnings listed, and no block.
- **caution**: exit 2, a finding an allowlist row cleared, and no block.
- **limit**: no string rule reaches this shape. The case exits 0 with no block, and the test asserts that, so a later rule that reaches it is seen. Where an authoring rule guards a limit, the limit names it; the others rest on the user's read of the text before it goes out.
- **passes**: a twin. It has no block; where it carries a warning, the warning is named in its row.

A planted case may also raise findings beyond the ones listed (a sentence can hold two leaks); the grading reports them and does not fail on them. A twin fails on any block.

## Files

| Path | What it is |
|---|---|
| `manifest.json` | every case: id, files, twin, overlay, install paths, command and arguments, mode, verdict, exit code, expected findings, rules, categories |
| `README.md` | this file |
| `.gitattributes` | keeps every file here LF on every system |
| `home/local/settings.json` | the test `settings/1`: the invented firm, its renderings and the user's invented account structure |
| `home/local/leak-terms.txt` | the test local list: one colleague above the first class line, and the firm's phonetic row and whitelist |
| `records/wrenfold-joinery/` | client record a, the record every case runs in |
| `records/marlbeck-freight/` | client record b, the other client |
| `overlays/<name>/` | files laid over record a for the cases that name the overlay |
| `cases/trap/`, `cases/key/`, `cases/rule/` | draft cases, one Markdown file per planted case and per twin |
| `cases/payload/` | payload cases, one JSON tool input per planted case and per twin |
| `cases/blueprint/`, `cases/summary/`, `cases/intake/` | a blueprint, a strand summary and a new call summary, each with its twin |
| `docx/<case>/` | the XML parts of a `.docx` case, zipped by the test |

## The test home

`settings.json` names the firm `Thymbel Advisory` with the renderings `Thymbel`, `Thymbel Advisory` and `thymbeladvisory.example`; the default build account `quarry-lane-build` (id `52806314`); two never-shown workspaces, `Pipeline Hub Internal` (`60417283`) and `Rate Card Vault` (`60417291`); and the GitHub archive account `quarry-lane-ops`. All of it is invented.

`leak-terms.txt` holds `Ines Calloway` above the first class line (class local, the user's colleague), then `class: firm` with `phonetic: Thymbel` and `whitelist: thimble`. The ordinary word thimble has the same phonetic key as the firm (`0MPL` under DECISIONS X32), so it blocks until that whitelist row names it.

## The two client records

Record a, `wrenfold-joinery` (Wrenfold Joinery, a kitchen joinery):

| File | What the cases use it for |
|---|---|
| `CLIENT.md` | the name and slug, the strand index (001 quote tracker, 002 fitting schedule) and the stakeholders |
| `research/2026-09-01-brief.md` | an internal file. The headcount 46 with no cost word (a record number); the cost figures 263,480, 73,000, 96,400, 23,750, 5,000, 22%, 41,200 and the seller's day rate 1,450, each beside a cost word; the internal runs the copied-run cases copy (the edge banding machine, the laminate offcuts, the warped oak fronts, the previous supplier's claim, the panel saw schedule, the cutting list); the current and former supplier; the outside contact; and the ordinary words skipper, silver, lantern, market, fresh, freight, contact and route, so that this record holds the everyday words record b uses in its names |
| `calls/2026-09-08-discovery.transcript.txt` | the raw transcript; its header is the only place holding the meeting id 8314 2290 57 |
| `calls/2026-09-08-discovery.md` | the call summary. Outside its client-safe block: two `[Q]` lines (one with the loaded rate 38), the 14 hours a week beside a cost word, the placeholder price 9,900, the `[X]` demo line with 12,600 and Halloran Doors, a run of common words (they will get back to us on that), the client's word callback and the objection. Inside the block: a sentence about a single board of open kitchen quotes, and a `[Q]` quote of twelve words |
| `inputs/2026-09-15-panel-procedure.txt` | the client's own document: its steps 3 and 4 are the runs the copied-run placement cases use |
| `inputs/2026-09-15-panel-procedure.md` | the document snapshot: a `[Q/doc]` extract of step 3, an analyst note on the supply clause (internal text), a client-safe block about edging, and a `## Conflicts` row that repeats step 4 |
| `strands/001-quote-tracker/solution/exclusions.md` | `Corvel Systems`, `Kestrin Boards`, `Tamsin Rook` |
| `strands/001-quote-tracker/solution/allowlist.md` | one row: `callback`, the client's own word, with the user's OK |
| `strands/001-quote-tracker/STRAND.md`, `strands/002-fitting-schedule/STRAND.md` | strand front matter; strand 002 has no allowlist |

Record b, `marlbeck-freight` (Marlbeck Freight, a haulage firm):

| File | What the wall reads from it |
|---|---|
| `CLIENT.md` | the name, the slug and the stakeholders Perrin Haldane and Quilla Oduya |
| `research/2026-08-12-brief.md` | the fuel spend 186,730 beside a cost word; the customer Tollmere Fresh Market and its initials TFM; the product Dockon; the partner Silver Lantern; Wendell Ayo, named only in this body line; the counterparty Brannock Cold Store and its part-owner Quessel Holdings |
| `calls/2026-08-19-discovery.md` | the alias table (Skipper is Perrin Haldane), the contact address and a `[Q]` line |
| `strands/001-route-board/solution/exclusions.md` | the term `cold-chain surcharge` |

The records are excerpts: they hold what the cases need and nothing else, written in the record-map's shapes. Sentences in record b start with common words, and record a also holds the ordinary words of record b's names, so a twin's everyday words are never the other client's alone.

## Overlays

| Overlay | What it changes in record a |
|---|---|
| `allowlist-attempts` | adds seven allowlist rows to strand 001 that try to clear a figure, a quote, a copied run, a marker, a pain id, an exclusion and the other client's name |
| `call-unmarked` | the same call summary with its two client-safe marks removed, so the block's text is ordinary internal text |
| `snapshot-unmarked` | the same document snapshot with its two client-safe marks removed |
| `third-party-excluded` | adds the outside contact Gideon Pryce to strand 001's exclusions.md |

## Cases

One row per planted case. The planted text column gives the line (or the payload path, or the `.docx` part) and the planted words. The category column uses the ids of DECISIONS section 3: `trap:` for a row of 3.2 (the twenty categories of A§:918, with the organisation-name and customer categories split into their parts), `key:` for a row of 3.1, `rule:` for a rule case of BP:158 (3.3) and `payload-kind:` for a payload kind of `Pinned: leak`.

### The trap categories of A§:918 (26)

| Case | Planted file | Planted text, where | Rule (class) | Category | Expected | Twin file | Twin expected | Why the twin is clean |
|---|---|---|---|---|---|---|---|---|
| T01-p | `cases/trap/T01-p.md` | line 1 `THYMBEL ADVISORY`; line 2 `marlbeck FREIGHT` | term (firm); wall (name) | trap:case-varied-names | blocks, exit 1 | `cases/trap/T01-t.md` | passes, exit 0 | the firm and the other client are replaced by the office and the carrier |
| T02-p | `cases/trap/T02-p.md` | line 1 `Thymbel's`; line 2 `Marlbeck Freight’s` | term (firm); wall (name) | trap:possessive-names | blocks, exit 1 | `cases/trap/T02-t.md` | passes, exit 0 | the possessives stay; the names go |
| T03-p | `cases/trap/T03-p.md` | line 1 `Thymbel, Advisory`; line 2 `Marlbeck,`; line 4 `Ines, Calloway` | term (firm); wall (name); term (local) | trap:comma-split-names | blocks, exit 1 | `cases/trap/T03-t.md` | passes, exit 0 | no name, split or whole |
| T04-p | `cases/trap/T04-p.md` | line 1 `8314 2290 57` | term (id-patterns) | trap:identifier-in-header; key:K24 | blocks, exit 1 | `cases/trap/T04-t.md` | passes, exit 0 | a date and a time, which are never ids |
| T05-p | `cases/trap/T05-p.md` | line 1 `Haldane` | wall (name) | trap:alias-ordinary-word | blocks, exit 1 | `cases/trap/T05-t.md` | passes, exit 0 | the alias word in its everyday sense, with no surname; the word is also in this record |
| T06-p | `cases/trap/T06-p.md` | line 1 `Wendell Ayo` | wall (name) | trap:name-from-body | blocks, exit 1 | `cases/trap/T06-t.md` | passes, exit 0 | the office in place of the name |
| T07-p | `cases/trap/T07-p.md` | line 1 `TFM` | wall (name) | trap:customer-acronym | blocks, exit 1 | `cases/trap/T07-t.md` | passes, exit 0 | no initials |
| T08-p | `cases/trap/T08-p.md` | line 1 `Tollmere Fresh Market` | wall (name) | trap:customer-full-name | blocks, exit 1 | `cases/trap/T08-t.md` | passes, exit 0 | a common noun in place of the name |
| T09-p | `cases/trap/T09-p.md` | line 1 `1,450`; line 1 `cost of waiting` | figure; term (method) | trap:seller-commercial-terms; key:K08 | blocks, exit 1 | `cases/trap/T09-t.md` | passes, exit 0 | no figure and no method words |
| T10-p | `cases/trap/T10-p.md` | line 1 `03 11 2026` | split-figure, warn | trap:split-date | warns, exit 2 | `cases/trap/T10-t.md` | passes, exit 0 | the same date written whole, which is not a figure |
| T11-p | `cases/trap/T11-p.md` | line 1 `decision maker` | paraphrase (assessment) | trap:assessment-of-individual; key:K13 | blocks, exit 1 | `cases/trap/T11-t.md` | passes, exit 0 | the approval described by team, with no person and no cue |
| T12a-p | `cases/trap/T12a-p.md` | line 1 `golf` | paraphrase (personal-life) | trap:small-talk; key:K25 | blocks, exit 1 | `cases/trap/T12a-t.md` | passes, exit 0 | the same shape about the delivery week |
| T12b-p | `cases/trap/T12b-p.md` | `Everyone joked about the rain before the call started.` | none (limit) | trap:small-talk; key:K25 | limit, exit 0 | `cases/trap/T12b-t.md` | passes, exit 0 | an agenda line in the same shape |
| T13a-p | `cases/trap/T13a-p.md` | `Ask Gideon Pryce to check the extractor fitting.` | none (limit) | trap:third-party-in-passing; key:K22 | limit, exit 0 | `cases/trap/T13a-t.md` | passes, exit 0 | the role named, not the person |
| T13b-p | `cases/trap/T13b-p.md` (overlay third-party-excluded) | line 1 `Gideon Pryce` | exclusion | trap:third-party-in-passing; key:K22 | blocks, exit 1 | `cases/trap/T13b-t.md` | passes, exit 0, overlay third-party-excluded | the role named, not the person, under the same overlay |
| T14-p | `cases/trap/T14-p.md` | line 1 `Silver Lantern` | wall (name) | trap:partner-two-ordinary-words | blocks, exit 1 | `cases/trap/T14-t.md` | passes, exit 0 | the two words apart in one sentence; both are also in this record |
| T15-p | `cases/trap/T15-p.md` | line 1 `Marlbek` | wall (name) | trap:corrupted-name-in-hypothetical; key:K30 | blocks, exit 1 | `cases/trap/T15-t.md` | passes, exit 0 | the carrier in place of the misspelt name |
| T16-p | `cases/trap/T16-p.md` | line 1 `Dockon` | wall (name) | trap:fused-product-name | blocks, exit 1 | `cases/trap/T16-t.md` | passes, exit 0 | the two words written apart |
| T17-p | `cases/trap/T17-p.md` | line 1 `Kestrin Boards` | exclusion | trap:vendor-substitution | blocks, exit 1 | `cases/trap/T17-t.md` | passes, exit 0 | the current supplier, which is in this record and in no exclusion |
| T18-p | `cases/trap/T18-p.md` | line 1 `perrinhaldane` | wall (name) | trap:email-separator-lost | blocks, exit 1 | `cases/trap/T18-t.md` | passes, exit 0 | no address |
| T19-p | `cases/trap/T19-p.md` | line 1 `Perrin`; line 1 `Quilla`; line 1 `Wendell` | wall (name) | trap:first-names-in-quotation | blocks, exit 1 | `cases/trap/T19-t.md` | passes, exit 0 | a common noun inside the same quotation |
| T20-p | `cases/trap/T20-p.md` | line 1 `Brannock Cold Store`; line 1 `Quessel Holdings` | wall (name) | trap:counterparty-owner-tools | blocks, exit 1 | `cases/trap/T20-t.md` | passes, exit 0 | roles in place of names and two tool categories, which pass |
| T21-p | `cases/trap/T21-p.md` | line 1 `quit` | paraphrase (departure) | trap:departure-hypothetical | blocks, exit 1 | `cases/trap/T21-t.md` | passes, exit 0 | the same hypothetical about a sheet |
| T22a-p | `cases/trap/T22a-p.md` | line 1 `Pipeline Hub Internal`; line 2 `quarry-lane-ops` | seller-account (seller-account) | trap:seller-account-structure | blocks, exit 1 | `cases/trap/T22a-t.md` | passes, exit 0 | ordinary places in the same shape |
| T22b-p | `cases/trap/T22b-p.md` | line 1 `60417283` | seller-account (seller-account) | trap:seller-account-structure; rule:monday-id-link | blocks, exit 1 | `cases/trap/T22b-t.md` | passes, exit 0 | an unrelated invented id inside the same link, which the id row exempts |
| T23-p | `cases/trap/T23-p.md` | line 1 `injury` | paraphrase (health-identity) | trap:health-remark-absent-person; key:K12 | blocks, exit 1 | `cases/trap/T23-t.md` | passes, exit 0 | the same remark about a van |

### The kinds of leak the answer keys describe (38)

| Case | Planted file | Planted text, where | Rule (class) | Category | Expected | Twin file | Twin expected | Why the twin is clean |
|---|---|---|---|---|---|---|---|---|
| K01-p | `cases/payload/K01-p.json` | $.lines[0] `Rework runs at 263480 a year.`; $.lines[1] `Rework runs at 263,480 a year.`; $.lines[2] `Rework runs at $263k a year.`; $.lines[3] `Rework runs at 263k a year.`; $.lines[4] `Rework runs at two hundred and sixty-three thousand a year.`; $.lines[5] `Rework runs at 264k a year.` | figure | key:K01 | blocks, exit 1 | `cases/payload/K01-t.json` | passes, exit 2 (number warn) | an unrelated invented figure in the same six forms; each is a number warning |
| K02-p | `cases/payload/K02-p.json` | $.markdown `A fitter is charged at 38 an hour.` | figure | key:K02 | blocks, exit 1 | `cases/payload/K02-t.json` | passes, exit 2 (record-number warn) | the same number with no cost word beside it: a record-number warning, kept |
| K03a-p | `cases/payload/K03a-p.json` | $.markdown `Quote checks take 14 hours a week at 38 an hour.` | figure | key:K03 | blocks, exit 1 | `cases/payload/K03a-t.json` | passes, exit 0 | a process sentence with no number |
| K03b-p | `cases/payload/K03b-p.json` | $.markdown `Quote checks take 14 hours a week.` | record-number, warn | key:K03; rule:flag-do-not-remove | warns, exit 2 | `cases/payload/K03b-t.json` | passes, exit 0 | a process sentence with no number |
| K04-p | `cases/payload/K04-p.json` | $.markdown `Fixing quotes is worth 96,400 a year.` | figure | key:K04 | blocks, exit 1 | `cases/payload/K04-t.json` | passes, exit 2 (number warn) | an unrelated invented number: a number warning |
| K05-p | `cases/payload/K05-p.json` | $.markdown `Scrapped doors came to 23.8k last spring.` | figure | key:K05 | blocks, exit 1 | `cases/payload/K05-t.json` | passes, exit 0 | no number |
| K06-p | `cases/payload/K06-p.json` | $.markdown `Orders over 5,000 go to approval.` | figure | key:K06 | blocks, exit 1 | `cases/payload/K06-t.json` | passes, exit 2 (number warn) | an order size that is in no record: a number warning |
| K07-p | `cases/payload/K07-p.json` | $.markdown `The margin on kitchens is 22%.` | figure | key:K07 | blocks, exit 1 | `cases/payload/K07-t.json` | passes, exit 2 (number warn) | another percentage, which matches no cost figure: a number warning |
| K09-p | `cases/payload/K09-p.json` | $.markdown `Start with 9,900 for the first build.` | figure | key:K09 | blocks, exit 1 | `cases/payload/K09-t.json` | passes, exit 0 | no number |
| K10a-p | `cases/key/K10a-p.md` | line 1 `oak fronts warped in the damp loading bay` | copied-run | key:K10 | blocks, exit 1 | `cases/key/K10a-t.md` | passes, exit 0 | no run of six words from the record |
| K10b-p | `cases/key/K10b-p.md` | `Some doors bent out of shape after a wet week in storage.` | none (limit) | key:K10 | limit, exit 0 | `cases/key/K10b-t.md` | passes, exit 0 | a neutral storage line |
| K11-p | `cases/key/K11-p.md` | line 1 `burnt out` | paraphrase (emotional) | key:K11 | blocks, exit 1 | `cases/key/K11-t.md` | passes, exit 0 | the same shape about a report |
| K12-p | `cases/key/K12-p.md` | line 1 `holiday` | paraphrase (personal-life) | key:K12 | blocks, exit 1 | `cases/key/K12-t.md` | passes, exit 0 | the same shape about a saw |
| K13b-p | `cases/key/K13b-p.md` | `Lise Varrow carries the title of office coordinator yet plans every install.` | none (limit) | key:K13 | limit, exit 0 | `cases/key/K13b-t.md` | passes, exit 0 | the role, not the person |
| K14-p | `cases/key/K14-p.md` | line 1 `never answers` | paraphrase (colleague-remark) | key:K14 | blocks, exit 1 | `cases/key/K14-t.md` | passes, exit 0 | the same shape about a phone |
| K15a-p | `cases/key/K15a-p.md` | line 1 `every quote goes out late because the cutting list is wrong` | quote | key:K15 | blocks, exit 1 | `cases/key/K15a-t.md` | passes, exit 0 | the point restated in new words, no run of six |
| K15c-p | `cases/key/K15c-p.md` | `The office doubts the fitters will keep a board current from site.` | none (limit) | key:K15 | limit, exit 0 | `cases/key/K15c-t.md` | passes, exit 0 | a plain wish in the same shape |
| K16-p | `cases/payload/K16-p.json` | $.markdown `We also looked at Corvel Systems.` | exclusion | key:K16 | blocks, exit 1 | `cases/payload/K16-t.json` | passes, exit 0 | the option unnamed |
| K17-p | `cases/payload/K17-p.json` | $.name `Delivery terms with Marlbeck Freight`; $.markdown `A cold-chain surcharge applies to chilled loads. ⏎  ⏎ The fuel line was $187k.`; $.markdown `A cold-chain surcharge applies to chilled loads. ⏎  ⏎ The fuel line was $187k.` | wall (name); wall (term); wall (figure) | key:K17; rule:wall-records | blocks, exit 1 | `cases/payload/K17-t.json` | passes, exit 0 | this record's own supplier and no figure |
| K18-p | `cases/key/K18-p.md` | line 1 `Thymbel Advisory`; line 2 `monday master builder`; line 3 `claude`; line 4 `Ines Calloway` | term (firm); term (plugin); term (assistant); term (local) | key:K18 | blocks, exit 1 | `cases/key/K18-t.md` | passes, exit 0 | the same lines in neutral words |
| K19-p | `cases/key/K19-p.md` | line 1 `cost of waiting`; line 2 `R4 Met`; line 2 `R4`; line 3 `P3`; line 4 `[found]` | term (method); term (pain-ids); term (markers) | key:K19 | blocks, exit 1 | `cases/key/K19-t.md` | passes, exit 0 | look-alike ordinary text with brackets and no ids |
| K20-p | `cases/key/K20-p.md` | line 1 `STRAND.md`; line 2 `@00:14:05`; line 3 `L142-144`; line 3 `cue 82`; line 4 `talk share`; line 5 `Speaker 2` | term (id-patterns); term (markers); term (internal-vocabulary); internal-note | key:K20 | blocks, exit 1 | `cases/key/K20-t.md` | passes, exit 0 | ordinary words without separators or numbers |
| K21a-p | `cases/payload/K21a-p.json` | $.items[0].column_values<json>.text_1 `Tamsin Rook, 0770 090 0418`; $.items[0].column_values<json>.text_1 `Tamsin Rook, 0770 090 0418` | exclusion; term (id-patterns) | key:K21 | blocks, exit 1 | `cases/payload/K21a-t.json` | passes, exit 0 | the customer and the number described, not given |
| K21b-p | `cases/key/K21b-p.md` | `Deliver to the cottage on Larch Row.` | none (limit) | key:K21 | limit, exit 0 | `cases/key/K21b-t.md` | passes, exit 0 | the address described, not given |
| K23a-p | `cases/payload/K23a-p.json` | $.markdown `The maintenance contract is 41,200 a year.` | figure | key:K23 | blocks, exit 1 | `cases/payload/K23a-t.json` | passes, exit 0 | no figure |
| K23b-p | `cases/key/K23b-p.md` | line 1 `The supplier can swap the board grade with no` | copied-run | key:K23 | blocks, exit 1 | `cases/key/K23b-t.md` | passes, exit 0 | no run of six words from the record |
| K26a-p | `cases/payload/K26a-p.json` | $.markdown `Show a saving of 12,600 on the dashboard.` | figure | key:K26 | blocks, exit 1 | `cases/payload/K26a-t.json` | passes, exit 0 | no figure |
| K26b-p | `cases/key/K26b-p.md` | `Add Halloran Doors as the sample customer.` | none (limit) | key:K26 | limit, exit 0 | `cases/key/K26b-t.md` | passes, exit 0 | no name |
| K27a-p | `cases/key/K27a-p.md` | line 1 `Their nesting tool would halve offcut waste` | copied-run | key:K27 | blocks, exit 1 | `cases/key/K27a-t.md` | passes, exit 0 | a plain statement, no run of six |
| K27b-p | `cases/key/K27b-p.md` | `A new nesting tool might cut the waste in half.` | none (limit) | key:K27 | limit, exit 0 | `cases/key/K27b-t.md` | passes, exit 0 | a plain statement |
| K28-p | `cases/key/K28-p.md` | line 1 `upsell` | term (sales-framing) | key:K28 | blocks, exit 1 | `cases/key/K28-t.md` | passes, exit 0 | the backlog named as improvements |
| K29a-p | `cases/key/K29a-p.md` | line 1 `fit risk` | term (method) | key:K29 | blocks, exit 1 | `cases/key/K29a-t.md` | passes, exit 0 | a neutral word |
| K29b-p | `cases/key/K29b-p.md` | `We want this agreed before our quarter closes.` | none (limit) | key:K29 | limit, exit 0 | `cases/key/K29b-t.md` | passes, exit 0 | no deadline |
| K30-p | `cases/key/K30-p.md` | line 1 `Thymble`; line 2 `Marlbek Frate` | phonetic (firm); wall (name) | key:K30 | blocks, exit 1 | `cases/key/K30-t.md` | passes, exit 0 | the whitelisted ordinary word that sounds like the firm, and a common noun |
| K31a-p | `cases/key/K31a-p.md` | line 1 `useless` | paraphrase (colleague-remark) | key:K31 | blocks, exit 1 | `cases/key/K31a-t.md` | passes, exit 0 | a neutral aside on the same job |
| K31b-p | `cases/key/K31b-p.md` | `On the council job the paperwork runs to three forms.` | none (limit) | key:K31 | limit, exit 0 | `cases/key/K31b-t.md` | passes, exit 0 | a neutral line |
| K35-p | `cases/key/K35-p.md` | `Rework probably costs a quarter of turnover.` | none (limit) | key:K35 | limit, exit 0 | `cases/key/K35-t.md` | passes, exit 0 | no estimate |
| K36-p | `cases/key/K36-p.md` | line 1 `alias table` | term (internal-vocabulary) | key:K36 | blocks, exit 1 | `cases/key/K36-t.md` | passes, exit 0 | an ordinary list name |

### The rule cases of BP:158 (28)

| Case | Planted file | Planted text, where | Rule (class) | Category | Expected | Twin file | Twin expected | Why the twin is clean |
|---|---|---|---|---|---|---|---|---|
| R01-p | `cases/rule/R01-p.md` | line 1 `73000`; line 2 `73,000`; line 3 `73k`; line 4 `$73k`; line 5 `seventy-three thousand` | figure | rule:figures-five-formats; key:K01 | blocks, exit 1 | `cases/rule/R01-t.md` | passes, exit 2 (number warn) | an unrelated invented figure in the same five forms; each is a number warning |
| R02-p | `cases/rule/R02-p.md` | line 1 `73 000`; line 2 `seventy-` | split-figure | rule:figures-split-renderings | blocks, exit 1 | `cases/rule/R02-t.md` | passes, exit 0 | no number in any rendering |
| R03a-p | `cases/rule/R03a-p.md` | line 1 `The edge banding machine jams on long runs` | copied-run | rule:copied-run-placements | blocks, exit 1 | `cases/rule/R03a-t.md` | passes, exit 0 | no run of six words from the record |
| R03b-p | `cases/rule/R03b-p.md` | line 1 `Doors are sprayed after the carcass passes inspection` | copied-run | rule:copied-run-placements; key:K34 | blocks, exit 1 | `cases/rule/R03b-t.md` | passes, exit 0 | seven words of the client's document in inputs/, in no conflict row: exempt from the run rule, and under the eight words the quote rule needs |
| R04-p | `cases/rule/R04-p.md` | line 1 `we lose track of which quotes went out` | quote | rule:quote-eight-words; key:K15 | blocks, exit 1 | `cases/rule/R04-t.md` | passes, exit 0 | seven words of the same quote: the block is exempt from the run rule and the quote rule needs eight |
| R05-p | `cases/rule/R05-p.md` | line 1 `[Q]`; line 2 `[Q?]`; line 3 `[Q/side]`; line 4 `[Q/recon]`; line 5 `[Q/doc]`; line 6 `[X]`; line 7 `[E]`; line 8 `[I]`; line 9 `[A]` | term (markers) | rule:markers-nine; key:K19 | blocks, exit 1 | `cases/rule/R05-t.md` | passes, exit 0 | ordinary brackets |
| R06-p | `cases/rule/R06-p.md` | line 1 `P3`; line 2 `N2`; line 3 `S4`; line 4 `O1`; line 5 `C2`; line 6 `R7`; line 7 `001:B1`; line 8 `001/v0.1`; line 9 `P-07`; line 10 `G-12`; line 11 `[A12]`; line 12 `[L15]` | term (pain-ids); term (id-patterns) | rule:internal-ids; key:K19 | blocks, exit 1 | `cases/rule/R06-t.md` | passes, exit 0 | look-alike ordinary text with no ids |
| R07-p | `cases/rule/R07-p.md` | line 1 `clients/wrenfold-joinery/calls/`; line 2 `clients\wrenfold-joinery\calls\`; line 3 `clients/wrenfold-joinery\strands\001-quote-tracker\`; line 4 `C:\Users\` | term (id-patterns) | rule:record-paths; key:K20 | blocks, exit 1 | `cases/rule/R07-t.md` | passes, exit 0 | ordinary words without separators |
| R08-p | `cases/rule/R08-p.md` | line 1 `<!--` | term (id-patterns) | rule:html-comments | blocks, exit 1 | `cases/rule/R08-t.md` | passes, exit 0 | a plain tag |
| R09-p | `cases/rule/R09-p.md` | line 1 `73029184` | term (id-patterns) | rule:monday-id-link | blocks, exit 1 | `cases/rule/R09-t.md` | passes, exit 0 | the same id inside a link, which the id row exempts |
| R10a-p | `cases/rule/R10a-p.md` (overlay call-unmarked) | line 1 `The office wants a single board showing open kitchen quotes` | copied-run | rule:exempt-blocks-and-glossary | blocks, exit 1 | `cases/rule/R10a-t.md` | passes, exit 0 | the same sentence against the record as it is, where the run sits inside the marked block |
| R10b-p | `cases/rule/R10b-p.md` (overlay snapshot-unmarked) | line 1 `puts every cut panel through edging` | copied-run | rule:exempt-blocks-and-glossary | blocks, exit 1 | `cases/rule/R10b-t.md` | passes, exit 0 | the same sentence against the record as it is, where the run sits inside the marked block |
| R10c-p | `cases/blueprint/R10c-p.md` | line 12 `The cutting list names each panel by cabinet` | copied-run | rule:exempt-blocks-and-glossary | blocks, exit 1 | `cases/blueprint/R10c-t.md` | passes, exit 0 | the same run inside the glossary marks, which the run rule exempts |
| R11-p | `cases/rule/R11-p.md` | line 1 `Laminate offcuts pile up beside the panel saw` | copied-run | rule:common-word-run | blocks, exit 1 | `cases/rule/R11-t.md` | passes, exit 0 | the case under test: a run copied from the call summary that is made of common words, which the run rule ignores (X19) |
| R12-p | `cases/rule/R12-p.md` | line 1 `spreadsheet` | tool-categories | rule:tool-categories-three-two | blocks, exit 1 | `cases/rule/R12-t.md` | passes, exit 0 | two tool categories, which pass (the category rows are counted, never blocked) |
| R13a-p | `cases/rule/R13a-p.md` | line 1 `Thymbel Advisory`; line 2 `thymbel`; line 3 `thymbeladvisory.example`; line 4 `Thymbel-Advisory` | term (firm) | rule:firm-renderings-phonetic-whitelist | blocks, exit 1 | `cases/rule/R13a-t.md` | passes, exit 0 | neutral words in the same lines |
| R13b-p | `cases/rule/R13b-p.md` | line 1 `Thimbel`; line 2 `Thymbell`; line 3 `Thym Bell`; line 4 `Thimble Advisory` | phonetic (firm) | rule:firm-renderings-phonetic-whitelist; key:K30 | blocks, exit 1 | `cases/rule/R13b-t.md` | passes, exit 0 | the ordinary word that sounds like the firm, which the local list whitelists, in five everyday uses; the last joins it to the word the (Y09) |
| R14-p | `cases/rule/R14-p.md` | line 1 `46` | record-number, warn | rule:flag-do-not-remove; key:K32 | warns, exit 2 | `cases/rule/R14-t.md` | passes, exit 0 | no number of ten or more |
| R15a-p | `cases/rule/R15a-p.md` | line 1 `callback` | term (method), caution | rule:caution; key:K33 | caution, exit 2 | `cases/rule/R15a-t.md` | passes, exit 0 | the same sentence with an ordinary phrase |
| R15b-p | `cases/rule/R15b-p.md` | line 1 `callback` | term (method) | rule:caution; key:K33 | blocks, exit 1 | `cases/rule/R15b-t.md` | passes, exit 0 | the same sentence with an ordinary phrase |
| R16-p | `cases/rule/R16-p.md` | line 1 `Bearer Fx7kQ2mL9pR4tV8wZ3yB`; line 2 `password = tidewater42`; line 3 `orders:Wq8zLm3x@`; line 4 `token=Hd72kPq9Lx`; line 5 `eyJhbGciOiJIUzI1NiJ9`; line 6 `AKIAFIXTURE000000000`; line 7 `pk_test_fixture0000000000`; line 8 `ghp_fixture00000000000000000000000000000`; line 9 `xoxb-fixture-only`; line 10 `-----BEGIN PRIVATE KEY-----`; line 11 `Qm7rT2vX9pL4sW8nB3kY6hJ1dF5gZ0cAe` | credential | rule:credentials | blocks, exit 1 | `cases/rule/R16-t.md` | passes, exit 0 | the same words with no secret value |
| R17-p | `cases/rule/R17-p.md` | line 1 `Internal: never client-facing`; line 2 `note to self`; line 3 `internal only`; line 4 `Not for the client`; line 5 `Speaker 2`; line 6 `owner: "office"`; line 7 `---` | internal-note | rule:internal-notes | blocks, exit 1 | `cases/rule/R17-t.md` | passes, exit 0 | the same lines with no internal mark: the key line has no quoted value and the hyphens are followed by ordinary text |
| R18-p | `cases/rule/R18-p.md` (overlay allowlist-attempts) | line 1 `73,000`; line 2 `We lose track of which quotes went out after the second visit`; line 3 `The edge banding machine jams on long runs`; line 4 `[E]`; line 5 `P3`; line 6 `Corvel Systems`; line 7 `Marlbeck Freight` | figure; quote; copied-run; term (markers); term (pain-ids); exclusion; wall (name); allowlist, warn | rule:allowlist-limits | blocks, exit 1 | `cases/rule/R18-t.md` | passes, exit 0, overlay allowlist-attempts | neutral lines under the same overlay |
| R19-p | `cases/summary/R19-p.md` | line 2 `Every quote waits on the panel saw schedule` | copied-run | rule:summary-two-rules | blocks, exit 1 | `cases/summary/R19-t.md` | passes, exit 0 | the same heading and a line in new words |
| R20-p | `cases/intake/R20-p.md` | line 6 `burnt out` | paraphrase (emotional) | rule:client-safe-block-at-intake; key:K11 | blocks, exit 1 | `cases/intake/R20-t.md` | passes, exit 0 | a neutral line in the same block |
| R19b-p | `cases/summary/R19b-p.md` | line 2 `we lose track of which quotes went out` | quote | rule:summary-two-rules; key:K15 | blocks, exit 1 | `cases/summary/R19b-t.md` | passes, exit 0 | seven words of the same quote, under the eight the quote rule needs |
| R21-p | `cases/payload/R21-p.json` | $.workspace_id `60417283`; $.description `Copy of board 73029184`; $.notes_ref `73029184` | seller-account (seller-account); term (id-patterns) | rule:structural-ids | blocks, exit 1 | `cases/payload/R21-t.json` | passes, exit 0 | ids only under structural keys (Y08), as a digit string and as a JSON number, neither of them the user's own account structure |
| R22-p | `cases/payload/R22-p.json` | $.Thymbel<key> `Thymbel`; $.rework `263480` | term (firm); figure | rule:payload-keys-and-numbers | blocks, exit 1 | `cases/payload/R22-t.json` | passes, exit 0 | an ordinary key and a number below ten |

### One payload sample per kind (24)

| Case | Planted file | Planted text, where | Rule (class) | Category | Expected | Twin file | Twin expected | Why the twin is clean |
|---|---|---|---|---|---|---|---|---|
| P-workspace-p | `cases/payload/P-workspace-p.json` | $.name `Kitchen quotes for Corvel Systems`; $.description `Prepared by Thymbel Advisory`; $.label `S2 open` | exclusion; term (firm); term (pain-ids) | payload-kind:workspace; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-workspace-t.json` | passes, exit 0 | the same fields in neutral words |
| P-folder-p | `cases/payload/P-folder-p.json` | $.name `Quotes [X] done`; $.description `Quotes shared with Kestrin Boards`; $.label `calls/ intake` | term (markers); exclusion; term (id-patterns) | payload-kind:folder; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-folder-t.json` | passes, exit 0 | the same fields in neutral words |
| P-board-p | `cases/payload/P-board-p.json` | $.name `Quote tracker 263,480`; $.description `Mirrors board 73029184`; $.label `Tamsin Rook` | figure; term (id-patterns); exclusion | payload-kind:board; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-board-t.json` | passes, exit 0 | the same fields in neutral words |
| P-group-p | `cases/payload/P-group-p.json` | $.name `Open quotes for Corvel Systems`; $.description `Shared with Marlbeck Freight`; $.label `pwd: tidewater42` | exclusion; wall (name); credential | payload-kind:group; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-group-t.json` | passes, exit 0 | the same fields in neutral words |
| P-column-p | `cases/payload/P-column-p.json` | $.name `Next date MMB`; $.description `Quotes shared with Kestrin Boards`; $.label `note to self` | term (plugin); exclusion; internal-note | payload-kind:column; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-column-t.json` | passes, exit 0 | the same fields in neutral words |
| P-view-p | `cases/payload/P-view-p.json` | $.name `This week S2 open`; $.description `Shows the cost of waiting`; $.label `Tamsin Rook` | term (pain-ids); term (method); exclusion | payload-kind:view; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-view-t.json` | passes, exit 0 | the same fields in neutral words |
| P-form-p | `cases/payload/P-form-p.json` | $.name `Quote request for Corvel Systems`; $.description `Copied from strands/001-quote-tracker/`; $.label `<!-- x -->` | exclusion; term (id-patterns) | payload-kind:form; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-form-t.json` | passes, exit 0 | the same fields in neutral words |
| P-subitems-p | `cases/payload/P-subitems-p.json` | $.name `Quote lines 73029184`; $.description `Quotes shared with Kestrin Boards`; $.label `cowork` | term (id-patterns); exclusion; term (assistant) | payload-kind:subitems; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-subitems-t.json` | passes, exit 0 | the same fields in neutral words |
| P-dashboard-p | `cases/payload/P-dashboard-p.json` | $.name `Quote overview pwd: tidewater42`; $.description `Owned by Ines Calloway`; $.label `Tamsin Rook` | credential; term (local); exclusion | payload-kind:dashboard; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-dashboard-t.json` | passes, exit 0 | the same fields in neutral words |
| P-widget-p | `cases/payload/P-widget-p.json` | $.name `Open count for Corvel Systems`; $.description `Internal only for now`; $.label `Thymbel` | exclusion; internal-note; term (firm) | payload-kind:widget; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-widget-t.json` | passes, exit 0 | the same fields in neutral words |
| P-portfolio-p | `cases/payload/P-portfolio-p.json` | $.name `Kitchen work readiness`; $.description `Quotes shared with Kestrin Boards`; $.label `[X] done` | term (method); exclusion; term (markers) | payload-kind:portfolio; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-portfolio-t.json` | passes, exit 0 | the same fields in neutral words |
| P-project-p | `cases/payload/P-project-p.json` | $.name `Spring kitchens <!-- x -->`; $.description `Tracks the 263,480 rework total`; $.label `Tamsin Rook` | term (id-patterns); figure; exclusion | payload-kind:project; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-project-t.json` | passes, exit 0 | the same fields in neutral words |
| P-publication-p | `cases/payload/P-publication-p.json` | $.name `Quote tracker release for Corvel Systems`; $.description `Drafted with claude`; $.label `Marlbeck` | exclusion; term (assistant); wall (name) | payload-kind:publication; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-publication-t.json` | passes, exit 0 | the same fields in neutral words |
| P-activation-p | `cases/payload/P-activation-p.json` | $.name `Quote reminders on Ines Calloway`; $.description `Quotes shared with Kestrin Boards`; $.label `MMB` | term (local); exclusion; term (plugin) | payload-kind:activation; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-activation-t.json` | passes, exit 0 | the same fields in neutral words |
| P-agent-p | `cases/payload/P-agent-p.json` | $.profile.name `Kestrin Boards order chaser`; $.profile.role `Assistant from Thymbel Advisory`; $.profile.role_description `Chases quotes the office prices at 263,480 a year`; $.goal `Clear every [A] item before the build`; $.plan `1. Read the notes in strands/001-quote-tracker/. ⏎ 2. Draft a reply for the office.`; $.user_prompt `Use password: tidewater42 to sign in`; $.knowledge[0].name `Marlbeck Freight rates` | exclusion; term (firm); figure; term (markers); term (id-patterns); credential; wall (name) | payload-kind:agent; rule:payload-per-kind | blocks, exit 1 | `cases/payload/P-agent-t.json` | passes, exit 0 | the same fields in neutral words |
| P-vibe_app-p | `cases/payload/P-vibe_app-p.json` | $.prompt `Build a quote view; note to self: hide the margins`; $.app_name `master builder quotes` | internal-note; term (plugin) | payload-kind:vibe_app; rule:payload-per-kind | blocks, exit 1 | `cases/payload/P-vibe_app-t.json` | passes, exit 0 | the same fields in neutral words |
| P-ai_column-p | `cases/payload/P-ai_column-p.json` | $.name `P4 status`; $.settings.prompt `Summarise the update and mention Tamsin Rook` | term (pain-ids); exclusion | payload-kind:ai_column; rule:payload-per-kind | blocks, exit 1 | `cases/payload/P-ai_column-t.json` | passes, exit 0 | the same fields in neutral words |
| P-workflow-p | `cases/payload/P-workflow-p.json` | $.name `Corvel Systems handover`; $.description `Runs the cost of waiting check`; $.steps[0].text `Post a note that the edge banding machine jams on long runs` | exclusion; term (method); copied-run | payload-kind:workflow; rule:payload-per-kind | blocks, exit 1 | `cases/payload/P-workflow-t.json` | passes, exit 0 | the same fields in neutral words |
| P-sequence-p | `cases/payload/P-sequence-p.json` | $.name `Thymbel Advisory follow-ups`; $.steps[0].text `Remind the office about board 73029184`; $.recipients[0] `tamsin.rook@homes.example` | term (firm); term (id-patterns); exclusion | payload-kind:sequence; rule:payload-per-kind | blocks, exit 1 | `cases/payload/P-sequence-t.json` | passes, exit 0 | the same fields with this record's own order address |
| P-webhook-p | `cases/payload/P-webhook-p.json` | $.url `https://hooks.example/in?token=Fx7kQ2mL9pR4` | credential | payload-kind:webhook; rule:payload-per-kind | blocks, exit 1 | `cases/payload/P-webhook-t.json` | passes, exit 0 | the same host with no token |
| P-automation-p | `cases/payload/P-automation-p.json` | $.name `[Q] reminder`; $.request_text `When a quote is late, tell Kestrin Boards` | term (markers); exclusion | payload-kind:automation; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-automation-t.json` | passes, exit 0 | the same fields in neutral words |
| P-item_batch-p | `cases/payload/P-item_batch-p.json` | $.name `Orders from Marlbeck Freight`; $.items[0].column_values<json>.text_1 `Tamsin Rook` | wall (name); exclusion | payload-kind:item_batch; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-item_batch-t.json` | passes, exit 0 | the same fields with invented sample words |
| P-doc-p | `cases/payload/P-doc-p.json` | $.name `Notes from Thymbel Advisory`; $.markdown `## Orders ⏎  ⏎ Corvel Systems was also considered.` | term (firm); exclusion | payload-kind:doc; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-doc-t.json` | passes, exit 0 | the same fields in neutral words |
| P-generic-p | `cases/payload/P-generic-p.json` | $.name `Corvel Systems trial`; $.description `Prepared by Thymbel Advisory`; $.label `[I] guess`; $.seed `Tamsin Rook`; $.markdown `Rework costs 263,480 a year.`; $.request_text `Ask Marlbeck Freight first`; $.role `Built with the master builder`; $.role_description `Tracks P4 for the office`; $.goal `Read clients/wrenfold-joinery/calls/ first`; $.plan `Open board 73029184 first`; $.user_prompt `secret: tidewater42`; $.knowledge_name `note to self`; $.prompt `Explain the cost of waiting`; $.app_name `Drafted with claude`; $.step_text `Ask Ines Calloway to check`; $.recipient `kestrin.boards@supply.example`; $.url `https://files.example/export?key=Hd72kPq9Lx` | exclusion; term (firm); term (markers); figure; wall (name); term (plugin); term (pain-ids); term (id-patterns); credential; internal-note; term (method); term (assistant); term (local) | payload-kind:generic; rule:payload-per-kind; rule:exclusion-per-family | blocks, exit 1 | `cases/payload/P-generic-t.json` | passes, exit 0 | the same keys in neutral words |

### The .docx samples (9)

| Case | Planted file | Planted text, where | Rule (class) | Category | Expected | Twin file | Twin expected | Why the twin is clean |
|---|---|---|---|---|---|---|---|---|
| D01-p | `docx/D01-p/` | word/document.xml `Thymbel Advisory` | term (firm) | rule:docx-parts | blocks, exit 1 | `docx/D01-t/` | passes, exit 0 | the same parts with neutral text |
| D02-p | `docx/D02-p/` | docProps/core.xml `Ines Calloway` | term (local) | rule:docx-parts | blocks, exit 1 | `docx/D02-t/` | passes, exit 0 | the same parts with neutral text |
| D03-p | `docx/D03-p/` | docProps/app.xml `Thymbel Advisory` | term (firm) | rule:docx-parts | blocks, exit 1 | `docx/D03-t/` | passes, exit 0 | the same parts with neutral text |
| D04-p | `docx/D04-p/` | word/header1.xml `[I]` | term (markers) | rule:docx-parts | blocks, exit 1 | `docx/D04-t/` | passes, exit 0 | the same parts with neutral text |
| D05-p | `docx/D05-p/` | word/footer1.xml `strands/001-quote-tracker/` | term (id-patterns) | rule:docx-parts | blocks, exit 1 | `docx/D05-t/` | passes, exit 0 | the same parts with neutral text |
| D06-p | `docx/D06-p/` | word/footnotes.xml `263,480` | figure | rule:docx-parts | blocks, exit 1 | `docx/D06-t/` | passes, exit 0 | the same parts with neutral text |
| D07-p | `docx/D07-p/` | word/endnotes.xml `Corvel Systems` | exclusion | rule:docx-parts | blocks, exit 1 | `docx/D07-t/` | passes, exit 0 | the same parts with neutral text |
| D08-p | `docx/D08-p/` | word/comments.xml `note to self` | internal-note | rule:docx-parts | blocks, exit 1 | `docx/D08-t/` | passes, exit 0 | the same parts with neutral text |
| D09-p | `docx/D09-p/` | docProps/custom.xml `Marlbeck Freight` | wall (name) | rule:docx-parts | blocks, exit 1 | `docx/D09-t/` | passes, exit 0 | the same parts with neutral text |

## Known limits the fixture asserts

- `T12b-p`: banter with no person and no cue: no string rule reaches it; call-intake keeps small talk away from the client-safe block (X38).
- `T13a-p`: an outside contact named once and in no exclusion: the contact is in this record, so the wall passes the name, and no other rule reaches a name; the guard is the exclusion row of T13b.
- `K10b-p`: the incident retold in new words: no copied run and no cue, so no string rule reaches it.
- `K13b-p`: a title set against what a person does, with no cue: no string rule reaches it.
- `K15c-p`: the objection paraphrased: no run, no quote and no cue.
- `K21b-p`: a street address with no number and no listed name: no string rule reaches it.
- `K26b-p`: a demonstration name presented as a client fact: it is in this record, so the wall passes it; the guard is the [X] quarantine in the record.
- `K27b-p`: the claim paraphrased: no string rule reaches it.
- `K29b-p`: the seller's commercial clock paraphrased: no string rule reaches it.
- `K31b-p`: an aside with no person and no cue: no string rule reaches it.
- `K35-p`: an estimate the record never states: the lint sees only figures the record holds.
- Colloquial digit-by-digit forms of a figure and approximate wording far from it are not matched (X25), and a misspelling that changes the phonetic key and sits beyond the edit distance is not matched (X32). No case asserts these; they are stated so the review can probe them.

## What this fixture cannot prove

- That the categories of A§:918 and the kinds of DECISIONS section 3.1 are the whole set of leaks.
- That a client's real vocabulary behaves like the invented one here.
- The false-positive rate on real client text, which only stage 4's seed records and the twenty-five answer keys begin to measure.
- Anything about a language other than English.

## Invented names and renderings

The closed list the self-test enforces (DECISIONS X18): every capitalised token in a fixture file outside this README is in this list, is a common word, or starts a sentence. Every entry is invented for this fixture and names no real person, firm, account or workspace.

- `Thymbel Advisory`: the user's own firm, as `firm.name` in the test settings.
- `Thymbel`: a firm rendering, and the phonetic source of the test local list.
- `Thymbel-Advisory`: the firm name written with a hyphen.
- `Thimbel`: a misspelt firm variant.
- `Thymbell`: a misspelt firm variant.
- `Thymble`: a misheard firm variant.
- `Thym Bell`: the firm name split in two.
- `Thimble Advisory`: the sound-alike word joined to the firm's second word.
- `Thimble`: the ordinary English word that sounds like the firm; whitelisted in the test local list.
- `Ines Calloway`: the user's own colleague, a row of class local in the test local list.
- `Pipeline Hub Internal`: a never-shown workspace of the user's, in the test settings.
- `Rate Card Vault`: a never-shown workspace of the user's, in the test settings.
- `Wrenfold Joinery`: client record a, a kitchen joinery.
- `Lise Varrow`: record a: office coordinator.
- `Maren Quist`: record a: finish shop.
- `Bram Kettleby`: record a: installer.
- `Odran Fisk`: record a: panel saw.
- `Ashby Sheet Supply`: record a: the current supplier.
- `Kestrin Boards`: record a: the former supplier, excluded.
- `Corvel Systems`: record a: a competing vendor, excluded.
- `Tamsin Rook`: record a: a homeowner customer, excluded.
- `Halloran Doors`: record a: the name typed in a demonstration.
- `Gideon Pryce`: record a: an outside contact, the building inspector.
- `Larch Row`: a customer's street, named only in K21b-p.
- `Marlbeck Freight`: client record b, a haulage firm.
- `Marlbek`: a misspelt variant of record b's name.
- `Marlbek Frate`: a misheard variant of record b's name.
- `Perrin Haldane`: record b: operations lead, called Skipper on calls.
- `Skipper`: record b: the alias, an ordinary word.
- `Quilla Oduya`: record b: finance.
- `Wendell Ayo`: record b: runs the night desk; named only in a body line of the brief.
- `Tollmere Fresh Market`: record b: the largest customer.
- `TFM`: record b: the same customer as initials.
- `Silver Lantern`: record b: a partner whose name is two ordinary words.
- `Dockon`: record b: a product, an ordinary word fused to a preposition.
- `Brannock Cold Store`: record b: a counterparty.
- `Quessel Holdings`: record b: the counterparty's part-owner.

Lower-case names and addresses, also invented:

- `thymbeladvisory.example`: the firm's domain, a firm rendering.
- `quarry-lane-build`: the user's default build account slug, in the test settings.
- `quarry-lane-ops`: the user's archive account, in the test settings.
- `perrin.haldane@marlbeckfreight.example`: record b: the contact address.
- `wrenfoldjoinery.example, homes.example, supply.example, projects.example, files.example, hooks.example`: invented domains under the reserved .example name.

Figures and ids, all invented:

- 263,480: record a: yearly rework cost (a cost figure, in the wall's figures).
- 73,000: record a: the saw budget (a cost figure; two significant digits, so not in the wall).
- 96,400: record a: the yearly upside of fixing quotes.
- 23,750: record a: last spring's write-off.
- 5,000: record a: the signing limit.
- 22%: record a: the margin, a cost percentage.
- 41,200: record a: the maintenance contract.
- 1,450: record a: the seller's day rate.
- 9,900: record a: the placeholder price floated on the call.
- 12,600: record a: the saving typed in the demonstration, from an [X] line.
- 38: record a: a fitter's loaded hourly rate.
- 14: record a: hours a week of quote checks, beside a cost word.
- 46: record a: the headcount, a record number with no cost word.
- 8314 2290 57: record a: the meeting id, only in the raw transcript's header.
- 186,730: record b: yearly fuel spend (a cost figure, in the wall's figures).
- 73029184: an invented eight-digit board id.
- 48273651: an invented eight-digit workspace id that is in no list.
- 60417283, 60417291: the never-shown workspaces' ids, in the test settings.
- 52806314: the default build account's id, in the test settings.
- 0770 090 0418: a phone number in digit groups, from a range kept for fiction.
- 18,250; 8,700; 2,350; 750; 15%: the twins' unrelated figures.

The shipped terms planted on purpose (the plugin row, the assistant rows, the method rows, the markers and the id patterns) come from `shared/leak-terms.txt` and are not names of anyone.
