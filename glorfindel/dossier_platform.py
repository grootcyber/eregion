"""The dossier's facts of the platform (DOS4, #1138; `docs/design/dossier-isolation.md` §3.2, §3.3, §3.6): what
the reads of Azure (`glorfindel/enquiry/platform.py`, made by the provider's adapter) said, as facts in the
form of `glorfindel/dossier.py` — F1a (the vault's job), F1b (the extensions: their writes in the log, the
platform's; their state in the instance view, the guest's), F1c (a start, a restart, a redeploy), F1d
(the health: its events, the availability now, the planned maintenance; `ServiceHealth` without object),
F2 (the host's series, for DOS5 to set against the guest's), F5a (Glorfindel's own gestures, their
duration by `operationId`), and F6g once the system is read in the VM's model.

**A fact says the state of its read.** A read `echec` or `refusee` makes every fact drawn from it
`illisible`, with the read's reason — never `vide`. A read that answered: a fact with rows is `lu`; with
none, `vide` only once its window is closed and its source's latency passed, `en_attente` before
(`complete`). Each fact names its read's author (`Read.author`: the first code to read it) and its
measure (`à mesurer`, with its DH). Composed by the code, never a verdict; nothing here reaches the
model, the signal or a gate. No call: the readings are given.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from glorfindel.dossier import (
    EN_ATTENTE, ILLISIBLE, LISTED, LU, SANS_OBJET, VIDE, WINDOWS_ONLY, _cut, _dict, fact,
)
from glorfindel.enquiry import catalog
from glorfindel.enquiry.platform import PLATFORM_READS

MEASURE = {"activity_window": "à mesurer (DH1)", "backup_jobs": "à mesurer (DH2)",
           "instance_view": "à mesurer (DH3)", "host_metrics": "à mesurer (DH4, DH13)",
           "resource_health": "à mesurer (DH7)"}
_SOURCE = {"activity_window": "le journal d'activité (ARM)", "backup_jobs": "les jobs du coffre (ARM)",
           "instance_view": "le modèle et la vue d'instance de la VM (ARM)",
           "host_metrics": "Azure Monitor, les métriques de l'hôte (ARM)",
           "resource_health": "Resource Health (ARM)"}
_OWN_ENV = ("AZURE_CLIENT_ID", "GLORFINDEL_OWN_CALLERS")
_EXTENSION_OPS = ("microsoft.compute/virtualmachines/extensions/write",
                  "microsoft.compute/virtualmachines/extensions/delete")
_BOOT_OPS = tuple(f"microsoft.compute/virtualmachines/{op}/action"
                  for op in ("start", "restart", "redeploy", "deallocate", "poweroff", "reapply"))
JOB_BEFORE, JOB_AFTER = timedelta(minutes=30), timedelta(minutes=10)      # F1a's window, §3.2


def complete(read_id: str, t: datetime, now: datetime) -> bool:
    """Whether `read_id`'s window is closed and its source's latency passed since: what it did not give
    then, it will not give."""
    read = PLATFORM_READS[read_id]
    return now >= catalog.window(read, t)[1] + timedelta(seconds=read.latency_s)


def own_ids() -> frozenset[str]:
    """Who Glorfindel is on Azure, as the door reads it (LEV2): AZURE_CLIENT_ID, GLORFINDEL_OWN_CALLERS."""
    out: set[str] = set()
    for name in _OWN_ENV:
        out |= {p.strip().lower() for p in (os.environ.get(name) or "").split(",") if p.strip()}
    return frozenset(out)


def _when(text) -> datetime | None:
    return catalog._when(text)


class _Facts:
    """The facts drawn from one pass's readings."""

    def __init__(self, readings: dict, t: datetime, now: datetime) -> None:
        self.readings, self.t, self.now, self.lu_a = readings, t, now, now.isoformat()

    def _common(self, read_id: str, reading) -> dict:
        read = PLATFORM_READS[read_id]
        return dict(source=_SOURCE[read_id], lecture=_cut(read.query, 400), lu_a=self.lu_a,
                    auteur=read.author, mesure=MEASURE[read_id])

    def drawn(self, code: str, id_: str, read_id: str, rows: list, dit, valeurs=None, auteur: str = "") -> dict:
        """A fact drawn from `rows` of `read_id`'s reading: its read's state when it said nothing."""
        reading = self.readings[read_id]
        common = self._common(read_id, reading)
        if auteur:
            common["auteur"] = auteur
        if reading.etat in (catalog.ECHEC, catalog.REFUSEE, catalog.NON_PERMISE, catalog.SANS_OBJET):
            return fact(code, id_, etat=catalog.CARD_STATE[reading.etat], etat_lecture=reading.etat,
                        dit=f"{_SOURCE[read_id]} : non lu", pourquoi=reading.why, **common)
        listed = rows[:LISTED]
        vals = {"nombre": len(rows), "liste": listed, **(valeurs or {})}
        if rows:
            open_ = "" if complete(read_id, self.t, self.now) else " (fenêtre encore ouverte : relu)"
            return fact(code, id_, etat=LU, etat_lecture=catalog.LIGNES, dit=dit(rows) + open_, valeurs=vals,
                        **common)
        if complete(read_id, self.t, self.now):
            return fact(code, id_, etat=VIDE, etat_lecture=catalog.VIDE, dit=dit(rows), valeurs=vals, **common)
        latency = PLATFORM_READS[read_id].latency_s
        return fact(code, id_, etat=EN_ATTENTE, etat_lecture=catalog.EN_ATTENTE, valeurs=vals, **common,
                    dit=f"{_SOURCE[read_id]} : rien encore — sa fenêtre n'est pas close, ou sa latence ({latency} s) "
                        "pas passée")

    def events(self, ops=(), category: str = "") -> list:
        rows = self.readings["activity_window"].rows if "activity_window" in self.readings else []
        return [r for r in rows if (not ops or str(r.get("operation") or "").lower() in ops)
                and (not category or str(r.get("category") or "").lower() == category)]


