# The readiness file

The shape of `strands/<id>/readiness.md`. The fields and their values are pinned in [record-map.md](../../../shared/record-map.md), "Pinned: readiness" (`readiness/1`); this file sets them out as the lean version writes them, one level-2 heading per field in the pinned order. `record.py` reads the front-matter `clearance` and the lines under `## Assumptions`, so those two are written exactly as below. Values are written without the angle brackets.

```
---
schema: "readiness/1"
clearance: "<cleared to build | cleared to build, generic | not yet>"
updated: "<YYYY-MM-DDTHH:MM>"
---
Internal: never client-facing
```

## The headings, in order

Four of the seven sweep patterns bear on `## Entities`, `### Leanings`, `### Patterns` and `### Element per pain`: one row for many, a pain with no element, a shared resource, a stale artefact. They are set out in [intake-shapes.md](../../call-intake/references/intake-shapes.md#the-seven-sweep-patterns).

**`## Note`.** One or two sentences: what the check was derived from (the summaries, by path), and that structure assertions stay provisional until the user has seen a real build. Say here when the input states no goal.

**`## Goals`.** One line per goal, `G1`, `G2`, … in the order the record first shows them:

```
- G1: <the goal, short, in the client's words> — [Q] "<verbatim quote>" @00:04:12 · <speaker role> · pains: P1, P3
```

**`## Pains`.** One line per pain, numbered as the summaries number them (`P1`, or `P1.1` and `P1.2` where one theme holds several quotes):

```
- P1: [Q] "<verbatim quote>" @00:06:40 · <speaker role> · stated | excavated · outcome: "<the wanted outcome in the client's words>" | none
```

Every pain line of the summaries is carried, a second line in a theme included. A pain the client puts off ends `· deferred` and still gets its outcome and its row under `### Element per pain`.

**`## Signals`.** `- [Q] "<verbatim quote>" @00:21:05 · pain: P2 · not confirmed: <what the user's side never confirmed>`. Carried forward, never counted as evidence.

**`## Entities`.** One line per entity, and on the next line its independence note:

```
- <name> · parent: <entity or none> · moves independently: yes | no | unknown · shared resource: true | false · goes stale: true | false · source: spoken | observed | documented | assumed · evidence: <location or none>
  independence: <what moves independently of what, and on what evidence>
```

`shared resource` is true for a record booked or reused across many jobs or owners; `goes stale` is true only for a record produced from data that later changes (a forecast, a report, an exported list), not for a record people edit. Each flag follows that entity's evidence; where there is none, the independence note says so.

**`## Structure`.** First these lines:

```
- products: <Work Management | CRM | Service>, by entity; Dev named and not built where it comes up
- build target: <own-account | client-account> · reason: <from CLIENT.md `build_target_reason`, or: the record's default; the input offered <target>, see Assumptions>
- workspaces: <name> – Ops; <name> – CRM
- native reuse: <the native boards reused, by entity, each with the client's word where it differs, or: no CRM or Service entity>; found by preflight, or installed from the native templates when the workspace is bare
```

Then three level-3 headings:

- `### Leanings`: `- question: <the open question> · option: <the leaning> · quotes: [Q] "<quote>" @00:11:02 · condition: <what would settle it> · pattern: <the pattern in a few words, or fork>`. Every quote keeps its location on the same line.
  One pursuit with several documents from an outside system gets this leaning: option, the pursuit as parent with each document as a child row and a roll-up; condition, how often a second document happens (rarely, and one row with earlier numbers in its updates will do).
- `### Patterns`: one line per pattern applied, as `- parent-row-with-roll-up: <parent> with <children> as child rows, <roll-up> on the parent`. Where the children live on a native board of their own, write `as connected rows on <board>` in place of `as child rows`. The pattern applies to every parent whose children move on their own, not only the first one found.
- `### Element per pain`: one line per pain id, `- P1 · element: <the element that answers it> · verdict: fixes | copies-today's-tool | none · <why, in one clause>`. `none` is a finding and stays visible. An element holding a value keyed by hand from another system names its `<system> status as of` date field and who keys it, or `who keys it: unknown`.

**`## Existing`.**

```
- account: <what the record says exists, with each live object's constraint, or: unknown, no account bound>
- incumbent: <tool category> · authority: stays system of record for: <fields>; follower for: <fields> · evidence: <location or none>
```

**`## Assumptions`.** One line each in exactly this form, which `record.py` reads for the sign-off warning, with the question on the next line:

```
- <statement> [kind: gap | call-type | automation-condition | board-architecture | leaning; state: assumed | accepted]
  question: <the question that would replace it>
```

`accepted` is for an assumption the user has accepted on the client's word. A confirmed one becomes evidence and leaves the list.

The kind follows what the line is. `gap` is a fact missing from the record (a name, a date, a count, who keys a value). A structural choice with a settling condition is a `leaning`; the overview of the boards, a territory or a team as a column rather than a workspace among them, is `board-architecture`; each trigger and threshold is `automation-condition`. A figure the client never gave is written in the statement as `ours, provisional: <figure>`, so the user can correct it. Handover work the input leaves open (an import, an earlier board's fate, invented sample rows) gets its line like any other.

**`## Unmet needs`.** `- <need> · clock: <when, or none> · why not met: <the product limit, the missing probe, or work outside monday>`.

**`## AI opportunities`.** `- pain_or_need: <pain id or need> · kind: workflow | agent | ai_column | vibe_app | sequence · round: 1 | 2 · probe_basis: P-19 | P-20 | P-21 | unprobed · idea: <one sentence>`.

**`## Verdict`.** The machine value solution-blueprint reads, the conditions and one reason:

```
- cleared_for: build | build-generic | not-yet
- conditions: the approval card; <an A11 question that matters now>; <a workspace not yet named>; <a probe not yet run>
- reason: <one sentence>
```

Each condition names what it waits on and who clears it. On an own-account build, write the workspace condition as the user's workspace, named in solution-blueprint, never as a client account not yet bound. Finding or installing the native boards is the build's step and is not a condition.

`cleared_for` and the front-matter `clearance` say the same thing: `build` is `cleared to build`, `build-generic` is `cleared to build, generic`, `not-yet` is `not yet`. A fresh file carries `none`, which the check never writes.

**`## Questions`.** At most five, ordered:

```
1. <the question> · kind: read-back | discovery · role: <who can answer> · known: <what the record already holds>
```

One question per unresolved structural choice comes before a second variant of one already asked. A quote in `known` keeps the location of the line it was copied from.

## Budget and checks

The file stays under 250 lines. `record.py check` blocks on a `clearance` outside the three strings and `none`, warns when it differs from `STRAND.md`, and warns on a quote marker with no location on its line. No grade, score, gate name or sales verdict appears anywhere in the file.
