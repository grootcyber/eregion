"""bench_shared — what `make bench-preflight` and `make bench-report` share (BNC1, #682).

- `run`: one outside command (az, ssh, terraform, docker, make), its output captured, never
  printed as it is: the two targets print only the lines they compose;
- `scrub`: the last gate before a line is printed or written. Each line already says a role (the
  console, H0, Orodruin, a human), a kind of scope or a bench name — never an id; whatever still
  looks like one (a GUID, an IPv4, a UPN, an ARM id) is masked here, by construction;
- `read_h0`: the files of H0's watch, read by ssh through scripts/bench_h0_reader.py;
- `Roles`: who a caller of the activity log is, as a role — the ids compared come from the
  operator's environment and from Terraform's outputs, read locally, never printed;
- the times and durations, written as the bench's reports write them (09/11).

Stdlib only here; the rights are read with Glorfindel's own reader (restore_rights), by the
preflight.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
READER = Path(__file__).resolve().parent / "bench_h0_reader.py"

GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
UPN = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
ARM_ID = re.compile(r"/subscriptions/[^\s'\",;()|]+", re.IGNORECASE)
# A VM name of the bench, a run id, a request id: what a command line may carry.
VM_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")

OK, WARN, FAIL = "✓", "⚠", "✗"
RUN_COMMAND_OP = "microsoft.compute/virtualmachines/runcommand/action"


def scrub(text: str) -> str:
    """The line without an id: an ARM id becomes `<ressource>`, a GUID `<id>`, an address `<ip>`,
    a user's name `<upn>`."""
    out = ARM_ID.sub("<ressource>", str(text))
    out = UPN.sub("<upn>", out)
    out = GUID.sub("<id>", out)
    return IPV4.sub("<ip>", out)


@dataclass
class Result:
    rc: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.rc == 0

    def first_error(self) -> str:
        lines = (self.err or self.out or "").strip().splitlines()
        return scrub(lines[0][:200]) if lines else f"code {self.rc}"


def run(argv: list[str], stdin: str | None = None, timeout: float = 180, env: dict | None = None) -> Result:
    """One command, its output captured. A command that can't start is a Result, not a raise."""
    try:
        res = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=timeout,
                             env=env, cwd=REPO)
    except FileNotFoundError:
        return Result(127, "", f"{argv[0]} : introuvable")
    except subprocess.TimeoutExpired:
        return Result(124, "", f"{argv[0]} : pas de réponse en {int(timeout)} s")
    return Result(res.returncode, res.stdout or "", res.stderr or "")


def az_json(args: list[str], timeout: float = 120):
    """`az … -o json`, parsed; raises RuntimeError with az's first line, masked."""
    res = run(["az", *args, "-o", "json"], timeout=timeout)
    if not res.ok:
        raise RuntimeError(res.first_error())
    try:
        return json.loads(res.out or "null")
    except ValueError as e:
        raise RuntimeError("réponse d'az illisible") from e


def tf_output(module: str, name: str) -> str:
    """`terraform -chdir=infra/<module> output -raw <name>`: '' when it can't be read."""
    res = run(["terraform", f"-chdir=infra/{module}", "output", "-no-color", "-raw", name], timeout=60)
    return res.out.strip() if res.ok else ""


def ssh_argv(var: str, env: dict | None = None) -> list[str]:
    """The ssh command the Makefile composed (`BENCH_H0_SSH`, `BENCH_ORO_SSH`), split; [] when not
    given or without a host."""
    env = os.environ if env is None else env
    words = shlex.split(env.get(var) or "")
    return words if len(words) >= 2 and words[0] == "ssh" and not words[-1].endswith("@") else []


def remote(base: list[str], command: str) -> list[str]:
    """The ssh argv for one remote command: never a prompt (BatchMode), the options before the
    host, the command last."""
    return [*base[:-1], "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", base[-1], command]


def read_h0(ask: str, vm: str, run_id: str = "", env: dict | None = None, timeout: float = 120) -> dict:
    """The watch's files on H0, through bench_h0_reader.py on the ssh's stdin. Raises RuntimeError
    when H0 can't be read (said by the caller)."""
    base = ssh_argv("BENCH_H0_SSH", env)
    if not base:
        raise RuntimeError("BENCH_H0_SSH vide : lancer par make (la commande ssh de H0 vient du Makefile)")
    if not VM_NAME.fullmatch(vm) or (run_id and not RUN_ID.fullmatch(run_id)):
        raise RuntimeError("nom de VM ou run_id invalide")
    words = ["docker", "exec", "-i", "eregion-watch", "python", "-", ask, vm, *([run_id] if run_id else [])]
    res = run(remote(base, " ".join(shlex.quote(w) for w in words)),
              stdin=READER.read_text(encoding="utf-8"), timeout=timeout)
    if not res.ok:
        raise RuntimeError(f"H0 ne répond pas par ssh ({res.first_error()})")
    try:
        doc = json.loads(res.out.strip().splitlines()[-1])
    except (ValueError, IndexError) as e:
        raise RuntimeError("la lecture de H0 n'a pas rendu de JSON") from e
    if not isinstance(doc, dict) or doc.get("error"):
        raise RuntimeError(f"la lecture de H0 a échoué ({scrub(str((doc or {}).get('error')))[:120]})")
    return doc


