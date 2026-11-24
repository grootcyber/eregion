"""MEM1 (#1016): scripts/memory_replay.py — the memory of decisions replayed on a copy of a store,
its ranking by distance against a ranking by date, aggregated numbers only.

Each store is written by the real CycleMemory (glorfindel/memory.py) in tmp_path, with the embedded
Chroma client, then copied: the script reads a copy, as it does Imladris's. Where the geometry
matters (the rankings, the share of the same technique), each cycle carries an embedding the test
chooses, and the signal's text is embedded by a function of the test. Elsewhere, Chroma's own ONNX
model embeds, from ~/.cache/chroma as the other tests of the memory use it (the suite's throwaway HOME
links it, tests/unit/home_sandbox.py; the CI fetches it before the tests, scripts/chroma_model.py):
nothing is fetched, no cloud, no model of language. Mutants M6957–M6961 (scripts/mutants/MEM1.py).

MEM2 (#1027): a fifth ranking, ``keys`` — the memory by keys's own code (`memory_keys.choose`).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from eregion_core import store_guard
from glorfindel import memory
from glorfindel.memory import CycleMemory

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "memory_replay.py"
DAY = 86400
B2 = memory.B2_FLOOR
VM = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/{}"
# Three directions: the signal's text of a technique is embedded on its own (`_embed`).
AXES = {"T1486": np.array([1.0, 0.0, 0.0]), "T1041": np.array([0.0, 1.0, 0.0]), "T1110.001": np.array([0.0, 0.0, 1.0])}


@pytest.fixture(scope="module")
def mr():
    spec = importlib.util.spec_from_file_location("memory_replay", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _env_restored(monkeypatch):
    """The script sets Chroma's telemetry off and the hub offline in its process: restored after."""
    monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)


def _embed(text: str):
    """The signal's text → the direction of its technique."""
    return AXES[text.split(" | ")[0].removeprefix("TTP: ")]


def _cycle(sid: str, ttp: str = "T1486", vm: str = "", rule: str = "", **over) -> dict:
    return {"signal_id": sid, "run_id": f"run-{sid}", "ttp": ttp, "severity": "high", "resource_type": "vm",
            "event": "detection", "action": "isolate_vm", "reasoning": f"reasoning of {sid}", "outcome": "done",
            "source": "real", "confidence": 0.9, "resource_id": VM.format(vm) if vm else "", "rule_name": rule,
            **over}


class _Store:
    """A store written by the real CycleMemory, each cycle at the date given; `copy` gives the copy
    the script reads."""

    def __init__(self, root: Path):
        self.root = root
        self.at = float(B2)
        self.mem = CycleMemory(path=root / "orig", clock=lambda: self.at)
        self._add = self.mem._collection.add

    def store(self, cycle: dict, at: float, vector=None) -> None:
        self.at = at
        if vector is not None:
            unit = np.asarray(vector, dtype=float) / np.linalg.norm(vector)
            self.mem._collection.add = lambda **kw: self._add(**kw, embeddings=[unit.tolist()])
        try:
            self.mem.store(cycle)
        finally:
            self.mem._collection.add = self._add

    def legacy(self, sid: str, ttp: str = "T1486") -> None:
        """A real cycle as stored before SEC17 and SEC-I: no date, no rule, no VM."""
        self._add(ids=[f"cycle-{sid}"], documents=[f"TTP: {ttp} | {sid}"],
                  metadatas=[{"source": "real", "signal_id": sid, "action": "isolate_vm", "run_id": "r", "ttp": ttp}])

    def copy(self) -> Path:
        target = self.root / "copy"
        shutil.copytree(self.root / "orig", target)
        return target


def _run(mr, capsys, *argv) -> tuple[int, dict | None, str]:
    code = mr.main([str(a) for a in argv])
    out, err = capsys.readouterr()
    return code, (json.loads(out) if code == 0 else None), out + err


# ── The rankings ─────────────────────────────────────────────────────────────────────────────────

