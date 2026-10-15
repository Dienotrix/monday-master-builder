---
schema: "blueprint/1"
strand: "001"
revision: "1"
sample_rows: "planned"
updated: "2026-10-26T15:40"
---
Internal: never client-facing

# Blueprint: Job tracking

## Elements

| key | kind | name | purpose |
|---|---|---|---|
| W1 | workspace | Larkmoor Joinery – Ops | holds the job tracking board |
| B1 | board | Jobs | one item per job, from accepted quote to installed |
| B1.V1 | view | Jobs by stage | the Jobs board grouped by its stage column |

## Sample rows

Six sample jobs with invented customers and sizes, checked against the strand's exclusions file before they are written.

## What this build rests on

- [A] A job is ready to install when every cutting-list line is ticked; basis: the readiness check, Assumptions; it stays assumed until the workshop lead confirms it.
