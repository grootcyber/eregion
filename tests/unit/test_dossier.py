"""DOS3 (#1043; `docs/design/dossier-isolation.md` §3.1, §3.5 to §3.7, §4.1, §4.5, §4.6, §12): the dossier of
an isolation, step 0 — its local facts, its file, its scope and its retention (the ceiling of Q9 replaced
by the reads' budget, DOS4).

One test a fact and a state (`glorfindel/dossier_local.py`), the scope of Q2, the file (0600, never
through a link), the ceiling of Q9, the retention of Q7; and the dossier apart: never in the signal, the
memory nor the message to the model (frozen to the byte, as DOS2 froze it: `test_cycle_line.py`), no gate
importing it. Mutants M6980–M6983 and M7075–M7077 (`scripts/mutants/DOS3.py`). No call reaches Azure nor a
model.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from glorfindel import agent, cycle_line, dossier, dossier_local, escalations
from glorfindel.config import AutonomyConfig
from tests.unit.test_cycle_line import MESSAGE_SHA256, PAST, USER_SHA256, _bree, _cycle, _llm
from tests.unit.test_cycle_line import hermetic  # noqa: F401 — its autouse fixture, here too
from tests.unit.test_dependency_failures import FakeMemory

ROOT = Path(__file__).resolve().parents[2]
VM = "/subscriptions/s/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/vm-dos3"
RULE = "ransomware-disk-write"
T = "2026-11-10T02:35:56+00:00"
NOW = datetime(2026, 11, 10, 2, 40, tzinfo=timezone.utc).timestamp()


def _signal(**raw) -> dict:
    return {"signal_id": "rule-ransomware-disk-write-0000dos3", "event": "detection", "ttp": "T1486",
            "severity": "high", "resource_id": VM, "resource_type": "vm", "timestamp": "2026-11-10T02:36:10+00:00",
            "context": {"workspace_id": "ws-dos3", "rule_name": RULE, "attribution": "asset",
                        "run_id": "watch-ransomware-disk-write-20261110T023610Z"},
            "raw_signal": {"first_result_row": {"Computer": "vm-dos3", "_ResourceId": VM, "MaxWrite": 65900000,
                                                "TimeGenerated": T}, **raw}}


def _isolated(**kw) -> dict:
    """A cycle whose isolation ran and was verified — the drain cut the sessions."""
    state = {"signal": _signal(), "dry_run": False, "action": "isolate_vm", "escalate": False, "confidence": 0.8,
             "autonomy_mode": "non_disruptive", "escalation_reason": "",
             "outcome": {"status": "isolated", "executed": True, "verified": True, "method": "nsg",
                         "verified_at": "2026-11-10T02:37:00+00:00", "drain": {"status": "drained"}}}
    state.update(kw)
    return state


def _proposed(**kw) -> dict:
    """A card that proposes the isolation, held by the mode."""
    state = {"signal": _signal(), "dry_run": False, "action": "isolate_vm", "escalate": True, "mode_hold": True,
             "confidence": 0.8, "autonomy_mode": "human_only", "escalation_reason": "Mode human_only",
             "outcome": {"status": "escalated", "executed": False, "action_pending": "isolate_vm"}}
    state.update(kw)
    return state


def _compose(state, data_plane=True, source="real", run="", now=NOW) -> dict | None:
    name = dossier.at_cycle_end(state, data_plane, source, run, now=now)
    return json.loads((dossier.DOSSIER_DIR / name).read_text()) if name else None


def _facts(state, **kw) -> dict:
    doc = _compose(state, **kw)
    assert doc and doc["compose"] is True
    return {f["code"]: f for f in doc["faits"]}


def _card(**kw) -> dict:
    card = {"id": hashlib.sha256(json.dumps(kw, sort_keys=True).encode()).hexdigest()[:32], "resource_id": VM,
            "rule_name": RULE, "ttp": "T1486", "signal_id": "rule-ransomware-disk-write-0000past",
            "escalation_type": "mode_hold", "status": "resolved", "first_seen": "2026-11-08T02:35:00+00:00"}
    card.update(kw)
    return card


def _store(*cards, raw: tuple[str, ...] = ()) -> None:
    escalations._STORE.parent.mkdir(parents=True, exist_ok=True)
    escalations._STORE.write_text("\n".join([json.dumps(c) for c in cards] + list(raw)) + "\n")


# ── La forme d'un fait (§3.1) ─────────────────────────────────────────────────────────────────────

def test_a_fact_says_its_source_its_author_its_reading_and_its_state():
    f = dossier.fact("F5c", "verification", etat=dossier.LU, dit="vérifiée", source="l'issue", lecture="outcome",
                     lu_a="2026-11-10T02:40:00+00:00")
    assert set(f) == {"code", "id", "etat", "dit", "valeurs", "source", "lecture", "auteur", "lu_a", "mesure"}
    assert f["auteur"] == "glorfindel" and f["mesure"] == "local"


def test_an_unreadable_fact_always_says_why_and_an_unknown_state_is_refused():
    f = dossier.fact("F3c", "past_cards", etat=dossier.ILLISIBLE, dit="?", source="s", lecture="l", lu_a="")
    assert f["pourquoi"] == "raison non dite"
    with pytest.raises(ValueError):
        dossier.fact("F3c", "past_cards", etat="rien", dit="?", source="s", lecture="l", lu_a="")


def test_the_states_are_the_five_of_the_design():
    assert dossier.ETATS == ("lu", "vide", "sans_objet", "illisible", "en_attente")


# ── F3c : les cartes passées ─────────────────────────────────────────────────────────────────────

def test_past_cards_of_the_vm_and_the_rule_with_their_verdicts():
    _store(_card(verdict="benign"), _card(verdict="benign", first_seen="2026-11-09T02:35:00+00:00"),
           _card(status="pending", first_seen="2026-11-07T02:35:00+00:00"),
           _card(first_seen="2026-10-30T02:35:00+00:00"),                      # 11 days before T: out
           _card(first_seen="2026-11-10T02:39:00+00:00"),                      # after T: F5d, not F3c
           _card(rule_name="ssh-brute-force", signal_id="rule-ssh-brute-force-00000000"),
           _card(resource_id=VM.replace("vm-dos3", "vm-other")))
    f = _facts(_isolated())["F3c"]
    assert f["etat"] == "lu" and f["valeurs"]["cartes"] == 3
    assert f["valeurs"]["par_verdict"] == {"benign": 2, "sans verdict": 1} and f["valeurs"]["en_attente"] == 1
    assert f["valeurs"]["jours"] == 10 and f["valeurs"]["jusqu_a"] == T
    assert f["valeurs"]["dernieres"][0]["first_seen"] == "2026-11-09T02:35:00+00:00"


def test_no_past_card_is_empty_only_when_the_store_answered_whole():
    _store(_card(resource_id=VM.replace("vm-dos3", "vm-other")))
    assert _facts(_isolated())["F3c"]["etat"] == "vide"
    assert _facts(_isolated(signal={**_signal(), "signal_id": "rule-x-00000002"}))["F3c"]["etat"] == "vide"


def test_a_store_that_cannot_be_read_is_unreadable_never_empty():
    """M6980: an unreadable store written « no card »."""
    escalations._STORE.parent.mkdir(parents=True, exist_ok=True)
    escalations._STORE.mkdir()                     # read_bytes on a directory: an OSError
    f = _facts(_isolated())["F3c"]
    assert f["etat"] == "illisible" and "magasin des cartes" in f["pourquoi"]


def test_lines_that_are_not_cards_make_none_unreadable_and_some_at_least():
    _store(raw=("{not a card",))
    f = _facts(_isolated())["F3c"]
    assert f["etat"] == "illisible" and f["valeurs"]["lignes_illisibles"] == 1
    _store(_card(), raw=("{not a card",))
    f = _facts(_isolated(signal={**_signal(), "signal_id": "rule-x-00000003"}))["F3c"]
    assert f["etat"] == "lu" and "au moins" in f["dit"]


def test_a_card_whose_time_has_no_zone_is_counted_never_placed():
    _store(_card(first_seen="2026-11-09T02:35:00"))
    f = _facts(_isolated())["F3c"]
    assert f["etat"] == "illisible" and f["valeurs"]["non_datees"] == 1


def test_a_signal_without_a_time_leaves_the_window_unanchored():
    signal = _signal()
    signal["raw_signal"]["first_result_row"].pop("TimeGenerated")
    signal["timestamp"] = "pas une heure"
    f = _facts(_isolated(signal=signal))["F3c"]
    assert f["etat"] == "illisible" and "ne s'ancre pas" in f["pourquoi"]


def test_t_is_the_row_s_time_else_the_signal_s():
    assert dossier.signal_time(_signal()) == (T, "ligne")
    signal = _signal()
    signal["raw_signal"]["first_result_row"].pop("TimeGenerated")          # an aggregated row
    assert dossier.signal_time(signal) == ("2026-11-10T02:36:10+00:00", "signal")


# ── F4c : ce que le modèle a vu des connexions ───────────────────────────────────────────────────

def test_the_login_lines_the_model_saw_each_state():
    rows = [{"TimeGenerated": "2026-11-10T02:30:00Z", "SyslogMessage": "Accepted password for root from 203.0.113.9"}]
    seen = _facts(_isolated(signal=_signal(investigative_context={"successful_auth_from_ip": rows})))["F4c"]
    assert seen["etat"] == "lu" and seen["valeurs"]["lignes"] == 1 and "forgeable" in seen["dit"]
    empty = _facts(_isolated(signal={**_signal(investigative_context={"successful_auth_from_ip": []}),
                                     "signal_id": "rule-x-00000004"}))["F4c"]
    assert empty["etat"] == "vide"
    gap = _facts(_isolated(signal={**_signal(investigative_context={"successful_auth_from_ip": []}),
                                   "signal_id": "rule-x-00000005"}, telemetry_gaps=["successful_auth_from_ip"]))
    assert gap["F4c"]["etat"] == "illisible"
    none = _facts(_isolated(signal={**_signal(), "signal_id": "rule-x-00000006"}))["F4c"]
    assert none["etat"] == "sans_objet" and "aucune requête" in none["dit"]       # no workspace, nothing run
    other = _facts(_isolated(signal={**_signal(investigative_context={"heartbeat_gap": []}),
                                     "signal_id": "rule-x-0000000c"}))["F4c"]
    assert other["etat"] == "sans_objet" and "pas un brute force" in other["dit"]


# ── F5b, F5c : la coupure et la vérification ─────────────────────────────────────────────────────

def _iso_state(**kw) -> None:
    from glorfindel.response import state as st
    st._save_isolation_state(VM, {"resource_id": VM, "isolated_at": "2026-11-10T02:36:20+00:00", **kw})


def test_a_drain_followed_by_drn1_is_pending_with_when_it_was_asked():
    _iso_state(drains_at=["2026-11-10T02:36:22+00:00"], drain={"status": "pending", "waited_s": 300})
    f = _facts(_isolated(outcome={**_isolated()["outcome"], "drain": {"status": "pending"}}))["F5b"]
    assert f["etat"] == "en_attente" and f["valeurs"]["demandee_a"] == "2026-11-10T02:36:22+00:00"


def test_a_drain_ended_says_how_long_it_took():
    _iso_state(drains_at=["2026-11-10T02:36:22+00:00"], drain={"status": "drained"},
               drain_ended_at="2026-11-10T02:43:36+00:00")
    f = _facts(_isolated())["F5b"]
    assert f["etat"] == "lu" and f["valeurs"]["duree_s"] == 434 and "434 s" in f["dit"]


def test_a_drain_refused_says_so():
    f = _facts(_isolated(outcome={**_isolated()["outcome"], "drain": {"status": "failed", "refused": True,
                                                                         "error": "Run Command refusé"}}))["F5b"]
    assert f["etat"] == "lu" and f["valeurs"]["cas"] == "refused"


def test_an_isolation_state_that_cannot_be_read_leaves_the_drain_unreadable():
    from glorfindel.response import state as st
    st._ISOLATION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    (st._ISOLATION_STATE_DIR / f"vm-dos3--{st._rid_hash(VM)}.json").write_text("{cut")
    f = _facts(_isolated())["F5b"]
    assert f["etat"] == "illisible" and "illisible" in f["pourquoi"]


def test_no_drain_said_anywhere_is_unreadable_never_cut():
    out = dict(_isolated()["outcome"])
    out.pop("drain")
    assert _facts(_isolated(outcome=out))["F5b"]["etat"] == "illisible"


def test_the_verification_each_verdict():
    assert _facts(_isolated())["F5c"]["etat"] == "lu"
    failed = _isolated(signal={**_signal(), "signal_id": "rule-x-00000007"},
                       outcome={**_isolated()["outcome"], "verified": False, "error": "une carte ouverte"})
    f = _facts(failed)["F5c"]
    assert f["etat"] == "lu" and "une carte ouverte" in f["dit"]
    unsure = _isolated(signal={**_signal(), "signal_id": "rule-x-00000008"},
                       outcome={**_isolated()["outcome"], "verified": None, "error": "liste illisible"})
    f = _facts(unsure)["F5c"]
    assert f["etat"] == "illisible" and f["pourquoi"] == "liste illisible"


def test_a_proposal_has_no_drain_nor_verification():
    facts = _facts(_proposed())
    assert facts["F5b"]["etat"] == facts["F5c"]["etat"] == "sans_objet"


# ── F6 : la décision telle qu'elle a été prise ───────────────────────────────────────────────────

def test_the_rule_its_fingerprint_and_the_row():
    f = _facts(_isolated())["F6a"]
    assert f["etat"] == "lu" and f["valeurs"]["ligne"]["MaxWrite"] == "65900000"
    assert f["valeurs"]["empreinte"]["name"] == RULE and "non lus" in f["dit"]


def test_a_rule_whose_fingerprint_cannot_be_read_is_unreadable(monkeypatch):
    monkeypatch.setattr(cycle_line, "rule_fingerprint",
                        lambda _s: {"name": RULE, "query_sha256": "", "unreadable": "règles illisibles"})
    f = _facts(_isolated())["F6a"]
    assert f["etat"] == "illisible" and "règles illisibles" in f["pourquoi"]


def test_a_threshold_that_cannot_be_read_leaves_the_gates_unreadable(monkeypatch):
    monkeypatch.setenv("GLORFINDEL_CONFIDENCE_THRESHOLD", "beaucoup")
    f = _facts(_proposed())["F6b"]
    assert f["etat"] == "illisible" and "seuil" in f["pourquoi"] and f["valeurs"]["seuil"] is None


def test_a_detection_without_its_row_is_unreadable():
    signal = _signal()
    signal["raw_signal"].pop("first_result_row")
    assert _facts(_isolated(signal=signal))["F6a"]["etat"] == "illisible"


def test_the_gates_the_mode_the_threshold_and_what_held():
    f = _facts(_proposed(held_by="confidence"))["F6b"]
    assert f["valeurs"]["mode"] == "human_only" and f["valeurs"]["seuil"] == 0.7
    assert f["valeurs"]["retenue_par"] == "confidence" and "retenue par confidence" in f["dit"]


def test_the_draws_and_the_model_and_its_sampling():
    draws = [{"action": "isolate_vm", "confidence": 0.8, "escalate": False}] * 3
    facts = _facts(_isolated(decision_draws=draws, decision_model="anthropic/claude-sonnet-5-5",
                             decision_temperature=None))
    assert facts["F6c"]["etat"] == "lu" and facts["F6c"]["valeurs"]["tirages"][0]["confidence"] == 0.8
    assert facts["F6d"]["valeurs"]["modele"] == "anthropic/claude-sonnet-5-5"
    assert facts["F6e"]["valeurs"]["premier"]["sampling"] == "provider_default"
    assert facts["F6e"]["valeurs"]["confirmation"]["sampling"] == "provider_default"


def test_no_draw_is_empty_and_no_model_is_without_object():
    facts = _facts(_isolated())
    assert facts["F6c"]["etat"] == "vide"
    assert facts["F6d"]["etat"] == facts["F6e"]["etat"] == "sans_objet"


def test_a_version_that_cannot_be_read_is_unreadable(monkeypatch):
    monkeypatch.setattr(cycle_line, "glorfindel_version",
                        lambda: {"ref": "", "revision": "", "package": "", "unreadable": "no git"})
    f = _facts(_isolated())["F6f"]
    assert f["etat"] == "illisible" and f["pourquoi"] == "no git"


def _inputs(**kw) -> dict:
    ctx = {"top_write_processes": [], "backup_agent_check": [], "heartbeat_gap": []}
    return _isolated(signal=_signal(investigative_context=ctx), **kw)


def test_the_process_counter_under_linux_is_without_object_never_empty():
    """The drain ran `ss`: Linux — the Process counter cannot say anything there (§1.3)."""
    f = _facts(_inputs())["F6g"]
    by = {i["requete"]: i for i in f["valeurs"]["requetes"]}
    assert f["valeurs"]["systeme"] == "linux" and f["etat"] == "lu"
    assert by["top_write_processes"]["etat"] == by["backup_agent_check"]["etat"] == "sans_objet"
    assert by["heartbeat_gap"]["etat"] == "vide"


def test_the_process_counter_on_an_unknown_system_is_without_object_as_the_catalogue_says_never_empty():
    """DOS4: one rule for the enquiry and the dossier (`catalog.says`) — the system unknown, a read that
    depends on it is sans objet, never empty; step 1 reads the system in the VM's model."""
    from glorfindel.enquiry import catalog
    out = dict(_isolated()["outcome"])
    out["drain"] = {"status": "failed", "error": "VM introuvable"}
    f = _facts(_inputs(outcome=out))["F6g"]
    by = {i["requete"]: i for i in f["valeurs"]["requetes"]}
    assert f["valeurs"]["systeme"] == "inconnu"
    assert by["backup_agent_check"] == {"requete": "backup_agent_check", "lignes": 0, "etat": "sans_objet",
                                        "pourquoi": catalog.UNKNOWN_SYSTEM}
    assert by["heartbeat_gap"]["etat"] == "vide"


