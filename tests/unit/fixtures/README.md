# WP2 unit fixtures

The hand-built record tree that `tests/unit/test_mmb_common.py` and `tests/unit/test_record.py` run on in stage 2 (BUILD-PLAN WP2, contract C27). WP2 owns it; it is distinct from WP14's seed records. Every value is fictional and neutral: a joinery workshop as the client, roles instead of names, the account `example-account` (id `10000001`), ids counted up from there, and a placeholder firm in the settings. The shapes are those of `plugins/monday-master-builder/shared/record-map.md` as amended by the WP2 decisions (G-numbers). Every version is below `v1.0`. `tools/` beside this file belongs to `test_lint_plugin.py` and is not described here.

## Layout

```
home/                                      MMB_HOME for the tests, as `home init` leaves it
  local/settings.json                      settings/1: firm, default build account, one never-show workspace, archive local
  local/leak-terms.txt                     empty
  local/sandbox-accounts.txt               empty
  cards/ monday-knowledge/ sandbox/ archive/   empty (a .gitkeep each, dropped by the copy)
  clients/larkmoor-joinery/                one client/2 record, bound to the user's own account
    CLIENT.md                              front matter with comments, A11 fields unanswered, strand index of two rows
    log.md                                 log/1, ten entries newest first, record level and per strand, two save entries
    account.json                           account/1; guard_index.lease mirrors the lock; three live objects
    live/live-map.md                       live-map/1, the same three rows
    calls/2026-10-20-discovery.transcript.txt   raw transcript, sha256 in its save entry
    inputs/2026-10-21-timber-orders.txt         raw pasted-text email, sha256 in its save entry
    .work/lock.json                        lock/2, held by 001 at epoch 2, run_id null, three history entries
    .work/history.json                     history/1, the ten entry hashes newest first
    strands/001-job-tracking/              platform, stage shown, v0.1 audited, cleared to build
      STRAND.md
      readiness.md                         assumptions: one structural assumed, one structural accepted, one gap
      solution/blueprint.md                sample_rows planned
      solution/exclusions.md               one row
      solution/build.json                  build/2: approval of r1, one ended run, objects W1, B1, B1.V1
      versions/v0.1/version.md             audited, proof-of-concept, one shown event
      versions/v0.1/blueprint-r1.md        byte copy of blueprint.md; its sha256 is in version.md and the approval
      versions/v0.1/audit.md               ends "cleared to show"
    strands/002-timber-orders/             platform, stage intake, no version, clearance none
      STRAND.md                            an escaped quote in opened_reason
      readiness.md
      solution/exclusions.md               the empty seeded table
crlf/home/clients/larkmoor-joinery/CLIENT.md   CRLF byte copy of the LF CLIENT.md, laid over a copy of home/
plugin/                                    the stand-in plugin root of G31
  .claude-plugin/plugin.json               name and version 0.1.0 only
  templates/record/                        CLIENT.md, log.md, account.json, STRAND.md, readiness.md,
                                           exclusions.md, version.md: fresh values, the keys record.py sets;
                                           build.json and client-gitignore.txt for `init`
  templates/other/SANDBOX.md               the sandbox cover `home init` places, its A11-1 field open
.gitattributes                             home/, crlf/ and plugin/ are checked out byte for byte on every system
```

