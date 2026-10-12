#!/usr/bin/env python3
"""Clean-room scan: prose shared between a file tree and quarantined files.

Reports every run of eight or more consecutive prose words (``--words`` sets
the length) that appears both in the scanned tree and in any quarantined
file. Identifier and enum lists are allowed; README.md in this folder says
how they are told apart from prose. Exit codes: 0 clean, 1 findings,
3 could not run. Standard library only; runs on Python 3.9 and later.
"""
import argparse
import os
import re
import sys

DEFAULT_TREE = os.path.join("plugins", "monday-master-builder")
TEXT_EXT = {".md", ".txt", ".json", ".py", ".sh", ".yml", ".yaml", ".csv"}
SKIP_DIRS = {".git", "__pycache__", ".work", "node_modules"}
STRIP = ".,:;!?\"'“”‘’()[]{}<>*#=+~\\"

CODE_SPAN = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^\s*(```|~~~)")
LIST_MARK = re.compile(r"^\s*(?:[-*+]|\d+[.)]|\|)\s*")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}")
IDENT = re.compile(r"_|\d|[a-z][A-Z]|::|/|\.[A-Za-z]")


def is_identifier(token):
    """A token with an underscore, a digit, an inner capital, a path or a dot."""
    return len(token) > 24 or bool(IDENT.search(token))


def prose_word(token):
    word = re.sub(r"[^a-z'’-]", "", token.lower()).strip("'’-")
    return word or None


def line_words(line):
    """The prose words of one line, or None when the line is not prose.

    Not prose: a table rule, an enum list (three or more comma, semicolon
    or pipe separated segments averaging at most two words each), and a
    line where identifier-like tokens are at least half of all tokens.
    Inline code is removed first, so identifiers inside it never count.
    """
    line = LIST_MARK.sub("", CODE_SPAN.sub(" ", line))
    if TABLE_RULE.match(line):
        return None
    segments = [s for s in re.split(r"[,;|]", line) if s.strip()]
    if len(segments) >= 3:
        if sum(len(s.split()) for s in segments) <= 2 * len(segments):
            return None
    tokens = [t for t in (t.strip(STRIP) for t in line.split()) if t]
    if not tokens:
        return None
    identifiers = sum(1 for t in tokens if is_identifier(t))
    if identifiers * 2 >= len(tokens):
        return None
    words = [prose_word(t) for t in tokens if not is_identifier(t)]
    return [w for w in words if w]


def paragraphs(lines):
    """Yield one list of (word, line number) per run of consecutive prose lines."""
    para, in_fence = [], False
    for number, raw in enumerate(lines, 1):
        if FENCE.match(raw):
            in_fence = not in_fence
            words = None
        else:
            words = None if in_fence else line_words(raw)
        if words:
            para.extend((w, number) for w in words)
        elif para:
            yield para
            para = []
    if para:
        yield para


def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read().splitlines()


def key_at(para, start, n):
    return " ".join(w for w, _ in para[start:start + n])


def index_quarantine(paths, n):
    """Map every n-word prose run in the quarantined files to its first source."""
    index = {}
    for path in paths:
        for para in paragraphs(read_lines(path)):
            for i in range(len(para) - n + 1):
                index.setdefault(key_at(para, i, n), (path, para[i][1]))
    return index


def scan_file(path, index, n):
    """Return (path, line, words, source) for each maximal shared run in one file."""
    findings = []
    for para in paragraphs(read_lines(path)):
        hits = [i for i in range(len(para) - n + 1) if key_at(para, i, n) in index]
        start = previous = None
        for i in hits + [None]:
            if start is not None and (i is None or i != previous + 1):
                words = [w for w, _ in para[start:previous + n]]
                findings.append((path, para[start][1], words, index[key_at(para, start, n)]))
                start = None
            if i is not None and start is None:
                start = i
            previous = i
    return findings


def text_files(root):
    """Every text file under root, sorted, skipping scratch and version control."""
    found = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            if os.path.splitext(name)[1] in TEXT_EXT:
                found.append(os.path.join(folder, name))
    return found


def expand(paths):
    """Files as given, directories walked for text files; unreadable paths dropped."""
    files, missing = [], []
    for path in paths:
        if os.path.isdir(path):
            files.extend(text_files(path))
        elif os.path.isfile(path):
            files.append(path)
        else:
            missing.append(path)
    return files, missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("quarantine", nargs="*", help="quarantined files or folders")
    parser.add_argument("--root", help="repository root (default: the parent of tools/)")
    parser.add_argument("--tree", action="append", metavar="PATH",
                        help="tree to scan; repeatable; default plugins/monday-master-builder")
    parser.add_argument("--words", type=int, default=8, help="run length in words (default 8)")
    parser.add_argument("--show", type=int, default=30, help="words of each run to print")
    args = parser.parse_args(argv)
    if not args.quarantine:
        print("cannot run: no quarantined files given")
        return 3
    if args.words < 2:
        print("cannot run: --words must be at least 2")
        return 3
    root = os.path.abspath(args.root or os.path.join(os.path.dirname(__file__), os.pardir))
    trees = args.tree or [os.path.join(root, DEFAULT_TREE)]
    quarantine, missing = expand(args.quarantine)
    for path in missing:
        print("cannot read quarantined path: " + path)
    if not quarantine:
        print("cannot run: no readable quarantined file")
        return 3
    for tree in trees:
        if not os.path.exists(tree):
            print("cannot run: tree not found: " + tree)
            return 3
    try:
        index = index_quarantine(quarantine, args.words)
        findings = []
        for tree in trees:
            for path in (text_files(tree) if os.path.isdir(tree) else [tree]):
                findings.extend(scan_file(path, index, args.words))
    except OSError as exc:
        print("cannot run: " + str(exc))
        return 3
    for path, line, words, (source, source_line) in findings:
        shown = " ".join(words[:args.show]) + (" …" if len(words) > args.show else "")
        print("%s:%d: %d words shared with %s:%d: \"%s\""
              % (os.path.relpath(path), line, len(words), source, source_line, shown))
    print("cleanroom_scan: %d finding(s) over %d quarantined file(s), %d-word runs"
          % (len(findings), len(quarantine), args.words))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
