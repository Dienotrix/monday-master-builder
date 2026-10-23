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

- `intent` flags as needed: `--operation update` for a change to a row already built; `--parent-key` (the board for a column, group, view, form or item batch; the folder for a board or dashboard; the workspace for a folder); `--sample-data` on an item batch; `--notifies user` on an automation that notifies the user (the ledger resolves it to the bound user), and none on one that notifies nobody; `--assumption-ref AT1` on a row that rests on an assumed term; `--ref board:<id>` for every board a write names outside its parent (a connect column's target, a dashboard's boards).
- **The payload** is the call's arguments as JSON fields, kind the row's type: for a raw call too, the arguments, never the GraphQL text, whose ids the lint reads as text. It carries nothing that is not sent (no note of your own). Exit 0 or 2 goes on, warnings shown to the user; exit 1 or 3 stops that write until the text changes. Never send a payload the lint has not seen. A phone value is digits only, and the lint reads any run of eight or more digits as an id, so sample rows carry no phone numbers.
- `record` takes `--id`; an item batch takes `--item-id` once per row, in the order the call returned them. A widget keeps the id from its create response.
- **The read file** is `{"read": "<the query or tool and its fields>", "object": {…}}`. The object always carries `id` and `workspace_id`, plus the row's identity fields below, with the values the read returned.
- `verify --result` is `match` when the read shows what the frozen revision planned, `mismatch` when it does not (see "When something goes wrong"), `not-checkable` when no read exists (widgets) with `--note` saying why, or `needs-user` when only the user can tell.

## Identity fields per kind

