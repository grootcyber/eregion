"""The loop of the enquiry (ENQ4, #1085; `docs/design/enquete-raisonnee.md` §5, §6.3): the model chooses
its reads in the closed catalogue, `lire(id)`, then ends with `conclure()`. **At the harness only**
(scripts/harness_enquete.py, `make llm-compare … ENQUETE=1`): neither the graph, nor the watch, nor
`investigate`, nor the CLI imports this module (tests/unit/test_enquiry_loop.py). ENQ5 brings it to
production behind a switch, after the end-to-end run.

**A plain Python loop, not a LangGraph subgraph** (Jonathan, 23/11, question C of the tenth review): the
graph does not change; a subgraph is discussed again after the harness's session, on its measure.

What the code holds, never the model:
- **the budget N** (4 reads the model chooses; `Budget.n`): every `lire` counts — an id outside the
  list, a read already done; past N, a read is `non_permise`, never run. The last turn offers
  `conclure` alone; without it the enquiry ends at the budget;
- **the delay T** (30 s for the whole enquiry, the model's turns included; `Budget.t`): a real delay,
  on a monotonic clock — each read and each turn of the model is waited for at most what is left of
  T. A read the code launched and T cut is `echec`; a read the model asks once T is spent is
  `non_permise`. What T counts (the reads alone, or the whole) and its value are the harness's
  session's to settle (Q2, EH2): the reference run of 23/11 gave 4.8 s a call (median), 8.9 s (p95) —
  four turns pass 30 s at p95;
- **the obligatory reads** of the sheet, run by the code in parallel before the model's first turn,
  outside N (§5.2): no line removes them. An obligatory read not served yet (announced, §4.3, §4.4)
  carries the marker `Reading.servie` False (ENQ5a), said « non servie » — never `vide`, never
  `non_permise` (the code asked it), never confused with a `sans_objet` (« never » there, « not yet »
  here). **Without a sheet, the base enquiry** runs the same way: ENQ2's routing on the line's columns
  (`fixed.selection`). Only these reads, asked by the code itself, make gaps (`Enquete.trous`, G2):
  failed or refused, and — ENQ5a, §7.2 — an obligatory read still `en_attente`;
- **the reads permitted**: the sheet's reads the catalogue serves under this system and whose
  parameters the code can fill (without a sheet, every read of the catalogue that reads under this
  system). An id outside the catalogue or outside that list is `non_permise`; an announced read asked
  is `non_permise`, « non servie »; a read of the sheet without object under this system is
  `sans_objet`; a read whose value the line does not give is `refusee`, noted — none of them is ever
  run nor `vide`, and a read the model asked is never a gap, whatever its state (§5.1, §7.2);
- **the VM** is the registry's (`vm`), **the vault** the configuration's (`coffre`, ENQ5a), each value
  of the line checked by its parameter's check (`catalog.PARAMS`): the model gives an id, never a VM, a
  value, a window nor a query. **The window** is anchored on the signal's hour by the reader
  (`glorfindel/enquiry/lecteur.py`), never by the model;
- **the system** comes from the caller (the harness's case, the capture's VM model; ENQ5b: the registry,
  filled from the VM's model): unknown, a read that depends on it is never run and says `sans_objet`
  (`catalog.UNKNOWN_SYSTEM`) — never `vide`. T1486's three obligatory reads depend on no system;
- **the citations** (§6.3): a hypothesis of the sheet, each proof a read of that hypothesis done today,
  in a state that carries a verdict (`lignes`, a line actually shown; `vide`, the absence); one proof
  that does not hold makes the hypothesis `inconnu`; where the hypothesis has a predicate the code
  computes the verdict, and it wins (`glorfindel/enquiry/predicats.py`: T1486-H1 and H2, ENQ5a — every
  enquiry computes them, cited or not, `Enquete.verdicts_code`). What the model adds to its conclusion
  is ignored, and noted;
- **what `decide` reads of it** (`Enquete.contexte`): only the reads the code actually ran — never a
  read not served, which today's message would say « aucun résultat »;
- **the memory per object** (`reference.py`, §5.5): shown after today's reads, never in their place;
  « as usual » received only on a human verdict « benign », never on a grave technique.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping

from glorfindel import kql
from glorfindel.enquiry import catalog, fixed, knowledge, message, predicats
from glorfindel.enquiry import reference as ref_

N_DEFAUT, T_DEFAUT = 4, 30.0          # Q2 (23/11): 4 reads chosen, 30 s — recalibrated on the measure
CONCLUE, BUDGET, DELAI, ERREUR = "conclue", "budget", "delai", "erreur_modele"
INCONNU = "inconnu"

NON_SERVIE = "annoncée, pas encore au catalogue (Q8 : mesurée au banc d'abord)"
HORS_LISTE = "hors de la liste permise (la fiche et le système)"
AU_DELA_N = "au-delà du budget N"
AU_DELA_T = "au-delà du délai T"
COUPEE = "coupée par le délai T"
NON_ATTRIBUEE = "détection non attribuée : aucune VM du registre à interroger"
NON_REMPLIE = "le code ne peut pas en remplir les paramètres : "
SANS_COFFRE = "aucun coffre connu (action_backends, GLORFINDEL_BACKUP_VAULT)"

# The predicates the code computes (§6.3, step 3), by hypothesis (ENQ5a: T1486-H1 and H2, on the reads
# that entered the catalogue). A hypothesis with a predicate and no code says `inconnu`, whatever the
# model says. A read that enters the catalogue brings its hypothesis's predicate with it
# (tests/unit/test_enquiry_loop.py fails otherwise).
PREDICATS: Mapping[str, Callable] = predicats.PREDICATS


@dataclass(frozen=True)
class Budget:
    n: int = N_DEFAUT
    t: float = T_DEFAUT


@dataclass(frozen=True)
class Preuve:
    """A proof that passed: the read, the line's number (0: the absence of a `vide` read), the row read."""
    lecture: str
    ligne: int
    texte: str


