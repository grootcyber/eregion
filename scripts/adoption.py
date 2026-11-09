#!/usr/bin/env python3
"""adoption — the role sheets on the project's site, every figure dated and sourced (ADO2, #671).

  python3 scripts/adoption.py check    docs/proofs.json and the pages that show its figures

`docs/proofs.json` is the one source of the figures the site shows. Each figure has its value,
what it says, its date (the day or the month of the measure), its kind (measured, an estimate, a
setting of the code, or a measure to take again) and its source: a file of the repository, the
sentence of that file that gives the figure (`quote`), and the heading it sits under (`anchor`, a
GitHub heading id) or the run it comes from (`run`). Held here, by `problems`:
- a figure without its date, its kind or its source is refused; so is a date to come;
- a source the repository does not hold, a heading its file does not have, a run it does not name,
  a quote its file (or its section) no longer says, or a quote that does not give the figure's
  numbers, is refused: an edit that moves the figure in its source fails here, and says which;
- on a page (`docs/adoption/index.html`), a figure is shown in an element `data-proof="<key>"`,
  whose value, text, date and source are the proof's own; any digit outside such an element — but
  a technique's id (`T1486`) and the license (`Apache 2.0`) — is a figure that is not in the
  source, and is refused; a proof no page shows is refused too.

The page's other rules (its content policy, no script, its links) are in tests/unit/test_adoption.py.
Runs on python3 alone, without a library.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOFS = "docs/proofs.json"
PAGES = ("docs/adoption/index.html",)
REPO_URL = "https://github.com/grootcyber/eregion/blob/main/"

# kind → the label the page shows beside the date ("" for a measure: nothing more to say).
KINDS = {"measured": "", "estimate": "estimate", "setting": "a setting", "to-remeasure": "to be re-measured"}
PROOF_KEYS = {"value", "says", "date", "kind", "source", "note"}
SOURCE_KEYS = {"path", "quote", "anchor", "run"}
DATE = re.compile(r"(\d{4})-(\d{2})(?:-(\d{2}))?")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# Not a figure: a technique's id, the license. Anything else with a digit is.
FREE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b|\bApache 2\.0\b")
FIELDS = ("value", "says", "date", "source", "kind", "note")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def norm(text: str) -> str:
    return " ".join(text.split())


def numbers(text: str) -> list[str]:
    return re.findall(r"\d+", text)


def parse_date(value) -> dt.date | None:
    """A day (2026-11-02) or a month (2026-10, read as its first day); None if neither."""
    m = DATE.fullmatch(value) if isinstance(value, str) else None
    if not m:
        return None
    try:
        return dt.date(int(m[1]), int(m[2]), int(m[3] or 1))
    except ValueError:
        return None


def show_date(value: str) -> str:
    """What the page shows: « 2 Nov 2026 », or « Oct 2026 » for a month."""
    d = parse_date(value)
    month = f"{MONTHS[d.month - 1]} {d.year}"
    return month if value.count("-") == 1 else f"{d.day} {month}"


def slug(heading: str) -> str:
    """The id GitHub gives a Markdown heading: lower case, punctuation dropped, spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def section(text: str, anchor: str) -> str | None:
    """The text under the heading whose id is `anchor`, up to the next heading of its level or above."""
    lines = text.splitlines()
    fence = False
    heads = []
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING.match(line)
        if m:
            heads.append((i, len(m[1]), slug(m[2])))
    for n, (i, level, sid) in enumerate(heads):
        if sid == anchor:
            end = next((j for j, lv, _ in heads[n + 1:] if lv <= level), len(lines))
            return "\n".join(lines[i + 1:end])
    return None


def source_url(src: dict) -> str:
    return REPO_URL + src["path"] + (f"#{src['anchor']}" if src.get("anchor") else "")


