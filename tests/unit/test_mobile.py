"""The workstation reached from the phone (MOB1, #686): `make mobile-check` and the console's tunnel.

`make mobile-check` reads, and only reads, what holds the two barriers — the private network, then the
SSH server by key alone. It runs here on fakes of `tailscale`, `ss`, `sshd -T` and `sudo`, first on
PATH: it must see a listener on every interface, a password admitted, a console exposed elsewhere,
Tailscale SSH open. `make glorfindel-host-tunnel-private` binds the console's port to the private
address alone, or opens nothing: never 0.0.0.0, never the loopback WSL shares with Windows. The
model of the SSH server (infra/poste/sshd_config.d/00-eregion.conf) passes the checks it was written
for. No address is printed by the check.
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


# ── the private address ──────────────────────────────────────────────────────

@pytest.mark.parametrize("out,ok", [
    (PRIVATE + "\n", True), ("100.64.0.1", True), ("100.127.255.254", True),
    ("", False), ("0.0.0.0", False), ("127.0.0.1", False), ("192.168.1.10", False), ("100.128.0.1", False),
    (f"{PRIVATE}\n100.64.0.9\n", False), ("::1", False), ("garbage", False),
])
def test_the_private_address_is_one_tailnet_ipv4_or_none(out, ok):
    ip, why = mob.tailnet_ipv4(out)
    assert bool(ip) is ok and (ip == out.split()[0] if ok else why)


def test_private_ip_prints_the_address_or_refuses(capsys):
    assert mob.main(["private-ip"], fake_run(world())) == 0
    assert capsys.readouterr().out.strip() == PRIVATE
    assert mob.main(["private-ip"], fake_run(world(ip4_rc=1, ip4=""))) == 1
    err = capsys.readouterr()
    assert err.out == "" and "pas d'adresse privée" in err.err and "jamais sur toutes les interfaces" in err.err


# ── mobile-check, on fakes ───────────────────────────────────────────────────

def test_a_workstation_in_order_passes(tmp_path):
    code, text, lines = _check(tmp_path)
    assert code == 0, text
    assert all(m == mob.OK for m, _ in lines), text
    assert "1 clé(s) admise(s) (1 ecdsa-sha2-nistp256)" in text
    assert IP.findall(text) == [] and "AAAAE2Vj" not in text


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
    assert IP.findall(text) == []


@pytest.mark.parametrize("key,value", [
    ("passwordauthentication", "yes"), ("kbdinteractiveauthentication", "yes"), ("permitemptypasswords", "yes"),
    ("hostbasedauthentication", "yes"), ("pubkeyauthentication", "no"), ("gssapiauthentication", "yes"),
])
def test_a_password_or_another_method_admitted_is_seen(tmp_path, key, value):
    code, text, lines = _check(tmp_path, sshd=GOOD_SSHD.replace(f"{key} {'yes' if value == 'no' else 'no'}",
                                                                f"{key} {value}"))
    assert code == 1
    assert _marks(lines, f"{key} {value}") == [mob.FAIL], text


@pytest.mark.parametrize("methods,ok", [("any", True), ("publickey", True), ("publickey,publickey", True),
                                        ("publickey,password", False), ("password", False),
                                        ("publickey keyboard-interactive", False)])
def test_authentication_methods_the_key_alone(tmp_path, methods, ok):
    code, text, lines = _check(tmp_path, sshd=GOOD_SSHD.replace("authenticationmethods publickey",
                                                                f"authenticationmethods {methods}"))
    assert _marks(lines, "authenticationmethods") == [mob.OK if ok else mob.FAIL]


def test_an_absent_keyword_is_not_a_no(tmp_path):
    code, text, lines = _check(tmp_path, sshd=GOOD_SSHD.replace("passwordauthentication no\n", ""))
    assert code == 1 and _marks(lines, "passwordauthentication") == [mob.FAIL]


@pytest.mark.parametrize("extra,mark", [
    ("LISTEN 0 128 0.0.0.0:7007 0.0.0.0:*\n", mob.FAIL),
    ("LISTEN 0 128 [::]:7007 [::]:*\n", mob.FAIL),
    ("LISTEN 0 128 192.168.1.10:7007 0.0.0.0:*\n", mob.FAIL),
    ("LISTEN 0 128 127.0.0.1:7007 0.0.0.0:*\n", mob.WARN),
    (f"LISTEN 0 128 {PRIVATE}:7007 0.0.0.0:*\n", mob.OK),
    (f"LISTEN 0 128 [{V6}]:7007 [::]:*\n", mob.OK),
])
def test_the_console_s_port_is_exposed_nowhere_but_the_private_address(tmp_path, extra, mark):
    code, text, lines = _check(tmp_path, ss=GOOD_SS + extra)
    assert _marks(lines, "console : le port 7007") == [mark], text
    assert code == (1 if mark == mob.FAIL else 0)


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
                                       ('from="100.64.0.0/10" sk-ecdsa-sha2-nistp256@openssh.com AAAA x\n', mob.OK)])
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
    assert len(listen) == 1 and mob.kind(listen[0], set()) == "other"
    assert mob.tailnet_ipv4(listen[0])[0] == listen[0]
    for key in ("allowtcpforwarding", "allowagentforwarding", "x11forwarding", "permittunnel"):
        assert conf[key] == ["no"]


# ── through make, on fake commands ───────────────────────────────────────────

@pytest.fixture
def fake_bin(tmp_path):
    """`tailscale`, `ss`, `sshd`, `sudo` (which runs what follows -n) and `ssh` (which logs), first on
    PATH; their answers read from files the test writes."""
    b, log = tmp_path / "bin", tmp_path / "ssh.log"
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
    (b / "ssh").write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done > "{log}"\n')
    for f in b.iterdir():
        f.chmod(0o755)

    def answer(**files):
        for k, v in files.items():
            (data / k).write_text(v)
    return b, data, log, answer


def _make(fake, target, *args):
    b = fake[0]
    env = {k: v for k, v in os.environ.items() if k not in ("HOST_SSH_FINGERPRINT",)}
    env.update(PATH=f"{b}{os.pathsep}{os.environ['PATH']}", HOME=str(b.parent))
    return subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, f"PYTHON={sys.executable}",
                           *args], capture_output=True, text=True, env=env, timeout=60)


@needs_make
def test_make_mobile_check_sees_every_interface_and_a_password(fake_bin):
    _, _, _, answer = fake_bin
    answer(tailscale_ip_4=PRIVATE + "\n", tailscale_ip_6="", tailscale_debug_prefs='{"RunSSH": false}',
           sshd_T=GOOD_SSHD.replace("passwordauthentication no", "passwordauthentication yes"),
           ss_Hltn="LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n")
    res = _make(fake_bin, "mobile-check")
    assert res.returncode != 0
    assert "✗ SSH : le serveur écoute sur toutes les interfaces" in res.stdout
    assert "✗ SSH : passwordauthentication yes, no attendu" in res.stdout
    answer(sshd_T=GOOD_SSHD, ss_Hltn=GOOD_SS)
    (fake_bin[0].parent / ".ssh").mkdir()
    (fake_bin[0].parent / ".ssh" / "authorized_keys").write_text("ecdsa-sha2-nistp256 AAAA phone\n")
    res = _make(fake_bin, "mobile-check")
    assert res.returncode == 0, res.stdout + res.stderr
    assert IP.findall(res.stdout) == []


HOST = ("HOST_IP=10.0.0.4", "HOST_SSH_FINGERPRINT=SHA256:test")


@needs_make
@pytest.mark.parametrize("ip4", [None, "", "0.0.0.0\n", "127.0.0.1\n", "192.168.1.10\n", f"{PRIVATE}\n100.64.0.9\n"])
def test_the_console_tunnel_opens_nothing_without_the_private_address(fake_bin, ip4):
    _, _, log, answer = fake_bin
    if ip4 is not None:
        answer(tailscale_ip_4=ip4)
    res = _make(fake_bin, "glorfindel-host-tunnel-private", "-o", "glorfindel-host-known", *HOST,
                "HOST_ENV=/nonexistent")
    assert res.returncode != 0 and "pas d'adresse privée" in res.stderr
    assert not log.exists()


@needs_make
def test_the_console_tunnel_binds_the_private_address_alone(fake_bin, tmp_path):
    _, _, log, answer = fake_bin
    answer(tailscale_ip_4=PRIVATE + "\n")
    env_file = tmp_path / "host.env"
    env_file.write_text("EREGION_CONSOLE_TOKEN=tok123\nEREGION_CONSOLE_HOSTS=h0.example\n")
    res = _make(fake_bin, "glorfindel-host-tunnel-private", "-o", "glorfindel-host-known", *HOST,
                f"HOST_ENV={env_file}")
    assert res.returncode == 0, res.stderr
    argv = log.read_text().splitlines()
    forwards = [argv[i + 1] for i, a in enumerate(argv) if a == "-L"]
    assert forwards == [f"{PRIVATE}:7007:127.0.0.1:7007"]
    assert "ExitOnForwardFailure=yes" in argv and "GatewayPorts=no" in argv and "StrictHostKeyChecking=yes" in argv
    assert not any("0.0.0.0" in a or a.startswith("7007:") or a.startswith("localhost") for a in argv)
    assert f"http://{PRIVATE}:7007/?token=tok123" in res.stdout
    assert "EREGION_CONSOLE_HOSTS" in res.stdout                 # the private address not listed: said
    env_file.write_text(f"EREGION_CONSOLE_TOKEN=tok123\nEREGION_CONSOLE_HOSTS=h0.example, {PRIVATE}\n")
    res = _make(fake_bin, "glorfindel-host-tunnel-private", "-o", "glorfindel-host-known", *HOST,
                f"HOST_ENV={env_file}")
    assert res.returncode == 0 and "EREGION_CONSOLE_HOSTS" not in res.stdout


@needs_make
def test_the_console_tunnel_wants_h0_s_pinned_host_key(fake_bin):
    _, _, log, answer = fake_bin
    answer(tailscale_ip_4=PRIVATE + "\n")
    res = _make(fake_bin, "glorfindel-host-tunnel-private", "-o", "glorfindel-host-known", "HOST_IP=10.0.0.4",
                "HOST_ENV=/nonexistent")
    assert res.returncode != 0 and "HOST_SSH_FINGERPRINT requis" in res.stderr
    assert not log.exists()
