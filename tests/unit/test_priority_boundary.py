"""PRI2a (#1219), PR1's guard of structure: a VM's priority touches neither the detection nor the response
(docs/design/classification.md, §0, §8.1).

The priority — `level_of`, and its former names `is_critical`, `critical_count` — is read only by a closed list
of modules (READERS): the model's budget, the gate of the calls (the order, PRI4), the class of a change, the
view « Relaxed », the console, the watch's start, and the reading and the writers of the config. Not the push
to Imladris: infra/glorfindel-host/host_config.py imports nothing of Glorfindel and has its own reading (PRI2b
holds the two equal). A reader more — the enquiry, the dossier, the bot, `decide`, the preparation, the
RulePoller — fails here, as tests/unit/test_provider_boundary.py does for a provider's SDK.

And `decide` (glorfindel/agent.py) and the bot (glorfindel/bot*.py) never read a field `priority` the data
carries (the signal, the card, the state), nor a rule's: no key « priority », no attribute `.priority` or
`.critical`, no name `priority` in them — the class cannot come in by another road. (The words `priority` and
`critical` alone are too common elsewhere — an NSG rule's priority, `log.critical` — for a guard by name.)
"""
from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("glorfindel", "eregion_console", "eregion_core")
NAMES = frozenset({"level_of", "is_critical", "critical_count"})
BLIND_ATTRS = frozenset({"priority", "critical", *NAMES})
READERS = frozenset({
    "glorfindel/config.py",             # the model: level_of, and the former names on it
    "glorfindel/config_assets.py",      # the strict reading of both formats
    "glorfindel/config_migrate.py",     # glorfindel config migrate
    "glorfindel/config_class.py",       # CFG4: the class of a change, name by name
    "glorfindel/model_budget.py",       # PRT2: the reserve of the essential VMs
    "glorfindel/decision_queue.py",     # PRT1's gate: the order between the VMs (PRI4)
    "glorfindel/relaxed.py",            # CFG3: the view « Relaxed »
    "glorfindel/watch/startup.py",      # the watch's start
    "eregion_console/api.py",           # the console
    "eregion_console/config_state.py",
})
# decide and the bot: no `priority` from the data, by any road.
DATA_BLIND = ("glorfindel/agent.py", "glorfindel/bot.py", "glorfindel/bot_*.py")
# The field and the rule, read around level_of (the review of PRI2a): outside READERS, no import of the level's
# pieces from glorfindel.config, and no attribute `.priority` (a rule's) nor `.critical` (its former name) —
# but where those words mean something else, each (file, attribute) named with its reason. No exemption for the
# imports: the level's pieces, by `from glorfindel.config import …` or through the module (`config._LEVEL_RANK`).
LEVEL_IMPORTS = frozenset({"ESSENTIAL", "STANDARD", "QUIET", "VALID_PRIORITIES", "_LEVEL_RANK", "_by_specificity",
                           "_highest"})
_NSG = "an NSG rule's priority (Azure's number, 100–4096), never a VM's"
FIELD_ELSEWHERE = {
    ("glorfindel/providers/azure/nsg.py", ".priority"): _NSG,
    ("glorfindel/providers/azure/network.py", ".priority"): _NSG,
    ("glorfindel/providers/azure/readers.py", ".priority"): _NSG,
    ("glorfindel/queue_watch.py", ".critical"): "`refused.critical`: a refusal of the signed queue said loud",
    ("glorfindel/restore_executor.py", ".critical"): "`refused.critical`: the same refusal, by the restore's executor",
}


def _files():
    for top in SCANNED:
        for p in sorted((ROOT / top).rglob("*.py")):
            if "__pycache__" not in p.parts:
                yield p.relative_to(ROOT).as_posix(), p


def _blind(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, g) for g in DATA_BLIND)


