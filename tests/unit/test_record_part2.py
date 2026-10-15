"""Unit tests for record.py part 2 (WP2, contract clauses by name): the lease, versions, the card, home init, init,
and the heartbeat that lies ahead of the clock.

The frame is test_record.py's Base: a copy of tests/unit/fixtures/home/ in a temporary folder whose name holds a
space, MMB_HOME pointed at it, HOME and USERPROFILE at an empty canary, mmb_common's clock pinned to the fixture's
reference time, and record.py run in process from a temporary plugin root made of tests/unit/fixtures/plugin/ and
a copy of scripts/. `home init` and `init` run here against the stand-in templates; stage 3 runs them again with
WP7's real templates. Tests whose docstring says "Windows run" must be repeated on a real Windows machine (C04).
"""
import ast, contextlib, io, json, os, re, shutil, subprocess, sys, threading, unittest  # noqa: E401
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from test_record import Base, CALL, CLOCK, FIXTURES, LABEL, S1, S2, V1, is_stdlib, make_plugin, summary_draft
import mmb_common as mc

STALE, RUN = CLOCK + timedelta(minutes=90), "run-2026-11-05-1"
CONDENSED = "v0.1 audited at revision 1 (sha 5b81f6a), shown on 2026-11-03."
ASSUMED = "A job is ready to install when every cutting-list line is ticked"
BACKLOG = '---\nschema: "backlog/1"\nstrand: "001"\n---\nInternal: never client-facing\n\n## Items\n\n- B1 a supplier view\n'
ANSWERS = ("--firm-name", "Example Consulting", "--firm-rendering", "Example Consulting", "--firm-rendering",
           "example-consulting", "--default-account-slug", "example-account", "--default-account-id", "10000001")
INIT = ("--name", "Fresh Client", "--topic", "orders", "--title", "Orders", "--kind", "platform", "--reason",
        "the first call asked for one place for orders")


class Part2(Base):

    def run_at(self, record, *argv):
        """(exit code, JSON) of main() with --record `record`, or with none when `record` is None."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.rec.main((["--record", str(record)] if record else []) + [str(arg) for arg in argv])
        data = json.loads(out.getvalue())
        self.four_parts(data)  # C21
        return code, data

    def release_fixture_lease(self):
        return self.ok("lease", "release", "--epoch", "2", "--label", LABEL)

    def breaking(self, *extra, **changes):
        args = dict(epoch="2", label=LABEL, for_strand="002", user_yes="yes, break the lease of 001",
                    account_id="10000001", choice="resume")
        args.update(changes)
        argv = ["lease", "break"]
        for key, value in args.items():
            if value is not None:
                argv += ["--" + key.replace("_", "-"), value]
        return argv + list(extra)

    def add_run(self, classes):
        """The lock carries RUN, interrupted in 001's ledger with a classify-only reconcile after the heartbeat."""
        self.edit_json(".work/lock.json", lambda lock: lock.update(run_id=RUN))
        run = {"id": RUN, "version": "v0.1", "state": "interrupted",
               "reconcile": {"at": "2026-11-05T15:50:00Z", "mode": "classify-only", "classes": classes}}
        self.edit_json(S1 + "/solution/build.json", lambda b: b["runs"].append(run))

    def headers(self, count, rel="log.md"):
        return [entry.split("\n", 1)[0] for entry in self.entries(rel)[:count]]


