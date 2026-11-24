"""The knowledge base of the enquiry (ENQ3, #1077; `docs/design/enquete-raisonnee.md` §2.3, §3): a sheet
(`Fiche`) per technique, its hypotheses, their states and their effect, and the pure rules by which a
lesson changes them. **No reader in production**: neither the watch, nor the graph, nor `investigate`
imports this module (tests/unit/test_enquiry_knowledge.py); the loop of ENQ4 reads it at the harness
first, ENQ5 in production, behind a switch. Nothing the model sees changes here.

**The seed** (§3.2): `glorfindel/enquiry/fiches/<technique>.yaml`, in the image, reviewed in a PR,
validated at loading — an unknown key, a read the catalogue does not know, an unreadable predicate: the
sheet is refused and said (`Base.refusees`), and its rule keeps the base enquiry. It alone carries `sens`,
`effet`, `obligatoires` and the predicates. A seed that cannot be read (its folder absent, no sheet in
it) is an error (`GraineIllisible`), never an empty base.

**The reads a sheet names** come from the catalogue (`catalog.READS`, each parameter declared with its
check), or from the reads it announces (`ANNONCEES`): the dossier's (§4.3) and the new ones (§4.4), which
enter the catalogue one by one, measured, each in its lot (Q8, 23/11). An announced read runs nowhere:
`catalog.ask` does not serve it. Any other id refuses the sheet.

**The lessons** (§3.3, §3.4): each one weighs by its source — the bench 1.0, a human verdict 0.8, the
dossier 0.5 (a fact of the platform or of Glorfindel) or 0.2 (a fact of the guest), the model 0.1 —, the
weight always drawn from its source, never read from where it is stored. The rules:
- **what tightens applies alone**; **what relaxes never applies without a human's accord** — a lesson
  that gives credit to a hypothesis that relaxes, or takes it from one that tightens (`appliquee`);
- **a state changes on the bench or a human verdict only** (`SOURCES_D_ETAT`): `contestee` once their
  contradictions reach 0.8, `mesuree` on a confirmation of the bench, for a hypothesis that tightens; the
  model and the dossier count (the model never: it proposes), and never change a state;
- **a hypothesis proposed is never shown to the model** (`vue_modele`): only to the human;
- **`sens` and `effet` are never learned**: they come from the seed; a lesson that asks to change them is
  kept for a PR (`a_relire_en_pr`), never applied.
The base never lifts a ceiling nor touches a guard (Q5): a `lifted_by` is written in the rule, by a PR.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

import yaml

from glorfindel.decision_queue import GRAVE_TTPS
from glorfindel.enquiry import catalog

GRAINE = Path(__file__).with_name("fiches")

# ── A hypothesis: its sense, its effect, its states (§3.1) ────────────────────────────────────────

CONFIRME, INFIRME, AUCUN = "confirme", "infirme", "aucun"       # sens: it confirms or infirms the attack
RESSERRE, RELACHE = "resserre", "relache"                        # effet: more vigilance, or less contention
SENS = (CONFIRME, INFIRME, AUCUN)
EFFETS = (RESSERRE, RELACHE, AUCUN)
# A `sens: confirme` tightens, a `sens: infirme` relaxes; a check of consistency has neither (§3.1).
EFFET_DU_SENS = MappingProxyType({CONFIRME: RESSERRE, INFIRME: RELACHE, AUCUN: AUCUN})

PROPOSEE, SUPPOSEE, MESUREE, CONTESTEE, RETIREE = "proposee", "supposee", "mesuree", "contestee", "retiree"
ETATS = (PROPOSEE, SUPPOSEE, MESUREE, CONTESTEE, RETIREE)
# What a PR writes in the seed: never `proposee` (not yet reviewed), never `contestee` (a verdict, the bench).
ETATS_DE_LA_GRAINE = (SUPPOSEE, MESUREE, RETIREE)
CACHES_AU_MODELE = (PROPOSEE, RETIREE)

# The sources of a seed's hypothesis: where it was read. The model is not one — its hypothesis is proposed.
GENRES_DE_LA_GRAINE = ("banc", "verdict", "dossier", "regle", "code", "externe")
# `mesuree`: a fact of the bench, or a measure written (a rule's), carries it (§3.1).
GENRES_MESURES = ("banc", "regle")

# The reads a sheet may name before they enter the catalogue (§4.3, §4.4, Q8): where the design describes
# each, and what measures it. None runs; each leaves this list as it enters the catalogue, in its lot.
# T1486's three obligatory reads (perf_minute_series, vault_jobs, vault_activity) entered the catalogue
# with ENQ5a (#1162), at the harness first. An announced read is said « non servie » by the loop
# (`Reading.servie` False) — never « vide », an absence no source vouched for, never `sans_objet`'s « never ».
ANNONCEES: Mapping[str, str] = MappingProxyType({
    "host_disk_metric": "§4.3, F2 : ARM metrics, PT1M ; mesurée par DOS8",
    "platform_reboot": "§4.3, F1c : le journal d'activité ; DH1",
    "guest_context": "§4.3, F1e : Syslog (waagent, apt, cron) ; sans objet au banc ; DH8",
    "ssh_accepted_window": "§4.3, F4a : Syslog, sans filtre d'adresse, 24 h ; DH8",
    "last_restore": "§2.1 : le dernier restore lancé par Glorfindel (glorfindel/jobs.py:74), un JSON sans signature",
    "process_write_io": "§4.4 : process.disk.io, la métrique par processus de l'agent, invité, forgeable ; EH7",
    "file_renames": "§4.4 : auditd par le canal A, ou DeviceFileEvents ; sans objet au banc",
})

_TECHNIQUE = re.compile(r"^T\d{4}(\.\d{3})?$")
_CLES_FICHE = ("technique", "nom", "regles", "grave", "obligatoires", "hypotheses")
_CLES_HYPOTHESE = ("id", "enonce", "sens", "effet", "lectures", "sources", "etat", "limite")
_CLES_PREDICAT = ("confirme", "infirme", "sinon")


class FicheRefusee(ValueError):
    """A sheet that does not pass its validation: refused and said; its rule keeps the base enquiry."""


class GraineIllisible(RuntimeError):
    """The seed cannot be read (its folder absent, unreadable, no sheet in it): an error, never an empty base."""


@dataclass(frozen=True)
class Source:
    genre: str
    ref: str
    date: str = ""


@dataclass(frozen=True)
class Hypothese:
    id: str
    enonce: str
    sens: str
    effet: str
    lectures: tuple[str, ...]
    sources: tuple[Source, ...]
    etat: str
    limite: str
    # What the code computes alone on the rows (ENQ4). A factory: Python 3.11 refuses an unhashable default.
    predicat: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class Fiche:
    technique: str
    nom: str
    regles: tuple[str, ...]
    grave: bool
    obligatoires: tuple[str, ...]
    hypotheses: tuple[Hypothese, ...]


# ── The validation of a sheet ─────────────────────────────────────────────────────────────────────

def _cles(raw, ou: str, requises: Iterable[str], facultatives: Iterable[str] = ()) -> dict:
    """`raw` a mapping with every key required and no key unknown."""
    if not isinstance(raw, dict):
        raise FicheRefusee(f"{ou} : un dictionnaire attendu, pas {type(raw).__name__}")
    requises = tuple(requises)
    if inconnues := sorted(str(k) for k in raw if k not in requises and k not in tuple(facultatives)):
        raise FicheRefusee(f"{ou} : clé inconnue {inconnues}")
    if manquantes := [k for k in requises if k not in raw]:
        raise FicheRefusee(f"{ou} : clé manquante {manquantes}")
    return raw


def _texte(value, ou: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FicheRefusee(f"{ou} : un texte non vide attendu")
    return value


def _parmi(value, permis: Iterable[str], ou: str) -> str:
    if value not in tuple(permis):
        raise FicheRefusee(f"{ou} : {value!r} hors de {list(permis)}")
    return value


def _textes(value, ou: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise FicheRefusee(f"{ou} : une liste non vide attendue")
    items = tuple(_texte(v, f"{ou}[{i}]") for i, v in enumerate(value))
    if len(set(items)) != len(items):
        raise FicheRefusee(f"{ou} : un doublon")
    return items


def _lecture(read_id: str, ou: str) -> str:
    """A read of the catalogue, its parameters each declared with its check — or one it announces."""
    if read_id in catalog.READS:
        if undeclared := [p for p in catalog.READS[read_id].params if p not in catalog.PARAMS]:
            raise FicheRefusee(f"{ou} : {read_id} nomme un paramètre non déclaré {undeclared}")
        return read_id
    if read_id in ANNONCEES:
        return read_id
    raise FicheRefusee(f"{ou} : {read_id!r} n'est ni au catalogue ni annoncée (ANNONCEES)")


def _source(raw, ou: str) -> Source:
    raw = _cles(raw, ou, ("genre", "ref"), ("date",))
    when = raw.get("date", "")
    if "date" in raw:
        try:
            date.fromisoformat(_texte(when, f"{ou}.date"))
        except ValueError:
            raise FicheRefusee(f"{ou}.date : {when!r} n'est pas une date AAAA-MM-JJ") from None
    return Source(_parmi(raw["genre"], GENRES_DE_LA_GRAINE, f"{ou}.genre"), _texte(raw["ref"], f"{ou}.ref"), when)


def _predicat(raw, ou: str) -> Mapping[str, str]:
    raw = _cles(raw, ou, (), _CLES_PREDICAT)
    if not ({CONFIRME, INFIRME} & set(raw)):
        raise FicheRefusee(f"{ou} : un prédicat dit ce qui confirme ou ce qui infirme")
    return MappingProxyType({k: _texte(v, f"{ou}.{k}") for k, v in raw.items()})


def _hypothese(raw, technique: str, ou: str) -> Hypothese:
    raw = _cles(raw, ou, _CLES_HYPOTHESE, ("predicat",))
    hid = _texte(raw["id"], f"{ou}.id")
    if not re.fullmatch(rf"{re.escape(technique)}-H\d+", hid):
        raise FicheRefusee(f"{ou}.id : {hid!r} n'est pas {technique}-H<n>")
    ou = f"{ou} ({hid})"
    sens = _parmi(raw["sens"], SENS, f"{ou}.sens")
    effet = _parmi(raw["effet"], EFFETS, f"{ou}.effet")
    if effet != EFFET_DU_SENS[sens]:
        raise FicheRefusee(f"{ou} : sens {sens} et effet {effet} (un sens {sens} a l'effet {EFFET_DU_SENS[sens]})")
    lectures = tuple(_lecture(r, f"{ou}.lectures") for r in _textes(raw["lectures"], f"{ou}.lectures"))
    if not isinstance(raw["sources"], list) or not raw["sources"]:
        raise FicheRefusee(f"{ou}.sources : une liste non vide attendue")
    sources = tuple(_source(s, f"{ou}.sources[{i}]") for i, s in enumerate(raw["sources"]))
    etat = _parmi(raw["etat"], ETATS_DE_LA_GRAINE, f"{ou}.etat")
    if etat == MESUREE and not any(s.genre in GENRES_MESURES for s in sources):
        raise FicheRefusee(f"{ou} : mesurée sans une source du banc ni d'une règle")
    predicat = _predicat(raw["predicat"], f"{ou}.predicat") if "predicat" in raw else MappingProxyType({})
    return Hypothese(hid, _texte(raw["enonce"], f"{ou}.enonce"), sens, effet, lectures, sources, etat,
                     _texte(raw["limite"], f"{ou}.limite"), predicat)


def valider(data, ou: str = "fiche") -> Fiche:
    """The sheet `data` (a seed's YAML, read), validated whole — else `FicheRefusee`, which says why."""
    data = _cles(data, ou, _CLES_FICHE)
    technique = _texte(data["technique"], f"{ou}.technique")
    if not _TECHNIQUE.match(technique):
        raise FicheRefusee(f"{ou}.technique : {technique!r} n'est pas un identifiant ATT&CK")
    if not isinstance(data["grave"], bool) or data["grave"] != (technique in GRAVE_TTPS):
        raise FicheRefusee(f"{ou}.grave : {data['grave']!r}, quand GRAVE_TTPS (decision_queue.py) dit "
                           f"{technique in GRAVE_TTPS}")
    if not isinstance(data["hypotheses"], list) or not data["hypotheses"]:
        raise FicheRefusee(f"{ou}.hypotheses : une liste non vide attendue")
    hypotheses = tuple(_hypothese(h, technique, f"{ou}.hypotheses[{i}]") for i, h in enumerate(data["hypotheses"]))
    if len({h.id for h in hypotheses}) != len(hypotheses):
        raise FicheRefusee(f"{ou}.hypotheses : un identifiant en double")
    obligatoires = () if data["obligatoires"] == [] else tuple(
        _lecture(r, f"{ou}.obligatoires") for r in _textes(data["obligatoires"], f"{ou}.obligatoires"))
    if orphelines := [r for r in obligatoires if not any(r in h.lectures for h in hypotheses)]:
        raise FicheRefusee(f"{ou}.obligatoires : {orphelines} ne sert à aucune hypothèse")
    return Fiche(technique, _texte(data["nom"], f"{ou}.nom"), _textes(data["regles"], f"{ou}.regles"),
                 data["grave"], obligatoires, hypotheses)


# ── Reading the seed ──────────────────────────────────────────────────────────────────────────────

class _SansDoublon(yaml.SafeLoader):
    """A key given twice is refused: the last one would win in silence, the reviewed line lost."""


def _mapping(loader, node, deep=False):
    keys = [loader.construct_object(k, deep=deep) for k, _ in node.value]
    if dup := sorted({str(k) for k in keys if keys.count(k) > 1}):
        raise FicheRefusee(f"clé en double {dup} (ligne {node.start_mark.line + 1})")
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_SansDoublon.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def lire_fiche(path: Path) -> Fiche:
    """The sheet of `path`, its name its technique's — else `FicheRefusee`."""
    path = Path(path)
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_SansDoublon)   # a SafeLoader
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise FicheRefusee(f"{path.name} : illisible ({exc})") from None
    except FicheRefusee as exc:
        raise FicheRefusee(f"{path.name} : {exc}") from None
    fiche = valider(data, path.name)
    if path.stem != fiche.technique:
        raise FicheRefusee(f"{path.name} : la fiche de {fiche.technique} porte le nom de sa technique")
    return fiche


