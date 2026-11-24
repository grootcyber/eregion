"""SEC-G (audit of 13/11, P-06): no release publishes a system package its distribution already fixed.

The base image of both images is pinned by its digest and nothing refreshed it: a fix of the distribution
reached the images only by a bump made by hand. Now Dependabot proposes the digest's bump every
week (.github/dependabot.yml), and the release gate builds both images and runs scripts/image_cves.py:
a High or Critical CVE, fixed upstream, in a package of the operating system refuses the release.

Here: the judgement on grype's reports (written by hand in grype's JSON form — no grype, no network),
the pinned installer (a local archive), the scan's call, and Dependabot's file against the Dockerfiles.
The gate's job itself: tests/unit/test_workflows.py (with Jonathan's patch of release-gate.yml).

ZLIB1 (#962): the first of the exceptions to « no apt-get upgrade », written and dated in both Dockerfiles —
zlib1g at its exact fixed version, until a digest of the base carries it. Read from the files, never
built here; the version in a built image is read only when the operator names the images
(EREGION_ZLIB1_IMAGES), skipped otherwise.

LIBC1 (#1098): the second exception, written and dated the same way — libc6 and libc-bin at their exact
fixed version (the point release 13.8, no DSA), the layer right after ZLIB1's; the header lists the
exceptions. The built images are read when the operator names them (EREGION_LIBC1_IMAGES).
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "image_cves.py"
sys.path.insert(0, str(SCRIPT.parent))
import image_cves as ic  # noqa: E402

sys.path.remove(str(SCRIPT.parent))
DEBIAN = {"name": "debian", "version": "13"}


def _match(cve="CVE-2026-0001", severity="High", state="fixed", versions=("1.2-1+deb13u1",), name="libexample1",
           version="1.2-1", kind="deb"):
    return {"vulnerability": {"id": cve, "severity": severity, "fix": {"state": state, "versions": list(versions)}},
            "artifact": {"name": name, "version": version, "type": kind}}


def _judge(tmp_path, report, summary=None):
    path = tmp_path / "report.json"
    path.write_text(report if isinstance(report, str) else json.dumps(report))
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_STEP_SUMMARY"}
    if summary:
        env["GITHUB_STEP_SUMMARY"] = str(summary)
    return subprocess.run([sys.executable, str(SCRIPT), "judge", str(path), "--image", "eregion-gate/glorfindel"],
                          capture_output=True, text=True, timeout=30, env=env)


@pytest.mark.parametrize("severity", ["High", "Critical"])
@pytest.mark.parametrize("kind", ["deb", "rpm", "apk"])
def test_a_high_or_critical_cve_fixed_upstream_in_a_system_package_refuses(tmp_path, severity, kind):
    res = _judge(tmp_path, {"distro": DEBIAN, "matches": [_match(severity=severity, kind=kind)]})
    assert res.returncode == 1
    assert "CVE-2026-0001" in res.stdout and "libexample1" in res.stdout and "1.2-1+deb13u1" in res.stdout
    assert "la porte est rouge" in res.stdout and "Monter l'empreinte de l'image de base" in res.stdout


@pytest.mark.parametrize("match", [
    _match(state="not-fixed", versions=()),               # nothing to take: said, never a refusal
    _match(state="wont-fix", versions=()),
    _match(state="unknown", versions=()),
    _match(state="fixed", versions=()),                   # « fixed » without a version is no fix to take
    _match(severity="Medium"), _match(severity="Low"), _match(severity="Negligible"), _match(severity="Unknown"),
    _match(kind="python", name="litellm"),                # the lock's: pip-audit's job, not this one
    _match(kind="binary", name="python"),
])
def test_what_has_no_fix_is_less_grave_or_outside_the_system_s_packages_passes_said(tmp_path, match):
    res = _judge(tmp_path, {"distro": DEBIAN, "matches": [match]})
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Aucune vulnérabilité élevée ou critique corrigée en amont" in res.stdout
    assert "1 autre(s) correspondance(s)" in res.stdout


@pytest.mark.parametrize("severity", ["HIGH", "high", "critical", " Critical "])
def test_the_severity_is_compared_without_its_case(tmp_path, severity):
    res = _judge(tmp_path, {"distro": DEBIAN, "matches": [_match(severity=severity)]})
    assert res.returncode == 1 and "CVE-2026-0001" in res.stdout


@pytest.mark.parametrize("severity", ["Severe", "Important", "", None, "Hi gh", 7])
def test_a_severity_of_another_word_proves_nothing_never_a_mild_one(tmp_path, severity):
    """Another word (a scanner that changed, a field moved) is never taken for a severity that passes."""
    match = _match()
    match["vulnerability"]["severity"] = severity
    res = _judge(tmp_path, {"distro": DEBIAN, "matches": [match]})
    assert res.returncode == 2 and "une sévérité inconnue" in res.stderr


@pytest.mark.parametrize("severity", ["Unknown", "Negligible"])
def test_a_cve_the_distribution_rates_unknown_or_negligible_never_refuses(tmp_path, severity):
    """The known limit (docs/operations.md, « Les images publiées »): the gate follows the distribution's rating."""
    res = _judge(tmp_path, {"distro": DEBIAN, "matches": [_match(severity=severity)]})
    assert res.returncode == 0


