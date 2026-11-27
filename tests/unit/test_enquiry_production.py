"""ENQ5b (#1284; `docs/design/enquete-raisonnee.md` §5, §6, §7, §9.4, §9.6, §9.7): the enquiry in production,
behind `GLORFINDEL_ENQUIRY` (glorfindel/enquiry/interrupteur.py).

- **`fixed`, the default**: the message `_build_user_message()` writes, `_SYSTEM_PROMPT`, `_DECISION_TOOL` and
  `few_shot_examples.yaml` are origin/main's, to the byte (their sha256, Linux and Windows signals, MEM2
  off), and a cycle loads nothing of the loop. Any other value is refused at the start, said.
- **`loop`**: `investigate` runs the loop on what the watch knows (the registry's VM, the discovery's
  system, the configuration's vault, the memory per object); `decide` reads the enquiry with its seven
  states, cites hypotheses the code checks; the telemetry guard counts the code's reads failed, refused or,
  obligatory, waiting — never a `sans_objet`, a `non_permise`, a read not served; the floor V-11 extended
  proposes the isolation on a grave technique whatever the model cites, and never runs it; the gate
  reserves the enquiry's turns; the memory per object is read for its own object only.
- `heartbeat_gap`, corrected for the loop: its window written, its end bounded by what the table delivered.

No call to Azure nor to a model: the reads, the model and the store are replaced. Mutants M8266–M8285
(scripts/mutants/ENQ5b.py) are measured here.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from glorfindel import agent, read_budget
from glorfindel.config import AutonomyConfig
from glorfindel.decision_queue import DecisionGate, calls_made
from glorfindel.enquiry import catalog, decision, interrupteur, knowledge, lecteur, memoire, production
from glorfindel.enquiry import reference as ref_

ROOT = Path(__file__).resolve().parents[2]
SUB = "00000000-0000-0000-0000-0000000000aa"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/vm-linux-01"
VAULT = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.RecoveryServices/vaults/vault-01"
WIN = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/vm-win-01"
AT = datetime(2026, 11, 10, 2, 34, 10, tzinfo=timezone.utc)
LATER = AT + timedelta(minutes=10)
RULE = "ransomware-disk-write"
M1 = AT.replace(second=0) - timedelta(minutes=1)

# ── origin/main, measured (78a37099): what `fixed` keeps to the byte ─────────────────────────────────
PROMPT_SHA256 = "36b767e85ac8ac327e2b630055787536f70d37c2d631421f7734c8ec1d24fb86"
TOOL_SHA256 = "ab777dd14385c56f971dc96c39c47d32649c23fc6e8802bb03ba9e2078c39150"
FEW_SHOT_SHA256 = "58c6c68b7d6f5eab1e669b9953ed7527afd5ada3320de839e7605379f8b56443"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _signal(rid=VM, ttp="T1486", rule=RULE, row=None, **ctx):
    row = row or {"Computer": "vm-linux-01", "_ResourceId": rid, "MaxWrite": 147000000, "TimeGenerated": AT.isoformat()}
    return {"signal_id": f"sig-{ttp}-{rule}", "event": "detection", "resource_id": rid, "ttp": ttp,
            "severity": "high", "timestamp": AT.isoformat(),
            "context": {"run_id": f"watch-{rule}-1", "rule_name": rule, **ctx},
            "raw_signal": {"log_analytics_workspace_id": "ws-test", "first_result_row": dict(row)}}


def _state(signal=None, **extra):
    return {"signal": signal or _signal(), "past_cycles": [], "incident": None, "dry_run": False,
            "reasoning": "", "confidence": 0.0, "action": "", "reversible": True, "explanation": "",
            "escalate": False, "escalation_reason": "", "outcome": None, "telemetry_gaps": [], **extra}


def _minute(debut, moyenne, pic=None, n=6):
    return {"Minute": debut.isoformat(), "InstanceName": "/", "Echantillons": n, "MoyenneMBs": moyenne,
            "MaxMBs": moyenne * 1.5, "PremierPic": pic.isoformat() if pic else None, "PasS": 10}


class Lecteur:
    """The reads replaced: each id's answer (rows, `catalog.Lu`, `catalog.Reading`, None), each call noted."""

    def __init__(self, rows=None):
        self.rows, self.calls = rows or {}, []

    def __call__(self, read, valeurs):
        self.calls.append((read.id, dict(valeurs)))
        if read.id in catalog.INGESTION_DITE and read.id not in self.rows:
            return catalog.Lu([], AT + timedelta(hours=1), True)
        return self.rows.get(read.id, [])


ATTAQUE = {"perf_minute_series": catalog.Lu([_minute(M1, 59.4, pic=M1 + timedelta(seconds=10)),
                                             _minute(M1 + timedelta(minutes=1), 61.0)], AT + timedelta(minutes=4), True),
           "vault_jobs": [], "vault_activity": []}


