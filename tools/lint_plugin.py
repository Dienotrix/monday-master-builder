#!/usr/bin/env python3
"""Plugin lint for monday Master Builder (BUILD-PLAN WP16, release check 3).

One function per check over the plugin tree; one output line per finding with
severity, file, line, check and message; "not present yet" for an input that does
not exist, so a partial tree lints. Exit 0 no errors, 1 errors, 3 could not run;
warnings do not change the exit code. Standard library only, Python 3.9 and later.
"""
import argparse, ast, hashlib, json, os, re, sys, unicodedata  # noqa: E401

PLUGIN_REL = os.path.join("plugins", "monday-master-builder")
TEXT_EXT = {".md", ".txt", ".json", ".py", ".sh", ".yml", ".yaml", ".csv"}
SKIP_DIRS = {".git", "__pycache__", ".work"}
DESCRIPTION_MAX, LINE_MAX = 800, 190
NAMES_INDEX, MANIFEST = "personal-names-index.json", ".claude-plugin/plugin.json"
RECORD_MAP, GOTCHAS, SCOPE = "shared/record-map.md", "shared/monday-gotchas.md", "templates/record/scope.md"
PINNED = (("call-type-vocabulary", "scripts/transcript_prep.py"),
          ("permitted-constants", "scripts/transcript_measure.py"),
          ("ledger", "scripts/ledger.py"))
HANDOFF = ("Building this work happens outside this product. This record holds its scope, "
           "open questions, dependencies, access needs and next steps; it does not design or build it.")
RESERVED = {"task-management", "project-status-report", "board-setup", "docs-collaborator",
            "forms-builder", "activity-insights", "automate-crm", "daily-briefing", "data-cleanup",
            "forecast", "log-activity", "meeting-to-deal", "run-sequence", "workspace-builder"}
EMPHASIS = {"critical", "important", "must", "always", "never", "warning", "note", "mandatory",
            "required", "forbidden", "stop", "danger", "caution", "attention", "only", "absolutely",
            "immediately", "strictly", "essential", "vital", "ensure", "remember", "not", "all",
            "any", "every", "cannot", "should", "shall", "need", "avoid", "urgent", "alert"}

SKILL_RE, REF_RE = re.compile(r"^skills/([^/]+)/SKILL\.md$"), re.compile(r"^skills/([^/]+)/references/(.+)$")
AGENT_RE, HEADING = re.compile(r"^agents/([^/]+)\.md$"), re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE, CODE_SPAN, BACKTICK = re.compile(r"^\s*(```|~~~)"), re.compile(r"`[^`]*`"), re.compile(r"`([^`]+)`")
LINK = re.compile(r"\[[^\]]*\]\(<?([^)\s>]+)>?\)")
ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
PREFIXED_TOOL = re.compile(r"\bmcp__[A-Za-z0-9][A-Za-z0-9-]*__[A-Za-z0-9_]+")
CAPS = re.compile(r"(?<![\w./-])([A-Z]{2,})(?![\w./-])")
GOTCHA_REF, GOTCHA_DEF = re.compile(r"\bG-(\d{2,3})\b"), re.compile(r"^[\s#*|>-]*G-(\d{2,3})\b")
TEMPLATE_REF = re.compile(r"templates/(record|other)/([A-Za-z0-9_-]+\.[a-z]+)")
CONSULTANT, WORD = re.compile(r"\bconsultants?\b", re.IGNORECASE), re.compile(r"[^\W\d_][^\W\d_'’-]*")


class Lint:
    """The plugin tree, a line cache and the findings collected over it."""

    def __init__(self, plugin):
        self.plugin, self.findings, self.files, self.cache = plugin, [], [], {}
        for folder, dirs, names in os.walk(plugin):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            self.files += [os.path.relpath(os.path.join(folder, n), plugin).replace(os.sep, "/")
                           for n in sorted(names) if os.path.splitext(n)[1] in TEXT_EXT]

    def path(self, rel):
        return os.path.join(self.plugin, *rel.split("/"))

    def exists(self, rel):
        return os.path.exists(self.path(rel))

    def lines(self, rel):
        if rel not in self.cache:
            with open(self.path(rel), "r", encoding="utf-8", errors="replace") as handle:
                self.cache[rel] = handle.read().splitlines()
        return self.cache[rel]

    def prose(self, rel):
        """The file's lines with fenced blocks and inline code blanked out."""
        fence = False
        for line in self.lines(rel):
            fence = (not fence) if FENCE.match(line) else fence
            yield "" if fence or FENCE.match(line) else CODE_SPAN.sub(" ", line)

    def add(self, severity, rel, line, check, message):
        self.findings.append((severity, rel, line, check, message))

    def absent(self, rel, check, detail=""):
        self.add("info", rel, 0, check, "not present yet" + detail)


