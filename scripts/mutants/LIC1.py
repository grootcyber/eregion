"""LIC1 (#988): the licence the project declares is the licence it carries — LICENSE is the canonical
Apache-2.0 text to the byte, and pyproject.toml declares the Pythons the CI runs. M6810–M6811."""
_T = "tests/unit/test_license.py"

MUTANTS = [
    ("M6810", "the licence's limitation of liability rewritten again: « exemplary » for « consequential » (LIC1)",
     "LICENSE", "incidental, or consequential damages of any character",
     "incidental, or exemplary damages of any character"),
    ("M6811", "the package no longer declares Python 3.12, which the CI runs (LIC1)",
     "pyproject.toml", '    "Programming Language :: Python :: 3.12",\n', ""),
]
TESTS = {
    "M6810": f"{_T}::test_the_licence_is_the_canonical_apache_2_0_text_to_the_byte",
    "M6811": f"{_T}::test_the_package_says_what_the_readme_says_and_the_pythons_the_ci_runs",
}
