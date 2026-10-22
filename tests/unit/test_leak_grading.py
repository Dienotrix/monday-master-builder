import sys

sys.dont_write_bytecode = True

"""Grades scripts/leak_lint.py against the leak-trap fixture (WP4, step 6).

Every case of tests/fixtures/leak/manifest.json is built in a fresh temporary home as the manifest's "home" block
says (settings and local list, both records, the overlay, `index` from each record, the case files, the .docx
built from its XML text with zipfile), and the lint runs through main(argv) in process with its output captured.
A planted case needs its exit code, its verdict and every "expect" entry (same rule, severity, class where named,
and place); other findings are not failed. A twin needs its exit code, no block finding and every "expect" entry.
A known limit is asserted as the manifest says it is: not caught, so that a later improvement shows as a change.
Nothing is skipped and nothing is an expected failure: a case that needs a part that is not built fails.
Standard library only; nothing under the real home or the fixture is touched.
"""
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
import zipfile  # noqa: E402
from unittest import mock  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FIX = os.path.join(REPO, "tests", "fixtures", "leak")
SCRIPT = os.path.join(REPO, "plugins", "monday-master-builder", "scripts", "leak_lint.py")
VERDICTS = {0: "clean", 1: "blocked", 2: "warnings", 3: "could-not-run"}

with open(os.path.join(FIX, "manifest.json"), encoding="utf-8") as handle:
    MANIFEST = json.load(handle)
CASES = MANIFEST["cases"]