@dataclass(frozen=True)
class Base:
    """The sheets read, by technique, and those refused (file → why), said."""
    fiches: Mapping[str, Fiche]
    refusees: Mapping[str, str]

    def pour(self, regle: str, technique: str = "") -> Fiche | None:
        """The sheet of `regle` (a client's rule of a shipped rule's name inherits it), else of its
        `technique`; None: the rule keeps the base enquiry (§3.1)."""
        for fiche in self.fiches.values():
            if regle in fiche.regles:
                return fiche
        return self.fiches.get(technique)


def charger(dossier: Path | None = None) -> Base:
    """The base of the seed in `dossier` (`GRAINE`). Unreadable, or without a sheet: `GraineIllisible`."""
    dossier = Path(dossier) if dossier is not None else GRAINE
    try:
        chemins = sorted(p for p in dossier.iterdir() if p.suffix == ".yaml")
    except OSError as exc:
        raise GraineIllisible(f"{dossier} : la graine est illisible ({exc})") from exc
    if not chemins:
        raise GraineIllisible(f"{dossier} : aucune fiche — une graine vide n'est jamais une base vide")
    fiches, refusees, regles = {}, {}, {}
    for path in chemins:
        try:
            fiche = lire_fiche(path)
        except FicheRefusee as exc:
            refusees[path.name] = str(exc)
            continue
        if doubles := [r for r in fiche.regles if r in regles]:
            refusees[path.name] = f"{doubles} déjà enquêtée par {[regles[r] for r in doubles]}"
            continue
        fiches[fiche.technique] = fiche
        regles.update({r: path.name for r in fiche.regles})
    return Base(MappingProxyType(fiches), MappingProxyType(refusees))