class LeaseTest(Part2):

    def test_C87_C88_C89_C99_take_mints_and_returns_the_label(self):
        released = self.release_fixture_lease()
        self.assertEqual((released["epoch"], released["state"]), (2, "released"))
        self.assertEqual(self.entries()[0], "## %s · 001 · lease · v0.1 · %s\nreleased, epoch 2\n\n" % (mc.stamp("log"), LABEL))
        self.assertEqual(self.refused("lease", "take", "audit", "--strand", "001"), {(".work/lock.json", "kind")})
        taken = self.ok("lease", "take", "build", "--strand", "001")
        self.assertRegex(taken["session_label"], r"^%s-[a-z0-9]{4}$" % mc.stamp("label"))
        self.assertEqual((taken["epoch"], taken["strand"], taken["version"]), (3, "001", "v0.1"))
        self.assertIn("refresh, release and break present them", taken["carry"])
        self.assertEqual(self.entries()[0].split("\n")[:2], ["## %s · 001 · lease · v0.1 · %s" % (
            mc.stamp("log"), taken["session_label"]), "taken, epoch 3"])
        status = {k: v for k, v in self.ok("lease", "status").items() if k not in ("ok", "command")}
        self.assertEqual(status, self.run_record("status", "--json")[1]["lease"])
        self.assertEqual((status["held"], status["session_label"], status["fresh"]), (True, taken["session_label"], True))
        self.assertEqual(self.check()[0], 0)

    def test_C90_C96_C98_refresh_and_release_need_the_label(self):
        for argv in (("lease", "refresh", "--epoch", "2"), ("lease", "refresh", "--epoch", "2", "--label", "x"),
                     ("lease", "refresh", "--label", LABEL), ("lease", "release", "--epoch", "2"),
                     ("lease", "release", "--epoch", "2", "--label", "20261105-1405-zzzz")):
            self.assertEqual(self.refused(*argv), {(".work/lock.json", "session_label")}, argv)
        before = self.entries()
        self.now = CLOCK + timedelta(minutes=5)
        moved = self.ok("lease", "refresh", "--epoch", "2", "--label", LABEL, "--run-id", RUN)
        self.assertEqual((moved["heartbeat_at"], moved["run_id"]), ("2026-11-05T14:35:00Z", RUN))
        self.assertEqual(self.entries(), before)  # C96: a refresh writes no log entry
        self.release_fixture_lease()
        self.assertEqual(self.refused("lease", "release", "--epoch", "2", "--label", LABEL),
                         {(".work/lock.json", "session_label")})

    def test_C91_C92_C93_C94_take_refusals_name_the_holder(self):
        code, data = self.run_record("lease", "take", "--strand", "002")
        self.assertEqual(code, 1)
        held = [f for f in data["refusals"] if f["field"] == "state"][0]
        for part in ("strand 001 (Job tracking) v0.1", "session %s" % LABEL, "heartbeat 10 minutes old: fresh",
                     "Nothing local is blocked", "the audit and the release of any strand are blocked"):
            self.assertIn(part, held["problem"])
        for part in ("wait for the run to end", "record.py lease release", "break it if it is stale"):
            self.assertIn(part, held["expected"])
        same = [f for f in self.run_record("lease", "take", "--strand", "001")[1]["refusals"] if f["field"] == "state"]
        self.assertIn("another session of this strand", same[0]["problem"])
        self.ok("strand", "kind", "--strand", "002", "--kind", "non-platform", "--reason", "a supplier portal script")
        self.assertEqual(self.refused("lease", "take", "--strand", "002"),
                         {(S2 + "/STRAND.md", "kind"), (S2 + "/STRAND.md", "version"), (".work/lock.json", "state")})
        self.assertEqual(self.refused("lease", "take", "--strand", "009"), {("strands/", "strand")})

    def test_C101_to_C106_break_lists_every_failing_condition(self):
        self.assertEqual(self.refused(*self.breaking()), {(".work/lock.json", "heartbeat_at")})
        self.now = STALE
        for changes, field in ((dict(user_yes=None), "user_yes"), (dict(user_yes="yes, clear the lock"), "user_yes"),
                               (dict(account_id="10000002"), "account.id"), (dict(choice=None), "choice"),
                               (dict(epoch="1"), "epoch"), (dict(label=None), "epoch")):
            refusal = self.refused(*self.breaking(**changes))
            self.assertEqual({field for _, field in refusal}, {field}, changes)
        self.assertEqual(self.refused(*self.breaking(for_strand="009")), {(".work/lock.json", "for_strand")})
        self.assertEqual(self.refused(*self.breaking(user_yes="yes 001\nand more")), {(".work/lock.json", "user_yes")})
        self.edit_json(".work/lock.json", lambda lock: lock.update(run_id=RUN))
        self.assertEqual(self.refused(*self.breaking()), {(S1 + "/solution/build.json", "runs[].reconcile")})

    def test_C108_C109_C110_C111_C113_G03_a_resume_break_writes_three_entries(self):
        self.now = STALE
        data = self.ok(*self.breaking())
        self.assertEqual((data["broken_epoch"], data["epoch"], data["choice"], data["paused"]), (2, 3, "resume", None))
        self.assertIn("record.py lease take --strand 001", data["next"])
        minute = mc.stamp("log")
        record, holder, taker = self.entries()[:3]
        self.assertEqual(record, '## %s · - · lease · - · %s\nbroken: epoch 2 · holder: 001 (Job tracking) v0.1 · run: '
                                 'none\nreconcile: none\nchoice: resume · for: 002 · the user: "yes, break the lease of '
                                 '001"\n\n' % (minute, LABEL))
        self.assertEqual(holder, "## %s · 001 · lease · v0.1 · %s\nbroken, epoch 2 · choice: resume · for: 002\n\n"
                         % (minute, LABEL))
        self.assertEqual(taker, "## %s · 002 · lease · - · %s\nbroke the lease of 001 v0.1, epoch 2 · choice: resume\n\n"
                         % (minute, LABEL))
        lock = json.loads((self.root / ".work" / "lock.json").read_text(encoding="utf-8"))
        self.assertEqual((lock["state"], lock["epoch"], self.fm("CLIENT.md")["lease"]), ("broken", 3, "none"))
        fresh = self.ok("lease", "take", "--strand", "001")
        self.assertEqual(fresh["epoch"], 4)
        self.assertNotEqual(fresh["session_label"], LABEL)
        self.ok("lease", "refresh", "--epoch", "4", "--label", fresh["session_label"], "--run-id", "run-2026-11-05-2")
        for epoch, label in ((2, LABEL), (4, LABEL)):
            self.assertFalse(mc.lease_fence(self.root, epoch, label, "run-2026-11-05-2")[0])
        self.assertEqual(mc.lease_fence(self.root, 4, fresh["session_label"], "run-2026-11-05-2"), (True, "ok"))
        self.assertEqual(self.check()[0], 0)

    def test_C107_C112_G52_a_park_pauses_the_holder(self):
        self.now = STALE
        self.add_run({"adopt": 2, "duplicate": 1})
        park = ("--park-yes", "yes, park 001 for now")
        self.assertEqual(self.refused(*self.breaking(*park, choice="park")), {(".work/lock.json", "reconcile")})
        self.edit_json(S1 + "/solution/build.json", lambda b: b["runs"][-1]["reconcile"].update(classes={"adopt": 2}))
        self.assertEqual(self.refused(*self.breaking(choice="park")), {(".work/lock.json", "park_yes")})
        data = self.ok(*self.breaking(*park, choice="park"))
        self.assertEqual((data["paused"], data["reconcile"]), ("001", {"adopt": 2}))
        fields, text = self.fm(S1 + "/STRAND.md"), mc.read_text(self.root / S1 / "STRAND.md")
        self.assertEqual(fields["state"], "paused")
        self.assertTrue(text.endswith('\n## Paused\n\n- parked %s by a lease break for strand 002: run %s, version v0.1, '
                                      'reconcile adopt 2; the user: "yes, park 001 for now"\n' % (mc.stamp("date"), RUN)))
        self.assertIn("| 001 | Job tracking | platform | paused |", mc.read_text(self.root / "CLIENT.md"))
        self.assertIn('park: "yes, park 001 for now"', self.entries()[0])
        self.assertIn("paused: what is unresolved is in STRAND.md", self.entries()[1])
        history = json.loads((self.root / ".work" / "lock.json").read_text(encoding="utf-8"))["history"]
        self.assertEqual([e["event"] for e in history[-2:]], ["broken", "parked"])
        self.assertEqual(self.refused("strand", "resume", "--strand", "001"), {(S1 + "/solution/build.json", "runs")})
        self.ok("version", "open", "--strand", "002")
        self.assertEqual(self.ok("lease", "take", "--strand", "002")["epoch"], 4)


class HeartbeatTest(Part2):
    """Added by part 2: a heartbeat more than five minutes ahead of this clock is a clock disagreement."""

    def test_C95_a_heartbeat_ahead_of_the_clock_is_never_read_as_fresh(self):
        self.now = datetime(2026, 10, 15, 3, 42, tzinfo=timezone.utc)  # the fixture read on the day it was built
        self.assertEqual(mc.heartbeat_age("2026-11-05T14:20:00Z"), (-30878, True))
        lease = self.run_record("status", "--json")[1]["lease"]
        self.assertEqual((lease["heartbeat_age_minutes"], lease["fresh"], lease["state"]), (-30878, False, "held"))
        for minute, age, fresh in ((16, 0, True), (15, 0, True), (14, -6, False)):
            self.now = datetime(2026, 11, 5, 14, minute, tzinfo=timezone.utc)
            lease = self.ok("lease", "status")
            self.assertEqual((lease["heartbeat_age_minutes"], lease["fresh"]), (age, fresh), minute)
        code, data = self.run_record("check")
        self.assertEqual((code, data["blocking"], [(f["file"], f["field"]) for f in data["warnings"]]),
                         (2, [], [(".work/lock.json", "heartbeat_at")]))
        self.assertIn("heartbeat 6 minutes ahead of this machine's clock: the clocks disagree", data["warnings"][0]["problem"])
        held = [f for f in self.run_record("lease", "take", "--strand", "002")[1]["refusals"] if f["field"] == "state"][0]
        self.assertIn("6 minutes ahead of this machine's clock", held["problem"])
        self.assertIn("(its heartbeat is not fresh: the clocks disagree)", held["expected"])
        self.assertEqual(self.ok(*self.breaking())["epoch"], 3)  # condition 1 holds; the fence guards the rest
        self.now = datetime(2026, 11, 5, 14, 16, tzinfo=timezone.utc)
        self.assertEqual(self.check()[0], 0)


