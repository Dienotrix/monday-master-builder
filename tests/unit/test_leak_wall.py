"""Unit tests for plugins/monday-master-builder/scripts/leak_lint.py, part 2: the cross-client wall, the index,
the payload walker over every kind, blueprint and terms (WP4 step 6).

Contract clauses of rebuild-workspace/build/wp4/CONTRACT.md by id in the test names, with the decision each part
follows (Xnn, Ynn, Znn). Each test copies the two planted records of tests/fixtures/leak/records/ and the fixture's
test settings into a temporary home whose folder name holds a space (PLAN nod 4), points MMB_HOME at it and HOME
and USERPROFILE at an empty canary folder; nothing is read from or written to the real home, and the fixture is
only read. leak_lint.py runs in process through main(), and as a subprocess where the process boundary is the
point (G49, X29). Record a, wrenfold-joinery, is the record the checks run in; record b, marlbeck-freight, is the
other client. Every name, firm, figure and id here is invented.
"""
import sys
sys.dont_write_bytecode = True  # nothing cached beside the scripts (G49)

import ast, importlib.util, io, json, os, shutil, subprocess, tempfile, time, zipfile  # noqa: E401,E402
import unittest  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PLUGIN = REPO / "plugins" / "monday-master-builder"
SCRIPTS = PLUGIN / "scripts"
FIX = REPO / "tests" / "fixtures" / "leak"
sys.path.insert(0, str(SCRIPTS))
import mmb_common as mc  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = load(SCRIPTS / "leak_lint.py", "leak_lint_wall")
MANIFEST = json.loads((FIX / "manifest.json").read_text(encoding="utf-8"))
A, B = "wrenfold-joinery", "marlbeck-freight"
SA, SB = "strands/001-quote-tracker", "strands/001-route-board"
WORK = ".work/strands/001-quote-tracker/payload.json"
CLOCK = datetime(2026, 10, 17, 9, 30, 0, tzinfo=timezone.utc)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


def tree(folder):
    return sorted(p.relative_to(folder).as_posix() for p in Path(folder).rglob("*"))


def docx_bytes(parts):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            archive.writestr(name, text)
    return buffer.getvalue()


BODY = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:body></w:document>')
SECTION_TITLES = ("Version scope and deferred items", "Product fit", "Requirement trace", "Structure mapping", "Forks",
                  "Live objects this strand touches", "Workspace and product binding", "Native-entity map",
                  "Portfolio and project plan", "Board inventory", "Columns, relations and mirrors",
                  "Groups, views, forms, docs, dashboards", "The lists",
                  "Permissions, ownership, plan tier and data policy",
                  "Irreversible operations, UI steps and client decisions", "Internal")


def sections(first, last=16):
    """R49 (G18): the numbered section headings `first` to `last`, empty and in the pinned shape, in the template's
    own words (R50) as the guide numbers the sixteen; a short test blueprint adds them so it reads as a full one, its
    own text left in place."""
    return "".join("\n## %d. %s\n" % (n, SECTION_TITLES[n - 1]) for n in range(first, last + 1))


