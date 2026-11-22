"""The dossier's local facts of step 0 (DOS3, #1043; `docs/design/dossier-isolation.md` §3.5 to §3.7): what
the cycle already holds, read at its end from its state and from local files, with no call — F3c (the
VM's past cards for the rule), F4c (what the model saw of a successful login), F5b (the drain), F5c (the
verification), F6a to F6h (the decision as it was taken; `glorfindel/cycle_line.py`).

Each fact in the form of `glorfindel/dossier.py` (`fact`): an unreadable source is `illisible` with its
reason, never `vide`; a source that cannot say anything here (the Process counter under Linux) is
`sans_objet`. One fact that breaks is unreadable, never the dossier lost (`local_facts`). Nothing here
reaches the signal, the memory or the model; no gate reads it.
"""
from __future__ import annotations

from glorfindel.dossier import (
    EN_ATTENTE, ILLISIBLE, ISOLATION, LISTED, LU, RECURRENCE_DAYS, SANS_OBJET, VIDE, WINDOWS_ONLY,
    _cut, _dict, _epoch, _first_line, _isolation_state, _iso, _kept, _same_id, fact, signal_time,
)

# ── F3c, F4c, F5b, F5c ─────────────────────────────────────────────────────────

def _past_cards(state: dict, t: str, now: str) -> dict:
    """F3c: the cards of this VM and this rule over RECURRENCE_DAYS before T, and their verdicts."""
    from glorfindel import escalations
    signal = state["signal"]
    rid, rule = str(signal.get("resource_id") or ""), str(_dict(signal.get("context")).get("rule_name") or "")
    ttp = str(signal.get("ttp") or "")
    by = f"la règle {rule}" if rule else f"la technique {ttp}"
    common = dict(source="~/.glorfindel/escalations.jsonl", lu_a=now,
                  lecture=f"cartes de la VM et de {by}, de T − {RECURRENCE_DAYS} j à T")
    until = _epoch(t)
    if until is None:
        return fact("F3c", "past_cards", etat=ILLISIBLE, dit="cartes passées non lues",
                    pourquoi="l'heure du signal ne se lit pas : la fenêtre ne s'ancre pas", **common)
    try:
        lines = escalations._read_lines() if escalations._STORE.exists() else []
    except OSError as exc:
        return fact("F3c", "past_cards", etat=ILLISIBLE, dit="cartes passées non lues",
                    pourquoi=f"le magasin des cartes ne se lit pas : {_first_line(exc)}", **common)
    since = until - RECURRENCE_DAYS * 86400
    unreadable, undated, found = 0, 0, []
    for line in lines:
        e = escalations._card_of(line)
        if e is None:
            unreadable += bool(line.strip())
            continue
        if not _same_id(e.get("resource_id"), rid) or e.get("signal_id") == signal.get("signal_id"):
            continue
        if (escalations.rule_of(e) != rule) if rule else (str(e.get("ttp") or "") != ttp):
            continue
        at = escalations._zoned(e)
        if at is None:
            undated += 1
        elif since <= at.timestamp() < until:
            found.append((at.timestamp(), e))
    found.sort(key=lambda p: p[0], reverse=True)
    verdicts: dict[str, int] = {}
    for _, e in found:
        verdict = str(e.get("verdict") or "sans verdict")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    valeurs = {"jours": RECURRENCE_DAYS, "depuis": _iso(since), "jusqu_a": t, "cartes": len(found),
               "par_verdict": verdicts, "en_attente": sum(e.get("status") == "pending" for _, e in found),
               "non_datees": undated, "lignes_illisibles": unreadable,
               "dernieres": [{"id": str(e.get("id") or "")[:8], "first_seen": str(e.get("first_seen") or ""),
                              "type": str(e.get("escalation_type") or ""), "statut": str(e.get("status") or ""),
                              "verdict": str(e.get("verdict") or "")} for _, e in found[:LISTED]]}
    said = f"{len(found)} carte(s) de cette VM pour {by} sur {RECURRENCE_DAYS} j"
    if not found and (unreadable or undated):     # a card may be among them: never « none »
        return fact("F3c", "past_cards", etat=ILLISIBLE, dit=said, valeurs=valeurs, pourquoi=(
            f"{unreadable} ligne(s) du magasin illisible(s), {undated} carte(s) sans heure placée : "
            "une carte de cette VM peut s'y trouver"), **common)
    if unreadable or undated:
        said += f" (au moins : {unreadable} ligne(s) illisible(s), {undated} sans heure)"
    return fact("F3c", "past_cards", etat=LU if found else VIDE, dit=said, valeurs=valeurs, **common)


