"""Unit tests for plugins/monday-master-builder/scripts/record.py, part 1 (WP2, contract clauses by name).

Each test copies tests/unit/fixtures/home/ into a temporary folder whose name holds a space, points
MMB_HOME at it and HOME and USERPROFILE at an empty canary folder, and pins mmb_common's clock to the
fixture's reference time; tearDown asserts the canary and the real default home are untouched (C17).
record.py runs from a temporary plugin root made of tests/unit/fixtures/plugin/ and a copy of scripts/
(G31, G36): in process through main() wherever the pinned clock matters, and as a subprocess where the
process boundary is the point (C18, C52, G49). Tests whose docstring says "Windows run" must be repeated
on a real Windows machine (C04).
"""
import ast, contextlib, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, unittest  # noqa: E401
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPTS = HERE.parent.parent / "plugins" / "monday-master-builder" / "scripts"
sys.dont_write_bytecode = True  # nothing cached beside the scripts (G49)
sys.path.insert(0, str(SCRIPTS))
import mmb_common as mc  # noqa: E402

REAL_HOME, CLOCK = Path.home(), datetime(2026, 11, 5, 14, 30, tzinfo=timezone.utc)
LABEL, IGNORE = "20261105-1405-r2d6", shutil.ignore_patterns(".gitkeep", ".DS_Store")
S1, S2, V1 = "strands/001-job-tracking", "strands/002-timber-orders", "strands/001-job-tracking/versions/v0.1"
TRANSCRIPT, EMAIL = "calls/2026-10-20-discovery.transcript.txt", "inputs/2026-10-21-timber-orders.txt"
KEYS = ["expected", "field", "file", "problem"]
NINE = ("What the work was", "Pains it served", "What was built", "What the client confirmed", "What must not be broken",
        "Cost of change, in the client's words", "Ownership and switch-off at close", "Backlog seeds carried forward",
        "Dates")
CALL = "[00:00:02] Office administrator: We order from three suppliers.\n[00:00:09] The user: Which one is late most?\n"


def is_stdlib(name):
    names = getattr(sys, "stdlib_module_names", None)  # Python 3.10 and later
    if names is not None:
        return name in names
    spec = importlib.util.find_spec(name)
    return spec is not None and "site-packages" not in str(spec.origin)


def add_lint(plugin):
    """R48: leak_lint.py beside record.py and the shipped list it reads, so that record.py's index after a write
    runs in a plugin copy as it does in the plugin. One helper for every test file that builds a plugin root."""
    shutil.copy(SCRIPTS / "leak_lint.py", plugin / "scripts" / "leak_lint.py")
    (plugin / "shared").mkdir(exist_ok=True)
    shutil.copy(SCRIPTS.parent / "shared" / "leak-terms.txt", plugin / "shared" / "leak-terms.txt")
    return plugin


def make_plugin(target):
    """A plugin root as G31 has the tests build it: the stand-in templates and plugin.json, scripts/ and the
    shipped leak list (R48)."""
    plugin = Path(shutil.copytree(FIXTURES / "plugin", target))
    (plugin / "scripts").mkdir()
    for name in ("mmb_common.py", "record.py"):
        shutil.copy(SCRIPTS / name, plugin / "scripts" / name)
    return add_lint(plugin)


