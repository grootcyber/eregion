"""The plan of an identity card (IR1a, docs/design/reponse-identite.md §3.2): what to do about
one finding of C2, written by the code from the row of the log — never by the model —, its
parameters read on Microsoft Graph, read only (glorfindel/providers/azure/graph.py).

        finding                 verbs (the identity executor's, IR1c)    steps for a human
        credential added        entra_remove_credential (that one)       the other credentials, if
                                                                         the author is not expected
        consent                 entra_disable_principal (the CLIENT,     remove the grant or the
                                never the resource's principal)          assignment; revoke the
                                                                         sessions of who consented
        privileged role         —  (a user's verb waits for IDI1b)       remove the assignment;
                                                                         revoke the sessions
        unusual sign-in         entra_remove_credential (the one used,   the other credentials
                                if the row names it), else
                                entra_disable_principal
        Glorfindel's identity   none                                     renew its credentials

Each item says what, on which object, with its exact parameters, the complete command a human
types today (no executor exists before IR1c: every item is done by hand, with the operator's own
account), its side effect, its way back, and what the check reads afterwards (entra_check.py).

What is never done:
  - **a value invented**: a parameter neither in the row nor read on Graph is marked « not read »,
    with why, and the command that needs it says so (`complete: False`);
  - **a value of the log put in a command unchecked**: a command holds only ids that are ids — an
    object id (a GUID), a grant's or an assignment's id (letters, digits, `-`, `_`), a scope of a
    role (`/`, `/administrativeUnits/<GUID>`), a permission's words. A name never: an attacker
    chooses the name of an application; the card shows it as text, escaped (the console's `_attr`,
    the bot's markdown);
  - **a verb of the executor on Glorfindel's identity**, actor or target (§3.5): its plan is
    the renewal of its credentials, and every step a human's;
  - **a verb on a user**: a user is enrolled only by IDI1b (§3.6), not built — its revocation and
    its disabling stay steps.

`never_target` (IDI1, #546, eregion_core/never_target.py): `build` takes a `protected` predicate
(`never_target_protected`, the watch's) which turns an item aimed at one of its ids into a human's
step, its reason said — the first of the three locks of §3.5 —, a human's own verb too (its
reason first). The list unreadable (no operator named), every id is covered: every item a
human's. Its whole rule on an identity read from Graph (`NeverTarget.why`: another tenant's
application, a resource's principal) is the executor's (IR1c), which reads the identity whole
before acting.

An identity of the defense (IR1f, #828, the bench of 14/11): never cut off by default.
  - **Glorfindel's** (its marks: actor, target, or the client of a consent — `ClientId`,
    `entra.target_ids`): never disabled; a consent given to it begins with what to check (that
    the gesture is the operator's: the watch's reads of Graph, docs/operations.md), every other
    step conditional (« Si ce n'est pas le geste de l'opérateur », optional, never counted by
    Verify); its credential or its sign-in, with the renewal of its credentials;
  - **one never_target lists** (read, `protected.listed`), that a step would disable or whose
    sessions it would revoke: the same check first, every step conditional, its reason said;
  - **an author never_target lists** (an operator, of a credential, a consent, a role): said
    protected, and no step aims at it — never a revocation of its sessions;
  - the plan says it (`defense`, `protected`), on the card, in the console and in Discord.
The hour of the event (`event_at`) is read as azure-monitor-query gives it (a datetime, or its
`str()`); absent or illegible, the plan says it (`event_at_why`) and Verify never says « held ».
"""
from __future__ import annotations

from datetime import datetime, timezone

from glorfindel.providers.azure.entra_grants import _consent_items, _role_items
from glorfindel.providers.azure.entra_items import (
    PLAN_VERSION, _GLORFINDEL, _NO_EXECUTOR, _Reads, _credential_items, _item, _signin_items, guid, placeholder,
    when,
)


# ── The plan ───────────────────────────────────────────────────────────────────────────────

_LISTED = ("une identité jamais ciblée (never_target : Glorfindel, Orodruin, Annatar, un opérateur, "
           "une identité listée)")


def never_target_protected(env=None):
    """`protected` from the process's never_target list (IDI1): an id it covers → why. The list
    unreadable, every id is covered, and its reason is the one said. `protected.listed(id)` (IR1f):
    the id is IN the list, the list read — never true of an unreadable list, which names no one:
    there every step stays, a human's, its reason said."""
    from eregion_core.never_target import NeverTarget
    never = NeverTarget.from_env(env)

    def protected(object_id: str) -> str:
        if not never.covers(object_id):
            return ""
        return ("never_target illisible, aucune identité n'est une cible : " + never.refusal()
                if never.refusal() else _LISTED)

    def listed(object_id: str) -> bool:
        return not never.refusal() and bool(guid(object_id)) and never.covers(object_id)

    protected.listed = listed
    return protected


def _glorfindels(row: dict) -> bool:
    return row.get("GlorfindelIdentity") is True or row.get("GlorfindelManaged") is True


