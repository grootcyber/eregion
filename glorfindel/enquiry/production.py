"""The enquiry in the watch (ENQ5b, #1284; `docs/design/enquete-raisonnee.md` §5, §9.6): the loop of ENQ4
(`loop.enqueter`) run by `investigate` once the switch says ``loop`` (`interrupteur.py`), on what the watch
knows — never on what the line says of itself.

- **the VM** is the registry's (the signal's resource id; none on a detection attributed to no VM: no read
  that names one runs, each is `refusee`, a gap when the code asked it);
- **its system** is the discovery's (`DiscoveredAsset.os`: `osType` of the VM's OS disk, the platform's
  word, read once per VM — §9.6, « la source proposée »), never `OSType` of `Heartbeat`, which the VM's
  agent writes; unknown, a read that depends on it says `sans_objet`, never `vide`;
- **the vault** is the configuration's (`backup_vault`, ``GLORFINDEL_BACKUP_VAULT``), in the VM's
  subscription; none known, the vault's reads are `refusee`;
- **the sheet** is the seed's (`knowledge.charger`), by the rule, else the technique; a refused sheet
  keeps the base enquiry (ENQ2's routing), and is said;
- **the last enquiry on this object** (the same VM, the same rule) is the watch's memory per object
  (`memoire.py`, §5.5), its human verdict read on its card;
- **the reader** (`lecteur.Lecteur`, `compter`): each KQL query noted on the `LOG_ANALYTICS` budget, never
  refused nor delayed — the detection's path, as `investigate`'s —, each read of the vault taken on the
  `ARM` budget before it runs; refused, `refusee`, a gap when the read is obligatory;
- **the model** is the decision's (`decide`'s, pinned): each turn through `completion_with_tool`, so under
  the breaker in dollars (PRT2), in the decision's context (its share); counted (`Enquete.appels`, the gate's
  `calls_made`). A turn refused by the breaker or the provider's limit stops the enquiry
  (`enquete.refusee`): `decide` then takes the code's path, as for its own call refused.

What it leaves in the state: `enquete` (a dict, `serialiser`: never in the signal — the whole signal is the
model's input), `telemetry_gaps` (`decision.trous`: the code's reads failed, refused or, obligatory, still
waiting — never a read the model asked, never a read not served) and the rows `decide` and the dossier read
(`raw_signal.investigative_context`: `Enquete.contexte`, the reads the code actually ran).
"""
from __future__ import annotations

import contextvars
import json
from datetime import datetime, timezone

from glorfindel.enquiry import catalog, interrupteur, knowledge, loop, message
from glorfindel.enquiry import lecteur as lecteur_
from glorfindel.enquiry import memoire
from glorfindel.enquiry import reference as ref_

LIGNES_GARDEES = message.LIGNES_MONTREES       # the rows of a read the state keeps: what the model was shown
ENQUIRY_MAX_TOKENS = 2048
_BASE: list = []


def _console():
    from glorfindel.terminal import GlorfindelConsole
    return GlorfindelConsole()


def base() -> knowledge.Base:
    """The seed, read once per process; its refused sheets said once."""
    if not _BASE:
        b = knowledge.charger()
        for name, why in b.refusees.items():
            from rich.markup import escape
            _console().print(f"[yellow]enquête : fiche {escape(name)} refusée — {escape(why[:300])} ; sa règle "
                             "garde l'enquête de base[/yellow]")
        _BASE.append(b)
    return _BASE[0]


def systeme_de(resource_id: str) -> str:
    """The VM's system, as the discovery read it in its model (`DiscoveredAsset.os`), or "" (unknown)."""
    from glorfindel import discovery
    low = str(resource_id or "").rstrip("/").lower()
    for asset in discovery.get_registry().all() if low else ():
        if str(asset.resource_id or "").rstrip("/").lower() == low:
            os_ = str(getattr(asset, "os", "") or "").lower()
            return os_ if os_ in catalog.SYSTEMS else ""
    return ""


def coffre_de(resource_id: str) -> str:
    """The vault's resource id the configuration names, in the VM's subscription — "" when none is known
    (the vault's reads refused). Checked by its parameter's check in the loop (`catalog.PARAMS["vault"]`)."""
    from glorfindel.agent import _backup_vault_target
    vault, vault_rg = _backup_vault_target()
    parts = str(resource_id or "").split("/")
    if not vault or len(parts) < 5:
        return ""
    return (f"/subscriptions/{parts[2]}/resourceGroups/{vault_rg or parts[4]}"
            f"/providers/Microsoft.RecoveryServices/vaults/{vault}")


