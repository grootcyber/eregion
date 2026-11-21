"""CDI1 (#918; Jonathan's decision of 18/11): `make imladris-cd-install`'s recipe lives in a script the
CODEOWNERS owns, infra/glorfindel-host/cd/install_from_workstation.sh; the target only checks Imladris's
key (imladris-known), then calls it.

Before, the recipe lived in the Makefile, which no line of .github/CODEOWNERS owns: a change there changed
what goes to Imladris and what sudo runs there, without a code owner's approval. The gestures did not
change, gesture for gesture: the webhook and the mention read on the workstation, ~/.eregion-cd created
700, the files copied, cosign downloaded by the VM, discord.env written under umask 077, installed-from,
then install.sh with sudo in a TTY — each stopping the installation when it fails.

The target really runs (`make imladris-cd-install`), against a fake `ssh-keyscan` (it presents a key the
test generated), a fake `ssh` and a fake `scp` that note their arguments and what they read on stdin, and a
`git` whose `rev-parse HEAD` answers a placeholder commit; the real `ssh-keygen` computes the fingerprints,
the real `python3` reads the webhook. No VM, no network: TEST-NET-1, placeholders only.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "infra/glorfindel-host/cd/install_from_workstation.sh"
IP = "192.0.2.10"   # TEST-NET-1: no machine answers there
WEBHOOK = "https://discord.example/api/webhooks/1/placeholder"
FILES = ("infra/glorfindel-host/cd/eregion_cd.py infra/glorfindel-host/cd/install.sh "
         "infra/glorfindel-host/cd/eregion-cd.service infra/glorfindel-host/cd/eregion-cd.timer "
         "infra/glorfindel-host/deploy.sh scripts/notify_discord.py glorfindel/chat_text.py "
         "scripts/published_image.py")
pytestmark = pytest.mark.skipif(not (shutil.which("make") and shutil.which("ssh-keygen")),
                                reason="make or ssh-keygen not installed")

# Each fake notes « <tool> <its arguments> », then what it read on stdin, each line under «   | ».
# FAKE_FAIL: a fragment of a call that fails (exit 255, as ssh does when the host does not answer).
_FAKE = r"""#!/bin/sh
printf '%s %s\n' "$(basename "$0")" "$*" >> "$FAKE_LOG"
in=$(cat)
[ -z "$in" ] || printf '%s\n' "$in" | sed 's/^/  | /' >> "$FAKE_LOG"
if [ -n "${FAKE_FAIL:-}" ]; then
  case "$(basename "$0") $*" in *"$FAKE_FAIL"*) exit 255 ;; esac
fi
exit 0
"""


def _key(tmp_path):
    """A throwaway ed25519 host key: (its known_hosts line for IP, its fingerprint)."""
    path = tmp_path / "h0"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True)
    pub = path.with_suffix(".pub").read_text().split()
    fp = subprocess.run(["ssh-keygen", "-lf", str(path.with_suffix(".pub"))], capture_output=True,
                        text=True, check=True).stdout.split()[1]
    return f"{IP} {pub[0]} {pub[1]}", fp


HEAD = "0123456789abcdef0123456789abcdef01234567"   # a placeholder commit, what the fake git answers
_REAL_GIT = shutil.which("git") or "git"


def _fakes(tmp_path):
    """bin/ with the fake ssh and scp, and a git whose `rev-parse HEAD` says FAKE_HEAD (empty: it fails, as
    outside a checkout) — the harness measures mutants in a copy that is no git repository."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for tool in ("ssh", "scp"):
        (bin_dir / tool).write_text(_FAKE)
    (bin_dir / "git").write_text(
        '#!/bin/sh\nif [ "$*" = "rev-parse HEAD" ]; then\n'
        '  [ -n "$FAKE_HEAD" ] || { echo "fatal: not a git repository" >&2; exit 128; }\n'
        '  echo "$FAKE_HEAD"; exit 0\nfi\n'
        f'exec "{_REAL_GIT}" "$@"\n')
    for tool in ("ssh", "scp", "git"):
        (bin_dir / tool).chmod(0o755)
    log = tmp_path / "calls.log"
    log.write_text("")
    return bin_dir, log


