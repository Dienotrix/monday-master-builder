"""Self-test of the leak-trap fixture under tests/fixtures/leak/ (WP4, step 4).

It checks the fixture alone: the manifest and its files agree, every planted case names its rule and its category
and has one clean twin, every category of the decisions' section 3 and every payload kind of Pinned: leak is
planted, every rule and kind is a pinned one, no twin carries a row of the shipped leak-terms.txt, every file is
UTF-8 with LF and no byte-order mark, and every capitalised token is an invented name of the README's closed list,
a common word or the start of a sentence (DECISIONS X18). It does not import leak_lint.py; grading the lint against
the manifest is step 6's, which adds to this file. Standard library only.
"""
import sys

sys.dont_write_bytecode = True

import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import unittest  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402
import zipfile  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FIX = os.path.join(REPO, "tests", "fixtures", "leak")
SHARED = os.path.join(REPO, "plugins", "monday-master-builder", "shared")

# DECISIONS section 3.2: the twenty trap categories of A§:918, split into their parts as the table splits them.
TRAP = ["case-varied-names", "possessive-names", "comma-split-names", "identifier-in-header",
        "alias-ordinary-word", "name-from-body", "customer-acronym", "customer-full-name",
        "seller-commercial-terms", "split-date", "assessment-of-individual", "small-talk",
        "third-party-in-passing", "partner-two-ordinary-words", "corrupted-name-in-hypothetical",
        "fused-product-name", "vendor-substitution", "email-separator-lost", "first-names-in-quotation",
        "counterparty-owner-tools", "departure-hypothetical", "seller-account-structure",
        "health-remark-absent-person"]
# DECISIONS section 3.1: the kinds of leak the twenty-five answer keys describe.
KEY = ["K%02d" % n for n in range(1, 37)]
# DECISIONS section 3.3 and PLAN section 4.1: the rule cases of BP:158.
RULE = ["figures-five-formats", "figures-split-renderings", "copied-run-placements", "quote-eight-words",
        "markers-nine", "internal-ids", "record-paths", "html-comments", "monday-id-link",
        "exempt-blocks-and-glossary", "common-word-run", "tool-categories-three-two",
        "firm-renderings-phonetic-whitelist", "flag-do-not-remove", "caution", "credentials", "internal-notes",
        "exclusion-per-family", "allowlist-limits", "payload-per-kind", "docx-parts", "summary-two-rules",
        "client-safe-block-at-intake", "wall-records", "structural-ids", "payload-keys-and-numbers"]
COMMANDS = ("scan", "payload", "blueprint", "wall", "terms", "index")
OUTCOMES = {"blocks": ("blocked", 1), "warns": ("warnings", 2), "caution": ("warnings", 2)}
CASE_KEYS = ("id", "role", "group", "record", "files", "overlay", "install", "command", "args", "mode", "verdict",
             "exit", "outcome", "expect")
TEXT_EXT = (".md", ".txt", ".json", ".xml")

# Common words that may be written with a capital inside a sentence (X18), compared in lower case.
COMMON = set("""
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august
september october november december i ok id ai crm erp json url html xml posix windows vibe met partial missing
users private key begin read mmb strand summary md client
""".split())

# DECISIONS Y08: the structural keys whose digit-only values are monday ids, not text. It mirrors the script's
# pinned structural-id-keys region; a value under one of them is not text the shipped id row reads.
STRUCTURAL_ID_KEYS = set("""
id ids account_id workspace_id workspace_ids workspaceId workspaceIds folder_id folder_ids folderId board_id board_ids
boardId boardIds group_id groupId item_id item_ids itemId itemIds parent_id parentId parent_item_id doc_id docId
object_id objectId view_id viewId dashboard_id dashboardId widget_id widgetId automation_id automationId workflow_id
workflowId agent_id agentId app_id appId user_id user_ids userId userIds team_id team_ids teamId teamIds owner_ids
subscriber_ids
""".split())

BLOCK_MARKS = ("<!-- client-safe:start -->", "<!-- client-safe:end -->", "<!-- glossary:start -->",
               "<!-- glossary:end -->")


def path(rel):
    return os.path.join(FIX, *rel.split("/"))


def raw(rel):
    with open(path(rel), "rb") as handle:
        return handle.read()