class Base(unittest.TestCase):
    """A fresh home with the fixture's settings, local list and both planted records; the real home untouched."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="leak wall "))
        self.home = self.tmp / "home with space"
        self.canary = self.tmp / "canary"
        self.canary.mkdir()
        for key in ("settings", "local_terms"):
            target = self.home / MANIFEST["home"][key]["to"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(FIX / MANIFEST["home"][key]["from"]), str(target))
        for record in MANIFEST["home"]["records"].values():
            shutil.copytree(str(FIX / record["from"]), str(self.home / record["to"]))
        self.a, self.b = self.home / "clients" / A, self.home / "clients" / B
        self.env = mock.patch.dict(os.environ, {"MMB_HOME": str(self.home), "HOME": str(self.canary),
                                                "USERPROFILE": str(self.canary)})
        self.env.start()
        self.clock = mock.patch.object(mc, "now_utc", return_value=CLOCK)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.env.stop()
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def raw(self, record, *argv):
        buffer = io.BytesIO()

        class Out:
            def write(self, text):
                buffer.write(text.encode("utf-8"))

            def flush(self):
                pass

        Out.buffer = buffer
        prefix = ["--record", str(record)] if record is not None else []
        with mock.patch.object(sys, "stdout", Out()):
            code = lint.main(prefix + list(argv))
        return code, buffer.getvalue()

    def lint(self, record, *argv):
        """main() in process; the envelope checked as X41 says; (code, data)."""
        code, raw = self.raw(record, *argv)
        self.assertNotIn(b"\r", raw)
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["ok"], code in (0, 2))
        self.assertEqual(data["verdict"], {0: "clean", 1: "blocked", 2: "warnings", 3: "could-not-run"}[code])
        for finding in data["findings"]:
            for key in ("file", "field", "problem", "expected"):
                self.assertTrue(finding[key], finding)
            self.assertIn(finding["rule"], lint.RULES)
            if finding["rule"] == "wall":
                self.assertIn(finding["class"], lint.WALL_CLASSES)
                self.assertIsNone(finding["source"])
        if code == 3:
            self.assertTrue(all(data["error"][k] for k in ("file", "field", "problem", "expected")), data["error"])
        return code, data

    def index(self, record=None):
        code, data = self.lint(record or self.a, "index")
        self.assertEqual(code, 0, data.get("error"))
        return data

    def both(self):
        self.index(self.b)
        self.index(self.a)

    def payload(self, value, kind="generic", record=None, strand="001"):
        root = record or self.a
        rel = WORK if root == self.a else ".work/strands/001-route-board/payload.json"
        write(root.joinpath(*rel.split("/")), json.dumps(value, indent=2, ensure_ascii=False))
        return self.lint(root, "payload", "--strand", strand, "--kind", kind, "--file", rel)

    def draft(self, text, name="d.md", record=None):
        root = record or self.a
        rel = "%s/drafts/%s" % (SA if root == self.a else SB, name)
        write(root.joinpath(*rel.split("/")), text)
        return self.lint(root, "scan", rel)

    def walls(self, data, cls=None):
        return [f for f in data["findings"] if f["rule"] == "wall" and (cls is None or f["class"] == cls)]

    def entry(self, slug):
        data = json.loads((self.home / "clients-index.json").read_text(encoding="utf-8"))
        return data["entries"][lint.digest("s:", slug)]

    def assertWall(self, data, cls=None, match=None, code=1):
        self.assertEqual(data["verdict"], {1: "blocked", 3: "could-not-run"}.get(code, data["verdict"]))
        hits = self.walls(data, cls)
        self.assertTrue(hits, data["findings"])
        if match is not None:
            self.assertIn(match, [h["match"] for h in hits], data["findings"])
        return hits


# 2.13 The index

class IndexTest(Base):

    def stamp_for(self, record, clock=CLOCK):
        """R44: an entry's stamp is the later of the clock and the newest change of the files it is built from. The
        clock is patched to an earlier day than the copied files' real times, so the files' time is the stamp."""
        def fail(*_):
            raise AssertionError("the record cannot be walked")
        newest = lint.newest_change(lint.record_walk(record, fail, fail), fail)
        return mc.stamp("utc", max(clock, datetime.fromtimestamp(newest, timezone.utc)))

    def test_L168_X02_index_creates_the_file_with_this_records_entry(self):
        self.assertFalse((self.home / "clients-index.json").exists())
        data = self.index(self.b)
        self.assertTrue(data["written"])
        self.assertIsNone(data["strand"])
        raw = (self.home / "clients-index.json").read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"}\n"))
        index = json.loads(raw.decode("utf-8"))
        self.assertEqual(list(index), ["schema", "hash", "normalisation", "entries"])
        self.assertEqual((index["schema"], index["hash"], index["normalisation"]),
                         ("clients-index/1", "sha256-128", "wall/1"))
        self.assertEqual(list(index["entries"]), [lint.digest("s:", B)])
        entry = index["entries"][lint.digest("s:", B)]
        self.assertEqual(list(entry), ["updated", "names", "phonetic", "terms", "figures"])
        self.assertEqual(entry["updated"], self.stamp_for(self.b))
        for field in ("names", "phonetic", "terms", "figures"):
            self.assertEqual(entry[field], sorted(set(entry[field])))
            self.assertTrue(entry[field], field)
            self.assertTrue(all(len(v) == 32 and int(v, 16) >= 0 for v in entry[field]))
        self.assertEqual(lint.digest("n:", "marlbeck freight"),
                         __import__("hashlib").sha256(b"n:marlbeck freight").hexdigest()[:32])
        self.assertIn("<home>/clients-index.json", [i["file"] for i in data["inputs"]])

    def test_L169_to_L173_L185_X26_names_harvested_from_the_whole_record(self):
        names = set(self.entry_of(B)["names"])
        for form in ("marlbeck freight", "marlbeckfreight",  # the client, and its slug
                     "perrin haldane", "quilla oduya", "wendell ayo",  # people; the last only in a body line
                     "tollmere fresh market", "tfm",  # a customer in full and as initials
                     "silver lantern",  # a partner of two ordinary words
                     "dockon",  # a product
                     "brannock cold store", "quessel holdings",  # a counterparty and its part-owner
                     "perrinhaldane", "skipper"):  # an e-mail's fused local part; the alias word
            self.assertIn(lint.digest("n:", form), names, form)
        for ordinary in ("the", "night desk", "route board", "every", "fuel"):
            self.assertNotIn(lint.digest("n:", ordinary), names, ordinary)
        phonetic = set(self.entry_of(B)["phonetic"])
        key = " ".join(lint.phonetic_key(w) for w in ("marlbeck", "freight"))
        self.assertIn(lint.digest("p:", key), phonetic)
        self.assertIn(lint.digest("p:", lint.phonetic_key("marlbeck")), phonetic)

    def entry_of(self, slug):
        self.index(self.home / "clients" / slug)
        return self.entry(slug)

    def test_L174_L175_X25_terms_of_every_strand_and_figures_above_the_floor(self):
        write(self.a / "strands" / "002-fitting-schedule" / "solution" / "exclusions.md",
              "# Exclusions\n\n## Exclusions\n- Ostrella Hinges Ltd [kind: name]\n- 4,250 [kind: figure]\n")
        entry = self.entry_of(A)
        for form in ("corvel systems", "corvelsystems", "kestrin boards", "tamsin rook", "ostrella hinges",
                     "ostrella hinges ltd", "ostrellahinges"):
            self.assertIn(lint.digest("n:", form), entry["terms"], form)
        figures = set(entry["figures"])
        for form in ("263480e0", "26348e1", "2635e2", "2634e2", "263e3"):  # 263,480: five significant digits
            self.assertIn(lint.digest("f:", form), figures, form)
        self.assertNotIn(lint.digest("f:", "73000e0"), figures)  # two significant digits: below the floor
        self.assertNotIn(lint.digest("f:", "5000e0"), figures)
        self.assertNotIn(lint.digest("f:", "46e0"), figures)  # a record number, not a cost figure
        self.assertIn(lint.digest("f:", "4250e0"), figures)  # an exclusion figure, any value
        self.assertIn(lint.digest("f:", "42e2"), figures)
        self.assertNotIn(lint.digest("f:", "4e3"), figures)  # R57 (G22): two significant digits on the wall

    def test_L176_X21_the_index_holds_no_plaintext(self):
        self.both()
        raw = (self.home / "clients-index.json").read_bytes().lower()
        for text in ("marlbeck", "freight", "perrin", "haldane", "tollmere", "tfm", "dockon", "silver", "lantern",
                     "wendell", "brannock", "quessel", "surcharge", "wrenfold", "joinery", "corvel", "kestrin",
                     "tamsin", "varrow", "186730", "186,730", "187k", "186.7", "263480", "263,480", "263k",
                     "two hundred", "sixty", A, B, "route-board", "quote-tracker"):
            self.assertNotIn(text.encode("utf-8"), raw, text)

    def test_L177_X46_a_rerun_writes_nothing_and_other_entries_stay_byte_equal(self):
        self.both()
        path = self.home / "clients-index.json"
        before = path.read_bytes()
        backups = tree(self.home / "local" / "backup")
        data = self.index(self.a)
        self.assertFalse(data["written"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(tree(self.home / "local" / "backup"), backups)
        other = json.dumps(self.entry(B), sort_keys=True)
        write(self.a / "research" / "2026-09-30-notes.md", "# Notes\n\nThe glazier is Ostrella Hinges.\n")
        later = datetime(2026, 10, 18, 8, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(mc, "now_utc", return_value=later):
            self.assertTrue(self.index(self.a)["written"])
        self.assertEqual(self.entry(A)["updated"], self.stamp_for(self.a, later))
        self.assertEqual(json.dumps(self.entry(B), sort_keys=True), other)
        self.assertEqual(self.entry(B)["updated"], self.stamp_for(self.b))
        saved = [p for p in (self.home / "local" / "backup").iterdir() if p.name.startswith("clients-index.json.")]
        self.assertTrue(saved)
        self.assertTrue((self.home / ".work" / "record.mutex").is_file())

    def test_L178_an_archived_record_stays_walled(self):
        self.both()
        (self.home / "archive").mkdir()
        shutil.move(str(self.b), str(self.home / "archive" / B))
        code, data = self.payload({"name": "Stock held at Quessel Holdings", "markdown": "A cold-chain surcharge."})
        self.assertEqual(code, 1)
        self.assertEqual({f["class"] for f in self.walls(data)}, {"name", "term"})

    def test_L180_index_opens_only_this_records_files_and_the_index(self):
        self.index(self.b)
        opened, real = [], lint.read_bytes
        with mock.patch.object(lint, "read_bytes", side_effect=lambda p: opened.append(Path(p)) or real(p)):
            self.index(self.a)
        root, shared = self.a.resolve(), (PLUGIN / "shared").resolve()
        for path in opened:
            path = path.resolve()
            inside = [base for base in (root, shared) if base in path.parents]
            self.assertTrue(inside or path == (self.home / "clients-index.json").resolve(), path)
            self.assertNotIn(self.b.resolve(), path.parents)

    def test_L181_X29_two_records_keep_both_entries_also_at_the_same_moment(self):
        self.both()
        self.assertEqual(len(json.loads((self.home / "clients-index.json").read_text())["entries"]), 2)
        (self.home / "clients-index.json").unlink()
        env = dict(os.environ, MMB_HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1")
        runs = [subprocess.Popen([sys.executable, str(SCRIPTS / "leak_lint.py"), "--record", str(root), "index"],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for root in (self.a, self.b)]
        for run in runs:
            out, _ = run.communicate(timeout=120)
            self.assertEqual(run.returncode, 0, out)
        entries = json.loads((self.home / "clients-index.json").read_text())["entries"]
        self.assertEqual(set(entries), {lint.digest("s:", A), lint.digest("s:", B)})

    def test_X29_a_torn_index_is_exit_3_never_a_pass(self):
        self.both()
        path = self.home / "clients-index.json"
        data = path.read_bytes()
        path.write_bytes(data[:len(data) // 2])
        write(self.a / SA / "drafts" / "d.md", "Orders.\n")
        for argv in (["scan", "%s/drafts/d.md" % SA], ["wall", "--text", "Orders"], ["index"]):
            code, out = self.lint(self.a, *argv)
            self.assertEqual((code, out["error"]["file"]), (3, "<home>/clients-index.json"), argv)

    def test_X30_index_refuses_a_slug_that_is_not_the_folder_name(self):
        moved = self.home / "clients" / "wrenfold-kitchens"
        shutil.move(str(self.a), str(moved))
        code, data = self.lint(moved, "index")
        self.assertEqual((code, data["error"]["field"]), (3, "slug"))
        self.assertFalse((self.home / "clients-index.json").exists())

    def test_L47_L203_X02_a_newer_or_malformed_index_is_exit_3_from_every_reader(self):
        self.both()
        good = json.loads((self.home / "clients-index.json").read_text())
        key = lint.digest("s:", B)

        def variant(change):
            data = json.loads(json.dumps(good))
            change(data)
            return json.dumps(data)

        variants = {
            "newer schema": variant(lambda d: d.update(schema="clients-index/2")),
            "other schema": variant(lambda d: d.update(schema="leak-index/1")),
            "other normalisation": variant(lambda d: d.update(normalisation="wall/2")),
            "other hash": variant(lambda d: d.update(hash="sha256")),
            "extra field": variant(lambda d: d.update(note="x")),
            "entries not an object": variant(lambda d: d.update(entries=[])),
            "a short digest": variant(lambda d: d["entries"][key]["names"].append("abc")),
            "a bad stamp": variant(lambda d: d["entries"][key].update(updated="yesterday")),
            "not JSON": "{\"schema\": \"clients-index/1\",",
            "not an object": "[]"}
        write(self.a / SA / "solution" / "blueprint.md", "# Blueprint\n\n## 1. Purpose\nA quote board.\n" + sections(2))
        write(self.a.joinpath(*WORK.split("/")), '{"name": "Orders"}')
        terms_folder = self.tmp / "folder to check"
        write(terms_folder / "notes.md", "Orders.\n")
        commands = (["scan", "%s/drafts/d.md" % SA], ["payload", "--strand", "001", "--kind", "board", "--file", WORK],
                    ["blueprint", "--strand", "001"], ["wall", "--text", "Orders"], ["terms", str(terms_folder)],
                    ["index"])
        write(self.a / SA / "drafts" / "d.md", "Orders.\n")
        for name, text in variants.items():
            write(self.home / "clients-index.json", text)
            for argv in commands:
                code, data = self.lint(self.a, *argv)
                self.assertEqual((code, data["ok"], data["error"]["file"]), (3, False, "<home>/clients-index.json"),
                                 (name, argv))
            self.assertEqual((self.home / "clients-index.json").read_text(), text, name)


# 2.13 The wall

class WallTest(Base):

    def setUp(self):
        super().setUp()
        self.both()

    def test_L193_L182_L183_L184_L186_one_hit_and_one_clean_pass(self):
        code, data = self.payload({"name": "Delivery terms with Marlbeck Freight",
                                   "markdown": "A cold-chain surcharge applies.\n\nThe fuel line was $187k."}, "doc")
        self.assertEqual(code, 1)
        found = {(f["field"], f["class"], f["match"]) for f in self.walls(data)}
        self.assertEqual(found, {("$.name", "name", "Marlbeck Freight"),
                                 ("$.markdown", "term", "cold-chain surcharge"), ("$.markdown", "figure", "$187k")})
        code, data = self.payload({"name": "Delivery terms with Ashby Sheet Supply",
                                   "markdown": "A delivery charge applies to large loads."}, "doc")
        self.assertEqual((code, self.walls(data)), (0, []))

    def test_L194_the_wall_is_symmetric(self):
        code, data = self.payload({"name": "Orders for Wrenfold Joinery", "description": "Not via Kestrin Boards",
                                   "label": "Rework 263,480"}, "board", record=self.b)
        self.assertEqual(code, 1)
        self.assertEqual({f["class"] for f in self.walls(data)}, {"name", "figure"})
        self.assertIn("$.description", [f["field"] for f in self.walls(data)])
        code, data = self.payload({"name": "Route board", "description": "Loads for the night desk"}, "board",
                                  record=self.b)
        self.assertEqual((code, self.walls(data)), (0, []))

    def test_L185_each_kind_of_name_blocks(self):
        for text in ("Marlbeck Freight", "Quilla Oduya", "Tollmere Fresh Market", "TFM", "Silver Lantern", "Dockon"):
            code, data = self.payload({"name": "Send it to %s" % text})
            self.assertEqual(code, 1, text)
            self.assertWall(data, "name")

    def test_L184_X25_the_other_records_figure_in_five_formats_and_round_figures_never_collide(self):
        for text in ("186730", "186,730", "$187k", "187k", "one hundred and eighty-six thousand seven hundred and "
                     "thirty", "186.7k", "$186,730"):
            code, data = self.payload({"markdown": "The fuel came to %s." % text})
            self.assertEqual(code, 1, text)
            self.assertWall(data, "figure")
        for text in ("185k", "190,000", "1,867"):
            self.assertFalse(self.walls(self.payload({"markdown": "The fuel came to %s." % text})[1]), text)
        brief = self.b / "research" / "2026-08-12-brief.md"
        write(brief, brief.read_text(encoding="utf-8") + "- The yard budget is 65,000 this year.\n")
        self.index(self.b)
        self.assertFalse(self.walls(self.payload({"markdown": "A budget of 65,000 for the saw."})[1]))
        code, data = self.payload({"count": 186730, "board_id": 186730})
        self.assertEqual([f["field"] for f in self.walls(data)], ["$.count"])  # Y08: a structural id is no figure

    def test_L187_a_term_in_both_records_passes(self):
        for root in (self.a, self.b):
            write(root / "research" / "2026-10-01-vendors.md", "# Vendors\n\nBoth use Brindlecombe Paints.\n")
            self.index(root)
        self.assertFalse(self.walls(self.payload({"name": "Brindlecombe Paints order"})[1]))
        self.assertTrue(self.walls(self.payload({"name": "Brannock Cold Store order"})[1]))

    def test_L188_X28_normalisation_on_both_sides_of_the_hash(self):
        for text in ("MARLBECK FREIGHT", "marlbeck freight", "Marlbeck Freight’s", "Marlbeck Freight's",
                     "Marlbéck Freight", "Marl​beck Freight", "Ｍａｒｌｂｅｃｋ Freight", "Mаrlbeck Freight",
                     "Marlbeck,\nFreight", "Marlbeck, Freight", "Marlbeck-Freight", "MarlbeckFreight",
                     "marlbeck_freight", "Marlbeck Freight Ltd", "perrin.haldane", "PerrinHaldane"):
            code, data = self.payload({"name": "Ask %s now" % text})
            self.assertEqual(code, 1, text)
            self.assertWall(data)

    def test_X27_fused_and_phonetic_candidates_and_their_twins(self):
        for text in ("Marlbek Frate", "Marlbek", "Brannok Cold Store"):
            self.assertTrue(self.walls(self.payload({"name": "Ask %s now" % text})[1]), text)
        for text in ("Book the slots, then dock on the east side.", "Silver paint and a lantern light the hall.",
                     "The skipper approved the route.", "Will they call at the depot? Sell it on track."):
            code, data = self.draft(text)
            self.assertEqual((code, self.walls(data)), (0, []), text)

    def test_L189_the_wall_runs_through_payload_blueprint_and_wall(self):
        self.assertEqual(self.payload({"name": "Silver Lantern feed"})[0], 1)
        code, data = self.lint(self.a, "wall", "--text", "Silver Lantern feed")
        self.assertEqual(code, 1)
        self.assertEqual(self.walls(data)[0]["field"], "line 1")
        code, data = self.lint(self.a, "wall", "--text", "Open kitchen quotes")
        self.assertEqual((code, data["findings"]), (0, []))
        self.assertNotIn("mode", data)
        write(self.a / SA / "solution" / "blueprint.md",
              "# Blueprint\n\n## 1. Purpose\nA feed from Silver Lantern.\n" + sections(2))
        code, data = self.lint(self.a, "blueprint", "--strand", "001")  # Z15: its own text makes nothing own
        self.assertEqual((code, data["mode"]), (1, "blueprint"))
        self.assertWall(data, "name", "Silver Lantern")
        self.assertEqual(self.payload({"name": "Silver Lantern feed"})[0], 0)  # X11: now a planned name of this record

    def test_L190_X21_with_no_entry_the_folder_name_alone_is_checked_and_nothing_inside_is_opened(self):
        (self.b / "CLIENT.md").unlink()
        index = json.loads((self.home / "clients-index.json").read_text())
        del index["entries"][lint.digest("s:", B)]
        write(self.home / "clients-index.json", lint.index_text(index["entries"]))
        opened, real = [], lint.read_bytes
        with mock.patch.object(lint, "read_bytes", side_effect=lambda p: opened.append(Path(p)) or real(p)):
            self.assertFalse(self.walls(self.payload({"name": "Quessel Holdings stock"})[1]))
            code, data = self.payload({"name": "Ask marlbeck-freight"})
        self.assertEqual(code, 1)
        self.assertWall(data, "slug", "marlbeck-freight")
        self.assertFalse([p for p in opened if self.b.resolve() in p.resolve().parents])

    def test_L191_X21_slugs_of_other_folders_block_and_the_own_slug_does_not(self):
        (self.home / "archive" / "fernhollow-supply").mkdir(parents=True)
        for text in ("fernhollow-supply", "Fernhollow Supply", "fernhollowsupply", "FERNHOLLOW", "marlbeck-freight"):
            code, data = self.payload({"name": "Orders for %s" % text})
            self.assertEqual(code, 1, text)
            self.assertTrue(self.walls(data), text)
        self.assertEqual([f["class"] for f in self.walls(self.payload({"name": "fernhollow-supply"})[1])], ["slug"])
        code, data = self.payload({"name": "Orders for wrenfold-joinery and Wrenfold Joinery"})
        self.assertEqual(self.walls(data), [])

    def test_L192_X41_a_wall_finding_names_nothing_only_the_other_record_holds(self):
        code, raw = self.raw(self.a, "wall", "--text", "Stock sits with Quessel Holdings; fuel $187k.")
        self.assertEqual(code, 1)
        text = raw.decode("utf-8")
        for word in ("marlbeck", "Marlbeck", B, "Brannock", "186,730", "186730", "Perrin", lint.digest("s:", B),
                     "route-board", "clients/marlbeck"):
            self.assertNotIn(word, text, word)
        data = json.loads(text)
        self.assertEqual({f["problem"] for f in self.walls(data)},
                         {"matches a name of another client record under the home",
                          "matches a figure of another client record under the home"})

    def test_L279_X45_a_draft_and_a_client_safe_block_with_another_clients_name_block(self):
        code, data = self.draft("Route data comes through Silver Lantern.\n")
        self.assertEqual(code, 1)
        self.assertWall(data, "name", "Silver Lantern")
        call = self.a / "calls" / "2026-09-29-discovery.md"
        write(call, "# Call\n\n<!-- client-safe:start -->\nThe office will copy Wendell Ayo on route notes.\n"
                    "<!-- client-safe:end -->\n")
        code, data = self.lint(self.a, "scan", "calls/2026-09-29-discovery.md")
        self.assertEqual((code, data["mode"]), (1, "client-safe-block"))
        self.assertWall(data, "name", "Wendell Ayo")

    def test_X37_summary_mode_does_not_run_the_wall(self):
        write(self.a / SA / "SUMMARY.md", "# Summary\n\nRoute data comes through Silver Lantern.\n")
        code, data = self.lint(self.a, "scan", "%s/SUMMARY.md" % SA)
        self.assertEqual((code, self.walls(data)), (0, []))

    def test_Y01_X10_an_allowlist_row_never_clears_the_wall_and_feeds_no_own_set(self):
        allow = self.a / SA / "solution" / "allowlist.md"
        write(allow, allow.read_text(encoding="utf-8") + "- Quessel Holdings [ok: yes; class: name]\n")
        code, data = self.payload({"name": "Quessel Holdings"})
        self.assertEqual(code, 1)
        self.assertWall(data, "name")
        self.assertTrue([f for f in data["findings"] if f["rule"] == "allowlist"])

    def test_X11_X27_a_draft_never_makes_another_clients_name_this_records_own(self):
        write(self.a / SA / "drafts" / "notes.md", "Ask Quessel Holdings.\n")
        write(self.a / ".work" / "notes.md", "Ask Quessel Holdings.\n")
        self.assertEqual(self.payload({"name": "Quessel Holdings"})[0], 1)
        write(self.a / "research" / "2026-10-02-partners.md", "# Partners\n\nWe also deal with Quessel Holdings.\n")
        self.assertFalse(self.walls(self.payload({"name": "Quessel Holdings"})[1]))

    def test_X30_L48_the_coverage_check(self):
        (self.home / "clients-index.json").unlink()
        shutil.rmtree(str(self.b))
        self.assertEqual(self.payload({"name": "Open quotes"})[0], 0)  # a fresh home: this record alone
        self.assertEqual(self.draft("Open quotes.")[0], 0)
        shutil.copytree(str(FIX / "records" / B), str(self.b))
        code, raw = self.raw(self.a, "payload", "--strand", "001", "--kind", "generic", "--file", WORK)
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual((code, data["error"]["file"], data["error"]["field"]), (3, "<home>/clients-index.json",
                                                                                 "entries"))
        self.assertIn("1 other client record under the home has no index entry", data["error"]["problem"])
        self.assertNotIn(b"marlbeck", raw.lower())
        for argv in (["scan", "%s/drafts/d.md" % SA], ["wall", "--text", "Open"], ["terms", str(PLUGIN / "shared")]):
            self.assertEqual(self.lint(self.a, *argv)[0], 3, argv)
        write(self.a / SA / "SUMMARY.md", "# Summary\n\nOpen quotes.\n")
        self.assertEqual(self.lint(self.a, "scan", "%s/SUMMARY.md" % SA)[0], 0)  # summary mode runs no wall
        self.index(self.b)
        self.assertEqual(self.payload({"name": "Open quotes"})[0], 0)
        (self.home / "archive" / "closed-client").mkdir(parents=True)
        self.assertEqual(self.payload({"name": "Open quotes"})[0], 0)  # a folder without CLIENT.md is a slug only
        write(self.home / "archive" / "closed-client" / "CLIENT.md", '---\nschema: "client/2"\n---\n')
        self.assertEqual(self.payload({"name": "Open quotes"})[0], 3)

    def test_L205_an_exception_inside_the_wall_is_exit_3(self):
        with mock.patch.object(lint.Wall, "hits", side_effect=RuntimeError("wall broke")):
            code, data = self.payload({"name": "Open quotes"})
        self.assertEqual((code, data["error"]["problem"]), (3, "wall broke"))

    def test_L207_a_failed_read_at_every_position_of_wall_and_index_is_exit_3(self):
        real = lint.read_bytes
        for argv in (["wall", "--text", "Open quotes"], ["index"]):
            calls = []
            with mock.patch.object(lint, "read_bytes", side_effect=lambda p: calls.append(p) or real(p)):
                self.assertEqual(self.lint(self.a, *argv)[0], 0)
            for nth in range(1, len(calls) + 1):
                count = [0]

                def failing(path, nth=nth):
                    count[0] += 1
                    if count[0] == nth:
                        raise OSError("injected")
                    return real(path)

                with mock.patch.object(lint, "read_bytes", side_effect=failing):
                    self.assertEqual(self.lint(self.a, *argv)[0], 3, (argv, nth))


# 2.11 The payload walker over every kind (X14, X22, Y08, Z10)

class PayloadKindTest(Base):

    def setUp(self):
        super().setUp()
        self.both()

    def case(self, ident):
        return next(c for c in MANIFEST["cases"] if c["id"] == ident)

    def run_case(self, ident, extra=None):
        case = self.case(ident)
        value = json.loads((FIX / case["files"][0]).read_text(encoding="utf-8"))
        if extra:
            value.update(extra)
        return case, self.payload(value, case["args"][3])

    def test_L133_to_L161_X14_every_kind_is_walked_family_by_family(self):
        self.assertEqual(sorted(c["args"][3] for c in MANIFEST["cases"] if c["id"].startswith("P-") and
                                c["role"] == "planted"), sorted(lint.KINDS))
        for kind in lint.KINDS:
            case, (code, data) = self.run_case("P-%s-p" % kind)
            self.assertEqual(code, 1, kind)
            for expect in case["expect"]:
                hits = [f for f in data["findings"] if f["rule"] == expect["rule"] and f["field"] == expect["where"]
                        and f["severity"] == expect["severity"] and expect["class"] in (None, f["class"])]
                self.assertTrue(hits, (kind, expect, data["findings"]))
            twin, (code, data) = self.run_case("P-%s-t" % kind)
            self.assertEqual(code, twin["exit"], (kind, data["findings"]))
            self.assertFalse([f for f in data["findings"] if f["severity"] == "block"], kind)

    def test_L134_L157_an_unnamed_field_of_every_kind_is_checked(self):
        for kind in lint.KINDS:
            _, (code, data) = self.run_case("P-%s-t" % kind, {"not_a_family": {"deep": [{"text": "Ask Dockon"}]}})
            self.assertEqual(code, 1, kind)
            self.assertEqual([f["field"] for f in self.walls(data)], ["$.not_a_family.deep[0].text"], kind)

    def test_L133_X22_json_inside_strings_at_every_depth_and_keys(self):
        inner = json.dumps({"board": json.dumps({"text": "Tollmere Fresh Market"})})
        code, data = self.payload({"items": [{"column_values": inner}], "Dockon": 1}, "item_batch")
        self.assertEqual(code, 1)
        fields = {f["field"] for f in self.walls(data)}
        self.assertLessEqual({"$.Dockon<key>", "$.items[0].column_values<json>.board<json>.text"}, fields)

    def test_L154_a_recipient_list_is_checked_entry_by_entry(self):
        recipients = ["orders@wrenfoldjoinery.example", "tamsin.rook@homes.example", "night@marlbeckfreight.example"]
        code, data = self.payload({"name": "Follow-ups", "recipients": recipients}, "sequence")
        self.assertEqual(code, 1)
        fields = {(f["field"], f["rule"]) for f in data["findings"] if f["severity"] == "block"}
        self.assertEqual(fields, {("$.recipients[1]", "exclusion"), ("$.recipients[2]", "wall")})
        code, data = self.payload({"name": "Follow-ups", "recipients": recipients[:1]}, "sequence")
        self.assertEqual(code, 0, data["findings"])

    def test_L155_a_webhook_url_with_a_token_a_path_or_another_clients_name_blocks(self):
        for url, rule in (("https://hooks.example/in?token=Fx7kQ2mL9pR4", "credential"),
                          ("https://hooks.example/clients/wrenfold-joinery/calls/x", "term"),
                          ("https://hooks.example/in/kestrin-boards", "exclusion"),
                          ("https://marlbeckfreight.example/in", "wall")):
            code, data = self.payload({"url": url}, "webhook")
            self.assertEqual(code, 1, url)
            self.assertIn(rule, [f["rule"] for f in data["findings"]], url)
        self.assertEqual(self.payload({"url": "https://hooks.example/in/orders"}, "webhook")[0], 0)

    def test_L157_another_clients_name_reaches_no_ai_field(self):
        for kind, value, field in (("agent", {"profile": {"name": "Perrin Haldane helper"}}, "$.profile.name"),
                                   ("vibe_app", {"prompt": "Build a board like Dockon"}, "$.prompt"),
                                   ("sequence", {"recipients": ["perrin.haldane@marlbeckfreight.example"]},
                                    "$.recipients[0]")):
            code, data = self.payload(value, kind)
            self.assertEqual(code, 1, kind)
            self.assertIn(field, [f["field"] for f in self.walls(data)], kind)


# 2.12 blueprint (X08, X09, X36)

class BlueprintTest(Base):

    def setUp(self):
        super().setUp()
        self.both()
        self.path = self.a / SA / "solution" / "blueprint.md"

    def blueprint(self, text):
        write(self.path, text)
        return self.lint(self.a, "blueprint", "--strand", "001")

    def test_L163_X36_the_fixture_blueprint_and_its_glossary(self):
        for ident in ("R10c-p", "R10c-t"):
            case = next(c for c in MANIFEST["cases"] if c["id"] == ident)
            code, data = self.blueprint((FIX / case["files"][0]).read_text(encoding="utf-8"))
            self.assertEqual((code, data["mode"], data["strand"]), (case["exit"], "blueprint", "001"), ident)
            for expect in case["expect"]:
                self.assertTrue([f for f in data["findings"] if f["rule"] == expect["rule"] and
                                 f["field"] == expect["where"]], ident)
        code, data = self.blueprint("# B\n\n## 1. Terms\n<!-- glossary:start -->\n- cutting list: the cutting list "
                                    "names each panel by cabinet [X]\n<!-- glossary:end -->\n" + sections(2))
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["class"]) for f in data["findings"] if f["severity"] == "block"],
                         [("term", "markers")])

    def test_L162_planned_names_under_the_name_rules_and_the_wall(self):
        code, data = self.blueprint("# B\n\n## 1. Purpose\nA board.\n" + sections(2, 3) + "\n## 4. Names\n"
                                    "- Board: Thymbel quotes\n- Group: Silver Lantern feed\n" + sections(5))
        self.assertEqual(code, 1)
        self.assertEqual({(f["rule"], f["class"]) for f in data["findings"] if f["severity"] == "block"},
                         {("term", "firm"), ("wall", "name")})

    def test_X09_only_the_client_facing_text_is_checked(self):
        text = ("# B\n\n## 1. Purpose\nA quote board.\n" + sections(2) + "\n## Build notes\n[A] check with "
                "Silver Lantern.\n\n### Prompt K1\n```text\nAsk TFM first.\n```\n")
        code, data = self.blueprint(text)
        self.assertEqual(code, 1)
        self.assertEqual([(f["field"], f["rule"]) for f in data["findings"] if f["severity"] == "block"],
                         [("line %d" % (text.split("\n").index("Ask TFM first.") + 1), "wall")])

    def test_X09_no_numbered_section_or_no_blueprint_is_exit_3(self):
        code, data = self.blueprint("# B\n\n## Purpose\nA quote board.\n")
        self.assertEqual((code, data["error"]["problem"]), (3, "cannot find sections 1 to 15"))
        self.path.unlink()
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual((code, data["error"]["file"]), (3, "%s/solution/blueprint.md" % SA))
        self.assertEqual(self.lint(self.a, "blueprint", "--strand", "009")[0], 3)

    def test_X09_malformed_glossary_marks_exempt_nothing_and_warn(self):
        # A33 (R68): the blueprint meets no copied-run rule, so the run under the broken mark no longer blocks; the
        # mark still warns, and every rule the blueprint keeps still runs on the text after it.
        code, data = self.blueprint("# B\n\n## 1. Terms\n<!-- glossary:start -->\n- cutting list: the cutting list "
                                    "names each panel by cabinet\n" + sections(2))
        self.assertEqual(code, 2)
        self.assertEqual(sorted((f["rule"], f["severity"]) for f in data["findings"]), [("copied-run", "warn")])
        code, data = self.blueprint("# B\n\n## 1. Terms\n<!-- glossary:start -->\n- cutting list: the cutting list "
                                    "names each panel [X]\n" + sections(2))
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["class"]) for f in data["findings"] if f["severity"] == "block"],
                         [("term", "markers")])

    def test_X11_the_blueprints_own_internal_text_still_counts(self):
        # A33 (R68): the blueprint's own text meets no copied-run rule, but its internal sections still count as a
        # source for every payload, which keeps the rule.
        code, data = self.blueprint("# B\n\n## 1. Purpose\nVeneer offcuts warp beside the kiln vents.\n" + sections(2) +
                                    "\n## Build notes\n- Veneer offcuts warp beside the kiln vents every winter.\n")
        self.assertEqual((code, data["findings"]), (0, []))
        code, data = self.payload({"description": "Veneer offcuts warp beside the kiln vents."})
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["source"]) for f in data["findings"] if f["severity"] == "block"],
                         [("copied-run", SA + "/solution/blueprint.md")])

    def test_A33_R68_the_blueprint_keeps_the_wall_and_a_payload_keeps_runs_and_quotes(self):
        code, data = self.blueprint("# B\n\n## 1. Purpose\nThe cutting list names each panel by cabinet, for "
                                    "Marlbeck Freight.\n" + sections(2))
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["class"]) for f in data["findings"] if f["severity"] == "block"],
                         [("wall", "name")])
        code, data = self.payload({"description": "The cutting list names each panel by cabinet."})
        self.assertEqual([f["rule"] for f in data["findings"] if f["severity"] == "block"], ["copied-run"])


# 2.14 terms (X31)

class TermsTest(Base):

    def terms(self, folder):
        return self.lint(None, "terms", str(folder))

    def shared_copy(self):
        copy = self.tmp / "shared copy"
        shutil.copytree(str(PLUGIN / "shared"), str(copy))
        return copy

    def test_L197_terms_over_the_real_shared_folder_exits_0(self):
        self.both()
        code, data = self.terms(PLUGIN / "shared")
        self.assertEqual((code, data["findings"]), (0, []))
        self.assertEqual((data["entries_compared"], data["slugs_compared"], data["strand"]), (2, 2, None))
        self.assertIn("<plugin>/shared/leak-terms.txt", [i["file"] for i in data["inputs"]])

    def test_L195_L196_a_planted_client_name_exits_1_naming_the_file_and_line(self):
        self.both()
        copy = self.shared_copy()
        target = copy / "safety.md"
        lines = target.read_text(encoding="utf-8").split("\n")
        lines.insert(3, "An example customer is Tollmere Fresh Market.")
        write(target, "\n".join(lines))
        code, data = self.terms(copy)
        self.assertEqual(code, 1)
        hits = self.walls(data)
        self.assertEqual({(f["file"], f["field"], f["class"]) for f in hits}, {("safety.md", "line 4", "name")})
        self.assertEqual(self.lint(self.a, "wall", "--text", "An example customer is Tollmere Fresh Market.")[0], 1)
        source = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        # one digest function for every side (L196), shared with record.py init through mmb_common since R39
        self.assertEqual(source.count("hexdigest()[:32]"), 0)
        self.assertIn("\ndigest = mc.digest", source)
        self.assertEqual((SCRIPTS / "mmb_common.py").read_text(encoding="utf-8").count("hexdigest()[:32]"), 1)
        execute = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == "execute")
        self.assertEqual(ast.get_source_segment(source, execute).count("wall_hits(self.run, self)"), 4)

    def test_L198_X30_the_counts_and_the_empty_home(self):
        shutil.rmtree(str(self.home / "clients"))
        code, data = self.terms(PLUGIN / "shared")
        self.assertEqual((code, data["entries_compared"], data["slugs_compared"]), (0, 0, 0))
        self.assertIn({"file": "<home>/clients-index.json", "state": "absent"}, data["inputs"])
        shutil.copytree(str(FIX / "records" / B), str(self.b))
        self.assertEqual(self.terms(PLUGIN / "shared")[0], 3)  # a record with no entry: X30

    def test_X31_the_firm_rule_runs_and_the_shipped_rows_do_not(self):
        self.both()
        folder = self.tmp / "folder"
        write(folder / "a.md", "Built by Thymbel Advisory.\n")
        write(folder / "b.md", "The cost of waiting and [Q] markers, P3 and clients/x/calls/ stay here.\n")
        write(folder / "c.md", "Stored with a thimble.\n")
        code, data = self.terms(folder)
        self.assertEqual(code, 1)
        self.assertEqual([(f["file"], f["rule"], f["class"]) for f in data["findings"]], [("a.md", "term", "firm")])

    def test_X31_Z14_what_terms_reads_and_where_it_stops(self):
        self.both()
        folder = self.tmp / "folder"
        write(folder / "notes.yml", "owner: Wendell Ayo\n")
        write(folder / ".gitkeep", "")
        write(folder / ".git" / "objects" / "blob", "Wendell Ayo")
        write(folder / "__pycache__" / "x.pyc", "Wendell Ayo")
        write(folder / ".DS_Store", "Wendell Ayo")
        (folder / "pack.docx").write_bytes(docx_bytes({"word/document.xml": BODY % "Ask Dockon."}))
        code, data = self.terms(folder)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(f["file"] for f in data["findings"]), ["notes.yml", "pack.docx"])
        write(folder / "image.png", "not text")
        code, data = self.terms(folder)
        self.assertEqual((code, data["error"]["file"]), (3, "image.png"))
        (folder / "image.png").unlink()
        (folder / "bad.md").write_bytes(b"\xff\xfe")
        self.assertEqual(self.terms(folder)[0], 3)
        (folder / "bad.md").unlink()
        (self.home / "local" / "settings.json").unlink()
        self.assertEqual(self.terms(folder)[0], 3)
        self.assertEqual(self.terms(self.tmp / "no such folder")[0], 3)


# The frame for the new commands

class FrameTest(Base):

    def test_X08_no_command_answers_not_built_yet(self):
        source = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        self.assertNotIn("not built", source)
        self.assertNotIn("wall_guard", source)
        self.assertEqual(set(lint.COMMANDS), {"scan", "payload", "blueprint", "wall", "terms", "index"})
        self.assertNotIn(None, [lint.COMMANDS[name] for name in lint.COMMANDS])

    def test_L09_X29_only_index_writes_and_only_the_index_its_backup_and_the_mutex(self):
        before = tree(self.home)
        self.lint(self.a, "wall", "--text", "Open quotes")
        self.lint(None, "terms", str(PLUGIN / "shared"))
        self.assertEqual(tree(self.home), before)
        self.both()
        self.index(self.a)
        added = sorted(set(tree(self.home)) - set(before))
        self.assertEqual(added[:4], [".work", ".work/record.mutex", "clients-index.json", "local/backup"])
        self.assertEqual(len(added), 5)
        self.assertTrue(added[4].startswith("local/backup/clients-index.json.20261017T093000"), added)

    def test_L04_G49_the_plugin_copy_is_unchanged_after_every_new_subcommand(self):
        plugin = self.tmp / "plugin copy"
        shutil.copytree(str(PLUGIN / "shared"), str(plugin / "shared"))
        (plugin / "scripts").mkdir()
        for name in ("mmb_common.py", "leak_lint.py"):
            shutil.copy(str(SCRIPTS / name), str(plugin / "scripts" / name))
        listing = tree(plugin)
        write(self.a / SA / "solution" / "blueprint.md", "# B\n\n## 1. Purpose\nA quote board.\n" + sections(2))
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        forms = (["index"], ["--record", str(self.b), "index"], ["blueprint", "--strand", "001"],
                 ["wall", "--text", "Ask Silver Lantern"], ["terms", str(plugin / "shared")],
                 ["payload", "--strand", "001", "--kind", "board", "--file", WORK])
        write(self.a.joinpath(*WORK.split("/")), '{"name": "Open quotes"}')
        codes = []
        for form in forms:
            argv = form if form[0] == "--record" else ["--record", str(self.a)] + form
            done = subprocess.run([sys.executable, str(plugin / "scripts" / "leak_lint.py")] + argv, env=env,
                                  cwd=str(self.tmp), capture_output=True)
            json.loads(done.stdout.decode("utf-8"))
            codes.append(done.returncode)
        self.assertEqual(codes, [0, 0, 0, 1, 0, 0])
        self.assertEqual(tree(plugin), listing)

    def test_L02_python_3_9_syntax(self):
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))


# The review of part 2 (leak-review-part2.md, G01 to G29), and DECISIONS R29 onward. Every name, figure and id is
# invented; the lines added to record b stand for another client's record.

class ReviewPart2Test(Base):

    def setUp(self):
        super().setUp()
        self.brief = self.b / "research" / "2026-08-12-brief.md"

    def add_to_b(self, *lines, index=True):
        write(self.brief, self.brief.read_text(encoding="utf-8") + "".join("- %s\n" % line for line in lines))
        if index:
            self.both()

    def text(self, text, record=None):
        return self.lint(record or self.a, "wall", "--text", text)

    def test_G01_X31_L195_U1_a_name_leaked_into_shared_stays_in_its_entry_and_terms_blocks_it(self):
        self.add_to_b("Odalys Brekke asked for the Tallowmere sync.")
        plugin = self.tmp / "plugin copy"
        shutil.copytree(str(PLUGIN / "shared"), str(plugin / "shared"))
        target = plugin / "shared" / "monday-gotchas.md"
        write(target, target.read_text(encoding="utf-8") +
              "\n- Example: Odalys Brekke asked for Tallowmere sync on the depot board.\n")
        with mock.patch.object(lint, "PLUGIN", plugin):
            self.index(self.b)  # the next intake of record b, with the leak already in shared/
            code, data = self.lint(None, "terms", str(plugin / "shared"))
            self.assertEqual(code, 1)
            self.assertEqual({f["file"] for f in self.walls(data)}, {"monday-gotchas.md"})
            for text in ("Open Tallowmere today.", "Ask Odalys Brekke."):
                self.assertEqual(self.text(text)[0], 1, text)

    def test_G01_Z12_the_embedded_shared_words_equal_the_shipped_shared_folder(self):
        live = lint.shared_vocabulary()
        # The source check L05 bars one tool name from the script text; leaving it out of the stop list only keeps
        # it as a name when a record writes it, which can block but never pass.
        self.assertEqual(sorted(live - lint.SHARED_WORDS - {"pdftotext"}), [],
                         "shared/ has words the reviewed list lacks")
        self.assertEqual(sorted(lint.SHARED_WORDS - live), [], "the reviewed list has words shared/ no longer holds")
        source = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        stop = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == "wall_stop")
        self.assertNotIn("iterdir", ast.get_source_segment(source, stop))


    def test_G02_X28_letters_with_no_decomposition_meet_their_plain_spellings(self):
        self.add_to_b("Østby Freight takes the loads.", "Łukasz Dærvel runs the yard.", "Đorin Sæther signs the sheets.")
        for text in ("Ask Ostby about the loads.", "Ask Oestby about the loads.", "Ask Daervel today.",
                     "Ask Darvel today.", "Ask Saether today.", "Ask Sather today.", "Ask Lukasz today.",
                     "Ask Dorin today.", "Ask Østby about the loads."):
            self.assertEqual(self.text(text)[0], 1, text)
        self.assertEqual(lint.fold_text("ØÆŒŁĐÐÞĦŦ"), "oaeoeldd" + "thht")

    def test_G02_X28_the_other_way_round_a_plain_record_name_meets_the_special_letter(self):
        self.add_to_b("Ostby Freight takes the loads.", "Oestgard Haulage runs the yard.", "Saether Mills packs.")
        for text in ("Ask Østby about the loads.", "Ask Østgard today.", "Ask Sæther today."):
            self.assertEqual(self.text(text)[0], 1, text)


    def test_G03_X27_a_name_broken_by_a_line_end_hyphen_or_a_markdown_mark_is_fused(self):
        self.add_to_b("Tallowmere is the stock app.", "Fernhollow runs the depots.", "Ontrack plans the routes.")
        for text in ("Open the Tallow-\nmere app today.", "Open the Tallow- \n\tmere app today.",
                     "Ask Fern-\nhollow about the depots.", "Ask Fern- \n hollow about the depots.",
                     "Ask Marl-\nbeck about the loads.", "Ask Marl-\t\n  beck about the loads.",
                     "Open Tallow**mere** today.", "Open Tallow*mere* today.", "Open Tallow~~mere~~ today.",
                     "Open Tallow`mere` today.", "Open **Tallow**mere today.", "Open Tallow__mere__ today."):
            self.assertEqual(self.text(text)[0], 1, text)
        code, data = self.payload({"name": "Stock notes", "markdown": "Open the Tallow-\nmere app."}, "doc")
        self.assertEqual(code, 1)
        self.assertWall(data, "name")
        # A real compound broken at a line end keeps its spaced twin; the hyphen form adds the fused word only.
        tokens, gaps = lint.wall_cut("Blue-\nHarbour")
        self.assertEqual({(form, fused) for _, _, form, fused in lint.wall_candidates(tokens, gaps)},
                         {("blue", False), ("harbour", False), ("blue harbour", False), ("blueharbour", True)})
        self.add_to_b("Blue Harbour packs the crates.")
        self.assertEqual(self.text("Ask Blue-\nHarbour today.")[0], 1)
        # Clean: words that stay apart are not fused, so the ordinary words never become the product Ontrack.
        for text in ("Open the stock app today, then go.\n\nMere details follow.", "We are on\ntrack today.",
                     "We are on -\ntrack today.", "We are on\n- track today.", "We are **on** track today.",
                     "We are on *track* today.", "We are on-\n\ntrack today.", "Keep the stock-\nroom tidy."):
            self.assertEqual(self.text(text)[0], 0, text)


    def test_G04_U1_X26_a_partner_name_of_two_ordinary_or_shared_words_is_published_and_blocks(self):
        self.add_to_b("Their marketing partner is Green Field.", "Their rota tool comes from Clear Path.",
                      "Their night loads go through Signal Path.", "Blue Harbour packs the crates.",
                      "the board sits in Native CRM and syncs with Monday CRM each Friday in March.")
        names = set(self.entry(B)["names"])
        for name in ("green field", "clear path", "signal path", "blue harbour"):
            self.assertIn(lint.digest("n:", name), names, name)
        for text in ("We use Green Field for coastal runs.", "The rota sits in Clear Path.",
                     "We booked Signal Path for the night loads.", "Ask Blue Harbour today."):
            self.assertEqual(self.text(text)[0], 1, text)
        # Clean: a run that shared/ itself writes as a phrase, and a run made only of X26's own small stop list
        # (days, months, product words, titles), are still dropped; so are the single shared/ words (Z12).
        for name in ("native crm", "monday crm", "signal", "path"):
            self.assertNotIn(lint.digest("n:", name), names, name)
        for text in ("Our leads sit in Native CRM now.", "We sync Monday CRM each Friday in March.",
                     "Send the signal down the path."):
            self.assertEqual(self.text(text)[0], 0, text)

    def test_G04_Z12_the_embedded_shared_phrases_equal_the_shipped_shared_folder(self):
        live = lint.shared_phrases()
        self.assertEqual(sorted(live - lint.SHARED_PHRASES), [], "shared/ has phrases the reviewed list lacks")
        self.assertEqual(sorted(lint.SHARED_PHRASES - live), [], "the reviewed list has phrases shared/ no longer holds")
        self.assertIn("native crm", lint.SHARED_PHRASES)
        source = (SCRIPTS / "leak_lint.py").read_text(encoding="utf-8")
        tree_ = ast.parse(source)
        for name in ("wall_stop", "kept"):
            node = next(n for n in ast.walk(tree_) if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertNotIn("iterdir", ast.get_source_segment(source, node))

    def exclude_in_b(self, *rows):
        path = self.b / SB / "solution" / "exclusions.md"
        write(path, path.read_text(encoding="utf-8") + "".join(
            "- %s [kind: %s; added: 2026-10-20; by: the user; source: the second call]\n" % row for row in rows))
        self.both()

    def test_G05_R33_U1_X26_an_exclusion_term_of_five_words_or_more_blocks_on_the_wall(self):
        self.exclude_in_b(("night shift overtime rebate scheme", "term"), ("Harrow Lane yard expansion plan", "name"),
                          ("the depot lease buyback", "term"))
        for text in ("We run the night shift overtime rebate scheme too.",
                     "We run the night-shift-overtime-rebate-scheme too.",
                     "The Harrow Lane yard expansion plan starts soon.",
                     "We run the depot lease buyback too.",  # the four-word control, which blocked before
                     "We keep the overtime rebate scheme.", "Walk round Harrow Lane yard first.",
                     "Our rebate scheme is new.", "We cover the night shift.", "The expansion plan is out."):
            # the last three are two-word slices of the long terms, which the user accepted would block (R33)
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertTrue(self.walls(data, "term") or self.walls(data, "name"), text)

    def test_G05_R33_a_window_of_common_words_only_is_not_published(self):
        self.exclude_in_b(("crate return for the night", "term"))
        terms = set(self.entry(B)["terms"])
        for window in ("crate return", "cratereturn", "crate return for", "crate return for the"):
            self.assertIn(lint.digest("n:", window), terms, window)
        for window in ("for the night", "forthenight", "the night", "return for", "return for the night"):
            self.assertNotIn(lint.digest("n:", window), terms, window)
        self.assertEqual(self.text("Send the crate return to the yard.")[0], 1)
        for text in ("Book the room for the night.", "Plan the return for the night shift."):
            self.assertEqual(self.text(text)[0], 0, text)

    def test_G05_R33_a_term_of_four_words_or_fewer_publishes_what_it_did_before(self):
        self.exclude_in_b(("the depot lease buyback", "term"), ("Brindle Tiles Ltd", "name"))
        expected = set()
        for term in ("cold-chain surcharge", "the depot lease buyback", "Brindle Tiles Ltd"):
            expected |= {lint.digest("n:", form) for form in lint.spaced_and_fused(term)}
        self.assertEqual(set(self.entry(B)["terms"]), expected)
        self.assertEqual(self.text("The depot lease is new.")[0], 0)  # no slice of a short term


    def test_G06_R34_X22_L134_a_json_string_literal_is_walked_as_its_own_unit(self):
        self.add_to_b("Østby Freight takes the loads.", "Tallowmere is the stock app.")
        # The text column's value as json.dumps writes it, with its \u escapes; a zero-width space before an object.
        cases = (({"board_id": 41873925, "column_id": "text", "value": json.dumps("Ask Østby about the loads")},
                  "$.value<json>"),
                 ({"value": json.dumps("Tällowmere desk")}, "$.value<json>"),
                 ({"column_values": "​" + json.dumps({"text_1": "Ask Østby about the loads"})},
                  "$.column_values<json>.text_1"),
                 ({"column_values": json.dumps(json.dumps({"text_1": "Open Tallowmere today"}))},
                  "$.column_values<json><json>.text_1"),
                 # the controls, which blocked before: the plain string, the object, JSON nested twice
                 ({"value": "Ask Østby about the loads"}, "$.value"),
                 ({"column_values": json.dumps({"text_1": "Ask Østby about the loads"})},
                  "$.column_values<json>.text_1"),
                 ({"column_values": json.dumps({"board": json.dumps({"text": "Open Tallowmere today"})})},
                  "$.column_values<json>.board<json>.text"))
        for value, field in cases:
            code, data = self.payload(value, "item_batch")
            self.assertEqual(code, 1, value)
            self.assertIn(field, [f["field"] for f in self.walls(data)], value)
        # Clean: a string that starts with a quote but is not JSON is checked as raw text only, with no error;
        # a JSON string literal of ordinary words passes.
        for value in ({"value": '"Quoted" is how the depot sheet labels it'}, {"value": '"unclosed quote'},
                      {"value": json.dumps("Ask the depot about the loads")}, {"value": '​"Plain words"'}):
            code, data = self.payload(value, "item_batch")
            self.assertEqual(code, 0, (value, data["findings"]))


    def clone(self, source, root, slug, name, *lines):
        """A copy of a planted record at <home>/<root>/<slug>, its CLIENT.md slug and name changed and lines added
        to its research brief."""
        target = self.home / root / slug
        shutil.copytree(str(source), str(target))
        client = target / "CLIENT.md"
        text = client.read_text(encoding="utf-8").split("\n")
        text = [('slug: "%s"' % slug) if l.startswith("slug: ") else ('name: "%s"' % name) if l.startswith("name: ")
                else l for l in text]
        write(client, "\n".join(text))
        brief = next((target / "research").glob("*.md"))
        write(brief, brief.read_text(encoding="utf-8") + "".join("- %s\n" % line for line in lines))
        return target

    def g07_home(self):
        """G07's home: an archived client at archive/brindle-tiles, indexed, a new and different client created
        at clients/brindle-tiles, and a third record, clients/corbel-hire; the planted records removed."""
        old = self.clone(self.b, "clients", "brindle-tiles", "Brindle Tiles Ltd",
                         "Tallowmere is the stock app.", "Odalys Brekke runs the yard.")
        third = self.clone(self.a, "clients", "corbel-hire", "Corbel Hire")
        shutil.rmtree(str(self.a))
        shutil.rmtree(str(self.b))
        self.index(old)
        self.index(third)
        (self.home / "archive").mkdir()
        archived = self.home / "archive" / "brindle-tiles"
        shutil.move(str(old), str(archived))
        new = self.clone(self.a.parent / "corbel-hire", "clients", "brindle-tiles", "Brindle Tiles Co")
        return archived, new, third

    def test_G07_R35_X29_L178_two_records_with_one_slug_never_take_the_archived_clients_wall(self):
        archived, new, third = self.g07_home()
        before = self.entry("brindle-tiles")
        # The twin folder is there: every wall and index run from either record of that slug stops.
        for record, argv in ((new, ["wall", "--text", "Open Tallowmere today."]), (new, ["index"]),
                             (archived, ["wall", "--text", "Open Tallowmere today."]), (archived, ["index"])):
            code, data = self.lint(record, *argv)
            self.assertEqual(code, 3, (record.parent.name, argv))
            for text in ("brindle-tiles", "Brindle", "Tallowmere"):  # X30: the error names no folder and no name
                self.assertNotIn(text.lower(), json.dumps(data["error"]).lower())
        self.assertEqual(self.entry("brindle-tiles"), before)
        for text in ("Open Tallowmere today.", "Ask Odalys Brekke."):
            self.assertEqual(self.text(text, third)[0], 1, text)
        # The archived folder gone (X29: its entry stays): index still will not replace the other client's entry,
        # and the new record's wall holds that entry as another client's, not its own.
        shutil.rmtree(str(archived))
        code, data = self.lint(new, "index")
        self.assertEqual((code, data["error"]["file"]), (3, "<home>/clients-index.json"))
        self.assertNotIn("brindle", json.dumps(data["error"]).lower())
        self.assertEqual(self.entry("brindle-tiles"), before)
        for text in ("Open Tallowmere today.", "Ask Odalys Brekke."):
            self.assertEqual(self.text(text, third)[0], 1, text)
            self.assertEqual(self.text(text, new)[0], 1, text)
        self.assertEqual(self.text("Ask Brindle Tiles Co about the order.", new)[0], 0)  # its own name: O

    def test_G07_R35_an_archived_record_with_no_twin_and_a_same_name_reindex_work_as_before(self):
        archived, new, third = self.g07_home()
        shutil.rmtree(str(new))
        self.assertEqual(self.text("Open Tallowmere today.", archived)[0], 0)  # its own name, from the archive
        self.assertEqual(self.text("Open Tallowmere today.", third)[0], 1)
        brief = next((archived / "research").glob("*.md"))
        write(brief, brief.read_text(encoding="utf-8") + "- Quarrow Pine supplies the battens.\n")
        self.assertTrue(self.index(archived)["written"])  # same CLIENT.md name: its own entry is replaced
        self.assertIn(lint.digest("n:", "quarrow pine"), self.entry("brindle-tiles")["names"])
        for text in ("Open Tallowmere today.", "Ask Quarrow Pine for battens."):
            self.assertEqual(self.text(text, third)[0], 1, text)
        self.assertFalse(self.index(third)["written"])

    def r40_home(self):
        """R40's home: a client named Blue Harbour Logistics at clients/larch-depot, indexed with `Tallowmere`, and a
        third record, clients/corbel-hire; the planted records removed. Neither the old name nor the new one shares
        a word with the slug, so only the index entry tells them (R35's name test)."""
        renamed = self.clone(self.b, "clients", "larch-depot", "Blue Harbour Logistics", "Tallowmere is the stock app.")
        third = self.clone(self.a, "clients", "corbel-hire", "Corbel Hire")
        shutil.rmtree(str(self.a))
        shutil.rmtree(str(self.b))
        self.index(renamed)
        self.index(third)
        return renamed, third

    def rename(self, record, name):
        """record.py client rename, in process; a real record has its log, which the planted ones lack."""
        if not (record / "log.md").exists():
            write(record / "log.md", '---\nschema: "log/1"\nclient: "%s"\n---\n# Log\n' % record.name)
        out = io.StringIO()
        with mock.patch.object(sys, "stdout", out):
            code = load(SCRIPTS / "record.py", "record_wall").main(["--record", str(record), "client", "rename",
                                                                    "--name", name])
        self.assertEqual(code, 0, out.getvalue())

    def hand_rename(self, record, name, former=None):
        client = record / "CLIENT.md"
        text = mc.set_front_matter(client.read_text(encoding="utf-8"), dict(
            {"name": name}, **({"former_names": former} if former is not None else {})))
        write(client, text)

    def renamed_works(self, renamed, third, by_record_py=False):
        """R40: index replaces the renamed record's entry; from the third record its old name, its new name and a
        name added after the rename block; its own text with both names passes. R48: record.py client rename has
        already run index after its write, so a rerun then writes nothing."""
        self.assertEqual(self.index(renamed)["written"], not by_record_py)
        names = self.entry("larch-depot")["names"]
        for name in ("Blue Harbour Logistics", "Østby Freight", "Tallowmere"):
            self.assertIn(lint.name_key(name), names, name)
        write(next((renamed / "research").glob("*.md")), next((renamed / "research").glob("*.md")).read_text(
            encoding="utf-8") + "- Quarrow Pine supplies the battens.\n")
        self.assertTrue(self.index(renamed)["written"])
        for text in ("Ask Blue Harbour Logistics about the loads.", "Ask Østby Freight about the loads.",
                     "Ask Quarrow Pine for battens.", "Open Tallowmere today."):
            self.assertEqual(self.text(text, third)[0], 1, text)
        self.assertEqual(self.text("Blue Harbour Logistics is now Østby Freight; Quarrow Pine and Tallowmere stay.",
                                   renamed)[0], 0)

    def test_R40_X29_a_client_renamed_through_record_py_keeps_its_entry_and_its_old_name_walled(self):
        renamed, third = self.r40_home()
        self.rename(renamed, "Østby Freight")
        self.assertEqual(mc.front_matter((renamed / "CLIENT.md").read_text(encoding="utf-8"))["former_names"],
                         "Blue Harbour Logistics")
        self.renamed_works(renamed, third, by_record_py=True)

    def test_R40_a_rename_by_hand_with_the_old_name_in_former_names_works_alike(self):
        renamed, third = self.r40_home()
        self.hand_rename(renamed, "Østby Freight", "Blue Harbour Logistics")
        self.renamed_works(renamed, third)

    def test_R40_R35_a_rename_by_hand_without_the_old_name_is_still_refused(self):
        renamed, third = self.r40_home()
        before = self.entry("larch-depot")
        for former in (None, "", "Brindle Tiles Ltd"):  # another client's name in former_names is not the old one
            self.hand_rename(renamed, "Østby Freight", former)
            code, data = self.lint(renamed, "index")
            self.assertEqual((code, data["error"]["file"], data["error"]["field"]),
                             (3, "<home>/clients-index.json", "entries"), former)
            self.assertNotIn("blue harbour", json.dumps(data["error"]).lower())
            self.assertEqual(self.entry("larch-depot"), before)
            self.assertEqual(self.text("Ask Blue Harbour Logistics about the loads.", third)[0], 1)

    def assertNamesNoOtherFolder(self, data, code, root):
        """G08: exit 3 with an error on the home root, and no slug or name of record b anywhere in the envelope."""
        self.assertEqual((code, (data.get("error") or {}).get("file")), (3, root), data.get("error"))
        for text in (B, "marlbeck", "Tallowmere"):
            self.assertNotIn(text.lower(), json.dumps(data).lower())

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "mode 000 does not deny access here")
    def test_G08_R36_X30_A24_L205_a_record_folder_that_cannot_be_searched_is_exit_3_naming_no_folder(self):
        self.add_to_b("Tallowmere is the stock app.", index=False)  # record b present and never indexed
        self.index(self.a)
        os.chmod(str(self.b), 0)
        try:
            for run in (lambda: self.text("Open Tallowmere today."),
                        lambda: self.payload({"name": "Tallowmere loads"})):
                code, data = run()
                self.assertNamesNoOtherFolder(data, code, "<home>/clients/")
                self.assertEqual((data["error"]["field"], data["error"]["problem"]),
                                 ("entries", "a folder under the home cannot be read, so the wall cannot tell "
                                  "whether it is a client record"))
        finally:
            os.chmod(str(self.b), 0o755)
        self.assertEqual(self.text("Open Tallowmere today.")[0], 3)  # readable again: X30's coverage check
        self.index(self.b)
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "a mode without search does not deny access here")
    def test_G08_R36_R35_A24_an_archive_that_can_be_listed_but_not_searched_is_exit_3_naming_no_folder(self):
        self.add_to_b("Tallowmere is the stock app.", index=False)
        self.index(self.a)
        archive = self.home / "archive"
        archive.mkdir()
        shutil.move(str(self.b), str(archive / B))
        os.chmod(str(archive), 0o400)  # the names can be listed; nothing under them can be looked at
        try:
            for run in (lambda: self.text("Open Tallowmere today."), lambda: self.payload({"name": "Tallowmere loads"}),
                        lambda: self.lint(self.a, "index")):
                code, data = run()
                self.assertNamesNoOtherFolder(data, code, "<home>/archive/")
        finally:
            os.chmod(str(archive), 0o755)


    G09_BLUEPRINT = ("# Blueprint\n\n## 1. Purpose\nA quote board.\n" + sections(2, 3) + "\n## 4. Boards\n"
                     "Jobs board, with a Tallowmere sync column for depot loads.\n" + sections(5))

    def g09_blueprint(self, strand=SA, frozen=()):
        """The finding's blueprint in a strand of record a, with byte-equal frozen copies as record.py freeze
        writes them at approval."""
        write(self.a / strand / "solution" / "blueprint.md", self.G09_BLUEPRINT)
        for version in frozen:
            write(self.a / strand / "versions" / version, self.G09_BLUEPRINT)

    def test_G09_R37_Z15_X45_L189_the_frozen_blueprint_copy_never_makes_its_own_words_this_records(self):
        self.add_to_b("Tallowmere is the stock app.")
        self.g09_blueprint()
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual(code, 1)
        self.assertWall(data, "name", "Tallowmere")
        for frozen in (["v0.1/blueprint-r1.md"], ["v0.1/blueprint-r1.md", "v0.2/blueprint-r2.md"]):
            self.g09_blueprint(frozen=frozen)
            code, data = self.lint(self.a, "blueprint", "--strand", "001")  # the build guard, after the freeze
            self.assertEqual(code, 1, frozen)
            self.assertWall(data, "name", "Tallowmere")
        # X11 as decided: the blueprint's client-facing lines are O for payloads, so the planned name passes there.
        self.assertEqual(self.payload({"name": "Tallowmere sync"})[0], 0)

    def test_G09_R37_a_word_held_outside_this_strands_blueprint_files_is_still_this_records(self):
        self.add_to_b("Tallowmere is the stock app.")
        self.g09_blueprint(frozen=["v0.1/blueprint-r1.md"])
        brief = self.a / "research" / "2026-09-01-brief.md"
        before = brief.read_text(encoding="utf-8")
        # Clean: another file of this record that holds the word keeps it this record's (Z15).
        write(brief, before + "- They want Tallowmere synced with the quote board.\n")
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
        write(brief, before)
        # Clean: another strand's blueprint, and its frozen copy alone, are O sources for this strand's check.
        other = "strands/002-fitting-schedule"
        self.g09_blueprint(other)
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
        (self.a / other / "solution" / "blueprint.md").unlink()
        write(self.a / other / "versions" / "v0.1" / "blueprint-r1.md", self.G09_BLUEPRINT)
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
        # The other strand's own check is not cleared by its frozen copy either, once strand 001 holds nothing.
        (self.a / SA / "solution" / "blueprint.md").unlink()
        shutil.rmtree(str(self.a / SA / "versions"))
        self.g09_blueprint(other)
        code, data = self.lint(self.a, "blueprint", "--strand", "002")
        self.assertEqual(code, 1)
        self.assertWall(data, "name", "Tallowmere")

    G10_EXAMPLE = "Example: open Tallowmere for the depot loads.\n"

    def link(self, target, at, folder=True):
        """A symbolic link at `at` to `target` (relative when given as a string); skipped where none can be made."""
        try:
            os.symlink(str(target), str(at), target_is_directory=folder)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("this system makes no symbolic links: %s" % exc)

    def test_G10_R38_X31_terms_walks_a_linked_folder_inside_the_folder_and_stops_on_one_outside(self):
        self.add_to_b("Tallowmere is the stock app.")
        bundle = self.tmp / "bundle"
        write(bundle / "notes.md", "Depot notes.\n")
        write(self.tmp / "elsewhere" / "example.md", self.G10_EXAMPLE)
        self.link(os.path.join("..", "elsewhere"), bundle / "examples")
        code, data = self.lint(None, "terms", str(bundle))  # the finding: exit 0 before the change
        self.assertEqual((code, (data.get("error") or {}).get("file")), (3, "examples"), data.get("error"))
        self.assertNotIn("elsewhere", json.dumps(data))  # the link is named, never its target
        os.unlink(str(bundle / "examples"))
        # The control: the same file copied in as a plain file blocks.
        shutil.copytree(str(self.tmp / "elsewhere"), str(bundle / "examples"))
        code, data = self.lint(None, "terms", str(bundle))
        self.assertEqual(code, 1)
        self.assertEqual({f["file"] for f in self.assertWall(data, "name", "Tallowmere")}, {"examples/example.md"})
        # A link to a folder inside the folder is walked, each real folder once, its files named where they are.
        self.link("examples", bundle / "also")
        self.link(".", bundle / "examples" / "again")  # a loop back to its own folder ends in a single visit
        code, data = self.lint(None, "terms", str(bundle))
        self.assertEqual(code, 1)
        self.assertEqual([f["file"] for f in self.walls(data)], ["examples/example.md"])
        # A linked file that resolves outside stops too; inside, it is read under its real name.
        self.link(os.path.join("..", "elsewhere", "example.md"), bundle / "copied.md", folder=False)
        code, data = self.lint(None, "terms", str(bundle))
        self.assertEqual((code, (data.get("error") or {}).get("file")), (3, "copied.md"), data.get("error"))
        os.unlink(str(bundle / "copied.md"))
        # Two links that point at each other never hang: the walk sees two entries it cannot read, exit 3.
        self.link("loop-b", bundle / "loop-a")
        self.link("loop-a", bundle / "loop-b")
        self.assertEqual(self.lint(None, "terms", str(bundle))[0], 3)

    def test_G10_R38_X30_a_linked_folder_in_the_record_is_harvested_inside_and_stops_outside(self):
        self.add_to_b("Tallowmere is the stock app.")
        write(self.tmp / "elsewhere" / "example.md", self.G10_EXAMPLE)
        # Outside the record, a linked file or folder is exit 3 naming the link in this record, never its target
        # (X30): read through the link, the file made the name this record's and the wall passed it.
        for name, target, folder in (("extra.md", self.tmp / "elsewhere" / "example.md", False),
                                     ("examples", self.tmp / "elsewhere", True),
                                     ("theirs", self.b / "research", True)):
            at = self.a / "research" / name
            self.link(target, at, folder)
            code, data = self.text("Open Tallowmere today.")
            self.assertEqual((code, (data.get("error") or {}).get("file")), (3, "research/" + name), data.get("error"))
            for text in ("elsewhere", B, "marlbeck"):
                self.assertNotIn(text, json.dumps(data))
            code, data = self.lint(self.a, "index")
            self.assertEqual((code, (data.get("error") or {}).get("file")), (3, "research/" + name), data.get("error"))
            os.unlink(str(at))
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)
        # Inside the record, a linked folder is harvested under its real name, so a link never changes a file's
        # kind: a draft reached through research/ is still a draft and never makes its words this record's.
        write(self.a / SA / "drafts" / "d.md", "Open Tallowmere today.\n")
        self.link(os.path.join("..", SA, "drafts"), self.a / "research" / "notes")
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)
        self.link(os.path.join("..", "calls"), self.a / "research" / "calls-too")
        write(self.b / "research" / "more" / "plan.md", "- Fernhollow runs the depots.\n")
        self.link("more", self.b / "research" / "linked-plan")
        read = [i["file"] for i in self.index(self.b)["inputs"]]
        self.assertEqual(read.count("research/more/plan.md"), 1, read)
        self.assertFalse([f for f in read if "linked-plan" in f], read)
        read = [i["file"] for i in self.index(self.a)["inputs"]]
        self.assertFalse([f for f in read if "/notes/" in f or "calls-too" in f or "drafts" in f], read)
        self.assertIn("calls/2026-09-08-discovery.md", read)
        self.assertEqual(self.text("Ask Fernhollow today.")[0], 1)


    def test_G11_R42_X27_a_one_word_name_written_as_two_or_three_words_blocks(self):
        self.add_to_b("Tallowmere is the stock app.", "Fernhollow runs the depots.")
        phonetic = set(self.entry(B)["phonetic"])
        # Z13 item 1 publishes Tallowmere's key and not Fernhollow's, which an ordinary word shares; so the
        # review's route (the run's key against phonetic) would catch the first split only, and R42 joins the run.
        self.assertIn(lint.digest("p:", lint.word_key("tallowmere")), phonetic)
        self.assertNotIn(lint.digest("p:", lint.word_key("fernhollow")), phonetic)
        for text in ("Open Tallow Mere today.", "Fern Hollow runs depots.", "Open Tal Low Mere today.",
                     "Open Tallow\nMere today.", "Ask fern hollow about the depots."):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, "name")
        code, data = self.payload({"name": "Stock notes", "markdown": "Open Tallow Mere today."}, "doc")
        self.assertEqual(code, 1)
        self.assertWall(data, "name")

    def test_G11_R42_X27_ordinary_two_word_phrases_never_fuse_into_another_records_single_word(self):
        self.add_to_b("Ontrack plans the routes.", "Followup sends the notes.", "Checkin logs the drivers.",
                      "Handover books the shifts.", "Lookout watches the gate.", "Layout draws the boards.",
                      "Tallowmere is the stock app.")
        names = set(self.entry(B)["names"])
        for word in ("ontrack", "followup", "checkin", "handover", "lookout", "layout"):
            self.assertIn(lint.digest("n:", word), names, word)
            self.assertEqual(self.text("Open %s today." % word.title())[0], 1, word)
        # Clean: every word of these runs is an ordinary word, so Z13 item 2 neither keys nor joins them, even where
        # Z13 item 1 published the single word's key (Ontrack, Followup, Checkin, Handover: seven letters or more,
        # a key no ordinary word shares). `lay` is not an ordinary word, but `lay out` holds six letters, under the
        # floor. A run split by a comma or a sentence end is not one spelling of a word.
        for text in ("We are on track today.", "Follow up with the yard.", "Check in with the yard.",
                     "Hand over the keys.", "Look out for the late loads.", "Lay out the board.",
                     "We are on\ntrack today.", "Open the tallow, mere details follow.", "Use tallow. Mere is fine."):
            self.assertEqual(self.text(text)[0], 0, text)
        # Clean: a run this record writes itself is its own (X27), so its joined spelling is not tested.
        write(self.a / "research" / "2026-10-21-notes.md", "- The Tallow Mere estate sells timber.\n")
        self.assertEqual(self.text("Ask the Tallow Mere estate today.")[0], 0)
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)


    def test_G12_R43_X28_plural_and_apostrophe_shapes_of_another_records_name_block(self):
        self.add_to_b("Fernhollow Supply runs the depots.", "Blue Harbour packs the crates.",
                      "O'Rourke Lifts fits the tail lifts.", "Kestle Fresh Food buys the loads.",
                      "Tallowmere is the stock app.")
        for text in ("We use Blue Harbours for runs.", "The Fernhollows run depots.", "The Fernhollows' depots.",
                     "The Fernhollows’ depots.", "Ask O‘Rourke.", "Ask OʼRourke.", "Ask O´Rourke.",
                     "Ask O`Rourke.", "Ask O Rourke.", "Ask O＇Rourke.", "Ask O’ Rourke.",
                     "Open the Tallowmeres today.", "Ask Fernhollow‘s depots.", "Ask Fern Hollows today.",
                     "Ask the Blue Harbour's crates.", "Ask the Blue Harbours' crates."):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, "name")
        # Kestle Fresh Food: the plural shape blocks on the whole name, not only on its first word.
        code, data = self.text("We buy from Kestle Fresh Foods.")
        self.assertEqual(code, 1)
        self.assertWall(data, "name", "Kestle Fresh Foods")
        code, data = self.payload({"name": "Lift notes", "markdown": "Call O‘Rourke about the Blue Harbours."},
                                  "doc")
        self.assertEqual(code, 1)
        self.assertEqual(len(self.walls(data, "name")), 2, data["findings"])

    def test_G12_R43_ordinary_plurals_and_markdown_code_stay_clean(self):
        self.add_to_b("Fernhollow Supply runs the depots.", "Blue Harbour packs the crates.",
                      "O'Rourke Lifts fits the tail lifts.", "Tallowmere is the stock app.")
        # Clean: ordinary plurals, whose stems are ordinary words no entry publishes, never block.
        for text in ("The runs, depots, loads, boxes, buses, notes, cases and lines are ready.",
                     "The drivers' sheets and the yards' gates are fine.", "Ask about the shifts' hours.",
                     "A Rourke is not a name here.", "I Owe the yard a call.", "Use `rourke` as a code word.",
                     "Run `make` then `check`.", "Run `tallow` `mere` as two commands.",
                     "He said ‘yes’ to the loads.", "It is the user´s board."):
            self.assertEqual(self.text(text)[0], 0, text)
        # Markdown code around a whole word is still a separator (X24), and a mark inside a word still fuses (R31).
        self.assertEqual(lint.words_of("`blue` `harbour`"), ["blue", "harbour"])
        self.assertEqual(lint.words_of("O‘Rourke OʼRourke O´Rourke O`Rourke O＇Rourke"),
                         ["orourke"] * 5)
        self.assertEqual(lint.words_of("‘quoted’ `code` it´s"), ["quoted", "code", "it"])
        self.assertEqual(self.text("Open Tallow`mere` today.")[0], 1)
        # Clean: this record's own plural is its own (X27), so its stem is not looked up.
        write(self.a / "research" / "2026-10-21-notes.md", "- The Blue Harbours estate sells timber.\n")
        self.assertEqual(self.text("Ask the Blue Harbours estate today.")[0], 0)
        self.assertEqual(self.text("Ask Blue Harbour today.")[0], 1)


    def later(self, path, seconds=60):
        """G13: give a file a modification time a minute from now, as an edit made well after the last index. The
        tests' clock is patched to an earlier day, so an entry's stamp follows the newest file it was built from."""
        moment = time.time() + seconds
        os.utime(str(path), (moment, moment))
        return path

    def test_G13_R44_X30_P5_an_entry_older_than_its_record_is_exit_3_until_that_record_is_indexed(self):
        self.both()
        for text in ("Ask about the Quarrow Point depot.", "Ysolde Marrick will call."):
            self.assertEqual(self.text(text)[0], 0, text)  # neither is in record b yet
        exclusions = self.b / SB / "solution" / "exclusions.md"
        write(exclusions, exclusions.read_text(encoding="utf-8") + "- Quarrow Point depot [kind: name; added: "
              "2026-10-21; by: the user; source: the solution design]\n")
        call = write(self.b / "calls" / "2026-10-21-yard-call.md", "# Yard call, 2026-10-21\n\n## What was said\n"
                     "- Ysolde Marrick will call the night desk about the depot.\n")
        self.later(exclusions)
        self.later(call)
        runs = [lambda: self.text("Ask about the Quarrow Point depot."), lambda: self.text("Ysolde Marrick will call."),
                lambda: self.payload({"name": "Ysolde Marrick loads"}),
                lambda: self.draft("Ask about the Quarrow Point depot.\n")]
        for run in runs:
            code, data = run()
            self.assertNamesNoOtherFolder(data, code, "<home>/clients-index.json")
            self.assertEqual(data["error"]["field"], "entries")
            self.assertEqual(data["error"]["problem"], "1 other client record under the home has changed since its "
                             "last index, so the wall may not see what was added to it")
            self.assertEqual(data["error"]["expected"], "run leak_lint.py index from each client record changed "
                             "since its last index, then run this again")
            for text in ("quarrow", "ysolde", "marrick", "yard-call"):
                self.assertNotIn(text, json.dumps(data).lower())
        terms = self.tmp / "terms"
        write(terms / "notes.md", "Plain notes.\n")
        self.assertEqual(self.lint(None, "terms", str(terms))[0], 3)
        self.index(self.b)
        for text, cls in (("Ask about the Quarrow Point depot.", "term"), ("Ysolde Marrick will call.", "name")):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, cls)
        self.assertEqual(self.lint(None, "terms", str(terms))[0], 0)

    def test_G13_R44_an_untouched_record_a_skipped_file_and_this_records_own_entry_never_trip_it(self):
        self.add_to_b("Tallowmere is the stock app.")
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)  # an untouched indexed record: as before
        self.assertEqual(self.text("Open the depot today.")[0], 0)
        # Clean: files the entry is never built from (X11: .work/, drafts/, deliverables/, every .json, the
        # allowlist and the live map) change without making the entry older than its record.
        for rel in (".work/intake/2026-10-21-yard-call.report.md", SB + "/drafts/notes.md",
                    SB + "/deliverables/handoff/notes.md", SB + "/solution/allowlist.md", "live/live-map.md",
                    "account.json", "calls/2026-10-21-yard-call.json"):
            self.later(write(self.b.joinpath(*rel.split("/")), "Quarrow Point depot\n"))
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)
        self.assertEqual(self.text("Open the depot today.")[0], 0)
        self.assertFalse(self.index(self.b)["written"])  # X46: nothing the entry reads changed, so nothing is written
        # Clean: this record's own entry is never checked for its age; another record's check of it is.
        self.later(write(self.a / "research" / "2026-10-21-notes.md", "- The glazier is Ostrella Hinges.\n"))
        self.assertEqual(self.text("Open the depot today.")[0], 0)
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)
        self.assertEqual(self.text("Open the depot today.", self.b)[0], 3)
        self.index(self.a)
        self.assertEqual(self.text("Open the depot today.", self.b)[0], 0)
        # An edit to a file the entry reads that changes none of its lists still makes it older; index then writes
        # the new stamp, and a rerun writes nothing (X46).
        self.later(write(self.b / "log.md", "the night desk moved to the north yard.\n"), 120)
        self.assertEqual(self.text("Open the depot today.")[0], 3)
        lists = {k: v for k, v in self.entry(B).items() if k != "updated"}
        self.assertTrue(self.index(self.b)["written"])
        self.assertEqual({k: v for k, v in self.entry(B).items() if k != "updated"}, lists)
        self.assertFalse(self.index(self.b)["written"])
        self.assertEqual(self.text("Open the depot today.")[0], 0)

    def test_G13_R44_a_change_within_the_stamps_second_and_the_slack_is_not_older(self):
        entry = {"updated": "2026-10-17T09:30:00Z"}
        stamped = CLOCK.timestamp()
        for offset in (-3600, 0, 0.999, 2.999):
            self.assertFalse(lint.entry_is_older(entry, stamped + offset), offset)
        for offset in (3, 3.001, 60):
            self.assertTrue(lint.entry_is_older(entry, stamped + offset), offset)

    def set_entry(self, slug, **lists):
        """G14: record b's entry changed by hand, as an emptied or partly restored index would hold it."""
        entries = json.loads((self.home / "clients-index.json").read_text(encoding="utf-8"))["entries"]
        entries[lint.digest("s:", slug)].update(lists)
        write(self.home / "clients-index.json", lint.index_text(entries))
        return (self.home / "clients-index.json").read_text(encoding="utf-8")

    def assertDamaged(self, code, data):
        self.assertNamesNoOtherFolder(data, code, "<home>/clients-index.json")
        self.assertEqual(data["error"]["field"], "entries")
        self.assertEqual(data["error"]["problem"], "1 entry of the index is damaged: leak_lint.py index always "
                         "writes a client's folder name among its names, and it holds no names, or not that one, so "
                         "the index was emptied or only partly restored")
        self.assertEqual(data["error"]["expected"], "run leak_lint.py index from each client record under the home; "
                         "if the index was restored from a backup, restore the whole file from that backup, not part "
                         "of it; then run this again")

    def test_G14_R45_Z18_X26_an_emptied_or_half_restored_entry_is_exit_3_until_its_record_is_indexed(self):
        self.add_to_b("Tallowmere is the stock app.")
        good = self.entry(B)
        terms = self.tmp / "terms"
        write(terms / "notes.md", "Plain notes.\n")
        # The review's input: all four lists emptied. Every reader of the wall stops, naming nothing of record b.
        self.set_entry(B, names=[], phonetic=[], terms=[], figures=[])
        for run in (lambda: self.text("Open Tallowmere today."), lambda: self.payload({"name": "Tallowmere loads"}),
                    lambda: self.draft("Open Tallowmere today.\n"), lambda: self.lint(None, "terms", str(terms))):
            self.assertDamaged(*run())
        # index from record b replaces the emptied entry, since replacing it drops nothing it held.
        self.assertTrue(self.index(self.b)["written"])
        self.assertEqual({k: v for k, v in self.entry(B).items() if k != "updated"},
                         {k: v for k, v in good.items() if k != "updated"})
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)
        # Half restored: names that lack the folder's own name, with or without the other lists.
        for lists in (dict(names=[lint.digest("n:", "tallowmere")]),
                      dict(names=[lint.digest("n:", "tallowmere")], phonetic=[], terms=[], figures=[]),
                      dict(names=[])):
            self.set_entry(B, **lists)
            self.assertDamaged(*self.text("Open Tallowmere today."))
            self.assertTrue(self.index(self.b)["written"], lists)
            self.assertEqual(self.text("Open Tallowmere today.")[0], 1, lists)
        # A damaged entry that holds a digest record b would not write is never replaced: restore the whole file.
        text = self.set_entry(B, names=[], terms=[lint.digest("n:", "quarrow pine")])
        code, data = self.lint(self.b, "index")
        self.assertEqual((code, data["error"]["file"], data["error"]["field"]), (3, "<home>/clients-index.json",
                                                                                   "entries"))
        self.assertIn("restore the whole clients-index.json from its backup", data["error"]["expected"])
        self.assertEqual((self.home / "clients-index.json").read_text(encoding="utf-8"), text)

    def test_G14_R45_a_normal_entry_one_with_names_only_and_an_archived_one_with_no_folder_pass(self):
        self.add_to_b("Tallowmere is the stock app.")
        for text, code in (("Open Tallowmere today.", 1), ("Open the depot today.", 0)):
            self.assertEqual(self.text(text)[0], code, text)  # a normal entry, as before
        self.set_entry(B, terms=[], figures=[])  # names kept, no terms and no figures: an entry index can write
        for text, code in (("Open Tallowmere today.", 1), ("Open the depot today.", 0)):
            self.assertEqual(self.text(text)[0], code, text)
        self.index(self.b)
        (self.home / "archive").mkdir()
        shutil.move(str(self.b), str(self.home / "archive" / B))
        for text, code in (("Open Tallowmere today.", 1), ("Open the depot today.", 0)):
            self.assertEqual(self.text(text)[0], code, text)  # archived, its folder there
        shutil.rmtree(str(self.home / "archive" / B))
        for text, code in (("Open Tallowmere today.", 1), ("Open the depot today.", 0)):
            self.assertEqual(self.text(text)[0], code, text)  # archived, its folder gone (X29): the entry stays

    def test_G14_R45_X26_index_always_writes_the_folders_name_even_with_no_client_name(self):
        hand = self.b / "CLIENT.md"
        write(hand, hand.read_text(encoding="utf-8").replace('name: "Marlbeck Freight"', 'name: ""'))
        self.add_to_b("Tallowmere is the stock app.")
        names = self.entry(B)["names"]
        self.assertIn(lint.name_key(B), names)
        self.assertEqual(lint.name_key(B), lint.digest("n:", "marlbeck freight"))
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)

    G15_PROBLEM = ("this record is not under <home>/clients/ or <home>/archive/ of the home in use, so the wall cannot "
                   "see the client records beside it")
    G15_EXPECTED = ("a record at <home>/clients/<slug>/ or <home>/archive/<slug>/: point MMB_HOME at the home that "
                    "holds this record, or move the record into that home's clients/, then run this again")

    def g15_other_home(self):
        """G15: a second home with the fixture's settings and local list and no client record, as a hook with
        another environment or a moved home would name."""
        other = self.tmp / "other home"
        for key in ("settings", "local_terms"):
            target = other / MANIFEST["home"][key]["to"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(FIX / MANIFEST["home"][key]["from"]), str(target))
        return other

    def assertOutsideHome(self, code, data):
        self.assertEqual((code, (data.get("error") or {}).get("file")), (3, "CLIENT.md"), data.get("error"))
        self.assertEqual((data["error"]["field"], data["error"]["problem"], data["error"]["expected"]),
                         ("record", self.G15_PROBLEM, self.G15_EXPECTED))
        for text in (B, "marlbeck", "Tallowmere"):
            self.assertNotIn(text.lower(), json.dumps(data).lower())

    def test_G15_R46_X30_a_record_checked_against_a_home_that_does_not_hold_it_is_exit_3(self):
        self.add_to_b("Tallowmere is the stock app.")
        self.assertEqual(self.text("Open Tallowmere today.")[0], 1)  # in its own home, record b is walled
        # The review's input: record a checked with MMB_HOME naming another home that holds no records.
        other = self.g15_other_home()
        with mock.patch.dict(os.environ, {"MMB_HOME": str(other)}):
            for run in (lambda: self.text("Open Tallowmere today."), lambda: self.payload({"name": "Tallowmere loads"}),
                        lambda: self.draft("Open Tallowmere today.\n"), lambda: self.lint(self.a, "index")):
                self.assertOutsideHome(*run())
        self.assertFalse((other / "clients-index.json").exists())  # index wrote nothing into the other home
        # A record moved out of its home, checked against that home: exit 3 as well, the index unchanged.
        index = (self.home / "clients-index.json").read_text(encoding="utf-8")
        moved = self.tmp / "moved" / A
        shutil.move(str(self.a), str(moved))
        for argv in (["wall", "--text", "Open Tallowmere today."], ["index"]):
            self.assertOutsideHome(*self.lint(moved, *argv))
        self.assertEqual((self.home / "clients-index.json").read_text(encoding="utf-8"), index)

    def test_G15_R46_records_under_clients_or_archive_and_a_home_reached_through_a_link_pass(self):
        self.add_to_b("Tallowmere is the stock app.")
        cases = (("Open Tallowmere today.", 1), ("Open the depot today.", 0))
        for text, code in cases:
            self.assertEqual(self.text(text)[0], code, text)  # a record under <home>/clients/, as before
        # The home reached through a link, the record named through the link and through its real path.
        linked = self.tmp / "linked home"
        self.link(self.home, linked)
        with mock.patch.dict(os.environ, {"MMB_HOME": str(linked)}):
            for record in (self.a, linked / "clients" / A):
                for text, code in cases:
                    self.assertEqual(self.text(text, record)[0], code, (record, text))
            self.assertEqual(self.payload({"name": "Tallowmere loads"})[0], 1)
            self.assertFalse(self.index(linked / "clients" / A)["written"])
        # A record under <home>/archive/, as before.
        (self.home / "archive").mkdir()
        archived = self.home / "archive" / A
        shutil.move(str(self.a), str(archived))
        for text, code in cases:
            self.assertEqual(self.text(text, archived)[0], code, text)
        # A scan of a plain file in a folder with no record stops on CLIENT.md, as before.
        plain = self.tmp / "plain"
        write(plain / "notes.md", "Open the depot today.\n")
        code, data = self.lint(plain, "scan", "notes.md")
        self.assertEqual((code, data["error"]["file"], data["error"]["field"], data["error"]["problem"]),
                         (3, "CLIENT.md", "record", "no CLIENT.md in the folder plain"))
        # A summary-mode scan runs no wall (X37), so it needs no home that holds the record.
        write(archived / SA / "SUMMARY.md", "# Summary\n\nRoute data comes through Silver Lantern.\n")
        with mock.patch.dict(os.environ, {"MMB_HOME": str(self.g15_other_home())}):
            code, data = self.lint(archived, "scan", "%s/SUMMARY.md" % SA)
        self.assertEqual((code, self.walls(data)), (0, []))


    G16_CAPITALISED = ("Fernhollow Supply runs the depots.", "Østby Freight takes the loads.",
                       "Blue Harbour packs the crates.", "Pell-Ardent Logistics carries the night loads.",
                       "Pallets ship on Thursdays.", "Tallowmere is the stock app.")
    G16_LOWER = ("the supply runs weekly, and freight is booked by the yard.",
                 "pallets are counted at the gate, and logistics costs rose.", "the harbour gate shuts at six.")
    G16_DRAFT = ("Supply notes for the depot.\nPallets arrive on Thursdays and the freight van collects them.\n"
                 "Logistics are handled by the yard team, and the Harbour Road site stores the spare grout.\n")
    G16_WORDS = ("supply", "freight", "pallets", "logistics", "harbour", "thursdays")

    def test_G16_R47_X26_ordinary_words_published_as_one_word_names_stop_blocking(self):
        # The review's input: record b writes the six words capitalised, five of them also in lower case as any
        # record does; `thursdays` is never written in lower case and falls with the stop word `thursday`.
        self.add_to_b(*(self.G16_CAPITALISED + self.G16_LOWER))
        names = set(self.entry(B)["names"])
        for word in self.G16_WORDS:
            self.assertFalse(lint.digest("n:", word) in names, word)
        for name in ("tallowmere", "fernhollow", "ostby", "oestby", "fernhollow supply", "ostby freight",
                     "blue harbour", "pell ardent logistics"):
            self.assertIn(lint.digest("n:", name), names, name)
        # Record a's draft passes. Its own brief writes `supply` and `freight` (O), which also keeps the slug word
        # `freight` of marlbeck-freight (X21) from blocking; the other four blocked before the change.
        code, data = self.draft(self.G16_DRAFT)
        self.assertEqual((code, self.walls(data)), (0, []), data["findings"])

    def test_G16_R47_real_one_word_names_keep_blocking_and_index_shows_the_single_words(self):
        self.add_to_b(*(self.G16_CAPITALISED + self.G16_LOWER + (
            "Mail ops@tallowmere.example or open https://tallowmere.example/sync for the tallowmere-sync board.",
            "The `tallowmere` export and the fernhollow_depot sheet run nightly.",
            "Odalys Banks signs the sheets on Fridays.", "Quillon is the yard app, and the quillon login is shared.")))
        names = set(self.entry(B)["names"])
        # Clean: a word written in lower case only inside an address, a link, a joined name or code is still a name,
        # and so is a plural of a common word that is not a stop word.
        for name in ("tallowmere", "fernhollow", "ostby", "oestby", "banks", "odalys"):
            self.assertIn(lint.digest("n:", name), names, name)
        for text in ("Open Tallowmere today.", "Ask Fernhollow today.", "Ask Østby today.", "Ask Ostby today.",
                     "Ask Banks today."):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, "name")
        # Plurals of the stop words fall with them; the nod: a name the record also writes in lower case in its
        # prose is no longer published on its own (the whole runs it sits in still are).
        for word in ("fridays", "thursdays", "quillon"):
            self.assertFalse(lint.digest("n:", word) in names, word)
        # index shows this record's own single words, sorted, each published.
        shown = self.index(self.b)["single_words"]
        self.assertEqual(shown["count"], len(shown["words"]))
        self.assertEqual(shown["words"], sorted(set(shown["words"])))
        self.assertTrue({"tallowmere", "fernhollow", "banks", "marlbeck"} <= set(shown["words"]), shown)
        self.assertFalse(set(self.G16_WORDS + ("quillon", "fridays")) & set(shown["words"]), shown)
        self.assertTrue(all(lint.digest("n:", word) in names for word in shown["words"]), shown)

    G18_TEXT = "Jobs board, with a Tallowmere sync column. Fuel budget 412,870."

    def g18_blueprint(self, heading, text=G18_TEXT):
        """An otherwise full blueprint whose section 4 is written under `heading`; blueprint run on it."""
        write(self.a / SA / "solution" / "blueprint.md", "# Blueprint\n\n## 1. Purpose\nA quote board.\n" +
              sections(2, 3) + "\n%s\n%s\n" % (heading, text) + sections(5))
        return self.lint(self.a, "blueprint", "--strand", "001")

    def test_G18_R49_X09_section_4_written_with_a_bracket_or_a_colon_is_checked(self):
        self.add_to_b("Tallowmere is the stock app.")
        for heading in ("## 4. Boards", "## 4.Boards", "## 4 Boards", "## 4) Boards", "## 4: Boards"):
            code, data = self.g18_blueprint(heading)
            self.assertEqual(code, 1, heading)
            self.assertWall(data, "name", "Tallowmere")
        # Clean: a full blueprint in the pinned shapes passes as before.
        code, data = self.g18_blueprint("## 4. Boards", "Jobs board, with a sync column for depot loads.")
        self.assertEqual((code, data["findings"]), (0, []))

    def test_G18_R49_X09_a_blueprint_without_sections_1_to_15_each_once_and_in_order_is_exit_3(self):
        self.add_to_b("Tallowmere is the stock app.")
        for heading in ("## **4. Boards**", "## Section 4: Boards", "## Four. Boards"):
            code, data = self.g18_blueprint(heading)
            self.assertEqual((code, data["error"]["problem"]), (3, "cannot find sections 1 to 15"), heading)
            self.assertIn("## 4. Structure mapping", data["error"]["expected"])
        full = "# Blueprint\n\n## 1. Purpose\nA quote board.\n" + sections(2)
        broken = {"a section left out": full.replace("\n## 7. Workspace and product binding\n", ""),
                  "a section twice": full + "\n## 4. Boards again\nJobs board.\n",
                  "two sections swapped": full.replace("## 5. Fo", "## 6. Fo").replace("## 6. Li", "## 5. Li"),
                  "section 16 before section 15": "# Blueprint\n\n## 1. Purpose\nA quote board.\n" + sections(2, 14) +
                  sections(16, 16) + sections(15, 15)}
        for name, text in broken.items():
            write(self.a / SA / "solution" / "blueprint.md", text)
            code, data = self.lint(self.a, "blueprint", "--strand", "001")
            self.assertEqual((code, data["error"]["problem"]), (3, "cannot find sections 1 to 15"), name)
        write(self.a / SA / "solution" / "blueprint.md", full)
        self.assertEqual(self.lint(self.a, "blueprint", "--strand", "001")[0], 0)

    def test_G18_R49_D19_a_heading_that_is_no_section_before_section_16_is_exit_3(self):
        self.add_to_b("Tallowmere is the stock app.")
        text = "# Blueprint\n\n## 1. Purpose\nA quote board.\n" + sections(2, 4) + "\n%s\n%s\n" + sections(5)
        for heading in ("## Boards", "# Boards", "## 17. Boards"):
            write(self.a / SA / "solution" / "blueprint.md", text % (heading, self.G18_TEXT))
            code, data = self.lint(self.a, "blueprint", "--strand", "001")
            self.assertEqual(code, 3, heading)
            line = (text % (heading, self.G18_TEXT)).split("\n").index(heading) + 1
            self.assertEqual(data["error"]["field"], "line %d" % line, heading)
            self.assertIn("level-3 subsection", data["error"]["expected"], heading)
        write(self.a / SA / "solution" / "blueprint.md", "# Blueprint\n\n## Contents\n" + text % ("", ""))
        self.assertEqual(self.lint(self.a, "blueprint", "--strand", "001")[0], 3)
        # An item added as a level-3 subsection inside a section is checked with it.
        code, data = self.g18_blueprint("## 4. Structure mapping\n\n### Boards")
        self.assertEqual(code, 1)
        self.assertWall(data, "name", "Tallowmere")
        # Clean: after section 16 the text is internal, under any heading, as before.
        write(self.a / SA / "solution" / "blueprint.md", "# Blueprint\n\n## 1. Purpose\nA quote board.\n" +
              sections(2) + "\n## Build notes\n%s\n\n# Appendix\n%s\n" % (self.G18_TEXT, self.G18_TEXT))
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual((code, data["findings"]), (0, []))

    def test_G18_R49_Z19_in_a_full_blueprint_the_glossary_is_exempt_from_the_copied_run_rule_only(self):
        self.add_to_b("Tallowmere is the stock app.")
        glossary = "<!-- glossary:start -->\n- cutting list: %s\n<!-- glossary:end -->"
        code, data = self.g18_blueprint("## 4. Boards", glossary % "the cutting list names each panel by cabinet")
        self.assertEqual((code, data["findings"]), (0, []))
        code, data = self.g18_blueprint("## 4. Boards", glossary % "the cutting list names each panel by cabinet [X]")
        self.assertEqual([(f["rule"], f["class"]) for f in data["findings"] if f["severity"] == "block"],
                         [("term", "markers")])
        code, data = self.g18_blueprint("## 4. Boards", glossary % "the Tallowmere sync column")
        self.assertEqual(code, 1)
        self.assertWall(data, "name", "Tallowmere")
        # A33 (R68): outside the glossary the blueprint meets no copied-run rule either now; a marker still blocks.
        code, data = self.g18_blueprint("## 4. Boards", "The cutting list names each panel by cabinet.")
        self.assertEqual((code, data["findings"]), (0, []))
        code, data = self.g18_blueprint("## 4. Boards", "The cutting list names each panel by cabinet [X].")
        self.assertEqual([(f["rule"], f["class"]) for f in data["findings"] if f["severity"] == "block"],
                         [("term", "markers")])

    def test_G18_R50_R47_the_sixteen_section_titles_publish_no_word_and_terms_over_shared_passes(self):
        # Record a's blueprint carries the sixteen titles in the template's own words and the pinned shape.
        write(self.a / SA / "solution" / "blueprint.md", "# Blueprint\n" + sections(1) +
              "\nBuild notes go to the yard team.\n")
        self.both()
        names = set(self.entry(A)["names"])
        shown = self.index(self.a)["single_words"]["words"]
        for title in SECTION_TITLES:
            words = lint.words_of(title)
            for i in range(len(words)):
                for j in range(i + 1, min(len(words), i + 4) + 1):
                    for form in {" ".join(words[i:j]), "".join(words[i:j])}:
                        self.assertFalse(lint.digest("n:", form) in names, form)
                        self.assertNotIn(form, shown)
        # The symmetric stem rule: a word whose plural is a stop word is one too, as a plural of one is (R47).
        self.assertIn("requirements", lint.plural_forms("requirement"))
        self.assertIn("boxes", lint.plural_forms("box"))
        self.assertEqual(lint.plural_forms("class"), ["classes"])
        # terms over the real shared/ passes with that record indexed (L04, L197), and the blueprint is clean.
        code, data = self.lint(None, "terms", str(PLUGIN / "shared"))
        self.assertEqual((code, data["findings"]), (0, []))
        self.assertEqual(self.lint(self.a, "blueprint", "--strand", "001")[0], 0)

    def test_G18_R50_a_real_one_word_name_under_a_section_heading_still_publishes_and_blocks(self):
        self.add_to_b("Tallowmere is the stock app.", index=False)
        write(self.b / SB / "solution" / "blueprint.md", "# Blueprint\n" + sections(1) +
              "\nQuorrin runs the night sync.\n\n### Brindle handover\nAsk the yard first.\n")
        self.both()
        names = set(self.entry(B)["names"])
        for name in ("quorrin", "brindle", "tallowmere"):
            self.assertIn(lint.digest("n:", name), names, name)
        self.assertFalse(lint.digest("n:", "requirement") in names)
        for text in ("Ask Quorrin today.", "Open the Brindle sheet.", "Open Tallowmere today."):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, "name")
        # Clean: the plural of a title word in ordinary prose no longer meets a published singular (R43, R50).
        for text in ("Check the requirements today.", "List the requirement traces."):
            self.assertEqual(self.text(text)[0], 0, text)

    def record_py(self, record, *argv):
        """R48: record.py in process on a planted record, which first gets the log.md a real record has."""
        if not (record / "log.md").exists():
            write(record / "log.md", '---\nschema: "log/1"\nclient: "%s"\n---\n# Log\n' % record.name)
        out = io.StringIO()
        with mock.patch.object(sys, "stdout", out):
            code = load(SCRIPTS / "record.py", "record_wall").main(["--record", str(record)] + list(argv))
        return code, json.loads(out.getvalue())

    def test_R48_R44_X30_a_record_py_write_in_another_record_keeps_its_entry_current_and_its_new_names_walled(self):
        write(self.b / "log.md", '---\nschema: "log/1"\nclient: "%s"\n---\n# Log\n' % B)
        self.both()
        self.assertEqual(self.text("Ysolde Marrick will call.")[0], 0)  # not in record b yet
        # R44's premise: record b's log.md edited with no index after it stops record a's wall with exit 3
        log = self.b / "log.md"
        self.later(write(log, log.read_text(encoding="utf-8") + "\nthe night desk moved to the north yard.\n"))
        self.assertEqual(self.text("Open the depot today.")[0], 3)
        code, data = self.record_py(self.b, "log", "--strand", "-", "--type", "decision", "--key", "night-desk",
                                    "--line", "The night desk is now run by Ysolde Marrick.")
        self.assertEqual((code, "warnings" in data), (0, False), data)
        self.assertIn(lint.name_key("Ysolde Marrick"), self.entry(B)["names"])
        self.assertEqual(self.text("Open the depot today.")[0], 0)  # record a's wall runs again
        for text in ("Ysolde Marrick will call.", "Ask Ysolde today."):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)  # record b's new name blocks
            self.assertWall(data, "name")
        self.assertEqual(self.text("Ysolde Marrick will call.", self.b)[0], 0)  # its own record's name
        # a record.py write in record a keeps record a's own entry current, so record b's wall runs too
        code, data = self.record_py(self.a, "log", "--strand", "-", "--type", "decision", "--key", "glazier",
                                    "--line", "The glazier is Ostrella Hinges.")
        self.assertEqual((code, "warnings" in data), (0, False), data)
        self.assertEqual(self.text("Ask Ostrella Hinges today.", self.b)[0], 1)

    G17_PAYLOAD = {"name": "Tallowmere sync", "description": "Depot loads"}
    G17_FIGURE = {"description": "Fuel comes to 186,730 a year."}  # record b's cost figure (its brief)
    G17_LINE = "Mirror the Tallowmere sync column. Fuel was 186,730 last year."

    def g17_blocked(self, why):
        code, data = self.payload(self.G17_PAYLOAD)
        self.assertEqual(code, 1, why)
        self.assertWall(data, "name", "Tallowmere")
        code, data = self.payload(self.G17_FIGURE)
        self.assertEqual(code, 1, why)
        self.assertWall(data, "figure")

    def g17_clean(self, why):
        code, data = self.payload(self.G17_PAYLOAD)
        self.assertEqual((code, self.walls(data)), (0, []), (why, data["findings"]))
        # The record's own figure meets its own figure rules, which are not the wall's (X25); the wall is quiet.
        self.assertEqual(self.walls(self.payload(self.G17_FIGURE)[1]), [], why)

    def g17_append(self, rel, line):
        """Adds one line to a file of record a and returns a function that puts the file back as it was."""
        path = self.a.joinpath(*rel.split("/"))
        before = path.read_text(encoding="utf-8") if path.exists() else None
        write(path, (before or "") + line + "\n")
        return lambda: write(path, before) if before is not None else path.unlink()

    def test_G17_R51_X27_X11_a_line_the_session_wrote_never_makes_another_records_name_this_records(self):
        # The finding's input: record b holds Tallowmere and the fuel figure; the payload blocks alone, and still
        # blocks after one line in any file the session writes into record a for its own work.
        self.add_to_b("Tallowmere is the stock app.")
        self.g17_blocked("alone")
        for rel in (SA + "/solution/build-notes.md", "log.md", "meetings.md", SA + "/STRAND.md", SA + "/SUMMARY.md",
                    SA + "/readiness.md", SA + "/versions/v0.1/notes.md"):
            restore = self.g17_append(rel, self.G17_LINE)
            self.g17_blocked(rel)
            restore()
        # The blueprint's internal text (here section 16) is a working note too; only its client-facing lines,
        # which payloads copy, stay this record's (X11, R37).
        write(self.a / SA / "solution" / "blueprint.md", "# Blueprint\n\n## 1. Purpose\nA quote board.\n" +
              sections(2) + "\n%s\n" % self.G17_LINE)
        self.g17_blocked("blueprint section 16")
        # CLIENT.md's body is written by the session; only its name and former names are this client's own.
        restore = self.g17_append("CLIENT.md", "\n## Notes\n- " + self.G17_LINE)
        self.g17_blocked("CLIENT.md body")
        restore()

    def test_G17_R51_a_name_in_this_records_calls_inputs_or_research_and_its_own_names_still_pass(self):
        self.add_to_b("Tallowmere is the stock app.", "Wrenfold Joinery buys the oak fronts.")
        line = "The Tallowmere sync feeds the depot loads, and fuel comes to 186,730 a year."
        for rel in ("calls/2026-09-08-discovery.transcript.txt", "calls/2026-09-08-discovery.md",
                    "inputs/2026-09-15-panel-procedure.txt", "research/2026-09-01-brief.md",
                    "research/2026-10-02-depot.md"):
            restore = self.g17_append(rel, ("Speaker 2: " if rel.endswith("transcript.txt") else "") + line)
            self.g17_clean(rel)
            restore()
        # This record's own CLIENT.md name, and a former name (R40), are its own, with the brief that also writes
        # the name emptied of it (its first line), so the front matter alone holds it.
        brief = self.a / "research" / "2026-09-01-brief.md"
        text = brief.read_text(encoding="utf-8")
        write(brief, text.replace("Wrenfold Joinery builds", "The workshop builds", 1))
        self.assertNotIn("Wrenfold", brief.read_text(encoding="utf-8"))
        code, data = self.payload({"name": "Wrenfold Joinery quotes"})
        self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
        write(brief, text)
        client = self.a / "CLIENT.md"
        meta = client.read_text(encoding="utf-8")
        write(client, meta.replace('name: "Wrenfold Joinery"\n',
                                   'name: "Wrenfold Joinery"\nformer_names: "Tallowmere Joinery"\n', 1))
        code, data = self.payload(self.G17_PAYLOAD)
        self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
        write(client, meta)
        # A planned name in the blueprint's client-facing lines passes in a payload, as X11 and R37 decided.
        write(self.a / SA / "solution" / "blueprint.md", self.G09_BLUEPRINT)
        code, data = self.payload({"name": "Tallowmere sync"})
        self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
        # The session's files still feed the harvest: a name written only in record a's build notes is published.
        write(self.a / SA / "solution" / "build-notes.md", "Mirror the Quillanbrook Yard column.\n")
        self.index(self.a)
        self.assertIn(lint.name_key("Quillanbrook Yard"), self.entry(A)["names"])
        code, data = self.text("Ask Quillanbrook Yard today.", self.b)
        self.assertEqual(code, 1)
        self.assertWall(data, "name")

    def r52_blueprint(self, heading, text="Jobs board, with a sync column for depot loads."):
        """A full blueprint whose section 4 is written under `heading`; (code, data, the heading's line)."""
        body = "# Blueprint\n\n## 1. Purpose\nA quote board.\n" + sections(2, 3) + "\n%s\n%s\n" % (heading, text)
        write(self.a / SA / "solution" / "blueprint.md", body + sections(5))
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        return code, data, body.split("\n").index(heading) + 1

    def test_R50_R52_X09_Z19_a_section_headings_title_is_checked_with_its_section(self):
        self.add_to_b("Tallowmere is the stock app.")
        for heading in ("## 4. Tallowmere mapping", "## 4.Tallowmere mapping", "## 4 Tallowmere mapping",
                        "## 4) Tallowmere mapping", "## 4: Tallowmere mapping", "## 4. Tallowmere mapping ##"):
            code, data, line = self.r52_blueprint(heading)
            self.assertEqual(code, 1, heading)
            hits = self.assertWall(data, "name", "Tallowmere")
            self.assertEqual([(h["field"], h["column"]) for h in hits], [("line %d" % line, heading.index("T") + 1)],
                             heading)
        # The firm's name, and record b's fuel figure, in a heading block too. A33 (R68): a run copied from record
        # a's research brief no longer blocks in the blueprint, in a heading or in its text.
        code, data, line = self.r52_blueprint("## 4. The cutting list names each panel by cabinet")
        self.assertEqual((code, data["findings"]), (0, []))
        code, data, line = self.r52_blueprint("## 4. Thymbel cutting list")
        self.assertEqual([(f["rule"], f["class"], f["field"]) for f in data["findings"] if f["severity"] == "block"],
                         [("term", "firm", "line %d" % line)])
        code, data, line = self.r52_blueprint("## 4. Fuel budget 186,730")
        self.assertEqual(code, 1)
        self.assertEqual([h["field"] for h in self.assertWall(data, "figure")], ["line %d" % line])
        # The glossary under a heading is exempt from no rule but the runs and quotes, which A33 (R68) drops for the
        # whole blueprint; its heading is checked as section text, never as glossary text.
        glossary = "<!-- glossary:start -->\n- cutting list: the cutting list names each panel by cabinet\n" \
                   "<!-- glossary:end -->"
        code, data, line = self.r52_blueprint("## 4. Structure mapping", glossary)
        self.assertEqual((code, data["findings"]), (0, []))
        code, data, line = self.r52_blueprint("## 4. Thymbel cutting list", glossary)
        self.assertEqual([(f["rule"], f["class"], f["field"]) for f in data["findings"] if f["severity"] == "block"],
                         [("term", "firm", "line %d" % line)])

    def test_R50_R52_a_blueprint_whose_headings_are_the_template_titles_passes_as_before(self):
        # The sixteen titles sit in the checked blueprint, its frozen copy, strand 002's blueprint and record b's,
        # all indexed: none of them is another record's word or an internal run, so no title is flagged.
        full = "# Blueprint\n" + sections(1).replace("\n## 16.", "Jobs board, with a sync column.\n\n## 16.") + \
            "\nBuild notes go to the yard team.\n"
        for rel in (SA + "/solution/blueprint.md", SA + "/versions/v0.1/blueprint-r1.md",
                    "strands/002-fitting-schedule/solution/blueprint.md"):
            write(self.a.joinpath(*rel.split("/")), full)
        write(self.b / SB / "solution" / "blueprint.md", full)
        self.both()
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual((code, data["findings"]), (0, []))
        # A long title of the session's own, in the blueprint and its copies, is client text and feeds no internal
        # set, so it is never a run copied from itself.
        own = full.replace("## 4. Structure mapping", "## 4. Jobs board with one sync column for each yard")
        for rel in (SA + "/solution/blueprint.md", SA + "/versions/v0.1/blueprint-r1.md",
                    "strands/002-fitting-schedule/solution/blueprint.md"):
            write(self.a.joinpath(*rel.split("/")), own)
        self.index(self.a)
        code, data = self.lint(self.a, "blueprint", "--strand", "001")
        self.assertEqual((code, data["findings"]), (0, []))
        # The script's titles are the template's; a section's own title, in any letter case, is plugin vocabulary
        # and is not checked, while any other title is kept alone in its place on the heading's line.
        self.assertEqual(lint.SECTION_TITLES, SECTION_TITLES)
        lines = full.split("\n") + ["## 6. Live Objects This Strand Touches", "## 4. Product fit",
                                    "## 4: Tallowmere mapping ##"]
        self.assertEqual(lint.section_titles(lines), {len(lines) - 2: "      Product fit",
                                                      len(lines) - 1: "      Tallowmere mapping   "})

    G19_RUN = "Laminate offcuts pile up beside the panel saw before collection"  # ten words of record a's brief
    G19_QUOTE = "every quote goes out late because the cutting"  # eight words of the call's [Q] line

    def blocks(self, data, rule):
        return [f for f in data["findings"] if f["rule"] == rule and f["severity"] == "block"]

    def test_G19_R53_A916_X22_a_run_a_quote_or_a_name_split_over_two_payload_fields_blocks(self):
        self.add_to_b("Their packing partner is Blue Field.")
        run, quote = self.G19_RUN.split(), self.G19_QUOTE.split()
        # The controls, which blocked before: each in one field.
        for value, kind, rule in (({"name": self.G19_RUN}, "board", "copied-run"),
                                  ({"steps": [{"text": self.G19_QUOTE}]}, "workflow", "quote"),
                                  ({"columns": [{"title": "Blue Field"}]}, "board", "wall")):
            code, data = self.payload(value, kind)
            self.assertEqual(code, 1, value)
            self.assertTrue(self.blocks(data, rule), value)
        # Split over two fields, with the keys between them left out of the join (structure, not text): reported
        # once, at the first field it touches, naming the fields it spans.
        cases = (({"name": " ".join(run[:5]), "description": " ".join(run[5:])}, "board", "copied-run",
                  "$.name", ["$.name", "$.description"]),
                 ({"name": "Quote follow-up", "steps": [{"text": " ".join(quote[:4])}, {"text": " ".join(quote[4:])}]},
                  "workflow", "quote", "$.steps[0].text", ["$.steps[0].text", "$.steps[1].text"]),
                 ({"name": "Depot loads", "columns": [{"title": "Blue"}, {"title": "Field"}]},
                  "board", "wall", "$.columns[0].title", ["$.columns[0].title", "$.columns[1].title"]),
                 # the join reaches into a JSON string as the walk does, past a structural id
                 ({"item_ids": ["41873925"], "column_values": json.dumps({"text_1": " ".join(run[:5]),
                                                                          "text_2": " ".join(run[5:])})},
                  "item_batch", "copied-run", "$.column_values<json>.text_1",
                  ["$.column_values<json>.text_1", "$.column_values<json>.text_2"]))
        for value, kind, rule, field, fields in cases:
            code, data = self.payload(value, kind)
            self.assertEqual(code, 1, value)
            found = self.blocks(data, rule)
            self.assertEqual([(f["field"], f.get("fields")) for f in found], [(field, fields)], value)
        code, data = self.payload(cases[0][0], "board")
        self.assertEqual(self.blocks(data, "copied-run")[0]["match"], self.G19_RUN)  # the break shown as a space
        # A JSON file in drafts/ goes through the same walker under scan, so it is joined too.
        code, data = self.draft(json.dumps(cases[0][0]), "columns.json")
        self.assertEqual([(f["field"], f.get("fields")) for f in self.blocks(data, "copied-run")],
                         [("$.name", ["$.name", "$.description"])])
        # A key is checked alone, as X22 has it, and never joins its value.
        code, data = self.payload({" ".join(run[:5]): " ".join(run[5:])}, "generic")
        self.assertEqual((code, data["findings"]), (0, []))
        # --spans gives the part of the first field the hit covers.
        write(self.a.joinpath(*WORK.split("/")), json.dumps(cases[0][0]))
        code, data = self.lint(self.a, "payload", "--strand", "001", "--kind", "board", "--file", WORK, "--spans")
        self.assertEqual(self.blocks(data, "copied-run")[0]["span"], {"start": 0, "end": len(" ".join(run[:5]))})

    def test_G19_R53_ordinary_joins_pass_and_a_run_inside_one_field_is_reported_once(self):
        self.add_to_b("Their packing partner is Blue Field.", "Ontrack plans the routes.")
        # Clean: fields that each pass and whose join holds nothing, and fields whose join is an ordinary phrase.
        for value, kind in (({"name": "Quote follow-up", "description": "Chase every open quote",
                              "steps": [{"text": "When a quote is sent"}, {"text": "wait five days"},
                                        {"text": "then notify the office coordinator"}]}, "workflow"),
                            ({"name": "Jobs", "columns": [{"title": "On"}, {"title": "track"}, {"title": "Blue"},
                                                          {"title": "Status"}, {"title": "Field"}]}, "board"),
                            ({"name": "Panel saw", "description": "before collection"}, "board")):
            code, data = self.payload(value, kind)
            self.assertEqual((code, data["findings"]), (0, []), value)
        # A run, a quote or a name found inside one field is reported once, also where the next field goes on with it.
        for value, kind, rule, field in (
                ({"name": self.G19_RUN, "description": "Ask the office"}, "board", "copied-run", "$.name"),
                ({"name": " ".join(self.G19_RUN.split()[:8]), "description": "before collection on Fridays"}, "board",
                 "copied-run", "$.name"),
                ({"steps": [{"text": self.G19_QUOTE + " list is wrong"}, {"text": "Check the board"}]}, "workflow",
                 "quote", "$.steps[0].text"),
                ({"columns": [{"title": "Blue Field"}, {"title": "Notes"}]}, "board", "wall", "$.columns[0].title")):
            code, data = self.payload(value, kind)
            self.assertEqual(code, 1, value)
            self.assertEqual([(f["field"], f.get("fields")) for f in self.blocks(data, rule)], [(field, None)], value)

    def raw_payload(self, text, kind="generic"):
        """A payload file written as raw text, since json.dumps never writes a key twice."""
        write(self.a.joinpath(*WORK.split("/")), text)
        return self.lint(self.a, "payload", "--strand", "001", "--kind", kind, "--file", WORK)

    def test_G20_R54_X22_a_key_written_twice_in_a_payload_is_exit_3_naming_the_key(self):
        self.add_to_b("Tallowmere is the stock app.")
        inner = '{\\"text_1\\": \\"Tallowmere sync\\", \\"text_1\\": \\"Depot loads\\"}'
        cases = (('{"board_id": 41873925, "item_name": "Tallowmere sync", "item_name": "Depot loads"}', "item_batch",
                  "$.item_name<key>", "item_name"),
                 ('{"board_id": 41873925, "item_name": "Depot loads", "item_name": "Depot loads"}', "item_batch",
                  "$.item_name<key>", "item_name"),
                 ('{"name": "Quote follow-up", "steps": [{"text": "Open Tallowmere", "text": "Check the board"}]}',
                  "workflow", "$.steps[0].text<key>", "text"),
                 # inside a column_values string, at that string's path and on through the walk
                 ('{"item_ids": ["41873925"], "column_values": "%s"}' % inner, "item_batch",
                  "$.column_values<json>.text_1<key>", "text_1"),
                 ('{"column_values": "\\u200b%s"}' % inner, "item_batch", "$.column_values<json>.text_1<key>",
                  "text_1"))
        for text, kind, field, key in cases:
            code, data = self.raw_payload(text, kind)
            self.assertEqual(code, 3, text)
            error = data["error"]
            self.assertEqual((error["file"], error["field"]), (WORK, field), text)
            self.assertIn('"%s"' % key, error["problem"])
            self.assertIn("once", error["expected"])
            self.assertIn("as the tool will receive it", error["expected"])
        # A JSON file in drafts/ goes through the same reader under scan.
        rel = "%s/drafts/columns.json" % SA
        write(self.a.joinpath(*rel.split("/")), cases[0][0])
        code, data = self.lint(self.a, "scan", rel)
        self.assertEqual((code, data["error"]["field"]), (3, "$.item_name<key>"))

    def test_G20_R54_X02_a_key_written_twice_in_the_index_or_the_settings_is_exit_3(self):
        self.both()
        path = self.home / "clients-index.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        key = lint.digest("s:", B)
        entries = ", ".join("%s: %s" % (json.dumps(k), json.dumps(v)) for k, v in data["entries"].items())
        # record b's entry written a second time, as a merge by hand might leave it
        text = json.dumps(dict(data, entries="@")).replace('"@"', "{%s, %s: %s}" % (
            entries, json.dumps(key), json.dumps(data["entries"][key])))
        write(path, text)
        code, out = self.text("Orders go out on Fridays.")
        self.assertEqual((code, out["error"]["file"], out["error"]["field"]),
                         (3, lint.INDEX_NAME, "$.entries[%s]<key>" % json.dumps(key)), out.get("error"))
        settings = self.home / "local" / "settings.json"
        original = settings.read_text(encoding="utf-8").rstrip()
        write(settings, original[:-1] + ', "schema": "settings/1"}')
        code, out = self.draft("Orders.\n")
        self.assertEqual((code, out["error"]["field"]), (3, "$.schema<key>"))

    def test_G20_R54_a_key_at_two_depths_a_repeat_in_plain_text_and_the_fixture_pass(self):
        self.both()
        for value in ({"name": "Depot loads", "group": {"name": "Inbound"}},
                      {"columns": [{"title": "Status"}, {"title": "Owner"}]},
                      {"column_values": json.dumps({"text_1": "Depot loads", "board": {"text_1": "Inbound"}})},
                      # a string that repeats a key but is not JSON is plain text, checked as text
                      {"text_1": '{"item_name": "Depot loads", "item_name": "Inbound"} is the wrong shape'},
                      {"text_1": "item_name: Depot loads, item_name: Inbound"}):
            code, data = self.payload(value, "item_batch")
            self.assertEqual((code, data["findings"]), (0, []), value)
        # The trap fixture's JSON, and every JSON string inside it, writes each key once in each object, so the
        # strict reader leaves every one of its payloads as it was; test_leak_grading keeps the 250 outcomes.
        def once(pairs):
            self.assertEqual(len(dict(pairs)), len(pairs), (path.name, pairs))
            return dict(pairs)

        for path in sorted(FIX.rglob("*.json")):
            stack = [json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=once)]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    stack.extend(item.values())
                elif isinstance(item, list):
                    stack.extend(item)
                elif isinstance(item, str) and item.strip()[:1] in ("{", "[", '"'):
                    try:
                        json.loads(item.strip())
                    except ValueError:
                        continue
                    stack.append(json.loads(item.strip(), object_pairs_hook=once))

    def table_in(self, path, *rows):
        """Appends a Markdown table, written as the rows give it, after a blank line."""
        write(path, path.read_text(encoding="utf-8") + "\n" + "".join("%s\n" % row for row in rows))

    def figures_of(self, slug, *values):
        """Which of the exact values `values` the entry of `slug` publishes as a wall figure."""
        held = set(self.entry(slug)["figures"])
        return [v for v in values if lint.digest("f:", "%de0" % v) in held]

    def test_G21_R56_U1_X25_a_cost_figure_in_a_table_without_a_cost_word_in_its_row_blocks_on_the_wall(self):
        # The finding's input, then a cost word only in the header, only in a first cell cut off by a full stop,
        # a table written without its outer pipes, one with no rule row, and the new cue words in a sentence.
        self.table_in(self.brief, "| Line | Amount |", "|---|---|", "| Fuel | 731,946 |")
        self.table_in(self.brief, "| Lane | Cost |", "|:---|---:|", "| Harbour run | 357,904 |")
        self.table_in(self.brief, "| Item | Q3 |", "|---|---|", "| Fuel, est. | 412,693 |")
        self.table_in(self.brief, "Route | Spend", "--- | ---", "Eastline | 645,281")
        self.table_in(self.brief, "| Depot | Total |", "| Northgate | 528,317 |")
        self.add_to_b("The amount for the cold store came to 263,914.", "Fuel came to 618,275 last year.")
        values = (731946, 357904, 412693, 645281, 528317, 263914, 618275)
        self.assertEqual(self.figures_of(B, *values), list(values))
        for value in values:
            code, data = self.text("The line comes to {:,}.".format(value))
            self.assertEqual(code, 1, value)
            self.assertWall(data, "figure")
        self.assertEqual(self.text("The line comes to 731,946.", self.b)[0], 0)  # its own record's figure

    def test_G21_R56_X25_a_cost_figure_in_a_table_of_this_records_own_files_meets_the_figure_rule(self):
        # Part 1: record a's own table makes 58,214 and 145 cost figures, so a draft that writes them is judged
        # by the figure rule, and a draft's own table lends its row the header's cost word as well.
        self.table_in(self.a / "research" / "2026-09-01-brief.md", "| Line | Amount |", "|---|---|",
                      "| Varnish | 58,214 |", "| Varnish tin | 145 |")
        self.both()
        # A34 (R70): the record's own cost figure meets the figure rule as before, and warns in its own build
        code, data = self.draft("We set aside 58,214 for the varnish.\n")
        self.assertEqual(code, 2)
        self.assertEqual([(f["rule"], f["severity"]) for f in data["findings"]], [("figure", "warn")])
        code, data = self.draft("| Item | Amount |\n|---|---|\n| Varnish tin | 145 |\n")
        self.assertEqual(code, 2)
        self.assertEqual([(f["rule"], f["severity"]) for f in data["findings"]], [("figure", "warn")])
        code, data = self.draft("| Item | Count |\n|---|---|\n| Varnish tin | 145 |\n")  # no cost word: it warns
        self.assertEqual(code, 2)
        self.assertEqual({f["rule"] for f in data["findings"]}, {"record-number"})

    def test_G21_R56_counts_dates_and_ids_in_a_table_publish_no_figure_and_a_cued_sentence_works_as_before(self):
        self.table_in(self.brief, "| Week | Pallets |", "|---|---|", "| Week 34 | 2,617 |", "| Week 35 | 2,843 |")
        self.table_in(self.brief, "| Shipped | Order | Amount |", "|---|---|---|",
                      "| 2026-08-14 | 52817403 | 8,315 |", "| 14 August 2026 | 61940275 | 9,472 |")
        self.add_to_b("The yard holds 4,318 pallets on a busy night.")
        self.assertEqual(self.figures_of(B, 2617, 2843, 52817403, 61940275, 20260814, 2026, 4318), [])
        self.assertEqual(self.figures_of(B, 8315, 9472, 186730), [8315, 9472, 186730])
        for text in ("We moved 2,617 pallets in week 34.", "The yard holds 4,318 pallets."):
            code, data = self.text(text)
            self.assertEqual((code, self.walls(data)), (0, []), text)
        code, data = self.text("Fuel comes to 186,730 a year.")  # record b's cost word in its own sentence
        self.assertEqual(code, 1)
        self.assertWall(data, "figure")

    def assertFigureBlocks(self, *texts):
        for text in texts:
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, "figure")

    def assertNoWall(self, *texts):
        for text in texts:
            code, data = self.text(text)
            self.assertEqual((code, self.walls(data)), (0, []), text)

    def test_G22_R57_X25_Z17_an_exclusion_figure_blocks_its_renderings_and_no_longer_a_one_digit_round_number(self):
        self.exclude_in_b(("58,315", "figure"))
        held = set(self.entry(B)["figures"])
        for form in ("58315e0", "5831e1", "5832e1", "583e2", "58e3"):
            self.assertIn(lint.digest("f:", form), held, form)
        for form in ("5e4", "6e4", "1e5"):  # one significant digit of a five-digit figure: not on the wall
            self.assertNotIn(lint.digest("f:", form), held, form)
        self.assertFigureBlocks("Keep it under 58,315.", "Keep it under $58,315.", "We set 58k aside.",
                                "It came to 58.3k.", "It came to fifty-eight thousand.")
        self.assertNoWall("We expect fifty thousand visits.", "We need a hundred thousand rows.",
                          "About sixty thousand people came.", "We expect 60k visits.")
        self.assertEqual(self.text("We expect fifty thousand visits.", self.b)[0], 0)

    def test_G22_R57_a_figure_written_with_one_significant_digit_keeps_its_own_round_forms(self):
        self.exclude_in_b(("60,000", "figure"), ("4,250", "figure"))
        held = set(self.entry(B)["figures"])
        for form in ("60000e0", "600e2", "60e3", "6e4", "4250e0", "425e1", "42e2", "43e2"):
            self.assertIn(lint.digest("f:", form), held, form)
        for form in ("1e5", "4e3"):  # past the figure's own leading digit, or one digit of a figure of three
            self.assertNotIn(lint.digest("f:", form), held, form)
        self.assertFigureBlocks("We hold sixty thousand back.", "We hold 60k back.", "We hold 4.25k back.")
        self.assertNoWall("We need a hundred thousand rows.", "We counted four thousand boxes.")

    def test_G23_R58_X25_A30_a_figure_with_cents_either_end_of_a_range_or_an_exponent_blocks_on_the_wall(self):
        self.add_to_b("The fuel cost came to 412,870 last year.")
        self.assertFigureBlocks("The fuel came to 412,870.50.", "The fuel came to 412,870.99.",
                                "The fuel came to $412,870.50.", "The range is 400k-413k.", "The range is 413k-430k.",
                                "The range is 400k–413k.", "It came to 4.1287e5.", "It came to 4.1287E+05.",
                                "It came to 4.13e5.")
        self.assertEqual(self.text("It came to 4.1287e5.", self.b)[0], 0)  # its own record's figure

    def test_G23_R58_Z17_two_digit_renderings_other_amounts_and_words_with_an_e_stay_clean(self):
        self.add_to_b("The fuel cost came to 412,870 last year.")
        self.assertNoWall("It came to 0.41M.", "It came to 412,860.50.", "It came to 4.1e5.",
                          "The board holds 1e3 rows.", "Use the colour #4e5b6c.", "Step 4e is next.",
                          "The 4.1287 build ships in May.")

    def test_G25_R60_X26_initials_written_with_spaces_or_full_stops_block_as_fused_ones_do(self):
        # Record b writes its customer as TFM (X26 step 3); here it also writes Fernhollow Supply as FS.
        self.add_to_b("Fernhollow Supply, FS for short, runs the depots.")
        self.assertIn(lint.digest("n:", "fs"), set(self.entry(B)["names"]))
        for text in ("Send the T F M report weekly.", "Send the report to T F M.", "Send the T  F  M report.",
                     "Send the T\tF\tM report.", "Send the T. F. M. report.", "Send the T.F.M. report weekly.",
                     "Send the T. F. M report.", "Send the T.F.M report.", "Send the T.  F.  M. report.",
                     "Send the TFM report weekly.", "Ask F S about the depots.", "Ask F. S. about the depots.",
                     "Ask A T F M rep today."):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, "name")
        code, data = self.payload({"name": "Report notes", "markdown": "Send the T. F. M. report weekly."}, "doc")
        self.assertEqual(code, 1)
        self.assertWall(data, "name")

    def test_G25_R60_X26_five_and_six_letter_initials_block_spaced_or_dotted(self):
        self.add_to_b("Kestle Harbour Lift Freight Tours, KHLFT for short, moves the crates.",
                      "Brindle Harbour Rail Depot Loads and Tiles, BHRDLT for short, stores the tiles.")
        names = set(self.entry(B)["names"])
        for initials in ("khlft", "bhrdlt"):
            self.assertIn(lint.digest("n:", initials), names, initials)
        for text in ("Book the K H L F T run.", "Book the K.H.L.F.T. run.", "Book the K. H. L. F. T. run.",
                     "Book the K  H  L  F  T run.", "Book the B H R D L T run.", "Book the B.H.R.D.L.T. run.",
                     "Book the B. H. R. D. L. T run.", "Ask X B H R D L T Y about it."):
            code, data = self.text(text)
            self.assertEqual(code, 1, text)
            self.assertWall(data, "name")

    def test_G25_R60_capital_runs_that_match_no_initials_and_lone_letters_stay_clean(self):
        self.add_to_b("Fernhollow Supply, FS for short, runs the depots.")
        # Clean: runs of capitals that no entry publishes, a lone I or a, lower-case letters, and letters split by a
        # comma, a word or a line break are never fused into another record's initials.
        self.assertNoWall("I A M here today.", "Plan B is fine.", "Grade A B C loads are ready.",
                          "Use A. B. C. D. E. as the steps.", "I said a word to the yard.", "Is it a t f m report?",
                          "Send T, F and M the report.", "Mark it T. F is next.", "Ask f s about it.",
                          "Ask f. s. about it.", "Ask F\nS about it.", "Ask F or S about it.")
        # Clean: spaced initials this record writes itself are its own (X27), while the fused spelling still blocks.
        write(self.a / "research" / "2026-10-21-notes.md", "- The T F M crew loads the vans.\n")
        self.assertNoWall("Ask the T F M crew today.")
        self.assertEqual(self.text("Ask the TFM crew today.")[0], 1)

    def method_hits(self, data):
        return [f for f in data["findings"] if f["rule"] == "term" and f["class"] == "method"]

    def assertMethod(self, text, blocks):
        code, data = self.draft(text + "\n")
        self.assertEqual((code, bool(self.method_hits(data))), (1, True) if blocks else (0, False),
                         (text, data["findings"]))
        return data

    def test_R13_R61_X39_an_everyday_method_phrase_passes_spaced_and_blocks_hyphenated(self):
        self.both()
        # The user's answer to R13, option (b): an agent prompt's "Never say a price" passes, its hyphenated row blocks.
        code, data = self.payload({"name": "Pricing helper", "description": "Never say a price."}, "generic")
        self.assertEqual((code, self.method_hits(data)), (0, []), data["findings"])
        code, data = self.payload({"name": "Pricing helper", "description": "Never-say a price."}, "generic")
        self.assertEqual(code, 1)
        self.assertTrue(self.method_hits(data), data["findings"])
        for text in ("Never say a price to the depot.", "The spare part is not obtainable this month.",
                     "The part is not, obtainable here."):
            self.assertMethod(text, False)
        for text in ("Keep the never-say rows apart.", "Mark it not-obtainable.", "Mark it not - obtainable.",
                     "Mark it not_obtainable.", "Mark it not‑obtainable.", "Keep the NEVER—SAY rows apart."):
            self.assertMethod(text, True)
        for row in ("exit-ramp", "cost-of-waiting"):  # R13's spaced build is narrowed for these rows too
            regex = lint.literal_regex(row, spaced=False)
            self.assertIsNone(regex.search(lint.fold_text(row.replace("-", " "))), row)
            self.assertTrue(regex.search(lint.fold_text(row)), row)
            self.assertMethod("Take the %s now." % row, True)
        # The user approved removing the spaced rows `exit ramp` and `cost of waiting` from the shipped list
        # (2026-10-21), so their spaced forms now pass, as the answer to R13 says.
        for text in ("Take the exit ramp now.", "Show the cost of waiting."):
            self.assertMethod(text, False)

    def test_R13_R61_method_rows_of_the_methods_own_jargon_block_spaced_and_hyphenated(self):
        self.both()
        for text in ("Check the run sheet for Friday.", "Check the run-sheet for Friday.",
                     "Keep the if asked list short.", "Keep the if-asked list short.", "Keep the if, asked list short.",
                     "File it in the deferred answer register.", "File it in the deferred-answer register.",
                     "Copy the client safe block.", "Copy the client-safe block."):
            self.assertMethod(text, True)
        # The other classes keep R13's spaced matching: an internal-note mark written without its hyphen.
        code, data = self.draft("Build file: never client facing.\n")
        self.assertEqual(code, 1)
        self.assertTrue([f for f in data["findings"] if f["rule"] == "internal-note"], data["findings"])

    def test_R13_R61_the_everyday_method_rows_are_hyphenated_method_rows_of_the_shipped_list(self):
        rows = lint.parse_list((PLUGIN / "shared" / "leak-terms.txt").read_text(encoding="utf-8"), "s", local=False)
        method = {r.term.strip().lower() for r in rows if r.kind == "literal" and r.cls == "method"}
        self.assertTrue(lint.EVERYDAY_METHOD_ROWS)
        for term in lint.EVERYDAY_METHOD_ROWS:
            self.assertIn(term, method, term)
            self.assertRegex(term, r"[^\W_]-[^\W_]", term)
        self.assertEqual(sorted(lint.EVERYDAY_METHOD_ROWS),
                         ["cost-of-waiting", "exit-ramp", "never-say", "not-obtainable"])

    def allow(self, *rows):
        allow = self.a / SA / "solution" / "allowlist.md"
        write(allow, "# Allowlist\n\n## Allowlist\n" + "".join("- %s\n" % row for row in rows))
        return "%s/solution/allowlist.md" % SA

    def notes(self, data, severity=None):
        return [f for f in data["findings"] if f["rule"] == "internal-note" and severity in (None, f["severity"])]

    def test_R17_R62_X39_an_internal_use_phrase_is_cleared_by_its_own_row_with_one_caution(self):
        self.assertEqual(sorted(lint.CLEARABLE_NOTES), ["internal only", "internal use only", "not for clients"])
        self.assertLessEqual(lint.CLEARABLE_NOTES, {lint.normal_form(p) for p in lint.INTERNAL_NOTE_PHRASES})
        self.both()
        cases = (("Internal use only, not visible to the customer.", "internal use only"),
                 ("Internal only: the depot rota.", "internal only"),
                 ("Not for clients: the stock sheet.", "not for clients"),
                 ("Keep it INTERNAL-USE-ONLY.", "internal use only"))
        for text, row in cases:
            with self.subTest(text=text):
                self.allow("callback [ok: yes; class: method]")
                code, data = self.payload({"name": "Service desk", "description": text}, "generic")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.notes(data, "block"), data["findings"])
                name = self.allow("callback [ok: yes; class: method]",
                                  "%s [ok: yes, the client's own label for a Service board; date: 2026-10-21]" % row)
                code, data = self.payload({"name": "Service desk", "description": text}, "generic")
                self.assertEqual((code, data["counts"]), (2, {"block": 0, "warn": 0, "caution": 1}), data["findings"])
                caution = self.notes(data, "caution")[0]
                self.assertEqual((caution["class"], caution["cleared_by"]), (None, "%s line 5" % name))
                self.assertIn("kept as the client's own word", caution["problem"])

    def test_R17_R62_X40_speaker_labels_front_matter_and_the_other_marks_stay_never_cleared(self):
        self.both()
        self.allow("SPEAKER_00 [ok: yes]", "Speaker A [ok: yes]", "schema: call-summary/1 [ok: yes]",
                   "title: \"Discovery\" [ok: yes]", "never client-facing [ok: yes]", "not client-facing [ok: yes]",
                   "not for the client [ok: yes]", "note to self [ok: yes]")
        for text in ("SPEAKER_00: we lose the tickets.", "Speaker A: we lose the tickets.",
                     "---\ntitle: Discovery\nschema: call-summary/1\n---\nBody", "title: \"Discovery\"",
                     "Build file: never client-facing.", "Draft notes, not client-facing.",
                     "This sheet is not for the client.", "Note to self: ring the depot."):
            with self.subTest(text=text):
                code, data = self.payload({"name": "Service desk", "description": text}, "generic")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.notes(data, "block"), data["findings"])
                self.assertFalse(self.notes(data, "caution"), data["findings"])

    def test_R17_R62_X09_a_row_with_an_empty_ok_clears_no_internal_use_phrase(self):
        self.both()
        for row in ("internal use only [date: 2026-10-21]", "internal use only [ok: ; date: 2026-10-21]",
                    "internal use only [ok: pending]"):
            with self.subTest(row=row):
                self.allow(row)
                code, data = self.payload({"name": "Service desk",
                                           "description": "Internal use only, not visible to the customer."}, "generic")
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.notes(data, "block"), data["findings"])
                self.assertFalse(self.notes(data, "caution"), data["findings"])
                self.assertTrue([f for f in data["findings"] if f["rule"] == "allowlist" and f["severity"] == "warn"])

    def ids(self, data):
        return [f for f in data["findings"] if f["rule"] == "term" and f["class"] == "id-patterns"
                and f["severity"] == "block" and any(c.isdigit() for c in f["match"])]

    def test_R27_R63_X34_a_com_address_without_a_scheme_hides_its_ids(self):
        self.both()
        for text in ("Open yourcompany.monday.com/boards/123456789 for the depot board.",
                     "The rota is at example.com/page/12345678, with the rest.",
                     "See www.example.com/a/12345678 today.", "See (ashgrove-depot.com/x/12345678).",
                     "See [the board](ashgrove.monday.com/boards/12345678).",
                     "See EXAMPLE.COM/page/12345678|the rest."):
            with self.subTest(text=text):
                code, data = self.payload({"name": "Depot board", "description": text})
                self.assertEqual(code, 0, data["findings"])

    def test_R27_R63_X34_an_id_outside_the_address_or_after_another_ending_still_blocks(self):
        self.both()
        for text in ("Open example.com/page/12345678 and board 87654321.",
                     "Open example.com/page/x,87654321 today.", "Open example.com/page/x|87654321 today.",
                     "Open example.org/page/12345678 today.", "Open example.co.uk/x/12345678 today.",
                     "Open example.com 12345678 today.", "Open example.com/ 12345678 today.",
                     "Open hxxp://example.com/page/12345678 today.", "Open ops@example.com/page/12345678 today.",
                     "Open example.comb/page/12345678 today.", "Open ex_ample.com/page/12345678 today.",
                     "Open example.com/page/run-1234-5678 today."):
            with self.subTest(text=text):
                code, data = self.payload({"name": "Depot board", "description": text})
                self.assertEqual(code, 1, data["findings"])
                self.assertTrue(self.ids(data), data["findings"])

    def test_R27_R63_L155_a_credential_in_a_com_address_without_a_scheme_still_blocks(self):
        self.both()
        for text, rule in (("Post to hooks.example.com/in/12345678?token=Fx7kQ2mL9pR4 nightly.", "credential"),
                           ("Post to hooks.example.com/clients/wrenfold-joinery/calls/x nightly.", "term")):
            with self.subTest(text=text):
                code, data = self.payload({"name": "Depot board", "description": text})
                self.assertEqual(code, 1, data["findings"])
                self.assertIn(rule, [f["rule"] for f in data["findings"] if f["severity"] == "block"])


