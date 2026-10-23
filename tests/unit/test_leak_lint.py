"""Unit tests for plugins/monday-master-builder/scripts/leak_lint.py, part 1: the frame, the lists, the readers and
the rules on one text (WP4 step 5).

Contract clauses of rebuild-workspace/build/wp4/CONTRACT.md by id in the test names, with the decision each rule
follows (Xnn, Ynn) where it sharpens the clause. Each test builds a temporary home whose folder name holds a space,
points MMB_HOME at it and HOME and USERPROFILE at an empty canary folder, and writes one invented client record
into it from the small inline samples below; nothing is read from or written to the real home and nothing is added
under tests/. leak_lint.py runs in process through main(), and as a subprocess where the process boundary is the
point (G49). Every name, firm, figure and id here is invented. The wall, the index, blueprint and terms are
step 6's; their tests are in test_leak_wall.py.
"""
import ast, hashlib, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, zipfile  # noqa: E401
import unittest
from pathlib import Path, PureWindowsPath
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PLUGIN = REPO / "plugins" / "monday-master-builder"
SCRIPTS = PLUGIN / "scripts"
sys.dont_write_bytecode = True  # nothing cached beside the scripts (G49)
sys.path.insert(0, str(SCRIPTS))
import mmb_common as mc  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = load(SCRIPTS / "leak_lint.py", "leak_lint")

SLUG, S1, S2 = "hollowmere-bakery", "strands/001-wholesale-orders", "strands/002-delivery-rounds"
SETTINGS = {"schema": "settings/1", "created": "2026-09-01", "plugin_version": "0.1.0",
            "firm": {"name": "Quellmoor Advisory", "renderings": ["Quellmoor", "quellmoor.example"]},
            "default_build_account": {"slug": "fernway-build", "id": "91000017"},
            "never_show_workspaces": [{"id": "91000023", "name": "Margin Desk Internal"}],
            "archive": "github", "github_account": "fernway-ops"}
LOCAL = "# test additions\nOrla Pennick\n\nclass: firm\nphonetic: Quellmoor\nwhitelist: calmer\n"
RECORD = {
    "CLIENT.md": "\n".join(['---', 'schema: "client/2"', 'slug: "%s"' % SLUG, 'name: "Hollowmere Bakery"',
                            'transcript_redaction: "unanswered"', 'updated: "2026-10-01T09:00"', '---',
                            "# Hollowmere Bakery", "", "## Stakeholders", "- Ysolde Marr, bakery manager", ""]),
    "research/2026-09-02-brief.md": "\n".join([
        "# Brief", "", "The bakery runs two ovens with 34 staff across three shifts.", "",
        "- Spoiled dough costs about 184,260 a year in wasted flour and labour.",
        "- The owner set a budget of 52,000 for the new proofer.",
        "- A baker is paid 27 an hour, loaded.",
        "- The margin on wholesale loaves is 31% this season.",
        "- The proofing cabinet overheats during the long summer afternoons.", ""]),
    "calls/2026-09-10-discovery.md": "\n".join([
        "---", 'sequence: "1"', 'call_type: "discovery"', "---", "# Discovery call, 2026-09-10", "",
        "## What was said",
        '- [Q] Ysolde Marr @00:05:10: "every tray of rolls sits waiting for the one working oven"',
        "- The office said they will get back to us on that by Monday.",
        "- The night shift checks the flour delivery against the paper order.", "",
        "<!-- client-safe:start -->",
        "The bakery wants one board for wholesale orders and their delivery days.",
        '[Q] Ysolde Marr @00:09:30: "we never know which café has paid for last month"',
        "<!-- client-safe:end -->", ""]),
    "inputs/2026-09-12-ordering-guide.txt": "\n".join([
        "Ordering guide, shop copy", "", "1. Wholesale orders close at four in the afternoon.",
        "2. Rye loaves are scored by hand before the second proof.",
        "3. Crates go back to the depot every Thursday morning.", ""]),
    "inputs/2026-09-12-ordering-guide.md": "\n".join([
        "---", 'schema: "document-summary/1"', 'title: "ordering guide"', "---",
        "# Ordering guide (document snapshot)", "", "## Extracts",
        '- [Q/doc] 2026-09-12-ordering-guide step 2: "Rye loaves are scored by hand before the second proof."',
        "- Analyst note: the depot may refuse crates that come back unwashed after the weekend.", "",
        "<!-- client-safe:start -->", "The guide sends every crate back to the depot on a fixed weekday.",
        "<!-- client-safe:end -->", "", "## Conflicts",
        "- The guide says crates go back to the depot every Thursday morning; the driver said Friday.", ""]),
    S1 + "/STRAND.md": '---\nschema: "strand/1"\nstrand: "001"\n---\n# wholesale orders\n',
    S1 + "/solution/exclusions.md": "\n".join([
        "# Exclusions", "", "## Exclusions",
        "- Brackwater Mills [kind: name; added: 2026-09-11; by: the user; source: the discovery call]",
        "- 47,500 [kind: figure; added: 2026-09-11; by: the user; source: the discovery call]", ""]),
    S1 + "/solution/allowlist.md": "\n".join([
        "# Allowlist", "", "## Allowlist",
        "- callback [ok: yes, the bakery's word for a return delivery; date: 2026-09-12; class: method]", ""]),
    S2 + "/STRAND.md": '---\nschema: "strand/1"\nstrand: "002"\n---\n# delivery rounds\n',
    S2 + "/solution/exclusions.md": "# Exclusions\n\n## Exclusions\n- Tarrow Feeds [kind: name]\n",
}
PAYLOAD_REL = ".work/strands/001-wholesale-orders/payload.json"


def tree_hash(folder):
    return {p.relative_to(folder).as_posix(): mc.sha256_file(p) for p in Path(folder).rglob("*") if p.is_file()}


def write(path, text, encoding="utf-8"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding=encoding, newline="") as handle:
        handle.write(text)
    return path


def docx_bytes(parts):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            archive.writestr(name, text)
    return buffer.getvalue()


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def body(*paragraphs):
    runs = "".join("<w:p>%s</w:p>" % "".join('<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % r for r in p)
                   for p in paragraphs)
    return '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s</w:body></w:document>' % (W, runs)


def core(creator):
    return ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
            'package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Order '
            'pack</dc:title><dc:creator>%s</dc:creator></cp:coreProperties>' % creator)


def app(company):
    return ('<?xml version="1.0" encoding="UTF-8"?><Properties xmlns="http://schemas.openxmlformats.org/'
            'officeDocument/2006/extended-properties"><Company>%s</Company></Properties>' % company)


class Base(unittest.TestCase):
    """A fresh home and record per test, the real home never touched."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="leak lint "))
        self.home = self.tmp / "home with space"
        self.canary = self.tmp / "canary"
        self.canary.mkdir()
        self.root = self.home / "clients" / SLUG
        write(self.home / "local" / "settings.json", json.dumps(SETTINGS, indent=2) + "\n")
        write(self.home / "local" / "leak-terms.txt", LOCAL)
        for rel, text in RECORD.items():
            write(self.root.joinpath(*rel.split("/")), text)
        self.env = mock.patch.dict(os.environ, {"MMB_HOME": str(self.home), "HOME": str(self.canary),
                                                "USERPROFILE": str(self.canary)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def raw(self, *argv):
        """(exit code, the printed bytes) of main() run in process."""
        buffer = io.BytesIO()

        class Out:
            def write(self, text):
                buffer.write(text.encode("utf-8"))

            def flush(self):
                pass

        Out.buffer = buffer
        with mock.patch.object(sys, "stdout", Out()):
            code = lint.main(["--record", str(self.root)] + list(argv))
        return code, buffer.getvalue()

    def lint(self, *argv):
        """Run main() in process; check the envelope (G10, X41) and return (code, data)."""
        code, raw = self.raw(*argv)
        self.assertNotIn(b"\r", raw)
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["ok"], code in (0, 2))
        self.assertEqual(data["verdict"], {0: "clean", 1: "blocked", 2: "warnings", 3: "could-not-run"}[code])
        for finding in data.get("findings", []):
            for key in ("file", "field", "problem", "expected"):
                self.assertTrue(finding[key], (key, finding))
            self.assertNotIn("\\", finding["file"])
            self.assertIn(finding["rule"], lint.RULES)
            self.assertIn(finding["severity"], lint.SEVERITIES)
        if code == 3:
            for key in ("file", "field", "problem", "expected"):
                self.assertTrue(data["error"][key], data["error"])
        self.assertEqual(data["counts"], {s: sum(1 for f in data["findings"] if f["severity"] == s)
                                          for s in lint.SEVERITIES})
        return code, data

    def draft(self, text, name="d.md", strand=S1):
        rel = "%s/drafts/%s" % (strand, name)
        write(self.root.joinpath(*rel.split("/")), text)
        return rel

    def scan(self, text, name="d.md", strand=S1, *extra):
        return self.lint("scan", *(list(extra) + [self.draft(text, name, strand)]))

    def payload(self, data, kind="generic", strand="001", *extra):
        write(self.root.joinpath(*PAYLOAD_REL.split("/")), json.dumps(data, indent=2))
        return self.lint("payload", "--strand", strand, "--kind", kind, "--file", PAYLOAD_REL, *extra)

    def found(self, data, rule=None, cls=None, severity=None):
        return [f for f in data["findings"] if (rule is None or f["rule"] == rule) and
                (cls is None or f["class"] == cls) and (severity is None or f["severity"] == severity)]

    def assertBlocks(self, text, rule, cls=None, match=None):
        code, data = self.scan(text)
        hits = self.found(data, rule, cls, "block")
        self.assertEqual(code, 1, data["findings"])
        self.assertTrue(hits, data["findings"])
        if match is not None:
            self.assertIn(match, [h["match"] for h in hits])
        return data

    def assertOwnFigure(self, text, rule="figure"):
        """A34 (R70): the client's own figure in its own build warns under its own rule, exit 2, with no block."""
        code, data = self.scan(text)
        self.assertEqual(code, 2, data["findings"])
        self.assertFalse(self.found(data, severity="block"), data["findings"])
        self.assertTrue(self.found(data, rule, None, "warn"), data["findings"])
        return data

    def assertClean(self, text, code_expected=0):
        code, data = self.scan(text)
        self.assertEqual(code, code_expected, data["findings"])
        self.assertFalse(self.found(data, severity="block"), data["findings"])
        return data


# 2.1 Runtime and cross-system rule

class RuntimeTest(Base):

    def tree(self):
        return ast.parse((SCRIPTS / "leak_lint.py").read_text(encoding="utf-8"))

    def test_L01_L10_standard_library_only_and_no_network_module(self):
        names = set()
        for node in ast.walk(self.tree()):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        names.discard("mmb_common")
        stdlib = getattr(sys, "stdlib_module_names", None)
        for name in names:
            if stdlib is not None:
                self.assertIn(name, stdlib)
            else:
                spec = importlib.util.find_spec(name)
                self.assertTrue(spec is not None and "site-packages" not in str(spec.origin), name)
        self.assertFalse(names & {"socket", "urllib", "http", "ssl", "requests"})

    def test_L02_python_3_9_syntax(self):
        for path in (SCRIPTS / "leak_lint.py", Path(__file__)):
            ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_L03_dont_write_bytecode_first_after_import_sys(self):
        body_nodes = self.tree().body
        index = next(i for i, n in enumerate(body_nodes) if isinstance(n, ast.Import) and
                     [a.name for a in n.names] == ["sys"])
        follow = body_nodes[index + 1]
        self.assertIsInstance(follow, ast.Assign)
        target = follow.targets[0]
        self.assertEqual((target.value.id, target.attr, follow.value.value), ("sys", "dont_write_bytecode", True))
        common = next(i for i, n in enumerate(body_nodes) if isinstance(n, ast.Import) and
                      any(a.name == "mmb_common" for a in n.names))
        self.assertGreater(common, index + 1)

    def test_L05_L167_no_shell_and_no_pdf_tool(self):
        text = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        for word in ("os.system", "shell=True", "os.popen", "subprocess", "pdftotext"):
            self.assertNotIn(word, text)

    def test_L13_own_frame_and_mmb_common_has_none(self):
        for name in ("Usage", "Parser", "emit", "main", "build_parser"):
            self.assertTrue(hasattr(lint, name))
        self.assertFalse(hasattr(mc, "emit"))

    def test_L206_python_below_3_9_is_exit_3_with_the_envelope(self):
        self.assertIsNone(lint.python_too_old((3, 9)))
        self.assertIsNone(lint.python_too_old((3, 14)))
        envelope = json.loads(lint.python_too_old((3, 8)))
        self.assertEqual((envelope["ok"], envelope["command"], envelope["error"]["problem"]),
                         (False, None, "Python 3.8"))

    def test_L09_L11_L120_nothing_written_in_the_record_or_the_home(self):
        before, canary = tree_hash(self.home), tree_hash(self.canary)
        rel = self.draft("The proofing cabinet overheats during the long summer afternoons. Spoiled dough 184,260.")
        self.assertEqual(self.lint("scan", rel)[0], 1)
        self.payload({"name": "Wholesale 52,000"})
        self.lint("scan")
        after = tree_hash(self.home)
        for rel_written in (rel, PAYLOAD_REL):
            after.pop("clients/%s/%s" % (SLUG, rel_written), None)
        self.assertEqual(after, before)
        self.assertEqual(tree_hash(self.canary), canary)
        self.assertFalse((self.root / ".work" / "record.mutex").exists())

    def test_L04_G49_no_file_appears_in_the_plugin_copy_after_any_command(self):
        """Every command form in its own process, the bytecode variable dropped; the copy's file list is unchanged."""
        plugin = self.tmp / "plugin copy"
        (plugin / "scripts").mkdir(parents=True)
        (plugin / "shared").mkdir()
        for name in ("mmb_common.py", "leak_lint.py"):
            shutil.copy(str(SCRIPTS / name), str(plugin / "scripts" / name))
        shutil.copy(str(PLUGIN / "shared" / "leak-terms.txt"), str(plugin / "shared" / "leak-terms.txt"))
        listing = sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*"))
        rel = self.draft("A plain line for the office.")
        write(self.root.joinpath(*PAYLOAD_REL.split("/")), '{"name": "Orders"}')
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        forms = (["scan", rel], ["scan"], ["payload", "--strand", "001", "--kind", "board", "--file", PAYLOAD_REL],
                 ["blueprint", "--strand", "001"], ["wall", "--text", "Orders"], ["terms", str(self.tmp)], ["index"],
                 ["migrate"])
        codes = []
        for form in forms:
            done = subprocess.run([sys.executable, str(plugin / "scripts" / "leak_lint.py"), "--record",
                                   str(self.root)] + form, env=env, cwd=str(self.tmp), capture_output=True)
            json.loads(done.stdout.decode("utf-8"))
            codes.append(done.returncode)
        # blueprint: the strand has no blueprint; terms: the record has no index entry yet, so X30 stops it
        self.assertEqual(codes, [0, 0, 0, 3, 0, 3, 0, 3])
        self.assertEqual(sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*")), listing)


# 2.2 The CLI frame, envelope and exit codes

class FrameTest(Base):

    def test_L20_L21_parser_and_usage_errors_are_exit_3(self):
        for argv in (["migrate"], ["payload", "--strand", "001"], ["payload", "--strand", "001", "--kind", "planet",
                                                                    "--file", "x.json"], ["scan", "-h"], []):
            code, data = self.lint(*argv)
            self.assertEqual(code, 3)
            self.assertIsNone(data["command"])
            self.assertEqual(data["error"]["field"], "arguments")
        parser = lint.build_parser()
        names = set(parser._subparsers._group_actions[0].choices)
        self.assertEqual(names, {"scan", "payload", "blueprint", "wall", "terms", "index"})

    def test_X08_the_part_2_commands_are_built_and_none_answers_not_built_yet(self):
        for argv, expected in ((["blueprint", "--strand", "001"], 3), (["wall", "--text", "Orders"], 0),
                               (["terms", "x"], 3), (["index"], 0)):
            code, data = self.lint(*argv)
            self.assertEqual(code, expected, argv)
            self.assertNotIn("not built", json.dumps(data))

    def test_L22_no_client_md_is_exit_3_naming_it(self):
        (self.root / "CLIENT.md").unlink()
        code, data = self.lint("scan")
        self.assertEqual((code, data["error"]["file"]), (3, "CLIENT.md"))

    def test_L23_L24_clean_text_is_exit_0_with_the_envelope(self):
        code, data = self.scan("The office keeps the order book up to date.")
        self.assertEqual(code, 0)
        self.assertEqual(list(data)[:3], ["ok", "command", "verdict"])
        self.assertEqual((data["command"], data["mode"], data["strand"], data["findings"]), ("scan", "full", "001", []))

    def test_L25_L26_L122_block_is_exit_1_and_warnings_only_exit_2(self):
        self.assertEqual(self.scan("Ask Orla Pennick.")[0], 1)
        code, data = self.scan("Order 1,200 loaves and 2,300 rolls.")
        self.assertEqual(code, 2)
        self.assertEqual(len(self.found(data, "number", severity="warn")), 2)

    def test_L28_one_run_reports_every_finding(self):
        code, data = self.scan("Quellmoor Advisory checks [Q] at ~/notes with P3, and the 184,260 total.\n"
                               "Bearer Fx7kQ2mL9pR4tV8wZ3yBq9")
        rules = {f["rule"] for f in data["findings"]}
        self.assertTrue({"term", "figure", "credential"} <= rules, rules)
        self.assertGreaterEqual(len(self.found(data, "term")), 4)

    def test_L29_L12_finding_parts_and_posix_names(self):
        rel = self.draft("Ask Orla Pennick.", "x.md")
        code, data = self.lint("scan", rel.replace("/", "\\") if os.sep == "\\" else rel)
        finding = data["findings"][0]
        self.assertEqual((finding["file"], finding["field"], finding["line"], finding["column"], finding["class"]),
                         (rel, "line 1", 1, 5, "local"))
        self.assertEqual(PureWindowsPath(rel.replace("/", "\\")).as_posix(), finding["file"])

    def test_L30_two_runs_give_byte_equal_output(self):
        rel = self.draft("Quellmoor [X] 52,000 and Orla Pennick, never client-facing.")
        outputs = [self.raw("scan", rel) for _ in range(2)]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0][0], 1)

    def test_L31_L210_X16_inputs_carry_sha256_also_on_exit_1(self):
        rel = self.draft("Ask Orla Pennick.")
        code, data = self.lint("scan", rel)
        self.assertEqual(code, 1)
        inputs = {i["file"]: i for i in data["inputs"]}
        self.assertEqual(inputs[rel]["sha256"], mc.sha256_file(self.root.joinpath(*rel.split("/"))))
        self.assertEqual(inputs["<home>/local/settings.json"]["sha256"],
                         mc.sha256_file(self.home / "local" / "settings.json"))
        self.assertIn("<plugin>/shared/leak-terms.txt", inputs)
        self.assertIn("research/2026-09-02-brief.md", inputs)
        self.assertEqual(inputs["%s/solution/allowlist.md" % S1]["sha256"],
                         mc.sha256_file(self.root / S1 / "solution" / "allowlist.md"))
        self.assertEqual(sorted(inputs), [i["file"] for i in data["inputs"]])
        first = inputs[rel]["sha256"]
        self.draft("Ask the office.")
        code, data = self.lint("scan", rel)
        self.assertEqual(code, 0)
        self.assertNotEqual({i["file"]: i for i in data["inputs"]}[rel]["sha256"], first)

    def test_X16_args_digest_is_the_canonical_payload(self):
        data = {"name": "Orders", "items": [{"b": 2, "a": "é"}]}
        code, out = self.payload(data)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.assertEqual(out["args_digest"], hashlib.sha256(canonical).hexdigest())
        self.assertNotIn("mode", out)

    def test_L32_X22_a_path_outside_the_record_is_exit_3(self):
        outside = write(self.tmp / "elsewhere.md", "Orders.")
        code, data = self.lint("scan", str(outside))
        self.assertEqual(code, 3)
        self.assertIn("outside the record", data["error"]["problem"])
        write(self.tmp / "p.json", "{}")
        code, data = self.lint("payload", "--strand", "001", "--kind", "board", "--file", str(self.tmp / "p.json"))
        self.assertEqual(code, 3)
        code, data = self.lint("scan", "../../elsewhere.md")
        self.assertEqual(code, 3)

    def test_X08_strand_rules(self):
        self.assertEqual(self.lint("payload", "--strand", "009", "--kind", "board", "--file", PAYLOAD_REL)[0], 3)
        self.assertEqual(self.lint("scan", "--strand", "1")[0], 3)
        rel = self.draft("Orders.")
        code, data = self.lint("scan", "--strand", "002", rel)
        self.assertEqual(code, 3)
        self.assertIn("strand 001", data["error"]["problem"])

    def test_X41_ok_is_false_on_every_exit_3(self):
        (self.home / "local" / "settings.json").unlink()
        code, data = self.scan("Orders.")
        self.assertEqual((code, data["ok"], data["verdict"]), (3, False, "could-not-run"))