class Modele:
    """The model of the enquiry replaced: its answers in order, then `conclure`; its calls counted."""

    def __init__(self, *answers, raises=None):
        self.answers, self.appels, self.refusee, self.raises = list(answers), 0, "", raises

    def __call__(self, prompt, texte, outil, timeout):
        self.appels += 1
        if self.raises is not None:
            self.refusee = str(self.raises)
            raise self.raises
        return self.answers.pop(0) if self.answers else {"geste": "conclure"}


def _enquete(state=None, *, rows=None, modele=None, systeme="linux", coffre=VAULT, now=LATER):
    return production.enqueter(state or _state(), "ws-test", model="m-test", lecteur=Lecteur(rows or ATTAQUE),
                               modele=modele or Modele(), systeme=systeme, coffre=coffre, maintenant=lambda: now)


def _response(action="snapshot", escalate=False, confidence=0.9, hypotheses=None):
    args = {"reasoning": "r", "confidence": confidence, "action": action, "reversible": True, "explanation": "e",
            "escalate": escalate, "escalation_reason": "x" if escalate else "", "suggested_steps": []}
    if hypotheses is not None:
        args["hypotheses"] = hypotheses
    call = MagicMock()
    call.function.arguments = json.dumps(args)
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(tool_calls=[call]))]
    return resp


def _decide(state, response, mode="human_only", calls=None):
    def completion(**kw):
        if calls is not None:
            calls.append(kw)
        return response
    with patch("litellm.completion", side_effect=completion):
        return agent.decide(state, model="m-test", autonomy=AutonomyConfig(default=mode))


# ── 1. The switch ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, mode", [(None, "fixed"), ("", "fixed"), ("  ", "fixed"), ("fixed", "fixed"),
                                       (" loop\n", "loop"), ("loop", "loop")])
def test_the_switch_reads_fixed_by_default_or_loop(raw, mode):
    assert interrupteur.mode({} if raw is None else {interrupteur.SWITCH: raw}) == mode


@pytest.mark.parametrize("raw", ["LOOP", "boucle", "on", "1", "fixed,loop", "loop\x00"])
def test_any_other_value_is_refused_and_said(raw):
    with pytest.raises(interrupteur.Refuse) as exc:
        interrupteur.mode({interrupteur.SWITCH: raw})
    assert interrupteur.SWITCH in str(exc.value) and "fixed" in str(exc.value) and "loop" in str(exc.value)


@pytest.mark.parametrize("name, raw", [("GLORFINDEL_ENQUIRY_N", "0"), ("GLORFINDEL_ENQUIRY_N", "9"),
                                       ("GLORFINDEL_ENQUIRY_N", "quatre"), ("GLORFINDEL_ENQUIRY_T_S", "4"),
                                       ("GLORFINDEL_ENQUIRY_T_S", "nan"), ("GLORFINDEL_ENQUIRY_T_S", "121")])
def test_t_and_n_outside_their_bounds_are_refused(name, raw):
    with pytest.raises(interrupteur.Refuse):
        interrupteur.verifier({interrupteur.SWITCH: "loop", name: raw})


def test_t_and_n_default_to_the_decisions_of_24_11():
    assert (interrupteur.n({}), interrupteur.t({})) == (4, 30.0)
    assert (interrupteur.n({"GLORFINDEL_ENQUIRY_N": "6"}), interrupteur.t({"GLORFINDEL_ENQUIRY_T_S": "45"})) == (6, 45.0)


def test_the_watch_does_not_start_on_a_switch_it_cannot_read(monkeypatch):
    monkeypatch.setenv(interrupteur.SWITCH, "lop")
    console = MagicMock()
    with pytest.raises(SystemExit) as exc:
        interrupteur.refuser(console)
    assert exc.value.code == 2 and "refusé" in console.print.call_args[0][0]
    with pytest.raises(interrupteur.Refuse):
        agent.GlorfindelAgent(dry_run=True, memory_path=None)


def test_the_start_says_the_loop_and_nothing_in_fixed(monkeypatch):
    console = MagicMock()
    interrupteur.refuser(console)
    assert not console.print.called
    monkeypatch.setenv(interrupteur.SWITCH, "loop")
    interrupteur.refuser(console)
    assert "loop" in console.print.call_args[0][0] and "30 s" in console.print.call_args[0][0]


# ── 2. `fixed`: nothing changes, to the byte ─────────────────────────────────────────────────────

def test_fixed_keeps_the_prompt_the_tool_and_the_examples_of_origin_main():
    assert _sha(agent._SYSTEM_PROMPT) == PROMPT_SHA256
    assert _sha(json.dumps(agent._DECISION_TOOL, sort_keys=True, ensure_ascii=False)) == TOOL_SHA256
    assert hashlib.sha256((ROOT / "glorfindel/few_shot_examples.yaml").read_bytes()).hexdigest() == FEW_SHOT_SHA256