class VersionTest(Part2):

    def test_C158_C159_G23_G25_open_takes_its_purpose_from_the_number(self):
        data = self.ok("version", "open", "--strand", "001")
        self.assertEqual((data["version"], data["qualified_version"], data["purpose"]), ("v0.2", "001/v0.2", "proof-of-concept"))
        fields = self.fm(S1 + "/versions/v0.2/version.md")
        self.assertEqual({k: fields[k] for k in ("strand", "version", "qualified_version", "state", "purpose", "revision",
                                                 "opened", "shown", "signed_off")},
                         {"strand": "001", "version": "v0.2", "qualified_version": "001/v0.2", "state": "planned",
                          "purpose": "proof-of-concept", "revision": "none", "opened": mc.stamp("date"), "shown": "none",
                          "signed_off": "none"})
        self.assertEqual((self.fm(S1 + "/STRAND.md")["version"], self.fm(S1 + "/STRAND.md")["version_state"]),
                         ("v0.2", "planned"))
        self.assertIn("| 001 | Job tracking | platform | active | v0.2 | planned |", mc.read_text(self.root / "CLIENT.md"))
        self.assertEqual(self.entries()[0].split("\n")[:2], ["## %s · 001 · version · v0.2 · opened" % mc.stamp("log"),
                                                             "purpose: proof-of-concept · state: planned"])
        self.assertEqual(self.check(), (2, set(), {(S1 + "/versions/v0.2/version.md", "planned")}))  # no revision yet
        for version, purpose in (("v0.9", "proof-of-concept"), ("v1.0", "working-solution"), ("v1.1", "working-solution")):
            self.assertEqual(self.ok("version", "open", "--strand", "001", "--version", version)["purpose"], purpose)
        for version in ("v0.5", "v1.1", "v01.2", "1.2"):
            self.assertEqual(self.refused("version", "open", "--strand", "001", "--version", version),
                             {(S1 + "/STRAND.md", "version")}, version)
        self.assertEqual(self.ok("version", "open", "--strand", "002")["version"], "v0.1")
        self.edit_fm(S2 + "/STRAND.md", kind="non-platform", state="closed")
        self.assertEqual(self.refused("version", "open", "--strand", "002"), {(S2 + "/STRAND.md", "kind"),
                                                                             (S2 + "/STRAND.md", "state")})

    def test_C160_C165_G16_G20_shown_is_kept_each_time(self):
        self.edit_fm(S1 + "/STRAND.md", stage="audited")
        first = self.ok("version", "mark", "shown", "--strand", "001", "--audience", "the owner",
                        "--words", "showed it to the owner")
        self.assertEqual((first["stage"], first["date"], first["recorded"]), ("shown", mc.stamp("date"), True))
        self.ok("version", "mark", "shown", "--strand", "001", "--date", "2026-11-06", "--audience", "the workshop lead",
                "--account", "example-account", "--words", "the lead tried the board")
        fields, text = self.fm(V1 + "/version.md"), mc.read_text(self.root / V1 / "version.md")
        self.assertEqual((fields["shown"], fields["state"]), ("2026-11-03; %s; 2026-11-06" % mc.stamp("date"), "audited"))
        self.assertEqual(re.findall(r"(?m)^### (.+)$", text), ["shown 2026-11-03", "shown " + mc.stamp("date"),
                                                                "shown 2026-11-06"])
        self.assertTrue(text.endswith('### shown 2026-11-06\n- audience: the workshop lead\n- account: example-account\n'
                                      '- words: "the lead tried the board"\n'))
        self.assertEqual((self.fm(S1 + "/STRAND.md")["stage"], self.fm(S1 + "/STRAND.md")["version_state"]),
                         ("shown", "audited"))
        self.assertEqual(self.entries()[0], '## %s · 001 · shown · v0.1 · 2026-11-06\naudience: the workshop lead · '
                         'account: example-account\nwords: "the lead tried the board"\n\n' % mc.stamp("log"))
        self.assertEqual(self.check()[0], 0)

    def test_C161_C162_C163_C164_C165_G21_G22_G23_signed_off_warns_then_records(self):
        argv = ("version", "mark", "signed-off", "--strand", "001", "--by", "the owner", "--words", "this is our system")
        before = self.tree()
        code, data = self.run_record(*argv)
        self.assertEqual((code, data["ok"], data["recorded"]), (2, True, False))
        self.assertEqual(data["unconfirmed"], [{"statement": ASSUMED, "kind": "automation-condition", "question":
                                                "When the last cutting-list line of a job is ticked, should the job "
                                                "move to ready to install on its own?"}])
        self.assertEqual(self.tree(), before)
        code, data = self.run_record(*argv + ("--go-on",))
        self.assertEqual((code, data["recorded"], data["stage"], data["purpose"]),
                         (2, True, "signed-off", "proof-of-concept"))
        self.assertIn("record.py version open --version v1.0", data["next"])  # G23, the recommended default
        fields, text = self.fm(V1 + "/version.md"), mc.read_text(self.root / V1 / "version.md")
        self.assertEqual((fields["signed_off"], fields["state"], fields["purpose"]), (mc.stamp("date"), "audited",
                                                                                      "proof-of-concept"))
        self.assertTrue(text.endswith('### signed-off %s\n- by: the owner\n- words: "this is our system"\n'
                                      '- unconfirmed structural assumptions:\n  - %s [kind: automation-condition; '
                                      'state: assumed]\n' % (mc.stamp("date"), ASSUMED)))
        self.assertEqual(self.entries()[0].split("\n")[:3], [
            "## %s · 001 · signed-off · v0.1 · %s" % (mc.stamp("log"), mc.stamp("date")),
            "by: the owner · unconfirmed structural assumptions: 1", 'words: "this is our system"'])
        self.assertEqual((self.fm(S1 + "/STRAND.md")["stage"], self.fm(S1 + "/STRAND.md")["version_state"]),
                         ("signed-off", "audited"))
        self.assertEqual(self.check()[0], 0)
        self.ok("version", "mark", "shown", "--strand", "001", "--audience", "the owner", "--words", "again")
        self.assertEqual(self.fm(S1 + "/STRAND.md")["stage"], "signed-off")  # G16
        readiness = self.root / S1 / "readiness.md"
        readiness.write_text(readiness.read_text(encoding="utf-8").replace("state: assumed]\n  question: When",
                                                                           "state: accepted]\n  question: When"),
                             encoding="utf-8")
        code, data = self.run_record(*argv)
        self.assertEqual((code, data["recorded"], data["unconfirmed"]), (0, True, []))
        self.assertTrue(mc.read_text(self.root / V1 / "version.md").endswith("- unconfirmed structural assumptions: none\n"))

    def test_G24_mark_preconditions_and_values(self):
        base = ("version", "mark", "shown", "--strand", "001", "--audience", "the owner", "--words", "w")
        self.assertEqual(self.refused("version", "mark", "shown", "--strand", "002", "--audience", "a", "--words", "w"),
                         {(S2 + "/STRAND.md", "version")})
        for extra, field in ((("--date", "2026-02-30"), "date"), (("--version", "v0.7"), "version")):
            self.assertIn(field, {f for _, f in self.refused(*base + extra)})
        self.assertEqual(self.refused("version", "mark", "demo", "--strand", "001", "--by", "x", "--words", "w"),
                         {(S1 + "/STRAND.md", "event")})
        self.assertEqual(self.refused("version", "mark", "signed-off", "--strand", "001", "--words", "w"),
                         {(V1 + "/version.md", "by")})
        self.assertEqual(self.refused("version", "mark", "shown", "--strand", "001", "--audience", "a"),
                         {(V1 + "/version.md", "words")})
        self.ok("version", "open", "--strand", "001")
        self.assertEqual(self.refused(*base), {(S1 + "/versions/v0.2/version.md", "state")})


