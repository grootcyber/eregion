"""R2bs (#841): `make stratus-stage` (scripts/stratus_stage.py) — the download+verify+layout
logic, hermetic. An injected ``fetch`` serves the archives; nothing reaches the network. Every
download is verified against a PIN fixture before it is laid out.
"""
import hashlib
import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "stratus_stage", _REPO / "scripts" / "stratus_stage.py")
stratus_stage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stratus_stage)
pinned_checksums = stratus_stage.pinned_checksums
stage = stratus_stage.stage
verify = stratus_stage.verify


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _targz(members: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _zip(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def _world(tmp_path):
    """A fake release world: the four downloads, a PIN recording their sha256, and a ``fetch``
    serving them by url. Returns ``(pin_path, fetch, want)``."""
    binary = b"fake-injector-binary\n"
    archive = _targz({"stratus": binary, "LICENSE": b"apache-2.0\n"})
    tf = b"fake-terraform-1.3.10\n"
    tf_zip = _zip({"terraform": tf})
    # Provider zips are placed whole (never unzipped by the stager), so any bytes do.
    azurerm = b"fake-azurerm-4.81.0\n"
    azuread = b"fake-azuread-2.53.1\n"
    served = {
        "stratus-red-team_Linux_x86_64.tar.gz": archive,
        "terraform_1.3.10_linux_amd64.zip": tf_zip,
        "terraform-provider-azurerm_4.81.0_linux_amd64.zip": azurerm,
        "terraform-provider-azuread_2.53.1_linux_amd64.zip": azuread,
    }
    recorded = dict(served)
    recorded["stratus"] = binary   # the extracted binary is pinned too
    pin = tmp_path / "PIN"
    pin.write_text("".join(f"#   {_sha(d)}  {n}\n" for n, d in recorded.items()), encoding="utf-8")

    def fetch(url: str) -> bytes:
        for name, data in served.items():
            if url.endswith(name):
                return data
        raise AssertionError(f"unexpected url {url}")

    return pin, fetch, {"binary": binary, "tf": tf}


def test_pinned_checksums_reads_the_pin_lines(tmp_path):
    pin = tmp_path / "PIN"
    pin.write_text("# a comment\n#   " + "a" * 64 + "  file.zip\nnot a checksum line\n",
                   encoding="utf-8")
    assert pinned_checksums(pin) == {"file.zip": "a" * 64}


def test_verify_refuses_a_mismatch():
    verify(b"x", _sha(b"x"), "ok")   # a match raises nothing
    with pytest.raises(SystemExit):
        verify(b"x", _sha(b"y"), "bad")


def test_stage_lays_out_the_verified_tree(tmp_path):
    pin, fetch, want = _world(tmp_path)
    dest = tmp_path / "staged"
    stage(dest, fetch=fetch, pin=pin)
    assert (dest / "stratus").read_bytes() == want["binary"]
    assert (dest / "home" / "terraform").read_bytes() == want["tf"]
    assert (dest / "home" / "terraform.sha256").read_text().split()[0] == _sha(want["tf"])
    mirror = dest / "plugin-cache" / "registry.terraform.io" / "hashicorp"
    assert (mirror / "azurerm" / "terraform-provider-azurerm_4.81.0_linux_amd64.zip").exists()
    assert (mirror / "azuread" / "terraform-provider-azuread_2.53.1_linux_amd64.zip").exists()
    assert "/opt/stratus/plugin-cache" in (dest / "terraformrc").read_text()


def test_stage_refuses_a_tampered_download(tmp_path):
    pin, fetch, _ = _world(tmp_path)

    def tampered(url: str) -> bytes:
        data = fetch(url)
        return data + b"tampered" if url.endswith(".tar.gz") else data

    with pytest.raises(SystemExit, match="does not match"):
        stage(tmp_path / "staged", fetch=tampered, pin=pin)


def test_stage_refuses_when_the_pin_has_no_checksum(tmp_path):
    pin, fetch, _ = _world(tmp_path)
    pin.write_text("# nothing pinned here\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no sha256"):
        stage(tmp_path / "staged", fetch=fetch, pin=pin)