# The message `_build_user_message()` writes on a fixed signal, Linux and Windows, MEM2 off — the function is
# origin/main's (78a37099), untouched by ENQ5b, so its sha256 here is origin/main's.
FIXED_MESSAGES = {
    "linux": (_signal(), "dde1083e231e1cca085a23498d50a63556393ec39be8d808b98b4731ffacbfbb"),
    "windows": (_signal(rid=WIN, row={"Computer": "vm-win-01", "_ResourceId": WIN, "DiskWrite": 88.0,
                                      "TimeGenerated": AT.isoformat()}),
                "30e0535e014f7787612db460251b1fcdfcee6aeed2911bdc215806ca16fd989a"),
}


@pytest.mark.parametrize("case", list(FIXED_MESSAGES))
def test_fixed_sends_origin_mains_message_prompt_and_tool_to_the_byte(case):
    """M8266, M8277: the switch ignored, or `fixed` changed — the model sees what it saw on origin/main."""
    signal, frozen = FIXED_MESSAGES[case]
    calls: list = []
    out = _decide(_state(signal), _response("snapshot"), calls=calls)
    sent = calls[0]
    assert sent["messages"][0]["content"][0]["text"] == agent._SYSTEM_PROMPT
    assert sent["tools"] == [agent._DECISION_TOOL]
    assert _sha(sent["messages"][1]["content"]) == frozen
    assert "enquete" not in out and "hypotheses" not in json.dumps(sent["tools"])


def test_fixed_runs_todays_enquiry_never_the_loop(monkeypatch):
    """M8266: the switch ignored — `investigate` ran the loop under `fixed`."""
    monkeypatch.setattr(production, "enqueter", MagicMock(side_effect=AssertionError("the loop in fixed")))
    from glorfindel.enquiry import fixed
    monkeypatch.setattr(fixed, "run_query", lambda ws, q: [])
    out = agent.investigate(_state())
    assert "enquete" not in out and out["signal"]["raw_signal"]["investigative_context"]


def test_a_cycle_in_fixed_loads_no_module_of_the_loop(tmp_path):
    """A cycle in `fixed`, through the switch: `investigate` not in dry run, with a workspace (the relecture of
    ENQ5b: in dry run, without one, it returned before the switch), today's reads served empty; then `decide`."""
    code = ("import sys, json\n"
            "from unittest.mock import MagicMock, patch\n"
            "from glorfindel import agent\n"
            "from glorfindel.enquiry import fixed\n"
            "from glorfindel.config import AutonomyConfig\n"
            "call = MagicMock(); call.function.arguments = json.dumps({'action': 'snapshot', 'confidence': 0.9})\n"
            "resp = MagicMock(); resp.choices = [MagicMock(message=MagicMock(tool_calls=[call]))]\n"
            f"s = {{'signal': json.loads({json.dumps(json.dumps(_signal()))}), 'past_cycles': [], 'incident': None,\n"
            "     'dry_run': False}\n"
            "with patch.object(fixed, 'run_query', return_value=[]) as rq, patch('litellm.completion', return_value=resp):\n"
            "    out = agent.investigate(s)\n"
            "    assert rq.called and 'investigative_context' in out['signal']['raw_signal'], 'the switch never reached'\n"
            "    agent.decide({**out, 'dry_run': True}, model='m', autonomy=AutonomyConfig(default='human_only'))\n"
            "lab = [m for m in sys.modules if m.startswith('glorfindel.enquiry.') and m.split('.')[-1] in\n"
            "       ('loop', 'production', 'decision', 'memoire', 'lecteur', 'predicats', 'message', 'reference')]\n"
            "print(sorted(lab))")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GLORFINDEL_ENQUIRY")}
    env["HOME"] = str(tmp_path)                               # nothing of the operator's ~/.glorfindel read or written
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120, env=env)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "[]"


# ── 3. `loop`: the enquiry in the watch ───────────────────────────────────────────────────────────

def test_the_switch_on_loop_runs_the_enquiry_in_investigate(monkeypatch):
    """M8266: the switch ignored — `loop` asked, today's enquiry ran."""
    monkeypatch.setenv(interrupteur.SWITCH, "loop")
    seen = {}

    def enqueter(state, ws, *, model, connector=None):
        seen.update(ws=ws, model=model)
        return {**state, "enquete": {"lectures": []}}
    monkeypatch.setattr(production, "enqueter", enqueter)
    out = agent.investigate(_state(), model="m-pinned")
    assert out["enquete"] == {"lectures": []} and seen == {"ws": "ws-test", "model": "m-pinned"}


def test_the_enquiry_reads_the_sheets_obligatory_reads_on_the_registrys_vm(monkeypatch):
    lu = Lecteur(ATTAQUE)
    out = production.enqueter(_state(), "ws", model="m", lecteur=lu, modele=Modele(), systeme="linux", coffre=VAULT,
                              maintenant=lambda: LATER)
    asked = {rid for rid, _ in lu.calls}
    assert {"perf_minute_series", "vault_jobs", "vault_activity"} <= asked
    assert all(v.get("vm") == VM for _, v in lu.calls) and all(v.get("vault") == VAULT for r, v in lu.calls if "vault" in r)
    e = out["enquete"]
    assert e["fiche"] == "T1486" and e["regle"] == RULE and e["appels"] == 1
    assert e["verdicts_code"]["T1486-H1"] == "confirme"
    assert out["telemetry_gaps"] == [] and "perf_minute_series" in out["signal"]["raw_signal"]["investigative_context"]
    assert "process_write_audit" not in asked and "process_write_io" not in asked      # WRT1, PIO1: to measure


