# The write path, command by command

Internal working instructions for account-build. Every command runs as `[python] ${CLAUDE_PLUGIN_ROOT}/scripts/<script> --record <client folder> …` (`python3` on macOS, `py -3` on Windows, or the exact version the environment names) and prints one JSON object. Files handed to a script live inside the record, under `.work/inputs/`, written as UTF-8 with LF line endings.

## What the session holds

- **The fence:** the lease epoch and session label from `record.py lease take`, and the run id from `ledger.py run start`. Every fenced command takes `--lease-epoch <epoch> --session-label <label> --run-id <run id>`; `run start` takes the first two.
- **The ledger's sha:** `approval`, `run start`, `run heartbeat`, `run end`, `intent`, `record`, `verify`, `depart`, `ui-step` and `irreversible-yes` take `--expect-sha <sha256 of solution/build.json>`, the value the last ledger write left. A new strand gets a skeleton `build.json` from the record templates, so even the first `approval` takes the file's real sha, as `ledger.py check --strand <id>` reports it; `none` is only for a strand with no `build.json` at all. Read it fresh before each command; a stale one is refused, which is the point.
- **The log:** every `log` entry a ledger command prints is written by the session with `record.py log --strand <id or -> --type <type> --version <v or -> --key <key> --body-file <file of its lines>`, as soon as it is printed. The ledger never writes `log.md` itself.

## One element

```
ledger.py intent --strand 001 --key B1.C3 --operation create --parent-key B1 [fence] [sha]
leak_lint.py payload --strand 001 --kind column --file .work/inputs/payload-B1.C3.json
  (the monday call)
ledger.py record --strand 001 --key B1.C3 --id <id the call returned> [fence] [sha]
  (the read)
ledger.py verify --strand 001 --key B1.C3 --result match --read .work/inputs/read-B1.C3.json [fence] [sha]
```

- `intent` flags as needed: `--operation update` for a change to a row already built; `--parent-key` (the board for a column, group, view, form or item batch; the folder for a board or dashboard; the workspace for a folder); `--sample-data` on an item batch; `--notifies <the bound user's id>` on an automation that notifies the user (the approval table writes `user`, the intent wants the id), and none on one that notifies nobody; `--assumption-ref AT1` on a row that rests on an assumed term; `--ref board:<id>` for every board a write names outside its parent (a connect column's target, a dashboard's boards).
- **The payload** is the call's arguments as JSON, kind the row's type. Exit 0 or 2 goes on, warnings shown to the user; exit 1 or 3 stops that write until the text changes. Never send a payload the lint has not seen.
- `record` takes `--id`; an item batch takes `--item-id` once per row, in the order the call returned them. A widget keeps the id from its create response.
- **The read file** is `{"read": "<the query or tool and its fields>", "object": {…}}`. The object always carries `id` and `workspace_id`, plus the row's identity fields below, with the values the read returned.
- `verify --result` is `match` when the read shows what the frozen revision planned, `mismatch` when it does not (see "When something goes wrong"), `not-checkable` when no read exists (widgets) with `--note` saying why, or `needs-user` when only the user can tell.

## Identity fields per kind

