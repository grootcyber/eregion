"""V-32 (SEC7): the host key of the hosted Glorfindel (H0), pinned by its fingerprint.

Before, every command toward H0 ran `ssh -o StrictHostKeyChecking=accept-new`: the host key
accepted at first contact, whoever answered at that address. Now the fingerprint the operator
read on the VM (HOST_SSH_FINGERPRINT, in his environment, never in the repository) decides:
a dedicated known_hosts is written from the key the host presents only when it has that
fingerprint, ssh then trusts that file alone, and a key of another fingerprint — presented or
recorded — refuses before anything runs. Without it, accept-new stayed, said on every command;
since SEC-C (audit of 06/11, V-26), nothing reaches Imladris without it, scp of host.env included, as
for Orodruin — and the fingerprint is read on the VM through Azure (make imladris-fingerprint).

The recipes really run (`make imladris-ssh`), against a fake `ssh-keyscan` (it answers
with a key the test generated) and a fake `ssh` that records its arguments; the real
`ssh-keygen` computes the fingerprints. No VM, no network. The keys are throwaway, made here.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IP = "192.0.2.10"   # TEST-NET-1: no machine answers there
pytestmark = pytest.mark.skipif(not (shutil.which("make") and shutil.which("ssh-keygen")),
                                reason="make or ssh-keygen not installed")


def _key(tmp_path, name):
    """A throwaway ed25519 host key: (its known_hosts line for IP, its fingerprint)."""
    path = tmp_path / name
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True)
    pub = path.with_suffix(".pub").read_text().split()
    fp = subprocess.run(["ssh-keygen", "-lf", str(path.with_suffix(".pub"))], capture_output=True,
                        text=True, check=True).stdout.split()[1]
    return f"{IP} {pub[0]} {pub[1]}", fp


def _make(tmp_path, *args, presented="", silent=True, target="imladris-ssh", root=ROOT):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "ssh.log"
    log.write_text("")
    (bin_dir / "ssh").write_text('#!/bin/sh\necho "$*" >> "$FAKE_SSH_LOG"\n')
    (bin_dir / "scp").write_text('#!/bin/sh\necho "scp $*" >> "$FAKE_SSH_LOG"\n')
    (bin_dir / "ssh-keyscan").write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_PRESENTED"\n')
    (bin_dir / "az").write_text('#!/bin/sh\necho "az $*" >> "$FAKE_SSH_LOG"\nprintf "%s\\n" "$FAKE_AZ"\n')
    (bin_dir / "terraform").write_text('#!/bin/sh\nprintf "%s" "$FAKE_TF_SUBNET"\n')
    for f in ("ssh", "scp", "ssh-keyscan", "az", "terraform"):
        (bin_dir / f).chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path),
           "FAKE_SSH_LOG": str(log), "FAKE_PRESENTED": presented}
    for k in ("HOST_SSH_FINGERPRINT", "HOST_KNOWN_HOSTS", "HOST_IP", "HOST_SSH_KEY", "IMLADRIS_VM_ID"):
        env.pop(k, None)
    env.update({k: v for k, v in (a.split("=", 1) for a in args if a.startswith("FAKE_"))})
    args = [a for a in args if not a.startswith("FAKE_")]
    res = subprocess.run(["make", *(["-s"] if silent else []), "--no-print-directory", "-C", str(root),
                          "-f", str(ROOT / "Makefile"), target, f"HOST_IP={IP}", *args], env=env,
                         capture_output=True, text=True, timeout=60)
    return res, log.read_text().splitlines()


def test_a_host_presenting_the_expected_key_is_written_then_trusted_alone(tmp_path):
    line, fp = _key(tmp_path, "h0")
    known = tmp_path / "kh"
    res, calls = _make(tmp_path, f"HOST_SSH_FINGERPRINT={fp}", f"HOST_KNOWN_HOSTS={known}", presented=line)
    assert res.returncode == 0, res.stderr
    assert known.read_text().strip() == line and oct(known.stat().st_mode & 0o777) == "0o600"
    assert len(calls) == 1
    assert f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known}" in calls[0]
    assert "accept-new" not in calls[0]
    # Next time, the file is read, the host not asked: the same key goes on.
    res, calls = _make(tmp_path, f"HOST_SSH_FINGERPRINT={fp}", f"HOST_KNOWN_HOSTS={known}", presented="")
    assert res.returncode == 0 and len(calls) == 1


def test_a_host_presenting_another_key_is_refused_before_anything_runs(tmp_path):
    _, fp = _key(tmp_path, "h0")
    other, _ = _key(tmp_path, "intruder")
    known = tmp_path / "kh"
    res, calls = _make(tmp_path, f"HOST_SSH_FINGERPRINT={fp}", f"HOST_KNOWN_HOSTS={known}", presented=other)
    assert res.returncode != 0 and calls == []
    assert "n'a pas l'empreinte HOST_SSH_FINGERPRINT" in res.stderr and not known.exists()


def test_a_recorded_key_that_no_longer_has_the_fingerprint_refuses(tmp_path):
    """The VM rebuilt (a new key, a new fingerprint posed): the old file refuses, and says how out."""
    old, _ = _key(tmp_path, "h0-old")
    new, fp_new = _key(tmp_path, "h0-new")
    known = tmp_path / "kh"
    known.write_text(old + "\n")
    res, calls = _make(tmp_path, f"HOST_SSH_FINGERPRINT={fp_new}", f"HOST_KNOWN_HOSTS={known}", presented=new)
    assert res.returncode != 0 and calls == []
    assert "VM reconstruite" in res.stderr and str(known) in res.stderr
    assert known.read_text() == old + "\n"            # never rewritten in silence


def test_without_a_fingerprint_nothing_reaches_imladris_never_accept_new(tmp_path):
    """SEC-C (audit of 06/11, V-26): accept-new stayed without HOST_SSH_FINGERPRINT — the key taken at
    first contact, whoever answered. Now refused, as for Orodruin: nothing runs, and the message says
    where to read the fingerprint (Azure, never SSH)."""
    line, _ = _key(tmp_path, "h0")
    res, calls = _make(tmp_path, presented=line)
    assert res.returncode != 0 and calls == []
    assert "HOST_SSH_FINGERPRINT requis" in res.stderr and "jamais accept-new" in res.stderr
    assert "make imladris-fingerprint" in res.stderr and IP not in res.stderr
    assert not (tmp_path / ".eregion" / "h0_known_hosts").exists()


def test_the_ssh_options_toward_imladris_never_accept_a_new_key_fingerprint_or_not(tmp_path):
    """The key check left aside (`-o imladris-known`), the options alone: strict, the pinned file,
    ed25519 — with or without the fingerprint, never accept-new (a recipe that would skip the check
    still connects to nothing it has not verified)."""
    for args in ((), ("HOST_SSH_FINGERPRINT=SHA256:x",)):
        res, calls = _make(tmp_path, "-o", "imladris-known", *args, f"HOST_KNOWN_HOSTS={tmp_path / 'kh'}")
        assert res.returncode == 0, res.stderr
        assert len(calls) == 1 and "accept-new" not in calls[0], calls
        assert f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={tmp_path / 'kh'} -o HostKeyAlgorithms=ssh-ed25519" in calls[0]
    import re
    opts = re.search(r"(?m)^HOST_SSH_OPTS\s*=(.*)$", (ROOT / "Makefile").read_text(encoding="utf-8")).group(1)
    assert "accept-new" not in opts and "$(if" not in opts
    known = (ROOT / "infra" / "glorfindel-host" / "known_host.sh").read_text(encoding="utf-8")
    assert "exit 0" not in known.split('if [ -z "$want" ]; then', 1)[1].split("\nfi\n", 1)[0]


def test_host_env_reaches_imladris_only_through_the_pinned_key(tmp_path):
    """make imladris-push: without the fingerprint, no scp, no ssh; with it, every scp — host.env's
    first — and every ssh take the pinned file alone."""
    work = tmp_path / "work"
    (work / "infra" / "glorfindel-host").mkdir(parents=True)
    import shutil
    for name in ("known_host.sh", "ssh_opts.sh"):         # CDI2: HOST_SSH_OPTS, printed by ssh_opts.sh
        shutil.copy(ROOT / "infra" / "glorfindel-host" / name, work / "infra" / "glorfindel-host")
    (work / "infra" / "glorfindel-host" / "host.env").write_text("AZURE_SUBSCRIPTION_ID=sub\n")
    (work / "glorfindel-config.yaml").write_text("autonomy: {}\n")
    (work / ".venv" / "bin").mkdir(parents=True)
    # host_env.py --check passes, host_config.py copies the config: what is sent is what is checked here.
    (work / ".venv" / "bin" / "python").write_text('#!/bin/sh\ncase "$1" in *host_config.py) cp "$2" "$3";; esac\nexit 0\n')
    (work / ".venv" / "bin" / "python").chmod(0o755)
    res, calls = _make(tmp_path, target="imladris-push", root=work)
    assert res.returncode != 0 and calls == [] and "HOST_SSH_FINGERPRINT requis" in res.stderr
    line, fp = _key(tmp_path, "h0")
    known = tmp_path / "kh"
    res, calls = _make(tmp_path, f"HOST_SSH_FINGERPRINT={fp}", f"HOST_KNOWN_HOSTS={known}", presented=line,
                       target="imladris-push", root=work)
    assert res.returncode == 0, res.stdout + res.stderr
    scp = [c for c in calls if c.startswith("scp ")]
    assert scp and "infra/glorfindel-host/host.env" in scp[0], calls
    for c in calls:
        assert f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known} -o HostKeyAlgorithms=ssh-ed25519" in c, c
        assert "accept-new" not in c


def test_imladris_s_fingerprint_is_read_on_the_vm_through_azure(tmp_path):
    """SEC-C: the first contact — the fingerprint read by Run Command (the operator's az login),
    never by SSH; the VM's id from the subnet of infra/glorfindel-host's state (its subscription,
    never the CLI's current one), or IMLADRIS_VM_ID."""
    _, fp = _key(tmp_path, "h0")
    sub = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-glorfindel"
    subnet = f"{sub}/providers/Microsoft.Network/virtualNetworks/vnet-glorfindel/subnets/snet-glorfindel"
    answer = f"Enable succeeded:\n[stdout]\n256 {fp} root@vm-glorfindel (ED25519)\n\n[stderr]\n"
    res, calls = _make(tmp_path, f"FAKE_AZ={answer}", f"FAKE_TF_SUBNET={subnet}", target="imladris-fingerprint")
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == f"export HOST_SSH_FINGERPRINT={fp}"
    vm = f"{sub}/providers/Microsoft.Compute/virtualMachines/vm-glorfindel"
    assert calls == [calls[0]] and calls[0].startswith(f"az vm run-command invoke --ids {vm} --command-id RunShellScript")
    assert "ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub" in calls[0]
    res, calls = _make(tmp_path, f"FAKE_AZ={answer}", "IMLADRIS_VM_ID=/subscriptions/x/vm-y", target="imladris-fingerprint")
    assert res.returncode == 0 and calls[0].startswith("az vm run-command invoke --ids /subscriptions/x/vm-y ")
    res, calls = _make(tmp_path, "FAKE_AZ=Enable succeeded: nothing", f"FAKE_TF_SUBNET={subnet}",
                       target="imladris-fingerprint")
    assert res.returncode != 0 and "pas d'empreinte" in res.stderr and "export" not in res.stdout
    res, calls = _make(tmp_path, f"FAKE_AZ={answer}", "FAKE_TF_SUBNET=", target="imladris-fingerprint")
    assert res.returncode != 0 and calls == [] and "make imladris-init" in res.stderr
    main = (ROOT / "infra" / "glorfindel-host" / "main.tf").read_text(encoding="utf-8")
    assert 'name = "glorfindel"' in main and 'name                  = "vm-${local.name}"' in main


def test_a_fingerprint_that_is_not_one_refuses(tmp_path):
    res, calls = _make(tmp_path, "HOST_SSH_FINGERPRINT=xyz", presented="")
    assert res.returncode != 0 and calls == [] and "SHA256:" in res.stderr


def test_every_command_toward_h0_checks_the_key_first_and_orodruin_keeps_its_own():
    """Each target whose recipe reaches H0 (HOST_SSH, HOST_SSH_TTY, its scp, its tunnel) waits
    on imladris-known; Orodruin's ssh never takes H0's known_hosts."""
    import re
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    rules = re.findall(r"(?m)^(imladris-[\w-]+):([^\n=]*)\n((?:\t.*\n)*)", text)
    reaching = {name: deps for name, deps, recipe in rules
                if re.search(r"\$\(HOST_SSH(_TTY|_OPTS)?\)|status\.sh", recipe)}
    assert {"imladris-push", "imladris-start", "imladris-tunnel-go",
            "imladris-status", "imladris-cd-install"} <= set(reaching)
    assert {n for n, deps in reaching.items() if "imladris-known" not in deps} == set()
    # SEC-C: the check itself requires the fingerprint, as Orodruin's does.
    assert ' "$(HOST_KNOWN_HOSTS)" HOST_SSH_FINGERPRINT required\n' in text
    assert "$(SSH_OPTS)" not in "".join(r for n, _, r in rules if n != "imladris-known")
    assert re.search(r"(?m)^ORO_SSH\s*=\s*ssh \$\(SSH_OPTS\)", text)



# ── SEC-C review (round 1): the bench's targets reach Imladris too — its key checked first ──

BENCH_TARGETS = {"bench-preflight": [], "bench-report": ["RUN=r1"],
                 "bench-run-go": ["TARGET=vm-celebrimbor-gondolin", "SCENARIO=T1486"],
                 "bench-restore-go": ["TARGET=vm-celebrimbor-gondolin"]}


def test_every_target_handed_imladris_s_ssh_checks_its_key_first():
    """Not only imladris-*: every rule that hands a script Imladris's ssh command (a target-specific
    export of $(HOST_SSH)) or reaches it in its recipe checks the key before — imladris-known as a
    prerequisite, or its check in the recipe, after the guards (the origin, the agent session)."""
    import re
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    rules = {}
    for names, deps, recipe in re.findall(r"(?m)^([\w-]+(?: [\w-]+)*):(?!=)(?! export)([^\n=]*)\n((?:\t.*\n)*)", text):
        for n in names.split():
            rules[n] = (deps, recipe)
    handed = {n for m in re.finditer(r"(?m)^([\w-]+(?: [\w-]+)*): export \w+ = .*\$\(HOST_SSH", text)
              for n in m.group(1).split()}
    reaching = {n for n, (_, recipe) in rules.items() if re.search(r"\$\(HOST_SSH(_TTY|_OPTS)?\)", recipe)}
    assert set(BENCH_TARGETS) <= handed
    unchecked = {n for n in handed | reaching if n != "imladris-known"
                 and "imladris-known" not in rules[n][0]
                 and not re.search(r"\$\(HOST_KNOWN_CHECK\)|\$\(PAIR_SSH\)|known_host\.sh", rules[n][1])}
    assert unchecked == set()
    for name, guard in (("bench-run-go", "$(CONSOLE_GUARD) bench-run"), ("bench-restore-go", "--guard-only")):
        recipe = rules[name][1]
        assert recipe.index("$(MOB1_ORIGIN)") < recipe.index(guard) < recipe.index("$(HOST_KNOWN_CHECK)")


def _bench(tmp_path, target, *args):
    """`make <bench target>` from a checkout outside any lot's worktree (the guards refuse one), not in an
    agent session; python is a spy that writes its arguments, ssh, scp, az and terraform are fakes."""
    root = tmp_path / "checkout"
    for rel in ("Makefile", "scripts/mobile.py", "scripts/bench_shared.py", "infra/glorfindel-host/known_host.sh",
                "infra/glorfindel-host/ssh_opts.sh"):          # CDI2: HOST_SSH_OPTS, printed by it
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, root / rel)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "calls.log"
    log.write_text("")
    for f in ("ssh", "scp", "az", "terraform", "docker", "ssh-keyscan"):
        (bin_dir / f).write_text(f'#!/bin/sh\necho "{f} $*" >> "{log}"\n')
    spy = bin_dir / "spy-python"
    spy.write_text(f'#!/bin/sh\necho "python $*" >> "{log}"\n')
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in (
        "HOST_SSH_FINGERPRINT", "HOST_KNOWN_HOSTS", "HOST_IP", "HOST_SSH_KEY", "EREGION_AGENT_SESSION",
        "TARGET", "SCENARIO", "BEFORE", "RUN", "OUT", "POINT_MAX_H", "DRY_RUN")}
    env.update(PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path))
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(root), target, f"HOST_IP={IP}",
                          f"PYTHON={spy}", *args], env=env, capture_output=True, text=True, timeout=60)
    return res, log.read_text().splitlines()