def test_wrt1_stays_to_measure_neither_investigate_nor_decide_runs_it():
    assert "process_write_audit" in catalog.A_MESURER and "process_write_audit" not in catalog.READS
    lu = Lecteur(ATTAQUE)
    production.enqueter(_state(), "ws", model="m", lecteur=lu,
                        modele=Modele({"geste": "lire", "id": "process_write_audit"}), systeme="linux", coffre=VAULT,
                        maintenant=lambda: LATER)
    assert "process_write_audit" not in {rid for rid, _ in lu.calls}


def test_the_vms_system_comes_from_the_discovery_never_from_the_line(tmp_path, monkeypatch):
    from glorfindel import discovery
    reg = discovery.AssetRegistry(path=tmp_path / "assets.json")
    reg.update([discovery.DiscoveredAsset("vm-linux-01", VM, "law", AT.isoformat(), os="linux"),
                discovery.DiscoveredAsset("vm-win-01", WIN, "law", AT.isoformat())])
    monkeypatch.setattr(discovery, "_registry", reg)
    assert production.systeme_de(VM.upper()) == "linux" and production.systeme_de(WIN) == ""
    assert production.systeme_de("") == ""


def test_the_discovery_reads_each_vms_system_once_in_its_model(tmp_path):
    from glorfindel import discovery
    reader = MagicMock(side_effect=lambda rid: "Linux" if "linux" in rid else "plan9")
    svc = discovery.DiscoveryService(MagicMock(monitoring_backends=[]), discovery.AssetRegistry(path=tmp_path / "a.json"),
                                     os_reader=reader)
    found = svc._with_os([discovery.DiscoveredAsset("vm-linux-01", VM, "law", "t"),
                          discovery.DiscoveredAsset("vm-win-01", WIN, "law", "t")])
    assert [a.os for a in found] == ["linux", ""]
    svc._registry.update(found)
    again = svc._with_os([discovery.DiscoveredAsset("vm-linux-01", VM, "law", "t")])
    assert again[0].os == "linux" and reader.call_count == 2          # carried over, never read again
    assert discovery.DiscoveryService(MagicMock(monitoring_backends=[]), svc._registry)._with_os(found) is found


def test_the_vault_is_the_configurations_in_the_vms_subscription(monkeypatch):
    monkeypatch.setattr(agent, "_backup_vault_target", lambda: ("vault-01", ""))
    assert production.coffre_de(VM) == VAULT
    monkeypatch.setattr(agent, "_backup_vault_target", lambda: ("", ""))
    assert production.coffre_de(VM) == ""


# ── 4. The gaps: the seven states, `servie` before the state (§7.2, §9.6) ──────────────────────────

def _lecture(rid, etat, **kw):
    return {"id": rid, "etat": etat, "servie": True, "d_office": True, "obligatoire": True, **kw}


def test_a_sans_objet_read_is_never_a_gap():
    """M8267: a `sans_objet` counted as a gap — a ransomware under Linux never contained alone again."""
    assert decision.trous({"lectures": [_lecture("top_write_processes", catalog.SANS_OBJET)]}) == []


def test_a_non_permise_read_is_never_a_gap():
    """M8268: a `non_permise` counted as a gap — a line makes the model ask an unknown id to hold the action."""
    assert decision.trous({"lectures": [_lecture("lire_le_coffre", catalog.NON_PERMISE, d_office=False,
                                                 obligatoire=False)]}) == []


def test_an_obligatory_read_still_waiting_is_a_gap():
    """M8269: an obligatory read `en_attente` not counted — the absence pushes toward the action."""
    assert decision.trous({"lectures": [_lecture("perf_minute_series", catalog.EN_ATTENTE)]}) == ["perf_minute_series"]
    assert decision.trous({"lectures": [_lecture("heartbeat_gap", catalog.EN_ATTENTE, obligatoire=False)]}) == []


def test_a_read_not_served_and_a_read_the_model_asked_are_never_gaps():
    assert decision.trous({"lectures": [_lecture("host_disk_metric", catalog.SANS_OBJET, servie=False),
                                        _lecture("vault_jobs", catalog.ECHEC, servie=False),
                                        _lecture("heartbeat_gap", catalog.ECHEC, d_office=False, obligatoire=False)]}) == []
    assert decision.trous({"lectures": [_lecture("vault_jobs", catalog.REFUSEE)]}) == ["vault_jobs"]


def test_the_enquirys_gaps_hold_a_disruptive_action_each_said_with_its_state():
    state = _enquete(rows={**ATTAQUE, "vault_jobs": None})
    assert state["telemetry_gaps"] == ["vault_jobs"]
    out = _decide(state, _response("isolate_vm", confidence=0.95), mode="full_auto")
    assert out["escalate"] and out["held_by"] == "telemetry"
    assert "vault_jobs (echec)" in out["escalation_reason"] and "lues comme vides" not in out["escalation_reason"]


