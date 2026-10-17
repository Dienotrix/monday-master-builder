"""Unit tests for plugins/monday-master-builder/scripts/ledger.py, part 2: the read side (WP3 step 6).

Contract clauses of rebuild-workspace/build/wp3/CONTRACT.md by id in the test names. The frame is test_ledger.py's
Base: a copy of tests/unit/fixtures/home/ in a temporary folder whose name holds a space, MMB_HOME pointed at it,
HOME and USERPROFILE at an empty canary, mmb_common's clock pinned, and ledger.py run in process from a temporary
plugin root. The reads are the synthetic reads of tests/fixtures/snapshots/ (amendment A29: met against synthetic
reads, confirmed at capture, A11-1); each test copies the files it needs into the record copy under .work/, and the
record variants the reads assume (the client's workspaces, a strand ledger, a held lease) are built in setup from
WP2's fixture, through the mmb_common primitives for the lease (K37). Nothing is written under tests/fixtures/.
"""
import ast, copy, json, os, re, shutil, socket, unittest  # noqa: E401
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from test_ledger import B1J, CLOCK, LABEL, S1, Base, pairs
import mmb_common as mc

HERE = Path(__file__).resolve().parent
SNAPS = HERE.parent / "fixtures" / "snapshots"
SCRIPTS = HERE.parent.parent / "plugins" / "monday-master-builder" / "scripts"
NO = SCRIPTS.parent / "shared" / "native-objects.md"
WORK = ".work/strands/001/"
GRADED = ("class", "rule", "confidence", "attributes", "lineage", "review", "limits")
ID_CLIENTS = ["90100000101", "90100000102"]
NATIVE_CLIENTS = ["90100000201", "90100000203", "90100000207"]
RUN = "run-2026-10-16-1"
ELEMENT = ("key", "kind", "class", "live_ids", "confirm", "needs_read", "predates_attempt")


def load(rel):
    return json.loads((SNAPS / rel).read_text(encoding="utf-8"))


def strip(rows, drop=("models", "case")):
    return [{k: v for k, v in row.items() if k not in drop} for row in rows]


def board(bid, ws, kind, columns=(), name="Ambrel Notes", term="item", cfb=None, key=None, btype="board",
          links=(), views=(), state="active", hierarchy="classic"):
    """A board as the NO 2.6 query returns it, for the synthetic cases a test builds itself."""
    return {"id": bid, "name": name, "type": btype, "state": state, "hierarchy_type": hierarchy,
            "object_type_unique_key": key, "board_kind": "public", "item_terminology": term,
            "created_from_board_id": cfb, "items_count": 1, "workspace_id": ws, "board_folder_id": None,
            "inferred_metadata": {"item_type": None}, "manual_metadata": {"board_md": None},
            "workspace": {"id": ws, "account_product": {"kind": kind}},
            "columns": [{"id": "name", "type": "name"}] + [{"id": c, "type": "text"} for c in columns],
            "links": list(links), "views": [{"id": "90400099901", "type": "TableBoardView", "name": "Main table",
                                             "source_view_id": v} for v in views]}


def sweep(boards, ws="90100000901", extra_pages=()):
    """A reads file of one swept workspace ending on its empty page, plus any pages given."""
    page = {"page": 1, "kind": "boards_sweep", "request": {"document": "NO 2.6", "variables": {"ws": [ws], "p": 1}},
            "response": {"data": {"version": {"kind": "release_candidate", "value": "2026-10"}, "boards": boards}},
            "requested_ids": [], "returned_ids": [b["id"] for b in boards], "missing_ids": []}
    last = copy.deepcopy(page)
    last.update(page=2, returned_ids=[])
    last["request"]["variables"]["p"] = 2
    last["response"]["data"]["boards"] = []
    return {"captured_at": "2026-10-16T00:00:00Z", "pages": [page, last] + list(extra_pages)}


class ReadBase(Base):

    def place(self, name, data):
        """A file the session hands, written inside the record (W91)."""
        path = self.root / WORK / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return WORK + name

    def guard(self, **fields):
        self.edit_json("account.json", lambda d: d["guard_index"].update(fields))

    def classify(self, reads, clients=None):
        if clients is not None:
            self.guard(client_workspace_ids=clients, build_targets_by_strand={})
        return self.ok("classify", "--reads", self.place("reads.json", reads))

    def grade(self, data, key):
        """K337, K365: every board against its answer key; zero differences, the totals and board count reproduced."""
        differences = []
        for bid, want in key["boards"].items():
            got = data["boards"].get(bid)
            if got is None:
                differences.append((bid, "missing"))
                continue
            differences += [(bid, want["case"], f, got[f], want[f]) for f in GRADED if got[f] != want[f]]
            if set(got["signals"]) != set(want["signals"]):
                differences.append((bid, want["case"], "signals", sorted(got["signals"]), sorted(want["signals"])))
        self.assertEqual(differences, [])
        self.assertEqual(set(data["boards"]), set(key["boards"]))
        self.assertEqual((data["totals"], data["board_count"]), (key["totals"], key["board_count"]))
        self.assertEqual(sum(key["totals"].values()) + len(key["limits"]), key["board_count"])  # K338, K366
        self.assertEqual(data["limits"], strip(key["limits"]))
        self.assertEqual(data["projects"], strip(key["projects"]))
        self.assertEqual((data["reports"], data["sweep_complete"], data["unreadable_ids"]),
                         (key["reports"], key["sweep_complete"], key["unreadable_ids"]))


# classify on the identification fixture (R0 to R11, C1 to C4).

