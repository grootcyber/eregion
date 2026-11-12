"""The workstation reached from the phone (MOB1, #686): `make imladris-tunnel-check`.

`make imladris-tunnel-check` reads, and only reads, what holds the two barriers — the private network, then the
SSH server by key alone. It runs here on fakes of `tailscale`, `ss`, `sshd -T` and `sudo`, first on
PATH: it must see a listener on every interface, a password admitted, a key handed by a command or a
certificate authority, a forwarding wider than the phone's local tunnel to 127.0.0.1:7007, a gateway
port, a console port listening elsewhere than on 127.0.0.1, Tailscale SSH open. The console reaches the
phone through the phone's own SSH tunnel (decision of Jonathan, 10/11): nothing changes on H0, nothing
binds the private address. The model of the SSH server (infra/poste/sshd_config.d/00-eregion.conf)
passes the checks it was written for. No address is printed.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mob = _load("mobile")
needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

PRIVATE = "100.101.102.103"
V6 = "fd7a:115c:a1e0::1234"
GOOD_SSHD = """port 22
listenaddress 100.101.102.103:22
passwordauthentication no
kbdinteractiveauthentication no
permitemptypasswords no
hostbasedauthentication no
gssapiauthentication no
pubkeyauthentication yes
authenticationmethods publickey
authorizedkeysfile .ssh/authorized_keys
authorizedkeyscommand none
trustedusercakeys none
allowtcpforwarding local
permitopen 127.0.0.1:7007
gatewayports no
allowstreamlocalforwarding no
allowagentforwarding no
x11forwarding no
permitrootlogin no
"""
GOOD_SS = f"LISTEN 0 128 {PRIVATE}:22 0.0.0.0:*\nLISTEN 0 4096 127.0.0.53%lo:53 0.0.0.0:*\n"
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def world(**over):
    w = {"ip4": PRIVATE + "\n", "ip6": V6 + "\n", "prefs": json.dumps({"RunSSH": False}), "sshd": GOOD_SSHD,
         "ss": GOOD_SS, "ip4_rc": 0, "sshd_rc": 0}
    w.update(over)
    return w


def fake_run(w):
    def run(argv, timeout=30):
        if argv[:3] == ["tailscale", "ip", "-4"]:
            return w["ip4_rc"], w["ip4"], "" if w["ip4_rc"] == 0 else "failed to connect to local tailscaled"
        if argv[:3] == ["tailscale", "ip", "-6"]:
            return 0, w["ip6"], ""
        if argv[:3] == ["tailscale", "debug", "prefs"]:
            return 0, w["prefs"], ""
        if argv[-2:] == ["sshd", "-T"]:
            return w["sshd_rc"], w["sshd"] if w["sshd_rc"] == 0 else "", "" if w["sshd_rc"] == 0 else "sudo: a password is required"
        if argv[:2] == ["ss", "-Hltn"]:
            return 0, w["ss"], ""
        raise AssertionError(f"unexpected command {argv}")
    return run


def _check(tmp_path, keys="ecdsa-sha2-nistp256 AAAAE2Vj phone\n", **over):
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True, exist_ok=True)
    if keys is not None:
        (home / ".ssh" / "authorized_keys").write_text(keys)
        (home / ".ssh" / "authorized_keys").chmod(0o600)
    lines = mob.check(7007, fake_run(world(**over)), home)
    text, code = mob.render(lines)
    return code, text, lines


def t_tunnel(text):
    return text.startswith("tunnel :")


def _marks(lines, word):
    return [m for m, t in lines if word in t]


def _sshd(key, value):
    """GOOD_SSHD with one keyword's value replaced (or the keyword removed, value None)."""
    out = [ln for ln in GOOD_SSHD.splitlines() if not ln.startswith(key + " ")]
    return "\n".join(out + ([f"{key} {value}"] if value is not None else [])) + "\n"


# ── the private address ──────────────────────────────────────────────────────

@pytest.mark.parametrize("out,ok", [
    (PRIVATE + "\n", True), ("100.64.0.1", True), ("100.127.255.254", True),
    ("", False), ("0.0.0.0", False), ("127.0.0.1", False), ("192.168.1.10", False), ("100.128.0.1", False),
    (f"{PRIVATE}\n100.64.0.9\n", False), ("::1", False), ("garbage", False),
])
def test_the_private_address_is_one_tailnet_ipv4_or_none(out, ok):
    ip, why = mob.tailnet_ipv4(out)
    assert bool(ip) is ok and (ip == out.split()[0] if ok else why)


def test_a_lan_address_given_for_the_tailnet_s_is_never_the_private_one(tmp_path):
    """The SSH server listening on a LAN address that `tailscale ip -4` would give: never read as private."""
    code, text, lines = _check(tmp_path, ip4="192.168.1.10\n", ss="LISTEN 0 128 192.168.1.10:22 0.0.0.0:*\n")
    assert code == 1 and any(m == mob.FAIL and "une autre adresse" in t for m, t in lines), text


# ── imladris-tunnel-check, on fakes ───────────────────────────────────────────────────

def test_a_workstation_in_order_passes(tmp_path):
    code, text, lines = _check(tmp_path)
    assert code == 0, text
    assert all(m == mob.OK for m, t in lines if not t_tunnel(t)), text
    assert [m for m, t in lines if t_tunnel(t)] == [mob.INFO], text     # MOB2: no tunnel set, said, not a ✗
    assert "1 clé(s) admise(s) (1 ecdsa-sha2-nistp256)" in text
    assert IP.findall(text.replace("127.0.0.1", "")) == [] and "AAAAE2Vj" not in text


@pytest.mark.parametrize("ss,said", [
    ("LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n", "toutes les interfaces"),
    ("LISTEN 0 128 [::]:22 [::]:*\n" f"LISTEN 0 128 {PRIVATE}:22 0.0.0.0:*\n", "toutes les interfaces"),
    ("LISTEN 0 4096 *:22 *:*\n", "toutes les interfaces"),
    ("LISTEN 0 128 127.0.0.1:22 0.0.0.0:*\n", "boucle locale"),
    ("LISTEN 0 128 192.168.1.10:22 0.0.0.0:*\n", "une autre adresse"),
    ("", "n'écoute pas"),
])
def test_an_ssh_server_listening_elsewhere_than_the_private_address_is_seen(tmp_path, ss, said):
    code, text, lines = _check(tmp_path, ss=ss)
    assert code == 1
    assert any(m == mob.FAIL and said in t for m, t in lines), text
    assert IP.findall(text.replace("127.0.0.1", "")) == []


@pytest.mark.parametrize("key,value", [
    ("passwordauthentication", "yes"), ("kbdinteractiveauthentication", "yes"), ("permitemptypasswords", "yes"),
    ("hostbasedauthentication", "yes"), ("pubkeyauthentication", "no"), ("gssapiauthentication", "yes"),
    ("gatewayports", "yes"), ("gatewayports", "clientspecified"),
    ("authorizedkeyscommand", "/usr/bin/sss_ssh_authorizedkeys"), ("trustedusercakeys", "/etc/ssh/ca.pub"),
    ("allowstreamlocalforwarding", "yes"), ("allowstreamlocalforwarding", "local"),
    ("allowagentforwarding", "yes"), ("x11forwarding", "yes"),
])
def test_a_password_or_another_way_in_admitted_is_seen(tmp_path, key, value):
    code, text, lines = _check(tmp_path, sshd=_sshd(key, value))
    assert code == 1
    assert _marks(lines, f"{key} {value}") == [mob.FAIL], text


@pytest.mark.parametrize("value,mark", [(".ssh/authorized_keys", mob.OK), ("%h/.ssh/authorized_keys", mob.OK),
                                        (".ssh/authorized_keys .ssh/authorized_keys2", mob.FAIL),
                                        ("/etc/ssh/keys/%u", mob.FAIL), (None, mob.FAIL)])
def test_the_keys_come_from_the_user_s_file_alone(tmp_path, value, mark):
    code, text, lines = _check(tmp_path, sshd=_sshd("authorizedkeysfile", value))
    assert _marks(lines, "authorizedkeysfile") == [mark], text


@pytest.mark.parametrize("value,mark", [("local", mob.OK), ("no", mob.WARN), ("yes", mob.FAIL), ("all", mob.FAIL),
                                        ("remote", mob.FAIL), (None, mob.FAIL)])
def test_forwarding_is_the_phone_s_local_tunnel_alone(tmp_path, value, mark):
    code, text, lines = _check(tmp_path, sshd=_sshd("allowtcpforwarding", value))
    assert _marks(lines, "allowtcpforwarding") == [mark], text
    assert code == (1 if mark == mob.FAIL else 0)


@pytest.mark.parametrize("value,mark", [("127.0.0.1:7007", mob.OK), ("any", mob.FAIL), ("127.0.0.1:22", mob.FAIL),
                                        ("127.0.0.1:7007 10.0.0.4:22", mob.FAIL), ("*:7007", mob.FAIL),
                                        ("none", mob.FAIL), (None, mob.FAIL)])
