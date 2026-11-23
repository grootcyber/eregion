"""CDI2 (#922; Jonathan's decision of 19/11): what the Makefile's recipes do to Imladris as root, or to
decide which host key ssh trusts, lives in scripts .github/CODEOWNERS owns; the Makefile, which it does
not own (decision of 18/11), only calls them.

Three groups, the follow-up of CDI1 (the installation, tests/unit/test_host_cd_install.py):
1. the recipes that ran sudo on Imladris through HOST_SSH_TTY (`imladris-cd-enable`, `-cd-disable`,
   `-cd-uninstall`): infra/glorfindel-host/cd/sudo_from_workstation.sh, the same gesture each;
2. the host key's check (`imladris-known`): infra/glorfindel-host/known_host.sh, owned now, the target
   only its call; it refuses a known_hosts that is not a dedicated file (/dev/null, ~/.ssh/known_hosts);
3. the SSH options (HOST_SSH_OPTS, so HOST_SSH): printed by infra/glorfindel-host/ssh_opts.sh, the same
   bytes as before; each owned script checks them itself (`ssh_opts.sh check`): the form word for word,
   the dedicated known_hosts, not empty, holding Imladris's key — never believing the Makefile.

Jonathan's gestures do not change: the targets really run (`make imladris-cd-enable`…), against a fake
`ssh-keyscan` (it presents a key the test generated) and a fake `ssh` that writes each of its arguments
between brackets, so that the comparison is to the byte; the expected lists are what the Makefile's
recipes sent before CDI2 (measured against origin/main before the move: the same bytes). The real
`ssh-keygen` computes the fingerprints. No VM, no network: TEST-NET-1, placeholders only.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUDO = "infra/glorfindel-host/cd/sudo_from_workstation.sh"
OPTS = "infra/glorfindel-host/ssh_opts.sh"
KNOWN = "infra/glorfindel-host/known_host.sh"
IP = "192.0.2.10"   # TEST-NET-1: no machine answers there
pytestmark = pytest.mark.skipif(not (shutil.which("make") and shutil.which("ssh-keygen")),
                                reason="make or ssh-keygen not installed")

# The gesture of each recipe, as the Makefile wrote it before CDI2 (HOST_SSH_TTY '…').
GESTURES = {
    "enable": "sudo systemctl enable --now eregion-cd.timer && systemctl list-timers eregion-cd.timer --no-pager",
    "disable": "sudo systemctl disable --now eregion-cd.timer",
    "uninstall": "sudo bash .eregion-cd/install.sh --remove",
}

# Each fake writes « <tool>[arg][arg]… »: every argument, its blanks included, between brackets.
_FAKE = r"""#!/bin/sh
{ printf '%s' "$(basename "$0")"; for a in "$@"; do printf '[%s]' "$a"; done; echo; } >> "$FAKE_LOG"
exit 0
"""


def _key(tmp_path, name="h0", ip=IP):
    """A throwaway ed25519 host key: (its known_hosts line for ip, its fingerprint)."""
    path = tmp_path / name
    if not path.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True)
    pub = path.with_suffix(".pub").read_text().split()
    fp = subprocess.run(["ssh-keygen", "-lf", str(path.with_suffix(".pub"))], capture_output=True,
                        text=True, check=True).stdout.split()[1]
    return f"{ip} {pub[0]} {pub[1]}", fp


def _fakes(tmp_path, presented=""):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "ssh").write_text(_FAKE)
    # ssh-keyscan notes its arguments too, then presents the key.
    (bin_dir / "ssh-keyscan").write_text(_FAKE.replace("exit 0", f'printf "%s\\n" "{presented}"\nexit 0'))
    for tool in ("ssh", "ssh-keyscan"):
        (bin_dir / tool).chmod(0o755)
    log = tmp_path / "calls.log"
    log.write_text("")
    return bin_dir, log


def _env(tmp_path, bin_dir, log, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("EREGION_", "HOST_", "FAKE_", "ORO_"))}
    env.update(PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path), FAKE_LOG=str(log), **extra)
    return env


def _make(tmp_path, target, *args, fingerprint=True, presented=True):
    """`make <target>` with Imladris's key pinned: (the result, the calls noted, the known_hosts)."""
    line, fp = _key(tmp_path)
    bin_dir, log = _fakes(tmp_path, line if presented else "")
    known = tmp_path / "kh"
    env = _env(tmp_path, bin_dir, log, **({"HOST_SSH_FINGERPRINT": fp} if fingerprint else {}))
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, f"HOST_IP={IP}",
                          f"HOST_KNOWN_HOSTS={known}", *args], env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=60)
    return res, log.read_text().splitlines(), known


