"""ENQ5a (#1162): capture, at the bench, the reads of the enquiry's catalogue for one episode — **read
only**, the maintainer's gesture, under his rights — into a file **out of the repository**, in the form
the harness plays (`scripts/harness_enquete.py`, `make llm-compare … ENQUETE=1 CAPTURES=<folder>`).

    python scripts/capture_enquete.py --vm <the VM's resource id> --at <the signal's hour, ISO> \\
        --workspace <the Log Analytics workspace's id> --rule ransomware-disk-write --ttp T1486 \\
        --expect caution --label "the nightly backup's peak" --vault <vault> --vault-rg <its group> \\
        --out "$HOME/eregion-banc/captures/<name>.json"
    make enquete-capture ENQ_VM=… ENQ_AT=… ENQ_WORKSPACE=… ENQ_EXPECT=… ENQ_OUT=…   # the same

**What it reads, and nothing else**: each read of the catalogue (`glorfindel/enquiry/catalog.py`, its
nine) whose values the episode fills, through the loop's own reader (`glorfindel/enquiry/lecteur.py`):
a KQL query on the workspace, its window anchored on `--at` (never `ago()`, never the API's default of
the last hours); the vault's reads by the provider's adapter (`enquiry_reads`: DOS4's, GET and list
only); the VM's system in its model (`vm_os`, the platform's word). No write, no call to the model, no
read the catalogue does not declare. A read that fails is written `null` (the harness plays it as a
failure, never as empty); a read the episode cannot fill is listed apart (`non_lues`), with why.

**No real identifier leaves the bench in the file by default** (`--keep-names` to keep them): the
subscription, the groups, the VM, the vault, the workspace, every GUID and every e-mail address of the
rows are replaced by the harness's names (`vm-smoke`, `vault-smoke`, `sub`, `rg`…) and stable
placeholders; `--hide WORD` hides one more (a host name, a user's). The file never goes in the
repository: an `--out` inside it is refused, and the harness refuses a folder of captures inside it.

**The truth of the bench** is the maintainer's: `--expect` (`contain`, `caution`, `act` with `--allowed`)
says what a good call would have been. `--now-s` is when, after T, the harness replays the decision
(60 s by default: what had been ingested then — `IngereA`, the series' horizon); a later one replays it
after the fact. `--reference FILE` attaches a memory of the object (§5.5), as the harness's cases 1 and 3.

Exit 0 written; 2 refused before any call (an argument, an `--out` in the repository or already there).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from glorfindel import kql  # noqa: E402
from glorfindel.enquiry import catalog, lecteur as lecteur_, loop  # noqa: E402

FORMAT = "eregion-enquete-capture/1"
EXPECTS = ("contain", "caution", "act")
_GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_MAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")


class Refus(ValueError):
    """Refused before any call."""


def hors_du_depot(out: str) -> Path:
    """`out` resolved, outside the repository and not there yet; its folder made 0700 if it is not."""
    path = Path(out).expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise Refus(f"{path} : une capture ne va jamais dans le dépôt (--out hors de {ROOT})")
    if path.exists():
        raise Refus(f"{path} : existe déjà, rien n'est écrasé")
    return path


class Pseudonymes:
    """The bench's names replaced by the harness's: the exact ones (longest first, whatever their case),
    then every GUID and e-mail address left, each by a stable placeholder of its own."""

    def __init__(self, noms: dict[str, str]):
        self.noms = sorted(((k, v) for k, v in noms.items() if k), key=lambda kv: -len(kv[0]))
        self.vus: dict[str, str] = {}

    def _stable(self, kind: str, value: str) -> str:
        key = value.lower()
        if key not in self.vus:
            n = sum(1 for k in self.vus.values() if k.startswith(kind)) + 1
            self.vus[key] = (f"00000000-0000-0000-0000-{n:012d}" if kind == "guid"
                             else f"user-{n}@example.invalid")
        return self.vus[key]

    def texte(self, text: str) -> str:
        for real, fake in self.noms:                     # a whole name, never a piece of a longer word
            text = re.sub(rf"(?<![\w-]){re.escape(real)}(?![\w-])", fake, text, flags=re.IGNORECASE)
        text = _GUID.sub(lambda m: m.group(0) if m.group(0).startswith("00000000-0000-0000-0000-")
                         else self._stable("guid", m.group(0)), text)
        return _MAIL.sub(lambda m: m.group(0) if m.group(0).endswith("@example.invalid")
                         else self._stable("mail", m.group(0)), text)

    def __call__(self, value):
        if isinstance(value, str):
            return self.texte(value)
        if isinstance(value, dict):
            return {self(k) if isinstance(k, str) else k: self(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self(v) for v in value]
        return value


def _plain(value):
    """A value as JSON writes it: an SDK's datetime as ISO, the rest as it is."""
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _entree(lu):
    """A read's answer as the harness plays it: its rows; `{"lignes", "ingere_jusqu_a"}` when it says how
    far its source ingested; None when it failed."""
    if isinstance(lu, catalog.Lu):
        return {"lignes": _plain(lu.rows), "ingere_jusqu_a": lu.ingere.isoformat() if lu.ingere else None}
    return None if lu is None else _plain(lu)


