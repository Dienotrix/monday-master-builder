---
name: probe-root
description: Stage-0 probe S0-1. Use when the user asks to use the probe-root skill.
---

Stage-0 probe S0-1. The three instructions below each name a path through the plugin root variable, written here exactly the way a shipped skill names its scripts (A§5.2 rung 1). The question is whether the variable is substituted in this text before you read it. So follow the instructions as written: do not fill the path in from anything you know or can search for, do not ask the user for a path, and do not look for the plugin folder some other way. Where a step fails, report the exact error text in place of a result.

1. Read the file "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" and report its name field.
2. In the device shell, run: echo "${CLAUDE_PLUGIN_ROOT}"; ls "${CLAUDE_PLUGIN_ROOT}/hooks"
3. In the cloud shell, run the same two commands. In Claude Code, which has one shell, run them once and say so.

Reply with the three results, each labelled with its step number, exactly as they came back and nothing else.