def front_matter(lines):
    """Flat `key: "value"` front matter as {key: (value, line)}; None when absent."""
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for number, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return fields
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = (match.group(2).strip().strip("\"'"), number)
    return None


def check_frontmatter(lint):
    """Description at most 800 characters with no angle bracket; name equals its folder."""
    descriptions, targets = [], []
    for pattern, folder in ((SKILL_RE, "skills/"), (AGENT_RE, "agents/")):
        found = [(f, pattern.match(f).group(1)) for f in lint.files if pattern.match(f)]
        targets += found or lint.absent(folder, "frontmatter") or []
    for rel, expected in targets:
        fields = front_matter(lint.lines(rel))
        if fields is None:
            lint.add("error", rel, 1, "frontmatter", "no flat front matter block")
            continue
        name, line = fields.get("name", (None, 1))
        if name is None:
            lint.add("error", rel, line, "frontmatter", "name missing")
        elif name != expected:
            lint.add("error", rel, line, "frontmatter", "name %r is not its folder %r" % (name, expected))
        description, line = fields.get("description", (None, 1))
        if description is None:
            lint.add("error", rel, line, "frontmatter", "description missing")
        else:
            descriptions.append((rel, line, description))
    if not lint.exists(MANIFEST):
        lint.absent(MANIFEST, "frontmatter")
    else:
        try:
            data = json.loads("\n".join(lint.lines(MANIFEST)))
            descriptions.append((MANIFEST, 1, str(data.get("description", ""))))
        except ValueError as exc:
            lint.add("error", MANIFEST, 1, "frontmatter", "not valid JSON: %s" % exc)
    for rel, line, description in descriptions:
        if len(description) > DESCRIPTION_MAX:
            lint.add("error", rel, line, "description",
                     "over %d characters (%d)" % (DESCRIPTION_MAX, len(description)))
        if "<" in description or ">" in description:
            lint.add("error", rel, line, "description", "contains an angle bracket")


def check_sizes(lint):
    """SKILL.md and every reference at or under 190 lines."""
    for rel in (f for f in lint.files if SKILL_RE.match(f) or (REF_RE.match(f) and f.endswith(".md"))):
        count = len(lint.lines(rel))
        if count > LINE_MAX:
            lint.add("error", rel, count, "size", "over %d lines (%d)" % (LINE_MAX, count))


def check_reference_depth(lint):
    """References sit directly under references/, never deeper."""
    for rel in (f for f in lint.files if REF_RE.match(f) and "/" in REF_RE.match(f).group(2)):
        lint.add("error", rel, 0, "reference-depth", "reference more than one level deep")


def check_links(lint):
    """Every relative Markdown link and every ${CLAUDE_PLUGIN_ROOT} path resolves."""
    for rel in lint.files:
        folder = os.path.dirname(lint.path(rel))
        for number, line in enumerate(lint.lines(rel), 1):
            targets = [(t, os.path.join(folder, t)) for t in LINK.findall(line)
                       if not t.startswith(("http://", "https://", "mailto:", "#", "/"))]
            targets += [(t, lint.path(t)) for t in ROOT_REF.findall(line)]
            for shown, target in targets:
                if not os.path.exists(target.split("#", 1)[0]):
                    lint.add("error", rel, number, "missing-link", "linked file not found: %s" % shown)


def check_reserved_names(lint):
    """No skill or agent carries a monday skill name."""
    for rel in (f for f in lint.files if SKILL_RE.match(f) or AGENT_RE.match(f)):
        folder = (SKILL_RE.match(rel) or AGENT_RE.match(rel)).group(1)
        name = (front_matter(lint.lines(rel)) or {}).get("name", ("",))[0]
        for reserved in {folder, name} & RESERVED:
            lint.add("error", rel, 1, "reserved-name", "%r is a reserved name" % reserved)


