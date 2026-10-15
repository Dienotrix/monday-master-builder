"""Shared library for the monday Master Builder scripts (ARCHITECTURE 5.3 and 5.4, WP2 decisions).

Flat front matter read and write, sha256, the backup-then-overwrite-in-place write, home and record
paths as path objects, the plugin version, the record mutex, and the lease primitives, the only code
that writes .work/lock.json and its two mirrors. A library with no subcommands. Standard library only,
Python 3.9 and later, the same behaviour on Windows and macOS; nothing here deletes or renames a file.
Errors carry (file, field, problem, expected) findings: Refusal exits 1, CannotRun exits 3 (G10).
"""
import sys
sys.dont_write_bytecode = True  # no cache beside the scripts (G49); callers set it before importing
import contextlib, errno, hashlib, json, os, posixpath, re, secrets, threading, time  # noqa: E401,E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path, PurePosixPath  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOME_FOLDERS = ("clients", "cards", "monday-knowledge", "sandbox", "archive", "local")
SCHEMAS = {"client": 2, "strand": 1, "log": 1, "lock": 2, "account": 1, "build": 2, "summary": 1, "version": 1,
           "readiness": 1, "scope": 1, "live-map": 1, "status": 1, "history": 1, "settings": 1}
FORMATS = {"utc": "%Y-%m-%dT%H:%M:%SZ", "backup": "%Y%m%dT%H%M%S%fZ", "minute": "%Y-%m-%dT%H:%M",
           "log": "%Y-%m-%d %H:%M", "date": "%Y-%m-%d", "label": "%Y%m%d-%H%M"}
STALE_SECONDS, MUTEX_TIMEOUT, MUTEX_RETRY, LABEL_CHARS = 3600, 30.0, 0.05, "abcdefghijklmnopqrstuvwxyz0123456789"
CLOCK_SKEW = 300  # seconds a heartbeat may sit ahead of this clock before the two clocks are said to disagree
LOCK_FIELDS = ("strand", "strand_title", "version", "run_id", "session_label", "taken_at", "heartbeat_at")
STATUS_FIELDS = ("strand", "strand_title", "version", "session_label", "run_id", "taken_at", "heartbeat_at")
KEY_LINE = re.compile(r'^([a-z_][a-z0-9_]*):[ \t]*"((?:[^"\\]|\\.)*)"[ \t]*(?:#.*)?$')
LOCK_REL, _HELD, WHOLE_FILE = ".work/lock.json", {}, "(whole file)"  # WHOLE_FILE: the field of an unreadable file (C21)
LOCK_STATES, TAKEABLE = ("none", "held", "released", "broken"), ("none", "released", "broken")
EVENTS, LABEL_FORM = ("taken", "released", "broken", "parked", "repaired"), re.compile(r"\d{8}-\d{4}-[a-z0-9]{4}")
REPAIR = "record.py lease repair, with the user's yes, rebuilds a missing, torn or malformed lock"


class MMBError(Exception):
    """A stop carrying (file, field, problem, expected) findings; `code` is the exit code."""
    code = 3

    def __init__(self, *findings, committed=None):
        self.findings = [dict(zip(("file", "field", "problem", "expected"), f)) for f in findings]
        self.committed = committed  # what a lease change committed before a later write failed (finding 4)
        super().__init__("; ".join("%s: %s: %s (expected %s)" % tuple(f) for f in findings))


class Refusal(MMBError):
    """Blocking: the call was refused and no file changed (exit 1)."""
    code = 1


class FrontMatterError(Refusal):
    """Front matter that does not parse: refused for a write, blocking in `check` (G38)."""


class CannotRun(MMBError):
    """A file missing or unreadable, malformed JSON, a mutex timeout (exit 3)."""


# Time (G40): UTC stamps in JSON and for every age; local time, no zone, for what the user reads.

def now_utc():
    """The one clock. Tests patch it in process; shipped code has no override."""
    return datetime.now(timezone.utc)

def stamp(kind, moment=None):
    """`utc` and `backup` in UTC; `minute`, `log`, `date` and `label` in the machine's local time."""
    zone = timezone.utc if kind in ("utc", "backup") else None
    return (moment or now_utc()).astimezone(zone).strftime(FORMATS[kind])

def parse_utc(text):
    return datetime.strptime(text, FORMATS["utc"]).replace(tzinfo=timezone.utc)

