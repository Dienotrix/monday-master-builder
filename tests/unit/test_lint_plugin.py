"""Unit tests for tools/lint_plugin.py over two synthetic plugin trees.

tests/unit/fixtures/tools/lint-clean/ passes every check; lint-bad/ carries one
fault per check. Size faults are generated into a temporary copy. The shared-region
check (WP4 R41) runs on the real tree and on temporary copies of it. MMB_HOME is
always a temporary folder, so no test reads the user's real files.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FIXTURES = os.path.join(HERE, "fixtures", "tools")
sys.path.insert(0, os.path.join(REPO, "tools"))
import lint_plugin  # noqa: E402

PLUGIN = os.path.join("plugins", "monday-master-builder")


def run(argv, home):
    out = io.StringIO()
    with mock.patch.dict(os.environ, {"MMB_HOME": home}), contextlib.redirect_stdout(out):
        code = lint_plugin.main(argv)
    return code, out.getvalue()


class LintPluginTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mmb-lint-")
        cls.home = os.path.join(cls.tmp, "home")
        cls.empty_home = os.path.join(cls.tmp, "empty-home")
        os.makedirs(cls.home)
        os.makedirs(cls.empty_home)
        hashes = [lint_plugin.name_hash("Talwar"), lint_plugin.name_hash("Priya Talwar")]
        with open(os.path.join(cls.home, lint_plugin.NAMES_INDEX), "w", encoding="utf-8") as handle:
            json.dump({"schema": "names-index/1", "hashes": hashes}, handle)
        cls.bad_code, cls.bad = run(["--root", os.path.join(FIXTURES, "lint-bad")], cls.home)
        cls.clean_code, cls.clean = run(["--root", os.path.join(FIXTURES, "lint-clean")], cls.home)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def copy_clean(self, name):
        dest = os.path.join(self.tmp, name)
        shutil.copytree(os.path.join(FIXTURES, "lint-clean"), dest)
        return dest

    def test_clean_tree_passes(self):
        self.assertEqual(self.clean_code, 0, self.clean)
        self.assertNotIn("error:", self.clean)
        self.assertNotIn("warning:", self.clean)
        # The stand-in leak_lint.py has no shared regions, so that check is the only one not present yet.
        self.assertIn("0 error(s), 0 warning(s), 2 not present yet", self.clean)

    def test_bad_tree_fails(self):
        self.assertEqual(self.bad_code, 1)

    def test_description_length_and_angle_brackets(self):
        root = self.copy_clean("long")
        skill = os.path.join(root, PLUGIN, "skills", "wordy")
        os.makedirs(os.path.join(skill, "references"))
        body = ["---", 'name: "wordy"', 'description: "%s"' % ("x" * 801), "---"]
        with open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(body + ["line"] * 187) + "\n")
        with open(os.path.join(skill, "references", "long.md"), "w", encoding="utf-8") as handle:
            handle.write("line\n" * 191)
        code, out = run(["--root", root], self.home)
        self.assertEqual(code, 1)
        self.assertIn("skills/wordy/SKILL.md:3: description: over 800 characters (801)", out)
        self.assertIn("skills/wordy/SKILL.md:191: size: over 190 lines (191)", out)
        self.assertIn("skills/wordy/references/long.md:191: size: over 190 lines (191)", out)
        self.assertIn("skills/board-setup/SKILL.md:3: description: contains an angle bracket", self.bad)

    def test_name_equals_folder(self):
        self.assertIn("skills/board-setup/SKILL.md:2: frontmatter: name 'boardsetup' is not its folder", self.bad)

    def test_reference_depth(self):
        self.assertIn("references/deep/too-deep.md: reference-depth: reference more than one level deep", self.bad)

    def test_missing_linked_file(self):
        self.assertIn("skills/engagement/SKILL.md:9: missing-link: linked file not found: references/missing.md", self.bad)
        self.assertIn("SKILL.md:11: missing-link: linked file not found: scripts/absent.py", self.bad)
        self.assertNotIn("missing-link", self.clean)

    def test_reserved_names(self):
        self.assertIn("skills/board-setup/SKILL.md:1: reserved-name: 'board-setup' is a reserved name", self.bad)
        self.assertIn("agents/daily-briefing.md:1: reserved-name: 'daily-briefing' is a reserved name", self.bad)

    def test_prefixed_tool_name(self):
        self.assertIn("SKILL.md:10: prefixed-tool: prefixed tool name mcp__monday-api__create_board", self.bad)
        self.assertNotIn("prefixed-tool", self.clean)

    def test_all_caps_emphasis(self):
        self.assertIn("SKILL.md:7: all-caps: all-caps emphasis word MUST", self.bad)
        self.assertIn("SKILL.md:7: all-caps: all-caps emphasis word ALWAYS", self.bad)
        self.assertNotIn("all-caps", self.clean)

    def test_absent_gotcha_and_template_ids(self):
        self.assertIn("SKILL.md:9: gotcha-id: G-77 referenced but absent", self.bad)
        self.assertIn("SKILL.md:9: template-id: templates/record/nothing.md referenced but absent", self.bad)
        self.assertNotIn("gotcha-id", self.clean)

    def test_consultant(self):
        self.assertIn("SKILL.md:7: consultant: the word \"consultant\"", self.bad)

    def test_handoff_sentence(self):
        self.assertIn("templates/record/scope.md:6: handoff-sentence: fixed sentence missing", self.bad)
        self.assertNotIn("handoff-sentence", self.clean)

    def test_shared_copy_differs(self):
        self.assertIn("skills/engagement/references/safety.md: shared-copy: differs from shared/safety.md", self.bad)

    def test_pinned_disagreement(self):
        self.assertIn("shared/record-map.md:3: pinned-agreement: `vendor-led` pinned but not embedded in scripts/transcript_prep.py", self.bad)
        self.assertIn("scripts/transcript_prep.py:2: pinned-agreement: `client-led` embedded but not pinned in shared/record-map.md", self.bad)
        self.assertIn("scripts/transcript_measure.py: pinned-agreement: not present yet (permitted-constants unchecked)", self.bad)

    def test_pinned_not_present_yet_is_not_an_error(self):
        root = self.copy_clean("no-scripts")
        shutil.rmtree(os.path.join(root, PLUGIN, "scripts"))
        code, out = run(["--root", root], self.home)
        self.assertIn("scripts/transcript_prep.py: pinned-agreement: not present yet (call-type-vocabulary unchecked)", out)
        self.assertIn("SKILL.md:16: missing-link", out)
        self.assertNotIn("pinned-agreement: `", out)

    def test_pinned_region_missing_is_an_error(self):
        root = self.copy_clean("no-region")
        with open(os.path.join(root, PLUGIN, "scripts", "transcript_prep.py"), "w", encoding="utf-8") as handle:
            handle.write("SEAT = ('partner-led',)\n")
        code, out = run(["--root", root], self.home)
        self.assertEqual(code, 1)
        self.assertIn("no parseable `# pinned: call-type-vocabulary`", out)

    def test_personal_name_found_and_masked(self):
        self.assertIn("SKILL.md:8: personal-name: personal name P**** T*****", self.bad)
        self.assertIn("SKILL.md:8: personal-name: personal name T*****", self.bad)
        self.assertNotIn("Talwar", self.bad)

    def test_absent_name_list_is_a_warning(self):
        code, out = run(["--root", os.path.join(FIXTURES, "lint-clean")], self.empty_home)
        self.assertEqual(code, 0)
        self.assertIn("warning: personal-names-index.json: personal-name: name list not found", out)

    def test_hash_name_helper_normalises(self):
        code, out = run(["--hash-name", "Priyá  TALWAR"], self.home)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), lint_plugin.name_hash("priya talwar"))
        self.assertEqual(lint_plugin.normalise_name("O'Brien-Zoë"), "obrienzoe")

    def test_empty_root_reports_absent_and_passes(self):
        root = os.path.join(self.tmp, "empty-root")
        os.makedirs(root)
        code, out = run(["--root", root], self.home)
        self.assertEqual(code, 0, out)
        self.assertIn("plugin folder not present yet", out)
        self.assertIn("shared/record-map.md: pinned-agreement: not present yet", out)
        self.assertIn("shared/: shared-region: not present yet (shared-words unchecked)", out)
        self.assertNotIn("error:", out)

    def copy_real(self, name):
        dest = os.path.join(self.tmp, name)
        shutil.copytree(os.path.join(REPO, PLUGIN), os.path.join(dest, PLUGIN),
                        ignore=shutil.ignore_patterns("__pycache__", ".work"))
        return dest

    def test_R41_the_real_tree_has_its_shared_regions_equal_to_shared(self):
        flag, common = sys.dont_write_bytecode, sys.modules.get("mmb_common")
        code, out = run(["--root", REPO], self.home)
        self.assertEqual(code, 0, out)
        self.assertNotIn("shared-region", out)
        # The script is loaded by path and the process is left as it was found.
        self.assertEqual(sys.dont_write_bytecode, flag)
        self.assertIs(sys.modules.get("mmb_common"), common)

    def test_R41_a_word_shared_gained_that_the_region_lacks_is_an_error(self):
        root = self.copy_real("shared-word")
        with open(os.path.join(root, PLUGIN, "shared", "safety.md"), "a", encoding="utf-8") as handle:
            handle.write("\nQuillanbrook\n")
        code, out = run(["--root", root], self.home)
        self.assertEqual(code, 1, out)
        self.assertIn("scripts/leak_lint.py:", out)
        self.assertIn("shared-region: `shared-words` differs from shared/ as shipped: 1 word(s) missing, 0 extra; "
                      "run `leak_lint.py terms` over the changed shared/, then regenerate the region with "
                      "shared_vocabulary()", out)
        self.assertNotIn("`shared-phrases` differs", out)
        self.assertNotIn("quillanbrook", out.lower())
        self.assertFalse(os.path.exists(os.path.join(root, PLUGIN, "scripts", "__pycache__")))

    def test_R41_an_extra_phrase_in_the_region_is_an_error(self):
        root = self.copy_real("shared-phrase")
        script = os.path.join(root, PLUGIN, "scripts", "leak_lint.py")
        with open(script, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("\nyyyymmdd hhmm,\n", text)
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(text.replace("\nyyyymmdd hhmm,\n", "\nyyyymmdd hhmm, tallowmere depot,\n", 1))
        code, out = run(["--root", root], self.home)
        self.assertEqual(code, 1, out)
        self.assertIn("shared-region: `shared-phrases` differs from shared/ as shipped: 0 phrase(s) missing, 1 extra; "
                      "run `leak_lint.py terms` over the changed shared/, then regenerate the region with "
                      "shared_phrases()", out)
        self.assertNotIn("`shared-words` differs", out)
        self.assertNotIn("tallowmere", out.lower())

    def test_R41_a_script_without_the_regions_is_not_present_yet(self):
        for ident in ("shared-words", "shared-phrases"):
            self.assertIn("info: scripts/leak_lint.py: shared-region: not present yet (%s unchecked)" % ident,
                          self.clean)
        self.assertEqual(self.clean_code, 0)
        self.assertNotIn("shared-region: `", self.clean + self.bad)

    def test_missing_root_exits_3(self):
        code, out = run(["--root", os.path.join(self.tmp, "nowhere")], self.home)
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
