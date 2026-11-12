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
- in a list of lots that goes on: after another lot's name and a comma, « et », « and », « → »,
  « / » or « + », and before another (`O1, H0, R1, G0`) — « Avant CI6, H0 (le CD) », « Depuis SEC18,
  H0 » at the end of a line, « H1 → H0 (#300) », « ID1, H0) » are the host;
- at the head of a list of two lots more at least (`(H0, H1, H1b)`) — « H0 et O1 tirent l'image »,
  « H0 / O1 : les deux VM », « **H0**, O1 » are the host;
- the first cell of a table of lots, one whose header begins with « Lot » (the ROADMAP's), or a value
  alone on its line (`"H0",`, the manual's JSON) — « | H0 | 10.0.0.4 | la VM de Glorfindel | » is
  the host;
- « anciennement H0 », « formerly H0 »: the first mention of Imladris;
- in one of LOT_PHRASES: the lots that no pattern tells from the host (the pre-observation of the
  ROADMAP), named one by one;
- in one of the texts KEPT for its file, each with its reason: the text of a query, whose WL1
  fingerprint covers the whole rule; the quotation, in the doc, of an output IML2 will rename (the CD,
  a workflow's step), so that it stays what the screen shows. Each must still be in its file, and a
  quotation in its source: else it is said.

**Not read**: HISTORY, the one exception for the name; and LATER, what IML2 renames with the resource
or what this lot does not touch — each with its reason. **The first mention**: in each Markdown
document read but the fragments of changes/ (a version's text, read under it), the first « Imladris »
says « (anciennement H0) » or « , anciennement H0 » (in English, « formerly »), so that a reader who
knew H0 finds it.

The files are those git tracks (an untracked file — a host.env, an .envrc — is never read); in a
copy without git (the mutation harness), the tree's files, hidden ones and `*.env` aside.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The history: what H0 was called when it was written.
HISTORY = ("CHANGELOG.md", "docs/historique.md")
# Not read, each with its reason: what IML2 renames with the resource, and what this lot does not
# touch. A key ending in « / » is a directory; a key starting with « . » is a suffix, in infra/.
LATER = {
    ".tf": "Terraform: its descriptions and messages go with the Azure resource (IML2)",
    ".tfvars": "Terraform: read at every plan of the resource (IML2)",
    ".tfvars.example": "Terraform: the example of a file read at every plan (IML2)",
    ".hcl": "Terraform: its tests and its lock, with the module (IML2)",
    "infra/glorfindel-host/deploy.sh": "deployed on the host: it runs there (IML2)",
    "infra/glorfindel-host/known_host.sh": "the host key's pinning, named with the resource (IML2)",
    "infra/glorfindel-host/status.sh": "deployed on the host: it runs there (IML2)",
    "infra/terraform/scripts/workload.sh": "bree's custom data: changing it rebuilds the VM (IML2)",
    "infra/identities/": "the role definitions: their description is Azure's (IML2)",
    ".github/": "the workflows: the sessions' App has no Workflows right — Jonathan's to push",
    "tests/": "the proofs: they quote what they test",
    "scripts/mutation_check.py": "the mutants: their anchors quote the code word for word, the CD's too",
    "scripts/mutants/": "the mutants: their anchors quote the code word for word, the CD's too",
    "scripts/host_name.py": "this check: it quotes the forms it tells apart",
}
# Texts kept as they are, by file: (the text, why, its source or None). A quotation's source must
# still say what the doc quotes — once IML2 renames it, the doc follows.
QUOTE = "the quotation of an output IML2 will rename: it stays what the screen shows"
KEPT = {
    "glorfindel/rules/azure/detection_rules.yaml": (
        ("Measured on H0's Syslog", "the text of a query: its WL1 fingerprint covers the whole rule", None),
    ),
    "infra/glorfindel-host/README.md": (
        ("« Verified as H0 verifies it »", QUOTE,
         (".github/workflows/publish.yml", "name: Verified as H0 verifies it")),
    ),
}
# A version's text, read under the version: no first mention of its own.
FIRST_MENTION_NOT = ("changes/",)

WORD = re.compile(r"\bH0\b")
_LOT = r"(?:[A-Z]{1,4}\d+[a-z]?|[A-Z]{1,4}-\d+[a-z]?)"
_SEP = r"\s*(?:,\s*(?:et|and)\b|,|\bet\b|\band\b|→|/|\+)\s*"
_LOT_SEP = _SEP + r"(?:\*\*)?" + _LOT + r"\b"
_BEFORE = (
    re.compile(r"\b[Ll]ots?\s+(?:\*\*)?$"),
    re.compile(r"\b(?:anciennement|formerly)\s+$", re.I),
    re.compile(r"\blots:\s*\[[^\]]*$"),
)
# In a list that goes on: after another lot, and before another (`O1, H0, R1`, `A0, H0 et IA0`).
_IN_LIST = re.compile(_LOT + r"(?:\s*✅)?(?:\*\*)?" + _SEP + r"(?:\*\*)?$")
_LIST_GOES_ON = re.compile(r"^(?:\*\*)?" + _LOT_SEP)
# At the head of a list: two lots more at least (`(H0, H1, H1b)`).
_HEAD = re.compile(r"(?:^|[(\[|]\s*|\*\*|:\s+)$")
_NEXT = re.compile(r"^(?:\*\*)?" + _LOT_SEP + r"(?:\*\*)?" + _LOT_SEP)
_CELL_BEFORE, _CELL_AFTER = re.compile(r"^\s*\|\s*$"), re.compile(r"^\s*\|")
_LOT_TABLE = re.compile(r"^\s*\|\s*Lots?\s*\|")
_ALONE_BEFORE, _ALONE_AFTER = re.compile(r'^\s*"$'), re.compile(r'^",?\s*$')

# The lot H0 where no pattern tells it from the host: the pre-observation, its decision, its end.
LOT_PHRASES = (
    "IA0 ✅ ; H0 en cours", "; H0 continue, puis point d'étape",
    "**H0** (Glorfindel hébergé, pré-observation)", "**H0** (Glorfindel sur une petite VM dédiée",
    "la pré-observation sur le banc (H0) ne le remplace pas", "une pré-observation sur le banc (H0).**",
    "après H0 (vers le 13/11)", "la pré-observation sur le banc (H0, 15/10)",
    "Pré-observation sur le banc (H0)", "Pré-observation (H0, décidé le 15/10",
    "et H0 (Glorfindel sur une VM dédiée, pré-observation)",
)

NAME = "Imladris"
FORMER = re.compile(r"^(?: \((?:anciennement|formerly) H0\)|, (?:anciennement|formerly) H0\b)")


def _within(line: str, texts, start: int, end: int) -> bool:
    for text in texts:
        i = line.find(text)
        while i >= 0:
            if i <= start and end <= i + len(text):
                return True
            i = line.find(text, i + 1)
    return False


def is_lot(line: str, start: int, end: int, lot_table: bool = False, kept=()) -> bool:
    """The H0 at line[start:end] names a lot (or the former name, or a kept text), not the host.
    `lot_table`: the line is a row of a table of lots; `kept`: the texts kept in this file."""
    if _within(line, LOT_PHRASES, start, end) or _within(line, kept, start, end):
        return True
    before, after = line[:start], line[end:]
    if any(p.search(before) for p in _BEFORE):
        return True
    if _IN_LIST.search(before) and _LIST_GOES_ON.match(after):
        return True
    if _HEAD.search(before) and _NEXT.match(after):
        return True
    if lot_table and _CELL_BEFORE.match(before) and _CELL_AFTER.match(after):
        return True
    return bool(_ALONE_BEFORE.match(before) and _ALONE_AFTER.match(after))


def host_mentions(text: str, kept=()) -> list[tuple[int, str]]:
    """Each line (1-based) where H0 names the host, with the line. A table's rows know its header."""
    out, header = [], None
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("|"):
            header = line if header is None else header
        else:
            header = None
        lot_table = header is not None and bool(_LOT_TABLE.match(header))
        if any(not is_lot(line, m.start(), m.end(), lot_table, kept) for m in WORD.finditer(line)):
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
    for key in LATER:
        if key.endswith("/"):
            if rel.startswith(key):
                return False
        elif key.startswith("."):
            if rel.startswith("infra/") and rel.endswith(key):
                return False
        elif rel == key:
            return False
    return True


def files(root: Path) -> list[str]:
    """The tracked files, by `git ls-files -z`: their names as they are, cut at « \\0 ». Without
    -z, git quotes a name that is not ASCII (« "docs/caf\\303\\251.md" »), which no file has: it
    was skipped, unsaid (FLK1, the second review of IML1). Without git, the tree, hidden and .env
    files aside."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True,
                             check=True).stdout
        names = out.split("\0")
    except (OSError, subprocess.CalledProcessError):
        names = [p.relative_to(root).as_posix() for p in root.rglob("*")
                 if p.is_file() and not p.name.endswith(".env")
                 and not any(part.startswith(".") for part in p.relative_to(root).parts)]
    return sorted({n for n in names if n})


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


def kept_gone(root: Path) -> list[str]:
    """A kept text no longer in its file, or a quotation whose source no longer says it."""
    out = []
    for rel, entries in KEPT.items():
        text = _text(root / rel)
        if text is None:
            continue
        for kept, _why, source in entries:
            if kept not in text:
                out.append(f"{rel}: the kept text « {kept} » is gone — take it out of KEPT (IML1)")
            said = _text(root / source[0]) if source else None
            if said is not None and source[1] not in said:
                out.append(f"{rel}: « {kept} » quotes {source[0]}, which no longer says it — "
                           "the doc follows its source (IML1)")
    return out


def problems(root: Path = REPO, only: list[str] | None = None) -> list[str]:
    out = []
    for rel in only if only is not None else files(root):
        if not read_here(rel):
            continue
        text = _text(root / rel)
        if text is None:
            continue
        kept = tuple(k for k, _why, _src in KEPT.get(rel, ()))
        for n, line in host_mentions(text, kept):
            out.append(f"{rel}:{n}: H0 names the host — Imladris (IML1): {line[:160]}")
        if rel.endswith(".md") and not rel.startswith(FIRST_MENTION_NOT) and first_mention_unsaid(text):
            out.append(f"{rel}: its first « Imladris » does not say « (anciennement H0) » (IML1)")
    if only is None:
        out += kept_gone(root)
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
