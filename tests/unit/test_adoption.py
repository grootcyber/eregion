"""ADO2 (#671): Eregion by role — the adoption sheets on the project's site, every figure dated and sourced.

``docs/proofs.json`` is the one source of the figures the site shows; ``scripts/adoption.py`` holds the
rule (a figure without its date or its source, a source the repository does not hold, a quote its
file no longer says, a figure on the page that is not in the source: refused). Held here:
- the real source and the real page pass the rule, and each refusal is said;
- the page runs no script under a strict content policy, loads only its stylesheet and the replay's
  fonts, links only to itself, the site and the repository;
- the page says what it does not promise (``full_auto`` planned, the ransomware times from a single
  bench run, the isolation verified only once the sessions are cut), and the README and the home page
  lead to it;
- the ransomware times are those of the bench run of 12/11, and a figure a later fact has overtaken
  (the disruptive actions judged wrong) is shown as one to measure again (MEN4, #748).
"""
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
PAGE = DOCS / "adoption" / "index.html"
CSS = DOCS / "adoption" / "adoption.css"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ad = _load("adoption")
cs = _load("console_shots")

DATA = json.loads((DOCS / "proofs.json").read_text(encoding="utf-8"))
PROOFS = DATA["proofs"]
HTML = PAGE.read_text(encoding="utf-8")
TODAY = dt.date(2026, 11, 9)


def _proof(**kw):
    p = {"value": "0 / 41", "says": "isolations and blocks judged wrong", "date": "2026-11-02", "kind": "measured",
         "source": {"path": "ROADMAP.md", "anchor": "la-finalité-et-ses-cinq-indicateurs",
                    "quote": "0 % sur 41 jugées en 30 jours"}}
    p.update(kw)
    return {k: v for k, v in p.items() if v is not None}


def _found(proof, today=TODAY):
    return ad.proof_problems({"x": proof}, ROOT, today)


def _stat(key="x", proof=None, **override):
    p = proof or _proof()
    f = {"value": p["value"], "says": p["says"], "date": ad.show_date(p["date"]), "datetime": p["date"],
         "href": ad.source_url(p["source"]), "path": p["source"]["path"], "kind": ad.KINDS[p["kind"]]}
    f.update(override)
    kind = f' · <em data-f="kind">{f["kind"]}</em>' if f["kind"] else ""
    return (f'<div class="stat" data-proof="{key}"><b data-f="value">{f["value"]}</b><span data-f="says">{f["says"]}</span>'
            f'<small><time data-f="date" datetime="{f["datetime"]}">{f["date"]}</time> · '
            f'<a data-f="source" href="{f["href"]}">{f["path"]}</a>{kind}</small></div>')


# ── the real source and the real page ──────────────────────────────────────────────────

def test_every_figure_of_the_site_is_dated_sourced_and_shown_as_its_source_says():
    assert ad.problems(ROOT) == []
    assert ad.main(["check"]) == 0


def test_the_source_holds_the_figures_the_page_shows_and_nothing_else():
    shown = {s["key"] for s in ad.read_page(HTML).stats}
    assert shown == set(PROOFS)
    assert len(ad.read_page(HTML).stats) == 27, "three proofs on each of the nine sheets"


def test_the_ransomware_times_come_from_the_bench_run_of_12_11():
    """RAN1 (#665), MEN4 (#748): replayed on the current architecture (Imladris, Orodruin, Dagorlad), the
    ransomware times are measured, dated 12/11 and sourced in the run's page, the run named; the run of
    09/06, from before, is no longer one of the site's figures."""
    for k in ("contain_ransom", "restore_ransom"):
        p = PROOFS[k]
        assert p["kind"] == "measured" and p["date"] == "2026-11-12", k
        assert p["source"]["path"] == "docs/banc-t1486.md" and p["source"]["run"] == "20261112T091448Z-b218", k
    assert PROOFS["last_e2e"]["date"] == "2026-11-12" and PROOFS["last_e2e"]["value"] == "12 Nov"
    assert "20260609T190824Z" not in json.dumps(PROOFS)


