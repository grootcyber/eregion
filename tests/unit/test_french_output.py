"""ENG1a (#1184): the product's output in English, surface by surface — a ratchet that only comes down.

The maintainer's decision (25/11): « tout en anglais, cli, discord, console, titre comme message, la
totale », in fifteen lots, in order; the docs, the comments and the docstrings stay as they are.
``scripts/french_output.py`` counts, file by file of the product (the repository's files), the strings
that still read French, and ``tests/unit/french_ceiling.json`` holds one ceiling per surface (S0 to S14,
and the console's), the sum of its files. Held here:
- no surface over its ceiling, and a surface absent from it at 0: S0 stays there, a new file never
  makes its surface go up, a file in no surface is at 0;
- a file may take what another of its surface gives up (a split): the surface's ceiling holds;
- a surface under its ceiling has its ceiling lowered in the same change (``--lower``): never raised;
- each surface with the lot that takes it;
- what the model sees out of the count, by name; the texts some code reads back and the English ones
  the detector would take for French not counted, each still where it is said to be;
- a file that cannot be read said, never a crash; the files read are the repository's, never the disk's;
- the first leftovers (S0: the TUI, the injectors' CLI, three files of the core) at 0.
The convention itself: CONTRIBUTING.md, « The product's output, in English ».
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("french_output", ROOT / "scripts" / "french_output.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["french_output"] = mod
    spec.loader.exec_module(mod)
    return mod


fo = _load()


@pytest.fixture(scope="module")
def scanned():
    return fo.scan()


@pytest.fixture(scope="module")
def counts(scanned):
    return scanned[0]


@pytest.fixture(scope="module")
def ceiling():
    return fo.load_ceiling()


# ── the repository, under its ceilings ────────────────────────────────────────────────────────

def test_no_product_file_reads_more_french_than_its_ceiling(counts, ceiling):
    """A surface over its ceiling, or one absent from it (at 0) that reads French: write it in English."""
    assert fo.over_ceiling(fo.totals(counts), ceiling, counts, fo.load_files()) == []
    assert [rel for rel in counts if fo.surface_of(rel) is None] == []


def test_a_ceiling_comes_down_with_its_file(counts, ceiling):
    """The ratchet: a surface under its ceiling has it lowered in the same change, never left loose."""
    assert fo.ceiling_to_lower(fo.totals(counts), ceiling) == []


def test_each_surface_has_its_lot_and_every_file_is_read(scanned, ceiling):
    counts, unreadable = scanned
    assert unreadable == []
    lots = {sid: lot for sid, lot, _name, _globs in fo.SURFACES}
    assert [lots[f"S{i}"] for i in range(15)] == [f"ENG1{c}" for c in "abcdefghijklmno"]
    assert lots["SC"] == "Console"
    assert fo.unknown_surfaces(ceiling) == [] and all(ceiling.values())    # no surface written empty
    assert sum(fo.load_files().values()) >= sum(ceiling.values())          # the detail adds up, at least


def test_the_files_read_are_the_repository_s(counts):
    """By git: the submodule of Stratus Red Team, Atomic Red Team's tests, a venv, never read."""
    listed = fo._listed_by_git(fo.ROOT)
    assert listed is not None and "scripts/french_output.py" in listed
    files = [rel for rel, _ in fo.product_files()]
    assert "glorfindel/tui.py" in files and "technique_catalog.yaml" in files and "schemas/scenario.schema.json" in files
    assert not [rel for rel in files if rel.startswith(("annatar/stratus/stratus-red-team/", "annatar/atomics/",
                                                         ".venv/", ".claude/"))]
    assert not fo.is_product("annatar/stratus/stratus-red-team/v2/x.go")


