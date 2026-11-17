"""Lot R2BX (#608) — construire l'injecteur de plan de contrôle DANS le conteneur `golang` épinglé
par défaut (plus de dépendance à un Go local ; EREGION_GO reste un override). Les mutants portent
sur la reproductibilité de la toolchain : l'épinglage de l'image PAR DIGEST et le `-trimpath`.
M5691–M5692. Mesurés par tests/unit/test_stratus_build.py::test_docker_build_argv_is_reproducible_and_pinned.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
BUILD = "scripts/stratus_build.py"

_ARGV = ("tests/unit/test_stratus_build.py::"
         "test_docker_build_argv_is_reproducible_and_pinned")

MUTANTS = [
    ("M5691", "the golang build image is pinned by tag, not by digest — the toolchain can drift and "
     "the built binary stops reproducing the pinned sha (R2BX)",
     BUILD,
     'GO_IMAGE = "golang:1.26@sha256:4165ee6bf3b7811fd7b40373290405c83d0167dcb87ee5f29c427cdcef45ff8f"',
     'GO_IMAGE = "golang:1.26"'),
    ("M5692", "the container build drops -trimpath — absolute build paths are baked in and the "
     "binary stops reproducing across machines (R2BX)",
     BUILD,
     '        "go", "build", "-trimpath", "-ldflags=-w -s", "-o", "/src/stratus", "./cmd/stratus",',
     '        "go", "build", "-ldflags=-w -s", "-o", "/src/stratus", "./cmd/stratus",'),
]

TESTS = {
    "M5691": _ARGV,
    "M5692": _ARGV,
}