def test_the_distance_and_the_date_give_other_precedents(tmp_path, mr):
    """The code's ranking (the distance) against the date, signal by signal: three cycles that name
    neither rule nor VM — one place, as before SEC-I. The last T1486 signal gets the older T1486 cycle
    by the distance, the newer T1041 one by the date."""
    s = _Store(tmp_path)
    s.store(_cycle("c0", "T1486"), B2 + 1 * DAY, AXES["T1486"])
    s.store(_cycle("c1", "T1041"), B2 + 2 * DAY, AXES["T1041"])
    s.store(_cycle("c2", "T1486"), B2 + 3 * DAY, AXES["T1486"])
    out = mr.replay(mr.load(s.copy()), _embed, shipped=set())["replay"]
    assert out["signals_with_a_precedent"] == 2
    assert out["distinct_query_texts"] == 2
    # c1 has one candidate, taken by both; c2 has two, the distance and the date part.
    assert out["same_set"] == {"distance_vs_date": 1, "distance_vs_ttp_then_date": 2,
                               "distance_vs_ttp_then_distance": 2, "ttp_then_date_vs_ttp_then_distance": 2,
                               "distance_vs_keys": 2, "ttp_then_date_vs_keys": 2}
    assert out["same_first"]["distance_vs_date"] == 1
    assert out["mean_jaccard"]["distance_vs_date"] == 0.5
    assert out["first_place_contested"] == 1
    assert out["mean_precedents"] == {"distance": 1.0, "date": 1.0, "ttp_then_date": 1.0, "ttp_then_distance": 1.0,
                                      "keys": 1.0}


def test_one_precedent_per_vm_at_most_the_unknown_vm_counting_as_one(tmp_path, mr):
    """M6957: three cycles of the signal's VM, nearest of all, take one place, as do two cycles that
    name no VM (the VM unknown); the third place goes to another VM, farther (memory.PER_VM)."""
    s = _Store(tmp_path)
    for i in range(3):
        s.store(_cycle(f"a{i}", "T1486", vm="vm-a"), B2 + (1 + i) * DAY, AXES["T1486"])
    s.store(_cycle("b0", "T1041", vm="vm-b"), B2 + 4 * DAY, AXES["T1041"])
    for i in range(2):
        s.store(_cycle(f"u{i}", "T1486"), B2 + (5 + i) * DAY, AXES["T1486"])
    cycles = mr.load(s.copy())
    vm_a, vm_b = memory._vm_key(VM.format("vm-a")), memory._vm_key(VM.format("vm-b"))
    picks = mr.pick(cycles, "", vm_a, lambda c: 1.0 - float(c["emb"] @ AXES["T1486"]))
    owners = [cycles[i]["vm"] for i in picks]
    assert sorted(owners) == sorted([vm_a, vm_b, ""])
    assert owners[0] == vm_a                    # the signal's VM first, then the distance
    # Replayed: 1, 1, 1, 2, 3 precedents for the five signals (a1, a2, b0, u0, u1).
    assert mr.replay(cycles, _embed, shipped=set())["replay"]["mean_precedents"]["distance"] == 1.6


def _toward(ttp: str):
    """The order by distance to the signal's text of ``ttp``."""
    return lambda c: 1.0 - float(c["emb"] @ AXES[ttp])


def _names(cycles: list[dict], picks: list[int]) -> list[str]:
    return [cycles[i]["key"][0] for i in picks]


def test_a_cycle_of_the_signal_rule_comes_before_a_nearer_one(tmp_path, mr):
    """M7020: the code's first key. Two cycles of one VM, one place: the cycle of the signal's rule,
    farther and older, stored after the nearer one, takes it — neither the distance, nor the date,
    nor the order of the store would."""
    s = _Store(tmp_path)
    s.store(_cycle("near", "T1486", vm="vm-x"), B2 + 2 * DAY, AXES["T1486"])
    s.store(_cycle("far", "T1486", vm="vm-x", rule="ransomware-disk-write"), B2 + 1 * DAY, AXES["T1041"])
    cycles = mr.load(s.copy())
    signal_vm = memory._vm_key(VM.format("vm-s"))
    assert _names(cycles, mr.pick(cycles, "ransomware-disk-write", signal_vm, _toward("T1486"))) == ["far"]
    # Without the signal's rule, the distance decides.
    assert _names(cycles, mr.pick(cycles, "", signal_vm, _toward("T1486"))) == ["near"]