# ── The lessons: their weights, their rules (§3.3, §3.4) ──────────────────────────────────────────

BANC, VERDICT, DOSSIER, MODELE = "banc", "verdict", "dossier", "modele"
GENRES = (BANC, VERDICT, DOSSIER, MODELE)
GLORFINDEL = "glorfindel"                     # a fact Glorfindel writes (a job it launched), not the guest
POIDS = MappingProxyType({BANC: 1.0, VERDICT: 0.8, MODELE: 0.1})
POIDS_DOSSIER_PLATEFORME, POIDS_DOSSIER_INVITE = 0.5, 0.2
# Only the bench and a human verdict change a state (§3.3's table); the dossier and the model never.
SOURCES_D_ETAT = frozenset({BANC, VERDICT})
SEUIL_CONTESTE = 0.8                          # contested once their contradictions reach it (EH14 sets it)

CONTREDIT, PROPOSE, REQUALIFIE = "contredit", "propose", "requalifie"
VERDICTS = (CONFIRME, CONTREDIT, PROPOSE, REQUALIFIE)


@dataclass(frozen=True)
class Lecon:
    """One event of the evolutions (§3.2): the hypothesis, its source, its verdict. Never a VM (Q9): what
    misled on one VM reaches the model by the enquiry's memory of that object, not by the base.

    `confirme`/`contredit` a hypothesis; `propose` a new one (`hypothese` its id, `texte` its statement);
    `requalifie` asks its `effet` changed — kept for a PR, never applied. `accord`: the human approval (a
    card, a PR) without which a lesson that relaxes never applies."""
    hypothese: str
    genre: str
    verdict: str
    ref: str
    date: str = ""
    auteur: str = ""          # for the dossier: the author of the fact (catalog.PLATFORM, GLORFINDEL, the guest)
    accord: str = ""
    texte: str = ""
    effet: str = ""