def readers(source: str) -> list[str]:
    """Each read of a name of NAMES in ``source``: an attribute (`x.level_of`), or `getattr(x, "level_of")`."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr in NAMES:
            out.append(f"{node.lineno}: .{node.attr}")
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("getattr", "hasattr")
              and len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and node.args[1].value in NAMES):
            out.append(f"{node.lineno}: {node.func.id}(…, {node.args[1].value!r})")
    return out


def priority_reads(source: str) -> list[str]:
    """Each road by which ``source`` could read a priority: a key « priority » (a constant, a dict's key read),
    an attribute `.priority`, `.critical` or a name of NAMES, a name or an argument `priority`."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.strip().lower() == "priority":
            out.append(f"{node.lineno}: {node.value!r}")
        elif isinstance(node, ast.Attribute) and node.attr in BLIND_ATTRS:
            out.append(f"{node.lineno}: .{node.attr}")
        elif isinstance(node, ast.Name) and "priority" in node.id.lower():
            out.append(f"{node.lineno}: name {node.id}")
        elif isinstance(node, ast.arg) and "priority" in node.arg.lower():
            out.append(f"{node.lineno}: argument {node.arg}")
    return out


def test_the_priority_is_read_only_by_the_closed_list():
    """PR1: `level_of` and its former names read nowhere outside READERS."""
    outside = {rel: hits for rel, p in _files() if rel not in READERS
               and (hits := readers(p.read_text(encoding="utf-8")))}
    assert outside == {}, ("the priority read outside the closed list of PR1 (tests/unit/test_priority_boundary.py)"
                           f" — it touches neither the detection nor the response: {outside}")


def field_reads(source: str) -> list[tuple[int, str]]:
    """Each (line, what) of ``source`` that could rebuild the level: a piece of LEVEL_IMPORTS imported from
    glorfindel.config, or read through the module (`from glorfindel import config` then `config._LEVEL_RANK`,
    `import glorfindel.config as c` then `c.ESSENTIAL`, `glorfindel.config.ESSENTIAL`); an attribute
    `.priority` or `.critical`."""
    tree = ast.parse(source)
    aliases: set[str] = set()                     # the names bound to the module glorfindel.config
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "glorfindel":
            aliases |= {a.asname or a.name for a in node.names if a.name == "config"}
        elif isinstance(node, ast.Import):
            aliases |= {a.asname for a in node.names if a.name == "glorfindel.config" and a.asname}
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "glorfindel.config":
            out += [(node.lineno, f"import {a.name}") for a in node.names if a.name in LEVEL_IMPORTS]
        elif isinstance(node, ast.Attribute) and node.attr in ("priority", "critical"):
            out.append((node.lineno, f".{node.attr}"))
        elif isinstance(node, ast.Attribute) and node.attr in LEVEL_IMPORTS and (
                (isinstance(node.value, ast.Name) and node.value.id in aliases)
                or (isinstance(node.value, ast.Attribute) and node.value.attr == "config"
                    and isinstance(node.value.value, ast.Name) and node.value.value.id == "glorfindel")):
            out.append((node.lineno, f"config.{node.attr}"))
    return out


def test_the_level_s_pieces_and_a_rule_s_field_are_read_only_by_the_closed_list():
    """PR1, by the field: `level_of` is not the only road — the constants of the level, `_by_specificity`, a
    rule's `.priority` or `.critical` read elsewhere would rebuild it. Outside READERS, none; where the word
    means another thing, the (file, attribute) is named in FIELD_ELSEWHERE with its reason — never an import."""
    outside = {rel: hits for rel, p in _files() if rel not in READERS
               and (hits := [h for h in field_reads(p.read_text(encoding="utf-8")) if (rel, h[1]) not in FIELD_ELSEWHERE])}
    assert outside == {}, f"the level rebuilt outside the closed list of PR1: {outside}"
    for (rel, attr) in FIELD_ELSEWHERE:
        assert any(h[1] == attr for h in field_reads((ROOT / rel).read_text(encoding="utf-8"))), \
            f"{rel} no longer reads {attr}: take the exemption out of FIELD_ELSEWHERE"
    assert field_reads("from glorfindel.config import ESSENTIAL\n") and field_reads("x = r.priority\n")
    assert field_reads("from glorfindel import config\nx = config._LEVEL_RANK\n")
    assert field_reads("import glorfindel.config as c\nx = c.ESSENTIAL\n")
    assert field_reads("import glorfindel.config\nx = glorfindel.config._by_specificity\n")
    assert not field_reads("from glorfindel.config import load_glorfindel_config\n")
    assert not field_reads("from glorfindel import config\nx = config.load_glorfindel_config()\n")


def test_decide_and_the_bot_never_read_a_priority_the_data_carries():
    """PR1: no key, attribute or name « priority » in decide's module nor in the bot's — the class never
    enters by the data."""
    hits = {rel: found for rel, p in _files() if _blind(rel) and (found := priority_reads(p.read_text("utf-8")))}
    assert hits == {}, f"decide or the bot reads a priority: {hits}"


def test_the_guard_sees_what_it_guards():
    """The guard is never blind: it finds the readers it lets through, each module of the list exists, the
    modules of decide and the bot are scanned, and it sees a reader written any way."""
    found = {rel for rel, p in _files() if readers(p.read_text(encoding="utf-8"))}
    assert {"glorfindel/model_budget.py", "glorfindel/config_class.py", "glorfindel/config_migrate.py"} <= found
    assert all((ROOT / rel).exists() for rel in READERS)
    assert {"glorfindel/agent.py", "glorfindel/bot.py"} <= {rel for rel, _ in _files() if _blind(rel)}
    assert readers("x = cfg.autonomy.level_of(vm)\n") and readers("getattr(a, 'is_critical')\n")
    assert readers("a.critical_count()\n") and not readers("x = level_of\n")
    assert priority_reads("data.get('priority')\n") and priority_reads("def f(priority): pass\n")
    assert priority_reads("r.critical\n") and priority_reads("x = r.priority\n") and priority_reads("a.level_of\n")
    assert not priority_reads('"""the priority of a VM"""\n')