def test_the_replay_shows_the_ransomware_times_of_the_bench_run_of_12_11():
    """RAN1b (#820): the replay (docs/replay/, PRES1) marks the times it shows « measured »; they are
    those of the bench run of 12/11 the README and the sheets give, from docs/proofs.json — the time to
    contain, the time to restored service, and the detection and isolation that make the second
    (« 141,6 + 19,5 + 1514 »). Before, it still said those of 09/06: « about a minute to contain »,
    « 21 min 29 s », a detection in « 55–71 s »."""
    replay = (DOCS / "replay" / "index.html").read_text(encoding="utf-8")
    contain, restore = PROOFS["contain_ransom"], PROOFS["restore_ransom"]
    assert contain["date"] == restore["date"] == "2026-11-12"
    for p in (contain, restore):
        assert p["value"] in replay, p["value"]
    # The detection and the isolation, as the restore's own quote adds them.
    m = re.search(r"(\d+),(\d) \+ (\d+),(\d) \+ \d+ = ", " ".join(ad.quotes(restore["source"])))
    detected, isolated = f"{m[1]}.{m[2]} s", f"{m[3]}.{m[4]} s"
    # Each marked measured where it shows: the flag 1 of the bar under the scene (`benchRef`), the
    # « measured » label of the closing cards (review, RAN1b).
    excluded = "the human’s wait excluded"
    for said in (f"['detected {detected} after T0',1]", f":['quarantined {isolated} after the detection',1]",
                 f":['contained in {contain['value']}, verified on Azure',1]",
                 f":['{restore['value']} to restored service, {excluded}',1]"):
        assert said in replay, said
    for value in (detected, contain["value"], restore["value"]):
        assert re.search(rf'<b>{re.escape(value)}</b><span>[^<]*</span><span class="meas">measured</span>',
                         replay), value
    # The time to restored service leaves out the human's wait, as the README and the proof say it: never
    # read as one from end to end, beside « 1 click approving the restore ».
    assert "the human's wait excluded" in restore["says"]
    assert replay.count(f"{restore['value']} to restored service, {excluded}") == 2
    assert f"<b>{restore['value']}</b><span>to restored service, {excluded}</span>" in replay
    assert replay.count("12 November 2026") == 2       # the closing caption and the foot
    for gone in ("21 min 29 s", "about a minute to contain", "about 1 min", "~1 min", "55–71 s", "the validated runs"):
        assert gone not in replay, gone


def test_a_measure_to_take_again_says_so_on_the_page():
    """Bree's isolation of 10/11, judged wrong on 11/11, overtakes « 0 / 41 » of 02/11: the figure stays,
    shown as one to measure again, with why (MEN4, #748)."""
    again = {k for k, p in PROOFS.items() if p["kind"] == "to-remeasure"}
    assert again == {"wrong_disruptive"}
    for s in ad.read_page(HTML).stats:
        if s["key"] in again:
            assert ad.norm(s["fields"]["kind"]) == "to be re-measured" and s["fields"]["note"].strip()


def test_the_figures_of_the_private_preview_that_the_repository_does_not_hold_are_gone():
    """ADO1 v2 showed costs published by vendors, a test count, a catalogue size, a proof a month:
    nothing in the repository dates them, so they are not here (and a digit outside a proof fails)."""
    text = ad.norm(" ".join(ad.read_page(HTML).outside))
    for gone in ("k€", "12 / year", "the only human step", "5 200", "3 350", "0 / 21"):
        assert gone not in HTML, gone
    assert not re.search(r"\d", ad.FREE.sub("", text))


# ── the rule on a figure ───────────────────────────────────────────────────────────────

def test_a_figure_with_its_date_its_kind_and_its_source_passes():
    assert _found(_proof()) == []
    assert _found(_proof(date="2026-10")) == []   # a month
    assert ad.show_date("2026-10") == "Oct 2026" and ad.show_date("2026-11-02") == "2 Nov 2026"


@pytest.mark.parametrize("bad, said", [
    (dict(date=None), "sans date"),
    (dict(date="02/11/2026"), "sans date"),
    (dict(date="2026-13-01"), "sans date"),
    (dict(date="2026-11-30"), "à venir"),
    (dict(kind=None), "son genre"),
    (dict(kind="hearsay"), "son genre"),
    (dict(kind="to-remeasure"), "dit pourquoi"),
    (dict(value="none"), "un chiffre"),
    (dict(says=""), "ce qu'il mesure"),
    (dict(source=None), "sans source"),
    (dict(when="today"), "n'existe pas"),
])
def test_a_figure_without_its_date_kind_or_source_is_refused(bad, said):
    found = _found(_proof(**bad))   # a None drops the field
    assert any(said in p for p in found), found


