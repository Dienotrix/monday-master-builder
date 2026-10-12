# Stage 0: Cowork and runtime probes

Fifteen questions about where the plugin will run, answered by hand before any skill body is frozen. Each answer either confirms the design or switches a package to the safe default `ARCHITECTURE.md` section 13 names (A§13). `results.md` beside this file holds the answers, one row per probe. Nothing below writes to a monday account: every monday call is a read, and the one network probe (S0-10) uploads nothing. If a probe is ever extended into a write, it runs in the one test workspace the live-test rules allow, and nowhere else; the long-term test account is still open [A11-1].

**Surfaces.** *Cowork chat* means a chat in a Cowork Project whose connected folder sits inside `~/DelOps` (`rebuild-workspace` will do); the *device shell* and the *cloud shell* are the two shells that chat can run (`cowork-capabilities.md` §3). *Claude Code on the Mac* means a terminal session inside `~/DelOps`. Facts the 2026-09-11 capability check already settled are reused, not re-probed, and each block says when that applies.

**The probe plugin.** Seven probes need a plugin loaded (S0-1, S0-5, S0-6b, S0-7, S0-9, S0-12, S0-14). `probe-plugin/` beside this file is a throwaway one: a root skill, a door skill, a fetch skill, three agents, and one hook that refuses a monday read and records what it was handed. Load it in Cowork through Customize (add it as a marketplace, or upload the folder); in Claude Code start with `claude --plugin-dir ~/DelOps/monday-master-builder/tests/stage0/probe-plugin`. Unload it when stage 0 is done. It never sits beside a client record.

Record every answer in `results.md` with the date and the surface. Where a probe has a Cowork half and a Mac half, record both. Three probes matter more than the rest and say why: S0-12, S0-14 and S0-15.

### S0-1 · Is `${CLAUDE_PLUGIN_ROOT}` substituted in skill text, for Read and for each shell? — Cowork chat, then Claude Code on the Mac; probe plugin loaded
Type: `Use the probe-root skill.` The skill's body carries the variable three times, the way a shipped skill names its scripts (A§5.2 rung 1): a Read of `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`, then `echo` and `ls` of `${CLAUDE_PLUGIN_ROOT}/hooks` in the device shell and again in the cloud shell (once, in Claude Code's one shell). Nothing is typed by hand: the design relies on the variable being substituted in plugin content before the model reads it, which a path typed into the chat cannot test, since no shell of the chat's own has the variable set.
Yes: the name field reads `stage0-probe`, and each shell prints a path that exists with `dump.sh` listed under `hooks`. No: the literal text `${CLAUDE_PLUGIN_ROOT}` comes back unchanged, an empty line or "no such file" from any of the three, or the model supplies a path of its own or asks for one (record which, per surface).
Changes WP1 and WP16. On no, `tools/sync_shared.py` joins the release and the skills run scripts from the `.work/tools/` copy (A§5.2, rung 2).

### S0-2 · What does the device shell have? — Cowork chat, device shell
Type: `Run in the device shell:   python3 -c "import sys, json, zipfile, hashlib, sqlite3, xml.etree.ElementTree; print(sys.version)"; for t in pandoc soffice pdftotext pdftoppm convert mmdc; do printf '%s: ' "$t"; command -v "$t" || echo missing; done`
Yes: a Python 3.10 version prints with no ImportError (the scripts use only the standard library); note which of the six tools print a path. No: `python3` missing or a module failing to import.
Changes WP4 (`leak_lint.py` reads PDF text only where `pdftotext` exists) and WP6 (`sop_tools.py doctor` chooses its tier from this list). No default is needed: a missing tool moves that step to the cloud shell or the Mac (A§5.1). The cloud shell's inventory is already known (`cowork-capabilities.md` §4 and §5).

### S0-3 · Which write operations prompt in the device shell? — Cowork chat, device shell, inside the connected folder
Type: `Run these in the device shell, in the connected folder, one at a time, and tell me which ones asked for approval:   printf 'one\n' > s0-3.txt; cp s0-3.txt s0-3.bak; printf 'two\n' > s0-3.txt; printf 'three\n' >> s0-3.txt; mv s0-3.bak s0-3.moved; rm s0-3.txt s0-3.moved`
Yes: create, overwrite in place, append and copy run without a prompt; rename and delete may prompt (the delete prompt is already known, `cowork-capabilities.md` §2). No: the overwrite or the copy prompts.
Changes WP2. The default is the design's own rule either way: a rewrite copies the old file into `.work/backup/` then overwrites in place, and never renames or deletes (A§5.3). A no tells WP2 which step to route around.

