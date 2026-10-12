# Stage 1 acceptance: WP0, WP-S0 and the WP16 tools

Run on 2026-09-20 in Claude Code on the Mac (Python 3.9.6, Claude Code 2.1.268), against the tree as it stands: no commits yet, everything untracked. The contract is the acceptance line of each package in `BUILD-PLAN.md` section 2, read with `ARCHITECTURE.md` section 13 (A§13) and `rebuild-workspace/cowork-capabilities.md`. Nothing was changed; every finding below is for its owning package to act on. Section 1 is what was run and what came back, section 2 the acceptance line by line, section 3 what has to change before stage 1 is signed off, section 4 notes that need no change to pass, section 5 what this run did not check.

Twenty-five checks: 21 pass, 2 fail, 1 partial, 1 not checked.

---

## 1. What was run

Every command from the repo root, `/Users/caramelm4/DelOps/monday-master-builder`.

### 1.1 Manifests (WP0)

```
$ claude plugin validate --strict plugins/monday-master-builder
Validating plugin manifest: .../plugins/monday-master-builder/.claude-plugin/plugin.json
✔ Validation passed                                                     (exit 0)

$ claude plugin validate --strict .
Validating marketplace manifest: .../.claude-plugin/marketplace.json
✔ Validation passed                                                     (exit 0)

$ claude plugin validate --strict tests/stage0/probe-plugin              (not required; run for WP-S0)
✔ Validation passed                                                     (exit 0)
```

No warning was printed by either required run, including the `CLAUDE.md` warning A§2 expects the validator to give; it did not.

```
$ find . -path ./.git -prune -o \( -iname CLAUDE.md -o -name .mcp.json -o -type d \( -name commands -o -name bin \) \) -print
(nothing)

$ grep -rn -i '"version"|^version:|version =' . --exclude-dir=.git --exclude-dir=__pycache__
plugins/monday-master-builder/.claude-plugin/plugin.json:4:  "version": "0.1.0",
plugins/monday-master-builder/shared/record-map.md:143: ... "version": "v0.1" ...     (a lock/2 field in a schema example)
plugins/monday-master-builder/shared/record-map.md:145: ... "version": "v0.1" ...     (same)
tests/stage0/probe-plugin/.claude-plugin/plugin.json:3:  "version": "0.0.1",         (the throwaway probe plugin)
tests/unit/fixtures/tools/lint-bad/.../plugin.json:4:  "version": "0.0.0",           (lint fixture)
tests/unit/fixtures/tools/lint-clean/.../plugin.json:4:  "version": "0.0.0",         (lint fixture)
```

Line counts: `marketplace.json` 18, `plugin.json` 10, `.gitignore` 19.

### 1.2 The lint (WP16)

```
$ python3 tools/lint_plugin.py
info: skills/: frontmatter: not present yet
info: agents/: frontmatter: not present yet
error: shared/monday-gotchas.md:104: all-caps: all-caps emphasis word NOT
info: templates/: template-id: not present yet
info: templates/record/scope.md: handoff-sentence: not present yet
info: scripts/transcript_prep.py: pinned-agreement: not present yet (call-type-vocabulary unchecked)
info: scripts/transcript_measure.py: pinned-agreement: not present yet (permitted-constants unchecked)
warning: personal-names-index.json: personal-name: name list not found at /Users/caramelm4/DelOps/personal-names-index.json; check not run
lint_plugin: 1 error(s), 1 warning(s), 6 not present yet, 10 file(s)      (exit 1)
```

The same output with `--root` given explicitly, and the same under Python 3.13.14. The ten files are the nine `shared/` files and `plugin.json`; `.gitkeep` placeholders are not text files to the lint.

The one error is line 104 of `monday-gotchas.md` (entry G-26), which quotes monday's own error text: `"data/settings must NOT have additional properties"`. The text sits in double quotes, not in a code span, so the lint reads it as prose. The lint's contract exempts code spans and fenced blocks only.