def test_one_refusing_among_many_refuses_each_said_once(tmp_path):
    matches = [_match(severity="Medium"), _match(cve="CVE-2026-0002", severity="Critical", name="apt"),
               _match(cve="CVE-2026-0002", severity="Critical", name="apt"), _match(state="not-fixed", versions=())]
    res = _judge(tmp_path, {"distro": DEBIAN, "matches": matches})
    assert res.returncode == 1 and res.stdout.count("CVE-2026-0002") == 1
    assert "1 vulnérabilité(s) élevée(s) ou critique(s)" in res.stdout


def test_the_judgement_goes_to_the_run_s_summary(tmp_path):
    summary = tmp_path / "summary.md"
    res = _judge(tmp_path, {"distro": DEBIAN, "matches": [_match()]}, summary=summary)
    assert res.returncode == 1 and "| CVE-2026-0001 | High | libexample1 |" in summary.read_text()


@pytest.mark.parametrize("report", [
    "not json", "[]", {"distro": DEBIAN}, {"distro": DEBIAN, "matches": "x"},
    {"matches": []},                                       # no distribution seen: the system's packages unread
    {"distro": {"name": ""}, "matches": []},
    {"distro": DEBIAN, "matches": [{"vulnerability": "x"}]},
])
def test_a_report_that_proves_nothing_never_passes(tmp_path, report):
    res = _judge(tmp_path, report)
    assert res.returncode == 2 and "la porte ne passe pas" in res.stderr


def test_a_clean_report_passes(tmp_path):
    assert _judge(tmp_path, {"distro": DEBIAN, "matches": []}).returncode == 0


# ── grype, pinned ───────────────────────────────────────────────────────────────────