class ReleaseTest(Part2):

    def plans(self, entries=None):
        """(condense sha, summary sha) of a fresh pair of plans for strand 001."""
        plan = self.stage(json.dumps(entries if entries is not None else [
            {"file": S1 + "/STRAND.md", "line": CONDENSED, "survives_in": V1 + "/version.md"},
            {"file": S1 + "/readiness.md", "line": "None in round one.", "survives_in": S1 + "/solution/blueprint.md"}]),
            "plan.json")
        condense = self.ok("version", "condense-plan", "--strand", "001", "--from", plan)["sha256"]
        summary = self.ok("strand", "summary", "--strand", "001", "--plan", self.stage(summary_draft(
            "W1, B1 and B1.V1 of 001/v0.1."), "draft.md"))["sha256"]
        return condense, summary

    def releasing(self, condense, summary, *extra):
        return ("version", "release", "--strand", "001", "--condense-plan-sha", condense, "--summary-plan-sha", summary) + extra

    def test_C166_C171_release_and_condense_wait_for_any_lease(self):
        plan = self.stage("[]", "plan.json")
        self.assertEqual(self.refused("version", "condense-plan", "--strand", "001", "--from", plan),
                         {(".work/lock.json", "state")})
        self.assertIn((".work/lock.json", "state"), self.refused(*self.releasing("0" * 64, "0" * 64)))
        self.release_fixture_lease()
        self.append(S1 + "/solution/backlog.md", BACKLOG)
        condense, summary = self.plans()
        self.ok("version", "open", "--strand", "002")
        self.ok("lease", "take", "--strand", "002")
        self.assertEqual(self.refused(*self.releasing(condense, summary)), {(".work/lock.json", "state")})
        self.assertEqual(self.refused("version", "condense-apply", "--strand", "001", "--plan-sha", condense),
                         {(".work/lock.json", "state")})

    def test_C167_C168_release_lists_what_is_missing(self):
        self.release_fixture_lease()
        condense, summary = self.plans([])
        self.assertEqual(self.refused(*self.releasing(condense, summary)),
                         {(S1 + "/solution/backlog.md", "released")})
        self.append(S1 + "/solution/backlog.md", BACKLOG)
        (self.root / V1 / "audit.md").unlink()
        self.assertEqual(self.refused(*self.releasing("0" * 64, summary)),
                         {(V1 + "/audit.md", "audited"), (".work/strands/001-job-tracking/condense-plan.json", "sha256")})
        shutil.copy(FIXTURES / "home" / "clients" / "larkmoor-joinery" / V1 / "audit.md", self.root / V1 / "audit.md")
        self.edit_fm(V1 + "/version.md", state="built")
        self.assertEqual(self.refused(*self.releasing(condense, summary)), {(V1 + "/version.md", "state")})
        self.edit_fm(V1 + "/version.md", state="audited")
        self.assertEqual(self.run_record(*self.releasing(condense, summary))[0], 0)

    def test_C168_v1_0_releases_only_with_its_signed_off_event(self):
        self.release_fixture_lease()
        v1 = S1 + "/versions/v1.0"
        shutil.copytree(self.root / V1, self.root / v1)
        self.edit_fm(v1 + "/version.md", version="v1.0", qualified_version="001/v1.0", purpose="working-solution",
                     shown="none")
        self.edit_json(S1 + "/solution/build.json", lambda b: b["approvals"].append(dict(b["approvals"][0], version="v1.0")))
        for kind, key in (("approval", "r1"), ("build", "run-2026-11-05-1")):
            self.ok("log", "--strand", "001", "--type", kind, "--version", "v1.0", "--key", key, "--line", "for v1.0")
        self.edit_fm(S1 + "/STRAND.md", version="v1.0", version_state="audited")
        self.append(S1 + "/solution/backlog.md", BACKLOG)
        condense, summary = self.plans([])
        self.assertEqual(self.refused(*self.releasing(condense, summary)), {(v1 + "/version.md", "signed_off")})
        signed = self.run_record("version", "mark", "signed-off", "--strand", "001", "--by", "the owner", "--words",
                                 "our system", "--go-on")
        self.assertEqual((signed[0], signed[1]["recorded"], signed[1]["purpose"]), (2, True, "working-solution"))
        self.assertEqual(self.run_record(*self.releasing(condense, summary))[0], 0)
        self.assertEqual(self.fm(v1 + "/version.md")["state"], "released")
        self.assertEqual(self.check()[:2], (0, set()))

    def test_C169_C170_C171_G08_G26_release_freezes_rolls_condenses_and_summarises(self):
        self.release_fixture_lease()
        self.append(S1 + "/solution/backlog.md", BACKLOG)
        for entries, field in (([{"file": S1 + "/STRAND.md", "line": CONDENSED}], "entry 1"),
                               ([{"file": S1 + "/STRAND.md", "line": "not in the file", "survives_in": "log.md"}], "entry 1"),
                               ([{"file": V1 + "/version.md", "line": "## Scope", "survives_in": "log.md"}], "entry 1"),
                               ([{"file": S1 + "/STRAND.md", "line": CONDENSED, "survives_in": S1 + "/STRAND.md"}],
                                "entry 1"), ({"file": "x"}, "entries")):
            plan = self.stage(json.dumps(entries), "bad.json")
            self.assertEqual({f for _, f in self.refused("version", "condense-plan", "--strand", "001", "--from", plan)},
                             {field}, entries)
        condense, summary = self.plans()
        sources = {name: (self.root / S1 / "solution" / name).read_bytes() for name in ("build.json", "backlog.md")}
        moved = [e for e in self.entries() if re.match(r"## \S+ \S+ · 001 · [a-z-]+ · v0\.1 · ", e)]
        before = mc.split_front_matter(mc.read_text(self.root / S1 / "readiness.md"))[1].split("\n")
        code, data = self.run_record(*self.releasing(condense, summary))
        self.assertEqual((code, data["release_checks"], data["entries"], data["condensed_lines"]), (0, [], len(moved), 2))
        for name, raw in sources.items():
            self.assertEqual((self.root / V1 / name).read_bytes(), raw)
        self.assertEqual([e.rstrip("\n") for e in self.entries(V1 + "/log.md")], [e.rstrip("\n") for e in moved])
        self.assertEqual(self.headers(1), ["## %s · 001 · release · v0.1 · released" % mc.stamp("log")])
        self.assertIn("rolled_to: %s/log.md\nentries: %d · sha256: %s\n" % (V1, len(moved), data["sha256"]), self.entries()[0])
        self.assertFalse([e for e in self.entries() if re.match(r"## \S+ \S+ · 001 · [a-z-]+ · v0\.1 · (?!released)", e)])
        version, strand = self.fm(V1 + "/version.md"), self.fm(S1 + "/STRAND.md")
        self.assertEqual((version["state"], version["released"]), ("released", mc.stamp("date")))
        self.assertEqual((strand["version_state"], strand["summary_current_to"]), ("released", "v0.1"))
        text = mc.read_text(self.root / S1 / "SUMMARY.md")
        self.assertEqual((mc.front_matter(text)["summary_current_to"], mc.front_matter(text)["versions"]), ("v0.1", "v0.1"))
        self.assertLessEqual(len(text.splitlines()), 80)
        self.assertNotIn(CONDENSED, mc.read_text(self.root / S1 / "STRAND.md"))
        stored = json.loads((self.root / ".work" / "strands" / "001-job-tracking" / "condense-plan.json").read_text(encoding="utf-8"))
        self.assertTrue(all((self.root / entry["survives_in"]).is_file() for entry in stored["entries"]))
        after = mc.split_front_matter(mc.read_text(self.root / S1 / "readiness.md"))[1].split("\n")
        self.assertEqual([line for line in before if line not in after], ["None in round one."])
        self.assertEqual(self.check()[:2], (0, set()))
        self.assertTrue({(V1 + "/version.md", "state"), (V1 + "/build.json", "released")}
                        <= self.refused(*self.releasing(condense, summary)))

    def test_C171_G25_condense_apply_alone(self):
        self.release_fixture_lease()
        condense = self.plans()[0]
        self.assertEqual(self.refused("version", "condense-apply", "--strand", "001", "--plan-sha", "0" * 64),
                         {(".work/strands/001-job-tracking/condense-plan.json", "sha256")})
        data = self.ok("version", "condense-apply", "--strand", "001", "--plan-sha", condense)
        self.assertEqual((data["lines"], data["files"]), (2, [S1 + "/STRAND.md", S1 + "/readiness.md"]))
        self.assertNotIn(CONDENSED, mc.read_text(self.root / S1 / "STRAND.md"))
        self.assertEqual(len(list((self.root / ".work" / "backup" / S1).glob("STRAND.md.*"))), 1)
        self.assertEqual(self.entries()[0].split("\n")[:2], ["## %s · 001 · version · - · condensed" % mc.stamp("log"),
                                                             "lines: 2 · files: 2 · plan: %s" % condense])
        self.assertEqual(self.refused("version", "condense-apply", "--strand", "001", "--plan-sha", condense),
                         {(S1 + "/STRAND.md", "sha256"), (S1 + "/readiness.md", "sha256")})
        self.assertEqual(self.check()[0], 0)