def test_a_cycle_of_the_signal_vm_comes_before_a_nearer_one(tmp_path, mr):
    """M7021: the code's second key. A cycle of the signal's VM, farther and older, stored after a
    nearer one that names no VM, comes first; with one place, it takes it."""
    s = _Store(tmp_path)
    s.store(_cycle("near", "T1486"), B2 + 2 * DAY, AXES["T1486"])                  # the VM unknown
    s.store(_cycle("far", "T1486", vm="vm-a"), B2 + 1 * DAY, AXES["T1041"])
    cycles = mr.load(s.copy())
    vm_a = memory._vm_key(VM.format("vm-a"))
    assert _names(cycles, mr.pick(cycles, "", vm_a, _toward("T1486"))) == ["far", "near"]
    assert _names(cycles, mr.pick(cycles, "", vm_a, _toward("T1486"), n=1)) == ["far"]
    # On another VM, the distance decides.
    assert _names(cycles, mr.pick(cycles, "", memory._vm_key(VM.format("vm-b")), _toward("T1486"))) == ["near", "far"]


def test_the_share_of_precedents_bearing_the_signal_technique(tmp_path, mr):
    """M6959: the share is counted per precedent given, never per signal — the measure the note rests
    on (77 % by the distance, 80 % by the date, 93 % by the technique then the date, on Imladris's
    copy of 21/11). Four VMs, three places: the last T1486 signal gets two T1486 cycles by the distance
    and by the technique, one by the date (the two newest are T1041)."""
    s = _Store(tmp_path)
    s.store(_cycle("y1", "T1486", vm="vm-y"), B2 + 1 * DAY, AXES["T1486"])
    s.store(_cycle("w1", "T1486", vm="vm-w"), B2 + 2 * DAY, AXES["T1486"])
    s.store(_cycle("x1", "T1041", vm="vm-x"), B2 + 3 * DAY, AXES["T1041"])
    s.store(_cycle("z1", "T1041", vm="vm-z"), B2 + 4 * DAY, [-0.1, 1.0, 0.0])   # farther than x1 from T1486
    s.store(_cycle("s", "T1486", vm="vm-s"), B2 + 5 * DAY, AXES["T1486"])
    out = mr.replay(mr.load(s.copy()), _embed, shipped=set())["replay"]
    # Given: 1 (w1), 2 (x1), 3 (z1), 3 (s) = 9 by each ranking; of the signal's technique: 1, 0, 1, then
    # 2 by the distance (y1, w1), 1 by the date (w1), 2 by the technique first (w1, y1).
    four, three = round(4 / 9, 3), round(3 / 9, 3)
    assert out["share_same_ttp"] == {"distance": four, "date": three, "ttp_then_date": four, "ttp_then_distance": four,
                                     "keys": four}
    assert out["share_same_ttp_by_signal_ttp"] == {
        "T1041": {"distance": 0.2, "date": 0.2, "ttp_then_date": 0.2, "ttp_then_distance": 0.2, "keys": 0.2},
        "T1486": {"distance": 0.75, "date": 0.5, "ttp_then_date": 0.75, "ttp_then_distance": 0.75, "keys": 0.75}}
    assert out["signals_with_a_same_ttp_cycle_in_memory"] == 3