def heartbeat_age(text):
    """(whole minutes elapsed, stale) for a UTC stamp; stale means more than 3,600 seconds (C95). A stamp more than
    CLOCK_SKEW ahead of this clock gives minus the whole minutes it lies ahead and reads as not fresh, because the
    clocks disagree and it proves nothing about the holder; within the skew it reads as 0 minutes old."""
    seconds = (now_utc() - parse_utc(text)).total_seconds()
    if seconds < -CLOCK_SKEW:
        return -int(-seconds // 60), True
    return max(0, int(seconds // 60)), seconds > STALE_SECONDS

def heartbeat_words(age, stale):
    """A heartbeat as messages state it: "N minutes old: fresh" or "...: stale", or how far ahead it lies."""
    if age < 0:
        return "%d minutes ahead of this machine's clock: the clocks disagree, so it is not read as fresh" % -age
    return "%d minutes old: %s" % (age, "stale" if stale else "fresh")


# Paths: the home, the plugin, references inside a record.

def home():
    """MMB_HOME when set, else `monday-builder` under the home directory the standard library reports."""
    value = os.environ.get("MMB_HOME")
    return Path(value) if value else Path.home() / "monday-builder"

def read_settings():
    """local/settings.json under the home as a dict, or None while there is none."""
    path = home() / "local" / "settings.json"
    return read_json(path, "local/settings.json") if path.exists() else None

def plugin_version(plugin_root=None):
    """`version` from .claude-plugin/plugin.json under the plugin root found from this file (G36)."""
    version = read_json((plugin_root or PLUGIN_ROOT) / ".claude-plugin" / "plugin.json", "plugin.json").get("version")
    if not isinstance(version, str) or not version:
        raise CannotRun(("plugin.json", "version", "no version", "a version string"))
    return version

def record_path(root, reference, base=""):
    """A record-relative reference written with `/` (in folder `base`) as a path under `root`, `..` folded
    on paper so the tree resolves alike under any path flavour (C07); absolute or escaping refuses."""
    text = reference.replace("\\", "/")
    if text.startswith("/") or re.match(r"[A-Za-z]:", text):
        raise Refusal((reference, "path", "an absolute path", "a path relative to the record"))
    parts = PurePosixPath(posixpath.normpath(posixpath.join(base, text))).parts
    if parts[:1] == ("..",):
        raise Refusal((reference, "path", "the path leaves the record", "a path inside the record"))
    return root.joinpath(*(part for part in parts if part != "."))

def relative(root, path):
    """`path` relative to `root` in POSIX spelling, as messages and backups name it (G10)."""
    return path.relative_to(root).as_posix()

def strand_dir(root, short_id):
    """strands/<NNN-topic>/ for a three-digit short id; refuses an id with no folder."""
    found = [p for p in sorted((root / "strands").glob("%s-*" % short_id)) if p.is_dir()] \
        if re.fullmatch(r"\d{3}", str(short_id)) else []
    if not found:
        raise Refusal(("strands/", "strand", "no strand %s in this record" % short_id, "a strand's short id"))
    return found[0]


# Reading, hashing, writing: read either line ending, write UTF-8 with LF and no BOM (G11, G39, G60).

def read_text(path, name=None):
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise CannotRun((name or path.name, WHOLE_FILE, "cannot read the file: %s" % exc, "a readable UTF-8 file"))

def read_json(path, name=None):
    try:
        return json.loads(read_text(path, name))
    except ValueError as exc:
        raise CannotRun((name or path.name, WHOLE_FILE, "not valid JSON: %s" % exc, "a JSON object"))

def json_text(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

def sha256_file(path):
    """sha256 of the file's bytes as stored: the one file hash."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()

def sha256_text(text):
    """sha256 of parsed text: LF endings, trailing blank lines dropped, every line ended by LF (G08)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return hashlib.sha256("".join(line + "\n" for line in lines).encode("utf-8")).hexdigest()

def backup_file(path, root, backup_dir=None):
    """Copy the old bytes to <backup_dir or root/.work/backup>/<path from root>.<UTC stamp>, `-2` on a clash."""
    target = (backup_dir or root / ".work" / "backup").joinpath(*path.relative_to(root).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    name, data, count = "%s.%s" % (target.name, stamp("backup")), path.read_bytes(), 1
    while True:
        candidate = target.parent / (name if count == 1 else "%s-%d" % (name, count))
        try:
            with open(candidate, "xb") as handle:
                handle.write(data)
            return candidate
        except FileExistsError:
            count += 1

def write_file(path, data, root, backup=True, backup_dir=None):
    """Text (as LF UTF-8) or bytes into `path`. An existing file is backed up, then truncated and rewritten
    in place, never renamed or deleted (C14, C15); a new one is created exclusively."""
    data = data.replace("\r\n", "\n").encode("utf-8") if isinstance(data, str) else data
    exists = path.exists()
    if exists and backup:
        backup_file(path, root, backup_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb" if exists else "xb") as handle:
        handle.write(data)

def guarded_write(path, data, root, expect_sha):
    """Rewrite `path` only while its sha256 is still `expect_sha` (None: it must not exist yet), under the mutex."""
    with record_mutex(root):
        found = sha256_file(path) if path.exists() else None
        if found != expect_sha:
            raise Refusal((relative(root, path), "sha256", "the file changed since it was read (now %s)"
                           % (found or "absent"), "the file as read (%s); re-read it" % (expect_sha or "absent")))
        write_file(path, data, root)


# Flat front matter (G38): `key: "value"` lines, `\"` and `\\` escaped, comments and blank lines kept.

def _parse(text, name):
    lines = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[0].rstrip() != "---":
        raise FrontMatterError((name, "---", "no front matter", "a first line ---"))
    fields = {}
    for number, line in enumerate(lines[1:], 1):
        if line.rstrip() == "---":
            if not fields:
                raise FrontMatterError((name, "schema", "no schema key", 'schema: "<name>/<n>" first'))
            return fields, lines, number
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, match = line.split(":", 1)[0].strip(), KEY_LINE.match(line)
        problem = ('line %d is not key: "value"' % (number + 1) if not match else "the key repeats"
                   if key in fields else "schema is not the first key" if not fields and key != "schema" else None)
        if problem:
            raise FrontMatterError((name, key, problem, 'one key per line, "schema" first, every value quoted'))
        fields[key] = re.sub(r'\\(["\\])', r"\1", match.group(2))
    raise FrontMatterError((name, "---", "no closing ---", "a closing --- line"))

def front_matter(text, name=""):
    """The front matter as {key: value} in file order, values unescaped."""
    return _parse(text, name)[0]

def split_front_matter(text, name=""):
    """(front matter, body), the body being the text after the closing ---."""
    fields, lines, end = _parse(text, name)
    return fields, "\n".join(lines[end + 1:])

def set_front_matter(text, updates, name=""):
    """The text, with LF endings, with `updates` set and every other byte kept: only the quoted value of a set
    line changes, a new key goes before the closing ---, and `updated` takes the local minute when a value
    changes and the file has it (C11)."""
    fields, lines, end = _parse(text, name)
    changes = {key: str(value) for key, value in updates.items() if fields.get(key) != str(value)}
    if changes and "updated" in fields and "updated" not in updates:
        changes["updated"] = stamp("minute")
    for key, value in changes.items():
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", key) or "\n" in value or "\r" in value:
            raise Refusal((name, key, "not a one-line value under a lowercase key", 'key: "one line"'))
    quoted = {key: value.replace("\\", "\\\\").replace('"', '\\"') for key, value in changes.items()}
    for index in range(1, end):
        match = KEY_LINE.match(lines[index])
        if match and match.group(1) in quoted:
            lines[index] = lines[index][:match.start(2)] + quoted.pop(match.group(1)) + lines[index][match.end(2):]
    lines[end:end] = ['%s: "%s"' % item for item in quoted.items()]
    return "\n".join(lines)

def schema_newer(found, expected):
    """True when `found` (such as "client/3") is newer than the known `expected` schema, or another (G57)."""
    name, _, number = str(found).partition("/")
    return name != expected or not number.isdigit() or int(number) > SCHEMAS[expected]

def require_schema(found, expected, name):
    if schema_newer(found, expected):
        raise Refusal((name, "schema", "schema %s is newer than this plugin's or not this file's" % found,
                       "%s/%d" % (expected, SCHEMAS[expected])))


# The record mutex (G09): a byte-0 lock on .work/record.mutex, a zero-byte file never deleted. The two
# branches are the tested per-system implementation A24 allows; a real Windows run exercises the first.

def _os_lock(handle, take):
    """Lock or unlock byte 0. A take returns False only when another holder has the byte; any other failure, such
    as a file system without locks, is exit 3 naming it, never read as contention (review finding 8)."""
    busy = (errno.EACCES, getattr(errno, "EDEADLOCK", errno.EDEADLK)) if os.name == "nt" else (errno.EWOULDBLOCK,
                                                                                                  errno.EAGAIN)
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK if take else msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), (fcntl.LOCK_EX | fcntl.LOCK_NB) if take else fcntl.LOCK_UN)
        return True
    except OSError as exc:
        if take and exc.errno in busy:
            return False
        if not take:
            raise
        raise CannotRun((".work/record.mutex", "lock", "the record mutex cannot be locked here: %s" % exc,
                         "a record folder on a local disk whose file system supports file locks"))

@contextlib.contextmanager
def record_mutex(root, timeout=None):
    """Hold the record mutex: re-entrant within a thread, retried every 50 ms, exit 3 after 30 seconds."""
    path = root / ".work" / "record.mutex"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Resolved and case-folded, so two spellings of one folder (a link, a drive-letter case, an 8.3 name) share a key.
    key = (os.path.normcase(str(path.parent.resolve() / path.name)), threading.get_ident())
    if key in _HELD:
        yield
        return
    with open(path, "a+b") as handle:
        deadline = time.monotonic() + (MUTEX_TIMEOUT if timeout is None else timeout)
        while not _os_lock(handle, True):
            if time.monotonic() >= deadline:
                raise CannotRun((".work/record.mutex", "record.mutex", "another writer held the record", "a free record"))
            time.sleep(MUTEX_RETRY)
        _HELD[key] = True
        try:
            yield
        finally:
            del _HELD[key]
            _os_lock(handle, False)


# The lease primitives (A9.8; G01 to G04, G50 to G53 and the lease fixes): the one writer of the lock and its two
# mirrors. A take, a release, a break and a repair back the lock up first; a refresh and the fence do not.

def _lock(epoch, state, history):
    lock = {"schema": "lock/2", "kind": "build", "epoch": epoch}
    lock.update(dict.fromkeys(LOCK_FIELDS), state=state, history=history)
    return lock

def _event(event, lock, by, choice=None, reconcile=None, note=None, for_strand=None):
    """A history entry about the lease `lock` holds, so `epoch` is that lease's epoch; a `broken`, `parked` or
    `repaired` entry also carries `for_strand` (finding 1)."""
    entry = {"event": event, "at": stamp("utc"), "epoch": lock["epoch"], "strand": lock["strand"],
             "version": lock["version"], "session_label": lock["session_label"], "run_id": lock["run_id"]}
    entry.update(by=by, choice=choice, reconcile=reconcile, note=note)
    if for_strand is not None:
        entry["for_strand"] = for_strand
    return entry

def read_lock(root):
    """.work/lock.json as parsed; exit 3 when it is missing or not JSON, the expected text naming the repair."""
    try:
        return read_json(root / ".work" / "lock.json", LOCK_REL)
    except CannotRun as exc:
        raise CannotRun((LOCK_REL, "lock", exc.findings[0]["problem"], "a readable lock/2 file; " + REPAIR))

def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)

def _is_utc(value):
    try:
        return bool(parse_utc(value))
    except (TypeError, ValueError):
        return False

LOCK_FORMS = {"strand": (lambda v: isinstance(v, str) and bool(re.fullmatch(r"\d{3}", v)), "a three-digit short id"),
              "strand_title": (lambda v: v is None or isinstance(v, str), "the strand's title"),
              "version": (lambda v: isinstance(v, str) and bool(re.fullmatch(r"v\d+\.\d+", v)), "a version vX.Y"),
              "run_id": (lambda v: v is None or (isinstance(v, str) and bool(v)), "null or a run id"),
              "session_label": (lambda v: isinstance(v, str) and bool(LABEL_FORM.fullmatch(v)), "YYYYMMDD-HHMM-xxxx"),
              "taken_at": (_is_utc, "a UTC stamp YYYY-MM-DDTHH:MM:SSZ"),
              "heartbeat_at": (_is_utc, "a UTC stamp YYYY-MM-DDTHH:MM:SSZ")}

def lock_findings(lock):
    """G02's shape of the lock as blocking findings, none when it is sound (finding 9): schema lock/2, history a
    list of entries with a known event and an integer epoch, the lock's epoch an integer at or above each, a known
    state, and the seven lock fields in form while held and null otherwise."""
    if not isinstance(lock, dict):
        return [(LOCK_REL, "lock", "the lock is not a JSON object", "a lock/2 object; " + REPAIR)]
    history, state, found = lock.get("history"), lock.get("state"), []
    entries = [e for e in history if isinstance(e, dict)] if isinstance(history, list) else []
    epochs = [e.get("epoch") for e in entries if _is_int(e.get("epoch"))]
    for key, ok, problem, expected in (
            ("schema", lock.get("schema") == "lock/2", "schema %r" % (lock.get("schema"),), "lock/2"),
            ("history", isinstance(history, list) and len(entries) == len(history) == len(epochs)
             and all(e.get("event") in EVENTS for e in entries), "the history is not a list of known entries",
             "a list of entries, each with an event of %s and an integer epoch" % " | ".join(EVENTS)),
            ("epoch", _is_int(lock.get("epoch")) and lock["epoch"] >= max(epochs + [0]),
             "epoch %r" % (lock.get("epoch"),), "an integer at or above every history epoch"),
            ("state", state in LOCK_STATES, "%r is not a lock state" % (state,), " | ".join(LOCK_STATES))):
        if not ok:
            found.append((LOCK_REL, key, problem, expected + "; " + REPAIR))
    for key in LOCK_FIELDS if state in LOCK_STATES else ():
        value, (ok, form) = lock.get(key), LOCK_FORMS[key]
        if (state == "held" and not ok(value)) or (state != "held" and value is not None):
            found.append((LOCK_REL, key, "%r while the lease is %s" % (value, state),
                          (form + " while held" if state == "held" else "null unless held") + "; " + REPAIR))
    return found

def _files(root, lock=True):
    """account.json, CLIENT.md and (unless `lock` is False) the lock, schemas and the lock's shape checked
    before anything is written (C13, finding 9)."""
    account, client = read_json(root / "account.json", "account.json"), read_text(root / "CLIENT.md", "CLIENT.md")
    require_schema(account.get("schema"), "account", "account.json")
    require_schema(front_matter(client, "CLIENT.md").get("schema"), "client", "CLIENT.md")
    if not lock:
        return None, account, client
    found = read_lock(root)
    if isinstance(found, dict) and str(found.get("schema")).startswith("lock/"):
        require_schema(found["schema"], "lock", LOCK_REL)  # newer: refused as such; any other schema is malformed
    problems = lock_findings(found)
    if problems:
        raise Refusal(*problems)
    return found, account, client

def _commit(root, lock, account, client, backup=True, write_lock=True):
    """Both mirrors rewritten from the lock, each only when its value changes, then the lock itself, last, so a
    failed write leaves the lease as it was and the same call can be retried (G09, finding 4). `backup` covers
    account.json and the lock (a refresh passes False); CLIENT.md is always backed up. Returns the names written."""
    held = lock["state"] == "held"
    line = "%s %s (%s)" % (lock["strand"], lock["version"], lock["session_label"]) if held else "none"
    mirror, writes = {key: lock[key] for key in ("strand", "epoch", "session_label", "heartbeat_at")}, []
    if account.setdefault("guard_index", {}).get("lease") != mirror:
        account["guard_index"]["lease"] = mirror
        writes.append(("account.json", json_text(account), backup))
    if front_matter(client, "CLIENT.md").get("lease") != line:
        writes.append(("CLIENT.md", set_front_matter(client, {"lease": line}, "CLIENT.md"), True))
    if write_lock:
        writes.append((LOCK_REL, json_text(lock), backup))
    for rel, data, keep in writes:
        try:
            write_file(root.joinpath(*rel.split("/")), data, root, keep)
        except OSError as exc:
            torn = rel == LOCK_REL
            raise CannotRun((rel, "lease", "could not write the file: %s; %s" % (
                exc, "the lock may be torn" if torn else "the lease is unchanged, the lock being written last"),
                "record.py lease status, and if the lock does not read, " + REPAIR if torn else "the same call again "
                "once no other program holds the file; record.py lease sync rewrites the mirrors from the lock"))
    return [rel for rel, _, _ in writes]

def _require_holder(lock, epoch, session_label):
    if lock["state"] != "held" or not session_label or session_label != lock["session_label"] \
            or str(epoch) != str(lock["epoch"]):
        raise Refusal((LOCK_REL, "session_label", "lease %s at epoch %s, session %s; presented epoch %s, session "
                       "%s: another session" % (lock["state"], lock["epoch"], lock["session_label"], epoch,
                                                session_label), "the epoch and label this session's take returned"))

def _holder(lock, strand):
    """The held-lease refusal: the holder, its heartbeat as a fact, what may go on, the three ways forward."""
    age, stale = heartbeat_age(lock["heartbeat_at"])
    state = "fresh" if not stale else "stale" if age >= 0 else "not fresh: the clocks disagree"
    same = ", another session of this strand" if lock["strand"] == strand else ""
    return (LOCK_REL, "state", "the build lease is held by strand %s (%s) %s%s, session %s, heartbeat %s. Nothing "
            "local is blocked: intake, the readiness check and a blueprint revision may go on; the audit and the "
            "release of any strand are blocked while a build is live" % (
                lock["strand"], lock["strand_title"], lock["version"], same, lock["session_label"],
                heartbeat_words(age, stale)),
            "wait for the run to end; ask the holder's session to release it with record.py lease release; or "
            "break it if it is stale (its heartbeat is %s)" % state)

def _runs(root, folder):
    path = folder / "solution" / "build.json"
    return (read_json(path, relative(root, path)).get("runs") or []) if path.is_file() else []

def _reserved(lock):
    """The strand whose take alone comes next, or None (finding 1, C111, C112): while the lock is `broken`, a
    resume break keeps the lease for the holder's strand, a park and a repair for their `for_strand`."""
    history = lock.get("history")
    last = history[-1] if lock.get("state") == "broken" and isinstance(history, list) and history else None
    if not isinstance(last, dict):
        return None
    if last.get("event") == "broken" and last.get("choice") == "resume":
        return last.get("strand")
    return last.get("for_strand") if last.get("event") in ("parked", "repaired") else None

def _closed(root, short):
    """True when the strand's STRAND.md reads `closed`: a reservation for a closed strand lapses."""
    try:
        path = strand_dir(root, short) / "STRAND.md"
        return front_matter(read_text(path), relative(root, path)).get("state") == "closed"
    except MMBError:
        return False

def lease_init(root):
    """The record's first lock, released at epoch 0 with no history, and its mirrors (for `init`)."""
    with record_mutex(root):
        if (root / ".work" / "lock.json").exists():
            raise Refusal((LOCK_REL, "state", "the record already has a lock", "a record without one"))
        _commit(root, _lock(0, "released", []), *_files(root, lock=False)[1:])

def lease_take(root, strand):
    """Take the build lease for a strand (short id); returns epoch, session_label, strand, version, taken_at. Only
    from allowlisted values (G50, G53, findings 7 and 13): the lock `none`, `released` or `broken` and kept for no
    other strand (finding 1); the strand `platform` or `hybrid`, `active`, or `paused` with an `interrupted` run
    (parked by a break), on a version vX.Y whose versions/<v>/version.md exists."""
    with record_mutex(root):
        lock, account, client = _files(root)
        folder = strand_dir(root, strand)
        name = relative(root, folder / "STRAND.md")
        fields = front_matter(read_text(folder / "STRAND.md", name), name)
        kind, state, version = fields.get("kind"), fields.get("state"), fields.get("version", "")
        parked = state == "paused" and any(run.get("state") == "interrupted" for run in _runs(root, folder))
        reasons = [(name, key, problem, expected) for key, bad, problem, expected in (
            ("kind", kind not in ("platform", "hybrid"), "the strand's kind is %s: only a platform or hybrid strand "
             "takes the build lease, a non-platform one never" % (kind or "missing"), "a platform or hybrid strand"),
            ("state", state != "active" and not parked, "the strand is %s%s" % (state or "missing", ", by the user, "
             "with no interrupted run" if state == "paused" else ""), "an active strand, or a paused one that a "
             "lease break parked (its run interrupted)"),
            ("version", not (re.fullmatch(r"v\d+\.\d+", version) and (folder / "versions" / version / "version.md")
                             .is_file()), "the strand has no opened version (version %s)" % (version or "missing"),
             "an opened version vX.Y with its versions/<v>/version.md")) if bad]
        if lock["state"] not in TAKEABLE:
            reasons.append(_holder(lock, strand))
        reserved = _reserved(lock)
        if reserved and reserved != strand and not _closed(root, reserved):
            last = lock["history"][-1]
            what = {"broken": "lease break (resume)", "parked": "lease break that parked strand %s" % last["strand"],
                    "repaired": "lock repair"}[last["event"]]
            reasons.append((LOCK_REL, "state", "the %s at epoch %s keeps the lease for strand %s: its take comes "
                            "next" % (what, last["epoch"], reserved), "the take of strand %s (record.py lease take "
                            "--strand %s); any strand may take once it has released" % (reserved, reserved)))
        if reasons:
            raise Refusal(*reasons)
        used, label = {entry.get("session_label") for entry in lock["history"]}, None
        while label is None or label in used:
            label = stamp("label") + "-" + "".join(secrets.choice(LABEL_CHARS) for _ in range(4))
        new = _lock(lock["epoch"] + 1, "held", lock["history"])
        new.update(strand=strand, strand_title=fields.get("title"), version=version,
                   session_label=label, taken_at=stamp("utc"), heartbeat_at=stamp("utc"))
        new["history"].append(_event("taken", new, label))
        _commit(root, new, account, client)
        return {key: new[key] for key in ("epoch", "session_label", "strand", "version", "taken_at")}

def _beat(root, lock, account, client, run_id=None):
    lock.update(heartbeat_at=stamp("utc"), run_id=lock["run_id"] or run_id)
    _commit(root, lock, account, client, backup=False)

def lease_refresh(root, epoch, session_label, run_id=None):
    """Move the heartbeat, with no history entry and no backup; `run_id` enters once, while the lock has none,
    and never a run id an earlier lease carried (G50, finding 2)."""
    run_id = run_id or None
    with record_mutex(root):
        lock, account, client = _files(root)
        _require_holder(lock, epoch, session_label)
        if run_id is not None and lock["run_id"] not in (None, run_id):
            raise Refusal((LOCK_REL, "run_id", "the lease already carries run %s" % lock["run_id"], "that run id"))
        earlier = [e["epoch"] for e in lock["history"] if run_id is not None and e.get("run_id") == run_id]
        if earlier and lock["run_id"] is None:
            raise Refusal((LOCK_REL, "run_id", "run %s ran under the lease of epoch %s, and a run enters only the "
                           "lease it starts under" % (run_id, earlier[-1]), "a new run id from ledger.py run start"))
        _beat(root, lock, account, client, run_id)
        return {key: lock[key] for key in ("epoch", "session_label", "run_id", "heartbeat_at")}

def lease_release(root, epoch, session_label):
    """Release the lease held under this epoch and label: a state change, the file and history kept."""
    with record_mutex(root):
        lock, account, client = _files(root)
        _require_holder(lock, epoch, session_label)
        history = lock["history"] + [_event("released", lock, session_label)]
        _commit(root, _lock(lock["epoch"], "released", history), account, client)
        return {"epoch": lock["epoch"], "state": "released"}

def _reconcile(root, lock):
    """Condition 4: the holder's interrupted run carries a classify-only reconcile newer than the heartbeat."""
    if lock["run_id"] is None:
        return {}, None
    path = strand_dir(root, lock["strand"]) / "solution" / "build.json"
    name = relative(root, path)
    run = next((r for r in (read_json(path, name).get("runs", []) if path.exists() else [])
                if r.get("id") == lock["run_id"]), {})
    found = run.get("reconcile") or {}
    try:
        ok = run.get("state") == "interrupted" and found.get("mode") == "classify-only" \
            and parse_utc(found.get("at", "")) > parse_utc(lock["heartbeat_at"])
    except ValueError:
        ok = False
    return dict(found.get("classes") or {}), None if ok else (
        name, "runs[].reconcile", "run %s has no classify-only reconcile after the last heartbeat" % lock["run_id"],
        "recovery over strand %s in classify-only mode first" % lock["strand"])

def lease_break(root, epoch, session_label, for_strand, user_yes, account_id, choice, park_yes=None):
    """Break a held lease when all five conditions hold, listing every failing one (A9.8, G03, G04). The lock
    goes to `broken` at epoch + 1 with a `broken` entry, and `parked` on park, both naming `for_strand`; no take
    happens here, and the next take is the holder's strand's on resume, the taker's on park (finding 1).
    Returns what record.py writes into the logs and, on park, into the holder's STRAND.md."""
    with record_mutex(root):
        lock, account, client = _files(root)
        if lock["state"] != "held" or str(epoch) != str(lock["epoch"]) or not session_label \
                or session_label != lock["session_label"]:
            raise Refusal((LOCK_REL, "epoch", "the lease changed since it was read", "epoch %s, session %s, held"
                           % (lock["epoch"], lock["session_label"])))
        holder, (age, stale) = lock["strand"], heartbeat_age(lock["heartbeat_at"])
        bound, (classes, reconcile) = (account.get("account") or {}).get("id"), _reconcile(root, lock)
        park = choice == "park"
        failed = [finding for bad, finding in (
            (not stale, (LOCK_REL, "heartbeat_at", "the heartbeat is %d minutes old: fresh" % age, "over 60 minutes")),
            (not re.search(r"(?<!\d)%s(?!\d)" % holder, user_yes or ""),
             (LOCK_REL, "user_yes", "no yes from the user naming strand %s" % holder, "the user's words naming it")),
            (bound in (None, "unbound") or str(account_id) != str(bound), ("account.json", "account.id",
             "the account read in this session (%s) is not the bound one (%s)" % (account_id, bound), "the same")),
            (reconcile is not None, reconcile),
            (choice not in ("resume", "park"), (LOCK_REL, "choice", "no choice for the run", "resume or park")),
            (park and not park_yes, (LOCK_REL, "park_yes", "no yes for parking", "the user's own yes to park")),
            (park and bool(classes.get("duplicate") or classes.get("partial")), (LOCK_REL, "reconcile",
             "the reconcile found duplicate or partial elements", "resume, not park")),
            (park and for_strand == holder, (LOCK_REL, "for_strand", "a park for the holder", "the taking strand")))
            if bad]
        if failed:
            raise Refusal(*failed)
        note = 'for %s: "%s"' % (for_strand, user_yes)
        history = lock["history"] + [_event("broken", lock, None, choice, classes, note, for_strand)]
        if park:
            history.append(_event("parked", lock, None, note='for %s: "%s"' % (for_strand, park_yes),
                                  for_strand=for_strand))
        _commit(root, _lock(lock["epoch"] + 1, "broken", history), account, client)
        return {"broken_epoch": lock["epoch"], "epoch": lock["epoch"] + 1, "choice": choice, "reconcile": classes,
                "for_strand": for_strand, "reserved_for": for_strand if park else holder,
                "holder": {key: lock[key] for key in LOCK_FIELDS}}

def lease_status(root):
    """The status lease block (G19): `held`, the lock's fields, heartbeat age and freshness (null unless held, and
    for a stamp that does not parse), and `reserved_for`, the strand whose take alone comes next (finding 1)."""
    with record_mutex(root):
        lock = read_lock(root)
    lock = lock if isinstance(lock, dict) else {}
    held = lock.get("state") == "held"
    try:
        age, stale = heartbeat_age(lock.get("heartbeat_at")) if held else (None, None)
    except (TypeError, ValueError):
        age, stale = None, None
    block = {"held": held, "state": lock.get("state"), "epoch": lock.get("epoch")}
    block.update({key: lock.get(key) for key in STATUS_FIELDS})
    block.update(heartbeat_age_minutes=age, fresh=None if stale is None else not stale, reserved_for=_reserved(lock))
    return block

def lease_fence(root, epoch, session_label, run_id=None):
    """(ok, reason) for an account-affecting write (G51, findings 2, 3 and 9): the lock held and sound, the same
    epoch, the same non-empty label, and a run on the lease that is the presented one, so nothing passes before
    `run start` has entered its id. When it passes, the heartbeat moves in the same hold, so a write never starts
    behind a heartbeat a break could read as stale; call it before every account-affecting write."""
    with record_mutex(root):
        try:
            lock, account, client = _files(root)
        except Refusal as exc:
            return False, str(exc)
        reasons = [reason for bad, reason in (
            (lock["state"] != "held", "no lease is held (state %s)" % lock["state"]),
            (str(epoch) != str(lock["epoch"]), "epoch %s is not the lock's %s" % (epoch, lock["epoch"])),
            (not session_label or session_label != lock["session_label"],
             "session %s is not the holder's %s" % (session_label, lock["session_label"])),
            (lock["state"] == "held" and lock["run_id"] is None,
             "no run has started under this lease: ledger.py run start enters its id through a refresh first"),
            (lock["run_id"] is not None and run_id != lock["run_id"],
             "run %s is not the lock's %s" % (run_id, lock["run_id"]))) if bad]
        if reasons:
            return False, "; ".join(reasons)
        _beat(root, lock, account, client)
        return True, "ok"

def lease_sync(root):
    """Rewrite both mirrors from the lock, the lock unchanged (finding 5): the repair for a mirror a failed or
    interrupted write left behind. Returns the epoch, the state and the files rewritten."""
    with record_mutex(root):
        lock, account, client = _files(root)
        return {"epoch": lock["epoch"], "state": lock["state"],
                "rewritten": _commit(root, lock, account, client, write_lock=False)}

def _backups(root):
    """The lock's backups, newest first, by stamp and then by clash suffix."""
    found = [(m.group(1), int(m.group(2) or 1), p) for p in (root / ".work" / "backup" / ".work").glob("lock.json.*")
             for m in [re.fullmatch(r"lock\.json\.(\d{8}T\d{12}Z)(?:-(\d+))?", p.name)] if m]
    return [p for _, _, p in sorted(found, key=lambda item: item[:2], reverse=True)]

def lease_repair(root, user_yes):
    """Rebuild a missing, unreadable or malformed lock with the user's yes (finding 6), never by a delete: a torn
    file is backed up and rewritten in place. The epoch is one above every epoch the newest sound lock backup and
    the account.json mirror know, so a session holding the lost lease is fenced out; the history is that backup's
    plus a `repaired` entry. While the mirror names a holder, or the backup kept the lease for a strand, the lock
    goes to `broken`, kept for that strand as a resume break would keep it; otherwise to `released`."""
    with record_mutex(root):
        _, account, client = _files(root, lock=False)
        try:
            current = read_lock(root) if (root / ".work" / "lock.json").exists() else None
        except CannotRun:
            current = None
        schema = str(current.get("schema")) if isinstance(current, dict) else ""
        if schema.startswith("lock/"):
            require_schema(schema, "lock", LOCK_REL)  # a newer plugin's lock is never rebuilt by this one
        if isinstance(current, dict) and not lock_findings(current):
            raise Refusal((LOCK_REL, "lock", "the lock reads and is sound: nothing to repair",
                           "a missing, torn or malformed lock; record.py lease sync rewrites the mirrors"))
        if not user_yes or not user_yes.strip() or "\n" in user_yes or "\r" in user_yes:
            raise Refusal((LOCK_REL, "user_yes", "no yes from the user for the repair", "the user's words on one line"))
        backup, source = None, "none"
        for path in _backups(root):
            try:
                data = read_json(path)
            except CannotRun:
                continue
            if not lock_findings(data):
                backup, source = data, path.name
                break
        mirror = (account.get("guard_index") or {}).get("lease") or {}
        known = [n for n in [mirror.get("epoch")] + ([backup["epoch"]] + [e["epoch"] for e in backup["history"]]
                                                     if backup else []) if _is_int(n)]
        holder = mirror.get("strand") if re.fullmatch(r"\d{3}", str(mirror.get("strand"))) else None
        kept = holder or (_reserved(backup) if backup else None)
        entry = dict(_event("repaired", _lock(max(known, default=0), None, []), None, note='from the lock backup %s '
                            'and the account.json mirror (epoch %s, strand %s, session %s): "%s"' % (
                                source, mirror.get("epoch"), mirror.get("strand"), mirror.get("session_label"),
                                user_yes), for_strand=kept),
                     strand=holder, session_label=mirror.get("session_label") if holder else None)
        new = _lock(entry["epoch"] + 1, "broken" if kept else "released", (backup or {}).get("history", []) + [entry])
        _commit(root, new, account, client)
        return {"epoch": new["epoch"], "state": new["state"], "reserved_for": kept, "from_backup": source,
                "mirror": mirror}