# 2.3 The inputs the lint loads

class ListsTest(Base):

    def shipped_copy(self, text):
        plugin = self.tmp / "plugin"
        write(plugin / "shared" / "leak-terms.txt", text)
        return mock.patch.object(lint, "PLUGIN", plugin)

    def test_L33_literal_boundaries(self):
        self.assertBlocks("Take the exit-ramp now.", "term", "method")
        self.assertBlocks("The exit-ramp.", "term", "method")
        self.assertClean("The boexit-rampx sign.")
        # R61 (R13 (b)): the spaced form is an everyday phrase and blocks only hyphenated.
        self.assertClean("Take the exit ramp now.")

    def test_L34_L35_classes_and_re_rows(self):
        data = self.assertBlocks("Open p3 today; see P12.", "term", "pain-ids")
        self.assertEqual(len(self.found(data, "term", "pain-ids")), 2)
        self.assertClean("Shelf P123 is fine.")

    def test_L36_X33_parse_roles_and_errors(self):
        rows = lint.parse_list("class: firm\nphonetic: Brendle\nwhitelist: brindle\nre: \\bx\\d\\b\nplain row\n", "t",
                               local=True)
        self.assertEqual([r.kind for r in rows], ["phonetic", "whitelist", "re", "literal"])
        bad = ("class: bad name!\n", "re: (\n", "class: method\nwhitelist: alone\n", "class: firm\nphonetic:\n",
               "class: x\nre:\n", "class: x\nre: (a+)+\n", "class: x\nre: (\\w*)*\n")
        for text in bad:
            with self.assertRaises(mc.CannotRun, msg=text):
                lint.parse_list(text, "t", local=True)
        with self.assertRaises(mc.CannotRun):
            lint.parse_list("row above\nclass: x\n", "t", local=False)
        self.assertEqual(lint.parse_list("row above\n", "t", local=True)[0].cls, "local")
        self.assertEqual(lint.parse_list("class: x\nRe: typo\n", "t", local=True)[0].kind, "literal")

    def test_L37_shipped_firm_class_is_empty(self):
        rows = lint.parse_list((PLUGIN / "shared" / "leak-terms.txt").read_text(encoding="utf-8"), "s", local=False)
        self.assertFalse([r for r in rows if r.cls == "firm"])

    def test_L38_X33_zero_byte_and_absent_local_list_add_nothing(self):
        text = "Orla Pennick and Kelmer sent the order."
        write(self.home / "local" / "leak-terms.txt", "")
        zero = self.scan(text)[1]["findings"]
        (self.home / "local" / "leak-terms.txt").unlink()
        code, data = self.scan(text)
        self.assertEqual(zero, data["findings"])
        self.assertIn({"file": "<home>/local/leak-terms.txt", "state": "absent"}, data["inputs"])
        write(self.home / "local" / "leak-terms.txt", "class: method\nproving schedule\n")
        self.assertBlocks("Share the proving schedule.", "term", "method")

    def test_L201_X33_a_local_list_that_cannot_be_read_is_exit_3(self):
        (self.home / "local" / "leak-terms.txt").write_bytes(b"class: x\n\xff\xfe broken\n")
        self.assertEqual(self.scan("Orders.")[0], 3)

    def test_L39_L49_L41_firm_renderings_and_local_firm_rows(self):
        for text in ("Prepared by Quellmoor Advisory.", "Prepared by quellmoor.", "See quellmoor.example now."):
            self.assertBlocks(text, "term", "firm")
        write(self.home / "local" / "leak-terms.txt", "class: firm\nQM Partners\n")
        self.assertBlocks("Signed QM Partners.", "term", "firm")
        settings = dict(SETTINGS, firm={"name": "Quellmoor Advisory", "renderings": []})
        write(self.home / "local" / "settings.json", json.dumps(settings))
        self.assertBlocks("Prepared by Quellmoor Advisory.", "term", "firm")

    def test_L40_L42_L201_settings_are_required_and_checked(self):
        cases = ({"schema": "settings/2"}, {"schema": "other/1"}, {"firm": {"name": ""}}, {"firm": "x"},
                 {"firm": {"name": "Quellmoor", "renderings": [""]}}, {"never_show_workspaces": "x"})
        for change in cases:
            write(self.home / "local" / "settings.json", json.dumps(dict(SETTINGS, **change)))
            code, data = self.scan("Orders.")
            self.assertEqual(code, 3, change)
            self.assertEqual(data["error"]["file"], "<home>/local/settings.json")
            self.assertEqual(data["findings"], [])
        write(self.home / "local" / "settings.json", '{"schema": "settings/1", ')
        self.assertEqual(self.scan("Orders.")[0], 3)
        (self.home / "local" / "settings.json").unlink()
        code, data = self.scan("Orders.")
        self.assertEqual((code, data["error"]["field"]), (3, "(whole file)"))
        write(self.home / "local" / "settings.json", "\ufeff" + json.dumps(SETTINGS))
        self.assertEqual(self.scan("Orders.")[0], 0)

    def test_L200_shipped_list_missing_or_broken_is_exit_3(self):
        with mock.patch.object(lint, "PLUGIN", self.tmp / "no plugin"):
            code, data = self.scan("Orders.")
        self.assertEqual((code, data["error"]["file"]), (3, "<plugin>/shared/leak-terms.txt"))
        shipped = (PLUGIN / "shared" / "leak-terms.txt").read_text(encoding="utf-8")
        for text in (shipped.replace("re: \\bP\\d{1,2}\\b", "re: \\bP(\\d{1,2}\\b"), "orphan row\n" + shipped,
                     shipped.replace("re: (?<![\\w/=?&#.-])\\d{8,}(?![\\w-])\n", "")):
            with self.shipped_copy(text):
                code, data = self.scan("Orders.")
            self.assertEqual(code, 3)

    def test_L43_L101_exclusions_of_every_strand(self):
        self.assertBlocks("Flour from Tarrow Feeds.", "exclusion")
        code, data = self.scan("Flour from Brackwater Mills.", "d.md", S2)
        self.assertEqual(code, 1)

    def test_L102_an_unreadable_exclusions_file_is_exit_3(self):
        (self.root / S2 / "solution" / "exclusions.md").write_bytes(b"## Exclusions\n- \xff\n")
        self.assertEqual(self.scan("Orders.")[0], 3)

    def test_X09_Y05_rows_and_the_bracketed_term(self):
        self.assertEqual(lint.row_parts("[E] [ok: yes; class: markers]"), ("[E]", {"ok": "yes", "class": "markers"}))
        self.assertEqual(lint.row_parts("[E]"), ("[E]", {}))
        self.assertEqual(lint.row_parts("Brackwater Mills [kind: name]"), ("Brackwater Mills", {"kind": "name"}))
        self.assertEqual(lint.row_parts("Rate [note: x]"), ("Rate [note: x]", {}))
        write(self.root / S1 / "solution" / "exclusions.md", "## Exclusions\n- [kind: name]\n")
        self.assertEqual(self.scan("Orders.")[0], 3)
        write(self.root / S1 / "solution" / "exclusions.md", "## Exclusions\n- Oatley [kind: brand]\n")
        self.assertEqual(self.scan("Orders.")[0], 3)
        write(self.root / S1 / "solution" / "exclusions.md", "## Exclusions\n- Oatley [kind: figure]\n")
        self.assertEqual(self.scan("Orders.")[0], 3)
        write(self.root / S1 / "solution" / "exclusions.md", "# Notes\n- Oatley\n\n## Exclusions\n- 9,350\n")
        self.assertClean("Oatley sends oats.")
        self.assertBlocks("Pay $9.35k.", "exclusion")


# 2.4 The term rules: names, ids, markers, paths, credentials, notes

class TermTest(Base):

    def test_L50_L51_case_possessive_and_split_renderings(self):
        for text in ("QUELLMOOR ADVISORY wrote it.", "Quellmoor's draft.", "quellmoor’s draft.",
                     "Prepared by Quellmoor, Advisory.", "Prepared by Quellmoor-Advisory.",
                     "By QuellmoorAdvisory today.", "By Quellmoor\nAdvisory today."):
            self.assertBlocks(text, "term", "firm")
        self.assertBlocks("Ask Orla, Pennick.", "term", "local")

    def test_X28_normalisation_steps(self):
        self.assertEqual(lint.normal_form("Quell\u200bmoor"), "quellmoor")        # 1 format characters
        self.assertEqual(lint.normal_form("Ｑｕｅｌｌｍｏｏｒ"), "quellmoor")         # 2 NFKC
        self.assertEqual(lint.normal_form("Quеllmооr"), "quellmoor")             # 3 look-alikes (Cyrillic)
        self.assertEqual(lint.normal_form("QUELLMOOR"), "quellmoor")             # 4 case
        self.assertEqual(lint.normal_form("Quéllmöor"), "quellmoor")             # 4 diacritics
        self.assertEqual(lint.normal_form("Quellmoor's don't"), "quellmoor dont")  # 5 possessive, apostrophe
        self.assertEqual(lint.normal_form("*Quell* | moor_x"), "quell moor x")    # 5 Markdown marks separate
        for disguise in ("Quell\u200bmoor Advisory", "Ｑｕｅｌｌｍｏｏｒ", "Quеllmооr", "Quéllmoor Advisory"):
            self.assertBlocks("Signed %s." % disguise, "term", "firm")

    def test_X32_phonetic_key_of_twenty_invented_words(self):
        expected = {"thymbel": "0MPL", "harbour": "HRPR", "Harbur": "HRPR", "knotley": "MTL", "wrenna": "RM",
                    "philbrook": "FLPRK", "xander": "SMTR", "quenby": "KMP", "ashcombe": "AXKMP", "gelling": "JLMK",
                    "cyrena": "SRM", "dodge": "TJ", "pschorr": "SKR", "wheaton": "WTM", "knightley": "MTL",
                    "vexby": "FKSP", "tatcham": "TXM", "ozzard": "ASRT", "yelverton": "YLFRTM", "mackley": "MKL"}
        self.assertEqual({w: lint.phonetic_key(w) for w in expected}, expected)
        self.assertEqual(lint.edit_distance("quellmoor", "quelmoor", 2), 1)
        self.assertEqual(lint.edit_distance("quellmoor", "qeullmoor", 2), 1)
        self.assertEqual(lint.edit_distance("quellmoor", "harbour", 2), 3)

    def test_L52_L53_L54_phonetic_variants_whitelist_and_sound_alike(self):
        for text in ("Prepared by Kelmer.", "Prepared by Quelmore.", "Prepared by Quell Moor.",
                     "Prepared by Quellmor."):
            self.assertBlocks(text, "phonetic", "firm")
        for text in ("Keep the room calmer.", "A calmer morning helps.", "Calmer weather is due.",
                     "The calmer the better."):
            self.assertClean(text)
        self.assertBlocks("Prepared by Calmer Advisory.", "phonetic", "firm")

    def test_Y09_a_fused_window_keys_each_word_apart(self):
        source = lint.PhoneticSource("firm", "Thymbel", "t", [])
        self.assertIn("0MPL", source.keys)
        self.assertEqual(lint.phonetic_key("the") + lint.phonetic_key("thimble"), "00MPL")
        self.assertEqual(lint.phonetic_key("thym") + lint.phonetic_key("bell"), "0MPL")

    def test_L56_plugin_and_assistant_names(self):
        for text, cls in (("Built with monday master builder.", "plugin"), ("Set MMB_HOME first.", "plugin"),
                          ("See mmb_common there.", "plugin"), ("Drafted with claude.", "assistant"),
                          ("Built with mondaymasterbuilder.", "plugin")):
            self.assertBlocks(text, "term", cls)
        self.assertClean("Built on monday for the office.")

    def test_L57_method_terms_and_grades(self):
        for text in ("Show the cost-of-waiting.", "This is a fit risk.", "R4 Met after the visit.",
                     "Met for R4 now."):
            self.assertBlocks(text, "term", "method")
        self.assertClean("The bakers met at noon.")

    def test_L58_L59_X17_record_ids(self):
        for text in ("See P3.", "See N2.", "See S1.", "See O4.", "See C2.", "See R7.", "See 001:B1.",
                     "See 001/v0.1.", "Incident priority P1 opens a ticket."):
            self.assertBlocks(text, "term", "pain-ids")
        self.assertClean("Shelf P123 is full.")

    def test_L60_L62_L63_L66_the_nine_markers(self):
        for marker in lint.MARKERS:
            self.assertBlocks("%s the office agreed." % marker, "term", "markers")
            code, data = self.payload({"name": "Orders %s" % marker, "markdown": "Done %s" % marker})
            self.assertEqual(len(self.found(data, "term", "markers")), 2)
        self.assertClean("[1] the office agreed. [note] and (see below).")

    def test_L66_L273_markers_pinned_equal_the_shipped_rows(self):
        rows = lint.parse_list((PLUGIN / "shared" / "leak-terms.txt").read_text(encoding="utf-8"), "s", local=False)
        literal = {r.term for r in rows if r.cls == "markers" and r.kind == "literal"}
        self.assertEqual(len(lint.MARKERS), 9)
        for marker in lint.MARKERS:
            self.assertIn(marker, literal)
        self.assertIn("# The nine evidence markers", (PLUGIN / "shared" / "leak-terms.txt").read_text("utf-8"))

    def test_L64_L65_L75_tags_status_markers_locations_and_design_ids(self):
        for text in ("See [A12].", "See [A14-2].", "See [L14].", "[found] in the copy.", "[inaudible] here.",
                     "[live board] now.", "Said @00:12:31.", "At cue 82.", "At cues 82-85.", "At L142.",
                     "At L142-144.", "Probe P-19 ran.", "Gotcha S0-4 too.",
                     "Hash " + "ab12" * 16 + " here."):
            data = self.assertBlocks(text, "term")
            self.assertTrue({f["class"] for f in self.found(data, "term")} & {"markers", "id-patterns"}, text)
        self.assertClean("The cue was clear.")

    def test_L67_L68_L69_X03_record_paths_in_both_spellings(self):
        for text in ("Saved in clients/hollowmere-bakery/calls/ today.", "Saved in .work/ today.",
                     "Saved in strands/001-wholesale-orders/ today.", "In ~/notes today.", "In /Users/office today.",
                     "Saved in clients\\hollowmere-bakery\\calls\\ today.", "Saved in .work\\ today.",
                     "Saved in strands\\001-wholesale-orders\\ today.", "Saved in C:\\Users\\office today.",
                     "Saved in clients/hollowmere-bakery\\calls\\x today.", "Saved in clients%2Fhollowmere%2F today.",
                     "Open file:///Users/office/notes now."):
            self.assertBlocks(text, "term", "id-patterns")
        self.assertClean("Saved with the calls and inputs for the strands of work.")

    def test_L70_record_file_names(self):
        for name in ("CLIENT.md", "STRAND.md", "SUMMARY.md", "discovery.md", "blueprint.md", "log.md", "account.json",
                     "build.json", "live-map.md"):
            code, data = self.payload({"name": "See %s" % name})
            self.assertEqual(code, 1, name)
        self.assertEqual(self.payload({"name": "See orders.md"})[0], 0)

    def test_L71_Y03_html_comments_and_the_mark_lines(self):
        self.assertBlocks("Check <!-- ask the office --> first.", "term", "id-patterns")
        self.assertClean("Check <b>with the office</b> first.")
        self.assertClean("Notes\n<!-- client-safe:start -->\nThe office agreed.\n  <!-- client-safe:end -->  \n")
        self.assertBlocks("<!-- client-safe:start --> note\n", "term", "id-patterns")

    def test_L72_L73_L74_X34_monday_ids_and_links(self):
        self.assertBlocks("Board 73100482 holds the orders.", "term", "id-patterns")
        self.assertEqual(self.scan("Board 7310048 holds the orders.")[0], 2)
        for text in ("[Board](https://boards.example/b/73100482) holds orders.", "See <https://boards.example/73100482>.",
                     '<a href="https://boards.example/73100482">board</a>', "Open https://boards.example/73100482 now."):
            self.assertClean(text)
        self.assertBlocks("[Quellmoor](https://boards.example/b/1) holds orders.", "term", "firm")
        self.assertBlocks("[Board](https://quellmoor.example/b/1) holds orders.", "term", "firm")
        self.assertBlocks("[Board](https://boards.example/Quellmoor%20Advisory) holds.", "term", "firm")
        self.assertBlocks("Open hxxp://boards.example/73100482 now.", "term", "id-patterns")

    def test_X34_Y02_split_ids_and_spaced_dates(self):
        for text in ("Join meeting 6620 1934 58.", "Ring 0770 090 0418 first.", "Ref 12-34-56-78 here."):
            self.assertBlocks(text, "term", "id-patterns")
        code, data = self.scan("Delivery starts on 03 11 2026.")
        self.assertEqual(code, 2)
        self.assertTrue(self.found(data, "split-figure", severity="warn"))
        self.assertClean("Delivery starts on 2026-11-03 at 14:30.")

    def test_L76_L263_X15_Y04_credentials_each_shape_and_twins(self):
        planted = ("Authorization: Bearer Fx7kQ2mL9pR4tV8wZ3yB", "password = oatfield42", "pwd:oatfield42",
                   '"secret": "oatfield42"', "https://orders:Wq8zLm3x@files.example/export",
                   "https://files.example/export?token=Hd72kPq9Lx", "https://files.example/x?sig=Hd72kPq9Lx&a=1",
                   "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.c2lnbmF0dXJldGVzdA",
                   "AKIA" + "TESTONLY00000000", "pk_test_" + "sample0000000000", "ghp_" + "sample" + "0" * 30,
                   "xoxb-sample-only", "-----BEGIN RSA PRIVATE KEY-----", "Qm7rT2vX9pL4sW8nB3kY6hJ1dF5gZ0cAe",
                   "https://files.example/export%3Ftoken%3DHd72kPq9Lx")
        for text in planted:
            self.assertBlocks(text, "credential")
        for text in ("The bearer of the order signs it.", "The password reset is handled by the office.",
                     "https://files.example/export?page=two", "The key box is by the door.",
                     "[Shop](https://files.example/Qm7rT2vX9pL4sW8nB3kY6hJ1dF5gZ0cAe)", "pass: no"):
            self.assertClean(text)

    def test_L77_X40_Y07_internal_notes(self):
        for text in ("Internal: never client-facing", "note to self: ring the office.", "This is internal only.",
                     "Not for the client yet.", "Speaker 2 said yes.", 'owner: "office"'):
            self.assertBlocks(text, "internal-note")
        code, data = self.scan("Notes\n---\nschema: draft\n")
        notes = self.found(data, "internal-note")
        self.assertEqual([(f["line"], f["match"]) for f in notes], [(2, "---")])
        self.assertClean("owner: office\n---\nThe layout review is next.\nReminder: ring the office.")

    def test_X28_step_6_a_legal_suffix_need_not_be_written(self):
        write(self.root / S2 / "solution" / "exclusions.md", "## Exclusions\n- Tarrow Feeds Ltd [kind: name]\n")
        for text in ("Flour from Tarrow Feeds.", "Flour from Tarrow Feeds, Ltd.", "Flour from TarrowFeeds."):
            self.assertBlocks(text, "exclusion")
        self.assertClean("Flour from the feed mill.")

    def test_X06_seller_account_names_and_ids(self):
        for text in ("Copy from Margin Desk Internal.", "Push to fernway-ops.", "Push to fernway ops.",
                     "Build in fernway-build.", "[Open](https://boards.example/w/91000023)", "Account 91000017."):
            self.assertBlocks(text, "seller-account", "seller-account")
        self.assertClean("Copy from the intake board.")

    def test_X06_vocabulary_groups(self):
        self.assertBlocks("The talk share was even.", "term", "internal-vocabulary")
        self.assertBlocks("See the alias table.", "term", "internal-vocabulary")
        self.assertBlocks("This opens an up-sell later.", "term", "sales-framing")
        self.assertClean("Possible next improvements for the bakers.")


