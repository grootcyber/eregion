"""R2BW (#608): `make stratus-build` (scripts/stratus_build.py) — build the control-plane injector
FROM the vendored submodule (the OFFICIAL DataDog/stratus-red-team at a pinned commit) with our
in-repo patch, instead of downloading the official binary (that was R2BS/R2BV). Hermetic: a fake
submodule (a tiny git tree carrying the version sources), an injected ``build_binary`` and an
injected ``fetch`` — nothing reaches the network and no real ``go build`` runs. Terraform + the
providers stay verified against a PIN fixture before they are laid out (verify + fail-closed, the
R2BS invariants, preserved by this lot).
"""
import hashlib
import importlib.util
import io
import subprocess
import zipfile
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "stratus_build", _REPO / "scripts" / "stratus_build.py")
stratus_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stratus_build)
pinned_checksums = stratus_build.pinned_checksums
verify = stratus_build.verify
build = stratus_build.build
submodule_commit = stratus_build.submodule_commit
terraform_version = stratus_build.terraform_version
required_providers = stratus_build.required_providers


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


_TERRAFORM_GO = 'package runner\n\nconst TerraformVersion = "1.3.10"\n'


def _main_tf(providers: dict[str, str]) -> str:
    """A technique's main.tf with the required_providers the build reads version pins from."""
    blocks = "\n".join(
        f'    {t} = {{\n      source  = "hashicorp/{t}"\n      version = "{v}"\n    }}'
        for t, v in providers.items())
    return "terraform {\n  required_providers {\n" + blocks + "\n  }\n}\n"


def _fake_submodule(tmp_path: Path, *, providers: dict[str, str] | None = None,
                    extra_tf: str | None = None) -> Path:
    """A tiny git repo mirroring the submodule layout: the Terraform version const and one azure
    technique's main.tf. ``extra_tf`` adds a second technique (to exercise divergent pins)."""
    providers = providers or {"azurerm": "4.81.0", "azuread": "2.53.1"}
    sub = tmp_path / "stratus-red-team"
    runner = sub / "v2" / "pkg" / "stratus" / "runner"
    runner.mkdir(parents=True)
    (runner / "terraform.go").write_text(_TERRAFORM_GO, encoding="utf-8")
    tech = sub / "v2" / "internal" / "attacktechniques" / "azure" / "persistence" / "fic"
    tech.mkdir(parents=True)
    (tech / "main.tf").write_text(_main_tf(providers), encoding="utf-8")
    if extra_tf is not None:
        tech2 = sub / "v2" / "internal" / "attacktechniques" / "azure" / "execution" / "run"
        tech2.mkdir(parents=True)
        (tech2 / "main.tf").write_text(extra_tf, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(sub)], check=True)
    subprocess.run(["git", "-C", str(sub), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(sub), "-c", "user.email=t@e", "-c", "user.name=t",
                    "commit", "-q", "-m", "fake"], check=True)
    return sub


def _world(tmp_path):
    """A fake build world: a submodule, the two HashiCorp downloads, an injected ``build_binary``
    that stages a fake binary, and a PIN recording every sha256. Returns
    ``(submodule, pin, fetch, build_binary, want)``."""
    submodule = _fake_submodule(tmp_path)
    binary = b"fake-built-injector\n"
    tf = b"fake-terraform-1.3.10\n"
    tf_zip = _zip({"terraform": tf})
    azurerm = b"fake-azurerm-4.81.0\n"
    azuread = b"fake-azuread-2.53.1\n"
    served = {
        "terraform_1.3.10_linux_amd64.zip": tf_zip,
        "terraform-provider-azurerm_4.81.0_linux_amd64.zip": azurerm,
        "terraform-provider-azuread_2.53.1_linux_amd64.zip": azuread,
    }
    recorded = dict(served)
    recorded["stratus"] = binary   # the built binary's sha is pinned (the reproducibility guard)
    pin = tmp_path / "PIN"
    pin.write_text("".join(f"#   {_sha(d)}  {n}\n" for n, d in recorded.items()), encoding="utf-8")

    def fetch(url: str) -> bytes:
        for name, data in served.items():
            if url.endswith(name):
                return data
        raise AssertionError(f"unexpected url {url}")

    def build_binary(dest: Path) -> str:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "stratus").write_bytes(binary)
        return _sha(binary)

    return submodule, pin, fetch, build_binary, {"binary": binary, "tf": tf}