def test_the_tunnel_opens_onto_the_console_alone(tmp_path, value, mark):
    code, text, lines = _check(tmp_path, sshd=_sshd("permitopen", value))
    assert _marks(lines, "permitopen") == [mark], text


@pytest.mark.parametrize("methods,ok", [("any", True), ("publickey", True), ("publickey,publickey", True),
                                        ("publickey,password", False), ("password", False),
                                        ("publickey keyboard-interactive", False)])
def test_authentication_methods_the_key_alone(tmp_path, methods, ok):
    code, text, lines = _check(tmp_path, sshd=_sshd("authenticationmethods", methods))
    assert _marks(lines, "authenticationmethods") == [mob.OK if ok else mob.FAIL]


def test_an_absent_keyword_is_not_a_no(tmp_path):
    code, text, lines = _check(tmp_path, sshd=_sshd("passwordauthentication", None))
    assert code == 1 and _marks(lines, "passwordauthentication") == [mob.FAIL]


@pytest.mark.parametrize("extra,mark", [
    ("LISTEN 0 128 127.0.0.1:7007 0.0.0.0:*\n", mob.OK),
    ("LISTEN 0 128 127.0.0.1:7007 0.0.0.0:*\nLISTEN 0 128 [::1]:7007 [::]:*\n", mob.OK),
    (f"LISTEN 0 128 {PRIVATE}:7007 0.0.0.0:*\n", mob.FAIL),
    (f"LISTEN 0 128 [{V6}]:7007 [::]:*\n", mob.FAIL),
    ("LISTEN 0 128 0.0.0.0:7007 0.0.0.0:*\n", mob.FAIL),
    ("LISTEN 0 128 [::]:7007 [::]:*\n", mob.FAIL),
    ("LISTEN 0 128 192.168.1.10:7007 0.0.0.0:*\n", mob.FAIL),
    ("LISTEN 0 128 127.0.0.2:7007 0.0.0.0:*\n", mob.FAIL),
    ("", mob.OK),
])
def test_the_console_s_port_listens_on_127_0_0_1_alone(tmp_path, extra, mark):
    code, text, lines = _check(tmp_path, ss=GOOD_SS + extra)
    assert _marks(lines, "console : le port 7007") == [mark], text
    assert code == (1 if mark == mob.FAIL else 0)


@pytest.mark.parametrize("prefs", ["", "not json", "[]", json.dumps({"RunSSH": "no"}), json.dumps({})])
def test_tailscale_prefs_unread_is_a_fail_never_a_green_verdict(tmp_path, prefs):
    code, text, lines = _check(tmp_path, prefs=prefs)
    assert code == 1 and _marks(lines, "Tailscale SSH") == [mob.FAIL], text
    assert "✓ le poste ne s'ouvre" not in text


def test_tailscale_ssh_open_is_one_barrier_not_two(tmp_path):
    code, text, lines = _check(tmp_path, prefs=json.dumps({"RunSSH": True}))
    assert code == 1 and _marks(lines, "Tailscale SSH") == [mob.FAIL]


def test_without_the_tailnet_every_listener_is_elsewhere(tmp_path):
    code, text, lines = _check(tmp_path, ip4_rc=1, ip4="")
    assert code == 1
    assert _marks(lines, "réseau privé : tailscale ip -4") == [mob.FAIL]
    assert any(m == mob.FAIL and "une autre adresse" in t for m, t in lines)


def test_an_sshd_that_cannot_be_read_is_a_fail(tmp_path):
    code, text, lines = _check(tmp_path, sshd_rc=1)
    assert code == 1 and "sudo -v" in text


@pytest.mark.parametrize("keys,mark", [(None, mob.WARN), ("", mob.WARN), ("# none\n", mob.WARN),
                                       ('from="100.64.0.0/10",permitopen="127.0.0.1:7007" '
                                        'sk-ecdsa-sha2-nistp256@openssh.com AAAA x\n', mob.OK)])
def test_the_keys_are_counted_never_printed(tmp_path, keys, mark):
    code, text, lines = _check(tmp_path, keys=keys)
    assert _marks(lines, "clés") == [mark]
    assert "AAAA" not in text


def test_a_writable_authorized_keys_is_a_fail(tmp_path):
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    f = home / ".ssh" / "authorized_keys"
    f.write_text("ssh-ed25519 AAAA x\n")
    f.chmod(0o666)
    assert mob.keys_line(f)[0] == mob.FAIL


def test_the_model_of_the_ssh_server_passes_the_checks_it_was_written_for():
    conf = mob.parse_sshd((ROOT / "infra/poste/sshd_config.d/00-eregion.conf").read_text(encoding="utf-8"))
    assert all(m == mob.OK for m, _ in mob.sshd_lines(conf)), mob.sshd_lines(conf)
    listen = conf["listenaddress"]
    assert len(listen) == 1 and mob.tailnet_ipv4(listen[0])[0] == listen[0]
    for key in ("allowagentforwarding", "allowstreamlocalforwarding", "x11forwarding", "permittunnel"):
        assert conf[key] == ["no"]


def test_the_access_rule_opens_the_ssh_server_alone():
    text = (ROOT / "infra/poste/tailscale-acl.hujson").read_text(encoding="utf-8")
    dst = re.findall(r'"dst":\s*\[([^\]]*)\]', text)
    assert dst == ['"workstation:22"'] and '"ssh": []' in text


# ── through make, on fake commands ───────────────────────────────────────────

@pytest.fixture
def fake_bin(tmp_path):
    """`tailscale`, `ss`, `sshd` and `sudo` (which runs what follows -n), first on PATH; their answers
    read from files the test writes."""
    b = tmp_path / "bin"
    b.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    for name in ("tailscale", "ss", "sshd"):
        (b / name).write_text(f"#!{sys.executable}\nimport os, sys\n"
                              f"key = '_'.join(['{name}'] + [a.strip('-') for a in sys.argv[1:]])\n"
                              f"p = os.path.join({str(data)!r}, key)\n"
                              "if not os.path.exists(p):\n    sys.exit(1)\n"
                              "sys.stdout.write(open(p).read())\n")
    (b / "sudo").write_text('#!/bin/sh\n[ "$1" = -n ] && shift\nexec "$@"\n')
    for f in b.iterdir():
        f.chmod(0o755)

    def answer(**files):
        for k, v in files.items():
            (data / k).write_text(v)
    return b, answer


def _make(fake, target, *args):
    b = fake[0]
    env = {**os.environ, "PATH": f"{b}{os.pathsep}{os.environ['PATH']}", "HOME": str(b.parent)}
    env.pop("MOBILE_HOST_IP", None)
    args = ("HOST_IP=", *args)             # no terraform output read: the address of Imladris unread
    return subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, f"PYTHON={sys.executable}",
                           *args], capture_output=True, text=True, env=env, timeout=60)


@needs_make
def test_make_mobile_check_sees_every_interface_a_password_and_a_wide_tunnel(fake_bin):
    _, answer = fake_bin
    answer(tailscale_ip_4=PRIVATE + "\n", tailscale_ip_6="", tailscale_debug_prefs='{"RunSSH": false}',
           sshd_T=_sshd("passwordauthentication", "yes").replace("allowtcpforwarding local", "allowtcpforwarding yes")
           .replace("permitopen 127.0.0.1:7007", "permitopen any"),
           ss_Hltn="LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\nLISTEN 0 128 0.0.0.0:7007 0.0.0.0:*\n")
    res = _make(fake_bin, "imladris-tunnel-check")
    assert res.returncode != 0
    for said in ("✗ SSH : le serveur écoute sur toutes les interfaces", "✗ SSH : passwordauthentication yes, no attendu",
                 "✗ SSH : allowtcpforwarding yes — local attendu", "✗ SSH : permitopen any",
                 "✗ console : le port 7007 est exposé sur toutes les interfaces"):
        assert said in res.stdout, res.stdout
    answer(sshd_T=GOOD_SSHD, ss_Hltn=GOOD_SS + "LISTEN 0 128 127.0.0.1:7007 0.0.0.0:*\n")
    (fake_bin[0].parent / ".ssh").mkdir()
    (fake_bin[0].parent / ".ssh" / "authorized_keys").write_text("ecdsa-sha2-nistp256 AAAA phone\n")
    res = _make(fake_bin, "imladris-tunnel-check")
    assert res.returncode == 0, res.stdout + res.stderr
    assert IP.findall(res.stdout.replace("127.0.0.1", "")) == []