def _ops_of(rows: list) -> list[dict]:
    """Events grouped by `operationId`: the first `Started`, the last state, the duration between."""
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r.get("operation_id") or f"{r.get('operation')}|{r.get('at')}", []).append(r)
    out = []
    for op_id, group in by.items():
        group.sort(key=lambda r: r.get("at") or "")
        started = next((r for r in group if str(r.get("status")).lower() == "started"), group[0])
        last = group[-1]
        a, b = _when(started.get("at")), _when(last.get("at"))
        out.append({"operation": started.get("operation"), "resource": _cut(started.get("resource")),
                    "operation_id": str(op_id)[:80], "debut": started.get("at"), "fin": last.get("at"),
                    "statut": last.get("status"), "ids": last.get("ids") or [],
                    **({"duree_s": round((b - a).total_seconds())} if a and b else {})})
    return sorted(out, key=lambda o: o["debut"] or "")


def platform_facts(readings: dict, t: datetime, now: datetime) -> list[dict]:
    """The facts of the platform from `readings` ({read id: catalog.Reading}, those of this pass)."""
    f, out = _Facts(readings, t, now), []
    if "backup_jobs" in readings:
        jobs = readings["backup_jobs"].rows
        near = [dict(j, ecart_s=round((_when(j["start"]) - t).total_seconds())) for j in jobs
                if _when(j.get("start")) and t - JOB_BEFORE <= _when(j["start"]) <= t + JOB_AFTER]
        backups = [j["start"] for j in jobs if str(j.get("operation")).lower() == "backup"]
        out.append(f.drawn("F1a", "backup_job", "backup_jobs", near, valeurs={"sauvegardes_10j": backups[-40:]},
                           dit=lambda r: (f"{len(r)} job(s) du coffre de T − 30 min à T + 10 min : "
                                          + "; ".join(f"{j['operation']} {j['status']} parti à {j['start']} "
                                                      f"({j['ecart_s']:+d} s de T)" for j in r[:3]))
                           if r else "aucun job du coffre de T − 30 min à T + 10 min — l'heure d'une sauvegarde "
                                     "est prévisible : une attaque peut s'y caler"))
    if "activity_window" in readings:
        ext = _ops_of(f.events(_EXTENSION_OPS))
        out.append(f.drawn("F1b", "extensions_log", "activity_window", ext,
                           dit=lambda r: f"{len(r)} écriture(s) d'extension au journal d'activité dans la fenêtre"
                           if r else "aucune écriture d'extension au journal d'activité de T − 30 à T + 30 min"))
        boots = _ops_of(f.events(_BOOT_OPS))
        out.append(f.drawn("F1c", "reboot", "activity_window", boots,
                           dit=lambda r: "; ".join(f"{o['operation'].rsplit('/', 2)[-2]} {o['statut']} à {o['debut']}"
                                                   for o in r[:3]) if r else
                           "aucun démarrage, redémarrage ni redéploiement au journal d'activité dans la fenêtre"))
        health = _ops_of(f.events(category="resourcehealth"))
        out.append(f.drawn("F1d", "health_events", "activity_window", health,
                           dit=lambda r: f"{len(r)} événement(s) de santé de la VM dans la fenêtre" if r
                           else "aucun événement de santé de la VM au journal d'activité dans la fenêtre"))
        out.append(_own_operations(f))
    if "instance_view" in readings:
        view = (readings["instance_view"].rows or [{}])[0]
        exts = view.get("extensions") or []
        out.append(f.drawn("F1b", "extensions_view", "instance_view", exts,
                           dit=lambda r: "état des extensions, dit par l'agent de la VM (l'invité) : "
                                         + "; ".join(f"{e['name']} {(e['states'] or [{}])[-1].get('code', '?')}"
                                                     for e in r[:4]) if r else
                           "aucune extension dans la vue d'instance (dit par l'agent de la VM)"))
        m = view.get("maintenance")
        out.append(f.drawn("F1d", "maintenance", "instance_view", [m] if m else [], auteur=catalog.PLATFORM,
                           dit=lambda r: f"maintenance planifiée : {r[0]}" if r
                           else "aucune maintenance planifiée dans la vue d'instance"))
    if "resource_health" in readings:
        out.append(f.drawn("F1d", "availability", "resource_health", readings["resource_health"].rows,
                           dit=lambda r: f"disponibilité selon Azure : {r[0]['etat']}"
                                         + (f" ({r[0]['raison']})" if r[0].get("raison") else "") if r
                           else "Resource Health ne dit rien de la VM"))
        out.append(fact("F1d", "service_health", etat=SANS_OBJET, source="ServiceHealth (abonnement)",
                        lecture="aucune", lu_a=f.lu_a, auteur=catalog.PLATFORM, mesure=MEASURE["resource_health"],
                        dit="ServiceHealth vit au niveau de l'abonnement : sans objet sous le Reader du groupe, "
                            "aucun droit n'est demandé (§3.2)"))
    if "host_metrics" in readings:
        points = readings["host_metrics"].rows
        out.append(f.drawn("F2", "host_metric", "host_metrics", points,
                           dit=lambda r: f"{len(r)} point(s) de l'hôte, à la minute, de T − 5 à T + 3 min (le "
                                         "rapport à l'invité, minute décalée : DOS5)" if r
                           else "l'hôte ne donne aucun point d'écriture disque de T − 5 à T + 3 min"))
    return out