def test_pinned_checksums_reads_the_pin_lines(tmp_path):
    pin = tmp_path / "PIN"
    pin.write_text("# a comment\n#   " + "a" * 64 + "  file.zip\nnot a checksum line\n",
                   encoding="utf-8")
    assert pinned_checksums(pin) == {"file.zip": "a" * 64}


def test_verify_refuses_a_mismatch():
    verify(b"x", _sha(b"x"), "ok")   # a match raises nothing
    with pytest.raises(SystemExit):
        verify(b"x", _sha(b"y"), "bad")


def test_terraform_version_read_from_submodule(tmp_path):
    submodule = _fake_submodule(tmp_path)
    assert terraform_version(submodule) == "1.3.10"


def test_required_providers_read_from_submodule(tmp_path):
    submodule = _fake_submodule(tmp_path)
    assert required_providers(submodule) == {"azurerm": "4.81.0", "azuread": "2.53.1"}


def test_required_providers_refuses_divergent_pins(tmp_path):
    submodule = _fake_submodule(
        tmp_path, extra_tf=_main_tf({"azurerm": "4.80.0"}))   # a second azurerm version
    with pytest.raises(SystemExit, match="pin one"):
        required_providers(submodule)


def test_submodule_commit_reads_head(tmp_path):
    submodule = _fake_submodule(tmp_path)
    assert len(submodule_commit(submodule)) == 40


def test_docker_build_argv_is_reproducible_and_pinned(tmp_path):
    """R2BX: the default build runs in the pinned golang container (no local Go). The command must
    stay reproducible and pin the toolchain by digest."""
    argv = stratus_build._docker_build_argv(tmp_path / "src")
    assert argv[0] == "docker"
    assert stratus_build.GO_IMAGE in argv
    assert "@sha256:" in stratus_build.GO_IMAGE            # toolchain pinned by digest (M5691)
    assert "-trimpath" in argv                             # reproducible build (M5692)
    assert "CGO_ENABLED=0" in argv                         # static, cross-user reproducible
    assert "--user" in argv                                # built as the operator (temp stays user-owned)


def test_build_lays_out_the_verified_tree(tmp_path):
    submodule, pin, fetch, build_binary, want = _world(tmp_path)
    dest = tmp_path / "staged"
    build(dest, fetch=fetch, build_binary=build_binary, pin=pin, submodule=submodule)
    assert (dest / "stratus").read_bytes() == want["binary"]
    assert (dest / "home" / "terraform").read_bytes() == want["tf"]
    assert (dest / "home" / "terraform.sha256").read_text().split()[0] == _sha(want["tf"])
    mirror = dest / "plugin-cache" / "registry.terraform.io" / "hashicorp"
    assert (mirror / "azurerm" / "terraform-provider-azurerm_4.81.0_linux_amd64.zip").exists()
    assert (mirror / "azuread" / "terraform-provider-azuread_2.53.1_linux_amd64.zip").exists()
    assert "/opt/stratus/plugin-cache" in (dest / "terraformrc").read_text()


def test_build_refuses_a_non_reproducible_binary(tmp_path):
    submodule, pin, fetch, _, _ = _world(tmp_path)

    def wrong(dest: Path) -> str:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "stratus").write_bytes(b"not the pinned bytes")
        return _sha(b"not the pinned bytes")

    with pytest.raises(SystemExit, match="does not match the pinned"):
        build(tmp_path / "staged", fetch=fetch, build_binary=wrong, pin=pin, submodule=submodule)


def test_build_refuses_a_tampered_download(tmp_path):
    submodule, pin, fetch, build_binary, _ = _world(tmp_path)

    def tampered(url: str) -> bytes:
        data = fetch(url)
        return data + b"tampered" if url.endswith("azurerm_4.81.0_linux_amd64.zip") else data

    with pytest.raises(SystemExit, match="does not match"):
        build(tmp_path / "staged", fetch=tampered, build_binary=build_binary, pin=pin,
              submodule=submodule)


def test_build_refuses_when_the_pin_has_no_checksum(tmp_path):
    submodule, _, fetch, build_binary, _ = _world(tmp_path)
    pin = tmp_path / "empty-PIN"
    pin.write_text("# nothing pinned here\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no sha256"):
        build(tmp_path / "staged", fetch=fetch, build_binary=build_binary, pin=pin,
              submodule=submodule)