### 1.3 Unit tests

```
$ python3 -m unittest discover -s tests/unit -v          (Python 3.9.6)
Ran 31 tests in 0.037s
OK                                                       (exit 0)

$ .../uv/python/cpython-3.13-.../bin/python3.13 -m unittest discover -s tests/unit
Ran 31 tests in 0.028s
OK
```

Ten tests for `cleanroom_scan.py`, twenty-one for `lint_plugin.py`. Both scripts import only the standard library (`argparse`, `ast`, `hashlib`, `json`, `os`, `re`, `sys`, `unicodedata`). No Python 3.11 is installed on this Mac (`uv python list` shows 3.13 and 3.14 installed, 3.11 as a download), so release check 2's 3.11 run is still owed.

### 1.4 `.gitignore`

```
$ git check-ignore -v --no-index tests/ tools/ tests/unit/test_lint_plugin.py tools/lint_plugin.py \
    .work/lock.json plugins/monday-master-builder/.work/x.json \
    tests/unit/fixtures/record/.work/lock.json plugins/monday-master-builder/.DS_Store tests/unit/__pycache__/
.gitignore:10:.work/        .work/lock.json
.gitignore:10:.work/        plugins/monday-master-builder/.work/x.json
.gitignore:19:.DS_Store     plugins/monday-master-builder/.DS_Store
.gitignore:14:__pycache__/  tests/unit/__pycache__/
```

`tests/` and `tools/` are not matched; `.work/` is; the `!tests/**/.work/` re-include works, so a fixture record's lock file would be tracked. `git status --short --ignored` agrees: `tests/` and `tools/` untracked, only `.DS_Store` and the two `__pycache__/` folders ignored.

### 1.5 Sweeps

```
$ grep -rn -i 'consultan' plugins/            (word "consultant": none)
plugins/.../shared/leak-terms.txt:3:   # ... the consultancy's name in its
plugins/.../shared/leak-terms.txt:31:  # The consultancy, in the renderings ...
plugins/.../shared/safety.md:83:       ... the consultancy, plugin and assistant names; ...
```

Personal names: a grep for the user's names, the Mac account name and the fixture's planted name found nothing under `plugins/`; the planted fictional name appears only in `tests/unit/fixtures/tools/lint-bad/` and in `tests/unit/test_lint_plugin.py`, where it is the test's own input. Every capitalised word pair in `plugins/` is a monday object, a product name or a heading (`Sales Targets`, `Service Contacts`, `Demo Build`, `Claude Code`, and so on). A word-bounded scan for `he`, `his`, `him`, `she`, `hers`, `himself`, `herself` over every `.md`, `.txt`, `.py`, `.json` and `.sh` file in the repo found nothing. The user's GitHub handle appeared in `plugin.json` (the `repository` field) and `record-map.md:69` (the archive repo naming), both placed by the design (A§2, A§7.1), and in the two stage-0 files where the design itself named the `gh` account; on 2026-10-13 it was removed from every file except `plugin.json`, where it names the publisher (D6). `DelOps` appears as the manifest author (A§2), as denylist entries in `leak-terms.txt`, and as the `~/DelOps` default root in `record-map.md:65` (A§5.3).

---

## 2. Acceptance, line by line