@dataclass(frozen=True)
class Verifiee:
    """A hypothesis cited, once the code has checked it (§6.3)."""
    id: str
    verdict: str
    verdict_modele: str
    par: str                                  # "code" (its predicate), "modele", or "" (discarded)
    preuves: tuple[Preuve, ...] = ()
    ecartees: tuple[str, ...] = ()
    desaccord: bool = False


@dataclass
class Enquete:
    """One enquiry: today's readings (the obligatory first), each ask of the model and what it got, the
    hypotheses checked, « as usual » received or not, why it ended, its turns and its duration."""
    lectures: dict = field(default_factory=dict)
    obligatoires: tuple = ()
    demandes: list = field(default_factory=list)
    hypotheses: list = field(default_factory=list)
    habitude: bool = False
    habitude_ecartee: str = ""
    resume: str = ""
    fin: str = ""
    tours: int = 0
    choisies: int = 0
    duree_s: float = 0.0
    notes: list = field(default_factory=list)
    reference: ref_.Reference | None = None
    d_office: set = field(default_factory=set)        # the reads the code itself asked (§5.2, §7.2)
    lancees: set = field(default_factory=set)         # the reads actually handed to the reader
    verdicts_code: dict = field(default_factory=dict)  # ENQ5a: each coded predicate's verdict, cited or not

    @property
    def trous(self) -> list[str]:
        """The gaps (G2): a read the code asked itself — an obligatory one, or the base enquiry without a
        sheet — that failed or was refused; and an obligatory read still `en_attente` (ENQ5a, §7.2: nothing
        is said yet, and its absence would push toward the action). Never a read the model asked: a line
        that makes it ask a read that fails, or one the code cannot fill, never holds the contention
        (§5.1, §7.2); never a `non_permise` nor a `sans_objet`, nor an obligatory read not served."""
        return self._echecs() + [r.id for r in self.lectures.values()
                                 if r.etat == catalog.EN_ATTENTE and r.id in self.obligatoires]

    def _echecs(self) -> list[str]:
        return [r.id for r in self.lectures.values() if r.gap and r.id in self.d_office]

    @property
    def contexte(self) -> dict[str, list]:
        """What today's `decide` reads of it (`investigative_context`): the reads the code actually ran,
        each one's rows, else []. Never a read not served (announced, without object, refused, not
        permitted): today's message would say « aucun résultat » for a read that never ran. Never a read
        the model asked that failed or that T cut either: not a gap (it came from the model), it would
        reach `decide` as an absence nobody vouched for (« no reboot ») and nothing would hold the
        action (G2). A read the code asked itself that failed stays — and stays a gap."""
        return {r.id: r.seen for r in self.lectures.values()
                if r.id in catalog.READS and r.id in self.lancees and not (r.gap and r.id not in self.d_office)}


