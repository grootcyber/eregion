#!/usr/bin/env python3
"""R2BS (#841): stage the pinned control-plane injector tool and its offline provisioning
toolchain into the image build context.

Runs on the operator's workstation WITH network — the only staging step that needs it. The
injector image (annatar/Dockerfile) then carries the result read-only at ``/opt/stratus/``, and
the execution host has no Internet egress. The binary is never committed to the repository.

Everything is verified against ``annatar/stratus/PIN`` before it is laid out:
  - the injector binary: the archive's sha256, then the extracted binary's sha256;
  - the provisioning tool (Terraform 1.3.10): the zip's sha256; the extracted binary's sha256 is
    recorded beside it so the runner can re-check it before every run (SEC5);
  - the provider plugins a technique's ``required_providers`` pins: each zip's sha256, then laid
    out in Terraform's packed filesystem-mirror layout so ``terraform init`` installs from disk.
"""
from __future__ import annotations

import hashlib
import io
import re
import tarfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parent.parent
PIN = REPO / "annatar" / "stratus" / "PIN"
STAGED = REPO / "annatar" / "stratus" / "staged"

STRATUS_VERSION = "v2.38.0"
TERRAFORM_VERSION = "1.3.10"
# The providers azure.persistence.backdoor-managed-identity-fic's main.tf pins at v2.38.0
# (hashicorp/<type> @ <version>); their zip sha256 are in PIN.
PROVIDERS = {"azurerm": "4.81.0", "azuread": "2.53.1"}

_PIN_LINE = re.compile(r"^#\s+([0-9a-f]{64})\s+(\S+)\s*$")


def pinned_checksums(pin_path: Path = PIN) -> dict[str, str]:
    """``{filename: sha256}`` from the PIN's checksum lines (``#  <sha256>  <filename>``)."""
    out: dict[str, str] = {}
    for line in pin_path.read_text(encoding="utf-8").splitlines():
        m = _PIN_LINE.match(line)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def verify(data: bytes, want: str, label: str) -> None:
    """Fail closed: refuse unless the bytes hash to the pinned sha256."""
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise SystemExit(f"{label}: sha256 {got} does not match the pinned {want} — refused")


def _default_fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise SystemExit(f"refusing a non-https download: {url}")
    with urlopen(url, timeout=180) as r:   # noqa: S310 — https-only, checked above
        return r.read()


def stage(dest: Path = STAGED, *, fetch=_default_fetch, pin: Path = PIN) -> None:
    """Download, verify and lay out the staged assets under ``dest`` (what the image copies to
    ``/opt/stratus/``). ``fetch`` (url -> bytes) is injected in the tests; nothing else reaches
    the network."""
    sums = pinned_checksums(pin)

    def need(name: str) -> str:
        if name not in sums:
            raise SystemExit(f"{name}: no sha256 recorded in {pin} — cannot verify, refused")
        return sums[name]

    dest.mkdir(parents=True, exist_ok=True)
    home = dest / "home"
    home.mkdir(exist_ok=True)
    mirror = dest / "plugin-cache"
    mirror.mkdir(exist_ok=True)

    # 1. The injector binary: verify the archive, extract, verify the extracted binary.
    arc = "stratus-red-team_Linux_x86_64.tar.gz"
    archive = fetch(f"https://github.com/DataDog/stratus-red-team/releases/download/"
                    f"{STRATUS_VERSION}/{arc}")
    verify(archive, need(arc), arc)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as t:
        member = t.extractfile("stratus")
        if member is None:
            raise SystemExit("stratus: no 'stratus' file in the archive — refused")
        binary = member.read()
    verify(binary, need("stratus"), "stratus (extracted)")
    (dest / "stratus").write_bytes(binary)
    (dest / "stratus").chmod(0o755)

    # 2. The provisioning tool: verify the zip, extract, record the extracted sha256 beside it.
    tf_zip_name = f"terraform_{TERRAFORM_VERSION}_linux_amd64.zip"
    tf_zip = fetch(f"https://releases.hashicorp.com/terraform/{TERRAFORM_VERSION}/{tf_zip_name}")
    verify(tf_zip, need(tf_zip_name), tf_zip_name)
    with zipfile.ZipFile(io.BytesIO(tf_zip)) as z:
        tf = z.read("terraform")
    (home / "terraform").write_bytes(tf)
    (home / "terraform").chmod(0o755)
    (home / "terraform.sha256").write_text(
        hashlib.sha256(tf).hexdigest() + "  terraform\n", encoding="utf-8")

    # 3. The provider plugins: verify each zip, place it in the packed filesystem-mirror layout.
    for ptype, pver in PROVIDERS.items():
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
    stage()
    print(f"staged into {STAGED} — build the injector image to carry it (make orodruin-push)")