| # | Package | Check | Result | Evidence |
|---|---|---|---|---|
| C1 | WP0 | `validate --strict` passes on the plugin | pass | 1.1 |
| C2 | WP0 | `validate --strict` passes on the marketplace | pass | 1.1 |
| C3 | WP0 | the version appears only in `plugin.json` | pass | 1.1: the other `version` strings are a record-schema field and the manifests of three repo-only throwaway plugins, none of them the product's version |
| C4 | WP0 | no `CLAUDE.md`, `.mcp.json`, `commands/` or `bin/` anywhere | pass | 1.1 |
| C5 | WP0 | manifests under 30 lines; shape as A§2 (`delops`, one entry, `displayName`, author `DelOps`, `repository`) | pass | 18 and 10 lines |
| C6 | WP-S0 | every README block says the surface, what to do, what yes and no look like, and what changes with which default | pass | all fifteen blocks carry the five parts; S0-14 leans on S0-12's query and S0-6b on S0-5's agent, both by explicit cross-reference |
| C7 | WP-S0 | each probe exercises the mechanism the design relies on | **fail** | S0-1 and S0-6b, section 3 |
| C8 | WP-S0 | the README's defaults agree with A§13 | pass | S0-1 to S0-15 each carry the A§13 default in A§13's words; S0-5's `tools: TodoWrite` fallback and S0-6b's write-detection fallback match A§4; S0-12's decoration default matches A§9.10; S0-10's C5 resolves to A§12.1 |
| C9 | WP-S0 | the README's reused facts agree with `cowork-capabilities.md` | pass | device Python 3.10 (§3), the delete prompt (§2, §3), upload host refused from the cloud shell (§7), no `gh` in either shell (§3, §8), a plugin listed (§9), the connected folder under `$HOME/mnt/` (§2), two shells (§3) |
| C10 | WP-S0 | `results.md`: every probe has a result with a date and surface, or `not-run` with the reason | partial | S0-4, S0-6b and S0-7 read `not-run` with no reason in the row; the preamble gives the blanket reason (the user has not run stage 0), the file's own rule asks for one per row |
| C11 | WP-S0 | each row names the package it changes and whether the safe default applies | pass | both columns filled on all fifteen rows |
| C12 | WP-S0 | S0-12, S0-14 and S0-15 carry an explicit yes or no | pass | "Working answers": no, no, no on every path |
| C13 | WP-S0 | no probe writes to a client account; a write probe runs only in the [A11-1] workspace | pass | README line 3 and results.md line 5 name the one test workspace and say the long-term answer is open |
| C14 | WP-S0 | probes the capability check already answers are marked so in `results.md` | pass | S0-2 (cloud half), S0-3 (two steps), S0-10 (cloud half), S0-11 (Cowork, 2026-09-11) and S0-13 (Cowork half) cite the section; S0-5, S0-8, S0-9 and S0-15 cite what the check does and does not settle; the closing section lists the same set |
| C15 | WP-S0 | sizes: README 95 lines, results 130 | pass | 86 and 39 |
| C16 | WP16 | the lint runs on the current tree and reports absent things as absent | pass | 1.2: six `not present yet` lines for skills, agents, templates, `scope.md` and the two pinned scripts; the two `Pinned:` headings the stage-2 check will need exist in `record-map.md` (lines 186 and 203) |
| C17 | WP16 | the lint runs clean (no error) on the current tree | **fail** | one error, `monday-gotchas.md:104`, section 3 |
| C18 | WP16 | unit tests pass under `python3` | pass | 31 tests, Python 3.9.6; the same 31 under 3.13.14 |
| C19 | WP16 | standard library only, Python 3.9 syntax | pass | imports listed in 1.3; both scripts ran under 3.9.6 |
| C20 | WP16 | sizes: lint 360, cleanroom 200 | pass | 360 and 186; `tools/README.md` 36 |
| C21 | WP16 | every item of the lint's acceptance list has a check and a test | pass | description length and angle bracket, name is its folder, `SKILL.md` and reference size, reference depth, missing link (Markdown and `${CLAUDE_PLUGIN_ROOT}`), reserved name, prefixed tool name, all-caps word, absent gotcha and template id, "consultant", personal name by hashed list outside the repo, hand-off sentence, shared copy, pinned agreement: one function and one test each; the hand-off sentence in the lint matches `record-map.md:107` character for character |
| C22 | WP16 | the personal-name check exercised on the real tree | not checked | no `personal-names-index.json` under `~/DelOps`, so the lint warned and skipped; the hand sweep in 1.5 stands in for it |
| C23 | WP0 | `.gitignore` keeps `tests/` and `tools/`, drops `.work/` | pass | 1.4 |
| C24 | sweep | no "consultant" in a shipped file | pass | 1.5 |
| C25 | sweep | no personal name in a shipped file (A12) | pass | 1.5; see note 10 on the GitHub handle |

