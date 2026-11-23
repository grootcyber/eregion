"""ENQ3 (#1077): the knowledge base of the enquiry — the seed `fiches/T1486.yaml` and its validator, the
store of the evolutions, the weights and the rules of a lesson (`docs/design/enquete-raisonnee.md` §2.3,
§3). No reader in production: the graph, the watch and `investigate` never import it."""
from __future__ import annotations

import ast
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from glorfindel.enquiry import catalog, evolutions as ev, knowledge as k

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "glorfindel" / "enquiry" / "fiches" / "T1486.yaml"


def seed() -> dict:
    return yaml.safe_load(SEED.read_text(encoding="utf-8"))


def fiche() -> k.Fiche:
    return k.lire_fiche(SEED)


def hyp(hid: str) -> k.Hypothese:
    return next(h for h in fiche().hypotheses if h.id == hid)


def lecon(hid, genre, verdict, **kw) -> k.Lecon:
    return k.Lecon(hid, genre, verdict, ref=kw.pop("ref", "carte-1"), **kw)


def write(tmp_path: Path, data, name="T1486.yaml") -> Path:
    folder = tmp_path / "fiches"
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text(data if isinstance(data, str) else yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ── The seed ──────────────────────────────────────────────────────────────────────────────────────

def test_the_shipped_seed_loads_whole_no_sheet_refused():
    base = k.charger()
    assert dict(base.refusees) == {}
    assert list(base.fiches) == ["T1486"]
    t1486 = base.pour("ransomware-disk-write")
    assert t1486 is base.fiches["T1486"] and t1486.grave is True
    assert t1486.obligatoires == ("perf_minute_series", "vault_jobs", "vault_activity")


def test_the_seed_holds_the_nine_hypotheses_of_the_note_their_sense_effect_and_state():
    """What Jonathan reviews (§2.3): any change to a sense, an effect or a state goes through a PR."""
    got = [(h.id, h.sens, h.effet, h.etat) for h in fiche().hypotheses]
    assert got == [
        ("T1486-H1", "confirme", "resserre", "mesuree"),
        ("T1486-H2", "infirme", "relache", "mesuree"),
        ("T1486-H3", "aucun", "aucun", "mesuree"),
        ("T1486-H4", "confirme", "resserre", "supposee"),
        ("T1486-H5", "confirme", "resserre", "supposee"),
        ("T1486-H6", "confirme", "resserre", "supposee"),
        ("T1486-H7", "confirme", "resserre", "supposee"),
        ("T1486-H8", "infirme", "relache", "supposee"),
        ("T1486-H9", "infirme", "relache", "supposee"),
    ]
    assert set(hyp("T1486-H1").predicat) == {"confirme", "infirme", "sinon"}
    assert hyp("T1486-H8").predicat == {}       # no predicate: H8 never dispenses the guard (§7.3)


def test_the_seed_s_rule_is_a_shipped_rule_of_its_technique():
    rules = yaml.safe_load((ROOT / "glorfindel/rules/azure/detection_rules.yaml").read_text(encoding="utf-8"))
    ttp = {r["name"]: r.get("ttp") for r in rules["rules"]}
    for name in fiche().regles:
        assert ttp[name] == "T1486"


def test_the_seed_cites_code_that_exists():
    """A `code` source names a file of the repository and lines within it."""
    for h in fiche().hypotheses:
        for s in h.sources:
            if s.genre == "code":
                rel, lines = s.ref.split(" ")[0].split(":")
                assert int(lines.split("-")[-1]) <= len((ROOT / rel).read_text(encoding="utf-8").splitlines())


def test_each_read_named_is_in_the_catalogue_or_announced_and_announced_ones_are_none_of_the_catalogue():
    named = {r for h in fiche().hypotheses for r in h.lectures} | set(fiche().obligatoires)
    assert named <= set(catalog.READS) | set(k.ANNONCEES)
    assert not set(k.ANNONCEES) & set(catalog.READS)    # a read that enters the catalogue leaves the list
    assert set(k.ANNONCEES) <= named                    # no announced read that no sheet names
    for rid in k.ANNONCEES:
        assert isinstance(catalog.ask(rid), catalog.Reading)   # never served: no query runs from it


# ── The validator ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("where", ["fiche", "hypothese", "source", "predicat"])
def test_an_unknown_key_is_refused_at_every_level(where):
    data = seed()
    target = {"fiche": data, "hypothese": data["hypotheses"][0],
              "source": data["hypotheses"][0]["sources"][0], "predicat": data["hypotheses"][0]["predicat"]}[where]
    target["poids"] = 1.0
    with pytest.raises(k.FicheRefusee, match="clé inconnue"):
        k.valider(data)


def test_a_lifted_by_is_no_key_of_a_sheet_the_base_never_lifts_a_ceiling():
    data = seed()
    data["lifted_by"] = ["vault_activity"]
    with pytest.raises(k.FicheRefusee, match="clé inconnue"):
        k.valider(data)


def _mutate(path, value):
    data = seed()
    node = data
    for key in path[:-1]:
        node = node[key]
    if value is KeyError:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return data


@pytest.mark.parametrize("path,value,why", [
    (("hypotheses", 0, "limite"), KeyError, "clé manquante"),
    (("hypotheses", 0, "lectures"), ["perf_minute_serie"], "ni au catalogue ni annoncée"),
    (("obligatoires",), ["vault_job"], "ni au catalogue ni annoncée"),
    (("hypotheses", 1, "effet"), "resserre", "sens infirme et effet resserre"),
    (("hypotheses", 2, "effet"), "relache", "sens aucun"),
    (("hypotheses", 3, "etat"), "proposee", "hors de"),
    (("hypotheses", 3, "etat"), "contestee", "hors de"),
    (("hypotheses", 3, "etat"), "mesuree", "mesurée sans une source du banc"),
    (("hypotheses", 0, "sources", 0, "genre"), "modele", "hors de"),
    (("hypotheses", 0, "sources", 0, "date"), "12/11/2026", "AAAA-MM-JJ"),
    (("hypotheses", 0, "predicat"), {"sinon": "inconnu"}, "ce qui confirme ou ce qui infirme"),
    (("hypotheses", 0, "predicat"), "la moyenne dépasse 25", "un dictionnaire attendu"),
    (("hypotheses", 0, "predicat", "confirme"), "", "un texte non vide"),
    (("hypotheses", 1, "id"), "T1486-H1", "en double"),
    (("hypotheses", 1, "id"), "T1490-H2", "n'est pas T1486-H<n>"),
    (("grave",), False, "GRAVE_TTPS"),
    (("grave",), "oui", "GRAVE_TTPS"),
    (("technique",), "ransomware", "identifiant ATT&CK"),
    (("regles",), [], "une liste non vide"),
    (("hypotheses",), [], "une liste non vide"),
])
def test_a_sheet_that_does_not_hold_is_refused_and_says_why(path, value, why):
    with pytest.raises(k.FicheRefusee, match=why):
        k.valider(_mutate(path, value))


def test_an_obligatory_read_no_hypothesis_uses_is_refused():
    with pytest.raises(k.FicheRefusee, match="ne sert à aucune hypothèse"):
        k.valider(_mutate(("obligatoires",), ["perf_minute_series", "top_write_processes"]))


def test_a_key_given_twice_is_refused_never_the_last_one_kept(tmp_path):
    text = SEED.read_text(encoding="utf-8").replace("    etat: supposee\n", "    etat: supposee\n    etat: mesuree\n", 1)
    with pytest.raises(k.FicheRefusee, match="clé en double"):
        k.lire_fiche(write(tmp_path, text))


def test_an_unquoted_date_is_refused(tmp_path):
    text = SEED.read_text(encoding="utf-8").replace('date: "2026-11-12"', "date: 2026-11-12", 1)
    with pytest.raises(k.FicheRefusee, match="AAAA-MM-JJ"):
        k.lire_fiche(write(tmp_path, text))


def test_a_sheet_is_named_by_its_technique(tmp_path):
    with pytest.raises(k.FicheRefusee, match="porte le nom de sa technique"):
        k.lire_fiche(write(tmp_path, SEED.read_text(encoding="utf-8"), "T1490.yaml"))


# ── Reading the seed: an unreadable seed is an error, never an empty base ─────────────────────────

def test_a_seed_folder_absent_is_an_error_never_an_empty_base(tmp_path):
    with pytest.raises(k.GraineIllisible, match="illisible"):
        k.charger(tmp_path / "absent")


def test_a_seed_folder_without_a_sheet_is_an_error(tmp_path):
    (tmp_path / "fiches").mkdir()
    (tmp_path / "fiches" / "README.md").write_text("rien", encoding="utf-8")
    with pytest.raises(k.GraineIllisible, match="aucune fiche"):
        k.charger(tmp_path / "fiches")


@pytest.mark.parametrize("text", ["", "technique: [T1486\n", "- une\n- liste\n", "\xff"])
def test_an_unreadable_sheet_is_refused_and_said_never_read_empty(tmp_path, text):
    write(tmp_path, SEED.read_text(encoding="utf-8"))
    path = tmp_path / "fiches" / "T1490.yaml"
    path.write_bytes(text.encode("latin-1"))
    base = k.charger(tmp_path / "fiches")
    assert list(base.fiches) == ["T1486"]
    assert "T1490.yaml" in base.refusees and base.refusees["T1490.yaml"]
    assert base.pour("x", "T1490") is None      # the rule keeps the base enquiry


def test_a_rule_two_sheets_claim_is_refused_in_the_second(tmp_path):
    write(tmp_path, SEED.read_text(encoding="utf-8"))
    other = seed()
    other["technique"], other["grave"] = "T1490", True
    for h in other["hypotheses"]:
        h["id"] = h["id"].replace("T1486", "T1490")
    write(tmp_path, other, "T1490.yaml")
    base = k.charger(tmp_path / "fiches")
    assert list(base.fiches) == ["T1486"] and "déjà enquêtée" in base.refusees["T1490.yaml"]


def test_a_rule_finds_its_sheet_by_name_then_by_technique():
    base = k.charger()
    assert base.pour("ransomware-disk-write").technique == "T1486"
    assert base.pour("une-regle-du-client", "T1486").technique == "T1486"
    assert base.pour("brute-force-ssh", "T1110") is None


# ── The weights (§3.3) ────────────────────────────────────────────────────────────────────────────

def test_the_weights_bench_verdict_dossier_model():
    assert k.poids("banc") == 1.0 and k.poids("verdict") == 0.8 and k.poids("modele") == 0.1
    assert k.poids("dossier", catalog.PLATFORM) == 0.5 and k.poids("dossier", k.GLORFINDEL) == 0.5
    assert k.poids("dossier", catalog.GUEST_FORGEABLE) == 0.2 and k.poids("dossier", catalog.GUEST_PROVOCABLE) == 0.2
    assert k.poids("dossier") == 0.2            # an author unknown weighs as the guest
    with pytest.raises(ValueError):
        k.poids("externe")


# ── The asymmetry (§3.4): what relaxes never applies without a human's accord ─────────────────────

def test_a_lesson_that_relaxes_never_applies_without_an_accord():
    h2 = hyp("T1486-H2")                       # infirms, relaxes: « a short peak at a backup's start »
    sans = lecon("T1486-H2", "verdict", "confirme")
    got = k.evoluer(h2, [sans])
    assert got.confirmations == 0.0 and got.en_attente_accord == (sans,)
    avec = lecon("T1486-H2", "verdict", "confirme", accord="carte-7")
    got = k.evoluer(h2, [avec])
    assert got.confirmations == 0.8 and got.en_attente_accord == ()


def test_credit_taken_from_what_tightens_relaxes_too():
    h1 = hyp("T1486-H1")
    contre = lecon("T1486-H1", "verdict", "contredit")
    assert k.direction(contre, h1.effet) == k.RELACHE
    assert k.evoluer(h1, [contre]).etat == "mesuree"            # not contested without an accord
    contre_accord = lecon("T1486-H1", "verdict", "contredit", accord="carte-8")
    assert k.evoluer(h1, [contre_accord]).etat == "contestee"


def test_what_tightens_applies_alone():
    h2 = hyp("T1486-H2")
    assert k.evoluer(h2, [lecon("T1486-H2", "verdict", "contredit")]).etat == "contestee"
    h4 = hyp("T1486-H4")
    assert k.evoluer(h4, [lecon("T1486-H4", "banc", "confirme", ref="drill-1")]).etat == "mesuree"


def test_the_bench_never_measures_what_relaxes_only_a_pr_does():
    h8 = hyp("T1486-H8")
    for accord in ("", "carte-9"):
        assert k.evoluer(h8, [lecon("T1486-H8", "banc", "confirme", accord=accord)]).etat == "supposee"


def test_a_human_verdict_contests_never_a_dossier_s_fact():
    h2 = hyp("T1486-H2")
    platform = [lecon("T1486-H2", "dossier", "contredit", auteur=catalog.PLATFORM) for _ in range(4)]
    got = k.evoluer(h2, platform)
    assert got.etat == "mesuree" and got.contradictions == 2.0
    guest = [lecon("T1486-H2", "dossier", "contredit", auteur=catalog.GUEST_FORGEABLE) for _ in range(10)]
    got = k.evoluer(h2, guest)
    assert got.etat == "mesuree" and got.contradictions == 2.0  # counted, never a change of state


# ── The model alone never changes a state, never counts ───────────────────────────────────────────

def test_the_model_alone_never_changes_a_state():
    h2, h4 = hyp("T1486-H2"), hyp("T1486-H4")
    many = [lecon("T1486-H2", "modele", "contredit", ref=f"cycle-{i}") for i in range(20)]
    got = k.evoluer(h2, many)
    assert got.etat == "mesuree" and got.contradictions == 0.0
    got = k.evoluer(h4, [lecon("T1486-H4", "modele", "confirme", ref=f"cycle-{i}") for i in range(20)])
    assert got.etat == "supposee" and got.confirmations == 0.0


def test_a_weight_written_in_the_store_is_never_read_back_the_source_s_is(tmp_path):
    store = ev.Evolutions(tmp_path / "k.sqlite")
    with sqlite3.connect(store.path) as conn:
        conn.execute("INSERT INTO evenements (hypothese, genre, auteur, verdict, ref, accord, texte, effet, poids, "
                     "date) VALUES ('T1486-H2', 'modele', '', 'contredit', 'cycle-1', '', '', '', 0.95, 'x')")
    lecons, refus = store.lire()
    assert refus == [] and k.evoluer(hyp("T1486-H2"), lecons).etat == "mesuree"


# ── A hypothesis proposed is never shown to the model ─────────────────────────────────────────────

def test_a_hypothesis_proposed_is_shown_to_the_human_never_to_the_model():
    f = fiche()
    proposed = lecon("T1486-P1", "modele", "propose", texte="Un chiffrement lent, à cheval sur deux minutes")
    human = k.evolutions(f, [proposed])
    assert [(v.id, v.etat, v.effet) for v in human[-1:]] == [("T1486-P1", "proposee", "aucun")]
    model = k.vue_modele(f, [proposed])
    assert [v.id for v in model] == [h.id for h in f.hypotheses]
    other = lecon("T1490-P1", "verdict", "propose", texte="ailleurs")
    assert "T1490-P1" not in {v.id for v in k.evolutions(f, [other])}


def test_a_hypothesis_withdrawn_is_not_shown_to_the_model():
    data = seed()
    data["hypotheses"][8]["etat"] = "retiree"
    f = k.valider(data)
    assert "T1486-H9" not in {v.id for v in k.vue_modele(f, [])}
    assert k.evoluer(f.hypotheses[8], [lecon("T1486-H9", "banc", "contredit")]).etat == "retiree"


# ── `effet` is never learned ──────────────────────────────────────────────────────────────────────

def test_effet_is_never_learned_a_lesson_asking_it_waits_for_a_pr():
    h2 = hyp("T1486-H2")
    ask = lecon("T1486-H2", "verdict", "requalifie", effet="resserre")
    confirm = lecon("T1486-H2", "verdict", "confirme")
    got = k.evoluer(h2, [ask, confirm])
    assert got.effet == "relache" and got.sens == "infirme"
    assert got.confirmations == 0.0 and got.en_attente_accord == (confirm,) and got.a_relire_en_pr == (ask,)


def test_a_lesson_badly_formed_is_refused():
    for bad in (lecon("T1486-H1", "externe", "confirme"), lecon("T1486-H1", "verdict", "efface"),
                lecon("", "verdict", "confirme"), lecon("T1486-P1", "verdict", "propose"),
                lecon("T1486-H1", "verdict", "requalifie", effet="ouvre")):
        with pytest.raises(ValueError):
            k.verifier(bad)


# ── The store: SQLite, empty, appended to, never rewritten ────────────────────────────────────────

def test_the_store_is_empty_0600_in_a_0700_folder_and_lives_where_the_suite_redirects_it(tmp_path):
    store = ev.Evolutions()
    assert store.path == ev.MAGASIN and tmp_path in store.path.parents       # never the real ~/.glorfindel
    assert store.compte() == 0 and store.lire() == ([], [])
    assert stat.S_IMODE(os.stat(store.path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(store.path.parent).st_mode) == 0o700


def test_an_event_appended_reads_back_dated_by_the_host_and_never_names_a_vm(tmp_path):
    from datetime import datetime, timezone
    store = ev.Evolutions(tmp_path / "e" / "k.sqlite")
    one = lecon("T1486-H2", "dossier", "contredit", auteur=catalog.PLATFORM, date="forgée")
    store.ajouter(one, now=datetime(2026, 11, 23, tzinfo=timezone.utc))
    (back,), refus = store.lire()
    assert refus == [] and back.date == "2026-11-23T00:00:00+00:00" and back.hypothese == "T1486-H2"
    with sqlite3.connect(store.path) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(evenements)")]
        assert conn.execute("SELECT poids FROM evenements").fetchone() == (0.5,)
    assert not {"vm", "resource_id", "vm_name"} & set(cols)


def test_an_event_is_never_rewritten_nor_erased(tmp_path):
    store = ev.Evolutions(tmp_path / "k.sqlite")
    store.ajouter(lecon("T1486-H1", "banc", "confirme"))
    with sqlite3.connect(store.path) as conn:
        for sql in ("UPDATE evenements SET verdict = 'contredit'", "DELETE FROM evenements"):
            with pytest.raises(sqlite3.IntegrityError, match="jamais"):
                conn.execute(sql)
    assert store.compte() == 1


def test_a_lesson_badly_formed_is_never_appended(tmp_path):
    store = ev.Evolutions(tmp_path / "k.sqlite")
    with pytest.raises(ValueError):
        store.ajouter(lecon("T1486-H1", "externe", "confirme"))
    assert store.compte() == 0


def test_a_row_that_does_not_read_is_left_out_and_said(tmp_path):
    store = ev.Evolutions(tmp_path / "k.sqlite")
    with sqlite3.connect(store.path) as conn:
        conn.execute("INSERT INTO evenements (hypothese, genre, auteur, verdict, ref, accord, texte, effet, poids, "
                     "date) VALUES ('T1486-H1', 'rumeur', '', 'confirme', 'x', '', '', '', 1.0, 'x')")
    lecons, refus = store.lire()
    assert lecons == [] and len(refus) == 1 and "rumeur" in refus[0]


def test_a_link_in_the_store_s_place_is_refused_never_followed(tmp_path):
    target = tmp_path / "ailleurs.sqlite"
    link = tmp_path / "k.sqlite"
    link.symlink_to(target)
    with pytest.raises(ev.MagasinRefuse):
        ev.Evolutions(link)
    assert not target.exists()
    (tmp_path / "vrai").mkdir()
    (tmp_path / "lien").symlink_to(tmp_path / "vrai", target_is_directory=True)
    with pytest.raises(ev.MagasinRefuse):
        ev.Evolutions(tmp_path / "lien" / "k.sqlite")


def test_a_store_that_is_not_a_database_raises_never_reads_empty(tmp_path):
    path = tmp_path / "k.sqlite"
    path.write_bytes(b"ceci n'est pas une base" * 100)
    with pytest.raises(sqlite3.DatabaseError):
        ev.Evolutions(path)


# ── No reader in production ───────────────────────────────────────────────────────────────────────

_BASE_MODULES = {"glorfindel.enquiry.knowledge", "glorfindel.enquiry.evolutions"}


def _imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:                                   # relative: placed in its package
                pkg = ".".join(path.relative_to(ROOT).with_suffix("").parts[:-node.level])
                mod = f"{pkg}.{mod}" if mod else pkg
            out |= {mod} | {f"{mod}.{a.name}" for a in node.names}
    return out


def test_no_module_of_the_product_imports_the_base():
    """The watch, the graph, `investigate`, the console, the bot: none reads the base yet (ENQ4, ENQ5)."""
    readers = []
    for pkg in ("glorfindel", "eregion_console", "eregion_core"):
        for path in sorted((ROOT / pkg).rglob("*.py")):
            rel = path.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")
            if rel not in _BASE_MODULES and _imports(path) & _BASE_MODULES:
                readers.append(rel)
    assert readers == []


def test_the_graph_and_the_watch_do_not_load_the_base():
    code = ("import sys, glorfindel.agent, glorfindel.watch.loop, glorfindel.enquiry.fixed, glorfindel.cli; "
            f"print(sorted(m for m in {sorted(_BASE_MODULES)!r} if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "[]"
