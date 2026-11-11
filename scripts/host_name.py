#!/usr/bin/env python3
"""IML1 (#688): the VM that carries Glorfindel is Imladris, and « H0 » never names it outside the history.

H0 was the lot that put Glorfindel on its own VM (#114), and the VM kept the lot's name. Since
10/11 (Jonathan's decision) it is Imladris, the house where Glorfindel lives. H0 stays the name of a
lot (H0, H1, H1b, H1c, H2), and the history keeps what it said.

    python scripts/host_name.py            # the repository; exit 1, with each place, if H0 names the host
    python scripts/host_name.py FILE …     # those files

**H0, the host, or H0, the lot.** Each `H0` as a word, in capitals (`h0_known_hosts`,
`bench_h0_reader.py`, `REQUEST_FROM=h0`, `H0_IP` are identifiers, not the word), is the host's name
unless it is, on its line:
- after « lot » or « lots » (`le lot H0`), or in a lot's list (`lots: [H0]`);
- in a list of lots: after another lot's name and a comma, « et », « and », « → », « / » or « + »,
  the list going on or closing after it (`O1, H0, R1, G0`; « Avant CI3, H0 construisait » is the
  host), or at the head of one (`(H0, H1, H1b)`, `| H0, H1 |`);
- a table's first cell (`| H0 |`, the lot's row), or a value alone on its line (`"H0",`, the
  manual's JSON);
- « anciennement H0 », « formerly H0 »: the first mention of Imladris;
- in one of LOT_PHRASES: the lots that no pattern tells from the host (the pre-observation of the
  ROADMAP), named one by one.

**Not read**: HISTORY, the one exception for the name; and LATER, what is not this lot's surface —
each with its reason. **The first mention**: in each Markdown document read, the first « Imladris »
says « (anciennement H0) » or « , anciennement H0 » (in English, « formerly »), so that a reader who
knew H0 finds it.

The files are those git tracks (an untracked file — a host.env, an .envrc — is never read); in a
copy without git (the mutation harness), the tree's files, hidden directories aside.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The history: what H0 was called when it was written.
HISTORY = ("CHANGELOG.md", "docs/historique.md")
# Not IML1's surfaces, each with its reason. A prefix ending in « / » is a directory.
LATER = {
    "infra/": "Terraform, the CD, the host's scripts and its Azure names: IML2 renames them with the "
              "resource (its Markdown, the doc, is read)",
    ".github/": "the workflows: Jonathan's alone to push",
    "tests/": "the proofs: they quote what they test, and say H0 where it is a fixture's name",
    "scripts/mutation_check.py": "the mutants: their anchors quote the code, kept with it",
    "scripts/mutants/": "the mutants: their anchors quote the code, kept with it",
    "scripts/host_name.py": "this check: it quotes the forms it tells apart",
}
LATER_DOCS = (".md",)     # the doc of a directory of LATER is read all the same

WORD = re.compile(r"\bH0\b")
_LOT = r"(?:[A-Z]{1,4}\d+[a-z]?|[A-Z]{1,4}-\d+[a-z]?)"
_SEP = r"\s*(?:,\s*(?:et|and)\b|,|\bet\b|\band\b|→|/|\+)\s*"
_BEFORE = (
    re.compile(r"\b[Ll]ots?\s+(?:\*\*)?$"),
    re.compile(r"\b(?:anciennement|formerly)\s+$", re.I),
    re.compile(r"\blots:\s*\[[^\]]*$"),
)
# In a list, after another lot: the list goes on, or closes (`A0, H0 et IA0`, `G0, et H0 (…)`) —
# never a verb (« Avant CI3, H0 construisait » is the host).
_IN_LIST = re.compile(_LOT + r"(?:\s*✅)?(?:\*\*)?" + _SEP + r"(?:\*\*)?$")
_LIST_GOES_ON = re.compile(r"^(?:\*\*)?(?:" + _SEP + r"|\s*[;)(]|\s*$)")
_HEAD = re.compile(r"(?:^|[(\[|]\s*|\*\*|:\s+)$")
_NEXT = re.compile(r"^(?:\*\*)?" + _SEP + r"(?:\*\*)?" + _LOT + r"\b")
_CELL_BEFORE, _CELL_AFTER = re.compile(r"^\s*\|\s*$"), re.compile(r"^\s*\|")
_ALONE_BEFORE, _ALONE_AFTER = re.compile(r'^\s*"$'), re.compile(r'^",?\s*$')

# The lot H0 where no pattern tells it from the host: the pre-observation, its decision, its end.
LOT_PHRASES = (
    "IA0 ✅ ; H0 en cours", "; H0 continue, puis point d'étape",
    "**H0** (Glorfindel hébergé, pré-observation)", "**H0** (Glorfindel sur une petite VM dédiée",
    "la pré-observation sur le banc (H0) ne le remplace pas", "une pré-observation sur le banc (H0).**",
    "après H0 (vers le 13/11)", "la pré-observation sur le banc (H0, 15/10)",
    "Pré-observation sur le banc (H0)", "Pré-observation (H0, décidé le 15/10",
)

NAME = "Imladris"
FORMER = re.compile(r"^(?: \((?:anciennement|formerly) H0\)|, (?:anciennement|formerly) H0\b)")


def is_lot(line: str, start: int, end: int) -> bool:
    """The H0 at line[start:end] names a lot (or the former name), not the host."""
    for phrase in LOT_PHRASES:
        i = line.find(phrase)
        while i >= 0:
            if i <= start and end <= i + len(phrase):
                return True
            i = line.find(phrase, i + 1)
    before, after = line[:start], line[end:]
    if any(p.search(before) for p in _BEFORE):
        return True
    if _IN_LIST.search(before) and _LIST_GOES_ON.match(after):
        return True
    if _HEAD.search(before) and _NEXT.search(after):
        return True
    if _CELL_BEFORE.match(before) and _CELL_AFTER.match(after):
        return True
    return bool(_ALONE_BEFORE.match(before) and _ALONE_AFTER.match(after))


def host_mentions(text: str) -> list[tuple[int, str]]:
    """Each line (1-based) where H0 names the host, with the line."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(not is_lot(line, m.start(), m.end()) for m in WORD.finditer(line)):
            out.append((n, line.strip()))
    return out