def text(rel):
    return raw(rel).decode("utf-8")


def all_files():
    out = []
    for root, dirs, files in os.walk(FIX):
        dirs.sort()
        for name in sorted(files):
            out.append(os.path.relpath(os.path.join(root, name), FIX).replace(os.sep, "/"))
    return out


def under(folder):
    return [rel for rel in all_files() if rel.startswith(folder.rstrip("/") + "/")]


def pinned_leak():
    """The Pinned: leak section of the shipped record map, as {field: [tokens]} and {kind: [families]}."""
    with open(os.path.join(SHARED, "record-map.md"), encoding="utf-8") as handle:
        body = handle.read()
    section = body.split("\n## Pinned: leak\n", 1)[1].split("\n## ", 1)[0]
    fields, families = {}, {}
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            continue
        left, right = re.findall(r"`([^`]+)`", cells[0]), re.findall(r"`([^`]+)`", cells[1])
        if left:
            for kind in left:
                families[kind] = right if cells[1] != "every family" else ["*"]
        elif right:
            fields[cells[0]] = right
    return fields, families


def shipped_patterns():
    """Every term row of shipped leak-terms.txt as (class, compiled pattern), following its syntax (LT:17 to 29).
    The counted tool-category classes are skipped: they never block, and a twin with two categories is meant."""
    out, cls = [], None
    with open(os.path.join(SHARED, "leak-terms.txt"), encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("class:"):
                cls = line[len("class:"):].strip()
                continue
            if cls and cls.startswith("tool-category-"):
                continue
            if line.startswith("whitelist:"):
                continue
            if line.startswith("re:"):
                out.append((cls, re.compile(line[3:].strip(), re.IGNORECASE)))
                continue
            if line.startswith("phonetic:"):
                line = line[len("phonetic:"):]
            term = line.strip()
            out.append((cls, re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE)))
    return out


def strip_xml(body):
    return re.sub(r"<[^>]+>", "\n", body.replace("</w:p>", "\n"))


def json_strings(value, out):
    """Every string and object key of a payload, a string holding JSON walked as JSON as well (X22)."""
    if isinstance(value, dict):
        for key, sub in value.items():
            out.append(key)
            if key in STRUCTURAL_ID_KEYS and structural_id(sub):
                continue
            json_strings(sub, out)
    elif isinstance(value, list):
        for sub in value:
            json_strings(sub, out)
    elif isinstance(value, str):
        out.append(value)
        if value[:1] in "{[":
            try:
                json_strings(json.loads(value), out)
            except ValueError:
                pass
    return out


def structural_id(value):
    """A digit string with no leading zero, a JSON integer, or a list of them (Y08)."""
    if isinstance(value, list):
        return bool(value) and all(structural_id(v) for v in value)
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value) is not None


def checked_text(rel):
    """The text the lint would check: payload strings, XML without tags, Markdown without the block-mark lines."""
    body = text(rel)
    if rel.endswith(".json"):
        return "\n".join(json_strings(json.loads(body), [])) + "\n"
    if rel.endswith(".xml"):
        return re.sub(r"<[^>]+>", "", body.replace("</w:p>", "\n"))
    return "\n".join(line for line in body.splitlines() if line.strip() not in BLOCK_MARKS) + "\n"


def closed_list():
    body = text("README.md")
    section = body.split("\n## Invented names and renderings\n", 1)[1].split("\n## ", 1)[0]
    words = set()
    for item in re.findall(r"`([^`]+)`", section):
        words.update(w.lower() for w in re.findall(r"[A-Za-z]+", item))
    return words


def capitalised_strays(body, allowed):
    """Capitalised tokens that are neither allowed nor first in their sentence (X18)."""
    strays = []
    for segment in re.split(r"[\n|\"“”()\[\]{}<>]|[.!?:;](?=\s)|\s[-–—]\s", body):
        first = True
        for match in re.finditer(r"[A-Za-z0-9_]+(?:['’][A-Za-z]+)*", segment):
            token = re.sub(r"['’]s$", "", match.group(0))
            if first:
                first = False
                continue
            if not token.isalpha() or len(token) < 2 or not token[0].isupper():
                continue
            if token.lower() not in allowed:
                strays.append(token)
    return strays