# 2.5 Client figures

class FigureTest(Base):

    def test_L78_X11_figures_from_calls_research_and_client_documents(self):
        write(self.root / "inputs" / "2026-09-20-price-list.txt", "The price list sets crates at 62,800 a year.\n")
        write(self.root / "calls" / "2026-09-21-review.md", "- The oven service costs 45,000 a year.\n")
        for text, source in (("Crates 62,800.", "inputs/2026-09-20-price-list.txt"),
                             ("Service 45,000.", "calls/2026-09-21-review.md"),
                             ("Dough 184,260.", "research/2026-09-02-brief.md")):
            data = self.assertOwnFigure(text)  # A34 (R70): the client's own figure warns in its own build
            self.assertEqual(self.found(data, "figure")[0]["source"], source)

    def test_L79_to_L84_five_formats_against_five_record_formats(self):
        forms = ("45000", "45,000", "45k", "$45k", "forty-five thousand")
        for record_form in forms:
            write(self.root / "research" / "2026-09-02-brief.md", "- The oven service costs %s a year.\n" % record_form)
            for payload_form in forms:
                code, data = self.payload({"markdown": "The service is %s." % payload_form})
                self.assertEqual(code, 2, (record_form, payload_form, data["findings"]))  # A34 (R70): it warns
                self.assertTrue(self.found(data, "figure", severity="warn"), (record_form, payload_form))

    def test_X25_rounded_and_truncated_forms_within_precision(self):
        for text in ("Waste runs at 184k.", "Waste runs at $185k.", "Waste runs at 184.3k.",
                     "Waste runs at one hundred and eighty-four thousand."):
            self.assertOwnFigure(text)  # A34 (R70): matched as before, and warned instead of blocked
        code, data = self.scan("Waste runs at 183k.")
        self.assertEqual(code, 2)
        self.assertTrue(self.found(data, "number"))

    def test_L85_L86_X25_floors_and_warnings(self):
        code, data = self.scan("The bakery bought 1,200 crates.")
        self.assertEqual((code, [f["rule"] for f in data["findings"]]), (2, ["number"]))
        self.assertEqual(self.scan("The bakery bought 9 crates.")[0], 0)
        # A33 (R67): the record's 27 an hour and 34 staff are below 100, so they are no client figures any more and
        # a 27 or a 34 passes (A33Test); the floors are shown with figures of 100 to 999 instead.
        write(self.root / "research" / "2026-09-04-vans.md", "- A delivery van costs 240 an hour to hire.\n"
                                                             "- The bakery serves 340 regular customers.\n")
        # A34 (R70): a cost figure beside a rate suffix, a currency sign or a cost word, and a cost percentage, warn.
        self.assertOwnFigure("A van is 240 an hour.")
        self.assertOwnFigure("Pay $240 for it.")
        code, data = self.scan("A tray takes 240 minutes.")
        self.assertEqual((code, data["findings"][0]["rule"]), (2, "record-number"))
        code, data = self.scan("The bakery has 340 cafes on its books.")
        self.assertEqual((code, data["findings"][0]["rule"]), (2, "record-number"))
        self.assertEqual(self.scan("A baker is paid 27 an hour.")[1]["findings"][0]["rule"], "copied-run")
        self.assertOwnFigure("The margin is 31%.")
        code, data = self.scan("About 15% of loaves.")
        self.assertEqual((code, data["findings"][0]["rule"]), (2, "number"))

    def test_X25_not_numbers_dates_times_versions_years_ordinals(self):
        self.assertClean("On 2026-10-17, 17/10/2026, 10/17/2026, 17.10.2026, 17 October 2026 and October 17 at "
                         "14:30, in 2026, v0.1 and 1.2.3.\n1. First step.\n12) Twelfth step.")
        code, data = self.scan("Spend $2026 on it.")
        self.assertEqual(code, 2)

    def test_X25_ambiguous_lower_case_m_is_read_both_ways(self):
        write(self.root / "research" / "2026-09-02-brief.md", "- The new line costs 2,000,000.\n")
        self.assertOwnFigure("The shop is 2m long.")  # A34 (R70): read both ways as before, and warned
        self.assertOwnFigure("A $2M line.")

    def test_L87_X25_exclusion_figures_in_every_rendering(self):
        for text in ("Pay 47500.", "Pay 47,500.", "Pay 47.5k.", "Pay $47.5k.", "Pay forty-seven thousand five hundred.",
                     "Pay 47 500."):
            code, data = self.scan(text)
            self.assertEqual(code, 1, text)
            self.assertTrue(self.found(data, "exclusion") or self.found(data, "split-figure"), text)

    def test_L105_L106_split_renderings(self):
        write(self.root / "research" / "2026-09-02-brief.md", "- The new proofer has a budget of 52,000.\n")
        # A34 (R70): the client's own figure in split form is found as before and warns
        self.assertOwnFigure("The proofer comes to 52 000 in all.", "split-figure")
        self.assertOwnFigure("A note puts it at fifty-\ntwo thousand.", "split-figure")
        self.assertOwnFigure("| 52 | 000 |", "split-figure")
        self.assertOwnFigure("It is 52.000 now.", "split-figure")
        code, data = self.scan("The proofer comes to 61 000 in all.")
        self.assertNotEqual(code, 1)
        code, data = self.scan("Crates 3 4 by the door.")
        self.assertNotEqual(code, 1)

    def test_X25_figures_in_links_block_and_warnings_skip_links(self):
        self.assertOwnFigure("[Sheet](https://files.example/report?total=184260)")  # A34 (R70): found, and warned
        self.assertClean("[Sheet](https://files.example/report?page=4421)")


# 2.6 Copied runs, quotes and the exemptions

class RunTest(Base):

    def test_L88_L89_six_words_block_five_pass(self):
        data = self.assertBlocks("The proofing cabinet overheats during the long summer.", "copied-run")
        self.assertEqual(self.found(data, "copied-run")[0]["source"], "research/2026-09-02-brief.md")
        self.assertClean("The proofing cabinet overheats during lunch.")
        self.assertClean("Our proofing cabinet often overheats during the summer.")

    def test_X24_runs_survive_case_punctuation_and_line_breaks(self):
        self.assertBlocks("THE PROOFING *cabinet* | overheats,\nduring the LONG summer", "copied-run")

    def test_X24_near_copy_one_word_changed_in_eight(self):
        data = self.assertBlocks("The proofing cabinet overheats while the long summer afternoons last.", "copied-run")
        self.assertTrue(self.found(data, "copied-run")[0].get("near"))
        self.assertClean("The proofing cabinet overheats while the long winter mornings last.")

    def test_L90_L252_eight_word_quote_blocks_seven_passes(self):
        data = self.assertBlocks("She said we never know which café has paid for it.", "quote")
        self.assertEqual(self.found(data, "quote")[0]["source"], "calls/2026-09-10-discovery.md")
        self.assertClean("She said we never know which café has paid.")

    def test_X24_quote_and_run_on_one_stretch_report_the_quote(self):
        code, data = self.scan("Every tray of rolls sits waiting for the one working oven.")
        self.assertEqual([f["rule"] for f in data["findings"]], ["quote"])

    def test_L91_L92_X36_client_document_passes_conflict_row_blocks(self):
        self.assertClean("Rye loaves are scored by hand before proofing.")
        self.assertBlocks("Crates go back to the depot every Thursday morning.", "copied-run")

    def test_L93_snapshot_outside_its_block_is_internal(self):
        self.assertBlocks("The depot may refuse crates that come back unwashed.", "copied-run")

    def test_L94_L95_client_safe_blocks_are_exempt_from_runs(self):
        self.assertClean("The bakery wants one board for wholesale orders.")
        self.assertClean("The guide sends every crate back to the depot daily.")
        text = RECORD["calls/2026-09-10-discovery.md"].replace("<!-- client-safe:start -->\n", "").replace(
            "<!-- client-safe:end -->\n", "")
        write(self.root / "calls" / "2026-09-10-discovery.md", text)
        self.assertBlocks("The bakery wants one board for wholesale orders.", "copied-run")

    def test_L97_X09_malformed_marks_exempt_nothing_and_warn(self):
        text = RECORD["calls/2026-09-10-discovery.md"].replace("<!-- client-safe:end -->\n", "")
        write(self.root / "calls" / "2026-09-10-discovery.md", text)
        code, data = self.scan("The bakery wants one board for wholesale orders.")
        self.assertEqual(code, 1)
        warns = self.found(data, "copied-run", severity="warn")
        self.assertEqual((warns[0]["file"], warns[0]["line"]), ("calls/2026-09-10-discovery.md", 12))

    def test_L98_L99_X19_common_word_runs_are_ignored_ids_are_not(self):
        self.assertClean("They will get back to us on that soon.")
        self.assertBlocks("They will get back to us on 73100482.", "term", "id-patterns")
        self.assertGreater(len(lint.COMMON_WORDS), 950)
        self.assertEqual(lint.RUN_MIN_DISTINCT, 2)

    def test_X11_drafts_are_no_source(self):
        self.draft("The sourdough starter lives in the walk-in fridge overnight.", "old.md")
        self.assertClean("The sourdough starter lives in the walk-in fridge overnight.")


# 2.7 Exclusions and the paraphrase categories

class ParaphraseTest(Base):

    def test_L100_exclusions_in_every_payload_family(self):
        families = ("name", "description", "label", "seed", "markdown", "request_text")
        code, data = self.payload({family: "Flour from Brackwater Mills" for family in families}, "generic")
        self.assertEqual(sorted(f["field"] for f in self.found(data, "exclusion")), sorted("$." + f for f in families))
        self.assertEqual(self.payload({"seed": "Sample miller"})[0], 0)
        self.assertBlocks("Mail brackwater.mills@flour.example now.", "exclusion")

    def test_L103_X06_the_cue_groups_with_a_person_and_their_twins(self):
        planted = (("In practice Ysolde Marr is the real decision maker.", "assessment"),
                   ("We heard that Penwith is burnt out after the rush.", "emotional"),
                   ("The team said Penwith is in hospital this week.", "health-identity"),
                   ("If Ysolde Marr decides to quit, nobody can price a tray.", "departure"),
                   ("The bakers say Penwith never answers the phone.", "colleague-remark"),
                   ("Before the call Penwith talked about her golf weekend.", "personal-life"),
                   ("Our manager is stressed about it.", "emotional"))
        for text, group in planted:
            data = self.assertBlocks(text, "paraphrase", group)
        for text in ("In practice the finance team approves each order.", "We heard that the report is late again.",
                     "The team said the oven is in for repair this week.", "The phone never rings on Mondays.",
                     "Holiday cover runs until June.", "Before the call the office talked about the delivery week."):
            self.assertClean(text)


# 2.8 The structural assertion (the tool-category assertion is dropped, A30, R64)

class AssertionTest(Base):

    def test_L104_R64_the_split_figure_assertion_runs_in_payloads_too(self):
        code, data = self.payload({"markdown": "The proofer comes to 52 000 in all."})
        self.assertEqual(code, 2, data["findings"])  # A34 (R70): the client's own figure warns; an exclusion blocks
        self.assertTrue(self.found(data, "split-figure", severity="warn"), data["findings"])
        code, data = self.payload({"markdown": "The fee comes to 47 500 in all."})
        self.assertEqual(code, 1, data["findings"])
        self.assertTrue(self.found(data, "split-figure", severity="block"), data["findings"])

    def test_L107_R64_three_tool_categories_in_one_sentence_are_no_finding(self):
        # A30: the lint runs no tool-category check; the planted sentence of L107 is clean, and no rule is named for it.
        self.assertClean("The office keeps orders in a spreadsheet, wages in a payroll system and photos in a shared "
                         "drive.")
        self.assertNotIn("tool-categories", lint.RULES)


