"""The Stratus detonator (R2c pièce 4, the sidecar): it runs the RAW Stratus phase subprocesses in
the sandbox — the network where the IMDS is DROPped (pièce 3) and the azurerm provider authenticates
by the federated exchange (the mounted assertion). The engine, on the bridge under Orodruin's
identity, keeps everything else — the contract (arm), the watch gate and its mid-cycle re-check, the
exercise window, the Graph probes and the journal — and asks the detonator to run each phase through
a shared directory (request/response files). Orodruin's managed identity never reaches this
container, so a compromised Stratus library cannot obtain its token from the IMDS.

Two halves share the protocol:
  - ``serve`` + ``main`` run in the detonator container
    (``python -m annatar.executors.stratus_detonator <ipc_dir> <technique_id>``);
  - ``ipc_detonate`` is the engine's delegate (``StratusExecutor(detonate=...)``).
The phases are sequential, so at most one request is outstanding; an ``id`` on each pairs the
response to its request, and ``__stop__`` ends the loop (the Makefile also removes the container).
"""
from __future__ import annotations

import itertools
import json
import os
import sys
import time
from pathlib import Path

REQ = "request.json"
RESP = "response.json"
POLL_S = 0.2
STOP = "__stop__"


def _atomic_write(path: Path, obj: dict) -> None:
    """Write JSON so a reader never sees a half-written file (write a temp, then rename)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    tmp.replace(path)


def serve(ipc_dir: str | Path, run_one, *, poll: float = POLL_S, sleep=time.sleep,
          max_idle_s: float | None = None, now=time.monotonic) -> None:
    """The detonator loop: read a phase request, run it through ``run_one(phase) -> (out, err, rc)``,
    write the response, until a ``__stop__`` request (or ``max_idle_s`` with no request — a guard so
    a forgotten detonator does not wait forever). ``run_one`` is ``StratusExecutor.run_subprocess``;
    the tests inject a fake."""
    d = Path(ipc_dir)
    d.mkdir(parents=True, exist_ok=True)
    last = now()
    while True:
        req_path = d / REQ
        if not req_path.exists():
            if max_idle_s is not None and now() - last > max_idle_s:
                return
            sleep(poll)
            continue
        last = now()
        try:
            req = json.loads(req_path.read_text(encoding="utf-8"))
        except Exception:
            sleep(poll)               # a half-written request: wait for the atomic rename
            continue
        phase = req.get("phase")
        if phase == STOP:
            req_path.unlink()
            return
        try:
            out, err, rc = run_one(phase)
            resp = {"id": req.get("id"), "stdout": out, "stderr": err, "rc": rc}
        except Exception as e:        # a crash in the detonator is a failed phase, never a hang
            resp = {"id": req.get("id"), "stdout": "",
                    "stderr": f"detonator: {type(e).__name__}: {e}"[:500], "rc": 1}
        _atomic_write(d / RESP, resp)
        req_path.unlink()


def ipc_detonate(ipc_dir: str | Path, *, timeout: float, poll: float = POLL_S,
                 sleep=time.sleep, now=time.monotonic):
    """The engine's delegate: send one phase to the detonator and wait for its result. Returns a
    ``detonate(name) -> (stdout, stderr, rc)`` the ``StratusExecutor`` calls in place of the local
    subprocess. The assertion and the staged binary live in the detonator; this only passes the
    phase name across, never a credential."""
    d = Path(ipc_dir)
    seq = itertools.count(1)

    def detonate(name: str):
        d.mkdir(parents=True, exist_ok=True)
        rid = next(seq)
        (d / RESP).unlink(missing_ok=True)       # no stale answer from a prior phase
        _atomic_write(d / REQ, {"id": rid, "phase": name})
        deadline = now() + timeout
        while now() < deadline:
            resp_path = d / RESP
            if resp_path.exists():
                try:
                    resp = json.loads(resp_path.read_text(encoding="utf-8"))
                except Exception:
                    sleep(poll)
                    continue
                if resp.get("id") == rid:
                    resp_path.unlink(missing_ok=True)
                    return resp.get("stdout", ""), resp.get("stderr", ""), resp.get("rc", 1)
            sleep(poll)
        raise RuntimeError(f"the Stratus detonator did not answer phase {name!r} within {timeout}s")

    def stop():
        _atomic_write(d / REQ, {"phase": STOP})

    detonate.stop = stop
    return detonate


def main() -> int:  # pragma: no cover - the container entrypoint; the tests drive serve() directly
    if len(sys.argv) != 3:
        print("usage: python -m annatar.executors.stratus_detonator <ipc_dir> <scenario>",
              file=sys.stderr)
        return 2
    ipc_dir, scenario_name = sys.argv[1], sys.argv[2]
    from annatar.engines.stratus import resolve
    from annatar.executors.stratus_host import StratusExecutor, staged_layout
    from annatar.runner.parser import ScenarioParser, find_scenario_by_name

    path = find_scenario_by_name(scenario_name)
    if not path:
        print(f"detonator: scenario {scenario_name!r} not found", file=sys.stderr)
        return 2
    resolved = resolve(ScenarioParser().load(path).engine_ref, binary_path=staged_layout().binary)
    executor = StratusExecutor(resolved, session=None,
                               target=os.environ.get("EREGION_STRATUS_TARGET", ""), dry_run=False)
    # A generous idle guard: longer than a phase, so the detonator exits if the engine vanished.
    serve(ipc_dir, executor.run_subprocess, max_idle_s=float(
        os.environ.get("EREGION_STRATUS_DETONATOR_IDLE_S", "1800")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
