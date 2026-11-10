#!/usr/bin/env python3
"""mobile — the workstation reached from the phone, held by two barriers (MOB1, #686; docs/demarrer/mobile.md).

  mobile.py check [--console-port 7007]    `make mobile-check`: read-only, one line ✓/⚠/✗ per check, exit 1
                                           on a ✗

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

No address is printed. Nothing is written, nothing is installed. The global configuration only: a
`Match` block can change it for one connection (said in the guide).
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

OK, WARN, FAIL = "✓", "⚠", "✗"
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


def check(console_port: int = CONSOLE_PORT, run=_run, home: Path | None = None) -> list[tuple[str, str]]:
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


def main(argv: list[str] | None = None, run=_run, home: Path | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--console-port", type=int, default=CONSOLE_PORT)
    args = p.parse_args(argv)
    text, code = render(check(args.console_port, run, home))
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