class IdentificationTest(ReadBase):

    def setUp(self):
        super().setUp()
        self.key = load("identification.expected.json")
        self.data = self.classify(load("identification.reads.json"), ID_CLIENTS)

    def test_K312_K313_K314_K315_to_K328_K337_K338_K440_every_board_against_the_key(self):
        self.grade(self.data, self.key)
        self.assertEqual(self.data["next_ids"], [])
        states = {b["attributes"]["state"] for b in self.data["boards"].values()}
        self.assertEqual(states, {"active", "archived", "deleted"})  # K313, K314: every state, state an attribute
        deleted = self.data["boards"]["90300000125"]
        self.assertEqual((deleted["class"], deleted["attributes"]["state"]), ("normal_classic_board", "deleted"))

    def test_K329_K330_K331_keyed_boards_projects_and_the_multi_level_board(self):
        reads = load("identification.reads.json")
        keyed = {b["id"] for p in reads["pages"] for b in p["response"]["data"].get("boards") or []
                 if isinstance(b, dict) and b.get("object_type_unique_key")}
        self.assertTrue(keyed)
        for bid in keyed:
            self.assertNotEqual(self.data["boards"][bid]["class"], "normal_classic_board", bid)
        classes = {bid: r["class"] for bid, r in self.data["boards"].items()}
        self.assertEqual((classes["90300000111"], classes["90300000113"], classes["90300000114"]),
                         ("project_tasks_board", "converted_project_board", "project_board_origin_unknown"))
        self.assertEqual(classes["90300000112"], classes["90300000111"])  # K322: the transient key, the same role
        self.assertEqual(classes["90300000122"], "multi_level_board_not_project")

    def test_K332_K333_K334_K335_K336_C1_to_C4_from_both_halves(self):
        projects = {p["tasks_board_id"]: p for p in self.data["projects"]}
        self.assertEqual((projects["90300000111"]["result"], projects["90300000111"]["rules"]),
                         ("connected", ["C1", "C2", "C3"]))
        self.assertEqual([projects[b]["result"] for b in ("90300000112", "90300000113")], ["partial link - review"] * 2)
        self.assertEqual((projects["90300000115"]["result"], projects["90300000115"]["rules"],
                          projects["90300000115"]["note"]), ("unconnected", ["C4"], "overview 90300000116"))
        reads = load("identification.reads.json")  # K336: a cursor on the items page and no project is unconnected
        reads["pages"][-1]["response"]["data"]["boards"][0]["items_page"]["cursor"] = "c-000009"
        data = self.classify(reads)
        results = {p["tasks_board_id"]: p["result"] for p in data["projects"]}
        self.assertEqual((results["90300000114"], results["90300000115"]), ("incomplete read - review",) * 2)
        self.assertEqual(results["90300000111"], "connected")

    def test_K313_R0_a_sweep_cut_short_is_incomplete(self):
        reads = load("identification.reads.json")
        reads["pages"] = [p for p in reads["pages"] if not (p["kind"] == "boards_sweep" and p["request"]["variables"]
                                                             ["ws"] == ["90100000102"] and p["request"]["variables"]["p"] == 2)]
        data = self.classify(reads)
        self.assertEqual((data["sweep_complete"], data["unfinished_sweeps"]), (False, ["90100000102"]))
        refusals = self.refused("native-map", "--reads", WORK + "reads.json", "--coverage", "a cut sweep")
        self.assertIn((WORK + "reads.json", "pages"), pairs(refusals))

    def test_K317_W79_without_the_workflow_objects_set_a_custom_object_is_low(self):
        reads = load("identification.reads.json")
        reads["pages"] = [p for p in reads["pages"] if p["kind"] != "workflow_objects"]
        data = self.classify(reads)
        for bid in ("90300000104", "90300000105", "90300000106"):
            row = data["boards"][bid]
            self.assertEqual((row["class"], row["rule"], row["confidence"]), ("custom_object_other", "R3", "low"))
            self.assertIn("workflow_objects:unread", row["signals"])
        self.assertTrue(any("workflow objects set not read" in note for note in data["notes"]))

    def test_K412_classify_writes_nothing(self):
        before = self.tree()
        self.ok("classify", "--reads", WORK + "reads.json")
        self.assertEqual(self.tree(), before)


# classify on the native fixture (N0 to N12), lineage, reserved ids, look-alikes and the known limits.