# What cuts an identity off: never a default step on an identity of the defense (IR1f, E-1).
_CUTS = ("entra_disable_principal", "entra_disable_user", "entra_revoke_sessions")
# The kinds whose actor is an author (an audit log's InitiatedBy); a sign-in's actor is its subject.
_AUTHORED = ("credential", "consent", "role")
_IF_NOT_OPERATOR = "Si ce n'est pas le geste de l'opérateur : "
_ASK = "Graph ne peut pas le vérifier : que ce soit le geste de l'opérateur, lui seul le dit"


def _conditional(i: dict) -> dict:
    """An item of a plan on an identity of the defense: done only if the gesture is not the
    operator's — never a default step, never counted in Verify's verdict."""
    if not i["what"].startswith(_IF_NOT_OPERATOR):
        i["what"] = _IF_NOT_OPERATOR + i["what"][:1].lower() + i["what"][1:]
    if i["by"] == "executor":         # after the check the human makes first: never ahead of it
        i.update(by="human", why_human=i["why_human"] or _NO_EXECUTOR)
    i["optional"] = True
    return i


def _ask_the_operator(who: str, why: str) -> dict:
    """The first step of a plan on an identity of the defense: what to check, and why."""
    return _item(f"Vérifier avec l'opérateur que ce geste est le sien (par exemple les lectures de Microsoft "
                 f"Graph données à la watch, docs/operations.md) : {who} — jamais désactivée ni privée de ses "
                 "droits d'office, un attaquant ne doit pas pouvoir faire couper la défense par Eregion (§3.5)",
                 why_human=why, unchecked=_ASK)


def _authors(row: dict) -> set[str]:
    """The author's ids: its object id, an application's client id."""
    return {guid(row.get("ActorId")), guid(row.get("ActorAppId"))} - {""}


def _defend(row: dict, kind: str, items: list[dict], protected, said: list[str]) -> tuple[list[dict], bool]:
    """E-2 then E-1 (IR1f): no step aims at an author never_target lists; an identity of the
    defense — Glorfindel's (its marks), or one never_target lists that a step would cut off — is
    never cut off by default: its plan says what to check first, and every other step is
    conditional. The plan says who is protected, and why (`said`)."""
    listed = (getattr(protected, "listed", None) or (lambda oid: bool(protected(oid)))) if protected \
        else (lambda oid: False)
    held = {a for a in _authors(row) if listed(a)} if kind in _AUTHORED else set()
    if held:
        items = [i for i in items if i["target"].get("id") not in held]
        said.append(f"L'auteur, {str(row.get('ActorName') or '').strip()[:200] or ', '.join(sorted(held))}, "
                    f"est protégé ({protected(sorted(held)[0])}) : aucune étape ne le vise. Vérifier que ce geste "
                    "est le sien (un opérateur : avec lui) ; sinon, son compte ou ses identifiants sont entre "
                    "d'autres mains — sa réponse revient à un humain de son niveau, hors de ce plan.")
    cut = [i for i in items if i["verb"] in _CUTS and listed(i["target"].get("id", ""))]
    glorfindel = _glorfindels(row)
    if glorfindel:
        items = [i for i in items if i["verb"] not in ("entra_disable_principal", "entra_disable_user")]
        for i in items:
            i.update(by="human", why_human=_GLORFINDEL)
    if glorfindel and not (kind == "consent" and row.get("GlorfindelIdentity") is not True):
        items.insert(0, _item("Renouveler les identifiants de Glorfindel, puis revoir ce qu'ils ont fait "
                              "(geste de l'opérateur)", why_human=_GLORFINDEL,
                              unchecked="Graph ne peut pas le vérifier : le renouvellement des identifiants de Glorfindel se dit par l'opérateur"))
        said.append("Identité de la défense : l'identité de Glorfindel, "
                    + ("l'acteur." if row.get("GlorfindelIdentity") is True else "la cible."))
    elif glorfindel or cut:
        who = ("l'application cliente est l'identité de Glorfindel, une identité de la défense" if glorfindel else
               " ; ".join(sorted({i["target"].get("name") or i["target"].get("id") for i in cut}))
               + f" : {_LISTED}")
        items = [_ask_the_operator(who, _GLORFINDEL if glorfindel else _LISTED)] + [_conditional(i) for i in items]
        said.append(f"{'Identité de la défense' if glorfindel else 'Identité protégée'} — {who}.")
    return items, glorfindel or bool(cut)


def _ordered(items: list[dict]) -> list[dict]:
    """The executor's verbs first, in their order, then the steps for a human; numbered."""
    out = [i for i in items if i["by"] == "executor"] + [i for i in items if i["by"] != "executor"]
    for n, i in enumerate(out, 1):
        i["n"] = n
    return out