def test_nothing_binds_the_console_on_the_private_address_any_more():
    """The tunnel on the private address is gone with the decision of 10/11: no target binds it."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "imladris-tunnel-private" not in makefile and "private-ip" not in makefile


# ── MOB2: the workstation's tunnel to the console of Imladris, armed on demand for 12 h ────────────────
#
# Decision of Jonathan (11/11): not permanent. A user unit of systemd, never started at boot (no
# [Install]), armed by `make imladris-tunnel-on` for 12 h at most — a deadline, a timer of expiry, an
# ExecCondition that refuses any (re)start past the deadline, RuntimeMaxSec on each run —, its port on
# 127.0.0.1 alone, the host key of Imladris pinned. Everything here runs on fakes of `systemctl`,
# `systemd-run`, `ss`, `terraform` and `ssh-keyscan`: nothing is installed, nothing started.


HOST = "203.0.113.9"
OTHER_HOST = "198.51.100.7"
BLOB = base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"k" * 32).decode()
OTHER_BLOB = base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"z" * 32).decode()
FP = mob.fingerprint_of(BLOB)
NOW = 1_800_000_000
# As under systemd: MainPID is timeout's, ssh its child, the one that listens; both in the unit's cgroup.
PID = "4242"
SSH_PID = "4243"
CG = "/user.slice/user-1000.slice/user@1000.service/app.slice/eregion-console-tunnel.service"


def _home(tmp_path) -> Path:
    home = tmp_path / "op"
    home.mkdir(exist_ok=True)
    return home


def _set_tunnel(home, unit=None, known=None, window=(NOW - 600, NOW - 600 + mob.WINDOW_S), **over):
    """The tunnel as make imladris-tunnel-install and -on leave it: the unit, its known_hosts, its deadline."""
    text = unit if unit is not None else mob.render_unit(
        HOST, "glorfindel", home / mob.TUNNEL_KNOWN_HOSTS, FP, None, home / mob.TUNNEL_DEADLINE)
    for old, new in over.items():
        assert old in text or old == "_", old
        text = text.replace(old, new)
    path = mob.unit_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o644)
    kh = home / mob.TUNNEL_KNOWN_HOSTS
    kh.parent.mkdir(parents=True, exist_ok=True)
    kh.write_text(f"{HOST} ssh-ed25519 {BLOB}\n" if known is None else known)
    kh.chmod(0o600)
    if window is not None:
        (home / mob.TUNNEL_DEADLINE).write_text(f"{window[0]} {window[1]}\n")
        (home / mob.TUNNEL_DEADLINE).chmod(0o600)
    return text


def tunnel_world(**over):
    """What systemd and ss say of an armed tunnel, in order."""
    # FragmentPath None: the unit's own path under the world's home, as systemd says it.
    w = {"unit": {"LoadState": "loaded", "ActiveState": "active", "SubState": "running", "UnitFileState": "static",
                  "NRestarts": "1", "MainPID": PID, "ControlGroup": CG, "FragmentPath": None, "DropInPaths": "",
                  "NeedDaemonReload": "no", "RuntimeMaxUSec": "12h", "WantedBy": "", "RequiredBy": "",
                  "BoundBy": "", "UpheldBy": "", "TriggeredBy": "", "OnFailureOf": "", "OnSuccessOf": ""},
         "timer": {"LoadState": "loaded", "ActiveState": "active"},
         "ss_p": f"LISTEN 0 128 127.0.0.1:7007 0.0.0.0:* users:((\"ssh\",pid={SSH_PID},fd=4))\n",
         "files": {f"/sys/fs/cgroup{CG}/cgroup.procs": f"{PID}\n{SSH_PID}\n",
                   f"/proc/{PID}/task/{PID}/children": f"{SSH_PID} "},
         "show_rc": 0, "fail": set(), "calls": [], "home": None}
    for k, v in over.items():
        if k in ("unit", "timer"):
            w[k] = {**w[k], **v}
        else:
            w[k] = v
    return w


def tunnel_run(tw, base=None):
    """systemctl, systemd-run and ss -Hltnp on a world; every call written down; the rest to `base`."""
    def run(argv, timeout=30):
        tw["calls"].append(list(argv))
        if argv[:3] == ["systemctl", "--user", "show"]:
            if tw["show_rc"]:
                return tw["show_rc"], "", "Failed to connect to bus: No medium found"
            state = tw["timer"] if argv[3].endswith(".timer") else tw["unit"]
            fragment = str(mob.unit_path(tw["home"])) if tw["home"] else ""
            return 0, "".join(f"{k}={fragment if v is None else v}\n" for k, v in state.items()), ""
        if argv[:2] == ["ss", "-Hltnp"]:
            return 0, tw["ss_p"], ""
        if argv[0] == "cat" and len(argv) == 2:
            text = tw["files"].get(argv[1])
            return (0, text, "") if text is not None else (1, "", f"cat: {argv[1]}: No such file or directory")
        if argv[0] in ("systemctl", "systemd-run"):
            verb = argv[0] if argv[0] == "systemd-run" else argv[2]
            return (1, "", f"{verb}: refused") if verb in tw["fail"] else (0, "", "")
        if base is not None:
            return base(argv, timeout)
        raise AssertionError(f"unexpected command {argv}")
    return run


def _tunnel(tmp_path, host_ip=HOST, now=NOW, **over):
    home = _home(tmp_path)
    tw = tunnel_world(home=home, **over)
    lines = mob.tunnel_lines(tunnel_run(tw), home, host_ip, 7007, now)
    return lines, tw


def _fails(lines):
    return [t for m, t in lines if m == mob.FAIL]


# ── the unit: the model's, read as imladris-tunnel-check reads it ─────────────────────

def test_the_model_filled_passes_every_check_of_the_unit(tmp_path):
    home = _home(tmp_path)
    text = _set_tunnel(home)
    lines = mob.unit_lines(text, HOST)
    assert lines and all(m == mob.OK for m, _ in lines), lines
    sections, odd = mob.parse_unit(text)
    assert "Install" not in sections and not odd and sections["Service"]["RuntimeMaxSec"] == ["12h"]
    assert "-L 127.0.0.1:7007:127.0.0.1:7007 glorfindel@203.0.113.9" in text and f"X-Eregion-HostKey={FP}" in text


@pytest.mark.parametrize("change,said", [
    # never at boot
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=12h\n\n[Install]\nWantedBy=default.target\n"}, "section [Install]"),
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=12h\n[Install]\n"}, "section [Install]"),
    # 12 h at most
    ({"RuntimeMaxSec=12h\n": ""}, "sans limite de durée"),
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=infinity\n"}, "sans limite de durée"),
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=13h\n"}, "sans limite de durée"),
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=2d\n"}, "sans limite de durée"),
    ({"ExecCondition=": "#ExecCondition="}, "ne lit pas la date limite"),
    ({"-lt": "-gt"}, "ne lit pas la date limite"),
    # 127.0.0.1 alone, one forward to the console
    ({"-L 127.0.0.1:7007:127.0.0.1:7007": "-L 0.0.0.0:7007:127.0.0.1:7007"}, "sur toutes les interfaces"),
    ({"-L 127.0.0.1:7007:127.0.0.1:7007": "-L *:7007:127.0.0.1:7007"}, "sur toutes les interfaces"),
    ({"-L 127.0.0.1:7007:127.0.0.1:7007": "-L 7007:127.0.0.1:7007"}, "sans adresse de liaison"),
    ({"-L 127.0.0.1:7007:127.0.0.1:7007": f"-L {PRIVATE}:7007:127.0.0.1:7007"}, "l'adresse privée"),
    ({"-L 127.0.0.1:7007:127.0.0.1:7007": "-L 192.168.1.10:7007:127.0.0.1:7007"}, "une autre adresse"),
    ({"-L 127.0.0.1:7007:127.0.0.1:7007": "-L 127.0.0.1:7007:127.0.0.1:22"}, "autre chose que la console"),
    ({"-L 127.0.0.1:7007:127.0.0.1:7007": "-L 127.0.0.1:7007:127.0.0.1:7007 -L 127.0.0.1:2222:127.0.0.1:22"},
     "2 redirections"),
    ({"-L 127.0.0.1:7007": "-g -L 127.0.0.1:7007"}, "autre chose que le modèle"),
    ({"-L 127.0.0.1:7007": "-R 0.0.0.0:2222:127.0.0.1:22 -L 127.0.0.1:7007"}, "autre chose que le modèle"),
    ({"-L 127.0.0.1:7007": "-D 1080 -L 127.0.0.1:7007"}, "autre chose que le modèle"),
    ({"-o BatchMode=yes": "-o BatchMode=yes -o GatewayPorts=yes"}, "autre chose que le modèle"),
    ({"-o BatchMode=yes": "-o BatchMode=yes -o ProxyCommand=nc"}, "autre chose que le modèle"),
    ({"Restart=on-failure\n": "Restart=on-failure\nExecStartPre=/bin/true\n"}, "autre chose que le modèle"),
    ({"/usr/bin/ssh": "-/usr/bin/ssh"}, "autre chose que le modèle"),
    # the host key pinned
    ({"StrictHostKeyChecking=yes": "StrictHostKeyChecking=no"}, "StrictHostKeyChecking=yes absent"),
    ({"StrictHostKeyChecking=yes": "StrictHostKeyChecking=accept-new"}, "StrictHostKeyChecking=yes absent"),
    ({"-o BatchMode=yes": "-o StrictHostKeyChecking=no -o BatchMode=yes"}, "dite deux fois"),
    ({"-o GlobalKnownHostsFile=/dev/null": ""}, "GlobalKnownHostsFile=/dev/null absent"),
    ({f"X-Eregion-HostKey={FP}\n": ""}, "ne nomme pas l'empreinte"),
    # a tunnel that holds by itself
    ({"ExitOnForwardFailure=yes": "ExitOnForwardFailure=no"}, "exitonforwardfailure=yes"),
    ({"-o ServerAliveInterval=30 ": ""}, "serveraliveinterval entre"),
    ({"ServerAliveCountMax=3": "ServerAliveCountMax=0"}, "serveralivecountmax entre"),
    ({"Restart=on-failure": "Restart=no"}, "Restart=on-failure"),
    ({"-F none ": ""}, "-F none"),
    ({"RestartSec=15": "RestartSec=0"}, "RestartSec"),
])
def test_a_unit_other_than_the_model_is_a_fail(tmp_path, change, said):
    home = _home(tmp_path)
    text = _set_tunnel(home, **change)
    fails = _fails(mob.unit_lines(text, HOST))
    assert any(said in t for t in fails), fails


@pytest.mark.parametrize("known,said", [
    (f"{HOST} ssh-ed25519 {OTHER_BLOB}\n", "une autre clé"),
    (f"{HOST} ssh-ed25519 {BLOB}\n{HOST} ssh-ed25519 {OTHER_BLOB}\n", "une autre clé"),
    (f"{HOST} ssh-ed25519 {BLOB}\n{OTHER_HOST} ssh-ed25519 {BLOB}\n", "une autre clé"),
    (f"@cert-authority * ssh-ed25519 {OTHER_BLOB}\n{HOST} ssh-ed25519 {BLOB}\n", "une autre clé"),
    (f"{OTHER_HOST} ssh-ed25519 {BLOB}\n", "aucune clé"),
    ("", "aucune clé"),
])
def test_the_host_key_is_pinned_by_the_unit_s_fingerprint(tmp_path, known, said):
    home = _home(tmp_path)
    text = _set_tunnel(home, known=known)
    fails = _fails(mob.unit_lines(text, HOST))
    assert any("n'est pas épinglée" in t and said in t for t in fails), fails


def test_a_known_hosts_another_may_write_is_no_pin(tmp_path):
    home = _home(tmp_path)
    text = _set_tunnel(home)
    (home / mob.TUNNEL_KNOWN_HOSTS).chmod(0o666)
    assert any("ne se lit pas" in t for t in _fails(mob.unit_lines(text, HOST)))
    (home / mob.TUNNEL_KNOWN_HOSTS).unlink()
    assert any("ne se lit pas" in t for t in _fails(mob.unit_lines(text, HOST)))


def test_a_hashed_known_hosts_line_is_read():
    import hashlib
    import hmac
    salt = b"0123456789abcdefghij"
    digest = base64.b64encode(hmac.new(salt, HOST.encode(), hashlib.sha1).digest()).decode()
    line = f"|1|{base64.b64encode(salt).decode()}|{digest} ssh-ed25519 {BLOB}\n"
    assert mob.known_host_fingerprints(line, HOST) == ([FP], 0)
    assert mob.known_host_fingerprints(line, OTHER_HOST) == ([], 1)


def test_the_fingerprint_is_ssh_keygen_s(tmp_path):
    """fingerprint_of says what `ssh-keygen -lf` says (when ssh-keygen is there: nothing is installed)."""
    if shutil.which("ssh-keygen") is None:
        pytest.skip("ssh-keygen not installed")
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True,
                   capture_output=True, timeout=30)
    pub = (tmp_path / "k.pub").read_text().split()
    said = subprocess.run(["ssh-keygen", "-lf", str(tmp_path / "k.pub")], capture_output=True, text=True,
                          check=True, timeout=30).stdout.split()[1]
    assert mob.fingerprint_of(pub[1]) == said


@pytest.mark.parametrize("host_ip,mark", [(HOST, mob.OK), (OTHER_HOST, mob.FAIL), (None, mob.WARN), ("", mob.WARN)])
def test_imladris_redeployed_under_another_address_is_seen(tmp_path, host_ip, mark):
    home = _home(tmp_path)
    lines = mob.unit_lines(_set_tunnel(home), host_ip)
    assert [m for m, t in lines if "adresse d'Imladris" in t or "n'est plus à l'adresse" in t] == [mark], lines


@pytest.mark.parametrize("value,seconds", [("12h", 43200), ("43200", 43200), ("720min", 43200), ("12h 0min", 43200),
                                           ("30s", 30), ("infinity", None), ("", None), ("2d", None)])
def test_durations_read_as_systemd_writes_them(value, seconds):
    assert mob.duration_s(value) == seconds


# ── the unit's ExecCondition, as /bin/sh runs it ─────────────────────────────

@pytest.mark.parametrize("window,starts", [((NOW - 60, None), True), ((NOW - 60, -10), False), (None, False),
                                           ("garbage", False), ((NOW - 60, 12 * 3600 - 60), True),
                                           ((NOW - 60, 13 * 3600), False), ((NOW - 60, 30 * 86400), False)])
def test_the_deadline_refuses_a_start_past_it(tmp_path, window, starts):
    """The model's ExecCondition, unescaped as systemd does it ($$ → $, %% → %), run by /bin/sh: past the
    deadline, without one, or with one more than 12 h ahead (a deadline written by another hand), it exits
    between 1 and 254 — systemd then skips the start without a failure, so Restart= never starts it
    again."""
    if shutil.which("sh") is None:
        pytest.skip("no sh")
    sections, _ = mob.parse_unit(mob.UNIT_MODEL.read_text(encoding="utf-8"))
    cond = sections["Service"]["ExecCondition"][0].replace("$$", "$").replace("%%", "%")
    argv = [w.replace("@DEADLINE@", str(tmp_path / "deadline")) for w in shlex.split(cond)]
    now = int(time.time())
    if isinstance(window, tuple):
        end = now + 3600 if window[1] is None else now + window[1]
        (tmp_path / "deadline").write_text(f"{now - 60} {end}\n")
    elif window == "garbage":
        (tmp_path / "deadline").write_text("soon\n")
    res = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    assert (res.returncode == 0) is starts
    assert 0 <= res.returncode <= 254


# ── imladris-tunnel-check: the tunnel's state ─────────────────────────────────────────

def test_a_tunnel_not_set_is_said_never_a_fail(tmp_path):
    lines, tw = _tunnel(tmp_path)
    assert lines == [(mob.INFO, lines[0][1])] and "pas posé" in lines[0][1]
    assert tw["calls"] == []


def test_a_tunnel_stopped_is_not_armed_never_a_fail(tmp_path):
    _set_tunnel(_home(tmp_path), window=None)
    lines, _ = _tunnel(tmp_path, unit={"ActiveState": "inactive", "SubState": "dead", "MainPID": "0"})
    assert not _fails(lines), lines
    assert [t for m, t in lines if m == mob.INFO] == ["tunnel : non armé — make imladris-tunnel-on l'arme pour 12 h"]


def test_an_armed_tunnel_says_since_when_until_when_and_listens_on_127_0_0_1_alone(tmp_path):
    _set_tunnel(_home(tmp_path))
    lines, _ = _tunnel(tmp_path)
    assert all(m == mob.OK for m, _ in lines), lines
    text = "\n".join(t for _, t in lines)
    assert "armé depuis" in text and "expire à" in text and "(dans 11 h 50)" in text
    assert "le minuteur de fin" in text and "n'écoutent qu'en 127.0.0.1:7007" in text


@pytest.fixture
def far_zone(monkeypatch):
    """The workstation in a zone 5 h 30 off UTC (a POSIX TZ: no tzdata needed): its local hour is
    never UTC's, so an hour said « UTC » but read locally shows."""
    monkeypatch.setenv("TZ", "XYZ-5:30")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_the_hours_of_the_tunnel_are_said_in_utc_whatever_the_workstation_s_zone(tmp_path, far_zone):
    """MOB3 (bench of 11/11): « armé depuis … expire à … » was the workstation's local hour, without its
    zone. Now in UTC, said: since, until, past the deadline, and the line of tunnel-on."""
    assert time.strftime("%H:%M", time.localtime(NOW)) == "13:30"     # the zone does apply here
    _set_tunnel(_home(tmp_path))
    lines, _ = _tunnel(tmp_path)
    text = "\n".join(t for _, t in lines)
    assert "armé depuis 15/01 07:50 UTC, expire à 15/01 19:50 UTC (dans 11 h 50)" in text, text
    lines, _ = _tunnel(tmp_path, now=NOW + mob.WINDOW_S)
    assert "armé au-delà de sa date limite (15/01 19:50 UTC)" in "\n".join(_fails(lines)), lines
    (tmp_path / "on").mkdir()
    home = _home(tmp_path / "on")
    _set_tunnel(home, window=None)
    code, out, _ = _main(home, "tunnel-on")
    assert code == 0 and "armé jusqu'à 15/01 20:00 UTC (12 h)" in out, out