def valeurs(read: catalog.Read, vm: str, detection: dict, coffre: str = "") -> dict | str:
    """The values the code fills for `read` — the registry's VM, the detected line's address, the vault
    the configuration names (ENQ5a) — each checked by its parameter's check (`catalog.PARAMS`); else why
    it cannot be run. Never a value of the model's."""
    brut = {"vm": vm, "ip": detection.get("SourceIP", "") if isinstance(detection, dict) else "",
            "vault": coffre}
    if not vm and "vm" in read.params:
        return NON_ATTRIBUEE
    if not coffre and "vault" in read.params:
        return SANS_COFFRE
    try:
        return {p: catalog.PARAMS[p].check(brut[p]) for p in read.params}
    except kql.UnsafeValue as exc:
        return f"une valeur refusée (kql) : {exc}"


def permises(fiche: knowledge.Fiche | None, systeme: str, *, detection: dict | None = None,
             vm: str | None = None, coffre: str = "") -> tuple[list[str], dict[str, catalog.Reading]]:
    """The reads the model may ask, and those it may not, each as the reading a request for it gets (said,
    never run): without object under this system (`sans_objet`), its parameters not filled (`refusee`,
    with the detection and the VM), or not served yet (`non_permise`, `servie` False: announced)."""
    noms = list(dict.fromkeys(r for h in fiche.hypotheses for r in h.lectures)) if fiche else list(catalog.READS)
    servies, non_servies = [], {}
    for rid in noms:
        if rid in catalog.READS:
            read = catalog.READS[rid]
            why = catalog.says(read, systeme)
            vals = valeurs(read, vm or "", detection or {}, coffre) if detection is not None else {}
            if why:
                non_servies[rid] = _non_lue(rid, catalog.SANS_OBJET, why)
            elif isinstance(vals, str):
                non_servies[rid] = _non_lue(rid, catalog.REFUSEE, f"{NON_REMPLIE}{vals}")
            else:
                servies.append(rid)
        else:
            non_servies[rid] = _non_servie(rid, catalog.NON_PERMISE)
    return servies, non_servies


def _non_lue(read_id: str, etat: str, why: str) -> catalog.Reading:
    """A read the code does not run: its state (`sans_objet`, `non_permise`) and why — never `vide`."""
    return catalog.Reading(str(read_id)[:60], etat, why=why)


def _non_servie(read_id: str, etat: str) -> catalog.Reading:
    """A read not served yet (announced: not in the catalogue, ENQ5a): its marker, never `vide`."""
    return catalog.Reading(str(read_id)[:60], etat, why=f"{NON_SERVIE} — {knowledge.ANNONCEES.get(read_id, '')}",
                           servie=False)


class _Delai:
    """T, a real delay: what is left of it on a monotonic clock, from the enquiry's start."""

    def __init__(self, t: float, horloge: Callable[[], float]):
        self.t, self.horloge = t, horloge
        self.debut = horloge()
        self.fin = self.debut + t

    def restant(self) -> float:
        return self.fin - self.horloge()