def _archive(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_grype_is_installed_only_from_the_archive_of_its_pinned_sha256(tmp_path, monkeypatch, capsys):
    good = _archive({"README.md": b"x", "grype": b"#!/bin/sh\necho grype\n"})
    (tmp_path / "good.tgz").write_bytes(good)
    monkeypatch.setattr(ic, "GRYPE_SHA256", hashlib.sha256(good).hexdigest())
    dest = tmp_path / "bin" / "grype"
    assert ic.install(dest, url=(tmp_path / "good.tgz").as_uri()) == 0
    assert dest.read_bytes() == b"#!/bin/sh\necho grype\n" and dest.stat().st_mode & 0o111
    other = _archive({"grype": b"something else"})
    (tmp_path / "other.tgz").write_bytes(other)
    dest.unlink()
    assert ic.install(dest, url=(tmp_path / "other.tgz").as_uri()) == 1 and not dest.exists()
    assert "rien n'est installé" in capsys.readouterr().err


def test_an_archive_without_the_binary_installs_nothing(tmp_path, monkeypatch):
    body = _archive({"README.md": b"x"})
    (tmp_path / "a.tgz").write_bytes(body)
    monkeypatch.setattr(ic, "GRYPE_SHA256", hashlib.sha256(body).hexdigest())
    assert ic.install(tmp_path / "grype", url=(tmp_path / "a.tgz").as_uri()) == 1
    assert not (tmp_path / "grype").exists()


def test_the_pin_names_one_release_of_grype_and_its_sha256():
    assert re.fullmatch(r"v\d+\.\d+\.\d+", ic.GRYPE_VERSION) and re.fullmatch(r"[0-9a-f]{64}", ic.GRYPE_SHA256)
    assert ic.GRYPE_URL == (f"https://github.com/anchore/grype/releases/download/{ic.GRYPE_VERSION}/"
                            f"grype_{ic.GRYPE_VERSION[1:]}_linux_amd64.tar.gz")


def test_the_scan_never_updates_the_database_and_judges_what_grype_wrote(tmp_path):
    """The database is fetched in a step of its own (retried); the scan reads it as it is."""
    fake = tmp_path / "grype"
    seen = tmp_path / "seen"
    fake.write_text("#!/bin/sh\n"
                    f'echo "$GRYPE_DB_AUTO_UPDATE $GRYPE_CHECK_FOR_APP_UPDATE $*" > "{seen}"\n'
                    'out=""; while [ $# -gt 0 ]; do [ "$1" = --file ] && out=$2; shift; done\n'
                    f"echo '{json.dumps({'distro': DEBIAN, 'matches': [_match()]})}' > \"$out\"\n")
    fake.chmod(0o755)
    out = tmp_path / "r.json"
    res = subprocess.run([sys.executable, str(SCRIPT), "scan", "eregion-gate/annatar", "--grype", str(fake),
                          "--json", str(out)], capture_output=True, text=True, timeout=30)
    assert res.returncode == 1 and "CVE-2026-0001" in res.stdout
    assert seen.read_text().split() == ["false", "false", "docker:eregion-gate/annatar", "-o", "json", "--file", str(out)]
    fake.write_text("#!/bin/sh\nexit 3\n")
    res = subprocess.run([sys.executable, str(SCRIPT), "scan", "x", "--grype", str(fake), "--json", str(out)],
                         capture_output=True, text=True, timeout=30)
    assert res.returncode == 2                                # grype failed: never a pass


# ── Dependabot proposes the base image's bump ─────────────────────────────────────────

DEPENDABOT = ROOT / ".github" / "dependabot.yml"


def _pinned_dockerfiles() -> dict[str, str]:
    """Each Dockerfile of the repository whose base is pinned by its digest: its directory → its FROM."""
    out = {}
    for path in sorted(ROOT.glob("*/Dockerfile")):
        froms = re.findall(r"(?m)^FROM\s+(\S+)", path.read_text(encoding="utf-8"))
        if froms and "@sha256:" in froms[0]:
            out[f"/{path.parent.name}"] = froms[0]
    return out


def test_dependabot_proposes_the_digest_of_every_pinned_base_image_weekly_in_one_pull_request():
    doc = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    assert doc["version"] == 2
    (docker,) = [u for u in doc["updates"] if u["package-ecosystem"] == "docker"]
    pinned = _pinned_dockerfiles()
    assert set(pinned) == {"/glorfindel", "/annatar"} and sorted(docker["directories"]) == sorted(pinned)
    assert docker["schedule"]["interval"] == "weekly"
    assert docker["groups"] == {"base-image": {"patterns": ["python"]}}          # both Dockerfiles, one PR
    (ignored,) = docker["ignore"]
    assert ignored["dependency-name"] == "python"
    assert sorted(ignored["update-types"]) == ["version-update:semver-major", "version-update:semver-minor"]


def test_both_images_start_from_the_same_base_by_its_digest():
    """One bump moves both (Dependabot's group): a base pinned apart would be refreshed apart."""
    froms = set(_pinned_dockerfiles().values())
    assert len(froms) == 1 and re.fullmatch(r"python:3\.12-slim@sha256:[0-9a-f]{64}", froms.pop())


def test_no_dockerfile_upgrades_its_packages_at_build():
    """The image is what its digest says: no apt-get upgrade (docs/operations.md, « Les images publiées »)."""
    for path in ROOT.glob("*/Dockerfile"):
        code = "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))
        assert not re.search(r"apt(-get)?\s+(dist-|full-)?upgrade", code), path


# ── ZLIB1 (#962): zlib1g at its fixed version, the first of the exceptions, dated ─────────────

ZLIB1G = "zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1"
ZLIB1_RUN = ("RUN apt-get update && \\\n"
             f"    apt-get install -y --no-install-recommends {ZLIB1G} && \\\n"
             "    rm -rf /var/lib/apt/lists/*\n")
IMAGES = ("glorfindel", "annatar")


def _dockerfile(name: str) -> str:
    return (ROOT / name / "Dockerfile").read_text(encoding="utf-8")


def _instructions(text: str) -> list[str]:
    """A Dockerfile's instructions as docker reads them: comments dropped, a line continued by a backslash
    joined to the next, the keyword in upper case, the words separated by one space."""
    out, cur = [], ""
    for line in text.splitlines():
        if not cur and line.lstrip().startswith("#"):
            continue
        if line.rstrip().endswith("\\"):
            cur += line.rstrip()[:-1] + " "
            continue
        cur += line
        if cur.split():
            keyword, _, rest = cur.strip().partition(" ")
            out.append(f"{keyword.upper()} {' '.join(rest.split())}")
        cur = ""
    return out


def _exception(text: str) -> str:
    """The exception as written: its comment, from « # ZLIB1 (#962) », through its RUN."""
    start = text.index("# ZLIB1 (#962)")
    return text[start:text.index(ZLIB1_RUN, start) + len(ZLIB1_RUN)]


def test_both_dockerfiles_carry_the_same_exception_byte_for_byte_with_the_exact_version():
    """One decision, one text: an exception edited in one Dockerfile only would leave the other image
    with the CVE, or with another version than the one decided."""
    texts = {name: _dockerfile(name) for name in IMAGES}
    for name, text in texts.items():
        assert text.count(ZLIB1_RUN) == 1, name
        assert text.count("# ZLIB1 (#962)") == 1, name
        assert [i for i in _instructions(text) if "zlib1g" in i] == [
            f"RUN apt-get update && apt-get install -y --no-install-recommends {ZLIB1G} && rm -rf /var/lib/apt/lists/*"]
    assert _exception(texts["glorfindel"]) == _exception(texts["annatar"])


def test_the_exception_is_the_first_layer_after_from_run_as_root_before_any_user():
    """apt-get needs root, and the layer must not depend on what the image copies after it."""
    for name in IMAGES:
        instructions = _instructions(_dockerfile(name))
        assert instructions[0].startswith("FROM python:3.12-slim@sha256:"), name
        assert "zlib1g" in instructions[1], (name, instructions[1])
        users = [n for n, i in enumerate(instructions) if i.startswith("USER ")]
        assert users and min(users) > 1, name


def test_every_apt_get_install_names_each_package_at_an_exact_version():
    """Never a free version, never a pattern: the image is what the Dockerfile and its digest say."""
    for path in sorted(ROOT.glob("*/Dockerfile")):
        for instruction in _instructions(path.read_text(encoding="utf-8")):
            for command in re.split(r"&&|;|\|\|", instruction):
                words = command.split()
                if "apt-get" not in words and "apt" not in words:
                    continue
                verb = [w for w in words if not w.startswith("-") and w not in ("RUN", "apt-get", "apt")]
                assert not verb or verb[0] in ("update", "install"), (path, command)
                if verb and verb[0] == "install":
                    packages = verb[1:]
                    assert packages, (path, command)
                    for package in packages:
                        assert re.fullmatch(r"[a-z0-9][a-z0-9.+-]*=[0-9][A-Za-z0-9.+:~-]*", package), (path, package)


def test_the_exception_says_its_reason_its_date_and_when_to_remove_it():
    """A pin nobody knows when to drop stays forever: the comment carries its own way out."""
    for name in IMAGES:
        text = " ".join(_exception(_dockerfile(name)).replace("#", " ").split())
        for said in ("CVE-2026-85091", "DSA-6613-1", "trixie-security", "Jonathan's decision of 20/11",
                     "never an apt-get upgrade, never a free version",
                     "Remove this layer as soon as the base digest carries zlib1g +deb13u1 or newer",
                     "in the very PR of Dependabot's bump that brings it",
                     "the build breaks loudly — on purpose"):
            assert said in text, (name, said)


def test_the_header_says_the_exception_once():
    """« no apt-get upgrade here » stays the rule, and lists its exceptions written below, in both Dockerfiles
    (the list of every exception: ZLIB1, then LIBC1)."""
    for name in IMAGES:
        header = _dockerfile(name).split("\nFROM ", 1)[0]
        assert header.count("no apt-get upgrade here") == 1, name
        assert " ".join(header.replace("#", " ").split()).count(
            "but for the exceptions written and dated below (ZLIB1, LIBC1), each package at its exact version") == 1, name


def test_the_operations_doc_says_the_exception_and_its_removal():
    doc = " ".join((ROOT / "docs" / "operations.md").read_text(encoding="utf-8").split())
    for said in ("ZLIB1", "CVE-2026-85091", "DSA-6613-1", "`+deb13u1`", "retirer la couche dans la même PR"):
        assert said in doc, said


_BUILT = [i.strip() for i in os.environ.get("EREGION_ZLIB1_IMAGES", "").split(",") if i.strip()]


@pytest.mark.skipif(not _BUILT, reason="EREGION_ZLIB1_IMAGES names no image built on this workstation")
@pytest.mark.parametrize("image", _BUILT or ["-"])
def test_a_built_image_carries_the_fixed_zlib1g(image):
    """Optional, on the workstation only: images already built (never built here), read without network."""
    import shutil
    if not shutil.which("docker"):
        pytest.skip("no docker")
    res = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "dpkg-query",
                          image, "-W", "-f=${Version}", "zlib1g"], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    assert res.stdout == ZLIB1G.split("=", 1)[1]


