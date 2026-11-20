"""VP1 (#615; docs/design/drill-banc.md §8.2): a verdict proposed on the exercise card of the detection
the drill of the week expected, confirmed in one click — never a verdict given.

Built on the drill and its expectations as this host's image holds them (``drills/``,
``expectations/``): the experiment and the rule are read from them, never written here. Orodruin's
status of the request, the run's report and the window are written as the watch would have pulled
them. No Azure, no model; the store of cards is the conftest's throwaway one.

The oracle: everything agrees, one proposal; each discord of §8.2 alone, none, its reason said.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from eregion_core import drill as dr
from eregion_core import expectations as ex
from glorfindel import escalations
from glorfindel import proposed_verdict as pv

DRILL = "banc-hebdo"
SUB = "00000000-0000-0000-0000-000000000000"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/vm-one"
OTHER = f"/subscriptions/{SUB}/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/vm-two"
REQ = "r-20261117T190000Z-abc123"
RUN = "20261117T190100Z-ab12"


def _shipped():
    d, sha = dr.loaded(dr.shipped_dir() / f"{DRILL}.yaml", dr.SHIPPED)
    return d, sha, ex.load_file(ex.shipped_dir() / f"{DRILL}.yaml")


DRILL_OBJ, SHA, EXPECTED = _shipped()
EXPERIMENT = DRILL_OBJ.wires[0].experiment
RULE = EXPECTED.wires[0].rule
WITHIN = EXPECTED.wires[0].within_s


class Bench:
    """What reached this host of one occurrence: the run's report, Orodruin's status, the window."""

    def __init__(self, root: Path, now: datetime):
        self.root, self.now = root, now
        self.t0 = now - timedelta(seconds=120)
        self.window = {"run_id": RUN, "injector": "annatar", "kind": "technique",
                       "experiment": f"{EXPERIMENT} its name", "targets": [VM.lower()],
                       "start": (self.t0 - timedelta(seconds=30)).isoformat(),
                       "end": (self.t0 + timedelta(seconds=90)).isoformat(),
                       "expires": (self.t0 + timedelta(hours=1)).isoformat(),
                       "destructive": False, "request": REQ}
        self.report()
        self.status()

    def report(self, **metrics) -> None:
        m = {"run_format": 1, "kind": "technique", "injector": "annatar", "experiment_id": EXPERIMENT,
             "resource_id": VM, "request": REQ, "attack_time": self.t0.isoformat(), "detection": "detected"}
        m.update(metrics)
        path = self.root / "glorfindel" / f"{RUN}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"scenario": "s", "run_id": RUN, "mitre": EXPERIMENT, "result": "PASS",
                                    "metrics": m, "thresholds": {}, "checks": {}}))

    def status(self, *, sha: str = SHA, wires=None, drill: bool = True, request: str = REQ) -> None:
        doc = {"request": request, "state": "finished", "at": self.now.isoformat(), "codes": [],
               "wires": wires if wires is not None else [
                   {"rank": 1, "state": "done", "code": "", "runs": [RUN], "result": "detected"}]}
        if drill:
            doc["drill"] = {"name": DRILL, "sha256": sha, "occurrence": self.t0.replace(second=0).isoformat()}
        path = self.root / "glorfindel" / "orodruin" / "requests" / f"{REQ}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc))

    def refresh(self, **kw) -> int:
        return pv.refresh(self.root, windows=kw.pop("windows", [self.window]), **kw)


@pytest.fixture
def bench(tmp_path):
    return Bench(tmp_path / "runs", datetime.now(timezone.utc))


def card(*, vm=VM, rule=RULE, run=RUN, source="exercise", action="snapshot", kind="low_confidence") -> str:
    return escalations.record(signal_id=f"rule-{rule}-0123abcd", resource_id=vm, action=action,
                              escalation_type=kind, reason="held", rule_name=rule, source=source,
                              exercise_run=run if source == "exercise" else "")


def redate(esc_id: str, when: datetime) -> None:
    lines = escalations._STORE.read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e["id"] == esc_id:
            e["timestamp"] = e["first_seen"] = e["last_seen"] = when.isoformat()
        out.append(json.dumps(e))
    escalations._STORE.write_text("\n".join(out) + "\n")


def the(esc_id: str) -> dict:
    return next(e for e in escalations.all_escalations() if e["id"] == esc_id)


def why(esc_id: str) -> str:
    return (the(esc_id).get(escalations.PROPOSED_WHY) or {}).get("code", "")


# ── The expected card, proposed ─────────────────────────────────────────────────────────────

def test_the_expected_card_carries_a_proposed_verdict_never_a_verdict_given(bench):
    c = card()
    assert bench.refresh() == 1
    e = the(c)
    p = e[escalations.PROPOSED_FIELD]
    assert (p["verdict"], p["on"], p["drill"], p["sha256"], p["request"], p["rank"], p["run"], p["rule"]) == (
        "right", "detection", DRILL, SHA, REQ, 1, RUN, RULE)
    assert 0 <= p["after_s"] <= WITHIN and p["within_s"] == WITHIN
    assert e.get("verdict") is None and escalations.PROPOSED_WHY not in e
    # A proposal made stays: a second pass changes nothing.
    assert bench.refresh() == 0


def test_a_proposed_verdict_is_never_counted_as_given(bench):
    c = card()
    bench.refresh()
    assert the(c).get("verdict") is None and "verdict_at" not in the(c)
    listed = [x for x in escalations.to_judge() if x["id"] == c]
    assert listed and listed[0][escalations.PROPOSED_FIELD]["verdict"] == "right"     # still to judge
    r = escalations.observation_report()
    assert (r["judged"], r["exercises"]) == (0, 1)


def test_one_click_confirms_it_as_the_operators_verdict(bench):
    c = card()
    bench.refresh()
    e = escalations.confirm_proposed(c[:8], note="seen")
    assert (e["verdict"], e["verdict_from"], e["verdict_note"]) == ("right", "proposed", "seen")
    assert c not in {x["id"] for x in escalations.to_judge()}
    with pytest.raises(ValueError, match="judged already"):
        escalations.confirm_proposed(c)


def test_a_refusal_erases_it_and_it_is_never_proposed_again(bench):
    c = card()
    bench.refresh()
    e = escalations.refuse_proposed(c)
    assert escalations.PROPOSED_FIELD not in e and e[escalations.PROPOSED_REFUSED]["verdict"] == "right"
    assert bench.refresh() == 0
    assert escalations.PROPOSED_FIELD not in the(c) and the(c).get("verdict") is None
    with pytest.raises(ValueError, match="no proposed verdict"):
        escalations.confirm_proposed(c)
    with pytest.raises(ValueError, match="no proposed verdict"):
        escalations.refuse_proposed(c)
    assert c in {x["id"] for x in escalations.to_judge()}                  # the operator judges it


def test_a_card_without_a_proposal_cannot_be_confirmed(bench):
    c = card(rule="another-rule")
    bench.refresh()
    with pytest.raises(ValueError, match="no proposed verdict"):
        escalations.confirm_proposed(c)
    assert the(c).get("verdict") is None


# ── No other card carries one, its reason said ──────────────────────────────────────────────

def test_a_real_card_never_carries_one_even_matching_everything(bench):
    c = card(source="real")
    assert bench.refresh() == 0
    e = the(c)
    assert escalations.PROPOSED_FIELD not in e and escalations.PROPOSED_WHY not in e
    # Nor written by hand through the store's writer: held to `proposable` again.
    assert escalations.note_proposals({c: {"proposed": {"verdict": "right"}}}) == 0
    listed = next(x for x in escalations.to_judge() if x["id"] == c)
    assert listed[escalations.PROPOSED_FIELD] is None


def test_a_proposal_forged_on_a_real_card_is_never_shown_nor_confirmed(bench):
    """Another writer of the store (the console, the bot, the CLI) cannot make a real card carry one."""
    c = card(source="real")
    lines = []
    for line in escalations._STORE.read_text().splitlines():
        e = json.loads(line)
        if e["id"] == c:
            e[escalations.PROPOSED_FIELD] = {"verdict": "right"}
        lines.append(json.dumps(e))
    escalations._STORE.write_text("\n".join(lines) + "\n")
    listed = next(x for x in escalations.to_judge() if x["id"] == c)
    assert listed[escalations.PROPOSED_FIELD] is None and listed["exercise"] is False
    with pytest.raises(ValueError, match="no proposed verdict"):
        escalations.confirm_proposed(c)


def test_a_card_judged_already_never_carries_one(bench):
    c = card()
    escalations.set_verdict(c, "wrong")
    assert bench.refresh() == 0 and escalations.PROPOSED_FIELD not in the(c)


def test_another_rule_another_vm(bench):
    a, b = card(rule="another-rule"), card(vm=OTHER, action="isolate_vm", kind="mode_hold")
    bench.refresh()
    assert (why(a), why(b)) == ("rule", "vm")
    assert all(escalations.PROPOSED_FIELD not in the(x) for x in (a, b))
    assert "another VM" in the(b)[escalations.PROPOSED_WHY]["said"]


def test_outside_t0_and_its_delay(bench):
    early, late = card(), card(action="isolate_vm", kind="mode_hold")
    redate(early, bench.t0 - timedelta(seconds=5))
    redate(late, bench.t0 + timedelta(seconds=WITHIN + 5))
    bench.window["end"] = (bench.t0 + timedelta(seconds=WITHIN)).isoformat()
    bench.refresh()
    assert (why(early), why(late)) == ("early", "late")


def test_at_its_delay_exactly_it_is_proposed(bench):
    c = card()
    redate(c, bench.t0 + timedelta(seconds=WITHIN))
    bench.window["end"] = (bench.t0 + timedelta(seconds=WITHIN)).isoformat()
    bench.refresh()
    assert the(c)[escalations.PROPOSED_FIELD]["after_s"] == WITHIN


def test_outside_its_window(bench):
    """In [T0, T0 + within_s] but past the window's end and its grace."""
    c = card()
    bench.window["start"] = (bench.t0 - timedelta(seconds=900)).isoformat()
    bench.window["end"] = (bench.t0 - timedelta(seconds=800)).isoformat()      # its last moment: T0 + 100 s
    redate(c, bench.t0 + timedelta(seconds=min(WITHIN, 300)))
    bench.refresh()
    assert why(c) == "window"