class NativeTest(ReadBase):

    def setUp(self):
        super().setUp()
        self.key = load("native.expected.json")
        self.reads = load("native.reads.json")
        self.data = self.classify(self.reads, NATIVE_CLIENTS)

    def cls(self, bid, data=None):
        return (data or self.data)["boards"][bid]["class"]

    def test_K340_to_K366_K368_K441_every_board_against_the_key(self):
        self.grade(self.data, self.key)
        for bid, row in self.data["boards"].items():  # K368: each result carries its rule, signals and confidence
            self.assertTrue(row["rule"] and row["signals"] and row["confidence"] in ("high", "medium", "low"), bid)
            if row["rule"].startswith("N") and row["rule"] != "N9":  # K354: a native rule never ends as R11's class
                self.assertNotEqual(row["class"], "normal_classic_board")

    def test_K340_K351_K355_a_native_moved_into_core_is_reviewed_and_a_keyed_board_stops_first(self):
        moved, keyed = self.data["boards"]["90300000260"], self.data["boards"]["90300000261"]
        self.assertEqual((moved["rule"], moved["review"], moved["attributes"]["fingerprint"]),
                         ("N10", True, "crm/accounts"))
        self.assertEqual((keyed["rule"], keyed["review"]), ("R7", True))
        self.assertIn("reserved:crm/leads", keyed["signals"])  # the signals are facts; the key decides first

    def test_K341_K342_K358_the_portal_active_and_archived(self):
        rules = {bid: self.data["boards"][bid]["rule"] for bid in ("90300000229", "90300000230", "90300000231")}
        self.assertEqual(rules, {"90300000229": "N1a", "90300000230": "N1a", "90300000231": "N1b"})
        self.assertEqual(self.cls("90300000232"), "workflow_object")  # N1b does not swallow a workflow object

    def test_K343_K371_to_K375_K382_lineage_walked_hop_by_hop(self):
        hops = {bid: self.data["boards"][bid]["lineage"] for bid in ("90300000201", "90300000211", "90300000222")}
        self.assertEqual([hops[b]["hops"] for b in sorted(hops)], [0, 1, 2])
        self.assertEqual(hops["90300000222"]["chain"], ["90300000221", "90300000220", "5727048235"])
        self.assertEqual([self.data["boards"][b]["attributes"]["install_kind"] for b in sorted(hops)],
                         ["direct_install", "descendant_copy(1)", "descendant_copy(2)"])
        reads = copy.deepcopy(self.reads)  # the 2-hop board resolves only once the second hop is read
        reads["pages"] = [p for p in reads["pages"] if p["requested_ids"] != ["90300000220"]]
        data = self.classify(reads)
        self.assertEqual((self.cls("90300000222", data), self.cls("90300000221", data)), ("pending", "pending"))
        self.assertEqual(data["next_ids"], ["90300000220"])
        self.assertEqual(data["next_query"], self.led.DETECT_QUERY)
        self.assertNotIn("pending", data["totals"])
        refusals = self.refused("native-map", "--reads", WORK + "reads.json", "--coverage", "a partial read")
        self.assertIn((WORK + "reads.json", "next_ids"), pairs(refusals))

    def test_K376_K377_K379_K380_K381_K420_unreadable_intermediates_and_the_dropped_ids(self):
        chain_broken = self.data["boards"]["90300000237"]
        self.assertEqual((chain_broken["lineage"]["result"], chain_broken["class"]), ("UNRESOLVED", "native_service_tickets"))
        self.assertEqual(self.data["unreadable_ids"], ["90300000901", "90300000902", "90300000903"])
        self.assertEqual(self.data["boards"]["90300000207"]["lineage"]["result"], "NO_LINEAGE")
        deleted = self.data["boards"]["90300000262"]
        self.assertEqual((deleted["class"], deleted["attributes"]["state"]), ("native_crm_contacts", "deleted"))
        reads = copy.deepcopy(self.reads)  # the diff is made on the page, whatever its missing_ids says
        page = next(p for p in reads["pages"] if p["kind"] == "boards_ids" and len(p["requested_ids"]) == 4)
        page["missing_ids"] = []
        data = self.classify(reads)
        self.assertEqual(data["unreadable_ids"], self.data["unreadable_ids"])
        self.assertTrue(data["notes"])

    def test_K378_W86_a_six_hop_chain_stops_at_the_fifth_and_a_cycle_ends_unresolved(self):
        ids = ["9030000080%d" % n for n in range(1, 9)]
        boards = [board(ids[n], "90100000901", "core", cfb=ids[n + 1]) for n in range(6)]
        boards.append(board(ids[6], "90100000901", "core", cfb="5678953932"))
        loop = [board("90300000811", "90100000901", "core", cfb="90300000812"),
                board("90300000812", "90100000901", "core", cfb="90300000811")]
        data = self.classify(sweep(boards + loop))
        long = data["boards"][ids[0]]["lineage"]
        self.assertEqual((long["result"], long["hops"], long["note"], len(long["chain"])),
                         ("UNRESOLVED", 5, "longer than 5 hops", 6))
        self.assertEqual(data["boards"][ids[2]]["lineage"]["result"], "RESOLVED_TEMPLATE")  # five hops: within the cap
        self.assertEqual(data["boards"][ids[2]]["lineage"]["hops"], 4)
        self.assertEqual(data["boards"]["90300000811"]["lineage"]["note"], "cycle")

    def test_K383_K384_K386_K387_K388_reserved_ids_stand_alone_and_suffixes_count_for_nothing(self):
        for bid in ("90300000206", "90300000237"):
            row = self.data["boards"][bid]
            self.assertEqual((row["rule"], row["attributes"]["install_kind"]), ("N4", "descendant_fingerprint"))
        self.assertEqual([self.cls(b) for b in ("90300000258", "90300000259")], ["normal_classic_board"] * 2)
        self.assertEqual(self.cls("90300000202"), "native_crm_opportunities_or_deals")
        data = self.classify(sweep([board("90300000821", "90100000901", "crm", ["person", "status", "date4", "date0"]),
                                    board("90300000822", "90100000901", "crm", ["lead_status_mka1b2c3",
                                                                                "lead_email_mka4b5c6",
                                                                                "lead_owner_mma7b8c9"])]))
        for bid in ("90300000821", "90300000822"):
            self.assertFalse(any(s.startswith("reserved:") for s in data["boards"][bid]["signals"]), bid)

    def test_K389_each_threshold_one_under_and_at(self):
        boards, expect, n = [], {}, 830
        for (product, entity), (threshold, ids) in self.led.SIGNATURES.items():
            if threshold is None or entity == "quotes_invoices":
                continue
            ws = {"crm": "90100000901", "service": "90100000902"}[product]
            for count in (threshold - 1, threshold):
                bid = "90300000%d" % n
                n += 1
                btype = "sub_items_board" if entity in ("qi_line_items", "tickets_subitems") else "board"
                boards.append(board(bid, ws, product, ids[:count], btype=btype))
                expect[bid] = (product, entity, count >= threshold)
        reads = sweep([b for b in boards if b["workspace_id"] == "90100000901"], "90100000901")
        second = sweep([b for b in boards if b["workspace_id"] == "90100000902"], "90100000902")
        reads["pages"] += second["pages"]
        data = self.classify(reads)
        for bid, (product, entity, met) in expect.items():
            self.assertEqual("reserved:%s/%s" % (product, entity) in data["boards"][bid]["signals"], met, (entity, bid))

    def test_W84_K369_a_tie_between_two_entities_is_medium_and_both_are_signals(self):
        leads, contacts = self.led.SIGNATURES[("crm", "leads")][1][:3], self.led.SIGNATURES[("crm", "contacts")][1][:3]
        data = self.classify(sweep([board("90300000871", "90100000901", "crm", leads + contacts),
                                    board("90300000872", "90100000901", "crm", leads + contacts[:2])]))
        tie, clear = data["boards"]["90300000871"], data["boards"]["90300000872"]
        self.assertEqual((tie["class"], tie["confidence"]), ("native_crm_leads", "medium"))  # NO 3.3's order breaks it
        self.assertTrue({"reserved:crm/leads", "reserved:crm/contacts"} <= set(tie["signals"]))
        self.assertEqual((clear["class"], clear["confidence"]), ("native_crm_leads", "high"))

    def test_K390_quotes_and_invoices_need_corroboration(self):
        self.assertEqual(self.cls("90300000218"), "ordinary_board_in_product_workspace")
        ids = self.led.SIGNATURES[("crm", "quotes_invoices")][1]
        data = self.classify(sweep([board("90300000851", "90100000901", "crm", ids),
                                    board("90300000852", "90100000901", "crm", ids, term="Document #")]))
        self.assertEqual((data["boards"]["90300000851"]["rule"], data["boards"]["90300000852"]["class"]),
                         ("N9", "native_crm_quotes_invoices"))

    def test_K391_K392_K393_K394_look_alikes_by_N8_never_by_name(self):
        self.assertEqual([self.data["boards"][b]["rule"] for b in ("90300000250", "90300000251")], ["N8", "N8"])
        self.assertEqual(self.cls("90300000204"), "native_crm_accounts")  # renamed, terminology Org
        self.assertEqual(self.cls("90300000254"), "ordinary_board_in_product_workspace")  # a relation into Tickets
        reads = copy.deepcopy(self.reads)
        for page in reads["pages"]:
            for b in page["response"]["data"].get("boards") or []:
                if isinstance(b, dict) and b.get("id") in ("90300000250", "90300000201"):
                    b["name"] = "Garvenn Notes"
        data = self.classify(reads)
        self.assertEqual((self.cls("90300000250", data), self.cls("90300000201", data)), ("lookalike_board",
                                                                                          "native_crm_leads"))

    def test_K395_the_imitation_test_is_exact(self):
        terms = {"90300000861": "Activity ", "90300000862": "Activity", "90300000863": "activity",
                 "90300000864": "Activity  ", "90300000865": "Org", "90300000866": "Client"}
        data = self.classify(sweep([board(b, "90100000901", "crm", term=t) for b, t in terms.items()]))
        rules = {b: data["boards"][b]["rule"] for b in terms}
        self.assertEqual(rules, {"90300000861": "N8", "90300000862": "N8", "90300000863": "N9", "90300000864": "N9",
                                 "90300000865": "N9", "90300000866": "N9"})

    def test_K396_K397_K398_K399_the_known_limits_are_reported_never_resolved(self):
        limits = {row["board_id"]: row for row in self.data["limits"]}
        self.assertEqual((limits["90300000257"]["code"], self.cls("90300000257")), ("L1", "native_crm_leads"))
        self.assertEqual((limits["90300000256"]["code"], self.cls("90300000256")), ("L2", "lookalike_board"))
        self.assertEqual((limits["90300000255"]["code"], limits["90300000255"]["codes"]), ("L3", ["L2", "L3"]))
        for row in limits.values():
            self.assertEqual(row["reason"], self.led.LIMIT_REASONS[row["code"]])
            self.assertEqual(row["codes"], sorted(self.data["boards"][row["board_id"]]["limits"]))
        self.assertEqual(sum(self.data["totals"].values()) + len(limits), self.data["board_count"])

    def test_K369_the_family_is_read_from_the_types(self):
        attrs = {b: self.data["boards"][b]["attributes"] for b in ("90300000202", "90300000210")}
        self.assertEqual([(a["family"], a["version"]) for a in attrs.values()], [("sales_crm", "v2"), ("crm_core", "v1")])

    def test_K370_W87_the_catalogue_tables_equal_native_objects_md(self):
        Drift(self, self.led, NO.read_text(encoding="utf-8")).run()

    def test_K418_K419_K421_K422_K254_the_one_query_selects_and_never_filters(self):
        text = NO.read_text(encoding="utf-8")
        block = re.search(r"```graphql\n(query DetectNativeBoards.*?)\n```", text, re.S).group(1)
        self.assertEqual(self.led.DETECT_QUERY, block)
        self.assertIn("columns { id type }", self.led.DETECT_QUERY)
        for held in [self.led.DETECT_QUERY] + list(self.led.SIDE_READS.values()):
            for word in ("query_params", "rules:", "compare_value", "column_id:"):  # G-83: select, never filter
                self.assertNotIn(word, held)
            for match in re.finditer(r"columns\(([^)]*)\)", held):  # K419: only the links alias takes a type list
                self.assertTrue(match.group(1).startswith("types:"), held)
        self.assertEqual(list(self.led.PAGE_SIZE), [25, 50])
        self.assertIn("limit: 50", self.led.DETECT_QUERY)
        self.assertEqual(self.data["page_size"], [25, 50])


