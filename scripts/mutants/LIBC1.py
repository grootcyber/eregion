"""LIBC1 (#1098): libc6 and libc-bin installed at their exact fixed version in both images, the second
written and dated exception to « no apt-get upgrade », until a digest of the base carries the fix.
M7167–M7171: the layer dropped from one Dockerfile, libc-bin left to apt-get's choice, another exact
version, the way out (when to remove it) lost, the header's list of exceptions back to ZLIB1 alone."""
GLOR = "glorfindel/Dockerfile"
ANNA = "annatar/Dockerfile"
_I = "tests/unit/test_image_cves.py::"

_PINS = "libc6=2.41-12+deb13u5 libc-bin=2.41-12+deb13u5"
_RUN = ("RUN apt-get update && \\\n"
        f"    apt-get install -y --no-install-recommends {_PINS} && \\\n"
        "    rm -rf /var/lib/apt/lists/*\n")
_REMOVE = ("# Remove this layer as soon as the base digest carries libc6 and libc-bin +deb13u5 or newer: in the very PR\n"
           "# of Dependabot's bump that brings it (docs/operations.md, « Les images publiées »). If Debian replaces\n")
_HEADER = "# the exceptions written and dated below (ZLIB1, LIBC1), each package at its exact version.\n"

MUTANTS = [
    ("M7167", "the injectors' image no longer installs the fixed libc: the two CVEs back in it alone (LIBC1)", ANNA,
     _RUN, ""),
    ("M7168", "libc-bin left out of the layer: it comes at whatever version apt-get resolves for it (LIBC1)", GLOR,
     f"--no-install-recommends {_PINS} && ", "--no-install-recommends libc6=2.41-12+deb13u5 && "),
    ("M7169", "the layer installs libc6 and libc-bin at another exact version than the one decided (LIBC1)", ANNA,
     f"--no-install-recommends {_PINS} && ",
     "--no-install-recommends libc6=2.41-12+deb13u4 libc-bin=2.41-12+deb13u4 && "),
    ("M7170", "the second exception's way out lost: nobody says when to remove the pin, it stays forever (LIBC1)",
     GLOR, _REMOVE, "# If Debian replaces\n"),
    ("M7171", "the header lists ZLIB1 alone: the second exception unsaid where the rule is written (LIBC1)", ANNA,
     _HEADER, "# the one exception written and dated below (ZLIB1), one package at its exact version.\n"),
]
TESTS = {
    "M7167": _I + "test_libc1_both_dockerfiles_carry_the_same_layer_byte_for_byte_with_both_packages_exact",
    "M7168": _I + "test_libc1_both_dockerfiles_carry_the_same_layer_byte_for_byte_with_both_packages_exact",
    "M7169": _I + "test_libc1_both_dockerfiles_carry_the_same_layer_byte_for_byte_with_both_packages_exact",
    "M7170": _I + "test_libc1_says_its_reason_its_date_and_when_to_remove_it",
    "M7171": _I + "test_the_header_says_the_exception_once",
}