def test_a_second_card_of_the_wire_is_never_proposed(bench):
    first, second = card(), card(action="isolate_vm", kind="mode_hold")
    redate(first, bench.t0 + timedelta(seconds=60))
    redate(second, bench.t0 + timedelta(seconds=90))
    bench.refresh()
    assert escalations.PROPOSED_FIELD in the(first)
    assert why(second) == "second" and escalations.PROPOSED_FIELD not in the(second)


def test_the_first_card_refused_the_second_still_waits_for_the_operator(bench):
    first = card()
    redate(first, bench.t0 + timedelta(seconds=60))
    bench.refresh()
    escalations.refuse_proposed(first)
    second = card(action="isolate_vm", kind="mode_hold")
    bench.refresh()
    assert why(second) == "second"


def test_a_first_card_on_another_vm_takes_the_wire(bench):
    """One card per wire: the first of the wire and the rule — whatever became of it."""
    stray, own = card(vm=OTHER), card(action="isolate_vm", kind="mode_hold")
    redate(stray, bench.t0 + timedelta(seconds=30))
    redate(own, bench.t0 + timedelta(seconds=60))
    bench.refresh()
    assert (why(stray), why(own)) == ("vm", "second")


def test_fingerprints_that_do_not_agree_orodruin_and_imladris_on_two_versions(bench):
    c = card()
    bench.status(sha="0" * 64)
    bench.refresh()
    assert why(c) == "fingerprint"


