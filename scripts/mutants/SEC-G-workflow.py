"""SEC-G (#848; audit of 13/11, P-06): the release gate builds both images and refuses a High or Critical
CVE fixed upstream in their system packages (release-gate.yml, its job image-cves). M5779–M5780 — with
Jonathan's patch of the workflow (the App of the sessions has no Workflows right); the rest of SEC-G:
scripts/mutants/SEC-G.py.
"""
GATE = ".github/workflows/release-gate.yml"
_W = "tests/unit/test_workflows.py::"

MUTANTS = [
    ("M5779", "the gate's CVE scan of the Glorfindel image masked: its red never fails the job (SEC-G)", GATE,
     '--json cves-glorfindel.json || rc=1\n', '--json cves-glorfindel.json || true\n'),
    ("M5780", "the release gate's total no longer waits for the images' CVEs: a red one passes the gate (SEC-G)",
     GATE, "mutants-total, terraform, image-cves]\n", "mutants-total, terraform]\n"),
]
TESTS = {
    "M5779": _W + "test_sec_g_the_gate_refuses_a_high_cve_fixed_upstream_in_either_image",
    "M5780": _W + "test_sec_g_the_gate_refuses_a_high_cve_fixed_upstream_in_either_image " + _W
    + "test_the_last_job_waits_for_every_job_that_blocks_never_macos",
}
