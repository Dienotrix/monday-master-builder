---
name: probe-door
description: Opens the probe door. Use whenever the user mentions a probe door, asks to open it, or wants to know whether the door works.
disable-model-invocation: true
---

Stage-0 probe S0-7. The description above invites the model to open this skill on its own; the flag in the frontmatter is meant to stop that. Only a typed `/probe-door` should reach this line.

Reply with exactly this line and nothing else:

probe-door opened
