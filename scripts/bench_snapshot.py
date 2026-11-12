"""bench_snapshot — the clean point after the confirmation, and the route of the 📸 button (BNC3b, #770).

docs/design/banc-autonome.md, §3.1 (« Le point propre », « Le chemin du bouton 📸 »). `make bench-run`
reads, once the request is confirmed, the newest recovery point of the target — the one the restore
will take — and keeps it when it is clean: taken after the VM's last restore (the vault's jobs) and
outside every quarantine, over every run (Imladris's history, scripts/bench_history.py). A read that
fails is no clean point. Otherwise it asks for one, by the route of the console's 📸 button,
`POST /api/action/snapshot/<vm>` of Imladris's console:

  the way in    a short port forward it opens itself, `ssh -L 127.0.0.1:<free port>:127.0.0.1:7007 … sleep
                FORWARD_MAX_S` to Imladris — a bounded remote command, not `-N` —, the host key pinned
                (the Makefile's `imladris-known` file), never through a multiplexed master
                (ControlMaster=no), closed whatever the end (a SIGTERM included, by its handler; past
                it, the command's bound) — the time of the request and its receipt only: it depends on
                no tunnel of MOB2, leaves nothing open, never takes the port 7007 of the phone's tunnel;
  the token     the console's, read in host.env by the Makefile, refused to a code session by its guard
                (`CONSOLE_GUARD`, scripts/mobile.py guard), handed to this script by the environment
                (BENCH_CONSOLE_TOKEN), taken out of every child's environment as soon as it is read
                (scripts/bench_run.py), never in an argv, never printed; sent as `Authorization:
                Bearer`, never in the URL; no proxy;
  the request   a JSON body (`Content-Type: application/json`) and a `Host` of `127.0.0.1:<port>`: two of
                the console's entry checks (eregion_console/api.py, `_TokenAuthMiddleware`);
  the receipt   under FS1 (EREGION_ACTION_QUEUE=1), the route deposits a signed request and the watch runs
                it: its receipt followed by `GET /api/queue/<id>` until final — `not_taken`, `untrusted`,
                `refused`, `failed`, `unknown`, or a request past its life stop the run;
  the job       the vault's job the console names, when it names one (`vault_job_name`: today it gives
                Glorfindel's own record, `snapshot-<vm>-<ts>`, which is none), else the vault's backup
                job of the VM started since the gesture, followed by `az backup job
                show` under the operator's `az login` until `Completed`, JOB_WAIT_S at most from the
                gesture (60 min: the first point after a restore is complete, ~40 min); one that fails or
                runs past it stops the run — before the request goes to Orodruin: nothing is attacked;
  the point     read again in the vault: newer than the one refused, or the run stops.

Then `make bench-run` replays its preflight, just before the attack (up to 60 min may have passed).
Never `docker exec` into a container of Imladris, nor Glorfindel's CLI in the console's (BNC1, FS1 §2.12).
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import bench_history as bh
import bench_shared as bs

CONSOLE_PORT = 7007
TOKEN_ENV = "BENCH_CONSOLE_TOKEN"
TUNNEL_WAIT_S = 30.0
HTTP_TIMEOUT_S = 60.0
MAX_ANSWER_BYTES = 256 * 1024
# The watch takes a request within its life, then runs it (eregion_core/action_queue.py: TAKE_S, RUN_S).
from eregion_core.action_queue import RUN_S as _RUN_S, TAKE_S as _TAKE_S  # noqa: E402
QUEUE_WAIT_S = float(_TAKE_S + _RUN_S + 60)
QUEUE_POLL_S = 5.0
# How long the forward lives at most: the request and its receipt (QUEUE_WAIT_S), and a margin.
FORWARD_MAX_S = QUEUE_WAIT_S + 120.0
JOB_WAIT_S = 3600.0
JOB_POLL_S = 60.0
JOB_FIND_S = 300.0
JOB_SKEW_S = 120.0
JOB_READ_FAILURES = 3
FINAL_REFUSALS = ("not_taken", "untrusted", "refused", "failed", "unknown")
_JOB_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,63}")
_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")


# ── the clean point ───────────────────────────────────────────────────────────

def judge(target: str, env: dict, config: str, now: float | None = None) -> dict:
    """{"clean", "said", "point", "rg", "vault", "vault_rg"}: the newest point of the target, kept
    when clean. Any read that fails: not clean, said why — a new point is asked."""
    import bench_preflight as bp
    now = time.time() if now is None else now
    hits = bs.locate_vm(target)
    if len(hits) != 1:
        raise RuntimeError(f"{len(hits)} VM nommée(s) {target} : une seule attendue")
    rg, vm_id = hits[0]["rg"], hits[0]["id"]
    try:
        vault, vault_rg, _ = bs.local_vault(config)
    except Exception as e:  # noqa: BLE001 — its message may repeat the file's values: only its type
        raise RuntimeError(f"la configuration du poste ne se lit pas ({type(e).__name__})") from None
    out ={"clean": False, "said": "", "point": None, "rg": rg, "vault": vault, "vault_rg": vault_rg or rg}
    if not vault:
        out["said"] = "aucun coffre dans la configuration du poste"
        return out
    try:
        times = bp.point_times(target, vault_rg or rg, vault)
    except RuntimeError as e:
        out["said"] = f"les points de la cible ne se lisent pas ({bs.scrub(str(e))[:200]})"
        return out
    out["point"] = max(times, default=None)
    reads = bh.Reads(target, vm_id, rg, vault, vault_rg, env, now)
    try:
        since = reads.anchor()
    except bh.Unreadable as e:
        out["said"] = f"le dernier restore de la VM ne se lit pas ({e})"
        return out
    if out["point"] is not None and out["point"] <= since.end:
        out["clean"], out["said"] = bh.point_clean(out["point"], since, [])
        return out
    try:
        quarantine = reads.quarantines()
    except bh.Unreadable as e:
        out["said"] = f"les quarantaines de la VM ne se lisent pas sur Imladris ({e})"
        return out
    out["clean"], out["said"] = bh.point_clean(out["point"], since, quarantine)
    return out


def rejudge(target: str, env: dict, config: str, point: float, now: float | None = None) -> tuple[bool, str]:
    """The point the 📸 route took, judged again (BNC3b review): after the last restore, outside every
    quarantine, read again — an isolation opened during the job, or a quarantine still open, refuses
    it. Any read that fails: refused."""
    now = time.time() if now is None else now
    hits = bs.locate_vm(target)
    if len(hits) != 1:
        return False, f"{len(hits)} VM nommée(s) {target} : une seule attendue"
    try:
        vault, vault_rg, _ = bs.local_vault(config)
    except Exception as e:  # noqa: BLE001
        return False, f"la configuration du poste ne se lit pas ({type(e).__name__})"
    reads = bh.Reads(target, hits[0]["id"], hits[0]["rg"], vault, vault_rg, env, now)
    try:
        since, quarantine = reads.anchor(), reads.quarantines()
    except bh.Unreadable as e:
        return False, f"le point pris ne se rejuge pas ({e})"
    return bh.point_clean(point, since, quarantine)


# ── the port forward ──────────────────────────────────────────────────────────

def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def forward_argv(base: list[str], port: int) -> list[str]:
    """The ssh of the forward: a bounded remote command (`sleep FORWARD_MAX_S`, never `-N`: a SIGTERM
    that skips the close leaves it open no longer — BNC3b review), no prompt, no tty, no multiplexed
    master, failing when it can't forward, to the console's port on Imladris's loopback alone."""
    return [*base[:-1], "-T", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=15",
            "-o", "ControlMaster=no", "-o", "ControlPath=none",
            "-L", f"127.0.0.1:{port}:127.0.0.1:{CONSOLE_PORT}", base[-1], f"sleep {int(FORWARD_MAX_S)}"]