def _pinned(known, key=""):
    """HOST_SSH_OPTS, word by word, as the Makefile computed it before CDI2."""
    words = ["-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={known}", "-o", "HostKeyAlgorithms=ssh-ed25519"]
    return words + (["-i", key, "-o", "IdentitiesOnly=yes"] if key else [])


def _noted(tool, *args):
    return tool + "".join(f"[{a}]" for a in args)


# ── 1. The recipes that run sudo on Imladris: the owned script, the same gesture ─────────────────

@pytest.mark.parametrize("verb", sorted(GESTURES))
def test_each_sudo_recipe_sends_ssh_the_same_arguments_to_the_byte(tmp_path, verb):
    res, calls, known = _make(tmp_path, f"imladris-cd-{verb}")
    assert res.returncode == 0, res.stdout + res.stderr
    assert calls == [_noted("ssh-keyscan", "-T", "10", "-t", "ed25519", IP),
                     _noted("ssh", "-t", *_pinned(known), f"glorfindel@{IP}", GESTURES[verb])]


@pytest.mark.parametrize("verb", sorted(GESTURES))
def test_with_the_maintainer_s_key_too(tmp_path, verb):
    """The same bytes, but for a `~`: with HOST_SSH_KEY=~/…, the recipe's shell expanded it before CDI2;
    the script now passes « -i ~/… » to ssh as it is, and OpenSSH expands it itself — no effect."""
    key = tmp_path / "id_imladris"
    res, calls, known = _make(tmp_path, f"imladris-cd-{verb}", f"HOST_SSH_KEY={key}", "HOST_USER=azureuser")
    assert res.returncode == 0, res.stdout + res.stderr
    assert calls[-1] == _noted("ssh", "-t", *_pinned(known, str(key)), f"azureuser@{IP}", GESTURES[verb])


@pytest.mark.parametrize("verb", sorted(GESTURES))
def test_without_its_fingerprint_no_sudo_recipe_reaches_imladris(tmp_path, verb):
    res, calls, _ = _make(tmp_path, f"imladris-cd-{verb}", fingerprint=False)
    assert res.returncode != 0 and calls == []
    assert "HOST_SSH_FINGERPRINT requis" in res.stderr


def test_without_a_vm_a_sudo_recipe_says_so_and_nothing_goes(tmp_path):
    """Before, ssh was run toward « glorfindel@ » and failed; the script says it, as -cd-install does."""
    res, calls, _ = _make(tmp_path, "imladris-cd-enable", "HOST_IP=")
    assert res.returncode != 0 and calls == []
    assert "Pas de VM : make imladris-up d'abord" in res.stdout


