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
DIGITS = re.compile(r"[0-9]+")
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
            "doc": ("name", "workspace_id"), "automation": ("active", "updated_at"),
            "dashboard": ("name", "workspace_id", "kind"), "agent": ("state", "version_id"),
            "vibe_app": ("status", "is_published", "code_version"), "workflow": ("name", "state"),
            "group": ("title", "color", "position"), "column": ("id", "title", "type", "settings"),
            "view": ("name", "type", "settings"), "item_batch": ("item_ids",),
            "publication": ("state", "is_published"), "activation": ("state", "is_published")}
for _kind in ("subitems", "portfolio", "project"):
    IDENTITY[_kind] = IDENTITY["board"]
NOT_BUILT = ("classify", "native-map", "snapshot", "compare", "reconcile", "estimate")


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


def numeric_ids(data, path=""):
    """Dotted paths of every JSON number held under a key named id, ids, *_id or *_ids (W35)."""
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            where = "%s.%s" % (path, key) if path else str(key)
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
    return {name: obj.get(name) for name in fields} if fields else dict(obj)


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

def element_table(text):
    """(rows [(key, kind, name)], problems [text]) of the `## Element keys` table; rows None when there is none."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = next((n for n, line in enumerate(lines) if line.rstrip() == "## Element keys"), None)
    if start is None:
        return None, []
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
                return [], problems
            continue
        if cells and all(cell and set(cell) <= set("-: ") for cell in cells):
            continue
        cells += [""] * (3 - len(cells))
        key, kind, name = cells[0], cells[1], cells[2]
        if len(key) > 1 and key.startswith("`") and key.endswith("`"):
            key = key[1:-1]
        rows.append((key, kind, name))
    if header is None:
        problems.append("no table follows the heading")
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
             for where in numbers])
    return data, name


def digits(flag, value, file="(flags)"):
    return None if value is None or DIGITS.fullmatch(str(value)) else (
        file, flag, "%r is not a monday id" % value, "a string of digits, stored as given")


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


def commit(command, steps, run_id=None, next_call=None):
    """Run the writes of one call in order (W25). The first write failing is exit 3 naming its file with nothing
    committed; a later one is exit 3 with error field `committed` and the `committed` report (W33)."""
    written, lease = [], None
    for index, (rel, step, lease_mark) in enumerate(steps):
        try:
            step()
        except (OSError, mc.MMBError) as exc:
            why = exc.findings[0]["problem"] if isinstance(exc, mc.MMBError) else "%s: %s" % (type(exc).__name__, exc)
            if not written:
                if isinstance(exc, mc.MMBError):
                    raise
                raise mc.CannotRun((rel, mc.WHOLE_FILE, "could not write the file: %s; nothing was written" % why,
                                    "the same call again once no other program holds the file"))
            report = {"command": command, "written": written, "not_written": [r for r, _, _ in steps[index:]],
                      "lease": lease, "run_id": run_id, "next": next_call}
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
    return getattr(args, "strand", None)


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
               "portal_object_ids", "build_targets_by_strand", "lease", "record_provenance")
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
                ("read_values", lambda v: isinstance(v, dict)))
LIVE_CHECKS = (("monday_id", is_str), ("kind", lambda v: v in TYPES), ("name_at_build", lambda v: isinstance(v, str)),
               ("owner_strand", lambda v: isinstance(v, str) and bool(re.fullmatch(r"\d{3}", v))),
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
        for where in numeric_ids(account):
            self.block(name, where, "an id stored as a number", "every monday id a string")

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
            "dependants": ", ".join(row.get("dependants") or []) or "none", "last verified": text(row.get("last_verified"))}


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


def cmd_live_map_set(root, args):
    led = Ledger(root)
    refuse(*led.newer())
    live = led.account.get("live_objects") or {}
    row = live.get(args.key)
    source = (args.source or "").strip()
    refuse(None if row is not None else ("account.json", "live_objects." + str(args.key), "no live-map row %s" % args.key,
                                         "a qualified key of a row the live map holds"),
           None if args.constraint in CONSTRAINTS else ("account.json", "live_objects.%s.constraint" % args.key,
                                                        "%r is not a constraint" % args.constraint, " | ".join(CONSTRAINTS)),
           None if source and source != "pending strand close" and "\n" not in source else (
               "account.json", "live_objects.%s.constraint_source" % args.key, "the source is empty or the interim value",
               "a client quote with its call location, or a user decision with its log reference"),
           None if row is None or row.get("owner_strand") == args.strand else (
               "account.json", "live_objects.%s.owner_strand" % args.key, "the row was built by strand %s, not %s" % (
                   row.get("owner_strand"), args.strand), "a row this strand built: a strand edits only its own rows"))
    row["constraint"], row["constraint_source"] = args.constraint, source
    led.account["updated_at"] = mc.stamp("utc")
    steps = [("account.json", json_step(root, root / "account.json", led.account), None)]
    step = map_step(led)
    steps += [step] if step else []
    commit("live-map set", steps, next_call="ledger.py live-map, which renders the map from live_objects")
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
    if forms[0]:
        product, ws = args.product, args.id
        reasons = [None if product in ("core", "crm", "service") else (
                       "account.json", "client_workspaces", "%r is not a product" % product, "core | crm | service"),
                   digits("--id", ws) if ws else ("(flags)", "--id", "no workspace id", "the id the create returned"),
                   None if args.name and args.name.strip() else ("(flags)", "--name", "no name", "the workspace's name"),
                   None if args.created_in == led.qualified else ("(flags)", "--created-in", "%r is not this strand's "
                                                                   "version %s" % (args.created_in, led.qualified),
                                                                   led.qualified)]
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
        elif current and not args.direction_change:
            reasons.append(("account.json", "client_workspaces.%s" % product, "the client already has a %s workspace, %s"
                            % (product, current.get("id")), "one workspace per product, unless the record says the "
                            "direction changed: --direction-change with the log reference of the user's decision"))
        refuse(*reasons)
    elif forms[1]:
        refuse(digits("--use", args.use),
               None if args.use in clients else ("account.json", "guard_index.client_workspace_ids", "strand %s: "
                                                 "workspace %s is outside the client's workspaces" % (short, args.use),
                                                 A21 + ": " + (", ".join(clients) or "none")),
               None if args.use not in operational else ("account.json", "guard_index.client_workspace_ids",
                                                         "workspace %s is operational: %s" % (args.use, operational[args.use]), A21))
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
                created_in=current.get("created_in"), superseded_in=args.created_in, direction_change=args.direction_change))
        workspaces[args.product] = {"id": args.id, "name": args.name.strip(), "created_in": args.created_in}
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


def cmd_approval(root, args):
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    srel = led.rel(led.folder / "STRAND.md")
    refuse(None if led.strand.get("kind") in ("platform", "hybrid") else (
               srel, "kind", "the strand is %s: it has no ledger" % led.strand.get("kind"), "a platform or hybrid strand"),
           None if (led.account.get("account") or {}).get("id") not in (None, "unbound") else (
               "account.json", "account.id", "the record is not bound to an account", "ledger.py bind first"))
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
    table = {key: (kind, name) for key, kind, name in rows}
    irreversible = list(args.irreversible or [])
    for key in irreversible:
        if key not in table:
            reasons.append(("(flags)", "--irreversible", "%s is not a row of the element-key table" % key, "a key of the table"))
        elif table[key][0] in LIST_TYPES:
            reasons.append(("(flags)", "--irreversible", "%s is a %s, a list" % (key, table[key][0]),
                            "an irreversible step; automations, workflows, agents and sequences are lists"))
    for key, (kind, _) in table.items():
        if kind in MUST_LIST and key not in irreversible:
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
    entry["rests_on"] = {"clearance": led.strand.get("clearance"), "purpose": purpose, "assumptions": counts["AS"],
                         "assumed_terms": counts["AT"], "forks_on_leaning": counts["FK"]}
    entry["live_objects_touched"] = touched
    b.setdefault("approvals", []).append(entry)
    delta = {"new": [], "kept": [], "replanned": [], "not_in_table": []}
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
        else:
            delta["kept"].append(key)
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

def next_run_id(root):
    date, highest = mc.stamp("utc")[:10], 0
    base = root / "strands"
    for folder in sorted(base.iterdir()) if base.is_dir() else []:
        path = folder / "solution" / "build.json"
        if folder.is_dir() and path.is_file():
            for run in mc.read_json(path, mc.relative(root, path)).get("runs") or []:
                match = re.fullmatch(r"run-(\d{4}-\d{2}-\d{2})-(\d+)", str((run or {}).get("id")))
                if match and match.group(1) == date:
                    highest = max(highest, int(match.group(2)))
    return "run-%s-%d" % (date, highest + 1)


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
    run_id, now = args.run_id or next_run_id(root), mc.stamp("utc")
    yes = args.another_build_running == "yes"
    answer = "%s, answered %s" % (args.another_build_running, local_minute_of_day()) + (
        ": %s" % args.answer_words.strip() if yes else "")
    preflight = b.get("preflight") or {}
    epoch = int(args.lease_epoch) if DIGITS.fullmatch(str(args.lease_epoch)) else args.lease_epoch
    interrupted = []
    for run in b.setdefault("runs", []):
        if run.get("state") == "running" and run.get("id") != run_id:
            run["state"] = "interrupted"
            interrupted.append(run.get("id"))
    run = {"id": run_id, "version": version, "kind": "build", "session_label": args.session_label, "lease_epoch": epoch,
           "another_build_running": answer, "started_at": now, "heartbeat_at": now, "ended_at": now if yes else None,
           "state": "ended" if yes else "running",
           "calls_estimated": preflight.get("estimated_calls") if preflight.get("version") == version else None,
           "calls_used": 0 if yes else None, "account_checks": [{"at": now, "before": "run start", "result": "match"}]}
    b["runs"].append(run)
    if not yes:
        b["lease_epoch_at_run"] = epoch
    b["updated_at"] = now
    build_step = (led.build_rel, json_step(root, led.build_path, b), None)
    if yes:
        commit("run start", [build_step, (mc.LOCK_REL, lambda: mc.lease_release(root, args.lease_epoch, args.session_label),
                                          {"released": {"epoch": epoch}})], run_id,
               "record.py lease release --epoch %s --label %s" % (args.lease_epoch, args.session_label))
    else:
        commit("run start", [(mc.LOCK_REL, lambda: mc.lease_refresh(root, args.lease_epoch, args.session_label, run_id),
                              {"refreshed": {"epoch": epoch, "session_label": args.session_label, "run_id": run_id}}),
                             build_step], run_id,
               "ledger.py run start --strand %s --lease-epoch %s --session-label %s --another-build-running no "
               "--account-check match --run-id %s, with the ledger's current sha" % (
                   led.short, args.lease_epoch, args.session_label, run_id))
    recovery = interrupted or [k for k, row in led.objects.items() if row.get("status") == "attempting"]
    return 0, {"run_id": run_id, "epoch": epoch, "session_label": args.session_label, "state": run["state"],
               "another_build_running": answer, "interrupted": interrupted, "recovery_first": bool(recovery),
               "released": yes, "written": {led.build_rel: mc.sha256_file(led.build_path)},
               "carry": None if yes else "hold the run id beside the epoch and the label: every fenced write presents all three",
               "log": [entry_log(led.short, "build", version, run_id, ["stopped: another build is running", "lease "
                                 "released, epoch %s" % epoch] if yes else ["run started"])]}


def fenced(root, args, states=("running",)):
    """The common opening of a fenced strand command (W28): newer schemas, the three flags, the sha, the holder and
    the run, each refused before anything is written. Returns the Ledger."""
    led = Ledger(root, args.strand)
    refuse(*led.newer())
    led.require_build()
    reasons = flatten(fence_flags(args), sha_reason(led, args.expect_sha), holder_reasons(root, led.short))
    if args.run_id:
        reasons += run_reasons(led, args.run_id, states)
    refuse(*reasons)
    return led


def cmd_run_heartbeat(root, args):
    led = fenced(root, args)
    refuse(None if args.account_check in (None, "match", "mismatch") else (
               "(flags)", "--account-check", "%r" % args.account_check, "match | mismatch"),
           None if not args.account_check or (args.before or "").strip() else (
               "(flags)", "--before", "no step named", "what the check came before, such as writes 21 to 40"))
    fence(root, args)
    led.reload()
    beat(led, args.run_id)
    run = led.run(args.run_id)
    if args.account_check:
        run.setdefault("account_checks", []).append({"at": mc.stamp("utc"), "before": args.before.strip(),
                                                     "result": args.account_check})
    written = save_build(led, "run heartbeat", args.run_id)
    return 0, {"run_id": args.run_id, "heartbeat_at": run["heartbeat_at"], "stop": args.account_check == "mismatch",
               "written": written}


def live_rows(led):
    """W60, W61: the live_objects rows `run end` writes or refreshes from the strand's verified rows."""
    live = led.account.setdefault("live_objects", {})
    native = (led.index.get("native_board_index") or {})
    created, refreshed, archived = [], [], []
    verified = {k: r for k, r in led.objects.items() if r.get("status") == "verified" and r.get("type") != "item_batch"}
    for key, row in sorted(verified.items()):
        verify = row.get("verify") or {}
        kind = row.get("type")
        if kind in ACCOUNT_LEVEL or (row.get("workspace_scope") and not row.get("workspace")):
            workspace = "account: %s" % "; ".join(row.get("workspace_scope") or [])
        elif kind == "workspace":
            workspace = row.get("id")
        else:
            workspace = led.row_workspace(key)
        fresh = {"monday_id": row.get("id"), "kind": kind, "workspace": workspace, "state": row.get("state") or "active",
                 "digest": verify.get("digest"), "last_verified": local_date(verify["at"]) if is_utc(verify.get("at")) else None,
                 "dependants": sorted("%s:%s" % (led.short, k) for k, r in verified.items() if r.get("parent_key") == key)}
        if row.get("origin") == "other-strand-modified":
            target = live.get(row.get("live_key"))
            if target is not None:
                target.update({k: v for k, v in fresh.items() if k != "dependants"})
                live[row["live_key"]] = full_live(target)
                refreshed.append(row["live_key"])
            continue
        qkey = "%s:%s" % (led.short, key)
        if qkey in live:
            live[qkey].update(fresh)
            live[qkey] = full_live(live[qkey])
            refreshed.append(qkey)
            continue
        built = ("native" if str(row.get("id")) in native else "client") if row.get("origin") in (
            "pre-existing-referenced", "pre-existing-modified") else "%s/%s" % (led.short, row.get("introduced_in"))
        live[qkey] = full_live(dict(fresh, name_at_build=row.get("name"), owner_strand=led.short, introduced_in=built,
                                    constraint="change-with-own-yes", constraint_source="pending strand close"))
        created.append(qkey)
    for key, row in sorted(led.objects.items()):
        qkey = row.get("live_key") if row.get("origin") == "other-strand-modified" else "%s:%s" % (led.short, key)
        if row.get("status") == "removed" and qkey in live and live[qkey].get("state") != "archived":
            live[qkey]["state"] = "archived"
            archived.append(qkey)
    return {"created": created, "refreshed": refreshed, "archived": archived}


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
           "and releasing the lease (ledger.py run end --strand %s --run-id %s ...)" % (led.short, args.run_id))
    return 0, {"run_id": args.run_id, "state": "ended", "calls_used": int(used), "live_rows": rows, "released": True,
               "written": {rel: mc.sha256_file(mc.record_path(root, rel)) for rel, _, _ in steps if rel != mc.LOCK_REL},
               "log": [entry_log(led.short, "build", led.version, args.run_id, [
                   "run ended, calls used %s" % used, "lease released, epoch %s" % epoch])],
               "next": "set version.md state built through record.py guard, and write the log entry through record.py log"}