class CardTest(Part2):

    def test_C172_G25_G39_card_copies_the_client_card_to_the_home(self):
        self.assertEqual(self.refused("card", "--strand", "001"), {("client-card.md", "file")})
        card = '---\nschema: "client-card/1"\n---\nInternal: never client-facing\n\n# Larkmoor Joinery\n'
        self.append("client-card.md", card)
        data = self.ok("card", "--strand", "002")
        target = self.home / "cards" / "larkmoor-joinery.md"
        self.assertEqual((data["card"], data["replaced"], target.read_bytes()), ("cards/larkmoor-joinery.md", False,
                                                                                card.encode("utf-8")))
        self.assertEqual(self.entries()[0], "## %s · - · closeout · - · card\ncopied to cards/larkmoor-joinery.md · "
                         "sha256: %s · asked_by: 002\n\n" % (mc.stamp("log"), data["sha256"]))
        self.append("client-card.md", "One more line.\n")
        self.assertTrue(self.ok("card", "--strand", "001")["replaced"])
        backups = list((self.root / ".work" / "backup" / "home" / "cards").glob("larkmoor-joinery.md.*"))
        self.assertEqual([b.read_bytes() for b in backups], [card.encode("utf-8")])
        self.assertEqual(self.refused("card", "--strand", "009"), {("strands/", "strand")})
        self.assertEqual(self.check()[0], 0)