@pytest.mark.parametrize("target", sorted(BENCH_TARGETS))
def test_without_a_fingerprint_no_bench_target_reaches_imladris(tmp_path, target):
    """SEC-C review: `make bench-*` handed its scripts an ssh toward Imladris without its key checked —
    without HOST_SSH_FINGERPRINT, ssh refused only for a missing known_hosts, and went for an old one. Now
    nothing runs but the guards: the script never starts, no ssh, no keyscan, and the way to the key said."""
    res, calls = _bench(tmp_path, target, *BENCH_TARGETS[target])
    assert res.returncode != 0
    assert "HOST_SSH_FINGERPRINT requis" in res.stderr and "make imladris-fingerprint" in res.stderr, res.stderr
    # make reads the addresses (terraform output), said in the Makefile; nothing else goes.
    assert [c for c in calls if c.split()[0] != "terraform" and not c.endswith("--guard-only")] == [], calls


@pytest.mark.parametrize("target", sorted(BENCH_TARGETS))
def test_with_its_key_pinned_each_bench_target_runs_its_script(tmp_path, target):
    line, fp = _key(tmp_path, "h0")
    known = tmp_path / "kh"
    known.write_text(line + "\n")
    res, calls = _bench(tmp_path, target, *BENCH_TARGETS[target], f"HOST_SSH_FINGERPRINT={fp}",
                        f"HOST_KNOWN_HOSTS={known}")
    assert res.returncode == 0, res.stdout + res.stderr
    script = target.removesuffix("-go").replace("-", "_")
    assert [c for c in calls if c.startswith("python") and not c.endswith("--guard-only")] == [
        f"python scripts/{script}.py"], calls
    assert not [c for c in calls if c.split()[0] in ("ssh", "scp", "ssh-keyscan")], calls

