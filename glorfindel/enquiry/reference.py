"""The enquiry's memory per object (ENQ4, #1085; `docs/design/enquete-raisonnee.md` §5.5): what the last
enquiry on the same VM and the same rule read, the decision it led to, and the human verdict when there
is one. **At the harness only**: the references are recorded (scripts/harness_enquete.py); ENQ5 writes
them in the watch's state, behind its switch. Nothing of the product imports this module.

**A dated fact, never a lesson.** A reference is what the last enquiry read and the verdict it received;
the next enquiry on the object replaces it. It never accumulates and changes no state of the base.
Shown only for its own object (the same VM, case-insensitive like Azure's resource ids, and the same
rule), and only within `AGE_MAX` — 30 days, the age of a proof, the note's proposal: no measure fixes it
yet, the harness's session and ENQ5 will.

**Rule 1: the past never replaces a reading of today** (740659a, §11.4). The loop keeps today's readings
apart (`loop.Enquete.lectures`): a reading of today in `echec` or `en_attente` stays so, the reference
never fills it, never answers a citation, never closes a gap. The block the model reads says a date,
never the VM's present state.

**Rule 2: the asymmetry.** « Different from usual, so dig » applies alone: it tightens (a read more, a
card). « As usual, so benign » (`habitude_recevable`) holds only on a **human verdict** — never on a
decision of the model, nor a cycle without a verdict — and **never on a grave technique**
(`GRAVE_TTPS`): there the guard of §7.3 holds anyway, and a ransomware at the backup's hour looks like
the habit (case 3 of §9.2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from glorfindel.decision_queue import GRAVE_TTPS
from glorfindel.enquiry import catalog

AGE_MAX = timedelta(days=30)          # past it, the reference is no longer shown (§5.5; to measure)
BENIN, MALVEILLANT = "benin", "malveillant"
VERDICTS_HUMAINS = (BENIN, MALVEILLANT)
LIGNES_MAX, VALEUR_MAX = 5, 160       # what a reference keeps of each read: bounded, like the day's

# Why « as usual » is not received — said to the model and in the enquiry's notes.
SANS_REFERENCE = "aucune enquête précédente sur cet objet"
SANS_VERDICT = "aucun verdict humain sur la dernière enquête : une décision n'est jamais un verdict"
PAS_BENIN = "le verdict humain de la dernière enquête n'était pas « bénin »"
TECHNIQUE_GRAVE = "technique grave : « comme d'habitude » n'y vaut jamais « bénin » (§5.5, règle 2)"


@dataclass(frozen=True)
class Trace:
    """One read of the last enquiry: its id, its state, its rows bounded (each value a short text)."""
    id: str
    etat: str
    lignes: tuple[tuple[tuple[str, str], ...], ...] = ()


@dataclass(frozen=True)
class Reference:
    """The last enquiry on an object: its VM (the registry's), its rule, its date, its reads, the decision
    it led to, and the human verdict (`benin`, `malveillant`, or "" — none)."""
    vm: str
    regle: str
    date: datetime
    lectures: tuple[Trace, ...]
    decision: str = ""
    verdict_humain: str = ""

    def __post_init__(self):
        if self.verdict_humain not in VERDICTS_HUMAINS + ("",):
            raise ValueError(f"verdict humain inconnu : {self.verdict_humain!r}")
        if not isinstance(self.date, datetime) or self.date.tzinfo is None:
            raise ValueError("une référence porte sa date, avec son fuseau")
        if any(t.etat not in catalog.ETATS for t in self.lectures):
            raise ValueError("une lecture de la référence a un état hors des sept")


def _court(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:VALEUR_MAX]


def trace(reading: catalog.Reading) -> Trace:
    """What a reference keeps of a reading: its state, at most `LIGNES_MAX` rows, each value bounded."""
    rows = reading.rows[:LIGNES_MAX] if reading.etat == catalog.LIGNES else []
    return Trace(reading.id, reading.etat, tuple(
        tuple((str(k)[:40], _court(v)) for k, v in row.items()) if isinstance(row, dict) else (("valeur", _court(row)),)
        for row in rows))


def depuis(lectures, *, vm: str, regle: str, date: datetime, decision: str = "",
           verdict_humain: str = "") -> Reference:
    """The reference an enquiry leaves on its object (ENQ5 writes it; the harness records it)."""
    return Reference(vm, regle, date, tuple(trace(r) for r in lectures), decision, verdict_humain)


def montrable(ref: Reference | None, *, vm: str, regle: str, now: datetime) -> Reference | None:
    """`ref` if it may be shown to this enquiry: its own object, dated, not in the future, within AGE_MAX."""
    if ref is None or not vm or ref.vm.lower() != str(vm).lower() or ref.regle != regle:
        return None
    if ref.date > now or now - ref.date > AGE_MAX:
        return None
    return ref


def habitude_recevable(ref: Reference | None, technique: str) -> str:
    """"" when « as usual, so benign » may be received from `ref` on `technique` — else why not (rule 2):
    a human verdict « benign » only, and never on a grave technique. The guard of §7.3 never reads it."""
    if technique in GRAVE_TTPS:
        return TECHNIQUE_GRAVE
    if ref is None:
        return SANS_REFERENCE
    if not ref.verdict_humain:
        return SANS_VERDICT
    return "" if ref.verdict_humain == BENIN else PAS_BENIN


def lire_dict(raw: dict) -> Reference:
    """A recorded reference (the harness's cases; ENQ5's store), validated — else ValueError."""
    if not isinstance(raw, dict):
        raise ValueError("une référence est un dictionnaire")
    try:
        date = datetime.fromisoformat(str(raw["date"]).replace("Z", "+00:00"))
        lectures = tuple(Trace(str(t["id"]), str(t["etat"]), tuple(
            tuple((str(k)[:40], _court(v)) for k, v in row.items()) for row in t.get("lignes", ())[:LIGNES_MAX]))
            for t in raw.get("lectures", ()))
        return Reference(str(raw["vm"]), str(raw["regle"]),
                         date if date.tzinfo else date.replace(tzinfo=timezone.utc),
                         lectures, str(raw.get("decision", "")), str(raw.get("verdict_humain", "")))
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"référence illisible ({type(exc).__name__}: {exc})") from None