def _install(tmp_path, *args, fail="", webhook=True, ip=IP, head=HEAD):
    """`make imladris-cd-install` with Imladris's key pinned: (the result, the calls noted, known_hosts)."""
    bin_dir, log = _fakes(tmp_path)
    line, fp = _key(tmp_path)
    (bin_dir / "ssh-keyscan").write_text(f'#!/bin/sh\nprintf "%s\\n" "{line}"\n')
    (bin_dir / "ssh-keyscan").chmod(0o755)
    known = tmp_path / "kh"
    discord = tmp_path / "discord.env"
    # The bot's token in the file too: it never goes.
    discord.write_text("EREGION_DISCORD_BOT_TOKEN=BOT-PLACEHOLDER\n"
                       + (f"EREGION_DISCORD_WEBHOOK_DEPLOY={WEBHOOK}\nEREGION_DISCORD_MENTION=42\n" if webhook else ""))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("EREGION_", "HOST_", "FAKE_"))}
    env.update(PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path), FAKE_LOG=str(log),
               FAKE_FAIL=fail, FAKE_HEAD=head, EREGION_DISCORD_ENV=str(discord), HOST_SSH_FINGERPRINT=fp)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), "imladris-cd-install",
                          f"HOST_IP={ip}", f"HOST_KNOWN_HOSTS={known}", *args], env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=60)
    return res, log.read_text().splitlines(), known


def _gestures(known, key_opts="", head=HEAD):
    """The installation, gesture for gesture, as the Makefile's recipe made it before CDI1 (measured against
    it before the move: the same list)."""
    opts = f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known} -o HostKeyAlgorithms=ssh-ed25519{key_opts}"
    to = f"glorfindel@{IP}"
    return [
        f"ssh {opts} {to} mkdir -p .eregion-cd && chmod 700 .eregion-cd",
        f"scp -q {opts} {FILES} {to}:.eregion-cd/",
        f"ssh {opts} {to} python3 .eregion-cd/published_image.py install-cosign .eregion-cd/cosign",
        f"ssh {opts} {to} umask 077 && cat > .eregion-cd/discord.env",
        f"  | EREGION_DISCORD_WEBHOOK_DEPLOY={WEBHOOK}",
        "  | EREGION_DISCORD_MENTION=42",
        f"ssh {opts} {to} cat > .eregion-cd/installed-from",
        *([f"  | {head}"] if head else []),
        f"ssh -t {opts} {to} sudo bash .eregion-cd/install.sh",
    ]


def test_a_failed_rev_parse_writes_installed_from_empty_and_goes_on(tmp_path):
    """As the recipe did (no pipefail): the agent then says once in #deploy that it cannot tell when to update
    itself (infra/glorfindel-host/README.md) — never an installation left half done for it."""
    res, calls, known = _install(tmp_path, head="")
    assert res.returncode == 0, res.stdout + res.stderr
    assert calls == _gestures(known, head="")


