"""The mutants only an invariant machine kills, measured each night on seeds drawn (MUT7, #699).

On 10/11 the 0.5.9 release gate was held five times by mutants that only the invariant machines
kill and that some draws of the seed let through (SEED1 draws one per round): M21, then M606 and
M09, then M13 and M33, found the evening of the release, one after the other. This measure finds
them before the gate: each night, a share of those mutants at the gate's 500 sequences, on N seeds
drawn (3 by default), each said CAUGHT n/n, flaky or SURVIVES, with the command that replays it on
the seed it survived on.

    python scripts/mutation_night.py --list                         # the list, by night: nothing measured
    python scripts/mutation_night.py --part auto --jobs 4 --json night.json   # tonight's share (the workflow's)
    python scripts/mutation_night.py --part all --only M21,M09 --seeds 3
    python scripts/mutation_night.py --only M21 --seed 89917386 --seeds 1     # a replay, one seed

**Which mutants.** A mutant's target (scripts/mutation_check.py, TESTS and each lot's TESTS_ALSO)
is a list of test paths. A word of it runs a machine when its file defines a RuleBasedStateMachine
and the word reaches the test that runs it: the file whole (and its `-k`, when the target has one,
matches that test's name), or a node naming that test. A node of the same file naming another
test does not: tests/unit/test_recovery_watch.py defines a machine, and 19 targets name its plain
tests only — file by file (mutation_check.machine), they read as machines. Every other test word is
a fixed test: a unit test, a frozen sequence.
- ALONE (by the table): the target runs a machine and nothing else. The machine is the only killer
  its target holds — or almost: a machine's file whole runs its few plain tests too.
- BESIDE (by the measure): the target runs a machine and fixed tests. The table cannot say whether
  those fixed tests catch the mutant: a lot names the tests it means to, and its measure at the time
  says CAUGHT whichever test failed. So the fixed tests run first, once, on the mutant: caught, the
  mutant is CAUGHT by its fixed tests, whatever the seed — out of the list; not caught, the machine
  alone kills it, and it is measured as an ALONE one. A fixed part that draws (Hypothesis) or races
  (mutation_check.chance) is no fixed killer: its mutant runs its whole target on each seed.
The uncounted mutants (EQUIVALENT, MULTI-HOST) are left out; a known survivor (TIMING) is measured
and said, never fragile.

**The verdict**, seed by seed — round r on S + r - 1, S drawn or given (SEED1): CAUGHT n/n, flaky
(caught on some seeds, not all), SURVIVES (caught on none). Fragile: flaky or SURVIVES, outside the
known survivors. Each fragile mutant is said with the seeds it survived on and, for each, the
command that measures it as the gate does (mutation_check.py --only … --seed … --rounds 1). The
remedy follows MUT5, MUT6 and MUT8: a frozen sequence in tests/unit/test_invariant_regressions.py
(or _aws.py), linked to the mutant by TESTS_ALSO — the mutant is then BESIDE, its fixed tests
catching it: CAUGHT by them on its night, in one run, the frozen sequence proven to hold it still
(docs/design/preuves.md, « Les mutants fragiles, de la nuit à la séquence figée »).

**The rotation**: a mutant's night is fixed by its id alone (crc32(id) mod PARTS), never by the
others — a mutant added or removed moves no other one, and each is measured once in PARTS nights.
`--part auto` takes the night of today's date (UTC). Each machine runs unmutated first, on each
seed, and the fixed tests of the share once: a red base makes the night no measure (exit 2).

Exit: 0 measured — with `--json`, whatever it found (the workflow reads the file); without, 1 when a
mutant is fragile; 2 when the unmutated code fails, or a part collects no test.
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import datetime
import json
import re
import shutil
import sys
import tempfile
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutation_check as mc  # noqa: E402  (a script beside this one, not a package)

PARTS = 7          # a share each night, the whole list in a week
SEEDS = 3
EXAMPLES = 500     # the release gate's
NO_TEST = 5        # pytest's exit status when it collected no test
_MACHINE_TESTS: dict[str, frozenset | None] = {}


def machine_tests(rel: str) -> frozenset | None:
    """The tests of a file that run one of its invariant machines: each test function whose body
    names a RuleBasedStateMachine class of the file (`run_state_machine_as_test(Machine…)`), and each
    module-level `TestX = Machine.TestCase`. Empty when it defines none; None when it cannot be read."""
    if rel not in _MACHINE_TESTS:
        source = mc._source(rel)
        try:
            tree = ast.parse(source) if source is not None else None
        except SyntaxError:
            tree = None
        if tree is None:
            _MACHINE_TESTS[rel] = None
            return None
        machines = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "") for b in node.bases}
                if "RuleBasedStateMachine" in bases or bases & machines:
                    machines.add(node.name)
        found = set()
        if machines:
            names = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(machines))) + r")\b")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                    if names.search(ast.get_source_segment(source, node) or ""):
                        found.add(node.name)
                elif isinstance(node, ast.Assign):
                    text = ast.get_source_segment(source, node) or ""
                    if ".TestCase" in text and names.search(text):
                        found |= {t.id for t in node.targets if isinstance(t, ast.Name) and t.id.startswith("Test")}
        _MACHINE_TESTS[rel] = frozenset(found)
    return _MACHINE_TESTS[rel]


def _keys(words: list[str]) -> set[str]:
    """The words of a target's `-k` expressions (as mutation_check.races reads them)."""
    return {w for i, word in enumerate(words) if word == "-k" and i + 1 < len(words)
            for w in re.findall(r"[A-Za-z_]\w*", words[i + 1]) if w not in ("and", "or", "not")}