# ── LIBC1 (#1098): libc6 and libc-bin at their fixed version, the second exception, dated ───────

LIBC = "2.41-12+deb13u5"
LIBC1_PINS = f"libc6={LIBC} libc-bin={LIBC}"
LIBC1_RUN = ("RUN apt-get update && \\\n"
             f"    apt-get install -y --no-install-recommends {LIBC1_PINS} && \\\n"
             "    rm -rf /var/lib/apt/lists/*\n")


def _libc1(text: str) -> str:
    """The second exception as written: its comment, from « # LIBC1 (#1098) », through its RUN."""
    start = text.index("# LIBC1 (#1098)")
    return text[start:text.index(LIBC1_RUN, start) + len(LIBC1_RUN)]


def test_libc1_both_dockerfiles_carry_the_same_layer_byte_for_byte_with_both_packages_exact():
    """Both packages named, at the one version decided: libc-bin left out would come at whatever version
    apt-get resolves for it; one Dockerfile edited alone would leave the other image with the CVEs."""
    texts = {name: _dockerfile(name) for name in IMAGES}
    for name, text in texts.items():
        assert text.count(LIBC1_RUN) == 1, name
        assert text.count("# LIBC1 (#1098)") == 1, name
        assert [i for i in _instructions(text) if "libc" in i] == [
            f"RUN apt-get update && apt-get install -y --no-install-recommends {LIBC1_PINS} "
            "&& rm -rf /var/lib/apt/lists/*"], name
    assert _libc1(texts["glorfindel"]) == _libc1(texts["annatar"])


