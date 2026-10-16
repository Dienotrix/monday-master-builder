"""Self-test of the synthetic monday reads under tests/fixtures/snapshots/ (WP3, A29).

It checks the reads and their answer keys against each other and against W01's rules:
the marking, the page id lists, the schema field list, the id ranges, the names, the
totals, the planted cases and every digest. Standard library only; it imports nothing
from ledger.py and opens no network connection.
"""
import sys

sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import unittest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SNAP = os.path.join(REPO, "tests", "fixtures", "snapshots")
SHARED = os.path.join(REPO, "plugins", "monday-master-builder", "shared")

FILES = [
    "README.md", ".gitattributes", "schema-fields.json",
    "identification.reads.json", "identification.expected.json",
    "native.reads.json", "native.expected.json",
    "compare/before.read.json", "compare/after.read.json", "compare/ledger-state.json",
    "compare/appendix.md", "compare/expected.json",
    "reconcile/live-inventory.json", "reconcile/ledger-state.json", "reconcile/expected.json",
]
HEADED = [
    "identification.reads.json", "native.reads.json", "compare/before.read.json", "compare/after.read.json",
    "compare/ledger-state.json", "reconcile/live-inventory.json", "reconcile/ledger-state.json",
]
KEYS = ["identification.expected.json", "native.expected.json", "compare/expected.json", "reconcile/expected.json"]
HEADER_KEYS = ["synthetic", "ring_modelled", "schema_source", "sources", "built", "confirmed_by_capture", "id_rule"]
RING = "release_candidate 2026-10"

RANGES = {
    "workspace": (90100000001, 90100009999), "folder": (90200000001, 90200009999),
    "board": (90300000001, 90300999999), "view": (90400000001, 90400999999),
    "item": (90500000001, 90509999999), "user": (90600000001, 90600009999),
    "object": (90700000001, 90700009999), "agent": (90800000001, 90800009999),
    "vibe_app": (90900000001, 90900009999), "workflow_draft": (91000000001, 91000009999),
    "automation": (91100000001, 91100999999), "dashboard": (91200000001, 91200009999),
    "doc": (91300000001, 91300009999), "account": (91400000001, 91400000099),
    "product": (91500000001, 91500000099), "widget": (91600000001, 91600099999),
    "team": (91700000001, 91700000999),
}
KEY_TYPES = {
    "workspace_id": "workspace", "workspace_ids": "workspace", "default_workspace_id": "workspace",
    "workspace": "workspace", "client_workspace_ids": "workspace", "workspace_scope": "workspace",
    "board_folder_id": "folder", "folder_id": "folder", "folder_ids": "folder",
    "board_id": "board", "board_ids": "board", "boardIds": "board", "created_from_board_id": "board",
    "object_id": "board", "tasks_board_id": "board", "portfolio_id": "board", "overview_board_id": "board",
    "doc_container_board_id": "board", "chain": "board", "unreadable_ids": "board", "dropped": "board",
    "source_view_id": "view", "view_id": "view",
    "linked_item_ids": "item", "item_ids": "item",
    "owners": "user", "subscribers": "user", "creator_user_id": "user", "owner_user_ids": "user",
}
COLLECTION_TYPES = {
    "boards": "board", "inventory": "board", "workflows": "board", "objects": "board", "portal_active": "board",
    "portal_archived": "board", "knowledge": "board", "board": "board", "workspaces": "workspace",
    "workspace": "workspace", "views": "view", "items": "item", "linked_items": "item", "products": "product",
    "account_product": "product", "docs": "doc", "folders": "folder", "automations": "automation",
    "agents": "agent", "vibe_apps": "vibe_app", "dashboards": "dashboard", "returned": "dashboard",
}
PAGE_ID_TYPES = {"boards_sweep": "board", "boards_ids": "board", "workspaces": "workspace",
                 "account_products": "product", "docs": "doc", "workflow_objects": "board",
                 "portfolio_items": "board"}
BOARD_RULES = {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "N1a", "N1b", "N2", "N3",
               "N4", "N5", "N6", "N7", "N8", "N9", "N10"}
PROJECT_RULES = {"C1", "C2", "C3", "C4"}
ENTRY_KEYS = ["case", "class", "rule", "attributes", "confidence", "signals", "lineage", "review", "limits", "models"]
ATTR_KEYS = ["family", "version", "install_kind", "sla_mark", "state", "items_count"]
LINEAGE_KEYS = ["chain", "resolved", "result", "hops", "note"]
NAME_KEYS = ("name", "title", "item_terminology", "name_at_build")
CLASSES = ["adopt", "retry", "duplicate", "partial", "changed-since-verified", "unrecorded-extra", "missing"]
BOARD_FIELDS = ("name", "type", "state", "workspace_id", "board_folder_id")

