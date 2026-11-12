"""IML1 (#688): the VM that carries Glorfindel is Imladris — « H0 » never names it outside the history
(scripts/host_name.py; mutants M4710–M4714); IML1b (#747): the commands of Imladris are `make
imladris-*`, the former names silent aliases (M4840–M4849), and a live text never cites a former one.

The lot H0 keeps its name: the guard tells it from the host by its place on the line (after « lot »,
in a list of lots, a table's first cell, a value alone), or by a phrase named in LOT_PHRASES.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("host_name", REPO / "scripts" / "host_name.py")
host_name = importlib.util.module_from_spec(_spec)
sys.modules["host_name"] = host_name
_spec.loader.exec_module(host_name)


def test_h0_never_names_the_host_outside_the_history():
    assert host_name.problems(REPO) == []


@pytest.mark.parametrize("line", [
    "Publier, c'est déployer H0 : son CD la tire",
    "H0 ne déploie qu'un tag ou un commit",
    "une attaque ou une panne sur le banc, H0, un appel payant au modèle",
    "H0's CD reads it before and after a switch",
    "le rapport s'écrit sur H0 (#167)",
    "Glorfindel hébergé (H0)",
    "(le CD de H0, H1) : rien n'est fait",            # the host, then the lot of its CD
    "| Q3, H0 | IMDS coupé à la console",              # a question about the host
    "Avant CI3, H0 construisait l'image",
    '    return _principal_rights(ctx, "H0", "glorfindel-host", needs)',
    "**H0** (Glorfindel hébergé, pré-observation) ; puis H0 redéployé",   # a lot phrase, then the host
    # The review of IML1 (round 1): common ways of naming the host the first patterns let through.
    "Après CI6, H0 (le CD) tire la release",
    "Depuis SEC18, H0",
    "H1 → H0 (#300)",
    "H0 et O1 tirent l'image publiée",
    "H0, O1 et le poste",
    "H0 / O1 : les deux VM",
    "**H0**, O1 : deux VM",
    "| H0 | 10.0.0.4 | la VM de Glorfindel |",
    "le rapport arrive (ID1, H0)",
])
def test_h0_as_the_host_is_said(line):
    assert host_name.host_mentions(line) == [(1, line.strip())]


@pytest.mark.parametrize("line", [
    "socle O0 → E1 → O1 → R1 → G0, et H0 (Glorfindel sur une VM dédiée, pré-observation)",
    "O1, H0, R1, G0 (infra réelle) se font avec Jonathan",
    "(`ROADMAP.md`, lot H0 ; `docs/observation.md`)",
    "(H0, H1, H1b, H2)",
    "    lots: [H0]",
    '    "H0",',
    "Publier, c'est déployer Imladris (anciennement H0) : son CD la tire",
    "the proof at any time (like Imladris, formerly H0, the bench's hosted Glorfindel)",
    "En parallèle : **H0** (Glorfindel hébergé, pré-observation) et la piste IA",
    "HOST_KNOWN_HOSTS ?= $(HOME)/.eregion/h0_known_hosts ; bench_h0_reader.py ; H0_IP ; REQUEST_FROM=h0",
])
def test_h0_as_a_lot_or_the_former_name_is_kept(line):
    assert host_name.host_mentions(line) == []


def test_the_first_cell_is_a_lot_in_a_table_of_lots_only():
    lots = "| Lot | Contenu |\n|---|---|\n| H0 | **Glorfindel hébergé, pré-observation.** |\n"
    hosts = "| VM | Adresse |\n|---|---|\n| H0 | 10.0.0.4 |\n"
    assert host_name.host_mentions(lots) == []
    assert host_name.host_mentions(hosts) == [(3, "| H0 | 10.0.0.4 |")]


def _tree(root: Path, files: dict[str, str | bytes]) -> Path:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
    return root


def test_the_history_is_the_one_exception_for_the_name(tmp_path):
    """Outside git (the harness's copy), the tree's files: the history and the surfaces left to
    IML2 (Terraform, the host's deployed scripts, the role definitions) are not read; a doc,
    the doc of infra/, the code, the CLI of infra/ (`make imladris-*`), the site and, since IML1b, the
    CD are."""
    host = "Le CD de H0 déploie la release.\n"
    _tree(tmp_path, {
        "CHANGELOG.md": host, "docs/historique.md": host,
        "infra/glorfindel-host/main.tf": "# " + host, "infra/glorfindel-host/cd/eregion_cd.py": "# " + host,
        ".github/workflows/publish.yml": "# " + host, "tests/unit/test_x.py": "# " + host,
        "scripts/mutants/X.py": "# " + host,
        "infra/glorfindel-host/deploy.sh": "# " + host, "infra/identities/x.json": host,
        "infra/glorfindel-host/session_drain.auto.tfvars": "# " + host,
        "docs/banc.md": host, "infra/glorfindel-host/README.md": host, "glorfindel/cli.py": "# " + host,
        "infra/glorfindel-host/host_config.py": "# " + host,
        "docs/manuel/modules.yaml": "    nom: \"" + host.strip() + "\"\n", "docs/sprite.png": b"\x89PNG\0H0 H0",
    })
    said = sorted(p.split(":")[0] for p in host_name.problems(tmp_path) if "names the host" in p)
    assert said == ["docs/banc.md", "docs/manuel/modules.yaml", "glorfindel/cli.py",
                    "infra/glorfindel-host/README.md", "infra/glorfindel-host/cd/eregion_cd.py",
                    "infra/glorfindel-host/host_config.py"]


@pytest.mark.parametrize("doc,said", [
    ("Glorfindel vit sur Imladris, la VM du banc. Imladris (anciennement H0) tourne.\n", True),
    ("Glorfindel vit sur Imladris (anciennement H0), la VM du banc.\n", False),
    ("La coupure des sessions d'Imladris, anciennement H0 (Started).\n", False),
    ("Like Imladris, formerly H0, the bench's hosted Glorfindel.\n", False),
    ("Rien sur l'hôte ici.\n", False),
])
def test_the_first_mention_of_a_document_says_it_was_h0(tmp_path, doc, said):
    _tree(tmp_path, {"docs/x.md": doc, "glorfindel/x.py": "# Imladris, la VM.\n"})
    assert bool(host_name.problems(tmp_path)) is said


# The binaries a recipe of Imladris could reach, first on the PATH: each refuses (exit 97), so that
# nothing reaches Azure, Imladris, Orodruin or a Terraform state — `make -n` only prints, but it runs
# a $(MAKE) line, and $(shell …) (HOST_IP: `terraform output`) at the expansion.
REFUSED = ("az", "ssh", "scp", "ssh-keyscan", "docker", "terraform", "systemctl", "systemd-run",
           "loginctl", "curl", "tailscale", "sudo")


@pytest.fixture(scope="module")
def refusing_path(tmp_path_factory):
    b = tmp_path_factory.mktemp("refusing-bin")
    for name in REFUSED:
        (b / name).write_text("#!/bin/sh\necho \"refused: $0\" >&2\nexit 97\n")
        (b / name).chmod(0o755)
    return f"{b}{os.pathsep}{os.environ['PATH']}"


def _make_n(target: str, path: str | None = None, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "REF", "HOST_IP")}
    if path:
        env["PATH"] = path
    return subprocess.run(["make", "-n", "-s", "--no-print-directory", "-C", str(REPO), target, *args],
                          capture_output=True, text=True, timeout=60, env=env)


# IML1b (#747): every former name, as `make help` listed it before (0.5.11), and the name it leads to.
FORMER = {f"glorfindel-host-{x}": f"imladris-{x}" for x in (
    "init", "plan", "up", "down", "env", "known", "push", "client-rules", "start", "stop", "logs",
    "status", "pull", "model", "report", "campaign-report", "containment", "fault-rate", "url",
    "tunnel", "tunnel-go", "ssh", "cd-install", "cd-check", "cd-enable", "cd-disable", "cd-status",
    "cd-retry", "cd-rollback", "cd-uninstall", "watch-key", "queue-keys")}
FORMER.update({"mobile-check": "imladris-tunnel-check"})
FORMER.update({f"mobile-tunnel-{x}": f"imladris-tunnel-{x}" for x in (
    "install", "remove", "on", "off", "install-go", "remove-go", "on-go", "off-go")})
# What a recipe needs to say all it does: the variables its own guards read.
ARGS = ("REF=v0.0.1", "MODEL=anthropic/x", "CAMPAIGN=c1", "TAG=v0.0.1", "HOST_IP=203.0.113.9",
        "HOST_SSH_FINGERPRINT=SHA256:x", "PYTHON=python3")


@pytest.mark.parametrize("former", sorted(FORMER))
def test_make_imladris_is_make_glorfindel_host(former, refusing_path):
    """IML1b: read with `make -n` (nothing runs; a $(MAKE) line runs, under -n too, and the binaries
    refuse): each former name runs the very recipe of its new one, its guards and its sub-makes
    included — $@ is the new name, so the guard of a code session names it."""
    new = FORMER[former]
    target, alias = _make_n(new, refusing_path, *ARGS), _make_n(former, refusing_path, *ARGS)
    assert target.returncode == 0 and target.stdout.strip(), target.stderr
    assert "refused:" not in target.stderr + alias.stderr
    assert (alias.returncode, alias.stdout, alias.stderr) == (0, target.stdout, target.stderr)


def test_the_guard_of_a_former_name_is_its_new_one_s(refusing_path):
    """The former name prints the very guard line: the refusal of a code session, first."""
    for former, new in (("glorfindel-host-url", "imladris-url"), ("mobile-tunnel-on", "imladris-tunnel-on")):
        first = _make_n(former, refusing_path, *ARGS).stdout.splitlines()[0]
        assert first.endswith(f"scripts/mobile.py guard {new}") or f"mobile.py {new[9:]} --guard-only" in first


def test_a_former_name_without_its_new_target_fails():
    for name in ("glorfindel-host-nothing-of-that-name", "mobile-tunnel-nothing", "imladris-nothing-of-that-name"):
        res = _make_n(name)
        assert res.returncode != 0 and name in res.stderr


def test_make_help_shows_the_new_names_only():
    """IML1b: `make help` never shows a former name; the console of Imladris under imladris-*."""
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(REPO), "help"],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    assert "glorfindel-host-" not in res.stdout and "mobile-" not in res.stdout
    shown = {w for line in res.stdout.splitlines() if line.startswith("  make ") for w in line.split()}
    for name in ("imladris-tunnel-install", "imladris-tunnel-on", "imladris-tunnel-off", "imladris-tunnel-remove",
                 "imladris-tunnel-check", "imladris-tunnel", "imladris-url", "imladris-start", "imladris-cd-install"):
        assert name in shown, name


@pytest.mark.parametrize("text,said", [
    ("Puis `make glorfindel-host-push`.\n", True),
    ("Le tunnel : make mobile-tunnel-on, puis Safari.\n", True),
    ("Elle refuse, comme toutes sauf `make\nmobile-check`.\n", True),          # across a line
    ("Puis `make imladris-push` et `make imladris-tunnel-on`.\n", False),
    ("Les anciens noms (`glorfindel-host-*`, `mobile-*`) restent des alias.\n", False),
    ("infra/glorfindel-host/README.md, make -C infra/glorfindel-host\n", False),
])
def test_a_former_command_in_a_live_text_is_said(tmp_path, text, said):
    _tree(tmp_path, {"docs/x.md": text, "glorfindel/x.py": "# " + text})
    found = [p for p in host_name.problems(tmp_path) if "a former command" in p]
    assert sorted(p.split(":")[0] for p in found) == (["docs/x.md", "glorfindel/x.py"] if said else [])


def test_a_former_command_is_read_but_in_the_history_and_the_kept_texts(tmp_path):
    cited = "Puis `make glorfindel-host-start REF=…` et `make mobile-check`).\n"
    _tree(tmp_path, {
        "CHANGELOG.md": cited, "docs/historique.md": cited, "changes/X1.md": "### Fixed\n- " + cited,
        "tests/unit/test_x.py": "# " + cited, "scripts/mutants/X1.py": "# " + cited,
        ".github/workflows/x.yml": "# " + cited,
        "CLAUDE.md": "Imladris ne déploie qu'un tag (`make glorfindel-host-start REF=…`).\n",
        "ROADMAP.md": "| 0.5.10 | la console, `make mobile-check`) | publiée |\n",
        "infra/glorfindel-host/main.tf": "# " + cited, "infra/glorfindel-host/cd/eregion_cd.py": "# " + cited,
        "infra/glorfindel-host/deploy.sh": "# " + cited, "Makefile": "# " + cited,
    })
    found = sorted({p.split(":")[0] for p in host_name.problems(tmp_path) if "a former command" in p})
    assert found == ["Makefile", "infra/glorfindel-host/cd/eregion_cd.py", "infra/glorfindel-host/deploy.sh",
                     "infra/glorfindel-host/main.tf"]
    _tree(tmp_path, {"CLAUDE.md": "Puis `make glorfindel-host-push`.\n"})
    said = host_name.problems(tmp_path)
    assert any(p.startswith("CLAUDE.md:1: a former command") for p in said)
    assert any("the kept command « `make glorfindel-host-start REF=…` » is gone" in p for p in said)


def test_the_kept_former_commands_are_where_they_are_said():
    for rel, entries in host_name.OLD_KEPT.items():
        text = (REPO / rel).read_text(encoding="utf-8")
        for kept, _why in entries:
            assert host_name.OLD_COMMAND.search(kept) and kept in text, (rel, kept)


def test_an_untracked_file_is_never_read(tmp_path):
    """In git, the tracked files only: an .envrc, a host.env or a doc not added are never read."""
    _tree(tmp_path, {"docs/tracked.md": "Rien sur l'hôte.\n", "docs/untracked.md": "Le CD de H0.\n",
                     ".envrc": "export X=H0\n", "infra/glorfindel-host/host.env": "A=H0\n"})
    git = ["git", "-c", "init.defaultBranch=main", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-q"], check=True, capture_output=True)
    subprocess.run([*git, "add", "docs/tracked.md"], check=True, capture_output=True)
    assert host_name.files(tmp_path) == ["docs/tracked.md"]
    assert host_name.problems(tmp_path) == []


def test_a_tracked_file_whose_name_is_not_ascii_is_read(tmp_path):
    """FLK1: `git ls-files` quotes a name that is not ASCII (core.quotePath, git's default, set here
    whatever the operator's config) — read without -z, « "docs/caf\\303\\251.md" » names no file,
    and its H0 was skipped, unsaid. Read by -z, the name as it is, and what it says is seen."""
    _tree(tmp_path, {"docs/café.md": "Le CD de H0.\n", "docs/plain.md": "Rien.\n"})
    git = ["git", "-c", "init.defaultBranch=main", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-q"], check=True, capture_output=True)
    subprocess.run([*git, "config", "core.quotePath", "true"], check=True, capture_output=True)
    subprocess.run([*git, "add", "docs"], check=True, capture_output=True)
    assert host_name.files(tmp_path) == ["docs/café.md", "docs/plain.md"]
    assert [p.split(":")[0] for p in host_name.problems(tmp_path)] == ["docs/café.md"]


def test_without_git_hidden_files_and_env_files_are_not_read(tmp_path):
    _tree(tmp_path, {".envrc": "H0\n", "infra/glorfindel-host/host.env": "H0\n", ".hidden/x.md": "H0\n",
                     "docs/x.md": "Rien.\n"})
    assert host_name.files(tmp_path) == ["docs/x.md"]


def test_a_fragment_of_changes_has_no_first_mention_of_its_own_but_is_read(tmp_path):
    _tree(tmp_path, {"changes/X1.md": "### Fixed\n- **Imladris keeps its card** (X1, #1).\n"})
    assert host_name.problems(tmp_path) == []
    _tree(tmp_path, {"changes/X1.md": "### Fixed\n- **H0 keeps its card** (X1, #1).\n"})
    assert [p.split(":")[0] for p in host_name.problems(tmp_path)] == ["changes/X1.md"]


RULES = "glorfindel/rules/azure/detection_rules.yaml"


def test_the_query_text_kept_with_h0_is_in_a_shipped_rule_s_query():
    """The KQL comment of t1136-001 says H0 and stays so: renamed, it would change the rule's WL1
    fingerprint (base_rule_sha256 covers the whole rule) and set every client copy of it aside."""
    import yaml
    (kept, _why, _src), = host_name.KEPT[RULES]
    rules = yaml.safe_load((REPO / RULES).read_text(encoding="utf-8"))["rules"]
    assert [r["name"] for r in rules if kept in r["query"]] == ["t1136-001-local-account-creation-linux-v1"]


def test_a_kept_text_renamed_or_a_quotation_its_source_no_longer_says_is_said(tmp_path):
    readme = "infra/glorfindel-host/README.md"
    files = {RULES: "      // Measured on Imladris's Syslog\n",
             readme: "« Verified as H0 verifies it »\n",
             ".github/workflows/publish.yml": "      - name: Verified as Imladris verifies it\n"}
    _tree(tmp_path, files)
    said = host_name.problems(tmp_path)
    assert len(said) == 2, said
    assert said[0].startswith(RULES + ": the kept text « Measured on H0's Syslog » is gone")
    assert said[1].startswith(readme + ": « « Verified as H0 verifies it » » quotes .github/workflows/publish.yml")
