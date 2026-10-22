#!/usr/bin/env python3
"""The client record's ledger: account.json and each strand's solution/build.json (ARCHITECTURE 5.4 and 7.3,
WP3 decisions W06 to W92).

ledger.py is the one writer of account.json (its guard_index.lease block apart, which the lease primitives of
mmb_common write) and of every strand's build.json. It never calls monday: the session makes every call and hands
ledger.py what it intends, what it sent and what it read back, as flags and as JSON files inside the record. Every
subcommand prints one JSON object, {"ok", "command", "asked_by", ...}, and exits 0 (done), 1 (refused, or `check`
found a blocking finding), 2 (done, warnings only) or 3 (could not run). Standard library only, Python 3.9 and later,
the same on Windows and macOS. Nothing here deletes or renames a file, writes the lock, parses the lock, or fills in
one of the open A11 fields.
"""
import sys
sys.dont_write_bytecode = True  # no cache beside the scripts (G49), set before mmb_common is imported
if sys.version_info < (3, 9):
    sys.stdout.write('{"ok": false, "command": null, "error": {"file": "ledger.py", "field": "python", '
                     '"problem": "Python %d.%d", "expected": "Python 3.9 or later"}}\n' % sys.version_info[:2])
    sys.exit(3)
import argparse, hashlib, json, math, re  # noqa: E401,E402
from pathlib import Path  # noqa: E402
import mmb_common as mc  # noqa: E402

KEYS = ("file", "field", "problem", "expected")
INTERNAL = "Internal: never client-facing"

# pinned: ledger
TYPES = ("workspace", "folder", "board", "group", "column", "view", "form", "subitems", "doc", "dashboard", "widget",
         "automation", "portfolio", "project", "workflow", "agent", "ai_column", "vibe_app", "sequence", "webhook",
         "item_batch", "publication", "activation")
ORIGINS = ("created", "pre-existing-modified", "pre-existing-referenced", "other-strand-modified")
STATUSES = ("planned", "attempting", "written", "verified", "mismatch", "departed", "removed")
RESULTS = ("match", "mismatch", "not-checkable", "needs-user")
STATES = ("active", "inactive", "archived", "removed-by-platform")
APPROVAL_MODES = ("own-account-poc", "per-list")
YES_MODES = ("card", "per-item", "grouped")
CLASSES = ("card", "list", "irreversible", "publication", "webhook", "removed")
OPERATIONS = ("create", "update", "archive", "activate", "publish", "connect", "convert", "delete")
RUN_KINDS = ("build", "doc-copy")
RUN_STATES = ("running", "ended", "interrupted")
CONSTRAINTS = ("do-not-change", "change-with-own-yes", "free")
CHANGE_RESULTS = ("no change affecting this build", "change affecting this build")
DECISIONS = ("ui-step", "blueprint-revision", "later-retry")
UI_STATUSES = ("open", "done")
RECONCILE_CLASSES = ("adopt", "retry", "duplicate", "partial", "changed-since-verified", "unrecorded-extra", "missing")
RECONCILE_MODES = ("classify-only",)
CONFIDENCES = ("high", "medium", "low")
# end pinned

# Element keys by type (A7.3:582, W11, W42): bare inside a strand's ledger and blueprint.
KEY_FORMS = {"workspace": r"W\d+", "folder": r"F\d+", "board": r"B\d+", "group": r"B\d+\.G\d+",
             "column": r"B\d+\.C\d+", "view": r"B\d+\.V\d+", "form": r"B\d+\.FM\d+", "subitems": r"B\d+\.SUB",
             "doc": r"D\d+", "dashboard": r"DB\d+", "widget": r"DB\d+\.W\d+", "automation": r"A\d+",
             "portfolio": r"PF\d+", "project": r"PJ\d+", "workflow": r"WF\d+", "agent": r"AG\d+",
             "ai_column": r"B\d+\.AI\d+", "vibe_app": r"VB\d+", "sequence": r"SQ\d+", "webhook": r"WH\d+",
             "item_batch": r"B\d+\.IB\d+", "publication": r"(?:WF|VB)\d+\.PUB", "activation": r"(?:AG|SQ)\d+\.ACT",
             "ui_step": r"U\d+"}
ACCOUNT_LEVEL = ("agent", "vibe_app", "sequence", "webhook")
LIST_TYPES = ("automation", "workflow", "agent", "sequence")
LISTS = (("automation", "automations_listed"), ("workflow", "workflows_listed"), ("agent", "agents_listed"),
         ("sequence", "sequences_listed"))
PROMPT_TYPES = ("agent", "ai_column", "vibe_app")
MUST_LIST = ("workspace", "folder", "publication", "activation", "webhook")  # W42: listed under --irreversible
INACTIVE_OK = ("agent", "workflow", "sequence", "automation", "activation")
NO_MATCH = ("ai_column", "sequence", "webhook", "widget")  # read back not-checkable until probed (W51, K198)
COMPANIONS = ("subitems_board_id", "doc_container_board_id", "form_board_id", "overview_board_id", "planner_board_id",
              "tasks_board_id", "folder_id")
FIT = {"activate": ("activation",), "publish": ("publication",), "connect": ("project",), "convert": ("board",)}
RAISES = ("IR-04", "IR-05", "IR-06")  # --ir raises a card row to irreversible (W10)
POLL_CEILINGS = {"portfolio": 120, "project": 120, "vibe_app": 300}  # seconds, polled every 10 (W54)
CALL_FORMS = ("flat", "wrapped", "tool", "raw")
KEY_IDS = ("column", "ai_column", "group")  # monday gives these string keys, not numeric ids
DEFAULT_TRIGGERS = ("When agent is mentioned", "When agent is assigned")
A21 = "inside this client's workspaces: the plugin never writes into any other workspace (A21)"
FENCE_EXPECTED = ("the epoch and session label this session's take returned and the run id run start returned, "
                  "held by the session and never read from the lock")
TARGET_OF = {"own": "own-account", "client": "client-account", "sandbox": "none"}
REF = re.compile(r"(v\d+\.\d+)r(\d+)(?:#(.+))?")
ASSUMPTION_ID = re.compile(r"(AS|AT|FK)\d+")
LOCAL_KEY = re.compile(r"\d{3}:[A-Z][A-Za-z0-9.]*")
RECIPIENT = re.compile(r"\d+|team:\d+|email:[^@\s]+@[^@\s]+")
DIGITS = re.compile(r"[0-9]+")  # a count, an epoch or a revision; never a monday id
ID = re.compile(r"[1-9][0-9]*")  # R4: a monday id has one spelling, digits with no leading zero
LEADING_ZERO = re.compile(r"0[0-9]*")
REF_FORM = re.compile(r"(board|workspace|doc|view|column):([1-9][0-9]*)")
STRICTNESS = {"do-not-change": 2, "change-with-own-yes": 1, "free": 0}
# R17: a client quote's location (a call or input file, then a location of its grammar), and a log entry's header line
QUOTE_AT = re.compile(r"(?:calls|inputs)/[^\s@]+\.md(?:@\d{2}:\d{2}:\d{2}|\s+(?:cues? \d+(?:-\d+)?|L\d+(?:-\d+)?|"
                      r"paragraph \d+|§\d+(?:\.\d+)*|p\.\s?\d+))")
LOG_AT = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} · (?:\d{3}|-) · [a-z-]+ · \S")
MAP_HEAD = "| key | monday id | kind | workspace | built by | state | constraint | source | dependants | last verified |"
MAP_SEP = "|---|---|---|---|---|---|---|---|---|---|"
MAP_COLUMNS = ("monday id", "kind", "workspace", "built by", "state", "constraint", "source", "dependants",
               "last verified")
LIVE_FIELDS = ("monday_id", "kind", "workspace", "name_at_build", "owner_strand", "introduced_in", "state",
               "constraint", "constraint_source", "digest", "last_verified", "dependants")
ROW_FIELDS = ("type", "id", "name", "parent_key", "parent_id", "origin", "source_strand", "introduced_in",
              "changed_in", "state", "status", "attempt", "verify", "creator_user_id", "owner_user_ids",
              "irreversible", "sample_data", "approval_ref", "notifies", "companions", "role", "prior_state", "url",
              "blueprint_ref", "item_ids", "product", "workspace", "workspace_scope", "refs", "assumption_refs",
              "prompt_ref", "version_id_at_build", "live_key", "read_values")
SKELETON = (("schema", "build/2"), ("client_slug", ""), ("strand", ""), ("account_ref", "../../../account.json"),
            ("account_id_at_bind", "unbound"), ("lease_epoch_at_run", None), ("reads_live", []),
            ("updated_at", None), ("approvals", []), ("preflight", None), ("runs", []), ("objects", {}),
            ("irreversible_yes", []), ("departures", []), ("ui_steps", []))
# The identity fields a digest covers, per kind (W73); a kind not listed digests its whole read object.
IDENTITY = {"workspace": ("name", "kind"), "folder": ("name", "workspace_id"),
            "board": ("name", "type", "state", "workspace_id", "board_folder_id"),
            "doc": ("name", "workspace_id"), "automation": ("id", "is_active", "updated_at"),
            "dashboard": ("name", "workspace_id", "kind"), "agent": ("state", "version_id"),
            "vibe_app": ("status", "is_published", "code_version"), "workflow": ("name", "state"),
            "group": ("title", "color", "position"), "column": ("id", "title", "type", "settings"),
            "view": ("name", "type", "settings"), "item_batch": ("item_ids",),
            "publication": ("state", "is_published"), "activation": ("state", "is_published")}
for _kind in ("subitems", "portfolio", "project"):
    IDENTITY[_kind] = IDENTITY["board"]
# Demos' fixes, 3: list_automations names the state is_active, and the older raw read and the snapshot say active;
# the id is in the identity so that two automations alike in every other field never share a digest.
ALIASES = {("automation", "is_active"): ("active",)}


# The frame (a copy of record.py's, PLAN 8 item 3): the envelope, the refusal helper, the parser.

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


def flatten(*groups):
    return [reason for group in groups for reason in (group if isinstance(group, list) else [group]) if reason]


# Small helpers: ids, references, digests, time.

def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def id_key(key):
    key = str(key)
    return key in ("id", "ids") or key.endswith("_id") or key.endswith("_ids")


LABEL_KEYS = ("labels",)  # demo 2: a status or dropdown column's labels carry monday's own label numbers, 0 included


def numeric_ids(data, path=""):
    """Dotted paths of every JSON number held under a key named id, ids, *_id or *_ids (W35); a column's labels
    are passed over, since their ids are label numbers, not monday ids."""
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            where = "%s.%s" % (path, key) if path else str(key)
            if key in LABEL_KEYS:
                continue
            if id_key(key) and (is_int(value) or isinstance(value, float)):
                found.append(where)
            elif id_key(key) and isinstance(value, list):
                found += ["%s[%d]" % (where, n) for n, item in enumerate(value) if is_int(item) or isinstance(item, float)]
                found += [p for n, item in enumerate(value) for p in numeric_ids(item, "%s[%d]" % (where, n))]
            else:
                found += numeric_ids(value, where)
    elif isinstance(data, list):
        for n, item in enumerate(data):
            found += numeric_ids(item, "%s[%d]" % (path, n))
    return found


def zero_ids(data, path=""):
    """Dotted paths of every string of digits with a leading zero held under an id key (R4): one id, one spelling.
    A column's labels are passed over, as in `numeric_ids`."""
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            where = "%s.%s" % (path, key) if path else str(key)
            if key in LABEL_KEYS:
                continue
            if id_key(key) and isinstance(value, str) and LEADING_ZERO.fullmatch(value):
                found.append(where)
            elif id_key(key) and isinstance(value, list):
                found += ["%s[%d]" % (where, n) for n, item in enumerate(value)
                          if isinstance(item, str) and LEADING_ZERO.fullmatch(item)]
                found += [p for n, item in enumerate(value) for p in zero_ids(item, "%s[%d]" % (where, n))]
            else:
                found += zero_ids(value, where)
    elif isinstance(data, list):
        for n, item in enumerate(data):
            found += zero_ids(item, "%s[%d]" % (path, n))
    return found


def canon(value, key=""):
    """W73's canonical form: ids as strings, id lists sorted, object lists sorted by id."""
    if isinstance(value, dict):
        return {k: canon(v, k) for k, v in value.items()}
    if isinstance(value, list):
        items = [canon(v, key) for v in value]
        if items and all(isinstance(i, dict) and "id" in i for i in items):
            items.sort(key=lambda i: str(i["id"]))
        elif id_key(key) and all(isinstance(i, str) for i in items):
            items.sort()
        return items
    if id_key(key) and is_int(value):
        return str(value)
    return value


def hash8(fields):
    text = json.dumps(canon(fields), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def digest(prefix, fields):
    """`prefix:` and the first eight hex digits of the sha256 of the canonical JSON (W73)."""
    return "%s:%s" % (prefix, hash8(fields))


def identity(kind, obj):
    fields = IDENTITY.get(kind)
    if not fields:
        return dict(obj)
    found = {}
    for name in fields:
        names = (name,) + ALIASES.get((kind, name), ())
        found[name] = next((obj[n] for n in names if n in obj), None)
    return found


def automation_active(entry):
    """An automation's state as list_automations gives it (is_active), or as the older raw read does (active)."""
    return entry.get("is_active") if "is_active" in entry else entry.get("active")


def local_date(utc_text):
    return mc.stamp("date", mc.parse_utc(utc_text))


def local_minute_of_day():
    return mc.stamp("log")[-5:]


def parse_ref(text):
    """(version, revision, key or None) of `vNrM` or `vNrM#KEY`; None when out of form."""
    match = REF.fullmatch(str(text or ""))
    return (match.group(1), int(match.group(2)), match.group(3)) if match else None


def key_parent(key):
    return key.rsplit(".", 1)[0] if "." in key else None


def key_fits(key, kind):
    return kind in KEY_FORMS and bool(re.fullmatch(KEY_FORMS[kind], str(key)))


def split_cells(line):
    parts = re.split(r"(?<!\\)\|", line.strip())
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [part.strip().replace("\\|", "|") for part in parts]


def front_text(pairs):
    return "---\n" + "".join('%s: "%s"\n' % (key, str(value).replace("\\", "\\\\").replace('"', '\\"'))
                             for key, value in pairs) + "---\n"


def normalise_prompt(text):
    return str(text).replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


# The frozen blueprint: the element-key table and the prompt blocks (U1, W42).

def unquote(cell):
    """A cell with one pair of backticks around it stripped."""
    return cell[1:-1] if len(cell) > 1 and cell.startswith("`") and cell.endswith("`") else cell


def table_cells(text):
    """(header, [cells per row], problems) of the `## Element keys` table; header None when there is no heading."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = next((n for n, line in enumerate(lines) if line.rstrip() == "## Element keys"), None)
    if start is None:
        return None, [], []
    rows, problems, header, n = [], [], None, start + 1
    while n < len(lines) and not lines[n].strip():
        n += 1
    while n < len(lines) and lines[n].startswith("|"):
        cells = split_cells(lines[n])
        n += 1
        if header is None:
            header = [cell.lower() for cell in cells]
            if header[:3] != ["key", "kind", "name"]:
                problems.append("the header reads %s" % " | ".join(header))
                return header, [], problems
            continue
        if cells and all(cell and set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(cells)
    if header is None:
        problems.append("no table follows the heading")
    return header or [], rows, problems


def element_table(text):
    """(rows [(key, kind, name)], problems [text]) of the `## Element keys` table; rows None when there is none."""
    header, cells_rows, problems = table_cells(text)
    if header is None:
        return None, []
    rows = []
    for cells in cells_rows:
        cells = cells + [""] * (3 - len(cells))
        rows.append((unquote(cells[0]), cells[1], cells[2]))
    seen = set()
    for key, kind, name in rows:
        if key in seen:
            problems.append("the key %s repeats" % key)
        seen.add(key)
        if kind not in TYPES and kind != "ui_step":
            problems.append("%s has the kind %r, which is no object type" % (key, kind))
        elif not key_fits(key, kind):
            problems.append("%s is not a key of the kind %s" % (key, kind))
        if not name:
            problems.append("%s has no name" % key)
    return rows, problems


def element_recipients(text):
    """({key: [recipient]}, problems) of the table's `notifies` column (R20 (a)); None when the column is absent.

    A cell is empty for nobody, `user` for the user alone, or recipients in W45's forms (a user id, team:<id>,
    email:<address>), several separated by commas, `user` among them if the user is one."""
    header, cells_rows, problems = table_cells(text)
    if header is None or problems or "notifies" not in header[3:]:
        return None, []
    column, found, problems = header.index("notifies", 3), {}, []
    for cells in cells_rows:
        key = unquote(cells[0]) if cells else ""
        cell = cells[column] if column < len(cells) else ""
        parts = [unquote(part.strip()) for part in cell.split(",")] if cell.strip() else []
        recipients = []
        for part in parts:
            if part != "user" and not RECIPIENT.fullmatch(part):
                problems.append("%s notifies %r, which is not user, a user id, team:<id> or email:<address>" % (key, part))
            elif part in recipients:
                problems.append("%s names the recipient %s twice" % (key, part))
            else:
                recipients.append(part)
        if recipients and len(cells) > 1 and cells[1] == "ui_step":
            problems.append("%s is a UI step, which notifies nobody" % key)
        found[key] = recipients
    return found, problems


TEMPLATE_CELL = re.compile(r"([1-9][0-9]*) ([a-z_]+)")


def element_templates(text):
    """({key: {template_id, entity}}, problems) of the table's optional `template` column (A38); {} when it is absent.

    A cell is empty, or on a board row that installs a native, monday's template id of that native and the entity the
    catalogue names for it (native-objects.md 3.1 and 4.1), such as `5678953932 leads`."""
    header, cells_rows, problems = table_cells(text)
    if header is None or problems or "template" not in header[3:]:
        return {}, []
    column, found, problems = header.index("template", 3), {}, []
    for cells in cells_rows:
        key = unquote(cells[0]) if cells else ""
        cell = unquote(cells[column].strip()) if column < len(cells) else ""
        if not cell:
            continue
        kind, match = cells[1] if len(cells) > 1 else "", TEMPLATE_CELL.fullmatch(cell)
        info = installable(match.group(1)) if match else None
        if kind != "board":
            problems.append("%s is a %s: only a board row installs a native" % (key, kind or "row of no kind"))
        elif match is None:
            problems.append("%s names the template %r, which is not <template id> <entity>" % (key, cell))
        elif info is None:
            problems.append("%s names the template %s, which is no native board of the catalogue" % (key, match.group(1)))
        elif info[1] != match.group(2):
            problems.append("%s names %s for the template %s, which installs %s" % (
                key, match.group(2), match.group(1), info[1]))
        else:
            found[key] = {"template_id": match.group(1), "entity": info[1]}
    return found, problems


def prompt_block(text, key):
    """The text of the first fenced `text` block after `### Prompt <KEY>`, or None."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = next((n for n, line in enumerate(lines) if line.rstrip() == "### Prompt %s" % key), None)
    if start is None:
        return None
    for n in range(start + 1, len(lines)):
        opening = re.fullmatch(r"(`{3,})(\w*)\s*", lines[n])
        if opening:
            if opening.group(2) != "text":
                return None
            for m in range(n + 1, len(lines)):
                if lines[m].rstrip() == opening.group(1):
                    return "\n".join(lines[n + 1:m])
            return None
        if lines[n].startswith("#"):
            return None
    return None


# Reading the record inside the mutex.

class Ledger:
    """One command's view of the record: account.json, CLIENT.md, and (with a short id) one strand's files."""

    def __init__(self, root, short=None):
        self.root, self.short = root, short
        self.folder = self.strand = self.build = self.build_path = None
        self.reload()

    def rel(self, path):
        return mc.relative(self.root, path)

    def reload(self):
        self.account = mc.read_json(self.root / "account.json", "account.json")
        if not isinstance(self.account, dict):
            raise mc.CannotRun(("account.json", mc.WHOLE_FILE, "the file is not a JSON object", "an account/1 object"))
        self.client = mc.front_matter(mc.read_text(self.root / "CLIENT.md", "CLIENT.md"), "CLIENT.md")
        if self.short is not None:
            self.folder = mc.strand_dir(self.root, self.short)
            path = self.folder / "STRAND.md"
            self.strand = mc.front_matter(mc.read_text(path, self.rel(path)), self.rel(path))
            self.build_path = self.folder / "solution" / "build.json"
            self.build = mc.read_json(self.build_path, self.build_rel) if self.build_path.is_file() else None
            if self.build is not None and not isinstance(self.build, dict):
                raise mc.CannotRun((self.build_rel, mc.WHOLE_FILE, "the file is not a JSON object", "a build/2 object"))

    @property
    def build_rel(self):
        return self.rel(self.build_path)

    @property
    def version(self):
        return (self.strand or {}).get("version", "none")

    @property
    def qualified(self):
        return "%s/%s" % (self.short, self.version)

    def version_path(self, version=None):
        version = version or self.version
        if not re.fullmatch(r"v\d+\.\d+", str(version)):
            return None
        return self.folder / "versions" / version / "version.md"

    def version_fields(self, version=None):
        path = self.version_path(version)
        if path is None or not path.is_file():
            return None
        return mc.front_matter(mc.read_text(path, self.rel(path)), self.rel(path))

    def newer(self):
        """G57, W36: one finding per file this command touches whose schema is newer than the plugin's."""
        checks = [("CLIENT.md", self.client.get("schema"), "client"),
                  ("account.json", self.account.get("schema"), "account")]
        live = self.root / "live" / "live-map.md"
        if live.is_file():
            checks.append(("live/live-map.md", mc.front_matter(mc.read_text(live, "live/live-map.md"),
                                                               "live/live-map.md").get("schema"), "live-map"))
        if self.short is not None:
            checks.append((self.rel(self.folder / "STRAND.md"), self.strand.get("schema"), "strand"))
            path = self.version_path()
            if path is not None and path.is_file():
                checks.append((self.rel(path), (self.version_fields() or {}).get("schema"), "version"))
            if self.build is not None:
                checks.append((self.build_rel, self.build.get("schema"), "build"))
        return [(rel, "schema", "schema %s is newer than this plugin's, or not this file's: the ledger refuses "
                 "writes" % found, "%s/%d" % (name, mc.SCHEMAS[name])) for rel, found, name in checks
                if mc.schema_newer(found, name)]

    def require_build(self):
        if self.build is None:
            refuse((self.rel(self.folder / "solution" / "build.json"), mc.WHOLE_FILE,
                    "strand %s has no ledger: a %s strand, or no revision approved yet" % (
                        self.short, self.strand.get("kind")),
                    "a platform or hybrid strand whose approval created solution/build.json"))

    @property
    def objects(self):
        return self.build.setdefault("objects", {})

    @property
    def index(self):
        return self.account.setdefault("guard_index", {})

    @property
    def client_ids(self):
        return [str(i) for i in self.index.get("client_workspace_ids") or []]

    def targets(self, short=None):
        entry = (self.index.get("build_targets_by_strand") or {}).get(short or self.short) or {}
        return [str(i) for i in entry.get("workspace_ids") or []]

    @property
    def bound_user(self):
        return str((self.account.get("account") or {}).get("bound_user_id"))

    def approval(self, ref):
        """The one approvals[] entry a `vNrM` ref spells, read from this file as it is now (W43)."""
        parsed = parse_ref(ref)
        if parsed is None or self.build is None:
            return None
        return next((a for a in self.build.get("approvals") or [] if str(a.get("version")) == parsed[0]
                     and str(a.get("revision")) == str(parsed[1])), None)

    def frozen(self, entry):
        """(text, record-relative name) of an approval's frozen file, or (None, name) when it is missing."""
        rel = str(entry.get("frozen_file") or "")
        path = mc.record_path(self.root, rel, self.rel(self.folder))
        name = self.rel(path)
        return (mc.read_text(path, name) if path.is_file() else None), name

    def operational(self):
        return operational_workspaces()

    def place(self, monday_id):
        """The workspace the record places a board, doc, view or column id in (W40), or None."""
        for key, row in self.objects.items():
            if str(row.get("id")) == monday_id:
                return self.row_workspace(key)
        for row in (self.account.get("live_objects") or {}).values():
            if str(row.get("monday_id")) == monday_id and DIGITS.fullmatch(str(row.get("workspace") or "")):
                return str(row["workspace"])
        return None

    def holder_of(self, monday_id):
        """The bare key of this ledger's row, or else the qualified live-map key, that holds a monday id, or None."""
        found = sorted(k for k, r in self.objects.items() if str(r.get("id")) == str(monday_id))
        found = found or shared_rows(self.account.get("live_objects") or {}, monday_id)
        return found[0] if found else None

    def row_workspace(self, key, seen=()):
        row = self.objects.get(key)
        if row is None or key in seen:
            return None
        if row.get("type") == "workspace":
            return str(row["id"]) if row.get("id") else None
        if row.get("workspace"):
            return str(row["workspace"])
        parent = row.get("parent_key")
        if parent and ":" in str(parent):
            live = (self.account.get("live_objects") or {}).get(parent) or {}
            if live.get("kind") == "workspace":
                return str(live.get("monday_id"))
            found = live.get("workspace")
            return str(found) if found and DIGITS.fullmatch(str(found)) else None
        return self.row_workspace(parent, seen + (key,)) if parent else None

    def run(self, run_id):
        return next((r for r in (self.build or {}).get("runs") or [] if r.get("id") == run_id), None)


def operational_workspaces():
    """{workspace id: the line that names it}: never_show_workspaces of local/settings.json and the workspace of
    every never-demo line of local/sandbox-accounts.txt (W41)."""
    found = {}
    for item in (mc.read_settings() or {}).get("never_show_workspaces") or []:
        if isinstance(item, dict) and item.get("id"):
            found[str(item["id"])] = 'local/settings.json never_show_workspaces: %s (%s)' % (item["id"], item.get("name"))
    for fields, line in sandbox_lines():
        if fields[0] == "never-demo" and len(fields) > 3 and DIGITS.fullmatch(fields[3]):
            found.setdefault(fields[3], "local/sandbox-accounts.txt: %s" % line)
    for listed in list(found):  # R4: a home file that spells an id with a leading zero still names that id
        if DIGITS.fullmatch(listed) and listed.lstrip("0"):
            found.setdefault(listed.lstrip("0"), found[listed])
    return found


def sibling_workspaces(root):
    """[(home-relative name, {workspace ids})] of every other client record under the home: its client_workspace_ids
    and superseded_workspaces ids, read for ids only inside this record's hold (R8, the cross-record check)."""
    found, base = [], mc.home() / "clients"
    for folder in sorted(base.iterdir()) if base.is_dir() else []:
        path = folder / "account.json"
        if not path.is_file() or folder.resolve() == root.resolve():
            continue
        name = "clients/%s/account.json" % folder.name
        data = mc.read_json(path, name)
        data = data if isinstance(data, dict) else {}
        index = data.get("guard_index") if isinstance(data.get("guard_index"), dict) else {}
        listed = index.get("client_workspace_ids") if isinstance(index.get("client_workspace_ids"), list) else []
        older = data.get("superseded_workspaces") if isinstance(data.get("superseded_workspaces"), list) else []
        ids = {str(i) for i in listed} | {str(item.get("id")) for item in older if isinstance(item, dict)}
        found.append((name, ids))
    return found


def sandbox_lines():
    path = mc.home() / "local" / "sandbox-accounts.txt"
    if not path.is_file():
        return []
    found = []
    for line in mc.read_text(path, "local/sandbox-accounts.txt").split("\n"):
        text = line.split("#", 1)[0].strip()
        if text:
            found.append(([field.strip() for field in text.split("|")], line.strip()))
    return found


def input_json(root, value, flag):
    """A JSON file the session hands, inside the record (W91), refused when an id is a number (W35)."""
    raw = Path(value)
    if raw.is_absolute():
        try:
            rel = raw.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            refuse((raw.as_posix(), flag, "the file lies outside the record", "a file inside the record, such as "
                    "under .work/strands/<id>/, so every finding names a record-relative path"))
    else:
        rel = value
    path = mc.record_path(root, rel)
    name = mc.relative(root, path)
    if not path.is_file():
        raise mc.CannotRun((name, mc.WHOLE_FILE, "the file %s names is missing" % flag, "a file the session wrote"))
    data = mc.read_json(path, name)
    if not isinstance(data, dict):
        raise mc.CannotRun((name, mc.WHOLE_FILE, "the file is not a JSON object", "a JSON object"))
    numbers = numeric_ids(data)
    refuse(*[(name, where, "an id stored as a number", "every monday id a string of digits, as GraphQL returns ID")
             for where in numbers] + [(name, where, "an id spelt with a leading zero", "a monday id as digits with no "
                                       "leading zero, so one id has one spelling (R4)") for where in zero_ids(data)])
    return data, name


def digits(flag, value, file="(flags)"):
    return None if value is None or ID.fullmatch(str(value)) else (
        file, flag, "%r is not a monday id" % value, "a string of digits with no leading zero, stored as given (R4)")


def fence_flags(args):
    return [(mc.LOCK_REL, field, "no %s was presented" % flag, FENCE_EXPECTED) for flag, field, value in (
        ("--lease-epoch", "epoch", args.lease_epoch), ("--session-label", "session_label", args.session_label),
        ("--run-id", "run_id", args.run_id)) if not value]


def holder_reasons(root, short):
    status = mc.lease_status(root)
    if status.get("held") and status.get("strand") != short:
        return [(mc.LOCK_REL, "strand", "the build lease is held by strand %s, not strand %s" % (
            status.get("strand"), short), "the strand that holds the build lease")]
    return []


def fence(root, args):
    """G51: the fence runs before every account-affecting write; a refusal is exit 1, a fence that cannot run
    (exit 3) propagates and nothing is written."""
    ok, reason = mc.lease_fence(root, args.lease_epoch, args.session_label, args.run_id)
    if not ok:
        raise mc.Refusal((mc.LOCK_REL, "lease", "the fence refused the write: %s" % reason, FENCE_EXPECTED))


def sha_reason(led, expect):
    """W34: --expect-sha against the bytes of build.json; `none` means it must not exist yet."""
    path = led.folder / "solution" / "build.json"
    rel = led.rel(path)
    if not expect:
        return (rel, "sha256", "no --expect-sha was presented", "the sha256 that ledger.py check or the last write "
                "printed, or none for a ledger not created yet")
    found = mc.sha256_file(path) if path.is_file() else None
    want = None if expect == "none" else expect
    if found != want:
        return (rel, "sha256", "the file changed since it was read (now %s)" % (found or "absent"),
                "the file as read (%s): read its sha again with ledger.py check" % (want or "absent"))
    return None


def run_reasons(led, run_id, states=("running",)):
    run = led.run(run_id)
    if run is None or run.get("state") not in states:
        return [(led.build_rel, "runs", "run %s is not a %s run of strand %s" % (
            run_id, " or ".join(states), led.short), "the run id run start returned to this session")]
    return []


def account_reasons(led, run_id):
    """R14: no write while the run's last account check found another account."""
    checks = (led.run(run_id) or {}).get("account_checks") or []
    if checks and isinstance(checks[-1], dict) and checks[-1].get("result") == "mismatch":
        return [(led.build_rel, "runs[].account_checks", "the last account check of run %s (before %s) read another "
                 "account than the bound one" % (run_id, checks[-1].get("before")), "stop before any write; once the "
                 "bound account is read again, run heartbeat --account-check match with the user's words "
                 "(--answer-words)")]
    return []


def current_approval(led):
    """(entry, ref) of the approval of the version being built: version.md's revision, the entry run start checked."""
    fields = led.version_fields() if led.version != "none" else None
    ref = "%sr%s" % (led.version, (fields or {}).get("revision", "none"))
    return (led.approval(ref) if fields else None), ref, fields


def latest_ref(led):
    """The vNrM of the strand's latest approval of its current version, or None (R12)."""
    found = [a for a in (led.build or {}).get("approvals") or [] if a.get("version") == led.version and is_int(
        a.get("revision"))]
    return "%sr%d" % (led.version, max(a["revision"] for a in found)) if found else None


def inventory_copy(led):
    """(data, record-relative name) of the inventory copy the last reconcile of this strand left, or (None, name)."""
    path = led.root / ".work" / "strands" / led.short / "live-inventory.json"
    name = led.rel(path)
    if not path.is_file():
        return None, name
    try:
        data = input_json(led.root, name, "--inventory")[0]
    except mc.MMBError:
        return None, name
    return (None if any(inventory_reasons(data, name, led.short)) else data), name


def after(later, earlier):
    """True when both are UTC stamps and the first is strictly later."""
    return is_utc(later) and is_utc(earlier) and mc.parse_utc(later) > mc.parse_utc(earlier)


def recovery_reasons(led, run_id):
    """R10: a run that started with recovery first takes no write and no departure before a reconcile read the
    account after the run began."""
    run = led.run(run_id) or {}
    if not run.get("recovery_first"):
        return []
    data, name = inventory_copy(led)
    if data is not None and after(data.get("read_at"), run.get("started_at")):
        return []
    return [(led.build_rel, "runs[].recovery_first", "run %s started with recovery first (an interrupted run or a row "
             "left attempting) and no reconcile has read the account since it began" % run_id,
             "ledger.py reconcile --strand %s --inventory <a read made now>, and the user's approval of its plan, "
             "before any new write (A8.11)" % led.short)]


def retry_reasons(led, key, row, what):
    """R10: a row left attempting (a timeout, a lost reply) is retried or departed only after a reconcile over a read
    made after its attempt began classes it `retry`; a kind no inventory carries needs that reconcile to have run,
    since the read it names is the session's."""
    rel, field = led.build_rel, "objects.%s.status" % key
    started = (row.get("attempt") or {}).get("started_at")
    data, name = inventory_copy(led)
    if data is None:
        return [(name, mc.WHOLE_FILE, "%s of %s, which may have been applied, with no reconcile made" % (what, key),
                 "ledger.py reconcile --strand %s --inventory <a read made after the attempt>, then %s" % (
                     led.short, what))]
    if not after(data.get("read_at"), started):
        return [(name, "read_at", "the last reconcile read the account at %s, not after the attempt on %s began (%s)" % (
            data.get("read_at"), key, started), "a reconcile over a read made after the attempt began")]
    plan = Reconciler(led, Inventory(data)).run()
    found = next((e for e in plan["elements"] if e["key"] == key), None)
    if found is None:
        if any(item["key"] == key for item in plan["not_in_inventory"]):
            return []
        return [(rel, field, "the last reconcile gives %s no class" % key, "a reconcile that classes it retry")]
    if found["class"] != "retry":
        return [(rel, field, "the last reconcile classes %s %s (live %s)" % (key, found["class"], ", ".join(
            found["live_ids"]) or "none"), "retry: an adopt is recorded with record, a duplicate goes to its "
                 "proposals, each with the user's approval")]
    return []


