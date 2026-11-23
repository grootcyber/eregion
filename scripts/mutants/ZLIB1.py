"""ZLIB1 (#962): zlib1g installed at its exact fixed version in both images, the one exception to « no
apt-get upgrade », written and dated until a digest of the base carries the fix. M6626–M6635: the layer
dropped from one Dockerfile, the version left free, an upgrade slipped in, the layer run after USER, its
way out (when to remove it) lost, the header's exception lost, another exact version, the doc's removal
lost, recommended packages let in at free versions."""
GLOR = "glorfindel/Dockerfile"
ANNA = "annatar/Dockerfile"
OPS = "docs/operations.md"
_I = "tests/unit/test_image_cves.py::"

_PIN = "zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1"
_RUN = ("RUN apt-get update && \\\n"
        f"    apt-get install -y --no-install-recommends {_PIN} && \\\n"
        "    rm -rf /var/lib/apt/lists/*\n")
_REMOVE = ("# Remove this layer as soon as the base digest carries zlib1g +deb13u1 or newer: in the very PR of\n"
           "# Dependabot's bump that brings it (docs/operations.md, « Les images publiées »). If Debian replaces\n")
_HEADER = ("# (scripts/image_cves.py) — no apt-get upgrade here: the image stays what its digest says, but for\n"
           "# the exceptions written and dated below (ZLIB1, LIBC1), each package at its exact version.\n")

MUTANTS = [
    ("M6626", "the injectors' image no longer installs the fixed zlib1g: the CVE back in it alone (ZLIB1)", ANNA,
     _RUN, ""),
    ("M6627", "Glorfindel's image no longer installs the fixed zlib1g: the CVE back in it alone (ZLIB1)", GLOR,
     _RUN, ""),
    ("M6628", "zlib1g installed at a free version: whatever the mirrors serve the day of the build (ZLIB1)", GLOR,
     f"--no-install-recommends {_PIN} && ", "--no-install-recommends zlib1g && "),
    ("M6629", "an apt-get upgrade slipped into the exception: the image no longer what its digest says (ZLIB1)",
     ANNA, _RUN, _RUN.replace("RUN apt-get update && \\\n", "RUN apt-get update && apt-get upgrade -y && \\\n", 1)),
    ("M6630", "the exception run after USER: as the operator's UID, apt-get never installs it (ZLIB1)", GLOR,
     (_RUN, "USER app\n"), ("", "USER app\n" + _RUN)),
    ("M6631", "the exception's way out lost: nobody says when to remove the pin, it stays forever (ZLIB1)", ANNA,
     _REMOVE, "# If Debian replaces\n"),
    ("M6632", "the header still says « no apt-get upgrade here », its exception unsaid (ZLIB1)", GLOR,
     _HEADER, "# (scripts/image_cves.py) — no apt-get upgrade here: the image stays what its digest says.\n"),
    ("M6633", "the exception installs zlib1g at another exact version than the one decided (ZLIB1)", ANNA,
     f"--no-install-recommends {_PIN} && ", "--no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+b1 && "),
    ("M6634", "the operations doc no longer says when nor how the exception goes: the pin outlives its cause "
     "(ZLIB1)", OPS, "retirer la couche dans la même PR", "garder la couche"),
    ("M6635", "the exception lets apt-get bring its recommended packages, at whatever version the mirrors serve "
     "(ZLIB1)", GLOR, f"    apt-get install -y --no-install-recommends {_PIN} && ",
     f"    apt-get install -y {_PIN} && "),
]
TESTS = {
    "M6626": _I + "test_both_dockerfiles_carry_the_same_exception_byte_for_byte_with_the_exact_version",
    "M6627": _I + "test_both_dockerfiles_carry_the_same_exception_byte_for_byte_with_the_exact_version",
    "M6628": _I + "test_every_apt_get_install_names_each_package_at_an_exact_version " + _I
    + "test_both_dockerfiles_carry_the_same_exception_byte_for_byte_with_the_exact_version",
    "M6629": _I + "test_no_dockerfile_upgrades_its_packages_at_build " + _I
    + "test_every_apt_get_install_names_each_package_at_an_exact_version",
    "M6630": _I + "test_the_exception_is_the_first_layer_after_from_run_as_root_before_any_user",
    "M6631": _I + "test_the_exception_says_its_reason_its_date_and_when_to_remove_it",
    "M6632": _I + "test_the_header_says_the_exception_once",
    "M6633": _I + "test_both_dockerfiles_carry_the_same_exception_byte_for_byte_with_the_exact_version",
    "M6634": _I + "test_the_operations_doc_says_the_exception_and_its_removal",
    "M6635": _I + "test_both_dockerfiles_carry_the_same_exception_byte_for_byte_with_the_exact_version",
}