def test_the_process_counter_under_windows_may_be_empty():
    out = dict(_isolated()["outcome"])
    out["drain"] = {"status": "unsupported", "note": "Windows"}
    f = _facts(_inputs(outcome=out))["F6g"]
    assert f["valeurs"]["systeme"] == "windows" and f["etat"] == "lu"
    assert {i["etat"] for i in f["valeurs"]["requetes"]} == {"vide"}


def test_a_failed_query_is_unreadable():
    f = _facts(_inputs(telemetry_gaps=["heartbeat_gap"]))["F6g"]
    assert f["etat"] == "illisible" and f["pourquoi"].startswith("heartbeat_gap : en échec")


def test_the_source_real_exercise_or_unreadable():
    assert _facts(_isolated(), source="exercise", run="run-1")["F6h"]["dit"] == "exercice (run-1)"
    assert _facts(_isolated(signal={**_signal(), "signal_id": "rule-x-00000009"}),
                  source="unknown")["F6h"]["etat"] == "illisible"


def test_a_fact_that_breaks_is_unreadable_never_the_dossier_lost(monkeypatch):
    def broken(*_a):
        raise RuntimeError("cassé")
    monkeypatch.setattr(dossier_local, "_drain", broken)
    facts = _facts(_isolated())
    assert facts["F5b"]["etat"] == "illisible" and facts["F5b"]["pourquoi"] == "cassé"
    assert {"F3c", "F4c", "F5c", "F6a", "F6h"} <= set(facts)


