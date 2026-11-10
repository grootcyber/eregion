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
- the page loads nothing from elsewhere but GitHub's public API, and writes nothing it reads as HTML;
- the manual in English (MAN1b, #676): a text of the YAML that reads French is refused, and the page
  and its script say nothing in French.
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

# What a release delivers is tested on the manual of the tree plus a brick of its own on main: a
# release passes every brick to livree, so the manual it leaves holds none (REL4, #694). Each such
# test runs on both: the manual as it is, and the manual as a release leaves it.
ON_MAIN = """
  - id: t-sur-main
    composant: socle
    poste: s-documenter
    nom: "A brick on main, held by the release's tests"
    etat: main
    release: "0.6"
"""


def _on_main(text):
    return text.rstrip("\n") + "\n" + ON_MAIN


MANUALS = {"as-is": _on_main(TEXT), "released": _on_main(mn.deliver(TEXT, "0.5.9", "2026-11-10")[0])}


def _brick(**kw):
    b = {"id": "x-brique", "composant": "glorfindel", "poste": "g-agir", "nom": "A brick", "etat": "livree",
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
    text = ('issues_securite: [630, 631]\nvide: []\nbriques:\n  - id: a-b\n    n: 12\n    pr: [659, 662]\n    s: "deux : « mots »"\n    l: [SEC-A4, D-1, CI6b]\n'
            '    e: []\n    z: null\n    t: true\n    p: docs/manuel/index.html\n')
    assert mn.load(text) == yaml.safe_load(text)
    for v in ("0.6", "texte", 42, None, ["A1", "MC0"], True):
        assert mn.load(f"x:\n  - k: {mn.quote(v)}\n") == {"x": [{"k": v}]}


# ── the public rule ────────────────────────────────────────────────────────────────────

NEUTRAL = "Security hardening"
SECU = 633   # an issue of the audit, in issues_securite


def _secure(**kw):
    """A security brick as the manual must hold it: neutral, and laid on s-signer until delivered."""
    return _brick(**{"composant": "socle", "poste": "s-signer", "nom": NEUTRAL, **kw})


@pytest.mark.parametrize("lots", [["SEC-A4"], ["A1", "SEC-D"], ["V-28"], ["P-03"]])
def test_a_security_brick_has_a_neutral_name_and_nothing_else(lots):
    neutral = _secure(lots=lots, issue=SECU)
    assert mn.problems(_with(neutral)) == []
    for bad, said in ((dict(nom="A log line attributed to a VM"), "s'appelle"),
                      (dict(note="A network appliance got through."), "pas de note"),
                      (dict(doc="docs/design/modele-de-menace.md"), "SECURITY.md"),
                      (dict(nom="Security hardening (#633)"), "s'appelle")):   # no number either
        found = mn.problems(_with({**neutral, **bad}))
        assert any(said in p for p in found), (bad, found)
    assert mn.problems(_with({**neutral, "doc": "SECURITY.md"})) == []
    assert mn.problems(_with(_secure(lots=lots))) == []   # no issue


def test_a_lot_in_lower_case_is_refused_and_still_read_as_security():
    """The review: `lots: [sec-a4]` with a descriptive name passed — the rule read capitals only."""
    found = mn.problems(_with(_brick(lots=["sec-a4"], nom="A log line attributed to a VM")))
    assert any("une liste de noms de lot" in p for p in found), found
    assert any("s'appelle « Security hardening »" in p for p in found), found
    assert mn.sensible({"lots": ["sec-a4"]}) and mn.sensible({"lots": ["v-05"]}) and mn.sensible({"lots": ["Sec-D"]})
    for lot in ("A1", "SEC-A4", "SEC-A4b", "UI-1", "DG-a", "CI6b", "L1Qs", "PRES1b"):
        assert mn.LOT.fullmatch(lot), lot
    for lot in ("sec-a4", "Sec-A4", "a1", "ci6b"):
        assert not mn.LOT.fullmatch(lot), lot


def test_a_brick_without_lots_whose_issue_is_the_audit_s_is_security():
    """The review: only `issue: 633` and a descriptive name passed."""
    data = _with(_brick(issue=SECU, nom="A log line attributed to a VM", etat="dev", version=None))
    assert SECU in data["issues_securite"]
    found = mn.problems(data)
    assert any("s'appelle « Security hardening »" in p for p in found), found
    assert any("se pose sur s-signer" in p for p in found), found
    pr_only = _with(_brick(pr=[700, SECU], nom="A rule proposal"))
    assert any("s'appelle" in p for p in mn.problems(pr_only))
    flagged = _with(_brick(securite=True, nom="A line attributed wrongly"))
    assert any("s'appelle" in p for p in mn.problems(flagged))
    assert mn.problems(_with(_secure(securite=True))) == []


def test_every_brick_whose_issue_is_the_audit_s_is_neutral():
    secu = set(DATA["issues_securite"])
    assert {630, 631, 632, 633, 634, 635, 636, 638, 642, 644, 654, 660} <= secu
    assert {639, 643, 645, 653, 666} <= secu   # the known security pull requests (SEC-D … SEC-A4)
    assert all(b.get("pr") is None or mn.sensible(b, secu) for b in DATA["briques"]
               if set(mn._prs(b)) & secu)
    named = [b for b in DATA["briques"] if b.get("issue") in secu or set(mn._prs(b)) & secu]
    assert named, "the manual has bricks of the audit (SEC-A1, SEC-A2, SEC-A4, SEC-A4b, SEC-D)"
    for b in named:
        assert mn.sensible(b, secu) and b["nom"] == NEUTRAL and "note" not in b, b


@pytest.mark.parametrize("field, text", [
    ("nom", "A detection line fixes V-05: network appliance"),
    ("note", "Fixes V-05: a network appliance got through."),
    ("note", "Closes sec-a4, the line without _ResourceId."),
    ("nom", "The follow-up of P-02"),
])
def test_no_text_of_any_brick_names_a_finding(field, text):
    """The review: a brick delivered, not a security one, whose note named « V-05 » passed."""
    found = mn.problems(_with(_brick(**{field: text})))
    assert any(f"« {field} » nomme un constat" in p for p in found), found


def test_no_text_of_the_manual_names_a_finding():
    data = json.loads(json.dumps(DATA))
    data["releases"][0]["resume"] = "What followed V-12."
    assert any("« resume » nomme un constat" in p for p in mn.problems(data))


def test_a_security_brick_not_delivered_waits_on_the_neutral_station():
    for etat in ("prevue", "dev", "relecture", "main"):
        placed = _brick(lots=["SEC-A4"], nom=NEUTRAL, etat=etat, version=None, poste="g-detecter")
        assert any("se pose sur s-signer" in p for p in mn.problems(_with(placed))), etat
        assert mn.problems(_with(_secure(lots=["SEC-A4"], etat=etat, version=None))) == []
    assert mn.problems(_with(_brick(lots=["SEC-A2"], nom=NEUTRAL, poste="g-decider"))) == []   # delivered
    for b in DATA["briques"]:
        if mn.sensible(b, DATA["issues_securite"]) and b["etat"] != "livree":
            assert (b["composant"], b["poste"]) == ("socle", "s-signer"), b["id"]


def test_every_security_brick_of_the_manual_is_neutral():
    found = [b for b in DATA["briques"] if mn.sensible(b, DATA["issues_securite"])]
    assert found, "the manual has security lots in flight (SEC-A4b)"
    for b in found:
        assert b["nom"] == NEUTRAL and "note" not in b and b.get("doc") in (None, "SECURITY.md"), b


@pytest.mark.parametrize("field, text", [
    ("nom", "La détection continue par règles"),            # an accented letter
    ("nom", "Le banc en Terraform, jetable"),                # a French word, no accent
    ("note", "Escaladées, jamais autonomes."),
    ("note", "Rien d'autre : une note"),                     # a space before the colon
    ("legende", "les cycles passes, exercice ou reel"),      # « les »
    ("resume", "La boucle mesurée sur du vrai trafic."),
    ("chaine", "Chez le client"),
    ("role", "Le produit : détecte, enquête."),
    ("nom", "« Verify » on the card"),                       # a guillemet
])
def test_a_text_in_french_is_refused(field, text):
    """MAN1b: the public manual is in English, as the site is; a lot's pull request writes its brick in
    English (docs/sessions.md)."""
    data = json.loads(json.dumps(DATA))
    section = {"nom": "briques", "note": "briques", "legende": "postes", "resume": "releases", "chaine": "postes",
               "role": "composants"}[field]
    data[section][0][field] = text
    if section == "briques":
        data["briques"][0]["etat"] = "livree"
    assert any(f"« {field} » est en français" in p for p in mn.problems(data)), (field, text)


@pytest.mark.parametrize("text", [
    "Isolate, block, lift: never another VM cut off",
    "The customer's NSG set aside, then given back: compatible with their Terraform, measured.",
    "Off by default: EREGION_ACTION_QUEUE=1 turns it on.",
    "Autonomy per VM: human_only by default, non_disruptive",
    "Release notes, a label, a set of rules",                # English words that start like French ones
])
def test_a_text_in_english_passes(text):
    assert not mn.FRENCH.search(text), text


def test_every_text_of_the_manual_and_of_its_page_is_in_english():
    """The YAML (its comments too), the page and its script: the public manual reads English (MAN1b)."""
    for name in mn.SECTIONS:
        for it in DATA[name]:
            for k in mn.TEXTS:
                assert not (isinstance(it.get(k), str) and mn.FRENCH.search(it[k])), (name, it.get("id"), k)
    comments = [line for line in TEXT.split("\n") if line.lstrip().startswith("#")]
    assert comments and not [c for c in comments if re.search(r"[àâçéèêëîïôûùüœ]", c)]
    html = (MANUEL / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in html
    p = _page()
    assert not re.search(r"[àâçéèêëîïôûùüœ«»]", html), "the page's text"
    assert not [a for _, a in p.tags for k, v in a.items() if k in ("title", "aria-label") and mn.FRENCH.search(v)]
    strings = re.findall(r'"([^"\n]*)"|`([^`\n]*)`', JS)
    said = [s for pair in strings for s in pair if s and not s.startswith(("${", "#", "."))]
    assert not [s for s in said if re.search(r"[àâçéèêëîïôûùüœ«»]", s)], "the script's text"
    assert '"en-GB"' in JS and '"fr-FR"' not in JS


def test_the_rule_reads_a_finding_or_its_lot_and_nothing_else():
    assert mn.sensible({"lots": ["V-12"]}) and mn.sensible({"lots": ["SEC-A1b"]}) and mn.sensible({"lots": ["P-02"]})
    assert not mn.sensible({"lots": ["SEC12", "DEV-1", "VP1", "P1", "PRES1"]})
    assert not mn.sensible({"lots": ["A1"], "issue": 700}, [633])


@pytest.mark.parametrize("field", ["geste", "relecture", "attend", "attend_jonathan", "verdict"])
def test_no_brick_has_a_field_for_a_gesture_or_a_review(field):
    found = mn.problems(_with(_brick(**{field: "Jonathan applies the plan"})))
    assert any(f"« {field} » n'existe pas" in p for p in found), found


@pytest.mark.parametrize("etat", ["prevue", "dev", "relecture", "main"])
def test_no_note_on_a_brick_not_delivered(etat):
    found = mn.problems(_with(_brick(etat=etat, version=None, note="What remains to be done.")))
    assert any("une note seulement sur une brique livrée" in p for p in found), found
    assert mn.problems(_with(_brick(note="What is released."))) == []


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
    (dict(pr=[659, "x"]), "un numéro"),
    (dict(securite=False), "true ou absent"),
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

@pytest.mark.parametrize("manual", MANUALS.values(), ids=MANUALS.keys())
def test_a_release_delivers_the_bricks_on_main_and_publishes_its_step(manual):
    before = mn.load(manual)
    out, delivered = mn.deliver(manual, "0.6.0", "2026-11-16")
    after = mn.load(out)
    was = {b["id"]: b for b in before["briques"]}
    assert delivered == [b["id"] for b in before["briques"] if b["etat"] == "main"] and "t-sur-main" in delivered
    for b in after["briques"]:
        if b["id"] in delivered:
            assert (b["etat"], b["version"], b["release"]) == ("livree", "0.6.0", "0.6"), b
        else:
            assert b == was[b["id"]]
    steps = {s["version"]: s for s in after["releases"]}
    assert (steps["0.6"]["etat"], steps["0.6"]["derniere"], steps["0.6"]["date"]) == ("publiee", "0.6.0", "2026-11-16")
    assert steps["0.x"]["etat"] == "montage" and steps["0.5"] == before["releases"][3]
    assert mn.problems(after, ROOT) == [] and out.count("\n# ") == manual.count("\n# ")   # comments kept


def test_the_manual_a_release_leaves_holds_no_brick_on_main_but_the_tests_own():
    """The second case above is the one a release makes (REL4, #694)."""
    assert [b["id"] for b in mn.load(MANUALS["released"])["briques"] if b["etat"] == "main"] == ["t-sur-main"]


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
    """Its expression, case-insensitive like the manual's; `securite` and `issues_securite` read; and,
    for a security brick, neither its issue nor its pull request shown."""
    assert f"/{mn.SENSIBLE.pattern}/i;" in JS and mn.SENSIBLE.flags & re.I
    assert "b.securite === true" in JS and "state.data.issues_securite" in JS
    assert "const secret = sensible(b);" in JS and "if (!secret) {" in JS
    assert 'sensible(b) ? "PR open" : `PR #${b.livePr} open`' in JS
    for state, label in (("livree", "Released"), ("main", "On main"), ("relecture", "In review"),
                         ("dev", "In development"), ("prevue", "Planned")):
        assert re.search(rf'{state}: "{label}', JS), state
    assert set(mn.ETATS) == set(re.findall(r'(\w+): "(?:Planned|In development|In review|On main|Released)', JS))


def test_the_page_names_a_security_brick_neutrally_whatever_the_yaml_says():
    """MAN1b: the page's own neutral name, the manual's; every name it writes goes through it."""
    assert f'const NEUTRAL = "{mn.NEUTRAL}";' in JS and mn.NEUTRAL == "Security hardening"
    assert "const nameOf = (b) => (sensible(b) ? NEUTRAL : b.nom);" in JS
    assert JS.count("b.nom") == 1 and JS.count("nameOf(b)") == 3   # the brick, the mini, the sheet


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


def test_the_page_says_a_version_github_has_not_published_yet():
    """The review: a version the repository says cut, GitHub not published, reads « to be published »;
    without the API, the page says it does not know."""
    assert '"a-publier": ", to be published"' in JS and "publication not checked on GitHub" in JS
    assert 'return newer(version, latest.version) ? "a-publier" : "publiee";' in JS
    assert 'if (!latest || !version) return "inconnu";' in JS
    assert '"a-publier": "to be published", inconnu: "published, as the repository says"' in JS
    # The highest version GitHub has published, not the first one listed (a patch on an older line).
    assert ".reduce((best, r) => (!best || newer(r.tag_name.slice(1), best.tag_name.slice(1)) ? r : best), null);" in JS
    assert "list(releases).find(" not in JS


def test_the_socle_s_bricks_show_their_state_on_the_diagram():
    """The review: on the socle's own colour, its bricks were invisible."""
    assert re.search(r"\.socle \.mb \{ --c: #[0-9a-f]{6};", CSS)


def test_the_readme_and_the_site_lead_to_the_manual():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "https://grootcyber.github.io/eregion/manuel/" in readme
    assert 'href="manuel/"' in (DOCS / "index.html").read_text(encoding="utf-8")
    assert (DOCS / ".nojekyll").is_file()   # Pages serves docs/ as it is