def test_the_drill_is_this_hosts_copy_never_the_instances(bench, tmp_path, monkeypatch):
    """A drill of the console named as the shipped one (``drill.find`` would take it) whose
    fingerprint the status announces: refused — the image's copy differs (§8.2, line S of §7)."""
    own = tmp_path / "instance-drills"
    own.mkdir()
    body = (dr.shipped_dir() / f"{DRILL}.yaml").read_text().replace(
        "description: \"", "description: \"forged: ", 1)
    (own / f"{DRILL}.yaml").write_text(body)
    monkeypatch.setenv(dr.DRILLS_ENV, str(own))
    forged = dr.fingerprint(body.encode())
    assert forged != SHA
    c = card()
    bench.status(sha=forged)
    bench.refresh()
    assert why(c) == "fingerprint"


def test_the_image_copy_read_from_the_drills_dir_given(bench, tmp_path):
    """The drill and its expectations come from this host's image — here given as directories."""
    drills, expect = tmp_path / "d", tmp_path / "e"
    drills.mkdir()
    expect.mkdir()
    shutil.copy(dr.shipped_dir() / f"{DRILL}.yaml", drills)
    c = card()
    bench.refresh(drills_dir=drills, expectations_dir=expect)
    assert why(c) == "expectations_unread"
    shutil.copy(ex.shipped_dir() / f"{DRILL}.yaml", expect)
    bench.refresh(drills_dir=drills, expectations_dir=expect)
    assert escalations.PROPOSED_FIELD in the(c)


