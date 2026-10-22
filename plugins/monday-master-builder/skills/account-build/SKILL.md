---
name: account-build
description: Builds an approved blueprint revision into monday for one strand of a client record, element by element through the ledger and the leak lint, and reads every element back. Run it only after the user has said yes to the approval card that solution-blueprint showed, as /account-build with the strand and version, for example 001/v0.1.
disable-model-invocation: true
---

# Account build

Internal working instructions. Every write follows one path: `ledger.py intent`, `leak_lint.py payload`, the monday call, `ledger.py record`, a read, `ledger.py verify`. The ledger is what makes a build resumable and auditable, so nothing is written to monday outside it. Lean version written from demo 1 and revised from demo 2 (A31); the exact command forms and read shapes are in [write-path.md](references/write-path.md).

A build runs the plugin's three scripts a few hundred times. The session needs them allowed before the first command, or the run stops half bound.

## Stop before writing when

- The strand is `non-platform`, or its version has no approved revision: the user's yes to the card comes first.
- The home has no `local/settings.json` with the firm name: `leak_lint.py payload` cannot run without it, and a payload it has not checked is never sent.
- The connector's account or user is not the one the record is bound to: show both and ask the user to reconnect.
- Another strand holds the record's build lease: say which, and wait.
- A connector tool the plan needs is missing from the session: the change check stops the build.
- The frozen revision lists an element kind this skill does not say how to build: stop and ask, or build it as a probe only on the user's word, logging what monday made.

## Before the first write

1. Read the frozen revision, `versions/<v>/blueprint-r<N>.md`, and build only what its element-key table lists. Where its sections disagree with each other (a view's columns in section 12 and in section 16's build checks), follow section 16 and say so in the build notes. Hold the user's words of approval.
2. **Bind** the record to the account once: read `me { id kind } account { id slug name tier products { id kind } } version { kind value }`, save it as `.work/inputs/bind.json` and run `ledger.py bind --binding .work/inputs/bind.json`; then write the mirror it prints into `CLIENT.md` through `record.py guard`, with `monday_tier` set to the tier the read returned and `monday_tier_source` to the bind, since the mirror leaves them out.
3. **Approve:** `ledger.py approval --strand <id> --version <v> --revision <N> --sha256 <frozen sha> --words "<the user's words>" --session "<date> build session"`, with `--irreversible` for every workspace and folder row (a referenced one too) and `--referenced` for every row that already exists, such as a named test workspace. Set `version.md` `state` and `STRAND.md` `version_state` to `approved`.
4. **Change check:** compare the session's connector tools with the roster in `shared/monday-gotchas.md` and the ring with `version { kind value }`, save the result as `.work/inputs/change-check.json` and run `ledger.py change-check --from …`. The file holds `ring`, `versions_seen` (a list), `release_notes_since` (`"<date> (read)"` or `"not-read"`), `roster_diff {added, removed, renamed}` (three lists), `schema_diff` (a list), `result` (`no change affecting this build` or `change affecting this build`) and `approved_by_user` (null, or the log reference of the user's yes). A removed tool the plan needs stops the build for the user.
5. **Development only (A31):** when the build goes into the test workspace the user named, run `tools/dev_test_workspace.py --record <folder> --strand <id> --workspace <id>` from the plugin repository.
6. **Lease and run:** `record.py lease take build --strand <id>` returns the epoch and a session label; `ledger.py run start --strand <id> --another-build-running no --account-check match` returns the run id. Hold all three in the session for every write; never read them back from the lock. Set `version.md` `state` and `STRAND.md` `version_state` to `building`, and `STRAND.md` `stage` to `building`; the audit moves the stage on.
7. **The referenced workspace:** `verify` is fenced, so `W1` is verified only now, with a read that shows its id, name and kind, and `workspace_id` equal to its own id. It takes no `intent` and no `record`.

## The build, in this order