@pytest.mark.parametrize("source, said", [
    ({"path": "docs/absent.md", "quote": "x"}, "n'existe pas dans le dépôt"),
    ({"path": "../outside.md", "quote": "x"}, "un chemin du dépôt"),
    ({"path": "/etc/hostname", "quote": "x"}, "un chemin du dépôt"),
    ({"path": "ROADMAP.md"}, "cite la phrase"),
    ({"path": "ROADMAP.md", "anchor": "nowhere", "quote": "0 % sur 41 jugées en 30 jours"}, "pas de titre"),
    ({"path": "ROADMAP.md", "anchor": "les-lots", "quote": "0 % sur 41 jugées en 30 jours"}, "ne dit plus"),
    ({"path": "ROADMAP.md", "quote": "0 % sur 42 jugées en 30 jours"}, "ne dit plus"),
    ({"path": "ROADMAP.md", "quote": "0 % sur 41 jugées en 30 jours", "run": "20990101T000000Z"}, "ne nomme pas le run"),
    ({"path": "ROADMAP.md", "quote": "0 % sur 41 jugées en 30 jours", "line": 27}, "n'existe pas"),
])
def test_a_source_the_repository_does_not_hold_is_refused(source, said):
    found = _found(_proof(source=source))
    assert any(said in p for p in found), found


def test_a_quote_that_does_not_give_the_figure_is_refused():
    found = _found(_proof(value="0 / 42"))
    assert any("« value » dit 42" in p for p in found), found


@pytest.mark.parametrize("field, text", [
    ("says", "isolations and blocks judged wrong, over 90 days"),   # the review: 30 days became 90, passed
    ("note", "a run of 2025, to be replayed"),
])
def test_a_number_of_what_a_figure_says_or_of_its_note_that_no_quote_gives_is_refused(field, text):
    found = _found(_proof(**{field: text}))
    assert any(f"« {field} » dit" in p for p in found), found
    assert _found(_proof(says="isolations and blocks judged wrong, over 30 days")) == []


def test_several_quotes_give_the_numbers_together_and_each_must_be_said():
    two = {"path": "README.md", "quotes": ["Over 30 days:", "detection in 107 s and a decision in 2 min (medians)"]}
    assert _found(_proof(value="107 s", says="median time to detect, over 30 days", source=two)) == []
    one = {"path": "README.md", "quote": "detection in 107 s and a decision in 2 min (medians)"}
    assert any("« says » dit 30" in p for p in _found(_proof(value="107 s", says="over 30 days", source=one)))
    lost = {"path": "README.md", "quotes": ["Over 30 days:", "detection in 106 s"]}
    assert any("ne dit plus « detection in 106 s »" in p for p in _found(_proof(value="107 s", source=lost)))
    for bad in ({"path": "README.md", "quotes": []}, {"path": "README.md", "quotes": "Over 30 days:"},
                {"path": "README.md", "quote": "Over 30 days:", "quotes": ["Over 30 days:"]}):
        assert any("cite la phrase" in p for p in _found(_proof(source=bad))), bad


def test_a_number_a_source_writes_in_words_gives_it_but_not_an_article():
    """docs/design/console.md says « cinq adresses » for the 5 blocks; « un » or « one » is no figure."""
    assert ad.numbers("Glorfindel a bloqué seul cinq adresses", words=True) == ["5"]
    assert ad.numbers("un instantané, one card, une carte", words=True) == []
    assert PROOFS["blocked_alone"]["source"]["path"] == "docs/design/console.md"


def test_a_quote_is_read_across_line_breaks_and_within_its_section():
    text = "# Top\n\n## A section\n\nit says 0 % sur\n41 jugées en 30 jours.\n\n## Another\n\nelse\n"
    assert "41" in ad.section(text, "a-section") and "else" not in ad.section(text, "a-section")
    assert ad.norm("0 % sur 41 jugées") in ad.norm(ad.section(text, "a-section"))
    assert ad.section(text, "another").strip() == "else" and ad.section(text, "nope") is None
    assert ad.section("```\n# not a heading\n```\n# Real\nx\n", "not-a-heading") is None


def test_the_heading_ids_are_github_s():
    assert ad.slug("La finalité et ses cinq indicateurs") == "la-finalité-et-ses-cinq-indicateurs"
    assert ad.slug("L'implémentation (19/10)") == "limplémentation-1910"
    assert ad.slug("4. Le fournisseur du modèle") == "4-le-fournisseur-du-modèle"
    assert ad.slug("Les cinq indicateurs (UI-2, #206)") == "les-cinq-indicateurs-ui-2-206"


