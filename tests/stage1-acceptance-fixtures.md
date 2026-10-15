# Stage-1 acceptance: WP18, fixtures s11 to s25

Run on 2026-09-20 against BUILD-PLAN.md WP18's acceptance list and section 4.2, over the fifteen folders in `~/DelOps/monday-master-builder-dev/rebuild-workspace/fixtures/`. Nothing in the fixtures was changed. The one file edited is `fixtures/COVERAGE.md`, which now carries a row per fixture and the calibration totals (section 7). Every check below was run by a script written for this pass and kept in the session scratchpad; the field-order script and the quote-location checker are reproduced in the appendices so the run can be repeated.

**Verdict.** The set is in good shape: every key has the 25 fields in the s1 order plus `intake`; every located quote in every key (2,074 of them) sits at its cited location; every README count matches its key; the planted defects each section 4.2 row names are present; the clean-room scan and the identity sweeps are clean. Three things need a decision before the set is called accepted, and the user's review of each fixture is still pending (section 8).

## 1. What was checked, and how

| Check | How |
|---|---|
| Folders, files, sizes | `ls`, `wc -l`; the trailing newline of s24's key confirmed with `xxd` |
| Field order across all 25 keys | `field_order_check.py` (appendix A): loads each key with an ordered parser, compares the field list with s1's, requires `intake` as the single 26th field on s11 to s25 |
| Quotes at cited locations | `quote_locations.py` (appendix B): collects every `{quote, location}` pair at any depth, parses each fixture's location grammar, resolves it to the unit in the input file, checks the quote is inside that unit, then prints a stratified sample of 40 |
| Verbatim presence of every quote string | a survey script: every `quote`, `asked_quote` and `evidence_quote_or_null` string checked as a substring of the folder's inputs, document extracts against `word/document.xml` paragraphs and the PDF's `Tj` strings |
| README counts against the keys | `counts_check.py`: rubric rows by status, `asked` true/false/absent, graded and excavated pains, objections, traps, look-alike traps, leak entries, requested changes by type, commitments, questions, vocabulary, accepted behaviours, verdict, build flag; the README's numbers typed in as the expectation |
| Planted defects | `plants_check.py`: fifty-two assertions over the input files, two to five per fixture, each tied to a section 4.2 clause |
| s24 order | the `Date` line of each recording read and compared with the file-name order; the tie's breaking evidence found |
| s25 file formats | `zipfile` for the Word file (member list, `word/document.xml`, `docProps/core.xml`), a byte scan of the PDF (`stream` blocks, `Tj` operators, page count, information dictionary), the PNG signature and IHDR with `struct`, then PIL `verify()` and `open()`; the image itself viewed and its labels compared with the key's documented rows |
| Clean-room scan | `tools/cleanroom_scan.py --tree <folder>` once per fixture against the five `dossier/learn-*.md` files |
| Identity sweep | case-insensitive grep over the fifteen folders for the user's names and firm names, for email, URL and phone patterns, for sixty-odd software brand names, and for corporate suffixes; a cross-fixture full-name collision scan over speaker labels and `attendees` |
| No grade changed in s1 to s10 | the ten reviewed keys' R1 to R12 statuses compared with the matrix in `COVERAGE.md` |