# intent (W07, W10, W41, W47, W48, W50).

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
    led = fenced(root, args)
    b, key, op, rel = led.build, args.key, args.operation, led.build_rel
    field = "objects." + str(key)
    refuse(None if op in OPERATIONS else ("(flags)", "--operation", "%r" % op, " | ".join(OPERATIONS)),
           None if op != "delete" else (rel, field + ".operation", "a delete: v1 never deletes any object, in any account",
                                        "archive, with its own yes and containment evidence"))
    row = led.objects.get(key)
    new = row is None
    if new:
        match = re.fullmatch(r"(B\d+)\.IB\d+", str(key))
        board = led.objects.get(match.group(1)) if match else None
        refuse(None if board is not None and board.get("type") == "board" else (
            rel, field, "no planned row %s: the key is in no approved revision of this strand" % key,
            "a key of an approved element-key table, or an item batch B<n>.IB<n> of a board row of this strand"))
        row = new_row("item_batch", key, args.name or "%s sample items" % board.get("name"), led.version, None)
        current = [a for a in b.get("approvals") or [] if a.get("version") == led.version]
        row["approval_ref"] = ("%sr%s" % (led.version, current[-1].get("revision"))) if current else board.get("approval_ref")
        row["blueprint_ref"] = None
    kind = row.get("type")
    reasons = [None if not args.type or args.type == kind else (rel, field + ".type", "%s given, %s planned" % (
        args.type, kind), "the planned type")]
    if op in FIT and kind not in FIT[op]:
        reasons.append(("(flags)", "--operation", "%s on a %s row" % (op, kind), "%s only on a %s row" % (
            op, " or ".join(FIT[op]))))
    if kind in ("activation", "publication") and op not in ("activate", "publish", "archive"):
        reasons.append(("(flags)", "--operation", "%s on a %s row" % (op, kind), "activate or publish"))
    move, status_before = intent_move(led, key, row, op, args.retry), row.get("status")
    if move:
        reasons.append((rel, field + ".status", move, "a move of the status chain record-map.md gives"))
    # approval and the frozen table (W07, W43, W47)
    ref = args.approval_ref or row.get("approval_ref")
    entry = led.approval(ref) if ref else None
    if not ref:
        reasons.append((rel, field + ".approval_ref", "the row has no approval_ref", "the vNrM of the approval that "
                        "planned it, given as --approval-ref or kept from the planned row"))
    elif entry is None:
        reasons.append((rel, field + ".approval_ref", "%s resolves to no approval of this ledger" % ref,
                        "the vNrM of an approval entry of this build.json"))
    elif kind != "item_batch":
        text, frel = led.frozen(entry)
        rows = element_table(text)[0] if text is not None else None
        table = {k: (kd, nm) for k, kd, nm in rows or []}
        if rows is None:
            reasons.append((frel, "## Element keys", "the frozen revision has no element-key table, so %s cannot be "
                            "matched to it" % key, "a revision approved with the ## Element keys table"))
        elif key not in table:
            reasons.append((frel, "## Element keys", "%s is not a row of %s" % (key, ref), "a key of that revision's table"))
        elif table[key][0] != kind:
            reasons.append((frel, "## Element keys", "%s is a %s there, a %s here" % (key, table[key][0], kind), "the same kind"))
        elif op == "create" and (args.name or row.get("name")) != table[key][1]:
            reasons.append((frel, "## Element keys", "the name %r is not the approved %r" % (
                args.name or row.get("name"), table[key][1]), "the planned name"))
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
    elif args.source_strand or args.live_key:
        reasons.append((rel, field + ".source_strand", "--source-strand or --live-key on a %s row" % origin,
                        "only on an other-strand-modified row"))
    # parent (K132, K179, W58)
    parent_key = args.parent_key if args.parent_key is not None else row.get("parent_key")
    parent_id = args.parent_id or row.get("parent_id")
    reasons.append(digits("--parent-id", args.parent_id))
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
        workspace = args.workspace or row.get("workspace") or (led.row_workspace(parent_key) if parent_key and ":" not in
                                                               str(parent_key) else None)
        if workspace is None and parent_key and ":" in str(parent_key):
            target = live.get(parent_key) or {}
            workspace = target.get("monday_id") if target.get("kind") == "workspace" else target.get("workspace")
        if not workspace:
            reasons.append((rel, field + ".workspace", "the row has no workspace", "--workspace, one of this strand's "
                            "build targets"))
        else:
            workspace = str(workspace)
            reasons.append(scope_reason(led, workspace, "the target workspace", led.targets(),
                                        "guard_index.build_targets_by_strand.%s" % led.short))
    refs = list(args.ref or row.get("refs") or [])
    for item in refs:
        match = re.fullmatch(r"(board|workspace|doc|view|column):(\d+)", item)
        if not match:
            reasons.append(("(flags)", "--ref", "%r" % item, "<board|workspace|doc|view|column>:<id>"))
        elif match.group(1) == "workspace":
            reasons.append(scope_reason(led, match.group(2), "the referenced workspace", led.client_ids,
                                        "guard_index.client_workspace_ids"))
        else:
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
    # recipients, sample data, assumptions, prompt, --ir
    notifies = list(args.notifies or row.get("notifies") or [])
    reasons += [None if RECIPIENT.fullmatch(n) else ("(flags)", "--notifies", "%r" % n, "a user id, team:<id> or "
                                                     "email:<address>") for n in notifies]
    if kind == "sequence" and not notifies:
        reasons.append((rel, field + ".notifies", "a sequence with no recipients", "every recipient, shown at approval"))
    real = [n for n in notifies if n != led.bound_user]
    if kind == "item_batch" and not args.sample_data:
        reasons.append(("(flags)", "--sample-data", "a seed batch without the flag", "--sample-data: a seed batch is "
                        "sample data"))
    if kind != "item_batch" and args.sample_data:
        reasons.append(("(flags)", "--sample-data", "on a %s row" % kind, "only on an item batch"))
    if kind == "workspace" and op == "create" and args.product not in ("core", "crm", "service"):
        reasons.append(("(flags)", "--product", "%r on a workspace create" % args.product,
                        "core | crm | service: the product the workspace is for"))
    if kind != "workspace" and args.product:
        reasons.append(("(flags)", "--product", "on a %s row" % kind, "only on a workspace row"))
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
    # the class and its yes (W10, W45, W48)
    cls = approval_class(dict(row, parent_key=parent_key), op, origin, args.ir, led)
    mode = (entry or {}).get("approval_mode") or "per-list"
    need = yes_needed(cls, mode, str(key), real)
    run = led.run(args.run_id) or {}
    yes = [e for e in b.get("irreversible_yes") or [] if e.get("key") == key and e.get("mode") in ("per-item", "grouped")
           and str(e.get("at") or "") >= str(run.get("started_at") or "9999")]
    chosen = [e for e in yes if e.get("mode") == need] if need else yes
    if need and not chosen:
        reasons.append((rel, "irreversible_yes", "%s needs its own %s yes in this run (class %s, mode %s%s)" % (
            key, need, cls, mode, ", it notifies %s" % ", ".join(real) if real else ""),
            "ledger.py irreversible-yes --key %s --mode %s in this run: a yes never carries to another run" % (key, need)))
    evidence = (chosen[-1].get("evidence") if chosen else None) or args.evidence
    if cls == "removed" and not (evidence and evidence.strip()):
        reasons.append((rel, "irreversible_yes", "an archive of %s with no containment evidence" % key,
                        "the evidence that nothing else uses it, on the yes or as --evidence"))
    refuse(*reasons)
    fence(root, args)
    led.reload()
    b = led.build
    row = ordered_row(led.objects.get(key) or row)
    now = mc.stamp("utc")
    payload = {"key": key, "type": kind, "operation": op, "name": row.get("name"), "parent_id": parent_id,
               "workspace": workspace, "workspace_scope": sorted(scope), "refs": sorted(refs),
               "notifies": sorted(notifies), "payload_sha256": args.payload_sha}
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
    card = mode == "own-account-poc" and cls != "card" and not need and not yes
    if card:
        b.setdefault("irreversible_yes", []).append({"key": key, "what": "%s %s %s" % (op, kind, row.get("name")),
                                                     "at": now, "mode": "card", "approval_ref": ref,
                                                     "evidence": (args.evidence or "").strip() or None, "log_ref": None})
    beat(led, args.run_id)
    written = save_build(led, "intent", args.run_id)
    return 0, {"key": key, "status": "attempting", "class": cls, "approval_mode": mode, "yes": need or (
        "card" if card else None), "attempt": row["attempt"], "irreversible": row["irreversible"], "written": written}


