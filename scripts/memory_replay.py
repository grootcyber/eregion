"""MEM1 (#1016): the memory of decisions replayed on a copy of a real store — its ranking by distance
against a ranking by date, signal by signal. Offline, and aggregated numbers only.

    d=$(mktemp -d) && tar xzf ~/.eregion/host-backups/glorfindel-<date>.tgz -C "$d" .glorfindel/cycles
    python scripts/memory_replay.py "$d/.glorfindel/cycles"

The copy is one that `make imladris-pull` brought back (its tar of Imladris's ~/.glorfindel, in
~/.eregion/host-backups/), extracted in a folder of its own. Chroma may write in what it opens (its
sqlite, its log): a copy, never the original.

**Refused** (exit 2, said on stderr). Before anything is opened: a path in the operator's
~/.glorfindel, ~/.eregion or ~/.annatar — under the home the system gives him and under HOME, as given
and resolved (eregion_core/store_guard.py's rule, here in any session: the store of a running watch is
never opened by this script); a folder one of whose files or folders leads there through a link (the
copy's chroma.sqlite3 linked to the original, its segments' folder too: walked, links not followed); a
folder that is not a store (no chroma.sqlite3: none is made); Chroma's model not on the disk. After the
copy is opened by Chroma's client: a store without the `cycles` collection.

**Offline**: the embedded Chroma client, its telemetry off (`ANONYMIZED_TELEMETRY=False` and
`Settings(anonymized_telemetry=False)`), `HF_HUB_OFFLINE=1`, and Chroma's own ONNX model
(all-MiniLM-L6-v2, ~/.cache/chroma), used only when its files are there — never fetched here
(`python scripts/chroma_model.py` fetches it, on the network, as the CI does: CI8). No cloud, no
model of language.

**The replay.** The cycles in the order they were stored (`stored_at`; one stored before cycles were
dated takes the B2 floor, as `glorfindel/memory.py` dates it, `_stored_at`). For each real cycle, the
memory holds the real cycles stored before it, within the age bound (90 days, `memory.max_age_days`'s
default): its signal is the cycle's own — its technique, severity, resource type, event, provider
« azure » (what the RulePoller writes, glorfindel/detection_rules.py), rule and VM. Four rankings,
each with the code's keys and bounds (`CycleMemory.retrieve_similar`): the same rule first, then the
same VM, then

- ``distance``: the cosine distance between the signal's text (`memory._signal_to_text`) and the
  cycle's stored embedding — what the code does;
- ``date``: the newest first;
- ``ttp_then_date``: the same technique first, then the newest;
- ``ttp_then_distance``: the same technique first, then the distance;

the copies of one cycle folded (signal_id, action, run_id), at most `memory.PER_VM` per VM, three
precedents. What it compares: the sets and the first precedent the rankings give, two by two
(`PAIRS`), and the share of the precedents given that bear the signal's technique.

**What it prints**: one JSON object of aggregated numbers — never a VM, an identifier, a run or a
text of a cycle. A rule's name is printed when it is a shipped rule's (public), else « (other) »; a
technique when it reads as an ATT&CK id, else « (other) ».

**Its limits**, said in docs/design/memoire.md: the pool Chroma bounds (`n * _DUPLICATE_SLACK` per
search) is replaced by every eligible cycle, and HNSW's approximate search by the exact distance; the
provider is taken as « azure »; the cycles stored before SEC-I carry neither rule nor VM, and the
order of the undated ones among themselves is the store's.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from eregion_core import store_guard  # noqa: E402
from glorfindel import memory  # noqa: E402

N = 3
COLLECTION = "cycles"
# The files of Chroma's ONNX model (chromadb 1.5.9, ONNXMiniLM_L6_V2._download_model_if_not_exists):
# all there, nothing is fetched.
MODEL_FILES = ("config.json", "model.onnx", "special_tokens_map.json", "tokenizer_config.json",
               "tokenizer.json", "vocab.txt")
_TTP = re.compile(r"T\d{4}(?:\.\d{3})?")
_SOURCES = ("real", "exercise")
RANKINGS = ("distance", "date", "ttp_then_date", "ttp_then_distance")
# The rankings compared, two by two: the code's against each other; the date against the distance
# once the technique comes first (option b of docs/design/memoire.md).
PAIRS = (("distance", "date"), ("distance", "ttp_then_date"), ("distance", "ttp_then_distance"),
         ("ttp_then_date", "ttp_then_distance"))


class Refused(Exception):
    """What this script will not open, said on stderr: exit 2."""


def _linked_into(path, roots: tuple[str, ...]) -> str | None:
    """The operator's folder (``.glorfindel``) a file or a folder of ``path`` leads into through a
    link, or None — the copy walked, links not followed (a linked folder is checked, never entered)."""
    for top, folders, files in os.walk(path):
        for name in files + folders:
            found = store_guard.located(os.path.join(top, name), roots)
            if found is not None:
                return found[1]
    return None


def refusal(path, homes=None) -> str | None:
    """Why ``path`` is not opened, or None: the operator's folders (``homes``: the home the system
    gives him and HOME), a copy one of whose files leads there, or a folder that is not a store."""
    homes = (store_guard.operator_home(), Path.home()) if homes is None else homes
    roots = tuple(dict.fromkeys(root for home in homes for root in store_guard.roots_of(home)))
    found = store_guard.located(path, roots)
    if found is not None:
        return (f"refusé : ce chemin est dans le ~/{found[1]} de l'opérateur. Une copie seulement : "
                "celle de make imladris-pull, extraite dans un dossier à part (l'en-tête de ce script).")
    linked = _linked_into(path, roots)
    if linked is not None:
        return (f"refusé : un fichier de ce dossier mène par un lien au ~/{linked} de l'opérateur. Une "
                "copie seulement, sans lien vers l'original.")
    if not (Path(path) / "chroma.sqlite3").is_file():
        return "refusé : ce dossier n'est pas la copie d'un magasin (pas de chroma.sqlite3) ; rien n'est créé."
    return None


def _offline() -> None:
    """Chroma's telemetry off, the Hugging Face hub offline — in this process."""
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    os.environ["HF_HUB_OFFLINE"] = "1"


