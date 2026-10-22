"""Unit tests for plugins/monday-master-builder/scripts/ledger.py, part 1: the write path (WP3 step 5).

Contract clauses of rebuild-workspace/build/wp3/CONTRACT.md by id in the test names. Each test copies
tests/unit/fixtures/home/ into a temporary folder whose name holds a space, points MMB_HOME at it and HOME and
USERPROFILE at an empty canary folder, and pins mmb_common's clock to 2026-11-05T14:30:00Z, as test_record.py does.
Record variants (a revision v0.2 carrying the element-key table, a client-account record, a sandbox record, planted
defects) are built in each test's own copy; nothing is added to tests/unit/fixtures/ (K14). Lease state is changed
only through the mmb_common primitives (K37). ledger.py runs from a temporary plugin root: in process through main(),
and as a subprocess where the process boundary is the point (K04, G49). Tests whose docstring says "Windows run" are
repeated on a real Windows machine and on a Mac.
"""
import ast, contextlib, hashlib, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, threading, time  # noqa: E401
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPTS = HERE.parent.parent / "plugins" / "monday-master-builder" / "scripts"
sys.dont_write_bytecode = True  # nothing cached beside the scripts (G49)
sys.path.insert(0, str(SCRIPTS))
import mmb_common as mc  # noqa: E402
from test_record import add_lint  # noqa: E402

REAL_HOME, CLOCK = Path.home(), datetime(2026, 11, 5, 14, 30, tzinfo=timezone.utc)
LABEL, IGNORE = "20261105-1405-r2d6", shutil.ignore_patterns(".gitkeep", ".DS_Store")
S1, S2 = "strands/001-job-tracking", "strands/002-timber-orders"
B1J, V1, V2 = S1 + "/solution/build.json", S1 + "/versions/v0.1", S1 + "/versions/v0.2"
KEYS = ["expected", "field", "file", "problem"]
OWN_WS, SALES_WS, OPS_WS, BOARD = "40000001", "90100000002", "40000002", "50000001"
A21_WORDS = "the plugin never writes into any other workspace (A21)"
TABLE = (("W1", "workspace", "Larkmoor Joinery – Ops"), ("B1", "board", "Jobs"), ("B1.V1", "view", "Jobs by stage"),
         ("W2", "workspace", "Larkmoor Joinery – Sales"), ("B2", "board", "Orders"), ("B2.C1", "column", "Supplier"),
         ("B1.C4", "column", "Ready to install"), ("B2.SUB", "subitems", "Order lines"),
         ("A1", "automation", "Notify when ready"), ("WF1", "workflow", "Intake flow"),
         ("WF1.PUB", "publication", "publish Intake flow, inactive"), ("AG1", "agent", "Dispatch helper"),
         ("AG1.ACT", "activation", "activate Dispatch helper"), ("B1.AI1", "ai_column", "Job summary"),
         ("VB1", "vibe_app", "Job wall"), ("VB1.PUB", "publication", "publish Job wall, active"),
         ("SQ1", "sequence", "Order reminders"), ("SQ1.ACT", "activation", "activate Order reminders"),
         ("WH1", "webhook", "Order feed"), ("DB1", "dashboard", "Workshop"), ("DB1.W2", "widget", "Jobs chart"),
         ("PF1", "portfolio", "Installs"), ("PJ1", "project", "Install at the mill"), ("F1", "folder", "Archive"),
         ("D1", "doc", "Start here"), ("B1.G2", "group", "Ready"), ("B1.FM1", "form", "Job request"),
         ("B9", "board", "Supplier list"), ("B9.C1", "column", "Supplier code"), ("B5", "board", "Shared stock"),
         ("U1", "ui_step", "Kanban view on Jobs"))
PROMPTS = {"AG1": "Read each new job and assign it to the workshop lead.\nSay why in one line.",
           "B1.AI1": "Summarise the job in one line.", "VB1": "A wall of the open jobs, by stage."}
NOTIFIES = {"SQ1": "user"}  # R20 (a): the recipients a revision approves, by key; every other row notifies nobody
IRREVERSIBLE = ("W1", "W2", "F1", "B1", "B2.SUB", "WF1.PUB", "AG1.ACT", "VB1.PUB", "SQ1.ACT", "WH1")
AGENT = {"plan": PROMPTS["AG1"], "state": "INACTIVE", "version_id": "vid-000001",
         "triggers": [{"name": "When agent is mentioned"}, {"name": "When agent is assigned"}], "knowledge": []}
VIBE = {"status": "READY", "is_published": False, "code_version": "1", "differs_from_request": False}
HOLD = ("import sys, time\nsys.path.insert(0, sys.argv[1])\nimport mmb_common as mc\nfrom pathlib import Path\n"
        "with mc.record_mutex(Path(sys.argv[2])):\n    print('held', flush=True)\n    time.sleep(float(sys.argv[3]))\n")
TRY = ("import sys\nsys.path.insert(0, sys.argv[1])\nimport mmb_common as mc\nfrom pathlib import Path\ntry:\n"
       "    with mc.record_mutex(Path(sys.argv[2]), timeout=0.3):\n        print('free')\nexcept mc.CannotRun:\n"
       "    print('held')\n")


def is_stdlib(name):
    names = getattr(sys, "stdlib_module_names", None)  # Python 3.10 and later
    if names is not None:
        return name in names
    spec = importlib.util.find_spec(name)
    return spec is not None and "site-packages" not in str(spec.origin)


def tree_hash(folder):
    return {p.relative_to(folder).as_posix(): mc.sha256_file(p) for p in folder.rglob("*") if p.is_file()}


def make_plugin(target):
    """A plugin root as G31 has the tests build it: the stand-in templates and plugin.json, and scripts/."""
    plugin = Path(shutil.copytree(FIXTURES / "plugin", target))
    (plugin / "scripts").mkdir()
    for name in ("mmb_common.py", "record.py", "ledger.py"):
        shutil.copy(SCRIPTS / name, plugin / "scripts" / name)
    return add_lint(plugin)  # R48: record.py beside ledger.py loads leak_lint.py after its commands


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blueprint(rows=TABLE, prompts=None, heading="## Element keys", notifies=True):
    """A frozen revision; a row of three cells takes its recipients from NOTIFIES, a fourth cell gives them (R20 (a)),
    and `notifies=False` leaves the column out."""
    prompts = PROMPTS if prompts is None else prompts
    if notifies:
        head, sep = "| key | kind | name | notifies |", "|---|---|---|---|"
        body = ["| %s | %s | %s | %s |" % (tuple(row) + (NOTIFIES.get(row[0], ""),))[:4] for row in rows]
    else:
        head, sep, body = "| key | kind | name |", "|---|---|---|", ["| %s | %s | %s |" % tuple(row[:3]) for row in rows]
    lines = ["---", 'schema: "blueprint/1"', 'strand: "001"', 'revision: "1"', 'sample_rows: "none"',
             'updated: "2026-11-04T10:00"', "---", "Internal: never client-facing", "", "# Blueprint: Job tracking, v0.2",
             "", heading, "", head, sep] + body
    lines += ["", "## Prompts", ""]
    for key, text in prompts.items():
        lines += ["### Prompt %s" % key, "", "```text", text, "```", ""]
    lines += ["## What this build rests on", "", "- AS1: a job is ready to install when every cutting-list line is "
              "ticked.", '- AT1: "install" means the fitting visit.', "- FK1: one board for all jobs, the owner's "
              "leaning.", ""]
    return "\n".join(lines)