def commit(command, steps, run_id=None, next_call=None, root=None):
    """Run the writes of one call in order (W25). The first write failing is exit 3 naming its file with nothing
    committed; a later one is exit 3 with error field `committed` and the `committed` report (W33), whose `shas`
    gives the new sha256 of each file written, so the retry's --expect-sha needs no check first (R19)."""
    written, lease = [], None
    for index, (rel, step, lease_mark) in enumerate(steps):
        try:
            step()
        except Exception as exc:  # R20: after a first write, any failure is reported with what stands
            why = exc.findings[0]["problem"] if isinstance(exc, mc.MMBError) else "%s: %s" % (type(exc).__name__, exc)
            if not written:
                if not isinstance(exc, OSError):
                    raise
                raise mc.CannotRun((rel, mc.WHOLE_FILE, "could not write the file: %s; none of this call's own writes "
                                    "was made, though a fence that passed before them moved the lease heartbeat "
                                    "(R19)" % why, "the same call again once no other program holds the file"))
            shas = {r: mc.sha256_file(mc.record_path(root, r)) for r in written if r != mc.LOCK_REL} if root else {}
            report = {"command": command, "written": written, "not_written": [r for r, _, _ in steps[index:]],
                      "lease": lease, "run_id": run_id, "next": next_call, "shas": shas}
            raise mc.CannotRun((rel, "committed", "%s; %d earlier write(s) of this call stand" % (why, len(written)),
                                next_call), committed=report)
        written.append(rel)
        lease = lease_mark if lease_mark is not None else lease


def json_step(root, path, data):
    return lambda: mc.write_file(path, mc.json_text(data), root)


def save_build(led, command, run_id=None, next_call=None):
    led.build["updated_at"] = mc.stamp("utc")
    commit(command, [(led.build_rel, json_step(led.root, led.build_path, led.build), None)], run_id, next_call)
    return {led.build_rel: mc.sha256_file(led.build_path)}


def beat(led, run_id):
    run = led.run(run_id)
    if run is not None:
        run["heartbeat_at"] = mc.stamp("utc")


def entry_log(strand, kind, version, key, lines):
    """W21: the log entry the skill writes through record.py log, printed and never written here."""
    return {"strand": strand, "type": kind, "version": version, "key": key, "lines": lines}


def strand_short(args):
    """W92: who asked; on reconcile --classify-only, the sibling named by --asked-by."""
    return getattr(args, "asked_by", None) or getattr(args, "strand", None)


def ordered_row(row):
    """A row with every ledger field present, in record-map order; fields it already had keep their values."""
    defaults = {"changed_in": [], "owner_user_ids": [], "notifies": [], "companions": {}, "item_ids": [],
                "workspace_scope": [], "refs": [], "assumption_refs": [], "read_values": {}, "irreversible": False,
                "sample_data": False}
    out = {name: row[name] if name in row else (defaults[name] if name in defaults else None) for name in ROW_FIELDS}
    out.update({name: value for name, value in row.items() if name not in out})
    if isinstance(out.get("changed_in"), list):
        out["changed_in"] = list(out["changed_in"])
    return out


# check (W63): what the ledger owns, writing nothing.

def is_str(value):
    return isinstance(value, str) and bool(value)


def opt_str(value):
    return value is None or isinstance(value, str)


def str_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_utc(value):
    try:
        return bool(mc.parse_utc(value))
    except (TypeError, ValueError):
        return False


def opt_utc(value):
    return value is None or is_utc(value)


ACCOUNT_BLOCKS = (("schema", is_str, "account/1"), ("client_slug", lambda v: isinstance(v, str), "the client's slug"),
                  ("updated_at", opt_utc, "null or a UTC stamp"), ("account", lambda v: isinstance(v, dict), "an object"),
                  ("client_workspaces", lambda v: isinstance(v, dict), "an object keyed by product"),
                  ("api", lambda v: isinstance(v, dict), "an object"),
                  ("change_check", lambda v: isinstance(v, dict), "an object"),
                  ("native_map", lambda v: isinstance(v, dict), "an object"),
                  ("guard_index", lambda v: isinstance(v, dict), "an object"),
                  ("live_objects", lambda v: isinstance(v, dict), "an object keyed by qualified key"),
                  ("prior_builds", lambda v: isinstance(v, list), "a list"))
ACCOUNT_FIELDS = (("id", is_str), ("slug", is_str), ("name", is_str), ("kind", lambda v: v in TARGET_OF),
                  ("build_target", lambda v: v in TARGET_OF.values()), ("tier", is_str), ("bound_user_id", is_str),
                  ("bound_at", is_str), ("builder_role", is_str),
                  ("products", lambda v: isinstance(v, list) and all(isinstance(p, dict) and is_str(p.get("id"))
                                                                     and p.get("kind") in ("core", "crm", "service")
                                                                     for p in v)))
GUARD_LISTS = ("account_products", "template_source_ids", "unreadable_intermediate_ids", "template_view_ids",
               "native_default_names_and_terminology", "client_workspace_ids")
GUARD_DICTS = ("product_workspaces", "native_board_index", "native_board_ids_by_entity", "reserved_column_ids",
               "portal_object_ids", "build_targets_by_strand", "lease", "record_provenance", "native_installs")
BUILD_TOP = (("schema", is_str), ("client_slug", lambda v: isinstance(v, str)), ("strand", lambda v: isinstance(v, str)),
             ("account_ref", is_str), ("account_id_at_bind", is_str),
             ("lease_epoch_at_run", lambda v: v is None or is_int(v)), ("reads_live", str_list),
             ("updated_at", opt_utc), ("approvals", lambda v: isinstance(v, list)),
             ("preflight", lambda v: v is None or isinstance(v, dict)), ("runs", lambda v: isinstance(v, list)),
             ("objects", lambda v: isinstance(v, dict)), ("irreversible_yes", lambda v: isinstance(v, list)),
             ("departures", lambda v: isinstance(v, list)), ("ui_steps", lambda v: isinstance(v, list)))
APPROVAL_FIELDS = (("version", lambda v: is_str(v) and bool(re.fullmatch(r"v\d+\.\d+", v))), ("qualified_version", is_str),
                   ("revision", is_int), ("frozen_file", is_str), ("sha256", is_str), ("approved_at", is_utc),
                   ("approved_words", is_str), ("approved_in_session", is_str), ("element_count", is_int),
                   ("irreversible_listed", str_list), ("automations_listed", str_list),
                   ("live_objects_touched", lambda v: isinstance(v, list) and all(
                       isinstance(t, dict) and is_str(t.get("key")) and t.get("constraint") in CONSTRAINTS for t in v)))
APPROVAL_OPTIONAL = (("approval_mode", lambda v: v in APPROVAL_MODES), ("workflows_listed", str_list),
                     ("agents_listed", str_list), ("sequences_listed", str_list),
                     ("notifies_approved", lambda v: isinstance(v, dict) and all(str_list(r) for r in v.values())),
                     ("native_installs", lambda v: isinstance(v, dict) and all(
                         isinstance(t, dict) and installable(str(t.get("template_id"))) is not None and
                         installable(str(t.get("template_id")))[1] == t.get("entity") for t in v.values())),
                     ("rests_on", lambda v: v is None or (isinstance(v, dict) and all(
                         k in v for k in ("clearance", "purpose", "assumptions", "assumed_terms", "forks_on_leaning")))))
RUN_FIELDS = (("id", lambda v: is_str(v) and bool(re.fullmatch(r"run-\d{4}-\d{2}-\d{2}-\d+", v))), ("version", is_str),
              ("kind", lambda v: v in RUN_KINDS), ("session_label", is_str), ("lease_epoch", lambda v: v is None or is_int(v)),
              ("started_at", is_utc), ("heartbeat_at", opt_utc), ("ended_at", opt_utc),
              ("state", lambda v: v in RUN_STATES),
              ("calls_estimated", lambda v: v is None or (isinstance(v, list) and len(v) == 2 and all(map(is_int, v)))),
              ("calls_used", lambda v: v is None or is_int(v)), ("account_checks", lambda v: isinstance(v, list)))
ROW_REQUIRED = (("type", lambda v: v in TYPES), ("id", opt_str), ("name", is_str), ("parent_key", opt_str),
                ("parent_id", opt_str), ("origin", lambda v: v in ORIGINS),
                ("source_strand", lambda v: v is None or (isinstance(v, str) and bool(re.fullmatch(r"\d{3}", v)))),
                ("introduced_in", is_str), ("changed_in", str_list), ("state", lambda v: v is None or v in STATES),
                ("status", lambda v: v in STATUSES),
                ("attempt", lambda v: v is None or (isinstance(v, dict) and all(
                    k in v for k in ("run_id", "started_at", "intent_digest")))),
                ("verify", lambda v: v is None or (isinstance(v, dict) and all(
                    k in v for k in ("read", "at", "result", "digest", "note")) and v.get("result") in RESULTS)),
                ("creator_user_id", opt_str), ("owner_user_ids", str_list), ("irreversible", lambda v: isinstance(v, bool)),
                ("sample_data", lambda v: isinstance(v, bool)), ("approval_ref", is_str), ("notifies", str_list),
                ("companions", lambda v: isinstance(v, dict) and set(v) <= set(COMPANIONS) and all(
                    isinstance(i, str) for i in v.values())),
                ("role", opt_str), ("prior_state", lambda v: True), ("blueprint_ref", opt_str))
ROW_OPTIONAL = (("url", opt_str), ("item_ids", str_list), ("product", lambda v: v in (None, "core", "crm", "service")),
                ("workspace", opt_str), ("workspace_scope", str_list),
                ("refs", lambda v: str_list(v) and all(re.fullmatch(r"(board|workspace|doc|view|column):\d+", r) for r in v)),
                ("assumption_refs", lambda v: str_list(v) and all(ASSUMPTION_ID.fullmatch(r) for r in v)),
                ("prompt_ref", opt_str), ("version_id_at_build", opt_str), ("live_key", opt_str),
                ("read_values", lambda v: isinstance(v, dict)),
                ("template_id", lambda v: v is None or (is_str(v) and installable(v) is not None)))
LIVE_CHECKS = (("monday_id", is_str), ("kind", lambda v: v in TYPES), ("name_at_build", lambda v: isinstance(v, str)),
               ("owner_strand", lambda v: v is None or (isinstance(v, str) and bool(re.fullmatch(r"\d{3}", v)))),
               ("introduced_in", lambda v: isinstance(v, str) and bool(re.fullmatch(r"\d{3}/v\d+\.\d+|client|native", v))),
               ("state", lambda v: v in STATES), ("constraint", lambda v: v in CONSTRAINTS),
               ("constraint_source", is_str), ("digest", opt_str), ("last_verified", opt_str),
               ("dependants", str_list))


class Checker:
    """W63: one pass over account.json, every build.json, the live map and the frozen files, writing nothing."""

    def __init__(self, root, only=None):
        self.root, self.only, self.blocking, self.warnings, self.shas = root, only, [], [], {}
        self.warned_files = set()

    def block(self, *finding):
        self.blocking.append(dict(zip(KEYS, finding)))

    def warn(self, *finding):
        self.warnings.append(dict(zip(KEYS, finding)))

    def run(self):
        root = self.root
        led = Ledger(root)
        for finding in led.newer():
            self.block(*finding)
        self.shas["account.json"] = mc.sha256_file(root / "account.json")
        account_ok = not mc.schema_newer(led.account.get("schema"), "account")
        self.account = led.account if account_ok else None
        if account_ok:
            self.account_shape(led.account)
        folders = [p for p in sorted((root / "strands").iterdir()) if p.is_dir() and re.match(r"\d{3}-", p.name)] \
            if (root / "strands").is_dir() else []
        for folder in folders:
            short = folder.name[:3]
            if self.only and short != self.only:
                continue
            strand = Ledger(root, short)
            for finding in strand.newer():
                if finding[0] not in ("CLIENT.md", "account.json", "live/live-map.md"):
                    self.block(*finding)
            if strand.build is None:
                continue
            self.shas[strand.build_rel] = mc.sha256_file(strand.build_path)
            if mc.schema_newer(strand.build.get("schema"), "build"):
                continue
            self.build_shape(strand)
        if account_ok:
            self.live_map(led)
            self.guard(led.account)
        return self

    def account_shape(self, account):
        name = "account.json"
        for key, test, expected in ACCOUNT_BLOCKS:
            if key not in account:
                self.block(name, key, "the field is missing", expected)
            elif not test(account[key]):
                self.block(name, key, "%s is not of its shape" % json.dumps(account[key])[:80], expected)
        block = account.get("account") if isinstance(account.get("account"), dict) else {}
        for key, test in ACCOUNT_FIELDS:
            if key not in block:
                self.block(name, "account." + key, "the field is missing", "the field record-map.md gives account/1")
            elif block[key] != "unbound" and not test(block[key]):
                self.block(name, "account." + key, "%s is not an allowed value" % json.dumps(block[key])[:80],
                           "the value set record-map.md gives")
        if block.get("kind") in TARGET_OF and block.get("build_target") != TARGET_OF[block["kind"]]:
            self.block(name, "account.build_target", "%s with kind %s" % (block.get("build_target"), block.get("kind")),
                       TARGET_OF[block["kind"]])
        check = account.get("change_check") if isinstance(account.get("change_check"), dict) else {}
        outcome = check.get("result", check.get("verdict"))
        if outcome is not None and outcome not in CHANGE_RESULTS:
            self.block(name, "change_check.result", "%r is not a change-check result" % outcome, " | ".join(CHANGE_RESULTS))
        index = account.get("guard_index") if isinstance(account.get("guard_index"), dict) else {}
        for key in GUARD_LISTS:
            if key in index and not isinstance(index[key], list):
                self.block(name, "guard_index." + key, "not a list", "a list")
        for key in GUARD_DICTS:
            if key in index and not isinstance(index[key], dict):
                self.block(name, "guard_index." + key, "not an object", "an object")
        for key, row in (account.get("live_objects") or {}).items() if isinstance(account.get("live_objects"), dict) else ():
            if not LOCAL_KEY.fullmatch(str(key)):
                self.block(name, "live_objects." + str(key), "the key is not qualified", "a key such as 001:B1")
            for field, test in LIVE_CHECKS:
                value = (row or {}).get(field)
                if not test(value):
                    self.block(name, "live_objects.%s.%s" % (key, field), "%s is not an allowed value" % json.dumps(value),
                               "the live_objects field as record-map.md gives it")
            if isinstance(row, dict) and "departed" in row and not is_str(row["departed"]):
                self.block(name, "live_objects.%s.departed" % key, "%s is not an allowed value" % json.dumps(
                    row["departed"]), "the departure's qualified version and decision, or no field at all")
            if isinstance(row, dict) and row.get("owner_strand") is None and not client_built(row):
                self.block(name, "live_objects.%s.owner_strand" % key, "a row built by %s with no owning strand" % (
                    row.get("introduced_in")), "the short id of the strand that built it; only a client or native row "
                    "has none (R17)")
        for where in numeric_ids(account):
            self.block(name, where, "an id stored as a number", "every monday id a string")
        live = account.get("live_objects") if isinstance(account.get("live_objects"), dict) else {}
        by_id = {}
        for key, row in sorted(live.items()):
            if isinstance(row, dict) and row.get("monday_id"):
                by_id.setdefault(str(row["monday_id"]), []).append(key)
        for oid, keys in sorted(by_id.items()):  # R5: one object, one constraint, whatever keys mirror it
            constraints = sorted({str(live[k].get("constraint")) for k in keys})
            if len(constraints) > 1:
                self.block(name, "live_objects.%s.constraint" % keys[0], "monday id %s is mirrored by %s with the "
                           "constraints %s" % (oid, ", ".join(keys), ", ".join(constraints)),
                           "one constraint for one object: ledger.py live-map set on each row to the same value")

    def build_shape(self, led):
        b, name = led.build, led.build_rel
        for key, test in BUILD_TOP:
            if key not in b:
                self.block(name, key, "the field is missing", "the field record-map.md gives build/2")
            elif not test(b[key]):
                self.block(name, key, "%s is not of its shape" % json.dumps(b[key])[:80], "the build/2 shape")
        bound = str(((self.account or {}).get("account") or {}).get("id"))
        if self.account is not None and str(b.get("account_id_at_bind")) not in (bound, "unbound"):
            self.block(name, "account_id_at_bind", "%s, while account.json is bound to %s" % (
                b.get("account_id_at_bind"), bound), bound)
        for where in numeric_ids(b):
            self.block(name, where, "an id stored as a number", "every monday id a string")
        approvals = [a for a in b.get("approvals") or [] if isinstance(a, dict)]
        tables = {}
        for n, entry in enumerate(approvals):
            self.approval_shape(led, n, entry, tables)
        running = [r for r in b.get("runs") or [] if isinstance(r, dict) and r.get("state") == "running"]
        if len(running) > 1:
            self.block(name, "runs", "%d runs are running at once: %s" % (len(running), ", ".join(
                str(r.get("id")) for r in running)), "at most one running run per strand")
        for n, run in enumerate(b.get("runs") or []):
            for key, test in RUN_FIELDS:
                if not isinstance(run, dict) or key not in run:
                    self.block(name, "runs[%d].%s" % (n, key), "the field is missing", "the runs[] field of build/2")
                elif not test(run[key]):
                    self.block(name, "runs[%d].%s" % (n, key), "%s is not an allowed value" % json.dumps(run[key])[:80],
                               "the runs[] value record-map.md gives")
            recon = run.get("reconcile") if isinstance(run, dict) else None
            if recon is not None and not (isinstance(recon, dict) and recon.get("mode") in RECONCILE_MODES and set(
                    recon.get("classes") or {}) <= set(RECONCILE_CLASSES)):
                self.block(name, "runs[%d].reconcile" % n, "the reconcile object is out of shape",
                           "{at, mode: classify-only, classes of the seven reconcile classes, findings}")
            if isinstance(run, dict) and run.get("state") == "running" and is_utc(run.get("heartbeat_at")):
                age, stale = mc.heartbeat_age(run["heartbeat_at"])
                if stale:
                    self.warn(name, "runs[%d].heartbeat_at" % n, "run %s is running with a heartbeat %s" % (
                        run.get("id"), mc.heartbeat_words(age, stale)), "recovery first: reconcile before any write")
        objects = b.get("objects") if isinstance(b.get("objects"), dict) else {}
        for key, row in objects.items():
            self.row_shape(led, key, row if isinstance(row, dict) else {}, tables)
        for n, entry in enumerate(b.get("irreversible_yes") or []):
            self.yes_shape(led, n, entry if isinstance(entry, dict) else {}, approvals)
        for n, entry in enumerate(b.get("departures") or []):
            entry = entry if isinstance(entry, dict) else {}
            decision = str(entry.get("decision"))
            for key in ("key", "version", "what", "error_code", "attempts", "decision"):
                if key not in entry:
                    self.block(name, "departures[%d].%s" % (n, key), "the field is missing", "the departures[] shape")
            if not (decision in ("blueprint-revision", "later-retry") or re.fullmatch(r"ui-step U\d+", decision)):
                self.block(name, "departures[%d].decision" % n, "%r is not a departure decision" % decision,
                           "ui-step U<n> | blueprint-revision | later-retry")
            if not isinstance(entry.get("attempts"), list) or len(entry.get("attempts") or []) > 2:
                self.block(name, "departures[%d].attempts" % n, "not a list of at most two call forms",
                           "the first call form and at most one different one")
        for n, step in enumerate(b.get("ui_steps") or []):
            step = step if isinstance(step, dict) else {}
            if not key_fits(step.get("key"), "ui_step"):
                self.block(name, "ui_steps[%d].key" % n, "%r is not a UI step key" % step.get("key"), "U<n>")
            if step.get("status") not in UI_STATUSES:
                self.block(name, "ui_steps[%d].status" % n, "%r is not a UI step status" % step.get("status"),
                           " | ".join(UI_STATUSES))

    def frozen_table(self, led, entry, tables):
        """The element table of an approval's frozen file: rows, or None when the file predates the pin."""
        rel = str(entry.get("frozen_file"))
        if rel not in tables:
            text, name = led.frozen(entry)
            tables[rel] = (None, name, text) if text is None else (element_table(text)[0], name, text)
            if text is not None and tables[rel][0] is None and name not in self.warned_files:
                self.warned_files.add(name)
                self.warn(name, "## Element keys", "frozen before the element-key table was pinned: keys not resolved",
                          "a revision frozen with the ## Element keys table that record-map.md pins under blueprint/1")
        return tables[rel]

    def approval_shape(self, led, n, entry, tables):
        name = led.build_rel
        for key, test in APPROVAL_FIELDS:
            if key not in entry:
                self.block(name, "approvals[%d].%s" % (n, key), "the field is missing", "the approvals[] field of build/2")
            elif not test(entry[key]):
                self.block(name, "approvals[%d].%s" % (n, key), "%s is not of its shape" % json.dumps(entry[key])[:80],
                           "the approvals[] shape record-map.md gives")
        for key, test in APPROVAL_OPTIONAL:
            if key in entry and not test(entry[key]):
                self.block(name, "approvals[%d].%s" % (n, key), "%s is not of its shape" % json.dumps(entry[key])[:80],
                           "the approvals[] shape record-map.md gives")
        if entry.get("approval_mode") == "own-account-poc" and self.account is not None and re.fullmatch(
                r"v\d+\.\d+", str(entry.get("version"))):
            derived = approval_mode(led, entry["version"], led.version_fields(entry["version"]))[0]
            if derived != "own-account-poc":  # R13: the card's one yes is for a proof of concept in the user's account
                self.block(name, "approvals[%d].approval_mode" % n, "own-account-poc, while the record's build target "
                           "and the version's purpose give %s" % derived, "own-account-poc only on an own-account "
                           "record building a proof of concept (A28, W44)")
        rows, frozen, text = self.frozen_table(led, entry, tables)
        if text is None:
            self.block(name, "approvals[%d].frozen_file" % n, "%s is missing" % frozen, "the frozen revision on disk")
            return
        sha = mc.sha256_file(mc.record_path(led.root, frozen))
        if sha != entry.get("sha256"):
            self.block(frozen, "sha256", "the frozen file hashes to %s, the approval records %s" % (sha, entry.get("sha256")),
                       "the frozen copy as approved: a frozen file is never edited")

    def ref_reasons(self, led, key, field, value, tables, prompt=False):
        name = led.build_rel
        parsed = parse_ref(value)
        if parsed is None or parsed[2] is None:
            return self.block(name, "objects.%s.%s" % (key, field), "%r is not of the form vNrM#KEY" % value, "v0.1r1#B1")
        entry = led.approval("v%sr%d" % (parsed[0][1:], parsed[1]))
        if entry is None:
            return None  # the revision half is record.py check's (C129)
        rows, frozen, text = self.frozen_table(led, entry, tables)
        if rows is None:
            return None
        if parsed[2] not in {row[0] for row in rows}:
            self.block(name, "objects.%s.%s" % (key, field), "%s: the key %s is not a row of the element-key table of %s"
                       % (value, parsed[2], frozen), "a key of that revision's ## Element keys table")
        elif prompt and prompt_block(text, parsed[2]) is None:
            self.block(name, "objects.%s.%s" % (key, field), "%s: %s holds no prompt block for %s" % (
                value, frozen, parsed[2]), "a ### Prompt %s heading with a fenced text block" % parsed[2])

    def row_shape(self, led, key, row, tables):
        name, field = led.build_rel, "objects." + key
        for item, test in ROW_REQUIRED:
            if item not in row:
                self.block(name, "%s.%s" % (field, item), "the field is missing", "the objects field of build/2")
            elif not test(row[item]):
                self.block(name, "%s.%s" % (field, item), "%s is not an allowed value" % json.dumps(row[item])[:80],
                           "the objects value record-map.md gives")
        for item, test in ROW_OPTIONAL:
            if item in row and not test(row[item]):
                self.block(name, "%s.%s" % (field, item), "%s is not an allowed value" % json.dumps(row[item])[:80],
                           "the objects value record-map.md gives")
        kind = row.get("type")
        if ":" in key or not key_fits(key, kind):
            self.block(name, field, "the key is not a bare key of the type %s" % kind, "a bare key such as B1, of its type")
        if row.get("template_id") and (kind != "board" or row.get("origin") != "created"):
            self.block(name, field + ".template_id", "a template on a %s %s row" % (row.get("origin"), kind),
                       "a template only on a created board row, the native this strand installs (A38)")
        if row.get("state") == "inactive" and kind not in INACTIVE_OK:
            self.block(name, field + ".state", "inactive on a %s row" % kind, "inactive only for " + ", ".join(INACTIVE_OK))
        if row.get("status") == "verified" and (row.get("verify") or {}).get("result") != "match":
            self.block(name, field + ".verify", "a verified row whose read-back is not a match", "verify.result match")
        origin = row.get("origin")
        needs = origin in ("pre-existing-modified", "other-strand-modified")
        if needs and row.get("prior_state") is None:
            self.block(name, field + ".prior_state", "missing on a %s row" % origin, "the prior state read before the change")
        if not needs and row.get("prior_state") is not None:
            self.block(name, field + ".prior_state", "set on a %s row" % origin, "null unless the row modifies an object")
        if origin == "other-strand-modified":
            live = ((self.account or {}).get("live_objects") or {}).get(row.get("live_key")) if row.get("live_key") else None
            if not row.get("source_strand") or not row.get("live_key"):
                self.block(name, field, "an other-strand-modified row without source_strand or live_key",
                           "both, naming the strand and the live-map row it changes")
            elif live is None:
                self.block(name, field + ".live_key", "%s is no live-map row" % row.get("live_key"), "a live_objects key")
            elif live.get("constraint") == "do-not-change":
                self.block(name, field + ".live_key", "%s is marked do-not-change (%s)" % (
                    row.get("live_key"), live.get("constraint_source")), "no change to a do-not-change row")
        ref = row.get("approval_ref")
        if not ref or led.approval(ref) is None:
            self.block(name, field + ".approval_ref", "%r resolves to no approval of this ledger" % ref,
                       "the vNrM of the approval entry of the revision that planned the row")
        if row.get("blueprint_ref"):
            self.ref_reasons(led, key, "blueprint_ref", row["blueprint_ref"], tables)
        if row.get("prompt_ref"):
            self.ref_reasons(led, key, "prompt_ref", row["prompt_ref"], tables, prompt=True)
        parent = row.get("parent_key")
        if parent:
            if ":" in str(parent):
                live = ((self.account or {}).get("live_objects") or {}).get(parent)
                found = live.get("monday_id") if live else None
            else:
                found = (led.objects.get(parent) or {}).get("id") if parent in led.objects else None
            if (":" in str(parent) and live is None) or (":" not in str(parent) and parent not in led.objects):
                self.block(name, field + ".parent_key", "%s does not resolve" % parent,
                           "a row of this ledger, or a qualified live-map key of a parent another strand built")
            elif row.get("parent_id") and found and str(found) != str(row["parent_id"]):
                self.block(name, field + ".parent_id", "%s, while %s has the id %s" % (row["parent_id"], parent, found),
                           "the parent's id")
        allowed = set(str(i) for i in (((self.account or {}).get("guard_index") or {}).get("client_workspace_ids") or []))
        if row.get("workspace") and kind != "workspace" and str(row["workspace"]) not in allowed:
            self.block(name, field + ".workspace", "%s is outside the client's workspaces" % row["workspace"],
                       A21 + ": " + (", ".join(sorted(allowed)) or "none"))
        for ws in row.get("workspace_scope") or []:
            if str(ws) not in allowed:
                self.block(name, field + ".workspace_scope", "%s is outside the client's workspaces" % ws,
                           A21 + ": " + (", ".join(sorted(allowed)) or "none"))
        if kind in ACCOUNT_LEVEL and not row.get("workspace_scope") and row.get("status") != "planned":
            self.block(name, field + ".workspace_scope", "an account-level row without a scope",
                       "the client workspaces it may read and write")

    def yes_shape(self, led, n, entry, approvals):
        name = led.build_rel
        for key in ("key", "what", "at", "log_ref"):
            if key not in entry:
                self.block(name, "irreversible_yes[%d].%s" % (n, key), "the field is missing", "the irreversible_yes shape")
        mode = entry.get("mode")
        if mode is not None and mode not in YES_MODES:
            self.block(name, "irreversible_yes[%d].mode" % n, "%r is not a yes mode" % mode, " | ".join(YES_MODES))
        key = entry.get("key")
        if mode == "card":
            listed = key in led.objects
        elif mode == "grouped":
            listed = any(key in (a.get(field) or []) for a in approvals for _, field in LISTS)
        else:
            listed = any(key in (a.get("irreversible_listed") or []) for a in approvals)
        if not listed:
            self.block(name, "irreversible_yes[%d].key" % n, "%s is listed in no approval for a %s yes" % (key, mode or "per-item"),
                       "a key of an approval's irreversible_listed (per-item) or one of its four lists (grouped)")
        ref = entry.get("approval_ref")
        if ref is not None and led.approval(ref) is None:
            self.block(name, "irreversible_yes[%d].approval_ref" % n, "%r resolves to no approval" % ref,
                       "the vNrM of an approval entry of this ledger")

    def live_map(self, led):
        live = led.account.get("live_objects") if isinstance(led.account.get("live_objects"), dict) else {}
        path = self.root / "live" / "live-map.md"
        if not path.is_file():
            for key in sorted(live):
                self.block("account.json", "live_objects." + key, "a live object and no live/live-map.md",
                           "the same rows on both sides")
            return
        text = mc.read_text(path, "live/live-map.md")
        try:
            _, header, rows = map_rows(text)
        except mc.FrontMatterError as exc:
            self.blocking.extend(exc.findings)
            return
        if mc.schema_newer(mc.front_matter(text, "live/live-map.md").get("schema"), "live-map"):
            return
        for key in sorted(set(rows) - set(live)):
            self.block("live/live-map.md", key, "a live-map row absent from account.json live_objects",
                       "the same rows on both sides")
        for key in sorted(set(live) - set(rows)):
            self.block("account.json", "live_objects." + key, "a live object absent from live/live-map.md",
                       "the same rows on both sides")
        for key in sorted(set(rows) & set(live)):
            want = map_view(live[key])
            for column in MAP_COLUMNS:
                found = rows[key].get(column, "") if column in header else ""
                if found != want[column]:
                    self.block("live/live-map.md", "%s.%s" % (key, column), "%r here, %r in account.json live_objects"
                               % (found, want[column]), "the same value on both sides; ledger.py live-map rewrites it")

    def guard(self, account):
        index = account.get("guard_index") if isinstance(account.get("guard_index"), dict) else {}
        allowed = {str(i) for i in index.get("client_workspace_ids") or []}
        for strand, target in sorted((index.get("build_targets_by_strand") or {}).items()):
            for ws in (target or {}).get("workspace_ids") or []:
                if str(ws) not in allowed:
                    self.block("account.json", "guard_index.build_targets_by_strand", "strand %s targets workspace %s, "
                               "outside the client's workspaces" % (strand, ws), A21)
        captured, days = index.get("captured_at"), (index.get("record_provenance") or {}).get("staleness_budget_days")
        if captured and is_utc(captured) and isinstance(days, (int, float)):
            age = (mc.now_utc() - mc.parse_utc(captured)).total_seconds() / 86400.0
            if age > days:
                self.warn("account.json", "guard_index.captured_at", "the native index was captured %s, %d days ago, past "
                          "its %s-day budget" % (captured, age, days), "a fresh native-map read before guarded writes")


def cmd_check(root, args):
    if args.strand:
        mc.strand_dir(root, args.strand)
    found = Checker(root, args.strand).run()
    code = 1 if found.blocking else 2 if found.warnings else 0
    return code, {"findings": {"blocking": found.blocking, "warnings": found.warnings}, "shas": found.shas}


# The live map (W59 to W62).

def map_rows(text):
    """(front matter, header cells, {key: {column: cell}}) of live/live-map.md; nine or ten columns."""
    fields, body = mc.split_front_matter(text, "live/live-map.md")
    header, rows = [], {}
    for line in body.split("\n"):
        if not line.startswith("|"):
            continue
        cells = split_cells(line)
        if not header:
            header = [cell.lower() for cell in cells]
            continue
        if cells and all(cell and set(cell) <= set("-: ") for cell in cells):
            continue
        rows[cells[0]] = dict(zip(header, cells))
    return fields, header, rows


def map_view(row):
    def text(value):
        return "" if value is None else str(value)
    return {"monday id": text(row.get("monday_id")), "kind": text(row.get("kind")), "workspace": text(row.get("workspace")),
            "built by": text(row.get("introduced_in")), "state": text(row.get("state")),
            "constraint": text(row.get("constraint")), "source": text(row.get("constraint_source")),
            "dependants": ", ".join(row.get("dependants") or []) or "none",
            "last verified": text(row.get("last_verified")) or ("departed, %s" % row["departed"] if row.get("departed") else "")}


def map_text(slug, live, updated):
    lines = []
    for key in sorted(live):
        view = map_view(live[key])
        cells = [key] + [view[column] for column in MAP_COLUMNS]
        lines.append("| %s |\n" % " | ".join(cell.replace("|", "\\|") for cell in cells))
    front = front_text((("schema", "live-map/1"), ("client", slug), ("rows", str(len(live))), ("updated", updated)))
    return front + INTERNAL + "\n\n" + MAP_HEAD + "\n" + MAP_SEP + "\n" + "".join(lines)


def map_step(led):
    """The live map rendered from live_objects, as a write step, or None when its rows are unchanged."""
    path = led.root / "live" / "live-map.md"
    slug = led.account.get("client_slug") or led.client.get("slug") or led.root.name
    live = led.account.get("live_objects") or {}
    if path.is_file():
        old = mc.read_text(path, "live/live-map.md")
        try:
            updated = mc.front_matter(old, "live/live-map.md").get("updated", "")
        except mc.FrontMatterError:
            updated = ""
        if map_text(slug, live, updated) == old.replace("\r\n", "\n"):
            return None
    text = map_text(slug, live, mc.stamp("minute"))
    return ("live/live-map.md", lambda: mc.write_file(path, text, led.root), None)


def cmd_live_map(root, args):
    led = Ledger(root)
    refuse(*led.newer())
    step = map_step(led)
    if step:
        commit("live-map", [step])
    return 0, {"rows": len(led.account.get("live_objects") or {}), "written": {
        "live/live-map.md": mc.sha256_file(root / "live" / "live-map.md")} if step else {}}


def client_built(row):
    """True for a live row of an object the client or the platform made (`built by` client or native): no strand owns
    it (R17)."""
    return (row or {}).get("introduced_in") in ("client", "native")


def stated_source(source):
    """True when a source names a client quote with its location (a call or input file and a location of its
    grammar) or a user decision with its log reference (the entry's header line), as the live map's source rules
    give (R17)."""
    return bool(QUOTE_AT.search(source) or LOG_AT.search(source))