def test_the_words_of_todays_guard_are_bound():
    """The two sentences `dire_trous` rewrites are `_apply_telemetry_guard`'s, to the letter."""
    held, added = decision._mots_d_aujourd_hui(1, "vault_jobs", "isolate_vm")
    d = {"action": "isolate_vm", "escalate": False, "escalation_reason": ""}
    agent._apply_telemetry_guard(d, ["vault_jobs"])
    assert d["escalation_reason"] == held
    d = {"action": "isolate_vm", "escalate": True, "escalation_reason": "x"}
    agent._apply_telemetry_guard(d, ["vault_jobs"])
    assert d["escalation_reason"] == f"x — {added}"


def test_a_vault_read_the_arm_budget_refuses_is_refused_and_a_gap(monkeypatch):
    monkeypatch.setattr(read_budget.ARM, "take", lambda n, who="": False)
    arm = MagicMock()
    read = lecteur.Lecteur(AT, kql=lambda q, s: [], arm=arm, now=lambda: LATER, compter=True)
    lu = read(catalog.READS["vault_jobs"], {"vm": VM, "vault": VAULT})
    assert isinstance(lu, catalog.Reading) and lu.etat == catalog.REFUSEE and not arm.enquiry_reads.called
    state = production.enqueter(_state(), "ws", model="m", lecteur=read, modele=Modele(), systeme="linux",
                                coffre=VAULT, maintenant=lambda: LATER)
    assert {"vault_jobs", "vault_activity"} <= set(state["telemetry_gaps"])


def test_each_kql_query_is_noted_on_log_analytics_never_refused(monkeypatch):
    noted = []
    monkeypatch.setattr(read_budget, "note_detection", lambda n=1: noted.append(n))
    monkeypatch.setattr(read_budget.LOG_ANALYTICS, "take", MagicMock(side_effect=AssertionError("never asked")))
    read = lecteur.Lecteur(AT, kql=lambda q, s: [{"GapMin": 14}], now=lambda: LATER, compter=True)
    assert read(catalog.READS["heartbeat_gap"], {"vm": VM}) == [{"GapMin": 14}] and noted == [1]
    assert lecteur.Lecteur(AT, kql=lambda q, s: [], now=lambda: LATER)(catalog.READS["heartbeat_gap"], {"vm": VM}) == []
    assert noted == [1]                                       # the harness and the capture count nothing


def test_the_arm_calls_past_the_first_are_counted_once_made(monkeypatch):
    spent = []
    monkeypatch.setattr(read_budget.ARM, "take", lambda n, who="": True)
    monkeypatch.setattr(read_budget.ARM, "spend", lambda n=1, who="": spent.append((n, who)))
    arm = MagicMock()
    arm.enquiry_reads.return_value = ({"vault_activity": catalog.Reading("vault_activity", catalog.VIDE)}, 3)
    lecteur.Lecteur(AT, arm=arm, now=lambda: LATER, compter=True)(catalog.READS["vault_activity"], {"vm": VM, "vault": VAULT})
    assert spent == [(2, read_budget.ENQUETE)]


# ── 5. `heartbeat_gap`, corrected for the loop (§9.7) ─────────────────────────────────────────────

def test_the_loops_heartbeat_gap_writes_its_window_and_never_closes_it_at_t_bare():
    """M8278: the end of `heartbeat_gap` at T bare — beats 25 min late read as an agent cut."""
    q = lecteur.texte(catalog.READS["heartbeat_gap"], {"vm": VM}, AT, LATER)
    assert "ago(" not in q and "let debut = datetime(2026-11-10T00:34:10Z);" in q
    assert "let fin = datetime(2026-11-10T02:34:10Z);" in q
    assert "let tenue = min_of(fin, now() - coalesce(retard, 45s));" in q
    assert "| union (print TimeGenerated = tenue)" in q and "print TimeGenerated = fin" not in q
    assert "ingestion_time()" in q and "prev(TimeGenerated, 1, debut)" in q and "{" not in q
    assert q.count(f"_ResourceId =~ \"{VM}\"") == 1 or q.count("_ResourceId =~ ") == 1
    assert "ago(2h)" in catalog.READS["heartbeat_gap"].query      # investigate's own text, to the byte


# ── 6. `decide` with the enquiry: its message, its tool, the citations (§6) ──────────────────────

