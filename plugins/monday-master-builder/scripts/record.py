#!/usr/bin/env python3
"""The client record's writer and checker (ARCHITECTURE 5.4, WP2 decisions G01 to G61).

Every subcommand prints one JSON object, {"ok", "command", ...}, and exits 0 (done), 1 (refused, or
`check` found a blocking finding), 2 (done, warnings only) or 3 (could not run); `status` prints the
status/1 object itself and exits 0 whenever it printed it (G10). The record is the current folder, or
the folder named by --record. Templates and plugin.json are found from this file's own place (G31,
G36). Standard library only, Python 3.9 and later, the same on Windows and macOS. Nothing here deletes
or renames a file, writes the lock or its two mirrors (mmb_common's lease primitives do), or fills in
one of the three open A11 fields. After a command that changed a file the index's harvest reads, it runs
leak_lint.py index for the record in process, and an index that stops is a warning (exit 2; WP4's R48).
"""
import sys
sys.dont_write_bytecode = True  # no cache beside the scripts (G49), set before mmb_common is imported
if sys.version_info < (3, 9):
    sys.stdout.write('{"ok": false, "command": null, "error": {"file": "record.py", "field": "python", '
                     '"problem": "Python %d.%d", "expected": "Python 3.9 or later"}}\n' % sys.version_info[:2])
    sys.exit(3)
import argparse, contextlib, fnmatch, hashlib, json, os, re, shutil  # noqa: E401,E402
import importlib.util  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
import mmb_common as mc  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates" / "record"
KEYS = ("file", "field", "problem", "expected")
INTERNAL = "Internal: never client-facing"
HANDOFF = ("Building this work happens outside this product. This record holds its scope, open questions, "
           "dependencies, access needs and next steps; it does not design or build it.")
SLUG, VERSION = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*"), re.compile(r"v(\d+)\.(\d+)")
HEADER = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (\S+) · (\S+) · (\S+) · (.+)$")
ENTRY = re.compile(r"(?m)^(?=## \d{4}-)")
INDEX_HEAD = "| strand | title | kind | state | version | version state | clearance | live objects | last activity |"
INDEX_SEP = "|---|---|---|---|---|---|---|---|---|"
REFERENCE = re.compile(r"(?<![\w/.:-])(\d{3})(?::([A-Z]+\d+(?:\.[A-Z]+\d*)*)|/(v\d+\.\d+)(?:r(\d+))?)(?!\w)")
LEDGER_REF = re.compile(r"(?<![\w/.-])(v\d+\.\d+)r(\d+)")
ABSOLUTE = re.compile(r"(?<![^\s\"'(])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|~/|/(?:Users|home|Volumes|private|tmp|var|"
                      r"opt|mnt|root|etc|usr|srv|media)/[^\s/\"')]+)")
LINK = re.compile(r"\]\(<?([^)\s>]+)>?\)")
MARKER = re.compile(r"\[(?:Q|Q\?|Q/side|Q/recon|Q/doc|X|E|I|A)\]")
QUOTE = re.compile(r"\[(?:Q|Q\?|Q/side|Q/recon|Q/doc|X)\]")
LOCATION = re.compile(r"@\d{1,2}:\d{2}(?::\d{2})?|\bcues? \d+|\bL\d+|\bparagraph \d+|§ ?\d+|\bp\. ?\d+|\bregion\b")
INTERNAL_ID = re.compile(r"\b\d{3}:[A-Z]+\d|\b\d{3}/v\d+\.\d+|\b\d{8}-\d{4}-[a-z0-9]{4}\b|\brun-\d{4}-\d{2}-\d{2}-\d+"
                         r"|\bG-\d{2,3}\b")

# pinned: log-types
LOG_TYPES = ("created", "binding", "workspace", "research", "call", "document", "email", "conflict", "readiness",
             "override", "superseded", "scope", "blueprint", "approval", "change-check", "preflight", "build",
             "departure", "irreversible", "automation", "workflow", "agent", "ai-column", "vibe", "sequence",
             "webhook", "write-failed", "recovery", "audit", "write-detected", "shown", "signed-off", "lint",
             "version", "release", "strand", "lease", "live-map", "summary", "api-surprise", "decision",
             "commitment", "closeout", "archive")
# end pinned

def one_of(*values):
    return "|".join(re.escape(value) for value in values), " | ".join(values)


STATES = ("planned", "approved", "building", "built", "fixing", "audited", "released")
CLEARANCES = ("none", "cleared to build", "cleared to build, generic", "not yet")
OUTPUT_CLASS = {"platform": "configured-structure", "non-platform": "bespoke-code", "hybrid": "hybrid"}
PLATFORM = ("new", "intake", "readiness", "blueprint", "building", "audited", "shown", "signed-off", "closing", "closed")
LADDER = {"platform": PLATFORM, "hybrid": PLATFORM, "non-platform": ("new", "scoping", "handed-off", "closed")}
TARGET_OF = {"own": "own-account", "client": "client-account", "sandbox": "none"}
BINDING = (("monday_account_id", "id"), ("monday_account_slug", "slug"), ("monday_bound_user_id", "bound_user_id"),
           ("monday_bound_at", "bound_at"), ("build_target", "build_target"), ("account_kind", "kind"))