def _context(state: dict) -> tuple[dict, list]:
    raw = _dict(state["signal"].get("raw_signal"))
    return _dict(raw.get("investigative_context")), [str(g) for g in state.get("telemetry_gaps") or []]


def _model_saw_auth(state: dict, now: str) -> dict:
    """F4c: the lines `successful_auth_from_ip` gave the model, when investigate ran it (a brute force)."""
    ctx, gaps = _context(state)
    common = dict(source="le cycle (raw_signal.investigative_context)", lu_a=now,
                  lecture="successful_auth_from_ip : Syslog, sshd, « Accepted » de l'adresse, 5 min")
    name = "successful_auth_from_ip"
    if name in gaps:
        return fact("F4c", "model_saw_auth", etat=ILLISIBLE, dit="ce que le modèle a vu des connexions : inconnu",
                    pourquoi="la requête a échoué, ou n'a pas été lancée (une valeur refusée)", **common)
    if name not in ctx:
        return fact("F4c", "model_saw_auth", etat=SANS_OBJET, dit="requête non lancée : pas un brute force", **common)
    rows = [r for r in ctx[name] if isinstance(r, dict)] if isinstance(ctx[name], list) else None
    if rows is None:
        return fact("F4c", "model_saw_auth", etat=ILLISIBLE, dit="ce que le modèle a vu des connexions : inconnu",
                    pourquoi="le résultat n'a pas la forme d'une liste de lignes", **common)
    lines = [{"TimeGenerated": _cut(r.get("TimeGenerated"), 40), "SyslogMessage": _cut(r.get("SyslogMessage"))}
             for r in rows[:LISTED]]
    said = (f"{len(rows)} ligne(s) « Accepted » de l'adresse vues par le modèle (Syslog : écrit par l'invité, "
            "forgeable)") if rows else "aucune ligne « Accepted » de l'adresse dans la fenêtre de la requête"
    return fact("F4c", "model_saw_auth", etat=LU if rows else VIDE, dit=said,
                valeurs={"lignes": len(rows), "extraits": lines}, **common)


def _drain(state: dict, kind: str, now: str) -> dict:
    """F5b: the drain — asked when, ended or not, in how long; `pending` followed by DRN1."""
    from glorfindel.response.policy import drain_case, drain_said
    common = dict(source="l'état d'isolement (drains_at, drain, drain_ended_at) ; l'issue du cycle", lu_a=now,
                  lecture="~/.glorfindel/isolation/ de la VM ; outcome.drain")
    if kind != ISOLATION:
        return fact("F5b", "drain", etat=SANS_OBJET, dit="aucune isolation exécutée par ce cycle", **common)
    iso, why = _isolation_state(str(state["signal"].get("resource_id") or ""))
    if why:
        return fact("F5b", "drain", etat=ILLISIBLE, dit="coupure inconnue", pourquoi=why, **common)
    iso = iso or {}
    drain = _dict(iso.get("drain")) or _dict(_dict(state.get("outcome")).get("drain"))
    if not drain:
        return fact("F5b", "drain", etat=ILLISIBLE, dit="coupure inconnue",
                    pourquoi="ni l'état d'isolement ni l'issue du cycle ne disent la coupure", **common)
    asked = [str(a) for a in iso.get("drains_at") or [] if a][-1:]
    valeurs = {"statut": str(drain.get("status") or ""), "demandee_a": asked[0] if asked else "",
               "terminee_a": str(iso.get("drain_ended_at") or ""), "cas": drain_case(drain)}
    a, b = _epoch(valeurs["demandee_a"]), _epoch(valeurs["terminee_a"])
    if a is not None and b is not None:
        valeurs["duree_s"] = round(b - a)
    case = valeurs["cas"]
    if case == "pending":
        return fact("F5b", "drain", etat=EN_ATTENTE, valeurs=valeurs, **common,
                    dit="coupure des sessions en attente sur Azure, suivie par la watch (DRN1)")
    said = drain_said(drain) if case else "coupure aboutie : sessions coupées"
    if "duree_s" in valeurs:
        said += f", en {valeurs['duree_s']} s"
    return fact("F5b", "drain", etat=LU, dit=said, valeurs=valeurs, **common)