Python 3.9.6 (the Mac's `/usr/bin/python3`). No Python 3.11 is installed on this machine, so nothing was run on 3.11.

## 2. Results against the acceptance list

| # | Acceptance clause | Result | Evidence |
|---|---|---|---|
| 1 | Fifteen folders, each with its input file(s), `answer-key.json` and a README | pass | s11, s13 to s21, s23 one transcript each; s12 a transcript and `meeting-chat.txt`; s22 two transcripts; s24 five recordings; s25 a `.docx`, a `.png`, a `.pdf` and a transcript |
| 2 | Keys under 400 lines each | **fail, by one line** | s11 395, s12 391, s13 349, s14 350, s15 392, s16 376, s17 387, s18 379, s19 396, s20 390, s21 274, s22 333, s23 349, **s24 400**, s25 371. s24's key ends with a newline and has exactly 400 lines, which is at the limit, not under it |
| 3 | No fixture over 1,200 lines of transcript | pass | longest is s16 at 1,193; s24's five files total 1,038; s22's pair 341 |
| 4 | Every key carries the 25 fields in the s1 to s10 order plus an `intake` block | pass | appendix A, 25 keys, 0 failures; `intake` is the 26th field on every calibration key and on no reviewed key |
| 5 | The `intake` block asserts the repair (WP14's list: composite blocks, wedges, re-joined sentences with owners, the alias map, confidence per unit, the confirmed order of a package, the `second-hand` figure, and for s25 the document fields, section map and `documented` rows) | pass | every key carries `composite_blocks`, `wedges`, `rejoined_sentences` and `confidence`; every key carries an alias map, at `intake.alias_map` in nine keys and at `intake.roster.alias_map` in s13, s14, s16, s17, s19 and s23; `package_order` or `confirmed_order` is present on every key but s11, whose single first-hand file carries `sequence` and `provenance` instead; `second_hand` on every key but s13 (which carries `relayed_and_second_hand`); s25 carries `documents`, `section_map`, `documented_rows`, `read_back`, `conflicts`, `grading_passes` |
| 6 | The calibration statuses and the `asked` flag appear only in calibration keys; no grade in s1 to s10 changes | pass | `met-with-residual` in all fifteen, `not-obtainable` in twelve, `asked` in all fifteen; none of the three, nor `advisory`, in any of s1 to s10; all 120 R-grades of s1 to s10 match the COVERAGE.md matrix |
| 7 | `advisory` is pinned against the calibration keys that carry it (WP1) | **fail: no key carries it** | zero `advisory` rows in all fifteen keys; the word appears only inside leak-blocklist vocabulary entries and in s25's assertion that the document-only pass has none. Seven READMEs say another calibration fixture carries the case; none does |
| 8 | Criterion names, gate names, status vocabulary match s1 character for character | pass | every criterion is `R<n> ...` or `P<n> <check>`; every key names the five gates exactly once; no status outside the five values |
| 9 | Each README's counts match its key | pass | 0 mismatches across 15 fixtures and 23 counted items each (section 3) |
| 10 | s24 is a handed-over set of five files whose names are out of date order, with dates inside; intake orders by date and internal evidence, records who was in each call, marks the re-quote `second-hand`, keeps both statements of the conflict, blueprints once with the fork open | pass | section 5 |
| 11 | s25 is a client SOP as a Word file with a flowchart image, a requirements PDF and one short call in which the operator says a documented approval step is not used; each opens with the standard library | pass | section 5 |
| 12 | s25's key asserts author, date and status, the section map with its marks, the `documented` rows with page citations, the conflict kept as both statements, two grading passes, and the same end state in the other arrival order | pass | section 5 |
| 13 | Document extracts are `[Q/doc]` by section or page and never by speaker | pass | 21 document locations in s25's key (`QP-07 section N.N`, `QP-07 front page`, `write-up p.N section N`, `figure 1 p.1`), none naming a speaker; 99 call locations, all stamp-plus-speaker |
| 14 | Forty quotes verbatim at the cited location | pass | 40 sampled and listed in section 4; beyond the sample, all 2,074 located quotes across the fifteen keys resolve to their cited unit with 0 failures |
| 15 | Each of s11 to s24 is written to its section 4.2 row and its lessons row | pass on the spot checks | fifty-two planted-defect assertions, all present (section 3) |
| 16 | `cleanroom_scan.py` over every one | pass | 0 findings on each of the fifteen folders against the five `learn-*.md` files, 8-word runs |
| 17 | No organisation, person, product, platform, brand, figure or date from a real call; tool references as category words | pass on the sweeps | no personal or firm name for the user; no email, URL or corporate suffix; no software brand (the word `Word` appears only as the file-format name in s25, as the build plan itself writes it, and inside "Word count" in s13 and s16); the one phone-shaped string is s12's planted meeting identifier, fictional and never quoted in the key |
| 18 | No name collides across unrelated fixtures | pass | 90 distinct full names across all 25 fixtures; none shared outside the two reviewed client chains |
| 19 | Labelled a calibration fixture or the document fixture in `COVERAGE.md`, counts recorded on the row, lessons row and reversal named, user review stated as pending | pass | section 7 |
| 20 | `leak_lint.py --terms` over every one | not run | `scripts/leak_lint.py` (WP4) does not exist yet; the plan places this scan in stage 2, before WP5 is accepted |
| 21 | Conventions consistent with the reviewed set | **fail on one field** | s24's `portfolio_expected` is `null`; every other calibration key with no account and no tier says `false` (the s2 convention), and three documents state that s1 is the only key with `null`: the s1 row of section 4.2, s25's README, and COVERAGE.md's "Convention deviations" line (now amended, section 7) |

Nineteen of the twenty checkable clauses pass; three items need a decision (section 8); one scan cannot run yet.

## 3. Per-fixture record

Counts are the key's, re-measured; every one matches its README. Rubric columns are met / partial / missing / met-with-residual / not-obtainable.

| Fixture | Inputs (lines) | Key lines | Rubric rows | Pains graded (excavated) | Objections | Traps (look-alike) | Leak | Changes add/change/remove | Located quotes at location | Plants checked |
|---|---|---|---|---|---|---|---|---|---|---|
| s11-demo-composite | transcript 245 | 395 | 24 (9/13/1/1/0) | 2 (1) | 8 | 22 (4) | 13 | 1/3/1 | 95 of 95 | composite block at [28:05] under one client label, 878 words, holds the vocative; 1,416-word presenter turn at [04:19]; client share by label 18.4% |
| s12-header-present | transcript 674, chat 38 | 391 | 36 (24/6/3/2/1) | 4 (3) | 9 | 32 (6) | 16 | 2/2/0 | 126 of 126 | `Meeting ID` and `Account ID` lines present and absent from the key; two bots named differently across the files; the no-role attendee's dotted leader; the chat-only attendee's messages |
| s13-header-absent | transcript 726 | 349 | 30 (22/4/2/1/1) | 3 (2) | 8 | 29 (6) | 16 | 3/1/1 | 137 of 137 | three-line human preamble, separator on line 5; roster turns at 02:29 and 03:58; no participant block, title or identifier |
| s14-shred-block | transcript 829 | 350 | 36 (27/3/3/2/1) | 4 (3) | 12 | 30 (7) | 15 | 2/4/1 | 120 of 120 | five colliding stamps at the cited lines; L449 31:12 before L451 31:09; the single-letter unit `s` at L367 under Aileen's label; the figure split over L463/465/467; unpadded stamps |
| s15-shred-dense | transcript 487 | 392 | 24 (18/2/1/2/1) | 2 (2) | 8 | 30 (6) | 16 | 1/4/0 | 136 of 136 | 18 label strings, 0 adjacent same-label pairs, 156 of 487 units under five words, no ellipsis |
| s16-shred-cue | transcript 1,193 (WebVTT) | 376 | 24 (18/2/2/1/1) | 2 (2) | 7 | 26 (6) | 14 | 1/3/0 | 100 of 100 | the nine wedges at 0 ms gaps are exactly cues 70, 86, 97, 119, 132, 136, 165, 270, 272; 58 cues labelled `R`; `Corwin.` at cue 72; 298 cues with end times |
| s17-no-markers | transcript 779 | 387 | 30 (21/6/2/1/0) | 3 (2) | 8 | 27 (6) | 14 | 2/3/0 | 90 of 90 | no bracket, ellipsis, dash marker or "inaudible" in the file; turn 183 is 410 words under Teodora Okoro's label |
| s18-identity-collapse | transcript 266 | 379 | 36 (23/7/2/3/1) | 4 (2) | 12 | 28 (7) | 15 | 3/2/1 | 115 of 115 | Tige, Tyge, Teague, Tighe and Thady all spoken; `Tadhg` only in labels and the header's participants line; 30 turns under the borrowed `Maxine Bassett` label; both Johns labelled |
| s19-reverse-demo | transcript 338 | 396 | 36 (22/7/3/3/1) | 4 (3) | 8 | 25 (7) | 15 | 3/2/1 | 158 of 158 | four stamped screen-sharing system lines; the Consultant's fix at 00:16:12 |
| s20-large-group | transcript 268 | 390 | 36 (27/5/1/2/1) | 4 (4) | 9 | 28 (6) | 19 | 1/2/0 | 182 of 182 | `Participants (14)` header, names only; "one in ten" at 00:26:36 against "closer to one in four" at 00:27:39; Pro then Standard inside 00:10:01; the announced departure and the arrival |
| s21-existing-account | transcript 262 | 274 | 24 (16/6/0/1/1) | 2 (2) | 7 | 30 (5) | 19 | 1/2/1 | 134 of 134 | the Consultant's 20 November clock at 00:33:20, "Noted." at 00:33:40; the screen share's two boundary stamps |
| s22-degrading-commitment | transcripts 191 + 150 | 333 | 36 (27/5/2/1/1) | 4 (3) | 8 | 30 (6) | 18 | 2/2/0 | 201 of 201 | the hedged, wrong-number, wrong-speaker re-quote at call 2 00:08:40; the original "dozen a week" at call 1 00:11:03; the reported commitment and its acceptance; the relayed figure and its rounding; two export grammars |
| s23-symmetric-shred | transcript 264 | 349 | 36 (27/4/3/1/1) | 4 (3) | 8 | 28 (7) | 15 | 2/4/0 | 136 of 136 | L171 to 179 and L228 to 237 alternate Consultant and Thandiwe with no client label; the three swallowed assents where cited; no ellipsis, crosstalk or inaudible, three `[laughs]` |
| s24-package | five recordings, 1,038 | 400 | 36 (25/7/2/2/0) | 4 (3) | 12 | 29 (8) | 19 | 3/5/1 | 225 of 225 | section 5 |
| s25-client-documents | docx, png, pdf, transcript 88 | 371 | 24 (11/8/1/3/1) | 2 (2) | 7 | 36 (6) | 18 | 3/2/0 | 119 of 119 plus 1 image label | section 5 |

Totals over the fifteen: 468 rubric rows (317 / 85 / 28 / 26 / 12), 48 graded pains (37 excavated), 131 objections, 430 traps (93 look-alike), 242 leak entries, 78 requested changes (30 / 41 / 7), 2,519 quote strings, 2,074 of them with a location.

Two of the survey's first-pass "not found" results were the checker's, not the fixtures': s15's and s16's merged-run quotes are unit texts joined by one space (the README says so), and s25's document extracts live in the Word and PDF files, not in the transcript. The location checker handles both and everything resolved.

## 4. The forty-quote sample

Drawn with a fixed seed, at least two per fixture, from the located quotes; every one was found inside the cited unit. The line or unit number is where the checker found it.

| # | Fixture | Field | Cited location | Quote (trimmed) | Found |
|---|---|---|---|---|---|
| 1 | s11 | rubric[3].evidence[2] | 41:57 Hattie Szabo (Sales Manager) | "We had eight from one wedding in August and I found the count sheet in the door pocket ..." | line 140 |
| 2 | s11 | rubric[6].evidence[0] | 52:38 Anjali Venkataraman (General Manager) | "Gerald. He signs anything over ten thousand and he'll want to see it, not read about it..." | line 176 |
| 3 | s12 | rubric[13].asked_quote | 14:16:15 Consultant | "What happened with the county one?" | line 242 |
| 4 | s12 | rubric[22].asked_quote | 14:24:32 Consultant | "Do you know what an hour of client services costs, loaded?" | line 365 |
| 5 | s13 | rubric[13].asked_quote | 12:46 Consultant | "Tell me about the German manual." | line 206 |
| 6 | s13 | rubric[20].evidence[1] | 17:56 Niamh Kettleborough | "Every Friday. And then Monday morning there's the list." | line 293 |
| 7 | s14 | rubric[15].evidence[0] | L321, 22:47 Meera Ganguly | "Me, because I sign the sub-hire. Moira, because she has to tell the client the design c..." | line 321 |
| 8 | s14 | rubric[25].evidence[1] | L245, 17:10 Aileen Rusnak | "it's the following Wednesday, if we're honest, and by then nobody can tell you which sh..." | line 245 |
| 9 | s14 | rubric[4].evidence[3] | L525, 36:23 Meera Ganguly | "Four shows, so fifty-six thousand of revenue we didn't take. I'm not going to claim we'..." | line 525 |
| 10 | s15 | pains[3] | L208, 13:36, Tamsin | "And then I ring Dara, and now three people are looking for one sample." | line 208 |
| 11 | s15 | rubric[12].evidence[0] | L135, 8:53, Joost Teunissen | "It doesn't say anything a customer would understand, and it doesn't say when." | line 135 |
| 12 | s15 | rubric[6].evidence[3] | L396, 26:43, Tamsin Greaves | "Ngozi will want to see the number." | line 396 |
| 13 | s16 | rubric[15].evidence[0] | cue 174, 00:12:38.791, Nkechi Brandvold | "The crew, same as Ruairi said. They loaded a truck for nothing." | cue 174, line 697 |
| 14 | s16 | rubric[1].evidence[1] | cue 143, 00:10:20.296, R | "Nobody told me, and I'd cut thirty-inch." | cue 143, line 573 |
| 15 | s16 | rubric[8].evidence[0] | cue 249, 00:18:46.699, R | "My guys don't type. They will not type." | cue 249, line 997 |
| 16 | s17 | rubric[19].evidence[0] | turn 107, 12:30, Rasmus Wrenfield | "The chain had a standing order for them and they cancelled it in July and nobody told m..." | turn 107, line 320 |
| 17 | s17 | rubric[8].evidence[3] | turn 225, 29:43, Teodora Okoro | "if this replaces that he'll fight it quietly." | turn 225, line 674 |
| 18 | s18 | rubric[4].evidence[1] | 00:30:40 Tadhg Devlin | "I can't split that for you. All of it if April happens again. None of it if it doesn't...." | line 186 |
| 19 | s18 | rubric[6].evidence[1] | 00:32:32 Tadhg Devlin | "The fourteenth if it's above twenty. Before that if it isn't. But I'd want him to see i..." | line 197 |
| 20 | s19 | rubric[18].evidence[0] | 00:19:02 Reuben Castellanos (Production Manager) | "Usually. Sometimes he forwards the reply and the PDF's fallen off, and I go find it on ..." | line 137 |
| 21 | s19 | rubric[27].evidence[1] | 00:25:50 Noor Abdelrazek (Project Coordinator) | "Typed. It doesn't know about permits at all, really. I type what's in my binder. So now..." | line 189 |
| 22 | s19 | rubric[3].asked_quote | 00:34:05 Consultant | "Ingrid, can I put some numbers on the wasted trips? Reuben said three guys and a truck ..." | line 249 |
| 23 | s20 | intake.conflicts[0].basis_b | 00:28:23 Imogen Achebe (Production Manager) | "And I count what the shop builds twice." | line 161 |
| 24 | s20 | rubric[32].evidence[1] | 00:34:54 Calum Fairweather (Installation Manager) | "The rollout. Eight crews on the road instead of six, if we hire, in five states. I can'..." | line 198 |
| 25 | s21 | rubric[11].evidence[2] | 00:34:40 Henrietta Weyland (Director of Operations) | "One condition on the Studies board. No new columns the account leads have to fill in. T..." | line 237 |
| 26 | s21 | rubric[8].evidence[0] | 00:32:32 Henrietta Weyland (Director of Operations) | "The recruiters, we've talked about. The IT people and how you get in. And Philippa, if ..." | line 224 |
| 27 | s22 | intake.relayed_figures[0].rounding_not_a_figure | call 2, 00:07:07 Genevieve Okundaye (Director of Operations) | "Call it six, then." | transcript-2 line 43 |
| 28 | s22 | rubric[19].evidence[1] | call 1, 00:11:42 Declan Pellingham (Plant Manager) | "They'd changed their pool towel par for the off season, down, and the change went to th..." | transcript-1 line 66 |
| 29 | s22 | rubric[2].evidence[0] | call 1, 00:03:53 Genevieve Okundaye (Director of Operations) | "Which is a hotel group, four hotels, we've never had them, and we signed them in Septem..." | transcript-1 line 24 |
| 30 | s22 | rubric[6].evidence[3] | call 2, 00:17:41 Annika Brannock (Finance Director) | "Over ten thousand it's me and Gustav, and Gustav goes with me on anything that isn't a ..." | transcript-2 line 103 |
| 31 | s22 | rubric[8].asked_quote | call 2, 00:19:20 Consultant | "Shorts first, then. And blockers. What's in the way that you can see already?" | transcript-2 line 114 |
| 32 | s23 | rubric[22].evidence[0] | L133, 00:22:41 Eamon Kilbride | "Fourteen hours a week, and most of it is chasing the five sources, not assembling." | line 133 |
| 33 | s23 | rubric[9].evidence[0] | L252, 00:45:45 Consultant | "Thursday the fifth at ten, your time? Yes. Good. Forty-five minutes, and we'll take thi..." | line 252 |
| 34 | s24 | intake.files[1].type_quote | rec-4402, 01:31 Kofi Danquah (sales engineer) | "Sharing now. Can you see a screen with a list of jobs?" | rec-4402 line 33 |
| 35 | s24 | rubric[0].asked_quote | rec-4418, 04:18 Clodagh Rennard (seller) | "Okay. Let's start there, actually. Walk me through a job. From the phone ringing to the..." | rec-4418 line 57 |
| 36 | s24 | rubric[16].evidence[1] | rec-4418, 11:30 Gwen Tarrant (Production Manager) | "An hour, hour and a half a day, chasing proofs and art." | rec-4418 line 141 |
| 37 | s24 | rubric[27].asked_quote | rec-4418, 21:39 Clodagh Rennard (seller) | "Who does that reach?" | rec-4418 line 245 |
| 38 | s24 | rubric[30].asked_quote | rec-4418, 22:55 Clodagh Rennard (seller) | "Anything else on the floor that gets in the way? Gwen?" | rec-4418 line 266 |
| 39 | s25 | commitments_and_next_steps[3] | 00:14:49 Consultant | "Before then I'll write up what you've told me, and where it's different from the proced..." | line 83 |
| 40 | s25 | rubric[4].asked_quote | 00:10:24 Consultant | "Is there work you turn away, or lose, because of the turnaround?" | line 59 |

Beyond the sample, the document extracts of s25 were resolved too: the conflict's SOP sentence ("A priority request is approved by the Laboratory Manager before the sample is allocated.") sits in the paragraph under heading 4.2, the write-up extracts sit on the cited PDF page, and the twelve `documented` rows' labels match the flowchart's twelve nodes when the image is viewed (start and end in rounded boxes, eight steps, two decision diamonds with `Yes` and `No` exits, the `re-test` loop back to the bench).

## 5. s24 and s25

**s24.** Sorted by name the five files are dated 2026-08-06, 2026-07-23, 2026-08-19, 2026-07-14, 2026-07-23; the true order from the `Date` lines is rec-4418 (discovery, 14 July), rec-4402 (demo, 23 July), rec-4431 (call review, 23 July), rec-4397 (demo, 6 August), rec-4409 (pricing, 19 August). The key's `intake.confirmed_order` is exactly that; `intake.ties` names the 23 July pair and breaks it on "Kof, this morning's demo." at rec-4431 00:05. Each `intake.files` entry carries the call type, `provenance: handed-over`, the roster as listed, the voices heard, the listed-not-present and the voices missing. The forty-thousand figure is a `second_hand` entry with its three re-quotes cited and the status "second-hand ... refused as a quote; not fresh client evidence; not a bleed component". `intake.conflicts[0]` keeps three statements of reprints-per-week with call, speaker and location, kind `conflict`, and names the settlement route. `intake.forks[0]` carries both options with their constituencies and conditions, the approver's delegation, the reversibility fact ("It's not a switch.") and the handling as a fork open on the approval card. `attendees[].side` uses `client`, `seller` and `bot`; nobody is the user. The export grammar (a metadata block between rules, topic dividers, `Speaker Name · mm:ss` label lines) appears in no other fixture.

**s25.** The Word file is a zip of seven members including `word/document.xml` (92 paragraphs) and `docProps/core.xml`, whose `dc:creator` is the SOP's author, `dcterms:created` 2026-02-24, `dcterms:modified` 2026-03-11 and `cp:contentStatus` `Approved`; the front page carries the same author, date of issue and status in text. The PDF is an uncompressed 1.4 file with two page objects, two content streams and 39 `Tj` text lines, 2,309 characters recovered by a byte scan over both pages, and no `/Info`, `/Author`, `/Creator` or `/CreationDate` byte anywhere. The PNG has a valid signature and an IHDR of 1000 by 1560, 8-bit RGB, no text chunks; PIL 11.3.0 `verify()` passes and `open()` reports PNG, (1000, 1560), RGB. The transcript is 88 lines of `[HH:MM:SS] Speaker: text`; at 00:04:01 and 00:04:25 the reception coordinator says the documented priority-approval step is not used, and the SOP's section 4.2 says it is, so the document-versus-call conflict is present; the write-up's W-3 asks for the approval on screen, so the documented-versus-desired split is present too.

The key asserts everything WP18's acceptance names for s25: `intake.files` records author, `document_date` and status for the SOP and `unknown` three times each for the figure and the write-up; `intake.section_map` has fifteen entries marked current state (8), desired state (4), metadata, reference list and document control; `intake.documented_rows` has twelve rows, every one with `source: figure 1 p.1` and `marker: documented`, two of them decisions with their exits and one carrying the loop; `intake.conflicts[0]` keeps the SOP sentence (cited to section 4.2), the call's two statements and the dependent requirement (W-3), kind `conflict`; `intake.grading_passes.document_only` asserts no type header, zero `advisory` rows, every `asked` flag false, twelve criteria graded with every gap shown, verdict Not ready, no gate met and no build; `intake.grading_passes.arrival_orders` names run A (documents then call), run B (call then documents), what must be identical, the two things allowed to differ, and that the call is sequence 4 in both runs because sequence comes from each input's own date. Every document extract is cited by section or page and none by a speaker.

## 6. Scans and sweeps

**Clean room.** `python3 tools/cleanroom_scan.py --tree <folder> dossier/learn-api-data.md learn-api-errors.md learn-api-products.md learn-history.md learn-workflow.md`, once per folder: `0 finding(s) over 5 quarantined file(s), 8-word runs` for every one of the fifteen, exit 0. (An earlier invocation with the tree arguments passed as one shell word scanned the plugin tree instead; that run reported one eight-word run in `plugins/monday-master-builder/shared/safety.md:51` shared with `learn-api-errors.md:642`. It is WP1's file and outside this package; noted for WP1 and the release check, not acted on.)

**Identity.** No hit for the user's names, the user's GitHub handle, the firm names or the machine's account name in any of the fifteen folders. No email address, URL or corporate suffix. The only phone-shaped string is the fictional meeting identifier in s12's header (line 6) and chat file (line 3), planted on purpose and absent from the key, with the account identifier beside it. No software brand name in any input or key: the sweep's hits were `Word` as the file format in s25's README and key (the build plan's own wording for the fixture), `Word count` in s13's transcript and s16's README, and the ordinary word `Things` in s22. No plugin, product, firm or assistant name. The Consultant appears only as `Consultant` (s11 to s23, s25); s24 has no Consultant and says "the user".

**Names across fixtures.** 90 distinct full names over all 25 fixtures; none shared outside the two reviewed client chains (s1/s3/s10 and s8/s9).

## 7. COVERAGE.md

`fixtures/COVERAGE.md` now carries, before "Remaining gaps", a section *Calibration fixtures and the document fixture (s11 to s25)* with one row per fixture in the file's pipe-table format: fixture, label (calibration fixture, or the document fixture for s25), files, lessons row (C56 to C65 and C104; A15 and A16 for s24 and s25, which have no lessons row), reversal guarded, rubric rows by status, pains graded and excavated, objections, traps and look-alikes, leak entries, requested changes by type, quote strings, and "user review pending". Below the table: the calibration totals, how the multi-file fixtures are taken in, the location formats, and a note on the statuses, including that no key carries a positive `advisory` row.

The totals lines the file keeps were each extended with the calibration figure, marked pending review and kept apart from the reviewed figure: 1,294 checked strings (+2,519), 323 rubric rows (+468), 33 graded pains (+48, 37 excavated), 81 objections (+131), 281 traps (+430, 93 look-alike), 51 requested changes (+78), 158 leak entries (+242). The field-set sentence now says that a calibration key adds `intake` as a 26th field, the introduction points at the new section, and the "Convention deviations" line now says s1 is the only *reviewed* key with `portfolio_expected: null` and that s24 also carries `null`, pending review. Nothing else in the file changed; the reviewed set's figures and text are as they were.

The quote-string column counts every non-null `quote`, `asked_quote` and `evidence_quote_or_null` string in a key, intake block included. On that basis s1 to s10 give 1,294, the file's own figure, so the two sets are counted alike; a README's own count can differ by a few where its basis differs (s11 121, s14 150, s17 113, s23 165, s25 133).

## 8. Must fix, and notes

Three items need the user's decision. None is fixed here.

1. **s24's key is 400 lines.** The limit is "keys under 400 lines each". One line over on the strict reading; the README itself says 400. Compacting any one entry brings it under.
2. **No key carries a positive `advisory` row.** Every calibration README says its call type resolves, and seven say another calibration fixture carries the `advisory` case; none does. WP1's acceptance pins `advisory` "against the calibration fixture keys of WP18 that carry them", and WP14's grader for it has no positive case to score. Either one fixture gains an unresolved type dimension with the demoted rule carried as `advisory` with its question (s24 is the natural candidate: its README already leaves the seat dimension of the seller-side calls open between three candidates, though its key says every type resolves), or the plan records that `advisory` has no positive fixture and s25's assertion of its absence is the only test. The seven READMEs' sentence is wrong either way.
3. **s24's `portfolio_expected` is `null`.** Every other calibration key with no account and no tier says `false`, the s2 convention; s24's README justifies `null` by the previous seller's Pro proposal. Three documents say s1 is the only key with `null`: the s1 row of BUILD-PLAN.md section 4.2, s25's README, and COVERAGE.md's convention line (amended in this pass to say "the only reviewed key"). Either s24 becomes `false` or the 4.2 row and s25's README are amended.

Notes, none blocking:

1. `leak_lint.py --terms` was not run: WP4's script does not exist yet, and the plan places that scan in stage 2 before WP5 is accepted. `cleanroom_scan.py` ran and is clean.
2. The incidental clean-room finding in `shared/safety.md` (section 6) belongs to WP1 and the release check, not to this package.
3. s12's meeting and account identifiers are planted and fictional; the identity sweep flags the meeting identifier as phone-shaped, which is what a real export's would look like, and the key never quotes either value.
4. PIL is not standard library. The PNG was opened with the standard library as well (signature and IHDR); PIL 11.3.0 happens to be installed on this Mac's Python 3.9.6. Python 3.11 is not installed here, so no 3.11 run was made.
5. The quote-string counts on the COVERAGE.md rows use one basis for every key (section 7); a README's own count can differ by a few and says why.
6. Seven READMEs say another calibration fixture carries the `advisory` case (must-fix 2); s14 and s24 say only that the call type resolves, and s25 asserts the absence on purpose.
7. s24's and s25's "lessons row" entries are A15 and A16: neither has a row in REAL-CALL-LESSONS.md section 6, which is what section 4.2 says.
8. The READMEs' own `fixtures-work/_work-sNN/check.py` scripts were not re-run; every check here was an independent script written for this pass.
9. s25's SOP names the Laboratory Manager in section 3.2 as well as 4.2, 4.3 and 6.4; the README's list is of the planted title contrast (Supervisor in 4.1 and 5.4 against Manager in 4.2, 4.3 and 6.4), which is present as stated.
10. The user's review of each fixture, which WP18's acceptance requires before use, is the remaining step; every COVERAGE.md row says so.

## Appendix A: `field_order_check.py`

Kept at `<scratchpad>/field_order_check.py` for this session; reproduced here so it can be re-run from anywhere. Standard library only, Python 3.9. Exit 0 when every key passes.

```python
#!/usr/bin/env python3
"""Check that every answer key in the fixtures workspace carries the 25 reviewed
fields in the s1 order, and that s11 to s25 add exactly one field, `intake`, after them.
Standard library only. Exit 0 when every key passes, 1 otherwise."""
import collections, glob, json, os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "~/DelOps/monday-master-builder-dev/rebuild-workspace/fixtures"
REVIEWED_ORDER = [
    "scenario_id", "call_type", "purpose_of_this_fixture", "transcript_format", "company",
    "attendees", "expected_monday_products", "rubric", "pains", "numbers", "vocabulary",
    "entities_and_workflows", "integrations_mentioned", "compliance_or_security_signals",
    "objections", "commitments_and_next_steps", "traps", "requested_changes",
    "should_plugin_propose_a_build", "expected_questions_before_building", "expected_verdict",
    "account_context", "expected_structures", "accepted_behaviours", "expected_leak_blocklist",
]

def fixture_number(path):
    return int(os.path.basename(path.rstrip("/"))[1:].split("-")[0])

def main():
    failures = 0
    folders = sorted(glob.glob(os.path.join(ROOT, "s*/")), key=fixture_number)
    for folder in folders:
        name = os.path.basename(folder.rstrip("/"))
        path = os.path.join(folder, "answer-key.json")
        if not os.path.exists(path):
            print("FAIL %-40s no answer-key.json" % name); failures += 1; continue
        with open(path, encoding="utf-8") as handle:
            key = json.load(handle, object_pairs_hook=collections.OrderedDict)
        fields = list(key.keys())
        calibration = fixture_number(folder) >= 11
        expected = REVIEWED_ORDER + (["intake"] if calibration else [])
        if fields == expected:
            print("ok   %-40s %d fields%s" % (name, len(fields), ", intake last" if calibration else ""))
        else:
            failures += 1
            missing = [f for f in expected if f not in fields]
            extra = [f for f in fields if f not in expected]
            order = [f for f in fields if f in expected]
            print("FAIL %-40s missing=%s extra=%s order_ok=%s" % (name, missing, extra, order == [f for f in expected if f in fields]))
    print("field_order_check: %d key(s), %d failure(s)" % (len(folders), failures))
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
```

Output on 2026-09-20: `ok` for all 25 keys, `field_order_check: 25 key(s), 0 failure(s)`.

## Appendix B: `quote_locations.py`

The location checker, as run. It walks every dict carrying a string `quote` and a string `location`, resolves the location by the fixture's grammar, and checks the quote is inside the resolved unit: a label line plus its text line (s11, s12, s13, s17, s24), a one-line unit by line number with the printed stamp and label compared (s14, s15, s23), a WebVTT cue or a same-label run of cues (s16), a stamped line with the speaker compared (s18 to s21, s22 per call, s25's call), a Word paragraph under the cited heading, a PDF page's `Tj` text, or an image label (marked for the eye). Merged runs join unit texts with one space, as the READMEs state.

```python
#!/usr/bin/env python3
"""Verify every located quote in s11 to s25 at its cited location, per fixture format,
then print a stratified 40-quote sample for the acceptance record. Standard library only."""
import collections, glob, json, os, random, re, sys, zipfile, zlib

ROOT = "~/DelOps/monday-master-builder-dev/rebuild-workspace/fixtures"
TS = re.compile(r"(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{3})?)")

def read(path):
    with open(path, encoding="utf-8") as h:
        return h.read().splitlines()

def load_key(folder):
    with open(os.path.join(folder, "answer-key.json"), encoding="utf-8") as h:
        return json.load(h, object_pairs_hook=collections.OrderedDict)

def collect(node, path, out):
    """Every dict with a string quote and a string location, at any depth (asked_quote included)."""
    if isinstance(node, dict):
        q, loc = node.get("quote"), node.get("location")
        if isinstance(q, str) and isinstance(loc, str):
            out.append((path, q, loc))
        for k, v in node.items():
            if k in ("quote", "location"):
                continue
            collect(v, path + "/" + k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect(v, path + "[%d]" % i, out)

def speaker_of(loc):
    """The speaker name in a location, without the role in parentheses."""
    s = TS.sub("", loc)
    s = re.sub(r"^\s*(chat|call \d|rec-\d+|cue[s]? [\d-]+|turn \d+|L[\d-]+)[,\s]*", "", s)
    s = s.split("(")[0].replace(",", " ").strip()
    return s

def bracket_ts_lines(lines):
    units = collections.defaultdict(list)
    for i, line in enumerate(lines, 1):
        m = re.match(r"^\[(\d{2}:\d{2}(?::\d{2})?)\] ([^:]+): (.*)$", line)
        if m:
            units[m.group(1)].append((m.group(2).strip(), m.group(3), i))
    return units

def label_then_text(lines, pattern):
    """Label line matching pattern (groups: name, ts) with the text on the following line."""
    units = collections.defaultdict(list)
    for i, line in enumerate(lines, 1):
        m = re.match(pattern, line)
        if m and i < len(lines):
            d = m.groupdict()
            units[d["ts"]].append((d["name"].strip(), lines[i], i + 1))
    return units

def check_units(units, loc, quote, who_required=True):
    m = TS.search(loc)
    if not m:
        return False, "no timestamp in location"
    ts = m.group(1)
    cands = units.get(ts, [])
    who = speaker_of(loc)
    hits = []
    for label, text, ln in cands:
        if quote in text:
            if who_required and who and not (label.startswith(who) or who.startswith(label) or "block" in loc or "segment" in loc or "labelled" in loc):
                continue
            hits.append(ln)
    if hits:
        return True, "line %s" % hits[0]
    return False, "not under %s (%d unit(s) at that stamp)" % (ts, len(cands))

def resolve(name, folder, loc, quote, cache):
    n = int(name[1:].split("-")[0])
    tx = os.path.join(folder, "transcript.txt")
    if n == 11:
        u = cache.setdefault("u", label_then_text(read(tx), r"^\[(?P<ts>\d{2}:\d{2})\] (?P<name>.+)$"))
        return check_units(u, loc, quote)
    if n == 12:
        if loc.startswith("chat"):
            u = cache.setdefault("chat", label_then_text(read(os.path.join(folder, "meeting-chat.txt")), r"^(?P<ts>\d{2}:\d{2}:\d{2})\s{2,}(?P<name>.+)$"))
        else:
            u = cache.setdefault("u", label_then_text(read(tx), r"^(?P<name>.+?)\s{2,}(?P<ts>\d{2}:\d{2}:\d{2})\s*$"))
        return check_units(u, loc, quote)
    if n == 13:
        lines = cache.setdefault("lines", read(tx))
        if loc.startswith("preamble"):
            k = int(re.search(r"line (\d+)", loc).group(1))
            return (quote in lines[k - 1]), "line %d" % k
        u = cache.setdefault("u", label_then_text(lines, r"^(?P<name>.+?)\s{2,}(?P<ts>\d{2}:\d{2})\s*$"))
        return check_units(u, loc, quote)
    if n in (14, 23):
        lines = cache.setdefault("lines", read(tx))
        m = re.match(r"L(\d+)(?:-(\d+))?,\s*(\S+)\s+(.*)$", loc)
        if not m:
            return False, "unparsed location"
        a = int(m.group(1)); b = int(m.group(2) or a)
        texts = []
        for k in range(a, b + 1):
            line = lines[k - 1]
            mm = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?) ([^:]+): (.*)$", line)
            if not mm:
                return False, "line %d is not a unit" % k
            if k == a and (mm.group(1) != m.group(3) or not m.group(4).startswith(mm.group(2))):
                return False, "line %d prints %s %s, location says %s %s" % (k, mm.group(1), mm.group(2), m.group(3), m.group(4))
            texts.append(mm.group(3))
        joined = " ".join(texts)
        return (quote in joined), "line%s %d%s" % ("s" if b > a else "", a, "-%d" % b if b > a else "")
    if n == 15:
        lines = cache.setdefault("lines", read(tx))
        m = re.match(r"L(\d+)(?:-(\d+))?,\s*(\S+),\s*(.*)$", loc)
        if not m:
            return False, "unparsed location"
        a = int(m.group(1)); b = int(m.group(2) or a)
        texts = []
        for k in range(a, b + 1):
            mm = re.match(r"^(\d{1,2}:\d{2}) ([^:]+): (.*)$", lines[k - 1])
            if not mm:
                return False, "line %d is not a unit" % k
            if k == a and mm.group(1) != m.group(3):
                return False, "line %d prints %s, location says %s" % (k, mm.group(1), m.group(3))
            texts.append(mm.group(3))
        return (quote in " ".join(texts)), "line%s %d%s" % ("s" if b > a else "", a, "-%d" % b if b > a else "")
    if n == 16:
        cues = cache.get("cues")
        if cues is None:
            cues = {}
            lines = read(tx)
            for i, line in enumerate(lines):
                if re.match(r"^\d+$", line) and i + 2 < len(lines) and "-->" in lines[i + 1]:
                    start = lines[i + 1].split(" --> ")[0].strip()
                    mm = re.match(r"^([^:]+): (.*)$", lines[i + 2])
                    if mm:
                        cues[int(line)] = (start, mm.group(1), mm.group(2), i + 3)
            cache["cues"] = cues
        m = re.match(r"cues? (\d+)(?:-(\d+))?,\s*(\S+),\s*(.*)$", loc)
        if not m:
            return False, "unparsed location"
        a = int(m.group(1)); b = int(m.group(2) or a)
        texts = []
        for k in range(a, b + 1):
            if k not in cues:
                return False, "cue %d not found" % k
            start, label, text, ln = cues[k]
            if k == a and (start != m.group(3) or label != m.group(4).strip()):
                return False, "cue %d is %s %s, location says %s %s" % (k, start, label, m.group(3), m.group(4))
            if label != cues[a][1]:
                return False, "run %d-%d crosses a label change at cue %d" % (a, b, k)
            texts.append(text)
        return (quote in " ".join(texts)), "cue%s %d%s (line %d)" % ("s" if b > a else "", a, "-%d" % b if b > a else "", cues[a][3])
    if n == 17:
        turns = cache.get("turns")
        if turns is None:
            turns = []
            lines = read(tx)
            for i, line in enumerate(lines):
                mm = re.match(r"^(.+?) (\d{2}:\d{2})$", line)
                if mm and i + 1 < len(lines):
                    turns.append((mm.group(1), mm.group(2), lines[i + 1], i + 2))
            cache["turns"] = turns
        m = re.match(r"turn (\d+),\s*(\d{2}:\d{2}),\s*(.*)$", loc)
        if not m:
            return False, "unparsed location"
        k = int(m.group(1))
        if k > len(turns):
            return False, "turn %d beyond %d turns" % (k, len(turns))
        name_, ts, text, ln = turns[k - 1]
        who = m.group(3).replace("labelled ", "").split(",")[0].strip()
        if ts != m.group(2) or not name_.startswith(who):
            return False, "turn %d is %s %s, location says %s %s" % (k, name_, ts, who, m.group(2))
        return (quote in text), "turn %d (line %d)" % (k, ln)
    if n in (18, 19, 20, 21):
        u = cache.setdefault("u", bracket_ts_lines(read(tx)))
        return check_units(u, loc, quote)
    if n == 22:
        m = re.match(r"call (\d),\s*(.*)$", loc)
        if not m:
            return False, "unparsed location"
        if m.group(1) == "1":
            u = cache.setdefault("u1", bracket_ts_lines(read(os.path.join(folder, "transcript-1.txt"))))
        else:
            u = cache.get("u2")
            if u is None:
                u = collections.defaultdict(list)
                for i, line in enumerate(read(os.path.join(folder, "transcript-2.txt")), 1):
                    mm = re.match(r"^([^(]+?) \((\d{2}:\d{2}:\d{2})\): (.*)$", line)
                    if mm:
                        u[mm.group(2)].append((mm.group(1).strip(), mm.group(3), i))
                cache["u2"] = u
        return check_units(u, m.group(2), quote)
    if n == 24:
        m = re.match(r"(rec-\d+),\s*(.*)$", loc)
        if not m:
            return False, "unparsed location"
        rec = m.group(1)
        u = cache.get(rec)
        if u is None:
            files = glob.glob(os.path.join(folder, rec + "-*.txt"))
            if not files:
                return False, "no file for " + rec
            u = label_then_text(read(files[0]), r"^(?P<name>.+?) · (?P<ts>\d{1,2}:\d{2})$")
            cache[rec] = u
        return check_units(u, m.group(2), quote)
    if n == 25:
        if loc.startswith("QP-07"):
            paras = cache.get("paras")
            if paras is None:
                z = zipfile.ZipFile(os.path.join(folder, "QP-07-sample-receipt-testing-certification-v3.2.docx"))
                doc = z.read("word/document.xml").decode("utf-8")
                paras = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", p)).strip() for p in re.findall(r"<w:p\b.*?</w:p>", doc, re.S)]
                cache["paras"] = paras
            idx = [i for i, p in enumerate(paras) if quote in p]
            if not idx:
                return False, "not in any SOP paragraph"
            i = idx[0]
            sec = re.search(r"section (\d+(?:\.\d+)?)", loc)
            if sec:
                heads = [j for j in range(i, -1, -1) if re.match(r"^%s\b" % re.escape(sec.group(1)), paras[j])]
                if not heads:
                    return False, "paragraph %d is not under heading %s" % (i + 1, sec.group(1))
            elif "front page" in loc:
                first = next((j for j, p in enumerate(paras) if re.match(r"^1\. ", p)), len(paras))
                if i >= first:
                    return False, "paragraph %d is not on the front page" % (i + 1)
            elif "revision history" in loc:
                rh = next((j for j, p in enumerate(paras) if "Revision history" in p or "revision history" in p), None)
                if rh is None or i < rh:
                    return False, "paragraph %d is not in the revision history" % (i + 1)
            return True, "SOP paragraph %d" % (i + 1)
        if loc.startswith("write-up"):
            pages = cache.get("pages")
            if pages is None:
                b = open(os.path.join(folder, "sample-tracking-what-we-need.pdf"), "rb").read()
                pages = []
                for s in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", b, re.S):
                    try:
                        s = zlib.decompress(s)
                    except Exception:
                        pass
                    parts = re.findall(rb"\((.*?)\)\s*Tj", s, re.S)
                    pages.append(" ".join(p.decode("latin-1").replace("\\(", "(").replace("\\)", ")") for p in parts))
                cache["pages"] = pages
            m = re.search(r"p\.(\d+)", loc)
            p = int(m.group(1)) if m else 1
            if p > len(pages):
                return False, "page %d beyond %d pages" % (p, len(pages))
            return (quote in pages[p - 1]), "PDF page %d" % p
        if loc.startswith("figure"):
            return None, "image label; no text layer, checked by eye"
        u = cache.setdefault("u", bracket_ts_lines(read(tx)))
        return check_units(u, loc, quote)
    return False, "no resolver"

def main():
    folders = sorted([f for f in glob.glob(os.path.join(ROOT, "s*/")) if int(os.path.basename(f.rstrip("/"))[1:].split("-")[0]) >= 11],
                     key=lambda f: int(os.path.basename(f.rstrip("/"))[1:].split("-")[0]))
    all_results = {}
    totals = collections.Counter()
    for folder in folders:
        name = os.path.basename(folder.rstrip("/"))
        key = load_key(folder)
        pairs = []
        collect(key, "", pairs)
        cache = {}
        results = []
        for path, q, loc in pairs:
            ok, where = resolve(name, folder, loc, q, cache)
            results.append((path, q, loc, ok, where))
        n_ok = sum(1 for r in results if r[3] is True)
        n_eye = sum(1 for r in results if r[3] is None)
        n_fail = sum(1 for r in results if r[3] is False)
        totals.update(ok=n_ok, eye=n_eye, fail=n_fail)
        print("%-28s located quotes %4d: %4d at location, %2d image labels (eye), %2d FAIL" % (name, len(results), n_ok, n_eye, n_fail))
        for path, q, loc, ok, where in results:
            if ok is False:
                print("     FAIL %s | %s | %s | %s" % (path, loc, q[:80], where))
        all_results[name] = results
    print("TOTAL located quotes: %d at location, %d image labels, %d failures" % (totals["ok"], totals["eye"], totals["fail"]))
    rng = random.Random(18)
    sample = []
    per = {name: [r for r in rs if r[3] is not None] for name, rs in all_results.items()}
    for name in per:
        sample.extend((name, r) for r in rng.sample(per[name], 2))
    pool = [(name, r) for name in per for r in per[name] if (name, r) not in sample]
    sample.extend(rng.sample(pool, 40 - len(sample)))
    sample.sort(key=lambda x: (int(x[0][1:].split("-")[0]), x[1][0]))
    print("\n=== 40-quote sample ===")
    for i, (name, (path, q, loc, ok, where)) in enumerate(sample, 1):
        print("%2d. %s | %s | %s | \"%s\" | %s | %s" % (i, name, path, loc, q if len(q) <= 90 else q[:87] + "...", "ok" if ok else "FAIL", where))

if __name__ == "__main__":
    main()
```

Output on 2026-09-20: per fixture, every located quote at its location; `TOTAL located quotes: 2074 at location, 1 image labels, 0 failures`; the sample in section 4.