def build(row: dict, reader=None, *, protected=None, now: datetime | None = None) -> dict:
    """The plan of one finding (its row, as `entra.prepare_rows` marked it). `reader`: Graph,
    read only (None: nothing read, each parameter the log does not give marked « not read »).
    `protected(object_id) -> why`: a list of identities never a target (never_target, IDI1)."""
    now = now or datetime.now(timezone.utc)
    kind = str(row.get("EntraKind") or "").strip().lower()
    event_at = when(row.get("TimeGenerated"))
    reads = _Reads(reader)
    note = ""
    items: list[dict] = []
    if row.get("OmittedOperations"):
        note = "carte de synthèse : chaque opération a son plan sur sa propre carte, une fois relevée"
    elif kind == "credential":
        items = _credential_items(row, reads)
    elif kind == "consent":
        items = _consent_items(row, reads, event_at)
    elif kind == "role":
        items = _role_items(row, reads, event_at)
    elif kind == "signin":
        items = _signin_items(row, reads)
    else:
        note = "constat d'un autre type : aucun plan écrit par le code, vérifier dans les journaux d'Entra ID"
    said: list[str] = []
    items, defense = _defend(row, kind, items, protected, said)
    for i in items:       # every item aimed at an identity (only a verb has a target): the executor's and a human's
        held = protected(i["target"].get("id", "")) if protected and i["target"].get("id") else ""
        if held:          # never a verb of the executor on it: a human's step (§3.5, the first lock), its reason said
            i.update(by="human", protected=held,
                     why_human=held if i["by"] == "executor" or i["why_human"] in ("", held, _NO_EXECUTOR)
                     else f"{held} ; {i['why_human']}")
        elif i["by"] == "executor":
            i["why_human"] = _NO_EXECUTOR
    corr = str(row.get("CorrelationId") or "").strip()[:120]
    sessions = any((i.get("check") or {}).get("kind") == "sessions_revoked" or i["verb"] == "entra_revoke_sessions"
                   for i in items)
    return {
        "version": PLAN_VERSION, "kind": kind, "built_at": now.isoformat(), "event_at": event_at,
        # E-3 (IR1f): an hour absent or illegible is said — Verify then says « unreadable », never « held ».
        "event_at_why": "" if event_at or not sessions else (
            "l'heure de l'événement n'est pas lue (TimeGenerated absent ou illisible) : la révocation des "
            "sessions ne peut pas lui être comparée — « Verify » dira illisible, jamais tenu"),
        # E-1, E-2 (IR1f): an identity of the defense in the finding, and who is protected, and why.
        "defense": defense, "protected": said,
        "correlation_id": corr,
        "graph": {"read": reader is not None and not reads.why and reads.done > 0,
                  "why": reads.why or ("" if reads.done else "rien à lire")},
        "confirm": ("Vérifier d'abord avec l'auteur ou le propriétaire que ce n'est pas voulu"
                    + (f" (CorrelationId {corr})" if corr else "") + " : légitime (un pipeline connu), "
                    "l'exclure dans la couche du client, et ne rien retirer."),
        "items": _ordered(items), "note": note,
    }


def steps_text(plan: dict) -> list[str]:
    """The plan as the card's steps (Discord, the TUI, `glorfindel pending`): a line per item, its
    command between backticks — only ids in it, never a name."""
    lines = [plan.get("confirm") or ""] + [str(x) for x in plan.get("protected") or []]
    for i in plan.get("items") or []:
        tag = f"[{i['verb']}] " if i.get("verb") else ""
        cmd = f" : `{i['command']}`" if i.get("command") else ""
        line = f"{i['n']}. {tag}{i['what']}{cmd}"
        unread = [p for p in i.get("params") or [] if not p.get("read")]
        if unread:
            line += " — non lu : " + " ; ".join(
                f"{p['name']} ({p.get('why') or 'non lu'})"
                + (f", à mettre à la place de {placeholder(p['name'])}" if placeholder(p["name"]) in i.get("command", "") else "")
                for p in unread)
        if i.get("protected"):
            line += f" — à la main : {i['protected']}"
        if i.get("find"):
            line += f" — pour le trouver : `{i['find']}`"
        if i.get("before"):
            line += f" — avant : `{i['before']}`"
        if i.get("side_effect"):
            line += f" — effet de bord : {i['side_effect']}"
        if i.get("rollback"):
            line += f" — retour : {i['rollback']}"
        lines.append(line)
    if plan.get("note"):
        lines.append(plan["note"])
    if plan.get("event_at_why"):
        lines.append(str(plan["event_at_why"])[:1].upper() + str(plan["event_at_why"])[1:] + ".")
    graph = plan.get("graph") or {}
    if not graph.get("read") and graph.get("why") and plan.get("items"):
        lines.append(f"Graph non lu ({graph['why']}) : chaque paramètre non lu est marqué, jamais inventé.")
    if any(i.get("check") for i in plan.get("items") or []):
        lines.append("Après le geste : « Verify » sur la carte, dans la console — la watch relit Graph et dit "
                     "tenu, pas tenu ou illisible.")
    return [x for x in lines if x]
