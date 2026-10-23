# Intake shapes

The shapes `call-intake` writes: the call summary, the document or email snapshot, and the `meetings.md` line. The record map pins the front-matter fields and the type-header vocabulary ([record-map.md](../../../shared/record-map.md), "Calls, documents and the strand files" and "Pinned: call-type-vocabulary"); the body below is the lean version's, and the readiness check reads it heading by heading. Values are written without the angle brackets. The recap is v2 and is not here.

## The call summary, `calls/<stem>.md`

```
---
schema: "call-summary/1"
call_date: "<YYYY-MM-DD, or unknown>"
call_type: "<one of the thirteen labels>"
seat: "<value> assumed"
relationship: "<value> assumed"
direction: "<value> assumed"
output_class: "<value> assumed"
room_shape: "<value> assumed"
money_live: "<value> assumed"
sequence: "<1, 2, … or unordered>"
package: "<none, or pkg-YYYY-MM-DD>"
provenance: "<first-hand or handed-over>"
handed_over_by: "<a role, or none>"
attendees: "client: <role>, <role>; ours: the user"
strands: "<short ids, comma-joined>"
updated: "<YYYY-MM-DDTHH:MM>"
---
Internal: never client-facing
```

A header field the signals cannot settle reads `"unresolved"`. `assumed` is the pinned word for the best guess intake carries on with; the user's correction makes it `confirmed`. The guard sets `updated`. The call summary starts from `templates/record/call-summary.md`.

Then these level-2 headings, in this order. A section the input says nothing about keeps its heading and reads "Nothing in this input.", so the readiness check sees the gap.

- `## Call type`: the guess in one sentence, then one line per signal in order (screen deixis, same-side direction, agenda, output markers, commercial markers), each with its quote and location or "none"; for an unresolved field, its candidates and the fallback applied; and any change of type mid-call, with the location and the event at it.
- `## Speakers`: a table, `| label | role | side | how known |`, one row per speaker: the label as the file writes it, the role ("titled X, behaves as Y" where they differ), the side (`client`, `ours`, `third-party`, `unknown`), and how known (`header`, `narrated`, `observed`). The user's side's lead speaker's role reads `the user`. Then one line each for anyone listed but silent and anyone speaking unlisted.
- `## Goals`: what the client wants, in their own words. `- G1: <the goal, short> — [Q] "<verbatim quote>" @00:04:12 · <speaker role>`. A yes to the user's side's playback is not a goal; it goes under `## Agreed`.
- `## Pains`: what hurts today. `- P1: <the pain, short> — [Q] "<verbatim quote>" @00:06:40 · <speaker role> · stated | excavated · outcome: "<the wanted outcome in their words>" | none`, ending `· deferred` when the client puts it off until later. `excavated` is a pain the client confirmed only when the user's side asked about it. Several quotes on one theme are `P1.1`, `P1.2`; a workaround kept by hand and a "will not survive" line are pains of their own.
- `## Constraints`: what the client says is not negotiable. `- <the rule> — [Q] "<verbatim quote>" @00:18:20 · <speaker role>`. The readiness check reads these into structure and unmet needs.
- `## Signals`: a client tie the user's side never confirmed, carried forward so the next question can read it back. `- [Q] "<verbatim quote>" @00:21:05 · pain P2 · not confirmed: <what was never confirmed>`. A signal is never evidence.
- `## Entities`: the things the client tracks, children, neighbours and today's artefacts included. `- <name> · parent: <entity or none> · moves on its own: yes | no | unknown · shared across jobs: yes | no | unknown · goes stale: yes | no | unknown · source: spoken | observed · @00:09:30`. "Moves on its own" means its own dates, owner, status or expiry, apart from its parent; "shared across jobs" means booked or reused by many; "goes stale" means produced from data that later changes. Each is set from what the input says of that entity.
- `## Current tools`: by category (a spreadsheet, a shared calendar, an accounting package, a paper form, an inbox), not by brand. `- <category> · holds: <what> · stays the record for: <fields, or unknown> · @00:12:10`.
- `## Figures`: `- <figure> · <what it counts> · said by <role>, <side> · @00:15:44`. A figure the user's side spoke is the user's side's; one re-quoted from another call or seller is `second-hand`; one the client gave in answer to the user's side's what-if is `estimate under a what-if`.
- `## Open questions`: what the call left open, handover work and a build-target offer included. `- <question> · who can answer: <role> · known: <what the record already holds>`.
- `## Agreed`: a playback the client said yes to. `- <the user's side's wording> · confirmed: [Q] "<the client's words>" @00:38:10 · <speaker role>`. Agreed scope, never a goal.
- `## Commitments`: `- <what> · owner: <role> · when: <date or unknown> · state: committed`. A commitment is done only on evidence.
- `## What the input cannot see`: decisions or figures said to have happened off the call, who may have joined or left, who was present when a figure was stated.
- `## Conflicts`, only when there is one: both statements, each with its call or document, speaker or section, and location. Recency never settles it.
- The client-safe block, last:

```
## Client-safe block

<!-- client-safe:start -->
<agreed items, commitments and the next step, in plain words>
<!-- client-safe:end -->
```

The block holds no quote, no evidence marker, no figure, nothing from `exclusions.md`, and nothing internal (strand, record, ledger). Each mark sits alone on its line.

**Condensing a long input.** The summary's budget is 120 lines. Past it, condense in this order: no blank line after a heading; figures grouped by theme, one line each; current tools by category; open questions, agreed items and commitments two or three to a line. Goals, pains, constraints and entities stay one per line, because the readiness check reads them line by line. When they alone pass the budget, accept the warning and say so in the hand back.