def _noms(vm: str, vault: str, vault_rg: str, workspace: str, hide) -> dict[str, str]:
    parts = vm.split("/")
    noms = {parts[2]: "sub", parts[4]: "rg", parts[-1]: "vm-smoke", workspace: "workspace"}
    if vault:
        noms[vault] = "vault-smoke"
    if vault_rg:
        noms[vault_rg] = "rg"
    for i, word in enumerate(hide or (), 1):
        noms[word] = f"hidden-{i}"
    return noms


def capturer(*, vm: str, at: datetime, row: dict, kql_run, arm, vault: str = "", vault_rg: str = "",
             now=None) -> dict:
    """The episode's reads, as `{"systeme", "lectures", "non_lues", "requetes"}`: each read of the catalogue
    the episode fills, run by the loop's reader anchored on `at`. `kql_run(query, timespan)` runs one
    query; `arm` is the provider's connector (`enquiry_reads`, `vm_os`). No call but these."""
    try:
        systeme = str(arm.vm_os(vm) or "").lower() if arm is not None else ""
    except Exception:
        systeme = ""
    systeme = systeme if systeme in catalog.SYSTEMS else ""
    coffre = ""
    if vault:
        coffre = (f"/subscriptions/{vm.split('/')[2]}/resourceGroups/{vault_rg or vm.split('/')[4]}"
                  f"/providers/Microsoft.RecoveryServices/vaults/{vault}")
    lire = lecteur_.Lecteur(at, kql=kql_run, arm=arm, now=now)
    lectures, non_lues = {}, {}
    for read in catalog.READS.values():
        vals = loop.valeurs(read, vm, row, coffre)
        if isinstance(vals, str):
            non_lues[read.id] = vals
            continue
        lectures[read.id] = _entree(lire(read, vals))
    return {"systeme": systeme, "lectures": lectures, "non_lues": non_lues, "requetes": len(lire.faites)}


def _args(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--vm", required=True, help="the VM's resource id (the registry's, as the card names it)")
    ap.add_argument("--at", required=True, help="the signal's hour T, ISO (the cycle's timestamp)")
    ap.add_argument("--workspace", required=True, help="the Log Analytics workspace's id")
    ap.add_argument("--rule", required=True, help="the rule that fired (ransomware-disk-write)")
    ap.add_argument("--ttp", required=True, help="its technique (T1486)")
    ap.add_argument("--expect", required=True, choices=EXPECTS, help="the good call, the bench's truth")
    ap.add_argument("--allowed", default="", help="with --expect act: the actions allowed, comma-separated")
    ap.add_argument("--label", default="", help="what the episode is, in a few words (no real name)")
    ap.add_argument("--vault", default="", help="the Recovery Services vault's name (none: its reads refused)")
    ap.add_argument("--vault-rg", default="", help="its resource group (default: the VM's)")
    ap.add_argument("--row", default="", help="the detected row, as JSON (default: {\"Computer\": <the VM>})")
    ap.add_argument("--now-s", type=int, default=60, help="when, after T, the harness replays the decision")
    ap.add_argument("--reference", default="", help="a JSON file: the memory of the object (§5.5), attached")
    ap.add_argument("--hide", action="append", default=[], help="one more word to hide (repeatable)")
    ap.add_argument("--keep-names", action="store_true", help="keep the bench's names (never in the repository)")
    ap.add_argument("--out", required=True, help="the file written, out of the repository")
    return ap.parse_args(argv)


