"""SEC-C (#635; audit of 06/11, V-25): the job that builds and signs the images (publish.yml) reads
no shared cache, and its BuildKit is pinned by its digest. M5464–M5465 — with Jonathan's patch of the
workflow (the App of the sessions has no Workflows right); the rest of SEC-C: scripts/mutants/SEC-C.py.
"""
PUBLISH = ".github/workflows/publish.yml"
_T = "tests/unit/test_workflows.py::test_sec_c_the_job_that_signs_reads_no_shared_cache_and_pins_its_buildkit"

MUTANTS = [
    ("M5464", "the job that signs reads images.yml's cache again, written on main (SEC-C)", PUBLISH,
     "            org.opencontainers.image.source=https://github.com/grootcyber/eregion\n",
     "            org.opencontainers.image.source=https://github.com/grootcyber/eregion\n"
     "          cache-from: type=gha,scope=${{ matrix.image }}\n"),
    ("M5465", "the job that signs builds on the BuildKit the action picks, not the one pinned by its digest (SEC-C)",
     PUBLISH, "          driver-opts: image=moby/buildkit@sha256:c5f8862f52499773af85bc07695b2379ef08e8002352b0df2c4864c91d78dabe\n",
     "          driver-opts: image=moby/buildkit:buildx-stable-1\n"),
]
TESTS = {"M5464": _T, "M5465": _T}
