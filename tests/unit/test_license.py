"""LIC1 (#988): the licence the project declares is the licence it carries.

Until LIC1, `LICENSE` was a rewritten Apache-2.0 (10 375 bytes): definitions shortened, « embodied »
for « incorporated » in the patent clause, an MIT-like grant added in section 4, « exemplary » for
« consequential » in the limitation of liability (section 8), the appendix removed. GitHub read it
as `NOASSERTION`, while `pyproject.toml` and the README declare Apache-2.0. It is now the canonical
text, to the byte: the one apache.org publishes, which the packages of the lock carry too (yarl,
propcache, sniffio, googleapis-common-protos, the same sha256). The copyright line goes in `NOTICE`,
as the Apache convention wants: the licence text itself is never edited.
"""
import hashlib
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

# sha256 of https://www.apache.org/licenses/LICENSE-2.0.txt (11 358 bytes, with its appendix).
CANONICAL_APACHE_2_0 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_licence_is_the_canonical_apache_2_0_text_to_the_byte():
    data = (ROOT / "LICENSE").read_bytes()
    assert len(data) == 11358
    assert hashlib.sha256(data).hexdigest() == CANONICAL_APACHE_2_0


def test_the_notice_carries_the_copyright_and_names_the_licence():
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert notice.startswith("Eregion\nCopyright ")
    assert "Apache License, Version 2.0" in notice
    assert "[yyyy]" not in notice and "[name of copyright owner]" not in notice


def test_the_package_declares_the_licence_it_carries():
    project = _pyproject()["project"]
    assert project["license"] == {"text": "Apache-2.0"}
    assert "License :: OSI Approved :: Apache Software License" in project["classifiers"]
    assert "[LICENSE](LICENSE)" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_package_says_what_the_readme_says_and_the_pythons_the_ci_runs():
    project = _pyproject()["project"]
    readme_title = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]
    assert "Cloud Detection & Response" in readme_title
    assert project["description"].startswith("Cloud Detection & Response for teams without a SOC")
    assert "cdr" in project["keywords"]
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    tested = set()
    for job in ci["jobs"].values():
        tested |= set((job.get("strategy") or {}).get("matrix", {}).get("python-version", []))
    declared = {c.rsplit(" :: ", 1)[1] for c in project["classifiers"]
                if c.startswith("Programming Language :: Python :: 3.")}
    assert tested and declared == tested