def test_the_message_carries_the_sheet_the_enquiry_and_the_last_enquiry_in_their_order(tmp_path, monkeypatch):
    ref = ref_.Reference(VM, RULE, AT - timedelta(days=1), (ref_.Trace("perf_minute_series", catalog.LIGNES),),
                         "snapshot", "benin")
    monkeypatch.setattr(memoire, "lire", lambda vm, regle, now: ref)
    state = _enquete()
    calls: list = []
    _decide(state, _response("snapshot"), calls=calls)
    text = calls[0]["messages"][1]["content"]
    order = [text.index(s) for s in ("## Signal reçu", "## La fiche T1486", "## L'enquête de ce cycle",
                                     "## État actuel de la VM", "## La dernière enquête sur cet objet",
                                     "*Aucun cycle passé disponible")]
    assert order == sorted(order)
    assert "verdict du code sur ce cycle : confirme" in text and "état lignes" in text
    assert "investigative_context" not in text.split("## La fiche")[0]          # the rows said once, with their state
    assert "non reçu ici" in text and "technique grave" in text                 # rule 2: never « as usual » here
    assert calls[0]["messages"][0]["content"][0]["text"] == agent._SYSTEM_PROMPT + decision.LOOP_PROMPT
    tool = calls[0]["tools"][0]["function"]["parameters"]
    assert "hypotheses" in tool["properties"] and "hypotheses" not in tool["required"]
    assert tool["required"] == agent._DECISION_TOOL["function"]["parameters"]["required"]


def test_a_read_not_done_is_never_taken_for_a_proof():
    """M8271: a read not done on this cycle accepted as a proof."""
    fiche = knowledge.charger().pour(RULE, "T1486")
    [h] = decision.verifier([{"id": "T1486-H6", "verdict": "confirme", "lectures": ["vault_activity"]}], fiche, {}, {})
    assert h["verdict"] == "inconnu" and h["lectures"] == [] and "aucune lecture faite" in h["ecartees"][0]


def test_a_read_not_served_or_without_a_verdict_proves_nothing():
    fiche = knowledge.charger().pour(RULE, "T1486")
    lus = {"host_disk_metric": catalog.Reading("host_disk_metric", catalog.SANS_OBJET, servie=False),
           "vault_activity": catalog.Reading("vault_activity", catalog.EN_ATTENTE)}
    a, b = decision.verifier([{"id": "T1486-H3", "verdict": "infirme", "lectures": ["host_disk_metric"]},
                              {"id": "T1486-H6", "verdict": "confirme", "lectures": ["vault_activity"]}], fiche, lus, {})
    assert a["verdict"] == b["verdict"] == "inconnu" and "pas encore servie" in a["ecartees"][0]
    ok = decision.verifier([{"id": "T1486-H6", "verdict": "confirme", "lectures": ["vault_activity"]}], fiche,
                           {"vault_activity": catalog.Reading("vault_activity", catalog.VIDE)}, {})
    assert ok[0]["verdict"] == "confirme" and ok[0]["auteur"] == catalog.PLATFORM


def test_the_codes_predicate_wins_over_the_models_verdict():
    """M8270: the model's verdict wins over the predicate."""
    state = _enquete()
    out = _decide(state, _response("snapshot", hypotheses=[{"id": "T1486-H1", "verdict": "infirme",
                                                            "lectures": ["perf_minute_series"]},
                                                           {"id": "T9999-H1", "verdict": "confirme", "lectures": []}]))
    h1, other = out["enquete"]["hypotheses"]
    assert (h1["verdict"], h1["par"], h1["desaccord"], h1["modele"]) == ("confirme", "code", True, "infirme")
    assert other["verdict"] == "inconnu" and "hors de la fiche" in other["ecartees"][0]
    assert out["enquete"]["citees"] is True


def test_a_model_that_cites_nothing_decides_as_today_and_it_is_said():
    out = _decide(_enquete(), _response("snapshot"))
    assert out["enquete"]["hypotheses"] == [] and out["enquete"]["citees"] is False


# ── 7. The floor V-11, extended (§7.3) ────────────────────────────────────────────────────────────

def test_a_grave_technique_not_contained_makes_a_card_that_proposes_the_isolation():
    out = _decide(_enquete(), _response("no_action", escalate=True))
    assert (out["action"], out["escalate"], out["held_by"]) == ("isolate_vm", True, "floor")
    assert "Technique grave (T1486)" in out["floor"] and "n'a cité aucune hypothèse" in out["floor"]
    assert agent._route_after_decide(out) == "escalate_to_human"


def test_the_floor_never_runs_the_isolation_it_proposes():
    """M8273: the floor that executes — a snapshot run alone turned into an autonomous isolation."""
    d = {"action": "snapshot", "escalate": False, "confidence": 0.9, "escalation_reason": "", "explanation": ""}
    floor, ceiling = decision.plancher_grave(d, _signal(rule="other-rule"), _enquete()["enquete"], "", {})
    assert d["action"] == "snapshot" and d["escalate"] is False and floor.startswith("Technique grave")
    out = _decide(_enquete(_state(_signal(rule="other-rule"))), _response("snapshot"), mode="full_auto")
    assert out["action"] == "snapshot" and out["floor_card"] is True and out["uncontained"] == ""


