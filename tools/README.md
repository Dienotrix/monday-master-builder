# tools/

Repo-only release tooling (BUILD-PLAN WP16). Nothing here ships with the plugin. Standard library only, Python 3.9 and later. Tests live in `tests/unit/test_lint_plugin.py`, with synthetic fixtures under `tests/unit/fixtures/tools/`.

## `cleanroom_scan.py` (release check 8)## The clean-room scan (retired 2026-10-13)

`cleanroom_scan.py`, its tests and their fixtures were retired on 2026-10-13 (stage 1b plan, decision D6). It compared the plugin tree against a quarantined corpus for any run of eight or more consecutive prose words, and that corpus no longer exists, so the scan had nothing left to compare against. The clean-room rule itself stands: nothing in the plugin is copied from any earlier plugin or from any real call. What the scan guarded is covered in stage 2 by the agnostic sweep, `tools/agnostic_sweep.py`, which becomes release check 8: it fails on a personal name from the local name index, a GitHub handle outside `plugin.json`, a long numeric id outside the template catalogue in `native-objects.md`, an earlier plugin's name, a firm name other than the publisher, and a reference to a retired file.

very WP16 acceptance check that can be run against files on disk, one function each. Output is one line per finding — `error`, `warning` or `info` — with file, line and check name. Exit 0 with no errors, 1 with errors, 3 when it cannot run; warnings do not change the exit code. An input that does not exist yet is reported as `not present yet`, so the lint runs on a partial tree.

```
python3 tools/lint_plugin.py [--root <repo>]
python3 tools/lint_plugin.py --hash-name "<name>"
```

Checks: description length and angle brackets (skills, agents, `plugin.json`); `name` equals its folder; `SKILL.md` and references at or under 190 lines; references one level deep; relative Markdown links and `${CLAUDE_PLUGIN_ROOT}` paths resolve; reserved names (monday's official skills); no literal `mcp__<server>__` tool name (`mcp__*` and regex matchers pass); all-caps emphasis words outside code; `G-` ids resolve to an entry line in `shared/monday-gotchas.md` and `templates/record|other/<file>` paths name a file; the word "consultant"; the fixed hand-off sentence in `templates/record/scope.md`; a copy of a shared file under a skill's `references/` is byte-identical; the pinned agreement below; and personal names.

**Pinned agreement.** `shared/record-map.md` carries a heading `Pinned: call-type-vocabulary` and a heading `Pinned: permitted-constants`; each section runs to the next heading of the same or a higher level, and the tokens it pins are exactly the backticked spans inside it, for example `` `partner-led` `` or `` `min_units` `` and `` `12` ``. `scripts/transcript_prep.py` and `scripts/transcript_measure.py` each hold the matching region between a line `# pinned: <id>` and a line `# end pinned`; every string and number literal in that region, and every assigned name (lowercased), is the embedded copy. The lint reports a pinned token the script does not embed, and a literal the script embeds that is not pinned. Until both files exist it reports `not present yet`.

**Personal names.** The list lives outside the repo, at `$MMB_HOME/personal-names-index.json` (default `~/DelOps`): `{"schema": "names-index/1", "hashes": ["<sha256>", ...]}`. A name is normalised the way `clients-index.json` normalises a client name — accents folded, lowercased, letters a to z only (a letter with no plain-letter form, such as ø or ß, is dropped) — and hashed; `--hash-name` prints the hash to add. The lint hashes every word and every adjacent word pair of every shipped file and reports a match with the word masked, so neither the list nor the output names anyone. An absent list is a warning, not an error.