def load_lint():
    sys.path.insert(0, os.path.dirname(SCRIPT))
    spec = importlib.util.spec_from_file_location("leak_lint_graded", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = load_lint()


def fixture_path(rel):
    return os.path.join(FIX, *rel.split("/"))


def copy_file(src_rel, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(fixture_path(src_rel), dest)


def copy_tree(src_rel, dest):
    """Copy every file under a fixture folder to dest, path for path (overlays land over what is there)."""
    base = fixture_path(src_rel)
    for folder, _dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, base)
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(full, target)


def build_zip(src_rel, dest):
    """Zip every file under a fixture folder, member names relative to it in POSIX spelling."""
    base = fixture_path(src_rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    members = []
    for folder, _dirs, files in os.walk(base):
        for name in files:
            full = os.path.join(folder, name)
            members.append((os.path.relpath(full, base).replace(os.sep, "/"), full))
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for member, full in sorted(members):
            with open(full, "rb") as handle:
                archive.writestr(member, handle.read())


def run_lint(argv):
    """main(argv) in process with stdout captured; returns (exit code, the envelope or None, the raw bytes)."""
    buffer = io.BytesIO()

    class Out:
        def write(self, text):
            buffer.write(text.encode("utf-8"))

        def flush(self):
            pass

    Out.buffer = buffer
    with mock.patch.object(sys, "stdout", Out()):
        code = lint.main(list(argv))
    raw = buffer.getvalue()
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        data = None
    return code, data, raw


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def fixture_hashes():
    out = {}
    for folder, _dirs, files in os.walk(FIX):
        for name in files:
            full = os.path.join(folder, name)
            out[os.path.relpath(full, FIX)] = sha(full)
    return out


def place_matches(finding, where):
    """A finding sits at `where`: the same field, the same .docx part, or a path or a part under it."""
    field = finding.get("field") or ""
    return (field == where or finding.get("part") == where or field.startswith(where + " ") or
            field.startswith(where + "[") or field.startswith(where + "."))


def entry_matched(entry, findings):
    for finding in findings:
        if finding.get("rule") != entry["rule"] or finding.get("severity") != entry["severity"]:
            continue
        if entry.get("class") is not None and finding.get("class") != entry["class"]:
            continue
        if place_matches(finding, entry["where"]):
            return True
    return False


class Case:
    """One case built in a fresh temporary home, and the lint's answer."""

    def __init__(self, case):
        self.case = case
        self.tmp = tempfile.mkdtemp(prefix="leak grading ")
        self.home = os.path.join(self.tmp, "home with space")
        self.canary = os.path.join(self.tmp, "canary")
        os.makedirs(self.canary)
        os.makedirs(self.home)
        self.index_codes = []

    def record_root(self, key):
        return os.path.join(self.home, *MANIFEST["home"]["records"][key]["to"].split("/"))

    def build(self):
        home, case = MANIFEST["home"], self.case
        for key in ("settings", "local_terms"):
            copy_file(home[key]["from"], os.path.join(self.home, *home[key]["to"].split("/")))
        for key in sorted(home["records"]):
            copy_tree(home["records"][key]["from"], self.record_root(key))
        if case["overlay"]:
            copy_tree(home["overlays"][case["overlay"]]["from"], self.record_root(home["overlays"][case["overlay"]]["onto"]))
        env = {"MMB_HOME": self.home, "HOME": self.canary, "USERPROFILE": self.canary}
        with mock.patch.dict(os.environ, env):
            for key in home["index_from"]:
                code, _data, _raw = run_lint(["--record", self.record_root(key), "index"])
                self.index_codes.append((key, code))
        root = self.record_root(case["record"])
        self.installed = []
        for entry in case["install"]:
            dest = os.path.join(root, *entry["to"].split("/"))
            if "zip" in entry:
                build_zip(entry["zip"], dest)
            else:
                copy_file(entry["from"], dest)
            self.installed.append(dest)

    def run(self):
        env = {"MMB_HOME": self.home, "HOME": self.canary, "USERPROFILE": self.canary}
        argv = ["--record", self.record_root(self.case["record"]), self.case["command"]] + list(self.case["args"])
        with mock.patch.dict(os.environ, env):
            return run_lint(argv)

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def describe(data, code):
    if data is None:
        return "exit %s with no readable envelope" % code
    parts = ["exit %s, verdict %s" % (code, data.get("verdict"))]
    if data.get("error"):
        parts.append("error %s: %s" % (data["error"].get("field"), data["error"].get("problem")))
    findings = ["%s/%s/%s at %s" % (f.get("rule"), f.get("class"), f.get("severity"), f.get("field"))
                for f in data.get("findings", [])]
    parts.append("findings: " + ("; ".join(findings[:12]) if findings else "none"))
    return " | ".join(parts)


class LeakGradingTests(unittest.TestCase):

    def test_manifest_counts_and_twins(self):
        self.assertEqual(MANIFEST["schema"], "leak-fixture/1")
        ids = [c["id"] for c in CASES]
        self.assertEqual(len(ids), len(set(ids)))
        planted = [c for c in CASES if c["role"] == "planted"]
        twins = [c for c in CASES if c["role"] == "twin"]
        self.assertEqual(len(CASES), 248)
        self.assertEqual(len(planted), 124)
        self.assertEqual(len(twins), 124)
        by_id = {c["id"]: c for c in CASES}
        for case in planted:
            twin = by_id.get(case["twin"])
            self.assertIsNotNone(twin, case["id"])
            self.assertEqual(twin["role"], "twin", case["id"])
            self.assertEqual(twin["twin_of"], case["id"])
            self.assertEqual(case["id"], twin["id"][:-2] + "-p")
        for case in twins:
            self.assertEqual(by_id[case["twin_of"]]["twin"], case["id"])
        outcomes = {}
        for case in CASES:
            outcomes[case["outcome"]] = outcomes.get(case["outcome"], 0) + 1
        self.assertEqual(outcomes["blocks"], 109)
        self.assertEqual(outcomes["warns"], 3)
        self.assertEqual(outcomes["caution"], 1)
        self.assertEqual(outcomes["limit"], 11)
        self.assertEqual(outcomes["passes"], 124)
        self.assertEqual(sum(1 for c in CASES if c["command"] == "scan"), 166)
        self.assertEqual(sum(1 for c in CASES if c["command"] == "payload"), 80)
        self.assertEqual(sum(1 for c in CASES if c["command"] == "blueprint"), 2)

    def test_index_builds_for_both_records(self):
        """Part 2: the home's index is built from each record in order, each answering exit 0."""
        harness = Case(CASES[0])
        try:
            harness.build()
            self.assertEqual(harness.index_codes, [(key, 0) for key in MANIFEST["home"]["index_from"]])
        finally:
            harness.cleanup()

    def test_every_case(self):
        before = fixture_hashes()
        for case in CASES:
            with self.subTest(case=case["id"]):
                harness = Case(case)
                try:
                    harness.build()
                    unchanged = None
                    if case.get("unchanged"):
                        unchanged = [(p, sha(p)) for p in harness.installed]
                    code, data, _raw = harness.run()
                    answer = describe(data, code)
                    self.assertIsNotNone(data, answer)
                    self.assertEqual(code, case["exit"], answer)
                    self.assertEqual(data["verdict"], case["verdict"], answer)
                    self.assertEqual(data["verdict"], VERDICTS[code], answer)
                    findings = data.get("findings", [])
                    if case["role"] == "twin":
                        self.assertEqual([f for f in findings if f["severity"] == "block"], [], answer)
                    if case["outcome"] == "limit":
                        # The lint is expected not to catch it: no block and no finding the manifest does not name.
                        self.assertEqual([f for f in findings if f["severity"] == "block"], [], answer)
                    if case["outcome"] == "blocks":
                        self.assertTrue([f for f in findings if f["severity"] == "block"], answer)
                    for entry in case["expect"]:
                        self.assertTrue(entry_matched(entry, findings),
                                        "expected %s at %s; %s" % (entry, entry["where"], answer))
                    if unchanged is not None:
                        self.assertEqual([(p, sha(p)) for p, _ in unchanged], unchanged, "the lint changed a file")
                finally:
                    harness.cleanup()
        self.assertEqual(fixture_hashes(), before, "the run changed a fixture file")


if __name__ == "__main__":
    unittest.main()
