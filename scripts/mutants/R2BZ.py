"""Lot R2BZ (#608) — l'hôte d'exécution durci laisse les providers Terraform s'exécuter : un tmpfs
EXEC dédié au HOME de run de Stratus (`/tmp` reste noexec). Sans lui, le warmup échoue au banc
(`fork/exec … permission denied`). Les mutants portent sur le mont exec (Makefile) et sur l'usage
de ce mont par l'adaptateur. M6081–M6082. Mesurés par tests/unit/test_annatar_stratus.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
HOST = "annatar/executors/stratus_host.py"
MK = "Makefile"

_HARDEN = "tests/unit/test_annatar_stratus.py::test_oro_harden_mounts_an_exec_home_and_keeps_tmp_noexec"
_HOME = ("tests/unit/test_annatar_stratus.py::"
         "test_executor_run_home_uses_the_exec_tmpfs_when_present")

MUTANTS = [
    ("M6081", "the hardened container mounts no exec tmpfs — Terraform providers cannot execute, the "
     "warmup fails (`fork/exec … permission denied`) (R2BZ)",
     MK, "--tmpfs /tmp --tmpfs /stratus-home:exec --cap-drop ALL",
     "--tmpfs /tmp --cap-drop ALL"),
    ("M6082", "the run HOME ignores the exec tmpfs and lands on noexec /tmp — the providers cannot "
     "execute (R2BZ)", HOST,
     "            base = EXEC_HOME if os.path.isdir(EXEC_HOME) else None",
     "            base = None"),
]

TESTS = {
    "M6081": _HARDEN,
    "M6082": _HOME,
}
