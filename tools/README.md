# tools/

Repo-only release tooling (BUILD-PLAN WP16). Nothing here ships with the plugin. Standard library only, Python 3.9 and later. Tests live in `tests/unit/test_cleanroom_scan.py` and `tests/unit/test_lint_plugin.py`, with synthetic fixtures under `tests/unit/fixtures/tools/`.

## `cleanroom_scan.py` (release check 8)

Finds any run of eight or more consecutive prose words that appears both in the plugin tree and in a set of quarantined files, and reports the file, the line and the run.

```
python3 tools/cleanroom_scan.py <quarantined file or folder>...
python3 tools/cleanroom_scan.py --tree <folder> --words 8 <quarantined>...
```

`--tree` names what to scan (repeatable; default `plugins/monday-master-builder`), so the same scan runs over the fixtures workspace. Exit 0 clean, 1 findings, 3 could not run.

How prose is told apart from identifier and enum lists, on both sides alike:

- Fenced code blocks are skipped, and inline code spans are removed before a line is read.
- A line is an enum list, and skipped, when it splits on commas, semicolons or pipes into three or more segments averaging at most two words each. Table rules are skipped too.
- A token is identifier-like when it carries an underscore, a digit, an inner capital, a path separator or a dot inside it. A line where such tokens are at least half of all tokens is skipped; in a prose line they are dropped and the words either side still join.
- What remains is lowercased and joined across the lines of a paragraph, so a copied sentence is found even when it wraps differently.

## `lint_plugin.py` (release check 3)

Every WP16 acceptance check that can be run against files on disk, one function each. Output is one line per finding — `error`, `warning` or `info` — with file, line and check name. Exit 0 with no errors, 1 with errors, 3 when it cannot run; warnings do not change the exit code. An input that does not exist yet is reported as `not present yet`, so the lint runs on a partial tree.

```
python3 tools/lint_plugin.py [--root <repo>]
python3 tools/lint_plugin.py --hash-name "<name>"
```

Checks: description length and angle brackets (skills, agents, `plugin.json`); `name` equals its folder; `SKILL.md` and references at or under 190 lines; references one level deep; relative Markdown links and `${CLAUDE_PLUGIN_ROOT}` paths resolve; reserved names (monday's official skills); no literal `mcp__<server>__` tool name (`mcp__*` and regex matchers pass); all-caps emphasis words outside code; `G-` ids resolve to an entry line in `shared/monday-gotchas.md` and `templates/record|other/<file>` paths name a file; the word "consultant"; the fixed hand-off sentence in `templates/record/scope.md`; a copy of a shared file under a skill's `references/` is byte-identical; the pinned agreement below; and personal names.

**Pinned agreement.** `shared/record-map.md` carries a heading `Pinned: call-type-vocabulary` and a heading `Pinned: permitted-constants`; each section runs to the next heading of the same or a higher level, and the tokens it pins are exactly the backticked spans inside it, for example `` `partner-led` `` or `` `min_units` `` and `` `12` ``. `scripts/transcript_prep.py` and `scripts/transcript_measure.py` each hold the matching region between a line `# pinned: <id>` and a line `# end pinned`; every string and number literal in that region, and every assigned name (lowercased), is the embedded copy. The lint reports a pinned token the script does not embed, and a literal the script embeds that is not pinned. Until both files exist it reports `not present yet`.

**Personal names.** The list lives outside the repo, at `$MMB_HOME/personal-names-index.json` (default `~/DelOps`): `{"schema": "names-index/1", "hashes": ["<sha256>", ...]}`. A name is normalised the way `clients-index.json` normalises a client name — accents folded, lowercased, letters a to z only (a letter with no plain-letter form, such as ø or ß, is dropped) — and hashed; `--hash-name` prints the hash to add. The lint hashes every word and every adjacent word pair of every shipped file and reports a match with the word masked, so neither the list nor the output names anyone. An absent list is a warning, not an error.