def test_every_fact_of_step_0_is_there_in_its_order():
    codes = [f["code"] for f in _compose(_isolated())["faits"]]
    assert codes == ["F3c", "F4c", "F5b", "F5c", "F6a", "F6b", "F6c", "F6d", "F6e", "F6f", "F6g", "F6h"]


# ── Le périmètre (Q2) ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("state, kind", [
    (_isolated(), "isolation"),
    (_isolated(escalate=True, outcome={**_isolated()["outcome"], "verified": False}), "isolation"),
    (_proposed(), "proposition"),
    (_proposed(action="block_suspicious_ip"), "proposition"),
    (_isolated(action="snapshot", floor_card=True), "proposition"),                       # B3a's card
    (_isolated(action="snapshot", ceiling_card=True, ceiling={"proposed": "isolate_vm"}), "proposition"),
])
def test_in_scope(state, kind):
    assert dossier.scope(state, True)[0] == kind
    assert _compose(state)["perimetre"] == kind


@pytest.mark.parametrize("state", [
    _isolated(dry_run=True),
    _isolated(action="snapshot"),                                          # a snapshot alone
    _isolated(action="block_suspicious_ip"),                               # a block executed: not an isolation
    _isolated(action="release_isolation"),
    _isolated(outcome={"status": "no_op", "executed": True}),
    _proposed(action="snapshot"),
    _isolated(action="snapshot", ceiling_card=True, ceiling={"proposed": "block_suspicious_ip"}),
])
def test_out_of_scope(state):
    assert dossier.at_cycle_end(state, True, "real", "", now=NOW) == ""
    assert not dossier.DOSSIER_DIR.exists() or not list(dossier.DOSSIER_DIR.glob("*.json"))