# 2.9 The allowlist, the warnings and the two non-removals

class AllowlistTest(Base):

    def test_L113_L121_X39_own_word_is_kept_with_a_caution(self):
        code, data = self.scan("Book a callback when a crate goes missing.")
        self.assertEqual(code, 2)
        caution = self.found(data, "term", "method", "caution")[0]
        self.assertEqual(caution["cleared_by"], "%s/solution/allowlist.md line 4" % S1)
        code, data = self.scan("Book a callback when a crate goes missing.", "d.md", S2)
        self.assertEqual(code, 1)

    def test_L119_L44_another_strands_allowlist_clears_nothing(self):
        write(self.root / S2 / "solution" / "allowlist.md", "## Allowlist\n- readiness [ok: yes]\n")
        self.assertEqual(self.scan("Check readiness first.")[0], 1)
        self.assertEqual(self.scan("Check readiness first.", "d.md", S2)[0], 2)

    def test_L114_to_L118_L264_Y06_rows_that_may_not_clear_leave_the_block_and_warn(self):
        rows = ["callback [ok: yes]", "184,260 [ok: yes]", "Quellmoor Advisory [ok: yes]", "P3 [ok: yes]",
                "[E] [ok: yes; class: markers]", "Brackwater Mills [ok: yes]", "Bearer Fx7kQ2mL9pR4tV8wZ3yB [ok: yes]",
                "the proofing cabinet overheats during the long summer afternoons [ok: yes]",
                "every tray of rolls sits waiting for the one working oven [ok: yes]"]
        write(self.root / S1 / "solution" / "allowlist.md", "## Allowlist\n" + "".join("- %s\n" % r for r in rows))
        text = ("184,260\nQuellmoor Advisory\nP3\n[E]\nBrackwater Mills\nBearer Fx7kQ2mL9pR4tV8wZ3yB\n"
                "The proofing cabinet overheats during the long summer afternoons\n"
                "Every tray of rolls sits waiting for the one working oven\n")
        code, data = self.scan(text)
        self.assertEqual(code, 1)
        blocked = {f["rule"] for f in self.found(data, severity="block")}
        self.assertTrue({"term", "exclusion", "credential", "copied-run", "quote"} <= blocked, blocked)
        # A34 (R70): the client's own figure is a warning now, which an allowlist row neither clears nor warns on
        self.assertTrue(self.found(data, "figure", severity="warn"), data["findings"])
        self.assertGreaterEqual(len(self.found(data, "allowlist", severity="warn")), 7)
        code, data = self.scan("The office keeps the order book.")
        self.assertEqual(code, 0)

    def test_X09_a_row_without_ok_clears_nothing_and_warns(self):
        write(self.root / S1 / "solution" / "allowlist.md", "## Allowlist\n- callback [date: 2026-09-12]\n- seed rows\n")
        code, data = self.scan("Book a callback.")
        self.assertEqual(code, 1)
        self.assertEqual(len(self.found(data, "allowlist", severity="warn")), 2)

    def test_X06_X10_a_paraphrase_cue_is_cleared_by_its_own_row(self):
        write(self.root / S1 / "solution" / "allowlist.md", "## Allowlist\n- hospital [ok: yes, a clinic client]\n")
        code, data = self.scan("The van takes Penwith to the hospital kitchen.")
        self.assertEqual(code, 2)
        self.assertTrue(self.found(data, "paraphrase", "health-identity", "caution"))

    def test_L120_L262_flagged_numbers_are_reported_and_the_file_kept(self):
        # A33 (R67): a record number of 100 or more, since the record's 34 staff is no figure any more
        write(self.root / "research" / "2026-09-04-vans.md", "- The bakery serves 340 regular customers.\n")
        rel = self.draft("The bakery runs with 340 cafes.")
        before = mc.sha256_file(self.root.joinpath(*rel.split("/")))
        code, data = self.lint("scan", rel)
        self.assertEqual((code, data["findings"][0]["rule"]), (2, "record-number"))
        self.assertEqual(mc.sha256_file(self.root.joinpath(*rel.split("/"))), before)


# 2.10 Reading the inputs

class ReaderTest(Base):

    def docx(self, parts, name="pack.docx"):
        rel = "%s/drafts/%s" % (S1, name)
        path = self.root.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(docx_bytes(parts))
        return rel

    def test_L124_to_L128_X35_docx_parts(self):
        clean = {"word/document.xml": body(["Order pack"]), "docProps/core.xml": core("The office"),
                 "docProps/app.xml": app("The bakery")}
        code, data = self.lint("scan", self.docx(clean))
        self.assertEqual(code, 0, data["findings"])
        self.assertEqual(data["inputs"][[i["file"] for i in data["inputs"]].index("%s/drafts/pack.docx" % S1)]
                         ["parts_read"], ["word/document.xml", "docProps/core.xml", "docProps/app.xml"])
        planted = (("word/document.xml", body(["Prepared by Quell", "moor Advisory"])),
                   ("docProps/core.xml", core("Orla Pennick")), ("docProps/app.xml", app("Quellmoor Advisory")),
                   ("word/header1.xml", body(["[I] draft"]).replace("w:document", "w:hdr")),
                   # A34 (R70): an exclusion figure, since the client's own 184,260 now warns
                   ("word/footnotes.xml", body(["Fee of 47,500."]).replace("w:document", "w:footnotes")),
                   ("docProps/custom.xml", '<?xml version="1.0"?><Properties xmlns:vt="http://schemas.openxmlformats.'
                    'org/officeDocument/2006/docPropsVTypes"><property name="Client"><vt:lpwstr>Brackwater Mills'
                    '</vt:lpwstr></property></Properties>'))
        for part, xml in planted:
            parts = dict(clean)
            parts[part] = xml
            code, data = self.lint("scan", self.docx(parts, "p.docx"))
            self.assertEqual(code, 1, part)
            self.assertIn(part, {f.get("part") for f in self.found(data, severity="block")})
        code, data = self.lint("scan", self.docx({"word/document.xml": body(["Bread &amp; rolls by Orla Pennick"])}))
        self.assertEqual(self.found(data, "term", "local")[0]["field"], "word/document.xml paragraph 1")

    def test_L129_L130_X35_bad_archives_are_exit_3(self):
        rel = "%s/drafts/fake.docx" % S1
        write(self.root.joinpath(*rel.split("/")), "plain text, not a zip")
        self.assertEqual(self.lint("scan", rel)[0], 3)
        self.assertEqual(self.lint("scan", self.docx({"docProps/core.xml": core("x")}))[0], 3)
        dtd = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><w:document %s/>' % W
        self.assertEqual(self.lint("scan", self.docx({"word/document.xml": dtd}))[0], 3)
        before = tree_hash(self.tmp)
        rel = self.docx({"word/document.xml": body(["Orders"]), "../../escape.xml": "<x/>"})
        before = tree_hash(self.tmp)
        self.assertEqual(self.lint("scan", rel)[0], 0)
        self.assertEqual(tree_hash(self.tmp), before)

    def test_X42_docx_limits(self):
        rel = self.docx({"word/document.xml": body(["Orders " * 300000])})
        with mock.patch.object(lint, "DOCX_RATIO_FLOOR", 1000), mock.patch.object(lint, "DOCX_RATIO", 10):
            code, data = self.lint("scan", rel)
        self.assertEqual(code, 3)
        with mock.patch.object(lint, "DOCX_MEMBER_LIMIT", 100):
            self.assertEqual(self.lint("scan", rel)[0], 3)

    def test_L131_L132_L204_unreadable_inputs_are_exit_3(self):
        write(self.root.joinpath(*PAYLOAD_REL.split("/")), '{"name": ')
        self.assertEqual(self.lint("payload", "--strand", "001", "--kind", "board", "--file", PAYLOAD_REL)[0], 3)
        rel = "%s/drafts/x.rtf" % S1
        write(self.root.joinpath(*rel.split("/")), "{\\rtf1 Orders}")
        self.assertEqual(self.lint("scan", rel)[0], 3)
        self.assertEqual(self.lint("scan", "%s/drafts" % S1)[0], 3)
        (self.root.joinpath(*rel.split("/"))).unlink()
        latin = self.root / S1 / "drafts" / "latin.txt"
        latin.write_bytes("Crème brûlée".encode("latin-1"))
        self.assertEqual(self.lint("scan", "%s/drafts/latin.txt" % S1)[0], 3)

    def test_L07_line_endings_and_byte_order_mark(self):
        text = "Quellmoor Advisory\nThe proofing cabinet overheats during the long summer.\nOrder 1,200 crates.\n"
        outputs = []
        for name, content in (("lf.md", text), ("crlf.md", text.replace("\n", "\r\n")), ("bom.md", "\ufeff" + text)):
            code, data = self.scan(content, name)
            outputs.append((code, [{k: v for k, v in f.items() if k != "file"} for f in data["findings"]]))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_X35_folder_scan_walks_skips_system_files_and_reads_json(self):
        self.draft("Orders.", "a.md")
        self.draft("Orders.", ".DS_Store")
        self.draft('{"name": "Ask Orla Pennick"}', "b.json")
        sub = self.root / S1 / "drafts" / "sub"
        write(sub / "c.txt", "Quellmoor")
        code, data = self.lint("scan")
        self.assertEqual(code, 1)
        files = [f["file"] for f in data["findings"]]
        self.assertIn("%s/drafts/b.json" % S1, files)
        self.assertIn("%s/drafts/sub/c.txt" % S1, files)
        write(self.root / S1 / "deliverables" / "handoff" / "h.md", "See [E] there.")
        self.assertIn("%s/deliverables/handoff/h.md" % S1, [f["file"] for f in self.lint("scan")[1]["findings"]])


# 2.11 The payload: generic walk (X22, Y08)

class PayloadTest(Base):

    def test_L133_L134_every_string_at_every_depth(self):
        code, data = self.payload({"steps": [{"text": "ok"}, {"extra": {"deep": ["fine", "Ask Orla Pennick"]}}]})
        self.assertEqual(self.found(data, "term", "local")[0]["field"], "$.steps[1].extra.deep[1]")
        self.assertIsNone(self.found(data, "term")[0]["line"])

    def test_X22_keys_numbers_and_json_inside_strings(self):
        code, data = self.payload({"Quellmoor": "notes", "waste": 184260, "odd key": "x",
                                   "column_values": json.dumps({"text_1": "Brackwater Mills"})})
        fields = {(f["rule"], f["field"]) for f in data["findings"]}
        self.assertIn(("term", "$.Quellmoor<key>"), fields)
        self.assertIn(("figure", "$.waste"), fields)
        self.assertIn(("exclusion", "$.column_values<json>.text_1"), fields)
        code, data = self.payload({"odd key": "Orla Pennick"})
        self.assertEqual(self.found(data, "term")[0]["field"], '$["odd key"]')

    def test_L158_an_unknown_kind_is_exit_3(self):
        write(self.root.joinpath(*PAYLOAD_REL.split("/")), '{"name": "Orders"}')
        self.assertEqual(self.lint("payload", "--strand", "001", "--kind", "spaceship", "--file", PAYLOAD_REL)[0], 3)
        for kind in lint.KINDS:
            self.assertEqual(self.lint("payload", "--strand", "001", "--kind", kind, "--file", PAYLOAD_REL)[0], 0)

    def test_L159_no_string_is_exit_0(self):
        code, data = self.payload({"count": 3, "flag": True, "none": None})
        self.assertEqual((code, data["findings"]), (0, []))

    def test_Y08_structural_ids(self):
        code, data = self.payload({"workspace_id": "73100482", "folder_id": 73100491, "item_ids": ["73100500", 73100501],
                                   "name": "Orders"})
        self.assertEqual((code, data["findings"]), (0, []))
        for change in ({"workspace_id": "91000023"}, {"notes_ref": "73100482"}, {"workspace_id": "073100482"},
                       {"description": "Copy of board 73100482"}, {"board_id": "7310 0482"},
                       {"column_values": json.dumps({"item_ids": [91000023]})}):
            code, data = self.payload(dict({"name": "Orders"}, **change))
            self.assertEqual(code, 1, change)
        code, data = self.payload({"workspace_id": "91000023"})
        self.assertEqual(data["findings"][0]["rule"], "seller-account")

    def test_X42_depth_and_size_limits(self):
        deep = "x"
        for _ in range(70):
            deep = [deep]
        self.assertEqual(self.payload({"a": deep})[0], 3)
        with mock.patch.object(lint, "PAYLOAD_LIMIT", 10):
            self.assertEqual(self.payload({"name": "Orders and more"})[0], 3)
        with mock.patch.object(lint, "TEXT_LIMIT", 10):
            self.assertEqual(self.scan("Orders and more orders.")[0], 3)

    def test_X42_long_lines_are_read_in_windows(self):
        self.assertBlocks("x" * 25000 + " Board 73100482 holds orders.", "term", "id-patterns")
        self.assertEqual(lint.windows(25000)[:2], [(0, 10000), (9800, 19800)])


# 2.12 SUMMARY.md and the client-safe block at intake (X37, X38)

class ModeTest(Base):

    def test_L165_X37_summary_mode_runs_runs_quotes_and_assertions_only(self):
        rel = "%s/SUMMARY.md" % S1
        write(self.root.joinpath(*rel.split("/")), "## Work\nThe proofing cabinet overheats during the long summer.\n"
                                                  "See P3 and [E] and Quellmoor.\n")
        code, data = self.lint("scan", rel)
        self.assertEqual((code, data["mode"], {f["rule"] for f in data["findings"]}), (1, "summary", {"copied-run"}))
        write(self.root.joinpath(*rel.split("/")), "## Work\nShe said we never know which café has paid for it.\n")
        code, data = self.lint("scan", rel)
        self.assertEqual({f["rule"] for f in data["findings"]}, {"quote"})
        write(self.root / S2 / "SUMMARY.md", "Rolls are glazed with beaten egg before the evening bake begins.\n")
        write(self.root.joinpath(*rel.split("/")), "Rolls are glazed with beaten egg before the evening bake.\n")
        self.assertEqual(self.lint("scan", rel)[0], 0)

    def test_L103_X38_client_safe_block_mode(self):
        rel = "calls/2026-09-29-review.md"
        write(self.root.joinpath(*rel.split("/")), "# Call\n\nPenwith is burnt out, said the notes.\n\n"
                                                  "<!-- client-safe:start -->\nWe heard that Penwith is burnt out.\n"
                                                  "<!-- client-safe:end -->\n")
        code, data = self.lint("scan", rel)
        self.assertEqual((code, data["mode"]), (1, "client-safe-block"))
        self.assertEqual([f["line"] for f in self.found(data, "paraphrase")], [6])
        write(self.root.joinpath(*rel.split("/")), "<!-- client-safe:start -->\nThe bakery wants one board for "
                                                  "wholesale orders and their delivery days.\n<!-- client-safe:end -->\n")
        self.assertEqual(self.lint("scan", rel)[0], 0)
        write(self.root.joinpath(*rel.split("/")), "# Call\nNo block here.\n")
        code, data = self.lint("scan", rel)
        self.assertEqual((code, data["findings"][0]["problem"]), (2, "no client-safe block in this file"))
        write(self.root.joinpath(*rel.split("/")), "<!-- client-safe:start -->\nText.\n")
        code, data = self.lint("scan", rel)
        self.assertEqual((code, data["error"]["field"]), (3, "line 1"))


# 2.15 Fail closed