# ── the rule on a page ─────────────────────────────────────────────────────────────────

def test_a_figure_shown_as_its_source_says_passes():
    found, shown = ad.page_problems({"x": _proof()}, f"<p>Read the figure.</p>{_stat()}")
    assert found == [] and shown == {"x"}


@pytest.mark.parametrize("override, said", [
    (dict(value="0 / 40"), "montre « 0 / 40 »"),
    (dict(says="none judged wrong"), "ne dit pas ce que dit"),
    (dict(date="3 Nov 2026"), "n'a pas la date"),
    (dict(datetime="2026-11-03"), "n'a pas la date"),
    (dict(href="https://github.com/grootcyber/eregion/blob/main/README.md"), "ne mène pas à sa source"),
    (dict(path="README.md"), "ne mène pas à sa source"),
    (dict(kind="estimate"), "son genre"),
])
def test_a_figure_shown_otherwise_than_its_source_is_refused(override, said):
    found, _ = ad.page_problems({"x": _proof()}, _stat(**override))
    assert any(said in p for p in found), found


def test_a_figure_of_the_page_not_in_the_source_is_refused():
    for html in ("<p>Contained in 45 s.</p>", "<p>One 3-step guide.</p>", '<a title="12 runs" href="#">x</a>',
                 '<img alt="5 attacks" src="x.png">', _stat(key="absent")):
        found, _ = ad.page_problems({"x": _proof()}, html)
        assert found, html
    found, _ = ad.page_problems({"x": _proof()}, "<p>T1486, T1136.001 and Apache 2.0 are no figures.</p>")
    assert found == []
    found, _ = ad.page_problems({"x": _proof()}, "<style>.a{width:12px}</style><p>a</p>")
    assert found == []


def test_a_card_says_nothing_outside_its_fields():
    """The review: « 99% of attacks stopped. » in a card, outside any data-f, was thrown away unread."""
    for loose in ("99% of attacks stopped.", "Stopped everything."):
        card = _stat().replace("</small>", f"</small><p>{loose}</p>")
        found, _ = ad.page_problems({"x": _proof()}, card)
        assert any("hors de ses champs" in p for p in found), (loose, found)
    found, _ = ad.page_problems({"x": _proof()}, _stat())
    assert found == []   # the separators « · » only


@pytest.mark.parametrize("html", [
    '<div class="stat" data-proof="x" title="99% contained"></div>',
    '<span aria-label="12 attacks blocked">x</span>',
    '<div data-proof="x"><b data-f="value" aria-label="contained in 1 min">0 / 41</b></div>',
    '<img alt="5 attacks" src="x.png">',
    '<meta name="description" content="Eregion stops 99% of attacks.">',
    '<meta property="og:description" content="contained in 1 minute">',
])
def test_a_figure_in_a_title_a_label_or_a_meta_is_refused(html):
    found, _ = ad.page_problems({"x": _proof()}, html + _stat())
    assert any("un chiffre hors de" in p for p in found), found


def test_the_viewport_and_an_issue_s_number_are_no_figures():
    html = '<meta name="viewport" content="width=device-width, initial-scale=1"><p>Planned (#668).</p>' + _stat()
    assert ad.page_problems({"x": _proof()}, html)[0] == []
    assert ad.page_problems({"x": _proof()}, "<p>Planned in 668 days.</p>" + _stat())[0]


def test_check_says_where_to_fix_a_figure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ad, "problems", lambda: ["x : sans date"])
    assert ad.main(["check"]) == 1
    out = capsys.readouterr().out
    assert "docs/proofs.json and the page in the same pull request" in out and "docs/sessions.md" in out


def test_a_proof_no_page_shows_is_refused(tmp_path):
    (tmp_path / "docs" / "adoption").mkdir(parents=True)
    (tmp_path / "ROADMAP.md").write_text((ROOT / "ROADMAP.md").read_text(encoding="utf-8"), encoding="utf-8")
    proofs = {"x": _proof(), "y": copy.deepcopy(_proof())}
    (tmp_path / "docs" / "proofs.json").write_text(json.dumps({"proofs": proofs}), encoding="utf-8")
    (tmp_path / "docs" / "adoption" / "index.html").write_text(_stat(), encoding="utf-8")
    assert ad.problems(tmp_path, TODAY) == ["y : aucune page ne le montre"]
    (tmp_path / "docs" / "proofs.json").write_text("{", encoding="utf-8")
    assert "illisible" in ad.problems(tmp_path, TODAY)[0]