# ── MOB3 (bench of 11/11): a command toward Imladris never printed, its address and key with it ──

def test_make_glorfindel_host_ssh_prints_nothing_of_its_command(tmp_path):
    """Without -s, make printed `ssh … glorfindel@<address of Imladris>`, the key's path with it: pasted
    from the phone's terminal, the line left as it was. Now the recipe runs silent; the ssh goes as before."""
    line, fp = _key(tmp_path, "h0")
    known = tmp_path / "kh"
    known.write_text(line + "\n")
    known.chmod(0o600)
    key = tmp_path / "id_imladris"
    res, calls = _make(tmp_path, f"HOST_SSH_FINGERPRINT={fp}", f"HOST_KNOWN_HOSTS={known}",
                       f"HOST_SSH_KEY={key}", silent=False)
    assert res.returncode == 0, res.stderr
    assert len(calls) == 1 and f"glorfindel@{IP}" in calls[0] and f"-i {key}" in calls[0]   # unchanged
    said = res.stdout + res.stderr
    assert IP not in said and str(key) not in said and "ssh " not in said, said


def test_no_command_toward_imladris_is_echoed_by_make():
    """Every logical line of every imladris-* recipe starts with @: none prints its command — the
    address of Imladris, its user, the key's path or the operator's address (terraform's operator_cidr)."""
    import re
    lines = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    echoed, target, cont = [], None, False
    for ln in lines:
        rule = re.match(r"^([\w-]+):(?!=)", ln)
        if rule:
            target, cont = rule.group(1), False
            continue
        if not ln.startswith("\t"):
            target = target if (not ln.strip() or ln.startswith("#")) else None
            cont = False
            continue
        if not cont and target and target.startswith("imladris-") and not ln[1:].startswith("@"):
            echoed.append((target, ln.strip()[:60]))
        cont = ln.endswith("\\")
    assert echoed == [], echoed
    reaching = [t for t in ("imladris-ssh", "imladris-tunnel-go", "imladris-start",
                            "imladris-cd-install", "imladris-plan")
                if f"\n{t}:" in "\n" + "\n".join(lines)]
    assert len(reaching) == 5, reaching