def version_md(sha, purpose="proof-of-concept"):
    return "\n".join(["---", 'schema: "version/1"', 'strand: "001"', 'version: "v0.2"', 'qualified_version: "001/v0.2"',
                      'state: "approved"', 'purpose: "%s"' % purpose, 'revision: "1"', 'sha256: "%s"' % sha,
                      'opened: "2026-11-04"', 'released: "none"', 'shown: "none"', 'signed_off: "none"',
                      'close_reason: "none"', 'updated: "2026-11-04T10:00"', "---", "Internal: never client-facing", "",
                      "## Scope", "", "Revision 1 of v0.2.", ""])


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fixtures_before = tree_hash(FIXTURES)
        cls.plugin_tmp = Path(tempfile.mkdtemp(prefix="mmb ledger plugin "))
        cls.plugin = make_plugin(cls.plugin_tmp / "plugin")
        cls.led = load(cls.plugin / "scripts" / "ledger.py", "ledger_under_test")
        cls.rec = load(cls.plugin / "scripts" / "record.py", "record_beside_ledger")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.plugin_tmp)
        if tree_hash(FIXTURES) != cls.fixtures_before:  # K14: WP2's fixtures are never written
            raise AssertionError("tests/unit/fixtures/ changed")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mmb ledger "))
        self.canary, self.now = self.tmp / "canary", CLOCK
        self.canary.mkdir()
        self.copy_home()
        self.real = self.snapshot(REAL_HOME / "monday-builder")
        env = {"MMB_HOME": str(self.home), "HOME": str(self.canary), "USERPROFILE": str(self.canary)}
        for patcher in (mock.patch.dict(os.environ, env), mock.patch.object(mc, "now_utc", lambda: self.now)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def copy_home(self):
        self.home = self.tmp / "mmb home"
        if self.home.exists():
            shutil.rmtree(self.home)
        shutil.copytree(FIXTURES / "home", self.home, ignore=IGNORE)
        self.root = self.home / "clients" / "larkmoor-joinery"
        self.epoch, self.label, self.run_id = "2", LABEL, None

    def tearDown(self):
        self.assertEqual(list(self.canary.iterdir()), [])  # K16
        self.assertEqual(self.snapshot(REAL_HOME / "monday-builder"), self.real)
        shutil.rmtree(self.tmp)

    @staticmethod
    def snapshot(path):
        return path.exists(), path.stat().st_mtime_ns if path.exists() else None

    # Running ledger.py.

    def ledger(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.led.main(["--record", str(self.root)] + [str(arg) for arg in argv])
        self.assertNotIn("\r", out.getvalue())  # K23
        data = json.loads(out.getvalue())
        self.assertTrue({"ok", "command", "asked_by"} <= set(data), data)
        self.four_parts(data)
        return code, data

    def four_parts(self, data):
        """K24, K25, K31: every refusal, finding and error names four non-empty parts, the file in POSIX form."""
        found = data.get("refusals", []) + [data["error"]] if "error" in data else data.get("refusals", [])
        found += (data.get("findings") or {}).get("blocking", []) + (data.get("findings") or {}).get("warnings", [])
        for finding in found:
            self.assertEqual(sorted(finding), KEYS)
            self.assertTrue(all(finding.values()), finding)
            self.assertNotIn("\\", finding["file"])

    def ok(self, *argv):
        code, data = self.ledger(*argv)
        self.assertEqual((code, data["ok"]), (0, True), data)
        return data

    def refused(self, *argv):
        """The refusals, after asserting exit 1 and an unchanged record tree (K27)."""
        before = self.tree()
        code, data = self.ledger(*argv)
        self.assertEqual((code, data["ok"]), (1, False), data)
        self.assertEqual(self.tree(), before)
        return data["refusals"]

    def check(self):
        """(exit code, blocking (file, field) pairs, warning pairs) of `check`, which writes nothing (K246)."""
        before = self.tree()
        code, data = self.ledger("check")
        self.assertEqual(self.tree(), before)
        found = data["findings"]
        return code, pairs(found["blocking"]), pairs(found["warnings"])

    def tree(self):
        return {p.relative_to(self.root).as_posix(): mc.sha256_file(p) for p in self.root.rglob("*")
                if p.is_file() and p.name != "record.mutex"}

    # Reading and editing the copy.

    def sha(self, rel=B1J):
        return mc.sha256_file(self.root / rel)

    def data(self, rel=B1J):
        return json.loads((self.root / rel).read_text(encoding="utf-8"))

    def row(self, key):
        return self.data()["objects"][key]

    def edit_json(self, rel, change):
        data = self.data(rel)
        change(data)
        (self.root / rel).write_bytes(mc.json_text(data).encode("utf-8"))

    def edit_fm(self, rel, **updates):
        path = self.root / rel
        path.write_bytes(mc.set_front_matter(mc.read_text(path), updates).encode("utf-8"))

    def put(self, name, data):
        path = self.root / ".work" / "strands" / "001" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return ".work/strands/001/" + name

    # The variants and the build steps.

    def make_v2(self, rows=TABLE, prompts=None, purpose="proof-of-concept", heading="## Element keys", notifies=True):
        vdir = self.root / V2
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "blueprint-r1.md").write_bytes(blueprint(rows, prompts, heading, notifies).encode("utf-8"))
        sha = mc.sha256_file(vdir / "blueprint-r1.md")
        (vdir / "version.md").write_bytes(version_md(sha, purpose).encode("utf-8"))
        self.edit_fm(S1 + "/STRAND.md", version="v0.2", version_state="approved")
        return sha

    def approval_argv(self, sha, irreversible=IRREVERSIBLE, referenced=("B9",)):
        argv = ["approval", "--strand", "001", "--sha256", sha, "--words", "yes, build revision 1 of v0.2", "--session",
                "blueprint session of 2026-11-04", "--expect-sha", self.sha()]
        for key in irreversible:
            argv += ["--irreversible", key]
        for key in referenced:
            argv += ["--referenced", key]
        return argv

    def approve(self, purpose="proof-of-concept", extra=(), **kw):
        sha = self.make_v2(purpose=purpose, **kw)
        return self.ok(*(self.approval_argv(sha) + list(extra)))

    def client(self):
        self.edit_fm("CLIENT.md", account_kind="client", build_target="client-account")
        self.edit_json("account.json", lambda d: d["account"].update(kind="client", build_target="client-account"))

    def change_check(self, result="no change affecting this build", strand="001", approved=None):
        path = self.put("change-check.json", {
            "ring": "release_candidate 2026-10", "versions_seen": ["2026-07", "2026-10"], "release_notes_since": "not-read",
            "roster_diff": {"added": [], "removed": [], "renamed": []}, "schema_diff": [], "result": result,
            "approved_by_user": approved})
        return self.ok("change-check", "--strand", strand, "--from", path)

    def start(self, cc=True):
        if cc:
            self.change_check()
        data = self.ok("run", "start", "--strand", "001", "--lease-epoch", self.epoch, "--session-label", self.label,
                       "--another-build-running", "no", "--account-check", "match", "--expect-sha", self.sha())
        self.run_id = data["run_id"]
        return data

    def fence(self):
        return ["--lease-epoch", self.epoch, "--session-label", self.label, "--run-id", self.run_id]

    def argv(self, command, *argv):
        words = command.split(" ")
        return words + ["--strand", "001"] + list(argv) + self.fence() + ["--expect-sha", self.sha()]

    def go(self, command, *argv):
        return self.ok(*self.argv(command, *argv))

    def no(self, command, *argv):
        return self.refused(*self.argv(command, *argv))

    def intent(self, key, *argv, op="create"):
        return self.go("intent", "--key", key, "--operation", op, *argv)

    def record(self, key, *argv):
        return self.go("record", "--key", key, *argv)

    def read_file(self, key, obj, read="a read of the object"):
        return self.put("verify-%s.json" % key, {"read": read, "object": obj})

    def verify(self, key, obj, result="match", note=None):
        return self.go("verify", "--key", key, "--result", result, "--read", self.read_file(key, obj),
                       *(["--note", note] if note else []))

    def yes(self, key, mode="per-item", *argv):
        return self.go("irreversible-yes", "--key", key, "--mode", mode, "--what", "the step for %s" % key, *argv)

    def end(self, used=7):
        return self.go("run end", "--calls-used", used)

    def sales(self, client=False):
        """W2 created, read back and recorded as the client's crm workspace and a target of strand 001."""
        if client:
            self.yes("W2")
        self.intent("W2", "--product", "crm")
        self.record("W2", "--id", SALES_WS)
        self.verify("W2", {"name": "Larkmoor Joinery – Sales", "kind": "open"})
        self.ok("workspaces", "--strand", "001", "--product", "crm", "--id", SALES_WS, "--name",
                "Larkmoor Joinery – Sales", "--created-in", "001/v0.2", *self.fence())

    def agent(self):
        self.intent("AG1", "--scope", OWN_WS)
        self.record("AG1", "--id", "90800000001")
        return self.verify("AG1", AGENT)

    def lease(self):
        return mc.lease_status(self.root)

    def inventory(self, name="inventory.json", read_at=None, **lists):
        """A live-inventory/1 file the session hands to reconcile (W70), read now unless `read_at` says otherwise."""
        data = {"schema": "live-inventory/1", "strand": "001", "read_at": read_at or mc.stamp("utc"),
                "ring": "release_candidate 2026-10"}
        for part in ("workspaces", "boards", "folders", "docs", "automations", "agents", "vibe_apps", "workflows"):
            data[part] = list(lists.get(part, []))
        data["dashboards"] = {"requested_ids": [], "returned": [], "missing_ids": []}
        return self.put(name, data)

    def reconcile(self, **lists):
        """The full reconcile over a read made half a minute after the last step (R10's precondition of a retry)."""
        self.now += timedelta(seconds=30)
        return self.ok("reconcile", "--strand", "001", "--inventory", self.inventory(**lists))

    def retake(self):
        """Release whatever is held and take a new lease, through the primitives only (K37)."""
        status = self.lease()
        if status["held"]:
            mc.lease_release(self.root, status["epoch"], status["session_label"])
        taken = mc.lease_take(self.root, "001")
        self.epoch, self.label, self.run_id = str(taken["epoch"]), taken["session_label"], None
        return taken

    def failing(self, name, nth=1):
        """mc.write_file failing on the nth write of a file of that name, as an OS error would."""
        real, count = mc.write_file, [0]

        def write(path, data, root, backup=True, backup_dir=None):
            if Path(path).name == name:
                count[0] += 1
                if count[0] == nth:
                    raise OSError("planted failure")
            return real(path, data, root, backup, backup_dir)
        return mock.patch.object(mc, "write_file", write)


def pairs(found):
    return {(f["file"], f["field"]) for f in found}


def words(found):
    return " ".join("%s %s" % (f["problem"], f["expected"]) for f in found)


class AAMutexReentryTest(Base):
    """W26: the mutex re-entry is proved first of all, before any test relies on it."""

    def test_K45_W26_the_fence_and_the_release_re_enter_a_hold_in_one_process(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

        def child():
            done = subprocess.run([sys.executable, "-B", "-c", TRY, str(SCRIPTS), str(self.root)], env=env,
                                  capture_output=True, timeout=60)
            return done.stdout.decode("utf-8").strip()
        self.start()
        with mc.record_mutex(self.root):
            began = time.monotonic()
            self.assertEqual(mc.lease_fence(self.root, "2", LABEL, self.run_id), (True, "ok"))
            self.assertEqual(mc.lease_release(self.root, "2", LABEL)["state"], "released")
            self.assertLess(time.monotonic() - began, 5)
            self.assertEqual(child(), "held")
        self.assertEqual(child(), "free")


class FrameTest(Base):

    def test_K01_K02_K03_K05_K06_K10_K15_K16_K34_K35_source_rules(self):
        source = (SCRIPTS / "ledger.py").read_text(encoding="utf-8")
        for path in (SCRIPTS / "ledger.py", Path(__file__)):
            module = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
            names = {a.name.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.Import) for a in n.names}
            names |= {n.module.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.ImportFrom)}
            for name in names - {"mmb_common", "test_record"}:
                self.assertTrue(is_stdlib(name), "%s imports %s" % (path.name, name))
        body = ast.parse(source).body
        first = next(n for n, node in enumerate(body) if isinstance(node, ast.Import) and node.names[0].name == "sys")
        self.assertEqual(ast.unparse(body[first + 1]) if hasattr(ast, "unparse") else "sys.dont_write_bytecode = True",
                         "sys.dont_write_bytecode = True")
        common = next(n for n, node in enumerate(body) if isinstance(node, ast.Import) and node.names[0].name == "mmb_common")
        self.assertGreater(common, first + 1)
        for pattern in (r"os\.system", r"shell\s*=", r"os\.popen", r"\bsubprocess\b", r"os\.(rename|replace|remove|unlink)",
                        r"shutil\.(move|rmtree)", r"\.(unlink|rename|rmdir)\(", r"expanduser", r"os\.sep", r'"~',
                        r'\+ *"(/|\\\\)"', r'"(/|\\\\)" *\+', r"lock\.json", r"read_lock", r"\[\"lease\"\]\s*=",
                        r"\.now\(", r"CLAUDE_PLUGIN_ROOT"):
            self.assertIsNone(re.search(pattern, source), pattern)
        for name in ("emit", "refuse", "Parser", "Usage"):  # K15: the frame is ledger.py's own copy
            self.assertTrue(hasattr(self.led, name))
            self.assertFalse(hasattr(mc, name))
        for text in (source, Path(__file__).read_text(encoding="utf-8")):
            for needle in ("Del" + "Ops", "/" + "Users/", "C:" + "\\" + "Users", "Library" + "/"):
                self.assertNotIn(needle, text)

    def test_C21_no_finding_is_built_with_an_empty_part(self):
        builders = {"CannotRun", "Refusal", "MMBError", "refuse", "block", "warn"}
        module = ast.parse((SCRIPTS / "ledger.py").read_text(encoding="utf-8"), feature_version=(3, 9))
        for call in (n for n in ast.walk(module) if isinstance(n, ast.Call)):
            if getattr(call.func, "attr", getattr(call.func, "id", None)) not in builders:
                continue
            for elts in [n.elts for arg in call.args for n in ast.walk(arg) if isinstance(n, ast.Tuple) and len(n.elts) == 4]:
                for part in elts:
                    self.assertFalse(isinstance(part, ast.Constant) and part.value in ("", None), call.lineno)

    def test_K20_K21_K29_K30_catalogue_and_usage_errors(self):
        catalogue = {"check", "bind", "approval", "change-check", "run start", "run heartbeat", "run end", "intent",
                     "record", "verify", "depart", "ui-step", "irreversible-yes", "reconcile", "estimate", "snapshot",
                     "compare", "classify", "native-map", "live-map", "live-map set", "workspaces"}
        self.assertEqual(set(self.led.COMMANDS), catalogue)
        for name in ("classify", "native-map", "snapshot", "compare", "reconcile", "estimate"):
            self.assertIsNotNone(self.led.COMMANDS[name])  # part 2 built them (test_ledger_read.py)
            code, data = self.ledger(name)
            self.assertEqual((code, data["error"]["field"]), (3, "arguments"))  # each needs its flags
        for argv in (("migrate",), (), ("run",), ("intent", "--strand", "001"), ("check", "--bogus"),
                     ("live-map", "set", "--key", "001:B1"), ("bind",)):
            code, data = self.ledger(*argv)
            self.assertEqual((code, data["ok"], data["error"]["field"]), (3, False, "arguments"), argv)

    def test_K22_a_folder_without_the_record_files_cannot_run(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.led.main(["--record", str(self.tmp), "check"])
        self.assertEqual((code, json.loads(out.getvalue())["error"]["file"]), (3, "CLIENT.md"))
        (self.root / "account.json").rename(self.root / "account.moved")
        code, data = self.ledger("check")
        self.assertEqual((code, data["error"]["file"]), (3, "account.json"))

    def test_K25_K29_K247_malformed_json_and_whole_file_errors(self):
        (self.root / "account.json").write_bytes(b"{ not json")
        code, data = self.ledger("check")
        self.assertEqual((code, data["error"]["file"], data["error"]["field"]), (3, "account.json", "(whole file)"))
        before = self.tree()
        code, data = self.ledger("bind", "--binding", ".work/none.json")
        self.assertEqual((code, self.tree()), (3, before))

    def test_R55_a_lock_that_writes_a_key_twice_stops_as_a_torn_lock_does(self):
        """WP4's R55: the lock read strictly; a key written twice, where a plain reader keeps the last copy, is the
        could-not-run path of a torn lock (exit 3 on .work/lock.json, nothing written), never a silent pick."""
        self.approve()
        self.start()
        path = self.root / ".work" / "lock.json"
        sound = path.read_text(encoding="utf-8")
        found = []
        for text in ("{ torn", sound.replace("{\n", '{\n  "epoch": 99,\n', 1)):
            path.write_text(text, encoding="utf-8")
            before = self.tree()
            code, data = self.ledger(*self.argv("intent", "--key", "B2", "--operation", "create", "--workspace", OWN_WS))
            self.assertEqual((code, self.tree()), (3, before), text)
            found.append(data["error"])
        self.assertEqual([(e["file"], e["field"], e["expected"]) for e in found], [
            (found[0]["file"], found[0]["field"], found[0]["expected"])] * 2)
        self.assertEqual(found[0]["file"], ".work/lock.json")
        self.assertIn('the key "epoch" is written twice in one object', found[1]["problem"])
        path.write_text(sound, encoding="utf-8")  # the same lock with each key once runs
        self.assertEqual(self.ledger(*self.argv("intent", "--key", "B2", "--operation", "create", "--workspace",
                                                OWN_WS))[0], 0)

    def test_R59_R55_a_json_block_that_writes_a_key_twice_is_refused_as_a_malformed_block_is(self):
        """WP4's R59: a json block of the documents appendix is read through mmb_common's strict reader; a key
        written twice, where a plain reader keeps the last copy and hides the first, gives the block no text, as a
        block that does not parse does, so compare refuses that document."""
        def appendix(*blocks):
            return "# Audit\n\n## Documents appendix\n\n" + "".join("```json\n%s\n```\n\n" % b for b in blocks)

        twice = '{"query": "mutation { delete_board (board_id: 5) { id } }", "query": "query { boards { id } }"}'
        nested = '{"steps": [{"query": "query { me { id } }", "note": "a", "note": "b"}]}'
        found = self.led.appendix_documents(appendix(twice, nested, "{ torn", '{"query": "query { users { id } }"}'))
        self.assertEqual([(n, body) for n, _, body, _ in found], [(1, None), (2, None), (3, None),
                                                                  (4, "query { users { id } }")])
        self.assertIn('the key "query" is written twice in one object', found[0][3])
        self.assertIn('the key "note" is written twice in one object', found[1][3])
        self.assertEqual(found[2][3], "a json block that does not parse")
        # the same key at two depths, or in two objects, is no repeat
        found = self.led.appendix_documents(appendix(
            '{"query": "query { me { id } }", "id": 1, "variables": {"id": 2}}',
            '[{"query": "query { boards { id } }"}, {"query": "query { users { id } }"}]'))
        self.assertEqual([body for _, _, body, _ in found], ["query { me { id } }", "query { boards { id } }",
                                                             "query { users { id } }"])

    def test_K46_K111_a_mutex_held_by_another_process_is_exit_3_and_nothing_is_written(self):
        """Windows run: the msvcrt branch of the record mutex."""
        self.approve()
        self.start()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        holder = subprocess.Popen([sys.executable, "-B", "-c", HOLD, str(SCRIPTS), str(self.root), "30"], env=env,
                                  stdout=subprocess.PIPE)
        try:
            self.assertEqual(holder.stdout.readline().decode("utf-8").strip(), "held")
            before = self.tree()
            with mock.patch.object(mc, "MUTEX_TIMEOUT", 0.3):
                code, data = self.ledger(*self.argv("intent", "--key", "B2", "--operation", "create", "--workspace",
                                                    OWN_WS))
            self.assertEqual((code, data["error"]["field"]), (3, "record.mutex"))
            self.assertEqual(self.tree(), before)
        finally:
            holder.kill()
            holder.wait(timeout=60)
        (self.root / ".work" / "lock.json").write_bytes(b"{ torn")  # a fence that cannot run: a stop, never a skip
        before = self.tree()
        code, data = self.ledger(*self.argv("intent", "--key", "B2", "--operation", "create", "--workspace", OWN_WS))
        self.assertEqual((code, self.tree()), (3, before))

    def test_K07_K08_K09_json_and_text_forms(self):
        """Windows run: CRLF and BOM copies read alike; every write is LF."""
        before_v01 = self.data()["approvals"][0]
        self.approve()
        self.start()
        self.sales()
        self.end()
        for rel in ("account.json", B1J):
            raw = (self.root / rel).read_bytes()
            self.assertEqual(raw.decode("utf-8"), mc.json_text(json.loads(raw.decode("utf-8"))))
        self.assertEqual(list(self.data()["approvals"][0].items()), list(before_v01.items()))
        live = (self.root / "live" / "live-map.md").read_bytes()
        self.assertFalse(live.startswith(b"\xef\xbb\xbf") or b"\r" in live)
        first = self.ledger("check")[1]["findings"]
        for rel in ("account.json", B1J):
            text = (self.root / rel).read_bytes()
            (self.root / rel).write_bytes(b"\xef\xbb\xbf" + text.replace(b"\n", b"\r\n"))
        self.assertEqual(self.ledger("check")[1]["findings"], first)

    def test_K10_K11_rewrites_back_up_keep_the_file_and_never_rename_or_delete(self):
        """Windows run: in-place overwrite semantics differ there."""
        targets = ("os.rename", "os.replace", "os.remove", "os.unlink", "os.rmdir", "shutil.move", "shutil.rmtree",
                   "pathlib.Path.unlink", "pathlib.Path.rename", "pathlib.Path.replace", "pathlib.Path.rmdir")
        build = self.root / B1J
        inode, old = build.stat().st_ino, build.read_bytes()
        with contextlib.ExitStack() as stack:
            spies = [stack.enter_context(mock.patch(target)) for target in targets]
            self.approve()
            self.start()
            self.sales()
            self.end()
        self.assertEqual([spy.call_count for spy in spies], [0] * len(targets))
        self.assertEqual(build.stat().st_ino, inode)
        backups = sorted((self.root / ".work" / "backup" / S1 / "solution").glob("build.json.*"))
        self.assertEqual(backups[0].read_bytes(), old)

    def test_K12_W36_a_newer_schema_refuses_every_writer_and_check_still_reads(self):
        self.approve()
        self.start()
        self.edit_json("account.json", lambda d: d.update(schema="account/2"))
        for argv in (["bind", "--binding", "x.json"], ["change-check", "--strand", "001", "--from", "x.json"],
                     self.approval_argv("0" * 64), ["live-map"],
                     ["live-map", "set", "--key", "001:B1", "--constraint", "free", "--source", "s", "--strand", "001"],
                     ["workspaces", "--strand", "001", "--use", OWN_WS] + self.fence(),
                     ["run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                      "--another-build-running", "no", "--account-check", "match"],
                     self.argv("run heartbeat"), self.argv("run end", "--calls-used", "1"),
                     self.argv("intent", "--key", "B2", "--operation", "create"),
                     self.argv("record", "--key", "B2", "--id", "1"),
                     self.argv("verify", "--key", "B2", "--result", "match", "--read", "x.json"),
                     self.argv("depart", "--key", "B2", "--what", "w", "--error-code", "E", "--decision", "later-retry"),
                     ["ui-step", "--strand", "001", "--what", "w", "--owner", "the user", "--target-version", "v0.2",
                      "--expect-sha", self.sha()],
                     self.argv("irreversible-yes", "--key", "W2", "--mode", "per-item", "--what", "w")):
            self.assertIn(("account.json", "schema"), pairs(self.refused(*argv)), argv)
        code, blocking, _ = self.check()
        self.assertEqual((code, ("account.json", "schema") in blocking), (1, True))

    def test_K04_G49_runs_from_a_plugin_copy_and_writes_nothing_there(self):
        """Windows run: the same launch form, [interpreter, script path, ...], with no shell."""
        plugin = make_plugin(self.tmp / "plugin copy")
        before = sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*"))
        env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
        env["HOME"] = env["USERPROFILE"] = str(self.tmp / "interpreter home")
        SubprocessTest.sequence(self, plugin, env)
        self.assertEqual(sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*")), before)


class SubprocessTest(Base):

    @staticmethod
    def sequence(case, plugin, env):
        """One call of every subcommand group, each in its own process, at the machine's own clock."""
        def launch(*argv):
            done = subprocess.run([sys.executable, str(plugin / "scripts" / "ledger.py"), "--record", str(case.root)]
                                  + [str(a) for a in argv], env=env, capture_output=True, timeout=120)
            data = json.loads(done.stdout.decode("utf-8"))
            case.assertNotIn(b"\r", done.stdout)
            case.four_parts(data)
            return done.returncode, data

        def sha():
            return case.sha()

        def fence():
            return ["--lease-epoch", "2", "--session-label", LABEL, "--run-id", run]
        case.assertEqual(launch("check")[0], 2)
        binding = case.put("binding.json", {"me": {"id": "20000001", "name": "The user", "kind": "admin"},
                                            "account": {"id": "10000001", "slug": "example-account", "name": "Example",
                                                        "tier": "standard", "products": [{"id": "30000001", "kind": "core"}]},
                                            "version": {"kind": "release_candidate", "value": "2026-10"}})
        case.assertEqual(launch("bind", "--binding", binding)[0], 0)
        cc = case.put("cc.json", {"ring": "release_candidate 2026-10", "versions_seen": ["2026-10"],
                                  "release_notes_since": "not-read", "roster_diff": {"added": [], "removed": [], "renamed": []},
                                  "schema_diff": [], "result": "no change affecting this build", "approved_by_user": None})
        case.assertEqual(launch("change-check", "--strand", "001", "--from", cc)[0], 0)
        frozen = case.make_v2()
        case.assertEqual(launch(*case.approval_argv(frozen))[0], 0)
        code, data = launch("run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                            "--another-build-running", "no", "--account-check", "match", "--expect-sha", sha())
        case.assertEqual(code, 0, data)
        run = data["run_id"]
        for argv in (("intent", "--key", "W2", "--operation", "create", "--product", "crm"),
                     ("record", "--key", "W2", "--id", SALES_WS)):
            case.assertEqual(launch(*(list(argv) + ["--strand", "001"] + fence() + ["--expect-sha", sha()]))[0], 0)
        read = case.read_file("W2", {"name": "Larkmoor Joinery – Sales", "kind": "open"})
        for argv in (("verify", "--key", "W2", "--result", "match", "--read", read), ("run", "heartbeat"),
                     ("irreversible-yes", "--key", "F1", "--mode", "per-item", "--what", "create the folder"),
                     ("depart", "--key", "B1.G2", "--what", "the group call failed", "--error-code", "E1",
                      "--decision", "blueprint-revision")):
            code, data = launch(*(list(argv) + ["--strand", "001"] + fence() + ["--expect-sha", sha()]))
            case.assertEqual(code, 0, data)
        case.assertEqual(launch("workspaces", "--strand", "001", "--product", "crm", "--id", SALES_WS, "--name",
                                "Larkmoor Joinery – Sales", "--created-in", "001/v0.2", *fence())[0], 0)
        case.assertEqual(launch("ui-step", "--strand", "001", "--what", "turn on the Kanban view", "--owner", "the user",
                                "--target-version", "v0.2", "--expect-sha", sha())[0], 0)
        case.assertEqual(launch("live-map")[0], 0)
        case.assertEqual(launch("run", "end", "--strand", "001", "--calls-used", "5", *fence(), "--expect-sha", sha())[0], 0)
        case.assertEqual(launch("live-map", "set", "--key", "001:W2", "--constraint", "free", "--source",
                                "decision 2026-11-05 10:00", "--strand", "001")[0], 0)
        case.assertEqual(launch("classify")[0], 3)
        case.assertEqual(launch("migrate")[0], 3)

    def test_K23_K26_every_group_runs_as_a_subprocess_with_no_shell(self):
        """Windows run."""
        SubprocessTest.sequence(self, self.plugin, dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def test_K47_two_writers_at_once_lose_nothing_and_tear_nothing(self):
        """Windows run: two processes, one ledger, the same sha: one writes, one is refused."""
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        sha = self.sha()
        workers = [subprocess.Popen([sys.executable, str(self.plugin / "scripts" / "ledger.py"), "--record",
                                     str(self.root), "ui-step", "--strand", "001", "--what", "step %d" % n, "--owner",
                                     "the user", "--target-version", "v0.1", "--expect-sha", sha], env=env,
                                    stdout=subprocess.PIPE) for n in range(2)]
        for worker in workers:
            worker.communicate(timeout=60)
        self.assertEqual(sorted(w.returncode for w in workers), [0, 1])
        self.assertEqual(len(self.data()["ui_steps"]), 1)


class MutexTest(Base):

    def test_K41_K42_K43_K44_every_read_and_write_sits_inside_one_hold(self):
        seen, real_read, real_write, real_fence = [], mc.read_json, mc.write_file, mc.lease_fence

        def held():
            return any(key[1] == threading.get_ident() for key in mc._HELD)

        def read(path, name=None):
            if Path(path).name in ("account.json", "build.json", "lock.json"):
                seen.append(("read", Path(path).name, held()))
            return real_read(path, name)

        def write(path, data, root, backup=True, backup_dir=None):
            seen.append(("write", Path(path).name, held()))
            return real_write(path, data, root, backup, backup_dir)

        def fence(*args):
            seen.append(("fence", "lock.json", held()))
            return real_fence(*args)
        with mock.patch.object(mc, "read_json", read), mock.patch.object(mc, "write_file", write), \
                mock.patch.object(mc, "lease_fence", fence):
            self.approve()
            self.start()
            self.sales()
            self.intent("B2", "--workspace", SALES_WS)
            self.record("B2", "--id", "90300000002")
            self.end()
        self.assertTrue(seen)
        self.assertEqual([entry for entry in seen if not entry[2]], [])
        names = [entry[:2] for entry in seen]  # K104: the fence comes before the first write of a fenced command
        self.assertLess(names.index(("fence", "lock.json")), max(n for n, e in enumerate(names) if e == ("write", "build.json")))

    def test_K48_K49_K50_K51_K120_W25_W33_run_end_reports_what_a_failure_left_committed(self):
        cases = (("account.json", 2, []), ("live-map.md", 1, ["account.json"]),
                 ("build.json", 1, ["account.json", "live/live-map.md"]),
                 ("lock.json", 2, ["account.json", "live/live-map.md", B1J]))
        for name, nth, written in cases:
            with self.subTest(name=name):
                self.copy_home()
                os.environ["MMB_HOME"] = str(self.home)
                self.approve()
                self.start()
                self.sales()
                self.now = CLOCK + timedelta(minutes=1)  # the fence then writes the mirror and the lock first
                with self.failing(name, nth):
                    code, data = self.ledger(*self.argv("run end", "--calls-used", "4"))
                self.assertEqual(code, 3)
                if not written:
                    self.assertNotIn("committed", data)
                    self.assertEqual(data["error"]["file"], "account.json")
                    continue
                self.assertEqual(data["error"]["field"], "committed")
                report = data["committed"]
                self.assertEqual(set(report), {"command", "written", "not_written", "lease", "run_id", "next", "shas"})
                self.assertEqual((report["command"], report["written"], report["run_id"]), ("run end", written, self.run_id))
                self.assertEqual(report["shas"], {rel: self.sha(rel) for rel in written})  # R19
                self.assertIn(".work/lock.json", report["not_written"])
                self.assertIn("same run end call", report["next"])
                self.ok(*self.argv("run end", "--calls-used", "4"))  # the repeat completes it
                self.assertEqual(self.lease()["state"], "released")
                self.assertEqual(self.data()["runs"][-1]["state"], "ended")

    def test_W25_W33_run_start_retries_with_its_run_id_after_a_failed_ledger_write(self):
        self.approve()
        self.change_check()
        with self.failing("build.json"):
            code, data = self.ledger("run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                                     "--another-build-running", "no", "--account-check", "match", "--expect-sha", self.sha())
        run = data["committed"]["run_id"]
        self.assertEqual((code, data["committed"]["lease"]["refreshed"]["run_id"], self.lease()["run_id"]), (3, run, run))
        self.assertIn("--run-id %s" % run, data["committed"]["next"])
        done = self.ok("run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                       "--another-build-running", "no", "--account-check", "match", "--run-id", run,
                       "--expect-sha", self.sha())
        self.assertEqual((done["run_id"], self.data()["runs"][-1]["id"]), (run, run))
        self.refused("run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                     "--another-build-running", "no", "--account-check", "match", "--run-id", run, "--expect-sha", self.sha())


class FenceFirstTest(Base):
    """K104: each of the eight fenced commands calls lease_fence before its first write, and a stale fence writes nothing."""

    def setUp(self):
        super().setUp()
        self.client()
        self.approve()
        self.start()

    def spied(self, run):
        events, real_write, real_fence = [], mc.write_file, mc.lease_fence

        def write(path, data, root, backup=True, backup_dir=None):
            events.append("write " + Path(path).name)
            return real_write(path, data, root, backup, backup_dir)

        def fence(*args):
            events.append("fence")
            return real_fence(*args)
        with mock.patch.object(mc, "write_file", write), mock.patch.object(mc, "lease_fence", fence):
            result = run()
        return events, result

    def fenced(self, make_argv):
        """Fence first on the valid call; then a stale epoch and a wrong label each refused at the fence, nothing written."""
        events, data = self.spied(lambda: self.ok(*make_argv()))
        self.assertEqual(events[0], "fence", events)
        self.assertTrue(any(e.startswith("write ") for e in events), events)
        self.assertEqual(events.count("fence"), 1, events)
        return data

    def stale(self, prepare, make_argv):
        for what in ("epoch", "label"):
            with self.subTest(stale=what):
                self.copy_home()
                os.environ["MMB_HOME"] = str(self.home)
                self.client()
                self.approve()
                self.start()
                prepare()
                if what == "epoch":
                    self.epoch = "1"
                else:
                    self.label = "another session label"
                argv = make_argv()
                events, found = self.spied(lambda: self.refused(*argv))  # exit 1 and the tree unchanged
                self.assertEqual(events, ["fence"])
                self.assertTrue(found)

    def check_command(self, prepare, make_argv):
        prepare()
        self.fenced(make_argv)
        self.stale(prepare, make_argv)

    def prep_workspace(self):
        self.yes("W2")
        self.intent("W2", "--product", "crm")
        self.record("W2", "--id", SALES_WS)
        self.verify("W2", {"name": "Larkmoor Joinery – Sales", "kind": "open"})

    def prep_intent(self):
        self.sales(client=True)

    def prep_record(self):
        self.prep_intent()
        self.intent("B2", "--workspace", SALES_WS)

    def prep_verify(self):
        self.prep_record()
        self.record("B2", "--id", "90300000002")

    def test_K104_workspaces_fences_before_its_first_write(self):
        self.check_command(self.prep_workspace, lambda: [
            "workspaces", "--strand", "001", "--product", "crm", "--id", SALES_WS, "--name", "Larkmoor Joinery – Sales",
            "--created-in", "001/v0.2"] + self.fence())

    def test_K104_run_heartbeat_fences_before_its_first_write(self):
        self.check_command(lambda: None, lambda: self.argv("run heartbeat"))

    def test_K104_run_end_fences_before_its_first_write(self):
        self.check_command(lambda: None, lambda: self.argv("run end", "--calls-used", 3))

    def test_K104_intent_fences_before_its_first_write(self):
        self.check_command(self.prep_intent, lambda: self.argv("intent", "--key", "B2", "--operation", "create",
                                                               "--workspace", SALES_WS))

    def test_K104_record_fences_before_its_first_write(self):
        self.check_command(self.prep_record, lambda: self.argv("record", "--key", "B2", "--id", "90300000002"))

    def test_K104_verify_fences_before_its_first_write(self):
        def prepare():
            self.prep_verify()
            self.read = self.read_file("B2", {"name": "Jobs", "kind": "open"})
        self.check_command(prepare, lambda: self.argv("verify", "--key", "B2", "--result", "match", "--read", self.read))

    def test_K104_depart_fences_before_its_first_write(self):
        self.check_command(lambda: None, lambda: self.argv("depart", "--key", "B1.G2", "--what", "w", "--error-code", "E",
                                                               "--decision", "later-retry"))

    def test_K104_irreversible_yes_fences_before_its_first_write(self):
        self.check_command(lambda: None, lambda: self.argv("irreversible-yes", "--key", "F1", "--mode", "per-item",
                                                           "--what", "the step for F1"))


class BindTest(Base):

    BINDING = {"me": {"id": "20000001", "name": "The user", "kind": "Admin"},
               "account": {"id": "10000001", "slug": "example-account", "name": "Example Account", "tier": "pro",
                           "products": [{"id": "30000001", "kind": "core"}, {"id": "30000002", "kind": "crm"},
                                        {"id": "30000009", "kind": "marketing"}]},
               "version": {"kind": "release_candidate", "value": "2026-10"}}

    def unbind(self):
        self.edit_json("account.json", lambda d: d["account"].update({k: "unbound" for k in d["account"] if k not in (
            "kind", "build_target", "products")}, products=[]))
        self.edit_fm("CLIENT.md", monday_account_id="unbound", monday_account_slug="unbound",
                     monday_bound_user_id="unbound", monday_bound_at="unbound")

    def bind(self, binding=None, **account):
        doc = json.loads(json.dumps(binding or self.BINDING))
        doc["account"].update(account)
        return "bind", "--binding", self.put("binding.json", doc)

    def test_K52_K53_K60_K61_bind_writes_the_account_and_the_mirror_check_agrees(self):
        self.unbind()
        data = self.ok(*self.bind())
        account = self.data("account.json")["account"]
        self.assertEqual({k: account[k] for k in ("id", "slug", "tier", "bound_user_id", "builder_role", "kind",
                                                  "build_target")},
                         {"id": "10000001", "slug": "example-account", "tier": "pro", "bound_user_id": "20000001",
                          "builder_role": "admin", "kind": "own", "build_target": "own-account"})
        self.assertEqual(account["products"], [{"id": "30000001", "kind": "core"}, {"id": "30000002", "kind": "crm"}])
        self.assertEqual(account["bound_at"], "2026-11-05T14:30:00Z")
        self.assertNotIn("unbound", json.dumps(account))
        self.assertEqual(self.data("account.json")["api"]["connector_ring"], "release_candidate 2026-10")
        self.assertEqual(data["log"][0]["type"], "binding")
        self.edit_fm("CLIENT.md", **data["mirror"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.rec.main(["--record", str(self.root), "check"])
        blocking = pairs(json.loads(out.getvalue())["blocking"])
        self.assertEqual({p for p in blocking if p[0] == "CLIENT.md"}, set())

    def test_K54_kind_and_target_follow_the_record(self):
        self.unbind()
        self.edit_fm("CLIENT.md", account_kind="client")
        self.assertIn(("CLIENT.md", "build_target"), pairs(self.refused(*self.bind())))
        self.client()
        self.ok(*self.bind(id="10000077", slug="client-account"))
        self.assertEqual(self.data("account.json")["account"]["build_target"], "client-account")

    def test_K55_K56_sandbox_accounts_bind_only_sandbox_records(self):
        self.unbind()
        self.client()
        (self.home / "local" / "sandbox-accounts.txt").write_text(
            "# kind | account_id | account_slug | workspace_id | label | note\n"
            "sandbox | 10000088 | example-sandbox | * | probes | test account\n", encoding="utf-8")
        found = self.refused(*self.bind(id="10000099", slug="example-sandbox"))  # matched on the slug alone
        self.assertIn(("local/sandbox-accounts.txt", "sandbox"), pairs(found))
        self.assertIn("example-sandbox", words(found))
        self.edit_fm("CLIENT.md", account_kind="sandbox", build_target="none")
        self.edit_json("account.json", lambda d: d["account"].update(kind="sandbox", build_target="none"))
        self.assertIn(("local/sandbox-accounts.txt", "sandbox"), pairs(self.refused(*self.bind(id="10000077", slug="other"))))
        self.ok(*self.bind(id="10000088", slug="example-sandbox"))

    def test_K57_K58_own_record_binds_the_default_account_once_and_refreshes(self):
        self.unbind()
        self.assertIn(("local/settings.json", "default_build_account"),
                      pairs(self.refused(*self.bind(id="10000077", slug="another"))))
        self.ok(*self.bind())
        first = self.data("account.json")["account"]["bound_at"]
        self.now = CLOCK + timedelta(days=1)
        again = self.ok(*self.bind(tier="enterprise"))
        account = self.data("account.json")["account"]
        self.assertEqual((again["refresh"], account["bound_at"], account["tier"]), (True, first, "enterprise"))
        self.assertIn(("account.json", "account.id"), pairs(self.refused(*self.bind(id="10000002", slug="example-account"))))
        other = json.loads(json.dumps(self.BINDING))
        other["me"]["id"] = "20000002"
        self.assertIn(("account.json", "account.bound_user_id"), pairs(self.refused(*self.bind(other))))

    def test_K59_K61_bind_writes_no_workspace_and_refuses_a_numeric_id(self):
        before = self.data("account.json")
        self.ok(*self.bind())
        after = self.data("account.json")
        self.assertEqual((after["client_workspaces"], after["guard_index"]["client_workspace_ids"]),
                         (before["client_workspaces"], before["guard_index"]["client_workspace_ids"]))
        numeric = json.loads(json.dumps(self.BINDING))
        numeric["account"]["id"] = 10000001
        found = self.refused("bind", "--binding", self.put("binding.json", numeric))
        self.assertIn((".work/strands/001/binding.json", "account.id"), pairs(found))


class WorkspacesTest(Base):
    """W38 as R8 reads it: `--product` records only a workspace row this strand's build wrote or verified."""

    SALES = "Larkmoor Joinery – Sales"

    def setUp(self):
        super().setUp()
        self.approve(rows=TABLE + (("W3", "workspace", "Larkmoor Joinery – Sales two"),),
                     extra=["--irreversible", "W3"])
        self.start()

    def ws(self, *argv):
        return ["workspaces", "--strand", "001"] + list(argv) + self.fence()

    def built(self, key, ws_id, name, *argv, product="crm"):
        self.intent(key, "--product", product, *argv)
        self.record(key, "--id", ws_id)
        self.verify(key, {"name": name, "kind": "open"})

    def test_K36_K62_K64_K66_K68_a_product_workspace_is_recorded_beside_the_others(self):
        core = self.data("account.json")["client_workspaces"]["core"]
        self.built("W2", SALES_WS, self.SALES)
        data = self.ok(*self.ws("--product", "crm", "--id", SALES_WS, "--name", self.SALES, "--created-in", "001/v0.2"))
        account = self.data("account.json")
        self.assertEqual(account["client_workspaces"]["crm"], {"id": SALES_WS, "name": self.SALES,
                                                               "created_in": "001/v0.2"})
        self.assertEqual(account["client_workspaces"]["core"], core)
        self.assertIn(SALES_WS, account["guard_index"]["client_workspace_ids"])
        self.assertIn(SALES_WS, account["guard_index"]["build_targets_by_strand"]["001"]["workspace_ids"])
        self.assertEqual(account["guard_index"]["product_workspaces"][SALES_WS], "crm")
        self.assertEqual(data["mirror"]["client_workspaces"], "core:40000001;crm:%s" % SALES_WS)
        lease = self.lease()
        self.assertEqual(account["guard_index"]["lease"], {k: lease[k] for k in ("strand", "epoch", "session_label",
                                                                                 "heartbeat_at")})

    def test_K63_K65_K67_K138_the_refusals(self):
        self.assertIn("core | crm | service", words(self.refused(*self.ws("--product", "dev", "--id", "90100000003",
                                                                         "--name", "Dev", "--created-in", "001/v0.2"))))
        found = self.refused(*self.ws("--product", "service", "--id", OPS_WS, "--name", "x", "--created-in", "001/v0.2"))
        self.assertIn("never-demo", words(found))
        self.assertIn("Internal Planning", words(found))
        found = self.refused(*self.ws("--use", "90100000444"))
        self.assertIn(A21_WORDS, words(found))
        self.assertIn(("(flags)", "--created-in"), pairs(self.refused(*self.ws(
            "--product", "crm", "--id", SALES_WS, "--name", "x", "--created-in", "002/v0.1"))))

    def test_K145_W39_a_second_workspace_in_a_product_needs_the_direction_change(self):
        self.built("W2", SALES_WS, self.SALES)
        self.ok(*self.ws("--product", "crm", "--id", SALES_WS, "--created-in", "001/v0.2"))
        change = "2026-11-05 14:30 · 001 · decision · v0.2 · fresh start"
        self.built("W3", "90100000003", "Larkmoor Joinery – Sales two", "--direction-change", change)
        self.ok(*self.ws("--product", "crm", "--id", "90100000003", "--created-in", "001/v0.2"))  # the row's reference
        account = self.data("account.json")
        self.assertEqual(account["client_workspaces"]["crm"]["id"], "90100000003")
        self.assertEqual((account["superseded_workspaces"][0]["id"], account["superseded_workspaces"][0][
            "direction_change"]), (SALES_WS, change))
        self.assertTrue({SALES_WS, "90100000003"} <= set(account["guard_index"]["client_workspace_ids"]))


class ApprovalTest(Base):

    def test_K69_K82_K83_K158_K176_the_entry_and_its_lists(self):
        data = self.approve()
        entry = self.data()["approvals"][-1]
        self.assertEqual(list(entry), ["version", "qualified_version", "revision", "frozen_file", "sha256", "approved_at",
                                       "approved_words", "approved_in_session", "approval_mode", "element_count",
                                       "irreversible_listed", "automations_listed", "workflows_listed", "agents_listed",
                                       "sequences_listed", "notifies_approved", "rests_on", "live_objects_touched"])
        self.assertEqual(entry["rests_on"], {"clearance": "cleared to build", "purpose": "proof-of-concept",
                                             "assumptions": 1, "assumed_terms": 1, "forks_on_leaning": 1})
        self.assertIn("VB1.PUB", entry["irreversible_listed"])
        self.assertEqual((entry["automations_listed"], entry["agents_listed"], entry["frozen_file"]),
                         (["A1"], ["AG1"], "versions/v0.2/blueprint-r1.md"))
        self.assertEqual(entry["element_count"], len([r for r in TABLE if r[1] not in ("publication", "activation",
                                                                                      "ui_step")]))
        self.assertEqual(set(data["delta"]["kept"]), {"W1", "B1", "B1.V1"})
        self.assertIn("B2", data["delta"]["new"])
        row = self.row("B2")
        self.assertEqual((row["status"], row["approval_ref"], row["blueprint_ref"]), ("planned", "v0.2r1", "v0.2r1#B2"))
        self.assertEqual((self.row("AG1")["prompt_ref"], self.row("B9")["origin"]), ("v0.2r1#AG1", "pre-existing-referenced"))
        self.assertEqual(self.row("B1")["status"], "verified")

    def test_K70_K71_K83_the_refusals_of_a_revision(self):
        sha = self.make_v2()
        path = self.root / V2 / "blueprint-r1.md"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertIn("--sha256", words(self.refused(*self.approval_argv(sha))))
        self.assertIn("is not a row", words(self.refused(*self.approval_argv(self.make_v2(), irreversible=IRREVERSIBLE + (
            "B99",)))))
        self.assertIn("a list", words(self.refused(*self.approval_argv(self.make_v2(), irreversible=IRREVERSIBLE + ("A1",)))))
        self.assertIn("is not listed", words(self.refused(*self.approval_argv(self.make_v2(), irreversible=("W1",)))))
        for rows, prompts, expect in ((TABLE + (("B2", "board", "Again"),), None, "repeats"),
                                      (TABLE + (("BX", "board", "Odd"),), None, "is not a key"),
                                      (TABLE + (("B7", "lamp", "Odd"),), None, "no object type"),
                                      (TABLE, {"AG1": "x", "VB1": "y"}, "no prompt block")):
            self.assertIn(expect, words(self.refused(*self.approval_argv(self.make_v2(rows, prompts)))), expect)
        self.assertIn("no element-key table", words(self.refused(*self.approval_argv(self.make_v2(heading="## Elements")))))
        self.approve()
        self.assertIn("approved already", words(self.refused(*self.approval_argv(mc.sha256_file(path)))))

    def test_K84_touches_and_reads_live(self):
        sha = self.make_v2()
        self.assertIn("not a constraint", words(self.refused(*(self.approval_argv(sha) + ["--touches", "001:B1=maybe"]))))
        self.ok(*(self.approval_argv(sha) + ["--touches", "001:B1=change-with-own-yes"]))
        build = self.data()
        self.assertEqual((build["approvals"][-1]["live_objects_touched"], build["reads_live"]),
                         ([{"key": "001:B1", "constraint": "change-with-own-yes"}], ["001:B1"]))

    def test_K72_W44_the_approval_mode_of_each_record(self):
        self.assertEqual(self.approve()["approval"]["approval_mode"], "own-account-poc")
        for variant in ("working", "client", "sandbox"):
            self.copy_home()
            os.environ["MMB_HOME"] = str(self.home)
            if variant == "client":
                self.client()
            if variant == "sandbox":
                self.edit_json("account.json", lambda d: d["account"].update(kind="sandbox", build_target="none"))
            purpose = "working-solution" if variant == "working" else "proof-of-concept"
            self.assertEqual(self.approve(purpose=purpose)["approval"]["approval_mode"], "per-list", variant)

    def test_K40_a_strand_without_a_ledger_is_refused_and_none_is_created(self):
        found = self.refused("run", "start", "--strand", "002", "--lease-epoch", "2", "--session-label", LABEL,
                             "--another-build-running", "no", "--account-check", "match", "--expect-sha", "none")
        self.assertIn((S2 + "/solution/build.json", "(whole file)"), pairs(found))
        self.edit_fm(S2 + "/STRAND.md", kind="non-platform")
        self.assertIn((S2 + "/STRAND.md", "kind"), pairs(self.refused(
            "approval", "--strand", "002", "--sha256", "0" * 64, "--words", "w", "--session", "s", "--expect-sha", "none")))
        self.assertFalse((self.root / S2 / "solution" / "build.json").exists())


class ChangeCheckTest(Base):

    def test_K88_K89_K90_K93_K95_the_block_and_nothing_else(self):
        mc.lease_release(self.root, "2", LABEL)  # R18: with strand 001 holding the lease, 002's check is refused
        before = self.data("account.json")
        data = self.change_check(strand="002")
        after = self.data("account.json")
        block = after["change_check"]
        self.assertEqual(list(block), ["at", "for_strand", "ring", "versions_seen", "release_notes_since", "roster_diff",
                                       "schema_diff", "result", "approved_by_user"])
        self.assertEqual((block["at"], block["for_strand"], block["approved_by_user"], data["asked_by"]),
                         ("2026-11-05T14:30:00Z", "002", None, "002"))
        for key in before:
            if key not in ("change_check", "updated_at"):
                self.assertEqual(after[key], before[key], key)
        mc.lease_take(self.root, "001")
        self.assertIn("held by strand 001", " ".join(f["problem"] for f in self.refused(
            "change-check", "--strand", "002", "--from", self.put("cc2.json", {k: v for k, v in block.items() if k not in (
                "at", "for_strand")}))))

    def test_K91_K92_K94_values_and_the_two_outcomes(self):
        bad = {"ring": "r", "versions_seen": [], "release_notes_since": "yesterday",
               "roster_diff": {"added": [], "removed": []}, "schema_diff": [], "result": "fine", "approved_by_user": None}
        found = self.refused("change-check", "--strand", "001", "--from", self.put("cc.json", bad))
        self.assertEqual({f["field"] for f in found}, {"release_notes_since", "roster_diff", "result"})
        self.assertTrue(self.change_check()["go_on"])
        self.assertFalse(self.change_check("change affecting this build")["go_on"])
        self.assertTrue(self.change_check("change affecting this build", approved="2026-11-05 14:31 · 001 · decision")["go_on"])


class RunTest(Base):

    def test_K96_K97_K98_K99_K103_run_start_enters_its_run_through_the_refresh(self):
        self.now = CLOCK + timedelta(minutes=1)
        data = self.start()
        self.assertEqual(data["run_id"], "run-2026-11-05-1")
        lease = self.lease()
        self.assertEqual((lease["run_id"], lease["heartbeat_at"]), ("run-2026-11-05-1", "2026-11-05T14:31:00Z"))
        build = self.data()
        run = build["runs"][-1]
        self.assertEqual(list(run), ["id", "version", "kind", "session_label", "lease_epoch", "another_build_running",
                                     "started_at", "heartbeat_at", "ended_at", "state", "calls_estimated", "calls_used",
                                     "account_checks", "recovery_first"])
        self.assertFalse(run["recovery_first"])
        self.assertEqual((build["lease_epoch_at_run"], run["state"], run["ended_at"], run["calls_used"]), (2, "running", None, None))
        self.assertRegex(run["another_build_running"], r"^no, answered \d\d:\d\d$")
        self.assertEqual(run["account_checks"], [{"at": "2026-11-05T14:31:00Z", "before": "run start", "result": "match"}])
        self.assertEqual((run["calls_estimated"], build["preflight"]["version"]), ([10, 20], "v0.1"))

    def test_K100_K121_a_yes_to_the_one_question_stops_and_releases(self):
        history = len(mc.read_lock(self.root)["history"])
        data = self.ok("run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                       "--another-build-running", "yes", "--answer-words", "yes, the other laptop is building",
                       "--account-check", "match", "--expect-sha", self.sha())
        run = self.data()["runs"][-1]
        self.assertEqual((data["released"], run["state"], run["calls_used"]), (True, "ended", 0))
        self.assertIn("the other laptop", run["another_build_running"])
        self.assertEqual((self.lease()["state"], len(mc.read_lock(self.root)["history"])), ("released", history + 1))

    def test_K101_K102_W30_who_may_start_a_run_and_how_the_id_is_counted(self):
        base = ["run", "start", "--strand", "001", "--another-build-running", "no", "--account-check", "match"]
        lock = mc.read_lock(self.root)
        for epoch, label in (("1", LABEL), ("2", "20261028-0915-m3p8")):
            self.refused(*(base + ["--lease-epoch", epoch, "--session-label", label, "--expect-sha", self.sha()]))
        self.assertEqual(mc.read_lock(self.root), lock)
        self.assertIn("match", words(self.refused(*(base[:-1] + ["mismatch", "--lease-epoch", "2", "--session-label",
                                                                  LABEL, "--expect-sha", self.sha()]))))
        self.edit_json(B1J, lambda d: d["runs"].append(dict(d["runs"][0], id="run-2026-11-05-4")))
        self.assertEqual(self.start()["run_id"], "run-2026-11-05-5")
        self.assertIn("already carries", words(self.refused(*(base + ["--lease-epoch", "2", "--session-label", LABEL,
                                                                       "--expect-sha", self.sha()]))))
        old = self.run_id
        self.go("run end", "--calls-used", "0")
        self.retake()
        self.refused(*(base + ["--lease-epoch", self.epoch, "--session-label", self.label, "--run-id", old,
                               "--expect-sha", self.sha()]))

    def test_K104_K105_K106_K107_K108_K134_K135_K136_the_three_parts_of_the_fence(self):
        self.start()
        old = (self.epoch, self.label, self.run_id)
        self.end()
        self.retake()
        self.start()
        new = (self.epoch, self.label, self.run_id)
        for (epoch, label, run), part in (((old[0], new[1], new[2]), "epoch"), ((new[0], old[1], new[2]), "session"),
                                          ((new[0], new[1], old[2]), "run")):
            self.epoch, self.label, self.run_id = epoch, label, run
            found = self.refused(*self.argv("run heartbeat"))
            self.assertIn(part, words(found).lower(), part)
        self.epoch, self.label, self.run_id = new
        self.go("run heartbeat")

    def test_K109_K110_K112_K113_K114_a_write_needs_a_started_run_and_the_three_values(self):
        self.approve()
        self.edit_json(B1J, lambda d: d["runs"].append(dict(d["runs"][0], id="run-2026-11-05-9", state="running")))
        self.run_id = "run-2026-11-05-9"
        self.change_check()
        found = self.no("intent", "--key", "B2", "--operation", "create", "--workspace", OWN_WS)
        self.assertIn("no run has started", words(found))
        self.edit_json(B1J, lambda d: d["runs"].pop())
        self.start(cc=False)
        for flag in ("--lease-epoch", "--session-label", "--run-id"):
            argv = self.argv("run heartbeat")
            index = argv.index(flag)
            del argv[index:index + 2]
            self.assertIn(flag, words(self.refused(*argv)) + " ".join(f["problem"] for f in self.refused(*argv)))
        self.label = "20261105-1405-zzzz"
        self.assertIn("session", words(self.no("intent", "--key", "B2", "--operation", "create", "--workspace", OWN_WS)))
        self.label = LABEL
        history = len(mc.read_lock(self.root)["history"])
        self.now = CLOCK + timedelta(minutes=2)
        self.go("run heartbeat", "--account-check", "mismatch", "--before", "writes 21 to 40")
        self.assertEqual((self.lease()["heartbeat_at"], len(mc.read_lock(self.root)["history"])),
                         ("2026-11-05T14:32:00Z", history))
        run = self.data()["runs"][-1]
        self.assertEqual((run["heartbeat_at"], run["account_checks"][-1]["result"]), ("2026-11-05T14:32:00Z", "mismatch"))

    def test_K115_K116_K117_K118_K119_K201_K226_run_end_writes_verified_rows_and_releases(self):
        self.approve()
        self.start()
        self.sales()
        self.intent("B2", "--parent-key", "W2")
        self.record("B2", "--id", "90300000002")
        self.verify("B2", {"name": "Orders", "type": "board", "state": "active", "workspace_id": SALES_WS})
        self.intent("B2.C1")
        self.record("B2.C1", "--id", "supplier_mkx1a2b3")
        self.verify("B2.C1", {"id": "supplier_mkx1a2b3", "title": "Sup"}, result="mismatch")
        self.intent("D1", "--workspace", OWN_WS)
        self.record("D1", "--id", "90300000041")
        self.go("depart", "--key", "B1.G2", "--what", "w", "--error-code", "E9", "--decision", "later-retry")
        history = len(mc.read_lock(self.root)["history"])
        data = self.end(used=11)
        run = self.data()["runs"][-1]
        self.assertEqual((run["state"], run["calls_used"], run["ended_at"]), ("ended", 11, "2026-11-05T14:30:00Z"))
        lock = mc.read_lock(self.root)
        self.assertEqual((lock["state"], len(lock["history"]), lock["history"][-1]["event"]), ("released", history + 1, "released"))
        live = self.data("account.json")["live_objects"]
        for key in ("001:W2", "001:B2"):
            self.assertEqual((live[key]["constraint"], live[key]["constraint_source"]), ("change-with-own-yes",
                                                                                         "pending strand close"))
        self.assertEqual(live["001:W2"]["kind"], "workspace")
        self.assertEqual(live["001:B2"]["digest"], self.row("B2")["verify"]["digest"])
        self.assertEqual((live["001:B2"]["workspace"], live["001:B2"]["introduced_in"]), (SALES_WS, "001/v0.2"))
        for key in ("001:B2.C1", "001:D1", "001:B1.G2", "001:A1"):
            self.assertNotIn(key, live)
        self.assertEqual(set(data["live_rows"]["created"]), {"001:W2", "001:B2"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.rec.main(["--record", str(self.root), "check"])
        self.assertEqual([f for f in json.loads(out.getvalue())["blocking"] if "live" in f["file"] or "live_objects" in
                          f["field"]], [])
        self.assertEqual(self.check()[1], set())

    def test_W32_run_end_refuses_a_row_still_attempting(self):
        self.approve()
        self.start()
        self.intent("B2", "--workspace", OWN_WS)
        self.assertIn("B2", words(self.no("run end", "--calls-used", "3")))


class RefusalTest(Base):

    def setUp(self):
        super().setUp()
        self.approve()
        self.start()

    def test_K122_K183_the_status_chain(self):
        self.assertIn("status chain", words(self.no("intent", "--key", "B1", "--operation", "create")))
        self.assertIn("attempting", words(self.no("record", "--key", "B2", "--id", "90300000002")))
        self.assertIn("record first", words(self.no("verify", "--key", "B2", "--result", "match", "--read",
                                                    self.read_file("B2", {"name": "Orders"}))))
        self.intent("B2", "--workspace", OWN_WS)  # planned to attempting
        self.no("intent", "--key", "B2", "--operation", "create")
        self.reconcile()  # R10: B2 is not live, so the reconcile classes it retry
        self.go("intent", "--key", "B2", "--operation", "create", "--retry")  # attempting to attempting
        self.record("B2", "--id", "90300000002")  # attempting to written
        self.verify("B2", {"name": "Orders"}, result="not-checkable", note="the user checks the board by eye")
        self.assertEqual(self.row("B2")["status"], "written")  # written stays written
        self.verify("B2", {"name": "Orders"}, result="mismatch")
        self.go("intent", "--key", "B2", "--operation", "create", "--retry")  # mismatch to attempting, once
        self.record("B2", "--id", "90300000002")
        self.verify("B2", {"name": "Orders"}, result="mismatch")
        self.assertIn("tried already", words(self.no("intent", "--key", "B2", "--operation", "create", "--retry")))
        self.go("depart", "--key", "B2", "--what", "w", "--error-code", "E1", "--decision", "later-retry")
        self.go("intent", "--key", "B2", "--operation", "create", "--retry")  # departed (later-retry) to attempting
        self.record("B2", "--id", "90300000002")
        self.verify("B2", {"name": "Orders"})
        self.intent("B2", op="update")  # verified to attempting, the version joins changed_in when it differs
        self.record("B2", "--id", "90300000002")
        self.verify("B2", {"name": "Orders"})
        self.intent("B1", "--approval-ref", "v0.2r1", "--evidence", "no automation or view outside the strand reads it",
                    op="archive")
        self.record("B1")
        self.assertEqual((self.row("B1")["status"], self.row("B1")["state"]), ("removed", "archived"))
        self.verify("B1", {"name": "Jobs", "state": "archived"})
        self.assertEqual(self.row("B1")["status"], "removed")
        self.assertIn("final", words(self.no("depart", "--key", "B1", "--what", "w", "--error-code", "E",
                                             "--decision", "later-retry")))

    def test_K123_K124_K125_K126_K155_a_row_without_its_approval_ref_is_refused(self):
        self.intent("WF1", "--workspace", OWN_WS)
        self.record("WF1", "--id", "90300000071")
        self.verify("WF1", {"name": "Intake flow", "state": "ACTIVE", "validation": "no issues"})
        for key in ("W2", "F1", "A1", "WF1.PUB", "AG1", "SQ1", "B1"):
            self.edit_json(B1J, lambda d, k=key: d["objects"][k].update(approval_ref=None))
        for key, op, extra in (("W2", "create", ["--product", "crm"]), ("F1", "create", ["--workspace", OWN_WS]),
                               ("A1", "create", ["--parent-key", "B1"]), ("AG1", "create", ["--scope", OWN_WS]),
                               ("SQ1", "create", ["--scope", OWN_WS, "--notifies", "20000001"]),
                               ("WF1.PUB", "publish", []), ("B1", "archive", ["--evidence", "nothing else reads it"])):
            found = self.no("intent", "--key", key, "--operation", op, *extra)
            self.assertIn((B1J, "objects.%s.approval_ref" % key), pairs(found), key)
        self.intent("F1", "--workspace", OWN_WS, "--approval-ref", "v0.2r1")
        self.assertTrue(self.row("F1")["irreversible"])

    def test_K127_K128_K129_K130_K178_origins_and_prior_states(self):
        prior = self.put("prior.json", {"name": "Shared stock", "columns": []})
        self.assertIn("prior state", words(self.no("intent", "--key", "B5", "--operation", "create", "--workspace", OWN_WS,
                                                   "--prior-state", prior)))
        self.assertIn("pre-existing-modified", words(self.no(
            "intent", "--key", "B5", "--operation", "create", "--workspace", OWN_WS, "--origin", "found")))
        self.assertIn("no prior state", words(self.no("intent", "--key", "B5", "--operation", "create", "--workspace",
                                                      OWN_WS, "--origin", "pre-existing-modified")))
        live_row = {"monday_id": "90300000077", "kind": "board", "workspace": OWN_WS, "name_at_build": "Stock",
                    "owner_strand": "002", "introduced_in": "002/v0.1", "state": "active", "constraint": "do-not-change",
                    "constraint_source": "calls/2026-10-20-discovery.md@00:12:10", "digest": "b7:00000000",
                    "last_verified": "2026-11-01", "dependants": []}
        self.edit_json("account.json", lambda d: d["live_objects"].update({"002:B7": live_row}))
        other = ["--workspace", OWN_WS, "--origin", "other-strand-modified", "--prior-state", prior]
        found = self.no("intent", "--key", "B5", "--operation", "create", *other, "--source-strand", "002",
                        "--live-key", "002:B7")
        self.assertIn("do-not-change", words(found))
        self.assertIn("discovery.md@00:12:10", words(found))
        self.assertIn("source_strand", " ".join(f["field"] for f in self.no(
            "intent", "--key", "B5", "--operation", "create", *other, "--live-key", "002:B7")))
        self.edit_json("account.json", lambda d: d["live_objects"]["002:B7"].update(constraint="change-with-own-yes"))
        self.intent("B5", *other, "--source-strand", "002", "--live-key", "002:B7")
        row = self.row("B5")
        self.assertEqual((row["origin"], row["source_strand"], row["live_key"], row["irreversible"]),
                         ("other-strand-modified", "002", "002:B7", True))

    def test_K131_K132_K133_K173_K179_ids_parents_shas_and_deletes(self):
        self.intent("B2", "--workspace", OWN_WS)
        self.record("B2", "--id", "90300000002")
        found = self.no("verify", "--key", "B2", "--result", "match", "--read", self.put("n.json", {
            "read": "r", "object": {"id": 50000001}}))
        self.assertIn((".work/strands/001/n.json", "object.id"), pairs(found))
        self.assertIn("--parent-id", words(self.no("intent", "--key", "B1.C4", "--operation", "create", "--parent-id",
                                                    "12a")) + " ".join(f["field"] for f in self.no(
            "intent", "--key", "B1.C4", "--operation", "create", "--parent-id", "12a")))
        self.assertIn("B77", words(self.no("intent", "--key", "B1.C4", "--operation", "create", "--parent-key", "B77")))
        self.assertIn(BOARD, words(self.no("intent", "--key", "B1.C4", "--operation", "create",
                                                                     "--parent-id", "999")))
        self.assertIn("no id yet", words(self.no("intent", "--key", "B1.FM1", "--operation", "create", "--parent-key",
                                                 "B1.G2")))
        stale = self.sha()
        self.ok("ui-step", "--strand", "001", "--what", "x", "--owner", "the user", "--target-version", "v0.2",
            "--expect-sha", stale)
        found = self.refused("ui-step", "--strand", "001", "--what", "y", "--owner", "the user", "--target-version",
                             "v0.2", "--expect-sha", stale)
        self.assertIn((B1J, "sha256"), pairs(found))
        self.assertIn("never deletes", words(self.no("intent", "--key", "B1", "--operation", "delete")))


class ScopeTest(Base):

    def setUp(self):
        super().setUp()
        self.approve()
        self.start()

    def b2(self, *argv):
        return self.no("intent", "--key", "B2", "--operation", "create", *argv)

    def test_K137_K146_K147_K148_K150_the_target_workspace(self):
        self.edit_json("account.json", lambda d: d["guard_index"]["client_workspace_ids"].append("90100000005"))
        found = self.b2("--workspace", "90100000005")
        self.assertIn(("account.json", "guard_index.build_targets_by_strand.001"), pairs(found))
        self.assertIn("strand 001", words(found))
        self.assertIn(A21_WORDS, words(found))
        sibling = self.b2("--workspace", "90100000999")  # a workspace of a sibling client's record
        self.assertIn("90100000999", words(sibling))
        self.assertIn(A21_WORDS, words(sibling))
        operational = self.b2("--workspace", OPS_WS)
        self.assertIn("never-demo", words(operational))
        (self.home / "local" / "sandbox-accounts.txt").write_text(
            "never-demo | 10000001 | example-account | 90100000888 | demo | kept for demos\n", encoding="utf-8")
        self.edit_json("account.json", lambda d: (d["guard_index"]["client_workspace_ids"].append("90100000888"),
                                                  d["guard_index"]["build_targets_by_strand"]["001"]["workspace_ids"]
                                                  .append("90100000888")))
        self.assertIn("never-demo | 10000001", words(self.b2("--workspace", "90100000888")))
        self.intent("B2", "--workspace", OWN_WS)
        self.assertEqual(self.row("B2")["workspace"], OWN_WS)

    def test_K139_K140_K141_K142_K143_K149_references_outside_the_client(self):
        outside = {"monday_id": "90300000555", "kind": "board", "workspace": "90100000777", "name_at_build": "Theirs",
                   "owner_strand": "001", "introduced_in": "client", "state": "active", "constraint": "free",
                   "constraint_source": "s", "digest": None, "last_verified": None, "dependants": []}
        self.edit_json("account.json", lambda d: d["live_objects"].update({"001:B8": outside}))
        for key, base in (("AG1", ["--scope", OWN_WS]), ("VB1", ["--scope", OWN_WS]),
                          ("WH1", ["--scope", OWN_WS]), ("SQ1", ["--scope", OWN_WS, "--notifies", "20000001"])):
            for ref, why in (("board:90300000555", "outside the client"), ("board:90300000666", "to place it"),
                             ("workspace:90100000777", "outside the client")):
                found = self.no("intent", "--key", key, "--operation", "create", *base, "--ref", ref)
                self.assertIn(why, words(found), (key, ref))
                self.assertIn(A21_WORDS, words(found))
        self.intent("AG1", "--scope", OWN_WS, "--ref", "board:%s" % BOARD)
        self.assertEqual(self.row("AG1")["refs"], ["board:%s" % BOARD])

    def test_K144_K177_workspace_rows_and_account_level_rows(self):
        self.intent("W2", "--product", "crm")
        row = self.row("W2")
        self.assertEqual((row["irreversible"], row["product"], self.data()["client_slug"]), (True, "crm", "larkmoor-joinery"))
        self.assertIn("--scope", " ".join(f["field"] for f in self.b2("--workspace", OWN_WS, "--scope", OWN_WS)))
        self.assertIn("no scope", words(self.no("intent", "--key", "AG1", "--operation", "create")))
        self.intent("AG1", "--scope", OWN_WS)
        self.assertEqual((self.row("AG1")["workspace"], self.row("AG1")["workspace_scope"]), (None, [OWN_WS]))


class ModesTest(Base):

    def test_K73_K74_K75_K76_K77_K78_K79_K81_K213_one_revision_on_both_build_targets(self):
        """Windows run and macOS run: the same revision on an own-account and on a client-account record."""
        rows = tuple(row + ("user",) if row[0] == "A1" else row for row in TABLE)  # R20 (a): A1 notifies the user
        self.approve(rows=rows)
        self.start()
        self.assertIn("grouped", words(self.no("intent", "--key", "A1", "--operation", "create", "--parent-key", "B1",
                                               "--notifies", "90600000001")))
        listed = self.intent("A1", "--parent-key", "B1", "--notifies", "20000001")
        workspace = self.intent("W2", "--product", "crm")
        self.record("W2", "--id", SALES_WS)
        self.agent()
        activation = self.intent("AG1.ACT", op="activate")
        for data, cls in ((listed, "list"), (workspace, "irreversible"), (activation, "publication")):
            self.assertEqual((data["class"], data["yes"], data["approval_mode"]), (cls, "card", "own-account-poc"))
        entries = self.data()["irreversible_yes"]
        self.assertEqual([(e["key"], e["mode"], e["approval_ref"]) for e in entries],
                         [("A1", "card", "v0.2r1"), ("W2", "card", "v0.2r1"), ("AG1", "card", "v0.2r1"),
                          ("AG1.ACT", "card", "v0.2r1")])
        build = self.data()
        for key, row in build["objects"].items():  # K78: every ref resolves to one entry, which names its mode
            found = [a for a in build["approvals"] if "%sr%s" % (a["version"], a["revision"]) == row["approval_ref"]]
            self.assertEqual(len(found), 1, key)
        self.copy_home()
        os.environ["MMB_HOME"] = str(self.home)
        self.client()
        self.approve(rows=rows)
        self.start()
        self.assertIn("grouped", words(self.no("intent", "--key", "A1", "--operation", "create", "--parent-key", "B1",
                                               "--notifies", "20000001")))
        self.assertIn("per-item", words(self.no("intent", "--key", "W2", "--operation", "create", "--product", "crm")))
        self.yes("A1", "grouped")
        self.assertEqual(self.intent("A1", "--parent-key", "B1", "--notifies", "20000001")["yes"], "grouped")
        for key in ("W2", "WH1"):  # the user said yes to the first and the third, not to F1
            self.yes(key)
        self.assertEqual([e["key"] for e in self.data()["irreversible_yes"] if e["mode"] == "per-item"], ["W2", "WH1"])
        self.assertEqual(self.intent("W2", "--product", "crm")["yes"], "per-item")
        self.assertIn("F1", words(self.no("intent", "--key", "F1", "--operation", "create", "--workspace", OWN_WS)))

    def test_K80_K214_a_yes_is_read_from_disk_and_never_carries_to_another_run(self):
        self.client()
        self.approve()
        self.start()
        self.yes("F1")
        self.end()
        self.retake()
        self.now = CLOCK + timedelta(minutes=1)
        self.start()
        self.assertIn("in this run", words(self.no("intent", "--key", "F1", "--operation", "create", "--workspace", OWN_WS)))
        self.edit_json(B1J, lambda d: d["approvals"][-1].update(approval_mode="own-account-poc"))
        found = self.no("intent", "--key", "F1", "--operation", "create", "--workspace", OWN_WS)  # R13: no card ride
        self.assertIn((B1J, "approvals[].approval_mode"), pairs(found))


class RowsTest(Base):

    def setUp(self):
        super().setUp()
        self.approve()
        self.start()

    def test_K151_K152_K153_K236_K237_K238_types_keys_and_shapes_through_check(self):
        self.assertEqual(len(self.led.TYPES), 23)
        bad = {"B2": dict(self.row("B2"), type="item"), "B1.X": dict(self.row("B1.C4"), name=None),
               "001:B7": dict(self.row("B2")), "B2.C1": dict(self.row("B2.C1"), owner_user_ids="20000001"),
               "D1": dict(self.row("D1"), origin="found", status="done", state="on"),
               "B9.C1": dict(self.row("B9.C1"), id=12345)}
        self.edit_json(B1J, lambda d: d["objects"].update(bad))
        code, blocking, _ = self.check()
        for field in ("objects.B2.type", "objects.B1.X", "objects.B1.X.name", "objects.001:B7",
                      "objects.B2.C1.owner_user_ids", "objects.D1.origin", "objects.D1.status", "objects.D1.state",
                      "objects.B9.C1.id"):
            self.assertIn((B1J, field), blocking, field)
        self.assertEqual(code, 1)

    def test_K154_W10_the_approval_class_of_each_kind(self):
        objects = {"B1": {"type": "board", "origin": "created"}, "B9": {"type": "board", "origin": "pre-existing-referenced"}}
        led = SimpleNamespace(objects=objects)
        cases = (({"type": "board"}, "create", "created", None, "card"),
                 ({"type": "workspace"}, "create", "created", None, "irreversible"),
                 ({"type": "folder"}, "create", "created", None, "irreversible"),
                 ({"type": "subitems"}, "create", "created", None, "irreversible"),
                 ({"type": "column", "parent_key": "B1"}, "create", "created", None, "card"),
                 ({"type": "column", "parent_key": "B9"}, "create", "created", None, "irreversible"),
                 ({"type": "column", "parent_key": "002:B4"}, "create", "created", None, "irreversible"),
                 ({"type": "automation"}, "create", "created", None, "list"),
                 ({"type": "workflow"}, "create", "created", None, "list"),
                 ({"type": "agent"}, "create", "created", "IR-04", "list"),
                 ({"type": "sequence"}, "create", "created", None, "list"),
                 ({"type": "webhook"}, "create", "created", None, "webhook"),
                 ({"type": "publication"}, "publish", "created", None, "publication"),
                 ({"type": "activation"}, "activate", "created", None, "publication"),
                 ({"type": "board"}, "archive", "created", None, "removed"),
                 ({"type": "project"}, "connect", "created", None, "irreversible"),
                 ({"type": "board"}, "convert", "created", None, "irreversible"),
                 ({"type": "board"}, "update", "pre-existing-modified", None, "irreversible"),
                 ({"type": "board"}, "create", "pre-existing-referenced", None, "card"),
                 ({"type": "view"}, "create", "created", "IR-05", "irreversible"),
                 ({"type": "dashboard"}, "create", "created", None, "card"))
        for row, op, origin, ir, cls in cases:
            self.assertEqual(self.led.approval_class(row, op, origin, ir, led), cls, (row, op, origin))
        need = self.led.yes_needed
        self.assertEqual([need("list", "per-list", "A1", []), need("list", "own-account-poc", "A1", []),
                          need("list", "own-account-poc", "A1", ["90600000001"]), need("webhook", "own-account-poc", "WH1", []),
                          need("publication", "own-account-poc", "SQ1.ACT", []), need("irreversible", "per-list", "W2", []),
                          need("card", "per-list", "B2", [])],
                         ["grouped", None, "grouped", "per-item", "per-item", "per-item", None])

    def test_K156_K181_subitems_and_companions(self):
        self.intent("B2", "--workspace", OWN_WS)
        self.record("B2", "--id", "90300000002")
        self.verify("B2", {"name": "Orders"})
        sub = self.intent("B2.SUB")
        self.assertEqual(sub["class"], "irreversible")
        self.record("B2.SUB", "--id", "90300000003")
        self.assertEqual(self.row("B2")["companions"], {"subitems_board_id": "90300000003"})
        self.intent("PJ1", "--workspace", OWN_WS)
        self.assertIn(("(flags)", "--companion"), pairs(self.no("record", "--key", "PJ1", "--id", "90300000090",
                                                                 "--companion", "tracker_id=1")))
        self.record("PJ1", "--id", "90300000090", "--companion", "tasks_board_id=90300000091", "--companion",
                    "overview_board_id=90300000092", "--companion", "folder_id=90200000001")
        self.assertEqual(set(self.row("PJ1")["companions"]), {"tasks_board_id", "overview_board_id", "folder_id"})

    def test_K157_a_column_on_a_referenced_or_protected_board(self):
        self.verify("B9", {"id": "90300000009", "workspace_id": OWN_WS, "name": "Supplier list"})
        self.assertEqual((self.row("B9")["status"], self.row("B9")["id"]), ("verified", "90300000009"))
        self.assertEqual(self.intent("B9.C1")["class"], "irreversible")
        self.ok("live-map", "set", "--key", "001:B1", "--constraint", "do-not-change", "--source",
                "calls/2026-10-20-discovery.md@00:14:02", "--strand", "001")
        found = self.no("intent", "--key", "B1.C4", "--operation", "create")
        self.assertIn("do-not-change", words(found))
        self.ok("live-map", "set", "--key", "001:B1", "--constraint", "free", "--source", "decision 2026-11-05", "--strand", "001")
        self.assertEqual(self.intent("B1.C4")["class"], "card")

    def test_K158_K159_an_automation_is_a_list_row_never_created_twice(self):
        self.assertEqual(self.data()["approvals"][-1]["automations_listed"], ["A1"])
        self.intent("A1", "--parent-key", "B1")
        self.record("A1", "--id", "91100000001")
        self.assertIn("status chain", words(self.no("intent", "--key", "A1", "--operation", "create")))
        self.verify("A1", {"active": True, "updated_at": "2026-11-05T14:30:00Z"}, result="mismatch")
        self.assertIn("never retried", words(self.no("intent", "--key", "A1", "--operation", "create", "--retry")))

    def test_K160_K197_a_workflow_and_its_publication(self):
        self.assertIn("verified", words(self.no("intent", "--key", "WF1.PUB", "--operation", "publish")))
        self.intent("WF1", "--workspace", OWN_WS)
        self.record("WF1", "--id", "90300000071")
        self.assertIn("validation", words(self.no("verify", "--key", "WF1", "--result", "match", "--read",
                                                  self.read_file("WF1", {"name": "Intake flow", "state": "ACTIVE"}))))
        self.assertIn("no issues", words(self.no("verify", "--key", "WF1", "--result", "match", "--read", self.read_file(
            "WF1", {"name": "Intake flow", "state": "ACTIVE", "validation": "2 issues"}))))
        self.verify("WF1", {"name": "Intake flow", "state": "ACTIVE", "validation": "no issues"})
        self.assertEqual(self.row("WF1")["read_values"], {"state": "ACTIVE"})
        self.edit_json(B1J, lambda d: d["objects"]["WF1.PUB"].update(name="publish Intake flow"))
        self.assertIn("activation state", words(self.no("intent", "--key", "WF1.PUB", "--operation", "publish")))
        self.edit_json(B1J, lambda d: d["objects"]["WF1.PUB"].update(name="publish Intake flow, inactive"))
        self.assertEqual(self.intent("WF1.PUB", op="publish")["class"], "publication")
        self.record("WF1.PUB")
        self.assertIn("sandbox trigger test", words(self.no("verify", "--key", "WF1.PUB", "--result", "match", "--read",
                                                            self.read_file("WF1.PUB", {"published": True}))))
        self.verify("WF1.PUB", {"published": True}, result="needs-user", note="the user runs the sandbox trigger test")

    def test_K161_K162_K174_K175_K191_K192_K193_the_agent(self):
        self.intent("AG1", "--scope", OWN_WS)
        self.record("AG1", "--id", "90800000001")
        self.assertIn("activation", words(self.no("intent", "--key", "AG1.ACT", "--operation", "activate")))
        lacking = {k: v for k, v in AGENT.items() if k != "knowledge"}
        self.assertIn("knowledge", words(self.no("verify", "--key", "AG1", "--result", "match", "--read",
                                                 self.read_file("AG1", lacking))))
        self.assertIn("skills", words(self.no("verify", "--key", "AG1", "--result", "match", "--read",
                                              self.read_file("AG1", dict(AGENT, skills=[])))))
        self.assertIn("frozen prompt", words(self.no("verify", "--key", "AG1", "--result", "match", "--read",
                                                     self.read_file("AG1", dict(AGENT, plan=AGENT["plan"] + "!")))))
        self.assertIn("activation", words(self.no("verify", "--key", "AG1", "--result", "match", "--read",
                                                  self.read_file("AG1", dict(AGENT, state="ACTIVE")))))
        crlf = dict(AGENT, plan=AGENT["plan"].replace("\n", "\r\n") + "\r\n")
        data = self.verify("AG1", crlf)
        row = self.row("AG1")
        self.assertEqual((row["status"], row["version_id_at_build"], row["prompt_ref"], row["state"]),
                         ("verified", "vid-000001", "v0.2r1#AG1", "inactive"))
        self.assertEqual(data["triggers_beyond_defaults"], [])
        self.assertEqual(self.intent("AG1.ACT", op="activate")["class"], "publication")

    def test_K163_K190_K198_K169_kinds_with_no_read_back(self):
        self.intent("B1.AI1")
        self.record("B1.AI1", "--id", "job_summary_mkab12cd")
        self.assertIn("not-checkable", words(self.no("verify", "--key", "B1.AI1", "--result", "match", "--read",
                                                     self.read_file("B1.AI1", {"id": "job_summary_mkab12cd"}))))
        self.assertIn("--note", " ".join(f["field"] for f in self.no("verify", "--key", "B1.AI1", "--result",
                                                                     "not-checkable", "--read", self.read_file(
                                                                         "B1.AI1", {"id": "x"}))))
        data = self.verify("B1.AI1", {"id": "job_summary_mkab12cd"}, result="not-checkable", note="the user reads it in the UI")
        self.assertEqual((data["result"], self.row("B1.AI1")["status"]), ("not-checkable", "written"))
        self.intent("DB1", "--workspace", OWN_WS, "--ref", "board:%s" % BOARD)
        self.record("DB1", "--id", "91200000001")
        self.verify("DB1", {"name": "Workshop", "workspace_id": OWN_WS, "kind": "PUBLIC"})
        self.intent("DB1.W2")
        self.assertIn("no id", words(self.no("record", "--key", "DB1.W2")))
        self.record("DB1.W2", "--id", "91600000001")
        self.assertIn("widget", words(self.no("verify", "--key", "DB1.W2", "--result", "match", "--read",
                                              self.read_file("DB1.W2", {"id": "91600000001"}))))
        self.assertEqual(self.row("DB1")["refs"], ["board:%s" % BOARD])  # K168

    def test_K164_K165_K172_K194_K195_K196_the_vibe_app(self):
        self.intent("VB1", "--scope", OWN_WS, "--ref", "board:%s" % BOARD)
        self.assertEqual(self.row("VB1")["id"], None)
        self.assertIn("keep polling", self.record("VB1", "--pending", "--polled-seconds", "30")["message"])
        self.assertIn("ceiling", self.record("VB1", "--pending", "--polled-seconds", "300")["message"])
        self.assertEqual(self.row("VB1")["status"], "attempting")
        self.assertIn("verified", words(self.no("intent", "--key", "VB1.PUB", "--operation", "publish")))
        self.record("VB1", "--id", "90900000001")
        self.assertIn("READY", words(self.no("verify", "--key", "VB1", "--result", "match", "--read",
                                             self.read_file("VB1", dict(VIBE, status="GENERATING")))))
        differs = dict(VIBE, differs_from_request=True, difference="a stage filter was added")
        self.assertIn("no yes from the user", words(self.no("verify", "--key", "VB1", "--result", "match", "--read",
                                                            self.read_file("VB1", differs))))
        data = self.verify("VB1", dict(differs, user_yes_to_difference="yes, keep the filter"))
        self.assertIn("the user's yes: yes, keep the filter", data["note"])
        self.assertEqual(self.row("VB1")["read_values"], {"status": "READY", "is_published": False, "code_version": "1"})
        self.assertEqual(self.intent("VB1.PUB", op="publish")["class"], "publication")

    def test_K166_K167_K198_sequences_and_webhooks(self):
        self.assertIn("recipients", words(self.no("intent", "--key", "SQ1", "--operation", "create", "--scope", OWN_WS)))
        self.assertIn("approves 20000001", words(self.no("intent", "--key", "SQ1", "--operation", "create", "--scope",
                                                         OWN_WS, "--notifies", "email:orders@example.com")))  # R20 (a)
        self.intent("SQ1", "--scope", OWN_WS, "--notifies", "20000001")
        self.assertIn("planned", words(self.no("intent", "--key", "WH9", "--operation", "create", "--scope", OWN_WS)))
        self.assertIn("per-item", words(self.no("intent", "--key", "WH1", "--operation", "create", "--scope", OWN_WS)))
        self.yes("WH1")
        self.intent("WH1", "--scope", OWN_WS)
        self.record("WH1", "--id", "90300000101")
        self.assertIn("not-checkable", words(self.no("verify", "--key", "WH1", "--result", "match", "--read",
                                                     self.read_file("WH1", {"id": "90300000101"}))))
        self.record("SQ1", "--id", "90300000102")
        self.verify("SQ1", {"id": "90300000102"}, result="not-checkable", note="the user checks the recipients")

    def test_K170_K171_K200_the_project_and_its_two_halves(self):
        self.assertIn("tasks board", words(self.no("intent", "--key", "PJ1", "--operation", "connect", "--workspace", OWN_WS)))
        self.intent("PJ1", "--workspace", OWN_WS)
        self.record("PJ1", "--id", "90300000090", "--companion", "tasks_board_id=90300000091", "--companion",
                    "overview_board_id=90300000092")
        self.verify("PJ1", {"name": "Install at the mill", "type": "board"})
        connect = self.intent("PJ1", op="connect")
        self.assertEqual((connect["class"], self.row("PJ1")["irreversible"]), ("irreversible", True))
        self.record("PJ1", "--id", "90300000090")
        half = {"link_board_ids": ["90300000091"], "row_board_ids": []}
        self.assertIn("partial link", words(self.no("verify", "--key", "PJ1", "--result", "match", "--read",
                                                    self.read_file("PJ1", half))))
        data = self.verify("PJ1", half, result="needs-user", note="the user opens the portfolio")
        self.assertIn("partial link", data["note"])
        self.verify("PJ1", {"link_board_ids": ["90300000091"], "row_board_ids": ["90300000091"]})
        self.assertEqual(self.row("PJ1")["status"], "verified")

    def test_K182_K184_K185_K186_K187_K189_K199_intent_record_and_verify(self):
        data = self.intent("B2", "--workspace", OWN_WS, "--payload-sha", "a" * 64)
        attempt = self.row("B2")["attempt"]
        self.assertEqual((attempt["run_id"], attempt["started_at"], len(attempt["intent_digest"])),
                         (self.run_id, "2026-11-05T14:30:00Z", 8))
        self.assertEqual(data["attempt"], attempt)
        self.assertIn("reconcile", self.record("B2", "--timed-out")["message"])
        self.record("B2", "--id-from-error", "--id", "90300000002")
        self.assertEqual((self.row("B2")["status"], self.row("B2")["id"]), ("attempting", "90300000002"))
        self.record("B2", "--id", "90300000002")
        self.assertEqual((self.row("B2")["status"], self.row("B2")["id"]), ("written", "90300000002"))
        self.assertIn("--result", " ".join(f["field"] for f in self.no("verify", "--key", "B2", "--result", "ok",
                                                                       "--read", self.read_file("B2", {"name": "x"}))))
        for doc in ({"read": "", "object": {"name": "Orders"}}, {"read": "boards(ids:)", "object": {}}):
            self.no("verify", "--key", "B2", "--result", "match", "--read", self.put("empty.json", doc))
        self.assertIn("permissions", words(self.no("verify", "--key", "B2", "--result", "match", "--read", self.read_file(
            "B2", {"name": "Orders", "column_permissions": []}))))
        self.verify("B2", {"name": "Orders", "type": "board", "state": "active", "workspace_id": OWN_WS})
        block = self.row("B2")["verify"]
        self.assertEqual(list(block), ["read", "at", "result", "digest", "note"])
        expected = self.led.digest("b2", {"name": "Orders", "type": "board", "state": "active", "workspace_id": OWN_WS,
                                          "board_folder_id": None})
        self.assertEqual((block["digest"], self.row("B2")["status"]), (expected, "verified"))
        self.assertRegex(block["digest"], r"^b2:[0-9a-f]{8}$")

    def test_K85_K86_K87_assumptions_and_sample_data_survive_the_write_path(self):
        self.assertIn("--sample-data", words(self.no("intent", "--key", "B1.IB1", "--operation", "create")))
        self.assertIn("not in the frozen", words(self.no("intent", "--key", "B1.IB1", "--operation", "create",
                                                         "--sample-data", "--assumption-ref", "AS7")))
        self.intent("B1.IB1", "--sample-data", "--assumption-ref", "AS1", "--assumption-ref", "FK1")
        before = {k: self.row("B1.IB1")[k] for k in ("assumption_refs", "sample_data")}
        self.assertEqual(before, {"assumption_refs": ["AS1", "FK1"], "sample_data": True})
        self.record("B1.IB1", "--item-id", "90500000001", "--item-id", "90500000002")
        self.verify("B1.IB1", {"item_ids": ["90500000002", "90500000001"]})
        self.assertEqual(self.row("B1.IB1")["item_ids"], ["90500000001", "90500000002"])
        self.end()
        self.assertEqual({k: self.row("B1.IB1")[k] for k in before}, before)
        self.assertFalse(self.row("B2")["sample_data"])
        self.assertNotIn("001:B1.IB1", self.data("account.json")["live_objects"])


class DepartTest(Base):

    def setUp(self):
        super().setUp()
        self.approve()
        self.start()

    def test_K202_K203_K204_K205_K206_departures(self):
        self.assertIn("call forms", words(self.no("depart", "--key", "B1.G2", "--what", "w", "--error-code", "E",
                                                  "--decision", "later-retry", "--attempt", "flat", "--attempt",
                                                  "wrapped", "--attempt", "raw")))
        self.no("depart", "--key", "B1.G2", "--what", "w", "--error-code", " ", "--decision", "later-retry")
        for key, decision in (("B1.G2", "later-retry"), ("B1.FM1", "blueprint-revision"), ("D1", "ui-step")):
            extra = ["--ui-what", "add the doc by hand", "--ui-owner", "the user"] if decision == "ui-step" else []
            data = self.go("depart", "--key", key, "--what", "the call failed", "--error-code", "ColumnValueException",
                           "--decision", decision, "--attempt", "flat", "--attempt", "wrapped", *extra)
            self.assertEqual(self.row(key)["status"], "departed")
        entry = self.data()["departures"][-1]
        self.assertEqual(list(entry), ["key", "version", "what", "error_code", "attempts", "decision"])
        self.assertEqual((entry["decision"], data["decision"]), ("ui-step U2", "ui-step U2"))
        self.assertEqual(self.data()["ui_steps"][-1]["key"], "U2")

    def test_K207_K208_K209_ui_steps(self):
        sha = self.sha()
        self.assertIn("U<n>", words(self.refused("ui-step", "--strand", "001", "--key", "X1", "--what", "w", "--owner",
                                                 "the user", "--target-version", "v0.2", "--expect-sha", sha)))
        data = self.ok("ui-step", "--strand", "001", "--key", "U1", "--what", "add the Kanban view", "--owner",
                       "the user", "--target-version", "v0.2", "--expect-sha", sha)
        self.assertEqual(list(data["ui_step"]), ["key", "what", "owner", "target_version", "status"])
        self.refused("ui-step", "--strand", "001", "--key", "U9", "--done", "--expect-sha", self.sha())
        self.ok("ui-step", "--strand", "001", "--key", "U1", "--done", "--expect-sha", self.sha())
        self.assertEqual(self.data()["ui_steps"][0]["status"], "done")

    def test_K210_K211_K212_K215_K216_irreversible_yes(self):
        self.copy_home()  # R13: a client record approved as such, not an own-account approval made client afterwards
        os.environ["MMB_HOME"] = str(self.home)
        self.client()
        self.approve()
        self.start()
        data = self.yes("F1", "per-item", "--log-ref", "2026-11-05 14:30 · 001 · irreversible · v0.2 · F1")
        entry = self.data()["irreversible_yes"][-1]
        self.assertEqual(list(entry), ["key", "what", "at", "mode", "approval_ref", "evidence", "log_ref", "run_id",
                                       "operation", "used_by"])
        self.assertEqual((entry["run_id"], entry["operation"], entry["used_by"]), (self.run_id, "create", None))
        self.assertEqual((entry["at"], entry["approval_ref"], data["log"][0]["type"]),
                         ("2026-11-05T14:30:00Z", "v0.2r1", "irreversible"))
        self.assertIn("not listed", words(self.no("irreversible-yes", "--key", "B2", "--mode", "per-item", "--what", "w")))
        self.assertIn("evidence", words(self.no("irreversible-yes", "--key", "B1", "--mode", "per-item", "--what",
                                                "archive the old Jobs board")))
        self.assertIn("--evidence", " ".join(f["field"] for f in self.no(
            "irreversible-yes", "--key", "B1", "--mode", "per-item", "--what", "the step", "--operation", "archive")))
        self.yes("B1", "per-item", "--approval-ref", "v0.2r1")  # a create's yes, which no archive rides (R2)
        self.assertIn("per-item yes for this archive", words(self.no("intent", "--key", "B1", "--operation", "archive",
                                                                     "--approval-ref", "v0.2r1")))
        self.yes("B1", "per-item", "--approval-ref", "v0.2r1", "--operation", "archive", "--evidence",
                 "no view, automation or other strand reads it")
        self.assertEqual(self.intent("B1", "--approval-ref", "v0.2r1", op="archive")["class"], "removed")
        self.assertTrue(self.row("B1")["irreversible"])
        self.assertIn("B1", [e["key"] for e in self.data()["irreversible_yes"]])


class LiveMapTest(Base):

    def setUp(self):
        super().setUp()
        self.approve()
        self.start()
        self.sales()
        self.end()

    def test_K217_K218_K219_K220_K221_K222_K223_K224_K226_the_map_and_its_rows(self):
        text = mc.read_text(self.root / "live" / "live-map.md")
        fields, body = mc.split_front_matter(text)
        live = self.data("account.json")["live_objects"]
        self.assertEqual(list(fields), ["schema", "client", "rows", "updated"])
        self.assertEqual((fields["schema"], fields["rows"]), ("live-map/1", str(len(live))))
        self.assertIn(self.led.MAP_HEAD, body)
        self.assertIn("| 001:W2 | %s | workspace | %s | 001/v0.2 | active | change-with-own-yes |" % (SALES_WS, SALES_WS),
                      body)
        for key, row in live.items():
            self.assertRegex(key, r"^\d{3}:")
            self.assertIsInstance(row["monday_id"], str)
            self.assertIn(row["state"], self.led.STATES)
            self.assertRegex(row["introduced_in"], r"^\d{3}/v\d+\.\d+$|^client$|^native$")
        self.assertEqual(self.check()[1], set())

    def test_K225_K227_K228_K229_K230_K231_K233_live_map_set(self):
        before = self.data("account.json")["live_objects"]["001:W2"]
        base = ["live-map", "set", "--strand", "001"]
        for argv, expect in ((["--key", "001:Z9", "--constraint", "free", "--source", "s"], "no live-map row"),
                             (["--key", "001:W2", "--constraint", "maybe", "--source", "s"], "not a constraint"),
                             (["--key", "001:W2", "--constraint", "free", "--source", " "], "interim"),
                             (["--key", "001:W2", "--constraint", "free", "--source", "pending strand close"], "interim")):
            self.assertIn(expect, words(self.refused(*(base + argv))))
        self.assertIn("built by strand 001", words(self.refused("live-map", "set", "--strand", "002", "--key", "001:W2",
                                                                "--constraint", "free", "--source", "s")))
        build = self.sha()
        data = self.ok(*(base + ["--key", "001:W2", "--constraint", "do-not-change", "--source",
                                 "calls/2026-10-20-discovery.md@00:21:40"]))
        after = self.data("account.json")["live_objects"]["001:W2"]
        self.assertEqual({k: v for k, v in after.items() if k not in ("constraint", "constraint_source")},
                         {k: v for k, v in before.items() if k not in ("constraint", "constraint_source")})
        self.assertIn("| do-not-change | calls/2026-10-20-discovery.md@00:21:40 |",
                      mc.read_text(self.root / "live" / "live-map.md"))
        self.assertEqual((self.sha(), data["asked_by"]), (build, "001"))
        self.assertEqual(self.ok("live-map", "--strand", "002")["asked_by"], "002")
        self.assertEqual(self.sha(), build)  # K38: record-level commands write no build.json
        self.assertEqual(self.check()[1], set())

    def test_K232_W61_a_later_run_end_keeps_a_promoted_constraint(self):
        self.ok("live-map", "set", "--strand", "001", "--key", "001:W2", "--constraint", "free", "--source",
                "decision 2026-11-05 14:40")
        self.retake()
        self.start()
        self.end()
        row = self.data("account.json")["live_objects"]["001:W2"]
        self.assertEqual((row["constraint"], row["constraint_source"]), ("free", "decision 2026-11-05 14:40"))


class CheckTest(Base):

    def table_in_v01(self):
        """The C129 stand-in: the v0.1 frozen file's heading as the pinned one, in this copy only (W42)."""
        path = self.root / V1 / "blueprint-r1.md"
        path.write_bytes(path.read_bytes().replace(b"## Elements\n", b"## Element keys\n"))
        sha = mc.sha256_file(path)
        self.edit_fm(V1 + "/version.md", sha256=sha)
        self.edit_json(B1J, lambda d: d["approvals"][0].update(sha256=sha))

    def test_K28_K248_the_untouched_fixture_checks_with_one_warning(self):
        code, blocking, warnings = self.check()
        self.assertEqual((code, blocking, warnings), (2, set(), {(V1 + "/blueprint-r1.md", "## Element keys")}))
        data = self.ledger("check")[1]
        self.assertEqual(data["shas"], {"account.json": self.sha("account.json"), B1J: self.sha()})

    def test_K243_C129_the_key_half_of_a_ref(self):
        self.table_in_v01()
        self.assertEqual(self.check(), (0, set(), set()))
        self.edit_json(B1J, lambda d: d["objects"]["B1"].update(blueprint_ref="v0.1r1#B9"))
        self.assertEqual(self.check()[:2], (1, {(B1J, "objects.B1.blueprint_ref")}))

    def test_K234_K235_K242_K247_schemas_fields_and_the_frozen_sha(self):
        self.edit_json(B1J, lambda d: d.update(schema="build/3"))
        self.assertEqual(self.check()[:2], (1, {(B1J, "schema")}))
        self.edit_json(B1J, lambda d: d.update(schema="build/2"))
        self.edit_json("account.json", lambda d: d["account"].pop("tier"))
        self.edit_json(B1J, lambda d: (d["approvals"][0].pop("approved_words"), d["runs"][0].pop("kind"),
                                       d["objects"]["B1"].pop("name")))
        blocking = self.check()[1]
        for pair in (("account.json", "account.tier"), (B1J, "approvals[0].approved_words"), (B1J, "runs[0].kind"),
                     (B1J, "objects.B1.name")):
            self.assertIn(pair, blocking)
        self.copy_home()
        os.environ["MMB_HOME"] = str(self.home)
        path = self.root / V1 / "blueprint-r1.md"
        path.write_bytes(path.read_bytes() + b"x")
        self.assertIn((V1 + "/blueprint-r1.md", "sha256"), self.check()[1])

    def test_K239_K240_K241_K244_K245_K249_the_ledger_rules(self):
        live_row = {"monday_id": "90300000077", "kind": "board", "workspace": OWN_WS, "name_at_build": "Stock",
                    "owner_strand": "002", "introduced_in": "002/v0.1", "state": "active", "constraint": "do-not-change",
                    "constraint_source": "s", "digest": None, "last_verified": None, "dependants": []}
        self.edit_json("account.json", lambda d: d["live_objects"].update({"002:B7": live_row}))

        def plant(d):
            objects = d["objects"]
            objects["B1.V1"].update(parent_key="B4")
            objects["B1"].update(prior_state={"name": "Jobs"}, workspace="90100000999")
            objects["W1"].update(origin="pre-existing-modified")
            objects["B1.C1"] = dict(objects["B1.V1"], type="column", parent_key="B1", origin="other-strand-modified",
                                    source_strand="002", live_key="002:B7", prior_state={}, approval_ref="v9.9r9")
            d["irreversible_yes"].append({"key": "B1", "what": "w", "at": "2026-11-05T14:30:00Z", "mode": "per-item",
                                          "approval_ref": "v0.1r1", "evidence": None, "log_ref": None})
        self.edit_json(B1J, plant)
        blocking = self.check()[1]
        for field in ("objects.B1.V1.parent_key", "objects.B1.prior_state", "objects.W1.prior_state",
                      "objects.B1.C1.live_key", "objects.B1.C1.approval_ref", "objects.B1.workspace",
                      "irreversible_yes[0].key"):
            self.assertIn((B1J, field), blocking, field)
        self.edit_json("account.json", lambda d: d["live_objects"].pop("002:B7"))
        self.assertIn((B1J, "objects.B1.C1.live_key"), self.check()[1])

    def test_W63_two_running_runs_a_stale_run_and_a_map_that_differs(self):
        self.edit_json(B1J, lambda d: d["runs"].extend([dict(d["runs"][0], id="run-2026-11-05-1", state="running",
                                                              heartbeat_at="2026-11-05T13:00:00Z"),
                                                         dict(d["runs"][0], id="run-2026-11-05-2", state="running",
                                                              heartbeat_at="2026-11-05T14:29:00Z")]))
        self.edit_json("account.json", lambda d: d["live_objects"]["001:B1"].update(state="archived"))
        code, blocking, warnings = self.check()
        self.assertIn((B1J, "runs"), blocking)
        self.assertIn(("live/live-map.md", "001:B1.state"), blocking)
        self.assertIn((B1J, "runs[1].heartbeat_at"), warnings)


class ReviewFixTest(Base):
    """The fixes of ledger-review.md (WP3 step 8): one test per finding, R1 to R20, each failing on the code the review
    read and passing now. The scenarios are the review's probes, rebuilt in this test's own record copy."""

    SALES = "Larkmoor Joinery – Sales"
    TWO = (("W3", "workspace", "Larkmoor Joinery – Ops two"),)

    def make_version(self, version, rows=TABLE, purpose="working-solution", revision=1):
        """A version folder of this strand with one frozen revision carrying the element-key table."""
        vdir = self.root / S1 / "versions" / version
        vdir.mkdir(parents=True, exist_ok=True)
        frozen = vdir / ("blueprint-r%d.md" % revision)
        text = blueprint(rows).replace("v0.2", version).replace('revision: "1"', 'revision: "%d"' % revision)
        frozen.write_bytes(text.encode("utf-8"))
        sha = mc.sha256_file(frozen)
        text = version_md(sha, purpose).replace('"v0.2"', '"%s"' % version).replace("001/v0.2", "001/" + version)
        text = text.replace('revision: "1"', 'revision: "%d"' % revision).replace("of v0.2", "of " + version)
        (vdir / "version.md").write_bytes(text.encode("utf-8"))
        self.edit_fm(S1 + "/STRAND.md", version=version, version_state="approved")
        return sha

    def board(self, bid, at):
        return {"id": bid, "name": "Orders", "type": "board", "state": "active", "created_at": at,
                "workspace_id": OWN_WS, "board_folder_id": None, "object_type_unique_key": None,
                "hierarchy_type": "classic"}

    def fresh_core(self):
        """A second core workspace W3, intended with the user's direction change and recorded as the client's."""
        self.approve(rows=TABLE + self.TWO, extra=["--irreversible", "W3"])
        self.start()
        change = "2026-11-05 14:30 · 001 · decision · v0.2 · a fresh workspace"
        self.intent("W3", "--product", "core", "--direction-change", change)
        self.record("W3", "--id", "40000009")
        self.verify("W3", {"name": "Larkmoor Joinery – Ops two", "kind": "open"})
        self.ok("workspaces", "--strand", "001", "--product", "core", "--id", "40000009", "--created-in", "001/v0.2",
                *self.fence())
        return change

    def test_R1_W44_a_working_solution_takes_its_own_mode_never_the_proof_of_concepts_card(self):
        self.approve()  # v0.2: a proof of concept in the user's own account, own-account-poc
        self.start()
        self.intent("A1", "--parent-key", "B1")
        self.record("A1", "--id", "91100000001")
        self.verify("A1", {"active": True, "updated_at": "2026-11-05T14:30:00Z"})
        self.sales()
        self.end()
        self.ok(*self.approval_argv(self.make_version("v1.0")))  # v1.0: a working solution, per-list (W44)
        self.retake()
        self.start()
        self.assertEqual(self.row("A1")["approval_ref"], "v0.2r1")  # the kept row keeps its planning ref
        found = self.no("intent", "--key", "A1", "--operation", "update")
        self.assertIn("grouped yes for this update", words(found))
        self.assertIn("mode per-list", words(found))
        self.assertIn("per-item", words(self.no("intent", "--key", "W2", "--operation", "archive", "--evidence",
                                                "nothing uses it")))
        found = self.no("intent", "--key", "B2", "--operation", "create", "--workspace", OWN_WS, "--approval-ref", "v0.2r1")
        self.assertIn(("(flags)", "--approval-ref"), pairs(found))
        self.yes("A1", "grouped", "--operation", "update")
        data = self.intent("A1", op="update")
        self.assertEqual((data["approval_mode"], data["yes"]), ("per-list", "grouped"))

    def test_R2_K215_one_yes_covers_one_step_and_an_archive_takes_its_own_with_its_evidence(self):
        self.client()
        self.approve()
        self.start()
        self.yes("W2")
        self.intent("W2", "--product", "crm")
        self.record("W2", "--timed-out")
        self.reconcile()  # nothing live: retry, which the same attempt's yes still covers
        self.assertEqual(self.go("intent", "--key", "W2", "--operation", "create", "--product", "crm", "--retry")["yes"],
                         "per-item")
        self.record("W2", "--id", SALES_WS)
        self.verify("W2", {"name": self.SALES, "kind": "open"})
        entry = self.data()["irreversible_yes"][-1]
        self.assertEqual((entry["run_id"], entry["operation"], entry["used_by"]), (self.run_id, "create", self.row("W2")[
            "attempt"]["started_at"]))
        for op in ("archive", "update"):
            self.assertIn("yes for this %s" % op, words(self.no("intent", "--key", "W2", "--operation", op,
                                                                "--evidence", "nothing uses it")))
        self.yes("W2", "per-item", "--operation", "archive", "--evidence", "no board, doc or strand uses it")
        self.assertEqual(self.intent("W2", op="archive")["class"], "removed")

    def test_R3_W40_a_parent_is_named_by_key_placed_and_in_the_rows_own_workspace(self):
        self.approve()
        self.start()
        found = self.no("intent", "--key", "A1", "--operation", "create", "--parent-id", "88800000001", "--workspace", OWN_WS)
        self.assertIn("no workspace it knows", words(found))
        self.ok("live-map", "set", "--key", "001:B1", "--constraint", "do-not-change", "--source",
                "calls/2026-10-20-discovery.md@00:14:02", "--strand", "001")
        self.assertIn("do-not-change", words(self.no("intent", "--key", "A1", "--operation", "create", "--parent-key", "B1")))
        found = self.no("intent", "--key", "A1", "--operation", "create", "--parent-id", BOARD, "--workspace", OWN_WS)
        self.assertIn("holds it as B1", words(found))
        self.assertIn("do-not-change", words(found))
        self.ok("live-map", "set", "--key", "001:B1", "--constraint", "free", "--source", "decision 2026-11-05",
                "--strand", "001")
        self.sales()
        found = self.no("intent", "--key", "A1", "--operation", "create", "--parent-key", "B1", "--workspace", SALES_WS)
        self.assertIn("the parent B1 is in workspace %s" % OWN_WS, words(found))
        self.intent("A1", "--parent-key", "B1")
        self.assertEqual((self.row("A1")["parent_id"], self.row("A1")["workspace"]), (BOARD, OWN_WS))

    def test_R4_W35_one_monday_id_has_one_spelling(self):
        self.approve()
        self.start()
        zero = "0" + OPS_WS
        found = self.refused("workspaces", "--strand", "001", "--product", "crm", "--id", zero, "--name", "x",
                             "--created-in", "001/v0.2", *self.fence())
        self.assertIn("leading zero", words(found))
        for argv in (("B2", "--workspace", zero), ("AG1", "--scope", zero),
                     ("AG1", "--scope", OWN_WS, "--ref", "board:0" + BOARD), ("A1", "--parent-key", "B1", "--parent-id",
                                                                                "0" + BOARD)):
            self.assertIn("leading zero", words(self.no("intent", "--key", argv[0], "--operation", "create", *argv[1:])),
                          argv)
        found = self.no("verify", "--key", "B9", "--result", "match", "--read", self.read_file("B9", {
            "id": "0" + BOARD, "workspace_id": OWN_WS, "name": "Supplier list"}))
        self.assertIn("leading zero", words(found))
        self.assertIn("leading zero", words(self.refused("workspaces", "--strand", "001", "--use", zero, *self.fence())))

    def test_R5_K157_do_not_change_protects_the_object_under_every_key(self):
        self.approve()
        self.start()
        theirs = {"monday_id": "50000099", "kind": "board", "workspace": OWN_WS, "name_at_build": "Supplier list",
                  "owner_strand": "002", "introduced_in": "client", "state": "active", "constraint": "do-not-change",
                  "constraint_source": "calls/2026-10-20-discovery.md@00:12:10", "digest": None,
                  "last_verified": "2026-11-01", "dependants": []}
        self.edit_json("account.json", lambda d: d["live_objects"].update({"002:B9": theirs}))
        data = self.verify("B9", {"id": "50000099", "workspace_id": OWN_WS, "name": "Supplier list"})
        self.assertEqual([s["key"] for s in data["same_object_as"]], ["002:B9"])
        found = self.no("intent", "--key", "B9.C1", "--operation", "create")
        self.assertIn("marked do-not-change as 002:B9", words(found))
        self.end()
        self.assertEqual(self.data("account.json")["live_objects"]["001:B9"]["constraint"], "do-not-change")
        self.edit_json("account.json", lambda d: d["live_objects"]["001:B9"].update(constraint="free"))
        self.assertIn(("account.json", "live_objects.001:B9.constraint"), self.check()[1])

    def test_R6_W25_a_run_start_whose_ledger_write_failed_is_recovered_by_the_classify_only_reconcile(self):
        self.approve()
        self.change_check()
        with self.failing("build.json"):
            code, data = self.ledger("run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                                     "--another-build-running", "no", "--account-check", "match", "--expect-sha", self.sha())
        run = data["committed"]["run_id"]
        self.assertEqual((code, self.lease()["run_id"], self.led.Ledger(self.root, "001").run(run)), (3, run, None))
        self.now = CLOCK + timedelta(hours=3)  # the session is gone and the heartbeat goes stale
        found = self.ok("reconcile", "--strand", "001", "--classify-only", "--asked-by", "002", "--inventory",
                        self.inventory())
        self.assertEqual((found["marked"], found["recorded_missing_run"]), (True, True))
        entry = next(r for r in self.data()["runs"] if r["id"] == run)
        self.assertEqual(entry["state"], "interrupted")
        self.assertIn("never reached the ledger", entry["note"])
        self.assertEqual([p for p in self.check()[1] if p[1].startswith("runs")], [])
        broken = mc.lease_break(self.root, "2", LABEL, "001", "yes, break the lease of strand 001", "10000001", "resume")
        self.assertEqual((broken["choice"], self.lease()["state"]), ("resume", "broken"))

    def test_R6_W30_a_run_id_the_lease_history_carries_is_skipped(self):
        self.approve()
        self.change_check()
        with self.failing("build.json"):
            data = self.ledger("run", "start", "--strand", "001", "--lease-epoch", "2", "--session-label", LABEL,
                               "--another-build-running", "no", "--account-check", "match", "--expect-sha", self.sha())[1]
        self.assertEqual(data["committed"]["run_id"], "run-2026-11-05-1")
        mc.lease_release(self.root, "2", LABEL)  # the session released without the retry: run 1 is in the history only
        self.retake()
        self.assertEqual(self.start(cc=False)["run_id"], "run-2026-11-05-2")

    def test_R7_G04_a_classify_only_reconcile_reads_the_account_after_the_last_heartbeat(self):
        self.approve()
        self.start()
        self.intent("B2", "--workspace", OWN_WS)  # the attempt begins at 14:30:00
        old = self.inventory("old.json", read_at="2026-11-05T14:30:30Z")
        self.now = CLOCK + timedelta(minutes=1)
        self.record("B2", "--timed-out")  # the heartbeat moves to 14:31:00
        self.ok("reconcile", "--strand", "001", "--inventory", old)  # a full reconcile leaves its copy
        self.now = CLOCK + timedelta(hours=2)
        for argv in (["--inventory", old], []):
            found = self.refused("reconcile", "--strand", "001", "--classify-only", "--asked-by", "002", *argv)
            self.assertIn("not after the holder's last heartbeat", words(found), argv)
        twice = [self.board("90300000002", "2026-11-05T14:30:10Z"), self.board("90300000003", "2026-11-05T14:30:20Z")]
        data = self.ok("reconcile", "--strand", "001", "--classify-only", "--asked-by", "002", "--inventory",
                       self.inventory("today.json", boards=twice))
        self.assertEqual((data["classes"]["duplicate"], data["reconcile"]["read_at"]), (1, "2026-11-05T16:30:00Z"))
        with self.assertRaises(mc.Refusal) as caught:
            mc.lease_break(self.root, "2", LABEL, "002", "yes, break strand 001", "10000001", "park", park_yes="yes, park")
        self.assertIn("duplicate", json.dumps(caught.exception.findings))

    def test_R8_W38_workspaces_records_only_a_workspace_this_build_created(self):
        self.approve()
        self.start()
        ws = ["workspaces", "--strand", "001", "--product", "crm", "--id", SALES_WS, "--name", self.SALES,
              "--created-in", "001/v0.2"]
        self.assertIn("no workspace row", words(self.refused(*(ws + self.fence()))))
        other = self.home / "clients" / "other-client"
        other.mkdir()
        sibling = {"schema": "account/1", "guard_index": {"client_workspace_ids": [SALES_WS]}}
        (other / "account.json").write_bytes(mc.json_text(sibling).encode("utf-8"))
        self.intent("W2", "--product", "crm")
        self.record("W2", "--id", SALES_WS)
        self.verify("W2", {"name": self.SALES, "kind": "open"})
        found = self.refused(*(ws + self.fence()))
        self.assertIn(("clients/other-client/account.json", "guard_index.client_workspace_ids"), pairs(found))
        self.assertIn("not service", words(self.refused("workspaces", "--strand", "001", "--product", "service", "--id",
                                                        SALES_WS, "--created-in", "001/v0.2", *self.fence())))
        sibling["guard_index"]["client_workspace_ids"] = ["90100000999"]
        (other / "account.json").write_bytes(mc.json_text(sibling).encode("utf-8"))
        self.ok(*(ws + self.fence()))
        account = self.data("account.json")
        self.assertEqual(account["client_workspaces"]["crm"]["name"], self.SALES)  # the name is the row's

    def test_R9_W61_a_modifying_row_stays_the_object_it_modifies(self):
        self.approve()
        self.start()
        live_row = {"monday_id": "90300000077", "kind": "board", "workspace": OWN_WS, "name_at_build": "Stock",
                    "owner_strand": "002", "introduced_in": "002/v0.1", "state": "active",
                    "constraint": "change-with-own-yes", "constraint_source": "decision 2026-11-01",
                    "digest": None, "last_verified": "2026-11-01", "dependants": []}
        self.edit_json("account.json", lambda d: d["live_objects"].update({"002:B7": live_row}))
        prior = self.put("prior.json", {"id": "90300000077", "name": "Stock"})
        self.intent("B5", "--workspace", OWN_WS, "--origin", "other-strand-modified", "--prior-state", prior,
                    "--source-strand", "002", "--live-key", "002:B7")
        self.assertEqual(self.row("B5")["id"], "90300000077")
        self.assertIn("whose object is 90300000077", words(self.no("record", "--key", "B5", "--id", "59999999")))
        self.record("B5")
        self.assertIn("modifies 90300000077", words(self.no("verify", "--key", "B5", "--result", "match", "--read",
                                                            self.read_file("B5", {"id": "59999999", "name": "Stock"}))))
        self.verify("B5", {"id": "90300000077", "name": "Stock", "type": "board", "state": "active",
                           "workspace_id": OWN_WS})
        theirs = self.put("prior-b2.json", {"id": "90300000066", "name": "Orders"})
        self.intent("B2", "--workspace", OWN_WS, "--origin", "pre-existing-modified", "--prior-state", theirs)
        self.assertIn("whose object is 90300000066", words(self.no("record", "--key", "B2", "--id", "90300000067")))
        self.record("B2", "--id", "90300000066")
        self.assertIn("modifies 90300000066", words(self.no("verify", "--key", "B2", "--result", "match", "--read",
                                                            self.read_file("B2", {"id": "90300000067"}))))
        self.end()
        row = self.data("account.json")["live_objects"]["002:B7"]
        self.assertEqual((row["monday_id"], row["owner_strand"]), ("90300000077", "002"))

    def test_R10_A86_a_timeout_and_an_interrupted_run_are_reconciled_before_any_write(self):
        self.approve()
        self.start()
        self.intent("B2", "--workspace", OWN_WS)
        self.record("B2", "--timed-out")
        self.assertIn("no reconcile made", words(self.no("intent", "--key", "B2", "--operation", "create", "--retry")))
        self.reconcile(boards=[self.board("90300000002", "2026-11-05T14:30:10Z")])
        self.assertIn("classes B2 adopt", words(self.no("intent", "--key", "B2", "--operation", "create", "--retry")))
        self.reconcile()
        self.go("intent", "--key", "B2", "--operation", "create", "--retry")
        self.record("B2", "--timed-out")
        self.retake()  # the session is lost; a new run starts with the old one running and B2 attempting
        self.assertTrue(self.start(cc=False)["recovery_first"])
        self.assertTrue(self.data()["runs"][-1]["recovery_first"])
        for argv in (("intent", "--key", "B1.G2", "--operation", "create"), ("intent", "--key", "B2", "--operation",
                                                                              "create", "--retry"),
                     ("depart", "--key", "B2", "--what", "w", "--error-code", "E1", "--decision", "later-retry")):
            self.assertIn("recovery first", words(self.no(*argv)), argv)
        self.reconcile()
        self.go("depart", "--key", "B2", "--what", "the create timed out twice", "--error-code", "TIMEOUT", "--decision",
                "later-retry")
        self.intent("B1.G2")

    def test_R11_BP136_a_second_workspace_in_a_product_is_refused_before_it_is_created(self):
        self.approve(rows=TABLE + self.TWO, extra=["--irreversible", "W3"])
        self.start()
        found = self.no("intent", "--key", "W3", "--operation", "create", "--product", "core")
        self.assertIn(("account.json", "client_workspaces.core"), pairs(found))
        self.copy_home()
        os.environ["MMB_HOME"] = str(self.home)
        change = self.fresh_core()
        account = self.data("account.json")
        self.assertEqual((self.row("W3")["direction_change"], account["client_workspaces"]["core"]["id"],
                          account["superseded_workspaces"][0]["direction_change"]), (change, "40000009", change))

    def test_R12_W27_a_later_revision_renames_and_withdraws_the_planned_rows_it_changes(self):
        self.approve()
        rows = tuple(("B2", "board", "Purchase orders") if r[0] == "B2" else r for r in TABLE if r[0] != "B5")
        data = self.ok(*self.approval_argv(self.make_version("v0.2", rows=rows, purpose="proof-of-concept", revision=2)))
        self.assertEqual(data["delta"]["dropped"], ["B5"])
        row = self.row("B2")
        self.assertEqual((row["name"], row["approval_ref"], row["blueprint_ref"]), ("Purchase orders", "v0.2r2", "v0.2r2#B2"))
        self.assertEqual((self.row("B5")["status"], self.data()["departures"][-1]["decision"]), ("departed",
                                                                                                "blueprint-revision"))
        self.start()
        self.assertIn("departed", words(self.no("intent", "--key", "B5", "--operation", "create", "--workspace", OWN_WS)))
        self.edit_json(B1J, lambda d: d["objects"]["B2"].update(approval_ref="v0.2r1"))
        self.assertIn("latest approval", words(self.no("intent", "--key", "B2", "--operation", "create", "--workspace",
                                                       OWN_WS)))
        self.edit_json(B1J, lambda d: d["objects"]["B2"].update(approval_ref="v0.2r2"))
        self.intent("B2", "--workspace", OWN_WS)
        self.assertEqual(self.check()[1], set())

    def test_R13_A28_a_proof_of_concept_mode_the_record_does_not_allow_is_refused_and_checked(self):
        self.client()
        self.approve()
        self.start()
        self.edit_json(B1J, lambda d: d["approvals"][-1].update(approval_mode="own-account-poc"))
        self.assertIn((B1J, "approvals[1].approval_mode"), self.check()[1])
        self.assertIn("A28", words(self.no("intent", "--key", "F1", "--operation", "create", "--workspace", OWN_WS)))

    def test_R14_SF3_a_recorded_account_mismatch_stops_every_write(self):
        self.approve()
        self.start()
        self.intent("B2", "--workspace", OWN_WS)
        self.assertTrue(self.go("run heartbeat", "--account-check", "mismatch", "--before", "writes 21 to 40")["stop"])
        for argv in (("intent", "--key", "D1", "--operation", "create", "--workspace", OWN_WS),
                     ("record", "--key", "B2", "--id", "90300000002"),
                     ("verify", "--key", "B9", "--result", "match", "--read", self.read_file(
                         "B9", {"id": "90300000009", "workspace_id": OWN_WS})),
                     ("irreversible-yes", "--key", "F1", "--mode", "per-item", "--what", "create the folder")):
            self.assertIn("another account", words(self.no(*argv)), argv[0])
        self.assertIn(("(flags)", "--answer-words"), pairs(self.no("run heartbeat", "--account-check", "match", "--before",
                                                                   "writes 21 to 40")))
        words_ = "yes, the connector is on the client's account again"
        self.go("run heartbeat", "--account-check", "match", "--before", "writes 21 to 40", "--answer-words", words_)
        self.assertEqual(self.data()["runs"][-1]["account_checks"][-1]["answer_words"], words_)
        self.record("B2", "--id", "90300000002")

    def test_R15_K214_a_yes_belongs_to_its_run_whatever_the_clock_does(self):
        self.client()
        self.approve()
        self.start()
        self.now = CLOCK + timedelta(minutes=5)
        self.yes("F1")
        self.end()
        self.retake()
        self.now = CLOCK + timedelta(minutes=3)  # a time-sync step puts the clock two minutes back
        self.start()
        self.assertIn("in this run", words(self.no("intent", "--key", "F1", "--operation", "create", "--workspace", OWN_WS)))

    def test_R16_W39_a_superseded_workspace_is_not_taken_up_again(self):
        self.fresh_core()
        targets = lambda d: d["guard_index"]["build_targets_by_strand"]["001"]["workspace_ids"]  # noqa: E731
        self.edit_json("account.json", lambda d: targets(d).remove(OWN_WS))
        self.assertIn("superseded", words(self.refused("workspaces", "--strand", "001", "--use", OWN_WS, *self.fence())))
        self.edit_json("account.json", lambda d: targets(d).append(OWN_WS))
        self.ok("workspaces", "--strand", "001", "--use", OWN_WS, *self.fence())  # the strand that builds there

    def test_R18_W49_only_the_lease_holders_strand_runs_the_change_check_while_a_build_is_live(self):
        found = self.refused("change-check", "--strand", "002", "--from", self.put("cc.json", {
            "ring": "release_candidate 2026-10", "versions_seen": ["2026-10"], "release_notes_since": "not-read",
            "roster_diff": {"added": [], "removed": [], "renamed": []}, "schema_diff": [],
            "result": "no change affecting this build", "approved_by_user": None}))
        self.assertIn((mc.LOCK_REL, "strand"), pairs(found))
        self.change_check()  # the holder's own strand

    def test_R19_W33_a_first_write_that_fails_says_what_the_fence_moved(self):
        self.approve()
        self.start()
        self.now = CLOCK + timedelta(minutes=1)
        with self.failing("build.json"):
            code, data = self.ledger(*self.argv("intent", "--key", "B2", "--operation", "create", "--workspace", OWN_WS))
        self.assertEqual(code, 3)
        self.assertNotIn("nothing was written", data["error"]["problem"])
        self.assertIn("moved the lease heartbeat", data["error"]["problem"])

    def test_R20_an_approval_waits_for_the_run_any_failure_after_a_write_is_reported_and_a_bad_heartbeat_refuses(self):
        self.approve()
        self.start()
        self.sales()
        self.now = CLOCK + timedelta(minutes=1)
        real = mc.write_file

        def write(path, data, root, backup=True, backup_dir=None):
            if Path(path).name == "live-map.md":
                raise ValueError("a planted failure of another kind")
            return real(path, data, root, backup, backup_dir)
        with mock.patch.object(mc, "write_file", write):
            code, data = self.ledger(*self.argv("run end", "--calls-used", "4"))
        self.assertEqual((code, data["error"]["field"], data["committed"]["written"]), (3, "committed", ["account.json"]))
        sha = self.make_version("v0.2", purpose="proof-of-concept", revision=2)
        self.assertIn("between runs", words(self.refused(*self.approval_argv(sha))))
        status = dict(self.lease(), heartbeat_at=None, fresh=None)
        with mock.patch.object(mc, "lease_status", lambda root: status):
            found = self.refused("reconcile", "--strand", "001", "--classify-only", "--inventory", self.inventory())
        self.assertIn("does not read", words(found))


class SettledTest(Base):
    """The two review findings the user settled on 2026-10-17 (DECISIONS.md, "Settled with the user"): R17, no strand
    owns a client or native row of the live map (test_U17_*), and R20 (a), the approved revision records who each
    element notifies (test_U20_*)."""

    DECISION = "2026-11-05 14:40 · 001 · decision · v0.2 · supplier list"
    QUOTE = '"Leave the supplier list as it is." calls/2026-10-20-discovery.md@00:12:10'

    def client_board(self):
        """Strand 001 references the client's board B9 and closes its run: run end writes 001:B9, built by client."""
        self.approve()
        self.start()
        self.verify("B9", {"id": "50000099", "workspace_id": OWN_WS, "name": "Supplier list"})
        self.end()
        return self.data("account.json")["live_objects"]["001:B9"]

    def with_notifies(self, **recipients):
        """TABLE with the notifies cells given by key, every other row as NOTIFIES gives it."""
        return tuple(row + (recipients[row[0]],) if row[0] in recipients else row for row in TABLE)

    def test_U17_P14_a_strand_cannot_set_a_client_row_without_a_client_quote_or_a_user_decision(self):
        row = self.client_board()
        self.assertEqual((row["introduced_in"], row["owner_strand"], row["constraint"], row["constraint_source"]),
                         ("client", None, "change-with-own-yes", "pending strand close"))
        for source in ("decision 2026-11-05", "the client is relaxed about it", "calls/2026-10-20-discovery.md"):
            found = self.refused("live-map", "set", "--strand", "001", "--key", "001:B9", "--constraint", "free",
                                 "--source", source)
            self.assertIn(("(flags)", "--source"), pairs(found), source)
            self.assertIn("no strand owns", words(found))
        self.assertEqual(self.check()[1], set())

    def test_U17_a_client_row_takes_a_user_decision_or_a_client_quote_from_any_strand(self):
        self.client_board()
        data = self.ok("live-map", "set", "--strand", "002", "--key", "001:B9", "--constraint", "free",
                       "--source", self.DECISION)
        self.assertEqual((data["constraint"], data["source"]), ("free", self.DECISION))
        for strand, source in (("002", "inputs/2026-10-02-supplier-sheet.md §2.1"), ("001", self.QUOTE)):
            self.ok("live-map", "set", "--strand", strand, "--key", "001:B9", "--constraint", "do-not-change",
                    "--source", source)
        row = self.data("account.json")["live_objects"]["001:B9"]
        self.assertEqual((row["constraint"], row["constraint_source"], row["owner_strand"]),
                         ("do-not-change", self.QUOTE, None))
        self.assertEqual(self.check()[1], set())

    def test_U17_a_row_a_strand_built_keeps_the_owner_rule(self):
        self.approve()
        self.start()
        self.sales()
        self.end()
        self.assertEqual(self.data("account.json")["live_objects"]["001:W2"]["owner_strand"], "001")
        found = self.refused("live-map", "set", "--strand", "002", "--key", "001:W2", "--constraint", "free",
                             "--source", self.DECISION)
        self.assertIn(("account.json", "live_objects.001:W2.owner_strand"), pairs(found))
        self.ok("live-map", "set", "--strand", "001", "--key", "001:W2", "--constraint", "free", "--source",
                "decision 2026-11-05 14:40")
        self.edit_json("account.json", lambda d: d["live_objects"]["001:W2"].update(owner_strand=None))
        self.assertIn(("account.json", "live_objects.001:W2.owner_strand"), self.check()[1])

    def test_U20_matching_recipients_pass_and_the_approval_records_them(self):
        data = self.approve(rows=self.with_notifies(A1="user", B2="`team:30000001`"))
        recorded = data["approval"]["notifies_approved"]
        self.assertEqual((recorded["A1"], recorded["SQ1"], recorded["B2"], recorded["B1"]),
                         (["user"], ["user"], ["team:30000001"], []))
        self.assertNotIn("U1", recorded)
        self.assertEqual(self.data()["approvals"][-1]["notifies_approved"], recorded)
        self.start()
        found = self.intent("A1", "--parent-key", "B1", "--notifies", "20000001")
        self.assertEqual((found["yes"], found["approval_mode"]), ("card", "own-account-poc"))
        self.assertEqual(self.row("A1")["notifies"], ["20000001"])
        self.intent("SQ1", "--scope", OWN_WS, "--notifies", "20000001")
        self.assertEqual(self.check()[1], set())

    def test_U20_a_missing_notifies_is_refused_where_the_revision_approves_recipients(self):
        self.approve(rows=self.with_notifies(A1="user"))
        self.start()
        found = self.no("intent", "--key", "A1", "--operation", "create", "--parent-key", "B1")
        self.assertIn((B1J, "objects.A1.notifies"), pairs(found))
        self.assertIn("no recipient given, while v0.2r1 approves 20000001", words(found))
        self.assertIn((B1J, "objects.SQ1.notifies"), pairs(self.no("intent", "--key", "SQ1", "--operation", "create",
                                                                   "--scope", OWN_WS)))

    def test_U20_an_extra_recipient_is_refused(self):
        self.approve(rows=self.with_notifies(A1="user"))
        self.start()
        for key, argv in (("A1", ["--parent-key", "B1", "--notifies", "20000001", "--notifies", "90600000001"]),
                          ("SQ1", ["--scope", OWN_WS, "--notifies", "20000001", "--notifies", "email:orders@example.com"]),
                          ("B2", ["--workspace", OWN_WS, "--notifies", "20000001"])):
            found = self.no("intent", "--key", key, "--operation", "create", *argv)
            self.assertIn((B1J, "objects.%s.notifies" % key), pairs(found), key)
        self.intent("B2", "--workspace", OWN_WS)  # approved for nobody, given nobody

    def test_U20_a_recipient_other_than_the_user_needs_the_lists_own_yes_on_a_proof_of_concept(self):
        self.approve(rows=self.with_notifies(A1="user, 90600000001"))
        self.start()
        argv = ["--parent-key", "B1", "--notifies", "90600000001", "--notifies", "20000001"]
        found = self.no("intent", "--key", "A1", "--operation", "create", *argv)
        self.assertEqual(pairs(found), {(B1J, "irreversible_yes")})
        self.assertIn("needs its own grouped yes", words(found))
        self.assertIn("mode per-list, it notifies 90600000001", words(found))
        self.yes("A1", "grouped")
        data = self.intent("A1", *argv)
        self.assertEqual((data["class"], data["yes"], data["approval_mode"]), ("list", "grouped", "per-list"))
        self.assertEqual([e["mode"] for e in self.data()["irreversible_yes"] if e["key"] == "A1"], ["grouped"])

    def test_U20_a_table_without_the_notifies_column_is_refused_and_an_older_approval_holds_nothing(self):
        found = self.refused(*self.approval_argv(self.make_v2(notifies=False)))
        self.assertIn((V2 + "/blueprint-r1.md", "## Element keys"), pairs(found))
        self.assertIn("no notifies column", words(found))
        for cell, expect in (("someone", "is not user"), ("user, user", "twice"), ("team:x", "is not user")):
            found = self.refused(*self.approval_argv(self.make_v2(rows=self.with_notifies(A1=cell))))
            self.assertIn(expect, words(found), cell)
        found = self.refused(*self.approval_argv(self.make_v2(rows=self.with_notifies(U1="user"))))
        self.assertIn("notifies nobody", words(found))
        self.approve()
        self.start()
        self.edit_json(B1J, lambda d: d["approvals"][-1].pop("notifies_approved"))
        found = self.no("intent", "--key", "B2", "--operation", "create", "--workspace", OWN_WS)
        self.assertIn((B1J, "approvals[].notifies_approved"), pairs(found))


class Demo2Test(Base):
    def test_demo2_a_columns_label_ids_are_not_monday_ids(self):
        # A status column's read, as the live ring returns it: label ids are numbers, and monday numbers them from 0.
        read = {"id": "status", "type": "status", "board": {"id": BOARD}, "settings": {"labels": [
            {"id": 0, "label": "Measured", "color": 0}, {"id": 1, "label": "Fitted", "is_done": True}]}}
        self.assertEqual((self.led.numeric_ids(read), self.led.zero_ids(read)), ([], []))
        spelt = {"settings": {"labels": [{"id": "0", "label": "Measured"}, {"id": "1", "label": "Fitted"}]}}
        self.assertEqual((self.led.numeric_ids(spelt), self.led.zero_ids(spelt)), ([], []))
        # Every other id still has its one spelling, beside the labels too.
        wrong = {"board": {"id": int(BOARD)}, "workspace_id": "0" + OWN_WS, "settings": {"labels": [{"id": 0}]}}
        self.assertEqual((self.led.numeric_ids(wrong), self.led.zero_ids(wrong)), (["board.id"], ["workspace_id"]))


if __name__ == "__main__":
    unittest.main()