# ── the page itself ────────────────────────────────────────────────────────────────────

class _Tags(HTMLParser):
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


def _tags() -> _Tags:
    p = _Tags()
    p.feed(HTML)
    return p


def test_the_page_runs_no_script_under_a_policy_that_allows_only_itself():
    p = _tags()
    assert p.inline == [] and not [t for t, _ in p.tags if t in ("script", "iframe", "object", "embed", "form", "base")]
    assert [a["href"] for t, a in p.tags if t == "link"] == ["adoption.css"]
    assert not [a for _, a in p.tags if "style" in a or any(k.startswith("on") for k in a)]
    (csp,) = [a["content"] for t, a in p.tags if t == "meta" and a.get("http-equiv") == "Content-Security-Policy"]
    rules = {r.split()[0]: r.split()[1:] for r in csp.split(";") if r.strip()}
    assert rules["default-src"] == ["'none'"] and "script-src" not in rules and "connect-src" not in rules
    assert rules["style-src"] == ["'self'"] and rules["font-src"] == ["'self'"]
    assert '<html lang="en">' in HTML and '<meta name="viewport"' in HTML and "<title>Eregion by role</title>" in HTML


def test_the_page_loads_only_the_replay_s_fonts():
    css = CSS.read_text(encoding="utf-8")
    assert "@import" not in css
    urls = re.findall(r"url\(([^)]*)\)", css)
    assert urls and all(u.strip("\"'").startswith("../replay/fonts/") for u in urls)
    for u in urls:
        assert (CSS.parent / u.strip("\"'")).resolve().is_file(), u


def test_every_link_of_the_page_resolves():
    p = _tags()
    ids = {a["id"] for _, a in p.tags if a.get("id")}
    hrefs = [a["href"] for t, a in p.tags if t == "a"]
    assert hrefs
    for href in hrefs:
        u = urlparse(href)
        if u.scheme:
            assert u.scheme == "https" and u.netloc == "github.com", href
            if u.path.startswith("/grootcyber/eregion/blob/main/"):
                assert (ROOT / u.path.removeprefix("/grootcyber/eregion/blob/main/")).is_file(), href
        elif href.startswith("#"):
            assert href[1:] in ids, href
        else:
            assert (PAGE.parent / href.split("#")[0]).resolve().exists(), href


def test_the_page_has_a_sheet_per_reader_each_with_its_parts():
    p = _tags()
    roles = [a["id"] for t, a in p.tags if t == "article"]
    assert roles == ["ciso", "cdio", "cto", "secu", "sre", "dpo", "mssp", "audit", "cfo"]
    for role in roles:
        sheet = HTML.split(f'id="{role}"', 1)[1].split("</article>", 1)[0]
        for part in ("The fear:", "What changes", "Show, in five minutes", "The objection", "Next step", 'class="stats"'):
            assert part in sheet, (role, part)
        assert sheet.count("data-proof=") == 3, role


def test_the_page_says_what_it_does_not_promise():
    limits = ad.norm(HTML.split('id="h-limits"', 1)[1].split("</section>", 1)[0])
    for said in ("<code>full_auto</code> is planned, not available", "detection only", "Not a SOC",
                 "come from a single bench run", "lifts the isolation by itself", "proven on Azure (#668)",
                 "once the open sessions are cut", "No hosted offer"):
        assert said in limits, said
    assert "side by side" not in HTML, "several customers on one host: neither documented nor proven"
    assert "in progress" not in limits
    assert "full_auto" not in HTML.replace("<code>full_auto</code> is planned, not available", "")


def test_the_page_is_not_sold_on_a_compliance_framework():
    for word in ("NIS2", "NIS 2", "DORA", "ISO", "SOC 2", "GDPR", "compliant"):
        assert not re.search(rf"\b{word}\b", HTML), word


def test_the_page_and_its_source_carry_no_identifier():
    assert cs.identifiers(HTML) == []
    assert cs.identifiers(json.dumps(DATA, ensure_ascii=False)) == []


def test_the_readme_and_the_home_page_lead_to_the_page():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "(https://grootcyber.github.io/eregion/adoption/)" in readme
    assert readme.index("eregion/adoption/") > readme.index("eregion/manuel/)")
    assert 'href="adoption/"' in (DOCS / "index.html").read_text(encoding="utf-8")