def test_the_trigger_never_reads_the_citations():
    """M8272: the trigger read in the citations — a relaxing hypothesis the code confirmed lifts the card."""
    enquete = {**_enquete()["enquete"], "verdicts_code": {"T1486-H1": "infirme", "T1486-H2": "confirme"},
               "hypotheses": [{"id": "T1486-H2", "verdict": "confirme", "modele": "confirme", "par": "code",
                               "lectures": ["perf_minute_series", "vault_jobs"], "auteur": catalog.GUEST_PROVOCABLE}]}
    d = {"action": "no_action", "escalate": True, "confidence": 0.9, "escalation_reason": "x", "explanation": ""}
    floor, _ = decision.plancher_grave(d, _signal(), enquete, "", {})
    assert d["action"] == "isolate_vm" and "T1486-H2 confirmée" in floor and "ne dispensent jamais" in floor


@pytest.mark.parametrize("action", ["isolate_vm", "block_suspicious_ip"])
def test_a_decision_that_contains_needs_no_floor(action):
    d = {"action": action, "escalate": True, "confidence": 0.5, "escalation_reason": "", "explanation": ""}
    assert decision.plancher_grave(d, _signal(), _enquete()["enquete"], "", {}) == ("", {})


def test_the_floor_is_the_attributions_on_a_detection_that_names_no_vm_and_steps_behind_other_cards():
    d = {"action": "no_action", "escalate": True, "confidence": 0.9, "escalation_reason": "", "explanation": ""}
    enquete = _enquete()["enquete"]
    assert decision.plancher_grave(d, _signal(attribution="unattributed"), enquete, "", {}) == ("", {})
    floor, _ = decision.plancher_grave(dict(d), _signal(), enquete, "B3a", {})
    assert floor.startswith("B3a — Technique grave")
    _, ceiling = decision.plancher_grave(dict(d), _signal(), enquete, "", {"proposed": "isolate_vm", "reason": "R"})
    assert ceiling["reason"].startswith("R — Technique grave")
    assert decision.plancher_grave(dict(d), _signal(ttp="T1110.001"), enquete, "", {}) == ("", {})


# ── 8. The gate: the enquiry's turns reserved (§5.1, PRT1, PRT2) ──────────────────────────────────

def test_a_decision_with_an_enquiry_is_admitted_with_the_reserve_of_its_turns(monkeypatch):
    """M8274: a decision with an enquiry admitted without the reserve of its turns."""
    gate, grave, low = DecisionGate(), _signal(), _signal(ttp="T1110.001", rule="ssh-brute-force")
    fixed_grave, fixed_low = gate.reserve(grave, 1), gate.reserve(low, 2)
    monkeypatch.setenv(interrupteur.SWITCH, "loop")
    assert gate.reserve(grave, 1) == min(fixed_grave + 5, gate.per_min - gate.low_per_min) > fixed_grave
    assert gate.reserve(low, 2) == min(fixed_low + 5, gate.low_per_min) > fixed_low
    assert DecisionGate.share(grave) == DecisionGate.share({**grave, "event": "detection_timeout"}) + 5
    assert gate.reserve({**grave, "context": {"plane": "control"}}, 1) == fixed_grave


def test_the_turns_made_are_counted_when_the_decision_ends():
    state = {"decision_model": "m", "decision_draws": [], "enquete": {"appels": 4}}
    assert calls_made(_signal(), state, 9) == 5 and calls_made(_signal(), {**state, "decision_model": ""}, 9) == 4
    assert calls_made(_signal(), {"decision_model": "m", "decision_draws": []}, 9) == 1


def test_a_turn_refused_by_the_breaker_stops_the_enquiry_and_decide_takes_the_codes_path():
    from glorfindel import model_budget
    state = _enquete(modele=Modele(raises=model_budget.Refused("budget du réel épuisé")))
    assert state["enquete"]["refusee"] and state["enquete"]["fin"] == "erreur_modele"
    called = MagicMock()
    with patch("litellm.completion", called):
        out = agent.decide(state, model="m", autonomy=AutonomyConfig(default="human_only"))
    assert not called.called and "PRT2" in out["reasoning"]


# ── 9. The memory per object (§5.5) ───────────────────────────────────────────────────────────────

def _ref(vm=VM, rule=RULE, days=1):
    return ref_.Reference(vm, rule, LATER - timedelta(days=days), (ref_.Trace("perf_minute_series", catalog.VIDE),),
                          "snapshot")


def test_the_memory_of_an_object_is_never_read_for_another(tmp_path):
    """M8275: the memory of an object read for another."""
    memoire.ecrire(_ref(), "sig-1", root=tmp_path)
    assert memoire.lire(VM.upper(), RULE, now=LATER, verdicts=dict, root=tmp_path).regle == RULE
    assert memoire.lire(VM, "ssh-brute-force", now=LATER, verdicts=dict, root=tmp_path) is None
    assert memoire.lire(WIN, RULE, now=LATER, verdicts=dict, root=tmp_path) is None
    forged = tmp_path / f"{memoire.cle(VM, 'ssh-brute-force')}.json"
    forged.write_text((tmp_path / f"{memoire.cle(VM, RULE)}.json").read_text())
    assert memoire.lire(VM, "ssh-brute-force", now=LATER, verdicts=dict, root=tmp_path) is None


