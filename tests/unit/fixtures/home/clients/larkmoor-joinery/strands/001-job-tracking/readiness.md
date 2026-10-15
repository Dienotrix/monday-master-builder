---
schema: "readiness/1"
clearance: "cleared to build"
updated: "2026-10-22T11:00"
---
Internal: never client-facing

## Note

Derived from the 2026-10-20 discovery call. Structure assertions stay provisional until the user has seen a real build.

## Goals

- G1 one place to see every job and its stage: [Q] "What I want is one place where I can see every job and what stage it is at." @00:01:12, the workshop lead; pains: P1

## Pains

- P1 [Q] "The trouble is we lose track after the quote." @00:00:31, the workshop lead; stated; outcome: one place where I can see every job

## Signals

None.

## Entities

- Job: parent none; moves independently yes; shared resource false; goes stale false; source spoken; evidence @00:00:15
- Cutting-list line: parent Job; moves independently no; shared resource false; goes stale true; source spoken; evidence @00:00:15

## Structure

- products: Work Management; build target own-account, a proof of concept in the user's own account
- workspaces: Larkmoor Joinery – Ops
- patterns: parent-row-with-roll-up: Job with cutting-list lines as child rows, lines done on the parent
- element per pain: P1, the Jobs board, fixes

## Existing

Account: the user's own account, bound; nothing of ours built yet. Incumbent: the office whiteboard, stays system of record for: nothing; follower for: nothing; evidence @00:00:15.

## Assumptions

- A job is ready to install when every cutting-list line is ticked [kind: automation-condition; state: assumed]
  question: When the last cutting-list line of a job is ticked, should the job move to ready to install on its own?
- One board holds every job, with the stage as a status column [kind: board-architecture; state: accepted]
  question: Should jobs sit on one board with a stage column, or on one board per stage?
- Site visits stay outside the board for now [kind: gap; state: assumed]
  question: Who books site visits today, and where are they kept?

## Unmet needs

- Site visit booking: clock none; not met because the owner asked to leave it out for now @00:02:05.

## AI opportunities

None in round one.

## Verdict

- cleared_for: build
- conditions: the approval stop
- reason: one pain with an entity and a wanted outcome, the product chosen, the structure stated and the build target named.

## Questions

1. When the last cutting-list line of a job is ticked, should the job move to ready to install on its own? (read-back; the workshop lead; known: @00:01:41)