def embedder():
    """The signal's text → its embedding, by Chroma's local ONNX model; Refused when a file of the
    model is missing (never fetched here)."""
    import numpy as np
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    folder = Path(ONNXMiniLM_L6_V2.DOWNLOAD_PATH) / ONNXMiniLM_L6_V2.EXTRACTED_FOLDER_NAME
    if not all((folder / name).is_file() for name in MODEL_FILES):
        raise Refused("refusé : le modèle ONNX de Chroma n'est pas sur le disque (~/.cache/chroma) ; ce "
                      "script ne le tire jamais. python scripts/chroma_model.py le tire, sur le réseau.")
    model = ONNXMiniLM_L6_V2()
    return lambda text: np.asarray(model([text])[0], dtype=float)


def _field(document: str, name: str) -> str:
    """A field of a cycle's text (`memory._cycle_to_text`), "" when absent."""
    for part in (document or "").split(" | "):
        if part.startswith(f"{name}: "):
            return part[len(name) + 2:]
    return ""


def load(path) -> list[dict]:
    """The cycles of the store at ``path``, as the replay reads them (embedded client, telemetry off)."""
    import chromadb
    import numpy as np
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    try:
        collection = client.get_collection(COLLECTION)
    except Exception as exc:   # chromadb 1.x: NotFoundError, ValueError before
        raise Refused(f"refusé : ce magasin n'a pas de collection « {COLLECTION} » ({type(exc).__name__}).") from None
    got = collection.get(include=["metadatas", "documents", "embeddings"])
    cycles = []
    for i, (meta, document, embedding) in enumerate(zip(got["metadatas"], got["documents"], got["embeddings"])):
        meta = meta or {}
        cycles.append({
            "i": i, "source": str(meta.get("source") or ""),
            # As the code dates it: its own date, else the B2 floor (memory._stored_at).
            "at": memory._stored_at(meta), "dated": memory._dated(meta),
            "rule": str(meta.get("rule_name") or ""), "vm": memory._vm_key(meta.get("resource_id")),
            "key": (meta.get("signal_id", ""), meta.get("action", ""), meta.get("run_id", "")),
            "ttp": str(meta.get("ttp") or ""), "event": str(meta.get("event") or ""),
            "severity": _field(document, "severity"), "rtype": _field(document, "resource_type"),
            "emb": np.asarray(embedding, dtype=float),
        })
    return cycles