def test_libc1_is_the_layer_right_after_zlib1_as_root_before_any_user():
    """The exceptions come first, in the order they were decided, as root, before anything is copied."""
    for name in IMAGES:
        instructions = _instructions(_dockerfile(name))
        assert "zlib1g" in instructions[1] and f"libc6={LIBC}" in instructions[2], (name, instructions[1:3])
        assert instructions[3].startswith("WORKDIR "), (name, instructions[3])
        users = [n for n, i in enumerate(instructions) if i.startswith("USER ")]
        assert users and min(users) > 2, name


def test_libc1_says_its_reason_its_date_and_when_to_remove_it():
    """No DSA here: the fix came with a point release, and the comment says it, with its own way out."""
    for name in IMAGES:
        text = " ".join(_libc1(_dockerfile(name)).replace("#", " ").split())
        for said in ("CVE-2026-19499", "CVE-2026-5435", "2.41-12+deb13u4", "no DSA", "the point release 13.8",
                     "Jonathan's decision of 23/11", "never an apt-get upgrade, never a free version",
                     "Remove this layer as soon as the base digest carries libc6 and libc-bin +deb13u5 or newer",
                     "in the very PR of Dependabot's bump that brings it",
                     "the build breaks loudly — on purpose"):
            assert said in text, (name, said)


def test_libc1_the_operations_doc_says_the_exception_and_its_removal():
    doc = " ".join((ROOT / "docs" / "operations.md").read_text(encoding="utf-8").split())
    for said in ("LIBC1", "#1098", "CVE-2026-19499", "CVE-2026-5435", "`2.41-12+deb13u5`", "13.8",
                 "retirer la couche de LIBC1 dans la même PR"):
        assert said in doc, said


_BUILT_LIBC1 = [i.strip() for i in os.environ.get("EREGION_LIBC1_IMAGES", "").split(",") if i.strip()]


@pytest.mark.skipif(not _BUILT_LIBC1, reason="EREGION_LIBC1_IMAGES names no image built on this workstation")
@pytest.mark.parametrize("image", _BUILT_LIBC1 or ["-"])
def test_a_built_image_carries_the_fixed_libc(image):
    """Optional, on the workstation only: images already built (never built here), read without network."""
    import shutil
    if not shutil.which("docker"):
        pytest.skip("no docker")
    for package in ("libc6", "libc-bin"):
        res = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "dpkg-query",
                              image, "-W", "-f=${Version}", package], capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, res.stderr
        assert res.stdout == LIBC, (package, res.stdout)