Build in phases and batch the bookkeeping: run `intent` and the payload check for every element of a phase, make the calls, then `record` and `verify` each one. A refusal is read and fixed, never retried blindly.

1. **Folder and boards.** Create a board with raw `create_board(… workspace_id, folder_id, empty: true)`: the `create_board` tool drops the folder. Rename each new board's default group to the first planned group: its row is an `intent --operation create` with the `update_group` payload, recorded under the id `topics`.
2. **Columns.** Status and dropdown labels as objects, with ids; label ids may stay the numbers monday returns, 0 included. A date that needs a time gets `show_time_by_default`. Connect columns are created two-way (A32): `allowCreateReflectionColumn: true`, which adds the other board's connect column, named "link to <board>". Run that column's `intent` before the call that creates it, then rename it to its planned name with a title-only change and record it under its own key. A column already built one way becomes two-way by `update_column` with the same setting and `boardIds` resent. A formula takes its settings from `get_column_type_info` and is verified on its `display_value` once the rows exist (phase 4).
3. **Groups.**
4. **Sample rows,** by item batch, at most 20 per `create_items` call. Create the rows a connect column points at first, then the rows that link to them with `item_ids`, each linked batch's `intent` carrying `--ref board:<the target board's id>`. Date-column times are UTC.
5. **Mirrors,** once both boards and their connect columns exist. A date mirror's earliest or latest is `calcType` (`earliest`, `latest`), named in `get_column_type_info`'s mirror schema. Its `display_value` still lists every linked date (G-31); a formula over it sees the aggregate, so check the formula, not the mirror's text.
6. **Views and forms.** Table views with their filters and sorts, sort directions in capitals (`ASC`, `DESC`): a lower-case `desc` is stored ascending. A view that shows only some columns stores the rest as hidden (G-87). Read them back with `get_board_info` views and check each stored sort direction and hidden column. A form view starts with every column as a question and is open to anyone with the link: hide the questions the blueprint leaves out, set its title, and turn on "require login" before anyone sees it.
7. **Automations,** after everything they read. `create_automation` with the trigger, the action, and for a notification monday's own "Notify someone" action named in the prompt, with the user by name: left to choose, the tool can pick another product's notify block and store nothing. A date trigger names a time of day, which monday stores in the account's timezone. Change a status, set a date to today and move an item to a group resolve from plain names. Read back with `list_automations` and check the trigger column and label, the offset and time, the action block and its target (column, label, date value or group), the receiver, and every field the message reads: a placeholder can be mapped to the wrong column. The stored title is the raw prompt (G-66). A wrong automation is never patched with a second one, since nothing deletes one from outside: verify it `mismatch` and `depart` it with decision `ui-step`, so the user fixes that one field in monday.
8. **Dashboard and widgets.** `create_dashboard` with the board set and the folder (the set cannot change later, G-90); widgets from `all_widgets_schema`'s properties only (G-63). Verify the dashboard through the search tool with its `id`, `workspace_id`, `name` and `kind`; search does not show the folder, so its place rests on the create call. Widgets cannot be read back (G-11) and are verified `not-checkable` with a note.
9. **UI steps:** `ledger.py ui-step` for each, owner the user, with `--target-version` and without the fence.

## After the last write

1. `ledger.py run end --strand <id> --calls-used <n>` writes the live map and releases the lease. Write each `log` entry a ledger command prints through `record.py log` as soon as it is printed.
2. A departed element that is still live in monday, such as an automation, does not reach the live map: name it in `version.md` `## Build` and in the switch-off UI step, so the audit and the user still see it.
3. Set `version.md` `state` to `built` and write under `## Build` what was built, what was verified, what was not checkable and what departed; set `STRAND.md` `version_state` to `built`.
4. Run `record.py check` and `ledger.py check --strand <id>`; both should be clean.
5. Tell the user: a link to each board and the dashboard, what each view is for, which automations will notify them and when, the UI steps left to do, and anything that did not go as planned. The audit (`solution-audit`) is the next step before the demo is shown.