def poids(genre: str, auteur: str = "") -> float:
    """A source's weight (§3.3): the bench 1.0, a verdict 0.8, the dossier 0.5 for a fact of the platform
    or of Glorfindel and 0.2 for any other (the guest's, or an author unknown), the model 0.1."""
    if genre == DOSSIER:
        return POIDS_DOSSIER_PLATEFORME if auteur in (catalog.PLATFORM, GLORFINDEL) else POIDS_DOSSIER_INVITE
    if genre not in POIDS:
        raise ValueError(f"genre de source inconnu : {genre!r}")
    return POIDS[genre]


def verifier(lecon: Lecon) -> Lecon:
    """`lecon` well formed — else ValueError (a row of the store that does not read)."""
    if lecon.genre not in GENRES or lecon.verdict not in VERDICTS:
        raise ValueError(f"genre {lecon.genre!r} ou verdict {lecon.verdict!r} inconnu")
    if not (isinstance(lecon.hypothese, str) and lecon.hypothese and isinstance(lecon.ref, str) and lecon.ref):
        raise ValueError("une leçon nomme son hypothèse et sa référence")
    if lecon.verdict == PROPOSE and not lecon.texte:
        raise ValueError("une hypothèse proposée a son énoncé")
    if lecon.verdict == REQUALIFIE and lecon.effet not in EFFETS:
        raise ValueError(f"effet demandé inconnu : {lecon.effet!r}")
    return lecon


