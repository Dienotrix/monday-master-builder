#!/bin/sh
# Stage-0 probes S0-12 and S0-14.
# Records what a PreToolUse hook is handed on stdin, then refuses the call, so nothing reaches monday.
# The dump holds only the hook's input: the tool name and its arguments. Delete it after recording.
# The refusal reason also carries the first 600 characters of that input, so S0-14 can be read
# from the chat itself on a surface where the plugin's own folder is not visible (Cowork).
here="$(cd "$(dirname "$0")" && pwd)"
input="$(cat)"
printf '%s\n' "$input" >> "$here/../hook-dump.jsonl"
seen="$(printf '%s' "$input" | tr -d '\n\r\t' | cut -c1-600 | sed 's/\\/\\\\/g; s/"/\\"/g')"
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"stage-0 probe hook ran (S0-12). It received (S0-14): %s"}}' "$seen"
exit 0
