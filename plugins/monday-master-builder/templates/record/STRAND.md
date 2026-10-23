---
schema: "strand/1"
strand: ""
slug: ""
title: ""
kind: "platform"                       # platform | non-platform | hybrid
output_class: "configured-structure"   # configured-structure | bespoke-code | hybrid
opened: ""
opened_reason: ""
state: "active"                        # active | paused | closed
stage: "new"                           # platform and hybrid: new | intake | readiness | blueprint | building | audited | shown | signed-off | closing | closed
                                       # non-platform: new | scoping | handed-off | closed
version: "none"
version_state: "none"
clearance: "none"                      # none | cleared to build | cleared to build, generic | not yet
override: "none"
round: "none"
workspaces: "none"
next_step: "none"                      # date, time, what, and (owner: the user)
depends_on: "none"
summary_current_to: "none"
closed: "none"
updated: ""
---
Internal: never client-facing

## Headline and top pains

## What this build rests on
<!-- build-readiness writes this block: the clearance, the count of assumptions in readiness.md and how many are
structural, then one line per structural assumption as readiness.md writes it, without its question:
- clearance: <the clearance string>
- assumptions: <n> in readiness.md, <n> structural
- <statement> [kind: <leaning | board-architecture | automation-condition>; state: <assumed | accepted>] -->

## Next step

## Open commitments
<!-- call-intake writes this block: one line per commitment still open, newest call first. A line leaves the
block only on evidence that the commitment was kept, from a later input or the user:
- <what> · owner: <role> · when: <date or unknown> · from: calls/<stem>.md -->

## Links

`readiness.md` · `solution/exclusions.md`