class Drift:
    """W87's drift test: the tables of ledger.py against the sections of native-objects.md they copy."""

    def __init__(self, case, led, text):
        self.case, self.led, self.text = case, led, text

    def section(self, start, end):
        return self.text.split(start, 1)[1].split(end, 1)[0]

    def table(self, start, end):
        return [[c.strip() for c in line.strip().strip("|").split("|")] for line in self.section(start, end).split("\n")
                if line.startswith("|") and not set(line) <= set("|-: ")][1:]

    def run(self):
        eq, led = self.case.assertEqual, self.led
        crm = {}
        for family, cell in self.table("**3.1 Template source ids.**", "**3.2"):
            fam = {"Sales CRM v2": ("sales_crm", "v2"), "v2 companions": ("sales_crm", "v2"),
                   "v2 subitems": ("sales_crm", "v2"), "CRM core v1": ("crm_core", "v1"),
                   "Smaller families": (None, "unknown")}[family]
            for tid in re.findall(r"`(\d+)`", cell):
                crm[tid] = fam + ({"v2 companions": "companion", "v2 subitems": "subitems"}.get(family),)
            for first, second, entity in re.findall(r"`(\d+)`(?: and `(\d+)`)? ([a-z_]+)", cell):
                for tid in filter(None, (first, second)):
                    crm[tid] = fam + (entity,)
        eq(crm, led.CRM_TEMPLATES)
        service = {}
        for family, _, cell in self.table("**4.1 Families and template ids.**", "**4.2"):
            for tid, entity in re.findall(r"`(\d+)` ([a-z_]+)", cell):
                service[tid] = (family.split()[0], entity)
        for tid, entity in re.findall(r"`(\d+)` ([a-z_]+)", re.search(r"Family E \(([^)]*)\)", self.text).group(1)):
            service[tid] = ("E", entity)
        eq(service, led.SERVICE_TEMPLATES)
        roles = dict((tid, name.replace(" ", "_")) for tid, name in re.findall(
            r"`(\d+)` ([a-z ]+?)(?=[,(]| \()", self.section("Template lineage marks the roles:", "`created_from")))
        eq(roles, led.ROLE_TEMPLATES)
        views = {}
        for segment in self.section("**3.2 Template view ids.**", "**3.3").strip().rstrip(".").split(";"):
            label = segment.split("`", 1)[0].strip()
            for vid in re.findall(r"`(\d+)`", segment):
                views[vid] = label
        eq(set(views), set(led.CRM_VIEWS))
        for vid, label in views.items():
            family, version, entity = led.CRM_VIEWS[vid]
            self.case.assertTrue(any(word in label for word in entity.split("_or_")[0].split("_")[:1] + (
                ["deals"] if entity == "opportunities_or_deals" else []) + (["quotes"] if entity == "quotes_invoices"
                                                                             else [])), (vid, label))
            self.case.assertEqual(label.startswith("v2"), version == "v2", (vid, label))
        sviews = {}
        for segment in self.section("**4.2 Template view ids.**", "**4.3").strip().rstrip(".").split(";"):
            label = segment.split("`", 1)[0].strip()
            words = label.split()
            family = words[0] if words[0] in ("A", "B", "C", "D") else ("Portal" if label == "portal" else None)
            entity = "_".join(words[1:] if family in ("A", "B", "C", "D") else words)
            entity = {"csat": "csat_survey", "portal": "portal_custom_object", "start_here_doc": "start_here_doc"}.get(
                entity, entity)
            for vid in re.findall(r"`(\d+)`", segment):
                sviews[vid] = (family, entity)
        eq(sviews, led.SERVICE_VIEWS)
        for product, start, end in (("crm", "**3.3 Column signatures.**", "## 4."), ("service", "**4.3 Column signatures.**",
                                                                                     "**4.4")):
            for entity, threshold, cell in self.table(start, end):
                ids = [t for t in re.findall(r"`([^`]+)`", cell) if re.fullmatch(r"[a-z][a-z_0-9]*", t)]
                for a, b in re.findall(r"`([a-z_]+)` (?:…|through) `([a-z_]+)`", cell):
                    months = list(self.led._MONTHS)
                    ma = next(m for m in months if m in a.split("_"))
                    mb = next(m for m in months if m in b.split("_"))
                    ids += [a.replace(ma, m) for m in months[months.index(ma):months.index(mb) + 1]]
                number = re.match(r"(\d+)", threshold)
                want = (int(number.group(1)) if number else None, sorted(set(ids)))
                got = led.SIGNATURES[(product, entity)]
                eq((got[0], sorted(set(got[1]))), want, entity)
                if "(24 ids)" in cell:
                    eq(len(got[1]), 24)
        names = re.search(r"native default names \(([^)]*)\)", self.text).group(1)
        eq(set(n.strip() for n in names.split(",")), set(led.DEFAULT_NAMES))
        terms = re.search(r"and terminologies \((.*?)\)\. ", self.text).group(1)
        eq({t.strip('"') for t in re.findall(r"`([^`]+)`", terms)}, set(led.DEFAULT_TERMINOLOGY))
        marks = self.section("**2.4 Corroborating marks**", "**2.5")
        eq(set(re.findall(r"`(\d{10})`", marks.split("V2_OPPS_FINGERPRINT", 2)[1].split("\n")[0])), set(led.V2_OPPS_IDS))
        eq(set(re.search(r"one of ([^|]*)\|", marks).group(1).replace("`", "").replace(" ", "").split(",")),
           set(led.STATIC_IMAGES))
        eq(re.search(r"SLA helper regex, [^`]*`([^`]+)`", marks).group(1), led.SLA_HELPER.pattern)
        reserved = self.section("**2.3 Reserved column ids.**", "**2.4")
        eq(re.search(r"matching `([^`]+)`", reserved).group(1), led.SUFFIXED.pattern)
        eq(set(re.search(r"defaults ((?:`\w+`[, and]*)+) are excluded", reserved).group(1).replace("`", "").replace(
            "and", ",").replace(" ", "").split(",")) - {""}, set(led.BLANK_DEFAULTS))
        rp = self.section("**7.2 Fingerprints and lineage.**", "**7.3")
        eq(re.findall(r"`(rp_[a-z_]+)`", rp), list(led.RP_IDS))
        r5 = next(line for line in self.text.split("\n") if line.startswith("| R5 |"))
        eq(re.findall(r"`(project_[a-z]+)`", r5), list(led.PROJECT_IDS))
        eq((re.search(r"at least (\d+) of `project", r5).group(1), re.search(r"== (\d+)`", r5).group(1)),
           (str(led.R5_MIN), led.TASKS_TEMPLATE))
        r8 = next(line for line in self.text.split("\n") if line.startswith("| R8 |"))
        r9 = next(line for line in self.text.split("\n") if line.startswith("| R9 |"))
        eq((re.search(r"at least (\d+)", r8).group(1), re.search(r"at least (\d+)", r9).group(1)),
           (str(led.R8_MIN), str(led.R9_MIN)))
        eq(re.search(r"capped at (\d+) hops", self.text).group(1), str(led.LINEAGE_CAP))


# native-map and the guard_index fields.

