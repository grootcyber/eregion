"""FLK6 (#1252): the tests of orodruin-update and orodruin-check no longer download cosign. What the two
recipes run to install it is ORO_COSIGN_INSTALL — the real install by default (published_image.py
install-cosign, kept only if its sha256 is the pinned one), replaced on the command line only, by a fake
that records its call in tests/unit/test_host_ssh.py. M8030–M8031: the install taken from the
environment, the update that no longer asks for it."""
MAKEFILE = "Makefile"
_H = "tests/unit/test_host_ssh.py::"

MUTANTS = [
    ("M8030", "cosign's install taken from the environment: an ORO_COSIGN_INSTALL left there skips it (FLK6)",
     MAKEFILE,
     "ORO_COSIGN_INSTALL = python3 scripts/published_image.py install-cosign\n",
     "ORO_COSIGN_INSTALL ?= python3 scripts/published_image.py install-cosign\n"),
    ("M8031", "orodruin-update no longer installs cosign: the latest release verified never read on a new "
     "workstation (FLK6)", MAKEFILE,
     "\t@$(ORO_COSIGN_INSTALL) >/dev/null || { echo \"✗ cosign : la dernière release vérifiée",
     "\t@true >/dev/null || { echo \"✗ cosign : la dernière release vérifiée"),
]

TESTS = {
    "M8030": _H + "test_cosign_s_install_is_the_pinned_one_an_environment_notwithstanding",
    "M8031": _H + "test_the_update_s_ssh_takes_the_pinned_key_alone",
}