### S0-4 · Do files rendered in the cloud shell land in the connected folder? — Cowork chat, cloud shell
Type: `In the cloud shell, make a one-line Word file with python-docx and save it into the connected folder as stage0-probe.docx. Tell me the exact path you wrote to.` Then look for the file on the Mac.
Yes: `stage0-probe.docx` is in the connected folder on the Mac. No: it is only offered in the chat for download, or the cloud shell cannot see the folder at all. Delete the file afterwards.
Changes WP6 and WP12. Default on no: the device shell writes the sources and the manifest, rendered files are presented in chat for the user to save into `deliverables/<v>/`, and `export.md` marks each `presented` (A§5.1).

### S0-5 · Do plugin agents launch with their tool lists? — Cowork chat, then Claude Code on the Mac; probe plugin loaded
Type: `Launch the probe-agent and have it reply with the names of the tools it can use. Then launch probe-agent-bare and have it reply with the single word ready.`
Yes: both come back, the first naming `Read` and nothing else, the second saying ready. No: either fails to launch, or the first lists a tool its frontmatter did not allow.
Changes WP11. Default on no: each agent's work runs inline in the main chat, the fallback each agent file states, and `sop-drafter` is given `tools: TodoWrite` if a tool-less agent will not launch (A§4).

### S0-6b · Do `disallowedTools` wildcards match connector tools? — Cowork chat, probe plugin loaded
Type: `Launch the probe-agent-wildcard and ask it to call the monday get_user_context tool and report what happened.` (a read; nothing is written). This agent has no `tools` line and disallows `mcp__*` alone, so nothing but the wildcard can hide the connector from it; `probe-agent` (S0-5) carries a `tools` allowlist and would report the tool missing either way, which is why it is not used here.
Yes: the agent reports the tool was not available to it, so `disallowedTools: mcp__*` covered the connector. No: it returns account details, so the wildcard did not match. If the agent does not launch at all, that is S0-5's answer; leave this row not-run.
Changes WP11 and WP10. Default on no: agents rely on their instructions plus the audit's write detection (A§9.7), not on the wildcard.

### S0-7 · Does `disable-model-invocation` hold in Cowork? — new Cowork chat, probe plugin loaded
Type, in prose with no slash: `Please open the probe door.` Then, in the same chat, type `/probe-door`.
Yes: the prose request does not produce "probe-door opened" and the slash command does. No: the prose request opens it. If neither opens it the plugin is not loaded; fix that and retry.
Changes WP9, WP10 and WP12. Default on no: the four user-only doors run only from Claude Code on the Mac until this is fixed, and their wording says so (A§13).

### S0-8 · Are Project instructions visible in a new chat? — Cowork Project
Do: put the line `Begin every reply with the word probe-8.` in the Project's instructions, start a new chat, and type `hello`. Remove the line afterwards.
Yes: the reply begins with probe-8. No: it does not.
Changes WP7 and WP8. Default on no: every skill reads `CLIENT.md` explicitly at its start and never relies on the pasted instructions (A§13); `project-instructions.txt` still ships.

