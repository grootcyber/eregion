"""MAN1 (#664): the public manual — Eregion's state, component by component, on the project's site.

``docs/manuel/modules.yaml`` is the source a lot's pull request edits; ``scripts/manuel.py`` reads it
(a strict subset of YAML, no library: ``make release`` runs on python3 alone), checks it and writes
``modules.json``, the page's data (``docs/manuel/index.html``, ``manuel.js``). Held here:
- the schema, and the YAML read the same by this file's reader and by PyYAML;
- the public rule: a security brick (lots ``SEC-…``, ``V-<n>``, ``P-0…``) has a neutral name only, no
  note, no document but SECURITY.md; no brick has a field for a gesture or a review; no note on a
  brick not delivered;
- a lot's pull request moves its brick: a fragment ``changes/<LOT>.md`` with no brick on ``main``
  naming LOT fails, read from the same tree;
- the page loads nothing from elsewhere but GitHub's public API, and writes nothing it reads as HTML.
The release's side (main → livree) is in tests/unit/test_release.py.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
MANUEL = DOCS / "manuel"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mn = _load("manuel")
cs = _load("console_shots")

TEXT = (MANUEL / "modules.yaml").read_text(encoding="utf-8")
DATA = mn.load(TEXT)


def _brick(**kw):
    b = {"id": "x-brique", "composant": "glorfindel", "poste": "g-agir", "nom": "Une brique", "etat": "livree",
         "release": "0.5", "version": "0.5.8"}
    b.update(kw)
    return {k: v for k, v in b.items() if v is not None}


def _with(*bricks):
    data = json.loads(json.dumps(DATA))
    data["briques"] = list(bricks)
    return data


# ── the file, its reader, its JSON ──────────────────────────────────────────────────────

def test_the_manual_is_read_the_same_by_its_reader_and_by_pyyaml():
    assert DATA == yaml.safe_load(TEXT)


def test_the_manual_holds_its_schema_and_its_documents_exist():
    assert mn.problems(DATA, ROOT) == []
    assert {c["id"] for c in DATA["composants"]} >= {"glorfindel", "annatar", "gothmog", "orodruin",
                                                     "celebrimbor", "console", "socle"}
    assert [s["version"] for s in DATA["releases"]][:5] == ["0.2", "0.3", "0.4", "0.5", "0.6"]
    assert DATA["releases"][-1]["version"] in ("1.0", "1.x")


def test_the_json_the_page_reads_is_the_yaml_s_own():
    """`make manuel` writes it; a YAML edited without it fails here."""
    assert (MANUEL / "modules.json").read_text(encoding="utf-8") == mn.to_json(DATA)
    assert mn.main(["check"]) == 0


def test_the_published_releases_match_the_changelog():
    """A step published says its last version, the one the CHANGELOG last cut on that line; a
    brick delivered says a version the CHANGELOG has."""
    cut = re.findall(r"(?m)^## \[(\d+\.\d+\.\d+)\]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    for s in DATA["releases"]:
        line = [v for v in cut if v.startswith(s["version"] + ".")]
        if s["etat"] == "publiee":
            assert s["derniere"] == line[0], s
    for b in DATA["briques"]:
        if b["etat"] == "livree":
            assert b["version"] in cut, b["id"]


def test_the_manual_carries_no_identifier():
    """No GUID, no address, no host: what the Dagorlad pages are held to (scripts/console_shots.py)."""
    assert cs.identifiers(TEXT) == []


@pytest.mark.parametrize("text, said", [
    ("briques:\n  - id: a\n    nom: 'simple'\n", "guillemets droits"),
    ('briques:\n  - id: a\n    release: 0.5\n', "guillemets droits"),
    ('briques:\n  - id: a\n    nom: "un \\" dedans"\n', "sans"),
    ("briques:\n  - id: a\n    etat: main  # commentaire\n", "guillemets droits"),
    ("briques:\n  - id: a\n    lots: [SEC-A4, yes]\n", "mots simples"),
    ("briques:\n  - id: a\n      nom: \"trop loin\"\n", "hors du format"),
    ("briques:\n  - id: a\n    nom: \"x\"\n    nom: \"y\"\n", "deux fois"),
])
def test_anything_outside_the_subset_is_refused_with_its_line(text, said):
    with pytest.raises(mn.ManuelError, match=said):
        mn.load(text)


def test_the_reader_and_pyyaml_agree_on_every_form_it_takes():
    text = ('briques:\n  - id: a-b\n    n: 12\n    s: "deux : « mots »"\n    l: [SEC-A4, D-1, CI6b]\n'
            '    e: []\n    z: null\n    t: true\n    p: docs/manuel/index.html\n')
    assert mn.load(text) == yaml.safe_load(text)
    for v in ("0.6", "texte", 42, None, ["A1", "MC0"], True):
        assert mn.load(f"x:\n  - k: {mn.quote(v)}\n") == {"x": [{"k": v}]}


# ── the public rule ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lots", [["SEC-A4"], ["A1", "SEC-D"], ["V-28"], ["P-03"]])
def test_a_security_brick_has_a_neutral_name_and_nothing_else(lots):
    neutral = _brick(lots=lots, issue=633, nom="Durcissement de sécurité (#633)")
    assert mn.problems(_with(neutral)) == []
    for bad, said in ((dict(nom="L'attribution d'une ligne à une VM"), "s'appelle"),
                      (dict(note="Une appliance réseau passait."), "pas de note"),
                      (dict(doc="docs/design/modele-de-menace.md"), "SECURITY.md"),
                      (dict(nom="Durcissement de sécurité (#634)"), "s'appelle")):
        found = mn.problems(_with({**neutral, **bad}))
        assert any(said in p for p in found), (bad, found)
    assert mn.problems(_with({**neutral, "doc": "SECURITY.md"})) == []
    assert mn.problems(_with(_brick(lots=lots, nom="Durcissement de sécurité"))) == []   # no issue


def test_every_security_brick_of_the_manual_is_neutral():
    found = [b for b in DATA["briques"] if mn.sensible(b)]
    assert found, "the manual has security lots in flight (SEC-A4, SEC-A4b)"
    for b in found:
        assert b["nom"] == mn.neutral_name(b) and "note" not in b and b.get("doc") in (None, "SECURITY.md"), b


def test_the_rule_reads_a_finding_or_its_lot_and_nothing_else():
    assert mn.sensible({"lots": ["V-12"]}) and mn.sensible({"lots": ["SEC-A1b"]}) and mn.sensible({"lots": ["P-02"]})
    assert not mn.sensible({"lots": ["SEC12", "DEV-1", "VP1", "P1", "PRES1"]})


@pytest.mark.parametrize("field", ["geste", "relecture", "attend", "attend_jonathan", "verdict"])
def test_no_brick_has_a_field_for_a_gesture_or_a_review(field):
    found = mn.problems(_with(_brick(**{field: "Jonathan applique le plan"})))
    assert any(f"« {field} » n'existe pas" in p for p in found), found


@pytest.mark.parametrize("etat", ["prevue", "dev", "relecture", "main"])
def test_no_note_on_a_brick_not_delivered(etat):
    found = mn.problems(_with(_brick(etat=etat, version=None, note="Ce qui reste à faire.")))
    assert any("une note seulement sur une brique livrée" in p for p in found), found
    assert mn.problems(_with(_brick(note="Ce qui est livré."))) == []


def test_no_brick_of_the_manual_says_anything_of_what_is_not_delivered():
    assert [b["id"] for b in DATA["briques"] if "note" in b and b["etat"] != "livree"] == []


@pytest.mark.parametrize("bad, said", [
    (dict(etat="banc"), "l'état est"),
    (dict(version=None), "sa version"),
    (dict(etat="main"), "une version seulement"),
    (dict(release="0.9"), "n'est pas une étape"),
    (dict(composant="saruman"), "n'existe pas"),
    (dict(poste="a-attaquer"), "est à annatar"),
    (dict(issue="633"), "un numéro"),
    (dict(lots="SEC-A4"), "une liste"),
    (dict(doc="../outside.md"), "un chemin"),
    (dict(id="Pas Un Id"), "un id"),
])
def test_the_schema_refuses_a_brick_out_of_its_shape(bad, said):
    found = mn.problems(_with(_brick(**bad)))
    assert any(said in p for p in found), found


def test_the_schema_refuses_two_bricks_of_one_id_and_two_steps_in_progress():
    assert any("deux fois" in p for p in mn.problems(_with(_brick(), _brick())))
    data = json.loads(json.dumps(DATA))
    data["releases"][-1]["etat"] = "montage"
    assert any("une seule release en montage" in p for p in mn.problems(data))
    data = json.loads(json.dumps(DATA))
    data["releases"][0].pop("derniere")
    assert any("dernière version" in p for p in mn.problems(data))


def test_a_missing_document_is_refused(tmp_path):
    assert any("n'existe pas dans le dépôt" in p for p in mn.problems(_with(_brick(doc="docs/absent.md")), ROOT))


# ── a lot's pull request moves its brick ────────────────────────────────────────────────

def test_every_fragment_of_changes_has_its_brick_on_main():
    """The tree's own changes/ and modules.yaml: a fragment added without its brick fails here."""
    assert mn.unnamed_fragments(ROOT, DATA) == []


