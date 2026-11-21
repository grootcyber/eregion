"""Check that a document split lost nothing (DX1): every paragraph of the old file is found
again, line by line, in the new files.

    python scripts/check_paragraphs.py --old 693bb59:CLAUDE.md
    python scripts/check_paragraphs.py --old /path/to/CLAUDE.old.md CLAUDE.md docs ROADMAP.md
    python scripts/check_paragraphs.py --code --old f656998b:glorfindel/cli.py glorfindel/cli.py glorfindel/watch

A paragraph is a block between blank lines. Each of its lines (whitespace collapsed) must
appear somewhere in the destinations (default: CLAUDE.md, docs/, ROADMAP.md). Prints the
paragraphs with a missing line, and that line; exits 1 if there is one.

`--code` (WCH1): the same for code moved out of a file — a directory's `*.py` read, and a line of
a closure that became a method found again as itself: `self.` dropped, and the `self` parameter; a
comment become a docstring, its `#` and its quotes.
What is still missing is what changed form (a cell `x[0]` become an attribute, a call given its
console): printed, for a human to read each.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_DESTINATIONS = ["CLAUDE.md", "docs", "ROADMAP.md"]


def _norm(line: str, code: bool = False) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    if code:
        line = re.sub(r"\bself\.", "", line).replace("(self, ", "(").replace("(self)", "()")
        line = re.sub(r'^(?:#\s*|""")|"""$', "", line).strip()      # a comment become a docstring
    return line


def _read_old(spec: str) -> str:
    path = Path(spec)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    # REV:PATH — read from git
    return subprocess.run(["git", "show", spec], capture_output=True, text=True, check=True).stdout


def _corpus(destinations: list[str], code: bool = False) -> str:
    texts = []
    for d in destinations:
        p = Path(d)
        files = sorted(p.rglob("*.py" if code else "*.md")) if p.is_dir() else [p]
        for f in files:
            if f.is_file():
                texts.append(f.read_text(encoding="utf-8"))
    return "\n".join(_norm(line, code) for t in texts for line in t.split("\n"))


def missing(old: str, corpus: str, code: bool = False) -> list[tuple[str, list[str]]]:
    """(first line of the paragraph, its lines not found in the corpus) for each incomplete one.
    Prose (the default) is found as a part of the corpus, a paragraph being rewrapped; code
    (`code`) only as a whole line of it — a short line is never found inside a longer one."""
    pool = set(corpus.split("\n")) if code else corpus
    out = []
    for para in re.split(r"\n\s*\n", old):
        lines = [_norm(line, code) for line in para.split("\n") if len(_norm(line, code)) >= 3]
        lost = [line for line in lines if line not in pool]
        if lost:
            out.append((lines[0][:90] if lines else "", lost))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old", required=True, help="old file: a path, or REV:PATH read from git")
    ap.add_argument("--code", action="store_true", help="code moved: *.py read, `self.` dropped (WCH1)")
    ap.add_argument("destinations", nargs="*", default=DEFAULT_DESTINATIONS)
    a = ap.parse_args()
    old = _read_old(a.old)
    found = missing(old, _corpus(a.destinations, a.code), a.code)
    paragraphs = len([p for p in re.split(r"\n\s*\n", old) if p.strip()])
    for first, lost in found:
        print(f"- paragraph « {first} »")
        for line in lost:
            print(f"    missing: {line[:160]}")
    print(f"{paragraphs} paragraphs, {len(found)} with a line not found")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
