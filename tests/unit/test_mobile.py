"""The workstation reached from the phone (MOB1, #686): `make mobile-check`.

`make mobile-check` reads, and only reads, what holds the two barriers — the private network, then the
SSH server by key alone. It runs here on fakes of `tailscale`, `ss`, `sshd -T` and `sudo`, first on
PATH: it must see a listener on every interface, a password admitted, a key handed by a command or a
certificate authority, a forwarding wider than the phone's local tunnel to 127.0.0.1:7007, a gateway
port, a console port listening elsewhere than on 127.0.0.1, Tailscale SSH open. The console reaches the
phone through the phone's own SSH tunnel (decision of Jonathan, 10/11): nothing changes on H0, nothing
binds the private address. The model of the SSH server (infra/poste/sshd_config.d/00-eregion.conf)
passes the checks it was written for. No address is printed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
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


# ── mobile-check, on fakes ───────────────────────────────────────────────────

def test_a_workstation_in_order_passes(tmp_path):
    code, text, lines = _check(tmp_path)
    assert code == 0, text
    assert all(m == mob.OK for m, _ in lines), text
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
    return subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, f"PYTHON={sys.executable}",
                           *args], capture_output=True, text=True, env=env, timeout=60)


@needs_make
def test_make_mobile_check_sees_every_interface_a_password_and_a_wide_tunnel(fake_bin):
    _, answer = fake_bin
    answer(tailscale_ip_4=PRIVATE + "\n", tailscale_ip_6="", tailscale_debug_prefs='{"RunSSH": false}',
           sshd_T=_sshd("passwordauthentication", "yes").replace("allowtcpforwarding local", "allowtcpforwarding yes")
           .replace("permitopen 127.0.0.1:7007", "permitopen any"),
           ss_Hltn="LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\nLISTEN 0 128 0.0.0.0:7007 0.0.0.0:*\n")
    res = _make(fake_bin, "mobile-check")
    assert res.returncode != 0
    for said in ("✗ SSH : le serveur écoute sur toutes les interfaces", "✗ SSH : passwordauthentication yes, no attendu",
                 "✗ SSH : allowtcpforwarding yes — local attendu", "✗ SSH : permitopen any",
                 "✗ console : le port 7007 est exposé sur toutes les interfaces"):
        assert said in res.stdout, res.stdout
    answer(sshd_T=GOOD_SSHD, ss_Hltn=GOOD_SS + "LISTEN 0 128 127.0.0.1:7007 0.0.0.0:*\n")
    (fake_bin[0].parent / ".ssh").mkdir()
    (fake_bin[0].parent / ".ssh" / "authorized_keys").write_text("ecdsa-sha2-nistp256 AAAA phone\n")
    res = _make(fake_bin, "mobile-check")
    assert res.returncode == 0, res.stdout + res.stderr
    assert IP.findall(res.stdout.replace("127.0.0.1", "")) == []


def test_nothing_binds_the_console_on_the_private_address_any_more():
    """The tunnel on the private address is gone with the decision of 10/11: no target binds it."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "glorfindel-host-tunnel-private" not in makefile and "private-ip" not in makefile