@pytest.mark.parametrize("over,said", [
    ({"unit": {"ActiveState": "activating", "SubState": "auto-restart"}}, "en échec"),
    ({"unit": {"ActiveState": "failed", "SubState": "failed"}}, "en échec"),
    ({"unit": {"UnitFileState": "enabled"}}, "démarrerait au boot"),
    ({"unit": {"UnitFileState": "enabled-runtime"}}, "démarrerait au boot"),
    ({"unit": {"LoadState": "not-found"}}, "pas chargée"),
    ({"show_rc": 1}, "ne se lit pas"),
    ({"timer": {"ActiveState": "inactive"}}, "minuteur de fin"),
    ({"timer": {"LoadState": "not-found"}}, "minuteur de fin"),
    ({"ss_p": f"LISTEN 0 128 0.0.0.0:7007 0.0.0.0:* users:((\"ssh\",pid={SSH_PID},fd=4))\n"}, "écoutent ailleurs"),
    ({"ss_p": f"LISTEN 0 128 127.0.0.1:7007 0.0.0.0:* users:((\"ssh\",pid={SSH_PID},fd=4))\n"
              f"LISTEN 0 128 {PRIVATE}:7007 0.0.0.0:* users:((\"ssh\",pid={SSH_PID},fd=5))\n"}, "écoutent ailleurs"),
    ({"ss_p": "LISTEN 0 128 127.0.0.1:7007 0.0.0.0:* users:((\"docker-proxy\",pid=99,fd=4))\n"},
     "hors de l'unité"),
    ({"ss_p": "LISTEN 0 128 127.0.0.1:7007 0.0.0.0:*\n"}, "hors de l'unité"),
    ({"ss_p": ""}, "pas encore connecté"),
])
def test_a_tunnel_failing_enabled_or_listening_elsewhere_is_a_fail(tmp_path, over, said):
    _set_tunnel(_home(tmp_path))
    lines, _ = _tunnel(tmp_path, **over)
    assert any(said in t for t in _fails(lines)), lines