| Kind | Fields the read object carries |
|---|---|
| workspace | `name`, `kind` |
| folder | `name`, `workspace_id` |
| board | `name`, `type`, `state`, `workspace_id`, `board_folder_id`; a native install also `created_from_board_id` and `items_count` |
| group | `title`, `color`, `position` |
| column | `id`, `title`, `type`, `settings` (label ids as the read returned them; the ledger's id checks pass over `labels`) |
| view, form | `name`, `type`, `settings` |
| item batch | `item_ids` |
| automation | `active` and `updated_at`, written from `list_automations`' `is_active` and `updated_at` |
| dashboard | `name`, `workspace_id`, `kind` |
| widget | none: `not-checkable` (G-11) |
| ai_column | `id` (the column id), `ai_kind`, `source_column_id`, `target_column_id`, `prompt` (the stored instructions or `aiQuery`, ids as stored) and `recipes` (each `{id, trigger}`) |
| workflow | `name`, `state` (`inactive` while it is an unpublished draft, since the object read says `active` either way, G-135), `workspace_id`, and `validation`: `no issues` when `validate_workflow` returned `issues: []`, else the issues |
| agent | `plan`, `identity`, `state`, `version_id`, `triggers` (each `{name}`), `knowledge` (each `{resource_id, scope_type, permission_type}`), `jobs` (each `{name, instructions, triggers}`); never `skills` |
| publication, activation | `state` (and for a publication `published`) as read |

## The reads that worked in demos 1 and 2

- **Boards, columns, groups:** raw `boards(ids) { id name state type board_kind workspace_id board_folder_id groups { id title color position } columns { id title type settings } }`.
- **Item batches:** raw `boards(ids) { items_count items_page(limit: 100) { items { id } } }`, every id of the batch present; the read object carries the board as `id`, with `items_count` and `item_ids`. For a linked board also `column_values(ids) { … on BoardRelationValue { linked_item_ids } }` and, for a mirror, `… on MirrorValue { display_value }` (G-31).
- **Formulas:** `… on FormulaValue { display_value }` on the rows, once they exist; the planted case shows whether it evaluates.
- **Views:** `get_board_info` with `filters.views.only`, which returns each view's stored filter, sort direction and hidden columns.
- **Forms:** the token is in raw `views(ids) { view_specific_data_str }` (G-48); `get_form` with it shows each question's visibility and the login setting. Keep the token out of the record.
- **Automations:** `list_automations` on the board: the trigger block and its column, label, offset, time and timezone; the action block and its target; the receiver; the message's fields.
- **Dashboards:** the search tool, type dashboards, scoped to the workspace; the read object carries `id`, `workspace_id`, `name` and `kind`.
- **AI columns (G-141):** raw `board_automations(board_ids: [<board>], limit: 1) { legacy_automations }`, keeping the recipes whose `config` names the column as `targetColumnId`; the classification type (`aiClassificationType.value`: `summarize text`, `categorize`, …, or none with an `aiQuery` for a custom prompt), `sourceColumnId`, and `additionalInstructions` or `aiQuery` as stored. The column's `settings` carry nothing of the AI. A minute later, read the column on two or three rows; say in the verify note whether they filled.
- **Agents:** `manage_agent get` (plan, identity, state, version_id), `manage_agent_jobs list`, `manage_agent_knowledge list`, `manage_agent_triggers list`, merged into one read object. Never record what an `update` answered (G-110).
- **Workflows:** `validate_workflow` with the draft id; `invoke_workflow_expert` asked "Do not change anything: list each step's block and every configured field"; raw `objects(ids) { id name state folder_id workspace_id }`. For the run once: `get_workflow_run_once_status` until `isTerminal`, the row it ran on, and raw `notifications(limit: 3) { text created_at }` for the message the user received (G-134).

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

  A condition goes in its own block between the trigger and the actions, naming the column, the comparison and the label:

```
Conditions:
  - Only if: status column <column> is <label>
```

  In demo 3 a condition written inline ("Only if the status column Stage is Quoted") was stored as "is not" (`shouldCheckIfStatusIsNot: true`, G-161). Read that flag on every status condition; a condition stored the wrong way is a `mismatch` and departs to a UI step.

- **Switching an automation off:** `manage_automations` with `action: deactivate` and `workflowId`, the id `list_automations` gives (G-65); `activate` turns it on again. Read it back with `list_automations` on its board: `is_active` false, the definition unchanged and `updated_at` moved. A row in the older read's `legacyAutomations` cannot be changed this way, and the build makes none.
- **Dashboards and widgets:** `create_dashboard {name, workspace_id, board_ids, board_folder_id, kind}`; `create_widget` per widget, settings from `all_widgets_schema` (G-63), keyed by board id as the schema says.
- **AI columns (G-140 to G-143):** `create_column` of the planned type (long text for a summary or custom prompt; status or dropdown with the planned labels for a category), then raw, through `all_api_write`, one of:
  - `configure_summarize_ai_column(board_id, column_id, source_type: column, source_column_id, additional_instructions, extra_settings: {run_backfill})`; `source_type` may also be `thread` or `item_name`;
  - `configure_categorize_ai_column(…the same…)`, the target a status or dropdown column;
  - `configure_open_block_ai_column(board_id, column_id, ai_query, extra_settings: {run_backfill})`, the prompt with each `{pulse.<column name>}` replaced by the monday id of that board's ledger row of that name, and `{pulse.name}` kept.

  Each answers only the column id, which the mutation must select (`{ column_id }`): `record --id <column id>`. The payload is these arguments. `run_backfill` is true unless the blueprint says the existing rows keep their own values. The activity timeline is not a source (G-144).
- **Workflows (G-130 to G-135):** `create_workflow(workspaceId, folderId, title, description)` answers `workflowObjectId` and `workflowDraftId`; record the object id and keep the draft id in the session and the verify note. Author it with `invoke_workflow_expert` on the draft in small requests, one or two steps each, every board, column, label and user id given, and the user as the only recipient by id. Each request is a payload of kind `workflow` (`{"workflowObjectId", "workflowDraftId", "prompt"}`), checked before it is sent; the lint passes the bound user's id and the ids of this strand's own rows there (A43), and blocks any other id, so name nothing outside the build. Never give the user by name. After every expert call, whatever it answered, run `validate_workflow`; never resend a request that failed or timed out, since its changes may have landed. Give a date trigger's time and zone and read them back in the expert's description (the expert defaulted to 09:00 UTC). No wait or approval step (G-132). When `issues: []` and the description matches section 13: `get_run_once_trigger_entities`, then `run_workflow_once` with the draft id on the sample row the blueprint names, its `value` passed unaltered, then `get_workflow_run_once_status` with the `automationId` until `isTerminal`. Then the publication: `intent --key WF<n>.PUB --operation publish`, `publish_workflow(workflowObjectId, workflowDraftId, shouldActivate)` as the row's name says, `record`, and `verify --result needs-user` with a note naming the run once as the check.
- **Agents (G-110 to G-116):** `manage_agent create_blank` with `name`, `role`, `role_description` (the agent starts INACTIVE): `record --id`. Then `update` with `identity` set to the `### Prompt AG<n>` block, `get`, and if the identity reads empty or different, `update` again with `plan` and `get` again; then `deactivate` if `get` shows ACTIVE (G-110, G-111). Then each job: `manage_agent_jobs create` with `name`, `instructions` (the `### Prompt AG<n>.J<m>` block), `enabled: true` and its `triggers` (`block_reference_id` from `agent_catalog list_triggers`; "Every time period" takes `schedulerConfig {type, occurrences, hour, minute, timezone, days}`); then `manage_agent_knowledge add` per planned board or doc, READ or READ_WRITE. No tools and no skills. The payload of `AG<n>` is all of these arguments in one file, checked once before the first call. The activation: `intent --key AG<n>.ACT --operation activate`, `manage_agent activate`, `record`, `get`, `verify` with the state read.

## When something goes wrong

- A call that may have written something (a timeout, a dropped connection) leaves the row `attempting`. Do not call again: read the board, and `record` what exists, or `depart` the row with the reason. A call the session refused (a permission, a lint stop after `intent`) leaves it `attempting` too, though nothing reached monday. To call again: read the workspace (folders, boards, docs) and the board's automations, write a `live-inventory/1` file as the record map gives it, with a `read_at` stamped after those reads, run `ledger.py reconcile --strand <id> --inventory <file>`, which classes the row `retry`, then `intent --retry` and the call. Objects the inventory lists that no row holds (another demo's) are left untouched. Write every time in the inventory as the read gave it, fractional seconds included: a time cut short reads as a change. A server error (500) that made nothing gets the same reconcile and one retry per changed form, at most two; then the row departs with the error.
- A read that does not match the plan is a `mismatch`. When monday ignored or reshaped a value the plan states (a sort direction, a filter's spelling, a setting's case), resend it once in another documented form: `intent --operation update --retry` (a plain `update` is refused from `mismatch`), the payload check, the call, `record`, a read, `verify`. If it still differs, `depart` the row with what monday stored, log it, and go on. Any other mismatch stops the build: show the user both.
- An automation that comes out wrong is not patched with a second one: `depart --decision ui-step` mints the next free U number and its version, and the user fixes the field in monday.
- `depart --attempt` takes the call form that was tried (`flat`, `wrapped`, `tool` or `raw`), not a description. `ledger.py ui-step` takes no fence flags and needs `--target-version`.
- An element the plan did not foresee, such as a column monday adds by itself, is recorded under its planned key when the plan has one, and otherwise reported to the user and left for the next revision.