The templates carry the same front-matter keys, in the same order, as the matching files in the record (strand 002 for `STRAND.md`, `readiness.md` and `exclusions.md`, 001's `v0.1` for `version.md`), with the values a fresh file has; keys `record.py` fills that have no default are `""`. Their names follow WP7's template list and G31's `templates/record/<name>`, so in stage 3 the tests copy the real `templates/record/` instead of this one. There is no lock template: `init` writes the first lock through `mmb_common`'s lease primitives, the one writer of `.work/lock.json` (C82; main-session decision of 2026-10-14, DECISIONS.md, after G02).

## Reference clock and expected results

- Pin `mmb_common`'s clock to `2026-11-05T14:30:00Z`. Local times in the tree equal the UTC stamps. At that clock the heartbeat (`2026-11-05T14:20:00Z`) is 10 minutes old, so the lease is fresh, and the native index (`captured_at` `2026-10-28T09:20:00Z`, budget 14 days) is in date. Every fixture time lies after the date the tree was built, so an unpinned clock gives negative ages.
- `record.py check` on the copy: exit 0, no findings. At the real clock of 2026-10 the held lease's heartbeat lies weeks ahead, so the same check exits 2 with one warning, the clock disagreement of `.work/lock.json` `heartbeat_at` (record.py part 2, DECISIONS.md "Added by part 2").
- The lease: holder 001 "Job tracking" `v0.1`, label `20261105-1405-r2d6`, epoch 2, `run_id` null (so break condition 4 holds as built, G04); the earlier label is `20261028-0915-m3p8`; the bound account id is `10000001`.
- Refused as built: `lease take` for 002 (C92) and for 001 (C93); `lease break` (fresh, C102); `strand close --strand 001` (holds the lease, C74; after a release still refused, v0.1 being unreleased with no close reason, C77); `strand kind --strand 001` (has `v0.1`, C72); `strand pause --strand 001` (holds the lease, G52); `version release` and `version condense-plan` (C166, C171); `freeze --strand 001` (r1 exists, G41).
- Accepted as built: `strand pause`, `kind`, `close` and `summary` on 002; `version mark shown` on 001; `version mark signed-off --strand 001`, which lists exactly one assumption, exits 2 and records nothing without `--go-on` (C162 to C164). The next strand ordinal is `003`.

## Making a variant

Copy, then mutate the copy; no broken tree is stored:

```python
home = Path(shutil.copytree(FIXTURES / "home", Path(tmp) / "mmb home", ignore=shutil.ignore_patterns(".gitkeep", ".DS_Store")))
```

Then `record = home / "clients" / "larkmoor-joinery"` and `MMB_HOME` set to `home`; the space in the folder name serves C06. For the CRLF variant, lay `crlf/` over the copy: `shutil.copytree(FIXTURES / "crlf" / "home", home, dirs_exist_ok=True)`. The plugin root is made the same way: copy `plugin/` to a temporary folder, copy `scripts/` from `plugins/monday-master-builder/` into it, and launch the scripts from there (G31, G36). Never run a script on the tree in place: scripts write `.work/` backups and the mutex, and a folder above the repository may hold a `CLAUDE.md`.

| Clause | Mutation of the copy |
|---|---|
| C13 | `CLIENT.md` `schema: "client/3"` |
| C53 | change one character of any entry in `log.md` |
| C54 | `version.md` `revision: "2"`, then `freeze --strand 001` |
| C95, C153 | clock to `15:19`, `15:20`, `15:21` on 2026-11-05 (59, 60, 61 minutes) |
| C105, C107, C119, C121 | lock `run_id: "run-2026-11-05-1"` and that run in 001's `build.json` `runs[]`, `running`, or `interrupted` with or without `reconcile` |
| C125, C126, C131 | one side only: `monday_account_id`; `account_id_at_bind`; either lease mirror |
| C128 | add `strands/003-extra/`, or drop an index row |
| C129, C130 | a `001:B9` row in the live map; drop a row on one side |
| C81, C91, C132, C133 | `strand kind --strand 002 --kind non-platform`, then plant `solution/blueprint.md`, or add `solution/scope.md` with or without the fixed sentence |
| C134 | 001 `readiness.md` `clearance: "ready"` |
| C136 | delete 001's `solution/exclusions.md` |
| C142 | `client` and `client-account` in `CLIENT.md` and `account.json` |
| C143 | a save entry with `fixture: no`, written through `record.py log` |
| C144 | `sandbox` and `none` in both files; `sandbox-accounts.txt` stays empty |
| C148 | `captured_at` more than 14 days before the clock |
| C149 | a foreign id in `build_targets_by_strand["001"].workspace_ids` |
| C150, C151 | change one byte of the transcript; of `blueprint-r1.md` |
| C152, C155 | a body line in `STRAND.md` holding a drive-letter path, another a POSIX home path |

## Clauses each part serves

| Part | Clauses |
|---|---|
| the whole tree, copied | C06, C07, C14, C16, C17, C20, C21, C23, C27, C114 to C124, C146 |
| `CLIENT.md` | C11 to C13, C45 to C47, C115, C125, C128, C131, C141, C145, C147 |
| `crlf/` copy | C08, C09 (a guarded rewrite writes it back with LF), C11 |
| `log.md`, `.work/history.json` | C48 to C53; C73 and C137 after a roll in the copy |
| `.work/lock.json` and its two mirrors | C74, C82 to C113, C118, C131, C153, C166, C171 |
| `account.json`, `live/live-map.md` | C86, C125, C126, C129, C130, C140, C148, C149 |
| `calls/`, `inputs/` | C10, C55 to C62, C143, C150 |
| strand 001 | C54, C72, C76, C77, C116, C117, C127, C134 to C136, C142, C151, C159 to C170, C181 |
| strand 002 | C63, C70 to C73, C75, C78 to C81, C91, C120, C132, C133 |
| `home/local/` | C16, C144, the settings-shape warning (G34) |
| `plugin/` | C18, C24, C64 to C69, C158, C159, and every other subcommand, which runs from this root |

Not served here: the code inspections (C01 to C05, C15, C19, C22, C25, C26); the Windows runs. `init` and `home init` (C28 to C44) run in `test_record_part2.py` against the stand-in templates above and an empty temporary home; stage 3 accepts them again with WP7's templates.
