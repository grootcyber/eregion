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
])
def test_h0_as_the_host_is_said(line):
    assert host_name.host_mentions(line) == [(1, line.strip())]


@pytest.mark.parametrize("line", [
    "socle O0 → E1 → O1 → R1 → G0, et H0 (Glorfindel sur une VM dédiée, pré-observation)",
    "O1, H0, R1, G0 (infra réelle) se font avec Jonathan",
    "(`ROADMAP.md`, lot H0 ; `docs/observation.md`)",
    "(H0, H1, H1b, H2)",
    "| H0 | **Glorfindel hébergé, pré-observation.** Glorfindel tourne en continu",
    "    lots: [H0]",
    '    "H0",',
    "Publier, c'est déployer Imladris (anciennement H0) : son CD la tire",
    "the proof at any time (like Imladris, formerly H0, the bench's hosted Glorfindel)",
    "En parallèle : **H0** (Glorfindel hébergé, pré-observation) et la piste IA",
    "HOST_KNOWN_HOSTS ?= $(HOME)/.eregion/h0_known_hosts ; bench_h0_reader.py ; H0_IP ; REQUEST_FROM=h0",
])
def test_h0_as_a_lot_or_the_former_name_is_kept(line):
    assert host_name.host_mentions(line) == []


def _tree(root: Path, files: dict[str, str | bytes]) -> Path:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
    return root


def test_the_history_is_the_one_exception_for_the_name(tmp_path):
    """Outside git (the harness's copy), the tree's files: the history and the surfaces left to
    IML2 (Terraform, the CD) are not read; a doc, the doc of infra/, the code and the site are."""
    host = "Le CD de H0 déploie la release.\n"
    _tree(tmp_path, {
        "CHANGELOG.md": host, "docs/historique.md": host,
        "infra/glorfindel-host/main.tf": "# " + host, "infra/glorfindel-host/cd/eregion_cd.py": "# " + host,
        ".github/workflows/publish.yml": "# " + host, "tests/unit/test_x.py": "# " + host,
        "scripts/mutants/X.py": "# " + host,
        "docs/banc.md": host, "infra/glorfindel-host/README.md": host, "glorfindel/cli.py": "# " + host,
        "docs/manuel/modules.yaml": "    nom: \"" + host.strip() + "\"\n", "docs/sprite.png": b"\x89PNG\0H0 H0",
    })
    said = sorted(p.split(":")[0] for p in host_name.problems(tmp_path))
    assert said == ["docs/banc.md", "docs/manuel/modules.yaml", "glorfindel/cli.py",
                    "infra/glorfindel-host/README.md"]


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
