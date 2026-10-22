"""Unit tests for plugins/monday-master-builder/scripts/mmb_common.py (WP2, contract clauses by name).

Each test works on a copy of tests/unit/fixtures/home/ in a temporary folder whose name holds a space,
with MMB_HOME pointed at it, HOME and USERPROFILE at an empty canary folder and the clock pinned to the
fixture's reference time; tearDown asserts the canary and the real default home are untouched (C17).
The Windows side is simulated with PureWindowsPath, CRLF copies and a patched Path.home(); tests whose
docstring says "Windows run" must be repeated on a real Windows machine (C04).
"""
import ast, contextlib, hashlib, importlib.util, json, os, random, re, shutil, subprocess, sys, tempfile  # noqa: E401
import errno, threading, time, unittest  # noqa: E401
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest import mock

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPTS = HERE.parent.parent / "plugins" / "monday-master-builder" / "scripts"
sys.dont_write_bytecode = True  # nothing cached beside the scripts (G49)
sys.path.insert(0, str(SCRIPTS))
import mmb_common as mc  # noqa: E402

REAL_HOME, CLOCK, STALE = Path.home(), datetime(2026, 11, 5, 14, 30, tzinfo=timezone.utc), timedelta(minutes=90)
LABEL, RUN, IGNORE = "20261105-1405-r2d6", "run-2026-11-05-1", shutil.ignore_patterns(".gitkeep", ".DS_Store")
STRAND_002 = "strands/002-timber-orders/STRAND.md"


def is_stdlib(name):
    names = getattr(sys, "stdlib_module_names", None)  # Python 3.10 and later
    if names is not None or name in ("msvcrt", "fcntl"):  # each exists on one system only
        return names is None or name in names
    spec = importlib.util.find_spec(name)
    return spec is not None and "site-packages" not in str(spec.origin)


def tree(root):
    """{record-relative path: sha256} of every file but the mutex, which a first hold creates."""
    return {p.relative_to(root).as_posix(): mc.sha256_file(p) for p in root.rglob("*")
            if p.is_file() and p.name != "record.mutex"}


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mmb common "))
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

    def json(self, rel, root=None):
        return json.loads(((root or self.root) / rel).read_text(encoding="utf-8"))

    def fm(self, rel):
        return mc.front_matter(mc.read_text(self.root / rel))

    def edit_fm(self, rel, **updates):
        path = self.root / rel
        path.write_bytes(mc.set_front_matter(mc.read_text(path), updates).encode("utf-8"))

    def edit_json(self, rel, change):
        data = self.json(rel)
        change(data)
        (self.root / rel).write_text(mc.json_text(data), encoding="utf-8")

    def add_run(self, at="2026-11-05T15:50:00Z", classes=None):
        """Lock run_id RUN, and that run interrupted in 001's ledger with a classify-only reconcile."""
        self.edit_json(".work/lock.json", lambda lock: lock.update(run_id=RUN))
        run = {"id": RUN, "state": "interrupted", "reconcile": {"at": at, "mode": "classify-only",
                                                                "classes": classes or {"adopt": 1}}}
        self.edit_json("strands/001-job-tracking/solution/build.json",
                       lambda b: b.update(runs=[r for r in b["runs"] if r["id"] != RUN] + [run]))

    def open_002(self, **updates):
        """Strand 002 on v0.1 with its version.md, as `version open` leaves it, and any other STRAND.md updates."""
        (self.root / "strands/002-timber-orders/versions/v0.1").mkdir(parents=True)
        (self.root / "strands/002-timber-orders/versions/v0.1/version.md").write_text(
            '---\nschema: "version/1"\nstrand: "002"\nversion: "v0.1"\nstate: "planned"\n---\n', encoding="utf-8")
        self.edit_fm(STRAND_002, version="v0.1", **updates)

    def refused(self, call, *args, **kwargs):
        with self.assertRaises(mc.Refusal) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, 1)
        return caught.exception

    def fields(self, call, *args, **kwargs):
        return [finding["field"] for finding in self.refused(call, *args, **kwargs).findings]

    def breaking(self, **changes):
        args = dict(epoch=2, session_label=LABEL, for_strand="002", user_yes="yes, break the lease of 001",
                    account_id="10000001", choice="resume")
        args.update(changes)
        return args

    def assert_mirrors(self, root=None):
        """C83, C84, C85: the lock exists, its state is one of four, and both mirrors agree with it."""
        root, lock = root or self.root, self.json(".work/lock.json", root)
        self.assertIn(lock["state"], ("none", "held", "released", "broken"))
        line = "%s %s (%s)" % (lock["strand"], lock["version"], lock["session_label"]) \
            if lock["state"] == "held" else "none"
        self.assertEqual(mc.front_matter(mc.read_text(root / "CLIENT.md"))["lease"], line)
        self.assertEqual(self.json("account.json", root)["guard_index"]["lease"],
                         {key: lock[key] for key in ("strand", "epoch", "session_label", "heartbeat_at")})
        return lock