def _verification(state: dict, kind: str, now: str) -> dict:
    """F5c: the verdict of verify_action, its reason, when."""
    common = dict(source="l'issue du cycle (verify_action)", lecture="outcome : verified, method, verified_at, error",
                  lu_a=now)
    if kind != ISOLATION:
        return fact("F5c", "verification", etat=SANS_OBJET, dit="aucune isolation exécutée par ce cycle", **common)
    out = _dict(state.get("outcome"))
    valeurs = {k: _cut(out.get(k)) for k in ("verified", "method", "verified_at", "error", "drain_case")
               if out.get(k) not in (None, "")}
    if out.get("verified") is True:
        return fact("F5c", "verification", etat=LU, valeurs=valeurs, **common,
                    dit=f"isolation vérifiée sur Azure ({out.get('method') or '?'})")
    if out.get("verified") is False:
        return fact("F5c", "verification", etat=LU, valeurs=valeurs, **common,
                    dit=f"vérification en échec : {_cut(out.get('error') or 'raison non dite')}")
    return fact("F5c", "verification", etat=ILLISIBLE, dit="vérification sans conclusion", valeurs=valeurs,
                pourquoi=str(out.get("error") or "Azure n'a pas été relu"), **common)


def _decision_facts(state: dict, source: str, exercise_run: str, now: str) -> list[dict]:
    """F6a to F6h: the decision as it was taken (§3.7)."""
    from glorfindel import cycle_line
    c = dict(source="l'état du cycle", lu_a=now)
    signal = state["signal"]
    raw = _dict(signal.get("raw_signal"))
    row = _dict(raw.get("first_result_row") or raw.get("detected_data"))
    fp = _dict(cycle_line.rule_fingerprint(signal))
    shown = {str(k)[:60]: _cut(v) for k, v in list(row.items())[:8] if v not in (None, "", [], {})}
    rule = f"règle {fp.get('name') or '?'} ({fp.get('query_sha256') or 'empreinte non lue'})"
    out = [fact("F6a", "rule_margin", etat=LU if row else ILLISIBLE, valeurs={"empreinte": fp, "ligne": shown},
                pourquoi="la détection ne porte aucune ligne", lecture="raw_signal.first_result_row ; la règle", **c,
                dit=f"{rule} : {', '.join(f'{k}={v}' for k, v in shown.items()) or 'aucune ligne'} ; le seuil et "
                    "le pas vivent dans la requête de la règle : non lus, l'écart non calculé")]
    try:
        settings = cycle_line.settings()
    except Exception:
        settings = {"confidence_threshold": None, "decision_draws_required": None}
    threshold = settings.get("confidence_threshold")
    held = str(state.get("held_by") or ("mode" if state.get("mode_hold") else ""))
    gates = {"mode": str(state.get("autonomy_mode") or ""), "confiance": state.get("confidence"),
             "seuil": threshold, "retenue_par": held, "mode_hold": bool(state.get("mode_hold")),
             "escalade": bool(state.get("escalate")), "raison": _cut(state.get("escalation_reason"), 300),
             "plafond": {k: _kept(v) for k, v in _dict(state.get("ceiling")).items()},
             "plancher": _cut(state.get("floor")), "non_contenue": _cut(state.get("uncontained"))}
    conf = state.get("confidence")
    said = (f"mode {gates['mode'] or '?'}, confiance "
            f"{f'{conf:.0%}' if isinstance(conf, (int, float)) else '?'} (seuil "
            f"{f'{threshold:.0%}' if isinstance(threshold, (int, float)) else 'illisible'}), "
            + (f"retenue par {held}" if held else "escaladée" if gates["escalade"] else "partie seule")
            + " ; les gardes traversées ne sont pas notées, seule celle qui a retenu")
    out.append(fact("F6b", "gates", etat=LU, dit=said, valeurs=gates, lecture="autonomy_mode, held_by, escalate", **c))
    draws = [d for d in state.get("decision_draws") or [] if isinstance(d, dict)]
    required = settings.get("decision_draws_required")
    out.append(fact("F6c", "draws", etat=LU if draws else VIDE, lecture="decision_draws", **c,
                    valeurs={"requis": required, "tirages": [{k: _kept(v) for k, v in d.items()} for d in draws[:LISTED]]},
                    dit=(f"{len(draws)} tirage(s) (requis : {required})" if draws
                         else f"aucun tirage de confirmation demandé (requis : {required})")))
    model = str(state.get("decision_model") or "")
    if model:
        out.append(fact("F6d", "model", etat=LU, dit=f"modèle {model}", valeurs={"modele": model},
                        lecture="decision_model", **c))
        sampling = {"premier": cycle_line.sampling(state),
                    "confirmation": dict(cycle_line.CONFIRMING_SAMPLING) if draws else None}
        out.append(fact("F6e", "temperature", etat=LU, valeurs=sampling, lecture="decision_temperature", **c,
                        dit=("premier tirage : défaut du fournisseur (le modèle refuse une température fixée)"
                             if sampling["premier"]["refused"] else "premier tirage : température 0, fixée")
                            + ("; tirages de confirmation : défaut du fournisseur" if draws else "")))
    else:
        for code, id_ in (("F6d", "model"), ("F6e", "temperature")):
            out.append(fact(code, id_, etat=SANS_OBJET, dit="le modèle n'a pas été appelé : une décision du code",
                            lecture="decision_model", **c))
    version = cycle_line.glorfindel_version()
    out.append(fact("F6f", "version", etat=ILLISIBLE if version.get("unreadable") else LU, valeurs=version,
                    pourquoi=str(version.get("unreadable") or ""), lecture="eregion_core.version", **c,
                    dit=f"Glorfindel {version.get('ref') or version.get('revision') or '?'} "
                        f"(paquet {version.get('package') or '?'})"))
    out.append(_model_inputs(state, now))
    labelled = source in ("real", "exercise")
    out.append(fact("F6h", "source", etat=LU if labelled else ILLISIBLE, lecture="_cycle_source (B2)", **c,
                    valeurs={"source": source, "exercise_run": exercise_run},
                    pourquoi="l'étiquetage exercice ou réel ne se lit pas",
                    dit="exercice" + (f" ({exercise_run})" if exercise_run else "") if source == "exercise"
                    else "trafic réel" if source == "real" else "source inconnue"))
    return out