class NativeMapTest(ReadBase):

    def setUp(self):
        super().setUp()
        self.key = load("native.expected.json")
        self.guard(client_workspace_ids=NATIVE_CLIENTS, build_targets_by_strand={"001": {
            "workspace_ids": ["90100000201"], "folder_ids": []}})
        self.reads = self.place("reads.json", load("native.reads.json"))

    def native_map(self, *extra):
        return self.ok("native-map", "--reads", self.reads, "--coverage", "the synthetic native sweep, every workspace",
                       *extra)

    def account(self):
        return self.data("account.json")

    def test_K400_K401_K402_K404_to_K410_K413_the_map_and_the_index(self):
        before = self.account()["guard_index"]
        out = self.native_map()
        account = self.account()
        index, native = account["guard_index"], account["native_map"]
        self.assertEqual(index["native_board_index"], self.key["native_board_index"])  # K404
        self.assertEqual(index["portal_object_ids"], self.key["portal_object_ids"])  # K410
        self.assertEqual(out["native_board_index"], self.key["native_board_index"])
        by_entity = index["native_board_ids_by_entity"]
        self.assertEqual(sorted(b for ids in by_entity.values() for b in ids), sorted(self.key["native_board_index"]))
        self.assertEqual(index["product_workspaces"]["90100000203"], "service")  # K405
        self.assertEqual([p["kind"] for p in index["account_products"]], ["core", "crm", "service"])  # K406
        self.assertTrue({"5678953932", "5727048235"} <= set(index["template_source_ids"]))  # K407
        self.assertEqual(index["unreadable_intermediate_ids"], ["90300000901", "90300000902", "90300000903"])
        self.assertIn("200776197", index["template_view_ids"])
        self.assertEqual(index["reserved_column_ids"]["crm/leads"]["threshold"], 3)  # K408
        self.assertEqual(index["reserved_column_ids"]["blank_default_exclusions"], ["person", "status", "date4", "date0"])
        self.assertEqual(index["native_default_names_and_terminology"], list(self.led.DEFAULT_NAMES) + list(
            self.led.DEFAULT_TERMINOLOGY))  # K409
        self.assertEqual(index["record_provenance"]["coverage"], "the synthetic native sweep, every workspace")  # K413
        self.assertEqual(index["record_provenance"]["staleness_budget_days"], 14)
        self.assertEqual((index["captured_at"], index["ring"]), ("2026-10-16T00:00:00Z", "release_candidate 2026-10"))
        for field in ("client_workspace_ids", "build_targets_by_strand", "lease"):  # K412, K411: kept as found
            self.assertEqual(index[field], before[field])
        for product in ("crm", "service"):
            for entity, entry in native[product].items():  # K400, K401, K402
                self.assertEqual(set(entry) - {"family"}, {"board_id", "rule", "confidence", "signals", "lineage",
                                                           "confirmed_by_user"}, entity)
                self.assertEqual("family" in entry, product == "service")
                self.assertIn(entry["confidence"], ("high", "medium", "low"))
                self.assertEqual(set(entry["lineage"]), {"chain", "resolved", "note"})
        self.assertEqual(native["crm"]["leads"]["board_id"], "90300000201")  # highest confidence, fewest hops, lowest id
        self.assertEqual(native["service"]["tickets"]["board_id"], "90300000220")
        self.assertEqual(set(native["portfolio"]["90300000263"]) >= {"board_id", "rule", "projects"}, True)
        self.assertNotIn("90300000218", index["native_board_index"])  # an ordinary board is no key

    def test_K403_K417_W88_nothing_below_high_is_confirmed(self):
        refusals = self.refused("native-map", "--reads", self.reads, "--coverage", "c", "--confirm", "crm/companion")
        self.assertIn(("account.json", "native_map.crm.companion.confirmed_by_user"), pairs(refusals))
        out = self.native_map("--confirm", "crm/leads")
        self.assertIs(self.account()["native_map"]["crm"]["leads"]["confirmed_by_user"], True)
        self.assertIs(self.account()["native_map"]["crm"]["companion"]["confirmed_by_user"], False)
        self.assertIn("90300000208", {r["board_id"] for r in out["needs_review"]})  # K417: asked about each time
        self.native_map()  # K416: a second call replaces the map and keeps the confirmation of an unchanged entry
        self.assertIs(self.account()["native_map"]["crm"]["leads"]["confirmed_by_user"], True)

    def test_K414_W89_an_empty_client_product_workspace_is_not_installed_here(self):
        out = self.native_map()
        self.assertEqual(out["reports"], self.key["reports"])
        self.assertNotIn("no natives", json.dumps(out))
        self.assertIn("90100000207", out["ui_steps_to_record"][0]["ui_step"])

    def test_K415_K416_natives_outside_the_client_are_indexed_and_never_targets(self):
        self.native_map()
        first = self.account()
        self.assertIn("90300000210", first["guard_index"]["native_board_index"])  # workspace 202 is no client's
        self.assertNotIn("90100000202", first["guard_index"]["client_workspace_ids"])
        self.native_map()
        second = self.account()
        self.assertEqual(second["native_map"], first["native_map"])
        self.assertEqual(second["guard_index"]["unreadable_intermediate_ids"],
                         first["guard_index"]["unreadable_intermediate_ids"])

    def test_W89_W90_refusals(self):
        self.assertIn(("(flags)", "--coverage"), pairs(self.refused("native-map", "--reads", self.reads, "--coverage",
                                                                   "two\nlines")))
        self.guard(build_targets_by_strand={"001": {"workspace_ids": ["90100000204"], "folder_ids": []}})
        self.assertIn(("account.json", "guard_index.build_targets_by_strand.001"),
                      pairs(self.refused("native-map", "--reads", self.reads, "--coverage", "c")))
        mixed = load("native.reads.json")
        mixed["pages"][0]["response"]["data"]["version"]["value"] = "2027-01"
        self.assertIn((WORK + "mixed.json", "pages[].response.data.version"), pairs(self.refused(
            "classify", "--reads", self.place("mixed.json", mixed))))
        numeric = load("native.reads.json")
        numeric["pages"][0]["response"]["data"]["boards"][0]["id"] = 90300000201
        self.assertTrue(self.refused("classify", "--reads", self.place("numeric.json", numeric)))


# snapshot and compare, offline, with the documents-appendix tokenizer.