def summary_draft(built="Nothing yet: the strand has no released version.", extra=0):
    blocks = ["## %s\n\n%s\n" % (title, built if title == "What was built" else "One line for %s." % title.lower())
              for title in NINE]
    return "\n".join(blocks) + "".join("filler line %d\n" % n for n in range(extra))


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plugin_tmp = Path(tempfile.mkdtemp(prefix="mmb record plugin "))
        cls.plugin = make_plugin(cls.plugin_tmp / "plugin")
        spec = importlib.util.spec_from_file_location("record_under_test", cls.plugin / "scripts" / "record.py")
        cls.rec = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rec)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.plugin_tmp)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mmb record "))
        self.canary, self.now = self.tmp / "canary", CLOCK
        self.canary.mkdir()
        self.home = Path(shutil.copytree(FIXTURES / "home", self.tmp / "mmb home", ignore=IGNORE))
        self.root = self.home / "clients" / "larkmoor-joinery"
        self.real = self.snapshot(REAL_HOME / "monday-builder")
        env = {"MMB_HOME": str(self.home), "HOME": str(self.canary), "USERPROFILE": str(self.canary)}
        for patcher in (mock.patch.dict(os.environ, env), mock.patch.object(mc, "now_utc", lambda: self.now)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.assertEqual(list(self.canary.iterdir()), [])  # C17
        self.assertEqual(self.snapshot(REAL_HOME / "monday-builder"), self.real)
        shutil.rmtree(self.tmp)

    @staticmethod
    def snapshot(path):
        return path.exists(), path.stat().st_mtime_ns if path.exists() else None

    def run_record(self, *argv):
        """(exit code, the one JSON object printed) of record.py main(), in process, on the copy's record."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.rec.main(["--record", str(self.root)] + [str(arg) for arg in argv])
        data = json.loads(out.getvalue())
        self.four_parts(data)
        return code, data

    def four_parts(self, data):
        """C21: every refusal, blocking and warning finding, status's findings and an exit-3 error name all four
        parts, each non-empty."""
        found = data.get("refusals", []) + data.get("blocking", []) + data.get("warnings", [])
        found += (data.get("findings") or {}).get("blocking", []) + (data.get("findings") or {}).get("warnings", [])
        found += [data["error"]] if "error" in data else []
        for finding in found:
            self.assertEqual(sorted(finding), KEYS)
            self.assertTrue(all(finding.values()), finding)

    def ok(self, *argv):
        code, data = self.run_record(*argv)
        self.assertEqual((code, data.get("ok")), (0, True), data)
        return data

    def refused(self, *argv):
        """The (file, field) pairs of a refusal, after asserting exit 1 and no change to the tree (C13, G10)."""
        before = self.tree()
        code, data = self.run_record(*argv)
        self.assertEqual((code, data["ok"]), (1, False), data)
        self.assertEqual(self.tree(), before)
        return {(finding["file"], finding["field"]) for finding in data["refusals"]}

    def check(self):
        """(exit code, blocking (file, field) pairs, warning pairs) of `check`, which must write nothing."""
        before = self.tree()
        code, data = self.run_record("check")
        self.assertEqual(self.tree(), before)  # C146
        return code, {(f["file"], f["field"]) for f in data["blocking"]}, {(f["file"], f["field"]) for f in data["warnings"]}

    def tree(self):
        return {p.relative_to(self.root).as_posix(): mc.sha256_file(p) for p in self.root.rglob("*")
                if p.is_file() and p.name != "record.mutex"}

    def fm(self, rel):
        return mc.front_matter(mc.read_text(self.root / rel))

    def edit_fm(self, rel, **updates):
        path = self.root / rel
        path.write_bytes(mc.set_front_matter(mc.read_text(path), updates).encode("utf-8"))

    def edit_json(self, rel, change):
        data = json.loads((self.root / rel).read_text(encoding="utf-8"))
        change(data)
        (self.root / rel).write_text(mc.json_text(data), encoding="utf-8")

    def append(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((path.read_bytes() if path.exists() else b"") + text.encode("utf-8"))

    def stage(self, text, name="staged.md", data=None):
        path = self.tmp / name
        path.write_bytes(data if data is not None else text.encode("utf-8"))
        return path

    def entries(self, rel="log.md"):
        return re.split(r"(?m)^(?=## \d{4}-)", mc.read_text(self.root / rel))[1:]


class FrameTest(Base):

    def test_C01_C02_C05_C06_C15_C19_C82_source_rules(self):
        source = (SCRIPTS / "record.py").read_text(encoding="utf-8")
        for path in (SCRIPTS / "record.py", Path(__file__)):
            module = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
            names = {a.name.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.Import) for a in n.names}
            names |= {n.module.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.ImportFrom)}
            for name in names - {"mmb_common"}:
                self.assertTrue(is_stdlib(name), "%s imports %s" % (path.name, name))
        for pattern in (r"os\.system", r"shell\s*=", r"os\.popen", r"\bsubprocess\b", r"os\.(rename|replace|remove|unlink)",
                        r"shutil\.(move|rmtree)", r"\.(unlink|rename|rmdir)\(", r"expanduser", r"os\.sep", r'"~',
                        r'\+ *"(/|\\\\)"', r'"(/|\\\\)" *\+', r"CLAUDE_PLUGIN_ROOT", r"write_file\([^\n]*(lock\.json|read_lock|LOCK)",
                        r"\[\"lease\"\]\s*=", r"\.now\("):
            self.assertIsNone(re.search(pattern, source), pattern)
        for text in (source, Path(__file__).read_text(encoding="utf-8")):
            for needle in ("Del" + "Ops", "/" + "Users/", "C:" + "\\" + "Users", "Library" + "/"):
                self.assertNotIn(needle, text)

    def test_C21_no_finding_or_error_is_built_with_an_empty_part(self):
        """Source rule behind the runtime tests: no tuple handed to a refusal, an error or a finding holds an empty
        string for the file, the field, the problem or the expected value (the five sites that once did are fixed)."""
        builders = {"CannotRun", "Refusal", "FrontMatterError", "MMBError", "refuse", "block", "warn"}
        for path in (SCRIPTS / "mmb_common.py", SCRIPTS / "record.py"):
            module = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
            for call in (n for n in ast.walk(module) if isinstance(n, ast.Call)):
                name = getattr(call.func, "attr", getattr(call.func, "id", None))
                if name not in builders:
                    continue
                parts = [n.elts for arg in call.args for n in ast.walk(arg) if isinstance(n, ast.Tuple) and len(n.elts) == 4]
                parts += [call.args] if name in ("block", "warn") and len(call.args) == 4 else []
                for elts in parts:
                    for part in elts:
                        self.assertFalse(isinstance(part, ast.Constant) and part.value in ("", None),
                                         "%s line %d" % (path.name, call.lineno))

    def test_C25_G05_G10_catalogue_and_usage_errors(self):
        catalogue = {"home init", "init", "status", "check", "log", "guard", "add-transcript", "add-document", "freeze",
                     "card", "lease take", "lease refresh", "lease release", "lease status", "lease break",
                     "lease sync", "lease repair",
                     "strand open", "strand list", "strand pause", "strand kind", "strand close", "strand summary",
                     "strand resume", "version open", "version mark", "version condense-plan", "version condense-apply",
                     "version release", "client rename"}
        self.assertEqual(set(self.rec.COMMANDS), catalogue)
        self.assertTrue(all(callable(command) for command in self.rec.COMMANDS.values()))  # part 2 built
        for argv in (("migrate",), ("tools-check",), ("log", "--strand", "001"), ("strand",), ("status", "--bogus"), (),
                     ("version", "mark", "--strand", "001"), ("lease", "take"), ("card",), ("init", "--slug", "x")):
            code, data = self.run_record(*argv)
            self.assertEqual((code, data["ok"], data["error"]["field"]), (3, False, "arguments"), argv)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.rec.main(["--record", str(self.tmp), "status"])
        self.assertEqual((code, json.loads(out.getvalue())["error"]["file"]), (3, "CLIENT.md"))

    def test_C18_C24_G36_G49_runs_from_a_plugin_copy_and_writes_nothing_there(self):
        """Windows run: the same launch form, [interpreter, script path, ...], with no shell (C22)."""
        plugin = make_plugin(self.tmp / "plugin copy")
        manifest = plugin / ".claude-plugin" / "plugin.json"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace('"0.1.0"', '"9.8.7"'), encoding="utf-8")
        before = sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*"))
        env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
        env["HOME"] = env["USERPROFILE"] = str(self.tmp / "interpreter home")  # the system Python's own cache

        def launch(*argv):
            done = subprocess.run([sys.executable, str(plugin / "scripts" / "record.py")] + list(argv), cwd=str(self.root),
                                  env=env, capture_output=True)
            return done.returncode, json.loads(done.stdout.decode("utf-8"))
        code, status = launch("status", "--json")
        self.assertEqual((code, status["schema"], status["plugin_version"]), (0, "status/1", "9.8.7"))
        self.assertEqual(launch("check")[1]["blocking"], [])  # the untouched fixture, at the real clock
        self.assertEqual(launch("log", "--strand", "-", "--type", "decision", "--key", "cli", "--line", "x")[0], 0)
        self.assertEqual(sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*")), before)
        shutil.rmtree(plugin / ".claude-plugin")
        code, status = launch("status")
        self.assertEqual((code, status["error"]["file"]), (3, "plugin.json"))

    def test_G31_a_missing_template_cannot_run_and_writes_nothing(self):
        before = self.tree()
        with mock.patch.object(self.rec, "TEMPLATES", self.tmp / "no templates"):
            code, data = self.run_record("strand", "open", "--topic", "x", "--title", "X", "--kind", "platform",
                                         "--reason", "r")
        self.assertEqual((code, data["error"]["file"]), (3, "templates/record/STRAND.md"))
        self.assertEqual(self.tree(), before)

    def test_C20_C21_C27_C145_the_fixture_record_checks_clean(self):
        self.assertEqual(self.run_record("check"), (0, {"ok": True, "command": "check", "blocking": [], "warnings": []}))

    def test_C13_G57_a_newer_schema_refuses_every_write_and_still_reads(self):
        self.edit_fm("CLIENT.md", schema="client/3")
        source, draft = self.stage(CALL, "call.txt"), self.stage(summary_draft(), "draft.md")
        staged = self.stage(mc.read_text(self.root / S2 / "STRAND.md"))
        for argv in (("log", "--strand", "-", "--type", "decision", "--key", "k", "--line", "x"),
                     ("guard", "--file", S2 + "/STRAND.md", "--expect-sha", mc.sha256_file(self.root / S2 / "STRAND.md"),
                      "--from", staged),
                     ("add-transcript", "--strand", "001", "--from", source, "--type", "intro", "--fixture"),
                     ("add-document", "--strand", "001", "--from", source, "--title", "notes", "--fixture"),
                     ("freeze", "--strand", "001"),
                     ("strand", "open", "--topic", "x", "--title", "X", "--kind", "platform", "--reason", "r"),
                     ("strand", "pause", "--strand", "002", "--reason", "r"),
                     ("strand", "kind", "--strand", "002", "--kind", "hybrid", "--reason", "r"),
                     ("strand", "close", "--strand", "002"), ("strand", "resume", "--strand", "002"),
                     ("strand", "summary", "--strand", "002", "--plan", draft)):
            self.assertIn(("CLIENT.md", "schema"), self.refused(*argv), argv)
        code, status = self.run_record("status", "--json")
        self.assertEqual((code, status["schema_newer"], status["record_schema"]), (0, True, "client/3"))
        self.assertEqual(self.check()[:2], (1, {("CLIENT.md", "schema")}))
        self.edit_fm("CLIENT.md", schema="client/2")
        self.edit_fm(S2 + "/STRAND.md", schema="strand/2")
        for argv in (("strand", "pause", "--strand", "002", "--reason", "r"), ("strand", "close", "--strand", "002")):
            self.assertEqual(self.refused(*argv), {(S2 + "/STRAND.md", "schema")})

    def test_C14_C15_rewrites_back_up_keep_the_file_and_never_rename_or_delete(self):
        """Windows run: in-place overwrite semantics differ there."""
        targets = ("os.rename", "os.replace", "os.remove", "os.unlink", "os.rmdir", "shutil.move", "shutil.rmtree",
                   "pathlib.Path.unlink", "pathlib.Path.rename", "pathlib.Path.replace", "pathlib.Path.rmdir")
        client = self.root / "CLIENT.md"
        inode, old = client.stat().st_ino, client.read_bytes()
        with contextlib.ExitStack() as stack:
            spies = [stack.enter_context(mock.patch(target)) for target in targets]
            self.ok("strand", "open", "--topic", "orders", "--title", "Orders", "--kind", "platform", "--reason", "r")
            self.ok("strand", "pause", "--strand", "002", "--reason", "waiting")
            self.ok("strand", "close", "--strand", "003")
            self.ok("add-transcript", "--strand", "002", "--from", self.stage(CALL, "c.txt"), "--type", "intro", "--fixture")
        self.assertEqual([spy.call_count for spy in spies], [0] * len(targets))
        self.assertEqual(client.stat().st_ino, inode)
        backups = sorted((self.root / ".work" / "backup").glob("CLIENT.md.*"))
        self.assertEqual(backups[0].read_bytes(), old)


class WriteTest(Base):

    def test_C45_C46_guard_refuses_a_stale_sha_and_writes_after_a_backup(self):
        path = self.root / "CLIENT.md"
        read = self.ok("guard", "--file", "CLIENT.md")["sha256"]
        self.assertEqual(read, mc.sha256_file(path))
        staged = self.stage(mc.read_text(path).replace("## Recent research\n\nNone.", "## Recent research\n\nOne brief."))
        self.append("CLIENT.md", "\nA line another session added.\n")
        self.assertEqual(self.refused("guard", "--file", "CLIENT.md", "--expect-sha", read, "--from", staged),
                         {("CLIENT.md", "sha256")})
        fresh = mc.sha256_file(path)
        self.assertEqual(self.ok("guard", "--file", "CLIENT.md", "--expect-sha", fresh, "--from", staged)["file"], "CLIENT.md")
        text = mc.read_text(path)
        self.assertIn("One brief.", text)
        self.assertEqual(self.fm("CLIENT.md")["updated"], mc.stamp("minute"))
        self.assertEqual(len(list((self.root / ".work" / "backup").glob("CLIENT.md.*"))), 1)
        lease = self.stage(text.replace('lease: "001 v0.1 (%s)"' % LABEL, 'lease: "none"'))
        self.assertEqual(self.refused("guard", "--file", "CLIENT.md", "--expect-sha", mc.sha256_file(path), "--from",
                                      lease), {("CLIENT.md", "lease")})
        for rel in ("log.md", V1 + "/blueprint-r1.md", ".work/lock.json"):
            self.assertIn((rel, "file"), self.refused("guard", "--file", rel, "--expect-sha", "none", "--from", lease))

    def test_C47_two_sessions_on_two_blocks_lose_neither(self):
        for rel in ("CLIENT.md", S1 + "/STRAND.md"):
            read, text = self.ok("guard", "--file", rel)["sha256"], mc.read_text(self.root / rel)
            first = self.stage(text + "\n## Block of session A\n\nA's notes.\n", "a.md")
            second = self.stage(text + "\n## Block of session B\n\nB's notes.\n", "b.md")
            self.ok("guard", "--file", rel, "--expect-sha", read, "--from", first)
            self.assertEqual(self.refused("guard", "--file", rel, "--expect-sha", read, "--from", second), {(rel, "sha256")})
            again = self.ok("guard", "--file", rel)["sha256"]  # session B re-reads, then writes its block again
            reread = self.stage(mc.read_text(self.root / rel) + "\n## Block of session B\n\nB's notes.\n", "b2.md")
            self.ok("guard", "--file", rel, "--expect-sha", again, "--from", reread)
            final = mc.read_text(self.root / rel)
            self.assertIn("A's notes.", final)
            self.assertIn("B's notes.", final)
        self.assertEqual(self.check()[0], 0)

    def test_G06_guard_on_a_strand_rewrites_the_index_in_the_same_step(self):
        rel = S2 + "/STRAND.md"
        staged = self.stage(mc.read_text(self.root / rel).replace('title: "Timber orders"', 'title: "Timber order book"'))
        self.ok("guard", "--file", rel, "--expect-sha", mc.sha256_file(self.root / rel), "--from", staged)
        self.assertIn("| 002 | Timber order book | platform |", mc.read_text(self.root / "CLIENT.md"))
        self.assertEqual(self.check()[0], 0)

    def test_C08_C09_C11_crlf_reads_alike_and_writes_back_lf_with_comments_kept(self):
        """Windows run: a CRLF CLIENT.md parses alike and every record.py write leaves LF behind."""
        lf_status = self.run_record("status")[1]
        shutil.copytree(FIXTURES / "crlf" / "home", self.home, dirs_exist_ok=True)
        self.assertIn(b"\r\n", (self.root / "CLIENT.md").read_bytes())
        crlf_status = self.run_record("status")[1]
        self.assertEqual((crlf_status["record"], crlf_status["strands"]), (lf_status["record"], lf_status["strands"]))
        self.assertEqual(self.check()[0], 0)
        self.ok("strand", "open", "--topic", "orders", "--title", "Orders", "--kind", "hybrid", "--reason", "r")
        data = (self.root / "CLIENT.md").read_bytes()
        self.assertNotIn(b"\r", data)
        for line in (b'lease: "001 v0.1 (20261105-1405-r2d6)"   # mirrors .work/lock.json',
                     b"# The three A11 fields stay open", b'account_kind: "own"                    # own | client'):
            self.assertIn(line, data)

    def test_C48_C49_C50_log_inserts_newest_first_with_the_strand_position(self):
        old = self.entries()
        self.ok("log", "--strand", "001", "--type", "decision", "--version", "v0.1", "--key", "k1", "--line", "first")
        self.ok("log", "--strand", "-", "--type", "research", "--key", "k2", "--line", "a", "--line", "b")
        entries, minute = self.entries(), mc.stamp("log")
        self.assertEqual([e.split("\n", 1)[0] for e in entries[:2]],
                         ["## %s · - · research · - · k2" % minute, "## %s · 001 · decision · v0.1 · k1" % minute])
        self.assertEqual(entries[2:], old)
        for entry in entries:
            self.assertRegex(entry, r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2} · (\d{3}|-) · [a-z-]+ · (v\d+\.\d+|-) · .+\n")
        self.assertEqual(json.loads((self.root / ".work" / "history.json").read_text(encoding="utf-8"))["entries"],
                         [mc.sha256_text(entry) for entry in entries])
        self.assertEqual(self.check()[0], 0)

    def test_C51_G45_log_takes_the_44_types_and_refuses_what_breaks_the_form(self):
        rm = (SCRIPTS.parent / "shared" / "record-map.md").read_text(encoding="utf-8")
        listed = list(dict.fromkeys(re.findall(r"`([a-z-]+)`", rm.split("agrees with this one: ", 1)[1].split(". A save", 1)[0])))
        self.assertEqual((len(self.rec.LOG_TYPES), list(self.rec.LOG_TYPES)), (44, listed))
        for kind in ("created", "signed-off", "ai-column", "archive"):
            self.ok("log", "--strand", "-", "--type", kind, "--key", "k", "--line", "x")
        base = ["--strand", "001", "--type", "decision", "--key", "k"]
        for change, field in ((["--type", "demo"], "type"), (["--line", "x"] * 6, "body"), (["--key", "a · b"], "key"),
                              (["--key", " "], "key"), (["--line", "## not a header"], "body"), (["--line", " "], "body"),
                              (["--strand", "009"], "strand"), (["--strand", "1"], "strand"), (["--version", "0.1"], "version")):
            self.assertEqual(self.refused("log", *(base + change)), {("log.md", field)}, change)

    def test_C52_concurrent_log_inserts_all_survive(self):
        """Windows run: the msvcrt branch of the record mutex."""
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        workers = [subprocess.Popen([sys.executable, str(self.plugin / "scripts" / "record.py"), "--record", str(self.root),
                                     "log", "--strand", "-", "--type", "decision", "--key", "writer-%d" % n, "--line",
                                     "insert %d" % n], env=env, stdout=subprocess.PIPE) for n in range(6)]
        for worker in workers:
            worker.communicate(timeout=60)
        self.assertEqual([worker.returncode for worker in workers], [0] * 6)
        entries = self.entries()
        self.assertEqual((len(entries), sum("· writer-" in e.split("\n", 1)[0] for e in entries)), (16, 6))
        self.assertEqual(json.loads((self.root / ".work" / "history.json").read_text(encoding="utf-8"))["entries"],
                         [mc.sha256_text(entry) for entry in entries])

    def test_C53_G08_history_only_grew(self):
        path = self.root / "log.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("calls used 14", "calls used 15"), encoding="utf-8")
        code, blocking, warnings = self.check()
        build = "2026-10-28 11:40 · 001 · build · v0.1 · run-2026-10-28-1"
        self.assertEqual((code, blocking, warnings), (1, {("log.md", build)}, {("log.md", build)}))
        path.write_text(text, encoding="utf-8")
        (self.root / ".work" / "history.json").unlink()
        self.assertEqual(self.check(), (2, set(), {(".work/history.json", "entries")}))
        self.ok("log", "--strand", "-", "--type", "decision", "--key", "k", "--line", "x")
        self.assertEqual(self.check()[0], 0)

    def test_C54_G41_freeze_returns_two_matching_sha256(self):
        self.assertEqual(self.refused("freeze", "--strand", "001"), {(V1 + "/blueprint-r1.md", "revision")})
        self.assertEqual(self.refused("freeze", "--strand", "002"), {(S2 + "/STRAND.md", "version")})
        self.edit_fm(V1 + "/version.md", revision="2")
        data = self.ok("freeze", "--strand", "001")
        frozen, working = self.root / V1 / "blueprint-r2.md", self.root / S1 / "solution" / "blueprint.md"
        self.assertEqual((data["frozen_file"], data["revision"]), (V1 + "/blueprint-r2.md", "2"))
        self.assertEqual({data["working_sha256"], data["frozen_sha256"], mc.sha256_file(frozen)}, {mc.sha256_file(working)})
        self.assertEqual(frozen.read_bytes(), working.read_bytes())
        self.assertEqual(self.fm(V1 + "/version.md")["sha256"], data["frozen_sha256"])
        self.edit_fm(S2 + "/STRAND.md", kind="non-platform", version="v0.1")
        self.assertIn((S2 + "/STRAND.md", "kind"), self.refused("freeze", "--strand", "002"))

    def test_demos_5_freeze_logs_the_freeze(self):
        """Demos' fixes, 5: a freeze writes its own `blueprint` entry, keyed by the revision, with the frozen sha256."""
        self.edit_fm(V1 + "/version.md", revision="2")
        before = len(self.entries())
        data = self.ok("freeze", "--strand", "001")
        entries = self.entries()
        self.assertEqual(len(entries), before + 1)
        head, body = entries[0].rstrip("\n").split("\n", 1)
        self.assertRegex(head, r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2} · 001 · blueprint · v0\.1 · r2$")
        self.assertEqual(body, "frozen: %s/blueprint-r2.md · sha256: %s" % (V1, data["frozen_sha256"]))
        self.assertEqual(data["entry"], head)
        _, blocking, warnings = self.check()  # the entry is in the history baseline too: nothing about log.md
        self.assertEqual((blocking, {w for w in warnings if w[0] == "log.md" or w[0].startswith(".work")}), (set(), set()))

    def test_C10_C55_C60_C61_C62_add_transcript_saves_the_bytes_once(self):
        """Windows run: a CRLF transcript keeps its CRLF bytes and its recorded sha256."""
        crlf = self.stage("", "crlf call.txt", CALL.replace("\n", "\r\n").encode("utf-8"))
        data = self.ok("add-transcript", "--strand", "002", "--from", crlf, "--type", "discovery", "--date", "2026-10-20",
                       "--fixture")
        saved = self.root / "calls" / "2026-10-20-discovery-2.transcript.txt"
        self.assertEqual((data["path"], data["stem"], data["input_kind"]),
                         ("calls/2026-10-20-discovery-2.transcript.txt", "2026-10-20-discovery-2", "transcript"))
        self.assertEqual((saved.read_bytes(), data["sha256"]), (crlf.read_bytes(), mc.sha256_file(saved)))
        self.assertEqual(self.entries()[0], "## %s · - · call · - · 2026-10-20-discovery-2\npath: %s\nsha256: %s\n"
                         "input_kind: transcript · fixture: yes · asked_by: 002 · redactions: 0\n\n"
                         % (mc.stamp("log"), data["path"], data["sha256"]))
        self.assertEqual(self.fm("CLIENT.md")["last_input"], "2026-10-20-discovery-2")
        self.assertEqual(self.refused("add-transcript", "--strand", "001", "--from", crlf, "--type", "intro", "--fixture"),
                         {(data["path"], "sha256")})
        lf = self.ok("add-transcript", "--strand", "002", "--from", self.stage(CALL, "lf call.txt"), "--type", "discovery",
                     "--date", "2026-10-20", "--fixture")
        self.assertEqual((lf["stem"], lf["lines"]), ("2026-10-20-discovery-3", data["lines"]))
        self.assertFalse(any(p.suffix == ".txt" for p in (self.root / "strands").rglob("*")))
        self.assertEqual(self.check()[0], 0)

    def test_C143_C146_G14_a_real_input_waits_for_the_A11_3_answers(self):
        source = self.stage(CALL, "call.txt")
        self.assertEqual(self.refused("add-transcript", "--strand", "001", "--from", source, "--type", "intro"),
                         {("CLIENT.md", "transcripts_at_close"), ("CLIENT.md", "transcript_redaction")})
        self.ok("log", "--strand", "-", "--type", "call", "--key", "2026-11-05-intro", "--line", "path: calls/x.txt",
                "--line", "input_kind: transcript · fixture: no · asked_by: 001 · redactions: 0")
        self.assertEqual(self.check()[:2], (1, {("CLIENT.md", "transcripts_at_close"), ("CLIENT.md", "transcript_redaction")}))
        self.edit_fm("CLIENT.md", transcripts_at_close="exclude", transcript_redaction="none")
        self.ok("add-transcript", "--strand", "001", "--from", source, "--type", "intro")
        self.assertIn("input_kind: transcript · fixture: no · asked_by: 001", self.entries()[0])
        self.assertEqual(self.check()[:2], (0, set()))
        self.assertEqual((self.fm("CLIENT.md")["sample_data_in_account"]), "unanswered")

    def test_C56_C57_C58_C59_add_document_takes_emails_screenshots_and_attachments(self):
        email = self.stage("From: the office administrator\nSubject: Suppliers\n\nThe supplier list is attached.\n", "m.txt")
        shot = self.stage("", "screen shot.PNG", b"\x89PNG\r\n\x1a\n" + bytes(range(256)))
        sheet = self.stage("supplier,lead time\nA,3 days\n", "suppliers.csv")
        before = sorted(p.name for p in (self.root / "inputs").iterdir())
        mail = self.ok("add-document", "--strand", "002", "--from", email, "--title", "suppliers", "--kind", "email",
                       "--date", "2026-11-04", "--fixture")
        self.assertEqual((mail["path"], mail["input_kind"]), ("inputs/2026-11-04-suppliers.txt", "email"))
        self.assertEqual((self.root / mail["path"]).read_bytes(), email.read_bytes())
        self.assertIn("input_kind: email · fixture: yes · asked_by: 002", self.entries()[0])
        self.assertEqual(sorted(p.name for p in (self.root / "inputs").iterdir()), sorted(before + ["2026-11-04-suppliers.txt"]))
        image = self.ok("add-document", "--strand", "002", "--from", shot, "--title", "suppliers-shot", "--kind", "email",
                        "--fixture")
        self.assertEqual((image["path"][-4:], (self.root / image["path"]).read_bytes()), (".png", shot.read_bytes()))
        self.assertEqual(self.refused("add-document", "--strand", "002", "--from", sheet, "--title", "list", "--came-with",
                                      EMAIL[:-4] + ".csv", "--fixture"), {("inputs/", "came_with")})
        attached = self.ok("add-document", "--strand", "002", "--from", sheet, "--title", "suppliers", "--date",
                           "2026-11-04", "--came-with", mail["path"], "--fixture")
        self.assertEqual(attached["path"], "inputs/2026-11-04-suppliers-2.csv")
        self.assertIn("came_with: inputs/2026-11-04-suppliers.txt\n", self.entries()[0])
        for path, extra, field in ((self.stage("x", "a.pdf"), ["--kind", "email"], "extension"),
                                   (self.stage("# x\n", "a.md"), [], "extension"), (sheet, [], "sha256"),
                                   (self.stage("y", "b.txt"), ["--title", "Bad Title"], "title")):
            refusal = self.refused("add-document", "--strand", "002", "--from", path, "--title", "t", "--fixture", *extra)
            self.assertIn(field, {f for _, f in refusal})
        self.assertEqual(self.check()[0], 0)


class StrandTest(Base):

    def test_C63_C64_C66_C67_C68_C69_open_writes_the_strand_and_the_index(self):
        data = self.ok("strand", "open", "--topic", "supplier-orders", "--title", "Supplier orders", "--kind", "platform",
                       "--reason", "the 2026-11-04 email asked for it")
        folder = self.root / "strands" / "003-supplier-orders"
        self.assertEqual((data["strand"], data["folder"], folder.name), ("003", "strands/003-supplier-orders", data["slug"]))
        fields = self.fm("strands/003-supplier-orders/STRAND.md")
        self.assertEqual({k: fields[k] for k in ("schema", "strand", "kind", "output_class", "opened", "state", "stage",
                                                 "version", "version_state", "clearance", "closed", "updated")},
                         {"schema": "strand/1", "strand": "003", "kind": "platform", "output_class": "configured-structure",
                          "opened": mc.stamp("date"), "state": "active", "stage": "new", "version": "none",
                          "version_state": "none", "clearance": "none", "closed": "none", "updated": mc.stamp("minute")})
        self.assertEqual(self.fm("strands/003-supplier-orders/readiness.md")["clearance"], "none")
        self.assertEqual(self.fm("strands/003-supplier-orders/solution/exclusions.md")["strand"], "003")
        self.assertEqual(sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")),
                         ["STRAND.md", "readiness.md", "solution", "solution/exclusions.md"])
        self.assertEqual((self.fm("CLIENT.md")["strands_total"], self.fm("CLIENT.md")["strands_open"]), ("3", "3"))
        self.assertIn("| 003 | Supplier orders | platform | active | none | none | none | 0 | %s |" % mc.stamp("date"),
                      mc.read_text(self.root / "CLIENT.md"))
        self.assertEqual(self.entries()[0].split("\n")[:2], ["## %s · 003 · strand · - · opened" % mc.stamp("log"),
                                                             "kind: platform · reason: the 2026-11-04 email asked for it"])
        self.assertEqual(self.check()[0], 0)
        for topic in ("a" * 25, "Supplier", "caf\u00e9", "a--b"):
            self.assertEqual(self.refused("strand", "open", "--topic", topic, "--title", "T", "--kind", "platform",
                                          "--reason", "r"), {("strands/", "topic")})
        self.assertEqual(self.refused("strand", "open", "--topic", "x", "--title", "T", "--kind", "app", "--reason", "r"),
                         {("strands/", "kind"), ("strands/", "output_class")})

    def test_C63_G56_ordinals_are_never_reused(self):
        for topic in ("one", "two"):
            self.ok("strand", "open", "--topic", topic, "--title", topic, "--kind", "platform", "--reason", "r")
        self.ok("strand", "close", "--strand", "003")
        self.assertEqual(self.ok("strand", "open", "--topic", "three", "--title", "T", "--kind", "platform", "--reason",
                                 "r")["strand"], "005")
        self.assertEqual(self.ok("strand", "list")["strands"][2]["state"], "closed")

    def test_C65_C69_each_kind_with_its_reason(self):
        for kind, output, short in (("platform", "configured-structure", "003"), ("non-platform", "bespoke-code", "004"),
                                    ("hybrid", "hybrid", "005")):
            data = self.ok("strand", "open", "--topic", kind, "--title", kind, "--kind", kind, "--reason", "why " + kind)
            fields = self.fm("strands/%s-%s/STRAND.md" % (short, kind))
            self.assertEqual((data["strand"], fields["kind"], fields["opened_reason"], fields["output_class"]),
                             (short, kind, "why " + kind, output))
            for name in ("versions", "solution/blueprint.md", "solution/build.json"):
                self.assertFalse((self.root / "strands" / ("%s-%s" % (short, kind)) / name).exists())
        self.assertEqual(self.check()[0], 0)

    def test_C70_G25_list(self):
        self.assertEqual(self.ok("strand", "list")["strands"],
                         [{"strand": "001", "title": "Job tracking", "kind": "platform", "state": "active", "version": "v0.1",
                           "version_state": "audited", "clearance": "cleared to build", "live_objects": "3",
                           "last_activity": "2026-11-05"},
                          {"strand": "002", "title": "Timber orders", "kind": "platform", "state": "active", "version": "none",
                           "version_state": "none", "clearance": "none", "live_objects": "0", "last_activity": "2026-10-23"}])

    def test_C71_G52_pause(self):
        self.assertEqual(self.refused("strand", "pause", "--strand", "001", "--reason", "r"), {(".work/lock.json", "strand")})
        self.ok("strand", "pause", "--strand", "002", "--reason", "waiting for the supplier list")
        self.assertEqual(self.fm(S2 + "/STRAND.md")["state"], "paused")
        self.assertTrue(mc.read_text(self.root / S2 / "STRAND.md").endswith(
            "\n## Paused\n\n- paused %s by the user: waiting for the supplier list\n" % mc.stamp("date")))
        self.assertIn("| 002 | Timber orders | platform | paused |", mc.read_text(self.root / "CLIENT.md"))
        self.assertEqual(self.refused("strand", "pause", "--strand", "002", "--reason", "r"), {(S2 + "/STRAND.md", "state")})
        self.assertEqual(self.check()[0], 0)

    def test_G05_resume(self):
        self.assertEqual(self.refused("strand", "resume", "--strand", "002"), {(S2 + "/STRAND.md", "state")})
        self.ok("strand", "pause", "--strand", "002", "--reason", "parked by the user")
        build = {"schema": "build/2", "strand": "002", "account_id_at_bind": "10000001", "runs": [
            {"id": "run-2026-11-05-1", "version": "v0.1", "state": "interrupted"}]}
        (self.root / S2 / "solution" / "build.json").write_text(mc.json_text(build), encoding="utf-8")
        self.assertEqual(self.refused("strand", "resume", "--strand", "002"), {(S2 + "/solution/build.json", "runs")})
        self.edit_json(S2 + "/solution/build.json", lambda b: b["runs"][0].update(state="ended"))
        self.ok("strand", "resume", "--strand", "002")
        text = mc.read_text(self.root / S2 / "STRAND.md")
        self.assertEqual(self.fm(S2 + "/STRAND.md")["state"], "active")
        self.assertTrue(text.endswith("\n## Paused\n\nnone (resumed %s)\n" % mc.stamp("date")))
        self.edit_fm(S1 + "/STRAND.md", state="paused")
        self.assertEqual(self.refused("strand", "resume", "--strand", "001"), {(".work/lock.json", "strand")})

    def test_C72_kind_changes_only_without_versions(self):
        self.assertEqual(self.refused("strand", "kind", "--strand", "001", "--kind", "hybrid", "--reason", "r"),
                         {(S1 + "/STRAND.md", "version")})
        data = self.ok("strand", "kind", "--strand", "002", "--kind", "non-platform", "--reason", "a supplier portal script")
        fields = self.fm(S2 + "/STRAND.md")
        self.assertEqual((fields["kind"], fields["output_class"], fields["stage"], data["stage"]),
                         ("non-platform", "bespoke-code", "new", "new"))
        self.assertEqual(self.entries()[0].split("\n")[:3], [
            "## %s · 002 · strand · - · kind" % mc.stamp("log"),
            "kind: platform to non-platform · reason: a supplier portal script", "stage: intake to new"])
        self.assertEqual(self.refused("strand", "kind", "--strand", "002", "--kind", "non-platform", "--reason", "r"),
                         {(S2 + "/STRAND.md", "kind")})
        self.assertEqual(self.check()[0], 0)

    def test_C73_C78_C137_close_rolls_the_strands_entries_and_archives_nothing(self):
        for key in ("k1", "k2"):
            self.ok("log", "--strand", "002", "--type", "decision", "--key", key, "--line", "x")
        moved = [e for e in self.entries() if " · 002 · " in e.split("\n", 1)[0]]
        before = self.tree()
        data = self.ok("strand", "close", "--strand", "002")
        rolled = self.root / S2 / "log.md"
        self.assertEqual((data["rolled_to"], data["entries"]), (S2 + "/log.md", 3))
        self.assertEqual([e.rstrip("\n") for e in self.entries(S2 + "/log.md")], [e.rstrip("\n") for e in moved])
        self.assertEqual(data["sha256"], mc.sha256_text("".join(e.rstrip("\n") + "\n" for e in moved)))
        self.assertEqual((self.fm(S2 + "/log.md")["sha256"], self.fm(S2 + "/log.md")["entries"]), (data["sha256"], "3"))
        left = [e for e in self.entries() if " · 002 · " in e.split("\n", 1)[0]]
        self.assertEqual(left, ["## %s · 002 · strand · - · closed\nrolled_to: %s/log.md\nentries: 3 · sha256: %s\n\n"
                                % (mc.stamp("log"), S2, data["sha256"])])
        fields = self.fm(S2 + "/STRAND.md")
        self.assertEqual((fields["state"], fields["stage"], fields["closed"]), ("closed", "closed", mc.stamp("date")))
        changed = {rel for rel in set(before) | set(self.tree()) if before.get(rel) != self.tree().get(rel)}
        self.assertEqual({rel for rel in changed if not rel.startswith(".work/")},
                         {"CLIENT.md", "log.md", S2 + "/STRAND.md", S2 + "/log.md"})
        self.assertEqual(list((self.home / "archive").iterdir()), [])
        self.assertEqual(self.check()[0], 0)
        rolled.write_text(rolled.read_text(encoding="utf-8").replace("· k1", "· k9"), encoding="utf-8")
        self.assertIn((S2 + "/log.md", "sha256"), self.check()[1])

    def test_C74_C75_C76_C77_close_refusals(self):
        self.assertEqual(self.refused("strand", "close", "--strand", "001"),
                         {(".work/lock.json", "strand"), (V1 + "/version.md", "close_reason")})
        mc.lease_release(self.root, 2, LABEL)
        self.assertEqual(self.refused("strand", "close", "--strand", "001"), {(V1 + "/version.md", "close_reason")})
        for state in ("building", "fixing"):
            self.edit_fm(V1 + "/version.md", state=state, close_reason="the client stopped the work")
            self.assertEqual(self.refused("strand", "close", "--strand", "001"), {(V1 + "/version.md", "state")})
        self.ok("strand", "pause", "--strand", "002", "--reason", "r")
        self.assertEqual(self.refused("strand", "close", "--strand", "002"), {(S2 + "/STRAND.md", "state")})
        self.assertFalse((self.root / S1 / "log.md").exists() or (self.root / S2 / "log.md").exists())

    def test_C79_C80_C81_summary_plan_then_apply(self):
        plan = self.ok("strand", "summary", "--strand", "002", "--plan", self.stage(summary_draft()))
        self.assertEqual(plan["plan"], ".work/strands/002-timber-orders/summary-plan.md")
        self.assertEqual(self.refused("strand", "summary", "--strand", "002", "--apply", "0" * 64),
                         {(plan["plan"], "sha256")})
        data = self.ok("strand", "summary", "--strand", "002", "--apply", plan["sha256"])
        text = mc.read_text(self.root / S2 / "SUMMARY.md")
        fields = mc.front_matter(text)
        self.assertLessEqual(len(text.splitlines()), 80)
        self.assertEqual(fields, {"schema": "summary/1", "strand": "002", "title": "Timber orders", "kind": "platform",
                                  "versions": "none", "closed": "none", "summary_current_to": "none", "budget_lines": "80"})
        self.assertEqual(re.findall(r"(?m)^## (.+)$", text), list(NINE))
        self.assertEqual((data["summary_current_to"], self.fm(S2 + "/STRAND.md")["summary_current_to"]), ("none", "none"))
        self.assertEqual(self.entries()[0].split("\n", 1)[0], "## %s · 002 · summary · - · written" % mc.stamp("log"))
        self.assertEqual(self.check()[0], 0)
        self.assertEqual(self.refused("strand", "summary", "--strand", "002", "--plan", self.stage(summary_draft(extra=60))),
                         {(S2 + "/SUMMARY.md", "budget_lines")})
        missing = self.stage(summary_draft().replace("## Dates", "## When"))
        self.assertEqual(self.refused("strand", "summary", "--strand", "002", "--plan", missing),
                         {(S2 + "/SUMMARY.md", "headings")})
        self.ok("strand", "kind", "--strand", "002", "--kind", "non-platform", "--reason", "r")
        self.assertEqual(self.refused("strand", "summary", "--strand", "002", "--plan", self.stage(summary_draft())),
                         {(S2 + "/SUMMARY.md", "What was built")})
        self.ok("strand", "summary", "--strand", "002", "--plan",
                self.stage(summary_draft("Nothing built inside the product; the hand-off is pending.")))


class CheckTest(Base):

    def test_C125_C126_binding_mismatches_block(self):
        self.edit_fm("CLIENT.md", monday_account_id="10000002")
        self.assertIn(("CLIENT.md", "monday_account_id"), self.check()[1])
        self.edit_fm("CLIENT.md", monday_account_id="10000001", build_target="client-account")
        self.assertIn(("CLIENT.md", "build_target"), self.check()[1])
        self.edit_fm("CLIENT.md", build_target="own-account")
        self.edit_json(S1 + "/solution/build.json", lambda b: b.update(account_id_at_bind="10000002"))
        self.assertEqual(self.check()[1], {(S1 + "/solution/build.json", "account_id_at_bind")})

    def test_C127_G27_required_files_warn_and_block_at_release(self):
        (self.root / V1 / "audit.md").unlink()
        code, blocking, warnings = self.check()  # STRAND.md's link to the audit now dangles too
        self.assertEqual((code, blocking), (2, set()))
        self.assertIn((V1 + "/audit.md", "audited"), warnings)
        self.edit_fm(V1 + "/version.md", state="released", released="2026-11-05")
        blocking = self.check()[1]
        self.assertEqual({field for _, field in blocking}, {"audited", "released"})
        self.assertEqual({file for file, _ in blocking}, {V1 + "/" + name for name in ("audit.md", "build.json",
                                                                                       "backlog.md", "log.md")})

    def fresh_client(self):
        """The fixture's client folder as it was copied, for a test that changes it once per case."""
        shutil.rmtree(self.root)
        shutil.copytree(FIXTURES / "home" / "clients" / "larkmoor-joinery", self.root, ignore=IGNORE)

    def put_version_in(self, state):
        self.edit_fm(V1 + "/version.md", state=state)
        self.edit_fm(S1 + "/STRAND.md", version_state=state)

    def test_C127_G27_every_state_row_warns_for_a_missing_file_and_blocks_at_release(self):
        """One required item removed per row, for the five rows the audited and released test leaves out. A row warns
        in its own state; the rows a released version has passed through (planned, approved, built) block at release;
        building and fixing are checked only while current (G27), so at release the one removal that still shows,
        the audit, is blocked by the audited row."""
        running = {"id": "run-2026-11-05-1", "version": "v0.1", "kind": "build", "state": "running", "lease_epoch": 2,
                   "another_build_running": "no, answered 14:06", "started_at": "2026-11-05T14:06:00Z"}

        def unlink(rel):
            return lambda: (self.root / rel).unlink()

        def start_run():
            self.edit_json(S1 + "/solution/build.json", lambda build: build["runs"].append(running))

        def drop_build_heading():
            path = self.root / V1 / "version.md"
            path.write_text(path.read_text(encoding="utf-8").replace("## Build\n", "## Built\n"), encoding="utf-8")
        # (state, before the removal, the removal, the file the row names, the row, the row at release or None)
        cases = (("planned", None, unlink(S1 + "/solution/blueprint.md"), S1 + "/solution/blueprint.md", "planned", "planned"),
                 ("approved", None, unlink(V1 + "/blueprint-r1.md"), V1 + "/blueprint-r1.md", "approved", "approved"),
                 ("building", start_run, unlink(S1 + "/solution/build.json"), S1 + "/solution/build.json", "building", None),
                 ("built", None, drop_build_heading, V1 + "/version.md", "built", "built"),
                 ("fixing", None, unlink(V1 + "/audit.md"), V1 + "/audit.md", "fixing", "audited"))
        for state, before, remove, file, row, at_release in cases:
            with self.subTest(state=state):
                self.fresh_client()
                if before:
                    before()
                self.put_version_in(state)
                found = self.run_record("check")[1]
                self.assertEqual([f for f in found["blocking"] + found["warnings"] if f["field"] == row], [])
                remove()
                code, blocking, warnings = self.check()
                self.assertEqual((code, (file, row) in warnings, (file, row) in blocking), (1 if blocking else 2, True, False))
                self.assertEqual({field for _, field in blocking} - {"reference"}, set())  # a gone file may leave a reference
                self.put_version_in("released")
                blocking, warnings = self.check()[1:]
                self.assertEqual((file, at_release) in blocking, at_release is not None)
                if at_release != row:  # a row checked only while current is silent once the version is released
                    self.assertNotIn((file, row), blocking | warnings)

    def test_C128_G06_index_against_the_folders(self):
        (self.root / "strands" / "003-extra").mkdir()
        self.assertTrue({("CLIENT.md", "strand index"), ("CLIENT.md", "strands_total"),
                         ("strands/003-extra/STRAND.md", "schema")} <= self.check()[1])
        (self.root / "strands" / "003-extra").rmdir()
        client = self.root / "CLIENT.md"
        text = client.read_text(encoding="utf-8")
        client.write_text(re.sub(r"(?m)^\| 002 .*\n", "", text), encoding="utf-8")
        self.assertEqual(self.check()[1], {("CLIENT.md", "strand index")})
        client.write_text(text.replace("| Timber orders |", "| Timber order book |"), encoding="utf-8")
        self.assertEqual(self.check(), (2, set(), {("CLIENT.md", "strand index")}))

    def test_C129_C130_references_and_the_live_map(self):
        self.append("live/live-map.md", "| 001:B9 | 60000009 | view | 001/v0.1 | active | free | the user | none | 2026-10-28 |\n")
        self.assertEqual(self.check()[1], {("live/live-map.md", "reference"), ("live/live-map.md", "001:B9")})
        self.edit_json("account.json", lambda a: a["live_objects"].pop("001:B1.V1"))
        self.assertIn(("live/live-map.md", "001:B1.V1"), self.check()[1])
        self.append(S2 + "/STRAND.md", "\nCompare 001/v0.3 and 001/v0.1r7.\n")
        found = self.run_record("check")[1]["blocking"]
        self.assertTrue({"001/v0.3 does not resolve", "001/v0.1r7 does not resolve"} <= {f["problem"] for f in found})

    def test_C129_the_ledger_form_resolves_its_revision_half(self):
        """`v0.1r4#B1` inside a strand's build.json: the revision half must be a frozen blueprint of that version. The
        #KEY half is not checked here: no source says where a blueprint's element keys are listed, so DECISIONS owes it
        to WP3's ledger.py, which owns element keys."""
        build = S1 + "/solution/build.json"
        for ref in ("v0.1r9#B1", "v0.7r1#B1"):
            self.edit_json(build, lambda b: b["objects"]["B1"].update(blueprint_ref=ref))
            found = self.run_record("check")[1]["blocking"]
            self.assertEqual([(f["file"], f["field"], f["problem"]) for f in found],
                             [(build, "reference", "%s does not resolve" % ref.split("#")[0])])
        self.edit_json(build, lambda b: b["objects"]["B1"].update(blueprint_ref="v0.1r1#B1"))
        self.assertEqual(self.run_record("check")[1], {"ok": True, "command": "check", "blocking": [], "warnings": []})

    def test_C131_lease_mirrors_against_the_lock(self):
        self.edit_fm("CLIENT.md", lease="none")
        self.assertEqual(self.check()[1], {("CLIENT.md", "lease")})
        self.edit_fm("CLIENT.md", lease="001 v0.1 (%s)" % LABEL)
        self.edit_json("account.json", lambda a: a["guard_index"]["lease"].update(epoch=3))
        self.assertEqual(self.check()[1], {("account.json", "guard_index.lease")})

    def test_C132_C133_non_platform_and_the_hand_off_sentence(self):
        self.ok("strand", "kind", "--strand", "002", "--kind", "non-platform", "--reason", "r")
        self.append(S2 + "/solution/blueprint.md", '---\nschema: "blueprint/1"\n---\nInternal: never client-facing\n')
        self.assertEqual(self.check()[1], {(S2 + "/solution/blueprint.md", "kind")})
        (self.root / S2 / "solution" / "blueprint.md").unlink()
        scope = '---\nschema: "scope/1"\nstrand: "002"\n---\nInternal: never client-facing\n\n## Next steps\n\nCall back.\n'
        self.append(S2 + "/solution/scope.md", scope)
        self.assertEqual(self.check()[1], {(S2 + "/solution/scope.md", "hand-off")})
        sentence = self.rec.HANDOFF.replace("product. ", "product.\n> ")
        (self.root / S2 / "solution" / "scope.md").write_text(scope + "\n## Hand-off\n\n> " + sentence + "\n", encoding="utf-8")
        self.assertEqual(self.check()[:2], (0, set()))

    def test_C134_C135_C136_clearance_and_exclusions(self):
        for value in ("ready", "build", "not-yet"):
            self.edit_fm(S1 + "/readiness.md", clearance=value)
            self.assertEqual(self.check()[1], {(S1 + "/readiness.md", "clearance")}, value)
        self.edit_fm(S1 + "/readiness.md", clearance="not yet")
        self.assertEqual(self.check(), (2, set(), {(S1 + "/readiness.md", "clearance")}))
        self.edit_fm(S1 + "/readiness.md", clearance="cleared to build")
        (self.root / S1 / "solution" / "exclusions.md").unlink()
        self.assertEqual(self.check()[1], {(S1 + "/solution/exclusions.md", "sample_rows")})

    def test_C138_C139_C140_budgets(self):
        self.append(S2 + "/STRAND.md", "line\n" * 120)
        self.assertEqual(self.check(), (2, set(), {(S2 + "/STRAND.md", "budget")}))
        self.append(S2 + "/SUMMARY.md", '---\nschema: "summary/1"\n---\nInternal: never client-facing\n' + "line\n" * 118)
        self.assertIn((S2 + "/SUMMARY.md", "budget"), self.check()[1])
        (self.root / S2 / "SUMMARY.md").unlink()
        self.append("live/live-map.md", "\n" * 400)
        self.assertEqual(self.check()[1], {("live/live-map.md", "budget")})
        (self.root / "live" / "live-map.md").write_bytes((FIXTURES / "home" / "clients" / "larkmoor-joinery" / "live" /
                                                          "live-map.md").read_bytes())
        (self.root / S2 / "solution" / "export.bin").write_bytes(b"\0" * (4 * 1024 * 1024 + 1))
        found = self.run_record("check")[1]["warnings"]
        self.assertIn("002-timber-orders 4.0 MB", [f["problem"] for f in found if f["field"] == "size"][0])

    def test_C141_C142_C144_C147_A11_fields_block_only_at_their_moment(self):
        for field, values in (("transcripts_at_close", ("unanswered", "exclude", "archive")),
                              ("transcript_redaction", ("unanswered", "none", "offered-per-call", "always")),
                              ("sample_data_in_account", ("unanswered", "allowed", "not-allowed", "not-needed"))):
            for value in values:
                self.edit_fm("CLIENT.md", **{field: value})
                self.assertEqual(self.check()[0], 0, value)
            self.edit_fm("CLIENT.md", **{field: "maybe"})
            self.assertEqual(self.check()[1], {("CLIENT.md", field)})
            self.edit_fm("CLIENT.md", **{field: "unanswered"})
        self.edit_fm("CLIENT.md", account_kind="client", build_target="client-account")
        self.edit_json("account.json", lambda a: a["account"].update(kind="client", build_target="client-account"))
        self.assertEqual(self.check()[1], {("CLIENT.md", "sample_data_in_account")})
        self.edit_fm(S1 + "/solution/blueprint.md", sample_rows="none")
        self.assertEqual(self.check()[:2], (0, set()))
        self.edit_fm("CLIENT.md", account_kind="sandbox", build_target="none")
        self.edit_json("account.json", lambda a: a["account"].update(kind="sandbox", build_target="none"))
        self.assertEqual(self.check()[1], {("local/sandbox-accounts.txt", "sandbox")})
        (self.home / "local" / "sandbox-accounts.txt").write_text(
            "# kind | account_id | account_slug | workspace_id | label | note\n"
            "sandbox | 10000009 | example-sandbox | * | probes | fictional\n", encoding="utf-8")
        self.assertEqual(self.check()[:2], (0, set()))

    def test_C148_C149_G47_guard_index(self):
        self.edit_json("account.json", lambda a: a["guard_index"]["build_targets_by_strand"]["001"]["workspace_ids"].append(
            "40000099"))
        found = self.run_record("check")[1]["blocking"]
        self.assertEqual([(f["field"], "40000099" in f["problem"], "001" in f["problem"]) for f in found],
                         [("guard_index.build_targets_by_strand", True, True)])
        self.edit_json("account.json", lambda a: a["guard_index"]["build_targets_by_strand"]["001"].update(
            workspace_ids=["40000001"]))
        self.now = CLOCK + timedelta(days=14)
        self.assertEqual(self.check(), (2, set(), {("account.json", "guard_index.captured_at"),
                                                   (".work/lock.json", "heartbeat_at")}))

    def test_C150_C151_raw_inputs_and_frozen_blueprints_are_never_edited(self):
        self.append(TRANSCRIPT, "[00:03:00] Owner: one more line.\n")
        self.append(V1 + "/blueprint-r1.md", "\nA late edit.\n")
        self.append("inputs/stray.txt", "never saved through record.py\n")
        self.assertEqual(self.check()[1], {(TRANSCRIPT, "sha256"), (V1 + "/blueprint-r1.md", "sha256"),
                                           ("inputs/stray.txt", "sha256")})

    def test_C152_C155_absolute_paths_in_either_spelling_and_links(self):
        """Windows run: both spellings are reported alike on both systems."""
        self.append(S2 + "/STRAND.md", "Notes at D:\\work\\orders.md and at /home/someone/orders.md.\n"
                    "See [the plan](/strands/plan.md) and [gone](missing.md).\n")
        code, data = self.run_record("check")
        self.assertEqual(sorted(f["problem"] for f in data["blocking"]), [
            "a link that is not relative: /strands/plan.md", "an absolute path /home/someone",
            "an absolute path D:\\"])
        self.assertEqual([(f["field"], f["problem"]) for f in data["warnings"]],
                         [("line %d" % len(mc.read_text(self.root / S2 / "STRAND.md").splitlines()),
                           "the link missing.md does not resolve")])

    def test_C153_G48_a_stale_lease_is_a_warning(self):
        for minute, expected in ((20, set()), (21, {(".work/lock.json", "heartbeat_at")})):
            self.now = datetime(2026, 11, 5, 15, minute, tzinfo=timezone.utc)
            self.assertEqual(self.check(), (2 if expected else 0, set(), expected))
        warning = self.run_record("check")[1]["warnings"][0]
        self.assertEqual((warning["problem"], warning["expected"]), (
            "held by 001 (Job tracking) v0.1, session %s, heartbeat 61 minutes old: stale" % LABEL,
            "resume the holder in a fresh session, or break the lease"))

    def test_C12_C154_G15_G16_G17_front_matter_schema_and_values(self):
        client = self.root / "CLIENT.md"
        text = client.read_text(encoding="utf-8")
        client.write_text(text.replace('monday_tier: "standard"', "monday_tier: standard"), encoding="utf-8")
        self.assertEqual(self.check()[1], {("CLIENT.md", "monday_tier")})
        client.write_text(text.replace('ai_notice: "not-yet"', 'ai_notice: "later"\npage_size: "a4"'), encoding="utf-8")
        self.assertEqual(self.check()[1:], ({("CLIENT.md", "ai_notice")}, {("CLIENT.md", "page_size")}))
        client.write_text(text, encoding="utf-8")
        self.edit_fm(S2 + "/readiness.md", schema="readiness")
        self.edit_fm(S2 + "/STRAND.md", stage="demo")
        self.edit_fm(S1 + "/STRAND.md", version_state="built")
        code, blocking, warnings = self.check()
        self.assertEqual(blocking, {(S2 + "/readiness.md", "schema"), (S2 + "/STRAND.md", "stage")})
        self.assertEqual(warnings, {(V1 + "/version.md", "state"), ("CLIENT.md", "strand index")})

    def test_C156_C157_G61_markers_drafts_and_the_internal_line(self):
        self.append(S2 + "/drafts/2026-11-05-admin-prerequisites.md",
                    '---\nschema: "admin-prerequisites/1"\n---\nPlease grant access to 001:B1 as discussed [Q].\n')
        self.append(S1 + "/readiness.md", "- P2 [Q] \"It is always the timber.\" the owner\n")
        (self.root / S2 / "STRAND.md").write_text(mc.read_text(self.root / S2 / "STRAND.md").replace(
            "Internal: never client-facing\n", ""), encoding="utf-8")
        code, blocking, warnings = self.check()
        self.assertEqual(blocking, {(S2 + "/drafts/2026-11-05-admin-prerequisites.md", "line 4")})
        self.assertEqual(warnings, {(S1 + "/readiness.md", "line %d" % len(mc.read_text(self.root / S1 / "readiness.md")
                                                                         .splitlines())), (S2 + "/STRAND.md", "Internal")})

    def test_G34_settings_shape(self):
        path = self.home / "local" / "settings.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("default_build_account")
        data["github_account"] = "example-handle"
        path.write_text(mc.json_text(data), encoding="utf-8")
        self.assertEqual(self.check(), (2, set(), {("local/settings.json", "default_build_account"),
                                                   ("local/settings.json", "github_account")}))


class StatusTest(Base):

    def test_C114_C115_C116_C117_C123_C124_status_on_the_fixture(self):
        before = self.tree()
        code, status = self.run_record("status", "--json")
        self.assertEqual(self.tree(), before)
        self.assertEqual((code, list(status)), (0, ["schema", "generated_at", "plugin_version", "record_schema",
                                                     "schema_newer", "record", "strands", "lease", "interrupted", "findings"]))
        self.assertEqual((status["generated_at"], status["plugin_version"], status["schema_newer"]),
                         ("2026-11-05T14:30:00Z", "0.1.0", False))
        self.assertEqual(status["record"], self.fm("CLIENT.md"))
        first, second = status["strands"]
        self.assertEqual({k: first[k] for k in first if k not in self.fm(S1 + "/STRAND.md")},
                         {"qualified_version": "001/v0.1", "purpose": "proof-of-concept", "shown": ["2026-11-03"],
                          "signed_off": None, "open_versions": ["v0.1"], "live_objects": 3, "last_activity": "2026-11-05",
                          "run": None})
        self.assertEqual({k: second[k] for k in ("qualified_version", "purpose", "shown", "open_versions", "live_objects",
                                                 "last_activity", "stage", "clearance", "version", "version_state")},
                         {"qualified_version": None, "purpose": None, "shown": [], "open_versions": [], "live_objects": 0,
                          "last_activity": "2026-10-23", "stage": "intake", "clearance": "none", "version": "none",
                          "version_state": "none"})
        self.assertEqual({k: status["lease"][k] for k in ("held", "epoch", "heartbeat_age_minutes", "fresh")},
                         {"held": True, "epoch": 2, "heartbeat_age_minutes": 10, "fresh": True})
        self.assertEqual((status["interrupted"], status["findings"]), ([], {"blocking": [], "warnings": []}))

    def test_C118_C119_C121_runs_and_the_lease_block(self):
        running = {"id": "run-2026-11-05-1", "version": "v0.1", "state": "running", "heartbeat_at": "2026-11-05T14:26:00Z"}
        stuck = {"id": "run-2026-11-04-1", "version": "v0.1", "state": "interrupted"}
        self.edit_json(S1 + "/solution/build.json", lambda b: b["runs"].extend([stuck, running]))
        status = self.run_record("status")[1]
        self.assertEqual(status["strands"][0]["run"], {"id": "run-2026-11-05-1", "state": "running",
                                                       "heartbeat_at": "2026-11-05T14:26:00Z", "heartbeat_age_minutes": 4})
        self.assertEqual(status["interrupted"], [{"strand": "001", "run_id": "run-2026-11-04-1", "version": "v0.1"}])
        mc.lease_release(self.root, 2, LABEL)
        lease = self.run_record("status")[1]["lease"]
        self.assertEqual((lease["held"], lease["state"], lease["epoch"], lease["strand"], lease["fresh"]),
                         (False, "released", 2, None, None))

    def test_C120_C122_one_strand_and_the_findings_of_check(self):
        self.assertEqual([s["strand"] for s in self.run_record("status", "--strand", "002")[1]["strands"]], ["002"])
        self.assertEqual(self.refused("status", "--strand", "009"), {("strands/", "strand")})
        self.edit_fm("CLIENT.md", lease="none")
        self.edit_fm(S2 + "/STRAND.md", title="Timber order book")
        check = self.run_record("check")[1]
        self.assertEqual(self.run_record("status", "--json")[1]["findings"],
                         {"blocking": check["blocking"], "warnings": check["warnings"]})


if __name__ == "__main__":
    unittest.main()