class _Boucle:
    def __init__(self, *, detection, vm, regle, technique, systeme, fiche, lecteur, modele, budget,
                 reference, at, maintenant, horloge, coffre=""):
        self.detection = detection if isinstance(detection, dict) else {}
        self.vm, self.regle, self.technique, self.systeme = vm or "", regle, technique, systeme
        self.coffre = coffre or ""
        self.fiche, self.lecteur, self.modele, self.budget = fiche, lecteur, modele, budget
        self.at, self.maintenant = at, maintenant
        self.delai = _Delai(budget.t, horloge)
        self.permises, self.non_servies = permises(fiche, systeme, detection=self.detection, vm=self.vm,
                                                   coffre=self.coffre)
        ref = ref_.montrable(reference, vm=self.vm, regle=regle, now=maintenant())
        self.out = Enquete(reference=ref)
        self.recevable = ref_.habitude_recevable(ref, technique)
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="enquete")

    # ── the reads ─────────────────────────────────────────────────────────────────────────────

    def _lancer(self, reads, vm: str) -> list[catalog.Reading]:
        """Run `reads` in parallel on `vm`, each waited for at most what is left of T."""
        lancees, out = {}, {}
        for read in reads:
            if why := catalog.says(read, self.systeme):
                out[read.id] = _non_lue(read.id, catalog.SANS_OBJET, why)       # never run
            elif isinstance(vals := valeurs(read, vm, self.detection, self.coffre), str):
                out[read.id] = catalog.Reading(read.id, catalog.REFUSEE, why=vals)
            else:
                self.out.lancees.add(read.id)
                lancees[read.id] = (read, self.pool.submit(self.lecteur, read, vals))
        for rid, (read, fut) in lancees.items():
            try:
                rows = fut.result(timeout=max(0.0, self.delai.restant()))
            except FuturesTimeout:
                out[rid] = catalog.Reading(rid, catalog.ECHEC, why=COUPEE)
                continue
            except Exception:
                rows = None                                                      # failed: unknown (G2)
            ingere = rows.ingere if isinstance(rows, catalog.Lu) else None       # how far its source ingested
            rows = rows.rows if isinstance(rows, catalog.Lu) else rows
            out[rid] = catalog.outcome(read, rows if isinstance(rows, list) or rows is None else None,
                                       system=self.systeme, at=self.at, now=self.maintenant(), ingere=ingere)
        return [out[r.id] for r in reads]

    def _garder(self, lu: catalog.Reading) -> None:
        self.out.lectures[lu.id] = lu             # today's reading, whatever the last enquiry read (§5.5, rule 1)

    def obligatoires(self) -> None:
        """What the code reads itself, in parallel, before the model's first turn, outside N (§5.2): the
        sheet's obligatory reads; without a sheet, the base enquiry — ENQ2's routing on the line's
        columns (`fixed.selection`). Their failures, their refusals are gaps (G2); a read not served is
        said, never a gap."""
        obligatoires = self.fiche.obligatoires if self.fiche is not None else ()
        self.out.obligatoires = tuple(obligatoires)
        base = () if self.fiche is not None else tuple(fixed.selection(self.detection))
        d_office = tuple(dict.fromkeys(obligatoires + base))
        self.out.d_office.update(d_office)
        lues = {lu.id: lu for lu in self._lancer([catalog.READS[r] for r in d_office if r in catalog.READS],
                                                 self.vm)}
        for rid in d_office:
            self._garder(lues.get(rid) or _non_servie(rid, catalog.SANS_OBJET))
        self.juger()

    def juger(self) -> None:
        """Each coded predicate of the sheet, on today's readings (§6.3): cited by the model or not."""
        hyps = self.fiche.hypotheses if self.fiche is not None else ()
        self.out.verdicts_code = {h.id: PREDICATS[h.id](self.out.lectures, self.at, self.maintenant())
                                  for h in hyps if h.predicat and h.id in PREDICATS}

    def demander(self, args: dict) -> catalog.Reading:
        """One `lire(id)` of the model: counted, then served or not — never a VM nor a value of its own."""
        read_id = args.get("id")
        self.out.choisies += 1
        if extra := sorted(k for k in args if k not in ("geste", "id")):
            self.out.notes.append(f"le modèle a donné {extra[:5]} avec sa lecture : ignorés")
        if self.out.choisies > self.budget.n:
            return _non_lue(read_id, catalog.NON_PERMISE, AU_DELA_N)
        if self.delai.restant() <= 0:
            return _non_lue(read_id, catalog.NON_PERMISE, AU_DELA_T)
        if isinstance(read_id, str) and read_id in self.out.lectures:
            self.out.notes.append(f"{read_id} déjà faite : son résultat gardé, rien n'est relancé")
            return self.out.lectures[read_id]
        if isinstance(read_id, str) and read_id in self.non_servies:
            lu = self.non_servies[read_id]                       # announced, without object, or not filled
            if lu.etat == catalog.REFUSEE:                       # never run; noted, never a gap (§7.2)
                self.out.notes.append(f"{read_id} demandée, refusée par le code : {lu.why[len(NON_REMPLIE):]}")
            return lu
        asked = catalog.ask(read_id, self.permises)
        if isinstance(asked, catalog.Reading):
            return _non_lue(asked.id, catalog.NON_PERMISE, HORS_LISTE)
        lu = self._lancer([asked], self.vm)[0]      # the registry's VM, never one of the model's (§5.1)
        self._garder(lu)
        return lu

    # ── the turns ─────────────────────────────────────────────────────────────────────────────

    def _tour(self) -> dict | None:
        lire_permis = self.out.choisies < self.budget.n
        demandables = [r for r in self.permises if r not in self.out.lectures]
        texte = message.message(
            detection=self.detection, fiche=self.fiche, permises=demandables, non_servies=self.non_servies,
            faites=self.out.lectures, obligatoires=self.out.d_office,
            reste_n=max(0, self.budget.n - self.out.choisies), reste_t=self.delai.restant(),
            ref=self.out.reference, recevable=self.recevable, verdicts=self.out.verdicts_code)
        outil = message.outil(demandables, lire_permis=lire_permis)
        reste = max(0.0, self.delai.restant())
        fut = self.pool.submit(self.modele, message.ENQUIRY_PROMPT, texte, outil, reste)
        return fut.result(timeout=reste)

    def tours(self) -> dict:
        """The model's turns, within N + 1 (N reads, then `conclure`) and within T. Its conclusion, or {}."""
        while self.out.tours < self.budget.n + 1:
            if self.delai.restant() <= 0:
                self.out.fin = DELAI
                return {}
            try:
                args = self._tour()
            except FuturesTimeout:
                self.out.fin = DELAI
                return {}
            except Exception as exc:
                self.out.fin = ERREUR
                self.out.notes.append(f"le modèle n'a pas répondu ({type(exc).__name__})")
                return {}
            self.out.tours += 1
            args = args if isinstance(args, dict) else {}
            geste = args.get("geste")
            if geste == message.CONCLURE:
                self.out.fin = CONCLUE
                return args
            if geste == message.LIRE:
                lu = self.demander(args)
                self.out.demandes.append((lu.id, lu.etat))
                continue
            self.out.notes.append("un tour sans geste lisible : compté, rien n'est lu")
        self.out.fin = BUDGET
        return {}

    def conclure(self, conclusion: dict) -> None:
        self.out.notes += inattendus(conclusion)
        self.juger()                              # on every read of today, the model's own among them
        self.out.hypotheses = verifier(conclusion.get("hypotheses"), self.fiche, self.out.lectures,
                                       code=self.out.verdicts_code)
        resume = conclusion.get("resume")
        self.out.resume = resume[:message.VALEUR_MAX * 5] if isinstance(resume, str) else ""
        if conclusion.get("comme_d_habitude") is True:
            if self.recevable:
                self.out.habitude_ecartee = self.recevable
                self.out.notes.append(f"« comme d'habitude » écarté : {self.recevable}")
            else:
                self.out.habitude = True