**Markers** ([record-map.md](../../../shared/record-map.md), "Evidence markers and the citation contract"): `[Q]` a client quote with a clear speaker; `[Q?]` an unclear speaker; `[Q/side]` the side only; `[Q/recon]` one sentence assembled from several units, with every unit's location; `[X]` quarantined; `[I]` an inference, with its basis, which can only shape a question. A quote whose first or last word sits under another speaker's label is refused, not marked.

## The document or email snapshot, `inputs/<stem>.md`

```
---
schema: "document-summary/1"
input_kind: "<document or email>"
title: "<title>"
source: "<the saved file's stem>"
sha256: "<the sha256 add-document printed>"
author: "<role, or unknown; for an email, the sender>"
document_date: "<YYYY-MM-DD, or unknown>"
status: "<unknown, draft, approved, current-practice or desired-state>"
sequence: "<1, 2, … or unordered>"
provenance: "<first-hand or handed-over>"
handed_over_by: "<a role, or none>"
strands: "<short ids>"
updated: "<YYYY-MM-DDTHH:MM>"
---
Internal: never client-facing
```

Then:

- `## Sections` for a document: `- §<n> <title> · p.<n> · current state | desired state | unknown`. `## Messages` for pasted email text: `- message <n> · from <role or unknown> · to <roles or unknown> · <date or unknown>`, in thread order. `## Text of the image` for a screenshot: the text written out by region, with what is cropped or missing noted.
- `## Goals`, `## Pains`, `## Constraints`, `## Signals`, `## Entities`, `## Current tools`, `## Figures`, `## Open questions`, `## Conflicts` and the client-safe block, as in a call summary. Quotes are `[Q/doc]` and cite `inputs/<stem>.md §3.2`, `p.4`, `message 2 paragraph 3` or `image region top left`. Desired-state sections feed goals and the requirement trace, never the current-state picture.
- `## Attachments`, for an email: the snapshots of any attachment the user added with it.

The snapshot starts from `templates/record/document-summary.md`. A document adds no `meetings.md` line.

## The `meetings.md` line

`meetings.md` starts from `templates/record/meetings.md` and opens with `schema: "meetings/1"`, `client: "<slug>"` and `updated` in its front matter, then the internal line. Under `## Meetings`, newest first, one line per call:

```
- <date> · <call type> · calls/<stem>.md · client: <roles>; ours: the user · strands: <ids> · <first-hand or handed-over>
```

When a package arrives, a line under `## Packages`: `- pkg-<date>: <what arrived>, from <role>, ordered by <the evidence>; second-hand figures: <list or none>`.

## The seven sweep patterns

Seven flaws an intake can make without noticing, each of which a build then carries. Check for each on every call. A hit is written where the pattern says, as a labelled open question or leaning with the quote it rests on, and never as a silent choice. A field that already holds the flaw is corrected as well. Where nothing in the input fits a pattern, write nothing for it: a pattern forced onto an input would be our framing labelled as the client's. A leaning names its pattern in a few words, as `pattern:` in the readiness file's leanings.

1. **One row where the call describes many.** Look for a record that the call describes as several things moving on their own (a job with many parts, a batch with many items, a pursuit with many documents) while the client's current tool holds one line with one date, status or owner. Write the parts as entities with `parent:` and `moves on its own: yes`, with the quote. Do not decide the structure at intake; the readiness check turns the hit into a leaning and applies `parent-row-with-roll-up`. Example: a client says one order "goes out in two lots, a week apart", and the sheet has one ship date per order.
2. **A pain with no element that fixes it.** Look for a pain whose wanted outcome the call never connects to anything that would deliver it, or one the call puts down to a record that has no place for it. Keep the pain and its outcome line even when nothing answers it. The readiness check's `### Element per pain` shows the gap with the verdict `none`; see [readiness-guide.md](../../build-readiness/references/readiness-guide.md).
3. **An alias that names more than one entity, or many names for one.** Give each person, place and organisation one entry, under the name the client uses most. Fold two labels in only when the call shows they are one (a speaker introduced under a nickname, a site called by its street and by its town). Never fold two different people or places into one entry because they are named together ("the two crew leads"); the build may need them apart, as when each place has its own rule. When the call does not settle whether two names are one, keep two entries and put the question under `## Open questions`.
4. **Our framing labelled as the client's.** Look for a list, stage set, term or requirement that traces only to the user's side (a playback, a demo, a suggestion) and not to a client's own words. Record it as the user's side's, or under `## Agreed` if the client said yes to it, never as a goal, a constraint or the client's own stages. The client's own words for their own steps stay as they said them, even when ours are tidier. See "Always" in [SKILL.md](../SKILL.md).
5. **A shared resource with no reservation tracking.** Look for anything the client books or reuses across jobs (a crane, a crew, a van, a room, a stock of crates). Set `shared across jobs: yes` on its entity line and quote how it is booked today. Note under `## Open questions` who holds it when, and how clashes are found now, because a build that lists the resource without showing who holds it when lets it be promised twice.
6. **An artefact that can go stale with nothing to flag it.** Look for anything produced from data that later changes (a printed ticket, a proof, a pack, a quote, a forecast, a list copied from another system). Set `goes stale: yes` on its entity line, with the quote that names the change and the failure it caused. Write the question of how the person would know it is out of date. The readiness check then asks for an element that shows it as outdated.
7. **An expected output the input cannot support.** Write only what the input carries. A surname never spoken, a date that a weekday alone cannot fix, a talk share from a transcript whose speaker labels were shredded, a figure from a call that was not recorded: each is `unknown` or an estimate with its basis, never a figure or a name filled in. Say under `## What the input cannot see` what is missing and why, and let a figure read "by label, likely understated" where the labels are unreliable. Nothing later depends on a value the input did not carry.