@pytest.mark.parametrize("window,said", [
    ((NOW - mob.WINDOW_S - 60, NOW - 60), "au-delà de sa date limite"),
    ((NOW, NOW + 2 * mob.WINDOW_S), "plus de 12 h"),
    ((NOW - 10 * mob.WINDOW_S, NOW + 600), "plus de 12 h"),
    (None, "sans date limite"),
])
def test_an_armed_tunnel_past_its_window_is_a_fail(tmp_path, window, said):
    _set_tunnel(_home(tmp_path), window=window)
    lines, _ = _tunnel(tmp_path)
    assert any(said in t for t in _fails(lines)), lines


def test_a_unit_hooked_to_a_target_would_start_at_boot(tmp_path):
    home = _home(tmp_path)
    _set_tunnel(home)
    wants = mob.unit_path(home).parent / "default.target.wants"
    wants.mkdir()
    (wants / mob.UNIT_NAME).symlink_to(mob.unit_path(home))
    lines, _ = _tunnel(tmp_path)
    assert any("accrochée à default.target.wants" in t for t in _fails(lines))


def test_a_unit_that_is_a_link_is_a_fail(tmp_path):
    home = _home(tmp_path)
    real = tmp_path / "elsewhere.service"
    real.write_text(_set_tunnel(home))
    mob.unit_path(home).unlink()
    mob.unit_path(home).symlink_to(real)
    lines, _ = _tunnel(tmp_path)
    assert _fails(lines) and "pas un fichier à soi" in lines[0][1]