def check_tool_names(lint):
    """Tools by base name only: no name carrying a literal connector prefix."""
    for rel in lint.files:
        for number, line in enumerate(lint.lines(rel), 1):
            for name in PREFIXED_TOOL.findall(line):
                lint.add("error", rel, number, "prefixed-tool", "prefixed tool name %s" % name)


def check_emphasis(lint):
    """No all-caps emphasis word in prose (code spans and fenced blocks excluded)."""
    for rel in (f for f in lint.files if f.endswith((".md", ".txt"))):
        for number, line in enumerate(lint.prose(rel), 1):
            for word in CAPS.findall(line):
                if word.lower() in EMPHASIS:
                    lint.add("error", rel, number, "all-caps", "all-caps emphasis word %s" % word)


def check_ids(lint):
    """Every G- id resolves in monday-gotchas.md; every templates/ path names a file."""
    defined = {m.group(1) for m in map(GOTCHA_DEF.match, lint.lines(GOTCHAS)) if m} \
        if lint.exists(GOTCHAS) else None
    unchecked, templates_present = 0, any(TEMPLATE_REF.search(f) for f in lint.files)
    for rel in lint.files:
        for number, line in enumerate(lint.lines(rel), 1):
            for gid in GOTCHA_REF.findall(line):
                if defined is None:
                    unchecked += 1
                elif gid not in defined:
                    lint.add("error", rel, number, "gotcha-id", "G-%s referenced but absent" % gid)
            for kind, name in TEMPLATE_REF.findall(line):
                if templates_present and not lint.exists("templates/%s/%s" % (kind, name)):
                    lint.add("error", rel, number, "template-id",
                             "templates/%s/%s referenced but absent" % (kind, name))
    if defined is None:
        lint.absent(GOTCHAS, "gotcha-id", " (%d references unchecked)" % unchecked)
    if not templates_present:
        lint.absent("templates/", "template-id")


def check_consultant(lint):
    """The word "consultant" appears in no shipped file."""
    for rel in lint.files:
        for number, line in enumerate(lint.lines(rel), 1):
            if CONSULTANT.search(line):
                lint.add("error", rel, number, "consultant", "the word \"consultant\"")


def check_handoff(lint):
    """The scope.md template ends with the fixed hand-off sentence."""
    if not lint.exists(SCOPE):
        return lint.absent(SCOPE, "handoff-sentence")
    if HANDOFF not in re.sub(r"\s+", " ", " ".join(lint.lines(SCOPE))):
        lint.add("error", SCOPE, len(lint.lines(SCOPE)), "handoff-sentence", "fixed sentence missing")


def check_shared_copies(lint):
    """A copy of a shared file inside a skill's references is byte-identical."""
    shared = [f for f in lint.files if f.startswith("shared/")]
    if not shared:
        return lint.absent("shared/", "shared-copy")
    for source in shared:
        for copy in (f for f in lint.files if REF_RE.match(f)):
            if REF_RE.match(copy).group(2) == os.path.basename(source):
                with open(lint.path(source), "rb") as a, open(lint.path(copy), "rb") as b:
                    if a.read() != b.read():
                        lint.add("error", copy, 0, "shared-copy", "differs from %s" % source)


def pinned_section(lines, ident):
    """Backticked tokens under the heading `Pinned: <ident>` in record-map.md."""
    tokens, start, level = set(), None, 0
    for number, line in enumerate(lines, 1):
        match = HEADING.match(line)
        if match and start is not None and len(match.group(1)) <= level:
            break
        if match and match.group(2).strip().lower() == "pinned: " + ident:
            start, level = number, len(match.group(1))
        elif start is not None:
            tokens.update(t.strip().lower() for t in BACKTICK.findall(line))
    return tokens, start


def pinned_region(text, ident):
    """Names, and string or number literals, between `# pinned: <ident>` and `# end pinned`."""
    lines, start, end = text.splitlines(), None, None
    for number, line in enumerate(lines, 1):
        if line.strip().lower() == "# pinned: " + ident:
            start = number
        elif line.strip().lower() == "# end pinned" and start and end is None:
            end = number
    if start is None or end is None:
        return None, None, start
    names, literals = set(), set()
    for line in lines[start:end - 1]:
        literals.update(t.strip().lower() for t in BACKTICK.findall(line))
    for node in ast.walk(ast.parse(text)):
        if not start < getattr(node, "lineno", 0) < end:
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id.lower())
        elif isinstance(node, ast.Constant) and type(node.value) in (str, int, float):
            literals.add(str(node.value).strip().lower())
    return names, literals, start