def preparer(args) -> dict:
    """Every check before any call: the VM, the hour, the row, the reference, the --out. Raises Refus."""
    try:
        vm = kql.resource_id(args.vm)
    except kql.UnsafeValue as exc:
        raise Refus(f"--vm : {exc}") from None
    at = catalog._when(args.at)
    if at is None:
        raise Refus("--at : une heure ISO (2026-11-10T02:34:10Z)")
    try:
        row = json.loads(args.row) if args.row else {"Computer": vm.split("/")[-1], "_ResourceId": vm}
        reference = json.loads(Path(args.reference).expanduser().read_text(encoding="utf-8")) if args.reference else None
    except (OSError, ValueError) as exc:
        raise Refus(f"--row ou --reference illisible ({type(exc).__name__})") from None
    if not isinstance(row, dict):
        raise Refus("--row : un objet JSON")
    allowed = [a.strip() for a in args.allowed.split(",") if a.strip()]
    if args.expect == "act" and not allowed:
        raise Refus("--expect act : --allowed (les actions permises)")
    return {"vm": vm, "at": at, "row": row, "reference": reference, "allowed": allowed,
            "out": hors_du_depot(args.out)}


def ecrire(args, prep: dict, lu: dict, now: datetime) -> Path:
    """The capture, pseudonymised unless --keep-names, written 0600 in a folder 0700."""
    cache = (lambda v: v) if args.keep_names else Pseudonymes(
        _noms(prep["vm"], args.vault, args.vault_rg, args.workspace, args.hide))
    doc = {"format": FORMAT, "label": args.label, "expect": args.expect, "ttp": args.ttp, "regle": args.rule,
           "systeme": lu["systeme"], "at": prep["at"].isoformat(), "now_s": args.now_s,
           "row": cache(_plain(prep["row"])), "lectures": cache(lu["lectures"]), "non_lues": lu["non_lues"],
           "capture": {"lu_a": now.isoformat(), "requetes": lu["requetes"], "pseudonymise": not args.keep_names}}
    if prep["allowed"]:
        doc["allowed"] = prep["allowed"]
    if prep["reference"] is not None:
        doc["reference"] = cache(prep["reference"])
    out = prep["out"]
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    return out


def _azure(workspace: str):
    """The bench's readers, read only: the workspace's queries, the provider's adapter."""
    from glorfindel.detectors import detector_for
    from glorfindel.providers.azure.connector import AzureConnector
    det = detector_for("azure_monitor", workspace_id=workspace)
    return (lambda query, span: det.run_query(query, timespan=span)), AzureConnector(dry_run=False, read_only=True)


def main(argv=None, *, readers=None) -> int:
    args = _args(argv)
    try:
        prep = preparer(args)
    except Refus as exc:
        print(f"Refusé, rien n'est lu : {exc}")
        return 2
    kql_run, arm = (readers or _azure)(args.workspace)
    now = datetime.now(timezone.utc)
    lu = capturer(vm=prep["vm"], at=prep["at"], row=prep["row"], kql_run=kql_run, arm=arm, vault=args.vault,
                  vault_rg=args.vault_rg, now=lambda: now)
    out = ecrire(args, prep, lu, now)
    etats = ", ".join(f"{k}: {'échec' if v is None else 'lu'}" for k, v in lu["lectures"].items())
    print(f"Capture écrite : {out} ({lu['requetes']} lecture(s) ; système : {lu['systeme'] or 'inconnu'})")
    print(f"  {etats}")
    if lu["non_lues"]:
        print("  non lues : " + "; ".join(f"{k} ({v})" for k, v in lu["non_lues"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