def pick(candidates: list[dict], rule: str, vm: str, order, n: int = N) -> list[int]:
    """The precedents the code would give (`retrieve_similar`): the same rule first, then the same VM,
    then ``order``; one cycle per (signal_id, action, run_id); at most ``memory.PER_VM`` per VM."""
    def rank(c):
        return (not rule or c["rule"] != rule, not vm or c["vm"] != vm, order(c))

    out, seen, per_vm = [], set(), Counter()
    for c in sorted(candidates, key=rank):
        if len(out) == n:
            break
        if c["key"] in seen or per_vm[c["vm"]] >= memory.PER_VM:
            continue
        seen.add(c["key"])
        per_vm[c["vm"]] += 1
        out.append(c["i"])
    return out


def public_rule(name: str, shipped: set[str]) -> str:
    """A rule's name as printed: a shipped rule's (public), else « (other) »."""
    if not name:
        return "(none)"
    return name if name in shipped else "(other)"


def public_ttp(ttp: str) -> str:
    """A technique as printed: an ATT&CK id, else « (other) »."""
    if not ttp:
        return "(none)"
    return ttp if _TTP.fullmatch(ttp) else "(other)"


def _public_source(source: str) -> str:
    if not source:
        return "(none)"
    return source if source in _SOURCES else "(other)"


def _shipped() -> set[str]:
    from glorfindel import detection_rules
    return detection_rules.shipped_rule_names()


