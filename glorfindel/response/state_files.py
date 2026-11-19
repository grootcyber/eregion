"""The local state's files: written atomically, one per VM, keyed by its name and its resource id
(moved from state.py, SEC-H). Each file records the resource id it belongs to, and a file is used
for a VM only when that id is the VM's: the 8 hex of its key (32 bits) are a name, never a proof.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


def _atomic_write_text(path: Path, text: str, mode: int = 0o600) -> None:
    """Write through a temp file + os.replace.

    A reader (War Room, a concurrent CLI, the watch) never sees a half-written state
    file, and a crash mid-write leaves the previous version intact instead of a
    truncated JSON that would break the next release.

    Readable by its owner only (SEC3, V-27): 0600, its directory made 0700 — the watch,
    the console, the bot and the CLI run as the operator; nothing else reads it. `mode`:
    what is written for others to read (the injectors' heartbeat), its directory 0755.
    """
    path.parent.mkdir(mode=0o755 if mode & 0o044 else 0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape") as f:   # SEC-B: a byte kept, written back
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _vm_ref(ref: str) -> tuple[str, str]:
    """(VM name, resource id) from a short name or a full resource id."""
    if "/" in (ref or ""):
        return ref.rstrip("/").split("/")[-1], ref
    return ref, ""


def _rid_hash(resource_id: str) -> str:
    """8 hex of the id's SHA-1: the key of a state file's name, and of the cards named for a VM.
    32 bits — a name, never an identity: the file says whose it is (`_file_rid`)."""
    return hashlib.sha1(resource_id.rstrip("/").lower().encode()).hexdigest()[:8]


def _rid_key(resource_id: str) -> str:
    """128 bits of the id's SHA-256, lowercase (SEC-H): the key of a state file whose 8-hex name
    another VM's file already holds — two ids that meet on 32 bits never on 128."""
    return hashlib.sha256(resource_id.rstrip("/").lower().encode()).hexdigest()[:32]


def _file_rid(f: Path) -> str:
    """The resource id a state file belongs to ("" if unreadable or not recorded)."""
    try:
        data = json.loads(f.read_text())
    except Exception:
        return ""
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}
    return str((data if isinstance(data, dict) else {}).get("resource_id") or "").rstrip("/").lower()


def _target_file(directory: Path, name: str, rid: str) -> Path:
    """Where this VM's state is written: `<name>--<8 hex>.json`, unless that file records ANOTHER
    resource id — two ids that meet on their 8 hex, a homonym's file (SEC-H): it was read and
    written over as this VM's. Then `<name>--<32 hex>.json`, the id's 128-bit key."""
    short = directory / f"{name.lower()}--{_rid_hash(rid)}.json"
    owner = _file_rid(short)
    if owner and owner != rid.rstrip("/").lower():
        return directory / f"{name.lower()}--{_rid_key(rid)}.json"
    return short


def _hash_variants(directory: Path, rid: str) -> list[Path]:
    """Every `*--<hash>.json` of this resource id — its 8-hex key or its 128-bit one —, whatever
    the case of its name part (the hash itself ignores case), that records this id or none.
    Newest first."""
    if not directory.exists():
        return []
    files = {f for pattern in (f"*--{_rid_hash(rid)}.json", f"*--{_rid_key(rid)}.json")
             for f in directory.glob(pattern) if _file_rid(f) in ("", rid.rstrip("/").lower())}
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def _state_file(directory: Path, ref: str) -> Path | None:
    """The state file of a VM, keyed `<name in lowercase>--<hash of its resource id>.json`.

    Keyed by name only, two VMs with the same name in two resource groups shared one
    file (third review). The name part is lowercase (fourth review, Q9), and a file is
    found by its HASH whatever the case of its name — a mixed-case file of an earlier
    version stayed invisible to lowercase ids (fifth review, C2). A legacy `<name>.json`
    is used only when it belongs to that resource id; by name alone, an ambiguous name
    resolves to nothing. By id, a file is this VM's only when the id it records is (SEC-H):
    found by its name, a homonym's file whose 8 hex met this id's was read as its own."""
    name, rid = _vm_ref(ref)
    legacy = directory / f"{name}.json"
    if rid:
        target = _target_file(directory, name, rid)
        if target.exists() and _file_rid(target) in ("", rid.rstrip("/").lower()):
            return target
        variants = _hash_variants(directory, rid)
        if variants:
            return variants[0]
        if legacy.exists() and _file_rid(legacy) in ("", rid.rstrip("/").lower()):
            return legacy
        return None
    if legacy.exists():
        return legacy
    if not directory.exists():
        return None
    keyed = sorted({f for f in directory.glob("*--*.json")
                    if _file_rid(f).rsplit("/", 1)[-1] == name.lower()})
    return keyed[0] if len(keyed) == 1 else None


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.samefile(b)
    except OSError:
        return False


def _write_state(directory: Path, ref: str, rid: str, payload) -> None:
    """Write under the keyed name, then remove this VM's OTHER files (plain name, other
    cases of the name part). Never one that IS the target: on a case-insensitive file
    system (macOS, Windows, Docker Desktop mounts) `VM-Foo--h.json` and `vm-foo--h.json`
    are the same file — removing the "old" one deleted the state just written (fifth
    review, C1). Never one that records another resource id (SEC-H)."""
    name, ref_rid = _vm_ref(ref)
    rid = rid or ref_rid
    if not rid:
        _atomic_write_text(directory / f"{name}.json", json.dumps(payload))
        return
    target = _target_file(directory, name, rid)
    olds = [old for old in [directory / f"{name}.json", *_hash_variants(directory, rid)]
            if old.name != target.name and old.exists() and not _same_file(old, target)
            and _file_rid(old) in ("", rid.rstrip("/").lower())]
    if olds and not target.exists():
        # Moved first (one atomic rename), then rewritten: a crash between writing the
        # new file and removing the old one left two — a lookup by name read the old
        # one (A0, an older version's state in the invariant machine).
        os.replace(olds.pop(0), target)
    _atomic_write_text(target, json.dumps(payload))
    for old in olds:
        old.unlink()