# ── SEC14 (V-32, V-34): Orodruin's host key pinned too, never accept-new; its containers hardened ──

def _make_oro(tmp_path, target, *args, presented="", az_out=""):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "ssh.log"
    log.write_text("")
    # printf, not echo: dash's echo would turn a remote command's « \n » into a line of its own (OI3).
    (bin_dir / "ssh").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FAKE_SSH_LOG"\n')
    (bin_dir / "ssh-keyscan").write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_PRESENTED"\n')
    (bin_dir / "az").write_text('#!/bin/sh\necho "az $*" >> "$FAKE_SSH_LOG"\nprintf "%s\\n" "$FAKE_AZ"\n')
    (bin_dir / "git").write_text("#!/bin/sh\nexit 0\n")      # orodruin-check's git fetch: no network (OI3)
    for f in ("ssh", "ssh-keyscan", "az", "git"):
        (bin_dir / f).chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path),
           "FAKE_SSH_LOG": str(log), "FAKE_PRESENTED": presented, "FAKE_AZ": az_out}
    for k in ("ORO_SSH_FINGERPRINT", "ORO_KNOWN_HOSTS", "ORO_IP", "HOST_SSH_KEY", "VM_ID"):
        env.pop(k, None)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, f"ORO_IP={IP}", *args],
                         env=env, capture_output=True, text=True, timeout=60)
    return res, log.read_text().splitlines()


