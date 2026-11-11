#!/usr/bin/env python3
"""mobile — the workstation reached from the phone, held by two barriers (MOB1, #686; docs/demarrer/mobile.md).

  mobile.py check [--console-port 7007]    `make mobile-check`: read-only, one line ✓/⚠/✗ per check, exit 1
                                           on a ✗
  mobile.py tunnel-install [--dry-run]     `make mobile-tunnel-install` (MOB2): the workstation's tunnel to
                                           the console of Imladris, a user unit of systemd, written, never
                                           enabled nor started
  mobile.py tunnel-on                      `make mobile-tunnel-on`: armed for 12 h at most (the deadline,
                                           the timer of expiry, then the start)
  mobile.py tunnel-off                     `make mobile-tunnel-off`: stopped, its deadline removed
  mobile.py tunnel-remove [--dry-run]      `make mobile-tunnel-remove`: stopped, the unit removed
  mobile.py guard <target>                 the refusal of a code session, alone: `make console-url` and the
                                           targets that print the console's token run it first

Every gesture refuses in a code session (bench_shared.session_refusal, as MOB1's): a session never sets
nor arms the tunnel, and never reads the console's token. The tunnel is armed on demand and bounded to
12 h (decision of Jonathan, 11/11), by three bounds: the deadline and the transient timer that stops the
unit then, both from `tunnel-on`; the unit's ExecCondition, which refuses any (re)start past the deadline;
RuntimeMaxSec=12h on each run.

The two barriers: the private network (Tailscale: the account with MFA, an access rule that opens only
phone → workstation:22), then the workstation's SSH server, in WSL, by key alone — a key kept in the
phone's secure chip. The console of H0 reaches the phone through the phone's own SSH tunnel to the
workstation's 127.0.0.1:7007, where `make glorfindel-host-tunnel` holds H0's (decision of Jonathan,
10/11): the same two barriers, then the console's token. What `check` reads, and nothing else:

  the tailnet     `tailscale ip -4`: one private address; `tailscale debug prefs`: Tailscale SSH off (unread: ✗; on,
                  it would let the tailnet into the workstation without the phone's key: one barrier, not two)
  the listeners   `ss -Hltn`: the SSH server's ports (`sshd -T`) listen on the private address only —
                  never on every interface (0.0.0.0, [::], *), a loopback (WSL shares it with Windows)
                  or another address; the console's port on 127.0.0.1 (and ::1, ssh's other loopback)
                  alone — never the private address, every interface or another one
  the SSH server  `sshd -T` (by sudo -n when not root: `sudo -v` first): PasswordAuthentication no,
                  KbdInteractiveAuthentication no, PermitEmptyPasswords no, HostbasedAuthentication no,
                  GSSAPIAuthentication no, PubkeyAuthentication yes, AuthenticationMethods publickey
                  (or any: the others closed), AuthorizedKeysFile .ssh/authorized_keys alone,
                  AuthorizedKeysCommand none, TrustedUserCAKeys none; the phone's tunnel and nothing
                  more: AllowTcpForwarding local (yes, all or remote: ✗; no: ⚠, the tunnel does not
                  open), PermitOpen 127.0.0.1:7007 alone, GatewayPorts no, AllowStreamLocalForwarding,
                  AllowAgentForwarding and X11Forwarding no; PermitRootLogin no (a ⚠ otherwise). These
                  bound sshd's own forwarding: with a shell, the phone relays as the operator does
                  (`nc`), which the key's loss or a phone unlocked covers (the threat model, frontier 9)
  the keys        ~/.ssh/authorized_keys: how many, of which types — never a key printed; their options
                  (`from=`, `permitopen=`) are not read: the guide sets them
  the tunnel      (MOB2) ~/.config/systemd/user/eregion-console-tunnel.service, the model's own
                  (infra/poste/): no [Install] nor link in a *.wants/ (it would start at boot);
                  RuntimeMaxSec at most 12 h and the deadline read (else: without a limit of time); one
                  forward, 127.0.0.1:7007 → Imladris's 127.0.0.1:7007, nothing more than the model
                  says; the host key pinned (StrictHostKeyChecking=yes, its own known_hosts holding only
                  keys of the fingerprint the unit names); ExitOnForwardFailure, ServerAlive, Restart; the
                  address of Imladris the one Terraform gives now (--host-ip; unread: a ⚠). Then
                  `systemctl --user show`: stopped, ℹ not armed (never a ✗); failing, restarting or
                  enabled, a ✗; armed: since when, until when (past its deadline or beyond 12 h: ✗), its
                  timer of expiry alive, and (`ss -Hltnp`) its process listening on 127.0.0.1:7007 alone.
                  Not set at all: ℹ.

No address is printed. `check` writes nothing, installs nothing. The global configuration only: a
`Match` block can change it for one connection (said in the guide).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bench_shared as bs  # noqa: E402

OK, WARN, FAIL, INFO = "✓", "⚠", "✗", "ℹ"
TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
TAILNET_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
CONSOLE_PORT = 7007
# What the SSH server must say (sshd -T, lowercase): the key alone, from the user's own file alone.
REQUIRED = (
    ("passwordauthentication", "no"),
    ("kbdinteractiveauthentication", "no"),
    ("permitemptypasswords", "no"),
    ("hostbasedauthentication", "no"),
    ("pubkeyauthentication", "yes"),
    ("authorizedkeyscommand", "none"),
    ("trustedusercakeys", "none"),
    ("gatewayports", "no"),
)
# Nothing relayed by sshd beyond the phone's local tunnel: no socket, no agent, no X11.
NO_RELAY = (
    ("allowstreamlocalforwarding", "no"),
    ("allowagentforwarding", "no"),
    ("x11forwarding", "no"),
)
KEYS_FILES = (".ssh/authorized_keys", "%h/.ssh/authorized_keys")
# Where the console's port may listen: the loopback ssh binds for `make glorfindel-host-tunnel`.
CONSOLE_LOOPBACK = ("127.0.0.1", "::1")
# Said only by a server built with it: closed when it is there.
IF_PRESENT = (("gssapiauthentication", "no"), ("challengeresponseauthentication", "no"))


def _run(argv: list[str], timeout: float = 30) -> tuple[int, str, str]:
    try:
        res = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                             stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return 127, "", f"{argv[0]} : introuvable"
    except subprocess.TimeoutExpired:
        return 124, "", f"{argv[0]} : pas de réponse en {int(timeout)} s"
    return res.returncode, res.stdout or "", res.stderr or ""


# ── the private address ──────────────────────────────────────────────────────

def tailnet_ipv4(text: str) -> tuple[str, str]:
    """(the one tailnet IPv4 of `tailscale ip -4`'s output, '') or ('', why)."""
    found = []
    for word in text.split():
        try:
            ip = ipaddress.ip_address(word.strip())
        except ValueError:
            return "", "la sortie de tailscale ip -4 n'est pas une adresse"
        found.append(ip)
    if not found:
        return "", "tailscale ip -4 ne donne aucune adresse (tailscale up ?)"
    if len(found) != 1:
        return "", f"tailscale ip -4 donne {len(found)} adresses, une seule attendue"
    ip = found[0]
    if ip.version != 4 or ip not in TAILNET_V4:
        return "", "l'adresse que donne tailscale ip -4 n'est pas une adresse du réseau privé (hors de la plage de Tailscale)"
    return str(ip), ""


def private_ipv4(run=_run) -> tuple[str, str]:
    rc, out, err = run(["tailscale", "ip", "-4"])
    if rc != 0:
        first = (err or out).strip().splitlines()
        return "", f"tailscale ip -4 a échoué ({first[0][:120] if first else f'code {rc}'})"
    return tailnet_ipv4(out)


# ── what the commands say ────────────────────────────────────────────────────

def parse_listeners(text: str) -> list[tuple[str, int]]:
    """`ss -Hltn` → [(address, port)]: the 4th column, `addr:port` ([v6]:port, *:port, addr%iface:port)."""
    out = []
    for line in text.splitlines():
        cols = line.split()
        if len(cols) < 4 or ":" not in cols[3]:
            continue
        addr, _, port = cols[3].rpartition(":")
        if not port.isdigit():
            continue
        addr = addr.strip("[]").split("%", 1)[0]
        out.append((addr, int(port)))
    return out


def kind(addr: str, private: set[str]) -> str:
    """private, every (every interface), loopback, or other."""
    if addr in ("*", "0.0.0.0", "::", ""):
        return "every"
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return "other"
    if str(ip) in private:
        return "private"
    if ip.is_unspecified:
        return "every"
    if ip.is_loopback:
        return "loopback"
    return "other"


SAID = {"every": "toutes les interfaces", "loopback": "la boucle locale (partagée avec Windows par WSL)",
        "other": "une autre adresse que l'adresse privée"}


def parse_sshd(text: str) -> dict[str, list[str]]:
    """`sshd -T` (or a configuration file) → {keyword lowercase: [values]}; comments and Match blocks
    left out (sshd -T prints none; a file's Match applies to some connections only)."""
    out: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(" ")
        key = key.lower()
        if key == "match":
            break
        out.setdefault(key, []).append(value.strip())
    return out


def sshd_lines(conf: dict[str, list[str]], console_port: int = CONSOLE_PORT) -> list[tuple[str, str]]:
    lines = []
    for key, want in REQUIRED + NO_RELAY:
        got = (conf.get(key) or [""])[0].lower()
        if got == want:
            lines.append((OK, f"SSH : {key} {want}"))
        else:
            lines.append((FAIL, f"SSH : {key} {got or '(absent)'}, {want} attendu"))
    for key, want in IF_PRESENT:
        if key in conf:
            got = conf[key][0].lower()
            lines.append((OK, f"SSH : {key} {want}") if got == want
                         else (FAIL, f"SSH : {key} {got}, {want} attendu"))
    keys = (conf.get("authorizedkeysfile") or [""])[0]
    lines.append((OK, "SSH : authorizedkeysfile .ssh/authorized_keys seul") if keys in KEYS_FILES
                 else (FAIL, f"SSH : authorizedkeysfile {keys or '(absent)'} — .ssh/authorized_keys seul attendu"))
    fwd = (conf.get("allowtcpforwarding") or [""])[0].lower()
    if fwd == "local":
        lines.append((OK, "SSH : allowtcpforwarding local — le tunnel du téléphone, aucun port ouvert sur le poste"))
    elif fwd == "no":
        lines.append((WARN, "SSH : allowtcpforwarding no — le tunnel du téléphone vers la console ne s'ouvre pas"))
    else:
        lines.append((FAIL, f"SSH : allowtcpforwarding {fwd or '(absent)'} — local attendu"))
    opens = (conf.get("permitopen") or [""])[0].lower().split()
    if opens == [f"127.0.0.1:{console_port}"]:
        lines.append((OK, f"SSH : permitopen 127.0.0.1:{console_port} seul — la console, rien d'autre"))
    else:
        lines.append((FAIL, f"SSH : permitopen {' '.join(opens) or '(absent)'} — 127.0.0.1:{console_port} seul attendu"))
    methods = (conf.get("authenticationmethods") or ["any"])[0].lower()
    lists = [m.split(",") for m in methods.split()]
    if methods == "any" or all(all(step.split(":", 1)[0] == "publickey" for step in lst) for lst in lists):
        lines.append((OK, f"SSH : authenticationmethods {methods} — la clé seule"))
    else:
        lines.append((FAIL, f"SSH : authenticationmethods {methods} — une autre méthode que la clé"))
    root = (conf.get("permitrootlogin") or [""])[0].lower()
    lines.append((OK, "SSH : permitrootlogin no") if root == "no"
                 else (WARN, f"SSH : permitrootlogin {root or '(absent)'} — no conseillé"))
    return lines


def listener_lines(listeners: list[tuple[str, int]], private: set[str], ssh_ports: set[int],
                   console_port: int) -> list[tuple[str, str]]:
    lines = []
    ssh = [(a, p) for a, p in listeners if p in ssh_ports]
    bad = sorted({kind(a, private) for a, _ in ssh} - {"private"})
    if not ssh:
        lines.append((FAIL, "SSH : le serveur n'écoute pas (systemctl status ssh)"))
    elif bad:
        lines.append((FAIL, "SSH : le serveur écoute sur " + ", ".join(SAID[b] for b in bad)
                      + " — ListenAddress <l'adresse privée> seule (infra/poste/sshd_config.d/00-eregion.conf)"))
    else:
        lines.append((OK, "SSH : le serveur n'écoute que sur l'adresse privée"))
    console = [a for a, p in listeners if p == console_port]
    bad = sorted({kind(a, private) for a in console if a not in CONSOLE_LOOPBACK})
    if bad:
        said = {**SAID, "private": "l'adresse privée (le téléphone passe par son tunnel SSH)",
                "loopback": "une autre boucle que 127.0.0.1"}
        lines.append((FAIL, f"console : le port {console_port} est exposé sur "
                      + ", ".join(said[b] for b in bad) + " — 127.0.0.1 seul (make glorfindel-host-tunnel)"))
    elif console:
        lines.append((OK, f"console : le port {console_port} n'écoute qu'en 127.0.0.1 — le tunnel du poste vers H0"))
    else:
        lines.append((OK, f"console : le port {console_port} n'est ouvert nulle part"))
    return lines


def tailscale_ssh_line(text: str, rc: int) -> tuple[str, str]:
    if rc != 0:
        return FAIL, "réseau privé : Tailscale SSH ne se lit pas (tailscale debug prefs) — off attendu, à vérifier"
    try:
        prefs = json.loads(text)
    except ValueError:
        return FAIL, "réseau privé : tailscale debug prefs illisible — Tailscale SSH off attendu, à vérifier"
    if not isinstance(prefs, dict) or not isinstance(prefs.get("RunSSH"), bool):
        return FAIL, "réseau privé : tailscale debug prefs ne dit pas RunSSH — Tailscale SSH off attendu, à vérifier"
    if prefs.get("RunSSH") is True:
        return FAIL, ("réseau privé : Tailscale SSH est ouvert — il ferait entrer sans la clé du téléphone "
                      "(tailscale set --ssh=false)")
    return OK, "réseau privé : Tailscale SSH fermé (le serveur SSH du poste, à clé, est le seul)"


def keys_line(path: Path) -> tuple[str, str]:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return WARN, "clés : aucun ~/.ssh/authorized_keys (la clé publique du téléphone y va)"
    except OSError:
        return WARN, "clés : ~/.ssh/authorized_keys illisible"
    if not stat.S_ISREG(st.st_mode):
        return FAIL, "clés : ~/.ssh/authorized_keys n'est pas un fichier (un lien ?)"
    if st.st_mode & 0o022:
        return FAIL, "clés : ~/.ssh/authorized_keys est modifiable par d'autres (chmod 600)"
    types = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            words = re.findall(r'(?:[^\s"]|"[^"]*")+', line)
            t = next((w for w in words if re.fullmatch(r"(ssh|ecdsa|sk)-[A-Za-z0-9@.-]+", w)), "inconnu")
            types.append(t)
    except OSError:
        return WARN, "clés : ~/.ssh/authorized_keys illisible"
    if not types:
        return WARN, "clés : ~/.ssh/authorized_keys est vide (la clé publique du téléphone y va)"
    counted = ", ".join(f"{types.count(t)} {t}" for t in sorted(set(types)))
    return OK, f"clés : {len(types)} clé(s) admise(s) ({counted}) — une par appareil, retirée s'il est perdu"


# ── the permanent tunnel to the console of Imladris (MOB2) ───────────────────

UNIT_NAME = "eregion-console-tunnel.service"
UNIT_MODEL = _HERE.parent / "infra" / "poste" / UNIT_NAME
UNIT_DIR = Path(".config") / "systemd" / "user"
# The tunnel's own known_hosts: the one key of Imladris whose fingerprint the unit names; and its window,
# « <armed at> <deadline> » in seconds since the epoch, written by `make mobile-tunnel-on`.
TUNNEL_KNOWN_HOSTS = Path(".eregion") / "console-tunnel" / "known_hosts"
TUNNEL_DEADLINE = Path(".eregion") / "console-tunnel" / "deadline"
# The window of exposure: 12 h at most from the gesture (decision of Jonathan, 11/11), and the transient
# timer of systemd that stops the unit then.
WINDOW_S = 12 * 3600
EXPIRY_UNIT = "eregion-console-tunnel-expiry"
FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")
HOST_USER_NAME = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
# A path written into ExecStart: no blank, no quote, no « % » (a specifier of systemd), no « $ ».
UNIT_PATH = re.compile(r"/[A-Za-z0-9._/-]+")
# What a session never does here (bench_shared.session_refusal).
NEVER_TUNNEL = "ne pose, n'arme ni ne retire jamais le tunnel du poste, l'opérateur le fait"
NEVER_TOKEN = "ne lit jamais le jeton de la console, l'opérateur le lit"

# The unit's keys, section by section: the model's, nothing else.
# No [Install]: nothing for `systemctl enable` to do, never started at boot.
UNIT_KEYS = {
    "Unit": {"Description", "Documentation", "StartLimitIntervalSec", "X-Eregion-HostKey"},
    "Service": {"Type", "ExecCondition", "ExecStart", "Restart", "RestartSec", "RuntimeMaxSec"},
}
DURATION = re.compile(r"(\d+)\s*(s|sec|m|min|h|hr)?")
# ssh's options the unit must say, with this value (keys lowercase, as ssh reads them).
TUNNEL_MUST = {"batchmode": "yes", "stricthostkeychecking": "yes", "globalknownhostsfile": "/dev/null",
               "exitonforwardfailure": "yes"}
# The keepalive: a link lost is seen, then ssh exits and systemd starts it again.
KEEPALIVE = {"serveraliveinterval": (1, 300), "serveralivecountmax": (1, 10)}
# The others it may say, with the value each must have (None: a number; "": a path, read apart).
TUNNEL_MAY = {"userknownhostsfile": "", "hostkeyalgorithms": "ssh-ed25519", "updatehostkeys": "no",
              "identitiesonly": "yes", "connecttimeout": None}
FLAGS_WITH_VALUE = ("-F", "-i", "-L", "-o")
FLAGS_ALONE = ("-N", "-T")


def unit_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / UNIT_DIR / UNIT_NAME


def parse_unit(text: str) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    """A unit file → ({section: {key: [values]}}, what is not a unit's line). A line ending in « \\ »
    goes on with the next one, as systemd reads it; comments (# ;) left out."""
    sections: dict[str, dict[str, list[str]]] = {}
    odd: list[str] = []
    current = None
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not pending and (not line or line[0] in "#;"):
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        line, pending = (pending + line).strip(), ""
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
            continue
        key, eq, value = line.partition("=")
        if not eq or current is None:
            odd.append(line[:60])
            continue
        current.setdefault(key.strip(), []).append(value.strip())
    if pending:
        odd.append(pending[:60])
    return sections, odd


def _option(value: str) -> tuple[str, str]:
    """`-o Key=Value` or `-o "Key Value"` → (key lowercase, value)."""
    m = re.match(r"\s*([A-Za-z0-9]+)\s*(?:=\s*|\s+)(.*)$", value)
    if not m:
        return value.strip().lower(), ""
    return m.group(1).lower(), m.group(2).strip()


def parse_ssh(argv: list[str]) -> dict:
    """ssh's arguments → its forwards, options (lowercase key → values), flags, config files, identities,
    destination(s), and what the model does not say."""
    out: dict = {"forwards": [], "options": {}, "flags": [], "config": [], "identity": [], "dest": [],
                 "unknown": []}
    i = 0
    while i < len(argv):
        arg = argv[i]
        i += 1
        if out["dest"]:
            out["unknown"].append(arg[:40])     # a remote command after the destination
            continue
        if not arg.startswith("-") or arg == "-":
            out["dest"].append(arg)
            continue
        flag, value = arg[:2], arg[2:]
        if flag in FLAGS_WITH_VALUE:
            if not value:
                if i >= len(argv):
                    out["unknown"].append(arg)
                    continue
                value = argv[i]
                i += 1
            if flag == "-o":
                key, val = _option(value)
                out["options"].setdefault(key, []).append(val)
            else:
                out[{"-L": "forwards", "-F": "config", "-i": "identity"}[flag]].append(value)
        elif all(f"-{c}" in FLAGS_ALONE for c in arg[1:]):
            out["flags"] += [f"-{c}" for c in arg[1:]]
        else:
            out["unknown"].append(arg[:40])
    return out


def fingerprint_of(blob_b64: str) -> str:
    """The SHA256 fingerprint of a public key, as `ssh-keygen -l` prints it."""
    raw = base64.b64decode(blob_b64.encode("ascii"), validate=True)
    return "SHA256:" + base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii").rstrip("=")


def _host_matches(field: str, host: str) -> bool:
    for name in field.split(","):
        if name.startswith("|1|"):
            try:
                _, _, salt, digest = name.split("|", 3)
                mac = hmac.new(base64.b64decode(salt), host.encode(), hashlib.sha1).digest()
            except (ValueError, TypeError):
                continue
            if hmac.compare_digest(base64.b64encode(mac).decode(), digest):
                return True
        elif name == host:
            return True
    return False


def known_host_fingerprints(text: str, host: str) -> tuple[list[str], int]:
    """(the fingerprints of the keys a known_hosts holds for `host`, how many of its lines are not
    one: another host, a marker — @cert-authority, @revoked —, an unreadable key)."""
    mine: list[str] = []
    others = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        words = line.split()
        if words[0].startswith("@") or len(words) < 3 or not _host_matches(words[0], host):
            others += 1
            continue
        try:
            mine.append(fingerprint_of(words[2]))
        except (ValueError, TypeError):
            others += 1
    return mine, others


def forward_said(fwd: str, console_port: int = CONSOLE_PORT) -> str:
    """'' when `fwd` is 127.0.0.1:<port>:127.0.0.1:<port>, else what it opens."""
    if fwd == f"127.0.0.1:{console_port}:127.0.0.1:{console_port}":
        return ""
    parts = re.findall(r"\[[^\]]*\]|[^:]+", fwd)
    if len(parts) == 3:
        return "sans adresse de liaison (ssh la prendrait de GatewayPorts)"
    if len(parts) != 4:
        return "illisible"
    bind, port, dest_host, dest_port = parts
    bind = bind.strip("[]")
    if (dest_host, dest_port) != ("127.0.0.1", str(console_port)):
        return "vers autre chose que la console d'Imladris"
    if port != str(console_port):
        return f"sur un autre port que {console_port}"
    if bind in ("*", "0.0.0.0", "::", ""):
        return "sur toutes les interfaces"
    try:
        ip = ipaddress.ip_address(bind)
    except ValueError:
        return "sur une adresse nommée (localhost : ::1 aussi, peut-être)"
    if (ip.version == 4 and ip in TAILNET_V4) or (ip.version == 6 and ip in TAILNET_V6):
        return "sur l'adresse privée (le tailnet joindrait la console sans la clé du téléphone)"
    return "sur une autre adresse que 127.0.0.1"


def duration_s(value: str) -> int | None:
    """A duration of systemd (« 12h », « 720min », « 43200 », « 12h 0min ») in seconds; None when
    absent, « infinity » or unread."""
    value = value.strip()
    if not value or not re.fullmatch(r"(?:\d+\s*(?:s|sec|m|min|h|hr)?\s*)+", value):
        return None
    unit = {None: 1, "s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hr": 3600}
    return sum(int(n) * unit[u or None] for n, u in DURATION.findall(value))


def _condition_model() -> re.Pattern | None:
    """The model's ExecCondition, its deadline's path left open."""
    try:
        sections, _ = parse_unit(UNIT_MODEL.read_text(encoding="utf-8"))
    except OSError:
        return None
    model = (sections.get("Service", {}).get("ExecCondition") or [""])[0]
    if "@DEADLINE@" not in model:
        return None
    return re.compile(re.escape(model).replace(re.escape("@DEADLINE@"), r"(/[A-Za-z0-9._/-]+)"))


def deadline_of(sections: dict) -> str:
    """The deadline's path the unit's ExecCondition reads — the model's line, word for word — or ''."""
    conds = sections.get("Service", {}).get("ExecCondition") or []
    model = _condition_model()
    m = model.fullmatch(conds[0]) if model and len(conds) == 1 else None
    return m.group(1) if m else ""


def _read_private(path) -> str:
    """A file of the operator's: a regular file, not a link, writable by them alone."""
    path = Path(path)
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o022:
        raise OSError(f"{path.name} : pas un fichier à soi")
    return path.read_text(encoding="utf-8", errors="replace")


def unit_lines(text: str, host_ip: str | None = None, console_port: int = CONSOLE_PORT,
               read=_read_private) -> list[tuple[str, str]]:
    """The unit, checked against the model: never started at boot, 12 h at most, nothing more than it
    says, one forward to the console on 127.0.0.1 alone, the host key pinned, a tunnel that starts again
    after a cut, the address of Imladris. `read(path)` gives the text of the tunnel's known_hosts, or
    raises OSError."""
    sections, odd = parse_unit(text)
    lines: list[tuple[str, str]] = []
    service = sections.get("Service", {})
    execs = service.get("ExecStart", [])

    # Armed by a gesture alone: no [Install], whatever it says (WantedBy, RequiredBy, Alias, Also).
    if "Install" in sections:
        lines.append((FAIL, "tunnel : l'unité a une section [Install] — `systemctl enable` la ferait démarrer "
                      "au boot, sans geste : make mobile-tunnel-install la réécrit"))
    # 12 h at most: a run bounded, and no start past the deadline (the model's ExecCondition).
    longest = duration_s((service.get("RuntimeMaxSec") or [""])[0])
    if longest is None or not 1 <= longest <= WINDOW_S:
        lines.append((FAIL, "tunnel : l'unité est sans limite de durée — RuntimeMaxSec entre 1 s et 12 h "
                      "attendu : make mobile-tunnel-install la réécrit"))
    elif not deadline_of(sections):
        lines.append((FAIL, "tunnel : l'unité ne lit pas la date limite (ExecCondition du modèle) — elle "
                      "repartirait au-delà des 12 h : make mobile-tunnel-install la réécrit"))
    else:
        lines.append((OK, "tunnel : jamais au boot, 12 h au plus — RuntimeMaxSec, la date limite lue à "
                      "chaque départ"))
    more = [f"[{name}]" for name in sections if name not in UNIT_KEYS and name != "Install"]
    more += [f"{k}=" for name, keys in sections.items() if name in UNIT_KEYS for k in keys
             if k not in UNIT_KEYS[name]]
    more += [f"« {o} »" for o in odd]
    argv: list[str] = []
    if len(execs) != 1:
        more.append(f"{len(execs)} ExecStart")
    else:
        try:
            argv = shlex.split(execs[0])
        except ValueError:
            more.append("un ExecStart illisible")
    if argv and (not argv[0].startswith("/") or Path(argv[0]).name != "ssh"):
        more.append("un ExecStart qui n'est pas /…/ssh")
        argv = []
    ssh = parse_ssh(argv[1:])
    opts = ssh["options"]
    more += ssh["unknown"]
    more += [f"-o {k}" for k in opts if k not in TUNNEL_MUST and k not in KEEPALIVE and k not in TUNNEL_MAY]
    if any(len(v) > 1 for v in opts.values()):
        more.append("une option dite deux fois (ssh garde la première)")
    for key, want in TUNNEL_MAY.items():
        got = (opts.get(key) or [None])[0]
        if got is not None and want != "" and not (got.isdigit() if want is None else got.lower() == want):
            more.append(f"-o {key}={got}")
    if service.get("Type", ["simple"])[0] not in ("simple", "exec"):
        more.append(f"Type={service['Type'][0]}")
    if more:
        lines.append((FAIL, "tunnel : l'unité dit autre chose que le modèle (" + ", ".join(more)[:200]
                      + ") — make mobile-tunnel-install la réécrit"))

    # One forward: the console, on 127.0.0.1 alone.
    fwds = ssh["forwards"]
    said = forward_said(fwds[0], console_port) if len(fwds) == 1 else ""
    if not argv:
        lines.append((FAIL, "tunnel : aucune commande ssh dans l'unité"))
    elif len(fwds) != 1:
        lines.append((FAIL, f"tunnel : {len(fwds)} redirections, une seule attendue "
                      f"(127.0.0.1:{console_port}:127.0.0.1:{console_port})"))
    elif said:
        lines.append((FAIL, f"tunnel : la redirection est {said} — 127.0.0.1:{console_port} seul, "
                      "le téléphone y ouvre son propre tunnel"))
    else:
        lines.append((OK, f"tunnel : une redirection, de 127.0.0.1:{console_port} seul vers la console d'Imladris"))

    # The host key, pinned.
    user, _, host = (ssh["dest"][0] if len(ssh["dest"]) == 1 else "").rpartition("@")
    pin = (sections.get("Unit", {}).get("X-Eregion-HostKey") or [""])[0]
    files = opts.get("userknownhostsfile", [])
    why = ""
    if (opts.get("stricthostkeychecking") or [""])[0].lower() != "yes":
        why = "StrictHostKeyChecking=yes absent (une clé inconnue serait acceptée, ou demandée)"
    elif (opts.get("globalknownhostsfile") or [""])[0] != "/dev/null":
        why = "GlobalKnownHostsFile=/dev/null absent (d'autres clés seraient lues)"
    elif len(files) != 1 or not files[0].startswith("/") or files[0] == "/dev/null":
        why = "pas de known_hosts à lui (UserKnownHostsFile)"
    elif not FINGERPRINT.fullmatch(pin):
        why = "l'unité ne nomme pas l'empreinte épinglée (X-Eregion-HostKey)"
    elif not host:
        why = "aucune destination"
    else:
        try:
            mine, others = known_host_fingerprints(read(files[0]), host)
        except OSError:
            mine, others = None, 0
        if mine is None:
            why = "son known_hosts ne se lit pas (absent, un lien, modifiable par d'autres)"
        elif not mine:
            why = "son known_hosts ne tient aucune clé d'Imladris"
        elif others or any(f != pin for f in mine):
            why = "son known_hosts tient une autre clé que celle de l'empreinte épinglée"
    if why:
        lines.append((FAIL, f"tunnel : la clé d'hôte n'est pas épinglée — {why} : make mobile-tunnel-install"))
    else:
        lines.append((OK, "tunnel : la clé d'hôte d'Imladris épinglée (son empreinte, son known_hosts, "
                      "StrictHostKeyChecking=yes)"))

    # A tunnel that holds by itself.
    missing = []
    if ssh["config"] != ["none"]:
        missing.append("-F none (sinon ~/.ssh/config est lu)")
    if "-N" not in ssh["flags"]:
        missing.append("-N")
    for key in ("batchmode", "exitonforwardfailure"):
        if (opts.get(key) or [""])[0].lower() != TUNNEL_MUST[key]:
            missing.append(f"{key}={TUNNEL_MUST[key]}")
    for key, (low, high) in KEEPALIVE.items():
        got = (opts.get(key) or [""])[0]
        if not (got.isdigit() and low <= int(got) <= high):
            missing.append(f"{key} entre {low} et {high}")
    if service.get("Restart", [""])[0] not in ("on-failure", "always"):
        missing.append("Restart=on-failure")
    delay = service.get("RestartSec", [""])[0]
    delay = delay[:-1] if delay.endswith("s") else delay
    if not (delay.isdigit() and int(delay) >= 1):
        missing.append("RestartSec ≥ 1 s")
    if missing:
        lines.append((FAIL, "tunnel : il ne se tient pas seul — " + ", ".join(missing)))
    else:
        lines.append((OK, "tunnel : il se tient seul jusqu'à la date limite — ExitOnForwardFailure, "
                      "ServerAlive, Restart"))

    # The address of Imladris: the one Terraform gives now.
    try:
        unit_ip = str(ipaddress.ip_address(host)) if host else ""
    except ValueError:
        unit_ip = ""
    if not unit_ip or not HOST_USER_NAME.fullmatch(user):
        lines.append((FAIL, "tunnel : la destination n'est pas <utilisateur>@<adresse d'Imladris>"))
    elif not host_ip:
        lines.append((WARN, "tunnel : l'adresse d'Imladris ne se lit pas ici (aucun état Terraform local) — "
                      "l'unité n'est pas comparée"))
    elif unit_ip != host_ip.strip():
        lines.append((FAIL, "tunnel : Imladris n'est plus à l'adresse de l'unité (redéployé ?) — "
                      "make mobile-tunnel-install"))
    else:
        lines.append((OK, "tunnel : l'adresse d'Imladris est celle que donne Terraform"))
    return lines


def _show(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        key, eq, value = line.partition("=")
        if eq:
            out[key.strip()] = value.strip()
    return out


def read_window(path: Path) -> tuple[int, int] | None:
    """(armed at, deadline), seconds since the epoch, from the file `make mobile-tunnel-on` writes."""
    try:
        words = _read_private(path).split()
    except OSError:
        return None
    if len(words) != 2 or not all(w.isdigit() for w in words):
        return None
    return int(words[0]), int(words[1])


def _clock(t: float) -> str:
    return time.strftime("%d/%m %H:%M", time.localtime(t))


def _span(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600} h {seconds % 3600 // 60:02d}"


def service_lines(run=_run, console_port: int = CONSOLE_PORT, deadline: Path | None = None,
                  now: float | None = None) -> list[tuple[str, str]]:
    """What systemd says of the unit: never enabled; stopped (ℹ, not armed), failing (✗), or running —
    then since when, until when, its timer of expiry, and what its process listens on."""
    lines: list[tuple[str, str]] = []
    rc, out, err = run(["systemctl", "--user", "show", UNIT_NAME, "--no-pager",
                        "--property=LoadState,ActiveState,SubState,UnitFileState,NRestarts,MainPID"])
    state = _show(out) if rc == 0 else {}
    if "LoadState" not in state:
        return [(FAIL, "tunnel : systemd de l'utilisateur ne se lit pas (systemctl --user : "
                 + _first(err, out, rc)[:80] + ") — systemd allumé dans WSL ?")]
    if state["LoadState"] != "loaded":
        return [(FAIL, f"tunnel : l'unité n'est pas chargée (LoadState={state['LoadState']}) — "
                 "systemctl --user daemon-reload")]
    if state.get("UnitFileState", "") not in ("static", "disabled", ""):
        lines.append((FAIL, f"tunnel : l'unité est activée (UnitFileState={state['UnitFileState']}) — elle "
                      f"démarrerait au boot, sans geste : systemctl --user disable {UNIT_NAME}"))
    restarts = state.get("NRestarts", "")
    restarts = restarts if restarts.isdigit() else "?"
    active = (state.get("ActiveState", ""), state.get("SubState", ""))
    if active[0] == "inactive":
        lines.append((INFO, "tunnel : non armé — make mobile-tunnel-on l'arme pour 12 h"))
        return lines
    if active != ("active", "running"):
        lines.append((FAIL, f"tunnel : en échec ({active[0] or '?'}/{active[1] or '?'}, {restarts} "
                      "redémarrage(s)) — journalctl --user -u eregion-console-tunnel ; Imladris redéployé "
                      "(une autre adresse, une autre clé) : make mobile-tunnel-install ; make mobile-tunnel-off"))
        return lines
    now = time.time() if now is None else now
    window = read_window(deadline) if deadline else None
    if window is None:
        lines.append((FAIL, "tunnel : armé sans date limite lisible — make mobile-tunnel-off, puis -on"))
    elif window[1] <= now:
        lines.append((FAIL, f"tunnel : armé au-delà de sa date limite ({_clock(window[1])}) — "
                      "make mobile-tunnel-off"))
    elif window[1] - window[0] > WINDOW_S or window[1] - now > WINDOW_S + 60:
        lines.append((FAIL, "tunnel : armé pour plus de 12 h — make mobile-tunnel-off, puis -on"))
    else:
        lines.append((OK, f"tunnel : armé depuis {_clock(window[0])}, expire à {_clock(window[1])} (dans "
                      f"{_span(window[1] - now)}) ; {restarts} redémarrage(s)"))
    rc, out, _ = run(["systemctl", "--user", "show", f"{EXPIRY_UNIT}.timer", "--no-pager",
                      "--property=LoadState,ActiveState"])
    timer = _show(out) if rc == 0 else {}
    if (timer.get("LoadState"), timer.get("ActiveState")) != ("loaded", "active"):
        lines.append((FAIL, f"tunnel : le minuteur de fin ({EXPIRY_UNIT}.timer) ne tourne pas — la fin ne "
                      "tient plus que par RuntimeMaxSec : make mobile-tunnel-off, puis -on"))
    else:
        lines.append((OK, f"tunnel : le minuteur de fin l'arrêtera à la date limite ({EXPIRY_UNIT}.timer)"))
    pid = state.get("MainPID", "")
    rc, out, _ = run(["ss", "-Hltnp"])
    if rc != 0 or not pid.isdigit() or pid == "0":
        lines.append((FAIL, "tunnel : ce qu'écoute son processus ne se lit pas (ss -Hltnp, MainPID)"))
        return lines
    held = set()
    for row in out.splitlines():
        if re.search(rf"\bpid={pid}\b", row):
            held.update(parse_listeners(row))
    if held == {("127.0.0.1", console_port)}:
        lines.append((OK, f"tunnel : son processus n'écoute qu'en 127.0.0.1:{console_port}"))
    elif not held:
        lines.append((FAIL, f"tunnel : son processus ne tient pas 127.0.0.1:{console_port} (pas encore "
                      "connecté ? le port pris par la console locale ?)"))
    else:
        lines.append((FAIL, f"tunnel : son processus écoute ailleurs qu'en 127.0.0.1:{console_port}"))
    return lines


def tunnel_lines(run=_run, home: Path | None = None, host_ip: str | None = None,
                 console_port: int = CONSOLE_PORT, now: float | None = None) -> list[tuple[str, str]]:
    home = home or Path.home()
    try:
        text = _read_private(unit_path(home))
    except FileNotFoundError:
        return [(INFO, "tunnel : pas posé — make mobile-tunnel-install, puis make mobile-tunnel-on")]
    except OSError:
        return [(FAIL, f"tunnel : ~/{UNIT_DIR / UNIT_NAME} n'est pas un fichier à soi (un lien ? modifiable "
                       "par d'autres ?)")]
    lines = unit_lines(text, host_ip, console_port) + wants_lines(home)
    path = deadline_of(parse_unit(text)[0])
    return lines + service_lines(run, console_port, Path(path) if path else None, now)


def wants_lines(home: Path) -> list[tuple[str, str]]:
    """A link to the unit in a target's .wants/ (or .requires/): it would start without a gesture."""
    wants = sorted(p.parent.name for p in (home / UNIT_DIR).glob(f"*/{UNIT_NAME}"))
    if not wants:
        return []
    return [(FAIL, f"tunnel : l'unité est accrochée à {', '.join(wants)} — elle démarrerait sans geste "
                   "(au boot) : retirer ce lien")]


# ── the install, the removal, the gesture that arms it ───────────────────────

def render_unit(host_ip: str, user: str, known_hosts: Path, fingerprint: str, identity: Path | None = None,
                deadline: Path | None = None, model: Path = UNIT_MODEL) -> str:
    """The model filled; ValueError for what cannot be written into ExecStart as it is."""
    try:
        ip = ipaddress.ip_address(host_ip.strip())
    except ValueError:
        raise ValueError("l'adresse d'Imladris n'est pas une adresse") from None
    if ip.version != 4 or ip.is_loopback or ip.is_unspecified or ip.is_multicast:
        raise ValueError("l'adresse d'Imladris n'est pas une adresse IPv4 joignable")
    if not HOST_USER_NAME.fullmatch(user):
        raise ValueError("HOST_USER n'est pas un nom d'utilisateur")
    if not FINGERPRINT.fullmatch(fingerprint):
        raise ValueError("HOST_SSH_FINGERPRINT n'est pas une empreinte SHA256:…")
    deadline = deadline or known_hosts.with_name(TUNNEL_DEADLINE.name)
    for path in (known_hosts, identity, deadline):
        if path is not None and not UNIT_PATH.fullmatch(str(path)):
            raise ValueError("un chemin ne s'écrit pas tel quel dans une unité (un blanc, %, $, un guillemet)")
    text = model.read_text(encoding="utf-8")
    ident = f"-i {identity} -o IdentitiesOnly=yes " if identity else ""
    for key, value in (("@FINGERPRINT@", fingerprint), ("@KNOWN_HOSTS@", str(known_hosts)),
                       ("@DEADLINE@", str(deadline)), ("@IDENTITY@", ident), ("@TARGET@", f"{user}@{ip}")):
        if key not in text:
            raise ValueError(f"le modèle ne dit plus {key}")
        text = text.replace(key, value)
    return text


def _write(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    if tmp.is_symlink():
        tmp.unlink()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _first(err: str, out: str, rc: int) -> str:
    lines = (err or out).strip().splitlines()
    return lines[0][:120] if lines else f"code {rc}"


def _home_path(value: str, home: Path, default: Path) -> Path:
    if not value:
        return default
    path = Path(str(home) + value[1:]) if value.startswith("~/") else Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def tunnel_install(env: dict, run=_run, home: Path | None = None, say=print, dry_run: bool = False) -> int:
    """`make mobile-tunnel-install`: the unit filled from the model — the address of Imladris Terraform
    gives (MOBILE_HOST_IP), HOST_USER, HOST_SSH_KEY, the key of HOST_SSH_FINGERPRINT taken from the
    known_hosts known_host.sh checked (MOBILE_KNOWN_HOSTS) into the tunnel's own —, checked as
    mobile-check reads it, then written; never enabled, never started (make mobile-tunnel-on arms it).
    DRY_RUN: shown, nothing written."""
    home = home or Path.home()
    ip = (env.get("MOBILE_HOST_IP") or "").strip()
    if not ip:
        say("✗ aucune adresse d'Imladris (terraform output public_ip, dans infra/glorfindel-host) : "
            "make glorfindel-host-up d'abord. Rien n'est écrit.")
        return 1
    want = (env.get("HOST_SSH_FINGERPRINT") or "").strip()
    if not FINGERPRINT.fullmatch(want):
        say("✗ HOST_SSH_FINGERPRINT requis (SHA256:…, dans ton environnement) : le tunnel n'accepte jamais "
            "une clé au premier contact. Rien n'est écrit.")
        return 1
    key = (env.get("MOBILE_HOST_KEY") or "").strip()
    identity = _home_path(key, home, Path()) if key else None
    pinned = home / TUNNEL_KNOWN_HOSTS
    try:
        unit = render_unit(ip, (env.get("MOBILE_HOST_USER") or "glorfindel").strip(), pinned, want, identity,
                           home / TUNNEL_DEADLINE)
    except (ValueError, OSError) as exc:
        say(f"✗ l'unité ne s'écrit pas : {exc}. Rien n'est écrit.")
        return 1
    # The one key of Imladris with that fingerprint, from the known_hosts known_host.sh has checked.
    source = _home_path((env.get("MOBILE_KNOWN_HOSTS") or "").strip(), home, home / ".eregion" / "h0_known_hosts")
    keep = ""
    try:
        for raw in source.read_text(encoding="utf-8").splitlines():
            if known_host_fingerprints(raw, ip) == ([want], 0):
                keep = raw.strip() + "\n"
                break
    except OSError:
        pass
    if not keep and not dry_run:
        say("✗ la clé d'hôte d'Imladris de cette empreinte n'est pas dans HOST_KNOWN_HOSTS "
            "(infra/glorfindel-host/known_host.sh l'y écrit) : rien n'est écrit.")
        return 1

    def read(path):
        if Path(path) == pinned and keep:
            return keep
        raise FileNotFoundError(path)
    bad = [t for m, t in unit_lines(unit, ip, read=read) if m == FAIL]
    if not keep:                     # a dry run before known_host.sh: the pin is checked at the install
        bad = [t for t in bad if "clé d'hôte" not in t]
    if bad:
        say("✗ l'unité ne passerait pas make mobile-check : " + " ; ".join(bad) + ". Rien n'est écrit.")
        return 1
    if identity is not None and not identity.is_file():
        say("⚠ HOST_SSH_KEY : le fichier de la clé est introuvable — le tunnel ne s'authentifiera pas")
    target = unit_path(home)
    if dry_run:
        say(f"# ~/{UNIT_DIR / UNIT_NAME} — DRY_RUN=1 : rien n'est écrit, rien n'est lancé")
        say(unit.rstrip("\n"))
        say(f"# ~/{TUNNEL_KNOWN_HOSTS} : " + ("la clé épinglée, une ligne" if keep else
                                              "la clé épinglée, écrite à l'installation, après known_host.sh"))
        return 0
    existed = target.exists()
    pinned.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(pinned.parent, 0o700)
    _write(pinned, keep, 0o600)
    _write(target, unit, 0o644)
    rc, out, err = run(["systemctl", "--user", "daemon-reload"])
    if rc != 0:
        say(f"✗ systemctl --user daemon-reload a échoué ({_first(err, out, rc)}) : l'unité est écrite, "
            "make mobile-tunnel-remove la retire")
        return 1
    say(f"✓ tunnel {'réécrit' if existed else 'posé'}, non armé : ~/{UNIT_DIR / UNIT_NAME}, la clé d'hôte "
        f"épinglée dans ~/{TUNNEL_KNOWN_HOSTS} — jamais démarré au boot")
    say("  L'armer pour 12 h : make mobile-tunnel-on" + (" (déjà armé : make mobile-tunnel-off, puis -on, "
                                                          "pour prendre la nouvelle unité)" if existed else ""))
    return 0


def tunnel_on(env: dict, run=_run, home: Path | None = None, say=print, now: float | None = None) -> int:
    """`make mobile-tunnel-on`: the unit checked as mobile-check reads it (the address of Imladris
    compared with Terraform's), the deadline written (now + 12 h), the timer of expiry started, then the
    unit. Any step that fails: nothing armed."""
    home = home or Path.home()
    try:
        text = _read_private(unit_path(home))
    except OSError:
        say("✗ le tunnel n'est pas posé (ou pas un fichier à soi) : make mobile-tunnel-install d'abord. "
            "Rien n'est armé.")
        return 1
    found = unit_lines(text, (env.get("MOBILE_HOST_IP") or "").strip() or None)
    found += wants_lines(home)
    bad = [t for m, t in found if m == FAIL]
    if bad:
        say("✗ l'unité ne passe pas make mobile-check : " + " ; ".join(bad) + ". Rien n'est armé.")
        return 1
    deadline = Path(deadline_of(parse_unit(text)[0]))
    start = int(time.time() if now is None else now)
    end = start + WINDOW_S
    deadline.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write(deadline, f"{start} {end}\n", 0o600)
    for unit in (f"{EXPIRY_UNIT}.timer", f"{EXPIRY_UNIT}.service"):
        run(["systemctl", "--user", "stop", unit])
        run(["systemctl", "--user", "reset-failed", unit])
    steps = [
        ["systemd-run", "--user", f"--unit={EXPIRY_UNIT}", f"--on-active={WINDOW_S}s",
         "--timer-property=AccuracySec=1s", "--description=Eregion: the end of the console's tunnel (12 h)",
         "systemctl", "--user", "stop", UNIT_NAME],
        ["systemctl", "--user", "start", UNIT_NAME],
    ]
    for argv in steps:
        rc, out, err = run(argv)
        if rc != 0:
            run(["systemctl", "--user", "stop", f"{EXPIRY_UNIT}.timer"])
            run(["systemctl", "--user", "stop", UNIT_NAME])
            deadline.unlink(missing_ok=True)
            say(f"✗ {' '.join(argv[:3])} a échoué ({_first(err, out, rc)}) : rien n'est armé")
            return 1
    say(f"✓ tunnel armé jusqu'à {_clock(end)} (12 h) : la console d'Imladris sur le 127.0.0.1:7007 du poste")
    say("  make mobile-check : son état ; make console-url : l'URL ; make mobile-tunnel-off : l'arrêter avant")
    return 0


def tunnel_off(run=_run, home: Path | None = None, say=print) -> int:
    """`make mobile-tunnel-off`: the timer of expiry and the unit stopped, the deadline removed."""
    home = home or Path.home()
    run(["systemctl", "--user", "stop", f"{EXPIRY_UNIT}.timer"])
    rc, out, err = (0, "", "")
    if unit_path(home).exists():
        rc, out, err = run(["systemctl", "--user", "stop", UNIT_NAME])
    (home / TUNNEL_DEADLINE).unlink(missing_ok=True)
    if rc != 0:
        say(f"✗ systemctl --user stop a échoué ({_first(err, out, rc)}) : la date limite est retirée, il ne "
            "repartira pas ; make mobile-check")
        return 1
    say("✓ tunnel désarmé : le 127.0.0.1:7007 du poste n'est plus tenu")
    return 0


def tunnel_remove(run=_run, home: Path | None = None, say=print, dry_run: bool = False) -> int:
    """`make mobile-tunnel-remove`: the tunnel stopped, then its unit, known_hosts and deadline removed.
    DRY_RUN: said, nothing done."""
    home = home or Path.home()
    there = [p for p in (unit_path(home), home / TUNNEL_KNOWN_HOSTS, home / TUNNEL_DEADLINE)
             if p.exists() or p.is_symlink()]
    if not there:
        say("✓ aucun tunnel posé : rien à retirer")
        return 0
    if dry_run:
        say(f"DRY_RUN=1 : systemctl --user stop {UNIT_NAME}, puis retirés : "
            + ", ".join(f"~/{p.relative_to(home)}" for p in there) + " — rien n'est fait")
        return 0
    code = tunnel_off(run, home, lambda _line: None)
    for p in there:
        if p.exists() or p.is_symlink():
            p.unlink()
    run(["systemctl", "--user", "daemon-reload"])
    say("✓ tunnel retiré : l'unité, son known_hosts et sa date limite" if code == 0 else
        "✗ tunnel retiré du disque, son arrêt à vérifier (make mobile-check)")
    return code


def guard(target: str, env: dict | None = None, cwd=None, here=None, never: str = NEVER_TOKEN,
          say=None) -> int:
    """The refusal of a code session, alone, before anything is read (make runs it first)."""
    refusal = bs.session_refusal(env, cwd, here, never=never)
    if refusal:
        (say or (lambda line: print(line, file=sys.stderr)))(
            f"✗ make {target} refusé : {refusal}. Rien n'est lu, rien n'est lancé.")
        return 1
    return 0


def check(console_port: int = CONSOLE_PORT, run=_run, home: Path | None = None, host_ip: str | None = None,
          now: float | None = None) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    ip, why = private_ipv4(run)
    private: set[str] = set()
    if ip:
        private.add(ip)
        lines.append((OK, "réseau privé : une adresse du tailnet (la plage de Tailscale)"))
        rc6, out6, _ = run(["tailscale", "ip", "-6"])
        for word in (out6.split() if rc6 == 0 else []):
            try:
                v6 = ipaddress.ip_address(word)
            except ValueError:
                continue
            if v6 in TAILNET_V6:
                private.add(str(v6))
    else:
        lines.append((FAIL, f"réseau privé : {why}"))
    rc, out, _ = run(["tailscale", "debug", "prefs"])
    lines.append(tailscale_ssh_line(out, rc))

    sshd = ["sshd", "-T"] if os.geteuid() == 0 else ["sudo", "-n", "sshd", "-T"]
    rc, out, err = run(sshd)
    conf = parse_sshd(out) if rc == 0 else {}
    if rc != 0 or not conf:
        first = (err or out).strip().splitlines()
        lines.append((FAIL, "SSH : sshd -T ne se lit pas (" + (first[0][:100] if first else f"code {rc}")
                      + ") — sudo -v, puis make mobile-check"))
        ports = {22}
    else:
        ports = {int(p) for p in conf.get("port", ["22"]) if p.isdigit()} or {22}
        lines += sshd_lines(conf, console_port)
    rc, out, err = run(["ss", "-Hltn"])
    if rc != 0:
        lines.append((FAIL, f"les écoutes ne se lisent pas (ss -Hltn : code {rc})"))
    else:
        lines += listener_lines(parse_listeners(out), private, ports, console_port)
    lines.append(keys_line((home or Path.home()) / ".ssh" / "authorized_keys"))
    lines += tunnel_lines(run, home, host_ip, console_port, now)
    return lines


def render(lines: list[tuple[str, str]]) -> tuple[str, int]:
    fails = sum(1 for m, _ in lines if m == FAIL)
    warns = sum(1 for m, _ in lines if m == WARN)
    text = "\n".join(f"{m} {t}" for m, t in lines)
    if fails:
        verdict = f"\n✗ {fails} point(s) à fermer avant d'ouvrir le poste au téléphone (docs/demarrer/mobile.md)"
    else:
        verdict = "\n✓ le poste ne s'ouvre au téléphone que par le réseau privé et la clé" + (
            f" ({warns} ⚠ à lire)" if warns else "")
    return text + verdict, 1 if fails else 0


def main(argv: list[str] | None = None, run=_run, home: Path | None = None, env: dict | None = None,
         cwd=None, here=None, say=print, now: float | None = None) -> int:
    env = dict(os.environ) if env is None else env
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--console-port", type=int, default=CONSOLE_PORT)
    c.add_argument("--host-ip", default=env.get("MOBILE_HOST_IP") or "",
                   help="the address of Imladris Terraform gives now (make passes it)")
    g = sub.add_parser("guard", help="the refusal of a code session, alone (the console's token)")
    g.add_argument("target")
    for name in ("tunnel-install", "tunnel-remove", "tunnel-on", "tunnel-off"):
        t = sub.add_parser(name)
        t.add_argument("--dry-run", action="store_true", default=(env.get("MOBILE_DRY_RUN") or "") == "1")
        t.add_argument("--guard-only", action="store_true",
                       help="the guard alone: make runs it before anything else is expanded")
    args = p.parse_args(argv)
    if args.cmd == "check":
        text, code = render(check(args.console_port, run, home, args.host_ip or None, now))
        say(text)
        return code
    if args.cmd == "guard":
        return guard(args.target, env, cwd, here)
    target = f"mobile-{args.cmd}"
    if guard(target, env, cwd, here, never=NEVER_TUNNEL, say=say):
        return 1
    if args.guard_only:
        return 0
    if args.cmd == "tunnel-install":
        return tunnel_install(env, run, home, say, args.dry_run)
    if args.cmd == "tunnel-remove":
        return tunnel_remove(run, home, say, args.dry_run)
    if args.dry_run:
        say(f"DRY_RUN=1 : make {target} ne fait rien à blanc — make mobile-check dit l'état")
        return 0
    if args.cmd == "tunnel-on":
        return tunnel_on(env, run, home, say, now)
    return tunnel_off(run, home, say)


if __name__ == "__main__":
    sys.exit(main())