def _sudo(tmp_path, verb="enable", known_line=True, **given):
    """The script run alone, as the Makefile calls it, `given` over its values: (the result, the calls).
    ~/kh holds Imladris's key (known_line), as imladris-known writes it."""
    bin_dir, log = _fakes(tmp_path)
    line, _ = _key(tmp_path)
    if known_line:
        (tmp_path / "kh").write_text(line + "\n")
    env = _env(tmp_path, bin_dir, log, **{"HOST_IP": IP, "HOST_USER": "glorfindel",
                                           "SSH_OPTS": " ".join(_pinned(tmp_path / "kh")), **given})
    res = subprocess.run(["bash", SUDO, *([verb] if verb is not None else [])], cwd=ROOT, env=env,
                         stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    return res, log.read_text().splitlines()


def test_the_script_alone_with_what_the_makefile_passes_goes(tmp_path):
    """The reference for the refusals below: each differs from it by one value."""
    res, calls = _sudo(tmp_path)
    assert res.returncode == 0, res.stderr
    assert calls == [_noted("ssh", "-t", *_pinned(tmp_path / "kh"), f"glorfindel@{IP}", GESTURES["enable"])]


@pytest.mark.parametrize("verb", [None, "", "remove", "enable;id", "ENABLE"])
def test_the_script_runs_its_three_gestures_never_another(tmp_path, verb):
    res, calls = _sudo(tmp_path, verb=verb)
    assert res.returncode != 0 and calls == []
    assert "enable, disable, uninstall, probe-enable ou probe-disable" in res.stderr


# HRN2 (#1079): the model's probe's timer, turned on and off by the same owned script, in a TTY.
PROBE_GESTURES = {
    "enable": "sudo systemctl enable --now harness-probe.timer && systemctl list-timers harness-probe.timer --no-pager",
    "disable": "sudo systemctl disable --now harness-probe.timer",
}


@pytest.mark.parametrize("verb", sorted(PROBE_GESTURES))
def test_the_probe_s_timer_is_turned_on_and_off_by_the_owned_script(tmp_path, verb):
    res, calls, known = _make(tmp_path, f"imladris-probe-{verb}")
    assert res.returncode == 0, res.stdout + res.stderr
    assert calls == [_noted("ssh-keyscan", "-T", "10", "-t", "ed25519", IP),
                     _noted("ssh", "-t", *_pinned(known), f"glorfindel@{IP}", PROBE_GESTURES[verb])]


def test_the_probe_s_targets_say_their_own_name_when_a_value_is_missing(tmp_path):
    res, calls = _sudo(tmp_path, verb="probe-enable", HOST_USER="")
    assert res.returncode != 0 and calls == []
    assert "make imladris-probe-enable le passe" in res.stderr


# Weakened, one way each: the options, the known_hosts they name.
WEAK = {
    "accept-new": lambda kh: f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={kh} -o HostKeyAlgorithms=ssh-ed25519",
    "no": lambda kh: f"-o StrictHostKeyChecking=no -o UserKnownHostsFile={kh} -o HostKeyAlgorithms=ssh-ed25519",
    "no first": lambda kh: f"-o StrictHostKeyChecking=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile={kh} "
                           "-o HostKeyAlgorithms=ssh-ed25519",
    "/dev/null": lambda kh: "-o StrictHostKeyChecking=yes -o UserKnownHostsFile=/dev/null -o HostKeyAlgorithms=ssh-ed25519",
    "then ProxyCommand": lambda kh: f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={kh} "
                                    "-o HostKeyAlgorithms=ssh-ed25519 -o ProxyCommand=/bin/false",
    "-F": lambda kh: f"-F /tmp/ssh_config -o StrictHostKeyChecking=yes -o UserKnownHostsFile={kh}",
}


@pytest.mark.parametrize("weak", sorted(WEAK))
def test_weakened_options_are_refused_before_any_call(tmp_path, weak):
    res, calls = _sudo(tmp_path, SSH_OPTS=WEAK[weak](tmp_path / "kh"))
    assert res.returncode != 0 and calls == [], res.stderr
    assert "rien ne part vers Imladris" in res.stderr


def _check_said(res):
    return "pas le known_hosts dédié d'Imladris" in res.stderr


def test_an_empty_known_hosts_is_refused(tmp_path):
    (tmp_path / "kh").write_text("")
    res, calls = _sudo(tmp_path, known_line=False)
    assert res.returncode != 0 and calls == [] and _check_said(res), res.stderr


def test_a_missing_known_hosts_is_refused(tmp_path):
    res, calls = _sudo(tmp_path, known_line=False)
    assert res.returncode != 0 and calls == [] and _check_said(res), res.stderr


def test_a_known_hosts_without_imladris_s_key_is_refused(tmp_path):
    """A file, not empty, but its keys for another address: never the one imladris-known checked."""
    other, _ = _key(tmp_path, "other", ip="198.51.100.7")
    (tmp_path / "kh").write_text(other + "\n")
    res, calls = _sudo(tmp_path, known_line=False)
    assert res.returncode != 0 and calls == [] and _check_said(res), res.stderr


@pytest.mark.parametrize("general", ["account", "through a link"])
def test_the_account_s_own_known_hosts_is_refused(tmp_path, general):
    """~/.ssh/known_hosts holds keys accepted elsewhere, at first contact: never the pinned file."""
    line, _ = _key(tmp_path)
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".ssh" / "known_hosts").write_text(line + "\n")
    kh = "~/.ssh/known_hosts"
    if general == "through a link":
        (tmp_path / "kh-link").symlink_to(tmp_path / ".ssh" / "known_hosts")
        kh = str(tmp_path / "kh-link")
    res, calls = _sudo(tmp_path, SSH_OPTS=" ".join(_pinned(kh)))
    assert res.returncode != 0 and calls == [] and _check_said(res), res.stderr