def test_orodruin_presenting_its_pinned_key_is_written_then_trusted_alone(tmp_path):
    line, fp = _key(tmp_path, "oro")
    known = tmp_path / "okh"
    res, calls = _make_oro(tmp_path, "orodruin-check", f"ORO_SSH_FINGERPRINT={fp}",
                           f"ORO_KNOWN_HOSTS={known}", presented=line)
    assert res.returncode == 0, res.stderr
    assert known.read_text().strip() == line
    # OI3: the image in service read first (~/.eregion-image), then the contract — each strict.
    assert len(calls) == 2 and ".eregion-image" in calls[0] and "python -m eregion_core.orodruin" in calls[1]
    assert all(f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known}" in c for c in calls)
    assert not any("accept-new" in c for c in calls)


STRICT_ORO = ("-o StrictHostKeyChecking=yes", "-o HostKeyAlgorithms=ssh-ed25519")


def test_the_update_s_ssh_takes_the_pinned_key_alone(tmp_path):
    """OI3: orodruin-update (run by orodruin-start) checks the host key first (orodruin-known), then
    reads the image in service through SSH_OPTS — the known_hosts written from the pinned key, ed25519
    only, never accept-new. The git here answers nothing: the comparison stops there, said."""
    line, fp = _key(tmp_path, "oro")
    known = tmp_path / "okh"
    res, calls = _make_oro(tmp_path, "orodruin-update", f"ORO_SSH_FINGERPRINT={fp}",
                           f"ORO_KNOWN_HOSTS={known}", presented=line)
    assert known.read_text().strip() == line, res.stderr        # orodruin-known ran, before
    assert calls and ".eregion-image" in calls[0], (calls, res.stderr)
    for c in calls:
        assert all(o in c for o in STRICT_ORO) and f"-o UserKnownHostsFile={known}" in c, c
        assert "accept-new" not in c
    assert res.returncode != 0 and "rien n'est mis à jour" in res.stderr