def resolve(data, where):
    """The value at a payload path such as $.items[0].column_values<json>.text_1 (X22); a path ending in <key>
    names an object key, and resolves to the key itself."""
    if where.endswith("<key>"):
        parent, _, key = where[:-5].rpartition(".")
        holder = resolve(data, parent) if parent != "$" else data
        return key if key in holder else None
    value = data
    for part in re.findall(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|(<json>)", where[1:]):
        name, index, inner = part
        if inner:
            value = json.loads(value)
        elif index:
            value = value[int(index)]
        else:
            value = value[name]
    return value


class LeakFixtureTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(text("manifest.json"))
        cls.cases = cls.manifest["cases"]
        cls.by_id = {case["id"]: case for case in cls.cases}
        cls.planted = [case for case in cls.cases if case["role"] == "planted"]
        cls.twins = [case for case in cls.cases if case["role"] == "twin"]
        cls.fields, cls.families = pinned_leak()

    # ---- files and encoding

    def test_files_utf8_lf_no_bom(self):
        files = all_files()
        self.assertGreater(len(files), 200)
        for rel in files:
            body = raw(rel)
            self.assertFalse(body.startswith(b"\xef\xbb\xbf"), rel + " has a byte-order mark")
            self.assertNotIn(b"\r", body, rel + " is not LF only")
            body.decode("utf-8")
            self.assertTrue(body.endswith(b"\n"), rel + " has no final newline")
            self.assertTrue(rel.endswith(TEXT_EXT) or rel == ".gitattributes", rel + " is not a text file kind")
        self.assertEqual(text(".gitattributes").split(), ["*", "text", "eol=lf"])

    def test_every_file_is_named_by_the_manifest(self):
        named = {"README.md", "manifest.json", ".gitattributes"}
        home = self.manifest["home"]
        named.update([home["settings"]["from"], home["local_terms"]["from"]])
        for record in home["records"].values():
            files = under(record["from"])
            self.assertTrue(files, record["from"])
            named.update(files)
        for overlay in home["overlays"].values():
            files = under(overlay["from"])
            self.assertTrue(files, overlay["from"])
            named.update(files)
        for case in self.cases:
            named.update(case["files"])
        self.assertEqual(sorted(set(all_files()) - named), [], "files no case names")
        self.assertEqual(sorted(named - set(all_files())), [], "files named but absent")

    # ---- the manifest

    def test_manifest_shape(self):
        self.assertEqual(self.manifest["schema"], "leak-fixture/1")
        self.assertEqual(len(self.by_id), len(self.cases), "case ids are unique")
        records = self.manifest["home"]["records"]
        overlays = self.manifest["home"]["overlays"]
        for case in self.cases:
            cid = case["id"]
            for key in CASE_KEYS:
                self.assertIn(key, case, cid)
            self.assertIn(case["role"], ("planted", "twin"), cid)
            self.assertIn(case["record"], records, cid)
            self.assertIn(case["command"], COMMANDS, cid)
            self.assertTrue(case["files"], cid)
            for rel in case["files"]:
                self.assertTrue(os.path.isfile(path(rel)), cid + ": " + rel)
            if case["overlay"] is not None:
                self.assertIn(case["overlay"], overlays, cid)
            for entry in case["install"]:
                self.assertIn("to", entry, cid)
                self.assertFalse(entry["to"].startswith("/") or "\\" in entry["to"] or ".." in entry["to"], cid)
                if "zip" in entry:
                    self.assertTrue(os.path.isfile(path(entry["zip"] + "/word/document.xml")), cid)
                    self.assertTrue(entry["to"].endswith(".docx"), cid)
                else:
                    self.assertIn(entry["from"], case["files"], cid)
            self.assertTrue(all(isinstance(a, str) for a in case["args"]), cid)
            if case["command"] == "scan":
                self.assertEqual(case["args"], [e["to"] for e in case["install"]], cid)
                self.assertIn(case["mode"], ("full", "summary", "client-safe-block"), cid)
            if case["command"] == "payload":
                args = case["args"]
                self.assertEqual(args[0::2], ["--strand", "--kind", "--file"], cid)
                self.assertEqual(args[5], case["install"][0]["to"], cid)
                self.assertIsNone(case["mode"], cid)
            if case["command"] == "blueprint":
                self.assertEqual(case["mode"], "blueprint", cid)
            self.assertEqual(case["verdict"], {0: "clean", 1: "blocked", 2: "warnings"}[case["exit"]], cid)

    def test_one_twin_for_each_planted_case(self):
        self.assertEqual(len(self.planted), len(self.twins))
        seen = set()
        for case in self.planted:
            twin = self.by_id.get(case["twin"])
            self.assertIsNotNone(twin, case["id"])
            self.assertEqual(twin["role"], "twin", case["id"])
            self.assertEqual(twin["twin_of"], case["id"])
            self.assertNotIn(twin["id"], seen)
            seen.add(twin["id"])
            self.assertEqual((twin["command"], twin["record"], twin["mode"]),
                             (case["command"], case["record"], case["mode"]), case["id"])
        for twin in self.twins:
            self.assertEqual(self.by_id[twin["twin_of"]]["twin"], twin["id"])
            self.assertEqual(twin["outcome"], "passes", twin["id"])
            self.assertIn(twin["exit"], (0, 2), twin["id"])
            self.assertTrue(twin.get("why_clean"), twin["id"])
            for entry in twin["expect"]:
                self.assertEqual(entry["severity"], "warn", twin["id"] + ": a twin may only carry warnings")
            self.assertEqual(twin["exit"] == 2, bool(twin["expect"]), twin["id"])

    def test_planted_cases_name_rule_category_and_outcome(self):
        prefixes = {"trap": TRAP, "key": KEY, "rule": RULE, "payload-kind": None}
        for case in self.planted:
            cid = case["id"]
            self.assertTrue(case["covers"], cid)
            for cover in case["covers"]:
                prefix, _, name = cover.partition(":")
                self.assertIn(prefix, prefixes, cid)
                if prefixes[prefix] is not None:
                    self.assertIn(name, prefixes[prefix], cid)
            self.assertTrue(case.get("summary"), cid)
            self.assertEqual(case["rules"], sorted({e["rule"] for e in case["expect"]}), cid)
            if case["outcome"] == "limit":
                self.assertTrue(case.get("limit"), cid)
                self.assertEqual(case["expect"], [], cid)
                self.assertIn(case["exit"], (0, 2), cid)
            else:
                self.assertIn(case["outcome"], OUTCOMES, cid)
                self.assertTrue(case["rules"], cid)
                self.assertEqual((case["verdict"], case["exit"]), OUTCOMES[case["outcome"]], cid)
                severities = {e["severity"] for e in case["expect"]}
                wanted = {"blocks": "block", "warns": "warn", "caution": "caution"}[case["outcome"]]
                self.assertIn(wanted, severities, cid)
                if case["outcome"] != "blocks":
                    self.assertNotIn("block", severities, cid)

    def test_every_category_has_a_planted_case(self):
        categories = self.manifest["categories"]
        self.assertEqual(categories["trap"], TRAP)
        self.assertEqual(categories["key"], KEY)
        self.assertEqual(categories["rule"], RULE)
        self.assertEqual(categories["payload-kind"], self.fields["payload kind"])
        covered = {cover for case in self.planted for cover in case["covers"]}
        for prefix, names in (("trap", TRAP), ("key", KEY), ("rule", RULE),
                              ("payload-kind", self.fields["payload kind"])):
            for name in names:
                self.assertIn("%s:%s" % (prefix, name), covered, "no planted case for %s:%s" % (prefix, name))

    def test_every_payload_kind_has_a_sample_and_a_twin(self):
        kinds = self.fields["payload kind"]
        self.assertEqual(len(kinds), 24)
        all_families = self.fields["field family"]
        for kind in kinds:
            samples = [c for c in self.planted if "payload-kind:" + kind in c["covers"]]
            self.assertEqual(len(samples), 1, kind)
            sample = samples[0]
            self.assertEqual(sample["command"], "payload", kind)
            self.assertEqual(sample["args"][3], kind)
            self.assertEqual(self.by_id[sample["twin"]]["args"][3], kind)
            wanted = self.families[kind]
            wanted = all_families if wanted == ["*"] else wanted
            got = [e.get("family") for e in sample["expect"]]
            self.assertEqual(sorted(set(got)), sorted(wanted), kind + ": one leak per field family")
            self.assertEqual(len(got), len(wanted), kind + ": one leak per field family")

    def test_rules_kinds_and_words_are_pinned(self):
        rules = set(self.fields["rule"])
        severities = set(self.fields["severity"])
        verdicts = set(self.fields["verdict"])
        modes = set(self.fields["scan mode"])
        wall_classes = set(self.fields["wall finding class"])
        families = set(self.fields["field family"])
        kinds = set(self.fields["payload kind"])
        self.assertEqual(len(rules), 16)
        for case in self.cases:
            cid = case["id"]
            self.assertIn(case["verdict"], verdicts, cid)
            if case["mode"] is not None:
                self.assertIn(case["mode"], modes, cid)
            if case["command"] == "payload":
                self.assertIn(case["args"][3], kinds, cid)
            for entry in case["expect"]:
                self.assertIn(entry["rule"], rules, cid)
                self.assertIn(entry["severity"], severities, cid)
                if entry["rule"] == "wall":
                    self.assertIn(entry["class"], wall_classes, cid)
                if "family" in entry:
                    self.assertIn(entry["family"], families, cid)
            for rule in case.get("rules", []):
                self.assertIn(rule, rules, cid)

    def test_planted_text_is_where_the_manifest_says(self):
        for case in self.planted:
            cid = case["id"]
            for entry in case["expect"]:
                where = entry["where"]
                if where is None:
                    continue
                if case["command"] == "payload":
                    data = json.loads(text(case["files"][0]))
                    value = resolve(data, where)
                    self.assertTrue(isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool)),
                                    cid + ": " + where)
                elif "zip" in case["install"][0]:
                    part = case["install"][0]["zip"] + "/" + where
                    self.assertIn(part, case["files"], cid)
                    self.assertIn(entry["match"], re.sub(r"<[^>]+>", "", text(part)), cid)
                else:
                    number = int(where.split()[1])
                    line = text(case["files"][0]).split("\n")[number - 1]
                    self.assertIn(entry["match"].split("\n")[0], line, cid + ": " + where)

    # ---- the twins carry no shipped term

    def test_no_twin_carries_a_shipped_term(self):
        patterns = shipped_patterns()
        self.assertGreater(len(patterns), 120)
        for case in self.twins:
            for rel in case["files"]:
                body = checked_text(rel)
                for cls, pattern in patterns:
                    hit = pattern.search(body)
                    self.assertIsNone(hit, "%s: %s matches the %s row %s" % (
                        case["id"], hit.group(0) if hit else "", cls, pattern.pattern))

    # ---- invented names (X18)

    def test_capitalised_tokens_are_invented_names_common_words_or_sentence_starts(self):
        allowed = closed_list() | COMMON
        self.assertIn("thymbel", allowed)
        self.assertGreater(len(allowed), 80)
        for rel in all_files():
            if rel == "README.md" or rel == ".gitattributes":
                continue
            body = text(rel)
            if rel.endswith(".xml"):
                body = strip_xml(body)
            strays = capitalised_strays(body, allowed)
            self.assertEqual(strays, [], rel + ": capitalised words outside the closed list")

    # ---- the README

    def test_readme_has_one_row_per_planted_case(self):
        rows = {}
        for line in text("README.md").splitlines():
            match = re.match(r"\| ([A-Z][A-Za-z0-9_-]*-p) \| `([^`]+)`", line)
            if match:
                self.assertNotIn(match.group(1), rows, "two rows for " + match.group(1))
                cells = line.split(" | ")
                rows[match.group(1)] = (match.group(2), cells[6].strip("` "))
        self.assertEqual(sorted(rows), sorted(c["id"] for c in self.planted))
        for case in self.planted:
            twin = self.by_id[case["twin"]]
            planted_file, twin_file = (c["install"][0]["zip"] + "/" if "zip" in c["install"][0] else c["files"][0]
                                       for c in (case, twin))
            self.assertEqual(rows[case["id"]], (planted_file, twin_file), case["id"])

    def test_readme_states_what_the_fixture_cannot_prove(self):
        body = text("README.md")
        section = body.split("\n## What this fixture cannot prove\n", 1)[1].split("\n## ", 1)[0]
        for words in ("whole set", "real vocabulary", "false-positive rate", "other than English"):
            self.assertIn(words, section)
        for case in self.planted:
            if case["outcome"] == "limit":
                self.assertIn("`%s`" % case["id"], body.split("\n## Known limits the fixture asserts\n", 1)[1])

    # ---- the home, the records and the .docx samples

    def test_settings_and_local_list(self):
        settings = json.loads(text(self.manifest["home"]["settings"]["from"]))
        self.assertEqual(settings["schema"], "settings/1")
        for key in ("created", "plugin_version", "firm", "default_build_account", "never_show_workspaces", "archive"):
            self.assertIn(key, settings)
        firm = settings["firm"]
        self.assertTrue(firm["name"] and isinstance(firm["renderings"], list) and firm["renderings"])
        self.assertTrue(all(isinstance(w["id"], str) and isinstance(w["name"], str)
                            for w in settings["never_show_workspaces"]))
        self.assertEqual(settings["archive"], "github")
        self.assertIn("github_account", settings)
        allowed = closed_list()
        for word in re.findall(r"[A-Za-z]+", " ".join([firm["name"]] + firm["renderings"])):
            self.assertIn(word.lower(), allowed | {"example"})
        local = text(self.manifest["home"]["local_terms"]["from"]).splitlines()
        rows = [line for line in local if line.strip() and not line.startswith("#")]
        self.assertFalse(rows[0].startswith("class:"), "the colleague row sits above the first class line")
        self.assertIn("class: firm", rows)
        self.assertIn("whitelist: thimble", rows)

    def test_records_carry_the_shapes_the_lint_reads(self):
        for key, record in self.manifest["home"]["records"].items():
            client = text(record["from"] + "/CLIENT.md")
            slug = re.search(r'^slug: "([^"]+)"$', client, re.M).group(1)
            self.assertEqual(record["from"].split("/")[-1], slug)
            self.assertEqual(record["to"], "clients/" + slug)
            self.assertTrue(any(rel.endswith("/solution/exclusions.md") for rel in under(record["from"])), key)
        a = self.manifest["home"]["records"]["a"]["from"]
        for rel in ("calls/2026-09-08-discovery.md", "inputs/2026-09-15-panel-procedure.md"):
            lines = [line.strip() for line in text(a + "/" + rel).splitlines()]
            self.assertEqual(lines.count(BLOCK_MARKS[0]), 1, rel)
            self.assertEqual(lines.count(BLOCK_MARKS[1]), 1, rel)
            self.assertLess(lines.index(BLOCK_MARKS[0]), lines.index(BLOCK_MARKS[1]), rel)
        self.assertIn("## Conflicts", text(a + "/inputs/2026-09-15-panel-procedure.md").splitlines())
        self.assertIn("## Allowlist", text(a + "/strands/001-quote-tracker/solution/allowlist.md").splitlines())
        for overlay in self.manifest["home"]["overlays"].values():
            for rel in under(overlay["from"]):
                inner = rel[len(overlay["from"]) + 1:]
                self.assertTrue(os.path.isfile(path(a + "/" + inner)), "an overlay replaces an existing file: " + rel)

    def test_docx_samples_build_with_zipfile(self):
        built = 0
        for case in self.cases:
            for entry in case["install"]:
                if "zip" not in entry:
                    continue
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                    for rel in under(entry["zip"]):
                        body = text(rel)
                        self.assertNotIn("<!DOCTYPE", body, rel)
                        ET.fromstring(raw(rel))
                        archive.writestr(rel[len(entry["zip"]) + 1:], raw(rel))
                with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
                    names = archive.namelist()
                    self.assertIn("word/document.xml", names, case["id"])
                    for e in case["expect"]:
                        self.assertIn(e["where"], names, case["id"])
                built += 1
        self.assertEqual(built, 18)
        parts = {e["where"] for c in self.planted if "zip" in c["install"][0] for e in c["expect"]}
        for part in ("word/document.xml", "docProps/core.xml", "docProps/app.xml"):
            self.assertIn(part, parts)


if __name__ == "__main__":
    unittest.main()