def _tree(tmp_path, *fragments):
    (tmp_path / "changes").mkdir()
    (tmp_path / "changes" / "README.md").write_text("# changes/\n", encoding="utf-8")
    for name in fragments:
        (tmp_path / "changes" / f"{name}.md").write_text("### Added\n- **x** (x).\n", encoding="utf-8")
    return tmp_path


def test_a_fragment_without_its_brick_on_main_fails(tmp_path):
    root = _tree(tmp_path, "NEW1", "MAN1")
    data = _with(_brick(id="s-manuel", etat="main", version=None, lots=["MAN1"]))
    assert mn.unnamed_fragments(root, data) == ["NEW1"]
    for etat in ("prevue", "dev", "relecture"):   # named, but its brick not moved to main
        moved = _with(_brick(id="n", etat=etat, version=None, lots=["NEW1"]), _brick(etat="main", version=None, lots=["MAN1"]))
        assert mn.unnamed_fragments(root, moved) == ["NEW1"], etat
    assert mn.unnamed_fragments(root, _with(_brick(etat="livree", lots=["NEW1", "MAN1"]))) == ["MAN1", "NEW1"]
    assert mn.unnamed_fragments(root, _with(_brick(etat="main", version=None, lots=["NEW1", "MAN1"]))) == []
    assert mn.unnamed_fragments(tmp_path / "nowhere", data) == []