def cmd_live_map_set(root, args):
    led = Ledger(root)
    refuse(*led.newer())
    live = led.account.get("live_objects") or {}
    row = live.get(args.key)
    source = (args.source or "").strip()
    unowned = row is not None and client_built(row)
    refuse(None if row is not None else ("account.json", "live_objects." + str(args.key), "no live-map row %s" % args.key,
                                         "a qualified key of a row the live map holds"),
           None if args.constraint in CONSTRAINTS else ("account.json", "live_objects.%s.constraint" % args.key,
                                                        "%r is not a constraint" % args.constraint, " | ".join(CONSTRAINTS)),
           None if source and source != "pending strand close" and "\n" not in source else (
               "account.json", "live_objects.%s.constraint_source" % args.key, "the source is empty or the interim value",
               "a client quote with its call location, or a user decision with its log reference"),
           None if not unowned or stated_source(source) else (
               "(flags)", "--source", "%s is built by %s, and %r names neither a client quote with its location nor a "
               "user decision with its log reference" % (args.key, row.get("introduced_in"), source),
               "for a client or native row, which no strand owns: the client's words with their location "
               "(calls/<file>.md@HH:MM:SS, or an inputs/<file>.md location), or the user's decision with the header "
               "line of its log entry (YYYY-MM-DD HH:MM · <strand> · <type> · ...), from any strand's session (R17)"),
           None if row is None or unowned or row.get("owner_strand") == args.strand else (
               "account.json", "live_objects.%s.owner_strand" % args.key, "the row was built by strand %s, not %s" % (
                   row.get("owner_strand"), args.strand), "a row this strand built: a strand edits only its own rows"))
    row["constraint"], row["constraint_source"] = args.constraint, source
    led.account["updated_at"] = mc.stamp("utc")
    steps = [("account.json", json_step(root, root / "account.json", led.account), None)]
    step = map_step(led)
    steps += [step] if step else []
    commit("live-map set", steps, next_call="ledger.py live-map, which renders the map from live_objects", root=root)
    return 0, {"key": args.key, "constraint": args.constraint, "source": source,
               "written": {rel: mc.sha256_file(mc.record_path(root, rel)) for rel, _, _ in steps},
               "log": [entry_log("-" if not args.strand else args.strand, "live-map", "-", args.key,
                                 ["constraint %s · source: %s" % (args.constraint, source)])]}


# bind and workspaces (W37 to W39).

def cmd_bind(root, args):
    led = Ledger(root)
    refuse(*led.newer())
    data, name = input_json(root, args.binding, "--binding")
    me, found, version = data.get("me") or {}, data.get("account") or {}, data.get("version") or {}
    kind, target = led.client.get("account_kind"), led.client.get("build_target")
    current = led.account.setdefault("account", {})
    aid, slug, user = str(found.get("id") or ""), str(found.get("slug") or ""), str(me.get("id") or "")
    reasons = [digits("account.id", aid or None, name) if aid else (name, "account.id", "no account id", "account { id }"),
               digits("me.id", user or None, name) if user else (name, "me.id", "no user id", "me { id }"),
               None if slug else (name, "account.slug", "no account slug", "account { slug }"),
               None if version.get("kind") and version.get("value") else (name, "version", "no ring read",
                                                                          "version { kind value }"),
               None if kind in TARGET_OF and target == TARGET_OF.get(kind) else (
                   "CLIENT.md", "build_target", "%s with account_kind %s" % (target, kind),
                   "own with own-account, client with client-account, sandbox with none")]
    sandbox = [line for fields, line in sandbox_lines() if fields[0] == "sandbox" and (
        (len(fields) > 1 and fields[1] == aid) or (len(fields) > 2 and fields[2] == slug))]
    if kind == "client" and sandbox:
        reasons.append(("local/sandbox-accounts.txt", "sandbox", "the account %s (%s) is a sandbox account: %s" % (
            aid, slug, sandbox[0]), "a client record bound to the client's own account, never a sandbox"))
    if kind == "sandbox" and not sandbox:
        reasons.append(("local/sandbox-accounts.txt", "sandbox", "the account %s (%s) is on no sandbox line" % (aid, slug),
                        "a sandbox record bound only to an account a sandbox line names"))
    if kind == "own":
        default = (mc.read_settings() or {}).get("default_build_account") or {}
        if str(default.get("id")) != aid or str(default.get("slug")) != slug:
            reasons.append(("local/settings.json", "default_build_account", "the account %s (%s) is not the default "
                            "build account %s (%s)" % (aid, slug, default.get("id"), default.get("slug")),
                            "an own-account record bound to the user's default build account only"))
    bound = current.get("id") not in (None, "unbound")
    if bound and (str(current.get("id")) != aid or str(current.get("slug")) != slug):
        reasons.append(("account.json", "account.id", "the record is bound to %s (%s); %s (%s) was read" % (
            current.get("id"), current.get("slug"), aid, slug), "the same account: a client record never rebinds"))
    elif bound and str(current.get("bound_user_id")) != user:
        reasons.append(("account.json", "account.bound_user_id", "bound by user %s; user %s read now" % (
            current.get("bound_user_id"), user), "the same bound user: ask the user before anything else"))
    refuse(*reasons)
    now = mc.stamp("utc")
    products = [{"id": str(p.get("id")), "kind": p.get("kind")} for p in found.get("products") or []
                if isinstance(p, dict) and p.get("kind") in ("core", "crm", "service")]
    for key, value in (("id", aid), ("slug", slug), ("name", found.get("name") or slug), ("kind", kind),
                       ("build_target", target), ("tier", found.get("tier") or "unknown"), ("bound_user_id", user),
                       ("bound_at", current.get("bound_at") if bound else now),
                       ("builder_role", str(me.get("kind") or "unknown").lower()), ("products", products)):
        current[key] = value
    ring = "%s %s" % (version.get("kind"), version.get("value"))
    other = data.get("execute_code_version") or {}
    led.account["api"] = {"connector_ring": ring, "execute_code_ring": "%s %s" % (other["kind"], other["value"])
                          if other.get("kind") and other.get("value") else ring, "read_at": now}
    if not led.account.get("client_slug"):
        led.account["client_slug"] = led.client.get("slug") or root.name
    led.account["updated_at"] = now
    commit("bind", [("account.json", json_step(root, root / "account.json", led.account), None)])
    mirror = {"monday_account_id": aid, "monday_account_slug": slug, "monday_bound_user_id": user,
              "monday_bound_at": current["bound_at"], "account_kind": kind, "build_target": target}
    return 0, {"refresh": bound, "account": current, "api": led.account["api"], "mirror": mirror,
               "written": {"account.json": mc.sha256_file(root / "account.json")},
               "log": [] if bound else [entry_log("-", "binding", "-", slug, ["account %s, user %s, build target %s"
                                                                              % (aid, user, target)])],
               "next": "write the mirror into CLIENT.md through record.py guard; record.py check blocks until it is"}


def workspaces_mirror(account, short):
    index = account.get("guard_index") or {}
    pairs = sorted("%s:%s" % (product, (item or {}).get("id")) for product, item in
                   (account.get("client_workspaces") or {}).items())
    mine = sorted("%s:%s" % ((index.get("product_workspaces") or {}).get(ws, "core"), ws) for ws in
                  ((index.get("build_targets_by_strand") or {}).get(short) or {}).get("workspace_ids") or [])
    return {"client_workspaces": ";".join(pairs) or "none", "strand_workspaces": ";".join(mine) or "none"}