def test_a_cycle_of_the_control_plane_or_an_identity_has_none():
    """M6982: a cycle out of scope composed — decided by the code, its facts already on its card."""
    assert dossier.at_cycle_end(_isolated(), False, "real", "", now=NOW) == ""
    assert dossier.at_cycle_end(_proposed(), False, "real", "", now=NOW) == ""
    assert not dossier.DOSSIER_DIR.exists() or not list(dossier.DOSSIER_DIR.glob("*.json"))


def test_an_exercise_has_its_dossier_marked_exercise():
    doc = _compose(_isolated(), source="exercise", run="run-7")
    assert doc["source"] == "exercise" and doc["exercise_run"] == "run-7"


# ── Le fichier (§4.1) ─────────────────────────────────────────────────────────────────────────────

def test_one_file_per_cycle_named_by_the_vm_and_the_signal_owner_only():
    a = dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW)
    b = dossier.at_cycle_end(_isolated(signal={**_signal(), "signal_id": "rule-x-0000000a"}), True, "real", "", now=NOW)
    h8 = hashlib.sha256(VM.lower().encode()).hexdigest()[:8]
    assert a != b and a.startswith(f"vm-dos3-{h8}-") and a.endswith(".json") and len(a.split("-")[-1]) == 13
    path = dossier.DOSSIER_DIR / a
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and stat.S_IMODE(dossier.DOSSIER_DIR.stat().st_mode) == 0o700
    doc = dossier.load(VM, _signal()["signal_id"])
    assert doc["resource_id"] == VM and doc["etape"] == 0 and doc["pour_information"] is True
    assert doc["T"] == T and doc["T_lu_dans"] == "ligne"