def test_the_update_without_its_fingerprint_sends_nothing(tmp_path):
    res, calls = _make_oro(tmp_path, "orodruin-update", presented="")
    assert res.returncode != 0 and calls == [] and "ORO_SSH_FINGERPRINT requis" in res.stderr


def test_orodruin_without_its_fingerprint_is_refused_never_accept_new(tmp_path):
    res, calls = _make_oro(tmp_path, "orodruin-check", presented="")
    assert res.returncode != 0 and calls == []
    assert "ORO_SSH_FINGERPRINT requis" in res.stderr and "jamais accept-new" in res.stderr


def test_orodruin_presenting_another_key_is_refused_before_anything_runs(tmp_path):
    _, fp = _key(tmp_path, "oro")
    other, _ = _key(tmp_path, "intruder")
    res, calls = _make_oro(tmp_path, "gothmog-run", f"ORO_SSH_FINGERPRINT={fp}",
                           f"ORO_KNOWN_HOSTS={tmp_path / 'okh'}", presented=other)
    assert res.returncode != 0 and calls == []
    assert "n'a pas l'empreinte ORO_SSH_FINGERPRINT" in res.stderr


def test_every_command_toward_orodruin_checks_its_key_first():
    """Each target whose recipe reaches Orodruin (ORO_SSH, SSH_OPTS: ssh, scp, an archive | ssh docker load)
    waits on orodruin-known — orodruin-exercise too, unless DRY_RUN, which sends nothing; and
    Orodruin's ssh options never accept a key on first contact."""
    import re
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    rules = re.findall(r"(?m)^([\w-]+):(?!=)([^\n]*)\n((?:\t.*\n)*)", text)
    reaching = {name: deps for name, deps, recipe in rules
                if re.search(r"\$\((ORO_SSH|SSH_OPTS)\)", recipe) and name != "orodruin-known"}
    assert {"orodruin-push", "orodruin-push-dev", "orodruin-check", "orodruin-ssh", "orodruin-exercise",
            "gothmog-preflight", "gothmog-run", "orodruin-campaign-plan", "orodruin-campaign-run"} <= set(reaching)
    assert {n for n, deps in reaching.items() if "orodruin-known" not in deps} == set()
    assert "$(if $(DRY_RUN),,orodruin-known)" in reaching["orodruin-exercise"]
    ssh_opts = re.search(r"(?m)^SSH_OPTS\s*=(.*)$", text).group(1)
    assert "StrictHostKeyChecking=yes" in ssh_opts and "UserKnownHostsFile=$(ORO_KNOWN_HOSTS)" in ssh_opts
    assert "accept-new" not in ssh_opts