---

## 3. Must fix before stage-1 sign-off

**1. S0-1 does not probe the path the design uses (WP-S0, `tests/stage0/README.md` lines 11 to 14).** The block has the user type `Read "${CLAUDE_PLUGIN_ROOT}/..."` and `echo "$CLAUDE_PLUGIN_ROOT"` into the chat. The design's mechanism is different: `${CLAUDE_PLUGIN_ROOT}` is substituted in plugin content — a skill body that says `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"` (A§5.2 rung 1) — and is set in the environment of a hook, not in the main chat's shell, where several plugins would each need their own value. A variable the user types is not substituted by anything, so the shell prints an empty line and the probe reads no even where the design's path works; or the model fills the path in from what it knows, and the probe reads yes for the wrong reason. Either way two packages switch on it (WP1 and WP16, `sync_shared.py` joining the release). The probe belongs in the probe plugin the way S0-9 already does: a `probe-root` skill whose body carries the three literal `${CLAUDE_PLUGIN_ROOT}` instructions, and an S0-1 block that says "Use the probe-root skill" on each surface.

**2. S0-6b cannot tell the wildcard from the allowlist (WP-S0, README lines 36 to 39; `probe-plugin/agents/probe-agent.md`).** `probe-agent` carries `tools: Read` beside `disallowedTools: ... mcp__*`. With a `tools` allowlist the agent has Read and nothing else whatever `disallowedTools` says, so the monday tool is unavailable to it on both branches of the question, and the block's yes ("the wildcard covered the connector") is not an inference the probe supports. A false yes here is the unsafe direction: the auditor (A§4) has no `tools` allowlist on purpose and relies on exactly this wildcard. S0-6b needs an agent with no `tools` line and only `disallowedTools: mcp__*` — `probe-agent-bare` is that shape apart from its instruction — while S0-5 keeps `probe-agent` as it is.

**3. The tree is not lint-clean (WP1's file, WP16's rule; `shared/monday-gotchas.md:104`).** G-26 quotes monday's error text `"data/settings must NOT have additional properties"` in double quotes, and the all-caps check reads the quoted `NOT` as emphasis. Two fixes are possible and one has to be chosen: WP1 puts the quoted error text in a code span, which the lint already exempts — G-25 two lines above quotes `INVALID_INPUT "labels/N must be object"` the same way and passes only because that quotation happens to carry no bare all-caps word; or WP16 exempts double-quoted strings in prose, which loosens the check for every file. The first is the smaller change and keeps the lint's contract as written in `tools/README.md`.

---

## 4. Notes