def test_the_texts_read_back_are_still_there_and_not_counted():
    assert fo.unfound() == []
    said = {(rel, text) for rel, text, _why in fo.READ_BACK}
    for rel, text in [("glorfindel/escalations.py", "Compte peut-être compromis"),       # COMPROMISE_MARK
                      ("glorfindel/response/policy.py", "zone exposée"),
                      ("glorfindel/exposed_zone.py", "réservée"),
                      ("eregion_console/api.py", "(?i)(?:étape|step)\\s+\\d+\\s*[–\\-:]"),
                      ("scripts/bench_preflight.py", "référence déployée"),
                      ("scripts/notify_discord.py", "[^\\w .,:;!?'’«»/=+-]|_"),
                      ("infra/glorfindel-host/cd/eregion_cd.py", "[^\\w .,:;!?'’«»()/=+-]")]:
        assert (rel, text) in said
        assert all(why for *_, why in fo.READ_BACK)
        found = [s for _, s in fo.strings_of(rel, (ROOT / rel).read_text(encoding="utf-8"))]
        assert text in found and fo.reads_french(text) and not fo.read_back(rel, text + " ")


def test_what_the_model_sees_is_out_of_the_count_by_name():
    assert fo.MODEL["glorfindel/agent.py"][0] == "_build_user_message"
    assert {"_SOURCE_TAGS", "_SYSTEM_PROMPT", "_DECISION_TOOL"} <= set(fo.MODEL["glorfindel/agent.py"])
    assert fo.MODEL["annatar/scenarios/**/*.yaml"] == ("hints",)          # detection_hints, to the model
    scenario = "description: Une attaque\ndetection:\n  query: T\n  hints:\n    log_source: la table des journaux\n"
    assert [s for _, s in fo.strings_of("annatar/scenarios/azure/x.yaml", scenario)] == ["Une attaque"]
    agent = (ROOT / "glorfindel/agent.py").read_text(encoding="utf-8")
    assert "[RÉEL]" in agent and "[RÉEL]" not in [s for _, s in fo.strings_of("glorfindel/agent.py", agent)]
    assert fo.MODEL["glorfindel/enquiry/**"] is None and fo.MODEL["glorfindel/memory_keys.py"] is None
    assert fo.MODEL["analysis/campaign_report.py"] == ("_SYSTEM",) == fo.MODEL["analysis/triage.py"]
    assert fo.strings_of("glorfindel/enquiry/loop.py", "x = 'la carte est lue'\n") == []
    source = ("def _build_user_message(s):\n    return f'## État actuel de la VM {s}'\n"
              "def said():\n    return 'Étape suivante'\n")
    assert [s for _, s in fo.python_strings(source, fo.MODEL["glorfindel/agent.py"])] == ["Étape suivante"]


def test_the_first_leftovers_are_in_english(counts, ceiling):
    """S0 (ENG1a): the TUI, the injectors' CLI, three files of the core — all at 0, S0 out of the ceilings."""
    assert "S0" not in ceiling
    for rel in ("glorfindel/tui.py", "annatar/cli.py", "gothmog/cli.py", "eregion_core/runs_layout.py",
                "eregion_core/rule_routing.py", "eregion_core/store_guard.py"):
        assert fo.surface_of(rel) == "S0" and rel not in counts, rel
    assert fo.surface_of("eregion_core/channel_reader.py") == "S6"     # with runs_channel, in ENG1g


def test_the_convention_is_written_where_the_guard_points():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "## The product's output, in English" in text
    for said in ("python scripts/french_output.py", "tests/unit/french_ceiling.json", "YYYY-MM-DD",
                 "notify_discord", "ENG1h", "ENG1o", "“…”", "**A file split**", "take the smaller side",
                 "`READ_BACK`", "`ENGLISH`"):
        assert said in text, said


# ── the detector ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "cette carte n'offre pas de restore", "déjà", "« Stop all »", "l'IP du poste", "qu'il relance",
    "la carte est là", "jamais lu", "rien", "Resource · : ·", "· : sessions", "un lien, une table",
])
def test_a_string_that_reads_french(text):
    assert fo.reads_french(text)