class HomeInitTest(Part2):
    """Stage 3 accepts these with WP7's templates; they run here against the stand-ins."""

    def home_init(self, *argv, home=None):
        home = home or self.tmp / "new home"
        with mock.patch.dict(os.environ, {"MMB_HOME": str(home)}):
            return self.run_at(None, "home", "init", *argv)

    def test_C28_C29_C31_C32_C33_G34_G58_a_first_run_builds_the_home(self):
        code, data = self.home_init(*ANSWERS, "--never-show", "40000002=Internal Planning")
        home = self.tmp / "new home"
        self.assertEqual((code, data["settings"], data["archive"]), (0, "written", "local"))
        self.assertEqual(sorted(p.name for p in home.iterdir()), sorted(mc.HOME_FOLDERS))
        settings = json.loads((home / "local" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings, {"schema": "settings/1", "created": mc.stamp("date"), "plugin_version": "0.1.0",
                                    "firm": {"name": "Example Consulting", "renderings": ["Example Consulting",
                                                                                          "example-consulting"]},
                                    "default_build_account": {"slug": "example-account", "id": "10000001"},
                                    "never_show_workspaces": [{"id": "40000002", "name": "Internal Planning"}],
                                    "archive": "local"})
        self.assertEqual(list(settings), ["schema", "created", "plugin_version", "firm", "default_build_account",
                                          "never_show_workspaces", "archive"])
        for name in ("leak-terms.txt", "sandbox-accounts.txt"):
            self.assertEqual((home / "local" / name).read_bytes(), b"")
        self.assertEqual((home / "sandbox" / "SANDBOX.md").read_bytes(),
                         (FIXTURES / "plugin" / "templates" / "other" / "SANDBOX.md").read_bytes())
        self.assertEqual(sorted(data["checks"]), ["connector", "plugin_root", "python"])
        self.assertEqual((data["checks"]["python"]["ok"], data["checks"]["plugin_root"]["plugin_version"]), (True, "0.1.0"))
        self.assertIn("checked by the session", data["checks"]["connector"])
        self.assertNotIn(b"\r", (home / "local" / "settings.json").read_bytes())
        with mock.patch.dict(os.environ, {"MMB_HOME": str(home)}):
            self.assertEqual(self.check()[0], 0)  # the fixture record reads the new settings without a finding

    def test_C30_C34_the_GitHub_archive_alone_stores_an_account_and_checks_the_tools(self):
        for extra in (("--github-account", "example-handle"), ("--archive", "github")):
            code, data = self.home_init(*ANSWERS + extra)
            self.assertEqual((code, [f["field"] for f in data["refusals"]]), (1, ["github_account"]), extra)
        self.assertFalse((self.tmp / "new home").exists())
        with mock.patch.object(self.rec.shutil, "which", side_effect=lambda tool: "found" if tool == "git" else None):
            code, data = self.home_init(*ANSWERS, "--archive", "github", "--github-account", "example-handle")
        self.assertEqual((code, data["checks"]["git"], data["checks"]["gh"]), (2, "found", "absent"))
        self.assertEqual([(w["file"], w["field"]) for w in data["warnings"] if w["field"] == "archive"], [("gh", "archive")])
        settings = json.loads((self.tmp / "new home" / "local" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual((settings["archive"], settings["github_account"]), ("github", "example-handle"))
        code, data = self.home_init(*ANSWERS, home=self.tmp / "local home")
        self.assertNotIn("github_account", (self.tmp / "local home" / "local" / "settings.json").read_text(encoding="utf-8"))
        self.assertFalse({"git", "gh"} & set(data["checks"]))

    def test_C36_G33_a_rerun_keeps_the_settings_unless_update_names_an_answer(self):
        self.home_init(*ANSWERS)
        path = self.tmp / "new home" / "local" / "settings.json"
        path.write_bytes(path.read_bytes().replace(b'"local"', b'"local" '))  # a hand edit
        kept = path.read_bytes()
        code, data = self.home_init("--firm-name", "Other Firm")
        self.assertEqual((code, data["settings"], path.read_bytes()), (0, "kept", kept))
        self.assertIn("--update", data["to_change"])
        self.assertEqual(data["created"], [])
        self.assertEqual({f["field"] for f in self.home_init("--update")[1]["refusals"]}, {"update"})
        code, data = self.home_init("--update", "--firm-name", "Other Firm", "--archive", "github", "--github-account",
                                    "example-handle")
        settings = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((data["settings"], settings["firm"], settings["github_account"]),
                         ("updated", {"name": "Other Firm", "renderings": ["Example Consulting", "example-consulting"]},
                          "example-handle"))
        self.assertEqual((settings["created"], settings["default_build_account"]["id"]), (mc.stamp("date"), "10000001"))
        self.assertEqual([p.read_bytes() for p in (self.tmp / "new home" / "local" / "backup").iterdir()], [kept])
        self.home_init("--update", "--archive", "local")
        self.assertNotIn("github_account", json.loads(path.read_text(encoding="utf-8")))

    def test_C35_G37_a_CLAUDE_md_above_the_clients_folder_is_named(self):
        """Windows run: the walk goes up to the drive's root there."""
        code, data = self.home_init(*ANSWERS)
        tmp = str(self.tmp.absolute())
        self.assertNotIn(tmp, [w["file"] for w in data["warnings"]])
        (self.tmp / "new home" / "clients" / "x").mkdir()
        (self.tmp / "new home" / "clients" / "x" / "CLAUDE.md").write_text("a client's own\n", encoding="utf-8")
        (self.tmp / "CLAUDE.md").write_text("instructions a client session would inherit\n", encoding="utf-8")
        code, data = self.home_init()
        found = [w for w in data["warnings"] if w["field"] == "CLAUDE.md"]
        self.assertEqual(code, 2)
        self.assertIn(tmp, [w["file"] for w in found])
        self.assertFalse([w for w in found if "clients" in w["file"]])
        self.assertEqual(found[0]["expected"], "no CLAUDE.md above the clients folder")

    def test_C38_G35_a_home_of_the_users_choosing(self):
        """Windows run: the printed line there is setx."""
        self.assertEqual(self.refused("home", "init", *ANSWERS, "--home", str(self.tmp / "chosen")), {("MMB_HOME", "home")})
        chosen = self.tmp / "chosen home"
        with mock.patch.dict(os.environ):
            del os.environ["MMB_HOME"]
            self.assertEqual(self.run_at(None, "home", "init", *ANSWERS, "--home", "relative home")[0], 1)
            code, data = self.run_at(None, "home", "init", *ANSWERS, "--home", str(chosen))
        self.assertEqual((code, data["home"]), (0, str(chosen)))
        self.assertTrue((chosen / "local" / "settings.json").is_file())
        self.assertEqual(data["set_mmb_home"]["env"], {"MMB_HOME": str(chosen)})
        self.assertIn(str(chosen), data["set_mmb_home"]["this_system"])

    def test_G31_a_missing_template_cannot_run_and_writes_nothing(self):
        with mock.patch.object(self.rec, "TEMPLATES", self.tmp / "no templates" / "record"):
            code, data = self.home_init(*ANSWERS)
        self.assertEqual((code, data["error"]["file"]), (3, "templates/other/SANDBOX.md"))
        self.assertFalse((self.tmp / "new home").exists())


class InitTest(Part2):
    """Stage 3 accepts these with WP7's templates; they run here against the stand-ins."""

    def test_C39_C40_C41_C42_C82_init_builds_a_record_that_checks_clean(self):
        with mock.patch.object(mc, "lease_init", wraps=mc.lease_init) as primitive:
            data = self.run_at(None, "init", "--slug", "fresh-client", *INIT)[1]
        root = self.home / "clients" / "fresh-client"
        self.assertEqual((data["ok"], data["folder"], data["archive"], primitive.call_count), (True, "strands/001-orders",
                                                                                              "local", 1))
        self.assertEqual(data["files"], ["CLAUDE.md", "CLIENT.md", "account.json", "log.md", "strands/001-orders/STRAND.md",
                                         "strands/001-orders/readiness.md", "strands/001-orders/solution/build.json",
                                         "strands/001-orders/solution/exclusions.md"])
        self.assertEqual(self.run_at(root, "check")[1], {"ok": True, "command": "check", "blocking": [], "warnings": []})
        client = mc.front_matter(mc.read_text(root / "CLIENT.md"))
        account = json.loads((root / "account.json").read_text(encoding="utf-8"))
        build = json.loads((root / "strands" / "001-orders" / "solution" / "build.json").read_text(encoding="utf-8"))
        self.assertEqual({client[k] for k in ("monday_account_id", "monday_account_slug", "monday_bound_user_id",
                                              "monday_bound_at")} | {account["account"]["id"], build["account_id_at_bind"]},
                         {"unbound"})
        self.assertEqual((client["slug"], client["name"], client["current_strand"], client["lease"]),
                         ("fresh-client", "Fresh Client", "001", "none"))
        self.assertEqual({client[k] for k in ("transcripts_at_close", "transcript_redaction", "sample_data_in_account")},
                         {"unanswered"})
        self.assertEqual((account["client_slug"], build["strand"], build["client_slug"]), ("fresh-client", "001",
                                                                                          "fresh-client"))
        instructions = (root / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(instructions.splitlines()), 10)
        for part in ("Read CLIENT.md first", "fresh session for a build or an audit",
                     "Nothing is written into monday except through the build command"):
            self.assertIn(part, instructions)
        lock = json.loads((root / ".work" / "lock.json").read_text(encoding="utf-8"))
        self.assertEqual((lock["state"], lock["epoch"], lock["history"]), ("released", 0, []))
        self.assertEqual([e.split("\n")[:2] for e in re.split(r"(?m)^(?=## \d{4}-)", mc.read_text(root / "log.md"))[1:]],
                         [["## %s · 001 · strand · - · opened" % mc.stamp("log"),
                           "kind: platform · reason: the first call asked for one place for orders"],
                          ["## %s · - · created · - · fresh-client" % mc.stamp("log"),
                           "record created; build target own-account; archive local"]])
        self.assertFalse((root / ".gitignore").exists())
        taken = self.run_at(root, "lease", "take", "--strand", "001")
        self.assertEqual(taken[0], 1)  # the strand has no version yet
        self.assertEqual(self.run_at(root, "version", "open", "--strand", "001")[0], 0)
        self.assertEqual(self.run_at(root, "lease", "take", "--strand", "001")[1]["epoch"], 1)

    def test_C43_a_gitignore_only_on_the_GitHub_archive_path(self):
        settings = self.home / "local" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        data.update(archive="github", github_account="example-handle")
        settings.write_text(mc.json_text(data), encoding="utf-8")
        new = self.tmp / "github-client"
        code, result = self.run_at(new, "init", "--slug", "github-client", *INIT)
        self.assertEqual((code, result["archive"]), (0, "github"))
        self.assertEqual((new / ".gitignore").read_bytes(),
                         (FIXTURES / "plugin" / "templates" / "record" / "client-gitignore.txt").read_bytes())
        self.assertEqual(self.run_at(new, "check")[0], 0)

    def test_C44_G56_the_slug_rule_and_an_occupied_folder(self):
        clients = sorted(p.name for p in (self.home / "clients").iterdir())
        for slug in ("a" * 41, "Fresh-Client", "café", "a--b"):
            code, data = self.run_at(None, "init", "--slug", slug, *INIT)
            self.assertEqual((code, [(f["file"], f["field"]) for f in data["refusals"]]), (1, [("CLIENT.md", "slug")]), slug)
        self.assertEqual(self.run_at(None, "init", "--slug", "a" * 40, *INIT)[0], 0)
        self.assertEqual(sorted(p.name for p in (self.home / "clients").iterdir()), sorted(clients + ["a" * 40]))
        code, data = self.run_at(None, "init", "--slug", "larkmoor-joinery", *INIT)
        self.assertEqual((code, [f["field"] for f in data["refusals"]]), (1, ["folder"]))
        code, data = self.run_at(self.tmp / "elsewhere", "init", "--slug", "fresh-client", *INIT)
        self.assertEqual((code, [f["field"] for f in data["refusals"]]), (1, ["slug"]))
        code, data = self.run_at(None, "init", "--slug", "bad-topic", *INIT[:3] + ("Bad Topic",) + INIT[4:])
        self.assertEqual((code, [f["field"] for f in data["refusals"]]), (1, ["topic"]))
        self.assertFalse((self.home / "clients" / "bad-topic").exists())

    def test_C40_G43_build_json_only_for_a_platform_or_hybrid_first_strand(self):
        for kind, built in (("non-platform", False), ("hybrid", True)):
            argv = list(INIT)
            argv[argv.index("--kind") + 1] = kind
            self.assertEqual(self.run_at(None, "init", "--slug", "client-" + kind, *argv)[0], 0)
            root = self.home / "clients" / ("client-" + kind)
            self.assertEqual((root / "strands" / "001-orders" / "solution" / "build.json").exists(), built)
            self.assertEqual(self.run_at(root, "check")[0], 0)


class LeaseFixTest(Part2):
    """The fixes of the build-lease review: R<n> is the review's finding n."""

    def failing_log(self):
        return mock.patch.object(self.rec, "insert_entries", side_effect=PermissionError(13, "held by another program"))

    def test_R1_C99_C111_status_names_whose_take_comes_next(self):
        self.now = STALE
        self.add_run({"adopt": 1, "duplicate": 2, "partial": 1})
        self.ok("version", "open", "--strand", "002")
        self.assertEqual(self.ok(*self.breaking())["reserved_for"], "001")
        self.assertEqual((self.ok("lease", "status")["reserved_for"],
                          self.run_record("status", "--json")[1]["lease"]["reserved_for"]), ("001", "001"))
        self.assertEqual(self.refused("lease", "take", "--strand", "002"), {(".work/lock.json", "state")})
        self.assertEqual(self.ok("lease", "take", "--strand", "001")["epoch"], 4)

    def test_R4_C87_C98_C109_a_failure_after_the_commit_reports_what_was_committed(self):
        with self.failing_log():
            code, data = self.run_record("lease", "release", "--epoch", "2", "--label", LABEL)
        self.assertEqual((code, data["error"]["field"], data["committed"]["epoch"], data["committed"]["state"]),
                         (3, "committed", 2, "released"))
        self.assertIn("released, epoch 2", data["committed"]["entries"][0])
        with self.failing_log():
            code, data = self.run_record("lease", "take", "--strand", "001")
        label = json.loads((self.root / ".work" / "lock.json").read_text(encoding="utf-8"))["session_label"]
        self.assertEqual((code, data["committed"]["epoch"], data["committed"]["session_label"]), (3, 3, label))
        self.assertIn("hold epoch 3 and session label %s" % label, data["error"]["expected"])
        self.now = STALE
        with self.failing_log():
            code, data = self.run_record(*self.breaking(epoch="3", label=label))
        self.assertEqual((code, data["committed"]["epoch"], data["committed"]["choice"], len(data["committed"]["entries"])),
                         (3, 4, "resume", 3))

    def test_R5_C84_G09_lease_sync_heals_the_mirrors_and_a_failed_release_can_be_retried(self):
        real = mc.write_file

        def failing(path, *args, **kwargs):
            if path.name == "account.json":
                raise PermissionError(13, "held by another program")
            return real(path, *args, **kwargs)
        with mock.patch.object(mc, "write_file", failing):
            code, data = self.run_record("lease", "release", "--epoch", "2", "--label", LABEL)
        self.assertEqual((code, data["error"]["file"]), (3, "account.json"))
        self.assertEqual(self.release_fixture_lease()["state"], "released")  # the lock was left as it was
        self.edit_fm("CLIENT.md", lease="001 v0.1 (%s)" % LABEL)
        self.edit_json("account.json", lambda a: a["guard_index"]["lease"].update(epoch=1))
        blocking = self.run_record("check")[1]["blocking"]
        self.assertEqual([("record.py lease sync" in f["expected"]) for f in blocking], [True, True])
        lock = (self.root / ".work" / "lock.json").read_bytes()
        self.assertEqual(sorted(self.ok("lease", "sync")["rewritten"]), ["CLIENT.md", "account.json"])
        self.assertEqual(((self.root / ".work" / "lock.json").read_bytes(), self.check()[:2]), (lock, (0, set())))

    def test_R6_C83_lease_repair_rebuilds_a_torn_lock_for_its_holder(self):
        lock = self.root / ".work" / "lock.json"
        lock.write_bytes(b"")
        code, data = self.run_record("lease", "status")
        self.assertEqual((code, "record.py lease repair" in data["error"]["expected"]), (3, True))
        self.assertEqual(self.refused("lease", "repair"), {(".work/lock.json", "user_yes")})
        data = self.ok("lease", "repair", "--user-yes", "yes, repair the lock")
        self.assertEqual((data["epoch"], data["state"], data["reserved_for"], data["from_backup"]), (3, "broken", "001", "none"))
        self.assertIn("record.py lease take --strand 001", data["next"])
        self.assertEqual(self.check()[:2], (0, set()))
        self.assertIn((".work/lock.json", "state"), self.refused("lease", "take", "--strand", "002"))
        self.assertEqual(self.ok("lease", "take", "--strand", "001")["epoch"], 4)
        self.assertEqual(self.refused("lease", "repair", "--user-yes", "yes"), {(".work/lock.json", "lock")})
        self.assertEqual(sorted((self.root / ".work" / "backup" / ".work").glob("lock.json.*"))[0].read_bytes(), b"")

    def test_R6_C97_lease_repair_keeps_the_newest_sound_backups_history(self):
        self.release_fixture_lease()
        (self.root / ".work" / "lock.json").write_bytes(b'{"schema": "lock/2", "epo')
        data = self.ok("lease", "repair", "--user-yes", "yes, rebuild it")
        lock = json.loads((self.root / ".work" / "lock.json").read_text(encoding="utf-8"))
        self.assertEqual((data["epoch"], data["state"], data["reserved_for"]), (3, "released", None))
        self.assertEqual([e["event"] for e in lock["history"]], ["taken", "released", "taken", "repaired"])
        self.assertEqual(self.ok("lease", "take", "--strand", "001")["epoch"], 4)

    def test_R9_C131_C153_a_malformed_lock_is_a_finding_not_a_crash(self):
        self.edit_json(".work/lock.json", lambda lock: lock.update(heartbeat_at=None))
        self.edit_json("account.json", lambda a: a["guard_index"]["lease"].update(heartbeat_at=None))
        self.assertEqual(self.check()[:2], (1, {(".work/lock.json", "heartbeat_at")}))
        self.assertEqual(self.refused("lease", "take", "--strand", "002"), {(".work/lock.json", "heartbeat_at")})
        code, status = self.run_record("status", "--json")
        self.assertEqual((code, status["lease"]["heartbeat_age_minutes"], status["lease"]["fresh"]), (0, None, None))
        self.assertEqual(self.ok("lease", "repair", "--user-yes", "yes, repair it")["epoch"], 3)
        (self.root / ".work" / "lock.json").write_bytes(b"{}")  # JSON with no schema is malformed too
        self.assertEqual(self.ok("lease", "repair", "--user-yes", "yes, again")["epoch"], 4)

    def test_R15_C44_a_second_init_of_the_slug_writes_nothing(self):
        root, real = self.home / "clients" / "fresh-client", self.rec.strand_files

        def other_init(*args):
            root.mkdir(parents=True)
            (root / "CLIENT.md").write_bytes(b"the other init's CLIENT.md\n")
            return real(*args)
        with mock.patch.object(self.rec, "strand_files", side_effect=other_init):
            code, data = self.run_at(None, "init", "--slug", "fresh-client", *INIT)
        self.assertEqual((code, [f["field"] for f in data["refusals"]]), (1, ["folder"]))
        self.assertEqual((root / "CLIENT.md").read_bytes(), b"the other init's CLIENT.md\n")
        self.assertFalse((root / ".work" / "backup").exists())

class NewerSchemaTest(Part2):

    def test_C13_G57_every_writing_subcommand_refuses_a_newer_schema(self):
        """All 23 writing subcommands (the catalogue less status, check, lease status, strand list, home init and init,
        which write no existing record), each refused with exit 1 and an unchanged tree. Part one runs the first
        eleven and the common tests run the lease primitives; this runs the whole set so none is left out."""
        self.edit_fm("CLIENT.md", schema="client/3")
        sha, zero = mc.sha256_file(self.root / S2 / "STRAND.md"), "0" * 64
        staged, call = self.stage(mc.read_text(self.root / S2 / "STRAND.md")), self.stage(CALL, "call.txt")
        draft, plan = self.stage(summary_draft(), "draft.md"), self.stage("[]", "plan.json")
        calls = (("log", "--strand", "-", "--type", "decision", "--key", "k", "--line", "x"),
                 ("guard", "--file", S2 + "/STRAND.md", "--expect-sha", sha, "--from", staged),
                 ("add-transcript", "--strand", "001", "--from", call, "--type", "intro", "--fixture"),
                 ("add-document", "--strand", "001", "--from", call, "--title", "notes", "--fixture"),
                 ("freeze", "--strand", "001"), ("card", "--strand", "001"),
                 ("strand", "open", "--topic", "x", "--title", "X", "--kind", "platform", "--reason", "r"),
                 ("strand", "pause", "--strand", "002", "--reason", "r"),
                 ("strand", "kind", "--strand", "002", "--kind", "hybrid", "--reason", "r"),
                 ("strand", "close", "--strand", "002"), ("strand", "resume", "--strand", "002"),
                 ("strand", "summary", "--strand", "002", "--plan", draft),
                 ("lease", "take", "--strand", "002"), ("lease", "refresh", "--epoch", "2", "--label", LABEL),
                 ("lease", "release", "--epoch", "2", "--label", LABEL), tuple(self.breaking()),
                 ("lease", "sync"), ("lease", "repair", "--user-yes", "yes, repair the lock"),
                 ("version", "open", "--strand", "001", "--version", "v0.2"),
                 ("version", "mark", "shown", "--strand", "001", "--audience", "the owner", "--words", "w"),
                 ("version", "condense-plan", "--strand", "001", "--from", plan),
                 ("version", "condense-apply", "--strand", "001", "--plan-sha", zero),
                 ("version", "release", "--strand", "001", "--condense-plan-sha", zero, "--summary-plan-sha", zero))
        named = {" ".join(argv[:2]) if argv[0] in ("strand", "lease", "version") else argv[0] for argv in calls}
        self.assertEqual((len(calls), named), (23, set(self.rec.COMMANDS) - {
            "status", "check", "lease status", "strand list", "home init", "init"}))
        for argv in calls:
            self.assertIn(("CLIENT.md", "schema"), self.refused(*argv), argv)


class ErrorTest(Part2):
    """C21: an exit-3 error names the file, the field, the problem and the expected value, each non-empty."""

    @contextlib.contextmanager
    def mutex_held(self):
        held, done = threading.Event(), threading.Event()

        def holder():
            with mc.record_mutex(self.root):
                held.set()
                done.wait(10)
        thread = threading.Thread(target=holder)
        thread.start()
        held.wait(10)
        try:
            with mock.patch.object(mc, "MUTEX_TIMEOUT", 0.2):
                yield
        finally:
            done.set()
            thread.join()

    def cannot_run(self, record, *argv):
        """(file, field) of the error of a run that exits 3; run_at has already asserted all four parts are non-empty."""
        code, data = self.run_at(record, *argv)
        self.assertEqual((code, data["ok"], sorted(data["error"])), (3, False, ["expected", "field", "file", "problem"]))
        return data["error"]["file"], data["error"]["field"]

    def test_C21_every_exit_3_error_names_file_field_problem_and_expected(self):
        account = self.root / "account.json"
        original = account.read_bytes()
        account.write_bytes(b"\xff\xfe not text")
        self.assertEqual(self.cannot_run(self.root, "check"), ("account.json", "(whole file)"))
        account.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.cannot_run(self.root, "check"), ("account.json", "(whole file)"))
        self.assertEqual(self.cannot_run(self.root, "status"), ("account.json", "(whole file)"))
        account.write_bytes(original)
        with self.mutex_held():
            self.assertEqual(self.cannot_run(self.root, "log", "--strand", "-", "--type", "decision", "--key", "k",
                                             "--line", "x"), (".work/record.mutex", "record.mutex"))
        templates = self.tmp / "templates copy" / "record"
        shutil.copytree(FIXTURES / "plugin" / "templates" / "record", templates)
        (templates / "account.json").write_text("{not json", encoding="utf-8")
        with mock.patch.object(self.rec, "TEMPLATES", templates):
            self.assertEqual(self.cannot_run(None, "init", "--slug", "fresh-client", *INIT),
                             ("templates/record/account.json", "(whole file)"))
        self.assertFalse((self.home / "clients" / "fresh-client").exists())
        settings = self.home / "local" / "settings.json"
        settings.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(self.cannot_run(None, "home", "init", "--update", "--firm-name", "Example Consulting"),
                         ("local/settings.json", "(whole file)"))
        for argv in (("status", "--bogus"), ("migrate",), ()):
            self.assertEqual(self.cannot_run(self.root, *argv)[1], "arguments")

    def test_C21_an_unexpected_exception_still_names_all_four_parts(self):
        def fails(root, args):
            raise RuntimeError()  # str() of this is empty
        with mock.patch.dict(self.rec.COMMANDS, {"lease status": fails}):
            self.assertEqual(self.cannot_run(self.root, "lease", "status"), ("record.py", "RuntimeError"))


class Part2FrameTest(Part2):

    def test_C01_C05_C82_part_two_source_rules(self):
        module = ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))
        names = {a.name.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(module) if isinstance(n, ast.ImportFrom)}
        for name in names - {"mmb_common", "test_record"}:
            self.assertTrue(is_stdlib(name), name)
        source = (self.plugin / "scripts" / "record.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertEqual(re.findall(r"shutil\.\w+", source), ["shutil.which"])  # C34: looked up, never run
        self.assertNotIn("Del" + "Ops", Path(__file__).read_text(encoding="utf-8"))

    def test_C18_G49_home_init_and_the_lease_from_a_plugin_copy_write_nothing_there(self):
        """Windows run: the same launch form, with no shell."""
        plugin = make_plugin(self.tmp / "plugin copy")
        before = sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*"))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MMB_HOME=str(self.tmp / "sub home"))

        def launch(*argv):
            done = subprocess.run([sys.executable, str(plugin / "scripts" / "record.py")] + list(argv), env=env,
                                  capture_output=True)
            return done.returncode, json.loads(done.stdout.decode("utf-8"))
        self.assertIn(launch("home", "init", *ANSWERS)[0], (0, 2))
        self.assertEqual(launch("--record", str(self.root), "lease", "status")[1]["epoch"], 2)
        self.assertEqual(sorted(p.relative_to(plugin).as_posix() for p in plugin.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