def test_the_file_is_never_written_through_a_link(tmp_path):
    """M6983: the file written through a link in its place — what it points to rewritten."""
    outside = tmp_path / "outside.txt"
    outside.write_text("à moi")
    dossier.DOSSIER_DIR.mkdir(parents=True, mode=0o700)
    path = dossier.file_for(VM, _signal()["signal_id"])
    path.symlink_to(outside)
    assert dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW) == path.name
    assert outside.read_text() == "à moi"
    assert not path.is_symlink() and json.loads(path.read_text())["resource_id"] == VM


def test_a_directory_that_is_a_link_is_never_written(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    dossier.DOSSIER_DIR.parent.mkdir(parents=True, exist_ok=True)
    dossier.DOSSIER_DIR.symlink_to(elsewhere, target_is_directory=True)
    assert dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW) == ""
    assert not list(elsewhere.iterdir())


# ── Pas de plafond à l'étape 0 (DOS4, décision du 24/11) ─────────────────────────────────────────

def _nth(i: int, now=NOW) -> dict:
    return _compose(_isolated(signal={**_signal(), "signal_id": f"rule-x-{i:08d}"}), now=now)


def test_no_ceiling_at_step_0_it_reads_nothing(monkeypatch):
    """DOS4: the fixed ceiling of Q9 (6 an hour) is replaced by the reads' budget — step 0 reads nothing,
    every dossier of a burst is composed; the variable that set the ceiling sets nothing any more."""
    monkeypatch.setenv("GLORFINDEL_DOSSIER_MAX_PER_H", "0")
    docs = [_nth(i, NOW + i) for i in range(12)]
    assert all(d["compose"] is True and d["faits"] for d in docs)
    assert not hasattr(dossier, "max_per_h") and not hasattr(dossier, "MAX_PER_H")