@pytest.mark.parametrize("text", [
    "this card offers no restore", "don't", "users' names", "  Engine  : · / ·", "  Dry-run : ·",
    "LIMIT ?", "a la", "en-US", "the “Stop all” button", "2026-11-25 10:00 UTC",
    "docs/operations.md, “Une sonde d'agent n'écrit jamais dans le vrai ~/.glorfindel”",
])
def test_a_string_that_does_not(text):
    assert not fo.reads_french(text)


def test_a_line_of_shell_has_no_spacing_rule():
    """`[ -f "$f" ] ; then` is shell, not French typography: the spacing is read in strings only."""
    assert fo.reads_french("[ -f \"$f\" ] ; then") and not fo.reads_french("[ -f \"$f\" ] ; then", spacing=False)
    assert fo.french_in("infra/x.sh", "[ -f \"$f\" ] ; then\necho 'déjà'\n") == [(2, "echo 'déjà'")]


def test_python_strings_never_a_docstring_nor_a_comment_and_an_fstring_is_one():
    source = ('"""Le module, en français."""\n'
              "# un commentaire en français\n"
              "def f(vm):\n"
              '    """La fonction."""\n'
              "    return f\"{vm} : jamais lu ({vm!s:.40})\"\n"
              "X = 'ok'\n")
    assert [s for _, s in fo.python_strings(source)] == ["· : jamais lu (·)", "ok"]


def test_js_strings_a_template_is_one_and_comments_and_regexes_are_aside():
    source = ("const a = `x ${b ? `la carte est ${c}` : 'non'} y`; // é commentaire\n"
              "let r = /'é/g; f('d\\'un'); x = a / 2 / 3; /* é */ g(\"ok\")\n")
    assert sorted(s for _, s in fo.js_strings(source)) == sorted(["x · y", "la carte est ·", "non", "d'un", "ok"])


def test_html_lines_yaml_and_json():
    assert [s for _, s in fo.html_strings('<!-- é --><p title="Fermer">Close</p><style>p{}</style>')] == \
        ["Fermer", "Close"]
    assert [s for _, s in fo.line_strings("# é\necho 'x # y' # é\n\n")] == ["echo 'x # y' "]
    rules = "rules:\n  - name: r\n    description: Une règle\n    query: |\n      T | where x == 'é'\n"
    assert [s for _, s in fo.yaml_strings(rules)] == ["r", "Une règle"]
    scenario = "prerequisites:\n  - why: la table\n    verify: \"T | where x == 'é'\"\n"
    assert [s for _, s in fo.yaml_strings(scenario)] == ["la table"]              # a `verify:` is a query
    schema = '{"title": "Scénario", "properties": {"x": {"description": "Une clé", "pattern": "é+"}}}'
    assert sorted(s for _, s in fo.json_strings(schema)) == ["Scénario", "Une clé"]


def test_the_product_and_what_is_not():
    for rel in ("glorfindel/tui.py", "annatar/cli.py", "eregion_core/x.py", "scripts/doctor.py", "Makefile",
                "infra/glorfindel-host/deploy.sh", ".github/workflows/ci.yml", "eregion_console/static/a.js",
                "technique_catalog.yaml", "drills/banc-hebdo.yaml", "schemas/scenario.schema.json",
                "annatar/scenarios/azure/x.yaml", "annatar/campaign/declared/x.yaml"):
        assert fo.is_product(rel), rel
    for rel in ("tests/unit/test_x.py", "infra/orodruin/tests/test_x.py", "scripts/mutation_check.py",
                "scripts/mutants/ENG1a.py", "scripts/french_output.py", "docs/operations.md",
                "annatar/atomics/T1136.001/T1136.001.yaml", "infra/identities/r.json"):
        assert not fo.is_product(rel), rel
    assert fo.strings_of("infra/terraform/main.tf", "") is None       # Terraform: out of ENG1
    assert fo.surface_of("glorfindel/providers/azure/entra.py") == "S12"
    assert fo.surface_of("glorfindel/providers/azure/release.py") == "S13"
    for rel in ("infra/glorfindel-host/client_rules.bench.yaml", "annatar/scenarios/azure/x.yaml",
                "technique_catalog.yaml", "gothmog/experiments/vm-restart.yaml", "schemas/x.json"):
        assert fo.surface_of(rel) == "S11", rel