class Tunnel:
    """The short port forward to Imladris's console, opened and closed by this script — closed
    whatever the end, an error included."""

    def __init__(self, env: dict, *, popen=subprocess.Popen, connect=socket.create_connection, port=None,
                 clock=time.monotonic, sleep=time.sleep, wait_s: float = TUNNEL_WAIT_S):
        self.env, self.popen, self.connect, self.port = env, popen, connect, port
        self.clock, self.sleep, self.wait_s = clock, sleep, wait_s
        self.proc = None

    def __enter__(self) -> int:
        base = bs.ssh_argv("BENCH_H0_SSH", self.env)
        if not base:
            raise RuntimeError("BENCH_H0_SSH vide : lancer par make bench-run")
        if not bs.host_key_pinned(base):
            raise RuntimeError("la clé d'hôte d'Imladris n'est pas vérifiée par son empreinte (HOST_SSH_FINGERPRINT, "
                               "make imladris-known) : aucun point demandé")
        self.port = self.port or free_port()
        self.proc = self.popen(forward_argv(base, self.port), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, cwd=bs.REPO)
        self._on_term()
        try:
            began = self.clock()
            while True:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"le renvoi de port vers la console d'Imladris ne s'ouvre pas (ssh, code "
                                       f"{self.proc.returncode})")
                try:
                    self.connect(("127.0.0.1", self.port), timeout=2).close()
                    break
                except OSError:
                    pass
                if self.clock() - began >= self.wait_s:
                    raise RuntimeError(f"le renvoi de port vers la console d'Imladris ne répond pas en {int(self.wait_s)} s")
                self.sleep(0.5)
        except BaseException:
            self.close()
            raise
        return self.port

    def _on_term(self) -> None:
        """A SIGTERM while the forward is open: the close runs (SystemExit through `__exit__`), then
        the handler before it is put back. Only in the main thread, where Python takes signals."""
        import signal
        import threading
        self._before = None
        if threading.current_thread() is not threading.main_thread():
            return

        def stop(signum, frame):
            raise SystemExit(143)
        self._before = signal.signal(signal.SIGTERM, stop)

    def close(self) -> None:
        before, self._before = getattr(self, "_before", None), None
        if before is not None:
            import signal
            signal.signal(signal.SIGTERM, before)
        proc, self.proc = self.proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def __exit__(self, *exc) -> bool:
        self.close()
        return False


