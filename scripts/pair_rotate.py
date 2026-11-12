#!/usr/bin/env python3
"""pair_rotate — a pair's secret turned in one command, its end noted on Imladris (ROT1, #737).

    make pair-rotate PAIR=<watch|console|bot> [DAYS=90]    a new secret, verified, in .envrc, then the old one removed
    make pair-expiry-note PAIR=<watch|console|bot>         the end in place noted on Imladris, nothing turned

Jonathan (12/11): « le plus simple possible à faire pour moi ». Before, the rotation was a
`az ad sp credential reset` whose `password` he pasted in .envrc by hand; it did not say which
pair serves where, what to restart, and it checked nothing — nor did anything remind him: the
console's secret, on its service principal (PAIR1), ends around 08/12.

`pair-rotate`, in this order, so that the service is never cut and a failure leaves all in place:
  0. refused in a code session (EREGION_AGENT_SESSION, a lot's worktree: bench_shared's rule) and
     without a terminal: it writes a secret;
  1. reads, before anything: .envrc (the pair's two lines, literal values, one each) and the
     loaded environment, which must be that .envrc (else a service would be recreated without its
     id: « source .envrc, puis relancer »); both objects of the pair as PAIR1 reads them (`az ad app
     show`, `az ad sp show`: the end dates, then the key ids of the secrets — never a secret, a
     hint, an id printed); the object that holds the valid secret is the one to turn (both, or
     neither: refused, said; an expired leftover on the other object does not count); the compose
     services that run;
  2. says what it will do — the pair, its appId masked, the object, the duration and the new end,
     the lines of .envrc, the services, the other readers — and asks « [o/N] »;
  3. adds a new secret on that object, beside the old one (`credential reset --append
     --end-date`): the old one still holds, nothing is cut — a reset without --append would cut
     every reader at once;
  4. verifies the new secret before anything else: a token of the pair (client credentials, the
     secret in the request's body, never a line), then a read of Azure Resource Manager
     (`GET /subscriptions`), retried while Entra propagates it (VERIFY_S). Refused: the new one is
     removed, the old one stays, .envrc and the services have not moved;
  5. writes .envrc: a copy of it first (0600, never over a previous one), then the file rewritten
     beside it and renamed over it, its mode kept; every line that held the old value takes the
     new one (`AZURE_CLIENT_SECRET`, when it is a copy and not `$GLORFINDEL_AZURE_CLIENT_SECRET`);
     read back. The secret goes to the file only — never to the screen, a log or an argv;
  6. recreates the compose services that read the pair and ran (`docker compose up -d --no-deps
     --force-recreate`, the new value in their environment), and reads they run again. A failure
     there: .envrc put back from its copy, the services recreated on the old value, the new
     secret removed — the old one was never touched;
  7. only then removes the old secret(s) of that object, by their key ids read in 1, then the copy
     of .envrc;
  8. reads both objects again (PAIR1), notes the nearest end on Imladris (as pair-expiry-note), and
     says the result: the pair, the object, the new end, what was recreated, verified, removed, noted.
An exception or a Ctrl-C after the new secret is asked for is caught too (`Turn`, `interrupted`):
.envrc not yet replaced, the new secret removed; replaced, .envrc put back and the service
recreated on the old one; that put-back failing, the copy kept (0600, ignored by git) and said, with
the command that restores it; past the restart, the new one stays and what is left is said.

`pair-expiry-note`: the end in place (the nearest valid, PAIR1's reading on both objects — an
object that can't be read refuses: a nearer date could be there) written on Imladris, by the
workstation's ssh, in ~/.eregion-cd/expiry/<pair>.json: the pair's name and a date, nothing else.
Imladris's CD reads it at each pass and reminds in #deploy at J-14, J-7, J-1 and on the day
(infra/glorfindel-host/cd/eregion_cd.py, « The reminders »). Refused in a code session too.

What it never does: print, log or pass in an argv a secret (az's answer is read from its pipe, the
token request goes in-process, compose takes its environment); print a client id or a key id;
touch Imladris's identity or Graph rights (nothing new: scripts/identity_map.py check); see a
rotation made outside it — `make azure-pairs-expiry` and the bench's preflight remain the net.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bench_shared as bs  # noqa: E402
import credential_expiry as ce  # noqa: E402

REPO = _HERE.parent
# The three pairs of the workstation, as credential_expiry names them: name → (id var, secret var).
PAIRS = {name: (var, var.replace("_CLIENT_ID", "_CLIENT_SECRET")) for name, var in ce.PAIRS}
# Who reads each pair, from the repository (docker-compose.yml, the Makefile, scripts/): the compose
# service this command recreates, then the readers that take the new value at their next start.
SERVICES = {"watch": "watch", "console": "war-room", "bot": "bot"}
ELSEWHERE = {
    "watch": ("une watch lancée depuis le venv (`AZURE_CLIENT_*` de .envrc) : à relancer à la main",
              "make glorfindel-shell, et la CLI du venv : la nouvelle valeur à la commande suivante "
              "(source .envrc)"),
    "console": ("un restore lancé du poste (make bench-restore, la CLI) : la nouvelle valeur à la commande "
                "suivante (source .envrc)",),
    "bot": (),
}
# The duration of a new secret, by default: 90 days, Jonathan's decision of 12/11 — its only place (the
# Makefile passes DAYS empty when unset). 365 at most.
DEFAULT_DAYS, MAX_DAYS = 90, 365
VERIFY_S, VERIFY_STEP_S = 180.0, 10.0
TOKEN_SCOPE = "https://management.azure.com/.default"
ARM_READ = "https://management.azure.com/subscriptions?api-version=2022-12-01"
BACKUP, TMP = ".envrc.pair-rotate.bak", ".envrc.pair-rotate.tmp"
HOST_ENV = Path("infra") / "glorfindel-host" / "host.env"
COMPOSE = ("docker", "compose", "--profile", "bot")
NEVER = "ne fait jamais tourner un secret ni n'en note la date, l'opérateur les tape"
YES = {"o", "oui", "y", "yes"}

# One assignment of .envrc, its value literal: single-quoted, double-quoted without `$` nor a
# backtick, or bare without any character the shell would read. Anything else is not a value.
_ASSIGN = re.compile(r"""^(?P<head>[ \t]*(?:export[ \t]+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)=)"""
                     r"""(?P<value>'[^']*'|"(?:[^"\\$`]|\\.)*"|[^\s'"#;&|<>()$`\\]*)(?P<tail>[ \t]*(?:#.*)?)$""")