def cmd_workspaces(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    forms = [bool(args.product or args.id or args.name or args.created_in), bool(args.use),
             bool(args.folder or args.in_workspace)]
    reasons = flatten(fence_flags(args), holder_reasons(root, led.short))
    if forms.count(True) != 1:
        reasons.append(("(flags)", "form", "%d forms given" % forms.count(True), "exactly one of --product --id --name "
                        "--created-in, --use, or --folder --in-workspace"))
    refuse(*reasons)
    operational, clients = led.operational(), led.client_ids
    index, short = led.index, led.short
    recorded = {str((item or {}).get("id")): product for product, item in (led.account.get("client_workspaces") or {}).items()}
    recorded.update({str(item.get("id")): item.get("product") for item in led.account.get("superseded_workspaces") or []
                     if isinstance(item, dict)})
    built = None
    superseded = {str(item.get("id")): item.get("direction_change") for item in led.account.get(
        "superseded_workspaces") or [] if isinstance(item, dict)}
    if forms[0]:
        product, ws = args.product, args.id
        reasons = [None if product in ("core", "crm", "service") else (
                       "account.json", "client_workspaces", "%r is not a product" % product, "core | crm | service"),
                   digits("--id", ws) if ws else ("(flags)", "--id", "no workspace id", "the id the create returned"),
                   None if args.created_in == led.qualified else ("(flags)", "--created-in", "%r is not this strand's "
                                                                   "version %s" % (args.created_in, led.qualified),
                                                                   led.qualified)]
        # R8: the workspace is one this strand's build created and read back, never an id the session names
        rows = sorted(k for k, r in (led.objects if led.build else {}).items() if r.get("type") == "workspace"
                      and str(r.get("id")) == str(ws) and r.get("status") in ("written", "verified"))
        built = led.objects[rows[0]] if rows else None
        direction = (args.direction_change or "").strip() or (built or {}).get("direction_change")  # R11
        if built is None:
            reasons.append((led.build_rel if led.build else "(flags)", "objects", "strand %s: no workspace row of this "
                            "ledger was written or verified with the id %s" % (short, ws), "a workspace the build "
                            "created: ledger.py intent, the create, record --id and verify first (W38)"))
        elif built.get("product") != product:
            reasons.append((led.build_rel, "objects.%s.product" % rows[0], "%s was created for %s, not %s" % (
                rows[0], built.get("product"), product), "the product the workspace row was created for"))
        elif args.name and args.name.strip() != built.get("name"):
            reasons.append(("(flags)", "--name", "%r given, %r recorded on %s" % (args.name, built.get("name"), rows[0]),
                            "the workspace row's name, or no --name"))
        for rel_other, ids in sibling_workspaces(root):  # the cross-record check: ids only, inside this record's hold
            if str(ws) in ids:
                reasons.append((rel_other, "guard_index.client_workspace_ids", "workspace %s is another client "
                                "record's" % ws, "a workspace this record's own build created (A21)"))
        if ws in operational:
            reasons.append(("account.json", "guard_index.client_workspace_ids", "strand %s: workspace %s is an operational "
                            "workspace (never-demo), never a build target: %s" % (short, ws, operational[ws]), A21))
        if ws in recorded and recorded[ws] != product:
            reasons.append(("account.json", "client_workspaces", "workspace %s is already recorded for %s" % (
                ws, recorded[ws]), "one product per workspace"))
        current = (led.account.get("client_workspaces") or {}).get(product)
        if current and str(current.get("id")) == ws:
            reasons.append(("account.json", "client_workspaces.%s" % product, "workspace %s is already recorded" % ws,
                            "nothing to record: the workspace is the client's already"))
        elif current and not direction:
            reasons.append(("account.json", "client_workspaces.%s" % product, "the client already has a %s workspace, %s"
                            % (product, current.get("id")), "one workspace per product, unless the record says the "
                            "direction changed: --direction-change with the log reference of the user's decision, given "
                            "here or at the workspace's intent"))
        refuse(*reasons)
    elif forms[1]:
        refuse(digits("--use", args.use),
               None if args.use in clients else ("account.json", "guard_index.client_workspace_ids", "strand %s: "
                                                 "workspace %s is outside the client's workspaces" % (short, args.use),
                                                 A21 + ": " + (", ".join(clients) or "none")),
               None if args.use not in operational else ("account.json", "guard_index.client_workspace_ids",
                                                         "workspace %s is operational: %s" % (args.use, operational[args.use]), A21),
               None if args.use not in superseded or args.use in led.targets() else (  # R16
                   "account.json", "superseded_workspaces", "strand %s: workspace %s was superseded when the user chose "
                   "a new direction (%s)" % (short, args.use, superseded[args.use]), "the product's current workspace; "
                   "a superseded one only for the strand that already builds there"))
    else:
        refuse(digits("--folder", args.folder) if args.folder else ("(flags)", "--folder", "no folder id", "the folder id"),
               None if args.in_workspace in led.targets() else (
                   "account.json", "guard_index.build_targets_by_strand.%s" % short, "strand %s: workspace %s is not "
                   "one of this strand's targets" % (short, args.in_workspace), A21 + ": " + (", ".join(led.targets()) or "none")))
    fence(root, args)
    led.reload()
    index = led.index
    targets = index.setdefault("build_targets_by_strand", {}).setdefault(short, {"workspace_ids": [], "folder_ids": []})
    targets.setdefault("workspace_ids", [])
    targets.setdefault("folder_ids", [])
    ids = index.setdefault("client_workspace_ids", [])
    if forms[0]:
        workspaces = led.account.setdefault("client_workspaces", {})
        current = workspaces.get(args.product)
        if current:
            led.account.setdefault("superseded_workspaces", []).append(dict(
                product=args.product, id=str(current.get("id")), name=current.get("name"),
                created_in=current.get("created_in"), superseded_in=args.created_in, direction_change=direction))
        workspaces[args.product] = {"id": args.id, "name": built.get("name"), "created_in": args.created_in}
        for listed, value in ((ids, args.id), (targets["workspace_ids"], args.id)):
            if value not in listed:
                listed.append(value)
        index.setdefault("product_workspaces", {})[args.id] = args.product
    elif forms[1]:
        if args.use not in targets["workspace_ids"]:
            targets["workspace_ids"].append(args.use)
    elif args.folder not in targets["folder_ids"]:
        targets["folder_ids"].append(args.folder)
    led.account["updated_at"] = mc.stamp("utc")
    commit("workspaces", [("account.json", json_step(root, root / "account.json", led.account), None)])
    what = ("%s workspace %s" % (args.product, args.id) if forms[0] else "workspace %s for strand %s" % (args.use, short)
            if forms[1] else "folder %s in %s" % (args.folder, args.in_workspace))
    return 0, {"targets": targets, "client_workspace_ids": ids, "mirror": workspaces_mirror(led.account, short),
               "written": {"account.json": mc.sha256_file(root / "account.json")},
               "log": [entry_log(short, "workspace", led.version, args.id or args.use or args.folder, [what])],
               "next": "write the mirror into CLIENT.md client_workspaces and STRAND.md workspaces through record.py "
                       "guard; record.py check blocks until it is"}


# change-check (W49).

def cmd_change_check(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    refuse(*holder_reasons(root, led.short))  # R18: while a build is live, only its strand replaces the block
    data, name = input_json(root, args.source, "--from")
    roster = data.get("roster_diff")
    notes = data.get("release_notes_since")
    refuse(None if is_str(data.get("ring")) else (name, "ring", "no ring", "the ring read, such as release_candidate 2026-10"),
           None if str_list(data.get("versions_seen")) else (name, "versions_seen", "not a list of versions", "a list"),
           None if notes == "not-read" or re.fullmatch(r"\d{4}-\d{2}-\d{2} \(read\)", str(notes)) else (
               name, "release_notes_since", "%r" % notes, '"<date> (read)" or "not-read"'),
           None if isinstance(roster, dict) and sorted(roster) == ["added", "removed", "renamed"] and all(
               isinstance(roster[k], list) for k in roster) else (name, "roster_diff", "not the three lists",
                                                                   "{added, removed, renamed}, each a list"),
           None if isinstance(data.get("schema_diff"), list) else (name, "schema_diff", "not a list", "a list"),
           None if data.get("result") in CHANGE_RESULTS else (name, "result", "%r" % data.get("result"),
                                                              " | ".join(CHANGE_RESULTS)),
           None if data.get("approved_by_user") is None or is_str(data.get("approved_by_user")) else (
               name, "approved_by_user", "%r" % data.get("approved_by_user"), "null or the log reference of the user's yes"))
    block = {"at": mc.stamp("utc"), "for_strand": led.short, "ring": data["ring"], "versions_seen": data["versions_seen"],
             "release_notes_since": notes, "roster_diff": {k: roster[k] for k in ("added", "removed", "renamed")},
             "schema_diff": data["schema_diff"], "result": data["result"], "approved_by_user": data.get("approved_by_user")}
    led.account["change_check"] = block
    led.account["updated_at"] = block["at"]
    commit("change-check", [("account.json", json_step(root, root / "account.json", led.account), None)])
    go = data["result"] == CHANGE_RESULTS[0] or bool(block["approved_by_user"])
    return 0, {"change_check": block, "go_on": go, "written": {"account.json": mc.sha256_file(root / "account.json")},
               "log": [entry_log(led.short, "change-check", led.version if led.version != "none" else "-", data["ring"],
                                 [data["result"]] + (["approved by the user: %s" % block["approved_by_user"]]
                                                     if block["approved_by_user"] else []))],
               "next": "go on to the build" if go else "stop: the change touches this build; the user decides"}


# approval (W27, W42 to W46).

def approval_mode(led, version, fields):
    purpose = (fields or {}).get("purpose")
    if not purpose:
        purpose = "proof-of-concept" if tuple(int(p) for p in version[1:].split(".")) < (1, 0) else "working-solution"
    target = (led.account.get("account") or {}).get("build_target")
    return ("own-account-poc" if target == "own-account" and purpose == "proof-of-concept" else "per-list"), purpose


def new_row(kind, key, name, version, ref):
    row = ordered_row({"type": kind, "id": None, "name": name, "parent_key": key_parent(key), "parent_id": None,
        "origin": "created", "source_strand": None,
        "introduced_in": version, "changed_in": [], "state": None, "status": "planned", "attempt": None,
        "verify": None, "creator_user_id": None, "owner_user_ids": [], "irreversible": False, "sample_data": False,
        "approval_ref": ref, "notifies": [], "companions": {}, "role": None, "prior_state": None, "url": None,
        "blueprint_ref": "%s#%s" % (ref, key) if ref else None})
    if kind in PROMPT_TYPES and ref:
        row["prompt_ref"] = "%s#%s" % (ref, key)
    return row


def read_only(led, key, kind, referenced):
    """True for a workspace or folder the revision references and the build never writes, which is off the must-list
    (demos' fixes, 1); a row the strand already created stays created whatever the flags say, so it stays on it."""
    row = ((led.build or {}).get("objects") or {}).get(key)
    return kind in ("workspace", "folder") and key in (referenced or []) and (
        row is None or row.get("status") == "planned" or row.get("origin") == "pre-existing-referenced")


def cmd_approval(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    srel = led.rel(led.folder / "STRAND.md")
    refuse(None if led.strand.get("kind") in ("platform", "hybrid") else (
               srel, "kind", "the strand is %s: it has no ledger" % led.strand.get("kind"), "a platform or hybrid strand"),
           None if (led.account.get("account") or {}).get("id") not in (None, "unbound") else (
               "account.json", "account.id", "the record is not bound to an account", "ledger.py bind first"))
    lease = mc.lease_status(root)
    refuse(None if not (lease.get("held") and lease.get("strand") == led.short and lease.get("run_id")) else (
        mc.LOCK_REL, "run_id", "strand %s is building: run %s is on the lease" % (led.short, lease.get("run_id")),
        "a revision approved between runs, never under one (R20)"))
    version = args.version or led.version
    fields = led.version_fields(version)
    vpath = led.version_path(version)
    refuse(None if fields is not None else (srel, "version", "no version.md for %s" % version, "an opened version"))
    revision = str(args.revision or fields.get("revision", "none"))
    refuse(None if DIGITS.fullmatch(revision) else (led.rel(vpath), "revision", "%r" % revision, "a revision number"))
    frozen = vpath.parent / ("blueprint-r%s.md" % revision)
    frel = led.rel(frozen)
    refuse(None if frozen.is_file() else (frel, mc.WHOLE_FILE, "the frozen revision is missing", "record.py freeze first"))
    sha = mc.sha256_file(frozen)
    text = mc.read_text(frozen, frel)
    reasons = [None if args.sha256 == sha == fields.get("sha256") else (
        frel, "sha256", "--sha256 %s, the frozen file %s, version.md %s" % (args.sha256, sha, fields.get("sha256")),
        "the three the same: the sha freeze returned, of the file as frozen"), sha_reason(led, args.expect_sha)]
    if led.build is not None and led.approval("%sr%s" % (version, revision)) is not None:
        reasons.append((led.build_rel, "approvals", "%s revision %s is approved already" % (version, revision),
                        "a revision not yet approved"))
    if led.build is not None and str(led.build.get("account_id_at_bind")) not in (
            "unbound", str((led.account.get("account") or {}).get("id"))):
        reasons.append((led.build_rel, "account_id_at_bind", "%s, while the record is bound to %s" % (
            led.build.get("account_id_at_bind"), (led.account.get("account") or {}).get("id")), "the bound account"))
    rows, problems = element_table(text)
    if rows is None:
        reasons.append((frel, "## Element keys", "the frozen revision has no element-key table",
                        "the ## Element keys table record-map.md pins under blueprint/1"))
        rows = []
    reasons += [(frel, "## Element keys", problem, "one row per element: a unique key of its kind's shape, a kind, a "
                 "name") for problem in problems]
    recipients = {}
    if rows and not problems:  # R20 (a): the approved revision records who each element notifies
        recipients, wrong = element_recipients(text)
        if recipients is None:
            reasons.append((frel, "## Element keys", "the table has no notifies column, so the approval could not "
                            "record who each element notifies", "a notifies column after key | kind | name: empty "
                            "for nobody, user for the user alone, or the recipients (a user id, team:<id>, "
                            "email:<address>) separated by commas"))
            recipients = {}
        reasons += [(frel, "## Element keys", problem, "each recipient once, as user, a user id, team:<id> or "
                     "email:<address>, separated by commas") for problem in wrong]
    installs = {}
    if rows and not problems:  # A38: a native install names monday's template for its board row
        installs, wrong = element_templates(text)
        built = (led.build or {}).get("objects") or {}
        for key in sorted(installs, key=natural):
            row = built.get(key)
            if key in (args.referenced or []):
                wrong.append("%s is referenced: a board the build reads is never installed" % key)
            elif row is not None and row.get("id") and row.get("template_id") != installs[key]["template_id"]:
                wrong.append("%s is built already as board %s: a native install is a new board" % (key, row["id"]))
        reasons += [(frel, "## Element keys", problem, "a template cell on a new board row only: monday's template id "
                     "of a native board and the entity the catalogue names for it (native-objects.md 3.1 and 4.1), "
                     "such as 5678953932 leads") for problem in wrong]
    table = {key: (kind, name) for key, kind, name in rows}
    irreversible = list(args.irreversible or [])
    for key in irreversible:
        if key not in table:
            reasons.append(("(flags)", "--irreversible", "%s is not a row of the element-key table" % key, "a key of the table"))
        elif table[key][0] in LIST_TYPES:
            reasons.append(("(flags)", "--irreversible", "%s is a %s, a list" % (key, table[key][0]),
                            "an irreversible step; automations, workflows, agents and sequences are lists"))
    for key, (kind, _) in table.items():
        if kind in MUST_LIST and key not in irreversible and not read_only(led, key, kind, args.referenced):
            reasons.append(("(flags)", "--irreversible", "the %s %s is not listed" % (kind, key),
                            "every workspace, folder, publication, activation and webhook listed as its own step"))
        if kind in PROMPT_TYPES and prompt_block(text, key) is None:
            reasons.append((frel, "### Prompt %s" % key, "no prompt block for the %s %s" % (kind, key),
                            "a ### Prompt %s heading followed by a fenced text block" % key))
    for key in args.referenced or []:
        if key not in table:
            reasons.append(("(flags)", "--referenced", "%s is not a row of the element-key table" % key, "a key of the table"))
    live, touched = led.account.get("live_objects") or {}, []
    for item in args.touches or []:
        key, _, constraint = item.partition("=")
        row = live.get(key)
        if constraint not in CONSTRAINTS:
            reasons.append(("(flags)", "--touches", "%r is not a constraint" % constraint, " | ".join(CONSTRAINTS)))
        elif row is None:
            reasons.append(("account.json", "live_objects." + key, "no live-map row %s" % key, "a qualified live-map key"))
        elif row.get("constraint") != constraint:
            reasons.append(("account.json", "live_objects.%s.constraint" % key, "%s here, %s given" % (
                row.get("constraint"), constraint), "the row's live constraint"))
        elif constraint == "do-not-change":
            reasons.append(("account.json", "live_objects.%s.constraint" % key, "the row is marked do-not-change (%s)" % (
                row.get("constraint_source")), "a revision that leaves it as it is"))
        else:
            touched.append({"key": key, "constraint": constraint})
    refuse(*reasons)
    if led.build is None:
        led.build = {key: (json.loads(json.dumps(value))) for key, value in SKELETON}
    b, account = led.build, led.account.get("account") or {}
    mode, purpose = approval_mode(led, version, fields)
    ref = "%sr%s" % (version, revision)
    counts = {prefix: len(set(re.findall(r"\b(%s\d+)\b" % prefix, text))) for prefix in ("AS", "AT", "FK")}
    entry = {"version": version, "qualified_version": "%s/%s" % (led.short, version), "revision": int(revision),
             "frozen_file": mc.relative(led.folder, frozen), "sha256": sha, "approved_at": mc.stamp("utc"),
             "approved_words": args.words, "approved_in_session": args.session, "approval_mode": mode,
             "element_count": sum(1 for kind, _ in table.values() if kind not in ("publication", "activation", "ui_step")),
             "irreversible_listed": [key for key in table if key in irreversible]}
    for kind, field in LISTS:
        entry[field] = [key for key, (k, _) in table.items() if k == kind]
    entry["notifies_approved"] = {key: list(recipients.get(key) or []) for key, (k, _) in table.items() if k != "ui_step"}
    entry["native_installs"] = {key: dict(installs[key]) for key in sorted(installs, key=natural)}
    entry["rests_on"] = {"clearance": led.strand.get("clearance"), "purpose": purpose, "assumptions": counts["AS"],
                         "assumed_terms": counts["AT"], "forks_on_leaning": counts["FK"]}
    entry["live_objects_touched"] = touched
    b.setdefault("approvals", []).append(entry)
    delta = {"new": [], "kept": [], "replanned": [], "dropped": [], "not_in_table": []}
    objects = b.setdefault("objects", {})
    for key, (kind, name) in table.items():
        if kind == "ui_step":
            continue
        row = objects.get(key)
        if row is None:
            row = objects[key] = new_row(kind, key, name, version, ref)
            if key in (args.referenced or []):
                row["origin"] = "pre-existing-referenced"
            delta["new"].append(key)
        elif row.get("status") == "departed":
            row = objects[key] = ordered_row(row)
            row.update(status="planned", approval_ref=ref, blueprint_ref="%s#%s" % (ref, key))
            if kind in PROMPT_TYPES:
                row["prompt_ref"] = "%s#%s" % (ref, key)
            delta["replanned"].append(key)
        elif row.get("status") == "planned":  # R12: nothing is built yet, so the row follows the latest approved plan
            if row.get("type") != kind:
                row = objects[key] = new_row(kind, key, name, version, ref)
            else:
                row = objects[key] = ordered_row(row)
                row.update(name=name, approval_ref=ref, blueprint_ref="%s#%s" % (ref, key))
                if kind in PROMPT_TYPES:
                    row["prompt_ref"] = "%s#%s" % (ref, key)
            row["origin"] = "pre-existing-referenced" if key in (args.referenced or []) else "created"
            delta["kept"].append(key)
        else:
            delta["kept"].append(key)
    for key in sorted(objects, key=natural):  # R12: a planned row the revision drops leaves the plan
        row = objects[key]
        if key not in table and row.get("status") == "planned" and row.get("type") != "item_batch":
            objects[key] = row = ordered_row(row)
            row["status"] = "departed"
            b.setdefault("departures", []).append({"key": key, "version": version, "what": "dropped from the plan by "
                                                   "revision %s" % ref, "error_code": "NONE", "attempts": [],
                                                   "decision": "blueprint-revision"})
            delta["dropped"].append(key)
    delta["not_in_table"] = [key for key in objects if key not in table and objects[key].get("type") != "item_batch"]
    b["reads_live"] = sorted({t["key"] for a in b["approvals"] for t in a.get("live_objects_touched") or []})
    if b.get("client_slug") in (None, ""):
        b["client_slug"] = led.account.get("client_slug") or led.client.get("slug")
    if b.get("strand") in (None, ""):
        b["strand"] = led.short
    if b.get("account_id_at_bind") in (None, "unbound"):
        b["account_id_at_bind"] = str(account.get("id"))
    written = save_build(led, "approval")
    return 0, {"approval": entry, "delta": delta, "written": written,
               "log": [entry_log(led.short, "approval", version, "r%s" % revision, [
                   'Approved in session: "%s".' % args.words, "frozen: %s · sha256: %s" % (frel, sha)])]}


# run start, run heartbeat, run end (W30 to W32).

def next_run_id(root, skip=()):
    """W30: one more than the highest N of today among every strand's runs and the ids in `skip` (R6: the ids the
    lease's history already carries, learnt from lease_refresh's refusal, since ledger.py never reads the lock)."""
    date, highest = mc.stamp("utc")[:10], 0
    base = root / "strands"
    ids = list(skip)
    for folder in sorted(base.iterdir()) if base.is_dir() else []:
        path = folder / "solution" / "build.json"
        if folder.is_dir() and path.is_file():
            ids += [str((run or {}).get("id")) for run in mc.read_json(path, mc.relative(root, path)).get("runs") or []]
    for run_id in ids:
        match = re.fullmatch(r"run-(\d{4}-\d{2}-\d{2})-(\d+)", run_id)
        if match and match.group(1) == date:
            highest = max(highest, int(match.group(2)))
    return "run-%s-%d" % (date, highest + 1)


def ran_before(exc):
    """True for lease_refresh's refusal of a run id an earlier lease carried (G50, finding 2 of WP2)."""
    first = exc.findings[0] if isinstance(exc, mc.Refusal) and exc.findings else {}
    return first.get("field") == "run_id" and "ran under the lease" in str(first.get("problem"))


def cmd_run_start(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    led.require_build()
    b, version = led.build, led.version
    fields = led.version_fields() if version != "none" else None
    revision = (fields or {}).get("revision", "none")
    entry = led.approval("%sr%s" % (version, revision)) if fields else None
    status = mc.lease_status(root)
    reasons = [sha_reason(led, args.expect_sha),
               None if args.lease_epoch else (mc.LOCK_REL, "epoch", "no --lease-epoch was presented", FENCE_EXPECTED),
               None if args.session_label else (mc.LOCK_REL, "session_label", "no --session-label was presented",
                                                FENCE_EXPECTED),
               None if args.another_build_running in ("no", "yes") else (
                   "(flags)", "--another-build-running", "%r" % args.another_build_running, "no | yes, the user's answer"),
               None if args.another_build_running != "yes" or (args.answer_words or "").strip() else (
                   "(flags)", "--answer-words", "a yes with no words", "the user's own words"),
               None if args.account_check == "match" else (
                   "(flags)", "--account-check", "%r: the account read is not the bound one" % args.account_check,
                   "match: stop before any write when the account differs"),
               None if args.kind == "build" else ("(flags)", "--kind", "%r: the doc-copy run is deferred" % args.kind,
                                                  "build"),
               None if fields is not None else (led.rel(led.folder / "STRAND.md"), "version",
                                                "the strand has no opened version (%s)" % version, "an opened version"),
               None if fields is None or entry is not None else (led.build_rel, "approvals", "%s revision %s has no "
                                                                 "approval" % (version, revision), "ledger.py approval first"),
               None if status.get("held") and str(status.get("epoch")) == str(args.lease_epoch) and status.get(
                   "session_label") == args.session_label and status.get("strand") == led.short else (
                   mc.LOCK_REL, "session_label", "lease %s by strand %s at epoch %s; presented epoch %s, session %s" % (
                       status.get("state"), status.get("strand"), status.get("epoch"), args.lease_epoch,
                       args.session_label), "the epoch and label this strand's take returned")]
    if entry is not None:
        text, frel = led.frozen(entry)
        found = mc.sha256_file(mc.record_path(root, frel)) if text is not None else "absent"
        if found != entry.get("sha256"):
            reasons.append((frel, "sha256", "the frozen file hashes to %s, the approval records %s" % (
                found, entry.get("sha256")), "the frozen revision as approved"))
    if args.run_id:
        if status.get("run_id") != args.run_id or led.run(args.run_id) is not None:
            reasons.append((led.build_rel, "runs", "run %s cannot be resumed: the lock carries %s and the ledger %s it" % (
                args.run_id, status.get("run_id"), "holds" if led.run(args.run_id) else "lacks"),
                "--run-id only for the retry of a run start whose ledger write failed"))
    elif status.get("run_id"):
        reasons.append((mc.LOCK_REL, "run_id", "the lease already carries run %s" % status.get("run_id"),
                        "one run per lease: a run enters only the lease it starts under"))
    refuse(*reasons)
    now = mc.stamp("utc")
    yes = args.another_build_running == "yes"
    answer = "%s, answered %s" % (args.another_build_running, local_minute_of_day()) + (
        ": %s" % args.answer_words.strip() if yes else "")
    preflight = b.get("preflight") or {}
    epoch = int(args.lease_epoch) if DIGITS.fullmatch(str(args.lease_epoch)) else args.lease_epoch
    interrupted = []
    for run in b.setdefault("runs", []):
        if run.get("state") == "running" and run.get("id") != args.run_id:
            run["state"] = "interrupted"
            interrupted.append(run.get("id"))
    recovery = interrupted or [k for k, row in led.objects.items() if row.get("status") == "attempting"]
    if not yes:
        b["lease_epoch_at_run"] = epoch
    b["updated_at"] = now
    build_step = (led.build_rel, json_step(root, led.build_path, b), None)
    taken = []
    while True:  # R6: an id the lease's history carries (a run whose ledger write never landed) is skipped
        run_id = args.run_id or next_run_id(root, taken)
        run = {"id": run_id, "version": version, "kind": "build", "session_label": args.session_label,
               "lease_epoch": epoch, "another_build_running": answer, "started_at": now, "heartbeat_at": now,
               "ended_at": now if yes else None, "state": "ended" if yes else "running",
               "calls_estimated": preflight.get("estimated_calls") if preflight.get("version") == version else None,
               "calls_used": 0 if yes else None, "account_checks": [{"at": now, "before": "run start", "result": "match"}],
               "recovery_first": bool(recovery) and not yes}
        b["runs"].append(run)
        try:
            if yes:
                commit("run start", [build_step, (mc.LOCK_REL, lambda: mc.lease_release(
                    root, args.lease_epoch, args.session_label), {"released": {"epoch": epoch}})], run_id,
                       "record.py lease release --epoch %s --label %s" % (args.lease_epoch, args.session_label), root)
            else:
                commit("run start", [(mc.LOCK_REL, lambda: mc.lease_refresh(root, args.lease_epoch, args.session_label,
                                                                            run_id),
                                      {"refreshed": {"epoch": epoch, "session_label": args.session_label,
                                                     "run_id": run_id}}), build_step], run_id,
                       "ledger.py run start --strand %s --lease-epoch %s --session-label %s --another-build-running no "
                       "--account-check match --run-id %s, with the ledger's current sha" % (
                           led.short, args.lease_epoch, args.session_label, run_id), root)
            break
        except mc.Refusal as exc:
            b["runs"].pop()
            if args.run_id or not ran_before(exc) or len(taken) >= 50:
                raise
            taken.append(run_id)
    return 0, {"run_id": run_id, "epoch": epoch, "session_label": args.session_label, "state": run["state"],
               "another_build_running": answer, "interrupted": interrupted, "recovery_first": bool(recovery),
               "released": yes, "written": {led.build_rel: mc.sha256_file(led.build_path)},
               "carry": None if yes else "hold the run id beside the epoch and the label: every fenced write presents all three",
               "log": [entry_log(led.short, "build", version, run_id, ["stopped: another build is running", "lease "
                                 "released, epoch %s" % epoch] if yes else ["run started"])]}


def fenced(root, args, states=("running",), account=False):
    """The common opening of a fenced strand command (W28): newer schemas, the three flags, the sha, the holder and
    the run, each refused before anything is written; with `account`, the run's last account check too (R14).
    Returns the Ledger."""
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    led.require_build()
    reasons = flatten(fence_flags(args), sha_reason(led, args.expect_sha), holder_reasons(root, led.short))
    if args.run_id:
        reasons += run_reasons(led, args.run_id, states)
        if account:
            reasons += account_reasons(led, args.run_id)
    refuse(*reasons)
    return led


def cmd_run_heartbeat(root, args):
    led = fenced(root, args)
    words = (args.answer_words or "").strip()
    after_mismatch = bool(account_reasons(led, args.run_id))
    refuse(None if args.account_check in (None, "match", "mismatch") else (
               "(flags)", "--account-check", "%r" % args.account_check, "match | mismatch"),
           None if not args.account_check or (args.before or "").strip() else (
               "(flags)", "--before", "no step named", "what the check came before, such as writes 21 to 40"),
           None if args.account_check != "match" or not after_mismatch or (words and "\n" not in words) else (
               "(flags)", "--answer-words", "a match after a mismatch with no words from the user",
               "the user's own words, on one line, that the run goes on in the bound account (R14)"))
    fence(root, args)
    led.reload()
    beat(led, args.run_id)
    run = led.run(args.run_id)
    if args.account_check:
        check = {"at": mc.stamp("utc"), "before": args.before.strip(), "result": args.account_check}
        if args.account_check == "match" and after_mismatch:
            check["answer_words"] = words
        run.setdefault("account_checks", []).append(check)
    written = save_build(led, "run heartbeat", args.run_id)
    return 0, {"run_id": args.run_id, "heartbeat_at": run["heartbeat_at"], "stop": args.account_check == "mismatch",
               "written": written}


def live_rows(led):
    """W60, W61: the live_objects rows `run end` writes or refreshes from the strand's verified rows, and from its
    departed rows that hold an id, since what departed after it was made is still in monday (demos' fixes, 2)."""
    live = led.account.setdefault("live_objects", {})
    native = (led.index.get("native_board_index") or {})
    created, refreshed, archived = [], [], []
    carried = {k: r for k, r in led.objects.items() if r.get("type") != "item_batch" and (
        r.get("status") == "verified" or (r.get("status") == "departed" and r.get("id")
                                          and r.get("origin") != "other-strand-modified"))}
    departures = {d.get("key"): d for d in led.build.get("departures") or []}  # the newest departure of each key
    for key, row in sorted(carried.items()):
        verify = row.get("verify") or {}
        kind = row.get("type")
        gone = departures.get(key, {}) if row.get("status") == "departed" else None
        if kind in ACCOUNT_LEVEL or (row.get("workspace_scope") and not row.get("workspace")):
            workspace = "account: %s" % "; ".join(row.get("workspace_scope") or [])
        elif kind == "workspace":
            workspace = row.get("id")
        else:
            workspace = led.row_workspace(key)
        fresh = {"monday_id": row.get("id"), "kind": kind, "workspace": workspace, "state": row.get("state") or "active",
                 "digest": verify.get("digest"), "last_verified": local_date(verify["at"]) if is_utc(verify.get("at"))
                 and gone is None else None,
                 "dependants": sorted("%s:%s" % (led.short, k) for k, r in carried.items() if r.get("parent_key") == key)}
        mark = {} if gone is None else {"departed": "%s/%s: %s" % (led.short, gone.get("version") or led.version,
                                                                    gone.get("decision") or "departed")}
        if row.get("origin") == "other-strand-modified":
            target = live.get(row.get("live_key"))
            if target is not None:
                target.update({k: v for k, v in fresh.items() if k != "dependants"})
                live[row["live_key"]] = full_live(target)
                refreshed.append(row["live_key"])
            continue
        qkey = "%s:%s" % (led.short, key)
        if qkey in live:
            live[qkey].update(fresh, **mark)
            if not mark:
                live[qkey].pop("departed", None)  # verified again: no longer departed
            live[qkey] = full_live(live[qkey])
            refreshed.append(qkey)
            continue
        built = ("native" if str(row.get("id")) in native else "client") if row.get("origin") in (
            "pre-existing-referenced", "pre-existing-modified") else "%s/%s" % (led.short, row.get("introduced_in"))
        if installed_native(row):  # A38: a native this strand installed is a native, which no strand owns (R17)
            built = "native"
        constraint, source = "change-with-own-yes", "pending strand close"
        same = shared_rows(live, row.get("id"), qkey)  # R5: one object under two keys keeps one constraint
        if same:
            strictest = max(same, key=lambda k: STRICTNESS.get(live[k].get("constraint"), 2))
            constraint = live[strictest].get("constraint")
            source = "as %s: %s" % (strictest, live[strictest].get("constraint_source"))
        owner = None if built in ("client", "native") else led.short  # R17: no strand owns a client or native row
        live[qkey] = full_live(dict(fresh, name_at_build=row.get("name"), owner_strand=owner, introduced_in=built,
                                    constraint=constraint, constraint_source=source, **mark))
        created.append(qkey)
    for key, row in sorted(led.objects.items()):
        qkey = row.get("live_key") if row.get("origin") == "other-strand-modified" else "%s:%s" % (led.short, key)
        if row.get("status") == "removed" and qkey in live and live[qkey].get("state") != "archived":
            live[qkey]["state"] = "archived"
            archived.append(qkey)
    return {"created": created, "refreshed": refreshed, "archived": archived}


def shared_rows(live, monday_id, but=None):
    """The qualified keys of every live row that holds this monday id, `but` aside (R5)."""
    if not monday_id:
        return []
    return sorted(k for k, r in live.items() if k != but and str((r or {}).get("monday_id")) == str(monday_id))


def protected_ids(live):
    """{monday id: qualified key} of every live row marked do-not-change (R5: the constraint protects the object)."""
    return {str(r.get("monday_id")): k for k, r in sorted(live.items())
            if (r or {}).get("constraint") == "do-not-change" and r.get("monday_id")}


def full_live(row):
    if all(name in row for name in LIVE_FIELDS):
        return row
    out = {name: row.get(name) for name in LIVE_FIELDS}
    out.update({k: v for k, v in row.items() if k not in out})
    return out


def cmd_run_end(root, args):
    led = fenced(root, args, ("running", "ended"))
    used = str(args.calls_used)
    pending = sorted(k for k, r in led.objects.items() if r.get("status") == "attempting"
                     and (r.get("attempt") or {}).get("run_id") == args.run_id)
    refuse(None if DIGITS.fullmatch(used) else ("(flags)", "--calls-used", "%r" % used, "a count, 0 or more"),
           None if not pending else (led.build_rel, "objects", "rows of run %s are still attempting: %s" % (
               args.run_id, ", ".join(pending)), "each recorded, departed or reconciled before the run ends"))
    fence(root, args)
    led.reload()
    before = mc.json_text(led.account)
    rows = live_rows(led)
    run = led.run(args.run_id)
    repeat = run.get("state") == "ended"
    if not repeat:
        now = mc.stamp("utc")
        run.update(ended_at=now, heartbeat_at=now, state="ended", calls_used=int(used))
        led.build["updated_at"] = now
    steps = []
    if mc.json_text(led.account) != before:
        led.account["updated_at"] = mc.stamp("utc")
        steps.append(("account.json", json_step(root, root / "account.json", led.account), None))
    step = map_step(led)
    steps += [step] if step else []
    if not repeat:
        steps.append((led.build_rel, json_step(root, led.build_path, led.build), None))
    epoch = int(args.lease_epoch) if DIGITS.fullmatch(str(args.lease_epoch)) else args.lease_epoch
    steps.append((mc.LOCK_REL, lambda: mc.lease_release(root, args.lease_epoch, args.session_label),
                  {"released": {"epoch": epoch}}))
    commit("run end", steps, args.run_id, "the same run end call again: it is safe to repeat, rewriting the live map "
           "and releasing the lease (ledger.py run end --strand %s --run-id %s ...)" % (led.short, args.run_id), root)
    return 0, {"run_id": args.run_id, "state": "ended", "calls_used": int(used), "live_rows": rows, "released": True,
               "written": {rel: mc.sha256_file(mc.record_path(root, rel)) for rel, _, _ in steps if rel != mc.LOCK_REL},
               "log": [entry_log(led.short, "build", led.version, args.run_id, [
                   "run ended, calls used %s" % used, "lease released, epoch %s" % epoch])],
               "next": "set version.md state built through record.py guard, and write the log entry through record.py log"}


# intent (W07, W10, W41, W47, W48, W50).

def counts_as_user(led, recipient):
    """Who counts as the user, for the one yes and the recipient rules (W45, R20 (a)): the bound user alone, read
    from account.json, or the blueprint's word `user` for that same person. This is the one place that decides it,
    so that a later decision of the user's can widen it."""
    return str(recipient) in ("user", led.bound_user)


def approved_recipients(led, entry, key):
    """The recipients the approval entry records for a key, `user` read as the bound user (R20 (a)); None when the
    entry was written before the approval recorded recipients."""
    recorded = entry.get("notifies_approved")
    if not isinstance(recorded, dict):
        return None
    return sorted({led.bound_user if r == "user" else str(r) for r in recorded.get(key) or []})


def approval_class(row, op, origin, ir, led):
    kind = row.get("type")
    if op == "archive":
        return "removed"
    if kind in ("publication", "activation"):
        return "publication"
    if origin in ("pre-existing-modified", "other-strand-modified"):
        return "irreversible"
    if origin == "pre-existing-referenced":
        return "card"
    if kind == "webhook":
        return "webhook"
    if (op == "connect" and kind == "project") or (op == "convert" and kind == "board"):
        return "irreversible"
    if kind in ("workspace", "folder", "subitems"):
        return "irreversible"
    if kind == "column":
        parent = row.get("parent_key")
        prow = led.objects.get(parent) if parent and ":" not in str(parent) else None
        if prow is None or prow.get("origin") != "created" or prow.get("type") != "board":
            return "irreversible"
    if kind in LIST_TYPES:
        return "list"
    return "irreversible" if ir in RAISES else "card"


def yes_needed(cls, mode, key, real):
    """The own yes a row needs at execution (W10, W45), `grouped`, `per-item` or None."""
    if cls == "card":
        return "per-item" if real else None
    if cls == "list":
        return "grouped" if mode == "per-list" or real else None
    if cls == "webhook" or mode == "per-list":
        return "per-item"
    if cls == "publication" and re.fullmatch(r"SQ\d+\.ACT", key):
        return "per-item"
    return "per-item" if real else None


def intent_move(led, key, row, op, retry):
    """None when the status chain allows this intent (W13), else the problem."""
    status, kind = row.get("status"), row.get("type")
    if retry:
        if status == "attempting":
            return None
        if status == "mismatch":
            if kind == "automation":
                return ("an automation in mismatch is never retried: a second automation is never created while the "
                        "first is live; depart the row with a switch-off step")
            if (row.get("attempt") or {}).get("retry"):
                return "the one different call form was tried already: depart the row"
            return None
        if status == "departed":
            last = [d for d in led.build.get("departures") or [] if d.get("key") == key]
            if last and last[-1].get("decision") == "later-retry":
                return None
            return "departed with the decision %s: only a later-retry departure is retried" % (
                last[-1].get("decision") if last else "none")
        return "%s is not a status a retry moves" % status
    if op in ("create", "activate", "publish") and status == "planned":
        return None
    if op == "update" and status in ("verified", "written"):
        return None
    if op == "update" and status == "planned" and template_part(led, row):  # A38: what the template brought
        return None
    if op == "archive" and status == "verified" and (row.get("id") or row.get("item_ids")):
        return None
    if op in ("connect", "convert") and status in ("planned", "verified"):
        return None
    return "row %s is %s; %s asks for attempting, a move the status chain does not allow" % (key, status, op)


def scope_reason(led, ws, what, allowed, label):
    operational = led.operational()
    if ws in operational:
        return ("account.json", label, "strand %s: %s %s is an operational workspace (never-demo), never a build target: "
                "%s" % (led.short, what, ws, operational[ws]), A21)
    if ws not in allowed:
        return ("account.json", label, "strand %s: %s %s is outside %s" % (
            led.short, what, ws, "this strand's build targets" if label.startswith("guard_index.build") else
            "the client's workspaces"), A21 + ": " + (", ".join(allowed) or "none"))
    return None


def cmd_intent(root, args):
    led = fenced(root, args, account=True)
    b, key, op, rel = led.build, args.key, args.operation, led.build_rel
    field = "objects." + str(key)
    refuse(None if op in OPERATIONS else ("(flags)", "--operation", "%r" % op, " | ".join(OPERATIONS)),
           None if op != "delete" else (rel, field + ".operation", "a delete: v1 never deletes any object, in any account",
                                        "archive, with its own yes and containment evidence"))
    row = led.objects.get(key)
    new = row is None
    current, current_ref, fields = current_approval(led)
    latest = latest_ref(led)
    if new:
        match = re.fullmatch(r"(B\d+)\.IB\d+", str(key))
        board = led.objects.get(match.group(1)) if match else None
        refuse(None if board is not None and board.get("type") == "board" else (
            rel, field, "no planned row %s: the key is in no approved revision of this strand" % key,
            "a key of an approved element-key table, or an item batch B<n>.IB<n> of a board row of this strand"))
        row = new_row("item_batch", key, args.name or "%s sample items" % board.get("name"), led.version, None)
        row["approval_ref"] = latest or board.get("approval_ref")
        row["blueprint_ref"] = None
    kind = row.get("type")
    reasons = [None if not args.type or args.type == kind else (rel, field + ".type", "%s given, %s planned" % (
        args.type, kind), "the planned type")]
    reasons += recovery_reasons(led, args.run_id)
    if op in FIT and kind not in FIT[op]:
        reasons.append(("(flags)", "--operation", "%s on a %s row" % (op, kind), "%s only on a %s row" % (
            op, " or ".join(FIT[op]))))
    if kind in ("activation", "publication") and op not in ("activate", "publish", "archive"):
        reasons.append(("(flags)", "--operation", "%s on a %s row" % (op, kind), "activate or publish"))
    move, status_before = intent_move(led, key, row, op, args.retry), row.get("status")
    if move:
        reasons.append((rel, field + ".status", move, "a move of the status chain record-map.md gives"))
    elif args.retry and status_before == "attempting":
        reasons += retry_reasons(led, key, row, "intent --retry")  # R10: a timeout is reconciled before any retry
    # approval and the frozen table (W07, W43, W47); the mode is the version being built's (R1, R13)
    ref = args.approval_ref or row.get("approval_ref")
    entry = led.approval(ref) if ref else None
    in_table = False
    if not ref:
        reasons.append((rel, field + ".approval_ref", "the row has no approval_ref", "the vNrM of the approval that "
                        "planned it, given as --approval-ref or kept from the planned row"))
    elif entry is None:
        reasons.append((rel, field + ".approval_ref", "%s resolves to no approval of this ledger" % ref,
                        "the vNrM of an approval entry of this build.json"))
    else:
        if args.approval_ref and str(entry.get("version")) != led.version and (new or op not in ("update", "archive")):
            reasons.append(("(flags)", "--approval-ref", "%s is an approval of %s, while the strand builds %s" % (
                args.approval_ref, entry.get("version"), led.version), "an approval of %s; an earlier version's only "
                            "for the table of a kept row's update or archive (R1)" % led.version))
        if op == "create" and status_before in ("planned", "departed") and ref != latest:
            reasons.append((rel, field + ".approval_ref", "%s is not the strand's latest approval of %s (%s)" % (
                ref, led.version, latest), "a create follows the latest approved revision: ledger.py approval moves "
                            "every planned row it keeps onto it (R12)"))
        if kind != "item_batch":
            text, frel = led.frozen(entry)
            rows = element_table(text)[0] if text is not None else None
            table = {k: (kd, nm) for k, kd, nm in rows or []}
            if rows is None:
                reasons.append((frel, "## Element keys", "the frozen revision has no element-key table, so %s cannot "
                                "be matched to it" % key, "a revision approved with the ## Element keys table"))
            elif key not in table:
                reasons.append((frel, "## Element keys", "%s is not a row of %s" % (key, ref),
                                "a key of that revision's table"))
            elif table[key][0] != kind:
                reasons.append((frel, "## Element keys", "%s is a %s there, a %s here" % (key, table[key][0], kind),
                                "the same kind"))
            elif op == "create" and (args.name or row.get("name")) != table[key][1]:
                reasons.append((frel, "## Element keys", "the name %r is not the approved %r" % (
                    args.name or row.get("name"), table[key][1]), "the planned name"))
            in_table = rows is not None and key in table
    if current is None:
        reasons.append((led.build_rel, "approvals", "no approval of %s, the revision of the version being built" %
                        current_ref, "ledger.py approval of the revision version.md names"))
    stored = (current or {}).get("approval_mode") or "per-list"
    derived = approval_mode(led, led.version, fields)[0] if fields else "per-list"
    if stored == "own-account-poc" and derived != "own-account-poc":
        reasons.append((led.build_rel, "approvals[].approval_mode", "%s records own-account-poc, while the record and "
                        "the version give %s" % (current_ref, derived), "own-account-poc only on an own-account record "
                        "building a proof of concept (A28, W44, R13)"))
    mode = "per-list" if "per-list" in (stored, derived) else stored
    if args.name and not new and args.name != row.get("name") and op == "create":
        reasons.append((rel, field + ".name", "%r given, %r planned" % (args.name, row.get("name")), "the planned name"))
    # origin and prior state (K127 to K130)
    origin = row.get("origin") or "created"
    if args.origin:
        if args.origin not in ORIGINS:
            reasons.append(("(flags)", "--origin", "%r" % args.origin, " | ".join(ORIGINS)))
        elif args.origin != origin and (origin != "created" or row.get("status") != "planned"
                                        or args.origin == "pre-existing-referenced"):
            reasons.append((rel, field + ".origin", "%s given, %s recorded" % (args.origin, origin), "the recorded origin"))
        else:
            origin = args.origin
    if origin == "pre-existing-referenced":
        reasons.append((rel, field + ".origin", "a referenced row is never written to monday", "ledger.py verify with "
                        "the read that proves the object exists"))
    needs_prior = origin in ("pre-existing-modified", "other-strand-modified")
    prior = None
    if args.prior_state and not needs_prior:
        reasons.append((rel, field + ".prior_state", "a prior state on a %s row" % origin,
                        "a prior state only on a pre-existing-modified or other-strand-modified row"))
    elif args.prior_state:
        prior = input_json(root, args.prior_state, "--prior-state")[0]
    if needs_prior and prior is None and row.get("prior_state") is None:
        reasons.append((rel, field + ".prior_state", "no prior state on a %s row" % origin,
                        "--prior-state with the object as read before the change"))
    source = args.source_strand or row.get("source_strand")
    live_key = args.live_key or row.get("live_key")
    live = led.account.get("live_objects") or {}
    owner_row = None
    if origin == "other-strand-modified":
        target = live.get(live_key) if live_key else None
        if not source or not re.fullmatch(r"\d{3}", str(source)) or source == led.short:
            reasons.append((rel, field + ".source_strand", "%r" % source, "the short id of the strand that built it"))
        if target is None:
            reasons.append(("account.json", "live_objects.%s" % live_key, "no live-map row %s" % live_key,
                            "--live-key <short>:<key>, a row of the live map"))
        elif source and not str(live_key).startswith("%s:" % source):
            reasons.append(("account.json", "live_objects.%s" % live_key, "the row is not strand %s's" % source,
                            "a row the source strand built"))
        elif target.get("constraint") == "do-not-change":
            reasons.append(("account.json", "live_objects.%s.constraint" % live_key, "%s is marked do-not-change (%s)" % (
                live_key, target.get("constraint_source")), "no change to it: a do-not-change row is left as it is"))
        else:
            owner_row = target
            if row.get("id") and str(row["id"]) != str(target.get("monday_id")):  # R9: the object is the live row's
                reasons.append((rel, field + ".id", "%s, while %s is %s" % (row["id"], live_key, target.get(
                    "monday_id")), "the id of the object the live row names"))
    elif args.source_strand or args.live_key:
        reasons.append((rel, field + ".source_strand", "--source-strand or --live-key on a %s row" % origin,
                        "only on an other-strand-modified row"))
    # parent (K132, K179, W58; R3: a parent is named by key, placed, and in the row's workspace)
    parent_key = args.parent_key if args.parent_key is not None else row.get("parent_key")
    parent_id = args.parent_id or row.get("parent_id")
    reasons.append(digits("--parent-id", args.parent_id))
    if args.parent_id and not parent_key and ID.fullmatch(str(args.parent_id)):
        holder = led.holder_of(args.parent_id)
        reasons.append(("(flags)", "--parent-id", "the parent %s is named by id alone%s" % (
            args.parent_id, ", while the record holds it as %s" % holder if holder else
            ", and the record places it in no workspace it knows"),
            "--parent-key with the row or the qualified live-map key that holds the parent, whose id is then read "
            "from it" + ("" if holder else "; " + A21 + ": record it as a pre-existing-referenced row and verify it "
                         "with a read that shows its workspace")))
    if args.parent_key and row.get("parent_key") and args.parent_key != row["parent_key"]:
        reasons.append((rel, field + ".parent_key", "%s given, %s planned" % (args.parent_key, row["parent_key"]),
                        "the planned parent"))
    parent_row = None
    if kind == "workspace" or kind in ACCOUNT_LEVEL:
        if parent_key:
            reasons.append((rel, field + ".parent_key", "a %s row has no parent" % kind, "no --parent-key"))
    elif parent_key and ":" in str(parent_key):
        target = live.get(parent_key)
        if target is None:
            reasons.append((rel, field + ".parent_key", "%s does not resolve" % parent_key, "a qualified live-map key"))
        elif parent_id and str(parent_id) != str(target.get("monday_id")):
            reasons.append((rel, field + ".parent_id", "%s, while %s is %s" % (parent_id, parent_key, target.get(
                "monday_id")), "the parent's id"))
        else:
            parent_id = target.get("monday_id")
    elif parent_key:
        parent_row = led.objects.get(parent_key)
        if parent_row is None:
            reasons.append((rel, field + ".parent_key", "%s does not resolve to a row of this ledger" % parent_key,
                            "a row of this ledger, or a qualified live-map key"))
        elif not parent_row.get("id") and kind not in ("publication", "activation"):
            reasons.append((rel, field + ".parent_key", "the parent %s has no id yet" % parent_key,
                            "the parent recorded with its id before a child is created"))
        elif parent_id and str(parent_id) != str(parent_row.get("id")):
            reasons.append((rel, field + ".parent_id", "%s, while %s is %s" % (parent_id, parent_key, parent_row["id"]),
                            "the parent's id"))
        else:
            parent_id = parent_row.get("id")
    guarded = ["%s:%s" % (led.short, key)] + ([parent_key if ":" in str(parent_key) else "%s:%s" % (led.short, parent_key)]
                                              if parent_key else [])
    for qkey in guarded:
        target = live.get(qkey) or {}
        if target.get("constraint") == "do-not-change":
            reasons.append(("account.json", "live_objects.%s.constraint" % qkey, "%s is marked do-not-change (%s)" % (
                qkey, target.get("constraint_source")), "no change to it or under it: a do-not-change row is left as it is"))
    if kind in ("publication", "activation"):
        if parent_row is None or parent_row.get("status") != "verified":
            reasons.append((rel, field, "the %s of %s comes only after %s has been verified" % (kind, parent_key, parent_key),
                            "%s verified by its read-back first" % parent_key))
        if re.fullmatch(r"SQ\d+\.ACT", str(key)):
            reasons.append((rel, field, "a sequence activation is refused in v1 until sequences are probed",
                            "a UI step for the user, or a later version once the probe has run"))
        if kind == "publication" and not re.search(r"\b(in)?active\b", str(row.get("name"))):
            reasons.append((rel, field + ".name", "the publication does not name the decided activation state",
                            "a name that says active or inactive, decided before publishing"))
    if op == "connect":
        companions = row.get("companions") or {}
        if not (companions.get("tasks_board_id") and companions.get("overview_board_id")):
            reasons.append((rel, field + ".companions", "the project's tasks board and overview are not recorded",
                            "record --companion tasks_board_id=<id> --companion overview_board_id=<id> first"))
    # workspace, scope and references (W40, W41, K137 to K150)
    workspace, scope = None, []
    reasons.append(digits("--workspace", args.workspace))
    reasons += [digits("--scope", ws) for ws in args.scope or []]
    account_level = kind in ACCOUNT_LEVEL or (kind in ("publication", "activation") and parent_row is not None
                                              and parent_row.get("type") in ACCOUNT_LEVEL)
    if account_level:
        if args.workspace:
            reasons.append(("(flags)", "--workspace", "an account-level %s has no workspace" % kind, "--scope instead"))
        scope = list(args.scope or row.get("workspace_scope") or (parent_row or {}).get("workspace_scope") or [])
        if not scope:
            reasons.append((rel, field + ".workspace_scope", "an account-level row with no scope",
                            "--scope, the client workspaces it may read and write"))
        reasons += [scope_reason(led, ws, "the scope workspace", led.client_ids, "guard_index.client_workspace_ids")
                    for ws in scope]
    elif kind == "workspace":
        if args.workspace or args.scope:
            reasons.append(("(flags)", "--workspace", "a workspace row takes no workspace or scope",
                            "no flag: record sets its own id as its workspace"))
    else:
        if args.scope:
            reasons.append(("(flags)", "--scope", "a %s is not an account-level row" % kind, "--workspace"))
        if args.workspace and row.get("workspace") and args.workspace != row["workspace"]:
            reasons.append((rel, field + ".workspace", "%s given, %s recorded" % (args.workspace, row["workspace"]),
                            "the recorded workspace"))
        placed = None
        if parent_key and ":" not in str(parent_key):
            placed = led.row_workspace(parent_key)
        elif parent_key:
            target = live.get(parent_key) or {}
            placed = target.get("monday_id") if target.get("kind") == "workspace" else target.get("workspace")
        workspace = args.workspace or row.get("workspace") or placed
        if not workspace:
            reasons.append((rel, field + ".workspace", "the row has no workspace", "--workspace, one of this strand's "
                            "build targets"))
        else:
            workspace = str(workspace)
            reasons.append(scope_reason(led, workspace, "the target workspace", led.targets(),
                                        "guard_index.build_targets_by_strand.%s" % led.short))
            if parent_key and (parent_row is not None or ":" in str(parent_key)) and str(placed or "") != workspace:
                reasons.append((rel, field + ".parent_key", "strand %s: the parent %s is in workspace %s, the row in %s"
                                % (led.short, parent_key, placed or "none the record knows", workspace),
                                A21 + ": a parent in the row's own workspace (R3)"))
    # A38: a native install (R-D narrowed) takes the template its approval holds, into a CRM or Service build target
    install = ((entry or {}).get("native_installs") or {}).get(key) if in_table else None
    template_id = (install or {}).get("template_id")
    if args.template_id and install is None:
        reasons.append(("(flags)", "--template-id", "%s holds no native install for %s" % (ref, key),
                        "a template id only on a board row whose approved table names that template"))
    elif args.template_id and args.template_id != template_id:
        reasons.append(("(flags)", "--template-id", "%s given, while %s approves %s for %s" % (
            args.template_id, ref, template_id, key), "the template id the approval holds, or no flag"))
    if template_id and op != "create":
        reasons.append((rel, field, "a %s of the native %s installs: the board itself keeps guard R-B" % (op, key),
                        "a create only; its planned columns and groups change under their own rows"))
    elif template_id and workspace:
        product, _, named = installable(template_id)
        entity = "%s/%s" % (product, named)
        kind_of = (led.index.get("product_workspaces") or {}).get(workspace)
        if kind_of != product:
            reasons.append(("account.json", "guard_index.product_workspaces.%s" % workspace, "strand %s: the target "
                            "%s is %s, and template %s installs a %s board" % (led.short, workspace, "a %s workspace" % (
                                kind_of) if kind_of else "a workspace of no product the record knows", template_id,
                                product), "a %s workspace among this strand's build targets" % product))
        for bid in (led.index.get("native_board_ids_by_entity") or {}).get(entity) or []:
            if led.place(str(bid)) == workspace and str(bid) != str(row.get("id")):
                reasons.append(("account.json", "guard_index.native_board_ids_by_entity.%s" % entity, "workspace %s "
                                "already has the native %s, board %s" % (workspace, entity, bid),
                                "the blueprint uses that board (A5): a native install only where its entity has none"))
    refs = list(args.ref or row.get("refs") or [])
    ref_ids = []
    for item in refs:
        match = REF_FORM.fullmatch(item)
        if not match:
            reasons.append(("(flags)", "--ref", "%r" % item, "<board|workspace|doc|view|column>:<id>, the id with no "
                            "leading zero"))
        elif match.group(1) == "workspace":
            reasons.append(scope_reason(led, match.group(2), "the referenced workspace", led.client_ids,
                                        "guard_index.client_workspace_ids"))
        else:
            ref_ids.append(match.group(2))
            placed = led.place(match.group(2))
            if placed is None:
                reasons.append(("account.json", "guard_index.client_workspace_ids", "strand %s: the referenced %s %s is "
                                "in no workspace the record knows, so it counts as outside the client's workspaces" % (
                                    led.short, match.group(1), match.group(2)),
                                A21 + "; to place it, record it as a pre-existing-referenced row and verify it with a "
                                "read that shows its workspace"))
            else:
                reasons.append(scope_reason(led, placed, "the referenced %s %s, in workspace" % (
                    match.group(1), match.group(2)), led.client_ids, "guard_index.client_workspace_ids"))
    # R5: a do-not-change constraint protects the object, whatever key a strand mirrors it under
    protected, named = protected_ids(live), set(guarded)
    for oid, what in [((owner_row or {}).get("monday_id") or row.get("id"), "the row's own object"),
                      (parent_id, "its parent")] + [(i, "a referenced object") for i in ref_ids]:
        qkey = protected.get(str(oid)) if oid else None
        if qkey and qkey not in named:
            named.add(qkey)
            reasons.append(("account.json", "live_objects.%s.constraint" % qkey, "%s, %s, is marked do-not-change as "
                            "%s (%s)" % (what, oid, qkey, live[qkey].get("constraint_source")),
                            "no change to it or under it, whatever key a strand mirrors it under"))
    # recipients, sample data, assumptions, prompt, --ir
    notifies = list(args.notifies or row.get("notifies") or [])
    if "user" in notifies:  # demos' fixes, 4: the word the approval table writes, read as the bound user's id
        if ID.fullmatch(led.bound_user):
            notifies = [led.bound_user if n == "user" else n for n in notifies]
        else:
            reasons.append(("account.json", "account.bound_user_id", "--notifies user, while the record has no bound "
                            "user (%s)" % led.bound_user, "ledger.py bind first, which records the bound user"))
    reasons += [None if n == "user" or RECIPIENT.fullmatch(n) else (
        "(flags)", "--notifies", "%r" % n, "user, a user id, team:<id> or email:<address>") for n in notifies]
    if kind == "sequence" and not notifies:
        reasons.append((rel, field + ".notifies", "a sequence with no recipients", "every recipient, shown at approval"))
    # R20 (a): the recipients are the ones the approved revision records for the key, as a set
    approved = approved_recipients(led, entry, key) if entry is not None and in_table else None
    if entry is not None and in_table and approved is None:
        reasons.append((led.build_rel, "approvals[].notifies_approved", "%s was approved before the approval recorded "
                        "who each element notifies, so the recipients of %s cannot be held to it" % (ref, key),
                        "a revision approved with the notifies column of the ## Element keys table"))
    elif entry is not None and kind == "item_batch":
        approved = []  # an item batch has no row in the table, so no recipient was approved for it
    if approved is not None and sorted(set(notifies)) != approved:
        reasons.append((rel, field + ".notifies", "%s given, while %s approves %s for %s" % (
            ", ".join(sorted(set(notifies))) or "no recipient", ref, ", ".join(approved) or "no recipient", key),
            "--notifies with exactly the recipients the approved revision records for %s, each once%s" % (
                key, "" if approved else ", which is none")))
    real = [n for n in notifies if not counts_as_user(led, n)]
    if kind == "item_batch" and not args.sample_data:
        reasons.append(("(flags)", "--sample-data", "a seed batch without the flag", "--sample-data: a seed batch is "
                        "sample data"))
    if kind != "item_batch" and args.sample_data:
        reasons.append(("(flags)", "--sample-data", "on a %s row" % kind, "only on an item batch"))
    direction = (args.direction_change or "").strip() or row.get("direction_change")
    if kind == "workspace" and op == "create" and args.product not in ("core", "crm", "service"):
        reasons.append(("(flags)", "--product", "%r on a workspace create" % args.product,
                        "core | crm | service: the product the workspace is for"))
    elif kind == "workspace" and op == "create":
        have = (led.account.get("client_workspaces") or {}).get(args.product)
        if have and have.get("id") and not direction:  # R11: refused before the create, never after it
            reasons.append(("account.json", "client_workspaces.%s" % args.product, "the client already has a %s "
                            "workspace, %s" % (args.product, have.get("id")), "one workspace per product, unless the "
                            "user decided on a new direction: --direction-change with the log reference of that decision"))
    if kind != "workspace" and args.product:
        reasons.append(("(flags)", "--product", "on a %s row" % kind, "only on a workspace row"))
    if args.direction_change and not (kind == "workspace" and op == "create"):
        reasons.append(("(flags)", "--direction-change", "on a %s %s" % (kind, op), "only on a workspace create"))
    assumptions = list(args.assumption_ref or row.get("assumption_refs") or [])
    text = led.frozen(entry)[0] if entry is not None else None
    for item in args.assumption_ref or []:
        if not ASSUMPTION_ID.fullmatch(item):
            reasons.append(("(flags)", "--assumption-ref", "%r" % item, "AS<n>, AT<n> or FK<n>"))
        elif text is None or not re.search(r"(?<![A-Za-z0-9])%s(?![0-9])" % item, text):
            reasons.append(("(flags)", "--assumption-ref", "%s is not in the frozen revision of %s" % (item, ref),
                            "an id the frozen revision gives"))
    prompt_ref = args.prompt_ref or row.get("prompt_ref")
    if kind in PROMPT_TYPES:
        parsed = parse_ref(prompt_ref)
        pentry = led.approval("%sr%d" % parsed[:2]) if parsed else None
        ptext = led.frozen(pentry)[0] if pentry else None
        if parsed is None or parsed[2] != key or ptext is None or prompt_block(ptext, key) is None:
            reasons.append((rel, field + ".prompt_ref", "%r does not name a frozen prompt of %s" % (prompt_ref, key),
                            "vNrM#%s, a revision whose file holds ### Prompt %s" % (key, key)))
    elif args.prompt_ref:
        reasons.append(("(flags)", "--prompt-ref", "on a %s row" % kind, "only on an agent, AI column or Vibe app"))
    if args.ir and args.ir not in RAISES:
        reasons.append(("(flags)", "--ir", "%r" % args.ir, "IR-04, IR-05 or IR-06, which raise a card row"))
    reasons.append(None if not args.payload_sha or re.fullmatch(r"[0-9a-f]{64}", args.payload_sha) else (
        "(flags)", "--payload-sha", "%r" % args.payload_sha, "the sha256 of the payload file"))
    # the change-check gate (W49)
    check = led.account.get("change_check") or {}
    outcome = check.get("result", check.get("verdict"))
    if check.get("for_strand") != led.short or not is_utc(check.get("at")) or local_date(check["at"]) != mc.stamp("date") \
            or not (outcome == CHANGE_RESULTS[0] or check.get("approved_by_user")):
        reasons.append(("account.json", "change_check", "no change check of today for strand %s that lets the build go on "
                        "(for %s, at %s, %s)" % (led.short, check.get("for_strand"), check.get("at"), outcome),
                        "ledger.py change-check --strand %s today, with no change affecting this build or the user's yes"
                        % led.short))
    # the class and its yes (W10, W45, W48); a yes is this run's, for this operation, and used once (R2, R15)
    if real:  # R20 (a), W45, A28: a recipient other than the user takes the row out of the card, in either account
        mode = "per-list"
    cls = approval_class(dict(row, parent_key=parent_key), op, origin, args.ir, led)
    need = yes_needed(cls, mode, str(key), real)
    run = led.run(args.run_id) or {}
    retried = (row.get("attempt") or {}).get("started_at") if args.retry else None
    entries = b.get("irreversible_yes") or []
    yes = [n for n, e in enumerate(entries) if e.get("key") == key and e.get("mode") in ("per-item", "grouped")
           and e.get("run_id") == args.run_id and (e.get("operation") or "create") == op
           and str(e.get("at") or "") >= str(run.get("started_at") or "9999")
           and (e.get("used_by") is None or (retried and e.get("used_by") == retried))]
    chosen = [n for n in yes if entries[n].get("mode") == need] if need else yes
    if need and not chosen:
        reasons.append((rel, "irreversible_yes", "%s needs its own %s yes for this %s in this run (class %s, mode %s%s)" % (
            key, need, op, cls, mode, ", it notifies %s" % ", ".join(real) if real else ""),
            "ledger.py irreversible-yes --key %s --mode %s --operation %s in this run: a yes covers one step, never "
            "another run or a later step" % (key, need, op)))
    used = chosen[-1] if chosen else None
    evidence = (entries[used].get("evidence") if used is not None else None) if need else args.evidence
    if cls == "removed" and not (evidence and evidence.strip()):
        reasons.append((rel, "irreversible_yes", "an archive of %s with no containment evidence" % key,
                        "the evidence that nothing else uses it, on the archive's own yes (or as --evidence under "
                        "the proof of concept's card)"))
    refuse(*reasons)
    fence(root, args)
    led.reload()
    b = led.build
    row = ordered_row(led.objects.get(key) or row)
    now = mc.stamp("utc")
    if owner_row is not None:
        row["id"] = str(owner_row.get("monday_id"))
    payload = {"key": key, "type": kind, "operation": op, "name": row.get("name"), "parent_id": parent_id,
               "workspace": workspace, "workspace_scope": sorted(scope), "refs": sorted(refs),
               "notifies": sorted(notifies), "payload_sha256": args.payload_sha}
    if template_id:
        payload["template_id"] = row["template_id"] = template_id
    row.update(origin=origin, parent_key=parent_key, parent_id=str(parent_id) if parent_id else None, status="attempting",
               attempt={"run_id": args.run_id, "started_at": now, "intent_digest": hash8(payload), "operation": op,
                        "retry": bool(args.retry) and status_before == "mismatch"},
               irreversible=cls != "card", approval_ref=ref, notifies=notifies, refs=refs, assumption_refs=assumptions,
               sample_data=kind == "item_batch")
    if account_level:
        row.update(workspace=None, workspace_scope=scope)
    elif kind != "workspace":
        row["workspace"] = workspace
    else:
        row["product"] = args.product or row.get("product")
        if direction:
            row["direction_change"] = direction
    if kind in ("publication", "activation") and parent_row is not None:
        row["id"] = parent_row.get("id")
    if prior is not None:
        row["prior_state"] = prior
    if origin == "other-strand-modified":
        row.update(source_strand=source, live_key=live_key)
    if kind in PROMPT_TYPES:
        row["prompt_ref"] = prompt_ref
    if op == "update" and led.version not in row["changed_in"] and led.version != row.get("introduced_in"):
        row["changed_in"].append(led.version)
    led.objects[key] = row
    if used is not None:
        b["irreversible_yes"][used]["used_by"] = now
    card = mode == "own-account-poc" and cls != "card" and not need and not yes
    if card:
        b.setdefault("irreversible_yes", []).append({
            "key": key, "what": "%s %s %s" % (op, kind, row.get("name")), "at": now, "mode": "card", "approval_ref": ref,
            "evidence": (args.evidence or "").strip() or None, "log_ref": None, "run_id": args.run_id, "operation": op,
            "used_by": now})
    beat(led, args.run_id)
    written = save_build(led, "intent", args.run_id)
    return 0, {"key": key, "status": "attempting", "class": cls, "approval_mode": mode, "yes": need or (
        "card" if card else None), "attempt": row["attempt"], "irreversible": row["irreversible"], "written": written}


# record, verify (W50 to W54).

def known_id(row):
    """The id a modifying row's object already has (R9): an other-strand-modified row's, set by intent from its live
    row, or the id of a pre-existing-modified row's prior state; None for every other row."""
    if row.get("origin") == "other-strand-modified":
        return str(row["id"]) if row.get("id") else None
    if row.get("origin") == "pre-existing-modified" and isinstance(row.get("prior_state"), dict):
        found = row["prior_state"].get("id")
        return str(found) if found not in (None, "") else None
    return None


def installed_native(row):
    """True for the board row of a native this strand installed (A38): created from an approved template and verified
    as that template's native, which gave it its role."""
    return bool(row) and row.get("type") == "board" and row.get("origin") == "created" and bool(
        row.get("template_id")) and bool(row.get("role"))


def template_part(led, row):
    """True for a column or group row on a native this strand installed (A38, R-B narrowed): what the template brought
    is recorded by its existing id and changed under this strand's approval, with no change-table row of its own."""
    parent = row.get("parent_key")
    return row.get("type") in ("column", "group") and bool(parent) and ":" not in str(parent) and installed_native(
        led.objects.get(parent))


def register_install(led, key, row):
    """A38: the native a verified install made, entered in guard_index as native-map enters a native it reads
    (native_board_index, native_board_ids_by_entity) and in native_installs as this strand's; its "product/entity"."""
    product, _, entity = installable(row["template_id"])
    value, bid = "%s/%s" % (product, entity), str(row["id"])
    index = led.index
    index.setdefault("native_board_index", {})[bid] = value
    ids = index.setdefault("native_board_ids_by_entity", {}).setdefault(value, [])
    if bid not in [str(i) for i in ids]:
        ids.append(bid)
        ids.sort(key=id_sort)
    index.setdefault("native_installs", {})[bid] = "%s:%s" % (led.short, key)
    row["role"] = value
    return value


def cmd_record(root, args):
    led = fenced(root, args, account=True)
    rel, key = led.build_rel, args.key
    field = "objects." + str(key)
    row = led.objects.get(key)
    refuse(None if row is not None else (rel, field, "no row %s" % key, "a row of this ledger"))
    kind, attempt = row.get("type"), row.get("attempt") or {}
    op = attempt.get("operation")
    items = list(args.item_id or [])
    companions = {}
    known = known_id(row)
    reasons = [None if row.get("status") == "attempting" else (
        rel, field + ".status", "row %s is %s; record moves only an attempting row" % (key, row.get("status")),
        "ledger.py intent first"), None if kind in KEY_IDS and re.fullmatch(r"[A-Za-z0-9_]+", str(args.id or "x"))
        else digits("--id", args.id)] + [digits("--item-id", item) for item in items]
    if known and args.id and str(args.id) != known:
        reasons.append((rel, field + ".id", "--id %s on a %s row whose object is %s" % (args.id, row.get("origin"), known),
                        "the id of the object the row modifies: a modification never makes the row another object"))
    for item in args.companion or []:
        name, _, value = item.partition("=")
        if name not in COMPANIONS or (name in ("tasks_board_id", "folder_id") and kind != "project"):
            reasons.append(("(flags)", "--companion", "%r" % name, "one of %s (the last two on a project)" % ", ".join(COMPANIONS)))
        reasons.append(digits("--companion", value))
        companions[name] = value
    if kind == "item_batch" and (args.id or len(items) > 20):
        reasons.append(("(flags)", "--item-id", "an item batch takes its item ids, at most 20, and no --id",
                        "--item-id per item returned"))
    if items and kind != "item_batch":
        reasons.append(("(flags)", "--item-id", "item ids on a %s row" % kind, "--id"))
    if args.id_from_error and not args.id:
        reasons.append(("(flags)", "--id", "--id-from-error with no id", "the id read out of the error payload"))
    if args.pending:
        if kind not in POLL_CEILINGS:
            reasons.append(("(flags)", "--pending", "a %s is not created asynchronously" % kind,
                            "only a portfolio, a project or a Vibe app is polled"))
        if not DIGITS.fullmatch(str(args.polled_seconds or "")):
            reasons.append(("(flags)", "--polled-seconds", "%r" % args.polled_seconds, "the seconds polled so far"))
    landed = not (args.timed_out or args.id_from_error or args.pending)
    if landed and op != "archive" and not (args.id or items or (kind in ("publication", "activation") and row.get("id"))
                                           or (row.get("origin") == "other-strand-modified" and known)):
        reasons.append(("(flags)", "--id", "no id returned", "--id (or --item-id for a batch), or --timed-out, "
                        "--id-from-error or --pending when the call gave none"))
    refuse(*reasons)
    fence(root, args)
    led.reload()
    row = led.objects[key] = ordered_row(led.objects[key])
    message = None
    if args.id:
        row["id"] = args.id
    if args.url:
        row["url"] = args.url
    row["companions"] = dict(row.get("companions") or {}, **companions)
    if args.timed_out:
        message = "possibly applied: reconcile before any retry"
    elif args.id_from_error:
        message = "the id read from the error is kept; the row stays attempting until reconcile or a read settles it"
    elif args.pending:
        ceiling = POLL_CEILINGS[kind]
        message = ("keep polling, every 10 seconds, up to %d seconds" % ceiling if int(args.polled_seconds) < ceiling else
                   "not found by the ceiling of %d seconds: run reconcile, then retry or depart" % ceiling)
    elif op == "archive":
        row.update(status="removed", state="archived")
    else:
        row["status"] = "written"
        if items:
            row["item_ids"] = items
        if kind == "workspace":
            row["workspace"] = row["id"]
        if kind == "subitems" and row.get("parent_key") in led.objects:
            parent = led.objects[row["parent_key"]] = ordered_row(led.objects[row["parent_key"]])
            parent["companions"] = dict(parent.get("companions") or {}, subitems_board_id=row["id"])
    beat(led, args.run_id)
    written = save_build(led, "record", args.run_id)
    return 0, {"key": key, "status": row["status"], "state": row.get("state"), "id": row.get("id"),
               "message": message, "written": written}


def verify_reasons(led, key, row, result, obj, note, rel):
    kind, field, found = row.get("type"), "objects.%s.verify" % key, []
    if result == "match":
        if kind in NO_MATCH:
            found.append((rel, field, "a %s has no read-back yet: match is never recorded for it" % kind,
                          "not-checkable, with a note saying who checks it and how"))
        if kind == "publication" and str(key).startswith("WF"):
            found.append((rel, field, "a workflow's live trigger binding is not readable", "needs-user, naming the "
                          "sandbox trigger test"))
        perms = [p for p in ("column_permissions", "item_permissions", "subitem_permissions") if p in obj]
        if perms:
            found.append((rel, field, "permissions below board level (%s) have no read" % ", ".join(perms),
                          "not-checkable for those; board-level permissions through the board's permissions field"))
    if kind == "agent":
        missing = [p for p in ("plan", "state", "version_id", "triggers", "knowledge") if p not in obj]
        if missing:
            found.append((rel, field, "the agent read lacks %s" % ", ".join(missing),
                          "plan, state, version_id, triggers and knowledge from manage_agent get"))
        if "skills" in obj:
            found.append((rel, field, "a skills read: no per-agent skill read exists", "skills left to the by-eye list"))
        if result == "match" and not missing:
            parsed = parse_ref(row.get("prompt_ref"))
            entry = led.approval("%sr%d" % parsed[:2]) if parsed else None
            text = led.frozen(entry)[0] if entry else None
            frozen = prompt_block(text, key) if text else None
            if frozen is None or normalise_prompt(obj.get("plan")) != normalise_prompt(frozen):
                found.append((rel, field, "the plan read differs from the frozen prompt of %s" % row.get("prompt_ref"),
                              "the plan equal to the ### Prompt %s block, line endings aside" % key))
            activation = led.objects.get("%s.ACT" % key) or {}
            if str(obj.get("state")).upper() == "ACTIVE" and activation.get("status") != "verified":
                found.append((rel, field, "the agent is active while its activation is not verified",
                              "the agent created inactive; activation is a step of its own"))
    if kind == "vibe_app":
        missing = [p for p in ("status", "is_published", "code_version", "differs_from_request") if p not in obj]
        if missing:
            found.append((rel, field, "the Vibe app read lacks %s" % ", ".join(missing),
                          "status, is_published, code_version and differs_from_request"))
        if result == "match" and obj.get("status") != "READY":
            found.append((rel, field, "status %r" % obj.get("status"), "READY before the app is verified"))
        if result == "match" and obj.get("differs_from_request") is True and not (
                is_str(obj.get("user_yes_to_difference")) and is_str(obj.get("difference"))):
            found.append((rel, field, "the delivered app differs from the request with no yes from the user",
                          "difference and user_yes_to_difference in the read, the user's own words"))
    if kind == "workflow":
        missing = [p for p in ("state", "validation") if p not in obj]
        if missing:
            found.append((rel, field, "the workflow read lacks %s" % ", ".join(missing), "state and validation"))
        if result == "match" and obj.get("validation") != "no issues":
            found.append((rel, field, "validation %r" % obj.get("validation"), "no issues"))
    if kind == "project" and ("link_board_ids" in obj or "row_board_ids" in obj) and result == "match":
        tasks = (row.get("companions") or {}).get("tasks_board_id")
        halves = [tasks in [str(i) for i in obj.get(p) or []] for p in ("link_board_ids", "row_board_ids")]
        if not all(halves):
            found.append((rel, field, "one half of the link only: partial link", "needs-user with the note partial link"))
    if kind == "board" and row.get("template_id") and result == "match":  # A38: a genuine install, its rows archived
        lineage = obj.get("created_from_board_id")
        if str(lineage) != str(row["template_id"]):
            found.append((rel, field, "the read's created_from_board_id is %s, while the approved template is %s" % (
                lineage, row["template_id"]), "the board's created_from_board_id equal to the approved template id"))
        if obj.get("items_count") not in (0, "0"):
            found.append((rel, field, "the read's items_count is %s: the template's rows are not all archived" % (
                obj.get("items_count") if "items_count" in obj else "not read"), "items_count 0, read after the "
                "template's rows are archived and before the build adds its own sample rows"))
    want = str(row["id"]) if row.get("origin") in ("other-strand-modified", "pre-existing-modified") and row.get(
        "id") else known_id(row)
    if want and obj.get("id") not in (None, "") and str(obj["id"]) != want:  # R9: the read is of the modified object
        found.append((rel, field, "the read is of %s, while the row modifies %s" % (obj["id"], want),
                      "a read of the object the row modifies"))
    if row.get("origin") == "pre-existing-referenced" and row.get("status") == "planned":
        if not (ID.fullmatch(str(obj.get("id") or "")) and ID.fullmatch(str(obj.get("workspace_id") or ""))):
            found.append((rel, field, "the read does not show the object's id and workspace",
                          "object.id and object.workspace_id, the read that proves it exists"))
        if result not in ("match", "mismatch"):
            found.append((rel, field, "%s on a referenced row" % result, "match or mismatch"))
    return found


def cmd_verify(root, args):
    led = fenced(root, args, account=True)
    rel, key = led.build_rel, args.key
    field = "objects." + str(key)
    row = led.objects.get(key)
    refuse(None if row is not None else (rel, field, "no row %s" % key, "a row of this ledger"),
           None if args.result in RESULTS else ("(flags)", "--result", "%r" % args.result, " | ".join(RESULTS)))
    status = row.get("status")
    referenced = row.get("origin") == "pre-existing-referenced" and status == "planned"
    refuse(None if status in ("written", "removed") or referenced else (
        rel, field + ".status", "row %s is %s; verify records a read of a written, removed or planned referenced row" % (
            key, status), "ledger.py record first"),
           None if args.result in ("match", "mismatch") or (args.note or "").strip() else (
               "(flags)", "--note", "a %s result with no note" % args.result, "who checks it and how"))
    data, name = input_json(root, args.read, "--read")
    obj = data.get("object")
    refuse(None if is_str(data.get("read")) else (name, "read", "no read named", "the read made: the query or tool and "
                                                  "its fields"),
           None if isinstance(obj, dict) and obj else (name, "object", "no fields read", "the fields the read returned"))
    refuse(*verify_reasons(led, key, row, args.result, obj, args.note, rel))
    fence(root, args)
    led.reload()
    row = led.objects[key] = ordered_row(led.objects[key])
    kind, result = row.get("type"), args.result
    note = (args.note or "").strip() or None
    if kind == "vibe_app" and obj.get("differs_from_request") is True and result == "match":
        note = "differs: %s; the user's yes: %s" % (obj["difference"], obj["user_yes_to_difference"]) + (
            "; %s" % note if note else "")
    if kind == "project" and result == "needs-user" and ("link_board_ids" in obj or "row_board_ids" in obj) and \
            "partial link" not in (note or ""):
        note = "partial link: %s" % note
    now = mc.stamp("utc")
    named = obj if obj.get("id") not in (None, "") or not row.get("id") else dict(obj, id=row["id"])  # demos' fixes, 3
    row["verify"] = {"read": data["read"], "at": now, "result": result, "digest": digest(str(key).lower(), identity(
        kind, named)), "note": note}
    if referenced:
        row.update(id=str(obj["id"]), workspace=str(obj["workspace_id"]), status="verified" if result == "match" else "mismatch")
    elif status == "written":
        row["status"] = {"match": "verified", "mismatch": "mismatch"}.get(result, "written")
    state = str(obj.get("state") or "").lower()
    if kind == "automation" and not state and isinstance(automation_active(obj), bool):
        state = "active" if automation_active(obj) else "inactive"
    if status != "removed" and state in STATES and (state != "inactive" or kind in INACTIVE_OK):
        row["state"] = state
    elif status != "removed" and result == "match" and row.get("state") is None:
        row["state"] = "active"
    values = {"agent": ("state", "version_id"), "vibe_app": ("status", "is_published", "code_version"),
              "workflow": ("state",)}.get(kind)
    if values:
        row["read_values"] = {name_: obj.get(name_) for name_ in values}
    if kind == "agent" and result == "match":
        row["version_id_at_build"] = obj.get("version_id")
    if row.get("origin") in ("pre-existing-referenced", "pre-existing-modified") and row.get("id"):
        index = led.index.get("native_board_index") or {}
        projects = {str(p.get("tasks_board_id")) for item in ((led.account.get("native_map") or {}).get("portfolio") or {}).values()
                    for p in (item or {}).get("projects") or []}
        row["role"] = index.get(str(row["id"])) or ("project_tasks_board" if str(row["id"]) in projects else None)
    native = register_install(led, key, row) if kind == "board" and row.get("template_id") and result == "match" else None
    beat(led, args.run_id)
    if native is None:
        written = save_build(led, "verify", args.run_id)
    else:  # A38: the index first, so a failure between the two writes still protects the board as native
        led.account["updated_at"] = led.build["updated_at"] = now
        commit("verify", [("account.json", json_step(root, root / "account.json", led.account), None),
                          (led.build_rel, json_step(root, led.build_path, led.build), None)], args.run_id,
               "the same verify call again: it registers the native as it is and writes the ledger row", root)
        written = {"account.json": mc.sha256_file(root / "account.json"), led.build_rel: mc.sha256_file(led.build_path)}
    extra = [t for t in obj.get("triggers") or [] if kind == "agent" and str(t if not isinstance(t, dict) else t.get(
        "name")) not in DEFAULT_TRIGGERS]
    live = led.account.get("live_objects") or {}
    shared = [{"key": k, "constraint": live[k].get("constraint"), "source": live[k].get("constraint_source")}
              for k in shared_rows(live, row.get("id"), "%s:%s" % (led.short, key))] if referenced else []
    return 0, {"key": key, "status": row["status"], "result": result, "digest": row["verify"]["digest"],
               "note": note, "triggers_beyond_defaults": extra, "written": written,
               "same_object_as": shared,  # R5: its live row will take the strictest of these constraints at run end
               "next": None if not shared else "this object is already in the live map as %s; run end gives its row "
               "the strictest constraint those rows hold" % ", ".join(s["key"] for s in shared)}


# depart, ui-step, irreversible-yes (W48, W55, W56).

def table_ui_keys(led):
    keys = set()
    for entry in led.build.get("approvals") or []:
        text = led.frozen(entry)[0]
        rows = element_table(text)[0] if text else None
        keys |= {key for key, kind, _ in rows or [] if kind == "ui_step"}
    return keys


def next_ui_key(led):
    taken = table_ui_keys(led) | {str(s.get("key")) for s in led.build.get("ui_steps") or []}
    numbers = [int(k[1:]) for k in taken if re.fullmatch(r"U\d+", k)]
    return "U%d" % (max(numbers + [0]) + 1)


def cmd_depart(root, args):
    led = fenced(root, args)
    rel, key = led.build_rel, args.key
    row = led.objects.get(key)
    attempts = list(args.attempt or [])
    ui = args.decision == "ui-step"
    refuse(None if row is not None else (rel, "objects." + str(key), "no row %s" % key, "a row of this ledger"),
           None if row is None or row.get("status") != "removed" else (
               rel, "objects.%s.status" % key, "a removed row is final", "a row that is not removed"),
           None if (args.what or "").strip() else ("(flags)", "--what", "nothing said of what failed", "what failed"),
           None if (args.error_code or "").strip() else ("(flags)", "--error-code", "an empty error code",
                                                         "the code read out of the error's message, or UNPROBED"),
           None if len(attempts) <= 2 else ("(flags)", "--attempt", "%d call forms" % len(attempts),
                                            "the first call form and at most one different one"),
           None if all(a in CALL_FORMS for a in attempts) else ("(flags)", "--attempt", "%r" % attempts,
                                                                " | ".join(CALL_FORMS)),
           None if args.decision in DECISIONS else ("(flags)", "--decision", "%r" % args.decision, " | ".join(DECISIONS)),
           None if not ui or ((args.ui_what or "").strip() and (args.ui_owner or "").strip()) else (
               "(flags)", "--ui-what", "a UI step decision without its step and owner", "--ui-what and --ui-owner"),
           *recovery_reasons(led, args.run_id),
           *(retry_reasons(led, key, row, "depart") if row is not None and row.get("status") == "attempting" else []))
    fence(root, args)
    led.reload()
    b = led.build
    decision = args.decision
    if ui:
        step = next_ui_key(led)
        b.setdefault("ui_steps", []).append({"key": step, "what": args.ui_what.strip(), "owner": args.ui_owner.strip(),
                                             "target_version": led.version, "status": "open"})
        decision = "ui-step %s" % step
    b.setdefault("departures", []).append({"key": key, "version": led.version, "what": args.what.strip(),
                                           "error_code": args.error_code.strip(), "attempts": attempts,
                                           "decision": decision})
    row = led.objects[key] = ordered_row(led.objects[key])
    row["status"] = "departed"
    beat(led, args.run_id)
    written = save_build(led, "depart", args.run_id)
    return 0, {"key": key, "status": "departed", "decision": decision, "written": written,
               "log": [entry_log(led.short, "departure", led.version, key, [
                   "%s · error %s · decision %s" % (args.what.strip(), args.error_code.strip(), decision)])]}


def cmd_ui_step(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    led.require_build()
    refuse(sha_reason(led, args.expect_sha))
    steps = led.build.setdefault("ui_steps", [])
    rel = led.build_rel
    if args.done:
        found = [s for s in steps if s.get("key") == args.key]
        refuse(None if found else (rel, "ui_steps", "no UI step %s" % args.key, "the key of a recorded UI step"))
        found[-1]["status"] = "done"
        step = found[-1]
    else:
        key = args.key or next_ui_key(led)
        refuse(None if key_fits(key, "ui_step") else ("(flags)", "--key", "%r is not a UI step key" % key, "U<n>"),
               None if key not in {s.get("key") for s in steps} else (rel, "ui_steps", "%s is taken" % key, "a free U<n>"),
               None if (args.what or "").strip() else ("(flags)", "--what", "no step said", "the step in plain words"),
               None if (args.owner or "").strip() else ("(flags)", "--owner", "no owner", "the user, or a role"),
               None if re.fullmatch(r"v\d+\.\d+", str(args.target_version)) else (
                   "(flags)", "--target-version", "%r" % args.target_version, "vX.Y"))
        step = {"key": key, "what": args.what.strip(), "owner": args.owner.strip(), "target_version": args.target_version,
                "status": "open"}
        steps.append(step)
    written = save_build(led, "ui-step")
    return 0, {"ui_step": step, "written": written}


def cmd_irreversible_yes(root, args):
    led = fenced(root, args, account=True)
    rel = led.build_rel
    keys = list(args.key or [])
    op = args.operation or "create"
    archive = op == "archive" or bool(re.search(r"\barchiv", args.what or "", re.I))
    reasons = [None if args.mode in ("per-item", "grouped") else ("(flags)", "--mode", "%r" % args.mode,
                                                                  "per-item | grouped"),
               None if op in OPERATIONS and op != "delete" else ("(flags)", "--operation", "%r" % op, "the operation "
                                                                 "the yes is for: " + " | ".join(OPERATIONS[:-1])),
               None if (args.what or "").strip() else ("(flags)", "--what", "no step said", "the step in plain words"),
               None if not archive or (args.evidence or "").strip() else (
                   "(flags)", "--evidence", "an archive's yes with no containment evidence", "the evidence it shows")]
    entries = []
    for key in keys:
        row = led.objects.get(key)
        ref = args.approval_ref or (row or {}).get("approval_ref")
        entry = led.approval(ref)
        if row is None:
            reasons.append((rel, "objects." + key, "no row %s" % key, "a row of this ledger"))
            continue
        if entry is None:
            reasons.append((rel, "objects.%s.approval_ref" % key, "%r resolves to no approval" % ref, "an approval entry"))
            continue
        listed = (key in (entry.get("irreversible_listed") or []) if args.mode == "per-item" else
                  any(key in (entry.get(f) or []) for _, f in LISTS))
        if not listed:
            reasons.append((rel, "approvals", "%s is not listed in %s for a %s yes" % (key, ref, args.mode),
                            "a key of irreversible_listed (per-item) or of a list (grouped)"))
        entries.append({"key": key, "what": (args.what or "").strip(), "at": None, "mode": args.mode,
                        "approval_ref": ref, "evidence": (args.evidence or "").strip() or None,
                        "log_ref": (args.log_ref or "").strip() or None, "run_id": args.run_id, "operation": op,
                        "used_by": None})  # R2, R15: this run's, this operation's, used once by the intent it covers
    refuse(*reasons)
    fence(root, args)
    led.reload()
    now = mc.stamp("utc")
    for item in entries:
        item["at"] = now
        led.build.setdefault("irreversible_yes", []).append(item)
    beat(led, args.run_id)
    written = save_build(led, "irreversible-yes", args.run_id)
    return 0, {"entries": entries, "written": written,
               "log": [entry_log(led.short, "irreversible", led.version, item["key"], ["yes (%s): %s" % (
                   item["mode"], item["what"])] + (["evidence: %s" % item["evidence"]] if item["evidence"] else []))
                   for item in entries]}


# monday's catalogue constants (W87): copied from shared/native-objects.md sections 2.4, 2.6, 3.1 to 3.3, 4.1 to 4.4,
# 5 and 7.2, never read from it at run time. test_ledger_read.py parses those sections and asserts these tables equal
# them (the drift test). Template ids and template view ids are monday-owned constants, the same in every account.

def _ids(text):
    return tuple(text.split())


CRM_TEMPLATES = {}  # template id: (family, version, entity as NO 3.1 names it)
for _family, _version, _pairs in (
        ("sales_crm", "v2", "5678953932 leads 5678953956 opportunities_or_deals 5678953938 contacts 5678953942 accounts "
                            "5678953951 activities 5678953895 sales_targets"),
        ("sales_crm", "v2", " ".join("%s companion" % i for i in _ids(
            "5678953861 5678953867 5678953868 5678953871 5678953875 5678953876 5678953878 5678953894 5678953934 "
            "5678953967 8975252031"))),
        ("sales_crm", "v2", " ".join("%s subitems" % i for i in _ids("5678954845 5678955164 8975252077 9396380271"))),
        ("crm_core", "v1", "2658101980 leads 2658101923 contacts 2658101956 accounts 2658101899 opportunities_or_deals "
                           "2658101993 activities 8179060947 quotes_invoices 2658102037 deals_subitems "
                           "18393462843 qi_line_items 10027024945 subitems 6131463946 project_companion "
                           "6131463958 project_companion_subitems 8615325260 companion"),
        (None, "unknown", "5092627193 contacts 5092627194 accounts 5092627197 opportunities_or_deals 5092627202 subitems "
                          "5092627206 subitems 9031562048 leads 9031562049 activities 9031562051 contacts 9031562062 project "
                          "9031562066 accounts 9031562081 opportunities_or_deals 9031562339 subitems 9031562445 subitems")):
    _words = _pairs.split()
    for _n in range(0, len(_words), 2):
        CRM_TEMPLATES[_words[_n]] = (_family, _version, _words[_n + 1])
SERVICE_TEMPLATES = {}  # template id: (family, entity as NO 4.1 names it); family E is unread (P-17) but named in NO 4
for _family, _pairs in (
        ("A", "7819831530 tickets 7819831540 tickets_subitems"),
        ("B", "5727048235 tickets 5727048230 contacts 5727048234 csat_survey 5727048483 tickets_subitems "
              "5765211778 start_here_doc"),
        ("C", "5561655961 tickets 5561655956 incidents 5561655946 csat_survey 5561655954 employee_lifecycle "
              "5561656011 employee_directory 5561656015 asset_management 5561656760 tickets_subitems "
              "5561656359 lifecycle_subitems 5750119042 start_here_doc"),
        ("D", "6410079972 tickets 6410079951 incidents 6410080630 subitems 6573685095 start_here_doc"),
        ("E", "7830923787 tickets 7830923821 subitems"),
        ("Portal", "9449773054 portal_custom_object")):
    _words = _pairs.split()
    for _n in range(0, len(_words), 2):
        SERVICE_TEMPLATES[_words[_n]] = (_family, _words[_n + 1])
ROLE_TEMPLATES = {"5882692393": "portfolio", "9857787491": "tasks", "6667825632": "overview", "9958257937": "planner",
                  "105719650": "workflow_object"}  # NO 7.2: roles, never a native entity; the last never decisive alone
CRM_VIEWS = {}  # template view id: (family, version, entity)
for _family, _version, _entity, _views in (
        ("sales_crm", "v2", "leads", "124433515 124433523 124433528"),
        ("sales_crm", "v2", "opportunities_or_deals", "124433522 124433524 124433536"),
        ("sales_crm", "v2", "contacts", "124433508 124433513"), ("sales_crm", "v2", "accounts", "124433511 124433514"),
        ("sales_crm", "v2", "activities", "124433520"),
        ("sales_crm", "v2", "sales_targets", "124433519 124433531 124433534 124433549"),
        ("crm_core", "v1", "quotes_invoices", "174990912 174990913"),
        ("crm_core", "v1", "opportunities_or_deals", "60638373 169248366"), ("crm_core", "v1", "leads", "121301932"),
        ("crm_core", "v1", "accounts", "124032534")):
    for _view in _ids(_views):
        CRM_VIEWS[_view] = (_family, _version, _entity)
SERVICE_VIEWS = {}  # template view id: (family, entity)
for _family, _entity, _views in (
        ("A", "tickets", "176205535"), ("B", "tickets", "125328754 125328758"), ("B", "csat_survey", "125328753"),
        ("C", "tickets", "122226426 122606170"), ("C", "csat_survey", "122226423"),
        ("C", "employee_lifecycle", "122226427"), ("D", "tickets", "139565036 176205700"),
        (None, "start_here_doc", "126013264"), ("Portal", "portal_custom_object", "200776197")):
    for _view in _ids(_views):
        SERVICE_VIEWS[_view] = (_family, _entity)
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
SIGNATURES = {  # (product, entity): (threshold or None for lineage only or none, reserved ids), NO 3.3 and 4.3
    ("crm", "leads"): (3, _ids("lead_status lead_email lead_company lead_phone lead_owner")),
    ("crm", "opportunities_or_deals"): (3, _ids(
        "deal_stage deal_owner deal_value deal_contact deal_account deal_forecast_value deal_expected_close_date "
        "deal_close_probability deal_close_date deal_creation_date deal_length deal_actual_value")
        + tuple("deal_%s_actual" % m for m in _MONTHS[:7]) + ("jul___actual",)
        + tuple("deal_%s_actual" % m for m in _MONTHS[8:])),
    ("crm", "contacts"): (3, _ids("contact_email contact_phone contact_company contact_account contact_deal")),
    ("crm", "accounts"): (3, _ids("account_contact account_deal company_domain company_description company_profile "
                                  "employee_count headquarters_loc industry")),
    ("crm", "activities"): (3, _ids("activity_item activity_owner activity_type activity_start_time activity_end_time "
                                    "activity_status")),
    ("crm", "products_services"): (2, _ids("product_and_service_description product_and_service_price "
                                           "product_and_service_sku product_and_service_type")),
    ("crm", "quotes_invoices"): (3, _ids("bill_to amount issue_date type file creation_log__1")),
    ("crm", "qi_line_items"): (6, tuple("line_item_%s" % s for s in _ids(
        "description unit_price quantity total_multipliers base_price adjustment_rate adjustment_value fees_rate "
        "fees_value tax_rate tax_value final_price currency product deal contact id"))),
    ("crm", "sales_targets"): (3, ("link_to___opportunities",) + tuple("%s___target" % m for m in _MONTHS[:11])
                               + _ids("q1_target q2_target q2_actual q4_target target_to_date target_to_date8")),
    ("crm", "deals_subitems"): (None, ()),
    ("service", "tickets"): (6, _ids(
        "status95 people0 long_text7 priority request_type date6 email date subitems text files collaborators item_id_1 "
        "time_tracking3 time_tracking formula9 formula13 formula17 status_163 date2 date20 board_relation6 "
        "connect_boards2 board_relation21")),
    ("service", "tickets_subitems"): (4, _ids("agent__1 status__1 priority__1 request_type__1 creation_date__1 email9__1 "
                                              "description__1 requestor_name__1")),
    ("service", "asset_management"): (5, _ids(
        "serial_number recovery_key mac_address ip_address computer_name operating_system jamf_intune_agent "
        "released_from_abm asset_tag disabled_pre_stage valid_data last_check_in dup_last_check_in more_details building "
        "duplicate")),
    ("service", "employee_lifecycle"): (4, _ids("subitems_status email1 email9 email95 color2 status_1")),
    ("service", "employee_directory"): (2, _ids("site___itsm connect_boards5")),
    ("service", "incidents"): (None, _ids("person board_relation status color date4 monday_doc")),
    ("service", "csat_survey"): (None, _ids("rating long_text date")),
    ("service", "service_contacts"): (None, _ids("status color__1 color2__1 email phone connect_boards5"))}
QI_CORROBORATION = ("8179060947", ("174990912", "174990913"), "Document #")  # NO 3.3: lineage, view or terminology
EXTENDED_TICKET_IDS = _ids("item_id_1 time_tracking3 formula9 status_163")  # NO 4.3, W84: families B and C only
BLANK_DEFAULTS = _ids("person status date4 date0")
SUFFIXED = re.compile(r"^[a-z_0-9]+_(mk|mm)[a-z0-9]{6,8}$")
SLA_HELPER = re.compile(r"^formula_[a-z0-9]{6,8}_(lst|ewh|tl|itr|ts|ttp)$")
STATIC_IMAGES = _ids("leads contacts accounts opportunities activities")
FEATURE_PREFIXES = ("custom_", "enrolled_sequences_")
V2_OPPS_IDS = ("2673708477", "1631647074")
PORTAL_LINEAGE, PORTAL_VIEW, WORKFLOW_LINEAGE = "9449773054", "200776197", "105719650"
PORTAL_KEY, WORKFLOW_KEY = "service::portal-object", "monday_workflows::workflow"
KEY_PORTFOLIO, KEY_STANDALONE = "work-management::portfolio", "work-management::standalone"
KEYS_PROJECT = ("work-management::portfolio-project", "work-management::project")
TASKS_TEMPLATE = "9857787491"
PROJECT_IDS = _ids("project_status project_timeline project_owner project_priority")
RP_IDS = _ids("rp_placeholder rp_placeholder_index rp_assignee rp_assignee_mirror rp_timeline rp_effort_per_day "
              "rp_total_effort rp_selected_effort rp_connected_project")
R5_MIN, R8_MIN, R9_MIN, LINEAGE_CAP = 2, 5, 5, 5
DEFAULT_NAMES = ("Leads", "Contacts", "Accounts", "Opportunities", "Deals", "Activities", "Sales Activities",
                 "Sales Targets", "Products & Services", "Quotes & Invoices", "Tickets", "Incidents", "CSAT Survey",
                 "Asset management", "Employee directory", "Employee lifecycle", "Portal", "Subitems of Tickets",
                 "Start here")
DEFAULT_TERMINOLOGY = ("Lead", "Deal", "Opportunity", "Contact", "Account", "Activity", "Activity ", "Document #",
                       "Sales Rep", "Ticket", "Incident", "Ticket ID", "Contact name", "Employee name", "employee",
                       "Serial Number")
DETECT_QUERY = """query DetectNativeBoards($ids: [ID!], $ws: [ID!]) {
  version { kind value }
  complexity { after }
  portal_active: objects(object_type_unique_keys: ["service::portal-object"], workspace_ids: $ws, state: ACTIVE, limit: 500) { id state }
  portal_archived: objects(object_type_unique_keys: ["service::portal-object"], workspace_ids: $ws, state: ARCHIVED, limit: 500) { id state }
  boards(ids: $ids, state: all, limit: 50) {
    id name type state hierarchy_type object_type_unique_key board_kind
    item_terminology created_from_board_id items_count workspace_id board_folder_id
    inferred_metadata { item_type }
    manual_metadata { board_md }
    workspace { id account_product { kind } }
    columns { id type }
    links: columns(types: [board_relation, subtasks, mirror]) { id type settings }
    views { id type name source_view_id }
  }
}"""
SIDE_READS = {  # W01, W79, W80, W89: the reads the session makes beside the one detection query
    "workspaces": "query ($ids: [ID!]) { workspaces(ids: $ids) { id name kind account_product { id kind } } }",
    "account_products": "query { account { products { id kind default_workspace_id } } }",
    "docs": "query ($ws: [ID!]) { docs(workspace_ids: $ws) { id object_id name workspace_id } }",
    "workflow_objects": "query ($ws: [ID!]) { objects(object_type_unique_keys: [\"%s\"], workspace_ids: $ws, state: "
                        "ACTIVE|ARCHIVED, limit: 500) { id state } }" % WORKFLOW_KEY,
    "portfolio_items": "query ($ids: [ID!]) { boards(ids: $ids) { items_page(limit: 100) { cursor items { id "
                       "column_values(ids: [\"portfolio_project_link\"]) { ... on BoardRelationValue { linked_item_ids "
                       "linked_items { id board { id } } } } } } } }"}
PAGE_KINDS = ("boards_sweep", "boards_ids") + tuple(SIDE_READS)
PAGE_SIZE = (25, 50)  # NO 2.6, G-92: never 200

# How the classifier names an entity (W16): NO's own name where it is the entity, these where NO names a template.
ENTITY_ALIAS = {("crm", "project_companion"): "companion", ("crm", "project"): "companion",
                ("crm", "project_companion_subitems"): "subitems", ("service", "contacts"): "service_contacts",
                ("service", "portal_custom_object"): "portal", ("service", "subitems"): "tickets_subitems"}
SUBITEM_PARENT = {"qi_line_items": "quotes_invoices", "deals_subitems": "opportunities_or_deals",
                  "tickets_subitems": "tickets", "lifecycle_subitems": "employee_lifecycle", "subitems": None}
MAP_ENTITY = {"quotes_invoices_subitems": "qi_line_items", "opportunities_or_deals_subitems": "deals_subitems",
              "employee_lifecycle_subitems": "lifecycle_subitems"}  # the W16 name of an N5 board's map entry
LIMIT_REASONS = {"L1": "planted reserved ids read the same as a chain-broken native",
                 "L2": "a native stripped of its template columns with a broken chain reads as this",
                 "L3": "a default-shaped satellite that lost its lineage"}
LIMIT_ORDER = ("L3", "L1", "L2")  # the most specific code first (W01 as the trace check amended it)
CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}
REVIEW_RULES = ("R7", "R9", "N7", "N10")
NOT_INSTALLED = "product boards not installed here"


def _template(tid):
    """(product, family, version, entity, raw entity) of a template id in a native catalogue, else None."""
    if tid in CRM_TEMPLATES:
        family, version, raw = CRM_TEMPLATES[tid]
        return "crm", family, version, ENTITY_ALIAS.get(("crm", raw), raw), raw
    if tid in SERVICE_TEMPLATES:
        family, raw = SERVICE_TEMPLATES[tid]
        return "service", family, None, ENTITY_ALIAS.get(("service", raw), raw), raw
    return None


NOT_INSTALLED_ALONE = ("companion", "project", "project_companion", "start_here_doc", "portal_custom_object")


def installable(tid):
    """(product, entity as NO 3.1 or 4.1 names it, entity as native_board_index names it) of a template id a native
    install may name (A38): a board of its own entity, never a companion, a subitems board, the Start here doc, the
    Portal or family E, which NO 4.1 does not list; None for every other id."""
    found = _template(str(tid))
    if found is None:
        return None
    product, family, _, entity, raw = found
    if family == "E" or raw in NOT_INSTALLED_ALONE or raw in SUBITEM_PARENT or raw.endswith("_subitems"):
        return None
    return product, raw, entity


def _view(vid):
    """(product, family, version, entity) of a template view id, else None."""
    if vid in CRM_VIEWS:
        family, version, raw = CRM_VIEWS[vid]
        return "crm", family, version, raw
    if vid in SERVICE_VIEWS:
        family, raw = SERVICE_VIEWS[vid]
        return "service", family, None, ENTITY_ALIAS.get(("service", raw), raw)
    return None


ALL_TEMPLATES = set(CRM_TEMPLATES) | set(SERVICE_TEMPLATES) | set(ROLE_TEMPLATES)
DEFAULT_IDS = set(("name",) + BLANK_DEFAULTS) | {i for (product, _), (t, ids) in SIGNATURES.items() if t is None for i in ids}
RESERVED_IDS = {i for (_, _), (t, ids) in SIGNATURES.items() if t is not None for i in ids}
CRM_RESERVED = {i for (product, _), (t, ids) in SIGNATURES.items() if product == "crm" for i in ids}


# classify (W78 to W86): both rule sets over the reads the session hands, in W81's order.

def natural(key):
    """A sort key that puts B2 before B10."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(key))]


def id_sort(value):
    return (len(str(value)), str(value))


class Reads:
    """The pages of a reads file (W01), the board set they return, and the side reads, diffed page by page (G-92)."""

    def __init__(self, data, name, account):
        self.name, self.notes = name, []
        pages = data.get("pages")
        refuse(None if isinstance(pages, list) and pages else (name, "pages", "no pages", "a list of response pages (W01)"))
        reasons, self.rings = [], set()
        self.boards, self.missing, self.sweeps, self.docs = {}, [], {}, {}
        self.portal = {"active": set(), "archived": set()}
        self.workflow_sets, self.workspace_kinds, self.products, self.items = None, {}, None, {}
        self.workspaces_read = []
        for n, page in enumerate(pages):
            where = "pages[%d]" % n
            if not isinstance(page, dict) or page.get("kind") not in PAGE_KINDS:
                reasons.append((name, where + ".kind", "%r is not a page kind" % (page or {}).get("kind")
                                if isinstance(page, dict) else "not an object", " | ".join(PAGE_KINDS)))
                continue
            response = ((page.get("response") or {}).get("data")) if isinstance(page.get("response"), dict) else None
            lists = [page.get(k) for k in ("requested_ids", "returned_ids", "missing_ids")]
            if not isinstance(response, dict) or not all(isinstance(v, list) for v in lists):
                reasons.append((name, where, "no response data or no id lists", "response.data and requested_ids, "
                                "returned_ids and missing_ids on every page (G-92)"))
                continue
            version = response.get("version")
            if isinstance(version, dict) and version.get("kind") and version.get("value"):
                self.rings.add("%s %s" % (version["kind"], version["value"]))
            reasons += self.page(page, response, name, where)
        if len(self.rings) > 1:
            reasons.append((name, "pages[].response.data.version", "the pages carry more than one ring: %s" % ", ".join(
                sorted(self.rings)), "one ring on every page; read again in one session"))
        refuse(*reasons)
        known = (account.get("guard_index") or {}).get("unreadable_intermediate_ids") or []
        self.unreadable = set(self.missing) | {str(i) for i in known}

    def page(self, page, data, name, where):
        kind, variables = page["kind"], (page.get("request") or {}).get("variables") or {}
        for state, alias in (("active", "portal_active"), ("archived", "portal_archived")):
            for obj in data.get(alias) or []:
                self.portal[state].add(str(obj.get("id")))
        if kind in ("boards_sweep", "boards_ids"):
            boards = data.get("boards")
            if not isinstance(boards, list):
                return [(name, where + ".response.data.boards", "not a list", "the boards the query returned")]
            returned = [str(b.get("id")) for b in boards if isinstance(b, dict)]
            for board in boards:
                if isinstance(board, dict) and str(board.get("id")) not in self.boards:
                    self.boards[str(board.get("id"))] = board
            if kind == "boards_ids":
                requested = [str(i) for i in (page.get("requested_ids") or variables.get("ids") or [])]
                missing = [i for i in requested if i not in returned]  # G-92: the diff is made here, on every page
                if sorted(missing) != sorted(str(i) for i in page.get("missing_ids") or []):
                    self.notes.append("%s: the page's missing_ids differ from requested minus returned; the diff is used"
                                      % where)
                self.missing += [i for i in missing if i not in self.missing]
            else:
                p = variables.get("p") if isinstance(variables.get("p"), int) else 1
                for ws in variables.get("ws") or []:
                    self.sweeps.setdefault(str(ws), []).append((p, not boards))
        elif kind == "workspaces":
            for ws in data.get("workspaces") or []:
                self.workspaces_read.append(ws)
                kind_of = ((ws or {}).get("account_product") or {}).get("kind")
                if kind_of:
                    self.workspace_kinds[str(ws.get("id"))] = kind_of
        elif kind == "account_products":
            self.products = [{"id": str(p.get("id")), "kind": p.get("kind"),
                              "default_workspace_id": None if p.get("default_workspace_id") is None else
                              str(p.get("default_workspace_id"))}
                             for p in (data.get("account") or {}).get("products") or [] if isinstance(p, dict)]
        elif kind == "docs":
            for doc in data.get("docs") or []:
                self.docs[str(doc.get("object_id"))] = str(doc.get("id"))
        elif kind == "workflow_objects":
            self.workflow_sets = (self.workflow_sets or set()) | {str(o.get("id")) for o in data.get("objects") or []}
        elif kind == "portfolio_items":
            ids = [str(i) for i in (page.get("returned_ids") or page.get("requested_ids") or variables.get("ids") or [])]
            for pid, board in zip(ids, data.get("boards") or []):
                items_page = (board or {}).get("items_page") or {}
                rows = {str(((linked or {}).get("board") or {}).get("id")) for item in items_page.get("items") or []
                        for value in (item or {}).get("column_values") or [] for linked in (value or {}).get(
                            "linked_items") or []}
                self.items[pid] = {"cursor": items_page.get("cursor"), "rows": rows}
        return []

    @property
    def sweep_complete(self):
        """R0, K313: every swept workspace ended on a page with boards: []."""
        return bool(self.sweeps) and all(max(pages)[1] for pages in self.sweeps.values())

    def unfinished(self):
        return sorted(ws for ws, pages in self.sweeps.items() if not max(pages)[1])


def walk(board, boards, unreadable):
    """NO 2.1, W86: the lineage walked hop by hop. Returns (lineage, pending id or None)."""
    chain, seen, cur = [], {str(board.get("id"))}, board.get("created_from_board_id")
    while True:
        if cur in (None, ""):
            return {"chain": chain, "resolved": False, "result": "NO_LINEAGE", "hops": len(chain), "note": None}, None
        cur = str(cur)
        if cur in seen:
            chain.append(cur)
            return {"chain": chain, "resolved": False, "result": "UNRESOLVED", "hops": len(chain) - 1,
                    "note": "cycle"}, None
        chain.append(cur)
        if cur in ALL_TEMPLATES:
            return {"chain": chain, "resolved": True, "result": "RESOLVED_TEMPLATE", "hops": len(chain) - 1,
                    "note": None}, None
        if cur in unreadable:
            return {"chain": chain, "resolved": False, "result": "UNRESOLVED", "hops": len(chain) - 1, "note": None}, None
        if cur not in boards:
            return {"chain": chain, "resolved": False, "result": None, "hops": len(chain) - 1,
                    "note": "waiting on the read of %s" % cur}, cur
        if len(chain) > LINEAGE_CAP:
            return {"chain": chain, "resolved": False, "result": "UNRESOLVED", "hops": len(chain) - 1,
                    "note": "longer than %d hops" % LINEAGE_CAP}, None
        seen.add(cur)
        cur = boards[cur].get("created_from_board_id")


class Facts:
    """What the rules read on one board: column ids, marks, signatures, lineage and views (NO 2.1 to 2.5)."""

    def __init__(self, board, reads, account):
        self.board, self.id = board, str(board.get("id"))
        self.type, self.key = board.get("type") or "board", board.get("object_type_unique_key")
        self.state, self.name, self.term = board.get("state"), board.get("name"), board.get("item_terminology")
        ws = board.get("workspace") or {}
        self.workspace = str(board.get("workspace_id") or ws.get("id") or "")
        self.product = ((ws.get("account_product") or {}).get("kind") or reads.workspace_kinds.get(self.workspace)
                        or "none")
        self.columns = [c for c in board.get("columns") or [] if isinstance(c, dict)]
        self.links = [c for c in board.get("links") or [] if isinstance(c, dict)]
        self.col_ids = [str(c.get("id")) for c in self.columns]
        self.types = {str(c.get("id")): c.get("type") for c in self.columns}
        plain = [i for i in self.col_ids if not SUFFIXED.match(i) and i not in BLANK_DEFAULTS]
        self.plain = plain
        self.lineage, self.pending = walk(board, reads.boards, reads.unreadable)
        terminal = self.lineage["chain"][-1] if self.lineage["resolved"] else None
        self.terminal = terminal
        self.template = _template(terminal) if terminal else None
        self.views = sorted({str(v.get("source_view_id")) for v in board.get("views") or []
                             if isinstance(v, dict) and _view(str(v.get("source_view_id")))}, key=id_sort)
        self.counts = {pe: sum(1 for i in plain if i in ids) for pe, (t, ids) in SIGNATURES.items() if t is not None}
        self.reserved_count = sum(1 for i in plain if i in RESERVED_IDS)
        self.marks = self.find_marks()
        corroborated = (terminal == QI_CORROBORATION[0] or any(v in QI_CORROBORATION[1] for v in self.views)
                        or self.term == QI_CORROBORATION[2])
        self.met = [pe for pe, (t, ids) in SIGNATURES.items() if t is not None and self.counts[pe] >= t
                    and (pe != ("crm", "quotes_invoices") or corroborated)]

    def find_marks(self):
        marks = []
        relations = [c for c in self.links if c.get("type") == "board_relation"]
        mirrors = [c for c in self.links if c.get("type") == "mirror"]
        if any((c.get("settings") or {}).get("staticImage") in STATIC_IMAGES for c in relations):
            marks.append("CRM_RELATION_MARK")
        if any(c.get("type") == "unsupported" and str(c.get("id")).startswith(FEATURE_PREFIXES) for c in self.columns):
            marks.append("CRM_FEATURE_MARK")
        if any(set(map(str, d.get("column_ids") or [])) & CRM_RESERVED for c in mirrors
               for d in (c.get("settings") or {}).get("displayed_linked_columns") or [] if isinstance(d, dict)):
            marks.append("CRM_MIRROR_MARK")
        if any(str(c.get("id")) == "deal_account" and set(map(str, (c.get("settings") or {}).get("boardIds") or []))
               & set(V2_OPPS_IDS) for c in mirrors):
            marks.append("V2_OPPS_FINGERPRINT")
        stems = {}
        for cid in self.col_ids:
            match = SLA_HELPER.match(cid)
            if match:
                stem = cid[:-len(match.group(1)) - 1]
                stem = stem[:-1] if match.group(1) in ("tl", "ts") else stem
                stems[stem] = stems.get(stem, 0) + 1
        if any(n >= 4 for n in stems.values()):
            marks.append("SERVICE_SLA_MARK")
        return marks

    def prefix_count(self, prefix):
        return sum(1 for i in self.col_ids if i.startswith(prefix) and not SUFFIXED.match(i))

    def signals(self, reads):
        out = ["type:%s" % self.type] if self.type != "board" else []
        out += ["key:%s" % self.key] if self.key else []
        out.append("N0:%s" % self.product)
        out += ["lineage:%s" % self.terminal] if self.terminal else []
        out += ["view:%s" % v for v in self.views]
        out += ["reserved:%s/%s" % pe for pe in self.met]
        out += self.marks
        if self.type == "custom_object":
            for state in ("active", "archived"):
                if self.id in reads.portal[state]:
                    out.append("portal_objects:%s" % state)
            out.append("workflow_objects:unread" if reads.workflow_sets is None else
                       "workflow_objects:in" if self.id in reads.workflow_sets else "workflow_objects:out")
        if self.type == "document" and self.id in reads.docs:
            out.append("doc:%s" % reads.docs[self.id])
        for prefix, label in (("rp_", "rp_ids"), ("project_", "project_ids"), ("portfolio_project_", "portfolio_project_ids")):
            count = self.prefix_count(prefix)
            if count:
                out.append("%s:%d" % (label, count))
        if self.board.get("hierarchy_type") == "multi_level":
            out.append("hierarchy:multi_level")
        return out

    def imitation(self):
        return (["imitation:name"] if self.name in DEFAULT_NAMES else []) + (
            ["imitation:terminology"] if self.term in DEFAULT_TERMINOLOGY else [])

    def default_shaped(self):
        """L3: every column id a monday default, and some column read."""
        return bool(self.col_ids) and all(i in DEFAULT_IDS for i in self.col_ids)


def _install(lineage, view=False):
    if lineage["resolved"]:
        return "direct_install" if lineage["hops"] == 0 else "descendant_copy(%d)" % lineage["hops"]
    if view:
        return "direct_install"
    return "lineage_unresolved" if lineage["result"] == "UNRESOLVED" else None


def _crm_version(facts):
    """W84: the CRM generation from the types first, then the lineage's catalogue row."""
    types = facts.types
    v2 = types.get("deal_close_probability") == "formula" or types.get("account_deal") == "board_relation" or \
        "V2_OPPS_FINGERPRINT" in facts.marks
    v1 = types.get("deal_close_probability") == "numbers" or types.get("account_deal") == "mirror"
    if v2 and not v1:
        return "sales_crm", "v2"
    if v1 and not v2:
        return "crm_core", "v1"
    if facts.template and facts.template[0] == "crm":
        return facts.template[1], facts.template[2]
    return None, "unknown"


def _service_family(facts, entity):
    if facts.template and facts.template[0] == "service":
        return facts.template[1]
    for view in facts.views:
        info = _view(view)
        if info and info[0] == "service" and info[1]:
            return info[1]
    if entity == "tickets":
        return "B or C" if any(i in facts.col_ids for i in EXTENDED_TICKET_IDS) else "A or D"
    return None


def _attributes(facts, product=None, entity=None, install=None, native=False):
    attrs = {"family": None, "version": None, "install_kind": None, "sla_mark": None, "state": facts.state,
             "items_count": facts.board.get("items_count")}
    if native:
        if product == "crm":
            attrs["family"], attrs["version"] = _crm_version(facts)
        elif product == "service":
            attrs["family"] = _service_family(facts, entity)
        attrs["install_kind"], attrs["sla_mark"] = install, "SERVICE_SLA_MARK" in facts.marks
    return attrs


def _fingerprint(facts):
    """N2, N3, N4 in that order: (rule, product, entity, install kind, tie) of the first that names a native entity."""
    tpl = facts.template
    if tpl and tpl[3] not in ("start_here_doc",):
        return "N2", tpl[0], tpl[3], _install(facts.lineage), False
    for view in facts.views:
        info = _view(view)
        if info and info[3] not in ("start_here_doc",):
            return "N3", info[0], info[3], "direct_install", False
    if facts.met:
        ranked = sorted(facts.met, key=lambda pe: (-facts.counts[pe], pe[0] != facts.product,
                                                   list(SIGNATURES).index(pe)))  # W84
        best = ranked[0]
        tie = len(ranked) > 1
        return "N4", best[0], best[1], "descendant_fingerprint", tie
    return None


def native_class(product, entity, parent=None):
    if entity == "companion":
        return "native_crm_companion_board"
    if entity in SUBITEM_PARENT:
        return "native_%s_%s_subitems" % (product, parent or SUBITEM_PARENT[entity] or "unknown")
    return "native_%s_%s" % (product, entity)


def _result(cls, rule, confidence, facts, attrs, signals, review=None, limits=()):
    return {"class": cls, "rule": rule, "attributes": attrs, "confidence": confidence, "signals": signals,
            "lineage": dict(facts.lineage), "review": rule in REVIEW_RULES if review is None else review,
            "limits": list(limits)}


def classify_board(facts, reads, ctx):
    """One board through R1 to R11 and N0 to N11 in W81's order; ctx carries the first pass's classes."""
    signals, attrs = facts.signals(reads), _attributes(facts)
    if facts.pending is not None:
        return dict(_result("pending", None, None, facts, attrs, signals, review=False), pending=facts.pending)
    if facts.type == "document":  # R1; a native lineage is an attribute (NO 4.1:104)
        if facts.template and facts.template[0] in ("crm", "service"):
            attrs = _attributes(facts, facts.template[0], facts.template[3], _install(facts.lineage), native=True)
        return _result("doc_container", "R1", "high", facts, attrs, signals)
    if facts.type == "sub_items_board":  # R2 with N5 inside it
        parents = ctx["parents"].get(facts.id, [])
        signals += ["parent:%s" % p for p in parents]
        sub = facts.template if facts.template and facts.template[3] in SUBITEM_PARENT else None
        met = [pe for pe in facts.met if pe in (("crm", "qi_line_items"), ("service", "tickets_subitems"))]
        if sub or met:
            product = sub[0] if sub else met[0][0]
            parent = next((ctx["entity"][p] for p in parents if ctx["entity"].get(p)), None)
            if parent is None and sub:
                parent = SUBITEM_PARENT[sub[3]]
            if parent is None and met:
                parent = SUBITEM_PARENT[met[0][1]]
            high = facts.lineage["resolved"] or any(pe[0] == facts.product for pe in met)
            attrs = _attributes(facts, product, "subitems", _install(facts.lineage), native=True)
            return _result(native_class(product, "subitems", parent), "N5", "high" if high else "medium", facts,
                           attrs, signals)
        return _result("subitems_board", "R2", "high", facts, attrs, signals)
    if facts.type == "custom_object":  # R3 with N1 inside it
        if any(facts.id in reads.portal[s] for s in ("active", "archived")):
            attrs = _attributes(facts, "service", "portal", _install(facts.lineage, PORTAL_VIEW in facts.views), True)
            attrs["family"] = "Portal"
            return _result("native_service_portal", "N1a", "high", facts, attrs, signals)
        if facts.terminal == PORTAL_LINEAGE or PORTAL_VIEW in facts.views:
            attrs = _attributes(facts, "service", "portal", _install(facts.lineage, PORTAL_VIEW in facts.views), True)
            attrs["family"] = "Portal"
            return _result("native_service_portal", "N1b", "high", facts, attrs, signals)
        if reads.workflow_sets is None:
            return _result("custom_object_other", "R3", "low", facts, attrs, signals)
        cls = "workflow_object" if facts.id in reads.workflow_sets else "custom_object_other"
        return _result(cls, "R3", "high", facts, attrs, signals)
    if facts.key:  # R4 to R7, before any N rule
        if facts.key == KEY_PORTFOLIO:
            return _result("portfolio_board", "R4", "high", facts, attrs, signals)
        if facts.key in KEYS_PROJECT:
            ids = sum(1 for i in PROJECT_IDS if i in facts.col_ids)
            if ids >= R5_MIN or facts.terminal == TASKS_TEMPLATE:
                cls = "project_tasks_board"
            elif not facts.columns:
                cls = "project_board_origin_unknown"
            else:
                cls = "converted_project_board"
            return _result(cls, "R5", "high", facts, attrs, signals)
        if facts.key == KEY_STANDALONE:
            return _result("project_overview_companion", "R6", "high", facts, attrs, signals)
        return _result("keyed_board_unrecognized_key", "R7", "low", facts, attrs, signals)
    found = _fingerprint(facts)  # N0 is the soft gate: both catalogues ran above
    if found:
        rule, product, entity, install, tie = found
        native = _attributes(facts, product, entity, install, native=True)
        if facts.product not in ("crm", "service"):  # N10
            native["fingerprint"] = "%s/%s" % (product, entity)
            return _result("native_descendant_misplaced", "N10", "low", facts, native, signals)
        if rule == "N4":
            high = (product == facts.product or bool(facts.marks)) and not tie
            return _result(native_class(product, entity), rule, "high" if high else "medium", facts, native, signals,
                           limits=["L1"] if install == "descendant_fingerprint" else [])
        parent = next((ctx["entity"][p] for p in ctx["parents"].get(facts.id, []) if ctx["entity"].get(p)), None)
        return _result(native_class(product, entity, parent), rule, "high", facts, native, signals)
    if facts.product == "crm" and ("CRM_RELATION_MARK" in facts.marks or "CRM_MIRROR_MARK" in facts.marks):  # N6
        native = _attributes(facts, "crm", "companion", _install(facts.lineage) if not facts.lineage["resolved"]
                             else None, native=True)
        return _result("native_crm_companion_board", "N6", "medium", facts, native, signals)
    imitation = facts.imitation()
    targets = ctx["targets"].get(facts.id, [])
    if facts.product == "service" and "imitation:terminology" in imitation and targets:  # N7
        native = _attributes(facts, "service", "satellite_probable", _install(facts.lineage) if not
                             facts.lineage["resolved"] else None, native=True)
        native["family"] = None
        return _result("native_service_satellite_probable", "N7", "low", facts, native,
                       signals + ["imitation:terminology"] + ["relation_target:%s" % t for t in targets])
    if facts.product in ("crm", "service"):
        limits = ["L2"] + (["L3"] if facts.product == "service" and facts.default_shaped() and not
                           facts.lineage["resolved"] else [])
        if facts.lineage["result"] in ("NO_LINEAGE", "UNRESOLVED") and facts.reserved_count == 0 and not facts.marks \
                and imitation:  # N8: shape, never intent
            return _result("lookalike_board", "N8", "medium", facts, attrs, signals + imitation, limits=["L2"])
        return _result("ordinary_board_in_product_workspace", "N9", "high", facts, attrs, signals, limits=limits)
    signals.append("N11")  # handed back to R8 to R11
    limits = ["L3"] if facts.product == "service" and facts.default_shaped() and not facts.lineage["resolved"] else []
    if sum(1 for i in RP_IDS if i in facts.col_ids) >= R8_MIN:
        return _result("resource_planner_companion", "R8", "high", facts, attrs, signals, limits=limits)
    if facts.prefix_count("portfolio_project_") >= R9_MIN:
        return _result("portfolio_shaped_board_without_key", "R9", "low", facts, attrs, signals, limits=limits)
    if facts.board.get("hierarchy_type") == "multi_level":
        return _result("multi_level_board_not_project", "R10", "high", facts, attrs, signals, limits=limits)
    return _result("normal_classic_board", "R11", "high", facts, attrs, signals, limits=limits)


def _projects(boards, facts, reads):
    """W80: C1 to C4 for every project board against every portfolio, from both halves."""
    portfolios = sorted((i for i, r in boards.items() if r["class"] == "portfolio_board"), key=id_sort)
    projects = sorted((i for i, r in boards.items() if r["rule"] == "R5"), key=id_sort)
    incomplete = any((reads.items.get(x) or {}).get("cursor") is not None or x not in reads.items for x in portfolios)
    targets = {}
    for x in portfolios:
        links = facts[x].links
        link = next((c for c in links if str(c.get("id")) == "portfolio_project_link"), None) or next(
            (c for c in links if c.get("type") == "board_relation" and (c.get("settings") or {}).get("type") ==
             "hierarchy"), None)
        targets[x] = {str(i) for i in ((link or {}).get("settings") or {}).get("boardIds") or []}
    out = []
    for p in projects:
        f = facts[p]
        relations = [c for c in f.links if c.get("type") == "board_relation"]
        reflected = {str(i) for c in relations for i in (c.get("settings") or {}).get("boardIds") or []}
        touched = []
        for x in portfolios:
            c1, c2 = p in targets[x], p in (reads.items.get(x) or {}).get("rows", set())
            if c1 or c2:
                rules = (["C1"] if c1 else []) + (["C2"] if c2 else [])
                result = "connected" if c1 and c2 else "partial link - review"
                if result == "connected" and x in reflected:
                    rules.append("C3")
                touched.append({"portfolio_id": x, "tasks_board_id": p, "result": result, "rules": rules, "note": None})
        if touched:
            out += touched
            continue
        overview = sorted((i for i in reflected if (boards.get(i) or {}).get("rule") == "R6"), key=id_sort)
        if incomplete:
            out.append({"portfolio_id": None, "tasks_board_id": p, "result": "incomplete read - review", "rules": [],
                        "note": None})
            continue
        shares = any((f.board.get("board_folder_id") and f.board.get("board_folder_id") ==
                      facts[x].board.get("board_folder_id")) or f.workspace == facts[x].workspace for x in portfolios)
        out.append({"portfolio_id": None, "tasks_board_id": p, "result": "unconnected", "rules": ["C4"] if shares else [],
                    "note": "overview %s" % overview[0] if overview else None})
    return out


def classify(reads, account):
    """Both rule sets over every board the pages return (W78): the shape the answer keys pin."""
    facts = {bid: Facts(board, reads, account) for bid, board in reads.boards.items()}
    parents = {}
    for bid, f in facts.items():
        for link in f.links:
            if link.get("type") == "subtasks":
                for child in (link.get("settings") or {}).get("boardIds") or []:
                    parents.setdefault(str(child), []).append(bid)
    ctx = {"parents": parents, "entity": {}, "targets": {}}
    first = {bid: classify_board(f, reads, ctx) for bid, f in facts.items()}
    entity = {}
    for bid, r in first.items():
        if r["class"].startswith("native_") and not r["class"].endswith("_subitems") and r["rule"] in ("N2", "N3", "N4"):
            entity[bid] = r["class"].split("_", 2)[2]
    targets = {}
    for bid, r in first.items():
        if r["class"] == "native_service_tickets":
            for link in facts[bid].links:
                if link.get("type") == "board_relation":
                    for target in (link.get("settings") or {}).get("boardIds") or []:
                        targets.setdefault(str(target), []).append(bid)
    ctx = {"parents": parents, "entity": entity, "targets": {k: sorted(set(v), key=id_sort) for k, v in targets.items()}}
    boards = {bid: classify_board(facts[bid], reads, ctx) for bid in sorted(facts, key=id_sort)}
    index = (account.get("guard_index") or {}).get("native_board_index") or {}
    for bid, qkey in sorted(((account.get("guard_index") or {}).get("native_installs") or {}).items()):
        r = boards.get(str(bid))
        if r is None or r["class"] == "pending":
            continue
        r["signals"].append("native_install:%s" % qkey)  # A38: a native a strand installed, never a build look-alike
        if not r["class"].startswith("native_") and "/" in str(index.get(str(bid)) or ""):
            product, entity = index[str(bid)].split("/", 1)  # read without its native signals: its role from the index
            r.update({"class": native_class(product, entity), "confidence": "medium", "review": True})
    totals, limits, pending = {}, [], []
    for bid, r in boards.items():
        if r["class"] == "pending":
            pending.append(r.pop("pending"))
            continue
        if r["limits"]:
            code = next(c for c in LIMIT_ORDER if c in r["limits"])
            limits.append({"board_id": bid, "code": code, "codes": sorted(r["limits"]), "class": r["class"],
                           "reason": LIMIT_REASONS[code]})
        else:
            totals[r["class"]] = totals.get(r["class"], 0) + 1
    client = [str(i) for i in (account.get("guard_index") or {}).get("client_workspace_ids") or []]
    kinds = dict(((account.get("guard_index") or {}).get("product_workspaces") or {}), **reads.workspace_kinds)
    reports = [{"workspace_id": ws, "product": kinds.get(ws), "report": NOT_INSTALLED} for ws in client
               if kinds.get(ws) in ("crm", "service") and not any(
                   facts[b].workspace == ws and r["class"].startswith("native_") for b, r in boards.items())]
    review = [{"board_id": bid, "class": r["class"], "rule": r["rule"], "confidence": r["confidence"],
               "action": "protect as native and ask"} for bid, r in boards.items()
              if r["class"].startswith("native_") and r["confidence"] != "high"]
    notes = list(reads.notes)
    if reads.workflow_sets is None and any(f.type == "custom_object" for f in facts.values()):
        notes.append("workflow objects set not read: custom objects that are not a Portal are custom_object_other at "
                     "low confidence (W79)")
    next_ids = sorted(set(pending), key=id_sort)
    return {"board_count": len(boards), "boards": boards, "totals": dict(sorted(totals.items())), "limits": limits,
            "projects": _projects(boards, facts, reads), "reports": reports,
            "unreadable_ids": sorted(set(reads.missing), key=id_sort), "next_ids": next_ids,
            "next_query": DETECT_QUERY if next_ids else None, "page_size": list(PAGE_SIZE),
            "sweep_complete": reads.sweep_complete, "unfinished_sweeps": reads.unfinished(),
            "needs_review": review, "notes": notes}, facts


def cmd_classify(root, args):
    led = Ledger(root)
    refuse(*led.newer())
    data, name = input_json(root, args.reads, "--reads")
    reads = Reads(data, name, led.account)
    result, _ = classify(reads, led.account)
    result["ring"] = next(iter(reads.rings), None)
    return 0, result


# native-map (W16, W18, W88 to W90): the classification stored in account.json, record level.

def index_value(result):
    """"<product>/<entity>" of a board native_board_index takes (W16), or None."""
    cls = result["class"]
    if result["rule"] == "N10":
        return result["attributes"].get("fingerprint")
    if not cls.startswith("native_"):
        return None
    product, entity = cls.split("_", 2)[1:]
    return "%s/%s" % (product, "companion" if entity == "companion_board" else entity)


def native_index(result, facts):
    """The parts of guard_index and native_map one classification gives (W16, W18, W80, W89)."""
    boards, index, by_entity, portals = result["boards"], {}, {}, {"active": [], "archived": []}
    for bid, r in boards.items():
        value = index_value(r)
        if value:
            index[bid] = value
            by_entity.setdefault(value, []).append(bid)
            if r["class"] == "native_service_portal":
                portals["archived" if r["attributes"].get("state") == "archived" else "active"].append(bid)
    candidates = {}
    for bid, value in index.items():
        product, entity = value.split("/", 1)
        candidates.setdefault((product, MAP_ENTITY.get(entity, entity)), []).append(bid)
    native_map = {"crm": {}, "service": {}, "portfolio": {}}
    for (product, entity), ids in sorted(candidates.items()):
        best = sorted(ids, key=lambda b: (CONFIDENCE_RANK[boards[b]["confidence"]], boards[b]["lineage"]["hops"],
                                          id_sort(b)))[0]
        native_map.setdefault(product, {})[entity] = map_entry(best, boards[best], product == "service")
    for bid, r in boards.items():
        if r["class"] == "portfolio_board":
            entry = map_entry(bid, r, False)
            entry["projects"] = []
            for project in result["projects"]:
                if project["portfolio_id"] != bid:
                    continue
                tasks = project["tasks_board_id"]
                folder = facts[tasks].board.get("board_folder_id") if tasks in facts else None
                entry["projects"].append({"tasks_board_id": tasks, "overview_board_id": None, "overview_state": None,
                                          "planner_board_id": None, "folder_id": None if folder is None else str(folder),
                                          "connected": project["result"]})
            native_map["portfolio"][bid] = entry
    return {"native_map": native_map, "native_board_index": index,
            "native_board_ids_by_entity": {k: sorted(v, key=id_sort) for k, v in sorted(by_entity.items())},
            "portal_object_ids": {k: sorted(v, key=id_sort) for k, v in portals.items()}}


def map_entry(bid, r, service):
    entry = {"board_id": bid, "rule": r["rule"], "confidence": r["confidence"], "signals": list(r["signals"]),
             "lineage": {"chain": list(r["lineage"]["chain"]), "resolved": r["lineage"]["resolved"],
                         "note": r["lineage"]["note"]}, "confirmed_by_user": False}
    if service:
        entry["family"] = r["attributes"].get("family")
    return entry


def catalogue_ids(products, met_templates, met_views):
    """W18, W87: the template and template view ids of every product the account carries, and those the reads met."""
    templates, views = set(met_templates), set(met_views)
    if "crm" in products:
        templates |= set(CRM_TEMPLATES)
        views |= set(CRM_VIEWS)
    if "service" in products:
        templates |= set(SERVICE_TEMPLATES)
        views |= set(SERVICE_VIEWS)
    if "core" in products:
        templates |= set(ROLE_TEMPLATES)
    return sorted(templates, key=id_sort), sorted(views, key=id_sort)


def cmd_native_map(root, args):
    led = Ledger(root)
    refuse(*led.newer())
    data, name = input_json(root, args.reads, "--reads")
    coverage = (args.coverage or "").strip()
    days = args.staleness_days
    refuse(None if coverage and "\n" not in coverage else ("(flags)", "--coverage", "no one-line coverage", "one line "
                                                           "stating what was read, as record_provenance.coverage"),
           None if days is None or DIGITS.fullmatch(str(days)) else ("(flags)", "--staleness-days", "%r" % days,
                                                                     "a whole number of days"))
    reads = Reads(data, name, led.account)
    result, facts = classify(reads, led.account)
    index = led.index
    clients = [str(i) for i in index.get("client_workspace_ids") or []]
    reasons = [None if not result["next_ids"] else (name, "next_ids", "lineage still waits on %s" % ", ".join(
        result["next_ids"]), "a boards_ids page for those ids appended to the reads file (W78), then native-map again"),
               None if result["sweep_complete"] else (name, "pages", "the sweep of %s did not end on an empty page" % (
                   ", ".join(result["unfinished_sweeps"]) or "any workspace"), "every swept workspace paged until "
                   "boards is [] (R0)")]
    for strand, target in sorted((index.get("build_targets_by_strand") or {}).items()):
        outside = [ws for ws in (target or {}).get("workspace_ids") or [] if str(ws) not in clients]
        if outside:
            reasons.append(("account.json", "guard_index.build_targets_by_strand.%s" % strand, "strand %s targets %s, "
                            "outside the client's workspaces" % (strand, ", ".join(map(str, outside))), A21))
    parts = native_index(result, facts)
    for item in args.confirm or []:
        product, _, entity = item.partition("/")
        entry = (parts["native_map"].get(product) or {}).get(entity)
        if entry is None:
            reasons.append(("(flags)", "--confirm", "%s is no entry of this map" % item, "<product>/<entity> of an entry"))
        elif entry["confidence"] != "high":
            reasons.append(("account.json", "native_map.%s.%s.confirmed_by_user" % (product, entity), "the entry is %s "
                            "confidence: nothing below high is confirmed (W88)" % entry["confidence"],
                            "protect it as native and ask the user each time it matters"))
    refuse(*reasons)
    old = led.account.get("native_map") or {}
    for product in ("crm", "service"):
        for entity, entry in parts["native_map"].get(product, {}).items():
            before = (old.get(product) or {}).get(entity) or {}
            if before.get("confirmed_by_user") is True and before.get("board_id") == entry["board_id"] and \
                    before.get("rule") == entry["rule"] and entry["confidence"] == "high":
                entry["confirmed_by_user"] = True
            if "%s/%s" % (product, entity) in (args.confirm or []):
                entry["confirmed_by_user"] = True
    for bid, entry in parts["native_map"]["portfolio"].items():
        if (((old.get("portfolio") or {}).get(bid)) or {}).get("confirmed_by_user") is True:
            entry["confirmed_by_user"] = True
    products = {p.get("kind") for p in (reads.products or [])} | {
        p.get("kind") for p in (led.account.get("account") or {}).get("products") or [] if isinstance(p, dict)}
    met_templates = {f.terminal for f in facts.values() if f.terminal}
    met_views = {v for f in facts.values() for v in f.views}
    templates, views = catalogue_ids(products, met_templates, met_views)
    workspaces = dict(index.get("product_workspaces") or {})
    for ws, kind in sorted(dict({f.workspace: f.product for f in facts.values() if f.workspace and f.product != "none"},
                                **reads.workspace_kinds).items()):
        if ws not in clients or ws not in workspaces:
            workspaces[ws] = kind
    entities = sorted({value for value in parts["native_board_index"].values()})
    reserved = {}
    for value in entities:
        product, entity = value.split("/", 1)
        key = (product, MAP_ENTITY.get(entity, entity))
        if key in SIGNATURES:
            threshold, ids = SIGNATURES[key]
            reserved["%s/%s" % key] = {"ids": list(ids), "threshold": threshold}
    reserved["blank_default_exclusions"] = list(BLANK_DEFAULTS)
    staleness = int(days) if days is not None else (index.get("record_provenance") or {}).get("staleness_budget_days", 7)
    captured = data.get("captured_at") if is_utc(data.get("captured_at")) else mc.stamp("utc")
    unreadable = sorted({str(i) for i in index.get("unreadable_intermediate_ids") or []} | set(result["unreadable_ids"]),
                        key=id_sort)
    fresh = {"captured_at": captured, "ring": next(iter(reads.rings), None) or index.get("ring"),
             "product_workspaces": workspaces,
             "account_products": reads.products if reads.products is not None else index.get("account_products") or [],
             "native_board_index": parts["native_board_index"],
             "native_board_ids_by_entity": parts["native_board_ids_by_entity"], "template_source_ids": templates,
             "unreadable_intermediate_ids": unreadable, "template_view_ids": views, "reserved_column_ids": reserved,
             "native_default_names_and_terminology": list(DEFAULT_NAMES) + list(DEFAULT_TERMINOLOGY),
             "portal_object_ids": parts["portal_object_ids"],
             "record_provenance": {"coverage": coverage, "staleness_budget_days": staleness}}
    for key in list(index):  # client_workspace_ids, build_targets_by_strand and lease stay exactly as found
        if key in fresh:
            index[key] = fresh.pop(key)
    index.update(fresh)
    led.account["native_map"] = parts["native_map"]
    led.account["updated_at"] = mc.stamp("utc")
    commit("native-map", [("account.json", json_step(root, root / "account.json", led.account), None)])
    steps = [{"workspace_id": r["workspace_id"], "ui_step": "ask the user to add the %s board set to workspace %s "
              "from monday's UI, recorded with ledger.py ui-step, then run native-map again (A11.5)" % (
                  r["product"], r["workspace_id"])} for r in result["reports"]]
    return 0, {"native_map": parts["native_map"], "native_board_index": parts["native_board_index"],
               "portal_object_ids": parts["portal_object_ids"], "totals": result["totals"], "limits": result["limits"],
               "reports": result["reports"], "ui_steps_to_record": steps, "needs_review": result["needs_review"],
               "unreadable_ids": unreadable, "captured_at": captured, "notes": result["notes"],
               "written": {"account.json": mc.sha256_file(root / "account.json")}}


# snapshot and compare (W73 to W77, A9.7): digests of the reads the session hands, compared offline.

BOARD_KINDS = ("board", "subitems", "portfolio", "project")
PROTECTED = ("do-not-change", "change-with-own-yes")
SNAPSHOT_PARTS = ("inventory", "boards", "automations", "forms", "docs", "dashboards", "agents", "workflows", "vibe_apps")
UNCHANGED = "unchanged during the audit window"
OUTSIDE = "a finding against the record, reported as changed outside this strand, never fixed here"
COMPARED = (("inventory", "board", "id", ("name", "type", "state", "description", "board_folder_id", "board_kind",
                                          "workspace_id")),
            ("boards", "board", "id", ("columns_digest", "groups_digest", "views_digest", "owners", "subscribers")),
            ("automations", "automation", "id", ("active", "updated_at")), ("forms", "form", "view_id", ("form_digest",)),
            ("docs", "doc", "id", ("block_count",)), ("dashboards", "dashboard", "id", ("name", "kind", "workspace_id")),
            ("agents", "agent", "id", ("state", "version_id", "plan_digest", "triggers_digest", "grants_digest")),
            ("workflows", "workflow", "id", ("name", "state")),
            ("vibe_apps", "vibe_app", "id", ("status", "is_published", "code_version")))  # W75; updated_at never


def shown(value):
    return value if isinstance(value, str) else json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def snapshot_scope(led):
    """W74, K287: the strand's own rows that have ids, and every protected live row whatever strand built it."""
    rows = [r for r in led.objects.values() if r.get("id")]
    protected = {k: r for k, r in sorted((led.account.get("live_objects") or {}).items())
                 if (r or {}).get("constraint") in PROTECTED and r.get("monday_id")}
    boards = sorted({str(r["id"]) for r in rows if r.get("type") in BOARD_KINDS} | {
        str(r["monday_id"]) for r in protected.values() if r.get("kind") in BOARD_KINDS}, key=id_sort)
    ids = {str(r["id"]) for r in rows} | {str(r["monday_id"]) for r in protected.values()}
    return boards, ids, protected


def cmd_snapshot(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    led.require_build()
    refuse(None if args.label in ("before", "after") else ("(flags)", "--label", "%r" % args.label, "before | after"))
    read, name = input_json(root, args.read, "--read")
    refuse(*[None if isinstance(read.get(part), list) else (name, part, "not a list", "the %s part of a snapshot read, "
                                                             "[] when none was read (W74)" % part)
             for part in SNAPSHOT_PARTS],
           None if is_utc(read.get("read_at")) else (name, "read_at", "%r" % read.get("read_at"), "the UTC time of the read"),
           None if is_str(read.get("ring")) else (name, "ring", "no ring", "the ring read, such as release_candidate 2026-10"))
    boards, ids, protected = snapshot_scope(led)
    clients = set(led.client_ids)
    dropped = []

    def keep(entry, inside):
        if inside:
            return True
        dropped.append(str(entry.get("id") or entry.get("view_id") or entry.get("board_id")))
        return False
    inventory = [{k: e.get(k) for k in ("id", "name", "type", "state", "description", "updated_at", "board_folder_id",
                                        "board_kind", "workspace_id")} for e in read["inventory"]
                 if keep(e, str(e.get("workspace_id")) in clients)]
    snap_boards = [{"id": str(e.get("id")), "columns_digest": digest("columns", e.get("columns") or []),
                    "groups_digest": digest("groups", e.get("groups") or []),
                    "views_digest": digest("views", e.get("views") or []),
                    "owners": sorted(map(str, e.get("owners") or [])), "subscribers": sorted(map(str, e.get("subscribers")
                                                                                              or []))}
                   for e in read["boards"] if keep(e, str(e.get("id")) in boards)]
    automations = [{"id": str(e.get("id")), "board_id": str(e.get("board_id")), "active": automation_active(e),
                    "updated_at": e.get("updated_at")} for e in read["automations"]
                   if keep(e, str(e.get("id")) in ids or str(e.get("board_id")) in boards)]
    forms = [{"board_id": str(e.get("board_id")), "view_id": str(e.get("view_id")), "form_digest": digest(
        "form", e.get("form"))} for e in read["forms"] if keep(e, str(e.get("view_id")) in ids or str(e.get("board_id"))
                                                               in boards)]
    docs = [{"id": str(e.get("id")), "block_count": e.get("block_count")} for e in read["docs"]
            if keep(e, str(e.get("id")) in ids)]
    dashboards = [{k: e.get(k) for k in ("id", "name", "workspace_id", "kind")} for e in read["dashboards"]
                  if keep(e, str(e.get("id")) in ids)]
    agents = [{"id": str(e.get("id")), "state": e.get("state"), "version_id": e.get("version_id"),
               "plan_digest": digest("plan", e.get("plan")), "triggers_digest": digest("triggers", e.get("triggers") or []),
               "grants_digest": digest("grants", e.get("knowledge") or [])} for e in read["agents"]
              if keep(e, str(e.get("id")) in ids)]
    workflows = [{k: e.get(k) for k in ("id", "name", "state")} for e in read["workflows"] if keep(e, str(e.get("id")) in ids)]
    vibe = [{k: e.get(k) for k in ("id", "status", "is_published", "code_version")} for e in read["vibe_apps"]
            if keep(e, str(e.get("id")) in ids)]
    covered = {"board": read["inventory"], "subitems": read["inventory"], "portfolio": read["inventory"],
               "project": read["inventory"], "automation": read["automations"], "dashboard": read["dashboards"],
               "agent": read["agents"], "workflow": read["workflows"], "vibe_app": read["vibe_apps"]}
    rows = []
    for key, row in protected.items():
        if row.get("kind") not in covered:
            continue
        entry = next((e for e in covered[row["kind"]] if str(e.get("id")) == str(row["monday_id"])), None)
        now = digest(key.split(":", 1)[1].lower(), identity(row["kind"], entry)) if entry is not None else None
        rows.append({"key": key, "monday_id": str(row["monday_id"]), "recorded_digest": row.get("digest"),
                     "digest_at_snapshot": now, "moved": now != row.get("digest")})
    folder = root / "live" / "snapshots"
    base = "%s-%s-%s-%s" % (mc.stamp("date"), led.short, led.version, args.label)
    count, path = 1, folder / (base + ".json")
    while path.exists():
        count += 1
        path = folder / ("%s-%d.json" % (base, count))
    rel = led.rel(path)
    data = {"schema": "snapshot/1", "strand": led.short, "version": led.version, "label": args.label,
            "taken_at": mc.stamp("utc"), "read_at": read["read_at"], "ring": read["ring"],
            "ledger_sha256": mc.sha256_file(led.build_path), "account_sha256": mc.sha256_file(root / "account.json"),
            "scope": {"boards": boards, "live_rows": list(protected), "dropped": sorted(set(dropped), key=id_sort)},
            "inventory": inventory, "boards": snap_boards, "automations": automations, "forms": forms, "docs": docs,
            "dashboards": dashboards, "agents": agents, "workflows": workflows, "vibe_apps": vibe, "protected": rows}
    commit("snapshot", [(rel, json_step(root, path, data), None)])
    return 0, {"path": rel, "label": args.label, "scope": data["scope"], "dropped": data["scope"]["dropped"],
               "protected": rows, "written": {rel: mc.sha256_file(path)}}


# The documents-appendix scan (W77): a small tokenizer after GraphQL's lexical grammar, failing closed.

GQL_PUNCT = "!$&()=:@[]{|}"
GQL_NAME = re.compile(r"[_A-Za-z][_0-9A-Za-z]*")
GQL_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
TYPE_SYSTEM = ("schema", "scalar", "type", "interface", "union", "enum", "input", "directive", "extend")
OPENS, CLOSES = {"{": "}", "(": ")", "[": "]"}, {"}": "{", ")": "(", "]": "["}


def gql_tokens(text):
    """(kind, value) tokens of a GraphQL document; ValueError names the syntax error."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n,﻿":
            i += 1
        elif c == "#":
            while i < n and text[i] not in "\r\n":
                i += 1
        elif text.startswith('"""', i):
            j = i + 3
            while True:
                k = text.find('"""', j)
                if k < 0:
                    raise ValueError("an unterminated block string")
                if text[k - 1] == "\\":
                    j = k + 3
                    continue
                break
            out.append(("string", text[i + 3:k]))
            i = k + 3
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] in "\r\n":
                    raise ValueError("an unterminated string")
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                raise ValueError("an unterminated string")
            out.append(("string", text[i + 1:j]))
            i = j + 1
        elif text.startswith("...", i):
            out.append(("punct", "..."))
            i += 3
        elif c in GQL_PUNCT:
            out.append(("punct", c))
            i += 1
        elif GQL_NAME.match(text, i):
            word = GQL_NAME.match(text, i).group(0)
            out.append(("name", word))
            i += len(word)
        elif GQL_NUMBER.match(text, i) and GQL_NUMBER.match(text, i).group(0) not in ("", "-"):
            number = GQL_NUMBER.match(text, i).group(0)
            out.append(("number", number))
            i += len(number)
        else:
            raise ValueError("a stray character %r" % c)
    return out


def scan_document(text):
    """(verdict, reason): `pass` for one query, else `refused` with what it holds (W77, K303 to K307)."""
    try:
        tokens = gql_tokens(text)
    except ValueError as exc:
        return "refused", "a syntax error: %s" % exc
    operations, i = [], 0
    while i < len(tokens):
        kind, value = tokens[i]
        if (kind, value) == ("punct", "{"):
            start = "query"
        elif kind == "name" and value in ("query", "mutation", "subscription", "fragment"):
            start, i = value, i + 1
        elif kind == "name" and value in TYPE_SYSTEM:
            return "refused", "a type-system definition"
        else:
            return "refused", "a syntax error: %s %r where a definition starts" % (kind, value)
        stack = []
        while i < len(tokens) and not (tokens[i] == ("punct", "{") and not stack):
            token = tokens[i][1] if tokens[i][0] == "punct" else None
            if token in OPENS:
                stack.append(token)
            elif token in CLOSES:
                if not stack or stack.pop() != CLOSES[token]:
                    return "refused", "a syntax error: unbalanced brackets"
            i += 1
        if i >= len(tokens):
            return "refused", "a syntax error: a definition with no selection set"
        while i < len(tokens):
            token = tokens[i][1] if tokens[i][0] == "punct" else None
            if token in OPENS:
                stack.append(token)
            elif token in CLOSES:
                if not stack or stack.pop() != CLOSES[token]:
                    return "refused", "a syntax error: unbalanced brackets"
                if not stack:
                    break
            i += 1
        if stack:
            return "refused", "a syntax error: unbalanced brackets"
        if start != "fragment":
            operations.append(start)
        i += 1
    for kind in ("mutation", "subscription"):
        if kind in operations:
            return "refused", kind
    if len(operations) > 1:
        return "refused", "more than one operation"
    if not operations:
        return "refused", "no operation"
    return "pass", "one query"


def appendix_documents(text):
    """The documents of the `## Documents appendix` section (W77), numbered from 1: (number, source, text or None,
    why unreadable), or None when there is no such section."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = next((n for n, line in enumerate(lines) if line.rstrip() == "## Documents appendix"), None)
    if start is None:
        return None
    end = next((n for n in range(start + 1, len(lines)) if re.match(r"##(?!#)", lines[n])), len(lines))
    found, n = [], start + 1
    while n < end:
        opening = re.match(r"\s*(`{3,}|~{3,})\s*([^\s`]*)", lines[n])
        if not opening:
            n += 1
            continue
        fence, info = opening.group(1), opening.group(2).lower()
        close = next((m for m in range(n + 1, end) if re.fullmatch(r"\s*%s%s*\s*" % (
            re.escape(fence), re.escape(fence[0])), lines[m])), None)
        body = "\n".join(lines[n + 1:close if close is not None else end])
        where = "line %d" % (n + 1)
        if close is None:
            found.append((where, None, "a fenced block that never closes"))
        elif info in ("graphql", "gql"):
            found.append((where, body, None))
        elif info == "json":
            try:  # WP4's R59: read strictly, so a repeated key never hides one of its two values
                value = mc.strict_json(body)
            except mc.RepeatedKey as repeated:
                found.append((where, None, "a json block in which the key %s is written twice in one object"
                              % json.dumps(repeated.args[1])))
            except ValueError:
                found.append((where, None, "a json block that does not parse"))
            else:
                stack = [value]
                while stack:
                    item = stack.pop(0)
                    if isinstance(item, dict):
                        for key, inner in item.items():
                            if key == "query" and isinstance(inner, str):
                                found.append((where, inner, None))
                            elif isinstance(inner, (dict, list)):
                                stack.append(inner)
                    elif isinstance(item, list):
                        stack.extend(item)
        else:
            found.append((where, None, "a %s block the scan cannot read" % (info or "plain")))
        n = (close if close is not None else end) + 1
    return [(number, where, body, why) for number, (where, body, why) in enumerate(found, 1)]


def input_text(root, value, flag):
    """A text file the session names, inside the record (W91)."""
    raw = Path(value)
    rel = value
    if raw.is_absolute():
        try:
            rel = raw.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            refuse((raw.as_posix(), flag, "the file lies outside the record", "a file inside the record"))
    path = mc.record_path(root, rel)
    name = mc.relative(root, path)
    if not path.is_file():
        raise mc.CannotRun((name, mc.WHOLE_FILE, "the file %s names is missing" % flag, "a file the session wrote"))
    return mc.read_text(path, name), name


def cmd_compare(root, args):
    led = Ledger(root)
    refuse(*led.newer())
    before, bname = input_json(root, args.before, "--before")
    after, aname = input_json(root, args.after, "--after")
    refuse(*[None if snap.get("schema") == "snapshot/1" else (name, "schema", "%r" % snap.get("schema"), "snapshot/1, "
                                                              "a file ledger.py snapshot wrote")
             for snap, name in ((before, bname), (after, aname))],
           None if before.get("label") == "before" else (bname, "label", "%r" % before.get("label"), "before"),
           None if after.get("label") == "after" else (aname, "label", "%r" % after.get("label"), "after"),
           None if (before.get("strand"), before.get("version")) == (after.get("strand"), after.get("version")) else (
               aname, "strand", "strand %s %s against %s %s" % (before.get("strand"), before.get("version"),
                                                             after.get("strand"), after.get("version")),
               "two snapshots of one strand and version"))
    flags, blocking, warnings = [], [], []

    def flag(kind, oid, field, was, now):
        where = "%s:%s.%s" % (kind, oid, field) if field else "%s:%s" % (kind, oid)
        problem = "%s to %s" % (shown(was), shown(now))
        flags.append({"field": where, "before": was, "after": now, "problem": problem, "expected": UNCHANGED})
        blocking.append({"file": aname, "field": where, "problem": problem, "expected": UNCHANGED})
    for part, kind, ident, fields in COMPARED:
        old = {str(e.get(ident)): e for e in before.get(part) or []}
        new = {str(e.get(ident)): e for e in after.get(part) or []}
        for oid in sorted(set(old) | set(new), key=id_sort):
            if oid not in new or oid not in old:
                flag(kind, oid, None if part == "inventory" else "read", "present" if oid in old else "absent",
                     "present" if oid in new else "absent")
                continue
            for field in fields:
                if old[oid].get(field) != new[oid].get(field):
                    flag(kind, oid, field, old[oid].get(field), new[oid].get(field))
    for field, kind, oid in (("ledger_sha256", "ledger", before.get("strand")), ("account_sha256", "account", "record")):
        if before.get(field) != after.get(field):
            flag(kind, oid, field, before.get(field), after.get(field))
    moved_after = {p.get("key") for p in after.get("protected") or [] if p.get("moved")}
    outside = []
    for row in before.get("protected") or []:
        if not row.get("moved"):
            continue
        problem = "%s to %s" % (shown(row.get("recorded_digest")), shown(row.get("digest_at_snapshot")))
        outside.append({"key": row.get("key"), "monday_id": row.get("monday_id"), "recorded_digest": row.get(
            "recorded_digest"), "digest_at_snapshot": row.get("digest_at_snapshot"),
            "moved_in": ["before"] + (["after"] if row.get("key") in moved_after else []), "problem": problem,
            "expected": OUTSIDE})
        warnings.append({"file": bname, "field": "%s.digest" % row.get("key"), "problem": "changed outside this strand "
                         "before the audit window: %s" % problem, "expected": OUTSIDE})
    documents = []
    if args.appendix:
        text, name = input_text(root, args.appendix, "--appendix")
        found = appendix_documents(text)
        if found is None:
            blocking.append({"file": name, "field": "## Documents appendix", "problem": "the audit file has no documents "
                             "appendix", "expected": "a ## Documents appendix section holding every read-only document "
                             "the audit ran (W77)"})
        for number, where, body, why in found or []:
            verdict, reason = ("refused", why) if body is None else scan_document(body)
            documents.append({"number": number, "at": where, "verdict": verdict, "reason": reason})
            if verdict != "pass":
                blocking.append({"file": name, "field": "document %d (%s)" % (number, where), "problem": "refused: %s"
                                 % reason, "expected": "one read-only query per document: no mutation, no subscription, "
                                 "a single operation"})
    code = 1 if blocking else 2 if warnings else 0
    return code, {"findings": {"blocking": blocking, "warnings": warnings}, "flags": flags, "changed_outside": outside,
                  "documents": documents, "write_detected": bool(flags) or any(d["verdict"] != "pass" for d in documents),
                  "written": {}}


# reconcile (W70 to W72, A8.11): the strand's rows against a live inventory, automations first.

INVENTORY_LISTS = ("workspaces", "boards", "folders", "docs", "automations", "agents", "vibe_apps", "workflows")
ORDER_FIRST = ("automation", "agent", "vibe_app", "workflow")  # K274, K275
NOT_IN_INVENTORY = ("group", "column", "view", "form", "widget", "item_batch", "ai_column", "sequence", "webhook")
PART_TYPES = {"dashboard": ("widget",)}  # W71 as the trace check clarified it: an object's own parts
for _kind in BOARD_KINDS:
    PART_TYPES[_kind] = ("group", "column", "view", "form", "subitems", "ai_column", "item_batch")
PUBLISHED = {"workflow": ("published", True), "vibe_app": ("is_published", True), "agent": ("state", "ACTIVE")}


class Inventory:
    """A live-inventory/1 file (W70), indexed by id."""

    def __init__(self, data):
        self.data = data
        for part in INVENTORY_LISTS:
            setattr(self, part, {str(e.get("id")): e for e in data.get(part) or [] if isinstance(e, dict)})
        dashboards = data.get("dashboards") or {}
        self.dashboards = {str(e.get("id")): e for e in dashboards.get("returned") or [] if isinstance(e, dict)}
        self.dashboards_missing = {str(i) for i in dashboards.get("missing_ids") or []}
        self.doc_boards = {str(e.get("object_id")): str(e.get("id")) for e in self.docs.values()}

    def entry(self, kind, oid):
        """(live entry or None, why it is absent)."""
        oid = str(oid)
        if kind in BOARD_KINDS:
            found = self.boards.get(oid)
        elif kind == "dashboard":
            if oid in self.dashboards_missing:
                return None, "%s in the dashboards read's missing_ids" % oid
            found = self.dashboards.get(oid)
        else:
            found = getattr(self, {"workspace": "workspaces", "folder": "folders", "doc": "docs",
                                   "automation": "automations", "agent": "agents", "vibe_app": "vibe_apps",
                                   "workflow": "workflows"}.get(kind, "boards"), {}).get(oid)
        return found, None if found is not None else "%s not in the inventory" % oid


def inventory_reasons(data, name, short):
    schema = str(data.get("schema"))
    reasons = [None if schema == "live-inventory/1" else (name, "schema", "%r: %s" % (
        schema, "newer than this plugin's: the ledger refuses it" if re.fullmatch(r"live-inventory/\d+", schema)
        else "not a live inventory"), "live-inventory/1"),
               None if str(data.get("strand")) == str(short) else (name, "strand", "%r, while --strand is %s" % (
                   data.get("strand"), short), "the strand the inventory was read for"),
               None if is_utc(data.get("read_at")) else (name, "read_at", "%r" % data.get("read_at"), "a UTC stamp"),
               None if not is_utc(data.get("read_at")) or mc.parse_utc(data["read_at"]) <= mc.now_utc() else (
                   name, "read_at", "%s is later than this machine's clock" % data["read_at"],
                   "the moment the read was made, never later than now"),
               None if is_str(data.get("ring")) else (name, "ring", "no ring", "\"<kind> <value>\"")]
    reasons += [None if isinstance(data.get(part), list) else (name, part, "not a list", "the %s read, [] when none"
                                                               % part) for part in INVENTORY_LISTS]
    dash = data.get("dashboards")
    reasons.append(None if isinstance(dash, dict) and all(isinstance(dash.get(k), list) for k in (
        "requested_ids", "returned", "missing_ids")) else (name, "dashboards", "not the by-id read", "{requested_ids, "
                                                           "returned, missing_ids}, read by stored id (G-92)"))
    return reasons


def _title(text):
    return " ".join(str(text or "").split()).casefold()


def _after(entry, started):
    """True when the live object was created at or after the attempt, None when the read carries no time."""
    created = (entry or {}).get("created_at")
    if not is_utc(created):
        return None
    return not is_utc(started) or mc.parse_utc(created) >= mc.parse_utc(started)


def read_for(led, row):
    board = row.get("parent_id") or (led.objects.get(row.get("parent_key")) or {}).get("id") or "<board id>"
    return {"column": "boards(ids: [%s]) { columns { id title type settings } }" % board,
            "group": "boards(ids: [%s]) { groups { id title color position } }" % board,
            "view": "boards(ids: [%s]) { views { id name type settings } }" % board,
            "form": "get_form on board %s" % board, "item_batch": "items(ids: [the batch's item ids]) { id }",
            "widget": "none: a widget cannot be read back (G-11); check it by eye on the dashboard"}.get(
        row.get("type"), "not-checkable until it is probed (A18); the user checks it by eye")


class Reconciler:
    """W71: at most one class per row and one per unclaimed live object."""

    def __init__(self, led, inv):
        self.led, self.inv, self.objects = led, inv, led.objects
        self.claimed, self.consumed, self.predates = set(), set(), set()
        for row in self.objects.values():
            self.claimed |= {str(i) for i in [row.get("id")] + list(row.get("item_ids") or []) + list(
                (row.get("companions") or {}).values()) if i}
            if row.get("type") == "doc" and row.get("id") and str(row["id"]) in inv.docs:
                self.claimed.add(str(inv.docs[str(row["id"])].get("object_id")))
        self.claimed |= {str((r or {}).get("monday_id")) for r in (led.account.get("live_objects") or {}).values()}
        self.claimed |= set((led.index.get("native_board_index") or {}))
        starts = [(r.get("attempt") or {}).get("started_at") for r in self.objects.values()]
        starts = [s for s in starts if is_utc(s)]
        self.earliest = min(starts, key=mc.parse_utc) if starts else None

    def element(self, key, kind, cls, live, confirm=False, needs=None, predates=False, note=None):
        return {"key": key, "kind": kind, "class": cls, "live_ids": [str(i) for i in live], "confirm": confirm,
                "needs_read": needs, "predates_attempt": predates, "note": note}

    def candidates(self, key, row):
        kind, name, inv = row.get("type"), row.get("name"), self.inv
        ws = row.get("workspace") or self.led.row_workspace(key)
        parent = self.objects.get(row.get("parent_key")) if row.get("parent_key") else None
        if kind == "workspace":
            return [e for e in inv.workspaces.values() if e.get("name") == name]
        if kind in BOARD_KINDS:
            folder = str(parent.get("id")) if parent and parent.get("type") == "folder" and parent.get("id") else None

            def fits(e):
                key_of = e.get("object_type_unique_key")
                if kind == "board":
                    return e.get("type") == "board" and key_of not in (KEY_PORTFOLIO,) + KEYS_PROJECT
                if kind == "subitems":
                    return e.get("type") == "sub_items_board"
                return key_of in ((KEY_PORTFOLIO,) if kind == "portfolio" else KEYS_PROJECT)
            return [e for e in inv.boards.values() if e.get("name") == name and e.get("state") != "deleted" and fits(e)
                    and (str(e.get("board_folder_id")) == folder if folder else str(e.get("workspace_id")) == str(ws))]
        if kind in ("folder", "doc", "workflow"):
            pool = {"folder": inv.folders, "doc": inv.docs, "workflow": inv.workflows}[kind]
            return [e for e in pool.values() if e.get("name") == name and str(e.get("workspace_id")) == str(ws)]
        if kind == "automation":
            board = str(row.get("parent_id") or (parent or {}).get("id"))
            want = _title(name)
            return [e for e in inv.automations.values() if str(e.get("board_id")) == board and (
                _title(e.get("title")) == want or (len(_title(e.get("title"))) >= 40 and want.startswith(
                    _title(e.get("title")))))]
        if kind == "agent":
            return [e for e in inv.agents.values() if e.get("name") == name]
        if kind == "vibe_app":
            bound = {r.split(":", 1)[1] for r in row.get("refs") or [] if str(r).startswith("board:")}
            return [e for e in inv.vibe_apps.values() if e.get("name") == name and set(map(str, e.get("board_ids") or []))
                    == bound]
        return []  # a dashboard is matched by stored id only

    def adopt_note(self, row, entry, timed):
        notes = []
        if row.get("type") == "automation":
            live = _title(entry.get("title"))
            if live != _title(row.get("name")):
                notes.append("live title is the request cut short at %d characters" % len(str(entry.get("title"))))
            notes.append("the user confirms after seeing the board's automation list")
        if row.get("type") == "workflow":
            notes.append("a workflow match always carries confirm")
        if timed is None:
            notes.append("the %ss read carries no created_at" % row.get("type"))
        return "; ".join(notes) or None

    def change_note(self, key, row, entry, old, new):
        pairs, kind = [], row.get("type")
        fields = IDENTITY.get(kind, ())
        if "name" in fields and row.get("name") is not None and entry.get("name") != row.get("name"):
            pairs.append(("name", row.get("name"), entry.get("name")))
        if kind in BOARD_KINDS and row.get("state") in STATES and entry.get("state") != row.get("state"):
            pairs.append(("state", row.get("state"), entry.get("state")))
        if kind == "automation" and row.get("state") in ("active", "inactive") and \
                automation_active(entry) is not (row.get("state") == "active"):
            pairs.append(("active", row.get("state") == "active", automation_active(entry)))
        values = dict(row.get("read_values") or {})
        if kind == "agent" and row.get("version_id_at_build") and "version_id" not in values:
            values["version_id"] = row["version_id_at_build"]
        pairs += [(f, v, entry.get(f)) for f, v in values.items() if f in entry and entry.get(f) != v]
        if pairs:
            return "; ".join("%s %s to %s" % (f, shown(a), shown(b)) for f, a, b in pairs)
        return "identity digest %s to %s" % (old, new)

    def publication(self, key, row):
        parent = self.objects.get(row.get("parent_key")) or {}
        kind = parent.get("type")
        if kind not in PUBLISHED or not (parent.get("id") or row.get("id")):
            return None, None
        entry, _ = self.inv.entry(kind, parent.get("id") or row.get("id"))
        field, want = PUBLISHED[kind]
        return entry, bool(entry) and entry.get(field) == want

    def row(self, key, row):
        kind, status, rid = row.get("type"), row.get("status"), row.get("id")
        if kind in ("publication", "activation"):
            entry, done = self.publication(key, row)
            if entry is None and done is None:
                return None
            live = [str(entry.get("id"))] if entry else []
            if status == "attempting":
                return self.element(key, kind, "adopt", live, confirm=True, note="the parent's live read shows the "
                                    "step done") if done else self.element(key, kind, "retry", [])
            if status in ("written", "mismatch"):
                return self.element(key, kind, "partial" if entry else "missing", live, note="written, parent live"
                                    if entry else "the parent is not in the inventory")
            if entry is None:
                return self.element(key, kind, "missing", [], note="the parent is not in the inventory")
            return "unchanged" if done else self.element(key, kind, "changed-since-verified", live,
                                                         note="the parent's live read no longer shows the step")
        if status == "attempting":
            started = (row.get("attempt") or {}).get("started_at")
            if rid:
                entry, why = self.inv.entry(kind, rid)
                if entry is not None and entry.get("state") != "deleted":
                    self.consumed.add(str(rid))
                    return self.element(key, kind, "adopt", [rid], confirm=kind in ("automation", "workflow"),
                                        needs="manage_agent get" if kind == "agent" else None,
                                        note="the recorded id is live")
                return self.element(key, kind, "retry", [], note="the recorded id %s is not live" % rid)
            matches = [e for e in self.candidates(key, row) if str(e.get("id")) not in self.claimed
                       and str(e.get("id")) not in self.consumed]
            timed = [(e, _after(e, started)) for e in matches]
            after = [e for e, t in timed if t is not False]
            early = [e for e, t in timed if t is False]
            self.predates |= {str(e.get("id")) for e in early}
            if len(after) == 1:
                entry, when = after[0], _after(after[0], started)
                self.consumed.add(str(entry.get("id")))
                return self.element(key, kind, "adopt", [entry.get("id")],
                                    confirm=kind in ("automation", "workflow") or when is None,
                                    needs="manage_agent get" if kind == "agent" else None,
                                    note=self.adopt_note(row, entry, when))
            if len(after) > 1:
                self.consumed |= {str(e.get("id")) for e in after}
                return self.element(key, kind, "duplicate", sorted((e.get("id") for e in after), key=id_sort))
            note = None
            if early:
                ids = ", ".join(sorted((str(e.get("id")) for e in early), key=id_sort))
                note = "its one match, %s, predates the attempt" % ids if len(early) == 1 else \
                    "its matches, %s, predate the attempt" % ids
            return self.element(key, kind, "retry", [], note=note)
        entry, why = self.inv.entry(kind, rid) if rid else (None, "no id recorded")
        if status in ("written", "mismatch"):
            if entry is None or entry.get("state") == "deleted":
                return self.element(key, kind, "missing", [rid] if entry else [], note=why or "live in state deleted")
            note = "%s, id live" % status
            if kind == "vibe_app" and entry.get("status") != "READY":
                note = "%s, live status %s" % (status, entry.get("status"))
            return self.element(key, kind, "partial", [rid], note=note)
        if entry is None:
            return self.element(key, kind, "missing", [], note=why)
        if entry.get("state") == "deleted":
            return self.element(key, kind, "missing", [rid], note="live in state deleted")
        if kind == "vibe_app" and entry.get("status") != "READY":
            return self.element(key, kind, "partial", [rid], note="live status %s" % entry.get("status"))
        old = (row.get("verify") or {}).get("digest")
        new = digest(str(key).lower(), identity(kind, entry))
        if new != old:
            return self.element(key, kind, "changed-since-verified", [rid], note=self.change_note(key, row, entry, old, new))
        parts = [(k, r.get("status")) for k, r in sorted(self.objects.items(), key=lambda kr: natural(kr[0]))
                 if r.get("parent_key") == key and r.get("type") in PART_TYPES.get(kind, ()) and r.get("status") != "verified"]
        if parts:
            if len(parts) == 1:
                note = "%s under it is %s, not verified" % parts[0]
            else:
                note = "%s under it are not verified (%s)" % (", ".join(k for k, _ in parts), ", ".join(s for _, s in parts))
            return self.element(key, kind, "partial", [rid], note=note)
        return "unchanged"

    def extras(self):
        inv, targets = self.inv, set(self.led.targets())
        taken = self.claimed | self.consumed
        workflow_ids = set(inv.workflows)
        found = []

        def add(kind, entry):
            oid = str(entry.get("id"))
            if oid not in taken:
                found.append(self.element(None, kind, "unrecorded-extra", [oid], predates=oid in self.predates))
        for entry in inv.workspaces.values():
            if str(entry.get("id")) in targets:
                add("workspace", entry)
        for entry in inv.boards.values():
            oid = str(entry.get("id"))
            if str(entry.get("workspace_id")) in targets and oid not in inv.doc_boards and oid not in workflow_ids:
                add("board", entry)
        for kind, pool in (("folder", inv.folders), ("doc", inv.docs), ("dashboard", inv.dashboards),
                           ("workflow", inv.workflows)):
            for entry in pool.values():
                if str(entry.get("workspace_id")) in targets and not (
                        kind == "doc" and str(entry.get("object_id")) in taken):
                    add(kind, entry)
        for entry in inv.automations.values():
            board = inv.boards.get(str(entry.get("board_id"))) or {}
            if str(board.get("workspace_id")) in targets:
                add("automation", entry)
        for kind, pool in (("agent", inv.agents), ("vibe_app", inv.vibe_apps)):
            for entry in pool.values():
                if self.earliest and _after(entry, self.earliest):
                    add(kind, entry)
        return found

    def run(self):
        elements, unchanged, not_started, not_reconciled, not_in = [], [], [], [], []
        for key in sorted(self.objects, key=natural):
            row = self.objects[key]
            status, kind = row.get("status"), row.get("type")
            if status == "planned":
                not_started.append(key)
            elif status in ("departed", "removed"):
                not_reconciled.append(key)
            elif kind in NOT_IN_INVENTORY:
                not_in.append({"key": key, "kind": kind, "status": status, "read": read_for(self.led, row)})
            else:
                found = self.row(key, row)
                if found is None:
                    not_in.append({"key": key, "kind": kind, "status": status, "read": read_for(self.led, row)})
                elif found == "unchanged":
                    unchanged.append(key)
                else:
                    elements.append(found)
        elements += self.extras()
        groups = {}
        for element in elements:
            groups.setdefault(element["kind"], []).append(element)

        def kind_order(kind):
            if kind in ORDER_FIRST:
                return (0, ORDER_FIRST.index(kind), [])
            keys = [e["key"] for e in groups[kind] if e["key"]]
            return (1, 0, natural(min(keys, key=natural))) if keys else (2, 0, [kind])
        ordered = []
        for kind in sorted(groups, key=kind_order):
            rows = sorted((e for e in groups[kind] if e["key"]), key=lambda e: natural(e["key"]))
            extra = sorted((e for e in groups[kind] if not e["key"]), key=lambda e: id_sort(e["live_ids"][0]))
            ordered += rows + extra
        classes = {name: 0 for name in RECONCILE_CLASSES}
        for element in ordered:
            classes[element["class"]] += 1
        proposals = [{"key": e["key"], "keep_one_of": e["live_ids"], "each_other": "a switch-off step" if e["kind"] ==
                      "automation" else "a deactivation proposal" if e["kind"] == "agent" else "an archive proposal",
                      "yes": "its own yes, per proposal"} for e in ordered if e["class"] == "duplicate"]
        return {"elements": ordered, "classes": classes, "unchanged": unchanged, "not_started": not_started,
                "not_reconciled": not_reconciled, "not_in_inventory": not_in, "proposals": proposals}


def cmd_reconcile(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    led.require_build()
    copy = root / ".work" / "strands" / led.short / "live-inventory.json"
    copy_rel = led.rel(copy)
    if args.inventory:
        data, name = input_json(root, args.inventory, "--inventory")
    elif copy.is_file():
        data, name = input_json(root, copy_rel, "--inventory")
    else:
        raise mc.CannotRun((copy_rel, mc.WHOLE_FILE, "no live inventory has been handed for strand %s" % led.short,
                            "ledger.py reconcile --strand %s --inventory <file the session wrote>" % led.short))
    refuse(*inventory_reasons(data, name, led.short))
    plan = Reconciler(led, Inventory(data)).run()
    steps = []
    if args.inventory and name != copy_rel:
        steps.append((copy_rel, json_step(root, copy, data), None))
    if not args.classify_only:
        commit("reconcile", steps)
        return 0, dict({"mode": "full", "strand": led.short, "inventory": copy_rel}, **plan, written={
            rel: mc.sha256_file(mc.record_path(root, rel)) for rel, _, _ in steps}, next=(
            "show the user this plan; adoption, retry and departure then go through record, intent --retry and depart, "
            "each with the user's approval (A8.11); a retry or a departure of a row left attempting needs this plan to "
            "class it retry, over a read made after its attempt began (R10)"))
    status = mc.lease_status(root)
    reasons = [None if status.get("held") else (mc.LOCK_REL, "state", "no lease is held (state %s)" % status.get("state"),
                                                "a lease held by strand %s whose heartbeat is stale" % led.short),
               None if not status.get("held") or status.get("strand") == led.short else (
                   mc.LOCK_REL, "strand", "the lease is held by strand %s, not strand %s" % (status.get("strand"),
                                                                                         led.short),
                   "--strand naming the strand that holds the lease"),
               None if status.get("fresh") is not True else (
                   mc.LOCK_REL, "heartbeat_at", "the holder's heartbeat is %s minutes old: fresh" %
                   status.get("heartbeat_age_minutes"), "a stale holder: a live holder's run is never marked from outside")]
    run_id = status.get("run_id") if status.get("held") else None
    run = led.run(run_id) if run_id else None
    # R7: the classes a break reads are the account's after the holder's last heartbeat, never an older read
    beat_at, read_at = status.get("heartbeat_at"), data.get("read_at")
    starts = [(r.get("attempt") or {}).get("started_at") for r in led.objects.values()
              if run_id and (r.get("attempt") or {}).get("run_id") == run_id]
    if status.get("held") and not is_utc(beat_at):
        reasons.append((mc.LOCK_REL, "heartbeat_at", "the holder's heartbeat does not read (%r)" % (beat_at,),
                        "a heartbeat the inventory's read can be placed after; record.py lease repair for a "
                        "malformed lock"))
    elif status.get("held") and not after(read_at, beat_at):
        reasons.append((name, "read_at", "the inventory was read at %s, not after the holder's last heartbeat, %s" % (
            read_at, beat_at), "a read of the account made after the holder went quiet: hand a new read as "
                        "--inventory; the copy an earlier reconcile left is read only by the retry of the same call"))
    late = sorted(s for s in starts if is_utc(s) and not after(read_at, s))
    if late:
        reasons.append((name, "read_at", "the inventory was read at %s, not after the attempt of run %s that began "
                        "at %s" % (read_at, run_id, late[-1]), "a read made after every attempt of the run began"))
    refuse(*reasons)
    findings = [{"key": e["key"], "class": e["class"], "live_ids": e["live_ids"], "note": e["note"]}
                for e in plan["elements"]]
    block = {"at": mc.stamp("utc"), "mode": "classify-only", "read_at": read_at, "classes": plan["classes"],
             "findings": findings}
    missing = run_id is not None and run is None
    if missing:  # R6: run start's ledger write failed after the refresh, so nothing was written under this run
        epoch = status.get("epoch")
        run = {"id": run_id, "version": status.get("version"), "kind": "build", "session_label": status.get(
            "session_label"), "lease_epoch": epoch if is_int(epoch) else None, "another_build_running": None,
               "started_at": beat_at, "heartbeat_at": beat_at, "ended_at": None, "state": "interrupted",
               "calls_estimated": None, "calls_used": None, "account_checks": [],
               "note": "never reached the ledger: run start entered this id into the lease and its ledger write "
                       "failed, so no write was made under it; recorded by the classify-only reconcile"}
        led.build.setdefault("runs", []).append(run)
    if run is not None:
        run["state"] = "interrupted"
        run["reconcile"] = block
        led.build["updated_at"] = mc.stamp("utc")
        steps.append((led.build_rel, json_step(root, led.build_path, led.build), None))
    commit("reconcile", steps, run_id, "ledger.py reconcile --strand %s --classify-only, without --inventory: it "
           "reads the copy already made" % led.short, root)
    return 0, {"mode": "classify-only", "holder": led.short, "run_id": run_id, "run_state": run["state"] if run else None,
               "reconcile": block, "marked": run is not None, "recorded_missing_run": missing,
               "classes": plan["classes"], "elements": plan["elements"],
               "note": None if run is not None else "the lock carries no run id: no run was written, so none is marked",
               "written": {rel: mc.sha256_file(mc.record_path(root, rel)) for rel, _, _ in steps}}


# estimate (W64 to W69, A9.9): the cost table, the classification query paid once per staleness window, no credits.

ESTIMATE_COUNTS = ("used_today", "client_reserve", "items", "updates", "automation_actions_monthly", "boards_to_classify",
                   "portfolios", "doc_pages")
COST = {  # W65; complexity is reported beside the calls, never added to them
    "preflight": 12,  # A9.9: about 12 calls
    "items_per_call": 20, "updates_per_call": 40,  # create_items and update_items batches (A8.6:798, A9.9)
    "retry_share": 5,  # the high figure adds a fifth for the one different call form (A8.6:799)
    "polls_low": {"portfolio": 4, "project": 4, "vibe_app": 6}, "polls_high": {"portfolio": 12, "project": 12,
                                                                               "vibe_app": 30},  # W54's ceilings
    "checks_per": 20,  # an account check every 20 writes (SF 3)
    "audit": {"board": 3, "subitems": 3, "portfolio": 3, "project": 3, "agent": 3, "vibe_app": 1, "workflow": 1},
    "query_pages": (50, 25), "query_complexity": (3600, 5300),  # NO 2.6:57, per board
    "items_page_complexity": (167000, 334000), "unread_daily_total": 1000, "unread_warning": 250, "headroom_share": 0.3}
AI_POWERED, MAY_BE_AI = ("agent", "ai_column", "vibe_app"), ("workflow", "sequence")  # W69, A17


def open_rows(build):
    return {k: r for k, r in ((build or {}).get("objects") or {}).items() if r.get("status") in ("planned", "attempting")}


def write_figures(led, rows, items=None, updates=0):
    """(writes, read-backs, polls, account checks) as [low, high] pairs over the open rows (W65, W67). With no item
    count (a sibling strand, whose inputs this strand never sees) each item_batch row is one create_items call."""
    plain = sum(1 for r in rows.values() if r.get("type") != "item_batch")
    batches = sum(1 for r in rows.values() if r.get("type") == "item_batch")
    seeded = batches if items is None else math.ceil(items / COST["items_per_call"])
    low = plain + seeded + math.ceil(updates / COST["updates_per_call"])
    writes = [low, low + math.ceil(low / COST["retry_share"])]
    polls = [sum(COST[band].get(r.get("type"), 0) for r in rows.values()) for band in ("polls_low", "polls_high")]
    checks_low = 1 + math.ceil(low / COST["checks_per"])
    other = sum(1 for k, r in rows.items() if approval_class(r, "create", r.get("origin"), None, led) != "card")
    return writes, list(writes), polls, [checks_low, checks_low + other]


def cmd_estimate(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    led.require_build()
    inputs, name = (input_json(root, args.inputs, "--inputs") if args.inputs else ({}, "(flags)"))
    reasons = [None if not args.write or args.inputs else ("(flags)", "--write", "--write with no inputs file",
                                                           "--inputs <the preflight reads> beside --write")]
    if args.write:
        reasons.append(sha_reason(led, args.expect_sha))
    counts = {}
    for key in ESTIMATE_COUNTS + ("daily_total", "plan_allowance"):
        value = inputs.get(key)
        if value is None:
            counts[key] = None if key in ("daily_total", "plan_allowance") else 0
        elif not is_int(value) or value < 0:
            reasons.append((name, key, "%r" % (value,), "a count, 0 or more"))
        else:
            counts[key] = value
    refuse(*reasons)
    rows = open_rows(led.build)
    writes, readbacks, polls, checks = write_figures(led, rows, counts["items"], counts["updates"])
    audit = sum(COST["audit"].get(r.get("type"), 0) for r in rows.values()) + counts["doc_pages"]
    n, p = counts["boards_to_classify"], counts["portfolios"]
    index = led.index
    window = (index.get("record_provenance") or {}).get("staleness_budget_days")
    captured = index.get("captured_at")
    paid = bool(is_utc(captured) and isinstance(window, (int, float)) and
                (mc.now_utc() - mc.parse_utc(captured)).total_seconds() < window * 86400)
    query = {"calls": [0, 0] if paid else [math.ceil(n / COST["query_pages"][0]), math.ceil(n / COST["query_pages"][1])],
             "complexity": [0, 0] if paid else [COST["query_complexity"][0] * n, COST["query_complexity"][1] * n],
             "paid": paid, "window_days": window, "captured_at": captured, "page_size": list(PAGE_SIZE),
             "note": "paid once per record per staleness window: counted at nothing inside it" if paid else
             "counted here; once native-map stores this read, later estimates inside the window see it paid"}
    side = {"calls": [0, 0] if paid else [4 + p, 4 + 2 * p + math.ceil(n / COST["query_pages"][1])],
            "complexity": [0, 0] if paid else [COST["items_page_complexity"][0] * p, COST["items_page_complexity"][1] * p]}
    components = {"preflight": [COST["preflight"]] * 2, "writes": writes, "read_backs": readbacks, "polls": polls,
                  "account_checks": checks, "audit": [audit, audit]}
    calls = [sum(c[i] for c in components.values()) + query["calls"][i] + side["calls"][i] for i in (0, 1)]
    others = []
    for folder in sorted((root / "strands").iterdir()) if (root / "strands").is_dir() else []:
        short = folder.name[:3]
        if not folder.is_dir() or not re.match(r"\d{3}-", folder.name) or short == led.short:
            continue
        sibling = Ledger(root, short)
        if sibling.strand.get("state") not in ("active", "paused") or sibling.build is None:
            continue
        open_ = {k: {"type": r.get("type"), "status": r.get("status"), "origin": r.get("origin"),
                     "parent_key": r.get("parent_key")} for k, r in open_rows(sibling.build).items()}
        if not open_:
            continue
        figures = write_figures(sibling, open_)  # W67: writes, read-backs, polls and account checks only
        others.append({"strand": short, "calls": [sum(f[i] for f in figures) for i in (0, 1)]})
    daily = counts["daily_total"]
    headroom = (daily if daily is not None else COST["unread_daily_total"]) - counts["used_today"] - counts["client_reserve"]
    after_others = headroom - sum(o["calls"][1] for o in others)
    warnings = []
    if calls[1] > COST["headroom_share"] * headroom:
        warnings.append("the high figure, %d calls, is above 30%% of today's headroom of %d: offer to split the build "
                        "across days" % (calls[1], headroom))
    if daily is None and calls[1] > COST["unread_warning"]:
        warnings.append("platform_api could not be read: 1,000 calls a day are assumed, and the high figure, %d, is "
                        "above %d" % (calls[1], COST["unread_warning"]))
    monthly, allowance = counts["automation_actions_monthly"], counts["plan_allowance"]
    automation = {"monthly": monthly, "allowance": allowance, "over": None if allowance is None else monthly > allowance}
    ai = sorted((k for k, r in rows.items() if r.get("type") in AI_POWERED), key=natural)
    maybe = sorted((k for k, r in rows.items() if r.get("type") in MAY_BE_AI), key=natural)
    batch = {"create_items": math.ceil(counts["items"] / COST["items_per_call"]),
             "update_items": math.ceil(counts["updates"] / COST["updates_per_call"])}
    payload = {"calls": calls, "components": components, "batches": batch, "classification_query": query,
               "classification_side_reads": side, "automation_actions": automation, "ai_powered": ai,
               "may_be_ai_powered": [{"key": k, "note": "AI-powered when the blueprint gives them an AI step"}
                                     for k in maybe], "other_strands": others, "headroom": headroom,
               "headroom_after_others": after_others, "warnings": warnings,
               "fields_present_not_read": sorted(k for k in inputs if re.search(r"credit|price|package", str(k), re.IGNORECASE)),
               "written": {}}
    if not args.write:
        return 0, payload
    preflight = {"at": mc.stamp("utc"), "version": led.version, "daily_total": daily, "used_today": counts["used_today"],
                 "client_reserve": counts["client_reserve"], "estimated_calls": calls,
                 "roster_ok": inputs.get("roster_ok"), "stale_gotchas": list(inputs.get("stale_gotchas") or []),
                 "workspaces_ok": inputs.get("workspaces_ok"), "findings": list(inputs.get("findings") or [])}
    led.build["preflight"] = preflight
    for run in led.build.get("runs") or []:
        if run.get("state") == "running":
            run["calls_estimated"] = list(calls)
    payload["preflight"] = preflight
    payload["written"] = save_build(led, "estimate")
    return 0, payload


# The catalogue, the parser and main.

COMMANDS = {  # A5.4:356, K20: the 22 command forms
    "check": cmd_check, "bind": cmd_bind, "workspaces": cmd_workspaces, "approval": cmd_approval,
    "change-check": cmd_change_check, "run start": cmd_run_start, "run heartbeat": cmd_run_heartbeat,
    "run end": cmd_run_end, "intent": cmd_intent, "record": cmd_record, "verify": cmd_verify, "depart": cmd_depart,
    "ui-step": cmd_ui_step, "irreversible-yes": cmd_irreversible_yes, "live-map": cmd_live_map,
    "live-map set": cmd_live_map_set, "classify": cmd_classify, "native-map": cmd_native_map, "snapshot": cmd_snapshot,
    "compare": cmd_compare, "reconcile": cmd_reconcile, "estimate": cmd_estimate}
FENCED = ("workspaces", "run heartbeat", "run end", "intent", "record", "verify", "depart", "irreversible-yes")


def build_parser():
    parser = Parser(prog="ledger.py", description="The client record's ledger.")
    parser.add_argument("--record", help="the client folder (default: the current folder)")
    top = parser.add_subparsers(dest="command", metavar="command")
    top.required = True
    groups = {}
    run = top.add_parser("run").add_subparsers(dest="sub", metavar="action")
    run.required = True
    for name in COMMANDS:
        if name.startswith("run "):
            groups[name] = run.add_parser(name[4:])
        elif name == "live-map":
            groups[name] = groups["live-map set"] = top.add_parser("live-map")
            groups[name].add_argument("sub", nargs="?", choices=["set"])
        elif name != "live-map set":
            groups[name] = top.add_parser(name)
    for name in ("check", "bind", "live-map", "classify", "native-map", "estimate", "compare", "snapshot", "reconcile"):
        groups[name].add_argument("--strand")
    for name in ("workspaces", "approval", "change-check", "run start", "run heartbeat", "run end", "intent", "record",
                 "verify", "depart", "ui-step", "irreversible-yes"):
        groups[name].add_argument("--strand", required=True)
    for name in FENCED + ("run start",):
        groups[name].add_argument("--lease-epoch")
        groups[name].add_argument("--session-label")
        if name != "run start":
            groups[name].add_argument("--run-id")
    for name in ("approval", "run start", "run heartbeat", "run end", "intent", "record", "verify", "depart", "ui-step",
                 "irreversible-yes"):
        groups[name].add_argument("--expect-sha")
    groups["bind"].add_argument("--binding", required=True)
    for flag in ("--product", "--id", "--name", "--created-in", "--direction-change", "--use", "--folder", "--in-workspace"):
        groups["workspaces"].add_argument(flag)
    for flag in ("--sha256", "--words", "--session"):
        groups["approval"].add_argument(flag, required=True)
    for flag in ("--version", "--revision"):
        groups["approval"].add_argument(flag)
    for flag in ("--irreversible", "--touches", "--referenced"):
        groups["approval"].add_argument(flag, action="append")
    groups["change-check"].add_argument("--from", dest="source", required=True)
    start = groups["run start"]
    start.add_argument("--another-build-running", required=True)
    start.add_argument("--account-check", required=True)
    for flag in ("--answer-words", "--run-id"):
        start.add_argument(flag)
    start.add_argument("--kind", default="build")
    groups["run heartbeat"].add_argument("--account-check")
    groups["run heartbeat"].add_argument("--before")
    groups["run heartbeat"].add_argument("--answer-words")
    groups["run end"].add_argument("--calls-used", required=True)
    intent = groups["intent"]
    intent.add_argument("--key", required=True)
    intent.add_argument("--operation", required=True)
    for flag in ("--type", "--name", "--origin", "--parent-key", "--parent-id", "--workspace", "--approval-ref",
                 "--prompt-ref", "--ir", "--prior-state", "--source-strand", "--live-key", "--evidence", "--payload-sha",
                 "--product", "--direction-change", "--template-id"):
        intent.add_argument(flag)
    for flag in ("--scope", "--ref", "--notifies", "--assumption-ref"):
        intent.add_argument(flag, action="append")
    for flag in ("--sample-data", "--retry"):
        intent.add_argument(flag, action="store_true")
    record = groups["record"]
    record.add_argument("--key", required=True)
    for flag in ("--id", "--url", "--polled-seconds"):
        record.add_argument(flag)
    for flag in ("--item-id", "--companion"):
        record.add_argument(flag, action="append")
    for flag in ("--timed-out", "--id-from-error", "--pending"):
        record.add_argument(flag, action="store_true")
    verify = groups["verify"]
    for flag in ("--key", "--result", "--read"):
        verify.add_argument(flag, required=True)
    verify.add_argument("--note")
    depart = groups["depart"]
    for flag in ("--key", "--what", "--error-code", "--decision"):
        depart.add_argument(flag, required=True)
    depart.add_argument("--attempt", action="append")
    for flag in ("--ui-what", "--ui-owner"):
        depart.add_argument(flag)
    for flag in ("--key", "--what", "--owner", "--target-version"):
        groups["ui-step"].add_argument(flag)
    groups["ui-step"].add_argument("--done", action="store_true")
    yes = groups["irreversible-yes"]
    yes.add_argument("--key", action="append", required=True)
    for flag in ("--mode", "--what"):
        yes.add_argument(flag, required=True)
    for flag in ("--evidence", "--log-ref", "--approval-ref", "--operation"):
        yes.add_argument(flag)
    for flag in ("--key", "--constraint", "--source"):
        groups["live-map"].add_argument(flag)
    groups["classify"].add_argument("--reads", required=True)
    native = groups["native-map"]
    for flag in ("--reads", "--coverage"):
        native.add_argument(flag, required=True)
    native.add_argument("--staleness-days")
    native.add_argument("--confirm", action="append")
    groups["snapshot"].add_argument("--label", required=True)
    groups["snapshot"].add_argument("--read", required=True)
    for flag in ("--before", "--after"):
        groups["compare"].add_argument(flag, required=True)
    groups["compare"].add_argument("--appendix")
    groups["reconcile"].add_argument("--inventory")
    groups["reconcile"].add_argument("--classify-only", action="store_true")
    groups["reconcile"].add_argument("--asked-by")
    groups["estimate"].add_argument("--inputs")
    groups["estimate"].add_argument("--write", action="store_true")
    groups["estimate"].add_argument("--expect-sha")
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args, extra = parser.parse_known_args(argv)
        name = " ".join(word for word in (args.command, getattr(args, "sub", None)) if word)
        if extra:
            raise Usage("unrecognized arguments: %s" % " ".join(extra))
        if name == "live-map set" and not (args.key and args.constraint and args.source is not None and args.strand):
            raise Usage("live-map set needs --key, --constraint, --source and --strand")
        if name in ("snapshot", "reconcile", "estimate") and not args.strand:
            raise Usage("%s needs --strand" % name)
        if name == "reconcile" and args.asked_by is not None and not re.fullmatch(r"\d{3}", args.asked_by):
            raise Usage("--asked-by takes a strand's three-digit short id")
    except Usage as exc:
        emit({"ok": False, "command": None, "asked_by": None, "error": dict(zip(KEYS, (
            "ledger.py", "arguments", str(exc), parser.format_usage().strip())))})
        return 3
    asked = strand_short(args)
    try:
        root = Path(args.record) if args.record else Path.cwd()
        for needed in ("CLIENT.md", "account.json"):
            if not (root / needed).is_file():
                raise mc.CannotRun((needed, "record", "no %s in the folder %s" % (needed, root.name),
                                    "a client folder holding CLIENT.md and account.json, or --record <folder>"))
        with mc.record_mutex(root):  # W25: one hold per command, kept until it has printed
            code, payload = COMMANDS[name](root, args)
            emit(dict({"ok": code != 1, "command": name, "asked_by": asked}, **payload))
        return code
    except mc.MMBError as exc:
        emit(dict({"ok": False, "command": name, "asked_by": asked},
                  **({"refusals": exc.findings} if exc.code == 1 else {"error": exc.findings[0]}),
                  **({"committed": exc.committed} if exc.committed is not None else {})))
        return exc.code
    except Exception as exc:  # G10: anything unexpected is "could not run", still one JSON object
        emit({"ok": False, "command": name, "asked_by": asked, "error": dict(zip(KEYS, (
            "ledger.py", type(exc).__name__, str(exc) or "an internal error with no message",
            "a run without an internal error")))})
        return 3


if __name__ == "__main__":
    sys.exit(main())
