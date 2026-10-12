"""Unit tests for tools/cleanroom_scan.py over synthetic fixtures.

The quarantine and the scanned tree live under tests/unit/fixtures/tools/cleanroom/.
"""
import contextlib
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FIXTURES = os.path.join(HERE, "fixtures", "tools", "cleanroom")
QUARANTINE = os.path.join(FIXTURES, "quarantine", "learn-notes.md")
TREE = os.path.join(FIXTURES, "tree")
sys.path.insert(0, os.path.join(REPO, "tools"))
import cleanroom_scan  # noqa: E402


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cleanroom_scan.main(argv)
    return code, out.getvalue()


class CleanroomScanTest(unittest.TestCase):

    def test_finds_copied_prose_with_file_line_and_run(self):
        code, out = run([QUARANTINE, "--tree", TREE])
        self.assertEqual(code, 1)
        self.assertIn("copied.md:7: 25 words shared with", out)
        self.assertIn("learn-notes.md:3: \"the build order starts with the workspace then the folders", out)
        self.assertIn("cleanroom_scan: 1 finding(s)", out)

    def test_wrapped_paragraph_is_one_run_reported_at_its_first_line(self):
        code, out = run([QUARANTINE, "--tree", TREE])
        self.assertEqual(out.count("copied.md:"), 1)
        self.assertIn("only then the automations\"", out)

    def test_identifier_and_enum_lists_are_allowed(self):
        code, out = run([QUARANTINE, "--tree", TREE])
        self.assertNotIn("allowed.md", out)

    def test_seven_shared_words_is_not_a_finding(self):
        code, out = run([QUARANTINE, "--tree", TREE])
        self.assertNotIn("clean.md", out)

    def test_run_length_option(self):
        code, out = run([QUARANTINE, "--tree", TREE, "--words", "30"])
        self.assertEqual(code, 0)
        self.assertIn("0 finding(s)", out)

    def test_quarantine_folder_is_walked(self):
        code, out = run([os.path.dirname(QUARANTINE), "--tree", TREE])
        self.assertEqual(code, 1)
        self.assertIn("copied.md:7:", out)

    def test_single_file_tree(self):
        code, out = run([QUARANTINE, "--tree", os.path.join(TREE, "clean.md")])
        self.assertEqual(code, 0)

    def test_exit_3_when_it_cannot_run(self):
        self.assertEqual(run([])[0], 3)
        self.assertEqual(run([os.path.join(FIXTURES, "absent.md"), "--tree", TREE])[0], 3)
        self.assertEqual(run([QUARANTINE, "--tree", os.path.join(FIXTURES, "absent")])[0], 3)
        self.assertEqual(run([QUARANTINE, "--tree", TREE, "--words", "1"])[0], 3)

    def test_line_classification(self):
        words = cleanroom_scan.line_words
        self.assertIsNone(words("Labels: intro, discovery, demo, sign-off"))
        self.assertIsNone(words("| B1 | board | account-build |"))
        self.assertIsNone(words("|---|---|"))
        self.assertIsNone(words("create_board create_column and"))
        self.assertIsNone(words(""))
        self.assertEqual(words("Call `create_board` with the workspace id, then read it back."),
                         ["call", "with", "the", "workspace", "id", "then", "read", "it", "back"])
        self.assertEqual(words("Use items_page for the read, not v0.1 notes"),
                         ["use", "for", "the", "read", "not", "notes"])

    def test_fenced_code_breaks_paragraphs(self):
        paras = list(cleanroom_scan.paragraphs(["one two", "```", "three four", "```", "five six"]))
        self.assertEqual([[w for w, _ in p] for p in paras], [["one", "two"], ["five", "six"]])
        self.assertEqual(paras[1][0][1], 5)


if __name__ == "__main__":
    unittest.main()