def split(target: str) -> tuple[list[str], list[str], list[str]]:
    """(its words that run a machine, its other test words, its options) — a `-k` with its expression."""
    words = target.split()
    keys = _keys(words)
    machine_words, fixed, options = [], [], []
    i = 0
    while i < len(words):
        word = words[i]
        path, _, rest = word.partition("::")
        if not path.endswith(".py"):
            options += words[i:i + 2] if word == "-k" else [word]
            i += 2 if word == "-k" else 1
            continue
        found = machine_tests(path) or frozenset()
        parts = [p.split("[")[0] for p in rest.split("::")] if rest else []
        if parts:
            runs = any(p in found for p in parts)
        else:
            runs = any(not keys or any(k in t for k in keys) for t in found)
        (machine_words if runs else fixed).append(word)
        i += 1
    return machine_words, fixed, options


ALONE, BESIDE = "alone", "beside"


def chosen(mutants: list, tests: dict) -> list[dict]:
    """The mutants a night measures, in the tree's order: each counted one whose target runs a machine,
    with its machine part, its fixed part ('' for an ALONE one) and its kind."""
    out = []
    for m in mutants:
        if mc.mark(m) in mc.UNCOUNTED_MARKS:
            continue
        target = tests.get(m[0], mc.INVARIANTS)
        machine_words, fixed, options = split(target)
        if not machine_words:
            continue
        out.append({"mutant": m, "target": target, "machine": " ".join(machine_words + options),
                    "fixed": " ".join(fixed + options) if fixed else "", "kind": BESIDE if fixed else ALONE})
    return out


def part_of(mid: str, parts: int = PARTS) -> int:
    """A mutant's night, 1 to `parts`: its id's alone."""
    return zlib.crc32(mid.encode("utf-8")) % parts + 1


def tonight(parts: int = PARTS, day: datetime.date | None = None) -> int:
    """The night of this date (UTC today when none): over `parts` days in a row, each night once."""
    day = day or datetime.datetime.now(datetime.timezone.utc).date()
    return day.toordinal() % parts + 1


PART = re.compile(r"([1-9]\d*)/([1-9]\d*)")


def parse_part(text: str) -> tuple[int, int] | None:
    """`--part`: 'auto' (tonight's of PARTS), 'all' (None), or K/N, 1 <= K <= N."""
    text = text.strip()
    if text == "auto":
        return tonight(), PARTS
    if text == "all":
        return None
    m = PART.fullmatch(text)
    if not m or int(m.group(1)) > int(m.group(2)):
        raise argparse.ArgumentTypeError(f"--part {text!r}: auto, all, or K/N with 1 <= K <= N")
    return int(m.group(1)), int(m.group(2))


def _count(text: str) -> int:
    """`--seeds N`: N >= 1."""
    if not re.fullmatch(r"[1-9]\d*", text.strip()):
        raise argparse.ArgumentTypeError(f"{text!r}: a number of seeds, 1 or more")
    return int(text)


def _caught(copy: Path, examples: int, target: str, seed: int | None) -> bool:
    """True when `target` fails on this copy, as mutation_check._run measures it — but a target
    that collects no test is no measure, never a catch: it raises."""
    proc = mc._pytest(copy, examples, target, "-x", seed=seed)
    missing = mc.unmeasurable(proc.stdout)
    if missing:
        raise RuntimeError(f"{missing}\n{proc.stdout[-2000:]}")
    if proc.returncode == NO_TEST:
        raise RuntimeError(f"{target}: collects no test")
    return proc.returncode != 0


