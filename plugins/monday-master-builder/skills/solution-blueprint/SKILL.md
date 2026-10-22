---
name: solution-blueprint
description: Designs the monday proof of concept for one strand of a client record. Reads the strand's readiness check, writes solution/blueprint.md with its sixteen sections and the element-key table, checks it with the leak lint, freezes it and puts one approval card to the user. Use when the user asks to design, plan or blueprint a build for a client, or right after a readiness check clears a strand to build. Builds nothing in monday; account-build does that after the user's yes.
---

# Solution blueprint

Internal working instructions. The blueprint is the plan the build follows element by element, and the approval card is the one thing the user says yes to. Lean version written from demo 1 and revised from demo 2 (A31); the full skill follows ARCHITECTURE A§3.4 and BUILD-PLAN WP9.

## Before anything

- Work inside the client's folder. Read `CLIENT.md`, the strand's `STRAND.md` and `readiness.md`, the strand's `solution/exclusions.md`, `live/live-map.md` if it exists, and the call or document summaries the readiness check cites. Where the record holds no summary, read the transcript or document itself and restate it in new words. Read no other strand's blueprint or ledger.
- A `non-platform` strand has no blueprint: say so and point at its `scope.md`.
- The readiness `clearance` must be `cleared to build` or `cleared to build, generic`. On `not yet` or `none`, stop, show the questions from `readiness.md`, and go on only if the user overrides with a reason (record it in `STRAND.md` as `override`).
- Compare what the readiness check says must stay out ("stays out of everything that leaves the room", a matter the client asked to keep private) with `exclusions.md`. The lint enforces only what `exclusions.md` lists, so if a line is missing there, ask the user once to add it, or add it with their yes, before the first lint run.
- Run the scripts with the plugin's Python: `python3` on macOS, `py -3` on Windows, or the exact version the environment names, as in `[python] ${CLAUDE_PLUGIN_ROOT}/scripts/record.py --record <client folder> <command>`. The scripts find the home from `MMB_HOME`, else the default home; the lint reads the home's `clients-index.json` and `local/settings.json`. Every script prints one JSON object; exit 1 is a refusal to read and fix, exit 3 means it could not run, and neither is ever a pass. The scripts' own `--help` is thin; the command forms here and in the record map are the reference.
- Stage any file you write through the guard in the record's `.work/staging/`, and delete that folder after the last guarded write.

## Where it will be built

- A prospect's proof of concept goes into the user's own account (A21), one new workspace per product, named for the client, unless it continues the client's earlier workspaces.
- While the plugin is developed (A31), every build goes into the test workspace the user named, one folder per demo, named as the workspace would be: `<name> – Ops`, where the name is the workspace name the readiness check gives, or else `CLIENT.md`'s `name`. Plan that workspace as row `W1` and the folder as `F1`. `W1` already exists and is never written: say so in section 16's build checks ("W1 is referenced"); account-build approves it as referenced, and the folder is the first irreversible step.
- In sections 1 to 15, describe the test workspace as a closed workspace set aside for demonstrations, not by its name and not as a "test workspace": its name sits in another demo's record, so the cross-client wall blocks it.
- CRM and Service entities live on monday's native boards, found in a workspace of that product, never imitated on an ordinary board (A5). In a Work Management workspace there are no native CRM or Service boards: plan the demo in another product's test workspace, or ask the user for one.

## Design rules

Work from the readiness check's goals, pains, entities and leanings. Every pain gets an element that answers it, or a plain "none" with the reason.

