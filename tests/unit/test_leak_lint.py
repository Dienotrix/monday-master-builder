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
        self.assertEqual(codes, [0, 0, 0, 3, 3, 3, 3, 3])
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

    def test_X08_commands_part_2_builds_are_exit_3_not_built_yet(self):
        for argv in (["blueprint", "--strand", "001"], ["wall", "--text", "Orders"], ["terms", "x"], ["index"]):
            code, data = self.lint(*argv)
            self.assertEqual((code, data["ok"]), (3, False))
            self.assertIn("not built yet", data["error"]["problem"])

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
        self.assertBlocks("Take the exit ramp now.", "term", "method")
        self.assertBlocks("The exit ramp.", "term", "method")
        self.assertClean("The boexit rampx sign.")

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
        for text in ("Show the cost of waiting.", "This is a fit risk.", "R4 Met after the visit.",
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
            data = self.assertBlocks(text, "figure")
            self.assertEqual(self.found(data, "figure")[0]["source"], source)

    def test_L79_to_L84_five_formats_against_five_record_formats(self):
        forms = ("45000", "45,000", "45k", "$45k", "forty-five thousand")
        for record_form in forms:
            write(self.root / "research" / "2026-09-02-brief.md", "- The oven service costs %s a year.\n" % record_form)
            for payload_form in forms:
                code, data = self.payload({"markdown": "The service is %s." % payload_form})
                self.assertEqual(code, 1, (record_form, payload_form, data["findings"]))
                self.assertTrue(self.found(data, "figure"), (record_form, payload_form))

    def test_X25_rounded_and_truncated_forms_within_precision(self):
        for text in ("Waste runs at 184k.", "Waste runs at $185k.", "Waste runs at 184.3k.",
                     "Waste runs at one hundred and eighty-four thousand."):
            self.assertBlocks(text, "figure")
        code, data = self.scan("Waste runs at 183k.")
        self.assertEqual(code, 2)
        self.assertTrue(self.found(data, "number"))

    def test_L85_L86_X25_floors_and_warnings(self):
        code, data = self.scan("The bakery bought 1,200 crates.")
        self.assertEqual((code, [f["rule"] for f in data["findings"]]), (2, ["number"]))
        self.assertEqual(self.scan("The bakery bought 9 crates.")[0], 0)
        self.assertBlocks("A baker is paid 27 an hour.", "figure")
        self.assertBlocks("Pay $27 for it.", "figure")
        code, data = self.scan("A tray takes 27 minutes.")
        self.assertEqual((code, data["findings"][0]["rule"]), (2, "record-number"))
        code, data = self.scan("The bakery has 34 staff.")
        self.assertEqual((code, data["findings"][0]["rule"]), (2, "record-number"))
        self.assertBlocks("The margin is 31%.", "figure")
        code, data = self.scan("About 15% of loaves.")
        self.assertEqual((code, data["findings"][0]["rule"]), (2, "number"))

    def test_X25_not_numbers_dates_times_versions_years_ordinals(self):
        self.assertClean("On 2026-10-17, 17/10/2026, 10/17/2026, 17.10.2026, 17 October 2026 and October 17 at "
                         "14:30, in 2026, v0.1 and 1.2.3.\n1. First step.\n12) Twelfth step.")
        code, data = self.scan("Spend $2026 on it.")
        self.assertEqual(code, 2)

    def test_X25_ambiguous_lower_case_m_is_read_both_ways(self):
        write(self.root / "research" / "2026-09-02-brief.md", "- The new line costs 2,000,000.\n")
        self.assertBlocks("The shop is 2m long.", "figure")
        self.assertBlocks("A $2M line.", "figure")

    def test_L87_X25_exclusion_figures_in_every_rendering(self):
        for text in ("Pay 47500.", "Pay 47,500.", "Pay 47.5k.", "Pay $47.5k.", "Pay forty-seven thousand five hundred.",
                     "Pay 47 500."):
            code, data = self.scan(text)
            self.assertEqual(code, 1, text)
            self.assertTrue(self.found(data, "exclusion") or self.found(data, "split-figure"), text)

    def test_L105_L106_split_renderings(self):
        write(self.root / "research" / "2026-09-02-brief.md", "- The new proofer has a budget of 52,000.\n")
        self.assertBlocks("The proofer comes to 52 000 in all.", "split-figure")
        self.assertBlocks("A note puts it at fifty-\ntwo thousand.", "split-figure")
        self.assertBlocks("| 52 | 000 |", "split-figure")
        self.assertBlocks("It is 52.000 now.", "split-figure")
        code, data = self.scan("The proofer comes to 61 000 in all.")
        self.assertNotEqual(code, 1)
        code, data = self.scan("Crates 3 4 by the door.")
        self.assertNotEqual(code, 1)

    def test_X25_figures_in_links_block_and_warnings_skip_links(self):
        self.assertBlocks("[Sheet](https://files.example/report?total=184260)", "figure")
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


# 2.8 The two structural assertions

class AssertionTest(Base):

    def test_L107_to_L111_tool_categories(self):
        three = "The office keeps orders in a spreadsheet, wages in a payroll system and photos in a shared drive."
        data = self.assertBlocks(three, "tool-categories")
        self.assertEqual(self.found(data, "tool-categories")[0]["match"], "spreadsheet")
        self.assertClean("The office keeps orders in a spreadsheet and wages in a payroll system.")
        self.assertClean("Orders sit in a spreadsheet. Wages sit in a payroll system. Photos sit in a shared drive.")
        self.assertClean("The office keeps orders for Brindlecombe in a spreadsheet, wages in a payroll system and "
                         "photos in a shared drive.")
        self.assertClean("Orders sit in a spreadsheet.")

    def test_L104_assertions_run_in_payloads_too(self):
        code, data = self.payload({"markdown": "Orders in a spreadsheet, wages in a payroll system, files in a wiki."})
        self.assertTrue(self.found(data, "tool-categories"))


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
        self.assertTrue({"figure", "term", "exclusion", "credential", "copied-run", "quote"} <= blocked, blocked)
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
        rel = self.draft("The bakery runs with 34 staff.")
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
                   ("word/footnotes.xml", body(["Waste of 184,260."]).replace("w:document", "w:footnotes")),
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

    def test_X01_part_1_has_no_wall_so_another_record_or_an_index_stops_the_check(self):
        write(self.home / "clients" / "other-client" / "CLIENT.md", "---\nslug: \"other-client\"\n---\n")
        code, data = self.scan("Orders.")
        self.assertEqual((code, data["error"]["field"]), (3, "wall"))
        self.assertEqual(self.payload({"name": "Orders"})[0], 3)
        rel = "%s/SUMMARY.md" % S1
        write(self.root.joinpath(*rel.split("/")), "Orders.\n")
        self.assertEqual(self.lint("scan", rel)[0], 0)
        shutil.rmtree(str(self.home / "clients" / "other-client"))
        write(self.home / "clients-index.json", '{"schema": "clients-index/1", "entries": {}}')
        self.assertEqual(self.scan("Orders.")[0], 3)
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

    def test_L274_L275_embedded_regions_and_the_counted_classes(self):
        text = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        for region in ("leak", "common-words", "stop-words", "paraphrase-cues", "internal-vocabulary", "sales-framing",
                       "cost-cues", "confusables", "credential-shapes", "internal-notes", "structural-id-keys"):
            self.assertIn("# pinned: %s\n" % region, text)
        self.assertEqual(text.count("# end pinned"), 11)
        rows = lint.parse_list((PLUGIN / "shared" / "leak-terms.txt").read_text(encoding="utf-8"), "s", local=False)
        counted = {r.cls for r in rows if r.cls.startswith(lint.COUNTED_PREFIX)}
        self.assertEqual(len(counted), 15)
        self.assertFalse(re.search(r"(?<![\d])\d{8,}(?![\d])", text))


if __name__ == "__main__":
    unittest.main()