def test_check_says_the_lot_whose_brick_was_not_moved(tmp_path, monkeypatch, capsys):
    root = _tree(tmp_path, "NEW1")
    (root / "docs" / "manuel").mkdir(parents=True)
    (root / "docs" / "manuel" / "modules.yaml").write_text(TEXT, encoding="utf-8")
    (root / "docs" / "manuel" / "modules.json").write_text(mn.to_json(DATA), encoding="utf-8")
    monkeypatch.setattr(mn, "_root", lambda: root)
    monkeypatch.setattr(mn, "problems", lambda data, r=None: [])   # its documents are not in this tree
    assert mn.main(["check"]) == 1
    assert "changes/NEW1.md : aucune brique sur main ne nomme NEW1" in capsys.readouterr().out
    (root / "docs" / "manuel" / "modules.json").write_text("{}\n", encoding="utf-8")
    (root / "changes" / "NEW1.md").unlink()
    assert mn.main(["check"]) == 1
    assert "make manuel" in capsys.readouterr().out


# ── the release delivers what is on main (scripts/release.py calls this) ────────────────

def test_a_release_delivers_the_bricks_on_main_and_publishes_its_step():
    out, delivered = mn.deliver(TEXT, "0.6.0", "2026-11-16")
    after = mn.load(out)
    was = {b["id"]: b for b in DATA["briques"]}
    assert delivered == [b["id"] for b in DATA["briques"] if b["etat"] == "main"] and delivered
    for b in after["briques"]:
        if b["id"] in delivered:
            assert (b["etat"], b["version"], b["release"]) == ("livree", "0.6.0", "0.6"), b
        else:
            assert b == was[b["id"]]
    steps = {s["version"]: s for s in after["releases"]}
    assert (steps["0.6"]["etat"], steps["0.6"]["derniere"], steps["0.6"]["date"]) == ("publiee", "0.6.0", "2026-11-16")
    assert steps["0.x"]["etat"] == "montage" and steps["0.5"] == DATA["releases"][3]
    assert mn.problems(after, ROOT) == [] and out.count("\n# ") == TEXT.count("\n# ")   # comments kept


def test_a_patch_delivers_into_its_own_line_and_leaves_the_step_in_progress():
    out, delivered = mn.deliver(TEXT, "0.5.9", "2026-11-10")
    after = mn.load(out)
    for b in after["briques"]:
        if b["id"] in delivered:
            assert (b["version"], b["release"]) == ("0.5.9", "0.5")
    steps = {s["version"]: s for s in after["releases"]}
    assert steps["0.5"]["derniere"] == "0.5.9" and steps["0.6"]["etat"] == "montage"
    assert mn.problems(after, ROOT) == []


def test_a_version_without_its_step_keeps_each_brick_s_release():
    out, delivered = mn.deliver(TEXT, "0.7.0", "2026-12-01")
    after = mn.load(out)
    was = {b["id"]: b for b in DATA["briques"]}
    assert all(b["release"] == was[b["id"]]["release"] for b in after["briques"])
    assert [s for s in after["releases"]] == DATA["releases"]
    assert mn.deliver(out, "0.7.1", "2026-12-02") == (out, [])   # nothing on main any more


# ── the page ────────────────────────────────────────────────────────────────────────────

class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict]] = []
        self.inline: list[str] = []
        self._tag = ""

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k: v or "" for k, v in attrs}))
        self._tag = tag

    def handle_endtag(self, tag):
        self._tag = ""

    def handle_data(self, data):
        if self._tag in ("script", "style") and data.strip():
            self.inline.append(data)