def _kql(workspace_id: str):
    def run(query: str, timespan):
        from glorfindel.detectors import detector_for
        return detector_for("azure_monitor", workspace_id=workspace_id).run_query(query, timespan=timespan)
    return run


class Appels:
    """The model's turns of one enquiry: each counted before it is asked (a call that fails stays counted),
    and the refusal of the breaker or of the provider's limit, kept."""

    def __init__(self):
        self.n, self.refusee = 0, ""


def tour_du_modele(model: str, appels: Appels):
    """One turn of the enquiry against the decision's model, in the decision's context (PRT2: its share of
    the budget): the tool's arguments, or None. Refused by the breaker, it raises — the loop stops."""
    import litellm
    import os
    from eregion_core import llm_call
    from glorfindel import model_budget
    from glorfindel.cycle_line import DECISION_TEMPERATURE
    contexte = contextvars.copy_context()
    extra = {"base_url": os.environ["GLORFINDEL_LLM_BASE_URL"]} if os.environ.get("GLORFINDEL_LLM_BASE_URL") else {}

    def appel(prompt: str, texte: str, outil: dict, timeout: float):
        appels.n += 1
        try:
            resp = llm_call.completion_with_tool(
                litellm, outil["function"]["name"], temperature=DECISION_TEMPERATURE, model=model,
                max_tokens=ENQUIRY_MAX_TOKENS, timeout=max(1.0, timeout), num_retries=0,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": texte}],
                tools=[outil], **extra)
        except Exception as exc:
            if model_budget.refused(exc):
                appels.refusee = str(exc).splitlines()[0][:300] if str(exc) else type(exc).__name__
            raise
        try:
            calls = getattr(resp.choices[0].message, "tool_calls", None) or []
            args = calls[0].function.arguments if calls else None
            return args if isinstance(args, dict) or args is None else json.loads(args)
        except Exception:
            return None

    return lambda *a: contexte.copy().run(appel, *a)


def serialiser(e: loop.Enquete, *, regle: str, technique: str, systeme: str, fiche, appels: Appels) -> dict:
    """What the state keeps of an enquiry: JSON, bounded — each read with its state, whether it is served,
    who asked it, its author and its rows (at most what the model was shown, each value bounded)."""
    lectures = []
    for lu in e.lectures.values():
        read = catalog.READS.get(lu.id)
        lectures.append({
            "id": lu.id, "etat": lu.etat, "servie": bool(lu.servie), "why": str(lu.why)[:300],
            "d_office": lu.id in e.d_office, "obligatoire": lu.id in e.obligatoires,
            "auteur": read.author if read else "", "n": len(lu.rows) if lu.etat == catalog.LIGNES else 0,
            "lignes": [json.loads(message.ligne(r)) for r in lu.rows[:LIGNES_GARDEES]] if lu.etat == catalog.LIGNES else [],
            "ingere": lu.ingere})
    faites = {x["id"] for x in lectures}
    for rid, etat in e.demandes:                 # what the model asked and the code did not run: said, never a gap
        if rid not in faites and etat in catalog.ETATS:
            faites.add(rid)
            lectures.append({"id": str(rid)[:60], "etat": etat, "servie": rid not in knowledge.ANNONCEES, "d_office": False,
                             "obligatoire": False, "auteur": "", "n": 0, "lignes": [], "ingere": "",
                             "why": "demandée par le modèle, non lancée par le code"})
    ref = e.reference
    return {
        "regle": regle, "technique": technique, "systeme": systeme, "fiche": fiche.technique if fiche else "",
        "fin": e.fin, "tours": e.tours, "choisies": e.choisies, "duree_s": e.duree_s, "appels": appels.n,
        "refusee": appels.refusee, "lectures": lectures, "demandes": [list(x) for x in e.demandes],
        "verdicts_code": dict(e.verdicts_code),
        "hypotheses_enquete": [{"id": h.id, "verdict": h.verdict, "modele": h.verdict_modele, "par": h.par,
                                "desaccord": h.desaccord} for h in e.hypotheses],
        "habitude": e.habitude, "habitude_ecartee": e.habitude_ecartee, "notes": [str(x)[:200] for x in e.notes[:20]],
        "reference": ({"date": ref.date.isoformat(), "decision": ref.decision, "verdict_humain": ref.verdict_humain,
                       "lectures": [{"id": t.id, "etat": t.etat, "lignes": [dict(row) for row in t.lignes]}
                                    for t in ref.lectures]}
                      if ref is not None else None),
        "habitude_recevable": ref_.habitude_recevable(ref, technique) if ref is not None else "",
    }