1. **`results.md` rows without a reason.** S0-4, S0-6b and S0-7 carry `not-run` alone. The other `not-run` rows say why (probe plugin needed, or what the capability check does and does not settle); these three could say "needs the probe plugin loaded in Cowork" or "not attempted" in the row, so the file follows its own rule from line 5.
2. **S0-1's yes condition is narrower than its question.** "A path ending in `probe-plugin` with `dump.sh` listed": a plugin added through Customize is copied to an install location whose last folder may be the plugin name or a version, not `probe-plugin`. The test is that the path exists and lists `dump.sh`. This matters less once fix 1 lands, but the wording is still there.
3. **S0-14's dump lands beside the installed copy.** `dump.sh` appends to `$here/../hook-dump.jsonl`, that is, inside whatever folder the plugin was loaded from. In Cowork that is the installed copy, not `tests/stage0/probe-plugin/`, and the README says only "open `probe-plugin/hook-dump.jsonl`". If that folder is not writable the append fails silently while the deny is still returned, so S0-12 reads yes and S0-14's file is missing — and the README's reason for a missing file ("the hook never ran") then contradicts S0-12. A dump path under the connected folder or `$HOME`, named in the README, removes the ambiguity. A false no here is the safe direction, so this is a note rather than a fix.
4. **The personal-name check is inert on this Mac.** No `~/DelOps/personal-names-index.json` exists, so the lint warned and skipped (C22). `python3 tools/lint_plugin.py --hash-name "<name>"` prints the hash to add; which names go in is the user's decision, and the file lives outside the repo by design. Until it exists, release check 3 does not cover A12 mechanically.
5. **Python 3.11 is not on this Mac.** The tests ran on 3.9.6 and 3.13.14. Release check 2 names 3.9 and 3.11; `uv python install 3.11` would fetch one, which is a download and so the user's call.
6. **The manifest descriptions predate A19.** Both describe "discovery grading against the user's sales method", "demo scripts" and "a progressive SOP" as what the plugin does; A19 (2026-09-19) makes those v2 and puts build-readiness and the AI offerings in v1. A19 also says stage 1 finishes as it is and the re-cut comes after, so this is for the re-cut, not for stage-1 acceptance.
7. **Placeholders and a stray file inside the plugin folder.** `agents/`, `hooks/`, `scripts/`, `skills/`, `shared/` and both `templates/` folders hold a `.gitkeep`; `shared/.gitkeep` is already redundant. `plugins/monday-master-builder/.DS_Store` is on disk. Git ignores the second and keeps the first; an uploaded folder carries both. Neither is in A§2's file list.
8. **Probe leftovers are not ignored.** `probe-plugin/hook-dump.jsonl` and `stage0-probe.docx` exist only while a probe runs, and the README asks the user to delete them; a line in `.gitignore` would make a forgotten one harmless.
9. **Adjacent words, for the user's judgment.** "consultancy" three times in `leak-terms.txt` and `safety.md` (where it names the thing the denylist protects) and "consulting engagement" in both manifest descriptions. Neither is the word the lint refuses, and A12's target is the person, not the trade; the user may still want "the user's" or "the firm's" there.
10. **The user's GitHub handle in two shipped files** (`plugin.json` `repository`, `record-map.md:69`). Placed by the design (A§2, A§7.1) and a GitHub account name rather than a personal name in A12's sense; recorded here so it is a decision and not an oversight. The stage-0 files named it too, as `BUILD-PLAN.md` did for S0-13. Closed 2026-10-13 (D6): the handle is each user's own configuration and was removed from every file; only `plugin.json` keeps the plugin's own repository address, which names the publisher.
11. **Loading the probe plugin in Cowork.** The README offers "add it as a marketplace, or upload the folder". A marketplace add needs a `.claude-plugin/marketplace.json` at the path given, and `probe-plugin/` has only a `plugin.json`; the repo's own marketplace lists the product plugin alone, as A§2 requires. "Upload the folder" is the route that matches what exists. The probe plugin itself passes `validate --strict` (1.1).

---

## 5. Not checked by this run

- `tools/sync_shared.py` and `tools/release.sh` (WP16): not present, by plan; `BUILD-PLAN.md` section 1 lands only the lint and the clean-room scan early, the rest in stage 5.
- `tools/cleanroom_scan.py` against a real quarantine: the learn files are not on this machine, so only its unit tests ran. Its acceptance (release check 8) is checked with WP1's shared files once a quarantine exists.
- The lint's pinned-agreement check on real scripts: reported `not present yet` for both, as designed; the two headings it will read are in place.
- Stage 0 itself: the probes are the user's to run by hand; this run judged the instructions, not the answers.
- Any WP1 acceptance line beyond what the lint and the sweeps touch; `shared/` was read only as the lint's input.