| Kind | Fields the read object carries |
|---|---|
| workspace | `name`, `kind` |
| folder | `name`, `workspace_id` |
| board | `name`, `type`, `state`, `workspace_id`, `board_folder_id` |
| group | `title`, `color`, `position` |
| column | `id`, `title`, `type`, `settings` (label ids as the read returned them; the ledger's id checks pass over `labels`) |
| view, form | `name`, `type`, `settings` |
| item batch | `item_ids` |
| automation | `active` and `updated_at`, written from `list_automations`' `is_active` and `updated_at` |
| dashboard | `name`, `workspace_id`, `kind` |
| widget | none: `not-checkable` (G-11) |

## The reads that worked in demos 1 and 2

- **Boards, columns, groups:** raw `boards(ids) { id name state type board_kind workspace_id board_folder_id groups { id title color position } columns { id title type settings } }`.
- **Item batches:** raw `boards(ids) { items_count items_page(limit: 100) { items { id } } }`, every id of the batch present; the read object carries the board as `id`, with `items_count` and `item_ids`. For a linked board also `column_values(ids) { … on BoardRelationValue { linked_item_ids } }` and, for a mirror, `… on MirrorValue { display_value }` (G-31).
- **Formulas:** `… on FormulaValue { display_value }` on the rows, once they exist; the planted case shows whether it evaluates.
- **Views:** `get_board_info` with `filters.views.only`, which returns each view's stored filter, sort direction and hidden columns.
- **Forms:** the token is in raw `views(ids) { view_specific_data_str }` (G-48); `get_form` with it shows each question's visibility and the login setting. Keep the token out of the record.
- **Automations:** `list_automations` on the board: the trigger block and its column, label, offset, time and timezone; the action block and its target; the receiver; the message's fields.
- **Dashboards:** the search tool, type dashboards, scoped to the workspace; the read object carries `id`, `workspace_id`, `name` and `kind`.

## The monday calls

- **Folders:** `create_folder` with the workspace id.
- **Boards:** raw `create_board(board_name, board_kind: public, workspace_id, folder_id, description, empty: true)`. The tool drops `folderId` (demo 1); a board that lands outside its folder is moved with `move_object` as an `update` of its row.
- **Default group:** raw `update_group(board_id, group_id: "topics", group_attribute: title, new_value: "<first group>")`; further groups with `create_group` or raw `create_group(… relative_to, position_relative_method: after_at)`.
- **Columns:** `create_column` with `columnSettings` built from `get_column_type_info` (schema), never copied from a read. Status labels `{id, label, color, index}`, one with `is_done: true`; dropdown labels `{id, label}` (G-25); connect columns `{boardIds, allowMultipleItems, allowCreateReflectionColumn: true}`; mirrors `{relation_column: {<connect column id>: true}, displayed_linked_columns: [{board_id, column_ids}], sumType | calcType}`, a date mirror's `calcType` being `earliest` or `latest`; formulas from the formula column's schema in the same tool. Changing a column's settings needs its current `revision` from `get_board_info`, and a connect column's `boardIds` are always resent (G-29).
- **Rows:** `create_items`, up to 20 per call, each entry succeeding or failing on its own (G-36); dates as `{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}` in UTC; connect values as `{"item_ids": [ … ]}`.
- **Views:** `create_view_table` with `filter {operator, rules}` and `sort`, its direction in capitals (`ASC`, `DESC`; a lower-case `desc` was stored ascending in demo 2); date rules take `["THIS_WEEK"]`, `["DAYS", 2]` with `within_the_next`, status rules take label ids (`get_column_type_info` guidelines).
- **Forms:** `create_view` type FORM; then `form_questions_editor` update `{type, visible: false}` per hidden question, `update_form` `updateFormHeader` for the title and description, and `updateFeatures` with `requireLogin {enabled: true, redirectToLogin: true}`.
- **Automations:** `create_automation` with a prompt in this shape, then `list_automations`:

```
Trigger:
  When a date arrives
  Details:
    Date column: <column title>
    Offset: 1 day before
    Time of day: 8:00 (hour 8, minute 0)

Actions:
  - Notify someone:
      Recipient: <the user's name>
      Message: {{item name}} on batch {{<column>}} …
```

  For a trigger that is not a date, say "monday's own notification, the Notify someone action" and name each column the message reads by its title and type ("Crew, the dropdown column named Crew"): in demo 2 the tool first chose another product's notify block and stored nothing, then mapped a dropdown placeholder to a status column. The other actions resolve from plain names, with no recipient:

```
Trigger:
  When a status changes to something
  Details:
    Status column: Stage
    Label: Installed

Actions:
  - Move the item to a group: Installed
```

  `Change a status: <column>, <label>`, `Set a date to today: <date column>` and `Move the item to a group: <group>` all built first time. Two automations on the same trigger run in an order the read does not show.

- **Dashboards and widgets:** `create_dashboard {name, workspace_id, board_ids, board_folder_id, kind}`; `create_widget` per widget, settings from `all_widgets_schema` (G-63), keyed by board id as the schema says.

## When something goes wrong

- A call that may have written something (a timeout, a dropped connection) leaves the row `attempting`. Do not call again: read the board, and `record` what exists, or `depart` the row with the reason.
- A read that does not match the plan is a `mismatch`. When monday ignored or reshaped a value the plan states (a sort direction, a filter's spelling, a setting's case), resend it once in another documented form: `intent --operation update --retry` (a plain `update` is refused from `mismatch`), the payload check, the call, `record`, a read, `verify`. If it still differs, `depart` the row with what monday stored, log it, and go on. Any other mismatch stops the build: show the user both.
- An automation that comes out wrong is not patched with a second one: `depart --decision ui-step` mints the next free U number and its version, and the user fixes the field in monday.
- `depart --attempt` takes the call form that was tried (`flat`, `wrapped`, `tool` or `raw`), not a description. `ledger.py ui-step` takes no fence flags and needs `--target-version`.
- An element the plan did not foresee, such as a column monday adds by itself, is recorded under its planned key when the plan has one, and otherwise reported to the user and left for the next revision.