def test_the_facts_are_read_outside_the_lock(monkeypatch):
    """The cycles of the VMs never wait behind one another's reads: under the lock, the write only."""
    seen = []
    real = dossier_local.local_facts

    def facts(*a):
        seen.append(dossier._LOCK.locked())
        return real(*a)
    monkeypatch.setattr(dossier_local, "local_facts", facts)
    assert _compose(_isolated())["compose"] is True and seen == [False]


def test_a_dossier_says_its_reads_to_come_or_why_none():
    """DOS4: a dossier of a VM waits for its reads of Azure (`a_faire`); one of a detection attributed to
    no VM says, among its facts, that none will be made (the decision of 23/11)."""
    assert _nth(0)["lectures"] == {"etat": "a_faire"}
    loose = _signal()
    loose["context"] = {**loose["context"], "attribution": "unattributed"}
    doc = _compose(_isolated(signal=loose))
    assert doc["lectures"] == {"etat": "sans_lecture", "pourquoi": "pas de lecture d'Azure, aucune VM attribuée"}
    said = {f["code"]: f for f in doc["faits"]}["F1"]
    assert said["etat"] == "sans_objet" and said["dit"] == "pas de lecture d'Azure, aucune VM attribuée"


# ── La rétention (Q7) ─────────────────────────────────────────────────────────────────────────────

DAY = 86400


def _held(isolated_at="2026-11-10T02:36:20+00:00") -> None:
    _iso_state(isolated_at=isolated_at, placements=[])


def test_a_dossier_is_kept_while_its_vm_is_held_and_30_days_after_the_lift():
    from glorfindel.response import state as st
    _held()
    name = dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW)
    path = dossier.DOSSIER_DIR / name
    assert dossier.retention_pass(now=NOW + 40 * DAY) == 0 and not json.loads(path.read_text())["leve_vu_a"]
    st._clear_isolation_state(VM)                                   # lifted
    assert dossier.retention_pass(now=NOW + 41 * DAY) == 0
    assert json.loads(path.read_text())["leve_vu_a"]
    assert dossier.retention_pass(now=NOW + 70 * DAY) == 0 and path.exists()
    assert dossier.retention_pass(now=NOW + 71.1 * DAY) == 1 and not path.exists()


def test_a_vm_held_again_by_this_isolation_stops_the_clock():
    from glorfindel.response import state as st
    _held()
    name = dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW)
    st._clear_isolation_state(VM)
    dossier.retention_pass(now=NOW + DAY)
    _held()                                                          # the same isolation's state back
    dossier.retention_pass(now=NOW + 2 * DAY)
    assert json.loads((dossier.DOSSIER_DIR / name).read_text())["leve_vu_a"] == ""


def test_a_vm_isolated_again_while_isolated_keeps_this_dossier():
    """M7075: isolating an isolated VM again rewrites its `isolated_at`, with no lift
    (providers/azure/isolation.py) — the first dossier must not start its clock, nor go 30 days later
    while the VM is still in quarantine."""
    _held()
    name = dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW)
    _held("2026-11-12T00:00:00+00:00")                               # isolated again, never lifted
    dossier.retention_pass(now=NOW + 3 * DAY)
    assert json.loads((dossier.DOSSIER_DIR / name).read_text())["leve_vu_a"] == ""
    assert dossier.retention_pass(now=NOW + 40 * DAY) == 0 and (dossier.DOSSIER_DIR / name).exists()


def test_a_directory_named_like_a_dossier_never_stops_the_retention():
    from glorfindel.response import state as st
    _held()
    name = dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW)
    (dossier.DOSSIER_DIR / "a-directory.json").mkdir()
    st._clear_isolation_state(VM)
    dossier.retention_pass(now=NOW + DAY)
    assert dossier.retention_pass(now=NOW + 32 * DAY) == 1 and not (dossier.DOSSIER_DIR / name).exists()
    assert (dossier.DOSSIER_DIR / "a-directory.json").is_dir()


def test_a_directory_open_to_others_is_put_back_to_its_owner():
    dossier.DOSSIER_DIR.mkdir(parents=True)
    os.chmod(dossier.DOSSIER_DIR, 0o755)
    assert dossier.at_cycle_end(_isolated(), True, "real", "", now=NOW)
    assert stat.S_IMODE(dossier.DOSSIER_DIR.stat().st_mode) == 0o700


def test_a_proposal_counts_from_its_first_pass_unless_its_isolation_was_approved():
    name = dossier.at_cycle_end(_proposed(), True, "real", "", now=NOW)
    dossier.retention_pass(now=NOW + 60)
    assert json.loads((dossier.DOSSIER_DIR / name).read_text())["leve_vu_a"]
    other = dossier.at_cycle_end(_proposed(signal={**_signal(), "signal_id": "rule-x-0000000b"}), True, "real", "",
                                 now=NOW)
    _held("2026-11-10T03:00:00+00:00")                                # approved by a human, after T
    dossier.retention_pass(now=NOW + 120)
    assert json.loads((dossier.DOSSIER_DIR / other).read_text())["leve_vu_a"] == ""