class RuntimeTest(Base):

    def test_C01_C02_standard_library_and_python_3_9_syntax(self):
        for path in (SCRIPTS / "mmb_common.py", Path(__file__)):
            module = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
            names = {a.name.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.Import) for a in n.names}
            names |= {n.module.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.ImportFrom)}
            for name in names - {"mmb_common"}:
                self.assertTrue(is_stdlib(name), "%s imports %s" % (path.name, name))

    def test_C05_C06_C15_C19_no_shell_no_delete_no_fixed_paths(self):
        source = (SCRIPTS / "mmb_common.py").read_text(encoding="utf-8")
        for pattern in (r"os\.system", r"shell\s*=", r"os\.popen", r"\bsubprocess\b",
                        r"os\.(rename|replace|remove|unlink|rmdir)\b", r"shutil\.(move|rmtree)",
                        r"\.(unlink|rename|rmdir)\(", r"expanduser", r"os\.sep", r'"~',
                        r'\+ *"(/|\\\\)"', r'"(/|\\\\)" *\+'):
            self.assertIsNone(re.search(pattern, source), pattern)
        for text in (source, Path(__file__).read_text(encoding="utf-8")):
            for needle in ("Del" + "Ops", "/" + "Users/", "C:" + "\\" + "Users", "Library" + "/"):
                self.assertNotIn(needle, text)

    def test_C18_C23_C24_G36_G49_library_in_a_plugin_copy(self):
        """A copied plugin root: the version is read from its plugin.json, nothing is written beside the
        scripts, and running the module directly does nothing (no subcommands)."""
        plugin = Path(shutil.copytree(FIXTURES / "plugin", self.tmp / "plugin copy"))
        (plugin / "scripts").mkdir(exist_ok=True)
        shutil.copy(SCRIPTS / "mmb_common.py", plugin / "scripts" / "mmb_common.py")
        manifest = plugin / ".claude-plugin" / "plugin.json"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace('"0.1.0"', '"9.8.7"'), encoding="utf-8")
        before = sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*"))
        # Without PYTHONDONTWRITEBYTECODE, to prove the first statement of G49 alone keeps the folder clean. The
        # macOS system Python caches its own standard library under HOME before any plugin code runs, so the
        # interpreter gets a home of its own here rather than the canary.
        env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
        env["HOME"] = env["USERPROFILE"] = str(self.tmp / "interpreter home")
        code = ("import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); import mmb_common; "
                "print(mmb_common.plugin_version()); print(mmb_common.PLUGIN_ROOT)")
        out = subprocess.run([sys.executable, "-c", code, str(plugin / "scripts")], env=env, capture_output=True,
                             text=True, check=True).stdout.splitlines()
        self.assertEqual((out[0], Path(out[1])), ("9.8.7", plugin.resolve()))
        bare = subprocess.run([sys.executable, str(plugin / "scripts" / "mmb_common.py")], env=env,
                              capture_output=True, text=True)
        self.assertEqual((bare.returncode, bare.stdout, bare.stderr), (0, "", ""))
        self.assertEqual(sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*")), before)
        self.assertTrue(sys.dont_write_bytecode)
        with self.assertRaises(mc.CannotRun) as caught:
            mc.plugin_version(self.tmp)
        self.assertEqual((caught.exception.code, caught.exception.findings[0]["file"]), (3, "plugin.json"))
        for name in ("home", "read_settings", "record_path", "strand_dir", "read_text", "read_json", "sha256_file",
                     "sha256_text", "backup_file", "write_file", "guarded_write", "front_matter", "set_front_matter",
                     "split_front_matter", "record_mutex", "stamp", "lease_init", "lease_take", "lease_refresh",
                     "lease_release", "lease_break", "lease_status", "lease_fence"):
            self.assertTrue(callable(getattr(mc, name)), name)

    def test_C20_C21_errors_carry_four_parts_and_an_exit_code(self):
        (self.root / ".work" / "lock.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(mc.CannotRun) as caught:
            mc.lease_status(self.root)
        finding = caught.exception.findings[0]
        self.assertEqual((caught.exception.code, sorted(finding), finding["file"]),
                         (3, ["expected", "field", "file", "problem"], ".work/lock.json"))
        stale = self.refused(mc.guarded_write, self.root / "CLIENT.md", "x\n", self.root, "0" * 64).findings[0]
        self.assertEqual((stale["file"], stale["field"]), ("CLIENT.md", "sha256"))
        self.assertTrue(stale["problem"] and stale["expected"])

    def test_C21_every_library_error_names_all_four_parts_each_non_empty(self):
        """The three exit-3 sites of mmb_common that once left the field empty: an unreadable file, a file that is not
        JSON, and a mutex another writer holds; the lock's own errors are tested above."""
        binary, broken = self.root / "binary.json", self.root / "broken.json"
        binary.write_bytes(b"\xff\xfe not text")
        broken.write_text("{not json", encoding="utf-8")
        held, done = threading.Event(), threading.Event()

        def holder():
            with mc.record_mutex(self.root):
                held.set()
                done.wait(10)
        thread = threading.Thread(target=holder)
        thread.start()
        held.wait(10)

        def waiting():
            with mc.record_mutex(self.root, timeout=0.2):
                pass
        try:
            found = []
            for call, args in ((mc.read_text, (binary,)), (mc.read_json, (broken,)), (mc.read_json, (broken, "named.json")),
                               (waiting, ())):
                with self.assertRaises(mc.CannotRun) as caught:
                    call(*args)
                found.append((caught.exception.code, caught.exception.findings))
        finally:
            done.set()
            thread.join()
        for code, findings in found:
            self.assertEqual(code, 3)
            for finding in findings:
                self.assertEqual(sorted(finding), ["expected", "field", "file", "problem"])
                self.assertTrue(all(finding.values()), finding)
        self.assertEqual([(f[0]["file"], f[0]["field"]) for _, f in found], [
            ("binary.json", "(whole file)"), ("broken.json", "(whole file)"), ("named.json", "(whole file)"),
            (".work/record.mutex", "record.mutex")])


class PathTest(Base):

    def test_C16_C17_home_is_mmb_home_or_the_default(self):
        """Windows run: the default home, built from a patched Path.home() of either flavour."""
        self.assertEqual(mc.home(), self.home)
        self.assertEqual(mc.read_settings()["schema"], "settings/1")
        with mock.patch.dict(os.environ, {"MMB_HOME": ""}):
            self.assertEqual(mc.home(), self.canary / "monday-builder")
            del os.environ["MMB_HOME"]
            self.assertEqual(mc.home(), self.canary / "monday-builder")
            self.assertIsNone(mc.read_settings())
            with mock.patch.object(Path, "home", return_value=PureWindowsPath("C:/profiles/someone")):
                self.assertEqual(str(mc.home()), "C:\\profiles\\someone\\monday-builder")
        self.assertEqual(mc.HOME_FOLDERS, ("clients", "cards", "monday-knowledge", "sandbox", "archive", "local"))

    def test_C07_references_resolve_alike_under_both_flavours(self):
        """Windows run: the same record references, on the CRLF tree, under Windows and POSIX path rules."""
        shutil.copytree(FIXTURES / "crlf" / "home", self.home, dirs_exist_ok=True)
        refs = set()
        for path in self.root.rglob("*.md"):
            text, base = mc.read_text(path), path.parent.relative_to(self.root).as_posix()
            refs |= {(base, link) for link in re.findall(r"\]\(([^)\s#]+)\)", text) if "://" not in link}
            refs |= {("", ref) for ref in re.findall(r"^(?:path|frozen): (\S+)", text, re.M)}
        self.assertGreaterEqual(len(refs), 10)
        windows = PureWindowsPath("C:/data/mmb home/clients/larkmoor-joinery")
        posix = PurePosixPath("/data/mmb home/clients/larkmoor-joinery")
        for base, ref in sorted(refs):
            on_windows, on_posix = mc.record_path(windows, ref, base), mc.record_path(posix, ref, base)
            self.assertEqual(on_windows.relative_to(windows).as_posix(), on_posix.relative_to(posix).as_posix())
            self.assertTrue(mc.record_path(self.root, ref, base).is_file(), ref)
        for bad in ("/etc/hosts", "C:\\temp\\x.md", "../other-client/CLIENT.md"):
            self.assertEqual(self.fields(mc.record_path, posix, bad), ["path"])

    def test_G56_strand_dir_by_short_id(self):
        self.assertEqual(mc.strand_dir(self.root, "002").name, "002-timber-orders")
        for bad in ("003", "1", "00*"):
            self.assertEqual(self.fields(mc.strand_dir, self.root, bad), ["strand"])


class TextTest(Base):

    def test_C08_C10_either_line_ending_reads_alike(self):
        """Windows run: CRLF and LF copies of CLIENT.md and of a transcript read the same."""
        crlf = FIXTURES / "crlf" / "home" / "clients" / "larkmoor-joinery" / "CLIENT.md"
        self.assertIn(b"\r\n", crlf.read_bytes())
        lf_text, crlf_text = mc.read_text(self.root / "CLIENT.md"), mc.read_text(crlf)
        self.assertEqual(mc.split_front_matter(lf_text), mc.split_front_matter(crlf_text))
        self.assertEqual(mc.front_matter(crlf_text.replace("\n", "\r\n")), mc.front_matter(lf_text))
        source = self.root / "calls" / "2026-10-20-discovery.transcript.txt"
        copy = self.tmp / "crlf transcript.txt"
        copy.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(mc.read_text(copy), mc.read_text(source))
        self.assertEqual(len(mc.read_text(copy).splitlines()), len(mc.read_text(source).splitlines()))

    def test_C09_G11_written_text_has_one_line_ending(self):
        """Windows run: a CRLF CLIENT.md comes back LF after a lease write; LF whatever os.linesep says."""
        shutil.copytree(FIXTURES / "crlf" / "home", self.home, dirs_exist_ok=True)
        mc.lease_release(self.root, 2, LABEL)
        data = (self.root / "CLIENT.md").read_bytes()
        self.assertNotIn(b"\r", data)
        self.assertEqual(mc.split_front_matter(data.decode())[1],
                         mc.split_front_matter(mc.read_text(FIXTURES / "home" / "clients" / "larkmoor-joinery"
                                                            / "CLIENT.md"))[1])
        with mock.patch.object(os, "linesep", "\r\n"):
            mc.write_file(self.tmp / "note.md", "a\r\nb\nc ä\n", self.tmp)
        self.assertEqual((self.tmp / "note.md").read_bytes(), "a\nb\nc ä\n".encode("utf-8"))

    def test_C11_front_matter_round_trips_byte_for_byte(self):
        count = 0
        for path in sorted(self.root.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            fields = mc.front_matter(text, path.name)
            self.assertEqual(mc.set_front_matter(text, fields), text, path)
            count += 1
        self.assertGreaterEqual(count, 13)
        client = mc.read_text(self.root / "CLIENT.md")
        new = mc.set_front_matter(client, {"lease": "none", "extra_key": "x"})
        changed = [(a, b) for a, b in zip(client.split("\n"), new.split("\n")) if a != b]
        self.assertEqual([b.split(":")[0] for a, b in changed[:2]], ["lease", "updated"])
        self.assertIn('lease: "none"   # mirrors .work/lock.json', new)
        self.assertIn('updated: "%s"\nextra_key: "x"\n---\n' % mc.stamp("minute"), new)
        strand = mc.read_text(self.root / STRAND_002)
        self.assertEqual(mc.front_matter(strand)["opened_reason"],
                         'the 2026-10-21 email asked for "one place for timber orders"')
        odd = 'a "quoted" word, a back\\slash and # no comment'
        rewritten = mc.set_front_matter(strand, {"opened_reason": odd})
        self.assertEqual(mc.front_matter(rewritten)["opened_reason"], odd)
        self.assertIn('opened_reason: "a \\"quoted\\" word, a back\\\\slash and # no comment"', rewritten)

    def test_C12_G38_parse_errors_name_the_key(self):
        cases = (('---\nschema: "client/2"\nslug: x\n---\n', "slug"), ('---\nslug: "a"\nschema: "c/1"\n---\n', "slug"),
                 ('---\nschema: "c/1"\nk: "a"\nk: "b"\n---\n', "k"), ('---\nschema: "c/1"\n', "---"),
                 ('schema: "c/1"\n', "---"), ('---\n# a comment\n---\n', "schema"), ('---\nKey: "v"\n---\n', "Key"))
        for text, field in cases:
            with self.assertRaises(mc.FrontMatterError) as caught:
                mc.front_matter(text, "X.md")
            self.assertEqual((caught.exception.findings[0]["file"], caught.exception.findings[0]["field"]),
                             ("X.md", field))
        text = '---\nschema: "c/1"  # trailing comment\n\n   # a comment line\nk: "v"\n---\nbody\n'
        self.assertEqual(mc.split_front_matter(text), ({"schema": "c/1", "k": "v"}, "body\n"))
        self.assertEqual(self.fields(mc.set_front_matter, text, {"k": "two\nlines"}), ["k"])
        self.assertEqual(self.fields(mc.set_front_matter, text, {"Bad": "v"}), ["Bad"])

    def test_G57_newer_or_foreign_schema(self):
        for found, newer in (("client/2", False), ("client/1", False), ("client/3", True), ("strand/1", True),
                             ("client", True), ("", True)):
            self.assertEqual(mc.schema_newer(found, "client"), newer, found)
        self.assertEqual(self.refused(mc.require_schema, "lock/3", "lock", "x").findings[0]["expected"], "lock/2")

    def test_G08_G60_file_and_entry_hashes_match_the_record(self):
        log = (self.root / "log.md").read_text(encoding="utf-8")
        recorded = re.findall(r"^(?:path|frozen): (\S+)(?:\nsha256:| · sha256:) ([0-9a-f]{64})$", log, re.M)
        self.assertEqual(len(recorded), 3)
        for rel, sha in recorded:
            self.assertEqual(mc.sha256_file(mc.record_path(self.root, rel)), sha)
        entries = re.split(r"(?m)^(?=## \d{4}-)", log)[1:]
        self.assertEqual([mc.sha256_text(e) for e in entries], self.json(".work/history.json")["entries"])
        self.assertEqual(mc.sha256_text(entries[0].replace("\n", "\r\n") + "\n\n"), mc.sha256_text(entries[0]))

    def test_R39_one_slug_key_for_the_index_and_init(self):
        """The index key leak_lint.py writes and record.py init checks has one implementation, here."""
        self.assertEqual(mc.slug_key("brindle-tiles"), hashlib.sha256(b"s:brindle-tiles").hexdigest()[:32])
        self.assertEqual(mc.digest("n:", "østby freight"),
                         hashlib.sha256("n:østby freight".encode("utf-8")).hexdigest()[:32])
        lint = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        self.assertIn("\ndigest = mc.digest", lint)
        self.assertNotIn("def digest(", lint)
        self.assertNotIn('digest("s:"', lint)
        self.assertIn("mc.slug_key(", (SCRIPTS / "record.py").read_text(encoding="utf-8"))

    def test_R55_R54_a_key_written_twice_in_one_object_is_exit_3_naming_its_path(self):
        """The one strict JSON reader, which read_json and leak_lint.py share: a repeat at the top or nested stops."""
        path = self.tmp / "repeated.json"
        for text, field, key in (('{"schema": "settings/1", "archive": "github", "archive": "local"}', "$.archive<key>",
                                  "archive"),
                                 ('{"firm": {"name": "Fernhollow Supply", "name": "Østby Freight"}}',
                                  "$.firm.name<key>", "name"),
                                 ('{"runs": [{"id": "run-1"}, {"id": "run-2", "id": "run-3"}]}', "$.runs[1].id<key>",
                                  "id"),
                                 ('{"entries": {"0f": 1, "0f": 2}}', '$.entries["0f"]<key>', "0f")):
            with self.assertRaises(mc.RepeatedKey) as caught:
                mc.strict_json(text)
            self.assertEqual(caught.exception.args, (field, key), text)
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(mc.CannotRun) as caught:
                mc.read_json(path, "named.json")
            finding = caught.exception.findings[0]
            self.assertEqual((caught.exception.code, finding["file"], finding["field"]), (3, "named.json", field))
            self.assertIn('the key "%s" is written twice in one object' % key, finding["problem"])
            self.assertIn("each key written once", finding["expected"])
        clean = '{"name": "Blue Harbour", "firm": {"name": "Tallowmere", "renderings": [{"name": "x"}, {"name": "y"}]}}'
        path.write_text(clean, encoding="utf-8")
        self.assertEqual(mc.read_json(path), json.loads(clean))  # the same key at two depths and in two objects
        lint = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        self.assertNotIn("def strict_json(", lint)
        self.assertIn("mc.strict_json", lint)

    def test_G40_time_formats(self):
        local = CLOCK.astimezone()
        self.assertEqual((mc.stamp("utc"), mc.stamp("backup")), ("2026-11-05T14:30:00Z", "20261105T143000000000Z"))
        for kind, form in (("minute", "%Y-%m-%dT%H:%M"), ("log", "%Y-%m-%d %H:%M"), ("date", "%Y-%m-%d"),
                           ("label", "%Y%m%d-%H%M")):
            self.assertEqual(mc.stamp(kind), local.strftime(form))
        self.assertEqual(mc.parse_utc("2026-11-05T14:30:00Z"), CLOCK)
        self.assertEqual(mc.heartbeat_age("2026-11-05T14:20:00Z"), (10, False))


class WriteTest(Base):

    def test_C14_C15_G39_backup_then_overwrite_in_place(self):
        path = self.root / STRAND_002
        old, inode = path.read_bytes(), path.stat().st_ino
        mc.write_file(path, "new text\n", self.root)
        mc.write_file(path, "newer text\r\n", self.root)
        backups = sorted((self.root / ".work" / "backup" / "strands" / "002-timber-orders").iterdir())
        self.assertEqual([p.name for p in backups], ["STRAND.md.20261105T143000000000Z",
                                                     "STRAND.md.20261105T143000000000Z-2"])
        self.assertEqual([p.read_bytes() for p in backups], [old, b"new text\n"])
        self.assertEqual((path.read_bytes(), path.stat().st_ino), (b"newer text\n", inode))
        settings, local = self.home / "local" / "settings.json", self.home / "local"
        mc.write_file(settings, "{}\n", local, backup_dir=local / "backup")
        self.assertEqual(len(list((local / "backup").glob("settings.json.*"))), 1)

    def test_C15_no_write_path_renames_or_deletes(self):
        targets = ("os.rename", "os.replace", "os.remove", "os.unlink", "os.rmdir", "shutil.move", "shutil.rmtree",
                   "pathlib.Path.unlink", "pathlib.Path.rename", "pathlib.Path.replace", "pathlib.Path.rmdir")
        fresh = self.home / "clients" / "fresh"
        for name in ("CLIENT.md", "account.json"):
            (fresh / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(FIXTURES / "plugin" / "templates" / "record" / name, fresh / name)
        with contextlib.ExitStack() as stack:
            spies = [stack.enter_context(mock.patch(target)) for target in targets]
            mc.guarded_write(self.root / STRAND_002, "x\n", self.root, mc.sha256_file(self.root / STRAND_002))
            mc.lease_release(self.root, 2, LABEL)
            taken = mc.lease_take(self.root, "001")
            mc.lease_refresh(self.root, taken["epoch"], taken["session_label"])
            self.now = CLOCK + STALE
            mc.lease_break(self.root, **self.breaking(epoch=taken["epoch"], session_label=taken["session_label"]))
            mc.lease_init(fresh)
        self.assertEqual([spy.call_count for spy in spies], [0] * len(targets))

    def test_C45_C46_guarded_write_refuses_a_stale_sha(self):
        path = self.root / "CLIENT.md"
        read_sha, before = mc.sha256_file(path), path.read_bytes()
        path.write_bytes(before + b"\nA line another session added.\n")
        self.assertEqual(self.fields(mc.guarded_write, path, "mine\n", self.root, read_sha), ["sha256"])
        self.assertEqual(path.read_bytes(), before + b"\nA line another session added.\n")
        mc.guarded_write(path, "mine\n", self.root, mc.sha256_file(path))
        self.assertEqual(path.read_bytes(), b"mine\n")
        self.assertEqual(len(list((self.root / ".work" / "backup").glob("CLIENT.md.*"))), 1)
        mc.guarded_write(self.root / "new.md", "new\n", self.root, None)
        self.assertEqual(self.fields(mc.guarded_write, self.root / "new.md", "again\n", self.root, None), ["sha256"])

    def test_C52_G09_mutex_serialises_processes(self):
        """Windows run: the msvcrt branch of the mutex is only exercised there."""
        (self.root / "counter.txt").write_text("0", encoding="utf-8")
        worker = ("import sys, time; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]);"
                  " import mmb_common; from pathlib import Path; root = Path(sys.argv[2])\n"
                  "counter = root / 'counter.txt'\n"
                  "for _ in range(20):\n    with mmb_common.record_mutex(root):\n"
                  "        value = int(counter.read_text()); time.sleep(0.004); counter.write_text(str(value + 1))\n")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        workers = [subprocess.Popen([sys.executable, "-c", worker, str(SCRIPTS), str(self.root)], env=env)
                   for _ in range(4)]
        self.assertEqual([process.wait(60) for process in workers], [0] * 4)
        self.assertEqual((self.root / "counter.txt").read_text(encoding="utf-8"), "80")
        self.assertEqual((self.root / ".work" / "record.mutex").stat().st_size, 0)

    def test_G09_mutex_is_reentrant_and_times_out(self):
        held, done = threading.Event(), threading.Event()

        def holder():
            with mc.record_mutex(self.root):
                held.set()
                done.wait(10)
        thread = threading.Thread(target=holder)
        thread.start()
        held.wait(10)
        try:
            with self.assertRaises(mc.CannotRun) as caught:
                with mc.record_mutex(self.root, timeout=0.2):
                    pass
            self.assertEqual(caught.exception.code, 3)
        finally:
            done.set()
            thread.join()
        with mc.record_mutex(self.root):
            with mc.record_mutex(self.root):
                self.assertEqual(mc.lease_status(self.root)["epoch"], 2)

    def test_G09_mutex_reentry_through_a_second_spelling_does_not_wait(self):
        # The Windows harness found a self-wait when one folder was reached by two spellings (review item 10).
        # A real Windows run repeats this with a drive-letter case and an 8.3 name.
        alias = self.tmp / "alias"
        try:
            os.symlink(str(self.root), str(alias), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("no symbolic links here")
        with mc.record_mutex(self.root):
            with mc.record_mutex(alias, timeout=0.2):
                self.assertTrue((alias / ".work" / "record.mutex").exists())


class LeaseTest(Base):

    def test_C82_C83_C84_C85_mirrors_follow_every_primitive(self):
        self.assertEqual(self.assert_mirrors()["state"], "held")
        mc.lease_release(self.root, 2, LABEL)
        self.assertEqual(self.fm("CLIENT.md")["lease"], "none")
        self.assertIn('lease: "none"   # mirrors .work/lock.json', mc.read_text(self.root / "CLIENT.md"))
        self.assert_mirrors()
        taken = mc.lease_take(self.root, "001")
        self.assertEqual(self.fm("CLIENT.md")["lease"], "001 v0.1 (%s)" % taken["session_label"])
        self.assert_mirrors()
        self.now = CLOCK + timedelta(minutes=5)
        mc.lease_refresh(self.root, 3, taken["session_label"])
        self.assertEqual(self.assert_mirrors()["heartbeat_at"], "2026-11-05T14:35:00Z")
        self.now = CLOCK + STALE
        mc.lease_break(self.root, **self.breaking(epoch=3, session_label=taken["session_label"]))
        self.assertEqual(self.assert_mirrors()["state"], "broken")

    def test_C83_C88_C97_C98_first_lock_take_release_take(self):
        fresh = self.home / "clients" / "fresh"
        shutil.copytree(self.root / "strands" / "001-job-tracking", fresh / "strands" / "001-job-tracking")
        for name in ("CLIENT.md", "account.json"):
            shutil.copy(FIXTURES / "plugin" / "templates" / "record" / name, fresh / name)
        before = tree(fresh)
        mc.lease_init(fresh)
        lock = self.assert_mirrors(fresh)
        self.assertEqual((lock["state"], lock["epoch"], lock["history"]), ("released", 0, []))
        self.assertEqual({k: v for k, v in tree(fresh).items() if k != ".work/lock.json"}, before)
        self.assertEqual(self.fields(mc.lease_init, fresh), ["state"])
        first = mc.lease_take(fresh, "001")
        mc.lease_release(fresh, first["epoch"], first["session_label"])
        lock = self.assert_mirrors(fresh)
        self.assertEqual((first["epoch"], lock["state"], lock["epoch"]), (1, "released", 1))
        self.assertEqual([e["event"] for e in lock["history"]], ["taken", "released"])
        self.assertEqual(lock["history"][1], {"event": "released", "at": "2026-11-05T14:30:00Z", "epoch": 1,
                                              "strand": "001", "version": "v0.1",
                                              "session_label": first["session_label"], "run_id": None,
                                              "by": first["session_label"], "choice": None, "reconcile": None,
                                              "note": None})
        self.assertEqual(self.fields(mc.lease_release, fresh, 1, first["session_label"]), ["session_label"])
        self.assertEqual(mc.lease_take(fresh, "001")["epoch"], 2)

    def test_C86_account_mirror_changes_only_its_block(self):
        before_text, before = (self.root / "account.json").read_text(encoding="utf-8"), self.json("account.json")
        mc.lease_release(self.root, 2, LABEL)
        after_text, after = (self.root / "account.json").read_text(encoding="utf-8"), self.json("account.json")
        self.assertEqual(after["guard_index"].pop("lease"),
                         {"strand": None, "epoch": 2, "session_label": None, "heartbeat_at": None})
        before["guard_index"].pop("lease")
        self.assertEqual(after, before)
        pairs = list(zip(before_text.splitlines(), after_text.splitlines()))
        self.assertEqual([a.split(":")[0].strip() for a, b in pairs if a != b],
                         ['"strand"', '"session_label"', '"heartbeat_at"'])
        self.assertEqual(len(list((self.root / ".work" / "backup").glob("account.json.*"))), 1)

    def test_C87_take_records_every_field(self):
        mc.lease_release(self.root, 2, LABEL)
        taken = mc.lease_take(self.root, "001")
        lock = self.json(".work/lock.json")
        self.assertEqual(list(lock), ["schema", "kind", "epoch", "strand", "strand_title", "version", "run_id",
                                      "session_label", "taken_at", "heartbeat_at", "state", "history"])
        self.assertEqual({k: lock[k] for k in ("kind", "epoch", "strand", "strand_title", "version", "run_id",
                                               "taken_at", "heartbeat_at", "state")},
                         {"kind": "build", "epoch": 3, "strand": "001", "strand_title": "Job tracking",
                          "version": "v0.1", "run_id": None, "taken_at": "2026-11-05T14:30:00Z",
                          "heartbeat_at": "2026-11-05T14:30:00Z", "state": "held"})
        self.assertEqual(taken, {"epoch": 3, "session_label": lock["session_label"], "strand": "001",
                                 "version": "v0.1", "taken_at": "2026-11-05T14:30:00Z"})
        self.assertEqual((lock["history"][-1]["event"], lock["history"][-1]["by"]), ("taken", taken["session_label"]))

    def test_C89_G01_labels_never_collide(self):
        mc.lease_release(self.root, 2, LABEL)
        draws, rng, labels = iter("a" * 12), random.Random(7), []
        with mock.patch.object(mc.secrets, "choice", side_effect=lambda chars: next(draws, None) or rng.choice(chars)):
            for _ in range(50):
                taken = mc.lease_take(self.root, "001")
                labels.append(taken["session_label"])
                mc.lease_release(self.root, taken["epoch"], taken["session_label"])
        self.assertEqual((len(set(labels)), labels[0][-4:]), (50, "aaaa"))
        for label in labels:
            self.assertRegex(label, r"^%s-[a-z0-9]{4}$" % mc.stamp("label"))
            self.assertRegex(label, r"^\d{8}-\d{4}-[a-z0-9]{4}$")

    def test_C90_C98_G53_only_the_holder_moves_the_lease(self):
        for call in (mc.lease_refresh, mc.lease_release):
            for label, epoch in ((None, 2), ("20261105-1405-zzzz", 2), (LABEL, 1)):
                self.assertEqual(self.fields(call, self.root, epoch, label), ["session_label"])
        self.now = CLOCK + STALE
        for label, epoch in ((None, 2), ("20261105-1405-zzzz", 2), (LABEL, 1)):
            self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(epoch=epoch, session_label=label)),
                             ["epoch"])
        mc.lease_release(self.root, 2, LABEL)
        for call in (mc.lease_refresh, mc.lease_release):
            self.assertEqual(self.fields(call, self.root, 2, LABEL), ["session_label"])
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking()), ["epoch"])

    def test_C91_G50_G53_take_follows_the_strand(self):
        self.assertEqual(self.fields(mc.lease_take, self.root, "002"), ["version", "state"])
        mc.lease_release(self.root, 2, LABEL)
        self.assertEqual(self.fields(mc.lease_take, self.root, "002"), ["version"])
        self.open_002(kind="non-platform")
        self.assertEqual(self.fields(mc.lease_take, self.root, "002"), ["kind"])
        self.edit_fm(STRAND_002, kind="hybrid", state="closed")
        self.assertEqual(self.fields(mc.lease_take, self.root, "002"), ["state"])
        self.edit_fm(STRAND_002, state="paused")  # paused by the user: refused since the lease fixes (finding 13)
        self.assertEqual(self.fields(mc.lease_take, self.root, "002"), ["state"])
        build = self.root / "strands/002-timber-orders/solution/build.json"
        build.write_text(mc.json_text({"schema": "build/2", "runs": [{"id": RUN, "state": "interrupted"}]}),
                         encoding="utf-8")
        self.assertEqual(mc.lease_take(self.root, "002")["strand"], "002")

    def test_C92_C93_C94_held_refusal_names_the_holder(self):
        for strand in ("002", "001"):
            problem, expected = [(f["problem"], f["expected"]) for f in
                                 self.refused(mc.lease_take, self.root, strand).findings if f["field"] == "state"][0]
            for part in ("strand 001 (Job tracking) v0.1", "session %s" % LABEL, "heartbeat 10 minutes old: fresh",
                         "Nothing local is blocked", "intake, the readiness check and a blueprint revision",
                         "the audit and the release of any strand are blocked"):
                self.assertIn(part, problem)
            for part in ("wait for the run to end", "record.py lease release", "break it if it is stale"):
                self.assertIn(part, expected)
            self.assertEqual("another session of this strand" in problem, strand == "001")
        self.now = CLOCK + STALE
        self.assertIn("100 minutes old: stale", self.refused(mc.lease_take, self.root, "001").findings[0]["problem"])

    def test_C95_stale_after_sixty_minutes(self):
        for minute, age, fresh in ((19, 59, True), (20, 60, True), (21, 61, False)):
            self.now = datetime(2026, 11, 5, 15, minute, tzinfo=timezone.utc)
            status = mc.lease_status(self.root)
            self.assertEqual((status["heartbeat_age_minutes"], status["fresh"], status["state"]), (age, fresh, "held"))

    def test_C96_G39_G50_refresh_moves_the_heartbeat_only(self):
        client, count = (self.root / "CLIENT.md").read_bytes(), len(self.json(".work/lock.json")["history"])
        self.now = CLOCK + timedelta(minutes=10)
        self.assertEqual(mc.lease_refresh(self.root, 2, LABEL)["heartbeat_at"], "2026-11-05T14:40:00Z")
        lock = self.assert_mirrors()
        self.assertEqual((lock["heartbeat_at"], len(lock["history"])), ("2026-11-05T14:40:00Z", count))
        self.assertEqual((self.root / "CLIENT.md").read_bytes(), client)
        self.assertFalse((self.root / ".work" / "backup").exists())
        self.assertEqual(mc.lease_refresh(self.root, 2, LABEL, RUN)["run_id"], RUN)
        self.assertEqual(mc.lease_refresh(self.root, 2, LABEL, RUN)["run_id"], RUN)
        self.assertEqual(self.fields(mc.lease_refresh, self.root, 2, LABEL, "run-2026-11-05-2"), ["run_id"])

    def test_C99_C118_status_block(self):
        status = mc.lease_status(self.root)
        self.assertEqual(list(status), ["held", "state", "epoch", "strand", "strand_title", "version", "session_label",
                                        "run_id", "taken_at", "heartbeat_at", "heartbeat_age_minutes", "fresh",
                                        "reserved_for"])
        self.assertEqual((status["held"], status["epoch"], status["heartbeat_age_minutes"], status["fresh"]),
                         (True, 2, 10, True))
        mc.lease_release(self.root, 2, LABEL)
        status = mc.lease_status(self.root)
        self.assertEqual((status["held"], status["state"], status["epoch"], status["strand"],
                          status["heartbeat_age_minutes"], status["fresh"]), (False, "released", 2, None, None, None))

    def test_C100_a_ledger_stand_in_uses_the_primitives(self):
        def ledger_write(epoch, label, run_id):
            ok, reason = mc.lease_fence(self.root, epoch, label, run_id)  # since the lease fixes it also refreshes
            return self.json(".work/lock.json") if ok else reason
        mc.lease_refresh(self.root, 2, LABEL, RUN)  # run start
        self.now = CLOCK + timedelta(minutes=5)
        self.assertEqual(ledger_write(2, LABEL, RUN)["heartbeat_at"], "2026-11-05T14:35:00Z")
        self.assertIn("run run-2026-11-05-2 is not the lock's %s" % RUN, ledger_write(2, LABEL, "run-2026-11-05-2"))
        mc.lease_release(self.root, 2, LABEL)
        self.assertIn("no lease is held (state released)", ledger_write(2, LABEL, RUN))

    def test_C101_to_C106_break_needs_all_five_conditions(self):
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking()), ["heartbeat_at"])
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(
            user_yes="clear the lock", account_id="10000002", choice=None)),
            ["heartbeat_at", "user_yes", "account.id", "choice"])
        self.now = CLOCK + STALE
        for changes, field in ((dict(user_yes="yes, clear the lock"), "user_yes"),
                               (dict(user_yes="yes 1001"), "user_yes"), (dict(account_id="10000002"), "account.id"),
                               (dict(choice="later"), "choice")):
            self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(**changes)), [field])
        self.edit_json(".work/lock.json", lambda lock: lock.update(run_id=RUN))
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking()), ["runs[].reconcile"])
        self.add_run(at="2026-11-05T14:10:00Z")
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking()), ["runs[].reconcile"])
        self.add_run()
        self.edit_json("account.json", lambda account: account["account"].update(id="unbound"))
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(account_id="unbound")), ["account.id"])
        self.edit_json("account.json", lambda account: account["account"].update(id="10000001"))
        result = mc.lease_break(self.root, **self.breaking(user_yes="yes, break 001-job-tracking"))
        self.assertEqual((result["reconcile"], result["holder"]["run_id"]), ({"adopt": 1}, RUN))

    def test_C107_park_needs_its_own_yes_and_no_duplicate_or_partial(self):
        self.now = CLOCK + STALE
        self.add_run(classes={"adopt": 2, "duplicate": 1, "partial": 0})
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(choice="park")),
                         ["park_yes", "reconcile"])
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(
            choice="park", park_yes="yes, park 001", for_strand="001")), ["reconcile", "for_strand"])
        mc.lease_break(self.root, **self.breaking(choice="resume"))  # resume stays open with duplicates

    def test_C110_C111_resume_break_then_the_holders_fresh_take(self):
        self.now = CLOCK + STALE
        result = mc.lease_break(self.root, **self.breaking())
        self.assertEqual((result["broken_epoch"], result["epoch"], result["choice"]), (2, 3, "resume"))
        lock = self.assert_mirrors()
        self.assertEqual((lock["state"], lock["epoch"], lock["strand"], lock["session_label"]),
                         ("broken", 3, None, None))
        entry = lock["history"][-1]
        self.assertEqual(entry, {"event": "broken", "at": "2026-11-05T16:00:00Z", "epoch": 2, "strand": "001",
                                 "version": "v0.1", "session_label": LABEL, "run_id": None, "by": None,
                                 "choice": "resume", "reconcile": {},
                                 "note": 'for 002: "yes, break the lease of 001"', "for_strand": "002"})
        taken = mc.lease_take(self.root, "001")
        self.assertEqual((taken["epoch"], taken["strand"]), (4, "001"))
        self.assertNotEqual(taken["session_label"], LABEL)

    def test_C112_park_break_then_the_takers_take(self):
        self.now = CLOCK + STALE
        self.add_run()
        mc.lease_break(self.root, **self.breaking(choice="park", park_yes="yes, park 001 for now"))
        history = self.json(".work/lock.json")["history"]
        self.assertEqual([(e["event"], e["choice"], e["epoch"]) for e in history[-2:]],
                         [("broken", "park", 2), ("parked", None, 2)])
        self.assertEqual(history[-1]["note"], 'for 002: "yes, park 001 for now"')
        self.open_002()
        taken = mc.lease_take(self.root, "002")
        self.assertEqual((taken["epoch"], self.assert_mirrors()["strand"]), (4, "002"))

    def test_C113_G51_fence_refuses_every_stale_triple(self):
        mc.lease_refresh(self.root, 2, LABEL, RUN)
        self.assertEqual(mc.lease_fence(self.root, 2, LABEL, RUN), (True, "ok"))
        self.now = CLOCK + STALE
        self.add_run()
        mc.lease_break(self.root, **self.breaking())
        taken = mc.lease_take(self.root, "001")
        new = taken["session_label"]
        mc.lease_refresh(self.root, 4, new, "run-2026-11-05-2")
        for epoch, label, run_id, reason in ((2, LABEL, None, "epoch 2 is not the lock's 4"),
                                             (4, LABEL, "run-2026-11-05-2", "session %s is not the holder's" % LABEL),
                                             (4, new, RUN, "run %s is not the lock's" % RUN)):
            ok, text = mc.lease_fence(self.root, epoch, label, run_id)
            self.assertFalse(ok)
            self.assertIn(reason, text)
        self.assertEqual(mc.lease_fence(self.root, 4, new, "run-2026-11-05-2"), (True, "ok"))

    def test_C13_G57_newer_schema_refuses_lease_writes_and_changes_nothing(self):
        for rel, schema in (("CLIENT.md", "client/3"), (".work/lock.json", "lock/3"), ("account.json", "account/2")):
            if rel.endswith(".md"):
                self.edit_fm(rel, schema=schema)
            else:
                self.edit_json(rel, lambda data: data.update(schema=schema))
            before = tree(self.root)
            for call, args in ((mc.lease_release, (2, LABEL)), (mc.lease_refresh, (2, LABEL)),
                               (mc.lease_take, ("001",))):
                refusal = self.refused(call, self.root, *args).findings[0]
                self.assertEqual((refusal["file"], refusal["field"]), (rel, "schema"))
            self.assertEqual(tree(self.root), before)
            if rel.endswith(".md"):
                self.edit_fm(rel, schema="client/2")
            else:
                self.edit_json(rel, lambda data: data.update(schema=schema[:-1] + str(int(schema[-1]) - 1)))