def _vm_os(state: dict) -> str:
    """The VM's system, as the cycle tells it with no call: the drain ran `ss` (linux) or said Windows."""
    drain = _dict(_dict(state.get("outcome")).get("drain"))
    if drain.get("status") == "unsupported":
        return "windows"
    if drain.get("status") in ("drained", "partial", "pending"):     # RunShellScript, asked after the OS read
        return "linux"
    row = _dict(_dict(state["signal"].get("raw_signal")).get("first_result_row"))
    return "linux" if "SyslogMessage" in row else ""


def _model_inputs(state: dict, now: str) -> dict:
    """F6g: each query of investigate, its rows, and what it could not say; the failed ones."""
    ctx, gaps = _context(state)
    system = _vm_os(state)
    items = []
    for name in list(ctx) + [g for g in gaps if g not in ctx]:
        rows = ctx.get(name)
        n = len(rows) if isinstance(rows, list) else 0
        if name in gaps or not isinstance(rows, list):
            item = {"etat": ILLISIBLE, "pourquoi": "en échec, ou non lancée (une valeur refusée)"}
        elif name in WINDOWS_ONLY and not n:
            item = ({"etat": SANS_OBJET, "pourquoi": "compteur Process : Windows seul, jamais rempli sous Linux"}
                    if system == "linux" else {"etat": VIDE} if system == "windows" else
                    {"etat": ILLISIBLE, "pourquoi": "compteur Process de Windows seul, et le système de la VM "
                                                    "ne se lit pas sans appel : ni vide ni sans objet"})
        else:
            item = {"etat": LU if n else VIDE}
        items.append({"requete": str(name)[:60], "lignes": n, **item})
    unread = [f"{i['requete']} : {i['pourquoi']}" for i in items if i["etat"] == ILLISIBLE]
    common = dict(source="le cycle (investigative_context, telemetry_gaps)", lu_a=now,
                  lecture="les requêtes d'investigate", valeurs={"systeme": system or "inconnu", "requetes": items})
    said = "; ".join(f"{i['requete']} : {i['lignes']} ligne(s), {i['etat']}" for i in items)
    if unread:
        return fact("F6g", "model_inputs", etat=ILLISIBLE, dit=said, pourquoi="; ".join(unread), **common)
    return fact("F6g", "model_inputs", etat=LU if items else VIDE, **common,
                dit=said or "aucune requête d'enquête sur ce signal")


def local_facts(state: dict, kind: str, source: str, exercise_run: str, now: str) -> list[dict]:
    """The facts of step 0, each on its own: one that breaks is unreadable, never the dossier lost."""
    t, _ = signal_time(state["signal"])
    parts = [("F3c", "past_cards", lambda: [_past_cards(state, t, now)]),
             ("F4c", "model_saw_auth", lambda: [_model_saw_auth(state, now)]),
             ("F5b", "drain", lambda: [_drain(state, kind, now)]),
             ("F5c", "verification", lambda: [_verification(state, kind, now)]),
             ("F6", "decision", lambda: _decision_facts(state, source, exercise_run, now))]
    out = []
    for code, id_, read in parts:
        try:
            out.extend(read())
        except Exception as exc:
            out.append(fact(code, id_, etat=ILLISIBLE, dit="fait non composé", source="le cycle", lecture="",
                            pourquoi=_first_line(exc), lu_a=now))
    return out