# ── the console's route ───────────────────────────────────────────────────────

def opener():
    """No proxy: the token goes to the forward on the loopback, and nowhere else."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(port: int, method: str, path: str, token: str, *, body: dict | None = None, open_=None) -> dict:
    """One request to the console through the forward: its Bearer, its JSON body, its Host. Its JSON
    answer, or {"error"} with the console's error; RuntimeError when it does not answer."""
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "Host": f"127.0.0.1:{port}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    status = 200
    try:
        with (open_ or opener().open)(req, timeout=HTTP_TIMEOUT_S) as r:
            text = r.read(MAX_ANSWER_BYTES)
            status = getattr(r, "status", 200)
    except urllib.error.HTTPError as e:
        status = e.code
        text = e.read(MAX_ANSWER_BYTES) if e.fp is not None else b""
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"la console d'Imladris ne répond pas par le renvoi de port ({type(e).__name__})") from None
    try:
        doc = json.loads(text or b"null")
    except ValueError:
        doc = None
    if not isinstance(doc, dict):
        doc = {"error": f"une réponse illisible (HTTP {status})"}
    if status >= 400:
        return {"error": str(doc.get("error") or f"HTTP {status}"), "http": status}
    return doc


def follow(port: int, request_id: str, token: str, *, open_=None, clock=time.monotonic, sleep=time.sleep,
           say=print) -> dict:
    """The receipt of a request of the queue, read until final, QUEUE_WAIT_S at most."""
    began = clock()
    said = False
    while True:
        doc = call(port, "GET", f"/api/queue/{request_id}", token, open_=open_)
        if not doc.get("pending"):
            return doc
        if not said:
            say(f"  … la demande {request_id} : {doc.get('state') or 'en attente'} — son reçu suivi, "
                f"{int(QUEUE_WAIT_S // 60)} min au plus")
            said = True
        if clock() - began >= QUEUE_WAIT_S:
            return {"state": "expired", "error": f"pas de reçu final en {int(QUEUE_WAIT_S // 60)} min"}
        sleep(QUEUE_POLL_S)


def ask_snapshot(port: int, target: str, token: str, *, open_=None, clock=time.monotonic, sleep=time.sleep,
                 say=print) -> str:
    """The 📸 route, then its receipt under FS1: the `job_id` the console gives (its own record's, or
    ''). Raises RuntimeError on every refusal."""
    doc = call(port, "POST", f"/api/action/snapshot/{target}", token, body={}, open_=open_)
    if doc.get("error"):
        raise RuntimeError(f"la console refuse l'instantané ({bs.scrub(str(doc['error']))[:200]})")
    if doc.get("via") == "queue":
        rid = str(doc.get("request") or "")
        if not _REQUEST_ID.fullmatch(rid):
            raise RuntimeError("la file d'actions ne rend pas l'identifiant de la demande")
        doc = follow(port, rid, token, open_=open_, clock=clock, sleep=sleep, say=say)
        state = str(doc.get("state") or "")
        if state in FINAL_REFUSALS or state == "expired" or not doc.get("ok") or state != "done":
            why = bs.scrub(str(doc.get("error") or doc.get("refused") or ""))[:200]
            raise RuntimeError(f"la demande d'instantané : {state or 'sans état'}" + (f" ({why})" if why else ""))
        return str(doc.get("job_id") or "")
    if doc.get("status") != "started":
        raise RuntimeError("la console ne dit pas l'instantané lancé")
    return str(doc.get("job_id") or "")


def vault_job_name(job_id: str, plan: dict) -> str:
    """The vault's job name in what the console gives, or ''. Today `action_snapshot` gives Glorfindel's
    own record, `snapshot-<vm>-<ts>` (glorfindel/jobs.py) — no job of the vault, never taken for one:
    then the job is looked for by its time. A GUID, or `rsv:<vault>/<group>/<name>` of this vault (the
    record's `snap_id`), is followed."""
    if bs.GUID.fullmatch(job_id or ""):
        return job_id
    m = re.fullmatch(r"rsv:([^/]+)/([^/]+)/([A-Za-z0-9-]{1,64})", job_id or "")
    if m and m.group(1).lower() == str(plan.get("vault") or "").lower() \
            and m.group(2).lower() == str(plan.get("vault_rg") or "").lower():
        return m.group(3)
    return ""