class CompareTest(ReadBase):

    def setUp(self):
        super().setUp()
        state, self.key = load("compare/ledger-state.json"), load("compare/expected.json")

        def build(d):
            d["objects"] = {k: self.led.ordered_row(dict(r, approval_ref="v0.1r1")) for k, r in state["objects"].items()}
        self.edit_json(B1J, build)
        self.edit_json("account.json", lambda d: (d.update(live_objects=state["live_objects"]),
                                                  d["guard_index"].update(client_workspace_ids=["90100000301"])))
        self.before_read = self.place("audit/before.read.json", load("compare/before.read.json"))
        self.after_read = self.place("audit/after.read.json", load("compare/after.read.json"))
        shutil.copy(SNAPS / "compare" / "appendix.md", self.root / WORK / "audit" / "appendix.md")

    def snap(self, label, read):
        return self.ok("snapshot", "--strand", "001", "--label", label, "--read", read)

    def pair(self):
        before = self.snap("before", self.before_read)
        self.now = CLOCK + timedelta(hours=2)
        return before, self.snap("after", self.after_read)

    def compare(self, before, after, *extra):
        return self.ledger("compare", "--before", before["path"], "--after", after["path"], *extra)

    def test_K286_K287_K288_K289_K290_the_snapshot_file(self):
        before = self.snap("before", self.before_read)
        data = self.data(before["path"])
        self.assertTrue(re.fullmatch(r"live/snapshots/\d{4}-\d{2}-\d{2}-001-v0\.1-before\.json", before["path"]))
        self.assertEqual((data["schema"], data["ring"], data["read_at"], data["label"]),
                         ("snapshot/1", "release_candidate 2026-10", "2026-10-16T09:00:00Z", "before"))
        self.assertTrue(mc.parse_utc(data["taken_at"]))
        self.assertEqual(data["scope"], self.key["scope"])  # K287: trimmed, never refused
        self.assertEqual((data["ledger_sha256"], data["account_sha256"]), (self.sha(), self.sha("account.json")))
        for part in ("inventory", "boards", "automations", "forms", "docs", "dashboards", "agents", "workflows",
                     "vibe_apps"):  # K289
            self.assertTrue(data[part], part)
        self.assertFalse(any("plan" in a or "knowledge" in a for a in data["agents"]))  # digests, never the raw reads
        self.assertNotIn("short summary", json.dumps(data))
        again = self.snap("before", self.before_read)  # a second call writes a new file, never over the first
        self.assertTrue(again["path"].endswith("-before-2.json"))
        self.assertIn(("(flags)", "--label"), pairs(self.refused("snapshot", "--strand", "001", "--label", "during",
                                                                "--read", self.before_read)))
        self.assertIn(("strands/002-timber-orders/solution/build.json", "(whole file)"), pairs(self.refused(
            "snapshot", "--strand", "002", "--label", "before", "--read", self.before_read)))

    def test_K291_K292_to_K299_K302_K310_every_A97_item_flags_and_the_controls_do_not(self):
        before, after = self.pair()
        with mock.patch.object(socket, "socket", side_effect=AssertionError("no network")):  # K291: offline
            code, data = self.compare(before, after)
        self.assertEqual(code, 1)
        got = {(f["field"], json.dumps(f["before"]), json.dumps(f["after"]), f["problem"]) for f in data["flags"]}
        want = {(f["field"], json.dumps(f["before"]), json.dumps(f["after"]), f["problem"]) for f in self.key["flags"]}
        self.assertEqual(got, want)
        flagged = {f["field"].split(".")[0] for f in data["flags"]}
        for control in self.key["not_flagged"]:  # K299
            self.assertNotIn(control["object"], flagged, control["case"])
        for finding in data["findings"]["blocking"]:  # K310: the after snapshot's path, the field, the two values
            self.assertEqual((finding["file"], finding["expected"]), (after["path"], "unchanged during the audit window"))
        self.edit_json(B1J, lambda d: d.update(updated_at="2026-11-05T15:00:00Z"))  # K302: the ledger moved
        moved = self.snap("after", self.after_read)
        code, data = self.compare(before, moved)
        self.assertIn("ledger:001.ledger_sha256", {f["field"] for f in data["flags"]})

    def test_K300_K301_a_protected_row_that_moved_before_the_window_is_changed_outside(self):
        before, after = self.pair()
        account = self.sha("account.json")
        code, data = self.compare(before, after)
        want = strip(self.key["changed_outside"])
        self.assertEqual(data["changed_outside"], want)
        self.assertEqual(data["findings"]["warnings"][0]["field"], "002:B1.digest")
        self.assertNotIn("90300000311", json.dumps(data["flags"]))  # never as a write during the window
        self.assertEqual(self.sha("account.json"), account)  # K301: reported, never fixed
        code, data = self.compare(before, self.snap("after", self.before_read))
        self.assertEqual((code, data["flags"]), (2, []))  # only the changed-outside warning remains
        moved = self.snap("before", self.after_read)
        code, data = self.ledger("compare", "--before", moved["path"], "--after", moved["path"])
        self.assertEqual(code, 1)  # a pair not labelled before and after is refused

    def test_K303_to_K309_the_documents_appendix(self):
        before, after = self.pair()
        code, data = self.compare(before, after, "--appendix", WORK + "audit/appendix.md")
        got = [(d["number"], d["verdict"], d["reason"]) for d in data["documents"]]
        self.assertEqual(got, [(d["number"], d["verdict"], d["reason"]) for d in self.key["documents"]])
        self.assertEqual(code, self.key["exit_code"])
        refused = [f for f in data["findings"]["blocking"] if f["file"] == WORK + "audit/appendix.md"]
        self.assertEqual(len(refused), 3)
        source = (SCRIPTS / "ledger.py").read_text(encoding="utf-8")  # K308: the tokenizer lives in ledger.py
        self.assertIn("def gql_tokens(", source)
        self.assertEqual([p.name for p in SCRIPTS.glob("*.py") if "def gql_tokens(" in p.read_text(encoding="utf-8")],
                         ["ledger.py"])

    def test_K307_W77_the_tokenizer_on_more_planted_documents(self):
        scan = self.led.scan_document
        cases = {'query { a(s: """mutation { x } \\""" still""") { id } }': ("pass", "one query"),
                 "fragment F on Board { id } query { boards { ...F } }": ("pass", "one query"),
                 "type Query { id: ID }": ("refused", "a type-system definition"),
                 'query { a(s: "open': ("refused", "a syntax error: an unterminated string"),
                 "query { a { id }": ("refused", "a syntax error: unbalanced brackets"),
                 "query Named($x: Int = 1)": ("refused", "a syntax error: a definition with no selection set"),
                 "query { a } ; ": ("refused", "a syntax error: a stray character ';'"),
                 "subscription { a } query { b }": ("refused", "subscription"),
                 "query { a } mutation { b }": ("refused", "mutation"), "# only a comment": ("refused", "no operation"),
                 "﻿{ me { id } }": ("pass", "one query")}
        for text, want in cases.items():
            self.assertEqual(scan(text), want, text)
        found = self.led.appendix_documents("# A\n\n## Documents appendix\n\n```text\nquery { a }\n```\n\n```graphql\n"
                                            "query { a }\n")
        self.assertEqual([(n, body, why) for n, _, body, why in found], [(1, None, "a text block the scan cannot read"),
                                                                         (2, None, "a fenced block that never closes")])
        self.assertIsNone(self.led.appendix_documents("# A\n\n## Notes\n"))


# reconcile: the seven classes, automations first, and the classify-only run of a sibling.