def direction(lecon: Lecon, effet: str) -> str:
    """Whether `lecon` tightens or relaxes, on a hypothesis of `effet`: credit given to what relaxes, or
    taken from what tightens, relaxes; the reverse tightens; a check of consistency does neither."""
    if lecon.verdict not in (CONFIRME, CONTREDIT) or effet == AUCUN:
        return AUCUN
    return RESSERRE if (effet == RESSERRE) == (lecon.verdict == CONFIRME) else RELACHE


def appliquee(lecon: Lecon, effet: str) -> bool:
    """What tightens applies alone; what relaxes, only with a human's accord (§3.4)."""
    if direction(lecon, effet) == RELACHE:
        return bool(lecon.accord)
    return lecon.verdict in (CONFIRME, CONTREDIT)


@dataclass(frozen=True)
class Evolution:
    """A hypothesis as the base holds it: the seed's `sens` and `effet`, its state, its weighted counts,
    and what waits for a human (a lesson that relaxes, without accord) or for a PR (`effet` asked)."""
    id: str
    enonce: str
    sens: str
    effet: str
    etat: str
    confirmations: float = 0.0
    contradictions: float = 0.0
    en_attente_accord: tuple[Lecon, ...] = ()
    a_relire_en_pr: tuple[Lecon, ...] = ()


