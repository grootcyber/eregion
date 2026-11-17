#!/usr/bin/env python3
"""R2BW (#608): build the control-plane injector FROM the vendored submodule (the OFFICIAL
DataDog/stratus-red-team at a pinned commit) with our in-repo patch applied, instead of
downloading the official binary (that was R2BS/R2BV, scripts/stratus_stage.py — replaced).

Runs on the operator's workstation WITH network (go mod + HashiCorp) — the only step that needs it.
Provenance of the binary: the pinned submodule commit + our patch (annatar/stratus/patches/) + a
reproducible build (Go pinned, -trimpath, CGO off) -> the sha256 recorded in PIN and verified here;
re-checked before EVERY phase by the adapter (annatar/engines/stratus.py, SEC5, unchanged). Anyone
can verify by rebuilding the pinned commit + the patch -> same sha. Terraform + the azurerm/azuread
providers stay OFFICIAL HashiCorp downloads, verified against PIN, their versions READ from the
submodule source (single source of truth).

Nothing is committed: the staged result (annatar/stratus/staged/) is gitignored; the image copies
it (make orodruin-push). The submodule is a BUILD INPUT only, excluded from the image (.dockerignore).
The subprocess runner and the downloader are injected, so the tests drive a fake submodule + fake
downloads with no network and no real `go build`."""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parent.parent
SUBMODULE = REPO / "annatar" / "stratus" / "stratus-red-team"
PATCH = REPO / "annatar" / "stratus" / "patches" / "bastion-sku.patch"
PIN = REPO / "annatar" / "stratus" / "PIN"
STAGED = REPO / "annatar" / "stratus" / "staged"
GO = os.environ.get("EREGION_GO")   # défini → ce binaire go LOCAL (doit être go1.26.11) ; sinon le conteneur épinglé
# La toolchain de build reproductible : go1.26.11, épinglée PAR DIGEST (l'image avec laquelle le banc
# a construit 834976c9…). Pas besoin de Go local ; `make stratus-build` tourne dans ce conteneur.
GO_IMAGE = "golang:1.26@sha256:4165ee6bf3b7811fd7b40373290405c83d0167dcb87ee5f29c427cdcef45ff8f"

_PIN_LINE = re.compile(r"^#\s+([0-9a-f]{64})\s+(\S+)\s*$")
_TF_VER = re.compile(r'TerraformVersion\s*=\s*"([^"]+)"')
_PROVIDER = re.compile(
    r'(\w+)\s*=\s*\{\s*source\s*=\s*"hashicorp/\w+"\s*version\s*=\s*"([^"]+)"', re.S)


def pinned_checksums(pin: Path = PIN) -> dict[str, str]:
    """``{filename: sha256}`` from the PIN's checksum lines (``#  <sha256>  <name>``)."""
    out: dict[str, str] = {}
    for line in pin.read_text(encoding="utf-8").splitlines():
        m = _PIN_LINE.match(line)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def verify(data: bytes, want: str, label: str) -> None:
    """Fail closed: refuse unless the bytes hash to the pinned sha256."""
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise SystemExit(f"{label}: sha256 {got} does not match the pinned {want} — refused")