def test_mobile_check_with_a_failing_tunnel_gives_no_green_verdict(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _set_tunnel(home)
    (home / ".ssh").mkdir()
    (home / ".ssh" / "authorized_keys").write_text("ecdsa-sha2-nistp256 AAAA phone\n")
    (home / ".ssh" / "authorized_keys").chmod(0o600)
    tw = tunnel_world(home=home, unit={"ActiveState": "activating", "SubState": "auto-restart"})
    text, code = mob.render(mob.check(7007, tunnel_run(tw, fake_run(world())), home, HOST, NOW))
    assert code == 1 and "✓ le poste ne s'ouvre" not in text and "✗ tunnel : en échec" in text
    assert IP.findall(text.replace("127.0.0.1", "")) == []
    tw = tunnel_world(home=home)
    text, code = mob.render(mob.check(7007, tunnel_run(tw, fake_run(world())), home, HOST, NOW))
    assert code == 0 and "✓ le poste ne s'ouvre" in text, text


# ── install, on, off, remove ─────────────────────────────────────────────────

def _env(home, **over):
    kh = home / ".eregion" / "h0_known_hosts"
    kh.parent.mkdir(parents=True, exist_ok=True)
    if not kh.exists():
        kh.write_text(f"{OTHER_HOST} ssh-ed25519 {OTHER_BLOB}\n{HOST} ssh-ed25519 {BLOB}\n")
    env = {"MOBILE_HOST_IP": HOST, "HOST_SSH_FINGERPRINT": FP, "MOBILE_HOST_USER": "glorfindel",
           "MOBILE_KNOWN_HOSTS": str(kh)}
    env.update(over)
    return {k: v for k, v in env.items() if v is not None}


def _main(home, *argv, env=None, tw=None, cwd=None, here=None):
    tw = tw or tunnel_world()
    tw["home"] = tw["home"] or home
    said = []
    code = mob.main(list(argv), tunnel_run(tw), home, env if env is not None else _env(home),
                    cwd=cwd or home, here=here or home, say=said.append, now=NOW)
    return code, "\n".join(said), tw


def test_install_writes_the_unit_and_its_pin_and_never_starts_it(tmp_path):
    home = _home(tmp_path)
    code, out, tw = _main(home, "tunnel-install")
    assert code == 0, out
    unit = mob.unit_path(home).read_text()
    assert all(m == mob.OK for m, _ in mob.unit_lines(unit, HOST)), mob.unit_lines(unit, HOST)
    assert (home / mob.TUNNEL_KNOWN_HOSTS).read_text() == f"{HOST} ssh-ed25519 {BLOB}\n"
    assert oct((home / mob.TUNNEL_KNOWN_HOSTS).stat().st_mode & 0o777) == "0o600"
    assert tw["calls"] == [["systemctl", "--user", "daemon-reload"]]
    assert not (home / mob.TUNNEL_DEADLINE).exists() and "non armé" in out


def test_install_with_a_key_names_it_alone(tmp_path):
    home = _home(tmp_path)
    (home / ".ssh").mkdir()
    (home / ".ssh" / "h0").write_text("k")
    code, out, _ = _main(home, "tunnel-install", env=_env(home, MOBILE_HOST_KEY="~/.ssh/h0"))
    assert code == 0, out
    assert f"-i {home}/.ssh/h0 -o IdentitiesOnly=yes -L" in mob.unit_path(home).read_text()


def test_install_dry_run_shows_the_unit_and_writes_nothing(tmp_path):
    home = _home(tmp_path)
    code, out, tw = _main(home, "tunnel-install", "--dry-run")
    assert code == 0 and "DRY_RUN=1 : rien n'est écrit" in out and "RuntimeMaxSec=12h" in out
    assert "-L 127.0.0.1:7007:127.0.0.1:7007" in out and tw["calls"] == []
    assert not mob.unit_path(home).exists() and not (home / mob.TUNNEL_KNOWN_HOSTS).exists()


@pytest.mark.parametrize("over,said", [
    ({"HOST_SSH_FINGERPRINT": None}, "HOST_SSH_FINGERPRINT requis"),
    ({"HOST_SSH_FINGERPRINT": "SHA256:short"}, "HOST_SSH_FINGERPRINT requis"),
    ({"MOBILE_HOST_IP": None}, "aucune adresse d'Imladris"),
    ({"MOBILE_HOST_IP": "127.0.0.1"}, "pas une adresse IPv4 joignable"),
    ({"MOBILE_HOST_USER": "root; rm"}, "HOST_USER"),
    ({"MOBILE_HOST_KEY": "/home/op/my key"}, "un chemin"),
    ({"HOST_SSH_FINGERPRINT": mob.fingerprint_of(OTHER_BLOB)}, "n'est pas dans HOST_KNOWN_HOSTS"),
])
def test_install_refuses_what_it_cannot_pin_or_write(tmp_path, over, said):
    home = _home(tmp_path)
    code, out, tw = _main(home, "tunnel-install", env=_env(home, **over))
    assert code == 1 and said in out, out
    assert not mob.unit_path(home).exists() and tw["calls"] == []


def test_on_arms_the_timer_of_expiry_before_the_unit_for_12_hours(tmp_path):
    home = _home(tmp_path)
    _set_tunnel(home, window=None)
    code, out, tw = _main(home, "tunnel-on")
    assert code == 0, out
    assert (home / mob.TUNNEL_DEADLINE).read_text() == f"{NOW} {NOW + 12 * 3600}\n"
    runs = [c for c in tw["calls"] if c[0] == "systemd-run" or c[2] == "start"]
    assert runs == [
        ["systemd-run", "--user", f"--unit={mob.EXPIRY_UNIT}", "--on-active=43200s", "--timer-property=AccuracySec=1s",
         "--description=Eregion: the end of the console's tunnel (12 h)", "systemctl", "--user", "stop", mob.UNIT_NAME],
        ["systemctl", "--user", "start", mob.UNIT_NAME],
    ]
    assert not [c for c in tw["calls"] if "enable" in c]
    # The window imladris-tunnel-check then reads: 12 h from the gesture.
    lines = mob.service_lines(tunnel_run(tunnel_world()), 7007, home / mob.TUNNEL_DEADLINE, NOW + 60)
    assert any("(dans 11 h 59)" in t for m, t in lines if m == mob.OK), lines


def test_on_without_its_timer_arms_nothing(tmp_path):
    home = _home(tmp_path)
    _set_tunnel(home, window=None)
    code, out, tw = _main(home, "tunnel-on", tw=tunnel_world(fail={"systemd-run"}))
    assert code == 1 and "rien n'est armé" in out
    assert ["systemctl", "--user", "start", mob.UNIT_NAME] not in tw["calls"]
    assert not (home / mob.TUNNEL_DEADLINE).exists()


@pytest.mark.parametrize("change,env_over,said", [
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=12h\n[Install]\nWantedBy=default.target\n"}, {}, "[Install]"),
    ({"RuntimeMaxSec=12h\n": ""}, {}, "sans limite"),
    ({"-L 127.0.0.1:7007": "-L 0.0.0.0:7007"}, {}, "toutes les interfaces"),
    ({}, {"MOBILE_HOST_IP": OTHER_HOST}, "n'est plus à l'adresse"),
])
def test_on_refuses_a_unit_mobile_check_refuses(tmp_path, change, env_over, said):
    home = _home(tmp_path)
    _set_tunnel(home, window=None, **change)
    code, out, tw = _main(home, "tunnel-on", env=_env(home, **env_over))
    assert code == 1 and said in out and "Rien n'est armé" in out, out
    assert [c[:3] for c in tw["calls"]] in ([], [["systemctl", "--user", "show"]])
    assert not (home / mob.TUNNEL_DEADLINE).exists()


def test_on_without_a_unit_arms_nothing(tmp_path):
    code, out, tw = _main(_home(tmp_path), "tunnel-on")
    assert code == 1 and "make imladris-tunnel-install d'abord" in out and tw["calls"] == []


def test_off_stops_the_timer_and_the_unit_and_drops_the_deadline(tmp_path):
    home = _home(tmp_path)
    _set_tunnel(home)
    code, out, tw = _main(home, "tunnel-off")
    assert code == 0 and "désarmé" in out
    assert ["systemctl", "--user", "stop", f"{mob.EXPIRY_UNIT}.timer"] in tw["calls"]
    assert ["systemctl", "--user", "stop", mob.UNIT_NAME] in tw["calls"]
    assert not (home / mob.TUNNEL_DEADLINE).exists()


def test_remove_stops_it_then_removes_unit_pin_and_deadline(tmp_path):
    home = _home(tmp_path)
    _set_tunnel(home)
    code, out, tw = _main(home, "tunnel-remove", "--dry-run")
    assert code == 0 and "rien n'est fait" in out and tw["calls"] == [] and mob.unit_path(home).exists()
    code, out, tw = _main(home, "tunnel-remove")
    assert code == 0, out
    assert not mob.unit_path(home).exists() and not (home / mob.TUNNEL_KNOWN_HOSTS).exists()
    assert not (home / mob.TUNNEL_DEADLINE).exists()
    assert ["systemctl", "--user", "stop", mob.UNIT_NAME] in tw["calls"]
    assert tw["calls"][-1] == ["systemctl", "--user", "daemon-reload"]


# ── never from a code session ────────────────────────────────────────────────

@pytest.mark.parametrize("cmd", ["tunnel-install", "tunnel-on", "tunnel-off", "tunnel-remove"])
@pytest.mark.parametrize("where", ["env", "worktree"])
def test_a_code_session_never_sets_nor_arms_the_tunnel(tmp_path, cmd, where):
    home = _home(tmp_path)
    _set_tunnel(home, window=None)
    lot = tmp_path / "eregion" / ".claude" / "worktrees" / "lot-x"
    lot.mkdir(parents=True)
    env = {**_env(home), "EREGION_AGENT_SESSION": "1"} if where == "env" else _env(home)
    for argv in ([cmd], [cmd, "--guard-only"]):
        code, out, tw = _main(home, *argv, env=env, cwd=lot if where == "worktree" else home)
        assert code == 1 and f"make imladris-{cmd} refusé" in out and "n'arme" in out, out
        assert tw["calls"] == []
    assert mob.unit_path(home).exists() and not (home / mob.TUNNEL_DEADLINE).exists()


@pytest.mark.parametrize("where", ["env", "worktree"])
def test_the_console_s_token_never_reaches_a_code_session(tmp_path, where, capsys):
    lot = tmp_path / ".claude" / "worktrees" / "agent-x"
    lot.mkdir(parents=True)
    env = {"EREGION_AGENT_SESSION": "1"} if where == "env" else {}
    assert mob.main(["guard", "console-url"], env=env, cwd=lot if where == "worktree" else tmp_path,
                    here=tmp_path) == 1
    assert "make console-url refusé" in capsys.readouterr().err
    assert mob.main(["guard", "console-url"], env={}, cwd=tmp_path, here=tmp_path) == 0


# ── through make ─────────────────────────────────────────────────────────────

OPERATOR_FILES = ("Makefile", "scripts/mobile.py", "scripts/bench_shared.py",
                  "infra/poste/eregion-console-tunnel.service", "infra/glorfindel-host/known_host.sh")
SPY = ("systemctl", "systemd-run", "terraform", "ssh-keyscan", "ssh", "loginctl", "ss")


@pytest.fixture
def spies(tmp_path):
    """Every command the targets could reach, first on the PATH: each call written down; `systemctl
    --user is-active` says « inactive »."""
    b = tmp_path / "spy"
    b.mkdir()
    log = tmp_path / "spy.log"
    for name in SPY:
        (b / name).write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n'
                              '[ "$1 $2" = "--user is-active" ] && { [ -n "$SPY_ACTIVE" ] && exit 0; exit 3; }\n'
                              'exit 0\n')
        (b / name).chmod(0o755)
    return b, log


def _operator(tmp_path, under=None) -> Path:
    root = (under or tmp_path) / "checkout"
    for rel in OPERATOR_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, root / rel)
    return root


def _make_at(root, spies, home, *args, **env_over):
    b, _ = spies
    env = {k: v for k, v in os.environ.items() if k not in ("EREGION_AGENT_SESSION", "MAKEFLAGS", "HOST_IP",
                                                             "HOST_SSH_FINGERPRINT", "EREGION_CONSOLE_PORT",
                                                             "EREGION_CONSOLE_TOKEN", "GLORFINDEL_WARROOM_TOKEN")}
    env.update({"PATH": f"{b}{os.pathsep}{os.environ['PATH']}", "HOME": str(home), **env_over})
    return subprocess.run(["make", "-s", "--no-print-directory", "-C", str(root), *args, f"PYTHON={sys.executable}"],
                          capture_output=True, text=True, env=env, timeout=60, cwd=root)


@needs_make
@pytest.mark.parametrize("target", ["imladris-tunnel-install", "imladris-tunnel-on", "imladris-tunnel-off",
                                    "imladris-tunnel-remove", "console-url", "imladris-url",
                                    "imladris-tunnel",
                                    # IML1b: the former names, silent aliases — the same guard, first
                                    "mobile-tunnel-install", "mobile-tunnel-on", "mobile-tunnel-off",
                                    "mobile-tunnel-remove", "glorfindel-host-url", "glorfindel-host-tunnel"])
@pytest.mark.parametrize("where", ["env", "worktree"])
def test_make_refuses_in_an_agent_session_before_anything_runs(tmp_path, spies, target, where):
    """The guard runs alone: no terraform output, no ssh-keyscan, no systemctl — and no token read.
    A former name (IML1b) refuses as its new one, and names it."""
    home = _home(tmp_path)
    _set_tunnel(home, window=None)
    (tmp_path / "host.env").write_text("EREGION_CONSOLE_TOKEN=fake-tok-Q7\n")
    if where == "env":
        root, extra = _operator(tmp_path), {"EREGION_AGENT_SESSION": "1"}
    else:
        root, extra = _operator(tmp_path, tmp_path / "eregion" / ".claude" / "worktrees" / "lot-x"), {}
    res = _make_at(root, spies, home, target, f"HOST_ENV={tmp_path / 'host.env'}",
                   f"HOST_SSH_FINGERPRINT={FP}", **extra)
    assert res.returncode != 0
    new = target.replace("mobile-", "imladris-").replace("glorfindel-host-", "imladris-")
    assert f"make {new} refusé" in res.stdout + res.stderr, res.stdout + res.stderr
    assert "fake-tok-Q7" not in res.stdout + res.stderr
    log = spies[1]
    assert not log.exists() or log.read_text() == ""
    assert not (home / mob.TUNNEL_DEADLINE).exists()