def replay(cycles: list[dict], embed, max_age_days: float = memory.DEFAULT_MAX_AGE_DAYS,
           n: int = N, shipped: set[str] | None = None) -> dict:
    """The aggregated numbers of the replay (the module's docstring)."""
    import numpy as np

    shipped = _shipped() if shipped is None else shipped
    max_age_s = memory.checked_max_age(max_age_days) * 86400
    real = sorted((c for c in cycles if c["source"] == "real"), key=lambda c: c["at"])
    by_i = {c["i"]: c for c in real}
    unit = {}
    for c in real:
        norm = float(np.linalg.norm(c["emb"]))
        unit[c["i"]] = c["emb"] / norm if norm else c["emb"]
    queries: dict[str, object] = {}

    with_precedent = contested = same_ttp_in_memory = 0
    same_set = Counter({f"{a}_vs_{b}": 0 for a, b in PAIRS})
    same_first = Counter({f"{a}_vs_{b}": 0 for a, b in PAIRS})
    jaccard: dict[str, list[float]] = {f"{a}_vs_{b}": [] for a, b in PAIRS}
    hits, given = Counter(), Counter()
    hits_by_ttp, given_by_ttp = defaultdict(Counter), defaultdict(Counter)
    for i, c in enumerate(real):
        eligible = [p for p in real[:i] if c["at"] - p["at"] <= max_age_s]
        if not eligible:
            continue
        with_precedent += 1
        text = memory._signal_to_text({"ttp": c["ttp"], "severity": c["severity"], "resource_type": c["rtype"],
                                       "event": c["event"], "provider": "azure"})
        if text not in queries:
            q = embed(text)
            norm = float(np.linalg.norm(q))
            queries[text] = q / norm if norm else q
        q = queries[text]
        distance = {p["i"]: 1.0 - float(np.dot(unit[p["i"]], q)) for p in eligible}
        picks = {
            "distance": pick(eligible, c["rule"], c["vm"], lambda p: distance[p["i"]], n),
            "date": pick(eligible, c["rule"], c["vm"], lambda p: -p["at"], n),
            "ttp_then_date": pick(eligible, c["rule"], c["vm"], lambda p: (p["ttp"] != c["ttp"], -p["at"]), n),
            "ttp_then_distance": pick(eligible, c["rule"], c["vm"],
                                      lambda p: (p["ttp"] != c["ttp"], distance[p["i"]]), n),
        }
        for a, b in PAIRS:
            one, other = set(picks[a]), set(picks[b])
            same_set[f"{a}_vs_{b}"] += one == other
            same_first[f"{a}_vs_{b}"] += picks[a][:1] == picks[b][:1]
            jaccard[f"{a}_vs_{b}"].append(len(one & other) / len(one | other) if one | other else 1.0)
        signal_ttp = public_ttp(c["ttp"])
        for name, chosen in picks.items():
            same = sum(by_i[x]["ttp"] == c["ttp"] for x in chosen)
            hits[name] += same
            given[name] += len(chosen)
            hits_by_ttp[signal_ttp][name] += same
            given_by_ttp[signal_ttp][name] += len(chosen)
        # The first place is played on the last key (the distance, or the date) when the best class —
        # same rule, same VM — holds more than one cycle.
        classes = Counter((not c["rule"] or p["rule"] != c["rule"], not c["vm"] or p["vm"] != c["vm"])
                          for p in eligible)
        contested += classes[min(classes)] > 1
        same_ttp_in_memory += any(p["ttp"] == c["ttp"] for p in eligible)

    def share(h: Counter, g: Counter) -> dict:
        return {name: round(h[name] / g[name], 3) if g[name] else None for name in RANKINGS}

    return {
        "store": {
            "cycles": len(cycles),
            "by_source": dict(Counter(_public_source(c["source"]) for c in cycles)),
            "real": len(real),
            "real_undated_b2_floor": sum(not c["dated"] for c in real),
            "real_span_days": round((real[-1]["at"] - real[0]["at"]) / 86400, 1) if real else 0.0,
            "real_without_rule_nor_vm": sum(not c["rule"] and not c["vm"] for c in real),
            "vm_keys": len({c["vm"] for c in real}),
            "rules": dict(Counter(public_rule(c["rule"], shipped) for c in real)),
            "ttps": dict(Counter(public_ttp(c["ttp"]) for c in real)),
        },
        "replay": {
            "max_age_days": max_age_s / 86400, "precedents": n, "per_vm": memory.PER_VM,
            "provider_assumed": "azure",
            "signals_with_a_precedent": with_precedent,
            "distinct_query_texts": len(queries),
            "first_place_contested": contested,
            "same_set": dict(same_set),
            "same_first": dict(same_first),
            "mean_jaccard": {pair: round(sum(js) / len(js), 3) if js else None for pair, js in jaccard.items()},
            "mean_precedents": {name: round(given[name] / with_precedent, 3) if with_precedent else None
                                for name in RANKINGS},
            "share_same_ttp": share(hits, given),
            "share_same_ttp_by_signal_ttp": {ttp: share(hits_by_ttp[ttp], given_by_ttp[ttp])
                                             for ttp in sorted(given_by_ttp)},
            "signals_with_a_same_ttp_cycle_in_memory": same_ttp_in_memory,
        },
    }


def _days(text: str) -> float:
    """A bound of age, as the memory reads it (memory.checked_max_age)."""
    try:
        return memory.checked_max_age(float(text))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MEM1 : la mémoire rejouée sur une copie du magasin, "
                                                 "chiffres agrégés seulement (l'en-tête du script).")
    parser.add_argument("store", help="le dossier cycles d'une COPIE du magasin (make imladris-pull, extraite)")
    parser.add_argument("--max-age-days", type=_days, default=memory.DEFAULT_MAX_AGE_DAYS,
                        help="la borne d'âge des précédents (défaut : celle de la mémoire, 90 jours)")
    args = parser.parse_args(argv)
    said = refusal(args.store)
    if said is not None:
        print(said, file=sys.stderr)
        return 2
    _offline()
    try:
        embed = embedder()
        out = replay(load(args.store), embed, max_age_days=args.max_age_days)
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