A11_3 = ("transcripts_at_close", "transcript_redaction")
DATE, NONE_DATE, NONE_VERSION = (r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD"), (r"none|\d{4}-\d{2}-\d{2}", "none | YYYY-MM-DD"), \
    (r"none|v\d+\.\d+", "none | vX.Y")
CLIENT_VALUES = {  # G15: client/2 in its order, with each value set or form (None: any one-line string)
    "schema": None, "slug": None, "name": None, "account_kind": one_of("own", "client", "sandbox"),
    "build_target": one_of("own-account", "client-account", "none"),
    "build_target_reason": None,  # intake fold 2: optional, why the target is what it is; init writes the default's
    "monday_account_id": None,
    "monday_account_slug": None, "monday_bound_user_id": None, "monday_bound_at": None, "monday_tier": None,
    "monday_tier_read_at": None, "monday_tier_source": one_of("preflight", "client statement", "unread"),
    "products_in_scope": (r"(core|crm|service)(,(core|crm|service))*", "core, crm or service, comma-joined"),
    "client_workspaces": (r"none|(core|crm|service):\d+(;(core|crm|service):\d+)*", "none, or product:id joined by ;"),
    "record_state": one_of("active", "closing", "closed"), "strands_open": (r"\d+", "a count"),
    "strands_total": (r"\d+", "a count"), "current_strand": (r"none|\d{3}", "none or a short id"),
    "live_build": one_of("yes", "no"), "lease": None, "last_input": None, "last_researched": None,
    "transcripts_at_close": one_of("unanswered", "exclude", "archive"),
    "transcript_redaction": one_of("unanswered", "none", "offered-per-call", "always"),
    "sample_data_in_account": one_of("unanswered", "allowed", "not-allowed", "not-needed"),
    "ai_notice": (r"not-yet|not-needed|given \d{4}-\d{2}-\d{2}", "not-yet | not-needed | given YYYY-MM-DD"),
    "updated": None,
    # R40: optional and last, where the writer appends it; a record written before it reads as having none
    "former_names": (r"(?:[^;]*[^;\s][^;]*(?:;[^;]*[^;\s][^;]*)*)?", "empty, or earlier names joined by ; with none empty")}
CLIENT_OPTIONAL = ("former_names", "build_target_reason")
TARGET_REASON = {"own-account": "the default: a proof of concept is built in the user's own account until the user "
                                "names another target"}
STRAND_VALUES = {  # G16; the stage is checked against the ladder of the strand's kind
    "schema": None, "strand": None, "slug": None, "title": None, "kind": one_of(*OUTPUT_CLASS),
    "output_class": one_of(*OUTPUT_CLASS.values()), "opened": DATE, "opened_reason": None,
    "state": one_of("active", "paused", "closed"), "stage": None, "version": NONE_VERSION,
    "version_state": one_of("none", *STATES), "clearance": one_of(*CLEARANCES), "override": None,
    "round": one_of("none", "one", "two"), "workspaces": None, "next_step": None,
    "depends_on": (r"none|\d{3}(, ?\d{3})*", "none or short ids"), "summary_current_to": NONE_VERSION,
    "closed": NONE_DATE, "updated": None}
VERSION_VALUES = {  # G17, the fields with a value set
    "state": one_of(*STATES), "purpose": one_of("proof-of-concept", "working-solution"),
    "revision": (r"none|\d+", "none or a number"), "sha256": (r"none|[0-9a-f]{64}", "none or a sha256"),
    "released": NONE_DATE, "shown": (r"none|\d{4}-\d{2}-\d{2}(; \d{4}-\d{2}-\d{2})*", "none or dates joined by ; "),
    "signed_off": NONE_DATE}
ROWS = {"planned": ("planned",), "approved": ("planned", "approved"), "building": ("planned", "approved", "building"),
        "built": ("planned", "approved", "built"), "fixing": ("planned", "approved", "built", "fixing"),
        "audited": ("planned", "approved", "built", "audited"),
        "released": ("planned", "approved", "built", "audited", "released")}
BUDGETS = (  # G44: (path pattern, lines, KB), warnings; SUMMARY.md past 120 and the live map past 400 block
    ("CLIENT.md", 160, 10), ("log.md", 300, 0), ("meetings.md", 150, 0), ("research/*-brief.md", 80, 0),
    ("research/*-deep-dive.md", 200, 0), ("research/updates.md", 150, 0), ("calls/*.md", 120, 0),
    ("inputs/*.md", 120, 0), ("live/live-map.md", 250, 16), ("client-card.md", 60, 0),
    ("archive-handoff.md", 60, 0), ("CLAUDE.md", 10, 0), ("strands/*/STRAND.md", 120, 0),
    ("strands/*/SUMMARY.md", 80, 0), ("strands/*/readiness.md", 250, 0), ("strands/*/solution/blueprint.md", 400, 0),
    ("strands/*/solution/scope.md", 200, 0), ("strands/*/solution/backlog.md", 150, 0),
    ("strands/*/solution/allowlist.md", 80, 0), ("strands/*/solution/exclusions.md", 80, 0),
    ("strands/*/solution/open-questions.md", 150, 0), ("strands/*/solution/dependencies.md", 120, 0),
    ("strands/*/solution/structure-inventory.md", 200, 0), ("strands/*/versions/*/version.md", 150, 0),
    ("strands/*/versions/*/audit*.md", 200, 0), ("strands/*/versions/*/build-notes.md", 250, 0),
    ("strands/*/drafts/*-admin-prerequisites.md", 60, 0), ("strands/*/close-out.md", 60, 0))
CALL_BUDGET = (120, 30, 250)  # intake fold 1: a call summary's lines: the floor, transcript words a line, the ceiling
TYPE_FIELDS = ("seat", "relationship", "direction", "output_class", "room_shape", "money_live")
TYPE_STATES = ("detected", "assumed", "confirmed", "proposed")  # intake fold 12: proposed, the first word, is assumed
SUMMARY_HEADINGS = ("## What the work was", "## Pains it served", "## What was built", "## What the client confirmed",
                    "## What must not be broken", "## Cost of change, in the client's words",
                    "## Ownership and switch-off at close", "## Backlog seeds carried forward", "## Dates")
EMAIL_EXTENSIONS = (".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp")
FIXED = {"CLIENT.md": "client", "log.md": "log", "account.json": "account", ".work/lock.json": "lock",
         ".work/history.json": "history", "live/live-map.md": "live-map"}
SETTINGS_SHAPE = (  # G34
    ("schema", lambda v: v == "settings/1", "settings/1"),
    ("created", lambda v: isinstance(v, str) and bool(re.fullmatch(DATE[0], v)), "YYYY-MM-DD"),
    ("plugin_version", lambda v: isinstance(v, str) and bool(v), "the plugin version that wrote it"),
    ("firm", lambda v: isinstance(v, dict) and isinstance(v.get("name"), str) and isinstance(v.get("renderings"), list),
     "{name, renderings[]}"),
    ("default_build_account", lambda v: isinstance(v, dict) and all(isinstance(v.get(k), str) for k in ("slug", "id")),
     "{slug, id}, each a string"),
    ("never_show_workspaces", lambda v: isinstance(v, list) and all(
        isinstance(i, dict) and isinstance(i.get("id"), str) and isinstance(i.get("name"), str) for i in v),
     "a list of {id, name}, possibly empty"),
    ("archive", lambda v: v in ("local", "github"), "local | github"))


class Usage(Exception):
    """A usage error: exit 3 with the JSON envelope, never argparse's own exit 2 (G10)."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)

def emit(data):
    """Print one JSON object as UTF-8 with LF: the same bytes on every system."""
    text = mc.json_text(data)
    sys.stdout.flush()
    raw = getattr(sys.stdout, "buffer", None)
    if raw is None:
        sys.stdout.write(text)
    else:
        raw.write(text.encode("utf-8"))
        raw.flush()

def refuse(*reasons):
    """Raise one Refusal listing every (file, field, problem, expected) given; None entries are passes."""
    found = [reason for reason in reasons if reason]
    if found:
        raise mc.Refusal(*found)

def one_line(value, bar=False):
    return bool(value and value.strip()) and "\n" not in value and "\r" not in value and not (bar and "|" in value)


# Reading the record: documents, strands, versions, schemas, templates.

def read_doc(root, path):
    """(front matter, body, text) of a record Markdown file."""
    name = mc.relative(root, path)
    text = mc.read_text(path, name)
    fields, body = mc.split_front_matter(text, name)
    return fields, body, text

def write_fm(root, path, updates):
    """Set front-matter values in place, after a backup, when any of them changes (G38, G39)."""
    name = mc.relative(root, path)
    text = mc.read_text(path, name)
    new = mc.set_front_matter(text, updates, name)
    if new != text:
        mc.write_file(path, new, root)

def front_text(pairs):
    return "---\n" + "".join('%s: "%s"\n' % (key, value.replace("\\", "\\\\").replace('"', '\\"'))
                             for key, value in pairs) + "---\n"

def strand_folders(root):
    base = root / "strands"
    return sorted(p for p in base.iterdir() if p.is_dir() and re.match(r"\d{3}-", p.name)) if base.is_dir() else []

def vnum(name):
    return tuple(int(part) for part in VERSION.fullmatch(name).groups())

def version_folders(folder):
    base = folder / "versions"
    found = [p for p in base.iterdir() if p.is_dir() and VERSION.fullmatch(p.name)] if base.is_dir() else []
    return sorted(found, key=lambda p: vnum(p.name))

def runs(root, folder):
    path = folder / "solution" / "build.json"
    return (mc.read_json(path, mc.relative(root, path)).get("runs") or []) if path.is_file() else []

def schema_for(rel):
    """The schema a record file must carry, by its place (G57); None for a file with a `<stem>/1` schema."""
    parts = rel.split("/")
    if rel in FIXED or parts[0] != "strands":
        return FIXED.get(rel)
    if parts[-1] in ("log.md", "build.json"):
        return {"log.md": "log", "build.json": "build"}[parts[-1]]
    if len(parts) == 3:
        return {"STRAND.md": "strand", "SUMMARY.md": "summary", "readiness.md": "readiness"}.get(parts[2])
    if parts[2:] == ["solution", "scope.md"]:
        return "scope"
    return "version" if len(parts) == 5 and parts[2] == "versions" and parts[4] == "version.md" else None

def newer(rel, found, name):
    return (rel, "schema", "schema %s is newer than this plugin's, or not this file's: the record refuses writes"
            % found, "%s/%d" % (name, mc.SCHEMAS[name]))

def refuse_newer(root, *paths, skip=()):
    """G57, C13: before anything is written, refuse naming every newer or foreign schema it will touch."""
    reasons = []
    for path in [mc.record_path(root, rel) for rel in FIXED if rel not in ("live/live-map.md",) + skip] + list(paths):
        rel = mc.relative(root, path)
        name = schema_for(rel)
        if name and path.is_file():
            found = (mc.read_json(path, rel).get("schema") if path.suffix == ".json"
                     else mc.front_matter(mc.read_text(path, rel), rel).get("schema"))
            reasons.append(newer(rel, found, name) if mc.schema_newer(found, name) else None)
    refuse(*reasons)

def fill(name, values):
    """A template from <plugin root>/templates/record/ with the front-matter keys record.py owns set (G31)."""
    path, shown = TEMPLATES / name, "templates/record/" + name
    if not path.is_file():
        raise mc.CannotRun((shown, name, "the template is missing from the plugin", "the plugin's own template"))
    text = mc.read_text(path, shown)
    try:
        fields = mc.front_matter(text, shown)
    except mc.FrontMatterError as exc:
        raise mc.CannotRun(*[tuple(f[k] for k in KEYS) for f in exc.findings])
    for key in values:
        if key not in fields:
            raise mc.CannotRun((shown, key, "the template has no %s key" % key, "every key record.py sets"))
    return mc.set_front_matter(text, dict(values, updated=mc.stamp("minute")) if "updated" in fields else values,
                               shown)

def strand_doc(root, short):
    """(folder, STRAND.md, its record-relative name, front matter, text), refused on a newer schema."""
    folder = mc.strand_dir(root, short)
    path = folder / "STRAND.md"
    refuse_newer(root, path)
    fields, _, text = read_doc(root, path)
    return folder, path, mc.relative(root, path), fields, text

def holds_lease(root, short):
    lock = mc.read_lock(root)
    if lock.get("state") == "held" and lock.get("strand") == short:
        return (".work/lock.json", "strand", "strand %s holds the build lease, session %s"
                % (short, lock.get("session_label")), "the lease released, or broken if it is stale")
    return None


# The log (G08, G13, G45): one record-wide history, newest first, entries never edited.

def split_log(text):
    """(the part before the first entry, [entry text, ...]), each entry from its header to the next."""
    parts = ENTRY.split(text)
    return parts[0], parts[1:]

def entry_parts(entry):
    """(header groups or None, body lines with trailing blank lines dropped) of one entry."""
    lines = entry.split("\n")
    body, match = lines[1:], HEADER.match(lines[0])
    while body and not body[-1].strip():
        body.pop()
    return (match.groups() if match else None), body

def values_of(body):
    """`key: value` pairs of an entry body, parts joined by ` · ` read one by one."""
    found = {}
    for line in body:
        for part in line.split(" · "):
            key, sep, value = part.partition(": ")
            if sep:
                found.setdefault(key.strip(), value.strip())
    return found

def new_entry(strand, kind, version, key, body):
    return "## %s · %s · %s · %s · %s\n%s\n" % (mc.stamp("log"), strand, kind, version, key,
                                                "".join(line + "\n" for line in body))

def roll_hash(entries):
    """G08: sha256 over the moved entries in file order, each line LF-ended, trailing blank lines dropped."""
    return mc.sha256_text("".join("\n".join(entry_lines(entry)) + "\n" for entry in entries))

def entry_lines(entry):
    lines = entry.replace("\r\n", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return lines

def log_files(root):
    """The record log, then every rolled log under strands/."""
    rolled = sorted((root / "strands").glob("*/log.md")) + sorted((root / "strands").glob("*/versions/*/log.md"))
    return [path for path in [root / "log.md"] + rolled if path.is_file()]

def entries_in(root):
    """[(log file, header groups or None, body lines, entry text)] over every log file."""
    found = []
    for path in log_files(root):
        name = mc.relative(root, path)
        for entry in split_log(mc.read_text(path, name))[1]:
            groups, body = entry_parts(entry)
            found.append((name, groups, body, entry))
    return found

def insert_entries(root, new, removed=()):
    """The one log writer: under the mutex, re-read log.md, drop `removed`, put `new` under the header (newest
    first), rewrite it in place, and move the baseline .work/history.json the same way (G08, G09)."""
    path, base = root / "log.md", root / ".work" / "history.json"
    with mc.record_mutex(root):
        text = mc.read_text(path, "log.md")
        mc.front_matter(text, "log.md")
        head, entries = split_log(text)
        kept = [entry for entry in entries if entry not in removed]
        mc.write_file(path, (head.rstrip("\n") + "\n\n" + "".join(list(new) + kept)).rstrip("\n") + "\n", root)
        hashes = (mc.read_json(base, ".work/history.json").get("entries") or [] if base.is_file()
                  else [mc.sha256_text(entry) for entry in entries])
        gone = {mc.sha256_text(entry) for entry in removed}
        hashes = [mc.sha256_text(entry) for entry in new] + [sha for sha in hashes if sha not in gone]
        mc.write_file(base, mc.json_text({"schema": "history/1", "entries": hashes}), root, backup=False)


# The strand index (G06, G18, G54): written by record.py from every STRAND.md in the same locked step.

def activity(root, entries=None):
    """{short id: date of its newest log entry} across the record log and the rolled logs."""
    newest = {}
    for _, groups, _, _ in entries_in(root) if entries is None else entries:
        if groups and groups[1] != "-" and groups[0] > newest.get(groups[1], ""):
            newest[groups[1]] = groups[0]
    return {short: moment[:10] for short, moment in newest.items()}

def live_counts(root):
    path, counts = root / "account.json", {}
    objects = (mc.read_json(path, "account.json").get("live_objects") or {}) if path.is_file() else {}
    for item in objects.values():
        if item.get("state") in ("active", "inactive"):
            counts[item.get("owner_strand")] = counts.get(item.get("owner_strand"), 0) + 1
    return counts

def index_rows(root):
    """The nine index cells per strand, from each STRAND.md."""
    seen, live, rows = activity(root), live_counts(root), []
    for folder in strand_folders(root):
        short, fields = folder.name[:3], read_doc(root, folder / "STRAND.md")[0]
        cells = [short] + [fields.get(key, "none") for key in ("title", "kind", "state", "version", "version_state",
                                                              "clearance")]
        rows.append([cell.replace("|", "/") for cell in cells + [str(live.get(short, 0)), seen.get(short, "none")]])
    return rows

def index_table(body):
    """{short id: cells} of the rows under `## Strand index` whose first cell is three digits."""
    rows, inside = {}, False
    for line in body.split("\n"):
        if line.startswith("## "):
            inside = line.rstrip() == "## Strand index"
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if inside and line.startswith("|") and re.fullmatch(r"\d{3}", cells[0]):
            rows[cells[0]] = cells
    return rows

def with_index(text, rows):
    lines = text.split("\n")
    table = [INDEX_HEAD, INDEX_SEP] + ["| %s |" % " | ".join(row) for row in rows]
    if "## Strand index" not in lines:
        return text.rstrip("\n") + "\n\n## Strand index\n\n" + "\n".join(table) + "\n"
    start = lines.index("## Strand index") + 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    lines[start:end] = table + ([""] if end == start and start < len(lines) else [])
    return "\n".join(lines)

def refresh_index(root, opened=None):
    """Rewrite the strand index, `strands_total`, `strands_open` and, for a first strand, `current_strand`."""
    path = root / "CLIENT.md"
    text = mc.read_text(path, "CLIENT.md")
    fields, rows = mc.front_matter(text, "CLIENT.md"), index_rows(root)
    updates = {"strands_total": str(len(rows)), "strands_open": str(sum(row[3] != "closed" for row in rows))}
    if opened and fields.get("current_strand") == "none":
        updates["current_strand"] = opened
    new = mc.set_front_matter(with_index(text, rows), updates, "CLIENT.md")
    if new != text and "updated" in fields:
        new = mc.set_front_matter(new, {"updated": mc.stamp("minute")}, "CLIENT.md")
    if new != text:
        mc.write_file(path, new, root)

def set_block(text, heading, lines):
    """`text` with the block under `heading` replaced by `lines`, or the block appended at the end (G52)."""
    rows = text.rstrip("\n").split("\n")
    if heading in rows:
        start = rows.index(heading) + 1
        end = next((i for i in range(start, len(rows)) if rows[i].startswith("## ")), len(rows))
        rows[start:end] = [""] + lines + ([""] if end < len(rows) else [])
    else:
        rows += ["", heading, ""] + lines
    return "\n".join(rows) + "\n"

def section(body, heading):
    found, inside = [], False
    for line in body.split("\n"):
        if line.startswith("## "):
            inside = line.rstrip() == heading
        elif inside:
            found.append(line)
    return "\n".join(found)

def heading(body, name):
    return re.search(r"(?m)^## %s[ \t]*$" % re.escape(name), body or "") is not None

def last_line(text):
    return next((line.strip() for line in reversed((text or "").split("\n")) if line.strip()), "")

def handoff_last(body):
    """C133: the last section ends with the fixed hand-off sentence (quote and emphasis marks ignored)."""
    tail = ("\n" + body).split("\n## ")[-1]
    return " ".join(re.sub(r"[>*_\"“”]", " ", tail).split()).endswith(HANDOFF)


# check (G27 to G30, G44, G47, G48, G55, G57, G61 and the clauses C125 to C157).

class Check:
    """One full pass over a record, writing nothing; findings are (file, field, problem, expected)."""

    def __init__(self, root):
        self.root, self.blocking, self.warnings, self.newer = root, [], [], []
        self.docs, self.builds, self.saves = {}, {}, {}

    def block(self, *finding):
        self.blocking.append(dict(zip(KEYS, finding)))

    def warn(self, *finding):
        self.warnings.append(dict(zip(KEYS, finding)))

    def fields(self, rel):
        return self.docs[rel][0] if rel in self.docs else None

    def json(self, rel):
        """A record JSON file (missing or malformed: exit 3), or None when its schema is newer."""
        data = mc.read_lock(self.root) if rel == mc.LOCK_REL else mc.read_json(mc.record_path(self.root, rel), rel)
        name, schema = schema_for(rel), data.get("schema") if isinstance(data, dict) else None
        if name and mc.schema_newer(schema, name):
            self.block(*newer(rel, schema, name))
            self.newer.append(rel)
            return None
        return data

    def run(self):
        root = self.root
        with mc.record_mutex(root):
            if not (root / "log.md").is_file():
                raise mc.CannotRun(("log.md", "schema", "the record has no log", "log.md (log/1)"))
            self.files = sorted((mc.relative(root, p), p) for p in root.rglob("*")
                                if p.is_file() and p.relative_to(root).parts[0] != ".work")
            self.read_docs()
            self.account, self.lock = self.json("account.json"), self.json(".work/lock.json")
            self.entries = entries_in(root)
            for folder in strand_folders(root):
                self.strand(folder)
            client = self.fields("CLIENT.md")
            if client is not None:
                self.client(client)
            self.live_map()
            self.logs()
            self.raw_inputs()
            self.references()
            self.text_rules()
            self.call_types()
            self.budgets()
            self.settings()
            if client is not None:
                self.a11(client)
            if self.account is not None:
                self.guard_index()
        return self

    def read_docs(self):
        """C12, C154, G38, G57: every record Markdown file parses and carries its schema."""
        for rel, path in self.files:
            if not rel.endswith(".md") or path.name == "CLAUDE.md":
                continue
            try:
                fields, body, text = read_doc(self.root, path)
            except mc.FrontMatterError as exc:
                self.blocking.extend(exc.findings)
                continue
            name, schema = schema_for(rel), fields.get("schema", "")
            if name and mc.schema_newer(schema, name):
                self.block(*newer(rel, schema, name))
                self.newer.append(rel)
                continue
            if not re.fullmatch(r"[a-z][a-z0-9-]*/\d+", schema):
                self.block(rel, "schema", "schema %r is not a name and a number" % schema, '"<name>/<n>", the first key')
            self.docs[rel] = (fields, body, text)

    def values(self, rel, fields, table, complete=True, optional=()):
        for key, rule in table.items():
            if key not in fields:
                if complete and key not in optional:
                    self.block(rel, key, "the field is missing", "%s, in the order record-map.md gives" % key)
            elif rule and not re.fullmatch(rule[0], fields[key]):
                self.block(rel, key, "%r is not an allowed value" % fields[key], rule[1])
        for key in fields if complete else ():
            if key not in table:
                self.warn(rel, key, "a field this schema does not know", "the fields record-map.md gives this file")

    def client(self, client):
        """G15, C125, C147: client/2 values, the target against the kind, and the binding mirrors."""
        self.values("CLIENT.md", client, CLIENT_VALUES, optional=CLIENT_OPTIONAL)
        if client.get("slug") != self.root.name:
            self.block("CLIENT.md", "slug", "%s in a folder named %s" % (client.get("slug"), self.root.name),
                       "the folder name: a slug is never renamed")
        kind = client.get("account_kind")
        if kind in TARGET_OF and client.get("build_target") != TARGET_OF[kind]:
            self.block("CLIENT.md", "build_target", "%s with account_kind %s" % (client.get("build_target"), kind),
                       TARGET_OF[kind])
        if self.account is not None:
            bound = self.account.get("account") or {}
            for field, key in BINDING:
                if field in client and str(bound.get(key)) != client[field]:
                    self.block("CLIENT.md", field, "%s here, %s in account.json account.%s" % (
                        client[field], bound.get(key), key), "the same value on both sides; ledger.py bind writes both")
            mine = set() if client.get("client_workspaces", "none") == "none" else set(client["client_workspaces"].split(";"))
            theirs = {"%s:%s" % (product, (item or {}).get("id"))
                      for product, item in (self.account.get("client_workspaces") or {}).items()}
            if "client_workspaces" in client and mine != theirs:
                self.block("CLIENT.md", "client_workspaces", "%s here, %s in account.json" % (
                    client["client_workspaces"], ";".join(sorted(theirs)) or "none"), ";".join(sorted(theirs)) or "none")
        self.index(client)
        if self.lock is not None:
            self.lease(client)

    def lease(self, client):
        """C131, G48: the lock's shape (finding 9) and both mirrors against it, blocking, a mirror naming lease sync
        (finding 5); a held lease with a stale heartbeat is a warning."""
        lock, sync = self.lock, "; record.py lease sync rewrites it from the lock"
        held = lock.get("state") == "held"
        line = "%s %s (%s)" % (lock.get("strand"), lock.get("version"), lock.get("session_label")) if held else "none"
        if client.get("lease") != line:
            self.block("CLIENT.md", "lease", "%s, while .work/lock.json gives %s" % (client.get("lease"), line), line + sync)
        mirror = {key: lock.get(key) for key in ("strand", "epoch", "session_label", "heartbeat_at")}
        found = ((self.account or {}).get("guard_index") or {}).get("lease")
        if self.account is not None and found != mirror:
            self.block("account.json", "guard_index.lease", "%s, while the lock gives %s" % (
                json.dumps(found, sort_keys=True), json.dumps(mirror, sort_keys=True)), json.dumps(mirror, sort_keys=True)
                + sync)
        problems = mc.lock_findings(lock)
        for finding in problems:
            self.block(*finding)
        if held and not problems:
            age, stale = mc.heartbeat_age(lock.get("heartbeat_at"))
            if stale:
                self.warn(".work/lock.json", "heartbeat_at", "held by %s (%s) %s, session %s, heartbeat %s" % (
                    lock.get("strand"), lock.get("strand_title"), lock.get("version"), lock.get("session_label"),
                    mc.heartbeat_words(age, stale)), "resume the holder in a fresh session, or break the lease"
                          if age >= 0 else "set the clock of each machine that writes this record to the right time; "
                          "until then the lease reads as not fresh and may be broken")

    def index(self, client):
        """C128, G06: index rows and counters against the folders (blocking); cells against STRAND.md (warning)."""
        rows, folders = index_table(self.docs["CLIENT.md"][1]), {f.name[:3]: f for f in strand_folders(self.root)}
        for short in sorted(set(rows) ^ set(folders)):
            self.block("CLIENT.md", "strand index", "row %s has no strand folder" % short if short in rows
                       else "strands/%s has no index row" % folders[short].name, "one row per strands/NNN-* folder")
        found = {short: self.fields("strands/%s/STRAND.md" % f.name) or {} for short, f in folders.items()}
        for key, count in (("strands_total", len(folders)),
                           ("strands_open", sum(1 for f in found.values() if f.get("state") != "closed"))):
            if client.get(key) != str(count):
                self.block("CLIENT.md", key, "%s, while the strand folders give %d" % (client.get(key), count), str(count))
        for short in sorted(set(rows) & set(folders)):
            for column, key in enumerate(("title", "kind", "state", "version", "version_state", "clearance"), 1):
                want = found[short].get(key, "none").replace("|", "/")
                cell = rows[short][column] if column < len(rows[short]) else ""
                if found[short] and cell != want:
                    self.warn("CLIENT.md", "strand index", "row %s reads %s %r, STRAND.md %r" % (short, key, cell, want),
                              "the index record.py writes from each STRAND.md")

    def live_map(self):
        """C130: the live map and account.json live_objects hold the same rows."""
        found = self.docs.get("live/live-map.md")
        if found is None or self.account is None:
            return
        rows = set()
        for line in found[1].split("\n"):
            cell = line.strip().strip("|").split("|")[0].strip() if line.startswith("|") else ""
            if cell and cell != "key" and set(cell) - set("-: "):
                rows.add(cell)
        objects = set(self.account.get("live_objects") or {})
        for key in sorted(rows - objects):
            self.block("live/live-map.md", key, "a live-map row absent from account.json live_objects",
                       "the same rows on both sides")
        for key in sorted(objects - rows):
            self.block("account.json", "live_objects." + key, "a live object absent from live/live-map.md",
                       "the same rows on both sides")

    def strand(self, folder):
        """G16, C126, C132 to C136: one strand's front matter, kind, clearance, scope, exclusions, versions."""
        short, base = folder.name[:3], "strands/" + folder.name
        rel = base + "/STRAND.md"
        if not (folder / "STRAND.md").is_file():
            return self.block(rel, "schema", "the strand folder has no STRAND.md", "STRAND.md (strand/1)")
        fields = self.fields(rel)
        if fields is None:
            return
        kind = fields.get("kind")
        self.values(rel, fields, STRAND_VALUES)
        for key, want in (("strand", short), ("slug", folder.name)):
            if fields.get(key) != want:
                self.block(rel, key, "%s in the folder %s" % (fields.get(key), folder.name), want)
        if kind in LADDER and fields.get("stage") not in LADDER[kind]:
            self.block(rel, "stage", "%s is not on the %s ladder" % (fields.get("stage"), kind), " | ".join(LADDER[kind]))
        for name in ("versions", "solution/blueprint.md", "solution/build.json") if kind == "non-platform" else ():
            if mc.record_path(folder, name).exists():
                self.block("%s/%s" % (base, name), "kind", "a non-platform strand holds %s" % name,
                           "no versions/, blueprint.md or build.json under a non-platform strand")
        readiness = self.fields(base + "/readiness.md")
        if readiness is not None and readiness.get("clearance") not in CLEARANCES:
            self.block(base + "/readiness.md", "clearance", "%r is not a clearance" % readiness.get("clearance"),
                       "cleared to build | cleared to build, generic | not yet | none (the check has not run)")
        elif readiness is not None and readiness.get("clearance") != fields.get("clearance"):
            self.warn(base + "/readiness.md", "clearance", "%s here, %s in STRAND.md" % (
                readiness.get("clearance"), fields.get("clearance")), "the same clearance in both files")
        scope = self.docs.get(base + "/solution/scope.md")
        if scope is not None and not handoff_last(scope[1]):
            self.block(base + "/solution/scope.md", "hand-off", "the fixed hand-off sentence is not the final section",
                       HANDOFF)
        blueprint = self.fields(base + "/solution/blueprint.md") or {}
        if blueprint.get("sample_rows") == "planned" and not (folder / "solution" / "exclusions.md").is_file():
            self.block(base + "/solution/exclusions.md", "sample_rows", "the blueprint plans sample rows and the "
                       "exclusions file is absent", "solution/exclusions.md beside a blueprint that plans sample rows")
        build = None
        if (folder / "solution" / "build.json").is_file():
            build = self.builds[short] = self.json(base + "/solution/build.json")
        bound = str(((self.account or {}).get("account") or {}).get("id"))
        if build is not None and self.account is not None and str(build.get("account_id_at_bind")) != bound:
            self.block(base + "/solution/build.json", "account_id_at_bind", "%s, while account.json is bound to %s"
                       % (build.get("account_id_at_bind"), bound), bound)
        for vdir in version_folders(folder):
            self.version(folder, vdir, fields, build)

    def version(self, folder, vdir, strand, build):
        """G17, G27, C127, C151: one version's fields, its frozen blueprints and the files its state needs."""
        short, rel = folder.name[:3], "strands/%s/versions/%s/version.md" % (folder.name, vdir.name)
        if not (vdir / "version.md").is_file():
            return self.warn(rel, "state", "the version folder has no version.md", "versions/<v>/version.md")
        if rel not in self.docs:
            return
        fields, body = self.docs[rel][:2]
        self.values(rel, fields, VERSION_VALUES, complete=False)
        for key, want in (("strand", short), ("version", vdir.name), ("qualified_version", "%s/%s" % (short, vdir.name))):
            if fields.get(key) != want:
                self.block(rel, key, "%s in %s" % (fields.get(key), rel), want)
        if vdir.name == strand.get("version") and fields.get("state") != strand.get("version_state"):
            self.warn(rel, "state", "%s here, %s in STRAND.md version_state" % (
                fields.get("state"), strand.get("version_state")), "the same state in both files")
        for path in sorted(vdir.glob("blueprint-r*.md")):
            number, sha = path.stem[len("blueprint-r"):], mc.sha256_file(path)
            recorded = [("version.md", fields.get("sha256"))] if number == fields.get("revision") else []
            recorded += [("build.json approvals", str(item.get("sha256"))) for item in (build or {}).get("approvals") or []
                         if str(item.get("version")) == vdir.name and str(item.get("revision")) == number]
            for where, value in recorded:
                if value not in (None, "none") and value != sha:
                    self.block(mc.relative(self.root, path), "sha256", "the frozen blueprint hashes to %s, %s records %s"
                               % (sha, where, value), "the frozen copy as approved: a frozen file is never edited")
        for item in self.required(folder, vdir, fields, body, build or {}) if fields.get("state") in ROWS else ():
            (self.block if fields.get("state") == "released" else self.warn)(*item)

    def required(self, folder, vdir, fields, body, build):
        """G27: what the state's row and the rows it passed through need, as missing (file, row, problem, what)."""
        short, version, state, revision = folder.name[:3], vdir.name, fields.get("state"), fields.get("revision", "none")
        base = "strands/%s/" % folder.name
        rel, vrel = base + "versions/%s/version.md" % version, base + "versions/%s/" % version
        logged = {groups[2] for _, groups, _, _ in self.entries if groups and groups[1] == short and groups[3] == version}
        audits = sorted(vdir.glob("audit*.md"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 1))
        texts = [(self.docs.get(mc.relative(self.root, p)) or (None, ""))[1] for p in audits]
        lock, change = self.lock or {}, (self.account or {}).get("change_check") or {}
        checks = {
            "planned": [((folder / "solution" / "blueprint.md").is_file(), base + "solution/blueprint.md",
                         "solution/blueprint.md"), (revision != "none", rel, "a revision in version.md"),
                        (heading(body, "Scope"), rel, "a ## Scope heading in version.md")],
            "approved": [((vdir / ("blueprint-r%s.md" % revision)).is_file(), vrel + "blueprint-r%s.md" % revision,
                          "the frozen blueprint of revision %s" % revision),
                         (any(str(a.get("version")) == version and str(a.get("revision")) == revision
                              for a in build.get("approvals") or []), base + "solution/build.json",
                          "the approval of %s revision %s in build.json approvals" % (version, revision)),
                         ("approval" in logged, "log.md", "an approval log entry at %s for %s" % (short, version))],
            "building": [(any(r.get("state") == "running" and r.get("version") == version and r.get("lease_epoch")
                              is not None and r.get("another_build_running") for r in build.get("runs") or []),
                          base + "solution/build.json", "a running run for %s with its lease epoch and the answer to "
                          "the one question" % version),
                         (lock.get("state") == "held" and lock.get("strand") == short, ".work/lock.json",
                          "the build lease held by strand %s" % short),
                         (change.get("for_strand") == short, "account.json", "change_check for strand %s" % short),
                         ((build.get("preflight") or {}).get("version") == version, base + "solution/build.json",
                          "a preflight for %s" % version)],
            "built": [(heading(body, "Build"), rel, "a ## Build heading in version.md"),
                      ("build" in logged, "log.md", "a build log entry at %s for %s" % (short, version))],
            "fixing": [(any(heading(text, "Findings") for text in texts), vrel + "audit.md",
                        "an audit*.md with a ## Findings heading")],
            "audited": [(bool(texts) and heading(texts[-1], "Write detection") and heading(texts[-1], "Documents appendix")
                         and last_line(texts[-1]) in ("cleared to show", "not cleared to show"), vrel + "audit.md",
                         "the newest audit*.md with ## Write detection, ## Documents appendix and its closing line")],
            "released": [((vdir / name).is_file(), vrel + name, "the frozen " + name)
                         for name in ("build.json", "backlog.md", "log.md")] + (
                [(fields.get("signed_off", "none") != "none", rel, "a signed-off event, from v1.0")]
                if vnum(version) >= (1, 0) else [])}
        rows = [row for row in ROWS[state] if row not in ("building", "fixing") or row == state]
        return [(file, row, "missing for state %s: %s" % (state, what), what)
                for row in rows for ok, file, what in checks[row] if not ok]

    def logs(self):
        """C50, C53, C137, G08, G45: entry form, the baseline, every roll against its pointer."""
        pointers = {}
        for name, groups, body, entry in self.entries:
            head = entry.split("\n", 1)[0]
            if groups is None:
                self.warn(name, "entry", "an entry header out of form: %s" % head,
                          "## YYYY-MM-DD HH:MM · <strand or -> · <type> · <version or -> · <key or session label>")
            elif groups[2] not in LOG_TYPES:
                self.warn(name, "type", "%s, in %s" % (groups[2], head), "a type record-map.md lists under The log")
            if len(body) > 5:
                self.warn(name, "entry", "%s has %d body lines" % (head, len(body)), "at most five lines")
            if values_of(body).get("rolled_to"):
                pointers[values_of(body)["rolled_to"]] = (name, values_of(body))
        record = [entry for name, _, _, entry in self.entries if name == "log.md"]
        self.baseline([mc.sha256_text(entry) for entry in record], record)
        for path in log_files(self.root)[1:]:
            rel = mc.relative(self.root, path)
            moved, fields = [e for name, _, _, e in self.entries if name == rel], self.fields(rel)
            sha, count = roll_hash(moved), str(len(moved))
            if fields is not None and (fields.get("sha256"), fields.get("entries")) != (sha, count):
                self.block(rel, "sha256", "%s moved entries hashing to %s; the front matter records %s, %s" % (
                    count, sha, fields.get("entries"), fields.get("sha256")), "the entries as rolled: history is never edited")
            pointer = pointers.pop(rel, None)
            if pointer is None:
                self.block(rel, "rolled_to", "no pointer entry names this rolled log", "the pointer entry the roll left")
            elif (pointer[1].get("sha256"), pointer[1].get("entries")) != (sha, count):
                self.block(pointer[0], "rolled_to", "the pointer to %s records %s entries, %s; the file holds %s, %s" % (
                    rel, pointer[1].get("entries"), pointer[1].get("sha256"), count, sha), "the pointer as the roll wrote it")
        for target, (name, _) in sorted(pointers.items()):
            self.block(name, "rolled_to", "the pointer names %s, which is not there" % target, "the rolled log it names")

    def baseline(self, current, record):
        """G08: the baseline must be an ordered subsequence of the record log's entry hashes."""
        if not (self.root / ".work" / "history.json").is_file():
            return self.warn(".work/history.json", "entries", "no baseline, so the log's growth cannot be proved",
                             "the baseline record.py log rebuilds at its next insert")
        data = self.json(".work/history.json")
        base, position = (data or {}).get("entries") or [], 0
        for index, sha in enumerate(base):
            while position < len(current) and current[position] != sha:
                position += 1
            if position == len(current):
                at = len(current) - (len(base) - index)
                where = record[at].split("\n", 1)[0][3:] if 0 <= at < len(record) else "entries"
                self.block("log.md", where, "an entry the baseline holds (sha256 %s) is no longer in the log: it was "
                           "changed or removed" % sha[:12], "history only grows: a correction is a new entry")
                break
            position += 1
        for sha, entry in zip(current, record) if data is not None else ():
            if sha not in base:
                self.warn("log.md", entry.split("\n", 1)[0][3:], "an entry absent from the baseline .work/history.json",
                          "entries written through record.py log")

    def raw_inputs(self):
        """C150, G13: every raw input has a save entry and still hashes to its recorded sha256."""
        for _, groups, body, _ in self.entries:
            if groups and groups[2] in ("call", "document", "email") and values_of(body).get("path"):
                self.saves[values_of(body)["path"]] = values_of(body)
        for rel, path in self.files:
            parts = rel.split("/")
            if path.name.startswith(".") or not ((parts[0] == "calls" and rel.endswith(".transcript.txt")) or (
                    parts[0] == "inputs" and len(parts) == 2 and not rel.endswith(".md"))):
                continue
            if rel not in self.saves:
                self.block(rel, "sha256", "a raw input with no save entry in log.md",
                           "a file saved through record.py add-transcript or add-document")
            elif mc.sha256_file(path) != self.saves[rel].get("sha256"):
                self.block(rel, "sha256", "the bytes no longer hash to the recorded %s: the file was edited"
                           % self.saves[rel].get("sha256"), "the file as saved: a raw input is never edited")

    def references(self):
        """C129: every fully qualified reference resolves; inside a ledger, every frozen revision exists."""
        folders = {f.name[:3]: f for f in strand_folders(self.root)}
        texts = [(rel, doc[2]) for rel, doc in self.docs.items() if "/drafts/" not in rel]
        texts += [(rel, mc.read_text(path, rel)) for rel, path in self.files if rel.endswith(".json")]
        for rel, text in texts:
            found = [(m.group(0), m.groups()) for m in REFERENCE.finditer(text)]
            ledger = folders.get(rel.split("/")[1][:3]) if rel.startswith("strands/") and rel.endswith(
                "/solution/build.json") else None
            found += [(m.group(0), (None, None, m.group(1), m.group(2), ledger)) for m in LEDGER_REF.finditer(text)
                      if ledger is not None]
            for shown, parts in found:
                folder = parts[4] if len(parts) == 5 else folders.get(parts[0])
                key, version, revision = parts[1:4]
                if folder is None:
                    ok = False
                elif key:
                    ok = key in ((self.builds.get(folder.name[:3]) or {}).get("objects") or {})
                else:
                    target = folder / "versions" / version
                    ok = (target / ("blueprint-r%s.md" % revision)).is_file() if revision else target.is_dir()
                if not ok:
                    self.block(rel, "reference", "%s does not resolve" % shown,
                               "a strand, version, frozen revision or element key of this record")

    def text_rules(self):
        """C152, C155 to C157, G30, G61: absolute paths, links, markers and internal ids, the internal line."""
        for rel, (fields, body, text) in sorted(self.docs.items()):
            parts = rel.split("/")
            drafts = len(parts) > 3 and parts[0] == "strands" and parts[2] == "drafts"
            cites = parts[0] in ("research", "calls", "inputs") or parts[0] == "strands" and parts[2:] in (
                ["readiness.md"], ["solution", "blueprint.md"])
            for number, line in enumerate(text.split("\n"), 1):
                where, hits = "line %d" % number, ABSOLUTE.findall(line)
                for token in hits:
                    self.block(rel, where, "an absolute path %s" % token, "a path relative to the record")
                for target in LINK.findall(line):
                    self.link(rel, "/".join(parts[:-1]), where, target.split("#", 1)[0], bool(hits))
                mark = drafts and (MARKER.search(line) or INTERNAL_ID.search(line))
                if mark:
                    self.block(rel, where, "%s in a draft" % mark.group(0), "drafts free of markers and internal ids")
                elif cites and QUOTE.search(line) and not LOCATION.search(line):
                    self.warn(rel, where, "a quote marker with no location", "a location on the same line: @HH:MM:SS, "
                              "@MM:SS, cue N, L<n>, paragraph <n>, §<n>, p.<n> or region")
            if not drafts and next((line for line in body.split("\n") if line.strip()), "") != INTERNAL:
                self.warn(rel, "Internal", "the first line after the front matter is not the internal line", INTERNAL)
        for rel, path in self.files:
            for number, line in enumerate(mc.read_text(path, rel).split("\n") if rel.endswith(".json") else (), 1):
                for token in ABSOLUTE.findall(line):
                    self.block(rel, "line %d" % number, "an absolute path %s" % token, "a path relative to the record")

    def link(self, rel, base, where, target, reported):
        if not target or "://" in target or target.startswith("mailto:"):
            return
        if target[:1] in "/\\~" or re.match(r"[A-Za-z]:", target):
            return None if reported else self.block(rel, where, "a link that is not relative: %s" % target,
                                                    "a link relative to the file")
        try:
            if not mc.record_path(self.root, target, base).exists():
                self.warn(rel, where, "the link %s does not resolve" % target, "a relative link to a file of the record")
        except mc.Refusal:
            self.warn(rel, where, "the link %s leaves the record" % target, "a link to a file inside the record")

    def call_types(self):
        """Intake fold 12 and 13: each of a call summary's six type-header fields reads `<value> <state>` or
        `unresolved`, its signals and candidates being the body's; `proposed`, the state word first pinned, reads as
        `assumed`, so a summary written with it passes. A missing or other value is a warning."""
        for rel, (fields, _, _) in sorted(self.docs.items()):
            if not (rel.startswith("calls/") and fields.get("schema") == "call-summary/1"):
                continue
            for key in TYPE_FIELDS:
                words = (fields.get(key) or "").split()
                if fields.get(key) != "unresolved" and not (len(words) == 2 and words[1] in TYPE_STATES):
                    self.warn(rel, key, "the field is missing" if key not in fields else "%r is not a value and its "
                              "state" % fields[key], "the value and its state, detected, assumed or confirmed, or "
                              "unresolved with its candidates and fallback under ## Call type")

    def budget(self, rule, rel):
        """(lines, how the figure was reached) of a file's budget. Intake fold 1: a call summary beside its saved
        transcript has one line per 30 words of it, at least 120 and at most 250."""
        transcript = self.root / (rel[:-len(".md")] + ".transcript.txt") if rule[0] == "calls/*.md" else None
        if transcript is None or not transcript.is_file():
            return rule[1], ""
        low, per, high = CALL_BUDGET
        words = len(transcript.read_bytes().decode("utf-8", "replace").split())
        return max(low, min(high, words // per)), " (one line per %d words of %s, at least %d and at most %d)" % (
            per, mc.relative(self.root, transcript), low, high)

    def budgets(self):
        """C138 to C140, G44: size budgets warn; SUMMARY.md past 120 and the live map past 400 lines block."""
        total, strands = 0, {}
        for rel, path in self.files:
            parts, size = rel.split("/"), path.stat().st_size
            if not (fnmatch.fnmatchcase(rel, "calls/*.transcript.txt") or (
                    parts[0] == "inputs" and len(parts) == 2 and not rel.endswith(".md"))):
                total += size
                if parts[0] == "strands" and len(parts) > 2:
                    strands[parts[1]] = strands.get(parts[1], 0) + size
            rule = next((rule for rule in BUDGETS if fnmatch.fnmatchcase(rel, rule[0])), None)
            if rule is None:
                continue
            lines, (most, how) = len(mc.read_text(path, rel).splitlines()), self.budget(rule, rel)
            if lines > most or (rule[2] and size > rule[2] * 1024):
                self.warn(rel, "budget", "%d lines, %.1f KB" % (lines, size / 1024.0),
                          "at most %d lines%s%s" % (most, ", %d KB" % rule[2] if rule[2] else "", how))
            limit = 120 if rule[0] == "strands/*/SUMMARY.md" else 400 if rel == "live/live-map.md" else None
            if limit and lines > limit:
                self.block(rel, "budget", "%d lines" % lines, "at most %d lines: blocking past it" % limit)
        if total > 4 * 1024 * 1024:
            largest = sorted(strands.items(), key=lambda item: -item[1])[:3]
            self.warn(".", "size", "the record holds %.1f MB; largest strands: %s" % (total / 1048576.0, ", ".join(
                "%s %.1f MB" % (name, size / 1048576.0) for name, size in largest) or "none"),
                "under the soft 4 MB (calls/*.transcript.txt, inputs/*.<ext> and .work/ excluded)")

    def settings(self):
        """G34: local/settings.json under the home has the settings/1 shape (warnings)."""
        path, name = mc.home() / "local" / "settings.json", "local/settings.json"
        if not path.is_file():
            return self.warn(name, "schema", "no settings file under the home", "local/settings.json from home init")
        try:
            data = mc.read_json(path, name)
        except mc.CannotRun as exc:
            return self.warnings.extend(exc.findings)
        data = data if isinstance(data, dict) else {}
        for key, test, expected in SETTINGS_SHAPE:
            if not test(data.get(key)):
                self.warn(name, key, "%s does not fit settings/1" % json.dumps(data.get(key)), expected)
        if (data.get("archive") == "github") != isinstance(data.get("github_account"), str):
            self.warn(name, "github_account", "present without the GitHub archive, or absent with it",
                      "a GitHub account only when archive is github")

    def a11(self, client):
        """G14, C141 to C146: an open A11 field blocks only at its moment, read from the record; none is filled."""
        real = sorted(path for path, values in self.saves.items() if values.get("fixture") == "no")
        for field in A11_3 if real else ():
            if client.get(field) == "unanswered":
                self.block("CLIENT.md", field, "unanswered, and a real input is saved (%s): the A11-3 question's "
                           "moment has come" % real[0], "the user's answer, asked now; record.py never fills it in")
        planned = [f.name for f in strand_folders(self.root)
                   if (self.fields("strands/%s/STRAND.md" % f.name) or {}).get("kind") in ("platform", "hybrid")
                   and (self.fields("strands/%s/solution/blueprint.md" % f.name) or {}).get("sample_rows") == "planned"]
        if client.get("build_target") == "client-account" and planned and \
                client.get("sample_data_in_account") == "unanswered":
            self.block("CLIENT.md", "sample_data_in_account", "unanswered, and strand %s plans sample rows in the "
                       "client's account: the A11-2 question's moment has come" % planned[0],
                       "the user's answer (allowed, not-allowed or not-needed); record.py never fills it in")
        if client.get("account_kind") == "sandbox":
            path = mc.home() / "local" / "sandbox-accounts.txt"
            lines = mc.read_text(path, "local/sandbox-accounts.txt").split("\n") if path.is_file() else []
            if not any(line.split("|")[0].strip() == "sandbox" for line in lines if not line.strip().startswith("#")):
                self.block("local/sandbox-accounts.txt", "sandbox", "the record is bound for write probes and no test "
                           "workspace is named: the A11-1 question's moment has come",
                           "the user names a test workspace for write probes; record.py never fills it in")

    def guard_index(self):
        """C148, C149, G30, G47: build targets inside the client's workspaces; the native index in date."""
        index = self.account.get("guard_index") or {}
        allowed = {str(workspace) for workspace in index.get("client_workspace_ids") or []}
        for strand, target in sorted((index.get("build_targets_by_strand") or {}).items()):
            for workspace in (target or {}).get("workspace_ids") or []:
                if str(workspace) not in allowed:
                    self.block("account.json", "guard_index.build_targets_by_strand", "strand %s targets workspace %s,"
                               " outside the client's workspaces" % (strand, workspace),
                               "a workspace of guard_index.client_workspace_ids (%s)" % (", ".join(sorted(allowed)) or "none"))
        captured, days = index.get("captured_at"), (index.get("record_provenance") or {}).get("staleness_budget_days")
        if captured and isinstance(days, (int, float)):
            try:
                age = (mc.now_utc() - mc.parse_utc(captured)).total_seconds() / 86400.0
            except ValueError:
                return self.warn("account.json", "guard_index.captured_at", "%r is not a UTC stamp" % captured,
                                 "YYYY-MM-DDTHH:MM:SSZ")
            if age > days:
                self.warn("account.json", "guard_index.captured_at", "the native index was captured %s, %d days ago, "
                          "past its %s-day budget" % (captured, age, days), "a fresh native-index read before guarded writes")


# Subcommands: each takes (record root, arguments) and returns (exit code, payload).

def cmd_status(root, args):
    """The status/1 object, the front door's one read (G19, G54); it changes nothing (C124)."""
    version = mc.plugin_version(PLUGIN_ROOT)
    with mc.record_mutex(root):
        try:
            client = read_doc(root, root / "CLIENT.md")[0]
        except mc.FrontMatterError as exc:
            raise mc.CannotRun(*[tuple(f[k] for k in KEYS) for f in exc.findings])
        folders = [mc.strand_dir(root, args.strand)] if args.strand else strand_folders(root)
        found, seen, live = Check(root).run(), activity(root), live_counts(root)
        interrupted = [{"strand": f.name[:3], "run_id": run.get("id"), "version": run.get("version")}
                       for f in strand_folders(root) for run in runs(root, f) if run.get("state") == "interrupted"]
        return 0, {"schema": "status/1", "generated_at": mc.stamp("utc"), "plugin_version": version,
                   "record_schema": client.get("schema"), "schema_newer": bool(found.newer), "record": client,
                   "strands": [strand_status(root, folder, seen, live) for folder in folders],
                   "lease": mc.lease_status(root), "interrupted": interrupted,
                   "findings": {"blocking": found.blocking, "warnings": found.warnings}}

def strand_status(root, folder, seen, live):
    short = folder.name[:3]
    try:
        entry = dict(read_doc(root, folder / "STRAND.md")[0])
    except (mc.FrontMatterError, mc.CannotRun):
        entry = {"strand": short}
    version, current, open_versions = entry.get("version", "none"), {}, []
    for vdir in version_folders(folder):
        try:
            fields = read_doc(root, vdir / "version.md")[0] if (vdir / "version.md").is_file() else {}
        except mc.FrontMatterError:
            fields = {}
        current = fields if vdir.name == version else current
        if fields.get("state") != "released" and fields.get("close_reason", "none") == "none":
            open_versions.append(vdir.name)
    running, run = [r for r in runs(root, folder) if r.get("state") == "running"], None
    if running:
        try:
            age = mc.heartbeat_age(running[-1].get("heartbeat_at") or "")[0]
        except ValueError:
            age = None
        run = {"id": running[-1].get("id"), "state": "running", "heartbeat_at": running[-1].get("heartbeat_at"),
               "heartbeat_age_minutes": age}
    shown = current.get("shown", "none")
    entry.update(qualified_version="%s/%s" % (short, version) if VERSION.fullmatch(version) else None,
                 purpose=current.get("purpose"), shown=[] if shown in ("none", "") else shown.split("; "),
                 signed_off=None if current.get("signed_off", "none") == "none" else current.get("signed_off"),
                 open_versions=open_versions, live_objects=live.get(short, 0), last_activity=seen.get(short), run=run)
    return entry

def cmd_check(root, args):
    found = Check(root).run()
    return 1 if found.blocking else 2 if found.warnings else 0, {"blocking": found.blocking, "warnings": found.warnings}

def cmd_log(root, args):
    """C48 to C52, G45: one entry under the header, its time from the clock, refused when out of form."""
    lines = [part for line in args.line or [] for part in line.split("\n")]
    if args.body_file:
        lines = mc.read_text(Path(args.body_file), "the body file").split("\n")
        while lines and not lines[-1].strip():
            lines.pop()
    with mc.record_mutex(root):
        refuse_newer(root)
        strands = {folder.name[:3] for folder in strand_folders(root)}
        refuse(None if args.type in LOG_TYPES else ("log.md", "type", "%s is not a log type" % args.type,
                                                    "one of the 44 types record-map.md lists under The log"),
               ("log.md", "body", "%d body lines" % len(lines), "at most five lines") if len(lines) > 5 else None,
               *[("log.md", "body", "the body line %r" % line, "body lines with text that do not open with ## ")
                 for line in lines if not line.strip() or line.startswith("## ")],
               None if one_line(args.key) and " · " not in args.key else (
                   "log.md", "key", "the key %r" % args.key, "one line without ' · '"),
               None if args.strand == "-" or args.strand in strands else (
                   "log.md", "strand", "%s is not a strand of this record" % args.strand, "a short id, or - for the record"),
               None if args.version == "-" or VERSION.fullmatch(args.version) else (
                   "log.md", "version", "%s is not a version" % args.version, "vX.Y, or -"))
        entry = new_entry(args.strand, args.type, args.version, args.key, lines)
        insert_entries(root, [entry])
    return 0, {"entry": entry.split("\n", 1)[0], "sha256": mc.sha256_text(entry)}

def guardable(rel):
    parts = rel.split("/")
    return rel.endswith(".md") and parts[0] != ".work" and parts[-1] not in ("log.md", "SUMMARY.md") \
        and not re.fullmatch(r"blueprint-r\d+\.md", parts[-1])

def cmd_guard(root, args):
    """C45 to C47: without --from, the file's sha256 as this session reads it; with --from, the staged text
    written in place after a backup, refused when the file changed since that read."""
    path = mc.record_path(root, args.file)
    rel = mc.relative(root, path)
    if args.strand:
        mc.strand_dir(root, args.strand)
    with mc.record_mutex(root):
        if args.source is None:
            if not path.is_file():
                raise mc.CannotRun((rel, "file", "no such file in the record", "an existing record file"))
            return 0, {"file": rel, "sha256": mc.sha256_file(path)}
        refuse(None if guardable(rel) else (rel, "file", "record.py guard does not write this file",
                                            "a current Markdown file: not a log, a frozen copy, SUMMARY.md or .work/"),
               None if args.expect_sha else (rel, "sha256", "no --expect-sha", "the sha256 this session read, or none"))
        staged = mc.read_text(Path(args.source), "the staging file")
        refuse_newer(root, *([path] if path.is_file() else []))
        fields, name = mc.front_matter(staged, rel), schema_for(rel)
        if name:
            mc.require_schema(fields.get("schema"), name, rel)
        if rel == "CLIENT.md":
            current = mc.front_matter(mc.read_text(path, rel), rel).get("lease")
            refuse(None if fields.get("lease") == current else (
                rel, "lease", "the staged file sets the lease mirror to %s" % fields.get("lease"), current))
        if "updated" in fields:
            staged = mc.set_front_matter(staged, {"updated": mc.stamp("minute")}, rel)
        mc.guarded_write(path, staged, root, None if args.expect_sha == "none" else args.expect_sha)
        if schema_for(rel) in ("client", "strand"):
            refresh_index(root)
        return 0, {"file": rel, "sha256": mc.sha256_file(path)}

def cmd_freeze(root, args):
    """C54, G41: freeze the working blueprint as versions/<v>/blueprint-r<N>.md; both sha256 values returned."""
    with mc.record_mutex(root):
        folder, path, rel, fields, _ = strand_doc(root, args.strand)
        version = fields.get("version", "none")
        refuse((rel, "kind", "a non-platform strand has no versions", "a platform or hybrid strand")
               if fields.get("kind") == "non-platform" else None,
               None if VERSION.fullmatch(version) else (rel, "version", "the strand has no version", "an opened version"))
        vpath = folder / "versions" / version / "version.md"
        refuse_newer(root, vpath)
        vrel, revision = mc.relative(root, vpath), read_doc(root, vpath)[0].get("revision", "none")
        refuse(None if revision.isdigit() else (vrel, "revision", "no revision to freeze (%s)" % revision,
                                                "the revision number the blueprint step wrote"))
        source = folder / "solution" / "blueprint.md"
        if not source.is_file():
            raise mc.CannotRun((mc.relative(root, source), "file", "no working blueprint", "solution/blueprint.md"))
        data = source.read_bytes()
        working, frozen = hashlib.sha256(data).hexdigest(), vpath.parent / ("blueprint-r%s.md" % revision)
        frel = mc.relative(root, frozen)
        try:
            with open(frozen, "xb") as handle:
                handle.write(data)
        except FileExistsError:
            refuse((frel, "revision", "revision %s is frozen already" % revision, "a new revision for a changed blueprint"))
        copied = mc.sha256_file(frozen)
        if copied != working:
            raise mc.CannotRun((frel, "sha256", "the copy hashes to %s, the blueprint to %s" % (copied, working),
                                "two equal values"))
        write_fm(root, vpath, {"sha256": copied})
        # Demos' fixes, 5: the freeze logs itself, as the other writing commands do; the frozen copy and version.md
        # are written by then, so a failed log write says so and how to finish rather than reading as nothing done.
        short = folder.name[:3]
        entry = new_entry(short, "blueprint", version, "r%s" % revision, ["frozen: %s · sha256: %s" % (frel, copied)])
        committed({"frozen_file": frel, "frozen_sha256": copied, "entries": [entry]}, "the freeze of revision %s" % (
            revision), [lambda: insert_entries(root, [entry])], file="log.md")
    return 0, {"strand": args.strand, "version": version, "revision": revision, "working_sha256": working,
               "frozen_sha256": copied, "frozen_file": frel, "entry": entry.split("\n", 1)[0]}

def cmd_add(root, args, transcript):
    """C55 to C62, G12 to G14: a raw input saved byte for byte at record level, never over a file, with its
    sha256 in a save entry; a real input is refused while the A11-3 fields are unanswered."""
    source = Path(args.source)
    if not source.is_file():
        raise mc.CannotRun((source.name, "file", "the file to save is not there", "an existing file"))
    data, kind = source.read_bytes(), "transcript" if transcript else args.kind
    sha, name, limit = hashlib.sha256(data).hexdigest(), args.type if transcript else args.title, 24 if transcript else 40
    extension, place = (".transcript.txt", "calls/") if transcript else (source.suffix.lower(), "inputs/")
    date = args.date or mc.stamp("date")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        date = None
    with mc.record_mutex(root):
        refuse_newer(root)
        mc.strand_dir(root, args.strand)
        client = read_doc(root, root / "CLIENT.md")[0]
        saves = {}
        for _, groups, body, _ in entries_in(root):
            if groups and groups[2] in ("call", "document", "email") and values_of(body).get("path"):
                saves[values_of(body)["path"]] = values_of(body)
        same = next((path for path, values in saves.items() if values.get("sha256") == sha), None)
        came = mc.relative(root, mc.record_path(root, args.came_with)) if getattr(args, "came_with", None) else None
        refuse(None if SLUG.fullmatch(name) and len(name) <= limit else (
                   place, "type" if transcript else "title", "%r breaks the naming rule" % name,
                   "lowercase ASCII words joined by hyphens, at most %d characters" % limit),
               None if date else (place, "date", "%r is not a date" % args.date, "YYYY-MM-DD"),
               None if kind in ("transcript", "document", "email") else (place, "kind", "%r" % kind, "document | email"),
               (place, "extension", "a .md document would collide with its snapshot", "save the copy as .txt")
               if extension == ".md" else None,
               (place, "extension", "the file has no extension", "a file extension") if not extension else None,
               (place, "extension", "an email arrives as pasted text or a screenshot, not %s" % extension,
                ", ".join(EMAIL_EXTENSIONS)) if kind == "email" and extension not in EMAIL_EXTENSIONS else None,
               (same, "sha256", "these bytes are saved already as %s" % same, "a file not saved before" + (
                   "; a corrected call type keeps the stem: call_type changes in the summary and the correction is "
                   "logged" if transcript else "")) if same else None,  # intake fold 14: a raw file is saved once
               (place, "came_with", "%s is not a saved email input" % came, "inputs/<an email saved before>")
               if came and (kind != "document" or saves.get(came, {}).get("input_kind") != "email") else None,
               (place, "redactions", "%d" % args.redactions, "zero or more") if args.redactions < 0 else None,
               *[("CLIENT.md", field, "unanswered, and saving a real input is the moment it matters: how transcripts "
                  "and documents are kept at close, and redacted, is the open A11-3 question",
                  "the user's answer recorded first, or --fixture for a fictional input")
                 for field in A11_3 if not args.fixture and client.get(field) == "unanswered"])
        folder = root / place.rstrip("/")
        folder.mkdir(parents=True, exist_ok=True)
        count, stem = 1, "%s-%s" % (date, name)
        while True:
            candidate = stem if count == 1 else "%s-%d" % (stem, count)
            path = folder / (candidate + extension)
            if any(p.name.startswith(candidate + ".") for p in folder.iterdir()):
                count += 1
                continue
            try:
                with open(path, "xb") as handle:
                    handle.write(data)
                break
            except FileExistsError:
                count += 1
        rel = mc.relative(root, path)
        body = ["path: " + rel, "sha256: " + sha, "input_kind: %s · fixture: %s · asked_by: %s · redactions: %d" % (
            kind, "yes" if args.fixture else "no", args.strand, args.redactions)] + (["came_with: " + came] if came else [])
        insert_entries(root, [new_entry("-", "call" if transcript else kind, "-", candidate, body)])
        write_fm(root, root / "CLIENT.md", {"last_input": candidate})
    result = {"path": rel, "sha256": sha, "stem": candidate, "input_kind": kind, "fixture": args.fixture}
    if path.suffix == ".txt":
        result["lines"] = len(data.decode("utf-8-sig", "replace").splitlines())
    return 0, result

def next_ordinal(root):
    return 1 + max([int(f.name[:3]) for f in strand_folders(root)] or [0])

def strand_reasons(root, topic, title, kind, reason, output, depends):
    """G43, G56: why a new strand would be refused (topic, kind, output class, title, reason, dependencies)."""
    shorts = {f.name[:3] for f in strand_folders(root)}
    return [None if SLUG.fullmatch(topic) and len(topic) <= 24 else (
                "strands/", "topic", "%r breaks the topic rule" % topic,
                "lowercase ASCII words joined by hyphens, at most 24 characters"),
            None if kind in OUTPUT_CLASS else ("strands/", "kind", "%r" % kind, "platform | non-platform | hybrid"),
            None if output in OUTPUT_CLASS.values() else ("strands/", "output_class", "%r" % output,
                                                          " | ".join(OUTPUT_CLASS.values())),
            None if one_line(title, bar=True) else ("strands/", "title", "%r" % title, "one line, no |"),
            None if one_line(reason) else ("strands/", "opened_reason", "no reason in one line", "why it opened"),
            None if depends == "none" or all(part.strip() in shorts for part in depends.split(",")) else (
                "strands/", "depends_on", "%s names a strand this record lacks" % depends, "none, or short ids"),
            None if next_ordinal(root) <= 999 else ("strands/", "strand", "no ordinal left after 999", "a new record")]

def strand_files(short, topic, title, kind, output, reason, depends):
    """G43: STRAND.md, readiness.md and solution/exclusions.md filled from the templates (exit 3 if one is missing)."""
    values = dict.fromkeys(("version", "version_state", "clearance", "override", "round", "workspaces", "next_step",
                            "summary_current_to", "closed"), "none")
    values.update(strand=short, slug="%s-%s" % (short, topic), title=title, kind=kind, output_class=output,
                  opened=mc.stamp("date"), opened_reason=reason, state="active", stage="new", depends_on=depends)
    return {"STRAND.md": fill("STRAND.md", values), "readiness.md": fill("readiness.md", {"clearance": "none"}),
            "solution/exclusions.md": fill("exclusions.md", {"strand": short})}

def place_strand(root, short, topic, kind, reason, files):
    """Write a new strand's files, its `opened` entry and the index (G06); returns the folder."""
    folder = root / "strands" / ("%s-%s" % (short, topic))
    (folder / "solution").mkdir(parents=True)
    for name, text in files.items():
        mc.write_file(mc.record_path(folder, name), text, root)
    insert_entries(root, [new_entry(short, "strand", "-", "opened", ["kind: %s · reason: %s" % (kind, reason)])])
    refresh_index(root, opened=short)
    return folder

def cmd_strand_open(root, args):
    """C63 to C69, G43, G56: the next ordinal, STRAND.md, readiness.md and solution/exclusions.md from the
    templates, an `opened` log entry and the index; no versions/, blueprint.md or build.json for any kind."""
    kind, depends = args.kind, args.depends_on or "none"
    output = args.output_class or OUTPUT_CLASS.get(kind, "")
    with mc.record_mutex(root):
        refuse_newer(root)
        refuse(*strand_reasons(root, args.topic, args.title, kind, args.reason, output, depends))
        short = "%03d" % next_ordinal(root)
        folder = place_strand(root, short, args.topic, kind, args.reason,
                              strand_files(short, args.topic, args.title, kind, output, args.reason, depends))
    return 0, {"strand": short, "slug": folder.name, "folder": mc.relative(root, folder), "kind": kind,
               "output_class": output}

def cmd_strand_list(root, args):
    """C70, G25: the nine index cells of every strand."""
    names = ("strand", "title", "kind", "state", "version", "version_state", "clearance", "live_objects", "last_activity")
    with mc.record_mutex(root):
        return 0, {"strands": [dict(zip(names, row)) for row in index_rows(root)]}

def cmd_strand_pause(root, args):
    """C71, G52: an active strand that does not hold the lease goes to paused, with the user's words."""
    with mc.record_mutex(root):
        folder, path, rel, fields, text = strand_doc(root, args.strand)
        refuse(None if fields.get("state") == "active" else (rel, "state", "the strand is %s" % fields.get("state"),
                                                             "an active strand"),
               holds_lease(root, args.strand),
               None if one_line(args.reason) else (rel, "reason", "no reason in one line", "the user's words, one line"))
        line = "- paused %s by the user: %s" % (mc.stamp("date"), args.reason)
        mc.write_file(path, set_block(mc.set_front_matter(text, {"state": "paused"}, rel), "## Paused", [line]), root)
        insert_entries(root, [new_entry(args.strand, "strand", "-", "paused", ["by the user: " + args.reason])])
        refresh_index(root)
    return 0, {"strand": args.strand, "state": "paused"}

def cmd_strand_resume(root, args):
    """G05: the one way from paused back to active, once its run has ended and it holds no lease."""
    with mc.record_mutex(root):
        folder, path, rel, fields, text = strand_doc(root, args.strand)
        live = [run.get("id") for run in runs(root, folder) if run.get("state") in ("running", "interrupted")]
        refuse(None if fields.get("state") == "paused" else (rel, "state", "the strand is %s" % fields.get("state"),
                                                             "a paused strand"),
               (mc.relative(root, folder / "solution" / "build.json"), "runs", "run %s has not ended" % live[0],
                "the run ended by the ordinary recovery first") if live else None,
               holds_lease(root, args.strand))
        line = "none (resumed %s)" % mc.stamp("date")
        mc.write_file(path, set_block(mc.set_front_matter(text, {"state": "active"}, rel), "## Paused", [line]), root)
        insert_entries(root, [new_entry(args.strand, "strand", "-", "resumed", ["state: paused to active"])])
        refresh_index(root)
    return 0, {"strand": args.strand, "state": "active"}

def cmd_strand_kind(root, args):
    """C72: the kind changes only while the strand has no versions, with a `strand` log entry; a stage that is
    not on the new kind's ladder goes back to `new`."""
    with mc.record_mutex(root):
        folder, path, rel, fields, text = strand_doc(root, args.strand)
        old, output = fields.get("kind"), args.output_class or OUTPUT_CLASS.get(args.kind)
        versions = [v.name for v in version_folders(folder)] or ([] if fields.get("version", "none") == "none"
                                                                  else [fields["version"]])
        refuse(None if args.kind in OUTPUT_CLASS else (rel, "kind", "%r" % args.kind, "platform | non-platform | hybrid"),
               (rel, "kind", "the strand is %s already" % old, "a different kind") if args.kind == old else None,
               (rel, "version", "the strand has versions (%s)" % ", ".join(versions),
                "a strand with no versions: a fresh strand otherwise") if versions else None,
               (rel, "state", "the strand is closed", "an open strand") if fields.get("state") == "closed" else None,
               None if output in OUTPUT_CLASS.values() else (rel, "output_class", "%r" % output,
                                                             " | ".join(OUTPUT_CLASS.values())),
               None if one_line(args.reason) else (rel, "reason", "no reason in one line", "the user's words, one line"))
        updates = {"kind": args.kind, "output_class": output}
        if fields.get("stage") not in LADDER[args.kind]:
            updates["stage"] = "new"
        mc.write_file(path, mc.set_front_matter(text, updates, rel), root)
        body = ["kind: %s to %s · reason: %s" % (old, args.kind, args.reason)] + (
            ["stage: %s to new" % fields.get("stage")] if "stage" in updates else [])
        insert_entries(root, [new_entry(args.strand, "strand", "-", "kind", body)])
        refresh_index(root)
    return 0, {"strand": args.strand, "kind": args.kind, "output_class": output, "stage": updates.get("stage",
                                                                                                     fields.get("stage"))}

def roll(root, target, short, version, why):
    """G08: write `target`, a new rolled log of the record log's entries at strand `short` (and at `version`, when
    one is given); returns (the moved entries, their roll hash, the target's record-relative name)."""
    log = mc.read_text(root / "log.md", "log.md")
    moved = [entry for entry in split_log(log)[1] if (entry_parts(entry)[0] or ("",) * 5)[1] == short
             and version in (None, (entry_parts(entry)[0] or ("",) * 5)[3])]
    sha, trel = roll_hash(moved), mc.relative(root, target)
    head = front_text([("schema", "log/1"), ("client", mc.front_matter(log, "log.md").get("client", "")),
                       ("strand", short), ("version", version or "none"), ("rolled_at", mc.stamp("minute")),
                       ("entries", str(len(moved))), ("sha256", sha)])
    mc.write_file(target, head + "%s\n\n# Log: strand %s\nRolled from the record log when %s. Entries are never "
                  "edited.\n%s" % (INTERNAL, short + (", " + version if version else ""), why,
                                   "".join(["\n"] + moved).rstrip("\n") + "\n" if moved else ""), root)
    return moved, sha, trel

def cmd_strand_close(root, args):
    """C73 to C78, G07, G08: refused while the strand holds the lease, is paused, has a version building or
    fixing, or an unreleased version without a close reason; otherwise its entries roll into
    strands/<id>/log.md, one pointer stays behind, and the strand is closed. Nothing is archived."""
    with mc.record_mutex(root):
        folder, path, rel, fields, _ = strand_doc(root, args.strand)
        versions = [v / "version.md" for v in version_folders(folder) if (v / "version.md").is_file()]
        refuse_newer(root, *versions)
        found = [(mc.relative(root, v), read_doc(root, v)[0]) for v in versions]
        target = folder / "log.md"
        refuse(holds_lease(root, args.strand),
               (rel, "state", "the strand is paused", "resume it first (record.py strand resume)")
               if fields.get("state") == "paused" else None,
               (rel, "state", "the strand is closed already", "an open strand") if fields.get("state") == "closed" else None,
               *[(vrel, "state", "version %s is %s" % (v.get("version"), v.get("state")), "no version building or fixing")
                 for vrel, v in found if v.get("state") in ("building", "fixing")],
               *[(vrel, "close_reason", "version %s is unreleased and has no close reason" % v.get("version"),
                  "a release, or the reason client-closeout records through guard")
                 for vrel, v in found if v.get("state") != "released" and v.get("close_reason", "none") == "none"],
               (mc.relative(root, target), "log.md", "the strand's rolled log exists already", "a strand never rolled")
               if target.exists() else None)
        moved, sha, trel = roll(root, target, args.strand, None, "the strand closed")
        pointer = new_entry(args.strand, "strand", "-", "closed", ["rolled_to: " + trel,
                                                                    "entries: %d · sha256: %s" % (len(moved), sha)])
        insert_entries(root, [pointer], removed=moved)
        write_fm(root, path, {"state": "closed", "stage": "closed", "closed": mc.stamp("date")})
        refresh_index(root)
    return 0, {"strand": args.strand, "rolled_to": trel, "entries": len(moved), "sha256": sha}

def summary_plan(root, folder, draft):
    """G42: the SUMMARY.md a draft becomes, front matter set from STRAND.md and the released versions, and
    the reasons it is refused (headings, the non-platform block, more than 80 lines)."""
    rel, fields = mc.relative(root, folder / "SUMMARY.md"), read_doc(root, folder / "STRAND.md")[0]
    released = [v.name for v in version_folders(folder) if (v / "version.md").is_file()
                and read_doc(root, v / "version.md")[0].get("state") == "released"]
    try:
        body = mc.split_front_matter(draft)[1].strip("\n")
    except mc.FrontMatterError:
        body = draft.strip("\n")
    if next((line for line in body.split("\n") if line.strip()), "") != INTERNAL:
        body = INTERNAL + "\n\n" + body
    text = front_text([("schema", "summary/1"), ("strand", folder.name[:3]), ("title", fields.get("title", "")),
                       ("kind", fields.get("kind", "")), ("versions", ", ".join(released) or "none"),
                       ("closed", fields.get("closed", "none")), ("summary_current_to", (released or ["none"])[-1]),
                       ("budget_lines", "80")]) + body + "\n"
    found, lines = [line.rstrip() for line in body.split("\n") if line.startswith("## ")], len(text.splitlines())
    return text, [reason for reason in (
        None if found == list(SUMMARY_HEADINGS) else (rel, "headings", "the blocks read: %s" % (
            "; ".join(h[3:] for h in found) or "none"), "; ".join(h[3:] for h in SUMMARY_HEADINGS)),
        (rel, "What was built", "the non-platform strand's built block lacks the fixed words",
         "nothing built inside the product") if fields.get("kind") == "non-platform" and
        "nothing built inside the product" not in section(body, SUMMARY_HEADINGS[2]).lower() else None,
        (rel, "budget_lines", "%d lines" % lines, "at most 80 lines") if lines > 80 else None) if reason]

def cmd_strand_summary(root, args):
    """C79 to C81, G42: --plan validates the session's draft and stores it with its sha; --apply <sha> writes
    SUMMARY.md from that stored plan, the user's yes having been given to that sha."""
    with mc.record_mutex(root):
        folder, path, rel, _, _ = strand_doc(root, args.strand)
        target, plan = folder / "SUMMARY.md", root / ".work" / "strands" / folder.name / "summary-plan.md"
        refuse_newer(root, *([target] if target.is_file() else []))
        prel = mc.relative(root, plan)
        if args.plan:
            text, reasons = summary_plan(root, folder, mc.read_text(Path(args.plan), "the draft"))
            refuse(*reasons)
            mc.write_file(plan, text, root, backup=False)
            return 0, {"strand": args.strand, "plan": prel, "sha256": mc.sha256_file(plan), "lines": len(text.splitlines())}
        refuse(None if plan.is_file() else (prel, "sha256", "no stored plan", "record.py strand summary --plan first"))
        stored, sha = mc.read_text(plan, prel), mc.sha256_file(plan)
        text, reasons = summary_plan(root, folder, stored)
        refuse(None if sha == args.apply else (prel, "sha256", "the stored plan hashes to %s, not %s" % (sha, args.apply),
                                               "the sha the plan step printed, which the user said yes to"),
               *reasons, None if text == stored or reasons else (prel, "summary_current_to", "the strand changed since "
                                                                 "the plan was made", "a fresh plan"))
        existed = target.is_file()
        mc.guarded_write(target, text, root, mc.sha256_file(target) if existed else None)
        current = mc.front_matter(text)["summary_current_to"]
        write_fm(root, path, {"summary_current_to": current})
        insert_entries(root, [new_entry(args.strand, "summary", "-" if current == "none" else current,
                                        "refreshed" if existed else "written",
                                        ["lines: %d · sha256: %s" % (len(text.splitlines()), mc.sha256_file(target))])])
        refresh_index(root)
    return 0, {"strand": args.strand, "file": mc.relative(root, target), "summary_current_to": current,
               "lines": len(text.splitlines())}


# Part 2: the lease, versions, the card, home init and init.

def lease_free(root):
    """C166, C171: a release or a condense waits while any strand holds the build lease (A9.8)."""
    lock = mc.read_lock(root)
    if lock.get("state") != "held":
        return None
    return (".work/lock.json", "state", "strand %s (%s) holds the build lease for %s, session %s, and a build may be "
            "writing the account" % (lock.get("strand"), lock.get("strand_title"), lock.get("version"),
                                     lock.get("session_label")),
            "the lease released by its session, or broken if it is stale")

FINISH = ("finish by hand: each entry under committed.entries that log.md lacks, through record.py log (its header "
          "gives the strand, type, version and key, its lines the --line values); then record.py check")

def committed(done, what, steps, remedy=FINISH, file=".work/lock.json"):
    """Run the writes that follow a committed lease change (or, with `file`, another committed write); a failure is
    exit 3 carrying what was committed and how to finish (finding 4), never a bare error that reads as if nothing had
    happened."""
    try:
        for step in steps:
            step()
    except Exception as exc:
        why = exc.findings[0]["problem"] if isinstance(exc, mc.MMBError) else "%s: %s" % (type(exc).__name__, exc)
        raise mc.CannotRun((file, "committed", "%s was committed, then a later write failed: %s" % (
            what, why), remedy), committed=done)

def cmd_lease_take(root, args):
    """C87 to C94, G50: take the build lease for a strand through mmb_common; the minted label is returned once."""
    with mc.record_mutex(root):
        refuse_newer(root, mc.strand_dir(root, args.strand) / "STRAND.md")
        refuse(None if args.kind == "build" else (".work/lock.json", "kind", "%r" % args.kind, "build, the one kind"))
        taken = mc.lease_take(root, args.strand)
        entry = new_entry(args.strand, "lease", taken["version"], taken["session_label"], ["taken, epoch %d" % taken["epoch"]])
        committed(dict(taken, entries=[entry]), "the take of epoch %d, session %s" % (
            taken["epoch"], taken["session_label"]), [lambda: insert_entries(root, [entry])],
            "hold epoch %d and session label %s in this session, as a take's output; then %s" % (
                taken["epoch"], taken["session_label"], FINISH))
    return 0, dict(taken, carry="hold the epoch and the label in this session: refresh, release and break present them")

def cmd_lease_refresh(root, args):
    """C90, C96, G50: move the heartbeat, and take the run id once; no log entry and no history entry."""
    return 0, mc.lease_refresh(root, args.epoch, args.label, args.run_id)

def cmd_lease_release(root, args):
    """C90, C98: the holder's session releases the lease, with a `lease` entry at the strand's position."""
    with mc.record_mutex(root):
        refuse_newer(root)
        lock = mc.read_lock(root)
        done = mc.lease_release(root, args.epoch, args.label)
        entry = new_entry(lock["strand"], "lease", lock["version"], args.label, ["released, epoch %s" % done["epoch"]])
        committed(dict(done, entries=[entry]), "the release of epoch %s" % done["epoch"],
                  [lambda: insert_entries(root, [entry])])
    return 0, done

def cmd_lease_status(root, args):
    """C99: the lease block of status --json."""
    return 0, mc.lease_status(root)

def cmd_lease_sync(root, args):
    """Finding 5: rewrite both lease mirrors from the lock, the lock unchanged; no log entry, nothing changed in the
    lease itself."""
    with mc.record_mutex(root):
        refuse_newer(root)
        return 0, mc.lease_sync(root)

def cmd_lease_repair(root, args):
    """Finding 6: rebuild a missing, torn or malformed lock with the user's yes, never by a delete, and log it at
    record level; the output's `next` names the take that comes next."""
    with mc.record_mutex(root):
        refuse_newer(root, skip=(mc.LOCK_REL,))
        done = mc.lease_repair(root, args.user_yes)
        mirror, kept = done["mirror"], done["reserved_for"]
        entry = new_entry("-", "lease", "-", "repaired", [
            "repaired, epoch %d · state: %s · from: lock backup %s" % (done["epoch"], done["state"], done["from_backup"]),
            "mirror: epoch %s, strand %s, session %s" % (mirror.get("epoch"), mirror.get("strand"),
                                                         mirror.get("session_label")),
            'next take: %s · the user: "%s"' % ("strand " + kept if kept else "any strand", args.user_yes)])
        committed(dict(done, entries=[entry]), "the lock repair at epoch %d" % done["epoch"],
                  [lambda: insert_entries(root, [entry])])
    return 0, dict(done, next="strand %s takes the lease in a fresh session and runs the ordinary recovery: record.py "
                   "lease take --strand %s" % (kept, kept) if kept else "any strand may take the lease")

def cmd_lease_break(root, args):
    """C101 to C113, G03, G04: break a stale lease when all five conditions hold; three `lease` entries carry the
    choice (record level, the holder's position, the taker's), and a park pauses the holder with what is unresolved."""
    words = [(flag, value) for flag, value in (("user_yes", args.user_yes), ("park_yes", args.park_yes)) if value]
    with mc.record_mutex(root):
        lock = mc.read_lock(root)
        taker = [f for f in strand_folders(root) if f.name[:3] == args.for_strand]
        refuse(None if taker else (".work/lock.json", "for_strand", "%s is not a strand of this record" % args.for_strand,
                                   "the short id of the strand that wants the lease"),
               *[(".work/lock.json", flag, "the user's words span lines", "the user's words on one line")
                 for flag, value in words if not one_line(value)])
        held = [mc.strand_dir(root, lock["strand"]) / "STRAND.md"] if lock.get("state") == "held" else []
        refuse_newer(root, taker[0] / "STRAND.md", *held)
        result = mc.lease_break(root, args.epoch, args.label, args.for_strand, args.user_yes, args.account_id,
                                args.choice, args.park_yes)
        old, park, broken = result["holder"], args.choice == "park", result["broken_epoch"]
        holder, version, label = old["strand"], old["version"], old["session_label"]
        counts = ", ".join("%s %s" % item for item in sorted(result["reconcile"].items())) or "none"
        entries = [new_entry("-", "lease", "-", label, [
            "broken: epoch %d · holder: %s (%s) %s · run: %s" % (broken, holder, old["strand_title"], version,
                                                                old["run_id"] or "none"),
            "reconcile: " + counts, 'choice: %s · for: %s · the user: "%s"' % (args.choice, args.for_strand, args.user_yes)]
            + (['park: "%s"' % args.park_yes] if park else [])),
            new_entry(holder, "lease", version, label, ["broken, epoch %d · choice: %s · for: %s" % (
                broken, args.choice, args.for_strand)] + (["paused: what is unresolved is in STRAND.md"] if park else []))]
        if args.for_strand != holder:
            entries.append(new_entry(args.for_strand, "lease", "-", label, [
                "broke the lease of %s %s, epoch %d · choice: %s" % (holder, version, broken, args.choice)]))
        path, rel = (held[0], mc.relative(root, held[0])) if park else (None, None)
        line = '- parked %s by a lease break for strand %s: run %s, version %s, reconcile %s; the user: "%s"' % (
            mc.stamp("date"), args.for_strand, old["run_id"] or "none", version, counts, args.park_yes)
        steps = [lambda: mc.write_file(path, set_block(mc.set_front_matter(mc.read_text(path, rel), {"state": "paused"},
                                                                           rel), "## Paused", [line]), root)] if park else []
        committed(dict(result, entries=entries, park_line=line if park else None),
                  "the break of epoch %d (choice %s, for strand %s)" % (broken, args.choice, args.for_strand),
                  steps + [lambda: insert_entries(root, entries)] + ([lambda: refresh_index(root)] if park else []),
                  FINISH.replace("; then", "; %s set to paused with committed.park_line under ## Paused, through "
                                 "record.py guard; then" % rel) if park else FINISH)
    then = (args.for_strand, "takes the lease") if park else (holder, "takes the lease in a fresh session and runs "
                                                                      "the ordinary recovery")
    return 0, dict(result, paused=holder if park else None, entries=[e.split("\n", 1)[0][3:] for e in entries],
                   next="strand %s %s: record.py lease take --strand %s" % (then[0], then[1], then[0]))


# G23, open with the user: what makes a version v1.0. The recommended default is built, and the whole choice is
# these three functions: purpose follows the version number only, so a signed-off v0.x stays a proof of concept
# and the next step proposed is opening v1.0. The alternative (the event makes that version the working solution)
# is sign_off_updates returning {"purpose": "working-solution"} for a v0.x, and next_version returning v1.0 once
# a v0.x of the strand carries a signed-off event.

def purpose_for(version):
    """C159: the purpose `version open` writes, proof-of-concept below v1.0 and working-solution from v1.0."""
    return "working-solution" if vnum(version) >= (1, 0) else "proof-of-concept"

def sign_off_updates(version):
    """(version.md fields a signed-off event sets beyond `signed_off`, the next step it proposes)."""
    if vnum(version) >= (1, 0):
        return {}, "release %s when the user says so: record.py version release" % version
    return {}, "open v1.0 for the working solution: record.py version open --version v1.0"

def next_version(highest):
    """The version `version open` opens when none is named: the next minor after the highest, v0.1 first."""
    return "v0.1" if highest is None else "v%d.%d" % (highest[0], highest[1] + 1)


ASSUMPTION = re.compile(r"^- (.+) \[kind: ([a-z-]+); state: ([a-z-]+)\]\s*$")
STRUCTURAL = ("automation-condition", "board-architecture", "leaning")

def is_date(text):
    try:
        return bool(re.fullmatch(DATE[0], text or "")) and bool(datetime.strptime(text, "%Y-%m-%d"))
    except ValueError:
        return False

def unconfirmed(root, folder):
    """G21: the strand's structural assumptions (automation condition, board architecture, a leaning) still
    `assumed` under `## Assumptions` in readiness.md, each with its question."""
    path = folder / "readiness.md"
    lines = section(read_doc(root, path)[1], "## Assumptions").split("\n") if path.is_file() else []
    found = []
    for index, line in enumerate(lines):
        match = ASSUMPTION.match(line.rstrip())
        if match and match.group(2) in STRUCTURAL and match.group(3) == "assumed":
            after = lines[index + 1].strip() if index + 1 < len(lines) else ""
            found.append({"statement": match.group(1), "kind": match.group(2),
                          "question": after[len("question:"):].strip() if after.startswith("question:") else None})
    return found

def add_event(text, lines):
    """G20: `lines` at the end of the `## Events` block of version.md, the block appended when absent."""
    rows = text.rstrip("\n").split("\n")
    if "## Events" not in rows:
        rows += ["", "## Events"]
    start = rows.index("## Events") + 1
    end = next((i for i in range(start, len(rows)) if rows[i].startswith("## ")), len(rows))
    while end > start and not rows[end - 1].strip():
        end -= 1
    rows[end:end] = [""] + lines
    return "\n".join(rows) + "\n"

def cmd_version_open(root, args):
    """C158, C159, G25: versions/<v>/version.md from the template, state planned and its purpose from the number,
    and STRAND.md pointed at it; the default is the next minor, and a version not above the highest is refused."""
    with mc.record_mutex(root):
        folder, path, rel, fields, text = strand_doc(root, args.strand)
        short, existing = folder.name[:3], [vnum(v.name) for v in version_folders(folder)]
        version = args.version or next_version(existing[-1] if existing else None)
        valid = bool(VERSION.fullmatch(version)) and "v%d.%d" % vnum(version) == version
        refuse((rel, "kind", "a non-platform strand has no versions", "a platform or hybrid strand")
               if fields.get("kind") == "non-platform" else None,
               (rel, "state", "the strand is closed", "an open strand") if fields.get("state") == "closed" else None,
               None if valid else (rel, "version", "%r is not a version" % version, "vX.Y, without leading zeros"),
               (rel, "version", "%s is not above %s, the highest opened" % (version, "v%d.%d" % existing[-1]),
                "a version above every opened one") if valid and existing and vnum(version) <= existing[-1] else None)
        vpath, purpose = folder / "versions" / version / "version.md", purpose_for(version)
        new = fill("version.md", dict(strand=short, version=version, qualified_version="%s/%s" % (short, version),
                                      state="planned", purpose=purpose, revision="none", sha256="none",
                                      opened=mc.stamp("date"), released="none", shown="none", signed_off="none",
                                      close_reason="none"))
        vpath.parent.mkdir(parents=True)
        mc.write_file(vpath, new, root)
        mc.write_file(path, mc.set_front_matter(text, {"version": version, "version_state": "planned"}, rel), root)
        insert_entries(root, [new_entry(short, "version", version, "opened", ["purpose: %s · state: planned" % purpose])])
        refresh_index(root)
    return 0, {"strand": short, "version": version, "qualified_version": "%s/%s" % (short, version), "purpose": purpose,
               "file": mc.relative(root, vpath)}

def cmd_version_mark(root, args):
    """C160 to C165, G20 to G24: a `shown` or `signed-off` event on an audited or released version. A signed-off
    event first lists the unconfirmed structural assumptions; the list warns and never refuses: without --go-on a
    non-empty list records nothing and exits 2, and with it the event is recorded with the list kept beside it."""
    event, date = args.event, args.date or mc.stamp("date")
    with mc.record_mutex(root):
        folder, path, rel, fields, _ = strand_doc(root, args.strand)
        short, version = folder.name[:3], args.version or fields.get("version", "none")
        vpath = folder / "versions" / version / "version.md" if VERSION.fullmatch(version) else None
        vrel, vfields, vtext = mc.relative(root, vpath) if vpath else rel, {}, ""
        if vpath and vpath.is_file():
            refuse_newer(root, vpath)
            vfields, _, vtext = read_doc(root, vpath)
        shown = event == "shown"
        refuse(None if event in ("shown", "signed-off") else (rel, "event", "%r" % event, "shown | signed-off"),
               (rel, "kind", "a non-platform strand has no versions", "a platform or hybrid strand")
               if fields.get("kind") == "non-platform" else None,
               (rel, "state", "the strand is closed", "an open strand") if fields.get("state") == "closed" else None,
               None if vfields else (vrel, "version", "no version %s in strand %s" % (version, short), "an opened version"),
               None if not vfields or vfields.get("state") in ("audited", "released") else (
                   vrel, "state", "version %s is %s" % (version, vfields.get("state")), "an audited or released version"),
               None if is_date(date) else (vrel, "date", "%r is not a date" % date, "YYYY-MM-DD"),
               None if one_line(args.words) else (vrel, "words", "no words in one line", "the user's words, one line"),
               None if one_line(args.audience if shown else args.by) else (
                   vrel, "audience" if shown else "by", "no role in one line",
                   "who saw it, by role" if shown else "who signed off, by role"))
        listed, after = [] if shown else unconfirmed(root, folder), None
        if listed and not args.go_on:
            return 2, {"strand": short, "version": version, "event": event, "date": date, "recorded": False,
                       "unconfirmed": listed, "next": "show the list to the user; if they go on, the same call with "
                                                     "--go-on records the event with the list kept beside it"}
        if shown:
            account = args.account or read_doc(root, root / "CLIENT.md")[0].get("monday_account_slug", "none")
            before = vfields.get("shown", "none")
            updates = {"shown": date if before in ("none", "") else before + "; " + date}
            lines = ["### shown " + date, "- audience: " + args.audience, "- account: " + account,
                     '- words: "%s"' % args.words]
            body = ["audience: %s · account: %s" % (args.audience, account), 'words: "%s"' % args.words]
            stage = "signed-off" if fields.get("stage") == "signed-off" else "shown"
        else:
            extra, after = sign_off_updates(version)
            updates = dict(extra, signed_off=date)
            lines = ["### signed-off " + date, "- by: " + args.by, '- words: "%s"' % args.words] + (
                ["- unconfirmed structural assumptions:"] + ["  - %s [kind: %s; state: assumed]" % (
                    item["statement"], item["kind"]) for item in listed] if listed else
                ["- unconfirmed structural assumptions: none"])
            body = ["by: %s · unconfirmed structural assumptions: %d" % (args.by, len(listed)), 'words: "%s"' % args.words]
            stage = "signed-off"
        mc.write_file(vpath, add_event(mc.set_front_matter(vtext, updates, vrel), lines), root)
        if stage != fields.get("stage"):
            write_fm(root, path, {"stage": stage})
        insert_entries(root, [new_entry(short, event, version, date, body)])
        refresh_index(root)
        purpose = read_doc(root, vpath)[0].get("purpose")
    payload = {"strand": short, "version": version, "event": event, "date": date, "recorded": True,
               "unconfirmed": listed, "stage": stage, "purpose": purpose}
    return (2 if listed else 0), dict(payload, next=after) if after else payload

def resolved(root, reference):
    """(path, record-relative name) of a reference inside the record, or (None, None)."""
    try:
        path = mc.record_path(root, reference)
        return path, mc.relative(root, path)
    except (mc.Refusal, AttributeError, TypeError, ValueError):
        return None, None

def condense_check(root, folder, entries, prel):
    """G25, C171: (reasons, entries as stored) for a plan of {file, line, survives_in}: each line a body line of a
    current file of the strand, each naming an existing record file where its fact survives, so a line with no
    surviving copy can never be removed."""
    if not isinstance(entries, list):
        return [(prel, "entries", "the plan is not a list", 'a list of {"file", "line", "survives_in"}')], []
    base, reasons, kept, taken = "%s/" % mc.relative(root, folder), [], [], {}
    for number, entry in enumerate(entries, 1):
        entry = entry if isinstance(entry, dict) else {}
        (path, rel), (spath, srel) = resolved(root, entry.get("file")), resolved(root, entry.get("survives_in"))
        line, where = entry.get("line"), "entry %d" % number
        current = bool(rel) and rel.startswith(base) and guardable(rel) and "/versions/" not in rel and path.is_file()
        body = read_doc(root, path)[1].split("\n") if current else []
        found = [reason for reason in (
            None if current else (rel or prel, where, "%s is not a current file of strand %s" % (
                entry.get("file"), folder.name[:3]), "a current Markdown file of the strand: no snapshot, log or "
                                                     "SUMMARY.md"),
            None if not current or (isinstance(line, str) and line.strip() and body.count(line) > taken.get(
                rel, []).count(line)) else (rel, where, "%r is not a body line of the file, or is listed more often "
                                                       "than it occurs" % (line,), "a body line copied verbatim"),
            None if srel and srel != rel and spath.is_file() else (rel or prel, where, "no surviving copy named for %r"
                                                                   % (line,), "survives_in, an existing record file "
                                                                              "holding the fact: a line without one stays"))
            if reason]
        if found:
            reasons += found
        else:
            taken.setdefault(rel, []).append(line)
            kept.append({"file": rel, "line": line, "survives_in": srel})
    return reasons, kept

def condense_path(root, folder):
    return root / ".work" / "strands" / folder.name / "condense-plan.json"

def stored_condense(root, folder, sha):
    """(the stored condense plan, the reasons it may not be applied): its sha, and every file as it was planned."""
    path = condense_path(root, folder)
    prel = mc.relative(root, path)
    if not path.is_file():
        return None, [(prel, "sha256", "no stored condense plan", "record.py version condense-plan first")]
    if mc.sha256_file(path) != sha:
        return None, [(prel, "sha256", "the stored plan hashes to %s, not %s" % (mc.sha256_file(path), sha),
                       "the sha the plan step printed, which the user said yes to")]
    stored = mc.read_json(path, prel)
    return stored, [(rel, "sha256", "the file changed since the plan was made", "a fresh condense plan")
                    for rel, want in sorted((stored.get("files") or {}).items())
                    if not resolved(root, rel)[0].is_file() or mc.sha256_file(resolved(root, rel)[0]) != want]

def without_lines(text, lines):
    """`text` with each of `lines` taken out of its body once; the front matter stays as it is."""
    rows, pending = text.split("\n"), list(lines)
    end = next(i for i in range(1, len(rows)) if rows[i].rstrip() == "---")
    kept = rows[:end + 1]
    for row in rows[end + 1:]:
        if row in pending:
            pending.remove(row)
        else:
            kept.append(row)
    return "\n".join(kept)

def apply_condense(root, stored):
    """G25: each planned line taken out of its file once through a guarded write; returns the lines removed."""
    plan = {}
    for entry in stored.get("entries") or []:
        plan.setdefault(entry["file"], []).append(entry["line"])
    for rel, lines in sorted(plan.items()):
        path = mc.record_path(root, rel)
        new = without_lines(mc.read_text(path, rel), lines)
        if "updated" in mc.front_matter(new, rel):
            new = mc.set_front_matter(new, {"updated": mc.stamp("minute")}, rel)
        mc.guarded_write(path, new, root, stored["files"][rel])
    if any(rel.endswith("/STRAND.md") for rel in plan):
        refresh_index(root)
    return sum(len(lines) for lines in plan.values())

def cmd_version_condense_plan(root, args):
    """C171, G25: validate the session's condense plan and store it with each file's sha256; the output shows line
    by line where each removed fact survives, and the sha the user's yes is given to."""
    with mc.record_mutex(root):
        folder = strand_doc(root, args.strand)[0]
        plan = condense_path(root, folder)
        reasons, entries = condense_check(root, folder, mc.read_json(Path(args.source), "the plan"),
                                          mc.relative(root, plan))
        refuse(lease_free(root), *reasons)
        files = sorted({entry["file"] for entry in entries})
        refuse_newer(root, *[resolved(root, rel)[0] for rel in files])
        stored = {"strand": folder.name[:3], "entries": entries,
                  "files": {rel: mc.sha256_file(resolved(root, rel)[0]) for rel in files}}
        mc.write_file(plan, mc.json_text(stored), root, backup=False)
        return 0, {"strand": folder.name[:3], "plan": mc.relative(root, plan), "sha256": mc.sha256_file(plan),
                   "entries": entries}

def cmd_version_condense_apply(root, args):
    """C171, G25: apply the stored condense plan the user said yes to, refused on another sha or a changed file."""
    with mc.record_mutex(root):
        folder = strand_doc(root, args.strand)[0]
        stored, reasons = stored_condense(root, folder, args.plan_sha)
        refuse(lease_free(root), *reasons)
        refuse_newer(root, *[resolved(root, rel)[0] for rel in stored.get("files") or {}])
        count = apply_condense(root, stored)
        insert_entries(root, [new_entry(folder.name[:3], "version", "-", "condensed", [
            "lines: %d · files: %d · plan: %s" % (count, len(stored.get("files") or {}), args.plan_sha)])])
    return 0, {"strand": folder.name[:3], "lines": count, "files": sorted(stored.get("files") or {})}

def cmd_version_release(root, args):
    """C166 to C170, G26: in the user's one yes, freeze build.json and backlog.md into versions/<v>/, apply the
    condense plan, write SUMMARY.md from its plan, roll the version's log entries and mark it released. Refused
    while any strand holds the lease, unless the version is audited, while a file the release needs is missing
    (listed), from v1.0 without a signed-off event, and when either plan's sha differs."""
    with mc.record_mutex(root):
        folder, path, rel, fields, _ = strand_doc(root, args.strand)
        short, version = folder.name[:3], args.version or fields.get("version", "none")
        vdir = folder / "versions" / version
        vpath, target = vdir / "version.md", folder / "SUMMARY.md"
        vrel = mc.relative(root, vpath) if VERSION.fullmatch(version) else rel
        refuse(None if VERSION.fullmatch(version) and vpath.is_file() else (
            vrel, "version", "no version %s in strand %s" % (version, short), "an opened, audited version"))
        refuse_newer(root, vpath, *([target] if target.is_file() else []))
        vfields, vbody, vtext = read_doc(root, vpath)
        found = Check(root).run()
        missing = found.required(folder, vdir, dict(vfields, state="audited"), vbody, found.builds.get(short) or {})
        frozen = [(folder / "solution" / name, vdir / name) for name in ("build.json", "backlog.md")]
        splan = root / ".work" / "strands" / folder.name / "summary-plan.md"
        sprel = mc.relative(root, splan)
        stored, creasons = stored_condense(root, folder, args.condense_plan_sha)
        if not splan.is_file() or mc.sha256_file(splan) != args.summary_plan_sha:
            sreasons = [(sprel, "sha256", "no stored summary plan" if not splan.is_file() else "the stored plan hashes "
                         "to %s, not %s" % (mc.sha256_file(splan), args.summary_plan_sha),
                         "the sha record.py strand summary --plan printed, which the user said yes to")]
        else:
            sreasons = summary_plan(root, folder, mc.read_text(splan, sprel))[1]
        refuse(lease_free(root),
               None if vfields.get("state") == "audited" else (vrel, "state", "version %s is %s" % (
                   version, vfields.get("state")), "an audited version"),
               *missing,
               *[(mc.relative(root, source), "released", "missing: the release freezes it as %s" % mc.relative(
                   root, copy), "the strand's current %s" % source.name) for source, copy in frozen if not source.is_file()],
               *[(mc.relative(root, copy), "released", "the snapshot exists already", "a version not released before")
                 for copy in [copy for _, copy in frozen] + [vdir / "log.md"] if copy.exists()],
               (vrel, "signed_off", "%s has no signed-off event" % version, "the event recorded first: record.py version "
                "mark signed-off") if vnum(version) >= (1, 0) and vfields.get("signed_off", "none") == "none" else None,
               *creasons, *sreasons)
        for source, copy in frozen:
            mc.write_file(copy, source.read_bytes(), root)
        mc.write_file(vpath, mc.set_front_matter(vtext, {"state": "released", "released": mc.stamp("date")}, vrel), root)
        count, existed = apply_condense(root, stored), target.is_file()
        summary = summary_plan(root, folder, mc.read_text(splan, sprel))[0]
        mc.guarded_write(target, summary, root, mc.sha256_file(target) if existed else None)
        moved, sha, trel = roll(root, vdir / "log.md", short, version, "the version was released")
        insert_entries(root, [new_entry(short, "release", version, "released", [
            "rolled_to: " + trel, "entries: %d · sha256: %s" % (len(moved), sha),
            "frozen: build.json, backlog.md · condensed lines: %d · summary: %s" % (
                count, "refreshed" if existed else "written")])], removed=moved)
        current = mc.front_matter(summary)["summary_current_to"]
        write_fm(root, path, dict({"summary_current_to": current}, **(
            {"version_state": "released"} if version == fields.get("version") else {})))
        refresh_index(root)
        after = Check(root).run()
        left = after.required(folder, vdir, *read_doc(root, vpath)[:2], after.builds.get(short) or {})
    return (2 if left else 0), {"strand": short, "version": version, "released": mc.stamp("date"),
                                "frozen": [mc.relative(root, copy) for _, copy in frozen], "rolled_to": trel,
                                "entries": len(moved), "sha256": sha, "condensed_lines": count,
                                "summary": mc.relative(root, target), "summary_current_to": current,
                                "release_checks": [dict(zip(KEYS, item)) for item in left]}

def cmd_card(root, args):
    """C172, G25: the record's client-card.md copied byte for byte to <home>/cards/<slug>.md, an existing card backed
    up into the record's .work/backup/home/ first (G39); --strand stamps who asked, in a `closeout` entry at `-`."""
    with mc.record_mutex(root):
        mc.strand_dir(root, args.strand)
        refuse_newer(root)
        source, slug = root / "client-card.md", read_doc(root, root / "CLIENT.md")[0].get("slug", "")
        refuse(None if source.is_file() else ("client-card.md", "file", "the record has no client card",
                                              "client-card.md, which the record close writes"),
               None if SLUG.fullmatch(slug) else ("CLIENT.md", "slug", "%r" % slug, "the record's slug"))
        home, data = mc.home(), source.read_bytes()
        target, sha = home / "cards" / (slug + ".md"), hashlib.sha256(data).hexdigest()
        replaced = target.is_file()
        mc.write_file(target, data, home, backup_dir=root / ".work" / "backup" / "home")
        insert_entries(root, [new_entry("-", "closeout", "-", "card", [
            "copied to cards/%s.md · sha256: %s · asked_by: %s" % (slug, sha, args.strand)])])
    return 0, {"card": "cards/%s.md" % slug, "sha256": sha, "replaced": replaced}


def template_bytes(name, group="record"):
    """A template copied byte for byte from <plugin root>/templates/<group>/ (G31); exit 3 when it is missing."""
    path = TEMPLATES.parent / group / name
    if not path.is_file():
        raise mc.CannotRun(("templates/%s/%s" % (group, name), name, "the template is missing from the plugin",
                            "the plugin's own template"))
    return path.read_bytes()

def fill_json(name, values):
    """A JSON template from templates/record/ with the top-level keys record.py owns set, every other value kept."""
    shown = "templates/record/" + name
    try:
        data = json.loads(template_bytes(name).decode("utf-8-sig"))
    except ValueError as exc:
        raise mc.CannotRun((shown, mc.WHOLE_FILE, "not valid JSON: %s" % exc, "the plugin's own template"))
    for key in values:
        if key not in data:
            raise mc.CannotRun((shown, key, "the template has no %s key" % key, "every key record.py sets"))
    data.update(values)
    return mc.json_text(data)

SETTINGS_REL = "local/settings.json"

def settings_from(current, args, version):
    """G33, G34: (settings, "written" | "updated" | "kept", reasons) from the walkthrough's answers."""
    if current is not None and not args.update:
        return current, "kept", []
    named = (args.firm_name, args.firm_rendering, args.default_account_slug, args.default_account_id,
             args.never_show, args.archive, args.github_account)
    if current is not None and not isinstance(current, dict):
        raise mc.CannotRun((SETTINGS_REL, mc.WHOLE_FILE, "not a JSON object", "settings/1"))
    data = dict(current or {})
    if current is not None:
        mc.require_schema(current.get("schema"), "settings", SETTINGS_REL)
    firm, account = dict(data.get("firm") or {}), dict(data.get("default_build_account") or {})
    for target, key, value in ((firm, "name", args.firm_name), (account, "slug", args.default_account_slug),
                               (account, "id", args.default_account_id)):
        if value is not None:
            target[key] = value
    firm["renderings"] = list(args.firm_rendering) if args.firm_rendering is not None else \
        firm.get("renderings") or ([firm["name"]] if firm.get("name") else [])
    never = [dict(zip(("id", "name"), (part.strip() for part in item.partition("=")[::2])))
             for item in args.never_show] if args.never_show is not None else data.get("never_show_workspaces") or []
    archive = args.archive or data.get("archive") or "local"
    github = args.github_account if args.github_account is not None else data.get("github_account")
    reasons = [(SETTINGS_REL, "update", "--update names no answer to change", "one or more answer flags with --update")
               if current is not None and all(value is None for value in named) else None,
               None if one_line(firm.get("name")) else (SETTINGS_REL, "firm", "no firm name in one line",
                                                         "--firm-name, the walkthrough's first answer"),
               *[(SETTINGS_REL, "firm", "the rendering %r" % item, "each rendering on one line")
                 for item in firm["renderings"] if not one_line(item)],
               *[(SETTINGS_REL, "default_build_account", "no account %s in one line" % key,
                  "--default-account-slug and --default-account-id") for key in ("slug", "id")
                 if not one_line(account.get(key))],
               *[(SETTINGS_REL, "never_show_workspaces", "%r" % item, "<workspace id>=<name>")
                 for item in args.never_show or () if not all(one_line(part) for part in item.partition("=")[::2])],
               None if archive in ("local", "github") else (SETTINGS_REL, "archive", "%r" % archive, "local | github"),
               (SETTINGS_REL, "github_account", "the GitHub archive with no GitHub account", "--github-account with "
                "--archive github") if archive == "github" and not one_line(github) else None,
               (SETTINGS_REL, "github_account", "a GitHub account with the local archive", "no GitHub account unless "
                "the GitHub archive is picked") if archive == "local" and args.github_account is not None else None]
    data.update(schema="settings/1", created=data.get("created") or mc.stamp("date"), plugin_version=version,
                firm=firm, default_build_account=account, never_show_workspaces=never, archive=archive)
    data.pop("github_account", None)
    if archive == "github":
        data["github_account"] = github
    return data, "updated" if current is not None else "written", [reason for reason in reasons if reason]

def cmd_home_init(record, args):
    """C28 to C38, G32 to G35, G37, G58: the home tree, local/settings.json from the walkthrough's answers (never
    replaced unless --update names an answer), the two seeded files and SANDBOX.md, the checks, and a warning per
    CLAUDE.md above the clients folder. It sets no environment variable and edits no profile."""
    env, default, version = os.environ.get("MMB_HOME"), Path.home() / "monday-builder", mc.plugin_version(PLUGIN_ROOT)
    refuse(("MMB_HOME", "home", "MMB_HOME is set, so the home is %s" % env, "--home only while MMB_HOME is unset")
           if args.home and env else None,
           ("MMB_HOME", "home", "%s is not an absolute folder" % args.home, "an absolute folder")
           if args.home and not Path(args.home).is_absolute() else None)
    home = Path(args.home) if args.home else mc.home()
    path = home / "local" / "settings.json"
    data, state, reasons = settings_from(mc.read_json(path, SETTINGS_REL) if path.is_file() else None, args, version)
    refuse(*reasons)
    cover = None if (home / "sandbox" / "SANDBOX.md").exists() else template_bytes("SANDBOX.md", "other")
    created = ["%s/" % name for name in mc.HOME_FOLDERS if not (home / name).is_dir()]
    for name in mc.HOME_FOLDERS:
        (home / name).mkdir(parents=True, exist_ok=True)
    seeds = [(rel, seed) for rel, seed in (("local/leak-terms.txt", b""), ("local/sandbox-accounts.txt", b""),
                                           ("sandbox/SANDBOX.md", cover)) if seed is not None and not (home / rel).exists()]
    for rel, seed in seeds:
        mc.write_file(home.joinpath(*rel.split("/")), seed, home)
    if state != "kept":
        mc.write_file(path, mc.json_text(data), home / "local", backup_dir=home / "local" / "backup")
    checks = {"python": {"version": "%d.%d.%d" % sys.version_info[:3], "ok": sys.version_info >= (3, 9)},
              "plugin_root": {"path": str(PLUGIN_ROOT), "plugin_version": version},
              "connector": "checked by the session: a script cannot see the session's tool roster"}
    warnings = []
    for tool in ("git", "gh") if data.get("archive") == "github" else ():
        checks[tool] = "found" if shutil.which(tool) else "absent"
        if checks[tool] == "absent":
            warnings.append(dict(zip(KEYS, (tool, "archive", "the GitHub tool %s is not on this system" % tool,
                                            "%s installed before the first GitHub archive" % tool))))
    start = home.absolute()
    warnings += [dict(zip(KEYS, (str(folder), "CLAUDE.md", "a CLAUDE.md sits here, above the clients folder, and "
                                 "every client session would inherit it", "no CLAUDE.md above the clients folder")))
                 for folder in [start] + list(start.parents) if (folder / "CLAUDE.md").is_file()]
    payload = {"home": str(start), "created": created + [rel for rel, _ in seeds] + (
        [SETTINGS_REL] if state == "written" else []), "settings": state, "archive": data.get("archive"),
        "checks": checks, "warnings": warnings}
    if state == "kept":
        payload["to_change"] = "record.py home init --update with the answer to change"
    if start != default.absolute():
        payload["set_mmb_home"] = {"env": {"MMB_HOME": str(start)}, "where": "the env block of the user's Claude Code "
                                   "user settings, the same on Windows and macOS", "this_system": 'setx MMB_HOME "%s"'
                                   % start if os.name == "nt" else 'export MMB_HOME="%s" in the login shell profile'
                                   % start}
    return (2 if warnings else 0), payload

CLIENT_CLAUDE = ("# This client's folder\n\n"
                 "- Read CLIENT.md first: it is this client's record, and its strand index says where each piece of "
                 "work stands.\n"
                 "- Open a fresh session for a build or an audit.\n"
                 "- Nothing is written into monday except through the build command.\n")

def occupied(root):
    """The `folder` refusal while the folder holds anything but a .work/ with only the mutex in it, else None."""
    present = sorted(p.name for p in root.iterdir() if p.name != ".work" or [q.name for q in p.iterdir()] != [
        "record.mutex"]) if root.is_dir() else []
    return ("CLIENT.md", "folder", "the folder %s is not empty: %s" % (root.name, ", ".join(present[:6])),
            "a new or empty client folder") if present else None

INDEX_FILE, HEX32 = "<home>/clients-index.json", re.compile(r"[0-9a-f]{32}")

def looked_at(path, name):
    """Whether a home path exists, by os.stat as leak_lint.py's path_kind does (WP4's R36). A path that cannot be
    looked at stops the run, naming `name` only and never another client's folder (WP4's X30)."""
    try:
        os.stat(str(path))
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError as exc:
        raise mc.CannotRun((name, mc.WHOLE_FILE, "cannot be looked at (%s), so init cannot tell whether the slug is "
                            "already used" % (exc.strerror or type(exc).__name__),
                            "a home readable by the user who runs record.py, then run init again"))

def index_keys(home):
    """The keys of <home>/clients-index.json, none while there is no index, read under the home mutex when that
    mutex exists, as leak_lint.py's reader does. An index that cannot be read, or is not clients-index/1 with
    32-hex keys, or that writes a key twice in one object (WP4's R55, read as the lint reads it), stops the run: an
    index init cannot trust cannot prove a slug free."""
    path = home / "clients-index.json"
    if not looked_at(path, INDEX_FILE):
        return set()
    held = looked_at(home / ".work" / "record.mutex", INDEX_FILE)
    with mc.record_mutex(home) if held else contextlib.nullcontext():
        try:
            data = mc.strict_json(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, ValueError, mc.RepeatedKey):
            data = None
    entries = data.get("entries") if isinstance(data, dict) and data.get("schema") == "clients-index/1" else None
    if not isinstance(entries, dict) or not all(HEX32.fullmatch(key) for key in entries):
        raise mc.CannotRun((INDEX_FILE, mc.WHOLE_FILE, "the index of client records cannot be read as clients-index/1, "
                            "so init cannot tell whether the slug is already used", "the index as leak_lint.py index "
                            "wrote it: restore the last copy from <home>/local/backup/, then run init again"))
    return set(entries)

def slug_used(home, root, slug):
    """R39: the `slug` refusal while another client holds the slug: a folder of that name under <home>/archive/, or
    under <home>/clients/ other than this init's own folder, or the slug's key in the index, which outlives an
    archived folder the user has removed (WP4's R35). It names the slug typed and nothing of the other client."""
    for folder in ("clients", "archive"):
        twin = home / folder / slug
        if looked_at(twin, "<home>/%s/" % folder) and (folder == "archive" or twin.resolve() != root.resolve()):
            break
    else:
        if mc.slug_key(slug) not in index_keys(home):
            return None
    return ("CLIENT.md", "slug", "the slug %s is already used by another client record under the home, open or "
            "archived, and a slug belongs to one client for good" % slug, "a slug no client record has used: choose "
            "another slug, then run init again")

def init_folder(record, slug):
    """The folder init writes: --record when given, else <home>/clients/<slug>/."""
    return record or mc.home() / "clients" / slug

def cmd_init(record, args):
    """C39 to C44, G43, G56: the record shell and strand 001 from the templates (CLIENT.md, log.md, account.json and
    a platform or hybrid strand's build.json, all unbound), the folder's own CLAUDE.md, a .gitignore only on the
    GitHub archive path, and the first lock through mmb_common's lease primitives; the A11 fields stay unanswered.
    A slug another client record holds, open, archived or only indexed, is refused (R39)."""
    slug, output = args.slug, args.output_class or OUTPUT_CLASS.get(args.kind, "")
    refuse(None if SLUG.fullmatch(slug) and len(slug) <= 40 else (
               "CLIENT.md", "slug", "%r breaks the slug rule" % slug,
               "lowercase ASCII words joined by hyphens, at most 40 characters"),
           None if one_line(args.name) else ("CLIENT.md", "name", "no client name in one line", "the client's name"))
    home = mc.home()
    root = init_folder(record, slug)
    archive = (mc.read_settings() or {}).get("archive", "local")
    refuse(None if root.name == slug else ("CLIENT.md", "slug", "%s in a folder named %s" % (slug, root.name),
                                           "the folder's name: a slug is never renamed"),
           slug_used(home, root, slug), occupied(root), *strand_reasons(root, args.topic, args.title, args.kind, args.reason, output, "none"))
    client = fill("CLIENT.md", {"slug": slug, "name": args.name})
    # Intake fold 2: the target the template gives comes with its reason, written and printed, never silently; the
    # key is appended when a template predates it. A skill that records another target rewrites both through guard.
    target = mc.front_matter(client)["build_target"]
    reason = mc.front_matter(client).get("build_target_reason") or TARGET_REASON.get(target, "")
    client = mc.set_front_matter(client, {"build_target_reason": reason}, "templates/record/CLIENT.md")
    files = {"CLIENT.md": client, "log.md": fill("log.md", {"client": slug}), "CLAUDE.md": CLIENT_CLAUDE,
             "account.json": fill_json("account.json", {"client_slug": slug})}
    if archive == "github":
        files[".gitignore"] = template_bytes("client-gitignore.txt")
    strand = strand_files("001", args.topic, args.title, args.kind, output, args.reason, "none")
    build = fill_json("build.json", {"client_slug": slug, "strand": "001"}) if args.kind != "non-platform" else None
    root.mkdir(parents=True, exist_ok=True)
    with mc.record_mutex(root):
        refuse(occupied(root))  # finding 15: again under the mutex, so a second init of the slug writes nothing
        for name, data in files.items():
            mc.write_file(root / name, data, root)
        mc.lease_init(root)
        insert_entries(root, [new_entry("-", "created", "-", slug, ["record created; build target %s; archive %s" % (
            target, archive)])])
        folder = place_strand(root, "001", args.topic, args.kind, args.reason, strand)
        if build:
            mc.write_file(folder / "solution" / "build.json", build, root)
    return 0, {"slug": slug, "strand": "001", "folder": mc.relative(root, folder), "archive": archive,
               "build_target": target, "build_target_reason": reason,
               "files": sorted(mc.relative(root, p) for p in root.rglob("*")
                               if p.is_file() and p.relative_to(root).parts[0] != ".work")}

def cmd_client_rename(root, args):
    """R40: the client's name changes in CLIENT.md and the old name is appended to `former_names` once, no entry
    ever dropped, so leak_lint.py still knows this record's index entry as its own and keeps every other record
    walled against the old name. A record-level `decision` entry logs it; the slug never changes."""
    path = root / "CLIENT.md"
    with mc.record_mutex(root):
        refuse_newer(root)
        fields, _, text = read_doc(root, path)
        old, new = (fields.get("name") or "").strip(), (args.name or "").strip()
        former = mc.former_names(fields.get("former_names"))
        refuse(None if one_line(new) and ";" not in new else (
                   "CLIENT.md", "name", "no new name in one line without a semicolon",
                   "the client's new name, one line, with no ; since former_names joins names with it"),
               None if one_line(old) and ";" not in old else (
                   "CLIENT.md", "name", "the current name is not one line without a semicolon, so it cannot be kept "
                   "in former_names", "a current name of one line with no ;"),
               ("CLIENT.md", "name", "%s is already the client's name" % new, "a name the client does not have")
               if new and new == old else None,
               ("CLIENT.md", "former_names", "%s is already a former name of the client" % new,
                "a name the client has not had") if new in former else None)
        former += [] if old in former else [old]
        mc.write_file(path, mc.set_front_matter(text, {"name": new, "former_names": "; ".join(former)}, "CLIENT.md"),
                      root)
        insert_entries(root, [new_entry("-", "decision", "-", "rename", ["name: %s to %s" % (old, new),
                                                                       "former_names: " + "; ".join(former)])])
    return 0, {"name": new, "former_names": former}


# R48 (WP4): a command that wrote a file the index's harvest reads runs leak_lint.py index for its record before it
# prints, so the record's entry in <home>/clients-index.json is never left older than its files (WP4's R44).
LINT_FILE = Path(__file__).resolve().parent / "leak_lint.py"
LOADED = {}  # leak_lint.py, loaded once per process

class Unwalked(Exception):
    """The record could not be walked as the index walks it."""

def lint_module():
    """leak_lint.py beside this file, loaded by path in process, as tools/lint_plugin.py loads it (WP4's R41): one
    implementation of the walk, the age test and the index, and no second process. sys.dont_write_bytecode is
    already set, so the load leaves no cache beside the scripts (G49)."""
    if "lint" not in LOADED:
        spec = importlib.util.spec_from_file_location("mmb_leak_lint", str(LINT_FILE))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        LOADED["lint"] = module
    return LOADED["lint"]

def harvested_marks(lint, root):
    """{name: (modification time, status-change time, size)} of the record's files that feed its index entry, found
    by leak_lint.py's own walk and feeds_entry (R44), so what counts as a write here is what the index reads; any
    change between two marks is a write, also a rewrite that leaves the newest time where it was. {} for a folder
    not made yet (init); None when the record cannot be walked, which the index then reports."""
    def stop(*_):
        raise Unwalked()
    try:
        if not root.is_dir():
            return {}
        marks = {}
        for rel, path in lint.record_walk(root.resolve(), stop, stop).items():
            if lint.feeds_entry(rel):
                try:
                    info = os.stat(str(path))
                except FileNotFoundError:
                    continue
                marks[rel] = (info.st_mtime_ns, info.st_ctime_ns, info.st_size)
        return marks
    except (Unwalked, OSError):
        return None

def index_baseline(root):
    """(leak_lint.py or the exception that stopped its load, the record's marks before the command)."""
    if root is None:
        return None, None
    try:
        lint = lint_module()
    except Exception as exc:  # reported after the command, which still runs
        return exc, None
    return lint, harvested_marks(lint, root)

def index_warning(file, field, cause, expected):
    """The warning a command carries when its record's index entry could not be kept current (exit 2)."""
    return dict(zip(KEYS, (file, field, "this command's writes are done and kept, but this record's entry in the "
                           "client index was not brought up to date, because %s. Until it is, other client records' "
                           "lint may stop with exit 3, and their wall may not see what this record now holds" % cause,
                           expected)))

def keep_index(root, lint, before):
    """After a command that succeeded: leak_lint.py index for this record when the command changed a file the
    harvest reads, or when that cannot be told. None when nothing was owed or the index ran; else the warning.
    record.py holds no mutex here, the record's having been released when the command returned, and index takes
    only the home's, so the two are never held together and no lock order can invert."""
    if isinstance(lint, BaseException):
        return index_warning("<plugin>/scripts/leak_lint.py", mc.WHOLE_FILE, "leak_lint.py beside record.py could "
                             "not be loaded (%s)" % type(lint).__name__, "the plugin's own leak_lint.py beside "
                             "record.py: reinstall the plugin, then run leak_lint.py index from this record")
    try:
        after = harvested_marks(lint, root)
        if before is not None and after is not None and after == before:
            return None  # nothing the harvest reads changed: a lease refresh, a check, a read
        code, data = lint.run_command(["--record", str(root), "index"])
    except Exception as exc:  # run_command catches its own; this is a last guard, so the output stays one envelope
        code, data = 3, {"error": {"field": type(exc).__name__, "problem": str(exc)}}
    if code in (0, 2):
        return None
    found = {key: str(value) for key, value in (data.get("error") or {}).items() if key in KEYS and value}
    error = dict({"file": "leak_lint.py", "field": mc.WHOLE_FILE, "problem": "no reason given",
                  "expected": "a run of index that finishes"}, **found)
    cause = "leak_lint.py index stopped with exit %d: %s" % (code, error["problem"].rstrip("."))
    return index_warning(error["file"], error["field"], cause, "%s (the run meant is leak_lint.py index from this "
                         "record; record.py also runs it after its next write)" % error["expected"])


COMMANDS = {  # C25 and G05: the catalogue
    "status": cmd_status, "check": cmd_check, "log": cmd_log, "guard": cmd_guard,
    "add-transcript": lambda root, args: cmd_add(root, args, True),
    "add-document": lambda root, args: cmd_add(root, args, False), "freeze": cmd_freeze,
    "strand open": cmd_strand_open, "strand list": cmd_strand_list, "strand pause": cmd_strand_pause,
    "strand kind": cmd_strand_kind, "strand close": cmd_strand_close, "strand summary": cmd_strand_summary,
    "strand resume": cmd_strand_resume, "home init": cmd_home_init, "init": cmd_init, "card": cmd_card,
    "lease take": cmd_lease_take, "lease refresh": cmd_lease_refresh, "lease release": cmd_lease_release,
    "lease status": cmd_lease_status, "lease break": cmd_lease_break, "lease sync": cmd_lease_sync,
    "lease repair": cmd_lease_repair, "version open": cmd_version_open,
    "version mark": cmd_version_mark, "version condense-plan": cmd_version_condense_plan,
    "version condense-apply": cmd_version_condense_apply, "version release": cmd_version_release,
    "client rename": cmd_client_rename}
NO_RECORD = ("home init", "init")  # these two run where no record exists yet

def build_parser():
    parser = Parser(prog="record.py", description="The client record's writer and checker.")
    parser.add_argument("--record", help="the client folder (default: the current folder)")
    top = parser.add_subparsers(dest="command", metavar="command")
    top.required = True
    groups = {}
    for name in COMMANDS:
        group, _, action = name.partition(" ")
        if action and group not in groups:
            groups[group] = top.add_parser(group).add_subparsers(dest="sub", metavar="action")
            groups[group].required = True
        groups[name] = groups[group].add_parser(action) if action else top.add_parser(group)
    for name in ("status", "check"):
        groups[name].add_argument("--json", action="store_true")
    for name in ("status", "guard"):
        groups[name].add_argument("--strand")
    for name in ("log", "add-transcript", "add-document", "freeze", "strand pause", "strand kind", "strand close",
                 "strand summary", "strand resume"):
        groups[name].add_argument("--strand", required=True)
    for name, flags in (("log", ("--type", "--key")), ("strand open", ("--topic", "--title", "--kind", "--reason")),
                        ("strand pause", ("--reason",)), ("strand kind", ("--kind", "--reason")),
                        ("guard", ("--file",)), ("add-transcript", ("--type",)), ("add-document", ("--title",))):
        for flag in flags:
            groups[name].add_argument(flag, required=True)
    groups["log"].add_argument("--version", default="-")
    body = groups["log"].add_mutually_exclusive_group()
    body.add_argument("--line", action="append")
    body.add_argument("--body-file")
    groups["guard"].add_argument("--expect-sha")
    groups["guard"].add_argument("--from", dest="source")
    for name in ("add-transcript", "add-document"):
        groups[name].add_argument("--from", dest="source", required=True)
        groups[name].add_argument("--date")
        groups[name].add_argument("--fixture", action="store_true")
        groups[name].add_argument("--redactions", type=int, default=0)
    groups["add-document"].add_argument("--kind", default="document")
    groups["add-document"].add_argument("--came-with")
    for name in ("strand open", "strand kind"):
        groups[name].add_argument("--output-class")
    groups["strand open"].add_argument("--depends-on")
    step = groups["strand summary"].add_mutually_exclusive_group(required=True)
    step.add_argument("--plan")
    step.add_argument("--apply")
    groups["lease take"].add_argument("kind", nargs="?", default="build")
    for name in ("lease take", "version open", "version mark", "version condense-plan", "version condense-apply",
                 "version release", "card"):
        groups[name].add_argument("--strand", required=True)
    for name, flags in (("lease refresh", ("--epoch", "--label", "--run-id")), ("lease release", ("--epoch", "--label")),
                        ("lease break", ("--epoch", "--label", "--for-strand", "--user-yes", "--account-id", "--choice",
                                         "--park-yes")), ("lease repair", ("--user-yes",)),
                        ("version open", ("--version",)), ("version release", ("--version", "--condense-plan-sha",
                                                                                "--summary-plan-sha")),
                        ("version mark", ("--version", "--date", "--audience", "--account", "--by", "--words")),
                        ("version condense-apply", ("--plan-sha",)),
                        ("home init", ("--firm-name", "--default-account-slug", "--default-account-id", "--archive",
                                       "--github-account", "--home")), ("init", ("--output-class",))):
        for flag in flags:
            groups[name].add_argument(flag)  # a missing value is refused by the command (exit 1), not a usage error
    groups["version mark"].add_argument("event")
    groups["version mark"].add_argument("--go-on", action="store_true")
    groups["version condense-plan"].add_argument("--from", dest="source", required=True)
    for flag in ("--firm-rendering", "--never-show"):
        groups["home init"].add_argument(flag, action="append")
    groups["home init"].add_argument("--update", action="store_true")
    for flag in ("--slug", "--name", "--topic", "--title", "--kind", "--reason"):
        groups["init"].add_argument(flag, required=True)
    groups["client rename"].add_argument("--name", required=True)
    return parser

def main(argv=None):
    parser = build_parser()
    try:
        args, extra = parser.parse_known_args(argv)
        name = " ".join(word for word in (args.command, getattr(args, "sub", None)) if word)
        if extra:
            raise Usage("unrecognized arguments: %s" % " ".join(extra))
    except Usage as exc:
        emit({"ok": False, "command": None, "error": dict(zip(KEYS, ("record.py", "arguments", str(exc),
                                                                      parser.format_usage().strip())))})
        return 3
    try:
        root = Path(args.record) if args.record else (None if name in NO_RECORD else Path.cwd())
        if name not in NO_RECORD and not (root / "CLIENT.md").is_file():
            raise mc.CannotRun(("CLIENT.md", "record", "no record in the folder %s" % root.name,
                                "a client folder holding CLIENT.md, or --record <folder>"))
        # R48: status prints status/1 bare and never writes, and home init has no record
        target = None if name in ("status", "home init") else init_folder(root, args.slug) if name == "init" else root
        lint, before = index_baseline(target)
        code, payload = COMMANDS[name](root, args)
    except mc.MMBError as exc:
        emit(dict({"ok": False, "command": name}, **({"refusals": exc.findings} if exc.code == 1
                                                     else {"error": exc.findings[0]}),
                  **({"committed": exc.committed} if exc.committed is not None else {})))
        return exc.code
    except Exception as exc:  # G10: anything unexpected is "could not run", still one JSON object
        emit({"ok": False, "command": name, "error": dict(zip(KEYS, ("record.py", type(exc).__name__,
              str(exc) or "an internal error with no message", "a run without an internal error")))})
        return 3
    warning = keep_index(target, lint, before) if target is not None and code in (0, 2) else None
    if warning:  # R48: done, with a warning (exit 2); the command's own writes stay as they are
        payload = dict(payload, warnings=list(payload.get("warnings") or []) + [warning])
        code = 2
    emit(payload if name == "status" else dict({"ok": code != 1, "command": name}, **payload))
    return code


if __name__ == "__main__":
    sys.exit(main())