def test_the_keys_ranking_is_the_memorys_code_and_parts_the_undated_by_their_order(tmp_path, mr):
    """MEM2: the ranking ``keys`` is what the memory by keys gives (`memory_keys.choose`). It differs
    from MEM1's ``ttp_then_date`` on the undated cycles only — all at the B2 floor: the memory takes the
    one stored last, MEM1's took the one stored first."""
    s = _Store(tmp_path)
    s.legacy("l0")
    s.legacy("l1")
    s.store(_cycle("d0", "T1486"), B2 + 10 * DAY)
    # Chroma's model embedded these (384 dimensions): the distance is not what is measured here.
    cycles = mr.load(s.copy())
    out = mr.replay(cycles, lambda _text: np.ones(384), shipped=set())["replay"]
    assert out["signals_with_a_precedent"] == 2
    # l1 (l0 alone before it): the same; d0 (l0, l1, the VM unknown, one place): l1 by the keys, l0 before.
    assert out["same_set"]["ttp_then_date_vs_keys"] == 1
    real = sorted((c for c in cycles if c["source"] == "real"), key=lambda c: c["at"])
    from glorfindel import memory_keys
    chosen = memory_keys.choose(real[:2], "", "", "T1486", 3)
    assert [c["key"][0] for c in chosen] == ["l1"]


# ── The dates ────────────────────────────────────────────────────────────────────────────────────

def test_an_undated_cycle_is_dated_by_the_b2_floor(tmp_path, mr, capsys):
    """M6958: a real cycle stored before cycles were dated takes the B2 floor, as the memory dates it
    (memory._stored_at) — a precedent of a cycle stored ten days after the floor, too old for one
    stored 120 days after; the age bound is the memory's (90 days), or the one given."""
    s = _Store(tmp_path)
    s.legacy("l1")
    s.legacy("l2")
    s.store(_cycle("d1"), B2 + 10 * DAY)
    s.store(_cycle("d2"), B2 + 120 * DAY)
    copy = s.copy()
    code, out, _said = _run(mr, capsys, copy)
    assert code == 0
    assert out["store"]["real_undated_b2_floor"] == 2
    assert out["store"]["real_span_days"] == 120.0
    # l2 (l1 before it), d1 (l1, l2 ten days before); d2: everything 110 days or more before it.
    assert out["replay"]["signals_with_a_precedent"] == 2
    assert out["replay"]["max_age_days"] == 90.0
    code, out, _said = _run(mr, capsys, copy, "--max-age-days", "200")
    assert code == 0 and out["replay"]["signals_with_a_precedent"] == 3


# ── What is opened ───────────────────────────────────────────────────────────────────────────────

def test_the_operator_store_is_refused_before_anything_is_opened(tmp_path, mr, capsys, monkeypatch):
    """M6960: the store under the home the system gives the operator (pwd), whatever HOME says, and
    the one under HOME, as given or through a link — refused, nothing opened; a folder that is no
    store too, and nothing is made in it."""
    operator = tmp_path / "operator"
    monkeypatch.setattr(store_guard, "operator_home", lambda: operator)
    store = operator / ".glorfindel" / "cycles"
    CycleMemory(path=store)
    sqlite = store / "chroma.sqlite3"
    before = sqlite.stat().st_mtime_ns
    link = tmp_path / "elsewhere"
    link.symlink_to(store, target_is_directory=True)
    for path in (store, link):
        code, out, said = _run(mr, capsys, path)
        assert code == 2 and out is None
        assert "refusé" in said and "~/.glorfindel de l'opérateur" in said
    assert sqlite.stat().st_mtime_ns == before

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    CycleMemory(path=home / ".glorfindel" / "cycles")
    code, _out, said = _run(mr, capsys, home / ".glorfindel" / "cycles")
    assert code == 2 and "~/.glorfindel de l'opérateur" in said

    empty = tmp_path / "not-a-store"
    empty.mkdir()
    code, _out, said = _run(mr, capsys, empty)
    assert code == 2 and "pas la copie d'un magasin" in said
    assert list(empty.iterdir()) == []