# ── the vault's job ───────────────────────────────────────────────────────────

def _day(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%d-%m-%Y")


def find_job(target: str, plan: dict, asked_at: float, *, clock=time.monotonic, sleep=time.sleep) -> str:
    """The vault's backup job of the VM started since the gesture: its name (never printed)."""
    began = clock()
    while True:
        jobs = bs.az_json(["backup", "job", "list", "-g", plan["vault_rg"], "-v", plan["vault"],
                           "--start-date", _day(asked_at - 86400), "--end-date", _day(asked_at + 86400)]) or []
        mine = []
        for j in jobs if isinstance(jobs, list) else []:
            p = j.get("properties") or {}
            start = bs.epoch(p.get("startTime"))
            if (str(p.get("entityFriendlyName") or "").lower() == target and str(p.get("operation") or "") == "Backup"
                    and start is not None and start >= asked_at - JOB_SKEW_S and _JOB_NAME.fullmatch(str(j.get("name") or ""))):
                mine.append((start, str(j["name"])))
        if mine:
            return min(mine)[1]
        if clock() - began >= JOB_FIND_S:
            raise RuntimeError(f"aucun job de sauvegarde de {target} lu dans le coffre depuis la demande "
                               f"({int(JOB_FIND_S // 60)} min)")
        sleep(30.0)


def await_job(name: str, plan: dict, began: float, *, clock=time.monotonic, sleep=time.sleep, say=print) -> None:
    """`az backup job show` until `Completed`, JOB_WAIT_S at most from `began` (the gesture, on `clock`)."""
    failures = 0
    said = ""
    while True:
        try:
            doc = bs.az_json(["backup", "job", "show", "-g", plan["vault_rg"], "-v", plan["vault"], "-n", name])
            status = str(((doc or {}).get("properties") or {}).get("status") or "")
            failures = 0
        except RuntimeError as e:
            failures += 1
            if failures >= JOB_READ_FAILURES:
                raise RuntimeError(f"le job du coffre ne se lit plus ({bs.scrub(str(e))[:160]})") from None
            status = ""
        if status == "Completed":
            return
        if status and status != "InProgress":
            raise RuntimeError(f"le job du coffre : {status}")
        if status and status != said:
            say(f"  … le job du coffre : {status} — suivi toutes les {int(JOB_POLL_S)} s, "
                f"{int(JOB_WAIT_S // 60)} min au plus depuis la demande")
            said = status
        if clock() - began >= JOB_WAIT_S:
            raise RuntimeError(f"le job du coffre n'est pas Completed en {int(JOB_WAIT_S // 60)} min")
        sleep(JOB_POLL_S)


def take(target: str, env: dict, plan: dict, say=print, *, token: str | None = None, tunnel=None, open_=None,
         clock=time.monotonic, sleep=time.sleep, now=time.time) -> float:
    """A new point by the 📸 route, its job followed to `Completed`; the new point's time. Raises
    RuntimeError on every refusal: the caller stops the run, nothing goes to Orodruin. `token`: the
    console's, as `make bench-run` read it and took it out of its children's environment (BNC3b review);
    else read in `env`."""
    import bench_preflight as bp
    token = (token if token is not None else env.get(TOKEN_ENV) or "").strip()
    if not token:
        raise RuntimeError(f"le jeton de la console manque ({TOKEN_ENV}, lu dans host.env par make bench-run) : "
                           "aucun point demandé")
    if not bs.VM_NAME.fullmatch(target) or not plan.get("vault"):
        raise RuntimeError("la cible ou son coffre ne se lit pas : aucun point demandé")
    asked_at, began = now(), clock()
    with (tunnel or Tunnel(env)) as port:
        say("  → la route du bouton 📸 de la console d'Imladris, par un renvoi de port court")
        given = ask_snapshot(port, target, token, open_=open_, clock=clock, sleep=sleep, say=say)
    say("  ✓ l'instantané lancé ; le renvoi de port fermé ; le job du coffre suivi")
    name = vault_job_name(given, plan) or find_job(target, plan, asked_at, clock=clock, sleep=sleep)
    await_job(name, plan, began, clock=clock, sleep=sleep, say=say)
    times = bp.point_times(target, plan["vault_rg"], plan["vault"])
    newest = max(times, default=None)
    if newest is None or (plan.get("point") is not None and newest <= plan["point"]):
        raise RuntimeError("le job est Completed, mais aucun point plus récent ne se lit dans le coffre")
    return newest