# ── who a caller is ───────────────────────────────────────────────────────────

ROLE_NAMES = {"console": "console", "bot": "bot", "h0": "H0", "orodruin": "Orodruin",
              "watch": "la watch du poste", "human": "un humain", "unknown": "inconnu"}
_USER_CLAIMS = ("upn", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn", "unique_name",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")


def _ids(*values) -> frozenset[str]:
    out = set()
    for v in values:
        for part in str(v or "").split(","):
            if part.strip():
                out.add(part.strip().lower())
    return frozenset(out)


@dataclass
class Roles:
    """The ids of each principal of the bench, lowercase — read locally, never printed."""
    ids: dict[str, frozenset[str]]

    @classmethod
    def from_environment(cls, env: dict | None = None, h0: str | None = None, orodruin: str | None = None) -> "Roles":
        env = os.environ if env is None else env
        h0 = tf_output("glorfindel-host", "principal_id") if h0 is None else h0
        orodruin = tf_output("orodruin", "principal_id") if orodruin is None else orodruin
        return cls({
            "console": _ids(env.get("EREGION_CONSOLE_AZURE_CLIENT_ID"), env.get("GLORFINDEL_RESTORE_PRINCIPALS")),
            "bot": _ids(env.get("GLORFINDEL_BOT_AZURE_CLIENT_ID")),
            "h0": _ids(h0),
            "orodruin": _ids(orodruin),
            "watch": _ids(env.get("GLORFINDEL_AZURE_CLIENT_ID")),
        })

    def of(self, event: dict) -> str:
        """The role of an activity-log event's caller: by `caller`, `claims.appid`, `claims.oid`."""
        claims = event.get("claims") if isinstance(event.get("claims"), dict) else {}
        seen = _ids(event.get("caller"), claims.get("appid"), claims.get("azp"), claims.get("oid"),
                    claims.get("http://schemas.microsoft.com/identity/claims/objectidentifier"))
        for role in ("console", "bot", "h0", "orodruin", "watch"):
            if seen & self.ids.get(role, frozenset()):
                return role
        if str(claims.get("idtyp") or "").lower() == "user" or any(claims.get(k) for k in _USER_CLAIMS) \
                or UPN.fullmatch(str(event.get("caller") or "")):
            return "human"
        return "unknown"


# ── times ─────────────────────────────────────────────────────────────────────

def epoch(value) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"(\.\d{6})\d+", r"\1", str(value).strip().replace("Z", "+00:00"))
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def iso(t: float | None) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat() if t is not None else ""


def hms(t: float | None, tenth: bool = False) -> str:
    """16:43:02 — or 16:43:02,8 with `tenth` when the time has one."""
    if t is None:
        return "—"
    dt = datetime.fromtimestamp(t, timezone.utc)
    out = dt.strftime("%H:%M:%S")
    d = int(round((t - int(t)) * 10))
    return f"{out},{d}" if tenth and 0 < d < 10 else out


def _number(x: float) -> str:
    """70,3 — or 152 when whole."""
    r = round(x, 1)
    return str(int(r)) if r == int(r) else f"{r:.1f}".replace(".", ",")


def duration(s: float | None) -> str:
    """70,3 s · 302 s · 15 min 17 · 4 h 24 min 23 s — the bench's way (09/11): seconds under ten
    minutes."""
    if s is None:
        return "—"
    if s < 600:
        return f"{_number(s)} s"
    total = int(round(s))
    h, rest = divmod(total, 3600)
    m, sec = divmod(rest, 60)
    if h:
        return f"{h} h {m} min {sec} s"
    return f"{m} min {sec:02d}"


def since_t0(s: float | None) -> str:
    """From T0: 70,3 s · 302 s · 15 863 s (4 h 24 min 23 s)."""
    if s is None:
        return "—"
    if s < 3600:
        return f"{_number(s)} s"
    whole = f"{int(round(s)):,}".replace(",", " ")
    return f"{whole} s ({duration(s)})"


# ── the target and its vault ──────────────────────────────────────────────────

def locate_vm(name: str) -> list[dict]:
    """Every VM of that name in the subscription (`az vm list`): [{"rg", "id"}] — one expected."""
    vms = az_json(["vm", "list", "--query", "[].{name:name, rg:resourceGroup, id:id}"]) or []
    return [{"rg": str(v.get("rg") or ""), "id": str(v.get("id") or "")}
            for v in vms if str(v.get("name") or "").lower() == name.lower()]


def local_vault(config: str) -> tuple[str, str, str]:
    """(vault, its group, the staging account) of the workstation's glorfindel-config.yaml — the
    configuration the restore reads (Glorfindel's own reader)."""
    from glorfindel.config import load_glorfindel_config
    rsv = load_glorfindel_config(config).backup_vault()
    if not rsv:
        return "", "", ""
    return rsv.vault_name or "", rsv.resource_group or "", rsv.restore_staging_storage or ""