def submodule_commit(submodule: Path = SUBMODULE) -> str:
    return subprocess.run(
        ["git", "-C", str(submodule), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True).stdout.strip()


def terraform_version(submodule: Path = SUBMODULE) -> str:
    """The Go const TerraformVersion, read from the submodule (single source of truth)."""
    src = (submodule / "v2" / "pkg" / "stratus" / "runner" / "terraform.go").read_text(encoding="utf-8")
    m = _TF_VER.search(src)
    if not m:
        raise SystemExit("TerraformVersion not found in the submodule — refused")
    return m.group(1)


def required_providers(submodule: Path = SUBMODULE) -> dict[str, str]:
    """``hashicorp/<type> @ <version>`` pinned by the azure techniques' required_providers."""
    out: dict[str, str] = {}
    base = submodule / "v2" / "internal" / "attacktechniques" / "azure"
    for tf in sorted(base.glob("**/main.tf")):
        for ptype, pver in _PROVIDER.findall(tf.read_text(encoding="utf-8")):
            prev = out.get(ptype)
            if prev is not None and prev != pver:
                raise SystemExit(
                    f"provider hashicorp/{ptype}: two versions in the techniques "
                    f"({prev} and {pver}) — pin one; refused")
            out[ptype] = pver
    return out


def _docker_build_argv(src: Path) -> list[str]:
    """The reproducible container build command: go1.26.11 pinned by digest (GO_IMAGE), run AS the
    operator (``--user`` so the temp source stays user-owned and cleans up), CGO off + ``-trimpath``
    (user/path independent) → the pinned sha. GOCACHE/GOPATH/HOME land inside the mount, writable."""
    uid, gid = os.getuid(), os.getgid()
    return [
        "docker", "run", "--rm",
        "-v", f"{src}:/src", "-w", "/src/v2",
        "-e", "CGO_ENABLED=0", "-e", "HOME=/src",
        "-e", "GOCACHE=/src/.gocache", "-e", "GOPATH=/src/.gopath",
        "--user", f"{uid}:{gid}", GO_IMAGE,
        "go", "build", "-trimpath", "-ldflags=-w -s", "-o", "/src/stratus", "./cmd/stratus",
    ]


def _default_build(dest: Path, submodule: Path = SUBMODULE, patch: Path = PATCH) -> str:
    """Copy the submodule source (sans its gitlink), apply our patch, build reproducibly, stage the
    binary, return its sha256. The submodule stays pristine (= the official source). The build runs
    in the pinned ``golang`` container by default (no local Go needed) ; ``EREGION_GO`` forces a
    local go binary instead (which must be go1.26.11 to reproduce the pinned sha)."""
    dest.mkdir(parents=True, exist_ok=True)
    binary = dest / "stratus"
    with tempfile.TemporaryDirectory(prefix="stratus-src-") as tmp:
        src = Path(tmp) / "stratus-red-team"
        shutil.copytree(submodule, src, ignore=shutil.ignore_patterns(".git"))
        subprocess.run(["git", "apply", str(patch)], cwd=str(src), check=True)
        if GO:
            subprocess.run(
                [GO, "build", "-trimpath", "-ldflags=-w -s", "-o", str(binary), "./cmd/stratus"],
                cwd=str(src / "v2"), check=True, env={**os.environ, "CGO_ENABLED": "0"})
        else:
            subprocess.run(_docker_build_argv(src), check=True)
            shutil.copy2(src / "stratus", binary)
    binary.chmod(0o755)
    return hashlib.sha256(binary.read_bytes()).hexdigest()


def _default_fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise SystemExit(f"refusing a non-https download: {url}")
    with urlopen(url, timeout=180) as r:   # noqa: S310 — https-only, checked above
        return r.read()


def build(dest: Path = STAGED, *, fetch=_default_fetch, build_binary=_default_build,
          pin: Path = PIN, submodule: Path = SUBMODULE) -> None:
    """Build the pinned+patched binary, stage it + the official Terraform/providers (versions read
    from the submodule). ``fetch``/``build_binary`` are injected in the tests; nothing else reaches
    the network and no real ``go build`` runs there."""
    sums = pinned_checksums(pin)
    commit = submodule_commit(submodule)

    def need(name: str) -> str:
        if name not in sums:
            raise SystemExit(f"{name}: no sha256 recorded in {pin} — cannot verify, refused")
        return sums[name]

    # 1. The binary: BUILT from the submodule + our patch; its sha verified against PIN (repro guard).
    sha = build_binary(dest)
    want = sums.get("stratus")
    if want and sha != want:
        raise SystemExit(
            f"the built binary sha256 {sha} does not match the pinned {want} — a non-reproducible "
            f"build or a changed submodule/patch (submodule @ {commit}); refused")
    if not want:
        print(f"PIN has no 'stratus' sha yet — record it: {sha}  stratus  (submodule @ {commit})")

    home = dest / "home"
    home.mkdir(parents=True, exist_ok=True)
    mirror = dest / "plugin-cache"
    mirror.mkdir(parents=True, exist_ok=True)

    # 2. Terraform (version from the submodule), official HashiCorp, verified against PIN.
    tf_ver = terraform_version(submodule)
    tf_name = f"terraform_{tf_ver}_linux_amd64.zip"
    tf_zip = fetch(f"https://releases.hashicorp.com/terraform/{tf_ver}/{tf_name}")
    verify(tf_zip, need(tf_name), tf_name)
    with zipfile.ZipFile(io.BytesIO(tf_zip)) as z:
        tf = z.read("terraform")
    (home / "terraform").write_bytes(tf)
    (home / "terraform").chmod(0o755)
    (home / "terraform.sha256").write_text(
        hashlib.sha256(tf).hexdigest() + "  terraform\n", encoding="utf-8")

    # 3. The providers (versions from the submodule), official HashiCorp, verified against PIN.
    for ptype, pver in required_providers(submodule).items():
        name = f"terraform-provider-{ptype}_{pver}_linux_amd64.zip"
        plugin = fetch(f"https://releases.hashicorp.com/terraform-provider-{ptype}/{pver}/{name}")
        verify(plugin, need(name), name)
        pdir = mirror / "registry.terraform.io" / "hashicorp" / ptype
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / name).write_bytes(plugin)

    # 4. The Terraform CLI config: install providers from the mirror, never the registry.
    (dest / "terraformrc").write_text(
        'provider_installation {\n'
        '  filesystem_mirror {\n'
        '    path = "/opt/stratus/plugin-cache"\n'
        '  }\n'
        '  direct {\n'
        '    exclude = ["*/*"]\n'
        '  }\n'
        '}\n', encoding="utf-8")


if __name__ == "__main__":
    build()
    print(f"staged into {STAGED} — build the injector image to carry it (make orodruin-push)")