class FailClosedTest(Base):

    def test_L202_an_undecodable_record_file_is_exit_3(self):
        (self.root / "calls" / "2026-09-11-notes.md").write_bytes(b"Notes \xff\xfe here\n")
        code, data = self.scan("Orders.")
        self.assertEqual((code, data["error"]["file"]), (3, "calls/2026-09-11-notes.md"))

    def test_L205_an_exception_inside_a_rule_is_exit_3(self):
        with mock.patch.object(lint.Check, "paraphrase", side_effect=RuntimeError("boom")):
            code, data = self.scan("Orders.")
        self.assertEqual((code, data["error"]["field"], data["error"]["problem"]), (3, "RuntimeError", "boom"))

    def test_L207_a_failed_read_at_every_position_is_exit_3(self):
        rel = self.draft("Orders for the office.")
        calls = []
        real = lint.read_bytes
        with mock.patch.object(lint, "read_bytes", side_effect=lambda p: calls.append(p) or real(p)):
            self.assertEqual(self.lint("scan", rel)[0], 0)
        self.assertGreater(len(calls), 8)
        for nth in range(1, len(calls) + 1):
            count = [0]

            def failing(path, nth=nth):
                count[0] += 1
                if count[0] == nth:
                    raise OSError("injected")
                return real(path)

            with mock.patch.object(lint, "read_bytes", side_effect=failing):
                code, data = self.lint("scan", rel)
            self.assertEqual(code, 3, nth)

    def test_L10_only_two_files_are_read_under_local(self):
        write(self.home / "local" / "sandbox-accounts.txt", "never-demo | x | y | 91000099\n")
        write(self.home / "personal-names-index.json", '{"hashes": []}')
        opened = []
        real = lint.read_bytes
        with mock.patch.object(lint, "read_bytes", side_effect=lambda p: opened.append(Path(p)) or real(p)):
            self.scan("Orders.")
        local = sorted(p.name for p in opened if p.parent == self.home / "local")
        self.assertEqual(local, ["leak-terms.txt", "settings.json"])
        self.assertFalse([p for p in opened if p.parent == self.home])

    def test_L208_a_block_and_an_unreadable_input_is_exit_3_with_the_findings(self):
        good = self.draft("Ask Orla Pennick.", "a.md")
        bad = self.draft("x", "b.md")
        self.root.joinpath(*bad.split("/")).write_bytes(b"\xff\xfe")
        code, data = self.lint("scan", good, bad)
        self.assertEqual((code, data["verdict"]), (3, "could-not-run"))
        self.assertTrue(self.found(data, "term", "local"))

    def test_X30_another_record_without_an_index_entry_stops_the_check(self):
        """Z02's interim stop is replaced by X30's coverage check; test_leak_wall.py proves the wall itself."""
        write(self.home / "clients" / "other-client" / "CLIENT.md", "---\nslug: \"other-client\"\n---\n")
        code, data = self.scan("Orders.")
        self.assertEqual((code, data["error"]["field"]), (3, "entries"))
        self.assertNotIn("other-client", json.dumps(data))
        self.assertEqual(self.payload({"name": "Orders"})[0], 3)
        rel = "%s/SUMMARY.md" % S1
        write(self.root.joinpath(*rel.split("/")), "Orders.\n")
        self.assertEqual(self.lint("scan", rel)[0], 0)
        shutil.rmtree(str(self.home / "clients" / "other-client"))
        write(self.home / "clients-index.json", '{"schema": "clients-index/1", "entries": {}}')
        self.assertEqual(self.scan("Orders.")[0], 3)  # an index that is not clients-index/1 in full
        write(self.home / "clients-index.json", '{"schema": "clients-index/1", "hash": "sha256-128", '
                                                '"normalisation": "wall/1", "entries": {}}')
        self.assertEqual(self.scan("Orders.")[0], 0)
        (self.home / "clients-index.json").unlink()
        write(self.home / "archive" / "closed-client" / "CLIENT.md", "---\n---\n")
        self.assertEqual(self.scan("Orders.")[0], 3)


# 2.16 Redaction written, not defaulted

class RedactionTest(Base):

    def test_L211_X23_spans_only_with_the_flag(self):
        text = "Notes\r\nAsk Orla Pennick now.\r\n"
        rel = self.draft(text)
        code, data = self.lint("scan", rel)
        self.assertNotIn("span", data["findings"][0])
        code, data = self.lint("scan", "--spans", rel)
        span = data["findings"][0]["span"]
        decoded = self.root.joinpath(*rel.split("/")).read_bytes().decode("utf-8-sig")
        self.assertEqual(decoded[span["start"]:span["end"]], "Orla Pennick")
        code, data = self.payload({"name": "Ask Orla Pennick"}, "board", "001", "--spans")
        self.assertEqual(data["findings"][0]["span"], {"start": 4, "end": 16})

    def test_L212_the_a11_fields_change_nothing(self):
        text = "Ask Orla Pennick about the 184,260 waste and the proofing cabinet overheats during the long summer."
        first = self.scan(text)[1]["findings"]
        client = (self.root / "CLIENT.md").read_text(encoding="utf-8").replace('"unanswered"', '"redact-names"')
        write(self.root / "CLIENT.md", client)
        self.assertEqual(self.scan(text)[1]["findings"], first)


# 2.17 The review's blocking findings, part 1 (leak-review.md F01 to F11; DECISIONS R entries)

class ReviewBlockingTest(Base):

    def docx(self, parts, name="pack.docx"):
        rel = "%s/drafts/%s" % (S1, name)
        path = self.root.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(docx_bytes(parts))
        return rel

    def test_F01_X25_a_figure_after_a_sign_a_dash_a_slash_or_a_quote_is_a_number(self):
        for text in ("The spend sits at 150k-184k for the year.", "Spend was 150,000–184,260 last year.",
                     "The waste cost is -184,260 on the ledger.", "The waste cost is −184,260.",
                     "The cost was '184k' last year.", "The cost was USD184,260 last year.", "Cost: EUR184k.",
                     "A c.184k overrun in waste costs.", "Waste cost per year/184,260.",
                     "A 184-thousand-dollar waste cost."):
            with self.subTest(text=text):
                self.assertOwnFigure(text + "\n")  # A34 (R70): read as a number as before, and warned
        self.assertBlocks("Fee band 40k-47k.\n", "exclusion", "figure")
        for data in ({"name": "Orders", "loss": -184260}, {"column_values": json.dumps({"numbers": "-184,260"})}):
            code, out = self.payload(data)
            self.assertEqual(code, 2, out["findings"])
            self.assertTrue(self.found(out, "figure", severity="warn"), out["findings"])
        self.assertClean("The trial ran 2026-09-01 to 2026-09-30 on v1.2.3, pages 4-6.\n")

    def test_F02_Y08_a_monday_id_as_a_json_number_outside_a_structural_key_blocks(self):
        for data in ({"name": "Orders", "notes_ref": 73100482}, {"name": "Orders", "refs": [73100482]},
                     {"name": "Orders", "board_id": 73100482.0}, {"name": "Orders", "board_id": -73100482}):
            with self.subTest(data=data):
                code, out = self.payload(data)
                self.assertEqual(code, 1, out["findings"])
                self.assertTrue(self.found(out, "term", "id-patterns", "block"), out["findings"])
        code, out = self.payload({"name": "Orders", "board_id": 73100482, "item_ids": [73100483]})
        self.assertEqual((code, out["findings"]), (0, []))

    def test_F03_X11_G57_a_snapshot_is_read_by_its_schema_quoted_or_not_and_a_newer_one_stops(self):
        snapshot = ('---\nschema: %s\nsource: "2026-09-20-proving"\n---\n# Snapshot\n\n'
                    "Analyst read: the proving room lead is overloaded and quietly resents the new owner.\n")
        draft = "Analyst read: the proving room lead is overloaded and quietly resents things.\n"
        rel = "inputs/2026-09-20-proving.md"
        for schema in ('"document-summary/1"', "document-summary/1", "'document-summary/1'"):
            with self.subTest(schema=schema):
                write(self.root.joinpath(*rel.split("/")), snapshot % schema)
                self.assertBlocks(draft, "copied-run")
        for schema in ('"document-summary/2"', "document-summary/3", '"call-summary/1"'):
            with self.subTest(schema=schema):
                write(self.root.joinpath(*rel.split("/")), snapshot % schema)
                code, out = self.scan(draft)
                self.assertEqual((code, out["error"]["file"], out["error"]["field"]), (3, rel, "schema"))
        write(self.root.joinpath(*rel.split("/")), "---\ntitle: notes\n---\n" + snapshot.split("---\n", 2)[2])
        self.assertBlocks(draft, "copied-run")  # front matter the lint cannot place never feeds the exemption

    def test_F04_X09_X33_an_exclusions_row_that_does_not_parse_is_exit_3(self):
        rel = "%s/solution/exclusions.md" % S1
        bodies = ("## Exclusions\n* Odell Quarry\n", "## Exclusions\n-Odell Quarry\n",
                  "## Exclusions\n1. Odell Quarry\n",
                  "### Exclusions\n- Odell Quarry\n", "## Exclusions (client asked)\n- Odell Quarry\n",
                  "## Exclusions\n- Odell Quarry [kind: name; note: from the call]\n",
                  "## Exclusions\n- 77,250 [knd: figure]\n",
                  "## Exclusions\nThe client asked us to leave out Odell Quarry.\n")
        for text in bodies:
            with self.subTest(text=text):
                write(self.root.joinpath(*rel.split("/")), "# Exclusions\n\n" + text)
                code, out = self.scan("Order from Odell Quarry this week.\n")
                self.assertEqual((code, out["error"]["file"]), (3, rel), out.get("error"))
                self.assertTrue(out["error"]["field"].startswith("line "), out["error"])
        write(self.root.joinpath(*rel.split("/")), "# Exclusions\n\n## Exclusions\n<!-- rows below -->\n\n"
                                                    "- Odell Quarry [kind: name; added: 2026-09-11]\n")
        self.assertBlocks("Order from Odell Quarry this week.\n", "exclusion")
        write(self.root / S1 / "solution" / "allowlist.md", "# Allowlist\n\nRows the user said yes to.\n\n"
                                                             "## Allowlist\n"
                                                             "* stray bullet\n- callback [ok: yes]\n")
        self.assertEqual(self.scan("Orders for the office.\n")[0], 0)

    def test_F05_X24_X28_html_entities_and_tags_never_break_a_match(self):
        for body_text, rule in (("<p>Order from Brackwater&nbsp;Mills this week.</p>", "exclusion"),
                                ("<p>Order from <b>Brackwater</b> Mills this week.</p>", "exclusion"),
                                ("<p>Set up by Quell&#109;oor.</p>", "term"),
                                # A34 (R70): the exclusion figure, since the client's own 184,260 now warns
                                ("<p>Fee cost 47,<br>500 a year.</p>", "split-figure"),
                                ("<p>Fee cost $47&#44;500 a year.</p>", "exclusion"),
                                ("<p>The proofing <b>cabinet</b> overheats during the <i>long</i> summer "
                                 "afternoons.</p>", "copied-run"),
                                ("The proofing cabinet<br>overheats during the long<br>summer afternoons.",
                                 "copied-run")):
            with self.subTest(body=body_text):
                code, out = self.payload({"body": body_text}, "doc")
                self.assertEqual(code, 1, out["findings"])
                self.assertTrue(self.found(out, rule, severity="block"), out["findings"])
        code, out = self.payload({"body": "<p>The board lists every <b>order</b> &amp; its day.</p>"}, "doc")
        self.assertEqual((code, out["findings"]), (0, []))
        for body_text, rule in (("<p>Waste cost 184,<br>260 a year.</p>", "split-figure"),
                                ("<p>Waste cost $184&#44;260 a year.</p>", "figure")):
            with self.subTest(body=body_text):  # A34 (R70): the client's own figure is found as before, and warns
                code, out = self.payload({"body": body_text}, "doc")
                self.assertEqual(code, 2, out["findings"])
                self.assertTrue(self.found(out, rule, severity="warn"), out["findings"])
        self.assertBlocks("Order from Brackwater&nbsp;Mills.\n", "exclusion")

    def test_F06_X24_a_quote_line_with_a_quoted_word_inside_keeps_its_whole_quote(self):
        write(self.root / "calls" / "2026-09-20-review.md", '---\nschema: "call-summary/1"\n---\n# Call\n\n'
              '<!-- client-safe:start -->\n[Q] Ysolde Marr: we lose the "rye" tickets on the bench almost every week\n'
              '<!-- client-safe:end -->\n')
        self.assertBlocks("We lose the rye tickets on the bench almost every week.\n", "quote")
        self.assertClean("We lose the rye tickets on Mondays.\n")

    def test_F07_X03_a_marker_written_straight_onto_a_word_blocks(self):
        for text in ("The planner is overloaded[I].", "[Q]Ysolde said the tickets go missing.", "See the note[E]s."):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "term", "markers")
        self.assertClean("See note E and part Q for the order list.\n")

    def test_F08_X35_docx_text_word_shows_is_read_and_parts_it_cannot_read_are_exit_3(self):
        ok = body(["Order pack"])
        rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship '
                'Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                'Target="file:///Users/x/clients/%s/calls/2026-09-10-discovery.md" TargetMode="External"/>'
                '</Relationships>' % SLUG)
        blocked = (
            {"word/document.xml": ok, "word/comments.xml": '<w:comments %s><w:comment w:id="0" w:author="Quellmoor '
             'Advisory" w:initials="QA"><w:p><w:r><w:t>Fine.</w:t></w:r></w:p></w:comment></w:comments>' % W},
            {"word/document.xml": body().replace("<w:body></w:body>", '<w:body><w:p><w:ins w:id="1" w:author='
                                                   '"Quellmoor Advisory"><w:r><w:t>Orders.</w:t></w:r></w:ins></w:p>'
                                                   '</w:body>')},
            {"word/document.xml": ok, "word/_rels/document.xml.rels": rels},
            {"word/document.xml": body().replace("<w:body></w:body>", '<w:body><w:p><w:fldSimple w:instr="HYPERLINK '
                                                   '&quot;https://quellmoor.example/x&quot;"><w:r><w:t>site</w:t></w:r>'
                                                   '</w:fldSimple></w:p></w:body>')},
            {"word/document.xml": body().replace("<w:body></w:body>", '<w:body><w:p><w:r><w:drawing><wp:inline '
                                                   'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/'
                                                   'wordprocessingDrawing"><wp:docPr id="1" name="Picture 1" descr='
                                                   '"Logo of Quellmoor Advisory"/></wp:inline></w:drawing></w:r></w:p>'
                                                   '</w:body>')})
        for parts in blocked:
            with self.subTest(parts=sorted(parts)):
                code, out = self.lint("scan", self.docx(parts))
                self.assertEqual(code, 1, out["findings"])
        for parts in ({"word/document.xml": body().replace("<w:body></w:body>", '<w:body><w:altChunk r:id="rId5" '
                                                             'xmlns:r="urn:r"/></w:body>'), "word/afchunk.docx": "x"},
                      {"word/document.xml": ok, "word/afchunk.htm": "<p>Quellmoor</p>"},
                      {"word/document.xml": ok, "word/embeddings/Sheet1.xlsx": "x"}):
            with self.subTest(parts=sorted(parts)):
                self.assertEqual(self.lint("scan", self.docx(parts))[0], 3)
        twin = {"word/document.xml": ok, "word/comments.xml": '<w:comments %s><w:comment w:id="0" w:author="The '
                'office"><w:p><w:r><w:t>Fine.</w:t></w:r></w:p></w:comment></w:comments>' % W}
        self.assertEqual(self.lint("scan", self.docx(twin))[0], 0)

    def test_R08_another_file_inside_stops_in_plain_words_and_a_picture_passes(self):
        ok = body().replace("<w:body></w:body>", "<w:body><w:p><w:r><w:t>Orders.</w:t></w:r></w:p></w:body>")
        picture = body().replace("<w:body></w:body>", '<w:body><w:p><w:r><w:drawing><wp:inline xmlns:wp="http://'
                                 'schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><wp:docPr id="1" '
                                 'name="Picture 1" descr="A delivery van"/></wp:inline></w:drawing></w:r></w:p>'
                                 '</w:body>')
        rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship '
                'Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                'Target="media/image1.png"/></Relationships>')
        for parts in ({"word/document.xml": picture, "word/_rels/document.xml.rels": rels,
                       "word/media/image1.png": "\x89PNG", "word/media/image2.emf": "x"},
                      {"word/document.xml": ok, "word/printerSettings/printerSettings1.bin": "x"}):
            with self.subTest(parts=sorted(parts)):
                code, out = self.lint("scan", self.docx(parts))
                self.assertEqual(code, 0, out)
        for parts in ({"word/document.xml": ok, "word/embeddings/oleObject1.bin": "x"},
                      {"word/document.xml": ok, "word/embeddings/Report.docx": "x"},
                      {"word/document.xml": body().replace("<w:body></w:body>", '<w:body><w:altChunk r:id="rId5" '
                                                           'xmlns:r="urn:r"/></w:body>')}):
            with self.subTest(parts=sorted(parts)):
                code, out = self.lint("scan", self.docx(parts))
                self.assertEqual(code, 3)
                self.assertFalse(out["ok"])
                self.assertEqual(out["error"]["problem"], "this document has another file inside it")
                self.assertEqual(out["error"]["expected"],
                                 "take that file out and add it as its own input, then run this again")

    def test_F09_X35_a_folder_linked_into_drafts_is_walked_or_stops(self):
        shared = self.root / S1 / "shared"
        write(shared / "part.md", "Quellmoor set this up.\n")
        (self.root / S1 / "drafts").mkdir(parents=True, exist_ok=True)
        outside = self.tmp / "outside"
        write(outside / "x.md", "Orders.\n")
        try:
            os.symlink(str(shared), str(self.root / S1 / "drafts" / "linked"))
            os.symlink(str(outside), str(self.root / S1 / "drafts" / "away"))
        except (OSError, NotImplementedError) as exc:
            self.skipTest("this system makes no symbolic links: %s" % exc)
        code, out = self.lint("scan")
        self.assertEqual(code, 3, out)
        os.unlink(str(self.root / S1 / "drafts" / "away"))
        code, out = self.lint("scan")
        self.assertEqual(code, 1)
        self.assertIn("%s/shared/part.md" % S1, [f["file"] for f in out["findings"]])

    def test_F10_X15_Y04_credentials_just_outside_the_six_shapes(self):
        for text in ("API key: 9f8e7d6c5b4a39281706f5e4d3c2b1a0", "The password is Tilework42 for the portal.",
                     "pw: Tilework42", "passphrase = blue-otter-lamp", "Login: depot.admin / Tilework42",
                     "Password:\nTilework42", "https://git.example/api?private_token=Ab12Cd34Ef56Gh78",
                     "Authorization: Basic dXNlcjpwYXNz", "secret_key: Tilework42",
                     "Key: 9F8E7D6C5B4A39281706F5E4D3C2B1A0"):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "credential")
        for text in ("Login: use your work email.", "The password is reset every month.", "Basic training starts soon.",
                     "The token is valid for a day.", "Credentials: stored in the office safe.",
                     "See https://x.example/a?sort=created"):
            with self.subTest(text=text):
                code, out = self.scan(text + "\n")
                self.assertFalse(self.found(out, "credential"), out["findings"])

    def test_F11_X24_X28_an_excluded_or_seller_name_broken_by_any_mark_blocks(self):
        for text, rule in (("We met Brackwater **Mills** today.", "exclusion"), ("We met Brackwater (Mills) today.",
                                                                                 "exclusion"),
                           ("We met Brackwater's Mills today.", "exclusion"), ("Kept in Margin Desk **Internal**.",
                                                                               "seller-account"),
                           ("Kept in Margin's Desk Internal.", "seller-account"), ("Brackwater: Mills.", "exclusion")):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", rule)
        self.assertClean("Brackwater is a river, and old mills line it.\n", 0)