def test_nothing_is_done_while_an_isolation_state_cannot_be_read():
    from glorfindel.response import state as st
    name = dossier.at_cycle_end(_proposed(), True, "real", "", now=NOW)
    st._ISOLATION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    (st._ISOLATION_STATE_DIR / "vm-other--00000000.json").write_text("{cut")
    assert dossier.retention_pass(now=NOW + 90 * DAY) == 0
    assert json.loads((dossier.DOSSIER_DIR / name).read_text())["leve_vu_a"] == ""


def test_an_unreadable_file_goes_past_its_time_and_a_link_at_once(tmp_path):
    dossier.DOSSIER_DIR.mkdir(parents=True, mode=0o700)
    bad = dossier.DOSSIER_DIR / "bad.json"
    bad.write_text("{cut")
    target = tmp_path / "kept.json"
    target.write_text("{}")
    (dossier.DOSSIER_DIR / "link.json").symlink_to(target)
    assert dossier.retention_pass(now=bad.stat().st_mtime + 10 * DAY) == 1 and bad.exists()
    assert target.exists()
    assert dossier.retention_pass(now=bad.stat().st_mtime + 31 * DAY) == 1 and not bad.exists()


def test_the_watch_s_housekeeping_runs_the_retention_once_an_hour(monkeypatch):
    from glorfindel.watch.housekeeping import Housekeeping
    hk = Housekeeping.__new__(Housekeeping)
    hk._last_dossier_retention, calls = 0.0, []
    monkeypatch.setattr(dossier, "retention_pass", lambda: calls.append(1) or 0)
    hk._dossier_retention()
    hk._dossier_retention()
    assert calls == [1]


# ── Le dossier à l'écart : ni le signal, ni la mémoire, ni le modèle, ni une garde ───────────────

def test_the_dossier_never_enters_the_signal():
    """M6981: the dossier in the signal — the signal reaches the model (`_build_user_message`)."""
    state = _isolated(signal=_bree())
    before = copy.deepcopy(state)
    assert dossier.at_cycle_end(state, True, "real", "", now=NOW)
    assert state == before
    assert hashlib.sha256(agent._build_user_message(state["signal"], PAST).encode()).hexdigest() == USER_SHA256


def test_a_cycle_with_its_dossier_leaves_the_message_to_the_model_unchanged_to_the_byte():
    """store_cycle composes the dossier; the message the model is then sent, from the same signal, is
    the one origin/main sent before DOS2 and DOS3 (`test_cycle_line.py`)."""
    state = {**_isolated(signal=_bree()), "past_cycles": PAST, "incident": None, "telemetry_gaps": [],
             "reasoning": "Écritures soutenues.", "explanation": ""}
    mem = FakeMemory()
    with patch("glorfindel.escalations.notify_action"):
        out = agent.store_cycle(state, memory=mem)
    assert list(dossier.DOSSIER_DIR.glob("*.json"))
    seen: list[dict] = []

    def completion(**kw):
        seen.append(kw)
        return _llm("snapshot")
    with patch("litellm.completion", side_effect=completion):
        agent.decide({"signal": out["signal"], "past_cycles": PAST, "incident": None, "dry_run": True,
                      "telemetry_gaps": []}, model="anthropic/claude-test",
                     autonomy=AutonomyConfig(default="human_only"))
    blob = json.dumps({"messages": seen[0]["messages"], "tools": seen[0]["tools"]}, sort_keys=True,
                      ensure_ascii=False)
    assert hashlib.sha256(blob.encode()).hexdigest() == MESSAGE_SHA256
    assert "dossier" not in json.dumps(mem.stored[0]) and "dossier" not in json.dumps(out["signal"])


def test_the_debug_line_names_the_dossier_s_file_never_its_content():
    final, line, _ = _cycle()
    name = line["dossier"]
    assert (dossier.DOSSIER_DIR / name).is_file() and "faits" not in line and "faits" not in json.dumps(final["signal"])
    doc = json.loads((dossier.DOSSIER_DIR / name).read_text())
    assert doc["perimetre"] == "proposition" and doc["compose"] is True
    facts = {f["code"]: f for f in doc["faits"]}
    assert facts["F6d"]["valeurs"]["modele"] == "anthropic/claude-test"
    # The Process counter, the system unknown with no call: sans objet, as the catalogue says (DOS4).
    assert facts["F6g"]["etat"] == "lu"
    assert {i["etat"] for i in facts["F6g"]["valeurs"]["requetes"] if i["requete"] != "heartbeat_gap"} <= {
        "sans_objet", "lu"}