NATIVE_CASES = {
    "CRM v2, each entity": ["crm-v2-leads", "crm-v2-opportunities", "crm-v2-contacts", "crm-v2-accounts-renamed",
                            "crm-v2-activities", "crm-v2-sales-targets-chain-broken"],
    "CRM core v1, each entity": ["crm-v1-deals", "crm-v1-contacts", "crm-v1-leads", "crm-v1-accounts",
                                 "crm-v1-activities", "crm-v1-deals-subitems"],
    "companions (N6)": ["crm-companion-marks", "crm-companion-unresolved"],
    "Quotes & Invoices with its line items": ["crm-quotes-invoices", "crm-qi-line-items"],
    "Products & Services": ["crm-products-services"],
    "Service family A": ["service-a-tickets-sla", "service-a-tickets-subitems"],
    "Service family B": ["service-b-tickets", "service-b-csat", "service-b-contacts"],
    "Service family C": ["service-c-tickets", "service-c-incidents", "service-c-asset-management",
                         "service-c-employee-lifecycle", "service-c-employee-directory"],
    "Service family D": ["service-d-tickets", "service-d-incidents"],
    "Service subitems (N5)": ["service-a-tickets-subitems", "service-c-tickets-subitems",
                              "service-c-lifecycle-subitems"],
    "a satellite (N7)": ["service-satellite"],
    "the Portal active and archived (N1a, N1b)": ["portal-active", "portal-archived-alias",
                                                  "portal-archived-lineage"],
    "lineage at 0, 1 and 2 hops and unresolved": ["crm-v2-leads", "crm-v1-deals-copy-1hop",
                                                  "service-b-tickets-copy-2hop",
                                                  "crm-v2-sales-targets-chain-broken"],
    "a chain-broken native by reserved ids (N4)": ["service-c-tickets-chain-broken"],
    "a template view id alone (N3)": ["service-c-csat-view-only"],
    "blank defaults and suffixed ids": ["ordinary-test-blank-defaults", "ordinary-test-suffixed-ids"],
    "the SLA mark as an attribute": ["service-a-tickets-sla"],
    "two look-alikes (N8)": ["lookalike-name", "lookalike-terminology"],
    "a renamed native with changed terminology": ["crm-v2-accounts-renamed"],
    "an ordinary board linking into a native (N9)": ["ordinary-links-into-native"],
    "ordinary boards in a product workspace": ["ordinary-terminology-client", "ordinary-terminology-call"],
    "ordinary boards in a test workspace": ["ordinary-test-blank-defaults", "ordinary-test-suffixed-ids"],
    "a native moved into a core workspace (N10)": ["native-moved-to-core"],
    "boards the identification rules own": ["keyed-board-with-native-signals", "custom-object-other",
                                            "service-b-start-here-doc"],
    "a deleted native with lineage only": ["deleted-native-lineage-only"],
    "the two known limits": ["planted-ids", "stripped-native", "default-shaped-satellite"],
}
CASE_RULES = {
    "crm-v2-leads": "N2", "crm-v1-deals-copy-1hop": "N2", "service-b-tickets-copy-2hop": "N2",
    "crm-v2-sales-targets-chain-broken": "N4", "service-c-tickets-chain-broken": "N4",
    "service-c-csat-view-only": "N3", "crm-companion-marks": "N6", "crm-companion-unresolved": "N6",
    "crm-qi-line-items": "N5", "service-a-tickets-subitems": "N5", "service-satellite": "N7",
    "portal-active": "N1a", "portal-archived-alias": "N1a", "portal-archived-lineage": "N1b",
    "lookalike-name": "N8", "lookalike-terminology": "N8", "stripped-native": "N8", "planted-ids": "N4",
    "ordinary-links-into-native": "N9", "ordinary-terminology-client": "N9", "native-moved-to-core": "N10",
    "keyed-board-with-native-signals": "R7", "custom-object-other": "R3", "service-b-start-here-doc": "R1",
    "ordinary-test-blank-defaults": "R11", "ordinary-test-suffixed-ids": "R11",
    "deleted-native-lineage-only": "N2",
}
COMPARE_FLAG_CASES = ["description-change", "archived-board", "column-digest-change", "owner-change",
                      "agent-version-id-moved", "agent-state-moved", "workflow-state-moved"]
COMPARE_DOC_CASES = {"appendix-mutation": "refused", "appendix-subscription": "refused",
                     "appendix-two-operations": "refused", "appendix-clean-query": "pass",
                     "appendix-word-in-string": "pass", "appendix-word-in-comment": "pass"}


def digest(prefix, fields):
    text = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    value = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return value if prefix is None else prefix + ":" + value


def raw(rel):
    with open(os.path.join(SNAP, *rel.split("/")), "rb") as handle:
        return handle.read()


def load(rel):
    return json.loads(raw(rel).decode("utf-8"))


def catalogue_ids():
    with open(os.path.join(SHARED, "native-objects.md"), encoding="utf-8") as handle:
        return set(re.findall(r"`(\d{8,})`", handle.read()))