@needs_make
def test_make_install_dry_run_shows_the_unit_and_writes_nothing(tmp_path, spies):
    home = _home(tmp_path)
    res = _make_at(_operator(tmp_path), spies, home, "imladris-tunnel-install", "DRY_RUN=1", f"HOST_IP={HOST}",
                   f"HOST_SSH_FINGERPRINT={FP}")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "DRY_RUN=1 : rien n'est écrit" in res.stdout and f"glorfindel@{HOST}" in res.stdout
    assert not mob.unit_path(home).exists()
    assert "ssh-keyscan" not in (spies[1].read_text() if spies[1].exists() else "")


@needs_make
def test_make_install_pins_the_key_known_host_sh_checked(tmp_path, spies):
    """known_host.sh, « required », then the unit: the key of the fingerprint from HOST_KNOWN_HOSTS."""
    if shutil.which("ssh-keygen") is None:
        pytest.skip("ssh-keygen not installed")
    home = _home(tmp_path)
    kh = home / ".eregion" / "h0_known_hosts"
    kh.parent.mkdir(parents=True)
    kh.write_text(f"{HOST} ssh-ed25519 {BLOB}\n")
    res = _make_at(_operator(tmp_path), spies, home, "imladris-tunnel-install", f"HOST_IP={HOST}",
                   f"HOST_SSH_FINGERPRINT={FP}")
    assert res.returncode == 0, res.stdout + res.stderr
    assert (home / mob.TUNNEL_KNOWN_HOSTS).read_text() == f"{HOST} ssh-ed25519 {BLOB}\n"
    calls = spies[1].read_text().splitlines()
    assert calls == ["systemctl --user daemon-reload"], calls
    res = _make_at(_operator(tmp_path), spies, home, "imladris-tunnel-install", f"HOST_IP={HOST}")
    assert res.returncode != 0 and "HOST_SSH_FINGERPRINT requis" in res.stdout + res.stderr


@needs_make
def test_make_console_url_names_imladris_url_when_the_tunnel_holds_the_port(tmp_path, spies):
    """IML1b: console-url is the local console's only. The tunnel holding 127.0.0.1:7007, the console
    there is Imladris's: no URL, no token — a line names make imladris-url, and the exit says it."""
    home = _home(tmp_path)
    (home / ".eregion" / "console").mkdir(parents=True)
    (home / ".eregion" / "console" / "token").write_text("local-tok-K2\n")
    env_file = tmp_path / "host.env"
    env_file.write_text("EREGION_CONSOLE_TOKEN=fake-tok-Q7\n")
    root = _operator(tmp_path)
    res = _make_at(root, spies, home, "console-url", f"HOST_ENV={env_file}", "CONSOLE_WAIT=0")
    assert res.returncode == 0 and "token=local-tok-K2" in res.stdout   # no tunnel: the local console's
    assert "imladris" not in res.stdout + res.stderr
    _set_tunnel(home)
    res = _make_at(root, spies, home, "console-url", f"HOST_ENV={env_file}", "CONSOLE_WAIT=0", SPY_ACTIVE="1")
    assert res.returncode != 0
    assert "fake-tok-Q7" not in res.stdout + res.stderr and "local-tok-K2" not in res.stdout + res.stderr
    assert "son URL → make imladris-url" in res.stderr, res.stderr


@needs_make
@pytest.mark.parametrize("name", ["imladris-url", "glorfindel-host-url"])
def test_make_imladris_url_gives_the_url_and_says_when_the_tunnel_is_not_armed(tmp_path, spies, name):
    """IML1b: always the URL of Imladris's console, alone on the output; the tunnel not armed, a line
    more on the error output says how to arm it (and to set it first, when it is not)."""
    home = _home(tmp_path)
    env_file = tmp_path / "host.env"
    env_file.write_text("EREGION_CONSOLE_TOKEN=fake-tok-Q7\n")
    root = _operator(tmp_path)
    url = "http://localhost:7007/?token=fake-tok-Q7\n"
    res = _make_at(root, spies, home, name, f"HOST_ENV={env_file}")                    # not set
    assert (res.returncode, res.stdout) == (0, url), res.stderr
    assert "make imladris-tunnel-install" in res.stderr and "make imladris-tunnel-on" in res.stderr
    _set_tunnel(home, window=None)
    res = _make_at(root, spies, home, name, f"HOST_ENV={env_file}")                    # set, not armed
    assert (res.returncode, res.stdout) == (0, url), res.stderr
    assert "n'est pas armé : make imladris-tunnel-on" in res.stderr and "install" not in res.stderr
    _set_tunnel(home)
    res = _make_at(root, spies, home, name, f"HOST_ENV={env_file}", SPY_ACTIVE="1")    # armed
    assert (res.returncode, res.stdout, res.stderr) == (0, url, "")


@needs_make
def test_make_mobile_check_sees_an_unbounded_unit(tmp_path, fake_bin):
    """`make imladris-tunnel-check`, the tunnel set with no limit of time: a ✗, never the green verdict."""
    _, answer = fake_bin
    home = fake_bin[0].parent
    answer(tailscale_ip_4=PRIVATE + "\n", tailscale_ip_6="", tailscale_debug_prefs='{"RunSSH": false}',
           sshd_T=GOOD_SSHD, ss_Hltn=GOOD_SS)
    (home / ".ssh").mkdir()
    (home / ".ssh" / "authorized_keys").write_text("ecdsa-sha2-nistp256 AAAA phone\n")
    (home / ".ssh" / "authorized_keys").chmod(0o600)
    for name, body in (("systemctl", "echo LoadState=loaded; echo ActiveState=inactive; echo SubState=dead; "
                                     "echo UnitFileState=static; echo RuntimeMaxUSec=12h; "
                                     "echo FragmentPath=$HOME/.config/systemd/user/eregion-console-tunnel.service"),):
        (fake_bin[0] / name).write_text(f"#!/bin/sh\n{body}\n")
        (fake_bin[0] / name).chmod(0o755)
    _set_tunnel(home, window=None)
    res = _make(fake_bin, "imladris-tunnel-check")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ℹ tunnel : non armé" in res.stdout
    _set_tunnel(home, window=None, **{"RuntimeMaxSec=12h\n": ""})
    res = _make(fake_bin, "imladris-tunnel-check")
    assert res.returncode != 0 and "✗ tunnel : l'unité est sans limite de durée" in res.stdout
    assert "✓ le poste ne s'ouvre" not in res.stdout


# ── MOB2, review round 1: what systemd loaded, the unit bounded alone, the owner, console-url ─────────

@pytest.mark.parametrize("over,said", [
    ({"DropInPaths": "/home/op/.config/systemd/user/eregion-console-tunnel.service.d/50-x.conf"}, "un drop-in"),
    ({"FragmentPath": "/etc/systemd/user/eregion-console-tunnel.service"}, "un autre fichier"),
    ({"RuntimeMaxUSec": "infinity"}, "RuntimeMaxUSec=infinity"),
    ({"RuntimeMaxUSec": "1d"}, "RuntimeMaxUSec=1d"),
    ({"RuntimeMaxUSec": "13h"}, "RuntimeMaxUSec=13h"),
    ({"WantedBy": "default.target"}, "WantedBy"),
    ({"RequiredBy": "other.service"}, "RequiredBy"),
    ({"TriggeredBy": "eregion-console-tunnel.path"}, "TriggeredBy"),
])
@pytest.mark.parametrize("armed", [True, False])
def test_what_systemd_loaded_is_read_beside_the_file(tmp_path, over, said, armed):
    """A drop-in, another file, a limit read otherwise, a unit that pulls it in: the file says the model,
    systemd runs something else — a ✗, armed or not."""
    _set_tunnel(_home(tmp_path), window=None if not armed else (NOW - 600, NOW - 600 + mob.WINDOW_S))
    unit = dict(over) if armed else {**over, "ActiveState": "inactive", "SubState": "dead", "MainPID": "0"}
    lines, _ = _tunnel(tmp_path, unit=unit)
    assert any("ce que systemd a chargé" in t and said in t for t in _fails(lines)), lines


def test_what_systemd_loaded_as_the_model_is_said(tmp_path):
    _set_tunnel(_home(tmp_path))
    lines, _ = _tunnel(tmp_path)
    assert (mob.OK, "tunnel : systemd a chargé le fichier seul — aucun drop-in, 12 h au plus, rien ne la tire") in lines


def test_on_refuses_a_unit_systemd_holds_otherwise(tmp_path):
    home = _home(tmp_path)
    _set_tunnel(home, window=None)
    tw = tunnel_world(unit={"DropInPaths": "/run/user/1000/systemd/transient/eregion-console-tunnel.service.d/x.conf"})
    code, out, tw = _main(home, "tunnel-on", tw=tw)
    assert code == 1 and "un drop-in" in out and "Rien n'est armé" in out, out
    assert [c for c in tw["calls"] if c[0] == "systemd-run" or "start" in c] == []
    assert not (home / mob.TUNNEL_DEADLINE).exists()


