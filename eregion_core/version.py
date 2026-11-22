"""What this host runs: the reference Imladris deployed, else the checkout's commit, and the package's
version — read once a process.

Born in the console (UI-2, `eregion_console/sections.py`, the version beside the logo), moved here by
DOS2 (#1042): the watch writes it on every cycle's debug line (`glorfindel_version`), and no component
imports another (D1, `scripts/component_check.py`) — the console imports it from here.
"""
from __future__ import annotations

import os
from pathlib import Path


def version() -> dict:
    """What this process runs: the reference Imladris deployed (``EREGION_REF``, ``EREGION_REVISION``,
    passed by deploy.sh at the image's build), else the commit of the checkout it runs from
    (local), and the package's version. ``label`` is what the console's header shows: the tag when one
    was deployed, else the package's version and the short commit."""
    if _version_cache:
        return _version_cache
    from importlib.metadata import PackageNotFoundError, version as pkg_version
    try:
        package = pkg_version("eregion")
    except PackageNotFoundError:
        package = ""
    ref, revision = os.environ.get("EREGION_REF", ""), os.environ.get("EREGION_REVISION", "")
    source = "deployed" if revision else ""
    if not revision:
        revision = checkout_revision()
        source = "checkout" if revision else ""
    if ref and not ref.startswith("v"):
        ref = ""                       # a commit deployed: its short form says it already
    label = ref or (f"v{package}" if package else "") + (f" · {revision[:7]}" if revision else "")
    _version_cache.update(package=package, ref=ref, revision=revision, source=source,
                          label=label.strip(" ·") or "unknown version")
    return _version_cache


_version_cache: dict = {}


def checkout_revision() -> str:
    """The commit of the git checkout this process runs from (a local console or watch), else ''."""
    import subprocess
    root = Path(__file__).resolve().parents[1]
    if not (root / ".git").exists():
        return ""
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