# ── the ratchet, on a tree of its own ────────────────────────────────────────────────────────

def _tree(tmp_path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def _ceiling(tmp_path, ceilings: dict[str, int], counts: dict[str, int]) -> Path:
    path = tmp_path / "ceiling.json"
    fo.write_ceiling(ceilings, counts, path)
    return path


@pytest.fixture
def own(monkeypatch):
    """A tree of its own: no text listed of the repository's."""
    monkeypatch.setattr(fo, "READ_BACK", ())
    monkeypatch.setattr(fo, "ENGLISH", ())


def test_a_new_file_never_makes_its_surface_go_up(tmp_path, own):
    root = _tree(tmp_path / "t", {"glorfindel/bot.py": "X = 'la carte est lue'\nY = 'jamais'\n",
                                  "glorfindel/agent.py": "Z = 'déjà'\n"})
    counts = fo.count(root)
    assert counts == {"glorfindel/bot.py": 2, "glorfindel/agent.py": 1}
    assert fo.totals(counts) == {"S1": 2, "S4": 1}
    [said] = fo.over_ceiling(fo.totals(counts), {"S1": 2})
    assert said.startswith("S4: 1 string(s) that read French, over its ceiling of 0")
    assert fo.over_ceiling(fo.totals(counts), {"S1": 2, "S4": 1}) == []
    [said] = fo.over_ceiling(fo.totals(counts), {"S1": 1, "S4": 1}, counts, {"glorfindel/bot.py": 1})
    assert said.startswith("S1: 2 string(s) that read French, over its ceiling of 1") and \
        said.endswith("Grew: glorfindel/bot.py 2 (was 1)")
    path = _ceiling(tmp_path, {"S1": 2}, {"glorfindel/bot.py": 2})
    assert fo.check(root, path)[0].startswith("S4: 1 string(s)")                    # a new file: refused


def test_a_file_may_take_what_another_of_its_surface_gives_up(tmp_path, own):
    """A split: bot.py held 2, gives one to bot_restore.py — S1 holds 2, and passes; one more, it fails."""
    path = _ceiling(tmp_path, {"S1": 2}, {"glorfindel/bot.py": 2})
    root = _tree(tmp_path / "t", {"glorfindel/bot.py": "X = 'la carte est lue'\n",
                                  "glorfindel/bot_restore.py": "Y = 'jamais'\n"})
    assert fo.check(root, path) == []
    (root / "glorfindel/bot_restore.py").write_text("Y = 'jamais'\nZ = 'déjà'\n", encoding="utf-8")
    [said] = fo.check(root, path)
    assert said.startswith("S1: 3 string(s) that read French, over its ceiling of 2")


def test_a_ceiling_is_lowered_never_raised_and_a_surface_at_0_leaves(tmp_path):
    assert fo.ceiling_to_lower({"S1": 2}, {"S1": 2}) == []
    [said] = fo.ceiling_to_lower({"S1": 1}, {"S1": 2})
    assert said.startswith("S1: 1 string(s) that read French, under its ceiling of 2 — lower it")
    assert fo.ceiling_to_lower({}, {"S4": 1})[0].startswith("S4: 0 string(s)")
    assert fo.lowered({"S1": 1, "S5": 5}, {"S1": 2, "S4": 3}) == {"S1": 1}    # S5 absent: it stays absent
    assert fo.lowered({"S1": 9}, {"S1": 2}) == {"S1": 2}       # a surface that grew: its ceiling holds
    path = _ceiling(tmp_path, {"S1": 3, "S4": 1}, {"glorfindel/bot.py": 3, "glorfindel/agent.py": 1})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["surfaces"] == {"S1": {"ceiling": 3, "files": {"glorfindel/bot.py": 3}},
                                "S4": {"ceiling": 1, "files": {"glorfindel/agent.py": 1}}}
    assert fo.load_ceiling(path) == {"S1": 3, "S4": 1}
    assert fo.load_files(path) == {"glorfindel/bot.py": 3, "glorfindel/agent.py": 1}
    assert fo.unknown_surfaces({"S1": 1, "S99": 2}) == ["S99: no such surface (SURFACES, scripts/french_output.py)"]


def test_a_text_read_back_that_left_its_file_is_said(tmp_path, own, monkeypatch):
    root = _tree(tmp_path, {"glorfindel/a.py": "MARK = 'Compte peut-être compromis'\n"})
    monkeypatch.setattr(fo, "READ_BACK", (("glorfindel/a.py", "Compte peut-être compromis", "why"),))
    assert fo.unfound(root) == [] and fo.count(root) == {}
    (root / "glorfindel/a.py").write_text("MARK = 'Account maybe compromised'\n", encoding="utf-8")
    [said] = fo.unfound(root)
    assert said.startswith("glorfindel/a.py: « Compte peut-être compromis » is no longer there")
    assert said.endswith("take it out of READ_BACK (scripts/french_output.py)")
    monkeypatch.setattr(fo, "READ_BACK", (("glorfindel/a.py", "Account maybe compromised", "why"),))
    assert fo.unfound(root)[0].startswith("glorfindel/a.py: « Account maybe compromised »")   # not French


def test_an_english_string_the_detector_misreads_is_listed_and_held(tmp_path, own, monkeypatch):
    sudo = "\\s*(?P<account>\\S+) : (?P<fields>TTY=.*)"
    root = _tree(tmp_path, {"glorfindel/expected_sudo.py": f"_LINE = r'{sudo}'\n"})
    assert fo.count(root) == {"glorfindel/expected_sudo.py": 1}                    # « x : y » reads French
    monkeypatch.setattr(fo, "ENGLISH", (("glorfindel/expected_sudo.py", sudo, "sudo's log line"),))
    assert fo.count(root) == {} and fo.unfound(root) == []
    (root / "glorfindel/expected_sudo.py").write_text("_LINE = r'(?P<account>\\S+): TTY'\n", encoding="utf-8")
    [said] = fo.unfound(root)
    assert said.endswith("take it out of ENGLISH (scripts/french_output.py)")
    assert all(why for *_, why in fo.ENGLISH)


def test_a_file_that_cannot_be_read_is_said_never_a_crash(tmp_path, own):
    root = _tree(tmp_path, {"glorfindel/a.py": "def (:\n", "schemas/x.json": "{not json",
                            "drills/x.yaml": "a: [\n"})
    (root / "glorfindel/b.py").write_bytes(b"X = '\xff caf\xe9 d\xe9j\xe0'\n")         # not UTF-8
    counts, unreadable = fo.scan(root)
    assert counts == {} and [u.split(":")[0] for u in unreadable] == ["drills/x.yaml", "glorfindel/a.py",
                                                                      "schemas/x.json"]
    assert all("cannot be read" in u for u in unreadable)


def test_outside_a_repository_the_walk_prunes_what_is_not_the_product(tmp_path, own):
    root = _tree(tmp_path, {"glorfindel/a.py": "X = 'déjà'\n", ".venv/lib/glorfindel/b.py": "X = 'déjà'\n",
                            ".claude/worktrees/x/glorfindel/c.py": "X = 'déjà'\n",
                            "annatar/stratus/stratus-red-team/d.py": "X = 'déjà'\n"})
    assert fo._listed_by_git(root) is None
    assert fo.count(root) == {"glorfindel/a.py": 1}


def test_the_command_says_what_the_test_says(capsys):
    assert fo.main([]) == 0
    assert "no surface over its ceiling" in capsys.readouterr().out
    assert fo.main(["--show", "glorfindel/tui.py"]) == 0 and capsys.readouterr().out == ""