def test_a_request_of_dagorlad_is_no_drill(bench):
    c = card()
    bench.status(drill=False)
    bench.refresh()
    assert why(c) == "not_drill"


@pytest.mark.parametrize("change,code", [
    ({"resource_id": OTHER}, "target"),
    ({"request": "r-20261117T190000Z-ffffff"}, "no_status"),
    ({"request": ""}, "no_request"),
    ({"experiment_id": "T0000.000"}, "experiment"),
    ({"kind": "fault", "injector": "gothmog", "fault_start": "2026-11-17T19:01:00+00:00"}, "not_technique"),
])
def test_the_run_report_must_say_the_wire(bench, change, code):
    c = card()
    bench.report(**change)
    bench.refresh()
    assert why(c) == code


def test_the_window_must_name_the_target_and_the_request(bench):
    c = card()
    bench.refresh(windows=[{**bench.window, "targets": [VM.lower(), OTHER.lower()]}])
    assert why(c) == "target"
    bench.refresh(windows=[{**bench.window, "request": "r-20261117T190000Z-ffffff"}])
    assert why(c) == "link"
    bench.refresh(windows=[])
    assert why(c) == "no_window"


def test_the_run_must_be_one_wire_of_the_status(bench):
    c = card()
    bench.status(wires=[{"rank": 1, "state": "done", "code": "", "runs": ["20261117T190100Z-ffff"], "result": ""}])
    bench.refresh()
    assert why(c) == "not_a_wire"


def test_a_t0_outside_its_window(bench):
    c = card()
    bench.window["start"] = (bench.t0 + timedelta(seconds=10)).isoformat()
    bench.refresh()
    assert why(c) == "t0"


def test_two_targets_armed_each_wire_takes_the_drills_expectation(bench):
    """Orodruin's timer lays each wire of the drill on each target armed: two wires in the request,
    the expectation of the drill's one wire for both."""
    c = card()
    bench.status(wires=[{"rank": 1, "state": "done", "code": "", "runs": ["20261117T191000Z-cd34"], "result": ""},
                        {"rank": 2, "state": "done", "code": "", "runs": [RUN], "result": ""}])
    bench.refresh()
    assert the(c)[escalations.PROPOSED_FIELD]["rank"] == 2


def test_wires_that_do_not_lay_out_the_drill(bench):
    c = card()
    bench.status(wires=[])
    bench.refresh()
    assert why(c) in ("not_a_wire", "layout")


def test_a_status_unreadable_or_absent(bench):
    c = card()
    path = bench.root / "glorfindel" / "orodruin" / "requests" / f"{REQ}.json"
    path.write_text('{"request": "x"}')
    bench.refresh()
    assert why(c) == "status_unread"
    path.unlink()
    bench.refresh()
    assert why(c) == "no_status"


def test_an_old_card_is_not_looked_at(bench):
    c = card()
    redate(c, bench.now - timedelta(days=8))
    assert bench.refresh() == 0 and escalations.PROPOSED_WHY not in the(c)


def test_the_reasons_name_no_identifier(bench):
    for code, said in pv._SAID.items():
        assert "/subscriptions/" not in said and REQ not in said and RUN not in said, code


def test_the_watch_runs_the_pass_every_minute():
    cli = (Path(__file__).resolve().parents[2] / "glorfindel" / "cli.py").read_text(encoding="utf-8")
    assert "        proposed_verdict.refresh(runs_dir, say=lambda text: _say_channel(" in cli
    assert "_propose_verdicts()  # VP1" in cli