def measure(item: dict, copy: Path, examples: int, seeds: list[int]) -> dict:
    """One mutant on its copy (the mutant applied): its fixed tests first, once, then its machine on
    each seed — the whole target on each seed when its fixed part draws or races."""
    mutant = item["mutant"]
    row = {"id": mutant[0], "title": mutant[1], "kind": item["kind"], "known": mc.mark(mutant),
           "rounds": len(seeds), "caught": 0, "survived_on": [], "by": "machine"}
    stale = mc.apply_mutant(mutant, copy)
    if stale is not None:
        return {**row, "verdict": "STALE", "detail": stale, "rounds": 0}
    fixed, target = item["fixed"], item["machine"]
    if fixed and mc.chance(fixed):
        target = f"{fixed} {item['machine']}"          # no fixed killer: the whole target, each seed
    elif fixed and _caught(copy, examples, fixed, seeds[0]):
        return {**row, "verdict": "CAUGHT", "caught": len(seeds), "by": "fixed",
                "detail": f"{len(seeds)}/{len(seeds)} by its fixed tests"}
    for s in seeds:
        if _caught(copy, examples, target, s):
            row["caught"] += 1
        else:
            row["survived_on"].append(s)
    n, k = len(seeds), row["caught"]
    verdict = "CAUGHT" if k == n else ("flaky" if k else "SURVIVES")
    return {**row, "verdict": verdict, "detail": f"{k}/{n}"}


def fragile(rows: list[dict]) -> list[dict]:
    """Each mutant a seed let through, outside the known survivors."""
    return [r for r in rows if r["verdict"] in ("flaky", "SURVIVES") and not r["known"]]


def output_line(rows: list[dict]) -> str:
    """The workflow's output: `M21:2/3:89917387,89917388 M09:0/3:…` — ids, rounds, seeds; nothing else."""
    return " ".join(f"{r['id']}:{r['caught']}/{r['rounds']}:{','.join(map(str, r['survived_on']))}"
                    for r in fragile(rows))


def say_rows(rows: list[dict], examples: int, seed: int, n: int, say=print) -> None:
    for r in rows:
        known = f" (a known survivor: {r['known']})" if r["known"] else ""
        by = " by its fixed tests" if r["by"] == "fixed" else ""
        on = f", survived on {', '.join(map(str, r['survived_on']))}" if r["survived_on"] else ""
        say(f"  {r['id']}  {r['verdict']:8}  {r['detail']:28}  [{r['kind']}{by}{on}]{known}  {r['title']}")
    for r in fragile(rows):
        for s in r["survived_on"]:
            say(f"    replay {r['id']} (seed {s}): {mc.replay_of(r['id'], s, examples, 1)}")
        say(f"    again, this night's measure: python scripts/mutation_night.py --only {r['id']} --seed {seed} "
            f"--seeds {n} --examples {examples} --part all")


def say_list(items: list[dict], parts: int, durations: dict, n: int, say=print) -> int:
    """`--list`: each mutant, its kind and its night; each night's count and its estimate."""
    measured = durations.get("mutants", {})
    by_part: dict[int, list] = {k: [] for k in range(1, parts + 1)}
    for item in items:
        by_part[part_of(item["mutant"][0], parts)].append(item)
    for item in items:
        mid = item["mutant"][0]
        say(f"  {mid}  {item['kind']:6}  night {part_of(mid, parts)}/{parts}  {item['target']}")
    alone = sum(1 for i in items if i["kind"] == ALONE)
    say(f"\n{len(items)} mutants run an invariant machine: {alone} alone (the table), "
        f"{len(items) - alone} beside fixed tests (the measure says whether those catch them)")
    for k, part in by_part.items():
        est = sum(_estimate(i, measured, n) for i in part)
        say(f"  night {k}/{parts}: {len(part):3d} mutants, about {est / 60:.0f} min of runner at {n} seeds")
    return 0


