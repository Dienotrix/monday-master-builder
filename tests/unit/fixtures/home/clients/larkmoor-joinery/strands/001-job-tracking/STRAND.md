---
schema: "strand/1"
strand: "001"
slug: "001-job-tracking"
title: "Job tracking"
kind: "platform"                       # platform | non-platform | hybrid
output_class: "configured-structure"
opened: "2026-10-19"
opened_reason: "jobs are lost between the accepted quote and the install"
state: "active"
stage: "shown"                         # platform and hybrid: new | intake | readiness | blueprint | building | audited | shown | signed-off | closing | closed
                                       # non-platform: new | scoping | handed-off | closed
version: "v0.1"
version_state: "audited"
clearance: "cleared to build"
override: "none"
round: "one"
workspaces: "core:40000001"
next_step: "2026-11-10 10:00 confirm the ready-to-install rule with the workshop lead (owner: the user)"
depends_on: "none"
summary_current_to: "none"
closed: "none"
updated: "2026-11-03T16:40"
---
Internal: never client-facing

# 001 Job tracking

## Headline and top pains

Jobs live on an office whiteboard and are lost after the quote; the workshop lead wants one place to see every job and its stage (2026-10-20 call).

## What this build rests on

Cleared to build; v0.1 is a proof of concept. One structural assumption is still unconfirmed: the ready-to-install rule (see the Assumptions of [the readiness check](readiness.md)).

## Version and state

v0.1 audited at revision 1 (sha 5b81f6a), shown on 2026-11-03.

## Next step

Confirm the ready-to-install rule with the workshop lead on 2026-11-10 (owner: the user).

## Links

[readiness](readiness.md) · [blueprint](solution/blueprint.md) · [exclusions](solution/exclusions.md) · [version v0.1](versions/v0.1/version.md) · [audit](versions/v0.1/audit.md)