# record, verify (W50 to W54).

def cmd_record(root, args):
    led = fenced(root, args)
    rel, key = led.build_rel, args.key
    field = "objects." + str(key)
    row = led.objects.get(key)
    refuse(None if row is not None else (rel, field, "no row %s" % key, "a row of this ledger"))
    kind, attempt = row.get("type"), row.get("attempt") or {}
    op = attempt.get("operation")
    items = list(args.item_id or [])
    companions = {}
    reasons = [None if row.get("status") == "attempting" else (
        rel, field + ".status", "row %s is %s; record moves only an attempting row" % (key, row.get("status")),
        "ledger.py intent first"), None if kind in KEY_IDS and re.fullmatch(r"[A-Za-z0-9_]+", str(args.id or "x"))
        else digits("--id", args.id)] + [digits("--item-id", item) for item in items]
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
    if landed and op != "archive" and not (args.id or items or (kind in ("publication", "activation") and row.get("id"))):
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
    if row.get("origin") == "pre-existing-referenced" and row.get("status") == "planned":
        if not (DIGITS.fullmatch(str(obj.get("id") or "")) and DIGITS.fullmatch(str(obj.get("workspace_id") or ""))):
            found.append((rel, field, "the read does not show the object's id and workspace",
                          "object.id and object.workspace_id, the read that proves it exists"))
        if result not in ("match", "mismatch"):
            found.append((rel, field, "%s on a referenced row" % result, "match or mismatch"))
    return found