def test_the_memory_is_bounded_in_age_and_never_read_through_a_link(tmp_path):
    memoire.ecrire(_ref(days=31), "sig-1", root=tmp_path)
    assert memoire.lire(VM, RULE, now=LATER, verdicts=dict, root=tmp_path) is None
    target = tmp_path / "elsewhere.json"
    memoire.ecrire(_ref(), "sig-1", root=tmp_path / "other")
    target.write_text((tmp_path / "other" / f"{memoire.cle(VM, RULE)}.json").read_text())
    path = tmp_path / f"{memoire.cle(VM, RULE)}.json"
    path.unlink()
    path.symlink_to(target)
    assert memoire.lire(VM, RULE, now=LATER, verdicts=dict, root=tmp_path) is None
    assert oct((tmp_path / "other" / f"{memoire.cle(VM, RULE)}.json").stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("verdict, action, said", [
    ("right", "no_action", "benin"), ("right", "isolate_vm", "malveillant"), ("right", "snapshot", "malveillant"),
    ("wrong", "no_action", "malveillant"), ("wrong", "isolate_vm", ""), ("unsure", "no_action", "")])
def test_the_human_verdict_is_the_cards_read_one_way_only(tmp_path, verdict, action, said):
    memoire.ecrire(_ref(), "sig-1", root=tmp_path)
    got = memoire.lire(VM, RULE, now=LATER, root=tmp_path,
                       verdicts=lambda: {"sig-1": {"verdict": verdict, "at": "", "action": action}})
    assert got.verdict_humain == said


def test_the_watch_writes_the_enquiry_on_its_object_at_the_end_of_the_cycle(tmp_path):
    state = {**_enquete(), "action": "snapshot"}
    path = memoire.retenir(state, root=tmp_path, now=LATER)
    data = json.loads(path.read_text())
    assert data["vm"] == VM and data["regle"] == RULE and data["signal_id"] == state["signal"]["signal_id"]
    assert memoire.retenir({**state, "signal": _signal(attribution="unattributed")}, root=tmp_path) is None


# ── 10. The card says the hypotheses (Console) ────────────────────────────────────────────────────

def test_the_card_says_each_hypothesis_its_state_and_what_settled_it(tmp_path, monkeypatch):
    from glorfindel import escalations
    state = _decide(_enquete(), _response("no_action", escalate=True,
                                          hypotheses=[{"id": "T1486-H1", "verdict": "infirme",
                                                       "lectures": ["perf_minute_series"]}]))
    agent.escalate_to_human(state)
    card = escalations.all_escalations()[-1]["enquete"]
    h1 = next(h for h in card["hypotheses"] if h["id"] == "T1486-H1")
    assert (h1["verdict"], h1["par"], h1["etat"]) == ("confirme", "le code (son prédicat)", "mesuree")
    assert card["fiche"] == "T1486" and card["plancher"].startswith("Technique grave")
    assert {x["id"] for x in card["lectures"]} >= {"perf_minute_series", "vault_jobs", "vault_activity"}


def test_a_card_in_fixed_carries_no_enquiry():
    from glorfindel import escalations
    agent.escalate_to_human({**_state(), "action": "snapshot", "escalate": True, "escalation_reason": "x"})
    assert "enquete" not in escalations.all_escalations()[-1]


def test_the_console_writes_nothing_of_the_enquiry_raw():
    """The card's fields go through `_attr` (tests/unit/test_console_escaping.py reads every page); the file
    is loaded by the page, before the script that calls it."""
    import re
    js = (ROOT / "eregion_console/static/enquiry_card.js").read_text(encoding="utf-8")
    html = (ROOT / "eregion_console/static/glorfindel.html").read_text(encoding="utf-8")
    assert '<script src="/static/enquiry_card.js"></script>' in html
    assert html.index("enquiry_card.js") < html.index("/static/glorfindel.js")
    assert "_enquiryNote(e)" in (ROOT / "eregion_console/static/glorfindel.js").read_text(encoding="utf-8")
    assert not re.search(r"\$\{(h|x|q|g|r)\.[a-z_]+\}", js)          # no field of the card written bare


def test_the_registrys_cache_writes_the_system_only_when_known(tmp_path):
    """The relecture of ENQ5b: a version before it reads the cache by `DiscoveredAsset(**item)` — an `os`
    written empty in `fixed` would lose the whole cache, silently, on a roll-back (H1)."""
    from glorfindel.discovery import AssetRegistry, DiscoveredAsset
    path = tmp_path / "assets.json"
    reg = AssetRegistry(path=path)
    seen = dict(monitoring_backend="azure_monitor", last_seen=datetime.now(timezone.utc).isoformat())
    reg.update([DiscoveredAsset(name="vm-a", resource_id=VM, **seen),
                DiscoveredAsset(name="vm-b", resource_id=VM + "b", os="linux", **seen)])
    stored = {a["name"]: a for a in json.loads(path.read_text())}
    assert "os" not in stored["vm-a"] and stored["vm-b"]["os"] == "linux"
    assert {a.name: a.os for a in AssetRegistry(path=path).all()} == {"vm-a": "", "vm-b": "linux"}