_CLES_CONCLUSION = ("geste", "hypotheses", "comme_d_habitude", "resume")
_CLES_HYPOTHESE = ("id", "verdict", "preuves")
_CLES_PREUVE = ("lecture", "ligne")


def _en_trop(raw, permises) -> list[str]:
    return sorted(str(k)[:40] for k in raw if k not in permises)[:5] if isinstance(raw, dict) else []


def inattendus(conclusion: dict) -> list[str]:
    """What the model added to its conclusion, to a hypothesis or to a proof: ignored, and said — as
    for `lire`."""
    notes = []
    if extra := _en_trop(conclusion, _CLES_CONCLUSION + ("id",)):
        notes.append(f"le modèle a donné {extra} avec sa conclusion : ignorés")
    hyps = conclusion.get("hypotheses")
    for h in hyps if isinstance(hyps, list) else []:
        if extra := _en_trop(h, _CLES_HYPOTHESE):
            notes.append(f"le modèle a donné {extra} avec l'hypothèse {str(h.get('id'))[:60]} : ignorés")
        preuves = h.get("preuves") if isinstance(h, dict) else None
        for p in preuves if isinstance(preuves, list) else []:
            if extra := _en_trop(p, _CLES_PREUVE):
                notes.append(f"le modèle a donné {extra} avec une preuve de {str(h.get('id'))[:60]} : ignorés")
    return notes


