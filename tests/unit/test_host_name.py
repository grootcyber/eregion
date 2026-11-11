"""IML1 (#688): the VM that carries Glorfindel is Imladris — « H0 » never names it outside the history
(scripts/host_name.py; mutants M4710–M4714), and `make imladris-<x>` is `make glorfindel-host-<x>`.

The lot H0 keeps its name: the guard tells it from the host by its place on the line (after « lot »,
in a list of lots, a table's first cell, a value alone), or by a phrase named in LOT_PHRASES.
"""
import importlib.util
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
    IML2 (Terraform, the CD, the host's deployed scripts, the role definitions) are not read; a doc,
    the doc of infra/, the code, the CLI of infra/ (`make glorfindel-host-*`) and the site are."""
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
                    "infra/glorfindel-host/README.md", "infra/glorfindel-host/host_config.py"]


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


def _make_n(target: str) -> subprocess.CompletedProcess:
    return subprocess.run(["make", "-n", "-s", "--no-print-directory", "-C", str(REPO), target],
                          capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("suffix", ["init", "env"])
def test_make_imladris_is_make_glorfindel_host(suffix):
    """Read with `make -n`: nothing runs. The alias runs the same recipe; the target it aliases is
    untouched (the bench's guides use it)."""
    alias, target = _make_n(f"imladris-{suffix}"), _make_n(f"glorfindel-host-{suffix}")
    assert target.returncode == 0 and target.stdout.strip()
    assert (alias.returncode, alias.stdout) == (0, target.stdout)


def test_an_imladris_target_without_its_glorfindel_host_one_fails():
    res = _make_n("imladris-nothing-of-that-name")
    assert res.returncode != 0 and "imladris-nothing-of-that-name" in res.stderr


def test_an_untracked_file_is_never_read(tmp_path):
    """In git, the tracked files only: an .envrc, a host.env or a doc not added are never read."""
    _tree(tmp_path, {"docs/tracked.md": "Rien sur l'hôte.\n", "docs/untracked.md": "Le CD de H0.\n",
                     ".envrc": "export X=H0\n", "infra/glorfindel-host/host.env": "A=H0\n"})
    git = ["git", "-c", "init.defaultBranch=main", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-q"], check=True, capture_output=True)
    subprocess.run([*git, "add", "docs/tracked.md"], check=True, capture_output=True)
    assert host_name.files(tmp_path) == ["docs/tracked.md"]
    assert host_name.problems(tmp_path) == []


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
             readme: "« Verified as H0 verifies it » ; dit, sans retenir H0 » ; … H0 ne construit plus »\n",
             ".github/workflows/publish.yml": "      - name: Verified as Imladris verifies it\n",
             "infra/glorfindel-host/cd/eregion_cd.py": '"retenir H0 : seuls" — H0 ne construit plus\n'}
    _tree(tmp_path, files)
    said = host_name.problems(tmp_path)
    assert len(said) == 2, said
    assert said[0].startswith(RULES + ": the kept text « Measured on H0's Syslog » is gone")
    assert said[1].startswith(readme + ": « « Verified as H0 verifies it » » quotes .github/workflows/publish.yml")