def lectures_de(enquete: dict) -> dict[str, catalog.Reading]:
    """The readings of a serialized enquiry, as the loop's: what `decide`'s message and checks read."""
    out = {}
    for x in enquete.get("lectures") or []:
        if isinstance(x, dict) and x.get("etat") in catalog.ETATS:
            out[str(x["id"])] = catalog.Reading(str(x["id"]), x["etat"], rows=list(x.get("lignes") or []),
                                                why=str(x.get("why") or ""), servie=bool(x.get("servie", True)),
                                                ingere=str(x.get("ingere") or ""))
    return out


def enqueter(state: dict, workspace_id: str, *, model: str, connector=None, lecteur=None, modele=None,
             base_=None, systeme: str | None = None, coffre: str | None = None, maintenant=None,
             horloge=None) -> dict:
    """The watch's enquiry on this cycle's detection: the state, with its `enquete`, its gaps and the rows
    the code read. The readers, the model, the base, the system and the vault are the watch's unless given
    (the tests: no call to Azure nor to a model)."""
    from glorfindel.enquiry import decision
    signal = state["signal"]
    raw = signal.get("raw_signal") or {}
    row = raw.get("detected_data") or raw.get("first_result_row") or {}
    rid = str(signal.get("resource_id") or "")
    ctx = signal.get("context") or {}
    unattributed = ctx.get("attribution") == "unattributed"
    regle, technique = str(ctx.get("rule_name") or ""), str(signal.get("ttp") or "")
    vm = "" if unattributed else rid
    now = maintenant or (lambda: datetime.now(timezone.utc))
    at = catalog.signal_at(signal)
    fiche = (base_ or base()).pour(regle, technique)
    systeme = systeme_de(rid) if systeme is None else systeme
    coffre = coffre_de(rid) if coffre is None else coffre
    appels = Appels()
    e = loop.enqueter(
        detection=row if isinstance(row, dict) else {}, vm=vm, regle=regle, technique=technique,
        systeme=systeme, fiche=fiche, coffre=coffre, at=at, maintenant=now,
        lecteur=lecteur or lecteur_.Lecteur(at or now(), kql=_kql(workspace_id), arm=connector, now=now,
                                            compter=True),
        modele=modele or tour_du_modele(model, appels),
        budget=loop.Budget(n=interrupteur.n(), t=interrupteur.t()),
        reference=memoire.lire(vm, regle, now=now()) if vm and regle else None,
        **({"horloge": horloge} if horloge is not None else {}))
    if modele is not None and hasattr(modele, "appels"):
        appels.n, appels.refusee = modele.appels, getattr(modele, "refusee", "")
    enquete = serialiser(e, regle=regle, technique=technique, systeme=systeme, fiche=fiche, appels=appels)
    gaps = decision.trous(enquete)
    _dire(enquete, gaps, rid)
    contexte = e.contexte
    out = {**state, "telemetry_gaps": gaps, "enquete": enquete}
    if contexte:
        out["signal"] = {**signal, "raw_signal": {**raw, "investigative_context": contexte}}
    return out


def _dire(enquete: dict, gaps: list[str], rid: str) -> None:
    """The watch's console line of an enquiry: its reads, how it ended, its gaps — each value escaped."""
    from rich.markup import escape
    vm = rid.rstrip("/").split("/")[-1] or "?"
    lus = ", ".join(f"{x['id']} {x['etat']}" for x in enquete["lectures"]) or "aucune"
    line = (f"  [dim]investigate (boucle) : {escape(vm)} — {escape(lus)} ; fin {escape(enquete['fin'] or '?')}, "
            f"{enquete['tours']} tour(s), {enquete['duree_s']:g} s[/dim]")
    if gaps:
        line += (f"\n  [yellow]investigate : {len(gaps)} trou(s) ({escape(', '.join(gaps))}) — aucune action "
                 "disruptive autonome sur ce cycle[/yellow]")
    if enquete.get("refusee"):
        line += f"\n  [yellow]investigate : un tour refusé ({escape(enquete['refusee'][:200])}) — le chemin du code[/yellow]"
    _console().print(line)