def _estimate(item: dict, measured: dict, n: int) -> float:
    """Seconds, from the gate's measure (two rounds at 500): n seeds' worth; unmeasured, HEAVY units."""
    s = mc._seconds(measured.get(item["mutant"][0]))
    return (s if s is not None else mc.HEAVY * mc.UNIT * 2) * n / 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--part", type=parse_part, default=None,
                    help="auto (tonight's of 7), all (the default), or K/N")
    ap.add_argument("--seeds", type=_count, default=SEEDS, help="seeds drawn per mutant (3)")
    ap.add_argument("--seed", type=mc._seed_arg, default=None, metavar="S",
                    help="the first seed, seed r on S + r - 1: given, a replay; drawn when none is given")
    ap.add_argument("--examples", type=int, default=EXAMPLES)
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--json", default="", help="write what was measured to this file")
    ap.add_argument("--output", default="", metavar="FILE",
                    help="append `fragile=…` and `examples=…` to this file (the workflow's $GITHUB_OUTPUT)")
    ap.add_argument("--list", action="store_true", help="say the list and its nights; measure nothing")
    args = ap.parse_args(argv)
    only = {m.strip() for m in args.only.split(",") if m.strip()}
    items = [i for i in chosen(mc.MUTANTS, mc.TESTS) if not only or i["mutant"][0] in only]
    if args.list:
        return say_list(items, args.part[1] if args.part else PARTS, mc.load_durations(), args.seeds)
    if args.part:
        k, parts = args.part
        items = [i for i in items if part_of(i["mutant"][0], parts) == k]
    seed = mc.draw_seed() if args.seed is None else args.seed
    seeds = mc.round_seeds(seed, args.seeds)
    where = f"night {args.part[0]}/{args.part[1]}" if args.part else "every night"
    print(f"{len(items)} mutants of the invariant machines ({where}), {args.examples} sequences, seeds "
          f"{', '.join(map(str, seeds))} ({'given' if args.seed is not None else 'drawn'}: --seed {seed} "
          f"replays them)", flush=True)
    with tempfile.TemporaryDirectory(prefix="glorfindel-night-") as tmp:
        pristine, base = Path(tmp) / "pristine", Path(tmp) / "base"
        mc._copy_repo(pristine)
        shutil.copytree(pristine, base)
        mc.prepare_embedding_model()
        machines = sorted({i["machine"] for i in items})
        fixed = " ".join(sorted({w for i in items for w in split(i["fixed"])[1]}))
        bases = [(m, s) for m in machines for s in seeds] + ([(fixed, seed)] if fixed else [])

        def unmutated(run):
            target, s = run
            try:
                return None if not _caught(base, args.examples, target, s) else f"{target} fails on seed {s}"
            except RuntimeError as exc:
                return str(exc).splitlines()[0]

        def one(item):
            copy = Path(tmp) / item["mutant"][0]
            shutil.copytree(pristine, copy)
            try:
                started = time.monotonic()
                row = measure(item, copy, args.examples, seeds)
                row["seconds"] = round(time.monotonic() - started, 1)
                print(f"{row['id']} {row['verdict']:8} {row['detail']} ({row['seconds']:.0f}s)", flush=True)
                return row
            finally:
                shutil.rmtree(copy, ignore_errors=True)
        cost = mc.load_durations().get("mutants", {})
        todo = mc.heaviest_first(items, {i["mutant"][0]: _estimate(i, cost, len(seeds)) for i in items},
                                 key=lambda i: i["mutant"][0])
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            problems = [p for p in pool.map(unmutated, bases) if p]
            rows = [] if problems else sorted(pool.map(one, todo), key=lambda r: r["id"])
    for p in problems:
        print(f"  ✗ the UNMUTATED code: {p} — fix that first: this night measured nothing")
    if problems:
        return 2
    print(f"\n{args.examples} sequences, seeds {', '.join(map(str, seeds))} ({where}):")
    say_rows(rows, args.examples, seed, len(seeds))
    weak = fragile(rows)
    print(f"\n{sum(r['verdict'] == 'CAUGHT' for r in rows)}/{len(rows)} caught on every seed; "
          f"{len(weak)} fragile" + (f": {', '.join(r['id'] for r in weak)}" if weak else ""))
    if args.json:
        Path(args.json).write_text(json.dumps({
            "night": args.part[0] if args.part else None, "parts": args.part[1] if args.part else None,
            "examples": args.examples, "seed": seed, "seeds": seeds, "rows": rows,
            "fragile": [r["id"] for r in weak]}, indent=1) + "\n", encoding="utf-8")
    if args.output:
        with open(args.output, "a", encoding="utf-8") as out:
            out.write(f"fragile={output_line(rows)}\nexamples={args.examples}\n")
    return 1 if weak and not args.json else 0


if __name__ == "__main__":
    sys.exit(main())