def _source_problems(key: str, src, root: Path) -> list[str]:
    if not isinstance(src, dict):
        return [f"{key} : la source est un objet (path, quote, anchor ou run)"]
    found = [f"{key} : « {k} » n'existe pas dans une source" for k in sorted(set(src) - SOURCE_KEYS)]
    path, quote = src.get("path"), src.get("quote")
    if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
        return found + [f"{key} : la source dit un chemin du dépôt"]
    if not isinstance(quote, str) or not quote.strip():
        return found + [f"{key} : la source cite la phrase qui donne le chiffre (quote)"]
    file = root / path
    if not file.is_file():
        return found + [f"{key} : {path} n'existe pas dans le dépôt"]
    text = file.read_text(encoding="utf-8")
    where, scope = text, path
    if src.get("anchor") is not None:
        where = section(text, src["anchor"]) if isinstance(src["anchor"], str) else None
        if where is None:
            return found + [f"{key} : {path} n'a pas de titre #{src['anchor']}"]
        scope = f"{path}#{src['anchor']}"
    if src.get("run") is not None and (not isinstance(src["run"], str) or src["run"] not in text):
        found.append(f"{key} : {path} ne nomme pas le run {src.get('run')}")
    if norm(quote) not in norm(where):
        found.append(f"{key} : {scope} ne dit plus « {quote} »")
    return found


def proof_problems(proofs: dict, root: Path = ROOT, today: dt.date | None = None) -> list[str]:
    today = today or dt.date.today()
    if not isinstance(proofs, dict) or not proofs:
        return ["proofs.json : « proofs » tient au moins un chiffre"]
    found: list[str] = []
    for key, p in proofs.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or not isinstance(p, dict):
            found.append(f"{key} : un id en minuscules, et un objet")
            continue
        found += [f"{key} : « {k} » n'existe pas dans une preuve" for k in sorted(set(p) - PROOF_KEYS)]
        value, says = p.get("value"), p.get("says")
        if not isinstance(value, str) or not numbers(value):
            found.append(f"{key} : la valeur est un chiffre, écrit comme la page le montre")
        if not isinstance(says, str) or not says.strip():
            found.append(f"{key} : il dit ce qu'il mesure (says)")
        day = parse_date(p.get("date"))
        if day is None:
            found.append(f"{key} : sans date (AAAA-MM-JJ, ou AAAA-MM pour un mois)")
        elif day > today:
            found.append(f"{key} : daté du {p['date']}, à venir")
        if p.get("kind") not in KINDS:
            found.append(f"{key} : son genre est l'un de {', '.join(KINDS)}")
        if p.get("kind") == "to-remeasure" and not (isinstance(p.get("note"), str) and p["note"].strip()):
            found.append(f"{key} : une mesure à reprendre dit pourquoi (note)")
        if "source" not in p:
            found.append(f"{key} : sans source")
            continue
        src_found = _source_problems(key, p["source"], root)
        found += src_found
        if not src_found and isinstance(value, str):
            missing = sorted(set(numbers(value)) - set(numbers(p["source"]["quote"])))
            if missing:
                found.append(f"{key} : la phrase citée ne donne pas {', '.join(missing)}")
    return found