@pytest.mark.parametrize("change,said", [
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=12h\nRuntimeMaxSec=infinity\n"}, "RuntimeMaxSec= deux fois"),
    ({"RuntimeMaxSec=12h\n": "RuntimeMaxSec=12h\n\n[Service]\nRuntimeMaxSec=infinity\n"}, "[Service] deux fois"),
    ({"Restart=on-failure\n": "ExecStart=\nRestart=on-failure\n"}, "ExecStart= deux fois"),
])
def test_a_key_or_a_section_said_twice_is_never_the_model(tmp_path, change, said):
    """systemd adds to a key said twice, or resets it, and merges a section: the first value read is not
    what it would run."""
    text = _set_tunnel(_home(tmp_path), **change)
    fails = _fails(mob.unit_lines(text, HOST))
    assert any("autre chose que le modèle" in t and said in t for t in fails), fails


@pytest.mark.parametrize("change", [
    # ssh alone, no timeout: a run would last until RuntimeMaxSec
    {"ExecStart=/bin/sh -c": "ExecStart=/bin/sh -x -c"},
    {"exec /usr/bin/timeout \"$$left\" \"$$@\"": "exec \"$$@\""},
])
def test_ssh_not_bounded_by_the_deadline_is_a_fail(tmp_path, change):
    text = _set_tunnel(_home(tmp_path), **change)
    fails = _fails(mob.unit_lines(text, HOST))
    assert any("n'est pas borné à la date limite" in t for t in fails), fails


def test_the_timeout_reads_the_same_deadline_as_the_condition(tmp_path):
    home = _home(tmp_path)
    text = _set_tunnel(home)
    other = text.replace(f"tunnel {home / mob.TUNNEL_DEADLINE}", f"tunnel {home / 'elsewhere'}")
    assert other != text
    assert any("n'est pas borné" in t for t in _fails(mob.unit_lines(other, HOST)))


def _wrapper(tmp_path, command):
    """The model's ExecStart up to ssh, unescaped as systemd does it, the deadline in tmp_path, then
    `command` in ssh's place."""
    sections, _ = mob.parse_unit(mob.UNIT_MODEL.read_text(encoding="utf-8"))
    argv = shlex.split(sections["Service"]["ExecStart"][0].replace("$$", "$").replace("%%", "%"))
    assert argv[4] == "@DEADLINE@" and argv[5] == "/usr/bin/ssh"
    return argv[:4] + [str(tmp_path / "deadline")] + command


@pytest.mark.parametrize("ahead,code,ran", [(2, 124, True), (-10, 0, False), (None, 0, False)])
def test_ssh_runs_under_timeout_until_the_deadline(tmp_path, ahead, code, ran):
    """The model's own wrapper, run by /bin/sh with a fake ssh that would last 8 s: ended by timeout at
    the deadline (124, which Restart= follows into ExecCondition's refusal); past the deadline or without
    one, never started, a clean exit."""
    if shutil.which("timeout") is None or not Path("/usr/bin/timeout").exists():
        pytest.skip("no /usr/bin/timeout")
    marker = tmp_path / "ran"
    now = int(time.time())
    if ahead is not None:
        (tmp_path / "deadline").write_text(f"{now - 60} {now + ahead}\n")
    start = time.monotonic()
    res = subprocess.run(_wrapper(tmp_path, ["/bin/sh", "-c", f'touch "{marker}"; exec sleep 8']),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == code, res.stderr
    assert marker.exists() is ran
    assert time.monotonic() - start < 6


def test_a_unit_file_of_another_user_is_not_the_operator_s(tmp_path, monkeypatch):
    home = _home(tmp_path)
    _set_tunnel(home)
    real = os.getuid()
    monkeypatch.setattr(mob.os, "getuid", lambda: real + 1)
    lines, _ = _tunnel(tmp_path)
    assert _fails(lines) and "pas un fichier à soi" in lines[0][1]
    with pytest.raises(OSError):
        mob._read_private(home / mob.TUNNEL_KNOWN_HOSTS)


@needs_make
def test_make_console_url_keeps_the_local_console_while_the_tunnel_is_stopped(tmp_path, spies):
    """The unit set, the tunnel stopped (systemctl is-active: inactive): the console behind 127.0.0.1:7007
    is the local one — its token, never Imladris's; a line names the way to Imladris's."""
    home = _home(tmp_path)
    (home / ".eregion" / "console").mkdir(parents=True)
    (home / ".eregion" / "console" / "token").write_text("local-tok-K2\n")
    env_file = tmp_path / "host.env"
    env_file.write_text("EREGION_CONSOLE_TOKEN=fake-tok-Q7\n")
    _set_tunnel(home, window=None)
    res = _make_at(_operator(tmp_path), spies, home, "console-url", f"HOST_ENV={env_file}", "CONSOLE_WAIT=0")
    assert res.returncode == 0, res.stderr
    assert "Console   →  http://localhost:7007/?token=local-tok-K2" in res.stdout
    assert "fake-tok-Q7" not in res.stdout + res.stderr
    assert "make imladris-url" in res.stderr and "make imladris-tunnel-on" in res.stderr


# ── MOB2, review round 2: the unit's processes, not MainPID alone; the loaded view, complete ──────────

def _listening(lines):
    """The one line on what the unit's processes listen on."""
    return [(m, t) for m, t in lines
            if t.startswith(("tunnel : ses processus", "tunnel : il ne tient pas", "tunnel : ce qu'écoutent"))]


def test_the_listener_of_ssh_under_timeout_is_the_unit_s(tmp_path):
    """MainPID is timeout's; ssh, its child, holds 127.0.0.1:7007: read through the unit's cgroup, an armed,
    healthy tunnel is a ✓ — never « it does not hold the port »."""
    _set_tunnel(_home(tmp_path))
    lines, tw = _tunnel(tmp_path)
    assert (mob.OK, "tunnel : ses processus n'écoutent qu'en 127.0.0.1:7007") in lines, lines
    assert ["cat", f"/sys/fs/cgroup{CG}/cgroup.procs"] in tw["calls"]


def test_without_the_cgroup_the_children_of_main_pid_are_read(tmp_path):
    _set_tunnel(_home(tmp_path))
    files = {f"/proc/{PID}/task/{PID}/children": f"{SSH_PID} "}
    lines, _ = _tunnel(tmp_path, files=files)
    assert (mob.OK, "tunnel : ses processus n'écoutent qu'en 127.0.0.1:7007") in lines, lines
    lines, _ = _tunnel(tmp_path, files=files, unit={"ControlGroup": ""})
    assert (mob.OK, "tunnel : ses processus n'écoutent qu'en 127.0.0.1:7007") in lines, lines


@pytest.mark.parametrize("over", [{"files": {}}, {"files": {}, "unit": {"MainPID": "0", "ControlGroup": ""}},
                                  {"unit": {"ControlGroup": "/../../etc", "MainPID": "0"}}])
def test_processes_that_cannot_be_read_are_a_warning_never_a_verdict(tmp_path, over):
    """Neither the cgroup nor /proc reads: a clear ⚠, never a ✓ on the listener nor a false ✗."""
    _set_tunnel(_home(tmp_path))
    lines, _ = _tunnel(tmp_path, **over)
    said = _listening(lines)
    assert said == [(mob.WARN, said[0][1])] and "n'est pas vérifiée" in said[0][1], lines


def test_ss_unread_is_a_warning_never_a_verdict(tmp_path):
    _set_tunnel(_home(tmp_path))
    tw = tunnel_world(home=_home(tmp_path))
    base = tunnel_run(tw)

    def run(argv, timeout=30):
        return (1, "", "ss: permission denied") if argv[:2] == ["ss", "-Hltnp"] else base(argv, timeout)
    lines = mob.tunnel_lines(run, _home(tmp_path), HOST, 7007, NOW)
    said = _listening(lines)
    assert said == [(mob.WARN, said[0][1])] and "ss -Hltnp" in said[0][1], lines


def test_a_listener_held_outside_the_unit_is_a_fail(tmp_path):
    """127.0.0.1:7007 held by a process outside the unit's cgroup (the local console, a tunnel by hand),
    the unit's own ssh not listening: a ✗ that says so."""
    _set_tunnel(_home(tmp_path))
    # `ss -Hltnp` lists listeners only: the unit's ssh, not yet listening, is absent from it.
    ss_p = "LISTEN 0 128 127.0.0.1:7007 0.0.0.0:* users:((\"ssh\",pid=999,fd=4))\n"
    lines, _ = _tunnel(tmp_path, ss_p=ss_p)
    assert any("hors de l'unité" in t for t in _fails(lines)), lines
    assert not any(m == mob.OK and "n'écoutent" in t for m, t in lines)


@pytest.mark.parametrize("key,value,said", [
    ("NeedDaemonReload", "yes", "NeedDaemonReload=yes"),
    ("BoundBy", "other.service", "BoundBy"),
    ("UpheldBy", "other.service", "UpheldBy"),
    ("OnFailureOf", "other.service", "OnFailureOf"),
    ("OnSuccessOf", "other.service", "OnSuccessOf"),
])
def test_a_file_changed_since_loaded_or_another_reverse_dependency_is_a_fail(tmp_path, key, value, said):
    _set_tunnel(_home(tmp_path))
    lines, _ = _tunnel(tmp_path, unit={key: value})
    assert any("ce que systemd a chargé" in t and said in t for t in _fails(lines)), lines