def test_the_installation_makes_the_same_gestures_in_the_same_order(tmp_path):
    res, calls, known = _install(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    assert calls == _gestures(known)
    assert "BOT-PLACEHOLDER" not in "\n".join(calls)          # never the bot's token


def test_the_key_of_the_maintainer_goes_with_every_gesture(tmp_path):
    key = tmp_path / "id_imladris"
    res, calls, known = _install(tmp_path, f"HOST_SSH_KEY={key}")
    assert res.returncode == 0, res.stdout + res.stderr
    assert calls == _gestures(known, f" -i {key} -o IdentitiesOnly=yes")


# Each gesture that reaches Imladris, failing: nothing after it goes, and the installation fails.
@pytest.mark.parametrize("fail, done", [
    ("mkdir -p .eregion-cd", 1),
    ("scp ", 2),
    ("install-cosign", 3),
    ("discord.env", 6),
    ("installed-from", 8),
    ("sudo bash", 9),
])
def test_a_failed_gesture_stops_the_installation_there(tmp_path, fail, done):
    res, calls, known = _install(tmp_path, fail=fail)
    assert res.returncode != 0
    assert calls == _gestures(known)[:done], calls


def test_without_the_webhook_nothing_reaches_imladris(tmp_path):
    res, calls, _ = _install(tmp_path, webhook=False)
    assert res.returncode != 0 and calls == []
    assert "EREGION_DISCORD_WEBHOOK_DEPLOY manque" in res.stderr


def test_without_a_vm_the_target_says_so_and_nothing_goes(tmp_path):
    res, calls, _ = _install(tmp_path, ip="")
    assert res.returncode != 0 and calls == []
    assert "Pas de VM : make imladris-up d'abord" in res.stdout


def test_without_its_fingerprint_nothing_reaches_imladris(tmp_path):
    res, calls, _ = _install(tmp_path, "HOST_SSH_FINGERPRINT=")
    assert res.returncode != 0 and calls == []
    assert "HOST_SSH_FINGERPRINT requis" in res.stderr


# ── The script run alone: what it checks of what the Makefile, not owned, passes it ──────────────

# The known_hosts of these options, under the HOME of the test (ssh reads « ~ » as it; so does
# ssh_opts.sh check): CDI2 (#922) refuses one that is not a file, empty, or without Imladris's key.
PINNED = "-o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.eregion/h0_known_hosts -o HostKeyAlgorithms=ssh-ed25519"
KNOWN_AT = (".eregion/h0_known_hosts", "op_1/k.h+@")


def _script(tmp_path, **given):
    """The script run alone, as the Makefile calls it, `given` over its values: (the result, the calls).
    The known_hosts of KNOWN_AT hold a key for the address, as imladris-known writes it."""
    bin_dir, log = _fakes(tmp_path)
    line, _ = _key(tmp_path)
    for rel in KNOWN_AT:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(line.replace(IP, given.get("HOST_IP", IP), 1) + "\n")
    discord = tmp_path / "discord.env"
    discord.write_text(f"EREGION_DISCORD_WEBHOOK_DEPLOY={WEBHOOK}\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("EREGION_", "HOST_", "FAKE_"))}
    env.update(PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path), FAKE_LOG=str(log),
               EREGION_DISCORD_ENV=str(discord), FAKE_HEAD=HEAD,
               **{"HOST_IP": IP, "HOST_USER": "glorfindel", "CD_FILES": FILES, "SSH_OPTS": PINNED, **given})
    res = subprocess.run(["bash", SCRIPT], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                         text=True, timeout=60)
    return res, log.read_text().splitlines()


def _tools(calls):
    return [c.split(f" glorfindel@{IP}")[0] for c in calls if not c.startswith("  | ")]


def test_the_script_alone_with_what_the_makefile_passes_goes(tmp_path):
    """The reference for the refusals below: each differs from it by one value."""
    res, calls = _script(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    assert _tools(calls) == [f"ssh {PINNED}", f"scp -q {PINNED} {FILES}", f"ssh {PINNED}", f"ssh {PINNED}",
                             f"ssh {PINNED}", f"ssh -t {PINNED}"]


KH = "-o UserKnownHostsFile=~/.eregion/h0_known_hosts"
ALGO = "-o HostKeyAlgorithms=ssh-ed25519"


@pytest.mark.parametrize("opts", [
    "-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null",
    "-o UserKnownHostsFile=/dev/null",
    "-o StrictHostKeyChecking=yesno",
    # ssh keeps an option's first value: « no » before « yes » is « no » (`ssh -G`, review of CDI1).
    f"-o StrictHostKeyChecking=no -o StrictHostKeyChecking=yes {KH} {ALGO}",
    f"-oStrictHostKeyChecking=no {PINNED}",
    f"-o StrictHostKeyChecking=no {KH} {ALGO}",
    # The form, then an option that undoes the pinning or goes around it.
    f"{PINNED} -o ProxyCommand=/bin/false",
    f"{PINNED} -F /tmp/ssh_config",
    f"{PINNED} -J jump.example",
    f"{PINNED} -i /tmp/id -o ProxyCommand=/bin/false",
    f"{PINNED} -i /tmp/id -o KnownHostsCommand=/bin/true",
    f"{PINNED} -i /tmp/id -o IdentitiesOnly=yes -o ProxyCommand=/bin/false",     # the whole form, then more
    f"{PINNED} -i /tmp/id -o IdentitiesOnly=yes -F /tmp/ssh_config",
    # The key's path, read as a path: never an option, never ssh's %-tokens (review of CDI1, round 2).
    f"{PINNED} -i -F -o IdentitiesOnly=yes",
    f"{PINNED} -i /tmp/%h -o IdentitiesOnly=yes",
    f"-o StrictHostKeyChecking=yes {KH} -o ProxyCommand=/bin/false",
    f"-o StrictHostKeyChecking=yes -o KnownHostsCommand=/bin/true {ALGO}",
    f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOME/kh {ALGO}",
    f"{KH} -o StrictHostKeyChecking=yes {ALGO}",
])
def test_the_script_never_goes_without_the_pinned_key(tmp_path, opts):
    """Only the form the Makefile computes, word for word: anything else refused before any gesture (SEC-C),
    the webhook unread."""
    res, calls = _script(tmp_path, SSH_OPTS=opts)
    assert res.returncode != 0 and calls == []
    assert "StrictHostKeyChecking=yes" in res.stderr


@pytest.mark.parametrize("opts", [
    f"-o StrictHostKeyChecking=yes {KH} {ALGO}",
    f"-o StrictHostKeyChecking=yes {KH} {ALGO} -i ~/.ssh/id_imladris -o IdentitiesOnly=yes",
    f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/op_1/k.h+@ {ALGO} -i /k/id-1 -o IdentitiesOnly=yes",
])
def test_the_forms_the_makefile_computes_go(tmp_path, opts):
    res, calls = _script(tmp_path, SSH_OPTS=opts)
    assert res.returncode == 0, res.stderr
    assert _tools(calls)[-1] == f"ssh -t {opts}"


@pytest.mark.parametrize("files", [
    FILES.replace("scripts/published_image.py", "tests/published_image.py"),   # an agent's name, elsewhere
    FILES + " scripts/json.py",                                                # next to eregion_cd.py
    FILES.replace(" scripts/published_image.py", ""),                          # one missing
])
def test_the_script_copies_its_own_list_never_another(tmp_path, files):
    """scp copies by base name: the Makefile's list, not owned, is checked against the script's own."""
    res, calls = _script(tmp_path, CD_FILES=files)
    assert res.returncode != 0 and calls == []
    assert "CD_FILES n'est pas la liste des fichiers du CD" in res.stderr


def test_the_same_list_spaced_otherwise_goes(tmp_path):
    """make passes HOST_CD_FILES with the blanks of its continuation lines: compared word for word."""
    res, calls = _script(tmp_path, CD_FILES="  " + FILES.replace(" ", "   \t") + " ")
    assert res.returncode == 0, res.stderr
    assert f"scp -q {PINNED} {FILES} glorfindel@{IP}:.eregion-cd/" in calls


@pytest.mark.parametrize("given, said", [
    # « user@address » is ssh's last word before the command: a user that starts with « - » is an option.
    ({"HOST_USER": "-oProxyCommand=sh"}, "HOST_USER n'est pas"),
    ({"HOST_USER": "Glorfindel"}, "HOST_USER n'est pas"),
    ({"HOST_USER": "glorfindel@other"}, "HOST_USER n'est pas"),
    ({"HOST_USER": "op user"}, "HOST_USER n'est pas"),
    ({"HOST_IP": "-oProxyCommand=sh"}, "HOST_IP n'est pas"),
    ({"HOST_IP": "imladris.example"}, "HOST_IP n'est pas"),
    ({"HOST_IP": "192.0.2.10 -oProxyCommand=sh"}, "HOST_IP n'est pas"),
    ({"HOST_IP": "192.0.2"}, "HOST_IP n'est pas"),
])
def test_the_script_takes_an_address_and_a_user_never_an_option(tmp_path, given, said):
    res, calls = _script(tmp_path, **given)
    assert res.returncode != 0 and calls == [] and said in res.stderr, res.stderr


@pytest.mark.parametrize("user, ip", [("glorfindel", IP), ("azureuser", "10.0.0.4"), ("_op-1", "203.0.113.255")])
def test_the_address_and_users_the_makefile_computes_go(tmp_path, user, ip):
    res, calls = _script(tmp_path, HOST_USER=user, HOST_IP=ip)
    assert res.returncode == 0, res.stderr
    assert calls[-1].endswith(f" {user}@{ip} sudo bash .eregion-cd/install.sh")


@pytest.mark.parametrize("name", ["HOST_USER", "SSH_OPTS", "CD_FILES"])
def test_the_script_without_a_value_refuses(tmp_path, name):
    res, calls = _script(tmp_path, **{name: ""})
    assert res.returncode != 0 and calls == [] and f"{name} manque" in res.stderr


# ── The target: the key checked, then the call — nothing else ────────────────────────────────────

CALL = ('\t@HOST_IP="$(HOST_IP)" HOST_USER="$(HOST_USER)" SSH_OPTS="$(HOST_SSH_OPTS)" '
        f'CD_FILES="$(HOST_CD_FILES)" bash {SCRIPT}\n')


def test_the_target_only_checks_the_key_then_calls_the_script():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    rules = re.findall(r"(?m)^imladris-cd-install:([^\n=]*)\n((?:\t.*\n)*)", text)
    assert rules == [(" imladris-known", CALL)]
    # And the recipe never came back elsewhere in the Makefile: no other rule names what it did.
    for gesture in ("chmod 700 .eregion-cd", "install-cosign .eregion-cd/cosign", "> .eregion-cd/discord.env",
                    "> .eregion-cd/installed-from", "export-discord-env", "bash .eregion-cd/install.sh'"):
        assert gesture not in text, gesture


def test_the_script_s_gestures_are_in_the_owned_script():
    """What the tests above see is the script's: each gesture written there once, in this order."""
    code = "\n".join(line for line in (ROOT / SCRIPT).read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))
    order = ["export-discord-env", "'mkdir -p .eregion-cd && chmod 700 .eregion-cd'", "scp -q $SSH_OPTS $CD_FILES",
             "install-cosign .eregion-cd/cosign'", "'umask 077 && cat > .eregion-cd/discord.env'",
             "git rev-parse HEAD |", "ssh -t $SSH_OPTS \"$TO\" 'sudo bash .eregion-cd/install.sh'"]
    assert all(code.count(g) == 1 for g in order), [g for g in order if code.count(g) != 1]
    assert [code.index(g) for g in order] == sorted(code.index(g) for g in order)
    assert "set -eu\n" in code and "pipefail" not in code
