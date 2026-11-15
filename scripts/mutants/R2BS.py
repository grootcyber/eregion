"""Lot R2BS (#841) — poser l'outillage épinglé de l'injecteur de plan de contrôle sur l'hôte
d'exécution (staging hors-ligne, partie de #608). Les mutants portent sur la vérification des
empreintes (pose et runtime) et sur le HOME inscrite par run. M5386–M5392.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
STAGE = "scripts/stratus_stage.py"
HOST = "annatar/executors/stratus_host.py"
ENG = "annatar/engines/stratus.py"

_MISMATCH = "tests/unit/test_stratus_stage.py::test_verify_refuses_a_mismatch"
_NOPIN = "tests/unit/test_stratus_stage.py::test_stage_refuses_when_the_pin_has_no_checksum"
_TF_MISMATCH = ("tests/unit/test_annatar_stratus.py::"
                "test_executor_refuses_a_staged_terraform_that_does_not_match_its_sha256")
_TF_MISSING = ("tests/unit/test_annatar_stratus.py::"
               "test_executor_refuses_when_the_staged_terraform_is_missing")
_HOME = ("tests/unit/test_annatar_stratus.py::"
         "test_executor_run_home_is_writable_and_close_removes_it")
_AIRGAP = "tests/unit/test_annatar_stratus.py::test_airgap_env_points_terraform_offline"

MUTANTS = [
    ("M5386", "a staged download whose sha256 does not match the PIN is not refused (R2BS)",
     STAGE, "    if got != want:", "    if False:"),
    ("M5387", "a file with no sha256 in the PIN is staged unverified (R2BS)",
     STAGE, "        if name not in sums:", "        if False:"),
    ("M5388", "the staged provisioning tool altered since its sha256 was recorded is not refused "
     "(R2BS)", HOST, "        if got != want:", "        if False:"),
    ("M5389", "the staged provisioning tool is not re-verified before a run (R2BS)",
     HOST, "            self._verify_staged_terraform()", "            pass"),
    ("M5390", "the read-only staged home is used as HOME instead of a writable run HOME (R2BS)",
     HOST, '            self._run_home_path = tempfile.mkdtemp(prefix="stratus-home-")',
     "            self._run_home_path = self.layout.home"),
    ("M5391", "the run-scoped HOME is never removed on close (R2BS)",
     HOST, "            shutil.rmtree(self._run_home_path, ignore_errors=True)",
     "            pass"),
    ("M5392", "the staged provisioning-tool binary is not pointed at offline (R2BS)",
     ENG, "        env[STRATUS_TERRAFORM_BINARY_ENV] = str(terraform_binary)", "        pass"),
]

TESTS = {
    "M5386": _MISMATCH,
    "M5387": _NOPIN,
    "M5388": _TF_MISMATCH,
    "M5389": _TF_MISSING,
    "M5390": _HOME,
    "M5391": _HOME,
    "M5392": _AIRGAP,
}
