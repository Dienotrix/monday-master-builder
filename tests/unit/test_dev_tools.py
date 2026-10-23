"""tools/dev_test_workspace.py: the development-only build target for the named test workspace (A31, demo 1 finding 8)."""
import sys

sys.dont_write_bytecode = True

import importlib.util  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
RECORD = REPO / "tests" / "unit" / "fixtures" / "home" / "clients" / "larkmoor-joinery"
spec = importlib.util.spec_from_file_location("dev_test_workspace", REPO / "tools" / "dev_test_workspace.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class DevTestWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dev tool "))
        self.record = self.tmp / "larkmoor-joinery"
        shutil.copytree(str(RECORD), str(self.record))

    def tearDown(self):
        shutil.rmtree(str(self.tmp))

    def account(self):
        return json.loads((self.record / "account.json").read_text(encoding="utf-8"))

    def test_the_workspace_becomes_a_target_of_the_strand_once(self):
        for _ in range(2):
            tool.target(self.record, "001", "10009999", "core")
        index = self.account()["guard_index"]
        self.assertEqual(index["client_workspace_ids"].count("10009999"), 1)
        self.assertEqual(index["build_targets_by_strand"]["001"]["workspace_ids"].count("10009999"), 1)
        self.assertEqual(index["product_workspaces"]["10009999"], "core")
        raw = (self.record / "account.json").read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"}\n"))

    def test_demo4_a_known_workspace_keeps_its_product_and_another_is_refused(self):
        tool.target(self.record, "001", "10009999", "crm")
        self.assertEqual(tool.target(self.record, "001", "10009999", None)["product"], "crm")
        before = (self.record / "account.json").read_bytes()
        with self.assertRaises(SystemExit):
            tool.target(self.record, "001", "10009999", "core")
        self.assertEqual((self.record / "account.json").read_bytes(), before)
        self.assertEqual(tool.target(self.record, "001", "10008888", None)["product"], "core")

    def test_bad_input_and_an_unbound_record_are_refused_with_nothing_written(self):
        before = (self.record / "account.json").read_bytes()
        for args in (("001", "012", "core"), ("1", "10009999", "core"), ("001", "10009999", "native")):
            with self.assertRaises(SystemExit):
                tool.target(self.record, *args)
        data = self.account()
        data["account"]["id"] = "unbound"
        (self.record / "account.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        unbound = (self.record / "account.json").read_bytes()
        with self.assertRaises(SystemExit):
            tool.target(self.record, "001", "10009999", "core")
        self.assertEqual((self.record / "account.json").read_bytes(), unbound)
        self.assertNotEqual(before, b"")


if __name__ == "__main__":
    unittest.main()