class LeaseFixTest(Base):
    """The fixes of the build-lease review: R<n> is the review's finding n."""

    def test_R1_C111_a_resume_break_keeps_the_lease_for_the_holders_strand(self):
        self.now = CLOCK + STALE
        self.add_run(classes={"adopt": 1, "duplicate": 2, "partial": 1})
        self.open_002()
        mc.lease_break(self.root, **self.breaking())  # resume, run for 002
        self.assertEqual((self.json(".work/lock.json")["history"][-1]["for_strand"],
                          mc.lease_status(self.root)["reserved_for"]), ("002", "001"))
        problem = self.refused(mc.lease_take, self.root, "002").findings[0]["problem"]
        self.assertIn("lease break (resume) at epoch 2 keeps the lease for strand 001", problem)
        self.assertEqual(mc.lease_take(self.root, "001")["epoch"], 4)
        self.assertIsNone(mc.lease_status(self.root)["reserved_for"])

    def test_R1_C112_after_a_park_only_the_taker_takes(self):
        self.now = CLOCK + STALE
        self.add_run()
        self.open_002()
        mc.lease_break(self.root, **self.breaking(choice="park", park_yes="yes, park 001 for now"))
        self.assertEqual([e["for_strand"] for e in self.json(".work/lock.json")["history"][-2:]], ["002", "002"])
        self.assertEqual(mc.lease_status(self.root)["reserved_for"], "002")
        self.assertEqual(self.fields(mc.lease_take, self.root, "001"), ["state"])
        taken = mc.lease_take(self.root, "002")
        mc.lease_release(self.root, taken["epoch"], taken["session_label"])
        self.assertEqual(mc.lease_take(self.root, "001")["epoch"], 5)

    def test_R1_G53_a_reservation_for_a_closed_strand_lapses(self):
        self.now = CLOCK + STALE
        self.add_run()
        mc.lease_break(self.root, **self.breaking(choice="park", park_yes="yes, park 001 for now"))
        self.assertEqual(self.fields(mc.lease_take, self.root, "001"), ["state"])
        self.edit_fm(STRAND_002, state="closed")
        self.assertEqual(mc.lease_take(self.root, "001")["epoch"], 4)

    def test_R2_G50_G51_no_fenced_write_before_a_run_and_no_old_run_in_a_new_lease(self):
        ok, reason = mc.lease_fence(self.root, 2, LABEL, "run-anything")
        self.assertEqual((ok, "no run has started under this lease" in reason), (False, True))
        self.now = CLOCK + STALE
        self.add_run()
        mc.lease_break(self.root, **self.breaking())
        taken = mc.lease_take(self.root, "001")
        self.assertEqual(self.fields(mc.lease_refresh, self.root, 4, taken["session_label"], RUN), ["run_id"])
        self.assertEqual(mc.lease_refresh(self.root, 4, taken["session_label"], "run-2026-11-05-2")["run_id"],
                         "run-2026-11-05-2")

    def test_R3_G51_the_fence_moves_the_heartbeat_before_the_write(self):
        self.edit_json(".work/lock.json", lambda lock: lock.update(run_id=RUN))
        self.now = datetime(2026, 11, 5, 15, 20, tzinfo=timezone.utc)  # the heartbeat 60 minutes old: fresh
        self.assertEqual(mc.lease_fence(self.root, 2, LABEL, RUN), (True, "ok"))
        self.assertEqual(self.assert_mirrors()["heartbeat_at"], "2026-11-05T15:20:00Z")
        self.add_run(at="2026-11-05T15:21:00Z")
        self.now = datetime(2026, 11, 5, 15, 22, tzinfo=timezone.utc)
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(choice="park", park_yes="yes, park")),
                         ["heartbeat_at"])

    def test_R4_G09_a_failed_mirror_write_leaves_the_lease_as_it_was(self):
        mc.lease_release(self.root, 2, LABEL)
        real = mc.write_file

        def failing(path, *args, **kwargs):
            if path.name == "account.json":
                raise PermissionError(13, "the file is held by another program")
            return real(path, *args, **kwargs)
        with mock.patch.object(mc, "write_file", failing), self.assertRaises(mc.CannotRun) as caught:
            mc.lease_take(self.root, "001")
        finding = caught.exception.findings[0]
        self.assertEqual((finding["file"], "the lease is unchanged" in finding["problem"]), ("account.json", True))
        self.assertEqual(self.json(".work/lock.json")["state"], "released")
        self.assertEqual(mc.lease_take(self.root, "001")["epoch"], 3)
        self.assert_mirrors()

    def test_R6_G39_take_release_and_break_back_up_the_lock(self):
        backups = self.root / ".work" / "backup" / ".work"
        mc.lease_refresh(self.root, 2, LABEL)
        self.assertFalse(backups.exists())  # a refresh backs nothing up
        before = (self.root / ".work" / "lock.json").read_bytes()
        mc.lease_release(self.root, 2, LABEL)
        taken = mc.lease_take(self.root, "001")
        self.now = CLOCK + STALE
        mc.lease_break(self.root, **self.breaking(epoch=3, session_label=taken["session_label"]))
        found = sorted(backups.glob("lock.json.*"))
        self.assertEqual((len(found), found[0].read_bytes()), (3, before))

    def test_R7_G50_G53_a_take_needs_allowlisted_values(self):
        mc.lease_release(self.root, 2, LABEL)
        path = self.root / "strands" / "001-job-tracking" / "STRAND.md"
        text = mc.read_text(path)
        for edit, field in ((lambda t: re.sub(r"(?m)^kind: .*\n", "", t), "kind"),
                            (lambda t: mc.set_front_matter(t, {"kind": "non_platform"}), "kind"),
                            (lambda t: mc.set_front_matter(t, {"state": "Closed"}), "state"),
                            (lambda t: mc.set_front_matter(t, {"version": ""}), "version"),
                            (lambda t: mc.set_front_matter(t, {"version": "v9.9"}), "version")):
            path.write_bytes(edit(text).encode("utf-8"))
            self.assertEqual(self.fields(mc.lease_take, self.root, "001"), [field])
        path.write_bytes(text.encode("utf-8"))
        self.edit_json(".work/lock.json", lambda lock: lock.update(state="Held"))
        self.assertEqual(self.fields(mc.lease_take, self.root, "001"), ["state"])

    def test_R8_G09_a_locking_error_is_named_not_read_as_contention(self):
        """Windows run: there the msvcrt branch raises the error."""
        error = OSError(getattr(errno, "ENOTSUP", errno.EINVAL), "Operation not supported")
        started = time.monotonic()
        with mock.patch("msvcrt.locking" if os.name == "nt" else "fcntl.flock", side_effect=error):
            with self.assertRaises(mc.CannotRun) as caught:
                with mc.record_mutex(self.root, timeout=1):
                    pass
        problem = caught.exception.findings[0]["problem"]
        self.assertLess(time.monotonic() - started, 0.9)
        self.assertIn("Operation not supported", problem)
        self.assertNotIn("another writer", problem)

    def test_R9_G51_a_held_lock_without_a_label_passes_neither_fence_nor_break(self):
        self.edit_json(".work/lock.json", lambda lock: lock.update(session_label=None, run_id=RUN))
        ok, reason = mc.lease_fence(self.root, 2, None, RUN)
        self.assertEqual((ok, "session_label" in reason), (False, True))
        self.now = CLOCK + STALE
        self.assertEqual(self.fields(mc.lease_break, self.root, **self.breaking(session_label=None)),
                         ["session_label"])

    def test_R13_G05_G53_a_strand_the_user_paused_does_not_take(self):
        mc.lease_release(self.root, 2, LABEL)
        self.edit_fm("strands/001-job-tracking/STRAND.md", state="paused")
        self.assertEqual(self.fields(mc.lease_take, self.root, "001"), ["state"])
        self.edit_json("strands/001-job-tracking/solution/build.json",
                       lambda b: b["runs"].append({"id": RUN, "state": "interrupted"}))
        self.assertEqual(mc.lease_take(self.root, "001")["epoch"], 3)


if __name__ == "__main__":
    unittest.main()