class ReconcileTest(ReadBase):

    def setUp(self):
        super().setUp()
        self.key = load("reconcile/expected.json")
        self.rebuild()

    def rebuild(self):
        """The holder strand's rows and runs, and the account fields reconcile reads, in this record copy."""
        state = load("reconcile/ledger-state.json")
        self.edit_json(B1J, lambda d: d.update(runs=state["build"]["runs"], objects=state["build"]["objects"]))
        self.edit_json("account.json", lambda d: (d["guard_index"].update(
            client_workspace_ids=state["account"]["client_workspace_ids"],
            build_targets_by_strand=state["account"]["build_targets_by_strand"],
            native_board_index=state["account"]["native_board_index"]), d.update(live_objects=state["account"][
                "live_objects"])))
        self.inventory = self.place("live-read.json", load("reconcile/live-inventory.json"))

    def hold(self):
        """The holder's lease carrying the interrupted run's id, its heartbeat then gone stale (K37: primitives)."""
        mc.lease_refresh(self.root, "2", LABEL, RUN)
        self.now = CLOCK + timedelta(hours=2)

    def fresh(self):
        """The synthetic inventory as read now, after the holder's heartbeat (R7: the classify-only form reads the
        account after the holder went quiet, never an older read)."""
        data = load("reconcile/live-inventory.json")
        data["read_at"] = mc.stamp("utc", self.now - timedelta(minutes=1))
        self.inventory = self.place("live-read-now.json", data)

    def elements(self, data):
        return [{k: e[k] for k in ELEMENT} for e in data["elements"]]

    def test_K265_to_K278_the_full_run(self):
        before = self.tree()
        data = self.ok("reconcile", "--strand", "001", "--inventory", self.inventory)
        full = self.key["full"]
        self.assertEqual(self.elements(data), [{k: e[k] for k in ELEMENT} for e in full["elements"]])
        self.assertEqual(data["classes"], full["classes"])  # K265, K266: every class, the seven tokens
        self.assertEqual(list(data["classes"]), list(self.led.RECONCILE_CLASSES))
        for field in ("unchanged", "not_started", "not_reconciled"):
            self.assertEqual(data[field], full[field], field)
        self.assertEqual([(r["key"], r["kind"], r["status"], r["read"]) for r in data["not_in_inventory"]],
                         [(r["key"], r["kind"], r["status"], r["read"]) for r in full["not_in_inventory"]])
        changed = {k for k, v in self.tree().items() if before.get(k) != v}
        self.assertEqual(changed, {".work/strands/001/live-inventory.json"})  # K278, W72 (b): only the copy
        self.assertEqual(data["mode"], "full")
        notes = {(e["key"], tuple(e["live_ids"])): e["note"] for e in data["elements"]}
        for element in full["elements"]:  # the notes too, but AG2's: its row records no version_id to name
            if element["key"] != "AG2":
                self.assertEqual(notes[(element["key"], tuple(element["live_ids"]))], element["note"], element["key"])
        again = self.ok("reconcile", "--strand", "001")  # the copy is read when no file is handed
        self.assertEqual(self.elements(again), self.elements(data))

    def test_K274_K275_K276_K277_the_order_and_the_lost_replies(self):
        data = self.ok("reconcile", "--strand", "001", "--inventory", self.inventory)
        kinds = [e["kind"] for e in data["elements"]]
        first = [k for k in kinds if k in ("automation", "agent", "vibe_app", "workflow")]
        self.assertEqual(kinds[:len(first)], first)  # K274: automations, then the AI kinds
        self.assertEqual(sorted(set(first), key=first.index), ["automation", "agent", "vibe_app", "workflow"])
        lost = next(e for e in data["elements"] if e["key"] == "A1")
        self.assertEqual((lost["class"], lost["confirm"]), ("adopt", True))  # K277
        self.assertEqual({e["kind"] for e in data["elements"] if e["kind"] in ("agent", "vibe_app", "workflow")},
                         {"agent", "vibe_app", "workflow"})  # K276
        extra = next(e for e in data["elements"] if e["live_ids"] == ["90300000419"])
        self.assertEqual((extra["class"], extra["predates_attempt"]), ("unrecorded-extra", True))  # K272

    def test_K279_to_K283_the_classify_only_run_from_the_sibling(self):
        self.hold()
        self.fresh()
        objects = json.dumps(self.data()["objects"], sort_keys=True)
        code, data = self.ledger("reconcile", "--strand", "001", "--classify-only", "--asked-by", "002",
                                 "--inventory", self.inventory)  # K283: no fence flags, no sha
        self.assertEqual((code, data["asked_by"], data["marked"]), (0, "002", True))
        run = next(r for r in self.data()["runs"] if r["id"] == RUN)
        want = self.key["classify_only"]
        self.assertEqual(run["state"], want["run_state_after"])  # K281
        self.assertEqual(set(run["reconcile"]), {"at", "mode", "read_at", "classes", "findings"})  # K280, R7
        self.assertEqual(run["reconcile"]["read_at"], mc.stamp("utc", self.now - timedelta(minutes=1)))
        self.assertEqual((run["reconcile"]["mode"], run["reconcile"]["classes"]), (want["mode"], want["classes"]))
        self.assertTrue(mc.parse_utc(run["reconcile"]["at"]))
        self.assertEqual([(f["key"], f["class"], f["live_ids"]) for f in run["reconcile"]["findings"]],
                         [(f["key"], f["class"], f["live_ids"]) for f in want["findings"]])  # K279
        self.assertEqual(json.dumps(self.data()["objects"], sort_keys=True), objects)  # K282: nothing adopted
        self.assertIsNone(mc._reconcile(self.root, mc.read_lock(self.root))[1])  # G04's condition 4 now holds

    def test_W72_the_refusals_of_classify_only(self):
        mc.lease_refresh(self.root, "2", LABEL, RUN)  # fresh: a live holder's run is never marked from outside
        self.assertIn((mc.LOCK_REL, "heartbeat_at"), pairs(self.refused("reconcile", "--strand", "001",
                                                                        "--classify-only", "--inventory", self.inventory)))
        self.copy_home()
        os.environ["MMB_HOME"] = str(self.home)
        self.rebuild()
        mc.lease_refresh(self.root, "2", LABEL, "run-2026-10-16-9")
        self.now = CLOCK + timedelta(hours=2)
        self.fresh()  # R6: a lock run id the ledger lacks is recorded as an interrupted run, no longer refused
        data = self.ok("reconcile", "--strand", "001", "--classify-only", "--inventory", self.inventory)
        self.assertEqual((data["marked"], data["recorded_missing_run"], data["run_state"]), (True, True, "interrupted"))
        mc.lease_release(self.root, "2", LABEL)
        self.assertIn((mc.LOCK_REL, "state"), pairs(self.refused("reconcile", "--strand", "001", "--classify-only",
                                                                "--inventory", self.inventory)))

    def test_K284_K280_a_lock_with_no_run_marks_nothing_and_every_count_is_printed(self):
        self.now = CLOCK + timedelta(hours=2)
        self.fresh()
        before = self.data()
        data = self.ok("reconcile", "--strand", "001", "--classify-only", "--asked-by", "002", "--inventory",
                       self.inventory)
        self.assertEqual((data["marked"], data["run_id"]), (False, None))
        self.assertEqual(self.data(), before)
        one = {"B6": dict(load("reconcile/ledger-state.json")["build"]["objects"]["B6"])}
        self.edit_json(B1J, lambda d: d.update(objects=one))
        data = self.ok("reconcile", "--strand", "001", "--inventory", self.inventory)
        self.assertEqual(list(data["classes"]), list(self.led.RECONCILE_CLASSES))  # all seven keys, zero where empty
        self.assertEqual(data["classes"]["adopt"], 1)
        self.assertTrue(all(isinstance(v, int) for v in data["classes"].values()))

    def test_W70_a_malformed_inventory_is_refused(self):
        bad = load("reconcile/live-inventory.json")
        bad.update(schema="live-inventory/2", strand="002")
        del bad["folders"]
        refusals = pairs(self.refused("reconcile", "--strand", "001", "--inventory", self.place("bad.json", bad)))
        self.assertTrue({(WORK + "bad.json", "schema"), (WORK + "bad.json", "strand"), (WORK + "bad.json", "folders")}
                        <= refusals)
        code, data = self.ledger("reconcile", "--strand", "002")
        self.assertEqual(code, 1)


# estimate: batches, the classification query paid once per window, the other strands, the AI-powered elements.