def test_a_copy_linked_to_the_operator_store_is_refused(tmp_path, mr, capsys, monkeypatch):
    """M7022, M7023: a copy outside the operator's folders whose chroma.sqlite3 is a link to the
    original, or one of whose folders is (a segment's), is refused before anything is opened; the
    copy is walked, its links never followed."""
    operator = tmp_path / "operator"
    monkeypatch.setattr(store_guard, "operator_home", lambda: operator)
    original = operator / ".glorfindel" / "cycles"
    CycleMemory(path=original)
    sqlite = original / "chroma.sqlite3"
    before = sqlite.stat().st_mtime_ns

    by_file = tmp_path / "copy-by-file"
    by_file.mkdir()
    (by_file / "chroma.sqlite3").symlink_to(sqlite)
    by_folder = tmp_path / "copy-by-folder"
    shutil.copytree(original, by_folder)
    (by_folder / "segment").symlink_to(original, target_is_directory=True)
    for copy in (by_file, by_folder):
        code, out, said = _run(mr, capsys, copy)
        assert code == 2 and out is None
        assert "mène par un lien au ~/.glorfindel de l'opérateur" in said
    assert sqlite.stat().st_mtime_ns == before


def test_the_model_is_never_fetched_and_the_store_opened_offline(tmp_path, mr, capsys, monkeypatch):
    """Chroma's model missing: refused, never fetched; present, the client is opened with its
    telemetry off, and the hub is said offline."""
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    s = _Store(tmp_path)
    copy = s.copy()
    real_path = ONNXMiniLM_L6_V2.DOWNLOAD_PATH
    nowhere = tmp_path / "no-model"
    monkeypatch.setattr(ONNXMiniLM_L6_V2, "DOWNLOAD_PATH", nowhere)

    def fetched(self):
        raise AssertionError("the model fetched")

    monkeypatch.setattr(ONNXMiniLM_L6_V2, "_download_model_if_not_exists", fetched)
    code, _out, said = _run(mr, capsys, copy)
    assert code == 2 and "ne le tire jamais" in said
    assert not nowhere.exists()

    monkeypatch.setattr(ONNXMiniLM_L6_V2, "DOWNLOAD_PATH", real_path)
    import chromadb
    opened = []
    real_client = chromadb.PersistentClient

    def client(path, settings=None, **kw):
        opened.append(settings.anonymized_telemetry)
        return real_client(path=path, settings=settings, **kw)

    monkeypatch.setattr(chromadb, "PersistentClient", client)
    code, out, _said = _run(mr, capsys, copy)
    assert code == 0 and out["store"]["cycles"] == 0
    assert opened == [False]
    assert os.environ["ANONYMIZED_TELEMETRY"] == "False" and os.environ["HF_HUB_OFFLINE"] == "1"


# ── What is printed ──────────────────────────────────────────────────────────────────────────────

def test_nothing_of_a_cycle_reaches_the_output(tmp_path, mr, capsys):
    """M6961: aggregated numbers only — never a VM, an identifier, a run, a text of a cycle, nor the
    name of a rule the client wrote; a shipped rule's name and an ATT&CK id are public."""
    s = _Store(tmp_path)
    s.store(_cycle("zz-secret-signal-1", vm="zz-secret-vm-1", rule="data-exfiltration-blob", ttp="T1041",
                   run_id="zz-secret-run-1", reasoning="zz-secret-reasoning", outcome="zz-secret-outcome"),
            B2 + DAY)
    s.store(_cycle("zz-secret-signal-2", vm="zz-secret-vm-2", rule="zz-secret-client-rule", ttp="zz-secret-ttp",
                   run_id="zz-secret-run-2"), B2 + 2 * DAY)
    s.store(_cycle("zz-secret-signal-3", vm="zz-secret-vm-1", source="exercise", exercise_run="zz-secret-exercise"),
            B2 + 3 * DAY)
    s.store(_cycle("zz-secret-signal-4", vm="zz-secret-vm-2", source="zz-secret-source"), B2 + 4 * DAY)
    code, out, said = _run(mr, capsys, s.copy())
    assert code == 0
    for word in ("zz-secret", "cycle-", "/subscriptions/", "rg-test"):
        assert word not in said
    assert out["store"]["rules"] == {"data-exfiltration-blob": 1, "(other)": 1}
    assert out["store"]["ttps"] == {"T1041": 1, "(other)": 1}
    assert out["store"]["by_source"] == {"real": 2, "exercise": 1, "(other)": 1}
    assert out["store"]["vm_keys"] == 2