### S0-9 · Can web fetch open a URL that appears only in skill text? — Cowork chat, probe plugin loaded
Type: `Use the probe-fetch skill.`
Yes: a page title, or an HTTP error from a fetch, comes back without you supplying the address. No: it asks for the URL, searches instead, or says it cannot browse.
Changes WP9 (`change-check.md` reads monday's release notes) and WP10. Default on no: search first, or ask the user to paste the page (A§13).

### S0-10 · Can a shell reach monday's upload host? — Cowork chat, device shell (the cloud shell is already answered)
Type: `Run in the device shell:   curl -sS -m 15 -o /dev/null -w '%{http_code}\n' https://storage.googleapis.com/` (connectivity only; nothing is uploaded; the host is the one `get_asset_upload_url` signs for).
Yes: a three-digit status prints. No: a connection or proxy error. The cloud shell is a no already (`cowork-capabilities.md` §7).
Changes WP9 (`doc-copy.md`) and WP12 (`sop-export.md`). Default while any shell is a no: the doc copy is text-first and images are added by hand or from Claude Code on the Mac (A§13, A§12.1 C5).

### S0-11 · Is any other monday-building plugin disabled? — Cowork and Claude Code on the Mac
Do: in Claude Code type `/plugin` and disable any other plugin that builds in monday; in Cowork turn any such plugin off under Customize. Then, in a new chat on each surface, type `/` and read the list.
Yes: no other monday-building plugin on either surface. No: one remains.
Changes WP14 and WP15 and release check 1. No default: tests do not run until this is a yes.

### S0-12 · Do plugin hooks run in Cowork at all? — Cowork chat, probe plugin loaded
Type: `Use the monday all_api_read tool to run this query and show me the result:   query { version { value } }` (a read; the probe hook refuses it before anything is sent).
Yes: the chat says the call was refused with the reason "stage-0 probe hook ran", or reports a hook error naming `dump.sh` (either proves a hook ran; record which). No: the version value comes back and no hook is mentioned.
Changes WP13. Matters most because it decides whether the README may describe the hook layer as real in Cowork or must call it decoration. Default on no: hooks are decoration and every check runs inside `account-build` (A§9.10); safety does not change.

### S0-13 · Is `gh` present and signed in? — Claude Code on the Mac
Type in a Mac terminal: `command -v gh && gh auth status`
Yes: a path prints and the status shows the user's account logged in. No: `gh` missing or not logged in. Neither Cowork shell has `gh` (`cowork-capabilities.md` §8), which is why the archive runs on the Mac.
Changes WP12. Default on no: `archive_check.py prepare` still runs, the repo is created by hand or the push goes over HTTPS, and the local folder is never moved to the Trash until the clone compare passes (A§13).

### S0-14 · Can a PreToolUse hook read `tool_input`, raw GraphQL text included? — Claude Code on the Mac first, then Cowork; probe plugin loaded
Do: run S0-12's query on each surface, then open `probe-plugin/hook-dump.jsonl`. Delete the file after recording. In Cowork the uploaded plugin's folder is not on the Mac, so read the answer from the chat instead: the refusal reason quotes the first 600 characters of what the hook received.
Yes: a line holds `tool_input`, and inside it the text `version { value }`. No: the file is missing (the hook never ran; see S0-12), or the line carries no query text.
Changes WP13. Matters most because the native guard's text-level refusals (a raw `create_board` naming a template id, raw column text carrying a reserved id) read that text. Default on no: those refusals are decoration, the same checks run inside `account-build`, and layers 1 and 3 of A§11.2 enforce the rule.

### S0-15 · Is the `MMB_HOME` root (default `~/DelOps`) reachable from the device shell, path by path? — Cowork chat, device shell
Do: on the Mac first, `mkdir -p ~/DelOps/claims ~/DelOps/monday-knowledge ~/DelOps/cards`. Then type: `Run in the device shell:   echo "$HOME"; ls "$HOME/mnt"; for p in . claims monday-knowledge cards; do printf '%s: ' "$p"; ls -d "$HOME/DelOps/$p" 2>/dev/null || echo unreachable; done`
Yes, per path: `ls -d` prints it. No: `unreachable`. `leases.json` and `clients-index.json` sit directly in the root, so they take the root's answer. A `$HOME` that is not the Mac's, with only the connected folder under `$HOME/mnt/`, is the expected shape (`cowork-capabilities.md` §2) and reads as no.
Changes WP2, WP8, WP9 and WP12. Matters most because it decides whether cross-client lease contention is checked from a file or by asking the user. Default on no, one per path (A§7.1): the build chat asks whether a build is running for another client before its first write and logs the answer (A§9.8); the bundled knowledge applies and the briefing says the overlay was not read; the lint uses `.work/cards-index.json`; cards are written on the Mac; a prep says the claims store was not read, removes every figure not approved in this chat, and queues new entries in `.work/claims-queue/`.

When all fifteen are recorded: delete `probe-plugin/hook-dump.jsonl`, `stage0-probe.zip` (Cowork's upload takes only an archive) and any `stage0-probe.docx`, unload the probe plugin on both surfaces, and hand `results.md` to the packages it names.