# 2.18 The review's should-fix findings and the cheap notes, part 1 (leak-review.md F12 to F41)

class ReviewShouldFixTest(Base):

    def test_F12_X28_invisible_characters_look_alikes_and_line_separators(self):
        for text, rule in (("We met Brackㅤwater Mills today.", "exclusion"), ("Written with clㅤaude code.", "term"),
                           ("Built by master buılder.", "term"), ("Sent to Tarrօw Feeds.", "exclusion"),
                           ("We met Brackwatᴇr Mills today.", "exclusion"), ("password：Tilework42", "credential"),
                           ("pаssword: Tilework42", "credential"), ("Saved in calls＼2026-09-01.md", "term"),
                           ("Fee cost 47 500 a year.", "split-figure")):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", rule)
        # A34 (R70): the client's own figure split by a line separator is found as before, and warns
        self.assertOwnFigure("Waste cost 184 260 a year.\n", "split-figure")
        self.assertClean("The ㅤboard lists orders.\n")

    def test_F13_X24_X32_a_hyphenated_row_matches_its_words_spaced(self):
        for text, rule in (("Check the run sheet for Friday.", "term"), ("Keep the if asked list short.", "term"),
                           ("Copy the client safe block.", "term"), ("Internal build file: never client facing.",
                                                                     "internal-note")):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", rule)
        self.assertClean("Stand on the Q side of the hall.\n")

    def test_F14_X24_a_near_copy_with_a_word_dropped_or_added_blocks(self):
        write(self.root / "research" / "2026-09-03-night.md", "# Night\n\nThe night baker reweighs every batch of rye "
                                                                "dough by hand before the ovens are lit at four.\n")
        for text in ("The night baker reweighs batch of rye dough hand before the ovens lit at four.",
                     "The night baker now reweighs every batch of the rye dough by hand before all the ovens are lit."):
            with self.subTest(text=text):
                data = self.assertBlocks(text + "\n", "copied-run")
                self.assertTrue(any(f.get("near") for f in self.found(data, "copied-run")), data["findings"])
        self.assertClean("The night baker checks the ovens before the shift.\n")

    def test_F15_X24_X36_a_block_held_quote_with_one_word_changed_or_dropped_blocks(self):
        for text in ("We never know which café has settled for last month.",
                     "We never know which café paid for last month."):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "quote")
        self.assertClean("We never know which day the van comes.\n")

    def test_F16_X03_record_paths_the_shipped_rows_now_cover(self):
        for text in ("See research/2026-09-02-brief.md for more.", "See solution/exclusions.md.",
                     "Saved under drafts/ for now.", "deliverables/handoff/close-out.md", "Logged in meetings.md.",
                     "Listed in allowlist.md.", "%USERPROFILE%\\monday-builder\\local\\",
                     "Under $HOME/monday-builder."):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "term", "id-patterns")
        self.assertClean("The solution/approach is simple and we go live/active soon.\n")

    def test_F17_X32_a_th_spelling_heard_as_t_is_a_sound_alike(self):
        settings = json.loads(json.dumps(SETTINGS))
        settings["firm"] = {"name": "Thymbel", "renderings": []}
        write(self.home / "local" / "settings.json", json.dumps(settings))
        write(self.home / "local" / "leak-terms.txt", "class: firm\nwhitelist: thimble\n")
        for text in ("Timbel set this up.", "Tymbol set this up.", "Timble set this up."):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "phonetic")
        self.assertClean("The thimble stays by the timber frame.\n")

    def test_F18_X40_internal_notes_in_their_common_spellings(self):
        for text in ("SPEAKER_00: we lose the tickets.", "Speaker A: we lose the tickets.",
                     "Draft notes, not client-facing.",
                     "For internal use only.", "Not for clients.",
                     "---\ntitle: Discovery\nschema: call-summary/1\n---\nBody"):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "internal-note")
        self.assertClean("The speaker at the front desk greets a customer.\n")

    def test_F19_X09_an_allowlist_ok_that_says_no_clears_nothing(self):
        allow = self.root / S1 / "solution" / "allowlist.md"
        for ok in ("no", "pending", "not yet, ask the user", "TBC"):
            with self.subTest(ok=ok):
                write(allow, "# Allowlist\n\n## Allowlist\n- readiness [ok: %s]\n" % ok)
                code, data = self.scan("The readiness check is done.\n")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, "allowlist", severity="warn"), data["findings"])
        write(allow, "# Allowlist\n\n## Allowlist\n- readiness [ok: yes, the bakery's word]\n")
        self.assertEqual(self.scan("The readiness check is done.\n")[0], 2)

    def test_F20_X09_X38_a_client_safe_mark_written_slightly_wrong_is_exit_3(self):
        rel = "calls/2026-09-20-review.md"
        for start, end in (("<!--client-safe:start-->", "<!--client-safe:end-->"),
                           ("<!-- Client-safe:start -->", "<!-- Client-safe:end -->"),
                           ("<!-- client‐safe:start -->", "<!-- client‐safe:end -->")):
            with self.subTest(start=start):
                write(self.root.joinpath(*rel.split("/")), "# Call\n\n%s\nWe heard Penwith is burnt out.\n%s\n" %
                      (start, end))
                code, data = self.lint("scan", rel)
                self.assertEqual((code, data["error"]["file"]), (3, rel))
                write(self.root.joinpath(*rel.split("/")), "# Call\n\n%s\nOrders.\n%s\n" % (start, end))
                code, data = self.scan("Orders.\n")
                self.assertTrue([f for f in data["findings"] if f["file"] == rel and f["severity"] == "warn"], data)
        write(self.root.joinpath(*rel.split("/")), "# Call\n\n<!-- client-safe:start -->\nOrders.\n"
                                                  "<!-- client-safe:end -->\n")
        self.assertEqual(self.lint("scan", rel)[0], 0)

    def test_F21_X33_X42_local_patterns_that_can_run_for_a_very_long_time_are_exit_3(self):
        for row in ("re: (?:(?:a+))+b", "re: (a|aa)+b", "re: ((ab)*c)+", "re: (?:x|y+)*z"):
            with self.subTest(row=row):
                write(self.home / "local" / "leak-terms.txt", "class: codes\n%s\n" % row)
                code, data = self.scan("a" * 34 + "\n")
                self.assertEqual((code, data["error"]["field"]), (3, "line 2"))
        for row in ("re: \\d{1,3}(?:,\\d{3})+", "re: (?:PO|INV)-\\d+", "re: (?:[a-z]{2}-)?\\d{4}"):
            with self.subTest(row=row):
                write(self.home / "local" / "leak-terms.txt", "class: codes\n%s\n" % row)
                self.assertNotEqual(self.scan("Orders.\n")[0], 3)

    def test_F22_X25_a_figure_split_at_its_thousands_comma(self):
        for text in ("The waste cost was 184,\n260 last year.", "The waste cost was 184, 260 last year."):
            with self.subTest(text=text):
                self.assertOwnFigure(text + "\n", "split-figure")  # A34 (R70): found as before, and warned
        self.assertBlocks("The fee was 47, 500 last year.\n", "split-figure")  # an exclusion figure still blocks
        code, data = self.scan("We need 4, 100 and 250 crates.\n")
        self.assertFalse(self.found(data, severity="block"), data["findings"])

    def test_F23_Z07_a_scan_with_nothing_to_check_is_exit_3(self):
        shutil.rmtree(str(self.root / S1 / "drafts"), ignore_errors=True)
        code, data = self.lint("scan")
        self.assertEqual((code, data["error"]["field"]), (3, "path"))
        (self.root / S1 / "drafts").mkdir(parents=True)
        self.assertEqual(self.lint("scan")[0], 3)
        write(self.root / S1 / "draft" / "a.md", "Quellmoor set this up.\n")
        self.assertEqual(self.lint("scan")[0], 3)
        self.draft("Orders.\n")
        self.assertEqual(self.lint("scan")[0], 0)

    def test_F24_X06_paraphrase_cues_in_ordinary_process_text_pass(self):
        for text in ("The item owner signs off the quote before it moves to Done.",
                     "The site manager is the approver for refunds over the limit.",
                     "A long lead time is a risk for the install date.",
                     "The owner wants English oak shelves and American walnut doors.",
                     "The supervisor sets holiday cover in the rota each month.",
                     "If a fitter is sick, the supervisor reassigns the job.",
                     "The owner pays by Visa or bank transfer."):
            with self.subTest(text=text):
                code, data = self.scan(text + "\n")
                self.assertFalse(self.found(data, "paraphrase"), data["findings"])
        for text in ("We heard that Ysolde is burnt out.", "Her manager is burnt out after the move.",
                     "Ysolde's manager quit last week.", "The approver, Penwith, is hostile to the change."):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "paraphrase")

    def test_F25_R64_a_full_stop_after_an_abbreviation_ends_no_sentence(self):
        # R24 kept by R64 for every rule that reads sentences: the cost cue of a number and the paraphrase rule.
        # A33 (R67): a cost figure of 100 to 999, since the record's 27 an hour is below 100 and no figure any more.
        write(self.root / "research" / "2026-09-04-vans.md", "- A delivery van costs 240 an hour to hire.\n")
        for text in ("The tray cost, e.g. 240 in all.", "The tray cost, i.e. 240 in all.", "The tray cost, approx. 240 "
                     "in all.", "The tray cost vs. 240 in all.", "The tray cost, the oven etc. 240 in all."):
            with self.subTest(text=text):
                self.assertOwnFigure(text + "\n")  # A34 (R70): the cost cue still reaches it, and it warns
        code, data = self.scan("The tray cost. 240 in all.\n")
        self.assertEqual((code, [f["rule"] for f in data["findings"]]), (2, ["record-number"]))
        self.assertBlocks("We heard that, e.g. Penwith is burnt out.\n", "paraphrase")
        self.assertClean("We heard that. Penwith is burnt out.\n")

    def test_F26_Y08_a_structural_id_inside_a_column_values_string_passes(self):
        for values in ({"board_relation_1": {"item_ids": [73100483]}},
                       {"person": {"personsAndTeams": [{"id": 73100484, "kind": "person"}]}}):
            with self.subTest(values=values):
                code, data = self.payload({"board_id": 73100482, "item_name": "Job A",
                                           "column_values": json.dumps(values)}, "item_batch")
                self.assertEqual((code, data["findings"]), (0, []))
        for values in ({"text_1": "ref 73100485"}, {"numbers": 73100486}, {"item_ids": [91000023]}):
            with self.subTest(values=values):
                code, data = self.payload({"board_id": 73100482, "column_values": json.dumps(values)}, "item_batch")
                self.assertEqual(code, 1, data["findings"])

    def test_F27_Z03_Y02_long_numbers_that_are_not_ids(self):
        for text in ("Depot at 51.50735095, -0.12775829.", "Report 20261017 attached.", "PO-20261017 ships Friday."):
            with self.subTest(text=text):
                code, data = self.scan(text + "\n")
                self.assertFalse(self.found(data, severity="block"), data["findings"])
        code, data = self.scan("Report 20261017 attached.\n")
        self.assertTrue(self.found(data, "split-figure", severity="warn"), data["findings"])
        for text in ("Board 73100482 holds orders.", "Ref 20261399 here.", "Ref 18991231 here."):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "term", "id-patterns")
        code, data = self.payload({"name": "Orders", "due": 20261017})
        self.assertFalse(self.found(data, severity="block"), data["findings"])

    def test_F29_X35_a_utf16_part_with_a_dtd_is_exit_3(self):
        xml = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY a "b">]><w:document %s/>' % W
        rel = "%s/drafts/u.docx" % S1
        path = self.root.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(docx_bytes({"word/document.xml": xml.encode("utf-16")}))
        self.assertEqual(self.lint("scan", rel)[0], 3)

    def test_F31_F32_X34_only_a_real_link_masks_an_id(self):
        for text in ("See [the board](boards/73100482).", "See https://x.example/a,73100482 now.",
                     "See https://x.example/a|73100482 now."):
            with self.subTest(text=text):
                self.assertBlocks(text + "\n", "term", "id-patterns")
        self.assertClean("See [the board](https://x.example/boards/73100482).\n")

    def test_F39_X04_settings_read_strictly(self):
        for change in ({"never_show_workspaces": [{"id": "  ", "name": "Margin Desk Internal"}]},
                       {"default_build_account": {"slug": "--", "id": "91000017"}}):
            with self.subTest(change=change):
                write(self.home / "local" / "settings.json", json.dumps(dict(SETTINGS, **change)))
                self.assertEqual(self.scan("Orders.\n")[0], 3)
        text = json.dumps(SETTINGS)
        write(self.home / "local" / "settings.json", text[:-1] + ', "github_account": "other"}')
        self.assertEqual(self.scan("Orders.\n")[0], 3)

    def test_F40_X35_header_part_names_in_any_case(self):
        rel = "%s/drafts/h.docx" % S1
        path = self.root.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(docx_bytes({"word/document.xml": body(["Orders"]),
                                     "word/Header2.xml": body(["Quellmoor"]).replace("w:document", "w:hdr")}))
        self.assertEqual(self.lint("scan", rel)[0], 1)

    def test_F41_X03_a_double_percent_encoding_is_decoded(self):
        self.assertBlocks("See https://files.example/x?f=calls%252F2026.md\n", "term", "id-patterns")


# 2.18 A33: the lint loosened where demo 1 blocked for nothing (R66 to R69)

def blueprint_text(bodies):
    """The sixteen numbered sections in the pinned shape (R49, R52), each with its body from `bodies`."""
    return "# Blueprint\n" + "".join("\n## %d. %s\n%s\n" % (n, lint.SECTION_TITLES[n - 1], bodies.get(n, ""))
                                     for n in range(1, 17))