def leak_patterns():
    patterns = []
    with open(os.path.join(SHARED, "leak-terms.txt"), encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#") or line.startswith("class:") or line.startswith("whitelist:"):
                continue
            if line.startswith("re:"):
                patterns.append(re.compile(line[3:].strip(), re.IGNORECASE))
                continue
            if line.startswith("phonetic:"):
                line = line[len("phonetic:"):]
            term = line.strip()
            patterns.append(re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE))
    return patterns


def stems():
    text = raw("README.md").decode("utf-8")
    section = text.split("## Allowed name stems", 1)[1].split("\n## ", 1)[0]
    return {w.lower() for w in re.findall(r"`([A-Za-z]+)`", section)}


def walk_values(value, path=()):
    """Yield (path, key, value) for every scalar; dict keys are yielded too, as ('<key>', key)."""
    if isinstance(value, dict):
        for key, sub in value.items():
            yield path, "<key>", key
            for item in walk_values(sub, path + (key,)):
                yield item
    elif isinstance(value, list):
        for sub in value:
            for item in walk_values(sub, path):
                yield item
    else:
        yield path, path[-1] if path else None, value


def response_paths(value, path, aliases, stops, out):
    if isinstance(value, list):
        for item in value:
            response_paths(item, path, aliases, stops, out)
        return
    if path:
        out.add(path)
    if any(path == s or path.startswith(s + ".") for s in stops):
        return
    if isinstance(value, dict):
        for key, sub in value.items():
            seg = aliases.get(key, key)
            response_paths(sub, path + "." + seg if path else seg, aliases, stops, out)


def get_at(data, at):
    for step in at:
        data = data[step]
    return data


def id_type(path, page_kind):
    keys = [k for k in path if not isinstance(k, int)]
    last = keys[-1] if keys else None
    if last in ("requested_ids", "returned_ids", "missing_ids"):
        return PAGE_ID_TYPES.get(page_kind, "dashboard")
    if last in KEY_TYPES:
        return KEY_TYPES[last]
    if last == "id" and len(keys) >= 2:
        return COLLECTION_TYPES.get(keys[-2])
    return None


class SnapshotFixtureTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = {rel: load(rel) for rel in FILES if rel.endswith(".json")}
        cls.catalogue = catalogue_ids()

    # ---- files, encoding, marking

    def test_files_exist_lf_utf8_no_bom(self):
        for rel in FILES:
            body = raw(rel)
            self.assertFalse(body.startswith(b"\xef\xbb\xbf"), rel + " has a byte-order mark")
            self.assertNotIn(b"\r", body, rel + " is not LF only")
            body.decode("utf-8")
            self.assertTrue(body.endswith(b"\n"), rel)
        self.assertEqual(raw(".gitattributes").decode("utf-8").split(), ["*", "text", "eol=lf"])

    def test_headers(self):
        for rel in HEADED + KEYS:
            head = self.data[rel]["fixture"]
            self.assertEqual(list(self.data[rel])[0], "fixture", rel)
            expected_keys = HEADER_KEYS + (["answers_for"] if rel in KEYS else [])
            self.assertEqual(list(head), expected_keys, rel)
            self.assertIs(head["synthetic"], True, rel)
            self.assertIsNone(head["confirmed_by_capture"], rel)
            self.assertEqual(head["ring_modelled"], RING, rel)
            self.assertEqual(head["built"], "2026-10-16", rel)
            self.assertEqual(head["schema_source"]["version"], "2026-10", rel)
            self.assertEqual(head["schema_source"]["field_list"], "schema-fields.json", rel)
            self.assertTrue(head["sources"], rel)
            for source in head["sources"]:
                self.assertNotIn("/", source.replace("live-map/1", "").replace("build/2", "")
                                 .replace("account/1", ""), rel + ": a source is a path")
        self.assertIn("P-19", self.data["reconcile/live-inventory.json"]["fixture"]["sources"])
        self.assertIn("P-21", self.data["compare/before.read.json"]["fixture"]["sources"])

    def test_no_answer_in_a_reads_file(self):
        for rel in ("identification.reads.json", "native.reads.json"):
            for path, key, value in walk_values(self.data[rel]):
                if key == "<key>":
                    self.assertNotIn(value, ("class", "rule", "confidence", "signals", "models"), rel)

    # ---- pages

    def test_pages_id_lists(self):
        for rel in ("identification.reads.json", "native.reads.json"):
            reads = self.data[rel]
            self.assertEqual(list(reads), ["fixture", "captured_at", "pages"])
            for number, page in enumerate(reads["pages"], 1):
                self.assertEqual(page["page"], number)
                for key in ("requested_ids", "returned_ids", "missing_ids"):
                    self.assertIsInstance(page[key], list, rel)
                self.assertEqual(page["missing_ids"],
                                 [i for i in page["requested_ids"] if i not in page["returned_ids"]], rel)
                if page["kind"] in ("boards_sweep", "boards_ids"):
                    self.assertEqual(page["returned_ids"], [b["id"] for b in page["response"]["data"]["boards"]])
                    self.assertEqual(page["response"]["data"]["version"],
                                     {"kind": "release_candidate", "value": "2026-10"})
                if page["kind"] == "boards_sweep":
                    self.assertEqual(page["requested_ids"], [])
        native = self.data["native.reads.json"]["pages"]
        self.assertTrue([p for p in native if p["kind"] == "boards_ids" and p["missing_ids"]],
                        "no page on which boards(ids:) drops an id")

    def test_sweeps_end_on_an_empty_page(self):
        for name in ("identification", "native"):
            last = {}
            for page in self.data[name + ".reads.json"]["pages"]:
                if page["kind"] == "boards_sweep":
                    ws = page["request"]["variables"]["ws"][0]
                    last[ws] = page["response"]["data"]["boards"]
            self.assertTrue(last)
            for ws, boards in last.items():
                self.assertEqual(boards, [], name + ": sweep of " + ws + " ends on a non-empty page")
            self.assertIs(self.data[name + ".expected.json"]["sweep_complete"], True)

    # ---- the schema field list

    def test_every_response_path_is_listed(self):
        fields = self.data["schema-fields.json"]
        self.assertEqual(fields["schema_version"], "2026-10")
        self.assertEqual(fields["sdl_bytes"], 621124)
        aliases = fields["aliases"]
        stops = list(fields["json_scalars"]) + list(fields["connector_shapes"])
        listed = set(fields["paths"])

        def covered(path):
            return path in listed or any(path == k or path.startswith(k + ".") for k in fields["connector_shapes"])

        found = set()
        for rel in ("identification.reads.json", "native.reads.json"):
            for page in self.data[rel]["pages"]:
                response_paths(page["response"]["data"], "", aliases, stops, found)
        inventory = self.data["reconcile/live-inventory.json"]
        for key, value in inventory.items():
            if key in ("fixture", "schema", "strand", "read_at", "ring"):
                continue
            if key == "dashboards":
                found.add("live-inventory.dashboards")
                response_paths(value["returned"], "live-inventory.dashboards.returned", {}, stops, found)
            else:
                response_paths(value, "live-inventory." + key, {}, stops, found)
        for rel in ("compare/before.read.json", "compare/after.read.json"):
            for key, value in self.data[rel].items():
                if key in ("fixture", "read_at", "ring"):
                    continue
                response_paths(value, "snapshot." + key, {}, stops, found)
        missing = sorted(p for p in found if not covered(p))
        self.assertEqual(missing, [], "response paths not in schema-fields.json")
        for path, target in fields["paths"].items():
            self.assertRegex(target, r"^[A-Z][A-Za-z]*(\.[a-z_]+)+$", path)

    # ---- ids

    def test_ids_are_strings_in_their_ranges(self):
        catalogue = self.catalogue
        for ids in catalogue:
            for lo, hi in RANGES.values():
                self.assertFalse(lo <= int(ids) <= hi, "catalogue id %s inside a range" % ids)

        def in_range(value, kind):
            number = int(value)
            if kind is None:
                return any(lo <= number <= hi for lo, hi in RANGES.values())
            lo, hi = RANGES[kind]
            return lo <= number <= hi

        for rel, data in self.data.items():
            if rel == "schema-fields.json":
                continue
            pages = data.get("pages") if isinstance(data, dict) else None
            items = []
            if pages:
                for page in pages:
                    items.extend((page["kind"], p, k, v) for p, k, v in walk_values(page))
                items.extend((None, p, k, v) for p, k, v in walk_values({x: y for x, y in data.items() if x != "pages"}))
            else:
                items.extend((None, p, k, v) for p, k, v in walk_values(data))
            for kind, path, key, value in items:
                name = path[-1] if path else None
                idish = name in ("id", "ids") or (isinstance(name, str) and (name.endswith("_id") or name.endswith("_ids")
                                                                         or name in KEY_TYPES))
                if key != "<key>" and idish:
                    self.assertFalse(isinstance(value, (int, float)) and not isinstance(value, bool),
                                     "%s: number under %s" % (rel, "/".join(map(str, path))))
                if not isinstance(value, str):
                    continue
                if key in ("intent_digest", "session_label"):
                    continue
                for run in re.findall(r"\d{8,}", re.sub(r"[a-z0-9.]+:[0-9a-f]{8}\b", "", value)):
                    self.assertTrue(run in catalogue or in_range(run, None), "%s: id %s outside every range" % (rel, run))
                if not re.fullmatch(r"\d{8,}", value) or value in catalogue:
                    continue
                if key == "<key>":
                    expected = "board" if path and path[-1] in ("boards", "native_board_index") else None
                else:
                    expected = id_type(path, kind)
                self.assertTrue(in_range(value, expected),
                                "%s: %s under %s is not a %s id" % (rel, value, "/".join(map(str, path)), expected))
        appendix = raw("compare/appendix.md").decode("utf-8")
        for run in re.findall(r"\d{8,}", appendix):
            self.assertTrue(in_range(run, "board"), run)

    # ---- names

    def test_names_use_the_stems_and_no_leak_term(self):
        allowed = stems()
        patterns = leak_patterns()
        self.assertGreater(len(allowed), 50)
        seen = 0
        for rel, data in self.data.items():
            for path, key, value in walk_values(data):
                if key in NAME_KEYS and isinstance(value, str) and path and path[0] != "fixture":
                    seen += 1
                    for word in re.findall(r"[A-Za-z]+", value):
                        self.assertIn(word.lower(), allowed, "%s: %r" % (rel, value))
                    for pattern in patterns:
                        self.assertIsNone(pattern.search(value), "%s: %r matches %s" % (rel, value, pattern.pattern))
        self.assertGreater(seen, 100)

    # ---- the classification answer keys

    def boards_of(self, name):
        boards = {}
        for page in self.data[name + ".reads.json"]["pages"]:
            if page["kind"] in ("boards_sweep", "boards_ids"):
                for board in page["response"]["data"]["boards"]:
                    self.assertNotIn(board["id"], boards, "board read twice")
                    boards[board["id"]] = board
        return boards

    def check_key(self, name):
        key = self.data[name + ".expected.json"]
        boards = self.boards_of(name)
        self.assertEqual(set(key["boards"]), set(boards), name + ": one entry per board")
        self.assertEqual(key["board_count"], len(boards))
        totals = {}
        limit_boards = []
        for bid, entry in key["boards"].items():
            self.assertEqual(list(entry), ENTRY_KEYS, bid)
            self.assertTrue(entry["models"], bid)
            self.assertIn(entry["rule"], BOARD_RULES, bid)
            self.assertIn(entry["confidence"], ("high", "medium", "low"), bid)
            self.assertEqual(list(entry["attributes"])[:6], ATTR_KEYS, bid)
            self.assertEqual(entry["attributes"]["state"], boards[bid]["state"], bid)
            self.assertEqual(entry["attributes"]["items_count"], boards[bid]["items_count"], bid)
            self.assertEqual(list(entry["lineage"]), LINEAGE_KEYS, bid)
            self.assertEqual(entry["lineage"]["resolved"], entry["lineage"]["result"] == "RESOLVED_TEMPLATE", bid)
            first = entry["lineage"]["chain"][0] if entry["lineage"]["chain"] else None
            self.assertEqual(first, boards[bid]["created_from_board_id"], bid)
            self.assertEqual(len(entry["signals"]), len(set(entry["signals"])), bid)
            if boards[bid]["object_type_unique_key"]:
                self.assertNotEqual(entry["class"], "normal_classic_board", bid)
            if entry["rule"].startswith("N"):
                self.assertNotEqual(entry["class"], "normal_classic_board", bid)
            if entry["rule"] in ("R7", "R9", "N7", "N10"):
                self.assertIs(entry["review"], True, bid)
            for code in entry["limits"]:
                self.assertIn(code, ("L1", "L2", "L3"), bid)
            if entry["limits"]:
                limit_boards.append(bid)
            else:
                totals[entry["class"]] = totals.get(entry["class"], 0) + 1
        self.assertEqual(key["totals"], totals, name + ": totals")
        self.assertEqual(sorted(l["board_id"] for l in key["limits"]), sorted(limit_boards))
        for limit in key["limits"]:
            self.assertEqual(list(limit), ["board_id", "code", "codes", "class", "reason", "models"])
            self.assertEqual(limit["codes"], sorted(key["boards"][limit["board_id"]]["limits"]))
            self.assertIn(limit["code"], limit["codes"])
            self.assertEqual(limit["class"], key["boards"][limit["board_id"]]["class"])
            self.assertTrue(limit["reason"] and limit["models"])
        self.assertEqual(key["board_count"], sum(key["totals"].values()) + len(key["limits"]))
        for project in key["projects"]:
            self.assertEqual(list(project), ["portfolio_id", "tasks_board_id", "result", "rules", "note", "models"])
            self.assertTrue(set(project["rules"]) <= PROJECT_RULES)
            self.assertTrue(project["models"])
            self.assertEqual(key["boards"][project["tasks_board_id"]]["rule"], "R5")
        for bid in key["unreadable_ids"]:
            self.assertNotIn(bid, boards)
        missing = set()
        for page in self.data[name + ".reads.json"]["pages"]:
            if page["kind"] == "boards_ids":
                missing.update(page["missing_ids"])
        self.assertEqual(set(key["unreadable_ids"]), missing)
        return key, boards

    def test_identification_key(self):
        key, boards = self.check_key("identification")
        rules = {e["rule"] for e in key["boards"].values()}
        self.assertTrue({"R%d" % n for n in range(1, 12)} <= rules, sorted(rules))
        states = {e["attributes"]["state"] for e in key["boards"].values()}
        self.assertEqual(states, {"active", "archived", "deleted"})
        project_rules = set()
        for project in key["projects"]:
            project_rules.update(project["rules"])
        self.assertEqual(project_rules, PROJECT_RULES)
        results = {p["result"] for p in key["projects"]}
        self.assertTrue({"connected", "partial link - review", "unconnected"} <= results)
        self.assertEqual([p["rules"] for p in key["projects"] if p["result"] == "partial link - review"],
                         [["C1"], ["C2"]])
        for bid, entry in key["boards"].items():
            if boards[bid]["object_type_unique_key"]:
                self.assertNotEqual(entry["class"], "normal_classic_board", bid)
        r5 = {boards[b]["object_type_unique_key"] for b, e in key["boards"].items()
              if e["class"] == "project_tasks_board"}
        self.assertTrue({"work-management::project", "work-management::portfolio-project"} <= r5)
        self.assertEqual({e["class"] for e in key["boards"].values() if e["rule"] == "R5"},
                         {"project_tasks_board", "converted_project_board", "project_board_origin_unknown"})

    def test_native_key(self):
        key, boards = self.check_key("native")
        by_case = {e["case"]: (bid, e) for bid, e in key["boards"].items()}
        self.assertEqual(len(by_case), len(key["boards"]), "case ids repeat")
        for item, cases in NATIVE_CASES.items():
            for case in cases:
                self.assertIn(case, by_case, item)
        for case, rule in CASE_RULES.items():
            self.assertEqual(by_case[case][1]["rule"], rule, case)
        hops = {c: by_case[c][1]["lineage"] for c in NATIVE_CASES["lineage at 0, 1 and 2 hops and unresolved"]}
        self.assertEqual([h["hops"] for h in list(hops.values())[:3]], [0, 1, 2])
        self.assertEqual(hops["crm-v2-sales-targets-chain-broken"]["result"], "UNRESOLVED")
        self.assertEqual(by_case["planted-ids"][1]["limits"], ["L1"])
        self.assertEqual(by_case["stripped-native"][1]["limits"], ["L2"])
        self.assertIn("L3", by_case["default-shaped-satellite"][1]["limits"])
        self.assertEqual(by_case["planted-ids"][1]["class"],
                         by_case["crm-v2-leads"][1]["class"])
        self.assertIs(by_case["service-a-tickets-sla"][1]["attributes"]["sla_mark"], True)
        self.assertEqual(by_case["service-c-tickets-chain-broken"][1]["attributes"]["install_kind"],
                         "descendant_fingerprint")
        self.assertEqual(by_case["native-moved-to-core"][1]["attributes"]["fingerprint"], "crm/accounts")
        self.assertEqual(by_case["service-b-start-here-doc"][1]["class"], "doc_container")
        index = key["native_board_index"]
        for bid, entry in key["boards"].items():
            self.assertEqual(bid in index, entry["class"].startswith("native_"), bid)
        self.assertEqual(sorted(key["portal_object_ids"]), ["active", "archived"])
        portals = {bid for bid, e in key["boards"].items() if e["class"] == "native_service_portal"}
        self.assertEqual(portals, set(key["portal_object_ids"]["active"] + key["portal_object_ids"]["archived"]))
        self.assertEqual([p["result"] for p in key["projects"]], ["incomplete read - review"])
        cursors = [p for p in self.data["native.reads.json"]["pages"] if p["kind"] == "portfolio_items"]
        self.assertIsNotNone(cursors[0]["response"]["data"]["boards"][0]["items_page"]["cursor"])
        self.assertEqual([r["report"] for r in key["reports"]], ["product boards not installed here"])
        states = {e["attributes"]["state"] for e in key["boards"].values()}
        self.assertEqual(states, {"active", "archived", "deleted"})

    # ---- compare

    def test_compare_cases(self):
        key = self.data["compare/expected.json"]
        before = self.data["compare/before.read.json"]
        after = self.data["compare/after.read.json"]
        self.assertTrue(set(COMPARE_FLAG_CASES) <= {f["case"] for f in key["flags"]})
        self.assertEqual([c["case"] for c in key["changed_outside"]], ["protected-row-moved-before"])
        for case, verdict in COMPARE_DOC_CASES.items():
            self.assertIn(case, {d["case"]: d["verdict"] for d in key["documents"]})
            self.assertEqual({d["case"]: d["verdict"] for d in key["documents"]}[case], verdict)
        self.assertEqual([d["number"] for d in key["documents"]], list(range(1, len(key["documents"]) + 1)))
        self.assertEqual(key["exit_code"], 1)

        def part(snapshot, kind, oid):
            table = {"board": "inventory", "agent": "agents", "workflow": "workflows"}[kind]
            found = [x for x in snapshot[table] if x["id"] == oid]
            if kind == "board" and not found:
                return None
            return found[0]

        for flag in key["flags"]:
            self.assertEqual(flag["expected"], "unchanged during the audit window")
            self.assertTrue(flag["problem"].endswith(" to " + (flag["after"] if isinstance(flag["after"], str)
                                                                else json.dumps(flag["after"], separators=(",", ":")))))
            kind, rest = flag["field"].split(":", 1)
            oid, field = rest.split(".", 1)
            if field == "columns_digest":
                b = [x for x in before["boards"] if x["id"] == oid][0]
                a = [x for x in after["boards"] if x["id"] == oid][0]
                self.assertEqual(flag["before"], digest("columns", sorted(b["columns"], key=lambda c: c["id"])))
                self.assertEqual(flag["after"], digest("columns", sorted(a["columns"], key=lambda c: c["id"])))
            elif field == "plan_digest":
                self.assertEqual(flag["before"], digest("plan", part(before, kind, oid)["plan"]))
                self.assertEqual(flag["after"], digest("plan", part(after, kind, oid)["plan"]))
            elif field in ("owners", "subscribers"):
                self.assertEqual(flag["before"], [x for x in before["boards"] if x["id"] == oid][0][field])
                self.assertEqual(flag["after"], [x for x in after["boards"] if x["id"] == oid][0][field])
            else:
                self.assertEqual(flag["before"], part(before, kind, oid)[field])
                self.assertEqual(flag["after"], part(after, kind, oid)[field])
        state_agent = [f for f in key["flags"] if f["case"] == "agent-state-moved"][0]["field"].split(":")[1].split(".")[0]
        self.assertEqual(part(before, "agent", state_agent)["version_id"], part(after, "agent", state_agent)["version_id"])
        flagged = {f["field"].split(".")[0] for f in key["flags"]}
        tables = {"board": ["inventory", "boards"], "automation": ["automations"], "doc": ["docs"],
                  "dashboard": ["dashboards"], "vibe_app": ["vibe_apps"], "form": ["forms"]}
        for control in key["not_flagged"]:
            self.assertNotIn(control["object"], flagged)
            kind, oid = control["object"].split(":")
            for table in tables[kind]:
                ident = "view_id" if kind == "form" else "id"
                b = [x for x in before[table] if x[ident] == oid]
                a = [x for x in after[table] if x[ident] == oid]
                if control["case"] == "control-updated-at-only" and table == "inventory":
                    self.assertNotEqual(b, a)
                    b[0] = dict(b[0], updated_at=None)
                    a[0] = dict(a[0], updated_at=None)
                if control["case"] == "control-dropped-from-scope":
                    self.assertNotIn(oid, key["scope"]["boards"])
                    self.assertIn(oid, key["scope"]["dropped"])
                    continue
                self.assertEqual(b, a, control["case"])
        ledger = self.data["compare/ledger-state.json"]
        protected = sorted(k for k, v in ledger["live_objects"].items()
                           if v["constraint"] in ("do-not-change", "change-with-own-yes"))
        self.assertEqual(key["scope"]["live_rows"], protected)
        row = key["changed_outside"][0]
        live = ledger["live_objects"][row["key"]]
        self.assertEqual(row["recorded_digest"], live["digest"])
        inv = [x for x in before["inventory"] if x["id"] == row["monday_id"]][0]
        prefix = row["key"].split(":", 1)[1].lower()
        self.assertEqual(row["digest_at_snapshot"], digest(prefix, {f: inv[f] for f in BOARD_FIELDS}))
        self.assertNotEqual(row["recorded_digest"], row["digest_at_snapshot"])
        inv_after = [x for x in after["inventory"] if x["id"] == row["monday_id"]][0]
        self.assertEqual(inv, inv_after, "the protected row must not move during the window")

    def test_appendix_documents(self):
        text = raw("compare/appendix.md").decode("utf-8")
        section = text.split("## Documents appendix", 1)[1].split("\n## ", 1)[0]
        count = 0
        for info, body in re.findall(r"```(\w*)\n(.*?)```", section, re.S):
            if info in ("graphql", "gql"):
                count += 1
            elif info == "json":
                count += len(re.findall(r'"query"\s*:', body))
            else:
                self.fail("a fence the scan cannot read: " + info)
        self.assertEqual(count, len(self.data["compare/expected.json"]["documents"]))
        self.assertIn("mutation", text.split("## Documents appendix", 1)[1].split("\n## ", 1)[1])

    # ---- reconcile

    def test_reconcile_cases(self):
        key = self.data["reconcile/expected.json"]
        inventory = self.data["reconcile/live-inventory.json"]
        ledger = self.data["reconcile/ledger-state.json"]
        self.assertEqual(inventory["schema"], "live-inventory/1")
        self.assertEqual(inventory["strand"], ledger["build"]["strand"])
        dash = inventory["dashboards"]
        returned = [d["id"] for d in dash["returned"]]
        self.assertEqual(dash["missing_ids"], [i for i in dash["requested_ids"] if i not in returned])
        full = key["full"]
        self.assertEqual(list(full["classes"]), CLASSES)
        for cls in CLASSES:
            self.assertGreaterEqual(full["classes"][cls], 1, cls)
            self.assertEqual(full["classes"][cls], len([e for e in full["elements"] if e["class"] == cls]))
        order = ["automation", "agent", "vibe_app", "workflow"]
        ranks = [order.index(e["kind"]) if e["kind"] in order else len(order) for e in full["elements"]]
        self.assertEqual(ranks, sorted(ranks), "automations first, then agents, Vibe apps, workflows")
        kinds_seen = []
        for element in full["elements"]:
            self.assertEqual(list(element), ["key", "kind", "class", "live_ids", "confirm", "needs_read",
                                             "predates_attempt", "note"])
            if element["kind"] in kinds_seen and kinds_seen[-1] != element["kind"]:
                self.fail("kind split: " + element["kind"])
            kinds_seen.append(element["kind"])
        for kind in set(kinds_seen):
            rows = [e for e in full["elements"] if e["kind"] == kind]
            extras = [i for i, e in enumerate(rows) if e["key"] is None]
            self.assertEqual(extras, list(range(len(rows) - len(extras), len(rows))), kind)
        objects = ledger["build"]["objects"]
        for element in full["elements"]:
            if element["key"] is not None:
                self.assertIn(element["key"], objects)
        automation_adopts = [e for e in full["elements"] if e["kind"] == "automation" and e["class"] == "adopt"]
        self.assertTrue(automation_adopts and all(e["confirm"] for e in automation_adopts))
        self.assertTrue([e for e in full["elements"] if e["class"] == "unrecorded-extra" and e["predates_attempt"]])
        for kind in ("agent", "vibe_app", "workflow"):
            self.assertTrue([e for e in full["elements"] if e["kind"] == kind], kind)
        once = full["unchanged"] + full["not_started"] + full["not_reconciled"] + \
            [n["key"] for n in full["not_in_inventory"]] + [e["key"] for e in full["elements"] if e["key"]]
        self.assertEqual(sorted(once), sorted(objects), "every row in exactly one place")
        only = key["classify_only"]
        self.assertEqual(only["classes"], full["classes"])
        self.assertEqual(only["run_id"], ledger["lock"]["run_id"])
        self.assertEqual(only["holder"], ledger["lock"]["strand"])
        self.assertEqual(only["asked_by"], ledger["sibling"]["strand"])
        self.assertEqual([(f["key"], f["class"], f["live_ids"]) for f in only["findings"]],
                         [(e["key"], e["class"], e["live_ids"]) for e in full["elements"]])
        runs = [r for r in ledger["build"]["runs"] if r["id"] == only["run_id"]]
        self.assertEqual(len(runs), 1)
        # the live identity digest equals the verified one exactly for the unchanged rows
        live = {}
        for b in inventory["boards"]:
            live[b["id"]] = ("board", {f: b[f] for f in BOARD_FIELDS})
        for w in inventory["workspaces"]:
            live[w["id"]] = ("workspace", {"name": w["name"], "kind": w["kind"]})
        for f in inventory["folders"]:
            live[f["id"]] = ("folder", {"name": f["name"], "workspace_id": f["workspace_id"]})
        for d in inventory["docs"]:
            live[d["id"]] = ("doc", {"name": d["name"], "workspace_id": d["workspace_id"]})
        for a in inventory["automations"]:
            live[a["id"]] = ("automation", {"active": a["active"], "updated_at": a["updated_at"]})
        for d in inventory["dashboards"]["returned"]:
            live[d["id"]] = ("dashboard", {"name": d["name"], "workspace_id": d["workspace_id"], "kind": d["kind"]})
        for a in inventory["agents"]:
            live[a["id"]] = ("agent", {"state": a["state"], "version_id": a["version_id"]})
        changed = {e["key"] for e in full["elements"] if e["class"] == "changed-since-verified"}
        for k, row in objects.items():
            if row["status"] != "verified" or row["id"] not in live:
                continue
            same = digest(k.lower(), live[row["id"]][1]) == row["verify"]["digest"]
            if k in full["unchanged"]:
                self.assertTrue(same, k)
            if k in changed:
                self.assertFalse(same, k)

    # ---- digests

    def test_digests_recompute(self):
        for rel in ("compare/ledger-state.json", "reconcile/ledger-state.json"):
            data = self.data[rel]
            entries = data["digest_fields"]
            self.assertTrue(entries)
            seen = set()
            for entry in entries:
                self.assertEqual(get_at(data, entry["at"]), digest(entry["prefix"], entry["fields"]),
                                 "%s: %s" % (rel, entry["at"]))
                seen.add(tuple(entry["at"]))
            for path, key, value in walk_values({k: v for k, v in data.items() if k != "digest_fields"}):
                if key in ("digest", "intent_digest") and value is not None:
                    self.assertIn(tuple(path), seen, "%s: digest with no fields: %s" % (rel, path))
        ledger = self.data["compare/ledger-state.json"]
        before = {x["id"]: x for x in self.data["compare/before.read.json"]["inventory"]}
        for entry in ledger["digest_fields"]:
            if entry["at"][0] == "objects" and ledger["objects"][entry["at"][1]]["type"] == "board":
                bid = ledger["objects"][entry["at"][1]]["id"]
                self.assertEqual(entry["fields"], {f: before[bid][f] for f in BOARD_FIELDS})


if __name__ == "__main__":
    unittest.main()