def cmd_verify(root, args):
    led = fenced(root, args)
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
    row["verify"] = {"read": data["read"], "at": now, "result": result, "digest": digest(str(key).lower(), identity(kind, obj)),
                     "note": note}
    if referenced:
        row.update(id=str(obj["id"]), workspace=str(obj["workspace_id"]), status="verified" if result == "match" else "mismatch")
    elif status == "written":
        row["status"] = {"match": "verified", "mismatch": "mismatch"}.get(result, "written")
    state = str(obj.get("state") or "").lower()
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
    beat(led, args.run_id)
    written = save_build(led, "verify", args.run_id)
    extra = [t for t in obj.get("triggers") or [] if kind == "agent" and str(t if not isinstance(t, dict) else t.get(
        "name")) not in DEFAULT_TRIGGERS]
    return 0, {"key": key, "status": row["status"], "result": result, "digest": row["verify"]["digest"],
               "note": note, "triggers_beyond_defaults": extra, "written": written}


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
               "(flags)", "--ui-what", "a UI step decision without its step and owner", "--ui-what and --ui-owner"))
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
    led = fenced(root, args)
    rel = led.build_rel
    keys = list(args.key or [])
    reasons = [None if args.mode in ("per-item", "grouped") else ("(flags)", "--mode", "%r" % args.mode,
                                                                  "per-item | grouped"),
               None if (args.what or "").strip() else ("(flags)", "--what", "no step said", "the step in plain words"),
               None if not re.search(r"\barchiv", args.what or "", re.I) or (args.evidence or "").strip() else (
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
                        "log_ref": (args.log_ref or "").strip() or None})
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