def test_the_known_hosts_under_the_home_goes(tmp_path):
    """« ~/… », as ssh reads it: the file under HOME, holding the key."""
    line, _ = _key(tmp_path)
    (tmp_path / ".eregion").mkdir()
    (tmp_path / ".eregion" / "h0_known_hosts").write_text(line + "\n")
    opts = " ".join(_pinned("~/.eregion/h0_known_hosts", "~/.ssh/id_imladris"))
    res, calls = _sudo(tmp_path, SSH_OPTS=opts)
    assert res.returncode == 0, res.stderr
    assert calls[0].startswith(_noted("ssh", "-t", *opts.split()))


@pytest.mark.parametrize("given, said", [
    ({"HOST_USER": "-oProxyCommand=sh"}, "HOST_USER n'est pas"),
    ({"HOST_IP": "-oProxyCommand=sh"}, "HOST_IP n'est pas"),
    ({"HOST_IP": "imladris.example"}, "HOST_IP n'est pas"),
    ({"HOST_USER": ""}, "HOST_USER manque"),
    ({"SSH_OPTS": ""}, "SSH_OPTS manque"),
])
def test_the_script_takes_an_address_a_user_and_options_never_an_option(tmp_path, given, said):
    res, calls = _sudo(tmp_path, **given)
    assert res.returncode != 0 and calls == [] and said in res.stderr, res.stderr


# ── 2. The host key's check: owned, the target only its call ──────────────────────────────────

def test_imladris_known_only_calls_the_owned_check():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.findall(r"(?m)^imladris-known:([^\n=]*)\n((?:\t.*\n)*)", text) == [("", "\t@$(HOST_KNOWN_CHECK)\n")]
    (check,) = re.findall(r"(?m)^HOST_KNOWN_CHECK = (.*)$", text)
    assert check == ('HOST_SSH_FINGERPRINT="$(HOST_SSH_FINGERPRINT)" bash infra/glorfindel-host/known_host.sh '
                     '"$(HOST_IP)" "$(HOST_KNOWN_HOSTS)" HOST_SSH_FINGERPRINT required')


def test_imladris_known_asks_the_host_as_before_then_trusts_the_file(tmp_path):
    """The key read once (ssh-keyscan, the same arguments), written 600; then read from the file alone."""
    res, calls, known = _make(tmp_path, "imladris-known")
    assert res.returncode == 0, res.stderr
    assert calls == [_noted("ssh-keyscan", "-T", "10", "-t", "ed25519", IP)]
    assert oct(known.stat().st_mode & 0o777) == "0o600"
    res, calls, _ = _make(tmp_path, "imladris-known")
    assert res.returncode == 0 and calls == []


@pytest.mark.parametrize("which", ["/dev/null", "~/.ssh/known_hosts"])
def test_imladris_known_refuses_a_known_hosts_that_is_not_dedicated_before_asking(tmp_path, which):
    """/dev/null: the key « written », nothing pinned; the account's file: keys accepted elsewhere."""
    if which.startswith("~"):
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh" / "known_hosts").write_text("")
        which = str(tmp_path / ".ssh" / "known_hosts")
    line, fp = _key(tmp_path)
    bin_dir, log = _fakes(tmp_path, line)
    res = subprocess.run(["bash", KNOWN, IP, which, "HOST_SSH_FINGERPRINT", "required"], cwd=ROOT,
                         env=_env(tmp_path, bin_dir, log, HOST_SSH_FINGERPRINT=fp), capture_output=True,
                         text=True, timeout=60)
    assert res.returncode != 0 and log.read_text() == ""
    assert "pas un known_hosts dédié" in res.stderr


# ── 3. The SSH options: printed by the owned script, the same bytes ─────────────────────────────

def test_the_makefile_takes_its_options_from_the_owned_script():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    (opts,) = re.findall(r"(?m)^HOST_SSH_OPTS\s*=\s*(.*)$", text)
    assert opts.startswith('$(or $(shell bash infra/glorfindel-host/ssh_opts.sh print "$(HOST_KNOWN_HOSTS)" '
                           '"$(HOST_SSH_KEY)"),$(error ')
    assert re.findall(r"(?m)^HOST_SSH\s*=\s*(.*)$", text) == ["ssh $(HOST_SSH_OPTS) $(HOST_USER)@$(HOST_IP)"]
    assert "StrictHostKeyChecking" not in opts