def _plane_state(plane: str) -> dict:
    """A cycle of the control plane (an AzureActivity line) or of an identity (an Entra line) that
    proposes an isolation — in scope but for its plane."""
    run = f"watch-{plane}-20261110T023610Z"
    row = ({"OperationNameValue": "MICROSOFT.COMPUTE/VIRTUALMACHINES/RUNCOMMAND/ACTION", "Type": "AzureActivity",
            "CorrelationId": "c0ffee00-0000-0000-0000-000000000001", "_ResourceId": VM}
           if plane == "control" else
           {"EntraOperation": "Add member to role", "Type": "AuditLogs", "EventId": "e-1",
            "InitiatedBy": "someone", "TargetResources": "[]"})
    signal = {**_signal(), "signal_id": f"rule-{plane}-00000001",
              "context": {"rule_name": f"{plane}-rule", "run_id": run, "plane": plane, "attribution": "asset"},
              "raw_signal": {"first_result_row": row}}
    return {**_proposed(signal=signal), "past_cycles": [], "incident": None, "reasoning": "r", "explanation": ""}


@pytest.mark.parametrize("plane", ["control", "identity"])
def test_store_cycle_of_the_control_plane_or_an_identity_writes_no_dossier(plane):
    """M7076: store_cycle saying every cycle of the data plane — a cycle decided by the code would get
    a dossier, its facts already on its card (§4.6)."""
    agent.store_cycle(_plane_state(plane), memory=FakeMemory())
    assert not dossier.DOSSIER_DIR.exists() or not list(dossier.DOSSIER_DIR.glob("*.json"))
    line = json.loads((Path("runs") / "glorfindel" / f"watch-{plane}-20261110T023610Z_debug.jsonl")
                      .read_text().splitlines()[-1])
    assert "dossier" not in line


def test_a_dry_run_cycle_has_no_dossier_and_its_line_names_none():
    state = {**_isolated(signal=_bree(), dry_run=True), "past_cycles": PAST, "incident": None,
             "reasoning": "r", "explanation": ""}
    agent.store_cycle(state, memory=FakeMemory())
    line = json.loads((Path("runs") / "glorfindel" /
                       "watch-ransomware-disk-write-20261110T021400Z_debug.jsonl").read_text().splitlines()[-1])
    assert "dossier" not in line


# The only places that import the dossier: store_cycle (step 0), the watch's housekeeping (the
# retention, and the `dossier` thread of DOS4), the dossier itself. No gate of `decide`, no lift, nothing
# the model reads.
ALLOWED = {("glorfindel/agent.py", "store_cycle"), ("glorfindel/watch/housekeeping.py", "_dossier_retention"),
           ("glorfindel/dossier.py", "at_cycle_end"), ("glorfindel/dossier_local.py", "<module>"),
           ("glorfindel/watch/housekeeping.py", "_dossier_reads"), ("glorfindel/watch/housekeeping.py", "_dossier_run"),
           ("glorfindel/dossier_platform.py", "<module>"), ("glorfindel/dossier_pass.py", "<module>"),
           ("glorfindel/dossier_pass.py", "_drain_now")}
MODULES = ("glorfindel.dossier", "glorfindel.dossier_local", "glorfindel.dossier_platform", "glorfindel.dossier_pass")


def _importers() -> set[tuple[str, str]]:
    found = set()
    for pkg in ("glorfindel", "eregion_core", "eregion_console", "analysis"):
        for path in sorted((ROOT / pkg).rglob("*.py")) if (ROOT / pkg).is_dir() else []:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            owners = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(node):
                        owners.setdefault(id(child), node.name)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    names = [mod] + [f"{mod}.{a.name}" for a in node.names]
                if any(n in MODULES for n in names):
                    found.add((path.relative_to(ROOT).as_posix(), owners.get(id(node), "<module>")))
    return found


def test_no_gate_imports_the_dossier():
    assert _importers() == ALLOWED


def test_the_dossier_s_modules_read_no_cloud_and_call_no_model():
    """DOS4: the dossier's reads of Azure live in the provider's adapter only (providers/azure/
    dossier_reads.py); the thread and its facts are handed a connector, never import one."""
    for name in ("dossier.py", "dossier_local.py", "dossier_platform.py", "dossier_pass.py"):
        text = (ROOT / "glorfindel" / name).read_text(encoding="utf-8")
        assert not any(w in text for w in ("azure.", "litellm", "providers.azure", "detector_for", "run_query"))


def test_the_tests_write_the_dossier_under_their_own_home():
    """HY1: the conftest redirects the dossiers' directory, never ~/.glorfindel/dossier."""
    assert dossier.DOSSIER_DIR.name == "dossier" and dossier.DOSSIER_DIR.parent.name == "glorfindel-home"


def test_days_are_dated_from_t():
    """The window of F3c ends at T, never at the read (§3.1): a card one minute before T counts."""
    _store(_card(first_seen=(datetime.fromisoformat(T) - timedelta(minutes=1)).isoformat()))
    assert _facts(_isolated())["F3c"]["valeurs"]["cartes"] == 1