class A33Test(Base):

    def blueprint(self, bodies):
        write(self.root / S1 / "solution" / "blueprint.md", blueprint_text(bodies))
        return self.lint("blueprint", "--strand", "001")

    # R66: ids that are arguments are not text

    def test_A33_R66_a_key_that_names_an_id_is_structural_and_a_word_ending_in_the_letters_is_not(self):
        for key in ("parentFolderId", "board_folder_id", "parent_container_id", "parentItemId", "accountProductId",
                    "position_object_id", "BOARD_ID", "boardIDs", "item_IDS", "Id", "IDS", "column_7Id"):
            self.assertTrue(lint.structural_key(key), key)
        for key in ("paid", "valid", "grid", "android", "squid", "idea", "identity", "idx", "PAID", "BOARDID",
                    "notes_ref", "id_note", "parent id"):
            self.assertFalse(lint.structural_key(key), key)
        self.assertTrue(all(lint.ID_KEY.fullmatch(key) for key in lint.STRUCTURAL_ID_KEYS))  # the rule holds the list

    def test_A33_R66_ids_under_id_keys_and_board_ids_as_object_keys_pass(self):
        code, data = self.payload({
            "name": "Orders", "parentFolderId": "73100482", "board_folder_id": 73100483,
            "parent_container_id": "73100484", "parentItemId": 73100485, "accountProductId": "73100486",
            "position_object_id": "73100487", "BOARD_ID": "73100488", "boardIDs": ["73100489", 73100490],
            "settings": json.dumps({"x_axis_columns": {"73100491": ["status"]},
                                    "displayed_linked_columns": {"73100492": ["numbers", "date4"]}}),
            "mirror": {"73100493": {"columns": ["status"]}}}, "widget")
        self.assertEqual((code, data["findings"]), (0, []))

    def test_A33_R66_an_id_written_as_text_still_blocks(self):
        for change in ({"name": "Board 73100482"}, {"description": "Copy of 73100482"}, {"label": "73100482"},
                       {"message": "Moved to folder 73100482"}, {"paid": "73100482"}, {"valid": 73100482},
                       {"parentFolderId": "Folder 73100482"}, {"073100482": ["status"]},
                       {"73100491": "Mirror of board 73100482"}, {"settings": {"73100491": {"note": "73100482"}}}):
            with self.subTest(change=change):
                code, data = self.payload(dict({"name": "Orders"}, **change), "widget")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, "term", "id-patterns", "block"), data["findings"])
        for change in ({"parentFolderId": "91000023"}, {"91000023": ["status"]}):
            with self.subTest(change=change):  # the user's own account ids block under any key (X06, Y08)
                code, data = self.payload(dict({"name": "Orders"}, **change), "widget")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, "seller-account", severity="block"), data["findings"])

    # R67: small numbers are not client figures

    def demo_record(self):
        """A readiness line puts "ten" beside a cost word, as demo 1's did: the cause of its three blocks."""
        write(self.root / S1 / "readiness.md", "\n".join([
            "# Readiness", "", "## Goals",
            "- G1 Keep the cafe chain at the spring renewal: ten working days from order to delivery.", "",
            "## Entities", "- rush order (three-day turnaround, charged double); parent: order", ""]))

    def test_A33_R67_the_cause_a_word_number_beside_a_cost_word_was_a_figure_give_or_take_its_last_digit(self):
        line = "Keep the cafe chain at the spring renewal: ten working days from order to delivery."
        ten = [n for n in lint.parse_numbers(lint.fold(line), line) if n.value == 10]
        self.assertTrue(ten and ten[0].cue, ten)  # "renewal" is a cost cue (X25)
        self.assertEqual(ten[0].precision, 10)  # so the figure 10 met every number from 1 to 19
        self.assertTrue(ten[0].matches(1, 1) and ten[0].matches(2, 1))
        self.assertLess(ten[0].value, lint.SMALL_FIGURE)  # A33: it is no client figure now

    def test_A33_R67_demo_1s_three_texts_pass_in_the_blueprint_and_in_a_payload(self):
        self.demo_record()
        texts = ("Sections and labs are values on the rows, not separate boards, so one board serves every lab.",
                 "| Column | Type | Values |\n|---|---|---|\n| Lab | status | Main lab, Satellite 1, Satellite 2 |\n"
                 "| Analyses | connect boards, two-way | links to the order's rows |")
        code, data = self.blueprint({1: texts[0], 11: texts[1]})
        self.assertEqual((code, data["findings"]), (0, []))
        for text in texts:
            with self.subTest(text=text):
                code, data = self.payload({"description": text})
                self.assertEqual((code, data["findings"]), (0, []))
        code, data = self.payload({"markdown": "The day rate is a hundred."})  # 100 give or take 100 met 10 before
        self.assertFalse(self.found(data, "figure"), data["findings"])
        self.assertEqual((code, [f["rule"] for f in data["findings"]]), (2, ["number"]))

    def test_A33_R67_numbers_below_100_in_digits_or_words_never_match_nor_warn(self):
        self.demo_record()
        for text in ("Each driver earns 27 an hour.", "Pay $27 for it.", "A tray takes 27 minutes.",
                     "The bakery has 34 staff.", "Ten working days, charged double.", "It costs ninety-nine.",
                     "The fee is 99.5 a crate.", "Rush orders cost three times as much."):
            with self.subTest(text=text):
                self.assertClean(text + "\n")
        self.assertOwnFigure("The margin is 31%.\n")  # a percentage keeps its own rule; A34 (R70): it warns
        code, data = self.scan("About 15% of loaves.\n")
        self.assertEqual((code, [f["rule"] for f in data["findings"]]), (2, ["number"]))
        code, data = self.scan("The bakery bought 1,200 crates.\n")
        self.assertEqual((code, [f["rule"] for f in data["findings"]]), (2, ["number"]))

    def test_A33_R67_a_client_figure_of_100_or_more_still_blocks_in_every_form(self):
        # A34 (R70): the client's own figure of 100 or more is still matched in every form, and now warns
        self.demo_record()
        write(self.root / "research" / "2026-09-03-rush.md", "- The rush desk's overtime costs 4,500 a month.\n"
                                                             "- Each rush order costs 150 extra.\n")
        for form in ("4500", "4,500", "4.5k", "$4.5k", "four and a half thousand", "four thousand five hundred",
                     "4 500"):
            with self.subTest(form=form):
                code, data = self.payload({"markdown": "Overtime runs at %s." % form})
                self.assertEqual(code, 2, data["findings"])
                self.assertTrue(self.found(data, "figure", severity="warn") or
                                self.found(data, "split-figure", severity="warn"), data["findings"])
                code, data = self.blueprint({1: "Overtime runs at %s a month." % form})
                self.assertEqual(code, 2, data["findings"])
        self.assertOwnFigure("The rush fee is 150.\n")
        self.assertEqual(lint.words_number("four and a half thousand".split()), (4500, 5))
        self.assertEqual(lint.words_number("two and a half million".split()), (2500000, 5))
        self.assertEqual(lint.words_number("four and a half".split()), (4, 1))

    # R68: the blueprint's prose meets no copied-run or quote rule; every payload still does

    def test_A33_R68_a_restated_run_and_quote_pass_the_blueprint_and_block_a_payload(self):
        write(self.root / S1 / "readiness.md", "# Readiness\n\n## Entities\n- Every tray is logged at the proofing "
                                               "bench before the oven list is printed.\n")
        run, own, quote = ("Every tray is logged at the proofing bench before the oven list is printed.",
                           "Counts down each tray's second proof at the bench.",
                           "Every tray of rolls sits waiting for the one working oven.")
        bodies = {1: run, 3: quote, 11: "| Column | Type | What it holds |\n|---|---|---|\n| Proof timer | timeline | "
                  "counts down each tray's second proof at the bench |",
                  16: "| Key | Element | Note |\n|---|---|---|\n| B1.C4 | Proof timer | counts down each tray's "
                      "second proof at the bench |"}
        code, data = self.blueprint(bodies)
        self.assertEqual((code, data["findings"]), (0, []))
        for text, rule, source in ((run, "copied-run", "%s/readiness.md" % S1),
                                   (own, "copied-run", "%s/solution/blueprint.md" % S1),
                                   (quote, "quote", "calls/2026-09-10-discovery.md")):
            with self.subTest(text=text):
                code, data = self.payload({"description": text})
                self.assertEqual(code, 1, data["findings"])
                self.assertEqual([f["source"] for f in self.found(data, rule, severity="block")], [source])

    def test_A33_R68_the_blueprint_keeps_the_firm_markers_credentials_ids_and_record_paths(self):
        for text, rule, cls in (("Built for Quellmoor Advisory.", "term", "firm"),
                                ("Check this [X].", "term", "markers"), ("password: Tilework42", "credential", None),
                                ("Board 73100482 holds orders.", "term", "id-patterns"),
                                ("See research/2026-09-02-brief.md first.", "term", "id-patterns"),
                                ("Orders from Brackwater Mills.", "exclusion", None),
                                # A34 (R70): the exclusion figure, since the client's own 184,260 now warns
                                ("The fee is 47,500.", "exclusion", None)):
            with self.subTest(text=text):
                code, data = self.blueprint({2: text})
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, rule, cls, "block"), data["findings"])

    # R69: sample rows raise no number warnings, and every other rule still runs on them

    def test_A33_R69_an_item_batch_raises_no_number_warning(self):
        write(self.root / "research" / "2026-09-03-volumes.md", "- The bakery delivers 1,350 loaves a week.\n")
        rows = {"board_id": 73100482, "items": [
            {"item_name": "Order 1042",
             "column_values": json.dumps({"numbers": "1350", "text_1": "Batch 2210, 480 rolls", "numbers4": 1180.5})},
            {"item_name": "Order 1043", "column_values": json.dumps({"numbers": 2875, "text_1": "About 15% rye"})}]}
        code, data = self.payload(rows, "item_batch")
        self.assertEqual((code, data["findings"]), (0, []))
        code, data = self.payload(rows, "board")  # the same values anywhere else still warn
        self.assertEqual(code, 2, data["findings"])
        self.assertEqual({f["rule"] for f in data["findings"]}, {"number", "record-number"})

    def test_A33_R69_every_other_rule_still_runs_on_an_item_batch(self):
        # A34 (R70): the client's own cost figure, 184260, warns on a sample row now (A34Test), so it is not listed
        for value, rule, cls in (("Quellmoor order", "term", "firm"), ("ref 73100485", "term", "id-patterns"),
                                 ("Brackwater Mills", "exclusion", None), ("47500", "exclusion", None),
                                 ("password: Tilework42", "credential", None),
                                 ("Check [X]", "term", "markers"), ("47 500", "split-figure", None),
                                 ("The proofing cabinet overheats during the long summer afternoons.", "copied-run",
                                  None)):
            with self.subTest(value=value):
                code, data = self.payload({"board_id": 73100482, "items": [
                    {"item_name": "Order", "column_values": json.dumps({"text_1": value})}]}, "item_batch")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, rule, cls, "block"), data["findings"])


class A34Test(Base):
    """A34 (R70): a client's own figure of 100 or more warns in its own build; the wall and the exclusions block."""

    FORMS = ("4500", "4,500", "4.5k", "$4.5k", "four and a half thousand", "four thousand five hundred", "4 500",
             "| Overtime | 4 | 500 |")

    def setUp(self):
        super().setUp()
        write(self.root / "research" / "2026-09-03-rush.md", "- The rush desk's overtime costs 4,500 a month.\n"
                                                             "- The loaded rate on the rush desk is 157 an hour.\n")

    def blueprint(self, bodies):
        write(self.root / S1 / "solution" / "blueprint.md", blueprint_text(bodies))
        return self.lint("blueprint", "--strand", "001")

    def assertWarns(self, code, data, rules=("figure", "split-figure")):
        """Exit 2, no block, and the client's own figure shown as a warning under its own rule."""
        self.assertEqual(code, 2, data["findings"])
        self.assertEqual(data["verdict"], "warnings")
        self.assertFalse(self.found(data, severity="block"), data["findings"])
        own = [f for f in data["findings"] if f["rule"] in rules and f["severity"] == "warn"]
        self.assertTrue(own, data["findings"])
        self.assertTrue(all("client" in f["problem"] and f["expected"] for f in own), own)
        return own

    def test_A34_R70_a_client_figure_of_100_or_more_warns_in_every_form_in_a_payload_a_blueprint_and_a_scan(self):
        for form in self.FORMS:
            with self.subTest(form=form):
                text = "Overtime runs at %s a month." % form if not form.startswith("|") else \
                    "| Line | Amount | Month |\n|---|---|---|\n" + form
                self.assertWarns(*self.payload({"markdown": text}, "doc"))
                self.assertWarns(*self.blueprint({1: text}))
                self.assertWarns(*self.scan(text + "\n"))
        for text in ("The rush rate is 157 an hour.", "Pay $157 for each rush hour.", "The rush fee is 157."):
            with self.subTest(text=text):
                own = self.assertWarns(*self.payload({"description": text}, "board"), rules=("figure",))
                self.assertEqual(own[0]["source"], "research/2026-09-03-rush.md")
                self.assertWarns(*self.blueprint({2: text}), rules=("figure",))
                self.assertWarns(*self.scan(text + "\n"), rules=("figure",))
        own = self.assertWarns(*self.payload({"rate": 4500}, "column"), rules=("figure",))  # a JSON number too
        self.assertEqual((own[0]["field"], own[0]["match"]), ("$.rate", "4500"))

    def test_A34_R70_a_figure_split_in_a_payload_and_in_a_scanned_summary_warns(self):
        for text in ("The overtime comes to 4 500 in all.", "A note puts it at four thousand\nfive hundred.",
                     "| 4 | 500 |", "It is 4.500 now."):
            with self.subTest(text=text):
                own = self.assertWarns(*self.payload({"markdown": text}, "doc"))
                self.assertIn("split-figure", {f["rule"] for f in own})
        write(self.root / S1 / "SUMMARY.md", "# Summary\n\nOvertime on the desk comes to 4 500 a month.\n")
        code, data = self.lint("scan", S1 + "/SUMMARY.md")  # summary mode reads split figures only (X37)
        self.assertEqual(data["mode"], "summary")
        self.assertWarns(code, data, rules=("split-figure",))

    def test_A34_R70_a_cost_percentage_warns_in_a_payload_a_blueprint_and_a_scan(self):
        for text in ("The margin is 31%.", "The margin is 31 per cent."):
            with self.subTest(text=text):
                for code, data in (self.payload({"description": text}, "board"), self.blueprint({1: text}),
                                   self.scan(text + "\n")):
                    own = self.assertWarns(code, data, rules=("figure",))
                    self.assertIn("cost percentage 31%", own[0]["problem"])

    def test_A34_R70_an_item_batch_warns_on_a_client_figure_and_on_no_other_number(self):
        rows = {"board_id": 73100482, "items": [
            {"item_name": "Order 1042", "column_values": json.dumps({"numbers": 4500, "text_1": "Overtime 4,500",
                                                                     "text_2": "Rush hour at 157 an hour"})},
            {"item_name": "Order 1043", "column_values": json.dumps({"numbers": 2875, "text_1": "About 15% rye",
                                                                     "text_2": "Split 4 500", "text_3": "1,180.5"})}]}
        code, data = self.payload(rows, "item_batch")
        own = self.assertWarns(code, data)
        # Each is found in the raw column_values string and in the value walked inside it (R34).
        self.assertEqual({(f["rule"], f["match"]) for f in data["findings"]},
                         {("figure", "157"), ("figure", "4,500"), ("figure", "4500"), ("split-figure", "4 500")})
        self.assertEqual(len(own), len(data["findings"]))
        self.assertFalse(self.found(data, "number") or self.found(data, "record-number"))  # R69 stays

    def test_A34_R70_an_exclusion_figure_still_blocks_at_any_value(self):
        exclusions = self.root / S1 / "solution" / "exclusions.md"
        write(exclusions, RECORD[S1 + "/solution/exclusions.md"] + "- 64 [kind: figure; added: 2026-10-22; by: the "
                                                                   "user; source: the rush call]\n")
        for text in ("Pay 47,500.", "Pay $47.5k.", "Pay forty-seven thousand five hundred.", "Pay 47 500.",
                     "Keep 64 for the rush desk."):
            with self.subTest(text=text):
                for code, data in (self.payload({"markdown": text}, "doc"), self.blueprint({1: text}),
                                   self.scan(text + "\n"),
                                   self.payload({"items": [{"column_values": json.dumps({"text_1": text})}]},
                                                "item_batch")):
                    self.assertEqual(code, 1, data["findings"])
                    self.assertTrue(self.found(data, "exclusion", severity="block") or
                                    self.found(data, "split-figure", severity="block"), data["findings"])

    def test_A34_R70_a_payload_with_an_own_figure_and_a_real_block_still_exits_1(self):
        code, data = self.payload({"name": "Overtime 4,500 a month", "description": "Built by Quellmoor Advisory."},
                                  "board")
        self.assertEqual((code, data["verdict"]), (1, "blocked"))
        self.assertTrue(self.found(data, "figure", severity="warn"), data["findings"])
        self.assertTrue(self.found(data, "term", "firm", "block"), data["findings"])
        self.assertEqual(data["counts"]["block"], 1)


class A36Test(Base):
    """A36 (R72, R73): the firm's sound-alike rule spares everyday phrases, and a payload may carry what the frozen
    revision plans for it. R71, the named test workspace, is in test_leak_wall.py, since it needs a second record."""

    TOWNS = ("Ashby Fold", "Carrow Mead", "Delby", "Esk Hollow", "Frith Vale")
    VIEW = "Rye and spelt loaves waiting on the oven"

    # R72: the phonetic rule that backs the firm name

    def test_A36_R72_a_near_sound_of_the_firm_made_of_ordinary_words_passes(self):
        self.assertEqual(lint.phonetic_key("callmore"), lint.phonetic_key("quellmoor"))  # the cause: one key
        for text in ("We will call more stores next week.", "Call more often.", "CALL MORE"):
            with self.subTest(text=text):
                self.assertClean(text + "\n")
                code, data = self.payload({"description": text}, "board")
                self.assertEqual((code, data["findings"]), (0, []))

    def test_A36_R72_the_firm_in_every_form_and_a_near_sound_that_is_no_ordinary_word_still_block(self):
        for text, rule in (("Built by Quellmoor Advisory.", "term"), ("Ask Quellmoor.", "term"),
                           ("See quellmoor.example today.", "term"), ("QUELLMOOR wrote it.", "term"),
                           ("Built by Quell Moor.", None), ("Built by Kwellmoor.", "phonetic"),
                           ("Built by Quelmore.", "phonetic"), ("Then call Moore.", "phonetic")):
            with self.subTest(text=text):
                data = self.assertBlocks(text + "\n", rule, "firm")
                code, data = self.payload({"description": text}, "board")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, rule, "firm", "block"), data["findings"])

    # R73: a payload's run that matches the frozen revision's planned value is not a copied run

    def frozen(self, revision=None, working=None, frozen=True):
        """Strand 001 with a blueprint frozen as v0.1 revision 1: the towns planned in section 16's sample data plan,
        a long view name in the element-key table, and an assumption in section 16."""
        text = blueprint_text({11: "| Column | Type | What it holds |\n|---|---|---|\n| Town | dropdown | the town "
                                    "that orders |",
                               16: "### Assumptions\n\n- AS1 the night baker weighs every crate before the van "
                                   "leaves.\n\n### Sample data plan\n\n- B1 Orders, 20 rows. Invented towns: %s.\n\n"
                                   "## Element keys\n\n| key | kind | name | notifies |\n|---|---|---|---|\n"
                                   "| B1 | board | Orders | |\n| B1.C3 | column | Town | |\n| B1.V1 | view | %s | |\n"
                                   % (", ".join(self.TOWNS), self.VIEW)})
        revision = text if revision is None else revision
        write(self.root / S1 / "solution" / "blueprint.md", text if working is None else working)
        write(self.root / S1 / "versions" / "v0.1" / "blueprint-r1.md", revision)
        write(self.root / S1 / "versions" / "v0.1" / "version.md", '---\nschema: "version/1"\nstrand: "001"\n'
              'version: "v0.1"\nrevision: "%s"\n---\nInternal: never client-facing\n' % ("1" if frozen else "none"))
        write(self.root / S1 / "STRAND.md", '---\nschema: "strand/1"\nstrand: "001"\nversion: "v0.1"\n---\n'
              '# wholesale orders\n')
        return text

    def labels(self, towns=None):
        return {"board_id": 73100482, "title": "Town", "column_type": "dropdown", "defaults": json.dumps(
            {"settings": {"labels": [{"id": i + 1, "label": t} for i, t in enumerate(towns or self.TOWNS)]}})}

    def test_A36_R73_planned_labels_and_a_planned_view_name_pass_a_payload(self):
        self.frozen()
        for data, kind in ((self.labels(), "column"), ({"board_id": 73100482, "name": self.VIEW}, "view"),
                           ({"labels": list(self.TOWNS)}, "column")):
            with self.subTest(kind=kind, data=data):
                code, found = self.payload(data, kind)
                self.assertEqual((code, found["findings"]), (0, []))

    def test_A36_R73_an_internal_run_another_source_and_an_unfrozen_plan_still_block(self):
        text = self.frozen()
        code, data = self.payload({"description": "Note: the night baker weighs every crate before the van leaves."})
        self.assertEqual(code, 1, data["findings"])  # an assumption of section 16 still counts
        sources = {f["source"] for f in self.found(data, "copied-run", severity="block")}
        self.assertTrue(sources and sources <= {"%s/solution/blueprint.md" % S1,
                                                "%s/versions/v0.1/blueprint-r1.md" % S1}, data["findings"])
        write(self.root / S1 / "readiness.md", "# Readiness\n\n## Entities\n- Towns served: %s.\n"
              % ", ".join(self.TOWNS))
        code, data = self.payload(self.labels(), "column")  # the same run in another internal file still blocks
        self.assertEqual(code, 1, data["findings"])
        self.assertEqual({f["source"] for f in self.found(data, "copied-run", severity="block")},
                         {"%s/readiness.md" % S1})
        (self.root / S1 / "readiness.md").unlink()
        for setup in ({"frozen": False}, {"revision": text.replace("Esk Hollow", "Esk Mere")}):
            with self.subTest(setup=setup):  # no frozen revision, or one that planned other values
                self.frozen(**setup)
                code, data = self.payload(self.labels(), "column")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, "copied-run", severity="block"), data["findings"])

    # R74: a row inside an HTML comment is an example, not a row

    COMMENTED = ("<!-- - Pellow Grain [kind: name] -->", "<!--", "- Quarry Lane Dairy [kind: name]",
                 "- 61,250 [kind: figure]", "-->", "<!-- one more example:", "- Sorrel Mash Co [kind: name] -->")

    def test_A36_R74_a_commented_example_row_is_not_read_and_a_real_row_after_it_is(self):
        for title, strict in (("## Exclusions", True), ("## Allowlist", False)):
            with self.subTest(title=title):
                text = "\n".join(["# File", "", title] + list(self.COMMENTED) + ["- Tamsk Oats [kind: name]", ""])
                self.assertEqual([term for _, term, _ in lint.section_rows(text, title, "x.md", strict)],
                                 ["Tamsk Oats"])
        write(self.root / S1 / "solution" / "exclusions.md", RECORD[S1 + "/solution/exclusions.md"].replace(
            "## Exclusions\n", "## Exclusions\n%s\n" % "\n".join(self.COMMENTED)) + "- Tamsk Oats [kind: name]\n")
        for text in ("Oats from Quarry Lane Dairy.", "Mash from Sorrel Mash Co.", "Grain from Pellow Grain.",
                     "Pay 61,250."):
            with self.subTest(text=text):
                code, data = self.payload({"description": text}, "board")
                self.assertFalse(self.found(data, "exclusion"), data["findings"])
        for text in ("Oats from Tamsk Oats.", "Orders from Brackwater Mills.", "Pay 47,500."):
            with self.subTest(text=text):
                code, data = self.payload({"description": text}, "board")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, "exclusion", severity="block"), data["findings"])