class A34Test(Base):
    """A34 (R70): a client's own figures warn in its own build, and another client's figures still block (the wall)."""

    def setUp(self):
        super().setUp()
        self.both()

    def blueprint(self, text):
        write(self.a / SA / "solution" / "blueprint.md", "# B\n\n## 1. Purpose\n%s\n" % text + sections(2))
        return self.lint(self.a, "blueprint", "--strand", "001")

    def severities(self, data):
        return sorted((f["rule"], f["class"], f["severity"]) for f in data["findings"]
                      if f["rule"] in ("figure", "split-figure", "wall"))

    def test_A34_R70_another_clients_figure_on_the_wall_still_blocks_beside_an_own_figure_that_warns(self):
        # Record a's own budget of 73,000 warns; record b's 186,730 blocks on the wall in every form it did.
        for other in ("186,730", "$187k", "186.7k", "one hundred and eighty-six thousand seven hundred and thirty"):
            with self.subTest(other=other):
                text = "The saw budget is 73,000 and the fuel came to %s." % other
                # The blueprint comes last: its planned text is this record's own from then on (X11, L189).
                for code, data in (self.payload({"markdown": text}, "doc"), self.draft(text),
                                   self.payload({"items": [{"column_values": json.dumps({"text_1": text})}]},
                                                "item_batch"), self.blueprint(text)):
                    self.assertEqual(code, 1, data["findings"])
                    self.assertEqual(sorted(set(self.severities(data))),
                                     [("figure", None, "warn"), ("wall", "figure", "block")])
                (self.a / SA / "solution" / "blueprint.md").unlink()
        code, data = self.payload({"markdown": "The saw budget is 73,000."}, "doc")
        self.assertEqual((code, self.severities(data)), (2, [("figure", None, "warn")]))
        # The wall is symmetric: in record b's own build its fuel figure warns, and record a's rework figure blocks.
        code, data = self.payload({"label": "Fuel came to 186,730."}, "board", record=self.b)
        self.assertEqual((code, self.severities(data)), (2, [("figure", None, "warn")]))
        code, data = self.payload({"label": "Remakes came to 263,480 a year."}, "board", record=self.b)
        self.assertEqual((code, self.severities(data)), (1, [("wall", "figure", "block")]))