def first_mention_unsaid(text: str) -> bool:
    """A document that names Imladris without saying, at its first mention, that it was H0."""
    i = text.find(NAME)
    return i >= 0 and not FORMER.match(text[i + len(NAME):])


def read_here(rel: str) -> bool:
    """A path of the repository this check reads (relative, with « / »)."""
    if rel in HISTORY:
        return False
    for prefix in LATER:
        if rel == prefix or (prefix.endswith("/") and rel.startswith(prefix)):
            return rel.endswith(LATER_DOCS) and prefix == "infra/"
    return True


def files(root: Path) -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout
        names = out.split("\n")
    except (OSError, subprocess.CalledProcessError):
        names = [p.relative_to(root).as_posix() for p in root.rglob("*")
                 if p.is_file() and not any(part.startswith(".") and part != ".github"
                                            for part in p.relative_to(root).parts[:-1])]
    return sorted(n for n in names if n)


def _text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def problems(root: Path = REPO, only: list[str] | None = None) -> list[str]:
    out = []
    for rel in only if only is not None else files(root):
        if not read_here(rel):
            continue
        text = _text(root / rel)
        if text is None:
            continue
        for n, line in host_mentions(text):
            out.append(f"{rel}:{n}: H0 names the host — Imladris (IML1): {line[:160]}")
        if rel.endswith(".md") and first_mention_unsaid(text):
            out.append(f"{rel}: its first « Imladris » does not say « (anciennement H0) » (IML1)")
    return out


def main(argv: list[str]) -> int:
    found = problems(REPO, [Path(a).resolve().relative_to(REPO).as_posix() for a in argv] or None)
    for p in found:
        print(f"✗ {p}")
    if not found:
        print("✓ H0 never names the host outside the history: Imladris")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
