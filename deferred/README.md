# deferred/

Files kept for the v2 and v2-or-v3 layers of the plugin. Nothing in this folder ships: the plugin is the tree under `plugins/monday-master-builder/`, and the always-on token count, the lint (`tools/lint_plugin.py`) and the release checks read that tree and never this folder. No skill is built on anything here until the layer it belongs to is scheduled.

Why the folder exists. The user's decision of 2026-09-19 (A19) put the build first: v1 turns inputs into a working monday proof of concept, and the sales layer, the house voice, the demo run-sheets, the recap drafts and the SOP package come later, with their files kept and no skill built. The plan for stage 1b (decision D5) moved those files out of the shipped tree, so a shipped file never links to a deferred one and a reader of `shared/` sees only what v1 uses.

What is here, and which layer it belongs to.

| Path | Layer | Was | Note |
|---|---|---|---|
| `shared/sales-method.md` | v2 | `plugins/monday-master-builder/shared/sales-method.md` | the readiness rubric, gates, verdicts, scope matrix, objection map and claims rules in sales terms; v2 is "bring your own method", so a replacement may stand in its place |
| `shared/house-style.md` | v2 | `plugins/monday-master-builder/shared/house-style.md` | the register for spoken and sent output; v1 carries nothing specific to one person's voice |

Both files were moved unchanged on 2026-10-13 in the fixture fix pass, so a path inside them that reads `shared/<file>` still means the shipped `shared/` folder as it was on that date, and `record-map.md` tags the strand rows and vocabularies they define as v2 or v2-or-v3 rather than deleting them. The v2 and v2-or-v3 skills, templates and scripts join this folder as they are written, in the same layout they would have in the plugin (`skills/`, `templates/`, `scripts/`), so a later promotion is a move back.

Rules that still apply here. Everything is fictional or generic: no person, former firm or monday account is named, and no reference to earlier work enters. A file promoted back into the plugin passes the lint and the agnostic sweep first.