def check_pinned(lint):
    """record-map.md's pinned vocabulary and constants agree with the scripts' embedded copies."""
    for ident, script in PINNED:
        if not (lint.exists(RECORD_MAP) and lint.exists(script)):
            lint.absent(script if lint.exists(RECORD_MAP) else RECORD_MAP,
                        "pinned-agreement", " (%s unchecked)" % ident)
            continue
        pinned, line = pinned_section(lint.lines(RECORD_MAP), ident)
        try:
            names, literals, region = pinned_region("\n".join(lint.lines(script)), ident)
        except SyntaxError as exc:
            names, region = None, exc.lineno
        if line is None:
            lint.add("error", RECORD_MAP, 0, "pinned-agreement", "no heading `Pinned: %s`" % ident)
        elif names is None:
            lint.add("error", script, region or 0, "pinned-agreement",
                     "no parseable `# pinned: %s` ... `# end pinned` region" % ident)
        else:
            for token in sorted(pinned - names - literals):
                lint.add("error", RECORD_MAP, line, "pinned-agreement",
                         "`%s` pinned but not embedded in %s" % (token, script))
            for token in sorted(literals - pinned):
                lint.add("error", script, region, "pinned-agreement",
                         "`%s` embedded but not pinned in %s" % (token, RECORD_MAP))


def normalise_name(text):
    """Lowercase, accents folded, letters only: the form that is hashed."""
    return "".join(c for c in unicodedata.normalize("NFKD", text).lower() if "a" <= c <= "z")


def name_hash(text):
    return hashlib.sha256(normalise_name(text).encode("ascii")).hexdigest()


def check_personal_names(lint):
    """No word or adjacent word pair hashes to an entry of the personal-name list."""
    index = os.path.join(os.environ.get("MMB_HOME") or os.path.join(os.path.expanduser("~"), "monday-builder"), NAMES_INDEX)
    if not os.path.exists(index):
        return lint.add("warning", NAMES_INDEX, 0, "personal-name",
                        "name list not found at %s; check not run" % index)
    with open(index, "r", encoding="utf-8") as handle:
        hashes = set(json.load(handle).get("hashes", []))
    for rel in lint.files:
        for number, line in enumerate(lint.lines(rel), 1):
            words = WORD.findall(line)
            for candidate in [(w,) for w in words] + list(zip(words, words[1:])):
                text = " ".join(candidate)
                if len(normalise_name(text)) > 1 and name_hash(text) in hashes:
                    masked = " ".join(w[0] + "*" * (len(w) - 1) for w in candidate)
                    lint.add("error", rel, number, "personal-name",
                             "personal name %s (hash %s)" % (masked, name_hash(text)[:12]))


CHECKS = (check_frontmatter, check_sizes, check_reference_depth, check_links, check_reserved_names,
          check_tool_names, check_emphasis, check_ids, check_consultant, check_handoff,
          check_shared_copies, check_pinned, check_personal_names)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", help="repository root (default: the parent of tools/)")
    parser.add_argument("--hash-name", metavar="NAME",
                        help="print the sha256 of a normalised name for the personal-name list")
    args = parser.parse_args(argv)
    if args.hash_name:
        print(name_hash(args.hash_name))
        return 0
    root = os.path.abspath(args.root or os.path.join(os.path.dirname(__file__), os.pardir))
    if not os.path.isdir(root):
        print("cannot run: root not found: " + root)
        return 3
    lint = Lint(os.path.join(root, PLUGIN_REL))
    if not os.path.isdir(lint.plugin):
        lint.add("warning", PLUGIN_REL, 0, "tree", "plugin folder not present yet; nothing linted")
    try:
        for check in CHECKS:
            check(lint)
    except (OSError, ValueError) as exc:
        print("cannot run: %s" % exc)
        return 3
    for severity, rel, line, check, message in lint.findings:
        print("%s: %s: %s: %s" % (severity, "%s:%d" % (rel, line) if line else rel, check, message))
    counts = {s: sum(1 for f in lint.findings if f[0] == s) for s in ("error", "warning", "info")}
    print("lint_plugin: %d error(s), %d warning(s), %d not present yet, %d file(s)"
          % (counts["error"], counts["warning"], counts["info"], len(lint.files)))
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