class EstimateTest(ReadBase):

    def estimate(self, strand="001", **inputs):
        argv = ["estimate", "--strand", strand]
        if inputs:
            argv += ["--inputs", self.place("estimate-%s.json" % strand, inputs)]
        return self.ok(*argv)

    def sibling(self, rows):
        """Strand 002 with a ledger of open rows, as an approval would leave it."""
        path = self.root / "strands" / "002-timber-orders" / "solution" / "build.json"
        objects = {key: {"type": kind, "id": None, "name": "Kelmoss %s" % key, "parent_key": None, "status": "planned",
                         "origin": "created"} for key, kind in rows}
        path.write_bytes(mc.json_text({"schema": "build/2", "strand": "002", "runs": [], "objects": objects}).encode())

    def test_K250_K251_K264_batches_and_the_two_figures(self):
        for items, calls in ((41, 3), (40, 2), (0, 0)):
            self.assertEqual(self.estimate(items=items)["batches"]["create_items"], calls)
        data = self.estimate(updates=81)
        self.assertEqual(data["batches"]["update_items"], 3)
        self.assertTrue(isinstance(data["calls"][0], int) and data["calls"][0] <= data["calls"][1])

    def test_K252_K253_K254_K256_the_components_and_the_classification_query(self):
        self.guard(captured_at="2026-10-01T00:00:00Z")
        data = self.estimate(boards_to_classify=120, portfolios=1, doc_pages=4)
        self.assertEqual((data["classification_query"]["calls"], data["classification_query"]["complexity"]),
                         ([3, 5], [432000, 636000]))
        self.assertEqual(data["classification_query"]["page_size"], [25, 50])
        self.assertEqual(set(data["components"]), {"preflight", "writes", "read_backs", "polls", "account_checks", "audit"})
        self.assertEqual(data["components"]["preflight"], [12, 12])
        self.assertEqual(data["classification_side_reads"]["calls"], [5, 11])

    def test_K255_automation_actions_against_the_allowance(self):
        self.assertIs(self.estimate(automation_actions_monthly=300, plan_allowance=250)["automation_actions"]["over"], True)
        self.assertIs(self.estimate(automation_actions_monthly=200, plan_allowance=250)["automation_actions"]["over"], False)
        none = self.estimate(automation_actions_monthly=200)["automation_actions"]
        self.assertEqual((none["allowance"], none["over"]), (None, None))

    def test_K257_K258_K450_the_other_open_strands_print_totals_only(self):
        self.sibling([("B1", "board"), ("B1.C1", "column"), ("A1", "automation")])
        data = self.estimate(daily_total=1000)
        self.assertEqual([o["strand"] for o in data["other_strands"]], ["002"])
        self.assertEqual(set(data["other_strands"][0]), {"strand", "calls"})
        self.assertNotIn("Kelmoss", json.dumps(data))
        self.assertEqual(data["headroom_after_others"], data["headroom"] - data["other_strands"][0]["calls"][1])
        self.edit_fm("strands/002-timber-orders/STRAND.md", state="closed")
        self.assertEqual(self.estimate(daily_total=1000)["other_strands"], [])

    def test_K259_K260_the_warnings(self):
        base = self.estimate(daily_total=1000)["calls"][1]
        under = self.estimate(daily_total=1000, used_today=1000 - int(base / 0.3) - 1)
        self.assertEqual(under["warnings"], [])
        over = self.estimate(daily_total=1000, used_today=1000 - int(base / 0.3) + 5)
        self.assertTrue(any("30%" in w for w in over["warnings"]))
        at = self.estimate(doc_pages=250 - base)
        self.assertEqual((at["calls"][1], at["warnings"]), (250, []))
        above = self.estimate(doc_pages=251 - base)
        self.assertTrue(any("1,000 calls a day" in w for w in above["warnings"]))

    def test_K261_W66_the_query_is_paid_once_per_staleness_window(self):
        self.now = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
        self.guard(captured_at="2026-09-01T00:00:00Z")
        self.sibling([("B1", "board")])
        self.edit_fm("strands/002-timber-orders/STRAND.md", version="v0.1")
        first = self.estimate(boards_to_classify=120)
        self.assertEqual((first["classification_query"]["paid"], first["classification_query"]["calls"]), (False, [3, 5]))
        self.guard(client_workspace_ids=NATIVE_CLIENTS, build_targets_by_strand={})
        self.ok("native-map", "--reads", self.place("reads.json", load("native.reads.json")), "--coverage", "a sweep")
        second = self.estimate("002", boards_to_classify=120)
        self.assertEqual((second["classification_query"]["paid"], second["classification_query"]["calls"],
                          second["classification_side_reads"]["calls"]), (True, [0, 0], [0, 0]))
        self.now = datetime(2026, 11, 30, 9, 0, tzinfo=timezone.utc)  # past the window it counts again
        self.assertIs(self.estimate("002", boards_to_classify=120)["classification_query"]["paid"], False)

    def test_K262_K263_the_ai_powered_elements_and_no_credit_figure(self):
        self.approve()
        data = self.estimate(credits_used=12, price_per_credit=3)
        self.assertEqual(data["ai_powered"], ["AG1", "B1.AI1", "VB1"])
        self.assertEqual([m["key"] for m in data["may_be_ai_powered"]], ["SQ1", "WF1"])
        self.assertEqual(data["fields_present_not_read"], ["credits_used", "price_per_credit"])

        def walk(value):
            if isinstance(value, dict):
                for key, inner in value.items():
                    if re.search(r"credit|price|package", key) and key != "fields_present_not_read":
                        self.fail(key)
                    walk(inner)
            elif isinstance(value, list):
                for inner in value:
                    walk(inner)
        walk(data)

    def test_W64_write_sets_preflight_and_the_running_runs_estimate(self):
        self.approve()
        self.start()
        self.assertIn(("(flags)", "--write"), pairs(self.refused("estimate", "--strand", "001", "--write",
                                                                "--expect-sha", self.sha())))
        inputs = self.place("in.json", {"daily_total": 1000, "used_today": 40, "client_reserve": 10, "roster_ok": True,
                                        "workspaces_ok": True, "stale_gotchas": [], "findings": []})
        self.assertIn((B1J, "sha256"), pairs(self.refused("estimate", "--strand", "001", "--inputs", inputs, "--write",
                                                          "--expect-sha", "0" * 64)))
        data = self.ok("estimate", "--strand", "001", "--inputs", inputs, "--write", "--expect-sha", self.sha())
        ledger = self.data()
        self.assertEqual(ledger["preflight"]["estimated_calls"], data["calls"])
        self.assertEqual((ledger["preflight"]["daily_total"], ledger["preflight"]["workspaces_ok"]), (1000, True))
        self.assertEqual(ledger["runs"][-1]["calls_estimated"], data["calls"])
        self.assertEqual(data["written"], {B1J: self.sha()})
        negative = self.place("neg.json", {"items": -1})
        self.assertIn((WORK + "neg.json", "items"), pairs(self.refused("estimate", "--strand", "001", "--inputs",
                                                                       negative)))


class SourceTest(ReadBase):

    def test_K290_K291_K444_no_network_module_and_no_answer_in_the_script(self):
        source = (SCRIPTS / "ledger.py").read_text(encoding="utf-8")
        module = ast.parse(source, feature_version=(3, 9))
        names = {a.name.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(names & {"socket", "urllib", "http", "ssl", "requests", "ftplib", "smtplib"})
        for rel in ("identification.expected.json", "native.expected.json", "compare/expected.json",
                    "reconcile/expected.json"):  # the classifier works from the rules alone
            key = load(rel)
            self.assertNotIn(Path(rel).name.split(".")[0] + ".reads", source)
            for bid in key.get("boards") or {}:
                self.assertNotIn(bid, source)
            for entry in (key.get("boards") or {}).values():
                self.assertNotIn(entry["case"], source)
        for word in re.findall(r"\b903000\d{5}\b|\b901000\d{5}\b", source):
            self.fail(word)

    def test_K20_the_six_commands_are_built(self):
        for name in ("classify", "native-map", "snapshot", "compare", "reconcile", "estimate"):
            self.assertIsNotNone(self.led.COMMANDS[name])
        code, data = self.ledger("reconcile")
        self.assertEqual((code, data["error"]["field"]), (3, "arguments"))


if __name__ == "__main__":
    unittest.main()