@pytest.mark.parametrize("known, key, printed", [
    # The trailing blank without a key, as $(SSH_KEY_OPTS) left it: the same bytes.
    ("/home/op/.eregion/h0_known_hosts", "",
     "-o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/op/.eregion/h0_known_hosts "
     "-o HostKeyAlgorithms=ssh-ed25519 "),
    ("/home/op/.eregion/h0_known_hosts", "~/.ssh/id_imladris",
     "-o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/op/.eregion/h0_known_hosts "
     "-o HostKeyAlgorithms=ssh-ed25519 -i ~/.ssh/id_imladris -o IdentitiesOnly=yes"),
])
def test_the_printed_options_are_the_makefile_s_former_ones(known, key, printed):
    res = subprocess.run(["bash", OPTS, "print", known, key], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0 and res.stdout == printed + "\n"


@pytest.mark.parametrize("args", [("print", ""), ("print", "-F/x"), ("print", "/kh", "-oProxyCommand=sh"),
                                  ("print", "/k h"), ("print", "/tmp/%h"), ("other",)])
def test_a_path_that_is_not_one_prints_nothing(args):
    res = subprocess.run(["bash", OPTS, *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert res.returncode != 0 and res.stdout == ""


def test_when_the_script_prints_nothing_make_stops_and_no_ssh_goes(tmp_path):
    """Never an ssh without the pinned options: $(error), before the recipe runs — the key checked first
    (imladris-known does not read HOST_SSH_KEY), then nothing."""
    res, calls, _ = _make(tmp_path, "imladris-ssh", "HOST_SSH_KEY=-oProxyCommand=sh")
    assert res.returncode != 0 and [c for c in calls if c.startswith("ssh[")] == [], calls
    assert "ssh_opts.sh n'a rien rendu" in res.stderr and "HOST_SSH_KEY « -oProxyCommand=sh »" in res.stderr


@pytest.mark.parametrize("target", ["imladris-ssh", "imladris-cd-retry", "imladris-stop"])
def test_every_ssh_toward_imladris_keeps_the_same_arguments(tmp_path, target):
    res, calls, known = _make(tmp_path, target)
    assert res.returncode == 0, res.stderr
    assert calls[-1].startswith(_noted("ssh", *_pinned(known), f"glorfindel@{IP}"))


# ── sudo, only in the owned script ─────────────────────────────────────────────────────────────

def _code(text):
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def test_sudo_is_run_on_imladris_only_by_the_owned_script():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    sudo = [line for line in _code(text) if re.search(r"\bsudo\b", line)]
    # The one sudo left is the workstation's own (make fix-state-ownership: the state's files, chowned here).
    assert sudo == ["\tsudo chown -R $(shell id -u):$(shell id -g) \\"], sudo
    assert "HOST_SSH_TTY" not in text and not re.search(r"\bssh -t\b", "\n".join(_code(text)))
    for verb in GESTURES:
        rules = re.findall(rf"(?m)^imladris-cd-{verb}:([^\n=]*)\n((?:\t.*\n)*)", text)
        assert rules == [(" imladris-known", f'\t@HOST_IP="$(HOST_IP)" HOST_USER="$(HOST_USER)" '
                          f'SSH_OPTS="$(HOST_SSH_OPTS)" bash {SUDO} {verb}\n')], rules
    script = "\n".join(_code((ROOT / SUDO).read_text(encoding="utf-8")))
    assert all(len(re.findall(rf"(?m)^\s*{verb}\)", script)) == 1 and script.count(g) == 1
               for verb, g in GESTURES.items())
    # HRN2: the probe's timer, the same way — the owned script's gesture, the target its call.
    for verb, g in PROBE_GESTURES.items():
        assert len(re.findall(rf"(?m)^\s*probe-{verb}\)", script)) == 1 and script.count(g) == 1
        rules = re.findall(rf"(?m)^imladris-probe-{verb}:([^\n=]*)\n((?:\t.*\n)*)", text)
        assert rules == [(" imladris-known", f'\t@HOST_IP="$(HOST_IP)" HOST_USER="$(HOST_USER)" '
                          f'SSH_OPTS="$(HOST_SSH_OPTS)" bash {SUDO} probe-{verb}\n')], rules
    assert 'ssh -t $SSH_OPTS "$HOST_USER@$HOST_IP" "$gesture"' in script
    assert script.index('ssh_opts.sh" check') < script.index("ssh -t ")
