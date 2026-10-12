---
name: "engagement"
description: "Front door for a client record. Reads the record, briefs the user and routes to the next step."
---
# engagement

Front door for a client record. It reads the record and briefs the user.

Always
- Start from `record.py status --json`, because the record is the memory.
- Refer to monday tools by base name, `create_board` for example, because the prefix varies by install.
- The word `MUST` inside a code span is code, not emphasis.

Steps
1. Read [routing](references/routing.md) and the copy in [safety](references/safety.md).
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/transcript_prep.py" type` when a transcript arrives.
3. Keep G-01 and G-02 in mind; the scope template is `templates/record/scope.md`.

Stop and ask when the record names two open strands and the call does not say which.

```text
NOTE inside a fenced block is code and is not an emphasis finding.
```