# The catalogue, the parser and main.

COMMANDS = {  # A5.4:356, K20: the 22 command forms; part 2 fills in the six left None
    "check": cmd_check, "bind": cmd_bind, "workspaces": cmd_workspaces, "approval": cmd_approval,
    "change-check": cmd_change_check, "run start": cmd_run_start, "run heartbeat": cmd_run_heartbeat,
    "run end": cmd_run_end, "intent": cmd_intent, "record": cmd_record, "verify": cmd_verify, "depart": cmd_depart,
    "ui-step": cmd_ui_step, "irreversible-yes": cmd_irreversible_yes, "live-map": cmd_live_map,
    "live-map set": cmd_live_map_set, "classify": None, "native-map": None, "snapshot": None, "compare": None,
    "reconcile": None, "estimate": None}
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
    groups["run end"].add_argument("--calls-used", required=True)
    intent = groups["intent"]
    intent.add_argument("--key", required=True)
    intent.add_argument("--operation", required=True)
    for flag in ("--type", "--name", "--origin", "--parent-key", "--parent-id", "--workspace", "--approval-ref",
                 "--prompt-ref", "--ir", "--prior-state", "--source-strand", "--live-key", "--evidence", "--payload-sha",
                 "--product"):
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
    for flag in ("--evidence", "--log-ref", "--approval-ref"):
        yes.add_argument(flag)
    for flag in ("--key", "--constraint", "--source"):
        groups["live-map"].add_argument(flag)
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args, extra = parser.parse_known_args(argv)
        name = " ".join(word for word in (args.command, getattr(args, "sub", None)) if word)
        if extra and COMMANDS.get(name) is not None:
            raise Usage("unrecognized arguments: %s" % " ".join(extra))
        if name == "live-map set" and not (args.key and args.constraint and args.source is not None and args.strand):
            raise Usage("live-map set needs --key, --constraint, --source and --strand")
    except Usage as exc:
        emit({"ok": False, "command": None, "asked_by": None, "error": dict(zip(KEYS, (
            "ledger.py", "arguments", str(exc), parser.format_usage().strip())))})
        return 3
    asked = strand_short(args)
    try:
        if COMMANDS[name] is None:
            raise mc.CannotRun(("ledger.py", name, "%s is not built yet" % name, "ledger.py part 2 (WP3 step 6)"))
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