class _Page(HTMLParser):
    """The figures a page shows (each element data-proof, its fields data-f) and its text outside them."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stats: list[dict] = []
        self.outside: list[str] = []
        self._stack: list[tuple[str, str | None]] = []   # (tag, field opened by it)
        self._stat: dict | None = None
        self._depth = 0          # depth of the open stat, in self._stack
        self._skip = 0           # inside <style> or <script>

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        if tag in VOID:
            if self._stat is None:
                self.outside += [a[k] for k in ("alt", "title", "aria-label") if a.get(k)]
            return
        field = None
        if self._stat is None and "data-proof" in a:
            self._stat = {"key": a["data-proof"], "fields": {}, "attrs": {}}
            self._depth = len(self._stack) + 1
        elif self._stat is not None and a.get("data-f") in FIELDS:
            field = a["data-f"]
            self._stat["fields"].setdefault(field, "")
            self._stat["attrs"][field] = a
        elif self._stat is None:
            self.outside += [a[k] for k in ("title", "aria-label") if a.get(k)]
        self._skip += tag in ("style", "script")
        self._stack.append((tag, field))

    def handle_endtag(self, tag):
        if tag in VOID or not any(t == tag for t, _ in self._stack):
            return
        while self._stack:
            t, _ = self._stack.pop()
            self._skip -= t in ("style", "script")
            if self._stat is not None and len(self._stack) < self._depth:
                self.stats.append(self._stat)
                self._stat = None
            if t == tag:
                break

    def handle_data(self, data):
        if self._skip:
            return
        if self._stat is None:
            self.outside.append(data)
            return
        for _, field in reversed(self._stack):
            if field:
                self._stat["fields"][field] += data
                break


def read_page(html: str) -> _Page:
    page = _Page()
    page.feed(html)
    page.close()
    return page


def page_problems(proofs: dict, html: str, name: str = "la page") -> tuple[list[str], set[str]]:
    """What a page shows that its source does not say; and the proofs it shows."""
    page = read_page(html)
    found: list[str] = []
    shown: set[str] = set()
    for s in page.stats:
        key, f, attrs = s["key"], {k: norm(v) for k, v in s["fields"].items()}, s["attrs"]
        p = proofs.get(key)
        if not isinstance(p, dict):
            found.append(f"{name} : data-proof=« {key} » n'est pas dans {PROOFS}")
            continue
        shown.add(key)
        if f.get("value") != norm(str(p.get("value"))):
            found.append(f"{name} : {key} montre « {f.get('value')} », la source dit « {p.get('value')} »")
        if f.get("says") != norm(str(p.get("says"))):
            found.append(f"{name} : {key} ne dit pas ce que dit la source")
        if parse_date(p.get("date")) and (attrs.get("date", {}).get("datetime") != p["date"]
                                          or f.get("date") != show_date(p["date"])):
            found.append(f"{name} : {key} n'a pas la date de la source ({p['date']})")
        src = p.get("source") if isinstance(p.get("source"), dict) else {}
        if src.get("path") and (attrs.get("source", {}).get("href") != source_url(src) or f.get("source") != src["path"]):
            found.append(f"{name} : {key} ne mène pas à sa source ({source_url(src)})")
        if f.get("kind", "") != KINDS.get(p.get("kind"), ""):
            found.append(f"{name} : {key} ne dit pas son genre (« {KINDS.get(p.get('kind'), '')} »)")
        if f.get("note", "") != norm(str(p.get("note") or "")):
            found.append(f"{name} : {key} ne porte pas la note de la source")
    for text in page.outside:
        bare = FREE.sub("", text)
        if re.search(r"\d", bare):
            m = re.search(r"\d", bare)
            found.append(f"{name} : un chiffre hors de {PROOFS} : « {norm(bare[max(0, m.start() - 30):m.end() + 30])} »")
    return found, shown


def problems(root: Path = ROOT, today: dt.date | None = None) -> list[str]:
    try:
        data = json.loads((root / PROOFS).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{PROOFS} : illisible ({exc})"]
    proofs = data.get("proofs") if isinstance(data, dict) else None
    found = proof_problems(proofs, root, today)
    if not isinstance(proofs, dict):
        return found
    shown: set[str] = set()
    for rel in PAGES:
        page_found, page_shown = page_problems(proofs, (root / rel).read_text(encoding="utf-8"), rel)
        found += page_found
        shown |= page_shown
    found += [f"{key} : aucune page ne le montre" for key in proofs if key not in shown]
    return found


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["check"]:
        print(__doc__)
        return 2
    found = problems()
    for p in found:
        print(f"✗ {p}")
    if not found:
        print(f"✓ {PROOFS} : chaque chiffre daté et sourcé, chaque page le montre tel quel")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