class A36Test(Base):
    """A36 (R71): a test workspace the user named for development builds, held by an own-account record as a
    referenced row, is not one of that record's names. Record b plays the earlier demo that holds it."""

    NAMES = ("Copperlane Test Workspace", "Saltry CRM Test Workspace")

    def demo_in_b(self, name, origin="pre-existing-referenced", own=True):
        """Record b as an own-account demo whose strand plans `name` as W1 and whose ledger holds it as `origin`."""
        client = (self.b / "CLIENT.md").read_text(encoding="utf-8")
        if own:
            client = client.replace('account_kind: "client"', 'account_kind: "own"').replace(
                'build_target: "client-account"', 'build_target: "own-account"')
        write(self.b / "CLIENT.md", client)
        write(self.b / SB / "solution" / "blueprint.md", "# B\n" + sections(1) + "\nW1 is %s, the test workspace the "
              "user named; it is referenced and never written.\n\n## Element keys\n\n| key | kind | name | notifies |\n"
              "|---|---|---|---|\n| W1 | workspace | %s | |\n| F1 | folder | Marlbeck – Ops | |\n" % (name, name))
        write(self.b / SB / "solution" / "build.json", json.dumps({"schema": "build/2", "client_slug": B, "strand": "001",
              "objects": {"W1": {"type": "workspace", "name": name, "origin": origin},
                          "F1": {"type": "folder", "name": "Marlbeck – Ops", "origin": "created"}}}, indent=2))
        self.both()

    def test_A36_R71_a_named_test_workspace_and_its_words_leave_the_index(self):
        for name in self.NAMES:  # no fixed name: whatever the ledger holds as the referenced workspace
            with self.subTest(name=name):
                data = self.demo_in_b(name) or self.index(self.b)
                names = set(self.entry(B)["names"])
                words = lint.words_of(name)
                for form in [" ".join(words), "".join(words), " ".join(words[-2:]), " ".join(words[:-1])]:
                    self.assertNotIn(lint.digest("n:", form), names, form)
                self.assertNotIn(words[0], data["single_words"]["words"])
                self.assertIn(lint.digest("n:", "marlbeck freight"), names)
                text = "Built in the test workspace the user named, %s, in one folder." % name
                code, data = self.payload({"name": "Quote board", "description": text})
                self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
                write(self.a / SA / "solution" / "blueprint.md", "# B\n\n## 1. Purpose\n%s\n" % text + sections(2))
                code, data = self.lint(self.a, "blueprint", "--strand", "001")
                self.assertEqual((code, self.walls(data)), (0, []), data["findings"])
                (self.a / SA / "solution" / "blueprint.md").unlink()

    def test_A36_R71_the_other_clients_names_and_an_unreferenced_workspace_still_block(self):
        write(self.b / "research" / "2026-08-13-vans.md", "- The depot hires its vans from Copperlane Haulage.\n")
        self.demo_in_b(self.NAMES[0])
        for text, match in (("Built for Marlbeck Freight.", "Marlbeck Freight"),
                            ("Vans from Copperlane Haulage.", "Copperlane Haulage")):  # the same word, another name
            with self.subTest(text=text):
                code, data = self.payload({"description": text})
                self.assertWall(data, "name", match)
        for origin, own in (("created", True), ("pre-existing-referenced", False)):
            with self.subTest(origin=origin, own=own):  # a workspace built for the client, or one in its own account
                self.demo_in_b(self.NAMES[1], origin, own)
                code, data = self.payload({"description": "Built in %s." % self.NAMES[1]})
                self.assertWall(data, "name")
                write(self.b / "CLIENT.md", (FIX / "records" / B / "CLIENT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
