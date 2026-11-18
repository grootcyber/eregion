#!/usr/bin/env python3
"""image_cves — no release publishes a package its distribution has already fixed (SEC-G, audit of
13/11, P-06).

  python3 scripts/image_cves.py install DEST
        grype, from its release archive kept only if its sha256 is the pinned one: the binary alone
        taken out of it, written to DEST
  python3 scripts/image_cves.py scan IMAGE --grype PATH [--json OUT]
        grype on the local image IMAGE (docker:IMAGE), its database already fetched (`grype db update`,
        in a step of its own), never updated during the scan; then `judge`
  python3 scripts/image_cves.py judge REPORT.json [--image NAME]
        exit 1 when the report holds a vulnerability rated High or Critical, fixed upstream (a fixed
        version published), in a package of the operating system (deb, rpm, apk); each one said,
        and in $GITHUB_STEP_SUMMARY when it is set. Exit 2 when the report does not read — no
        matches list, or no distribution seen: a scan that saw no system package proves nothing.

Why the system's packages only: the Python dependencies come from the lock (requirements/*.txt, with
their hashes) and are audited on every push and pull request (pip-audit.yml); a package of the base
image comes from python:3.12-slim, pinned by its digest in both Dockerfiles — nothing refreshed it but
a bump of that digest, which Dependabot now proposes every week (.github/dependabot.yml). The release
gate (.github/workflows/release-gate.yml, its job « image CVEs ») builds both images from the tree it
publishes and runs this: a release whose base image carries a High or Critical CVE fixed upstream is
held until the digest moves. A CVE without a fix is said, never a refusal: there is nothing to take.

grype, not trivy: the publication already trusts anchore's syft, pinned the same way
(scripts/published_image.py, SYFT_*). Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

GRYPE_VERSION = "v0.121.1"
GRYPE_SHA256 = "bc3ea3f9e6fd56ac781c08c6c5e614271b79f438200757f6932085c19b0a4657"   # grype_0.121.1_linux_amd64.tar.gz
GRYPE_URL = (f"https://github.com/anchore/grype/releases/download/{GRYPE_VERSION}/"
             f"grype_{GRYPE_VERSION[1:]}_linux_amd64.tar.gz")
GRYPE_MAX = 150 * 1024 * 1024
# What refuses: a severity among these, a fix published, a package of the operating system.
REFUSED_SEVERITIES = frozenset({"High", "Critical"})
OS_TYPES = frozenset({"deb", "rpm", "apk"})
SAID = 20     # vulnerabilities named; the others counted


class Unreadable(Exception):
    """The report proves nothing."""


def install(dest: Path, url: str = GRYPE_URL) -> int:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "eregion-image-cves"})
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read(GRYPE_MAX + 1)
    except Exception as e:  # noqa: BLE001 — the network: retry.sh tries again
        print(f"✗ grype : {type(e).__name__}", file=sys.stderr)
        return 3
    got = hashlib.sha256(body).hexdigest()
    if len(body) > GRYPE_MAX or got != GRYPE_SHA256:
        print(f"✗ grype téléchargé : sha256 {got[:12]}…, pas {GRYPE_SHA256[:12]}… — rien n'est installé",
              file=sys.stderr)
        return 1
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.name == "grype" and m.isfile()), None)
        if member is None:
            print("✗ grype : pas de binaire « grype » dans l'archive — rien n'est installé", file=sys.stderr)
            return 1
        binary = tar.extractfile(member).read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(binary)
    tmp.chmod(0o755)
    os.replace(tmp, dest)
    print(f"✓ {dest} : grype {GRYPE_VERSION}, archive au sha256 vérifié")
    return 0


def refused(report: dict) -> tuple[list[dict], int, str]:
    """(the vulnerabilities that refuse, how many others were seen, the distribution) — Unreadable
    when the report is not one: no list of matches, no distribution."""
    if not isinstance(report, dict) or not isinstance(report.get("matches"), list):
        raise Unreadable("pas de liste « matches » : ce n'est pas un rapport de grype")
    distro = report.get("distro") if isinstance(report.get("distro"), dict) else {}
    name = str(distro.get("name") or "").strip()
    if not name:
        raise Unreadable("aucune distribution vue dans l'image : ses paquets système n'ont pas été lus")
    out, others, seen = [], 0, set()
    for m in report["matches"]:
        vuln = m.get("vulnerability") if isinstance(m, dict) else None
        art = m.get("artifact") if isinstance(m, dict) else None
        if not isinstance(vuln, dict) or not isinstance(art, dict):
            raise Unreadable("une correspondance sans vulnérabilité ni paquet")
        fix = vuln.get("fix") if isinstance(vuln.get("fix"), dict) else {}
        versions = [str(v) for v in fix.get("versions") or [] if v]
        key = (str(vuln.get("id")), str(art.get("name")), str(art.get("version")))
        if (vuln.get("severity") in REFUSED_SEVERITIES and fix.get("state") == "fixed" and versions
                and art.get("type") in OS_TYPES):
            if key not in seen:
                seen.add(key)
                out.append({"id": key[0], "severity": vuln["severity"], "package": key[1], "version": key[2],
                            "fixed": ", ".join(versions)})
        else:
            others += 1
    return out, others, f"{name} {distro.get('version') or ''}".strip()


def judge(report_path: Path, image: str = "") -> int:
    label = image or report_path.name
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        bad, others, distro = refused(report)
    except (OSError, ValueError) as e:
        print(f"✗ {label} : le rapport ne se lit pas ({type(e).__name__}) — la porte ne passe pas", file=sys.stderr)
        return 2
    except Unreadable as e:
        print(f"✗ {label} : {e} — la porte ne passe pas", file=sys.stderr)
        return 2
    lines = [f"### {label} ({distro})", ""]
    if bad:
        lines += ["| CVE | Sévérité | Paquet | Version | Corrigé en |", "|---|---|---|---|---|"]
        lines += [f"| {b['id']} | {b['severity']} | {b['package']} | {b['version']} | {b['fixed']} |"
                  for b in bad[:SAID]]
        if len(bad) > SAID:
            lines.append(f"| … et {len(bad) - SAID} de plus | | | | |")
        lines += ["", f"**{len(bad)} vulnérabilité(s) élevée(s) ou critique(s) corrigée(s) en amont dans les paquets "
                  "du système : la porte est rouge.** Monter l'empreinte de l'image de base (la PR de Dependabot, "
                  "ou `docker buildx imagetools inspect python:3.12-slim`, les deux Dockerfile)."]
    else:
        lines.append("Aucune vulnérabilité élevée ou critique corrigée en amont dans les paquets du système.")
    lines.append(f"({others} autre(s) correspondance(s) : sans correctif, moins graves, ou hors des paquets système — "
                 "dites ici, jamais un refus.)")
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n\n")
    return 1 if bad else 0


def scan(image: str, grype: Path, out: Path) -> int:
    env = {**os.environ, "GRYPE_DB_AUTO_UPDATE": "false", "GRYPE_CHECK_FOR_APP_UPDATE": "false"}
    res = subprocess.run([str(grype), f"docker:{image}", "-o", "json", "--file", str(out)], env=env,
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(f"✗ grype sur {image} : code {res.returncode}\n{(res.stderr or '')[-1500:]}", file=sys.stderr)
        return 2
    return judge(out, image)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="image_cves.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("install")
    p.add_argument("dest", type=Path)
    p = sub.add_parser("scan")
    p.add_argument("image")
    p.add_argument("--grype", type=Path, required=True)
    p.add_argument("--json", type=Path)
    p = sub.add_parser("judge")
    p.add_argument("report", type=Path)
    p.add_argument("--image", default="")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        return install(a.dest)
    if a.cmd == "scan":
        return scan(a.image, a.grype, a.json or Path(f"cves-{a.image.replace('/', '-').replace(':', '-')}.json"))
    return judge(a.report, a.image)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