def _preuves(raw, lectures: Mapping[str, catalog.Reading], siennes) -> tuple[list[Preuve], list[str]]:
    """The proofs that pass (one of the hypothesis's reads, done today, in a state that carries a verdict,
    a line shown), and why the others do not."""
    ok, ko = [], []
    for p in raw if isinstance(raw, list) else []:
        rid = p.get("lecture") if isinstance(p, dict) else None
        n = p.get("ligne") if isinstance(p, dict) else None
        lu = lectures.get(rid) if isinstance(rid, str) else None
        if isinstance(rid, str) and rid not in siennes:
            ko.append(f"{rid[:60]} : n'est pas une lecture de cette hypothèse")
        elif lu is None:
            ko.append(f"{str(rid)[:60]} : aucune lecture faite aujourd'hui sous cet identifiant")
        elif lu.etat == catalog.LIGNES:
            shown = lu.rows[:message.LIGNES_MONTREES]
            if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(shown):
                ok.append(Preuve(rid, n, message.ligne(shown[n - 1])))
            else:
                ko.append(f"{rid}[{str(n)[:12]}] : aucune ligne lue sous ce numéro")
        elif lu.etat == catalog.VIDE and (n is None or n == 0):
            ok.append(Preuve(rid, 0, "(vide : une absence que la source garantit)"))
        else:
            ko.append(f"{rid} : état {lu.etat}, il ne confirme ni n'infirme rien")
    return ok, ko


def verifier(citees, fiche: knowledge.Fiche | None, lectures: Mapping[str, catalog.Reading], *,
             code: Mapping[str, str] | None = None) -> list[Verifiee]:
    """The hypotheses the model cites, checked by the code (§6.3): in the sheet, each proof a read of
    today that carries a verdict, the code's predicate first. What does not pass is `inconnu` — and one
    proof that does not hold makes the whole hypothesis `inconnu`, whatever its other proofs (a line
    cited that was never read is a fabrication: the verdict it carries is not taken)."""
    hyps = {h.id: h for h in fiche.hypotheses} if fiche is not None else {}
    vues = {v.id for v in knowledge.vue_modele(fiche, ())} if fiche is not None else set()
    out = []
    for c in citees if isinstance(citees, list) else []:
        if not isinstance(c, dict):
            continue
        hid = str(c.get("id", ""))[:60]
        dit = c.get("verdict") if c.get("verdict") in message.VERDICTS else INCONNU
        if hid not in vues:
            out.append(Verifiee(hid, INCONNU, dit, "", ecartees=("hors de la fiche de la technique",)))
            continue
        preuves, ecartees = _preuves(c.get("preuves"), lectures, hyps[hid].lectures)
        verdict, par = (dit, "modele") if preuves and not ecartees else (INCONNU, "modele")
        calcul = PREDICATS.get(hid)
        if hyps[hid].predicat:
            du_code = (code or {}).get(hid, INCONNU) if calcul is not None else INCONNU
            verdict, par = du_code, "code"
            if du_code == INCONNU and calcul is None:
                ecartees.append("son prédicat n'est pas codé : ses lectures ne sont pas servies")
        out.append(Verifiee(hid, verdict, dit, par, tuple(preuves), tuple(ecartees),
                            desaccord=par == "code" and calcul is not None and dit not in (INCONNU, verdict)))
    return out


def enqueter(*, detection: dict, vm: str, regle: str, technique: str, systeme: str,
             fiche: knowledge.Fiche | None, lecteur: Callable, modele: Callable,
             budget: Budget = Budget(), reference: ref_.Reference | None = None,
             at: datetime | None = None, maintenant: Callable[[], datetime] | None = None,
             horloge: Callable[[], float] = time.monotonic, coffre: str = "") -> Enquete:
    """One enquiry on the detection `detection`, on the registry's VM `vm` (its system `systeme`), its
    vault `coffre` the configuration's (ENQ5a; "" when none is known: a read of the vault is refused).

    `lecteur(read, valeurs)` runs one read of the catalogue with the values the code checked: its rows,
    `catalog.Lu` (its rows and how far its source ingested), or None when it failed (the harness's
    recorded or captured reads; `lecteur.Lecteur`, anchored on `at`). `modele(prompt, message, outil,
    timeout)` is one turn of the model: the tool's arguments, or None. Neither is ever called past T."""
    b = _Boucle(detection=detection, vm=vm, regle=regle, technique=technique, systeme=systeme, fiche=fiche,
                lecteur=lecteur, modele=modele, budget=budget, reference=reference, at=at,
                maintenant=maintenant or (lambda: datetime.now(timezone.utc)), horloge=horloge, coffre=coffre)
    try:
        b.obligatoires()
        b.conclure(b.tours())
    finally:
        b.pool.shutdown(wait=False, cancel_futures=True)
        b.out.duree_s = round(horloge() - b.delai.debut, 3)
    return b.out