def _somme(lecons: Iterable[Lecon]) -> float:
    return round(math.fsum(poids(le.genre, le.auteur) for le in lecons), 6)


def evoluer(hyp: Hypothese, lecons: Iterable[Lecon]) -> Evolution:
    """`hyp` once its lessons are applied by the rules of §3.3 and §3.4."""
    mine = [le for le in lecons if le.hypothese == hyp.id]
    effet = hyp.effet                                        # the seed's alone: never learned (§3.3, rule 3)
    faites = [le for le in mine if appliquee(le, effet)]
    comptees = [le for le in faites if le.genre != MODELE]  # the model proposes, never counts
    fortes = [le for le in faites if le.genre in SOURCES_D_ETAT]
    etat = hyp.etat
    if etat != RETIREE and _somme(le for le in fortes if le.verdict == CONTREDIT) >= SEUIL_CONTESTE:
        etat = CONTESTEE
    elif etat == SUPPOSEE and effet == RESSERRE and any(le.genre == BANC and le.verdict == CONFIRME for le in fortes):
        etat = MESUREE
    return Evolution(
        hyp.id, hyp.enonce, hyp.sens, effet, etat,
        confirmations=_somme(le for le in comptees if le.verdict == CONFIRME),
        contradictions=_somme(le for le in comptees if le.verdict == CONTREDIT),
        en_attente_accord=tuple(le for le in mine if direction(le, effet) == RELACHE and not le.accord),
        a_relire_en_pr=tuple(le for le in mine if le.verdict == REQUALIFIE))


def evolutions(fiche: Fiche, lecons: Iterable[Lecon]) -> list[Evolution]:
    """Every hypothesis of `fiche` evolved, then those proposed for its technique (`proposee`, with no
    `sens` nor `effet`: only a PR gives them) — what the human sees."""
    lecons = list(lecons)
    vues = [evoluer(h, lecons) for h in fiche.hypotheses]
    connues = {h.id for h in fiche.hypotheses}
    for le in lecons:
        if (le.verdict == PROPOSE and le.hypothese.startswith(f"{fiche.technique}-")
                and le.hypothese not in connues):
            connues.add(le.hypothese)
            vues.append(Evolution(le.hypothese, le.texte, AUCUN, AUCUN, PROPOSEE))
    return vues


@dataclass(frozen=True)
class VueModele:
    """What the model may read of a hypothesis — built field by field, so that a field added to
    `Evolution` later never reaches the model by default. Never a lesson: neither those that wait for a
    human's accord (a lesson of the model's own, its free text among them), nor those that wait for a PR."""
    id: str
    enonce: str
    sens: str
    effet: str
    etat: str
    confirmations: float
    contradictions: float


def _au_modele(v: Evolution) -> VueModele:
    return VueModele(v.id, v.enonce, v.sens, v.effet, v.etat, v.confirmations, v.contradictions)


def vue_modele(fiche: Fiche, lecons: Iterable[Lecon]) -> list[VueModele]:
    """What the model may be shown of `fiche` (ENQ4 at the harness, ENQ5 behind its switch): never a
    hypothesis proposed — it would learn itself (§3.3, rule 1) — nor one withdrawn, and of the others
    never a lesson that waits (§3.4): only the seed's statement, sense and effect, the state, the counts."""
    vues = [v for v in evolutions(fiche, lecons) if v.etat not in CACHES_AU_MODELE]
    return [_au_modele(v) for v in vues]