def test_the_api_confirms_and_refuses(bench, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from .console_client import console
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    client = console()
    a, b = card(), card(rule="another-rule", action="isolate_vm", kind="mode_hold")
    bench.refresh()
    listed = {x["id"]: x for x in client.get("/api/to-judge?since=7d").json()["cards"]}
    assert listed[a][escalations.PROPOSED_FIELD]["verdict"] == "right"
    assert listed[b][escalations.PROPOSED_WHY]["code"] == "rule"
    assert "error" in client.post(f"/api/escalations/{b}/proposed/confirm", json={}).json()
    assert client.post(f"/api/escalations/{a}/proposed/refuse", json={"note": "n"}).json() == {"ok": True}
    assert "error" in client.post(f"/api/escalations/{a}/proposed/confirm", json={}).json()
    escalations._STORE.unlink()
    c = card()
    bench.refresh()
    assert client.post(f"/api/escalations/{c}/proposed/confirm", json={}).json() == {"ok": True, "verdict": "right"}
    assert the(c)["verdict"] == "right"


# ── VP1b (#917): the remainders of VP1's review ────────────────────────────────────────────────

def test_confirmed_then_judged_by_hand_it_no_longer_says_proposed(bench, monkeypatch):
    """A card confirmed from its proposal, then judged again by hand — in the console, by its API —
    is the operator's own verdict: neither the card, nor TO JUDGE, nor the report says « proposed »."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from .console_client import console
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    client = console()
    c = card()
    bench.refresh()
    assert client.post(f"/api/escalations/{c}/proposed/confirm", json={}).json() == {"ok": True, "verdict": "right"}
    assert the(c)["verdict_from"] == "proposed"
    said = client.post(f"/api/escalations/{c}/verdict", json={"verdict": "wrong", "note": "disproportionate"}).json()
    assert said == {"ok": True, "verdict": "wrong"}
    e = the(c)
    assert (e["verdict"], e["verdict_note"]) == ("wrong", "disproportionate") and "verdict_from" not in e
    assert c not in {x["id"] for x in client.get("/api/to-judge?since=7d").json()["cards"]}
    assert "proposed" not in json.dumps(escalations.observation_report())
    # By the CLI's path too (set_verdict): a verdict given by hand, never « proposed ».
    escalations.set_verdict(c[:8], "unsure", "")
    assert "verdict_from" not in the(c)


def test_a_card_without_a_time_zone_among_others_the_others_proposed(bench):
    """A card whose time carries no time zone raised in the pass, and the whole pass stopped each
    minute: nothing more was proposed. It is skipped — never proposed, its zone never guessed —, said
    once on the card, and the others are proposed."""
    a = card(rule="another-rule", action="isolate_vm", kind="mode_hold")
    n = card(rule="a-third-rule", action="isolate_vm", kind="low_confidence")
    redate(n, (bench.now - timedelta(seconds=60)).replace(tzinfo=None))
    c = card()
    assert bench.refresh() == 3
    assert the(c)[escalations.PROPOSED_FIELD]["verdict"] == "right"
    assert why(a) == "rule" and why(n) == "no_tz"
    assert escalations.PROPOSED_FIELD not in the(n)
    assert bench.refresh() == 0                      # said once: the next pass changes nothing


def test_a_card_without_a_time_zone_in_the_wire_which_came_first_is_never_guessed(bench):
    """The same rule on the same wire: the first card cannot be told — none of them is proposed."""
    n = card()
    redate(n, (bench.now - timedelta(seconds=60)).replace(tzinfo=None))
    c = card(action="isolate_vm", kind="mode_hold")
    bench.refresh()
    assert why(n) == "no_tz" and why(c) == "unordered"
    assert escalations.PROPOSED_FIELD not in the(c)


def test_a_card_the_pass_cannot_assess_is_skipped_said_once_the_others_proposed(bench, monkeypatch):
    monkeypatch.setattr(pv, "_SKIPPED", set())
    bad, c = card(rule="another-rule", action="isolate_vm", kind="mode_hold"), card()
    real = pv.assess

    def assess(card_, cards, src):
        if card_["id"] == bad:
            raise TypeError("a card the pass cannot read <@everyone>")
        return real(card_, cards, src)

    monkeypatch.setattr(pv, "assess", assess)
    said = []
    assert bench.refresh(say=said.append) == 1
    assert the(c)[escalations.PROPOSED_FIELD]["verdict"] == "right"
    assert escalations.PROPOSED_FIELD not in the(bad) and escalations.PROPOSED_WHY not in the(bad)
    assert len(said) == 1 and bad[:8] in said[0] and "TypeError" in said[0]
    assert "everyone" not in said[0]                  # the error's kind, never its text
    bench.refresh(say=said.append)
    assert len(said) == 1                             # once