class Refused(Exception):
    """Said, nothing written."""


@dataclass
class Ctx:
    env: dict
    root: Path = REPO
    envrc: Path | None = None
    host_env: Path | None = None
    az: str = "az"
    ssh: str = ""                       # the command that reaches Imladris (make passes it), or ""
    http: object = None
    ask: object = None
    say: object = print
    now: datetime | None = None
    sleep: object = time.sleep
    verify_s: float = VERIFY_S
    step_s: float = VERIFY_STEP_S
    tty: bool | None = None
    cwd: Path | None = None
    here: Path | None = None

    def __post_init__(self):
        # az by its path, found on the PATH this command is given (PAIR1's reading runs it as named).
        self.az = shutil.which(self.az, path=self.env.get("PATH")) or self.az
        self.envrc = self.envrc or self.root / ".envrc"
        self.host_env = self.host_env or self.root / HOST_ENV
        self.now = self.now or datetime.now(timezone.utc)
        self.http = self.http or http
        self.ask = self.ask or input


def run(argv: list[str], env: dict, stdin: str | None = None, cwd: Path | None = None,
        timeout: float = 120) -> bs.Result:
    """One outside command, its output captured, never printed as it is."""
    try:
        res = subprocess.run(argv, capture_output=True, text=True, env=env, input=stdin, cwd=cwd, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return bs.Result(127, "", type(e).__name__)
    return bs.Result(res.returncode, res.stdout or "", res.stderr or "")


def _error(res: bs.Result) -> str:
    return bs.scrub(res.first_error())[:200]


def masked(app_id: str) -> str:
    return f"…{app_id[-4:]}" if len(app_id) > 4 else "…"


def http(method: str, url: str, data: dict | None = None, headers: dict | None = None,
         timeout: float = 30) -> tuple[int, dict]:
    """(status, JSON) — the form `data` in the request's body; never raises, never quotes a URL."""
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": "eregion-pair-rotate", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            doc = json.loads(raw) if raw else {}
            return r.status, doc if isinstance(doc, dict) else {}
    except urllib.error.HTTPError as e:
        try:
            doc = json.loads(e.read() or b"{}")
        except ValueError:
            doc = {}
        return e.code, doc if isinstance(doc, dict) else {}
    except Exception as e:  # noqa: BLE001 — the network: said by its name, never its text
        return 0, {"error": type(e).__name__}


# ── .envrc ───────────────────────────────────────────────────────────────────────────

def _assigning(line: str, name: str) -> bool:
    return re.match(rf"[ \t]*(?:export[ \t]+)?{re.escape(name)}=", line) is not None


def literal(line: str) -> str | None:
    """The literal value of an assignment line, or None when it is not one (a `$`, a command)."""
    m = _ASSIGN.match(line.rstrip("\r\n"))
    if not m:
        return None
    v = m.group("value")
    if v[:1] == "'":
        return v[1:-1]
    if v[:1] == '"':
        return re.sub(r"\\(.)", r"\1", v[1:-1])
    return v


def rewritten(line: str, value: str) -> str:
    m = _ASSIGN.match(line.rstrip("\r\n"))
    end = line[len(line.rstrip("\r\n")):]
    return m.group("head") + shlex.quote(value) + m.group("tail") + end


def the_line(lines: list[str], name: str) -> tuple[int, str]:
    """The one active assignment of `name` in .envrc, and its literal value."""
    found = [i for i, ln in enumerate(lines) if _assigning(ln, name)]
    if not found:
        raise Refused(f"{name} n'est posée par aucune ligne de .envrc : je ne sais pas où écrire")
    if len(found) > 1:
        raise Refused(f"{name} est posée par {len(found)} lignes de .envrc : une seule attendue")
    value = literal(lines[found[0]])
    if not value:
        raise Refused(f"{name} n'a pas une valeur écrite dans .envrc (une référence, une commande, ou vide) : "
                      "je ne sais pas où écrire")
    return found[0], value


def pair_id(lines: list[str], env: dict, var: str) -> str:
    """The pair's appId: its .envrc line (a literal GUID), checked against the loaded environment."""
    found = [i for i, ln in enumerate(lines) if _assigning(ln, var)]
    written = literal(lines[found[0]]) if len(found) == 1 else None
    loaded = (env.get(var) or "").strip()
    app_id = written or loaded
    if not app_id:
        raise Refused(f"{var} vide : aucune paire à faire tourner")
    if not bs.GUID.fullmatch(app_id):
        raise Refused(f"{var} n'est pas un appId (un GUID)")
    if written and loaded and written != loaded:
        raise Refused(f"{var} : l'environnement chargé n'est pas celui de .envrc (source .envrc, puis relancer)")
    return app_id


def write_atomic(path: Path, text: str, mode: int) -> None:
    """`text` beside `path` (created 0600, never over a file left there), then its mode, then renamed over it."""
    tmp = path.with_name(TMP)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            os.fchmod(fd, mode)
            os.write(fd, text.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def keep_copy(path: Path, text: str) -> Path:
    copy = path.with_name(BACKUP)
    fd = os.open(copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return copy


# ── Azure ────────────────────────────────────────────────────────────────────────────

def key_ids(app_id: str, obj: str, ctx: Ctx) -> list[str]:
    """The key ids of one object's secrets (`passwordCredentials`), never anything else of them."""
    res = run([ctx.az, "ad", obj, "show", "--id", app_id, "--query", "passwordCredentials[].keyId", "-o", "json"],
              ctx.env)
    if not res.ok:
        raise RuntimeError(_error(res) or f"az a rendu {res.rc}")
    try:
        keys = json.loads(res.out)
    except ValueError:
        raise RuntimeError("réponse d'az illisible") from None
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise RuntimeError("réponse d'az inattendue (une liste attendue)")
    return keys


def connects(tenant: str, client_id: str, secret: str, ctx: Ctx) -> tuple[bool, str]:
    """A token of the pair, then a read of Azure Resource Manager under it. The secret goes in the
    request's body only."""
    if not bs.GUID.fullmatch(tenant or ""):
        return False, "le tenant ne se lit pas (ni dans la réponse d'az ni dans AZURE_TENANT_ID)"
    code, doc = ctx.http("POST", f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                         {"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret,
                          "scope": TOKEN_SCOPE})
    token = doc.get("access_token") if code == 200 else None
    if not token:
        said = re.sub(r"[^A-Za-z0-9_]", "", str(doc.get("error") or ""))[:40]
        return False, f"jeton refusé (HTTP {code}{' ' + said if said else ''})"
    code, _ = ctx.http("GET", ARM_READ, None, {"Authorization": f"Bearer {token}"})
    if code != 200:
        return False, f"lecture d'Azure Resource Manager refusée (HTTP {code})"
    return True, ""


def verify(tenant: str, client_id: str, secret: str, ctx: Ctx) -> tuple[bool, str]:
    """`connects`, tried again every step_s while Entra propagates the new secret, verify_s at most."""
    tries = 1 + int(max(0.0, ctx.verify_s) // max(ctx.step_s, 0.001))
    why = ""
    for i in range(tries):
        ok, why = connects(tenant, client_id, secret, ctx)
        if ok:
            return True, ""
        if i < tries - 1:
            ctx.sleep(ctx.step_s)
    return False, why


def remove_keys(app_id: str, obj: str, keys, ctx: Ctx) -> list[str]:
    """Each key removed from the object; the ones that would not go, by their count only."""
    left = []
    for key in keys:
        if not run([ctx.az, "ad", obj, "credential", "delete", "--id", app_id, "--key-id", key], ctx.env).ok:
            left.append(key)
    return left


def nearest(app_id: str, ctx: Ctx) -> tuple[ce.Credential | None, list[ce.Credential]]:
    """PAIR1's reading on both objects: the nearest valid end, and every valid one. Raises when an
    object can't be read — never read as « aucun »."""
    found: list[ce.Credential] = []
    for obj, where in ce.OBJECTS:
        try:
            found += ce.credentials(app_id, obj, ctx.az)
        except Exception as e:  # noqa: BLE001
            raise Refused(f"date de fin illisible sur {where} ({bs.scrub(str(e))[:160]}) : "
                          "une date plus proche peut s'y trouver") from None
    valid = sorted((c for c in found if c.end >= ctx.now), key=lambda c: c.end)
    return (valid[0] if valid else None), valid


# ── compose ──────────────────────────────────────────────────────────────────────────

def running(ctx: Ctx) -> tuple[set[str], str]:
    """The compose services that run, and why none could be read ('' when read)."""
    res = run([*COMPOSE, "ps", "--status", "running", "--services"], ctx.env, cwd=ctx.root)
    if not res.ok:
        return set(), "docker compose ne répond pas (aucun conteneur lu)"
    return {s.strip() for s in res.out.splitlines() if s.strip()}, ""


def recreate(service: str, env: dict, ctx: Ctx) -> bool:
    """The service recreated with `env` — the pair's value in its environment, never on a line —,
    then read running again."""
    if not run([*COMPOSE, "up", "-d", "--no-deps", "--force-recreate", service], env, cwd=ctx.root, timeout=600).ok:
        return False
    again, _ = running(ctx)
    return service in again


# ── Imladris ─────────────────────────────────────────────────────────────────────────

def note_on_imladris(pair: str, end: datetime, ctx: Ctx, by: str) -> tuple[bool, list[str]]:
    """The end written on Imladris (~/.eregion-cd/expiry/<pair>.json, 0600, by stdin), then what its
    CD says of its reminders. A date and a pair's name: nothing else leaves the workstation."""
    again = f"make pair-expiry-note PAIR={pair}"
    if not ctx.ssh:
        return False, [f"⚠ Imladris : injoignable d'ici (pas d'adresse, ou sa clé d'hôte refusée : make "
                       f"glorfindel-host-known) — la date n'est pas notée, aucun rappel ; ensuite {again}"]
    payload = json.dumps({"pair": pair, "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "noted_at": ctx.now.strftime("%Y-%m-%dT%H:%M:%SZ"), "by": by})
    tmp, final = f".eregion-cd/expiry/.{pair}.json.tmp", f".eregion-cd/expiry/{pair}.json"
    remote = (f"umask 077 && {{ test -d .eregion-cd || exit 3; }} && mkdir -p .eregion-cd/expiry && "
              f"cat > {tmp} && mv -f {tmp} {final} && python3 .eregion-cd/eregion_cd.py reminders")
    res = run([*shlex.split(ctx.ssh), remote], ctx.env, stdin=payload + "\n", timeout=60)
    if res.rc == 3:
        return False, ["✗ Imladris : son CD n'est pas installé (~/.eregion-cd absent : make glorfindel-host-cd-install) "
                       f"— aucun rappel ; ensuite {again}"]
    if res.rc == 2:
        return False, ["⚠ Imladris : la date est notée, mais l'agent de son CD ne connaît pas encore les rappels "
                       "(une version d'avant ROT1) : make glorfindel-host-cd-install, depuis un checkout de main à jour"]
    if not res.ok:
        return False, [f"✗ Imladris : la date n'est pas notée ({_error(res) or f'ssh a rendu {res.rc}'}) ; ensuite {again}"]
    said = [bs.scrub(ln) for ln in res.out.splitlines() if ln.lstrip().startswith("rappels") and f" {pair} " in ln]
    return True, [f"✓ Imladris : fin le {end:%Y-%m-%d} notée ; son CD rappelle dans #deploy à J-14, J-7, J-1 et le "
                  "jour même"] + said


# ── the commands ─────────────────────────────────────────────────────────────────────

def refusal(target: str, ctx: Ctx, need_tty: bool) -> str:
    why = bs.session_refusal(ctx.env, ctx.cwd, ctx.here, never=NEVER)
    if why:
        return f"✗ make {target} refusé : {why}. Rien n'est lu, rien n'est écrit."
    tty = ctx.tty if ctx.tty is not None else (sys.stdin.isatty() and sys.stdout.isatty())
    if need_tty and not tty:
        return (f"✗ make {target} refusé : sans terminal. La commande écrit un secret et demande ton accord : "
                "à taper toi-même, dans ton terminal. Rien n'est lu, rien n'est écrit.")
    return ""


def _pair(pair: str) -> tuple[str, str]:
    if pair not in PAIRS:
        raise Refused(f"PAIR={pair or '…'} : une de {', '.join(PAIRS)} attendue (make pair-rotate PAIR=console)")
    return PAIRS[pair]


def note(pair: str, ctx: Ctx) -> int:
    say = ctx.say
    why = refusal("pair-expiry-note", ctx, need_tty=False)
    if why:
        say(why)
        return 1
    try:
        id_var, _ = _pair(pair)
        lines = ctx.envrc.read_text(encoding="utf-8").splitlines(True) if ctx.envrc.exists() else []
        app_id = pair_id(lines, ctx.env, id_var)
        first, valid = nearest(app_id, ctx)
        if not first:
            raise Refused(f"aucun secret valable sur la paire « {pair} » : la faire tourner (make pair-rotate PAIR={pair})")
    except Refused as e:
        say(f"✗ {pair} : {e}")
        return 1
    say(f"✓ {pair} : {first.kind} valable jusqu'au {first.end:%Y-%m-%d}, sur {ce._where(first.obj)}"
        + (f" ({len(valid)} valables : la plus proche est notée)" if len(valid) > 1 else ""))
    ok, said = note_on_imladris(pair, first.end, ctx, "pair-expiry-note")
    for line in said:
        say(line)
    return 0 if ok else 1


def rotate(pair: str, days: int, ctx: Ctx) -> int:
    say = ctx.say
    why = refusal("pair-rotate", ctx, need_tty=True)
    if why:
        say(why)
        return 1
    try:
        return _rotate(pair, days, ctx)
    except Refused as e:
        say(f"✗ {pair or 'pair-rotate'} : {e}")
        return 1


def _rotate(pair: str, days: int, ctx: Ctx) -> int:
    say, env = ctx.say, ctx.env
    id_var, secret_var = _pair(pair)
    if not 1 <= days <= MAX_DAYS:
        raise Refused(f"DAYS={days} : de 1 à {MAX_DAYS} jours")
    envrc = ctx.envrc
    if envrc.with_name(BACKUP).exists() or envrc.with_name(TMP).exists():
        raise Refused(f"{BACKUP} (ou {TMP}) reste d'une rotation interrompue, à côté de .envrc : comparer, garder le "
                      "bon .envrc, retirer la copie (elle tient un secret), puis relancer")
    if not envrc.is_file():
        raise Refused(".envrc absent : la paire ne s'y lit pas")
    text = envrc.read_text(encoding="utf-8")
    mode = envrc.stat().st_mode & 0o777
    lines = text.splitlines(True)
    app_id = pair_id(lines, env, id_var)
    _, old = the_line(lines, secret_var)
    # The loaded environment must be this .envrc: compose recreates the service from it, and a pair
    # missing there would restart it without its id — then its old secret removed.
    if (env.get(id_var) or "").strip() != app_id or (env.get(secret_var) or "") != old:
        raise Refused(f"l'environnement chargé n'est pas celui de .envrc ({id_var} ou {secret_var} absent ou "
                      "différent) : source .envrc, puis relancer")
    # Every line that holds the old value as written (AZURE_CLIENT_SECRET, when it is a copy).
    copies = [i for i, ln in enumerate(lines) if literal(ln) == old and _ASSIGN.match(ln.rstrip("\r\n"))]
    names = [_ASSIGN.match(lines[i].rstrip("\r\n")).group("name") for i in copies]
    if ctx.host_env.is_file() and old in ctx.host_env.read_text(encoding="utf-8"):
        raise Refused("infra/glorfindel-host/host.env tient ce secret : Imladris n'en porte jamais (son identité "
                      "managée, host_env.py) — le retirer de host.env d'abord, sinon son retrait couperait Imladris")

    # Both objects, as PAIR1 reads them; the one that holds the secret is the one turned.
    held: dict[str, list[ce.Credential]] = {}
    keys: dict[str, list[str]] = {}
    for obj, where in ce.OBJECTS:
        try:
            held[obj] = [c for c in ce.credentials(app_id, obj, ctx.az) if c.kind == "secret"]
            keys[obj] = key_ids(app_id, obj, ctx)
        except Exception as e:  # noqa: BLE001 — never read as « aucun »
            raise Refused(f"{where} ne se lit pas ({bs.scrub(str(e))[:160]}) : rien n'est fait") from None
    # The object that holds a valid secret; none valid (a pair already expired): the one holding any.
    holders = [obj for obj, _ in ce.OBJECTS if any(c.end >= ctx.now for c in held[obj])] \
        or [obj for obj, _ in ce.OBJECTS if keys[obj]]
    if len(holders) > 1:
        raise Refused("des secrets valables sur son application et sur son principal de service : celui de .envrc "
                      "ne se distingue pas — make azure-pairs-expiry dit leurs dates ; retirer les anciens, puis relancer")
    if not holders or not keys[holders[0]]:
        raise Refused("aucun secret, ni sur son application ni sur son principal de service : rien à faire tourner")
    obj = holders[0]
    where, before = ce._where(obj), keys[obj]
    current = sorted(held[obj], key=lambda c: c.end)
    end = (ctx.now + timedelta(days=days)).replace(microsecond=0)
    service = SERVICES[pair]
    up, docker_why = running(ctx)
    restart = [service] if service in up else []

    say(f"Rotation du secret de la paire « {pair} » ({id_var[:-len('_CLIENT_ID')]}_CLIENT_*)")
    say(f"  appId          {masked(app_id)} (masqué)")
    say(f"  le secret vit  sur {where} : {len(before)} secret(s)"
        + (f", fin le {current[0].end:%Y-%m-%d}" if current else ""))
    say(f"  le nouveau     ajouté à côté de l'ancien (--append) sur {where}, pour {days} jours : fin le {end:%Y-%m-%d}")
    say("  vérifié        avant tout le reste : un jeton de la paire, puis une lecture d'Azure Resource Manager")
    say(f"  .envrc         {', '.join(names)} réécrite(s), ses droits gardés (copie de secours 0600, retirée une fois l'ancien secret retiré)")
    say(f"  relancé        {service} (docker compose)" if restart else
        f"  relancé        rien : {service} ne tourne pas{' — ' + docker_why if docker_why else ''}")
    for other in ELSEWHERE[pair]:
        say(f"  ailleurs       {other}")
    say(f"  puis retiré    l'ancien secret ({len(before)}), seulement une fois le nouveau vérifié et "
        + ("le service relancé" if restart else ".envrc réécrite"))
    say("  Imladris       la date de fin notée : rappels à J-14, J-7, J-1 et le jour même dans #deploy"
        if ctx.ssh else "  Imladris       injoignable d'ici : la date ne sera pas notée (make pair-expiry-note ensuite)")
    try:
        answer = str(ctx.ask("Continuer ? [o/N] ") or "").strip().lower()
    except EOFError:
        answer = ""
    if answer not in YES:
        say("Rien n'est fait.")
        return 1

    t = Turn(pair=pair, obj=obj, where=where, app_id=app_id, before=before, end=end, text=text, mode=mode,
             lines=lines, copies=copies, names=names, restart=restart, old=old, secret_var=secret_var)
    try:
        return turn(t, ctx)
    except BaseException as e:  # noqa: BLE001 — an OSError, a Ctrl-C: what is in place said, never a traceback
        return interrupted(t, ctx, e)


@dataclass
class Turn:
    """One rotation, once agreed: what it knows, and how far it went — said on any failure."""
    pair: str
    obj: str
    where: str
    app_id: str
    before: list
    end: datetime
    text: str
    mode: int
    lines: list
    copies: list
    names: list
    restart: list
    old: str
    secret_var: str
    new: str = ""
    added: list | None = None        # the new secret's key ids (None: not read yet)
    unread: bool = False             # the key ids could not be read: the new one is unknown
    copy: Path | None = None         # .envrc's copy, while it exists
    replaced: bool = False           # .envrc holds the new value
    committed: bool = False          # the services run on it: no way back, only forward
    step: str = "l'ajout du nouveau secret"


def _added(t: Turn, ctx: Ctx) -> list[str]:
    if t.added is None:
        try:
            t.added = [k for k in key_ids(t.app_id, t.obj, ctx) if k not in t.before]
        except Exception:  # noqa: BLE001 — the new one then unknown: only the old ones are ever removed
            t.added, t.unread = [], True
    return t.added


def undo_new(t: Turn, ctx: Ctx) -> str:
    """The new secret removed, by the key ids that were not there before; what is left, said."""
    added = _added(t, ctx)
    if added and not remove_keys(t.app_id, t.obj, added, ctx):
        return "le nouveau secret retiré"
    if not added and not t.unread:
        return "aucun nouveau secret sur Azure"
    return (f"le nouveau secret à retirer à la main (az ad {t.obj} credential list --id <appId> : celui qui finit "
            f"le {t.end:%Y-%m-%d})")


def put_back(t: Turn, ctx: Ctx, step: str) -> int:
    """.envrc from before, the services recreated on the old secret, the new one removed. Raises
    when .envrc can't be written back: the caller keeps the copy and says it."""
    write_atomic(ctx.envrc, t.text, t.mode)
    t.replaced = False
    back = [s for s in t.restart if not recreate(s, ctx.env, ctx)]
    if t.copy:
        t.copy.unlink(missing_ok=True)
        t.copy = None
    ctx.say(f"✗ {t.pair} : {step} ; .envrc remise comme avant"
            + (f", {', '.join(t.restart)} relancé(s) sur l'ancien secret" if t.restart and not back else "")
            + (f" — ⚠ {', '.join(back)} ne repart pas : make glorfindel-restart" if back else "")
            + f" ; {undo_new(t, ctx)} ; l'ancien reste")
    return 1


def interrupted(t: Turn, ctx: Ctx, e: BaseException) -> int:
    """An exception or a Ctrl-C after the new secret was asked for: everything put back that can be,
    and what is in place said."""
    what = "interrompue (Ctrl-C)" if isinstance(e, KeyboardInterrupt) else f"arrêtée ({type(e).__name__})"
    pair, say = t.pair, ctx.say
    if t.committed:
        if t.copy:
            t.copy.unlink(missing_ok=True)
        say(f"✗ {pair} : rotation {what} pendant {t.step} ; le nouveau secret est en place (.envrc"
            + (f", {', '.join(t.restart)}" if t.restart else "") + ") ; un ancien peut rester valable : make "
            f"azure-pairs-expiry, puis az ad {t.obj} credential delete")
        return 1
    replaced = t.replaced
    if not replaced and t.copy:
        try:     # renamed over it, but stopped before it was said
            replaced = ctx.envrc.read_text(encoding="utf-8") != t.text
        except OSError:
            replaced = True
    if replaced:
        try:
            return put_back(t, ctx, f"rotation {what} pendant {t.step}")
        except BaseException as e2:  # noqa: BLE001
            say(f"✗ {pair} : rotation {what} pendant {t.step}, puis .envrc ne se remet pas ({type(e2).__name__}) : "
                f"l'ancien .envrc est dans {BACKUP} (0600, ignoré par git, il tient les secrets) — cp -p {BACKUP} "
                f".envrc, puis rm {BACKUP} ; l'ancien secret reste valable ; le nouveau : make azure-pairs-expiry")
            return 1
    try:
        undone = undo_new(t, ctx)
    except BaseException:  # noqa: BLE001
        undone = (f"le nouveau secret à retirer à la main (az ad {t.obj} credential list --id <appId> : celui qui "
                  f"finit le {t.end:%Y-%m-%d})")
    if t.copy:
        t.copy.unlink(missing_ok=True)
    say(f"✗ {pair} : rotation {what} pendant {t.step} ; .envrc et les services n'ont pas bougé ; {undone} ; "
        "l'ancien reste")
    return 1


def turn(t: Turn, ctx: Ctx) -> int:
    say, env, pair, obj, app_id = ctx.say, ctx.env, t.pair, t.obj, t.app_id
    # 3. The new secret, beside the old one: nothing is cut. Its answer read from its pipe; on a
    #    failure, only az's error output is said — its standard output may hold a password.
    res = run([ctx.az, "ad", obj, "credential", "reset", "--id", app_id, "--append",
               "--end-date", t.end.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "--display-name", f"eregion-{pair}-{ctx.now:%Y%m%d}", "-o", "json"], env)
    try:
        answer_doc = json.loads(res.out) if res.ok else {}
    except ValueError:
        answer_doc = {}
    t.new = str(answer_doc.get("password") or "") if isinstance(answer_doc, dict) else ""
    if not t.new:
        said = bs.scrub(bs.Result(res.rc, "", res.err).first_error())[:200]
        say(f"✗ {pair} : az n'a pas rendu de nouveau secret ({said or f'az a rendu {res.rc}'}) ; {undo_new(t, ctx)} ; "
            "l'ancien reste, .envrc et les services n'ont pas bougé (make azure-pairs-expiry le confirme)")
        return 1
    new = t.new
    tenant = str(answer_doc.get("tenant") or env.get("AZURE_TENANT_ID") or "")
    _added(t, ctx)

    # 4. Verified before anything else.
    t.step = "la vérification du nouveau secret"
    ok, why = verify(tenant, app_id, new, ctx)
    if not ok:
        say(f"✗ {pair} : le nouveau secret ne se connecte pas ({why}) ; {undo_new(t, ctx)} ; l'ancien reste, .envrc et "
            "les services n'ont pas bougé")
        return 1
    say(f"✓ {pair} : le nouveau secret se connecte (un jeton, puis une lecture d'Azure Resource Manager)")

    # 5. .envrc: its copy first, then rewritten beside it and renamed over it, its mode kept.
    t.step = "l'écriture de .envrc"
    t.copy = keep_copy(ctx.envrc, t.text)
    new_lines = list(t.lines)
    for i in t.copies:
        new_lines[i] = rewritten(t.lines[i], new)
    new_env = {k: (new if v == t.old else v) for k, v in env.items()}
    new_env.update({name: new for name in t.names})
    write_atomic(ctx.envrc, "".join(new_lines), t.mode)
    t.replaced = True
    reread = ctx.envrc.read_text(encoding="utf-8").splitlines(True)
    if len(reread) != len(t.lines) or [literal(reread[i]) for i in t.copies] != [new] * len(t.copies):
        return put_back(t, ctx, ".envrc ne se relit pas comme écrite")

    # 6. What reads the pair, recreated on the new value.
    t.step = "la relance"
    for s in t.restart:
        if not recreate(s, new_env, ctx):
            return put_back(t, ctx, f"{s} ne repart pas sur le nouveau secret")
    if t.restart:
        say(f"✓ {pair} : {', '.join(t.restart)} relancé(s) sur le nouveau secret")
    t.committed = True

    # 7. Only now, the old one(s); then the copy of .envrc.
    t.step = "le retrait de l'ancien secret"
    left = remove_keys(app_id, obj, t.before, ctx)
    if left:
        say(f"⚠ {pair} : {len(left)} ancien(s) secret(s) ne se retire(nt) pas — toujours valable(s) ; à retirer : "
            f"az ad {obj} credential list --id <appId>, puis az ad {obj} credential delete (make azure-pairs-expiry dit leurs dates)")
    else:
        say(f"✓ {pair} : l'ancien secret retiré de {t.where} ({len(t.before)})")
    t.copy.unlink()
    t.copy = None

    # 8. Read again, as PAIR1 reads it, and noted on Imladris.
    t.step = "la relecture et la note sur Imladris"
    try:
        first, valid = nearest(app_id, ctx)
    except Refused as e:
        say(f"⚠ {pair} : relecture : {e} ; la date n'est pas notée (make pair-expiry-note PAIR={pair} ensuite)")
        return 1
    secrets = [c for c in valid if c.kind == "secret"]     # a certificate beside it is not a second secret
    if not first or not secrets:
        say(f"✗ {pair} : aucun secret valable relu — make azure-pairs-expiry")
        return 1
    say(f"✓ {pair} : {len(secrets)} secret(s) valable(s), le plus proche jusqu'au {secrets[0].end:%Y-%m-%d} sur "
        f"{ce._where(secrets[0].obj)}" + ("" if len(secrets) == 1 else " — un seul attendu (make azure-pairs-expiry)"))
    noted, said = note_on_imladris(pair, first.end, ctx, "pair-rotate")
    for line in said:
        say(line)
    if t.names != [t.secret_var]:
        say(f"ℹ .envrc : {', '.join(n for n in t.names if n != t.secret_var)} tenai(en)t la même valeur : "
            "réécrite(s) aussi")
    say("ℹ ton shell garde l'ancienne valeur : source .envrc (ou direnv allow)")
    return 0 if not left and noted and len(secrets) == 1 else 1


def main(argv: list[str] | None = None, ctx: Ctx | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("guard", help="the refusal of a code session, alone (make runs it first)")
    g.add_argument("target")
    r = sub.add_parser("rotate")
    r.add_argument("pair", nargs="?", default="")
    r.add_argument("--days", default=str(DEFAULT_DAYS))
    n = sub.add_parser("note")
    n.add_argument("pair", nargs="?", default="")
    args = p.parse_args(argv)
    ctx = ctx or Ctx(env=dict(os.environ), ssh=os.environ.get("EREGION_HOST_SSH", ""))
    if args.cmd == "guard":
        why = refusal(args.target, ctx, need_tty=False)
        if why:
            print(why, file=sys.stderr)
        return 1 if why else 0
    if args.cmd == "note":
        return note(args.pair, ctx)
    try:
        days = int(args.days) if args.days.strip() else DEFAULT_DAYS     # make passes DAYS, empty when unset
    except ValueError:
        ctx.say(f"✗ DAYS={args.days} : un nombre de jours attendu")
        return 1
    return rotate(args.pair, days, ctx)


if __name__ == "__main__":
    sys.exit(main())