def _page() -> _Page:
    p = _Page()
    p.feed((MANUEL / "index.html").read_text(encoding="utf-8"))
    return p


JS = (MANUEL / "manuel.js").read_text(encoding="utf-8")
CSS = (MANUEL / "manuel.css").read_text(encoding="utf-8")


def test_the_page_runs_only_its_own_script_under_a_policy_that_allows_github_s_api_alone():
    p = _page()
    assert p.inline == [], "no inline script nor style: the policy forbids them"
    assert [a["src"] for t, a in p.tags if t == "script"] == ["manuel.js"]
    assert [a["href"] for t, a in p.tags if t == "link"] == ["manuel.css"]
    assert not [a for _, a in p.tags if "style" in a or any(k.startswith("on") for k in a)]
    (csp,) = [a["content"] for t, a in p.tags if t == "meta" and a.get("http-equiv") == "Content-Security-Policy"]
    rules = {r.split()[0]: r.split()[1:] for r in csp.split(";") if r.strip()}
    assert rules["default-src"] == ["'none'"] and rules["script-src"] == ["'self'"]
    assert rules["style-src"] == ["'self'"] and rules["font-src"] == ["'self'"]
    assert rules["connect-src"] == ["'self'", "https://api.github.com"]


def test_the_page_calls_no_host_but_github_s_api_and_links_only_to_github():
    urls = set(re.findall(r"https?://[^\s\"'`)<>;]+", JS + (MANUEL / "index.html").read_text(encoding="utf-8") + CSS))
    hosts = {urlparse(u).netloc for u in urls}
    assert hosts <= {"github.com", "api.github.com"}, hosts
    assert re.findall(r'const API = "([^"]+)"', JS) == ["https://api.github.com/repos/grootcyber/eregion"]
    fetched = re.findall(r"(?<!function )(?:fetch|getJSON)\(([^,)]+)", JS)
    assert sorted(fetched) == sorted(['"modules.json"', "url", "`${API}/pulls?state=open&per_page=100`",
                                      "`${API}/issues?state=open&per_page=100`", "`${API}/releases?per_page=10`"])
    # Read without a token: no header is ever sent, and no cookie.
    assert "Authorization" not in JS and "headers" not in JS and 'credentials: "omit"' in JS


def test_nothing_read_is_written_as_html():
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function",
                 "setAttribute(\"style\"", "srcdoc"):
        assert sink not in JS, sink
    # An href only through h(), which keeps the repository's links and drops anything else.
    assert JS.count('setAttribute("href"') == 1 and 'if (isRepoUrl(v)) el.setAttribute("href", v);' in JS


def test_the_page_s_fonts_are_the_site_s_own():
    fonts = re.findall(r'url\("([^"]+)"\)', CSS)
    assert fonts and all((MANUEL / f).resolve().is_file() for f in fonts), fonts
    assert all(f.startswith("../replay/fonts/") for f in fonts)
    assert "@import" not in CSS


def test_every_station_of_the_manual_has_its_place_on_the_diagram():
    slots = set(re.findall(r'data-slot="([a-z-]+)"', (MANUEL / "index.html").read_text(encoding="utf-8")))
    assert {p["schema"] for p in DATA["postes"]} <= slots
    assert {p["nature"] for p in DATA["postes"]} <= {"code", "ia", "garde", "humain", "option"}
    for nature in ("code", "ia", "garde", "humain", "option"):
        assert f".station.k-{nature}" in CSS, nature


def test_the_page_says_the_same_rule_as_the_manual():
    assert mn.SENSIBLE.pattern in JS
    for state, label in (("livree", "Livrée"), ("main", "Sur main"), ("relecture", "En relecture"),
                         ("dev", "En développement"), ("prevue", "Prévue")):
        assert re.search(rf'{state}: "{label}', JS), state
    assert set(mn.ETATS) == set(re.findall(r'(\w+): "(?:Prévue|En développement|En relecture|Sur main|Livrée)', JS))


def test_every_link_of_the_page_resolves():
    for t, a in _page().tags:
        href = a.get("href")
        if t != "a" or not href:
            continue
        u = urlparse(href)
        if u.scheme:
            assert u.scheme == "https" and u.netloc == "github.com", href
            if u.path.startswith("/grootcyber/eregion/blob/main/"):
                assert (ROOT / u.path.removeprefix("/grootcyber/eregion/blob/main/")).exists(), href
        else:
            assert (MANUEL / href).resolve().exists(), href


def test_the_readme_and_the_site_lead_to_the_manual():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "https://grootcyber.github.io/eregion/manuel/" in readme
    assert 'href="manuel/"' in (DOCS / "index.html").read_text(encoding="utf-8")
    assert (DOCS / ".nojekyll").is_file()   # Pages serves docs/ as it is
