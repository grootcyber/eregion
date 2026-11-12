from __future__ import annotations

import functools
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_STORE = Path.home() / ".glorfindel" / "escalations.jsonl"

# SEC3 (V-10): the store has many writers — the watch's workers and its reassertion pass, the
# console, the bot, the CLI. Each read-modify-write holds an flock on `<store>.lock`, and the
# store is rewritten whole (temporary file + os.replace): no card lost between two writers,
# no reader ever sees half a file.
_AFTER = threading.local()


def _locked(fn):
    """`fn` reads, changes and rewrites the store under its lock; what it hands to
    `_after_unlock` (a webhook) runs once the lock is released."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from glorfindel.response.locks import _file_lock
        outer = getattr(_AFTER, "calls", None) is None
        if outer:
            _AFTER.calls = []
        try:
            with _file_lock(_STORE.with_name(_STORE.name + ".lock")):
                result = fn(*args, **kwargs)
            calls = _AFTER.calls if outer else []
        finally:
            if outer:
                _AFTER.calls = None
        for call, arg in calls:
            call(arg)
        return result
    return wrapper


def _after_unlock(call, arg) -> None:
    pending_calls = getattr(_AFTER, "calls", None)
    if pending_calls is None:
        call(arg)
    else:
        pending_calls.append((call, arg))


# FS1a (#551, docs/design/file-actions-signee.md §2.4): who signs the proposals — set by the watch
# alone (glorfindel/cli.py, `watch`: its key, SEC19). A card the watch writes that holds an action
# (`action_queue.proposable`) carries the proposal it signs, signed again when the card is seen
# again; a card the console, the bot or the CLI writes carries none. Nobody reads it yet to act
# (FS1b). A signer unavailable, or a signature that fails, never stops a card being written.
_PROPOSER = None


def sign_proposals(signer_of) -> None:
    """The watch's: `signer_of()` gives its key's Signer, or None while it is unavailable."""
    global _PROPOSER
    _PROPOSER = signer_of


# FS1b (§7, « Ne re-signer qu'au-delà d'un âge »): a card seen again keeps the proposal it carries
# while that one still stands (this watch's, for the card as it is) and is younger than this —
# re-signed at each refresh, its digest changed under a request just named. Short enough for the
# age of an approval, read from the proposal's signed issued_at, to stay right.
RESIGN_AFTER_S = 600


def _propose(e: dict, seen_again: bool = False) -> None:
    if _PROPOSER is None:
        return
    try:
        from eregion_core import action_queue
        if not action_queue.proposable(e):
            return
        signer = _PROPOSER()
        if signer is None:
            return
        now = datetime.now(timezone.utc)
        if seen_again and action_queue.proposal_fresh(e, e.get("proposal"), signer.public, now, RESIGN_AFTER_S):
            return
        e["proposal"] = action_queue.sign_proposal(e, signer, now)
    except Exception:       # the card first: a proposal is never worth a card lost
        pass


def _write_lines(lines: list[str]) -> None:
    """The whole store, through a temporary file: owner-only (0600), never half-written."""
    from glorfindel.response.state import _atomic_write_text
    _atomic_write_text(_STORE, "\n".join(lines) + "\n")

# A re-fired escalation refreshes its (LLM-generated) content only when confidence
# moves at least this much — keeps a standing card current without flickering its
# reason/steps on every poll for a stable finding.
_MATERIAL_CONFIDENCE_DELTA = 0.1
# COR1 (#407): what a card that says a possible compromise opens with (agent._correlation_said).
# A card that did not say it, re-fired by a signal that does, is a material change: never a
# silent fold. So is a severity that rises (high → critical).
COMPROMISE_MARK = "Compte peut-être compromis"
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
# I3G (#446): the signal ids of what the reassertion says (glorfindel/reassert.py,
# reassert_cards.py, reassert_quarantine.py). Its cards never fold into a card of another
# origin — the graph's, say —, nor one of those into its own: see `record`.
_REASSERTION = ("reassert-", "state-unreadable-")


def _reassertion(signal_id) -> bool:
    """A card the reassertion wrote: its signal id, whatever its case (I3C)."""
    return str(signal_id or "").lower().startswith(_REASSERTION)


# DRN1 (#677): the cards of the session drain followed by the reassertion (glorfindel/drain_watch.py)
# — a card of its own on its VM, never folded into another card of the reassertion (a rule gone)
# nor one of those into it: the reason of the one would overwrite the other's. Its `:` is never in an
# Azure VM's name: the reassertion's card on a VM named `drain-web` is not one (DRN1 review).
_DRAIN_FOLLOW = "reassert-drain:"


def _drain_follow(signal_id) -> bool:
    return str(signal_id or "").lower().startswith(_DRAIN_FOLLOW)


_ACTION_LABELS = {
    "isolate_vm": "VM isolée du réseau",
    "release_isolation": "Isolation levée",
    "snapshot": "Snapshot forensique créé",
    "block_suspicious_ip": "IP suspecte bloquée",
    "revoke_temp_access": "Accès temporaire révoqué",
    "restore_from_backup": "Restauration depuis backup",
    "delete_resource": "Ressource supprimée",
    "wipe_storage": "Stockage effacé",
    "modify_network_rule": "Règle réseau modifiée",
    "escalate_permissions": "Permissions élevées",
    "improve_detection": "Règle de détection proposée",
    "investigate_detection_gap": "Détection empêchée — enquête requise",
    "activate_autonomy": "Réponse autonome en attente de confirmation",
    "review_isolation": "Isolation à revoir (TTL dépassé)",
    "review_recovery": "Reprise à revoir (restauration lue sur Azure, levée retenue)",
    "review_bypass": "Contournement à revoir (règle d'un tiers)",
    "repair_local_state": "État local à réparer",
    "review_left_rule": "Règle laissée à revoir (elle vise une autre VM)",
    "review_unverified": "Isolation ou blocage non vérifié (la vérification échoue)",
    "review_drain": "Coupure des sessions en attente (Run Command en cours sur Azure)",
}

_ESCALATION_LABELS = {
    "low_confidence": "confiance insuffisante",
    "destructive_action": "action destructive",
    "proposed_action": "action inconnue",
    "verification_failed": "vérification échouée",
    "proposed_rule": "règle de détection proposée",
    "posture_gap": "gap de posture",
    "orphan_rule": "règle orpheline (carte disparue)",
    "quarantine_altered": "NSG de quarantaine modifié",
    "detection_blocked": "détection empêchée (règle déjà en place)",
    "mode_hold": "action retenue (mode human_only)",
    "write_blocked": "écriture refusée (droits)",
    "action_failed": "action en échec",
    "cycle_failed": "signal non traité (cycle interrompu)",
    "uncharacterized_signal": "signal non caractérisé (garde-fou)",
    "release_hold": "levée retenue (restauration non terminée, ou rejeu possible au démarrage)",
    "ttl_exceeded": "isolation levée à l'expiration du TTL",
    "unattributed_signal": "détection non attribuée à cette VM",
    "telemetry_gap": "télémétrie incomplète (requêtes d'enquête en échec)",
    "unstable_decision": "décision instable (les tirages ne s'accordent pas)",
    "readiness_hold": "VM retenue en observation (préparation)",
    "queue_tampered": "file d'actions : une demande que son service n'a pas écrite (FS1b)",
    "queue_unavailable": "file d'actions : le registre de la watch illisible (FS1b)",
    "control_plane_change": "plan de contrôle modifié (détection seule)",
    "identity_change": "identité modifiée dans Entra ID (détection seule)",
    "protected_address": "adresse protégée (jamais bloquée)",
    "uncontained_detection": "détection non contenue (instantané seul)",
    "bypassed": "contournée (une règle d'autorisation passe avant le deny)",
    "state_unreadable": "état local illisible",
    "rule_left": "règle du blocage laissée (retournée, elle vise une autre VM)",
    "unverified": "non vérifiée (la vérification échoue)",
    "account_compromised": "compte peut-être compromis (brute force puis connexion réussie)",
    "compromise_unchecked": "connexion après brute force non vérifiée",
    "undecided_detection": "détection non décidée par le modèle (dédoublonnée, plafond, file pleine)",
    "drain_pending": "coupure des sessions en attente (l'isolation tient, la coupure est suivie)",
    "autonomous_action": "action autonome exécutée et vérifiée (à juger)",
}

# JUG1 (#760): the card of a disruptive action Glorfindel took alone (`non_disruptive`,
# `full_auto`), once its check held — a judgement after the fact, never an action to approve (not in
# `action_queue.APPROVABLE_TYPES`: no one-click execute, no proposal signed). Its `action` is the
# action that ran, so the report counts it among the disruptive ones; `executed` says the mode, the
# check and the evidence; `action_keys`, the action it stands for: one card per action, whatever
# the watch's restarts (`record`, `action_key`), never folded into another's.
EXECUTED_TYPE = "autonomous_action"


def executed_key(signal_id: str, resource_id: str, action: str, ip: str = "") -> str:
    """The key of one autonomous action: the cycle's signal (one per cycle), the VM, the action and
    the address it blocked — never the time it ran."""
    return ":".join(("executed", str(signal_id or "?"), str(resource_id or "").rstrip("/").lower(),
                     str(action or ""), str(ip or "")))


def _keys_of(e: dict) -> list[str]:
    keys = e.get("action_keys")
    return [k for k in keys if isinstance(k, str)] if isinstance(keys, list) else []


@_locked
def record(
    signal_id: str,
    resource_id: str,
    action: str,
    escalation_type: str,
    reason: str,
    run_id: str = "",
    suggested_steps: list[str] | None = None,
    ttp: str = "",
    severity: str = "",
    proposal_id: str = "",
    proposed_query: str = "",
    confidence: float = 0.0,
    action_params: dict | None = None,
    rule_name: str = "",
    source: str = "",
    exercise_run: str = "",
    explanation: str = "",
    replaces: dict[str, str] | None = None,
    identity_plan: dict | None = None,
    target: dict | None = None,
    action_key: str = "",
    executed: dict | None = None,
) -> str:
    """Append an escalation and return its id.

    `action_key` (JUG1, #760: `executed_key`): the autonomous action this card stands for. A card
    that already holds it — pending or not, judged or not — is the one: its id is returned and
    nothing is written, after a restart of the watch too. `executed`: what the action's card says
    (its mode, its check, its evidence).

    `target` (AL1c, #597): what a card of the control plane or of an identity is about
    (glorfindel/card_target.py) — kept on the card for the console and Discord; its `resource_id`
    is the target's.

    `replaces` (L1A, #480): the pending cards this one takes the place of, by id, each with
    the note of its closure — closed in the same write as this card is written, never before.
    Closed first, then the new card refused (a full disk), no card was left: the old one
    closed, the mark of what was said kept from before, and a pass that could not read the
    block again (its check unverified) said nothing — a disappearance in silence (L1). The
    write refused, both stay as they were. Closed before the dedup below: a replaced card
    never takes the new one in.

    Dedup: a pending escalation with the same action + resource_id + escalation_type
    is NOT duplicated — instead the standing one is kept as a single card and made
    *live*:
      - `occurrences` is incremented and `last_seen` bumped (cheap, every re-fire) so
        the operator sees "this keeps happening" at a glance (`first_seen` is preserved);
      - the expensive content (reason / suggested_steps / confidence) is refreshed ONLY
        on a MATERIAL change (a confidence shift ≥ _MATERIAL_CONFIDENCE_DELTA) so the
        card reflects the current situation without flickering on every poll, and the
        FIRST triage is preserved (`first_reason` / `first_suggested_steps`).
    This stops the re-decide output from being silently discarded on a persistent
    finding (the stale-card behaviour seen in the field).

    `source` (B2, eregion_core/exercise.py): `exercise` when an injector's window covers
    this VM, else `real` (empty on older cards = real). It is part of the dedup key: a
    real detection never merges into a pending exercise card, nor the reverse.
    A `control_plane_change` card (AL1) never merges: each is one operation. Nor an
    `identity_change` card (C2): each is one finding on one identity. Nor two cards whose
    action names two addresses (`action_params.ip`, SEC2): one card per address.
    Nor a card of the reassertion's (`reassert-…`, `state-unreadable-…`) and a card of
    another origin, either way (I3G): the graph's `verification_failed` card on a VM, still
    pending, took in the alert that its isolation vanished — its text, kept or overwritten,
    no notification, and the reassertion, which reads its own ids, never found it; folded
    the other way, the graph's re-fire overwrote the alert's text, its id still read « said ».
    """
    rid_lower = resource_id.lower()
    now = datetime.now(timezone.utc).isoformat()
    steps = suggested_steps or []
    lines = _STORE.read_text().splitlines() if _STORE.exists() else []
    if replaces:
        lines = _replaced(lines, replaces, now)
    if action_key:
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict) and action_key in _keys_of(e):
                return str(e.get("id") or "")       # JUG1: one card per action, never a second
    if lines:
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if (
                e.get("status") == "pending"
                and e.get("resource_id", "").lower() == rid_lower
                and e.get("action") == action
                and e.get("escalation_type") == escalation_type
                and (e.get("source") or "real") == (source or "real")
                # A control-plane card is one operation (who, what, which resource — AL1):
                # the next one, perhaps on Glorfindel's own rules, is never folded into it.
                and escalation_type != "control_plane_change"
                # Nor an identity card (C2): the next, perhaps on Glorfindel's own identity.
                and escalation_type != "identity_change"
                # Two addresses are two cards (SEC2): folded into one, its approval
                # blocked the first address only, the other never said.
                and (e.get("action_params") or {}).get("ip") == (action_params or {}).get("ip")
                # One origin, one card (I3G): what the reassertion says is said by its own card,
                # with its text and its notification — never folded into the graph's.
                and _reassertion(e.get("signal_id")) == _reassertion(signal_id)
                and _drain_follow(e.get("signal_id")) == _drain_follow(signal_id)
                # A detection without a decision of the model (SEC-A2): one card per VM and rule,
                # never one rule's folded into another's.
                and (escalation_type != "undecided_detection" or e.get("rule_name", "") == rule_name)
                # JUG1: each action taken alone has its own card — judged on its own, counted once
                # each among the disruptive actions; never folded into the card of another.
                and escalation_type != EXECUTED_TYPE
            ):
                e["occurrences"] = int(e.get("occurrences", 1)) + 1
                e["last_seen"] = now
                try:
                    material = abs(
                        float(confidence or 0.0) - float(e.get("confidence") or 0.0)
                    ) >= _MATERIAL_CONFIDENCE_DELTA
                except (TypeError, ValueError):
                    material = False
                # COR1: a compromise said now, or a severity that rises — the card says it.
                rises = _SEVERITY_RANK.get(severity or "", 0) > _SEVERITY_RANK.get(e.get("severity") or "", 0)
                said = COMPROMISE_MARK in (reason or "") and COMPROMISE_MARK not in (e.get("reason") or "")
                material = material or rises or said
                # SEC-A2: the card of the detections without a decision names the latest of them.
                material = material or escalation_type == "undecided_detection"
                if rises:
                    e["severity"] = severity
                if material:
                    # Preserve the initial triage before overwriting with the latest.
                    e.setdefault("first_reason", e.get("reason", ""))
                    e.setdefault("first_suggested_steps", e.get("suggested_steps", []))
                    e.setdefault("first_confidence", e.get("confidence", 0.0))
                    # COR1: a card that says a compromise keeps saying it — a plain re-fire of
                    # the same address (a scanner that goes on) never wipes it out.
                    if COMPROMISE_MARK in (reason or "") or COMPROMISE_MARK not in (e.get("reason") or ""):
                        e["reason"] = reason
                    e["suggested_steps"] = steps
                    e["confidence"] = confidence
                    if explanation:
                        e["explanation"] = explanation
                    e["updated_at"] = now
                _propose(e, seen_again=True)     # FS1a, FS1b: seen again — signed again past an age
                lines[i] = json.dumps(e, default=str)
                _write_lines(lines)
                return e["id"]

    esc = {
        "id": str(uuid.uuid4()),
        "timestamp": now,
        "first_seen": now,
        "last_seen": now,
        "occurrences": 1,
        "signal_id": signal_id,
        "resource_id": resource_id,
        "action": action,
        "escalation_type": escalation_type,
        "reason": reason,
        "run_id": run_id,
        "suggested_steps": steps,
        "ttp": ttp,
        "severity": severity,
        "proposal_id": proposal_id,
        "proposed_query": proposed_query,
        "confidence": confidence,
        "action_params": action_params or {},
        "rule_name": rule_name,
        "source": source,
        "exercise_run": exercise_run,
        # The model's plain-language explanation of the decision — what an operator judges
        # on; `reason` is often the gate's wording (a mode hold, low confidence).
        "explanation": explanation,
        "status": "pending",
        "resolved_at": None,
    }
    if target:
        # AL1c (#597): what a card of the control plane or of an identity is filed on — its
        # `resource_id` is the target's id; `vms`, the VMs an NSG covers, where the console shows it.
        esc["target"] = target
    if identity_plan:
        # IR1a: the plan of an identity card, and the thread of its checks (« Verify »). Never a
        # proposal of FS1a: an identity card holds no action (`action_queue.proposed_verbs`).
        esc["identity_plan"] = identity_plan
        esc["identity_checks"] = []
    if action_key:
        esc["action_keys"] = [action_key]
    if executed:
        esc["executed"] = executed
    _propose(esc)       # FS1a: the watch's proposal, when the card holds an action
    # Rewritten whole, as every write of the store: an append seen half-done by a reader
    # made its last line unreadable (SEC3, V-10). The cards it replaces closed in it (L1A).
    _write_lines([ln for ln in lines if ln.strip()] + [json.dumps(esc, default=str)])
    _after_unlock(_notify, esc)
    return esc["id"]


def _replaced(lines: list[str], replaces: dict[str, str], now: str) -> list[str]:
    """The store's lines, each pending card of `replaces` closed with its note (L1A) — a card
    closed since (by the operator) left as it is: its word stays the last."""
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except Exception:
            out.append(line)
            continue
        if isinstance(e, dict) and e.get("id") in replaces and e.get("status") == "pending":
            e["status"] = "resolved"
            e["resolved_at"] = now
            if replaces[e["id"]]:
                e["resolution"] = replaces[e["id"]]
            line = json.dumps(e, default=str)
        out.append(line)
    return out


@_locked
def resolve(escalation_id: str, note: str = "") -> None:
    """Mark an escalation as resolved — `note`: what resolved it, when Glorfindel did
    (an orphan rule taken off, A3)."""
    if not _STORE.exists():
        return
    lines = _STORE.read_text().splitlines()
    updated = []
    for line in lines:
        e = json.loads(line)
        if e["id"] == escalation_id:
            e["status"] = "resolved"
            e["resolved_at"] = datetime.now(timezone.utc).isoformat()
            if note:
                e["resolution"] = note
        updated.append(json.dumps(e, default=str))
    _write_lines(updated)


@_locked
def refresh(escalation_id: str, reason: str, **fields) -> bool:
    """A pending card's text brought up to what it says now (SEC13: a check's last error),
    its first text kept in `first_reason`; `fields` written beside it. False when the card
    no longer waits."""
    if not _STORE.exists():
        return False
    lines, done = _STORE.read_text().splitlines(), False
    for i, line in enumerate(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("id") == escalation_id and e.get("status") == "pending":
            now = datetime.now(timezone.utc).isoformat()
            e.setdefault("first_reason", e.get("reason", ""))
            e.update(fields, reason=reason, updated_at=now, last_seen=now)
            _propose(e, seen_again=True)     # FS1a, FS1b: seen again — signed again past an age
            lines[i], done = json.dumps(e, default=str), True
    if done:
        _write_lines(lines)
    return done


# IR1a: the checks a card keeps (its thread), newest last.
IDENTITY_CHECKS_KEPT = 20


def _rewrite_one(escalation_id: str, change) -> dict | None:
    """`change(e)` on the pending card `escalation_id` (under the lock, by the caller); the card
    changed, or None."""
    if not _STORE.exists():
        return None
    lines, found = _STORE.read_text().splitlines(), None
    for i, line in enumerate(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("id") == escalation_id and e.get("status") == "pending":
            change(e)
            lines[i], found = json.dumps(e, default=str), e
    if found is not None:
        _write_lines(lines)
    return found


@_locked
def request_identity_check(escalation_id: str) -> str:
    """The console's « Verify » on an identity card (IR1a): a request the watch reads, and answers
    by reading Graph (`identity_checks.run_requested`) — the console never reads Graph itself. The
    time of the request; KeyError when no pending card has this id, ValueError when it has no plan."""
    now = datetime.now(timezone.utc).isoformat()
    seen: dict = {}

    def change(e):
        seen["card"] = dict(e)
        if e.get("escalation_type") == "identity_change" and isinstance(e.get("identity_plan"), dict):
            e["identity_check_requested"] = now

    card = _rewrite_one(escalation_id, change)
    if card is None:
        raise KeyError(f"no pending card {escalation_id}")
    if "identity_check_requested" not in card or card["identity_check_requested"] != now:
        raise ValueError("this card has no identity plan to verify")
    return now


@_locked
def note_identity_check(escalation_id: str, result: dict) -> bool:
    """The watch's check, noted on the card's thread (`identity_checks`, the last
    IDENTITY_CHECKS_KEPT); the request it answers cleared, unless a newer one came meanwhile."""
    def change(e):
        thread = [c for c in (e.get("identity_checks") or []) if isinstance(c, dict)]
        e["identity_checks"] = (thread + [result])[-IDENTITY_CHECKS_KEPT:]
        asked = e.get("identity_check_requested") or ""
        if asked and asked <= (result.get("requested_at") or ""):
            e.pop("identity_check_requested", None)
        e["updated_at"] = datetime.now(timezone.utc).isoformat()

    return _rewrite_one(escalation_id, change) is not None


def identity_checks_requested() -> list[dict]:
    """The pending identity cards whose « Verify » waits for the watch."""
    return [e for e in pending() if e.get("escalation_type") == "identity_change"
            and isinstance(e.get("identity_plan"), dict) and e.get("identity_check_requested")]


@_locked
def resolve_by_resource(resource_id: str, action: str) -> int:
    """Resolve all pending escalations matching resource_id + action.

    resource_id comparison is case-insensitive — Azure ARM IDs are
    case-insensitive but Python string equality is not.
    """
    if not _STORE.exists():
        return 0
    rid_lower = resource_id.lower()
    lines = _STORE.read_text().splitlines()
    updated = []
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    for line in lines:
        e = json.loads(line)
        if (
            e["status"] == "pending"
            and e.get("resource_id", "").lower() == rid_lower
            and e["action"] == action
        ):
            e["status"] = "resolved"
            e["resolved_at"] = now
            count += 1
        updated.append(json.dumps(e, default=str))
    _write_lines(updated)
    return count


@_locked
def resolve_by_proposal(proposal_id: str) -> int:
    """Resolve all pending proposed_rule escalations for a given proposal_id."""
    if not _STORE.exists() or not proposal_id:
        return 0
    lines = _STORE.read_text().splitlines()
    updated = []
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    for line in lines:
        if not line.strip():
            updated.append(line)
            continue
        try:
            e = json.loads(line)
        except Exception:
            updated.append(line)
            continue
        if (
            e.get("status") == "pending"
            and e.get("escalation_type") == "proposed_rule"
            and e.get("proposal_id") == proposal_id
        ):
            e["status"] = "resolved"
            e["resolved_at"] = now
            count += 1
        updated.append(json.dumps(e, default=str))
    _write_lines(updated)
    return count


def pending() -> list[dict]:
    """Return all unresolved escalations, oldest first."""
    if not _STORE.exists():
        return []
    result = []
    for line in _STORE.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e["status"] == "pending":
            result.append(e)
    return result


def _action_words(action: str, resource_id: str, run_id: str, confidence: float, explanation: str,
                  verified: bool | None, ttp: str, severity: str, note: str, card: str,
                  mode: str) -> tuple[str, str, str, dict]:
    """An autonomous action's announcement: (title, text, level) for the VM's thread, and the
    webhook's (Slack) message as it always was — the card to judge named in both (JUG1)."""
    from glorfindel.chat_text import webhook_code, webhook_text
    label = _ACTION_LABELS.get(action) or action
    status = "✓" if verified else ("⚠" if verified is None else "✗")
    pct = f"{int(confidence * 100)}% confidence"
    meta = " · ".join(filter(None, [ttp, severity, pct, f"mode {mode}" if mode else ""]))
    card_said = f"Carte à juger : {card[:8]} (console, TO JUDGE)." if card else ""
    # The card and the run before the explanation: a text cut (the webhook's 800 characters, the
    # fallback's: JUG2 review) never loses them.
    text = " ".join(filter(None, [
        f"{action} · {meta}.", card_said, f"Run {run_id}." if run_id else "", explanation[:800],
        f"⚠ {note[:300]}" if note else ""]))
    level = "ok" if verified else ("unknown" if verified is None else "failed")
    # Text from outside (the model's, Azure's names): one line each, no link nor mention
    # of its own (SEC6, N-09 — glorfindel/chat_text.py).
    resource_short = webhook_code(resource_id.split("/")[-1])
    payload = {"text": (
        f":robot_face: *{_ACTION_LABELS.get(action) or webhook_text(action)}* {status}  |  `{resource_short}`\n"
        f"`{webhook_code(action)}` · {webhook_text(meta)}\n"
        f"> {webhook_text(explanation[:800])}\n"
        + (f"> ⚠ {webhook_text(note[:300])}\n" if note else "")
        + (f"> {webhook_text(card_said)}\n" if card_said else "")
        + f"`{webhook_code(run_id)}`"
    )}
    return f"{label} {status}", text, level, payload


def notify_action(
    action: str,
    resource_id: str,
    run_id: str,
    confidence: float,
    explanation: str,
    verified: bool | None,
    ttp: str = "",
    severity: str = "",
    note: str = "",
    key: str = "",
    card: str = "",
    mode: str = "",
) -> str:
    """Announce an autonomous action: in the VM's Discord thread when the bot is configured, else
    by the webhook (GLORFINDEL_WEBHOOK_URL), as before — never both (JUG1, #760: until then it went
    by the webhook, in the channel, even with the bot). `note`: what the action left open (an
    isolation by rules: Azure's DNS / IMDS — S7). `key` (`executed_key`): once per action, after a
    restart too (glorfindel/vm_notices.py); none, every call is said. `card`: the card to judge
    (`EXECUTED_TYPE`), named. Where it went (`bot`, `webhook`, `relayed`, `none`, `already`); a
    notification never stops the agent.

    JUG2 (#765): the bot configured but mute (its heartbeat absent or stale: glorfindel/bot_beat.py),
    the webhook says it in the channel, the role pinged (`relayed`, vm_notices.say) — and at the
    watch's passes after, an announcement the bot has not posted (vm_notices.relay_pass)."""
    import os
    try:
        title, text, level, payload = _action_words(action, resource_id, run_id, confidence, explanation,
                                                    verified, ttp, severity, note, card, mode)
    except Exception:
        return "none"
    from glorfindel import vm_notices
    detail = {"action": action, "verified": verified, "card": card, "mode": mode, "run_id": run_id}
    key = key or f"action:{uuid.uuid4()}"
    try:
        return vm_notices.say(resource_id, key, EXECUTED_TYPE, title, text,
                              level=level, detail=detail, webhook=payload)
    except Exception:
        # The notices' store refused (a full disk): an autonomous action is always said somewhere
        # (JUG1 review). The bot posts only what the stores hold: its card written and the bot
        # alive, the bot says it in the VM's thread; the bot mute, the webhook says it as the
        # fallback does, its ping with it (JUG2); else the webhook says it, as before the store.
        if not os.environ.get("GLORFINDEL_WEBHOOK_URL", ""):
            return "none"
        bot = discord_bot_configured()
        why = vm_notices.relay_reason() if bot else ""
        if bot and card and not why:
            return "none"
        if why:
            sent = vm_notices.relay({"key": key, "resource_id": resource_id, "kind": EXECUTED_TYPE,
                                     "title": title, "text": text, "level": level, "detail": detail}, why)
            return "relayed" if sent else "none"
        vm_notices.post_webhook(payload, key)
        return "webhook"


def discord_bot_configured(environ=None) -> bool:
    """The Discord bot posts the escalations (one thread per VM): the webhook then stays
    silent. A bot needs its token and its channel — a channel alone runs no bot, and an
    escalation always goes somewhere, or the watch says it does not.

    Only the bot's container holds the token (M-3, #183): docker compose tells the watch
    and the War Room that it is set with GLORFINDEL_DISCORD_BOT ("1" or "", from
    ${DISCORD_BOT_TOKEN:+1}), never its value. Outside compose, DISCORD_BOT_TOKEN itself."""
    import os
    env = os.environ if environ is None else environ
    token = env.get("GLORFINDEL_DISCORD_BOT") or env.get("DISCORD_BOT_TOKEN")
    return bool(token and env.get("DISCORD_CHANNEL_ID"))


def alerting_configured(environ=None) -> bool:
    """An escalation reaches someone: the webhook, or the Discord bot."""
    import os
    env = os.environ if environ is None else environ
    return bool(env.get("GLORFINDEL_WEBHOOK_URL") or discord_bot_configured(env))


def _notify(esc: dict) -> None:
    """POST an escalation notification to GLORFINDEL_WEBHOOK_URL if set.

    Skipped when the Discord bot is configured — the bot handles escalations in
    per-VM threads, which is a better UX than a flat channel message.
    """
    import os
    if discord_bot_configured():
        return
    if esc.get("escalation_type") == EXECUTED_TYPE:
        return      # JUG1: the action's announcement says it, once (notify_action) — never twice
    url = os.environ.get("GLORFINDEL_WEBHOOK_URL", "")
    if not url:
        return
    try:
        import requests

        from glorfindel.chat_text import webhook_code, webhook_text
        # The reason carries the model's words and Azure's names (an Entra application's
        # display name): one line, no link nor mention of its own (SEC6, N-09).
        resource_short = webhook_code(esc["resource_id"].split("/")[-1])
        label = _ACTION_LABELS.get(esc["action"]) or webhook_text(esc["action"])
        type_label = _ESCALATION_LABELS.get(
            esc["escalation_type"], esc["escalation_type"]
        )
        parts = [esc.get("ttp", ""), esc.get("severity", ""), type_label]
        meta = webhook_text(" · ".join(filter(None, parts)))
        requests.post(url, json={
            "text": (
                f":rotating_light: *{label}*  |  `{resource_short}`\n"
                f"`{webhook_code(esc['action'])}` · {meta}\n"
                f"> {webhook_text(esc['reason'][:500])}\n"
                f"`{webhook_code(esc['run_id'])}`"
            )
        }, timeout=5)
    except Exception:
        pass  # notification failure must never block the agent


# ── Observation: was a recommendation right? ─────────────────────────────────────
#
# The decision to let Glorfindel act alone rests on a measured number: over weeks of
# human_only, how often would a disruptive action have been wrong. The operator judges
# each card (right / wrong / unsure); the report counts. See docs/observation.md.

VERDICTS = ("right", "wrong", "unsure")
# Recommended actions that disrupt the workload: a wrong one is the false positive the
# autonomy decision weighs.
DISRUPTIVE_ACTIONS = ("isolate_vm", "block_suspicious_ip")
# Cards that are not a decision on a detection: posture, housekeeping, proposals.
_NOT_DECISIONS = {"posture_gap", "orphan_rule", "quarantine_altered", "proposed_rule", "readiness_hold",
                  "ttl_exceeded", "detection_blocked", "bypassed", "state_unreadable", "rule_left",
                  "unverified", "queue_tampered", "queue_unavailable", "drain_pending"}


def all_escalations() -> list[dict]:
    """Every card, resolved ones included, in file order. Unreadable lines are skipped."""
    if not _STORE.exists():
        return []
    out = []
    for line in _STORE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


@_locked
def set_verdict(escalation_id: str, verdict: str, note: str = "") -> dict:
    """Record the operator's judgement of a card — independent of its acknowledgement.

    `escalation_id`: the full id or a unique prefix of at least 6 characters (the War
    Room and `pending` show 8). Raises ValueError on an unknown verdict or an ambiguous
    prefix, KeyError when no card matches. Returns the updated card."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    ref = (escalation_id or "").strip().lower()
    if len(ref) < 6:
        raise ValueError("give the card id, or at least its first 6 characters")
    lines = _STORE.read_text().splitlines() if _STORE.exists() else []
    hits = []
    for i, line in enumerate(lines):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if str(e.get("id", "")).lower().startswith(ref):
            hits.append((i, e))
    exact = [h for h in hits if str(h[1].get("id", "")).lower() == ref]
    hits = exact or hits
    if not hits:
        raise KeyError(f"no card {escalation_id}")
    if len(hits) > 1:
        raise ValueError(f"{escalation_id} matches {len(hits)} cards — give more characters")
    i, e = hits[0]
    e["verdict"] = verdict
    e["verdict_at"] = datetime.now(timezone.utc).isoformat()
    e["verdict_note"] = note
    lines[i] = json.dumps(e, default=str)
    _write_lines(lines)
    return e


def rule_of(e: dict) -> str:
    """The detection rule behind a card: recorded since the observation kit, otherwise
    read from the RulePoller's signal id (`rule-<name>-<8 hex>`)."""
    if e.get("rule_name"):
        return e["rule_name"]
    sid = str(e.get("signal_id") or "")
    if sid.startswith("rule-"):
        parts = sid[len("rule-"):].rsplit("-", 1)
        if len(parts) == 2 and len(parts[1]) == 8:
            return parts[0]
    return ""


def is_decision(e: dict) -> bool:
    """A card that carries a decision on a detection — not posture, housekeeping, a
    proposal, or an alert of the reassertion."""
    sid = str(e.get("signal_id") or "")
    return (e.get("escalation_type") not in _NOT_DECISIONS
            and not sid.startswith(("reassert-", "ttl-", "posture-")))


def _ip_of(e: dict) -> str:
    return str((e.get("action_params") or {}).get("ip") or "").strip()


def _when(e: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(e.get("first_seen") or e.get("timestamp")).replace("Z", "+00:00"))
    except ValueError:
        return None


def recurrence(e: dict, escs: list[dict] | None = None, days: int = 7) -> dict | None:
    """The earlier cards on the same IP in the last `days` days — in observation nothing is
    blocked, so a scanner comes back and opens a new card after each ack (three cards for
    one attacker on bree, 16–17/10). Said on the card, never judged for the operator."""
    ip, me = _ip_of(e), _when(e)
    if not ip or me is None:
        return None
    window = timedelta(days=days)
    prev = [x for x in (all_escalations() if escs is None else escs)
            if x.get("id") != e.get("id") and _ip_of(x) == ip
            and (w := _when(x)) is not None and w < me and me - w <= window]
    if not prev:
        return None
    last = max(prev, key=_when)
    return {"previous": len(prev), "last_id": last.get("id"), "last_seen": last.get("first_seen"),
            "last_verdict": last.get("verdict")}


def to_judge(since: datetime | None = None, limit: int = 100) -> list[dict]:
    """The decision cards still waiting for the operator's verdict, newest first — pending
    or acknowledged (a verdict is independent of the ack): what the War Room's "To judge"
    list shows during an observation. An exercise card stays in the list, flagged
    (``exercise``, ``exercise_run``) — H-1: a window is a claim from the injectors' host, and
    whoever can write one could otherwise hide a real attack from the operator. The
    observation report still counts it apart (``observation_report``)."""
    out = []
    escs = all_escalations()
    for e in escs:
        if not is_decision(e) or e.get("verdict") in VERDICTS:
            continue
        when = e.get("first_seen") or e.get("timestamp") or ""
        if since is not None:
            try:
                if datetime.fromisoformat(str(when).replace("Z", "+00:00")) < since:
                    continue
            except ValueError:
                continue
        card = {k: e.get(k) for k in (
            "id", "action", "escalation_type", "resource_id", "ttp", "severity", "confidence",
            "reason", "explanation", "action_params", "first_seen", "last_seen", "occurrences",
            "status", "rule_name", "target",
            # JUG1: what the console opens a line on — the card's steps, and what an action taken
            # alone did and how it was checked.
            "suggested_steps", "executed", "run_id", "signal_id")}
        card["exercise"] = e.get("source") == "exercise"
        card["exercise_run"] = (e.get("exercise_run") or "") if card["exercise"] else ""
        card["recurrence"] = recurrence(e, escs)
        out.append(card)
    out.sort(key=lambda c: str(c.get("first_seen") or ""), reverse=True)
    return out[:limit]


_NO_ACTION_LABELLED = frozenset({"account_compromised", "compromise_unchecked"})


def observation_report(since: datetime | None = None) -> dict:
    """Counts of the operator's verdicts on decision cards since `since` (all if None).
    A card counts once, however many times it re-fired (its `occurrences`). An exercise
    card (B2: an injector's window covered the VM) is left out — counted in `exercises`."""
    def bucket() -> dict:
        return {"right": 0, "wrong": 0, "unsure": 0, "unjudged": 0}

    by_action: dict[str, dict] = {}
    by_rule: dict[str, dict] = {}
    disruptive = bucket()
    cards = 0
    exercises = 0
    block_ips: list[str] = []
    for e in all_escalations():
        if not is_decision(e):
            continue
        when = e.get("first_seen") or e.get("timestamp") or ""
        if since is not None:
            try:
                if datetime.fromisoformat(str(when).replace("Z", "+00:00")) < since:
                    continue
            except ValueError:
                continue
        if e.get("source") == "exercise":
            exercises += 1
            continue
        cards += 1
        v = e.get("verdict") if e.get("verdict") in VERDICTS else "unjudged"
        # A card that recommends no action is named by its type when it has a label (COR1).
        key = e.get("action") or (_ESCALATION_LABELS.get(e.get("escalation_type") or "")
                                  if e.get("escalation_type") in _NO_ACTION_LABELLED else "") or "?"
        by_action.setdefault(key, bucket())[v] += 1
        by_rule.setdefault(rule_of(e) or "(sans règle)", bucket())[v] += 1
        if e.get("action") in DISRUPTIVE_ACTIONS:
            disruptive[v] += 1
        if e.get("action") == "block_suspicious_ip" and _ip_of(e):
            block_ips.append(_ip_of(e))
    judged = disruptive["right"] + disruptive["wrong"]
    return {
        "since": since.isoformat() if since else None,
        "cards": cards,
        "exercises": exercises,
        # A returning scanner opens a card per visit: how many attackers behind the blocks.
        "blocks": {"cards": len(block_ips), "distinct_ips": len(set(block_ips))},
        "judged": sum(b["right"] + b["wrong"] + b["unsure"] for b in by_action.values()),
        "by_action": by_action,
        "by_rule": by_rule,
        "disruptive": {**disruptive, "false_rate": (disruptive["wrong"] / judged) if judged else None},
    }