1. **One board per thing that moves on its own.** A thing whose rows have their own dates, owners or statuses gets its own rows. Where children move independently of a parent (an analysis inside a batch, a permit on a job), put them on their own board linked to the parent, not in subitems: the ledger has no element key for a subitems board's columns yet. When the client does not want a second board to open, keep the linked board and show its values on the parent through mirrors; record that as a fork in the client's terms.
2. **Connect columns are two-way** (A32). Plan the connect column on each board as its own element; one-way only when the user says so, with the reason in section 11.
3. **Roll-ups are mirrors.** A mirror shows the linked rows' values; for dates it can show the earliest or latest (`calcType`). Mirrors cannot be filtered, so filter a view on the source board's own column where you can. Where a plain copy on the parent is unavoidable, say who or what keeps it equal to the mirror, as an assumed term.
4. **Formulas show a value and nothing else.** They cannot be filtered (G-33) and cannot trigger an automation. A formula over number mirrors is proved (G-32); one over a date mirror's earliest or latest is not, so list it in section 16's build checks with its fallback, such as dropping it and showing the two mirrors side by side.
5. **Checks across rows.** monday has no native rule that compares one row with another (two installs on the same crew at the same time) or follows two links (an install after its job's permit ends). Choose one answer and say which: a view sorted so the clash sits on neighbouring rows, with a flag a person sets; a formula over mirrors on the parent; or a workflow or AI step deferred to a later version. The requirement trace then reads "partly" with the reason, never "fixes" for something a person sets by hand.
6. **Status columns carry the lifecycle,** with one label marked done. Groups split what is open from what is finished, unless the client asked for a grouping of their own (weeks, regions): that comes first, with one finished group after it, and section 15 says who adds the next group, as a UI step or an assumed term. A new board's default group becomes the first planned group. The default Name column is not an element: it keeps its name and takes no key.
7. **Views:** only table, form, dashboard and app views can be created; plan kanban, calendar, Gantt and timeline views as UI steps for the user. A table view takes one filter operator across its rules, so a view cannot say "this date or that date, and not done"; pick the one rule that matters and sort by the other.
8. **Forms** ask only what the person filling them in knows, and require a monday login.
9. **Automations** notify the user only, with the item's name and the field that matters in the message. A date trigger names a time of day; a change trigger notifies when the change happens. Each automation's trigger, condition and action is an assumed term to confirm with the client.
10. **People.** People columns assign only the user, and no one else is notified, until the user's list of test people arrives. Until then, plan a person the client names as a dropdown (Crew A, Crew B) or leave the people column empty, and say which in section 14.
11. **Dashboards visualise the data, charts first** (A35). Plan one chart for each question the client asks of the work: how many are at each stage (a pie or column chart by status), who carries what (a column chart of items per person), what is due when (a column chart by week from a date column, or a calendar), and how the work splits across groups or boards (a stacked column chart). Number and battery widgets carry only the headline totals; a dashboard over two or three boards has six to eight widgets, and the sample rows give every chart shape. The widget kinds are chart (pie, donut, column, bar, line, area, bubbles and stacked forms), number, battery, calendar, Gantt and list. A chart groups its X axis by status, group, person, board, name or date, not by a dropdown, so a per-person chart needs a people column; until the user's list of test people arrives it shows the user alone, and the card says so. A number widget cannot be limited to a group; chart a status or a group instead.
12. **Sample data** (A28) makes the demo look real: dozens of rows where dashboards and roll-ups need numbers, a handful where a board only has to read well. Invented names and figures in the client's industry, shaped by the call but never the client's real customers, jobs or people, even where the readiness check allows them; the card says so. Nothing from `exclusions.md`. Dates around the week of the build, so views show a live week; dated group names and sample dates freeze with the revision, so a build that slips past the named weeks needs a new revision, and section 16 says so. No open row is already past its own deadline, unless one is meant to show an alert. Nothing that would read as a result, a price or a real person's name. Plant one case for each check the readiness clearance asks to be shown (a planted overlap). Item batches hold at most 20 rows each.
13. **AI and workflow opportunities** in the readiness check are deferred unless it marks one for this version: a deferred one is named in section 1's deferred items. "Round 2" there means the AI layer, built after the first showing unless the user sets another cadence (A27). A planned one needs its element kind (workflow, AI column, agent), a probe first, and, for an account-level object, the user's own yes.
14. Nothing names the user's firm, the plugin or the assistant, and no assumption is written into monday as text.

## Writing the blueprint

`solution/blueprint.md` opens with this front matter, then the line "Internal: never client-facing". Write the values without the angle brackets; revisions start at 1; `sample_rows` is `planned` or `none`:

```
---
schema: "blueprint/1"
strand: "<short id>"
version: "<v0.1>"
revision: "<N>"
sample_rows: "planned"
updated: "<YYYY-MM-DDTHH:MM>"
---
```

Then these level-2 headings, numbered and titled exactly, and no other level-2 heading between them:

```
## 1. Version scope and deferred items      (with "### What this build rests on")
## 2. Product fit
## 3. Requirement trace                       (a table: need → what answers it, fixes or partly)
## 4. Structure mapping
## 5. Forks
## 6. Live objects this strand touches
## 7. Workspace and product binding
## 8. Native-entity map
## 9. Portfolio and project plan
## 10. Board inventory
## 11. Columns, relations and mirrors         (a table per board: column, type, values)
## 12. Groups, views, forms, docs, dashboards
## 13. The lists                              (the automations table: board, trigger, condition, action, recipients)
## 14. Permissions, ownership, plan tier and data policy
## 15. Irreversible operations, UI steps and client decisions
## 16. Internal
## Element keys
```

- **Sections 1 to 15 are written for the client to read:** plain words, no quote from a call, no element key, no assumption id, no file path, no internal word such as strand, ledger or record. Restate the client's facts in new words. Section 6's heading is pinned as it stands; the word in it is exempt.
- **Section 14 and the plan tier:** a blueprint makes no monday reads, so when `CLIENT.md` gives no tier, list what the build needs (boards, table views, mirrors, formulas, the automations, the dashboard) and say the tier is read when account-build binds the account, before any write.
- **Section 16** holds what is internal: the assumption ids in the order of section 1 (`AS1`, `AS2`, …), the assumed terms (`AT1` for the automation conditions), the forks built on their leaning (`FK1`), the sample data plan, and the build checks: each two-way pair, each mirror's source column and calculation, each unproved formula or widget with its fallback, the readiness clearance's conditions (what to test before the first look), and `W1` as referenced.
- **The element-key table** comes last: header `| key | kind | name | notifies |`, one row per element, `notifies` empty or `user`. Key forms: `W1` workspace, `F1` folder, `B1` board, `B1.G1` group, `B1.C1` column, `B1.V1` view, `B1.FM1` form, `B1.IB1` item batch (at most 20 rows), `A1` automation, `DB1` dashboard, `DB1.W1` widget, `U1` UI step. The kind words are the ledger's: `workspace`, `folder`, `board`, `group`, `column`, `view`, `form`, `doc`, `dashboard`, `widget`, `automation`, `item_batch` and `ui_step`; `ledger.py approval` refuses any other. Each side of a two-way connection is a column row of its own board. Name every row exactly as it will be built.
- The lean version writes no `backlog.md`, `allowlist.md`, `open-questions.md` or `dependencies.md`: open items go in section 16 and on the card.

## Saving, checking and freezing

1. If the strand has no version yet: `record.py --record <folder> version open --strand <id>` (it opens the next version; `--strand` is the three-digit id).
2. Write the file through the guard: `record.py --record <folder> guard --strand <id> --file strands/<strand folder>/solution/blueprint.md --expect-sha none --from <staged file>` the first time; later, read the current sha with `guard --file …` alone and pass it as `--expect-sha`.
3. Set `revision` in `versions/<v>/version.md` to the blueprint's revision, through the guard, with the `## Scope` section saying in one sentence what the version covers.
4. Read section 12 against section 16's build checks once more: each view's columns, filters and sorts, and each planted case's group, said the same way in both, since the build follows section 16 where they differ. Then check it: `leak_lint.py --record <folder> blueprint --strand <id>`, then `record.py --record <folder> check`. A block is fixed by rewording; warnings are shown to the user on the card. Run both before freezing: a frozen revision cannot change, so a blocked one costs a revision number.
5. Freeze it: `record.py --record <folder> freeze --strand <id>`. Keep the `frozen_sha256` it prints; `ledger.py approval` needs it.
6. Log it: `record.py --record <folder> log --strand <id> --type blueprint --version <v> --key r<N> --line "revision <N> frozen · sha256 <sha>"`.
7. Set `STRAND.md` `stage` to `blueprint` and `next_step` to the card, through the guard. Delete `.work/staging/`.

## The approval card

One message, in plain words, in this order:

1. **Where:** the account, the workspace and the folder, and that nothing else is touched.
2. **What this build rests on:** each assumption, assumed term and fork on its leaning, marked assumed, with what a later change would and would not keep.
3. **The boards:** what one row is, the columns in a sentence each, the groups.
4. **Views, forms and the dashboard:** each widget and the question it answers.
5. **Automations:** a table of board, trigger, action and recipients (the user only).
6. **Sample data:** how many rows, invented, around this week, and the cases planted to show a check.
7. **Hard to undo:** the folder (and a workspace, when the build makes one), and that automations made through the API cannot be switched off through the API (G-65).
8. **Left for the user in monday:** the UI steps.
9. **Build checks:** each unproved element and its fallback.
10. Any lint warning.

On a proof of concept in the user's own account one yes covers the whole card (A28). Ask nothing else unless an A11 decision first matters now. The user's words are what account-build passes to `ledger.py approval`, which records them; if the build does not follow in the same session, put them in `STRAND.md` `next_step` with the build as the next step, so the next session has them.
