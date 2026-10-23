---
schema: "document-summary/1"
input_kind: "document"                 # document | email
title: ""
source: ""                             # the saved file's stem
sha256: ""                             # the sha256 add-document printed
author: "unknown"                      # a role, or unknown; for an email, the sender
document_date: "unknown"               # YYYY-MM-DD, or unknown
status: "unknown"                      # unknown | draft | approved | current-practice | desired-state
sequence: ""                           # 1, 2, ... from date and internal evidence, or unordered
provenance: "first-hand"               # first-hand | handed-over
handed_over_by: "none"                 # a role, or none
strands: ""                            # short ids, comma-joined, or unassigned
updated: ""
---
Internal: never client-facing

<!-- One heading per part, in this order; the line forms under each are the intake skill's. The first heading is
Sections for a document, Messages for pasted email text, or Text of the image for a screenshot. A heading the input
says nothing about stays and reads: Nothing in this input. A Conflicts heading, only when there is a conflict, and
an Attachments heading, for an email with attachments, go before the client-safe block. -->

## Sections

## Goals

## Pains

## Constraints

## Signals

## Entities

## Current tools

## Figures

## Open questions

## Client-safe block

<!-- client-safe:start -->
<!-- client-safe:end -->