class A39Test(Base):
    """A39 (R75, R77): a phone column's value is not an id, and a label colour or index in a status or dropdown
    column's settings is not a record number. R76, the index's names, is in test_leak_wall.py, since it needs a second
    record. The phone numbers are in the 555-01 range, which no line uses."""

    PHONES = {"lead_phone": {"phone": "14195550123", "countryShortName": "US"}, "contact_phone": "4195550188 US",
              "phone_mm8k2q4z": {"phone": "+14195550142", "countryShortName": "US"}, "phone": "4195550177"}

    # R75: a phone value is not an id

    def test_A39_R75_a_phone_columns_value_in_column_values_passes(self):
        for data, kind in (
                ({"board_id": 73100482, "items": [{"item_name": "Lakeview Pumps", "column_values":
                                                   json.dumps(self.PHONES)}]}, "item_batch"),
                ({"board_id": 73100482, "item_name": "Lakeview Pumps", "column_values": self.PHONES}, "generic"),
                ({"boardId": "73100482", "itemId": "73100499", "columnValues": json.dumps(
                    {"lead_phone": "4195550123 US", "contact_phone": json.dumps(
                        {"phone": "4195550123", "countryShortName": "US"})})}, "generic")):
            with self.subTest(kind=kind, data=data):
                code, found = self.payload(data, kind)
                self.assertEqual((code, found["findings"]), (0, []))
        code, data = self.payload({"board_id": 73100482, "column_values": json.dumps(
            {"lead_phone": "4195550123 US", "long_text": "Board 73100482"})})
        self.assertEqual(code, 1, data["findings"])  # beside a phone that passes, an id in a text column blocks
        self.assertEqual({f["field"] for f in self.found(data, "term", "id-patterns")},
                         {"$.column_values<json>.long_text"})

    def test_A39_R75_digits_written_as_text_or_outside_a_phone_columns_value_still_block(self):
        for change in ({"item_name": "Call 4195550123"}, {"column_values": {"text_1": "4195550123"}},
                       {"column_values": {"lead_phone": "Call 4195550123 after six"}},
                       {"column_values": {"lead_phone": {"phone": "4195550123", "countryShortName": "USA"}}},
                       {"column_values": {"lead_phone": {"phone": "4195550123", "countryShortName": "US",
                                                         "note": "the depot line"}}},
                       {"lead_phone": {"phone": "4195550123", "countryShortName": "US"}},
                       {"column_values": {"phonetic_notes": "4195550123"}},
                       {"description": "Ring 419 555 0123 today."}):
            with self.subTest(change=change):
                code, data = self.payload(dict({"board_id": 73100482}, **change))
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.found(data, "term", "id-patterns", "block"), data["findings"])
        code, data = self.payload({"board_id": 73100482, "column_values": {"lead_phone": "91000017 US"}})
        self.assertEqual(code, 1, data["findings"])  # the user's own account id blocks as a phone too (X06)
        self.assertTrue(self.found(data, "seller-account", severity="block"), data["findings"])

    # R77: a label colour number is not a record number

    def depot(self):
        write(self.root / "research" / "2026-09-04-depot.md", "- The depot loads 153 crates and 108 trays on a "
                                                              "Friday.\n")

    @staticmethod
    def status(labels, key="columnSettings", text=False):
        settings = {"labels": labels}
        return {"board_id": 73100482, "columnType": "status", "columnTitle": "Stage",
                key: json.dumps(settings) if text else settings}

    LABELS = [{"id": 0, "label": "New", "color": 153, "index": 0}, {"id": 1, "label": "Won", "color": 108, "index": 1},
              {"id": 2, "label": "Lost", "color": "153", "index": 108}]

    def test_A39_R77_label_colours_and_indexes_in_a_columns_settings_raise_no_number_warning(self):
        self.depot()
        for data in (self.status(self.LABELS), self.status(self.LABELS, text=True),
                     self.status(self.LABELS, "settings_str", True),
                     {"board_id": 73100482, "column_type": "dropdown", "title": "Oven", "defaults": json.dumps(
                         {"settings": {"labels": [{"id": 1, "label": "Deck oven", "color": 153, "position": 108}]}})}):
            with self.subTest(data=data):
                code, found = self.payload(data, "column")
                self.assertEqual((code, found["findings"]), (0, []))

    def test_A39_R77_a_number_in_a_label_or_outside_the_labels_still_warns_and_an_exclusion_or_an_id_blocks(self):
        self.depot()
        for data in (self.status([{"id": 0, "label": "153 crates", "color": 7, "index": 0}]),
                     {"board_id": 73100482, "name": "Stage", "color": 153},
                     {"board_id": 73100482, "columnSettings": {"color": 153, "labels": [{"label": "New"}]}},
                     {"board_id": 73100482, "items": [{"item_name": "Crates", "column_values": {"labels": {
                         "color": 153}}}]}):
            with self.subTest(data=data):
                code, found = self.payload(data, "column")
                self.assertEqual(code, 2, found["findings"])
                self.assertTrue(self.found(found, "record-number", severity="warn"), found["findings"])
        for color, rule, cls in ((47500, "exclusion", None), ("47500", "exclusion", None),
                                 (73100482, "term", "id-patterns")):
            with self.subTest(color=color):
                code, found = self.payload(self.status([{"id": 0, "label": "Hold", "color": color, "index": 0}]),
                                           "column")
                self.assertEqual(code, 1, found["findings"])
                self.assertTrue(self.found(found, rule, cls, "block"), found["findings"])


class A42Test(Base):
    """A42 (R79, R80): a payload value that holds JSON is read with its escapes decoded, and the column part of an
    element key is no pain id. Each loosening has a control that still blocks."""

    VISITS = {"long_text_mm8c1": {"text": "Visit on 2 October: samples asked for.\n15 October: samples arrived."}}

    # R79: escapes are read as what they stand for

    def test_A42_R79_an_escaped_line_break_before_a_date_is_not_a_pain_id(self):
        accented = {"long_text_mm8c1": {"text": "Café counter\tS1 shelf? No: 3 shelves.\n9 cases."}}
        for data in ({"board_id": 73100482, "items": [{"item_name": "Sterling Gear Works", "column_values":
                                                       json.dumps(self.VISITS)}]},
                     {"board_id": 73100482, "column_values": json.dumps(json.dumps(self.VISITS))},
                     {"board_id": 73100482, "column_values": json.dumps({"text_1": "Line one\n12 crates"})}):
            with self.subTest(data=data):
                code, found = self.payload(data, "item_batch")
                self.assertEqual((code, found["findings"]), (0, []))
        code, found = self.payload({"board_id": 73100482, "column_values": json.dumps(accented, ensure_ascii=True)})
        self.assertEqual([f["match"] for f in self.found(found, "term", "pain-ids")], ["S1", "S1"])  # the real one

    def test_A42_R79_a_pain_id_inside_json_still_blocks_in_the_value_and_the_decoded_string(self):
        data = {"board_id": 73100482, "column_values": json.dumps({"long_text": {"text": "Pain\nP3 is solved."}})}
        code, found = self.payload(data)
        self.assertEqual(code, 1, found["findings"])
        self.assertEqual({f["field"] for f in self.found(found, "term", "pain-ids", "block")},
                         {"$.column_values", "$.column_values<json>.long_text.text"})

    # R80: an element key is not a pain id

    def test_A42_R80_an_element_key_in_a_payload_passes(self):
        for data in ({"B3.C9": "Visit on 2 October."}, {"key": "B1.C4", "keys": ["B4.C10", "b3.c7", "DB1.W2"]},
                     {"prompt": "From {pulse.B3.C7} draft one line."}):
            with self.subTest(data=data):
                code, found = self.payload(data)
                self.assertEqual((code, found["findings"]), (0, []))

    def test_A42_R80_a_pain_id_alone_after_a_dot_or_in_a_qualified_key_still_blocks(self):
        for text, match in (("Column C9 is new.", "C9"), ("See 001:B3.C9 there.", "001:B3.C9"), ("x.C9 here", "C9"),
                            ("P3 and B3.C9", "P3")):
            with self.subTest(text=text):
                code, found = self.payload({"description": text})
                self.assertEqual(code, 1, found["findings"])
                self.assertIn(match, [f["match"] for f in self.found(found, "term", "pain-ids", "block")])


class A43Test(Base):
    """A43 (R81): in a workflow request, the ids the record holds as its own pass, the bound user's and those of the
    strand's ledger rows; every other id still blocks there, and every id still blocks in any other kind of payload."""

    USER, BOARD, OTHER = "93800417", "73100482", "73100499"  # none reads as a date (Y02)

    def own(self):
        write(self.root / "account.json", json.dumps({"schema": "account/1", "account": {"bound_user_id": self.USER}}))
        write(self.root / "strands" / "001-wholesale-orders" / "solution" / "build.json", json.dumps(
            {"schema": "build/2", "objects": {"B1": {"type": "board", "id": self.BOARD},
                                              "B1.C1": {"type": "column", "id": "status"}}}))

    def test_A43_R81_a_workflow_request_names_its_own_user_and_board_by_id(self):
        self.own()
        prompt = "Set step 6: board %s, the item from step 1, and notify only user %s." % (self.BOARD, self.USER)
        code, found = self.payload({"workflowObjectId": 90300000071, "prompt": prompt}, "workflow")
        self.assertEqual((code, found["findings"]), (0, []))

    def test_A43_R81_another_id_another_kind_or_no_ledger_still_blocks(self):
        self.own()
        for data, kind in (({"prompt": "Notify only user %s." % self.OTHER}, "workflow"),
                           ({"prompt": "Notify only user %s." % self.USER}, "automation"),
                           ({"name": "Board %s" % self.BOARD}, "board")):
            with self.subTest(kind=kind, data=data):
                code, found = self.payload(data, kind)
                self.assertEqual(code, 1, found["findings"])
                self.assertTrue(self.found(found, "term", "id-patterns", "block"), found["findings"])
        (self.root / "account.json").unlink()
        (self.root / "strands" / "001-wholesale-orders" / "solution" / "build.json").unlink()
        code, found = self.payload({"prompt": "Notify only user %s." % self.USER}, "workflow")
        self.assertEqual(code, 1, found["findings"])


class IntakeFoldTest(Base):
    """R78: a scan with no path and no draft says that no draft exists, in the exit the contract gives for nothing
    to check."""

    def test_17_a_bare_strand_scan_with_no_draft_says_no_draft_exists(self):
        code, data = self.lint("scan", "--strand", "001")
        self.assertEqual((code, data["verdict"]), (3, "could-not-run"))
        error = data["error"]
        self.assertEqual(error["file"], S1 + "/drafts/")
        self.assertIn("no draft exists for strand 001", error["problem"])
        self.assertNotIn("handoff file to check", error["problem"])
        self.assertIn("path of the file to check", error["expected"])
        self.assertEqual(data["inputs"], [])

    def test_17_a_bare_scan_with_no_draft_anywhere_says_so_without_a_strand(self):
        code, data = self.lint("scan")
        self.assertEqual(code, 3)
        self.assertIn("no draft exists", data["error"]["problem"])
        self.assertEqual(data["error"]["file"], "strands/")

    def test_17_a_scan_with_a_real_path_or_a_draft_to_find_behaves_as_before(self):
        rel = self.draft("Orders for the office.")
        code, data = self.lint("scan", "--strand", "001", rel)
        self.assertEqual((code, data["findings"]), (0, []))
        self.assertEqual(self.lint("scan", "--strand", "001")[0], 0)  # the draft is now found without a path
        (self.root / "strands" / "002-delivery-rounds" / "drafts").mkdir()
        code, data = self.lint("scan", S2 + "/drafts")
        self.assertEqual(code, 3)  # a given folder that holds no file keeps R22's message
        self.assertEqual(data["error"]["problem"], "no draft or handoff file to check")


# 2.19 Pins (DECISIONS 4.5, Y08)

class PinTest(unittest.TestCase):

    def test_L161_L271_L272_the_leak_region_equals_pinned_leak(self):
        tool = load(REPO / "tools" / "lint_plugin.py", "lint_plugin_for_leak")
        lines = (PLUGIN / "shared" / "record-map.md").read_text(encoding="utf-8").splitlines()
        pinned, line = tool.pinned_section(lines, "leak")
        names, literals, region = tool.pinned_region((SCRIPTS / "leak_lint.py").read_text(encoding="utf-8"), "leak")
        self.assertIsNotNone(line)
        self.assertIsNotNone(region)
        self.assertEqual(pinned - names - literals, set())
        self.assertEqual(literals - pinned, set())

    def test_Y08_the_fixture_copy_of_the_structural_keys_equals_the_region(self):
        tree = ast.parse((HERE / "test_leak_fixture.py").read_text(encoding="utf-8"))
        copy = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "STRUCTURAL_ID_KEYS" for t in node.targets):
                copy = set(next(n.value for n in ast.walk(node.value) if isinstance(n, ast.Constant) and
                                isinstance(n.value, str)).split())
        self.assertEqual(copy, set(lint.STRUCTURAL_ID_KEYS))

    def test_L274_L275_embedded_regions_and_no_counted_class(self):
        text = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        for region in ("leak", "common-words", "stop-words", "paraphrase-cues", "internal-vocabulary", "sales-framing",
                       "cost-cues", "confusables", "credential-shapes", "internal-notes", "structural-id-keys", "shared-words",
                       "shared-phrases", "everyday-method-rows"):
            self.assertIn("# pinned: %s\n" % region, text)
        self.assertEqual(text.count("# end pinned"), 14)
        rows = lint.parse_list((PLUGIN / "shared" / "leak-terms.txt").read_text(encoding="utf-8"), "s", local=False)
        # A30 (R64): the tool-category classes are gone from the shipped list; a class left there would block as
        # an ordinary term class, since the script no longer counts any class.
        self.assertFalse([r.cls for r in rows if r.cls.startswith("tool-category")])
        self.assertFalse(hasattr(lint, "COUNTED_PREFIX"))
        self.assertFalse(re.search(r"(?<![\d])\d{8,}(?![\d])", text))


if __name__ == "__main__":
    unittest.main()