def test_the_fingerprint_is_read_on_the_vm_through_azure(tmp_path):
    _, fp = _key(tmp_path, "oro")
    vm = ("/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-x/providers"
          "/Microsoft.Compute/virtualMachines/vm-x")
    answer = f"Enable succeeded:\n[stdout]\n256 {fp} root@vm-x (ED25519)\n\n[stderr]\n"
    res, calls = _make_oro(tmp_path, "orodruin-fingerprint", f"VM_ID={vm}", az_out=answer)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == f"export ORO_SSH_FINGERPRINT={fp}"
    assert calls[0].startswith(f"az vm run-command invoke --ids {vm} --command-id RunShellScript")
    res, _ = _make_oro(tmp_path, "orodruin-fingerprint", f"VM_ID={vm}", az_out="Enable succeeded: nothing")
    assert res.returncode != 0 and "pas d'empreinte" in res.stderr and "export" not in res.stdout


def test_every_injector_container_on_orodruin_runs_hardened_as_compose_does():
    """V-34: read-only root, /tmp in tmpfs, no capability, no privilege gained — every `docker run`
    of Orodruin's section goes through ORO_HARDEN."""
    import re
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    harden = re.search(r"(?m)^ORO_HARDEN\s*=(.*)$", text).group(1).split()
    assert harden == ["--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL", "--security-opt",
                      "no-new-privileges:true"]
    section = text.split("# ── Orodruin (O1)", 1)[1].split("# ── Profils d'usage", 1)[0]
    runs = [ln for ln in section.splitlines() if "docker run" in ln and not ln.startswith("#")]
    assert len(runs) >= 2 and all("docker run --rm $(ORO_HARDEN) " in ln for ln in runs), runs
