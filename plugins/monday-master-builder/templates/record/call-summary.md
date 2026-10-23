---
schema: "call-summary/1"
call_date: ""                          # YYYY-MM-DD, or unknown when the input gives no date
call_type: ""                          # one of the thirteen labels of the call-type vocabulary
seat: ""                               # each of the six fields: the value and its state, detected, assumed or
relationship: ""                       # confirmed; or unresolved, with its candidates and fallback under Call type
direction: ""
output_class: ""
room_shape: ""
money_live: ""
sequence: ""                           # 1, 2, ... from date and internal evidence, or unordered
package: "none"                        # none, or pkg-YYYY-MM-DD
provenance: "first-hand"               # first-hand | handed-over
handed_over_by: "none"                 # a role, or none
attendees: ""                          # client: <role>, <role>; ours: the user
strands: ""                            # short ids, comma-joined, or unassigned
updated: ""
---
Internal: never client-facing

<!-- One heading per part, in this order; the line forms under each are the intake skill's. A heading the input
says nothing about stays and reads: Nothing in this input. A Conflicts heading goes before the client-safe block,
only when there is a conflict. -->

## Call type

## Speakers

| label | role | side | how known |
|---|---|---|---|

## Goals

## Pains

## Constraints

## Signals

## Entities

## Current tools

## Figures

## Open questions

## Agreed

## Commitments

## What the input cannot see

## Client-safe block

<!-- client-safe:start -->
<!-- client-safe:end -->
