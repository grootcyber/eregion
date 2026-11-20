#!/usr/bin/env python3
"""console_rotate — the console token of Imladris turned in one command, its reminder noted (ROT2, #968).

    make imladris-console-rotate [DAYS=90]        a new token in host.env, pushed, the console alone
                                                  restarted, the new one accepted and the old one refused
    make imladris-console-token-note [DAYS=90]    the token in place noted on Imladris, nothing turned

Before, the console of Imladris read EREGION_CONSOLE_TOKEN from host.env, drawn once by
`make imladris-env` (which never overwrites a host.env, so that the token never changes), and
`make console-rotate` refuses a token the deployment sets (SEC10): nothing ever turned it. It stayed
in the browser's history and the terminal's, the phone's included.

`imladris-console-rotate`, in this order:
  0. refused in a code session (EREGION_AGENT_SESSION, a lot's worktree: bench_shared's rule), and
     without Imladris within reach (no address, or its host key refused: make imladris-known) —
     nothing drawn;
  1. reads host.env: missing, unreadable or without a console token (EREGION_CONSOLE_TOKEN, or its
     former name GLORFINDEL_WARROOM_TOKEN, the console's rule) — refused, nothing written;
  2. draws a new token (the form `make imladris-env` draws) and writes host.env
     beside it, 0600, then checks it as `make imladris-push` will (host_env.py --check), then renames
     it over the old one: atomic, never a half-written file. Only the token's line changes: it takes
     the new token under EREGION_CONSOLE_TOKEN, at its place; any other line of either name (the
     former name beside the new, an earlier line of the same key) is removed — it held a token no
     longer in use. Every other line stays to the byte;
  3. pushes it by the existing path, `make imladris-push` (host.env → ~/eregion/.env, and the config);
  4. restarts the console alone (`docker compose up -d --no-deps --force-recreate war-room`), so that
     it reads its environment again; the watch and the bot do not move;
  5. checks it as `make imladris-status` probes the console — curl on Imladris, the token on its
     standard input, never on a command line: the new one answers, the old one is refused (401);
  6. notes on Imladris the day to turn it again, the draw + DAYS (90 by default), under its own name,
     « console-token », by ROT1's path (~/.eregion-cd/expiry/console-token.json: a name and a date),
     whose CD reminds in #deploy at J-14, J-7, J-1 and on the day.

A failure says what is in place. Refused before 2: nothing written. After 2, host.env holds the new
token, coherent, on the workstation: a push or a restart that fails leaves the console of Imladris on
the old token; typing the command again draws another one and pushes it the same way.

`imladris-console-token-note`: the token in place, noted on Imladris as drawn today (+ DAYS) —
Imladris cannot read when it was drawn. Refused in a code session too.

What it never does: print the token, put it in an argv (ssh, curl), log it; `make imladris-url`
reads it from host.env. Stdlib only.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import secrets
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bench_shared as bs  # noqa: E402
import pair_rotate as pr  # noqa: E402

REPO = _HERE.parent
HOST_ENV = Path("infra") / "glorfindel-host" / "host.env"
TMP = ".host.env.console-rotate.tmp"
# Its name on Imladris, beside the three pairs (infra/glorfindel-host/cd/eregion_cd.py, REMIND_PAIRS).
NAME = "console-token"
ROTATE, NOTE = "imladris-console-rotate", "imladris-console-token-note"
# The day to turn it again, by default: 90 days, as the pairs (ROT1) — its only place. 365 at most.
DEFAULT_DAYS, MAX_DAYS = 90, 365
NEVER = "ne fait jamais tourner le jeton de la console ni n'en note la date, l'opérateur les tape"
# The console of Imladris, behind its loopback (docker-compose.yml: 127.0.0.1:7007), probed as status.sh does.
PROBE_PATH = "/api/to-judge?since=7d"
RESTART = "cd eregion && docker compose up -d --no-deps --force-recreate war-room"
# On Imladris: the two tokens read from stdin, never on a line; the new one waited for while the
# console starts (up to 60 s), then the old one; one line, `new=<code> old=<code>`.
PROBE = (
    "read -r new; read -r old; "
    "code() { printf 'Authorization: Bearer %s\\n' \"$1\" | curl -s -o /dev/null -w '%{http_code}' "
    f"-H @- 'http://127.0.0.1:7007{PROBE_PATH}'; }}; "
    "n=$(code \"$new\"); i=0; "
    "while [ \"$n\" != 200 ] && [ $i -lt 30 ]; do sleep 2; i=$((i+1)); n=$(code \"$new\"); done; "
    "o=$(code \"$old\"); echo \"new=$n old=$o\""
)


class Refused(Exception):
    """Said, nothing written."""


@dataclass
class Ctx:
    env: dict
    root: Path = REPO
    host_env: Path | None = None
    ssh: str = ""                 # the command that reaches Imladris (make passes it), or ""
    push: str = ""                # the existing path: `make imladris-push` (make passes it)
    say: object = print
    now: datetime | None = None
    cwd: Path | None = None
    here: Path | None = None

    def __post_init__(self):
        self.host_env = self.host_env or self.root / HOST_ENV
        self.now = self.now or datetime.now(timezone.utc)


def _host_env_module():
    """infra/glorfindel-host/host_env.py, its rules: how compose reads a host.env, the token's names,
    its form, the check `make imladris-push` runs."""
    path = REPO / "infra" / "glorfindel-host" / "host_env.py"
    spec = importlib.util.spec_from_file_location("host_env_console_rotate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


he = _host_env_module()


def draw_token() -> str:
    """A console token in the form `make imladris-env` draws it (host_env.py, `host_env`)."""
    return secrets.token_urlsafe(24)


def refusal(target: str, ctx: Ctx) -> str:
    why = bs.session_refusal(ctx.env, ctx.cwd, ctx.here, never=NEVER)
    if why:
        return f"✗ make {target} refusé : {why}. Rien n'est lu, rien n'est écrit."
    return ""


def _days(raw: str) -> int:
    try:
        days = int(raw) if str(raw).strip() else DEFAULT_DAYS     # make passes DAYS, empty when unset
    except ValueError:
        raise Refused(f"DAYS={raw} : un nombre de jours attendu") from None
    if not 1 <= days <= MAX_DAYS:
        raise Refused(f"DAYS={days} : de 1 à {MAX_DAYS} jours")
    return days


def _key(line: str) -> str:
    """The variable a line of host.env assigns, as compose reads it (host_env.read_env), or ""."""
    if line.strip() and not line.lstrip().startswith("#") and "=" in line:
        return line.split("=", 1)[0].strip()
    return ""


def read_token(path: Path) -> tuple[str, str, str]:
    """(its text, the name that carries the token, the token) — refused when host.env is missing,
    unreadable, or carries no token: nothing is drawn then."""
    if not path.is_file():
        raise Refused(f"{HOST_ENV} manquant (make imladris-env) : aucun jeton à faire tourner")
    try:
        text = path.read_bytes().decode("utf-8")     # never read_text: it would turn a CRLF into a LF
    except (OSError, UnicodeDecodeError) as e:
        raise Refused(f"{HOST_ENV} illisible ({type(e).__name__}) : rien n'est fait") from None
    env = he.read_env(path)
    name = he.token_name(env)
    if not name:
        raise Refused(f"{HOST_ENV} : aucun jeton de la console ({he.TOKEN}, ou son ancien nom {he.LEGACY_TOKEN}) "
                      "— rien à faire tourner ; make imladris-push le refuserait aussi")
    return text, name, env[name]


def rewritten(text: str, name: str, token: str) -> str:
    """host.env with its token's line alone changed: the last line of `name` (the one compose reads)
    takes `token` under the new name, at its place, its line ending kept; every other line of either
    name goes — the former name beside the new, an earlier line of the key. The rest, to the byte."""
    lines = text.splitlines(keepends=True)
    names = (he.TOKEN, he.LEGACY_TOKEN)
    at = max(i for i, ln in enumerate(lines) if _key(ln) == name)
    out = []
    for i, ln in enumerate(lines):
        if i == at:
            out.append(f"{he.TOKEN}={token}" + ln[len(ln.rstrip("\r\n")):])
        elif _key(ln) not in names:
            out.append(ln)
    return "".join(out)


def _checked(path: Path, shown: Path) -> str:
    """host_env.py --check on `path`, as `make imladris-push` runs it: "" when it passes, else what it
    says (never a value: the check prints none), `shown` named in place of the temporary file."""
    said = io.StringIO()
    try:
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            he.check(str(path))
    except SystemExit as e:
        return str(e.code if e.code is not None else "").replace(str(path), str(shown)) or "refusé"
    return ""


def write_atomic(path: Path, text: str) -> None:
    """`text` beside `path`, created 0600 (a file left by an interrupted run removed first: it is
    ours, its token never used), checked as the push will check it, then renamed over `path`.
    Refused by the check: nothing replaced, the temporary file removed."""
    tmp = path.with_name(TMP)
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, text.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        if why := _checked(tmp, path):
            raise Refused(f"{HOST_ENV} ne passerait pas host_env.py --check : {why} — rien n'est écrit")
        os.replace(tmp, path)
    except BaseException:    # a refusal, an OSError or a Ctrl-C: never a temporary file left, it holds a token
        tmp.unlink(missing_ok=True)
        raise


def _run(argv: list[str], ctx: Ctx, stdin: str | None = None, timeout: float = 180) -> bs.Result:
    return pr.run(argv, ctx.env, stdin=stdin, cwd=ctx.root, timeout=timeout)


def push(ctx: Ctx) -> tuple[bool, str]:
    """`make imladris-push`, its output on the screen (it never prints the token)."""
    import subprocess
    try:
        rc = subprocess.run(shlex.split(ctx.push), env=ctx.env, cwd=ctx.root, timeout=300).returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, type(e).__name__
    return rc == 0, f"make imladris-push a rendu {rc}"


def restart(ctx: Ctx) -> tuple[bool, str]:
    """The console alone, recreated: it reads its environment again (the watch and the bot untouched)."""
    res = _run([*shlex.split(ctx.ssh), RESTART], ctx, stdin="")     # never the terminal's input
    return res.ok, (pr._error(res) or f"ssh a rendu {res.rc}")


def probe(new: str, old: str, ctx: Ctx) -> tuple[str, str]:
    """(the code the new token gets, the old one's), read on Imladris; ("", "") when it does not answer."""
    res = _run([*shlex.split(ctx.ssh), PROBE], ctx, stdin=f"{new}\n{old}\n", timeout=120)
    for line in res.out.splitlines():
        parts = dict(p.split("=", 1) for p in line.split() if "=" in p)
        if "new" in parts and "old" in parts:
            return parts["new"], parts["old"]
    return "", ""


def note_on_imladris(end: datetime, ctx: Ctx, by: str) -> tuple[bool, list[str]]:
    """The day to turn it again, on Imladris, by ROT1's path; an agent of the CD from before ROT2 (it
    reads only the three pairs) is said: the date is there, no reminder leaves."""
    pctx = pr.Ctx(env=ctx.env, root=ctx.root, ssh=ctx.ssh, now=ctx.now, cwd=ctx.cwd, here=ctx.here)
    ok, said = pr.note_on_imladris(NAME, end, pctx, by, again=f"make {NOTE}")
    if ok and not any(f" {NAME} " in s for s in said[1:]):
        return False, ["⚠ Imladris : la date est notée, mais l'agent de son CD ne connaît pas encore le jeton de la "
                       "console (une version d'avant ROT2) : make imladris-cd-install, depuis un checkout de main à jour"]
    if ok:
        said[0] = (f"✓ Imladris : à faire tourner le {end:%Y-%m-%d} ; son CD le rappelle dans #deploy à J-14, J-7, "
                   "J-1 et le jour même")
    return ok, said


def _reach(ctx: Ctx, nothing: str) -> None:
    if not ctx.ssh:
        raise Refused("Imladris injoignable d'ici (pas d'adresse, ou sa clé d'hôte refusée : make imladris-known, "
                      f"HOST_SSH_FINGERPRINT) — {nothing}")


def rotate(days_raw: str, ctx: Ctx) -> int:
    say = ctx.say
    if why := refusal(ROTATE, ctx):
        say(why)
        return 1
    try:
        days = _days(days_raw)
        _reach(ctx, "rien n'est tiré")
        if not ctx.push:
            raise Refused("le chemin de la pose manque (make imladris-push) : à lancer par make imladris-console-rotate")
        text, name, old = read_token(ctx.host_env)
        new = draw_token()
        while new == old:                       # never the same, however unlikely
            new = draw_token()
        write_atomic(ctx.host_env, rewritten(text, name, new))
    except Refused as e:
        say(f"✗ {e}")
        return 1
    end = ctx.now + timedelta(days=days)
    renamed = f" (sous {he.TOKEN}, son ancien nom {he.LEGACY_TOKEN} retiré)" if name == he.LEGACY_TOKEN else ""
    say(f"✓ {HOST_ENV} : un nouveau jeton de la console{renamed}, 0600 ; aucune autre ligne n'a changé")
    left = (f"{HOST_ENV} porte le nouveau jeton (le poste) ; la console d'Imladris accepte encore l'ancien. "
            f"Une fois Imladris joignable, relance make {ROTATE} : un autre jeton, la même pose")
    ok, why = push(ctx)
    if not ok:
        say(f"✗ la pose a échoué ({why}) : {left}")
        return 1
    ok, why = restart(ctx)
    if not ok:
        say(f"✗ la console d'Imladris ne redémarre pas ({why}) : ~/eregion/.env porte le nouveau jeton, mais la "
            f"console a pu garder l'ancien. {left}")
        return 1
    say("✓ la console d'Imladris relancée seule (war-room) : la watch et le bot n'ont pas bougé")
    got_new, got_old = probe(new, old, ctx)
    if got_new != "200" or got_old != "401":
        said = "pas de réponse" if not got_new else f"le nouveau : {got_new}, l'ancien : {got_old}"
        say(f"✗ la console d'Imladris ne répond pas comme attendu ({said} ; 200 et 401 attendus) : make "
            f"imladris-status, make imladris-logs. {left}")
        return 1
    say("✓ la console d'Imladris accepte le nouveau jeton et refuse l'ancien : toute session de l'ancien est "
        "refusée, le navigateur et le téléphone compris")
    noted, said = note_on_imladris(end, ctx, ROTATE)
    for line in said:
        say(line)
    say("ℹ l'URL : make imladris-url (le jeton n'est jamais affiché ici)")
    return 0 if noted else 1


def note(days_raw: str, ctx: Ctx) -> int:
    say = ctx.say
    if why := refusal(NOTE, ctx):
        say(why)
        return 1
    try:
        days = _days(days_raw)
        _reach(ctx, "rien n'est noté")
        read_token(ctx.host_env)                # a token in place, or nothing to note
    except Refused as e:
        say(f"✗ {e}")
        return 1
    end = ctx.now + timedelta(days=days)
    say(f"ℹ le jeton en place, compté comme tiré aujourd'hui : à faire tourner dans {days} jours (DAYS=…)")
    ok, said = note_on_imladris(end, ctx, NOTE)
    for line in said:
        say(line)
    return 0 if ok else 1


def main(argv: list[str] | None = None, ctx: Ctx | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("guard", help="the refusal of a code session, alone (make runs it first)")
    g.add_argument("target")
    for name in ("rotate", "note"):
        sub.add_parser(name).add_argument("--days", default="")
    args = p.parse_args(argv)
    ctx = ctx or Ctx(env=dict(os.environ), ssh=os.environ.get("EREGION_HOST_SSH", ""),
                     push=os.environ.get("EREGION_PUSH", ""))
    if args.cmd == "guard":
        why = refusal(args.target, ctx)
        if why:
            print(why, file=sys.stderr)
        return 1 if why else 0
    return (rotate if args.cmd == "rotate" else note)(args.days, ctx)


if __name__ == "__main__":
    sys.exit(main())