def _own_operations(f: _Facts) -> dict:
    """F5a: Glorfindel's own gestures on the VM since T − 1 min, their duration by operationId."""
    mine = own_ids()
    reading = f.readings["activity_window"]
    if not mine and reading.etat in (catalog.LIGNES, catalog.VIDE, catalog.EN_ATTENTE):
        return fact("F5a", "own_operations", etat=ILLISIBLE, **f._common("activity_window", reading),
                    dit="gestes de Glorfindel non reconnus",
                    pourquoi="l'identité de Glorfindel n'est pas connue de la watch (AZURE_CLIENT_ID, "
                             "GLORFINDEL_OWN_CALLERS)")
    since = f.t - timedelta(minutes=1)
    rows = [r for r in f.events() if mine & set(r.get("ids") or []) and (_when(r.get("at")) or since) >= since]
    ops = _ops_of(rows)
    return f.drawn("F5a", "own_operations", "activity_window", ops,
                   dit=lambda r: "; ".join(f"{o['operation']} {o['statut']}"
                                           + (f" en {o['duree_s']} s" if "duree_s" in o else "")
                                           for o in r[:4]) if r else
                   "aucun geste de Glorfindel sur la VM au journal d'activité depuis T")


def system_of(readings: dict) -> str:
    """The VM's system, read in its model (the platform's word), or ""."""
    reading = readings.get("instance_view")
    if reading is None or reading.etat != catalog.LIGNES:
        return ""
    return str((reading.rows or [{}])[0].get("systeme") or "")


def with_system(model_inputs: dict, system: str) -> dict:
    """F6g once the VM's system is read (step 0 could not, with no call): each empty read of the Process
    counter said by the catalogue's rule for that system — sans objet under Linux, empty under Windows."""
    if not system or model_inputs.get("code") != "F6g":
        return model_inputs
    vals = _dict(model_inputs.get("valeurs"))
    items = []
    for item in vals.get("requetes") or []:
        item = dict(item)
        if item.get("requete") in WINDOWS_ONLY and not item.get("lignes") and item.get("etat") != ILLISIBLE:
            why = catalog.says(catalog.READS[item["requete"]], system)
            item.update({"etat": SANS_OBJET, "pourquoi": why} if why else {"etat": VIDE})
            if not why:
                item.pop("pourquoi", None)
        items.append(item)
    return {**model_inputs, "valeurs": {**vals, "systeme": system, "systeme_lu_dans": "le modèle de la VM (ARM)",
                                        "requetes": items}}
