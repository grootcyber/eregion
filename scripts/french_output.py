"""ENG1a (#1184): the product's output in English — the strings that still read French, counted file by
file, under a ceiling by surface that only comes down (the maintainer's decision, 25/11: « tout en
anglais, cli, discord, console, titre comme message, la totale »; the docs, the comments and the
docstrings stay as they are).

What is counted, in each file of the product:
- Python: each string the code writes (an f-string is one), never a docstring nor a comment;
- JavaScript: each string literal (a template is one), comments and regular expressions aside;
- HTML: each text and each attribute a reader sees, comments, styles and scripts aside;
- shell, the Makefile, the workflows: each line outside a comment;
- the YAML of descriptions (the rules, the scenarios, the catalogue, the drills…): each value outside a
  query (`query:`, `verify:`); the JSON schemas: each `description` and `title`.

A string reads French when it holds an accent, « », an elision (« l'IP », « n'offre »), a word only French
writes (« jamais », « aucun »), two French function words (« la carte est … ») or, outside a line of
shell, the French spacing before a colon (« Resource : »). Out of the count, by name: what the model sees
(MODEL: lots of their own, with a run end to end), the texts some code reads back (READ_BACK: they stay
French while their reader knows one language), the files that copy the product's text on purpose
(NOT_PRODUCT).

    python scripts/french_output.py                 # each surface over or under its ceiling
    python scripts/french_output.py --count         # every file that still reads French, by surface
    python scripts/french_output.py --show FILE     # the strings of one file that read French
    python scripts/french_output.py --lower         # lower the ceilings to what is left (never raises one)

The ceilings: tests/unit/french_ceiling.json, one per surface (the sum of its files, each file's count
given beside it for information); a surface absent is at 0, and stays there. A file may take what
another file of its surface gives up (a split); a surface never goes up. The files the guard reads are
the repository's (`git ls-files`, the untracked ones not ignored included). The guard:
tests/unit/test_french_output.py. The convention: CONTRIBUTING.md, « The product's output, in English ».
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CEILING = ROOT / "tests" / "unit" / "french_ceiling.json"

ACCENT = re.compile(r"[àâäçéèêëîïôöûùüÿœæÀÂÄÇÉÈÊËÎÏÔÖÛÙÜŸŒÆ«»]")
ELISION = re.compile(r"(?<![\w'’])(?:[lLdDjJnNsScCmMtT]|[qQ]u|[jJ]usqu|[lL]orsqu|[pP]uisqu)['’]"
                     r"(?=[A-Za-zàâéèêîôûœÀÂÉÈÊÎÔÛ])")
FUNCTION_WORDS = ("le", "la", "les", "des", "du", "une", "et", "est", "pour", "sans", "qui", "sur", "pas", "aux",
                  "par", "ne", "au", "ce", "ses", "leur", "un", "de", "en", "ou")
WORDS = re.compile(r"\b(?:" + "|".join(FUNCTION_WORDS) + r")\b", re.I)
# A word no English sentence holds: one is enough.
ONLY_FRENCH = re.compile(r"\b(?:jamais|rien|aucun|aucune|illisible|introuvable|seulement|toujours|avec|dans|"
                         r"mais|cette|sont|attendu|attendue|lu|lue)\b", re.I)
# The French spacing before « : », « ; », « ! », after a value, a bracket or a quote (« {vm} : … »): never
# after a word, which an aligned column of labels does too (« Engine  : », « Dry-run : »), nor before « ? »,
# which a query's parameter is.
SPACED = re.compile(r"[·)\]»”\"'`] [:;!](?:\s|$)")
# What stands for a value written into a string (an f-string's `{…}`, a template's `${…}`): neither a
# blank nor a letter, so it makes no word and no spacing of its own.
HOLE = "·"
# A section of the docs cited by its title, in “…” after its file (« docs/operations.md, “Verrou des
# dépendances” »): the docs stay French, so does the title that leads to them; it is not read.
CITED = re.compile(r"(\S+\.md(?:#[\w-]+)?),? “[^”]*”")


def reads_french(text: str, spacing: bool = True) -> bool:
    """An accent, « », an elision, a word only French writes, two French function words — or, with
    `spacing` (a string, not a line of shell), the French spacing before a colon. A title of the docs
    cited after its file is not read."""
    text = CITED.sub(r"\1", text)
    return bool(ACCENT.search(text) or ELISION.search(text) or ONLY_FRENCH.search(text)
                or len(WORDS.findall(text)) >= 2 or (spacing and SPACED.search(text)))


# ── the product, its surfaces ───────────────────────────────────────────────────────────────────

# Where the product's output lives. Every file under these, of a kind read below, is counted.
SCANNED = ("glorfindel/**", "annatar/**", "gothmog/**", "eregion_core/**", "eregion_console/**",
           "analysis/**", "scripts/**", "infra/**", "Makefile", ".github/workflows/*.yml",
           "technique_catalog.yaml", "drills/**", "schemas/**", "expectations/**")

# Out of the product: they copy its text on purpose, are another's, or are this detector.
NOT_PRODUCT = {
    "scripts/mutation_check.py": "its mutants' anchors copy the product's text, and move with it",
    "scripts/mutants/*": "the same: each lot's mutants, anchored on the product's text",
    "scripts/french_output.py": "this detector: its patterns are French by definition",
    "**/tests/**": "the tests: they compare the product's text, and follow it",
    "annatar/stratus/stratus-red-team/**": "Stratus Red Team, a public library pinned in a submodule",
    "annatar/atomics/**": "Atomic Red Team's tests, a public library pinned (annatar/atomics/PIN)",
    "infra/identities/**": "the role definitions deployed in Azure, as Terraform (out of ENG1)",
}

# A string in English that the detector takes for French: a proper name with an accent, a language's
# code… Each: the file, the string as the guard reads it, and why. Each must still be in its file, and
# still read French to the detector (tests/unit/test_french_output.py): else it leaves the list.
_CURSOR_JS = ("(() => { const c = document.getElementById('shots-cursor'); return c ? [parseFloat(c.style.left) + 2, "
              "parseFloat(c.style.top) + 2] : null; })()")
ENGLISH: tuple[tuple[str, str, str], ...] = (
    ("glorfindel/expected_sudo.py",
     '\\s*(?P<account>\\S+) : (?P<fields>(?:TTY|PWD)=.*?[ ;])COMMAND=(?P<command>.*)',
     "sudo's own log line, « account : TTY=… »: its spacing, not French"),
    ("glorfindel/providers/azure/entra_grants.py",
     "az ad app permission list-grants --id · ; az rest --method GET --url ·/servicePrincipals/·/appRoleAssignments",
     "two az commands, a shell's « ; » between them"),
    ("scripts/console_shots.py",
     "location.href + ' — ' + (typeof S !== 'undefined' ? JSON.stringify({err: S.err, planErr: S.planErr, board: "
     "!!S.board, wires: (S.wires || []).length, plan: !!S.plan, note: S.note}) : 'no S') + ' — ' + (document.body "
     "? document.body.innerText.slice(0, 200) : '')",
     "JavaScript run in the page: a ternary's « : »"),
    ("scripts/console_shots.py", "S.board.reds[·].available ? '' : (S.board.reds[·].why || 'unavailable')",
     "JavaScript run in the page: a ternary's « : »"),
    ("scripts/console_shots.py", _CURSOR_JS, "JavaScript run in the page: a ternary's « : »"),
)

# What the model sees: out of ENG1's count, translated in lots of their own with a run end to end
# (CLAUDE.md, « Edit de few_shot_examples.yaml, _SYSTEM_PROMPT ou _build_user_message() »). Each entry:
# a glob, and the functions or assignments whose strings are out (None: the whole file).
MODEL = {
    "glorfindel/agent.py": ("_build_user_message", "_SOURCE_TAGS", "_SYSTEM_PROMPT", "_DECISION_TOOL"),
    "glorfindel/enquiry/**": None,                # the enquiry: its prompt, its fiches, its catalogue
    "glorfindel/memory_keys.py": None,            # the verdicts, given back to the model with each cycle
    "glorfindel/memory.py": ("_cycle_to_text",),  # a past cycle, as the model reads it
    "glorfindel/few_shot_examples.yaml": None,
    "analysis/campaign_report.py": ("_SYSTEM",),  # the reports' prompts: they ask for French (ENG1k)
    "analysis/triage.py": ("_SYSTEM",),
    # A scenario's `hints:` go to the model in a detection_missed signal (annatar/runner/engine.py,
    # `detection_hints`), which propose_detection_rule reads; the catalogue's `name` goes into the hints
    # a generated scenario carries (annatar/campaign/synthesizer.py, `_build_hints`).
    "annatar/scenarios/**/*.yaml": ("hints",),
    "technique_catalog.yaml": ("name",),
    # The harness's sets, given to the model as they are (make llm-compare): the precedents' cycles, and
    # the smoke test's scenarios.
    "scripts/harness_precedents.py": ("CONTAINED", "CLOSED"),
    "scripts/llm_smoke.py": ("SCENARIOS",),
}

# The texts some code reads back: they stay French while their reader knows one language, and are no
# debt to lower. Each: the file, the string as the guard reads it (each `{…}` a HOLE; for a line of shell,
# a part of the line), and why. Each must still be in its file (tests/unit/test_french_output.py): the lot
# that teaches its reader English takes it out of here, with its writer.
READ_BACK = (
    ("glorfindel/escalations.py", "Compte peut-être compromis",
     "COMPROMISE_MARK: the cards already filed carry it, and are read back by it (ENG1b: both languages)"),
    ("glorfindel/response/policy.py", "zone exposée",
     "the source of a block of the exposed zone, read back by exposed_zone.py (ENG1d)"),
    ("glorfindel/response/policy.py", "zone exposée, réseau nommé « · »",
     "the same, with its named network, read back by client_network_watch.py (ENG1d)"),
    ("glorfindel/exposed_zone.py", "zone exposée", "reads the source policy.py writes (ENG1d)"),
    ("glorfindel/client_network_watch.py", "réseau nommé", "reads the source policy.py writes (ENG1d)"),
    ("glorfindel/exposed_zone.py", "adresse réservée par Azure dans le sous-réseau ·/·",
     "written by not_one_host, read back by its caller for « réservée » (ENG1d)"),
    ("glorfindel/exposed_zone.py", "adresse de réseau ou de diffusion de la zone ·",
     "written by not_one_host, read back by its caller for « diffusion » (ENG1d)"),
    ("glorfindel/exposed_zone.py", "réservée", "the reader of the two above (ENG1d)"),
    ("eregion_console/api.py", "(?i)(?:étape|step)\\s+\\d+\\s*[–\\-:]",
     "« Étape N »: the steps of the model's reasoning, which it writes in French (glorfindel.js reads them "
     "too, by a regular expression, which the guard does not count)"),
    ("glorfindel/masking.py",
     "(?<![A-Za-z0-9])((?:subscription|abonnement)s?(?:[ _-]?(?:identifier|id))?)([\\s\\\"'=:(«»/]{1,4})(",
     "the masking recognises a subscription named in either language (ENG1n)"),
    ("scripts/manuel.py",
     "[àâäçéèêëîïôöûùüÿœæ«»]|\\s[:;!?](?:\\s|$)|\\b(?:le|la|les|des|du|une|et|est|pour|dans|avec|sans|qui|sur)\\b",
     "FRENCH: the public manual's own detector of French (MAN1b)"),
    ("scripts/bench_preflight.py", "([✓⚠✗]) référence déployée : (\\S+)(?: \\(([0-9a-f]{7,40})\\))?",
     "parses make imladris-status, which deploy.sh and status.sh write (ENG1h with ENG1j)"),
    ("scripts/bench_preflight.py", "référence déployée", "the same (ENG1h with ENG1j)"),
    ("scripts/bench_preflight.py", "dernière release : (\\S+)",
     "parses make imladris-cd-status, which the CD writes (ENG1h with ENG1j)"),
    ("infra/glorfindel-host/deploy.sh", "référence déployée", "read back by bench_preflight.py (ENG1h)"),
    ("infra/glorfindel-host/status.sh", "référence déployée", "read back by bench_preflight.py (ENG1h)"),
    ("infra/glorfindel-host/cd/eregion_cd.py", "  dernière release : ·",
     "read back by bench_preflight.py (ENG1h)"),
    ("infra/glorfindel-host/cd/eregion_cd.py", "  dernière release : illisible (·)",
     "read back by bench_preflight.py (ENG1h)"),
    ("infra/glorfindel-host/cd/eregion_cd.py", "[^\\w .,:;!?'’«»()/=+-]",
     "discord_text, the CD's fallback: its whitelist of quotes widens with ENG1h, not before"),
    ("scripts/notify_discord.py", "[^\\w .,:;!?'’«»/=+-]|_",
     "_strict: its whitelist of quotes widens with ENG1o, not before"),
    ("scripts/notify_discord.py", "à faire", "STATE_TAGS: the forum's tags live on the server (ENG1o renames both)"),
    ("scripts/notify_discord.py", "bloqué", "the same"),
    ("scripts/roadmap_discord.py", "à faire", "the forum's tags, as in notify_discord.py (ENG1o)"),
    ("scripts/roadmap_discord.py", "bloqué", "the same"),
    ("scripts/roadmap_discord.py", "**Critères de la 1.0**", "read in ROADMAP.md, which stays French"),
    ("scripts/roadmap_discord.py", "État", "RELEASES_HEADER: a column of ROADMAP.md, which stays French"),
    ("scripts/identity_map.py", "dépôt", "a source of the identity map in docs/, which stays French"),
    ("scripts/identity_map.py", "dépôt, à la main", "the same"),
    ("scripts/identity_map.py", "prévue", "the same"),
    ("scripts/identity_map.py", "à la main", "the same"),
    ("scripts/identity_map.py", "## 4. D'où vient chaque ligne", "a heading of the map in docs/, which stays French"),
    ("scripts/mobile.py", "clé d'hôte", "picks the pin's line out of unit_lines' own texts (ENG1i, both together)"),
)

RULE_FILES = ("glorfindel/rules/**/*.yaml", "infra/glorfindel-host/client_rules*.yaml")
# The YAML and JSON that describe (ENG1l): the rules, the scenarios, the declared campaigns, the
# technique catalogue (the console's coverage reads it), the drills, what the watch should see, the
# faults, the schemas.
DESCRIPTION_FILES = RULE_FILES + (
    "annatar/scenarios/**/*.yaml", "annatar/campaign/declared/*.yaml", "technique_catalog.yaml",
    "drills/*.yaml", "expectations/*.yaml", "gothmog/experiments/*.yaml", "schemas/*.json")
# The keys of a description whose value is a query, never prose.
QUERY_KEYS = ("query", "verify")

# The surfaces, each with the lot that takes it (ENG1, the plan of #1184). The most precise glob that
# holds a file (the longest) gives its surface; a file that reads French in none is refused.
SURFACES = (
    ("S0", "ENG1a", "the first leftovers: the TUI, the injectors' CLI, three files of the core",
     ("glorfindel/tui.py", "annatar/**", "gothmog/**", "eregion_core/runs_layout.py",
      "eregion_core/rule_routing.py", "eregion_core/store_guard.py")),
    ("S1", "ENG1b", "the Discord bot and the cards' labels",
     ("glorfindel/bot*.py", "glorfindel/escalations.py", "glorfindel/vm_notices.py", "glorfindel/chat_text.py")),
    ("S2", "ENG1c", "the reassertion, release and cleanup cards",
     ("glorfindel/reassert*.py", "glorfindel/orphans.py", "glorfindel/dormant_isolations.py",
      "glorfindel/exposed_blocks.py", "glorfindel/drain_watch.py", "glorfindel/recovery_watch.py",
      "glorfindel/drill_watch.py", "glorfindel/response/**")),
    ("S3", "ENG1d", "the decision, budget, queue and client network cards",
     ("glorfindel/model_budget.py", "glorfindel/decision_queue.py", "glorfindel/queue_watch.py",
      "glorfindel/approval.py", "glorfindel/client_network*.py", "glorfindel/exposed_zone.py",
      "glorfindel/lateral.py", "glorfindel/correlation.py", "glorfindel/signal_origin.py",
      "glorfindel/auditd.py", "glorfindel/relaxed.py")),
    ("S4", "ENG1e", "the reasons agent.py writes, _build_user_message aside", ("glorfindel/agent.py",)),
    ("S5", "ENG1f", "the glorfindel CLI and the gestures",
     ("glorfindel/cli.py", "glorfindel/gestures.py", "glorfindel/restore_*.py", "glorfindel/jobs.py",
      "glorfindel/readiness.py", "glorfindel/audit.py")),
    ("S6", "ENG1g", "the watch's start, its logs, the config, the rules; the rest of Glorfindel and the core",
     ("glorfindel/watch/**", "glorfindel/config*.py", "glorfindel/detection_rules.py", "glorfindel/rule_*.py",
      "glorfindel/memory*.py", "glorfindel/kql.py", "glorfindel/proposed_rules.py", "glorfindel/read_budget.py",
      "eregion_core/channel_reader.py", "eregion_core/**", "glorfindel/**")),
    ("S7", "ENG1h", "Imladris's CD and the host's scripts",
     ("infra/glorfindel-host/**", "scripts/published_image.py", "scripts/harness_attest.py",
      "scripts/host_*.py")),
    ("S8", "ENG1i", "the Makefile, the operator's scripts, the rest of infra/",
     ("Makefile", "scripts/doctor.py", "scripts/mobile.py", "scripts/pair_rotate.py",
      "scripts/console_rotate.py", "scripts/agent_token.py", "scripts/identity_map.py", "scripts/adoption.py",
      "scripts/credential_expiry.py", "scripts/operator_cidr.py", "infra/**")),
    ("S9", "ENG1j", "the bench", ("scripts/bench_*.py",)),
    ("S10", "ENG1k", "the analysis reports", ("analysis/**",)),
    ("S11", "ENG1l", "the descriptions: the rules, the scenarios, the catalogue, the drills, the schemas",
     DESCRIPTION_FILES),
    ("S12", "ENG1m", "the providers: identity, the door, the dossier",
     ("glorfindel/providers/azure/entra*.py", "glorfindel/providers/azure/graph*.py",
      "glorfindel/providers/azure/door*.py", "glorfindel/providers/azure/dossier*.py",
      "glorfindel/providers/azure/recovery*.py", "glorfindel/dossier*.py", "glorfindel/door*.py")),
    ("S13", "ENG1n", "the providers: the actions' results, and the masking",
     ("glorfindel/providers/**", "glorfindel/masking.py")),
    ("S14", "ENG1o", "the lots' workshop: Discord, the release, the CI; the rest of scripts/",
     (".github/workflows/*.yml", "scripts/notify_discord.py", "scripts/agents_discord.py",
      "scripts/roadmap_discord.py", "scripts/release.py", "scripts/manuel.py", "scripts/pip_audit_issues.py",
      "scripts/review_verdict.py", "scripts/**")),
    ("SC", "Console", "the console, after LEG1 and IDT1 (its own session)", ("eregion_console/**",)),
)


def match(rel: str, pattern: str) -> bool:
    """A glob over the path: `**` crosses directories, `*` does not."""
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(rx, rel) is not None


def surface_of(rel: str) -> str | None:
    """The surface of the most precise glob that holds the file (the longest), or None."""
    held = [(len(g), sid) for sid, _lot, _name, globs in SURFACES for g in globs if match(rel, g)]
    return max(held)[1] if held else None


def _model_names(rel: str):
    for pattern, names in MODEL.items():
        if match(rel, pattern):
            return "all" if names is None else names
    return ()


def is_product(rel: str) -> bool:
    return any(match(rel, g) for g in SCANNED) and not any(match(rel, g) for g in NOT_PRODUCT)


# ── the readers, one per kind of file ───────────────────────────────────────────────────────────

def _docstrings(tree: ast.AST) -> set[int]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _named(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _under(tree: ast.AST, names) -> set[int]:
    """The nodes under the named functions or assignments (what the model sees)."""
    return {id(n) for node in ast.walk(tree) if _named(node) in names for n in ast.walk(node)}


def python_strings(source: str, model=()) -> list[tuple[int, str]]:
    """Each string the code writes (line, text): an f-string is one, its parts joined, each `{…}` a
    HOLE; never a docstring, never a string under a function or an assignment of `model`."""
    tree = ast.parse(source)
    skip = _docstrings(tree) | (_under(tree, model) if model else set())
    inner: set[int] = set()
    out = []
    for node in ast.walk(tree):
        if id(node) in skip or id(node) in inner or not isinstance(node, ast.JoinedStr):
            continue            # a format spec (`{x:.40}`) is read with its f-string, walked first
        parts = []
        for v in node.values:
            inner.add(id(v))
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
                continue
            parts.append(HOLE)
            if isinstance(v, ast.FormattedValue) and isinstance(v.format_spec, ast.JoinedStr):
                inner.update(id(x) for x in ast.walk(v.format_spec))
        out.append((node.lineno, "".join(parts)))
    for node in ast.walk(tree):
        if id(node) not in skip and id(node) not in inner and isinstance(node, ast.Constant) \
                and isinstance(node.value, str):
            out.append((node.lineno, node.value))
    return sorted(out)


# Before a `/`, what makes it a regular expression's start rather than a division.
_REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^") | {""}
_REGEX_WORDS = ("return", "typeof", "case", "do", "else", "in", "of", "void", "yield", "await")


class _Js:
    """A script read once, left to right: its strings, its comments, its regular expressions, its
    templates (a template inside a `${…}` read on its own)."""

    def __init__(self, source: str):
        self.src, self.n = source, len(source)
        self.out: list[tuple[int, str]] = []
        self.templates: list[list] = []     # each open template: [its line, its parts, the depth in `${`]
        self.last = ""                      # the last significant token of code, for a `/`

    def line(self, k: int) -> int:
        return self.src.count("\n", 0, k) + 1

    def template(self, k: int) -> int:
        """A template's text from k to its end or its next `${`; where the code resumes."""
        src, top = self.src, self.templates[-1]
        while k < self.n:
            if src[k] == "\\":
                top[1].append(src[k:k + 2])
                k += 2
            elif src[k] == "`":
                break
            elif src.startswith("${", k):
                top[1].append(HOLE)
                top[2] = 1
                return k + 2
            else:
                top[1].append(src[k])
                k += 1
        line, parts, _ = self.templates.pop()
        self.out.append((line, "".join(parts)))
        return k + 1

    def quoted(self, i: int) -> int:
        src, q, j = self.src, self.src[i], i + 1
        while j < self.n and src[j] not in (q, "\n"):
            j += 2 if src[j] == "\\" else 1
        self.out.append((self.line(i), re.sub(r"\\(['\"`\\])", r"\1", src[i + 1:j])))
        return j + 1

    def regex(self, i: int) -> int:
        src, j, klass = self.src, i + 1, False
        while j < self.n and src[j] != "\n":
            if src[j] == "\\":
                j += 2
                continue
            if src[j] in "[]":
                klass = src[j] == "["
            elif src[j] == "/" and not klass:
                break
            j += 1
        return j + 1

    def word(self, i: int) -> int:
        j = i
        while j < self.n and (self.src[j].isalnum() or self.src[j] in "_$"):
            j += 1
        self.last = self.src[i:j] if self.src[i:j] in _REGEX_WORDS else "a"
        return j

    def read(self) -> list[tuple[int, str]]:
        src, i = self.src, 0
        while i < self.n:
            c = src[i]
            if src.startswith("//", i):
                j = src.find("\n", i)
                i = self.n if j < 0 else j
            elif src.startswith("/*", i):
                j = src.find("*/", i + 2)
                i = self.n if j < 0 else j + 2
            elif c in "'\"":
                i, self.last = self.quoted(i), "a"
            elif c == "`":
                self.templates.append([self.line(i), [], 0])
                i, self.last = self.template(i + 1), "a"
            elif c == "/" and (self.last in _REGEX_AFTER or self.last in _REGEX_WORDS):
                i, self.last = self.regex(i), "a"
            elif self.templates and self.templates[-1][2] and c in "{}":
                self.templates[-1][2] += 1 if c == "{" else -1
                i += 1
                if self.templates[-1][2] == 0:
                    i, self.last = self.template(i), "a"
                else:
                    self.last = c
            elif c.isalnum() or c in "_$":
                i = self.word(i)
            else:
                self.last = self.last if c.isspace() else c
                i += 1
        return sorted(self.out)


def js_strings(source: str) -> list[tuple[int, str]]:
    """Each string literal of a script (line, text), comments and regular expressions aside; a template
    is one string, each `${…}` a HOLE."""
    return _Js(source).read()


class _Html(HTMLParser):
    SEEN = ("title", "placeholder", "aria-label", "alt", "value", "label")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[tuple[int, str]] = []
        self._raw = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._raw += 1
        self.out += [(self.getpos()[0], v) for name, v in attrs if name in self.SEEN and v]

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._raw:
            self._raw -= 1

    def handle_data(self, data):
        if not self._raw and data.strip():
            self.out.append((self.getpos()[0], data.strip()))


def html_strings(source: str) -> list[tuple[int, str]]:
    """Each text and each attribute a reader sees (line, text); comments, styles and scripts aside."""
    p = _Html()
    p.feed(source)
    return p.out


def _strip_comment(line: str) -> str:
    """A line of shell, Makefile or YAML without its comment: a `#` outside quotes, at the start or after
    a blank."""
    quote = None
    for i, c in enumerate(line):
        if quote:
            quote = None if c == quote else quote
        elif c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def line_strings(source: str) -> list[tuple[int, str]]:
    """Each line outside a comment (line, text): shell, the Makefile, a workflow."""
    return [(n, s) for n, line in enumerate(source.splitlines(), 1) if (s := _strip_comment(line)).strip()]


def yaml_strings(source: str, skip=()) -> list[tuple[int, str]]:
    """Each value of a description's YAML outside a query (QUERY_KEYS) and the keys of `skip` (what the
    model sees); line 0: the YAML reader keeps none."""
    out = []
    skipped = set(QUERY_KEYS) | set(skip)

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k not in skipped:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            out.append((0, node))
    walk(yaml.safe_load(source))
    return out


def json_strings(source: str) -> list[tuple[int, str]]:
    """Each `description` and `title` of a JSON schema (line 0)."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("description", "title") and isinstance(v, str):
                    out.append((0, v))
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(json.loads(source) if source.strip() else {})
    return out


def is_lines(rel: str) -> bool:
    """A file read line by line: shell, the Makefile, a workflow."""
    return rel.endswith((".sh", ".bash")) or rel == "Makefile" or rel.startswith(".github/workflows/")


def strings_of(rel: str, source: str) -> list[tuple[int, str]] | None:
    """The strings of a file the guard reads, or None for a kind it does not read."""
    model = _model_names(rel)
    if rel.endswith(".py"):
        return [] if model == "all" else python_strings(source, model)
    if rel.endswith(".js"):
        return js_strings(source)
    if rel.endswith(".html"):
        return html_strings(source)
    if is_lines(rel):
        return line_strings(source)
    if any(match(rel, g) for g in DESCRIPTION_FILES):
        if model == "all":
            return []
        return json_strings(source) if rel.endswith(".json") else yaml_strings(source, model)
    return None


def _listed(rel: str, text: str, entries) -> bool:
    """`text` of `rel` among `entries`: the string itself, or a part of a line of shell."""
    return any(path == rel and (said in text if is_lines(rel) else said == text) for path, said, _ in entries)


def read_back(rel: str, text: str) -> bool:
    """A text some code reads back (READ_BACK)."""
    return _listed(rel, text, READ_BACK)


def french_in(rel: str, source: str) -> list[tuple[int, str]]:
    """The strings of a file that read French, the texts read back and the English ones listed aside."""
    spacing = not is_lines(rel)
    return [(n, s) for n, s in (strings_of(rel, source) or [])
            if reads_french(s, spacing) and not read_back(rel, s) and not _listed(rel, s, ENGLISH)]


# The directories a walk of the disk never enters, when git does not list the files.
_PRUNED = {".git", ".venv", "venv", ".claude", "node_modules", "__pycache__"}


def _listed_by_git(root: Path) -> list[str] | None:
    """The repository's files (tracked, and untracked ones not ignored), or None outside a repository."""
    import subprocess
    try:
        res = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
                              "--exclude-standard"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return sorted({p for p in res.stdout.decode("utf-8", "surrogateescape").split("\0") if p})


def _walked(root: Path) -> list[str]:
    """The files under `root`, its hidden directories, venvs and caches pruned (outside a repository)."""
    import os
    out = []
    for top, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _PRUNED and not (d.startswith(".") and d != ".github"))
        out += [(Path(top) / f).relative_to(root).as_posix() for f in files]
    return sorted(out)


def product_files(root: Path = ROOT):
    """Each file of the product the guard reads (rel, path): the repository's, by git (`--others`: a new
    file counts before its `git add`); a walk of the disk outside a repository."""
    listed = _listed_by_git(root)
    for rel in (_walked(root) if listed is None else listed):
        path = root / rel
        if is_product(rel) and strings_of(rel, "") is not None and path.is_file() and not path.is_symlink():
            yield rel, path


def read(path: Path) -> str:
    """A file's text: a byte that is not UTF-8 replaced, never a crash."""
    return path.read_bytes().decode("utf-8", errors="replace")


def scan(root: Path = ROOT) -> tuple[dict[str, int], list[str]]:
    """(each product file that still reads French → its count, each file that cannot be read and why)."""
    counts, unreadable = {}, []
    for rel, path in product_files(root):
        try:
            n = len(french_in(rel, read(path)))
        except (SyntaxError, ValueError, yaml.YAMLError) as exc:      # a JSON error is a ValueError
            unreadable.append(f"{rel}: cannot be read ({type(exc).__name__}) — never counted, fix it")
            continue
        if n:
            counts[rel] = n
    return counts, unreadable


def count(root: Path = ROOT) -> dict[str, int]:
    """Each product file that still reads French → its count."""
    return scan(root)[0]


def unfound(root: Path = ROOT) -> list[str]:
    """Each text of READ_BACK or of ENGLISH no longer in its file, or no longer French to the detector:
    take it out of its list."""
    out = []
    for name, entries in (("READ_BACK", READ_BACK), ("ENGLISH", ENGLISH)):
        for rel, said, _why in entries:
            path = root / rel
            texts = [s for _, s in strings_of(rel, read(path)) or []] if path.is_file() else []
            if not reads_french(said) or not any(said in s if is_lines(rel) else said == s for s in texts):
                out.append(f"{rel}: « {said} » is no longer there, or no longer reads French — take it out "
                           f"of {name} (scripts/french_output.py)")
    return out


# ── the ceilings, one per surface ───────────────────────────────────────────────────────────────

def load_ceiling(path: Path = CEILING) -> dict[str, int]:
    """Each surface's ceiling, as written (a surface absent is at 0)."""
    return {sid: s["ceiling"] for sid, s in json.loads(path.read_text(encoding="utf-8"))["surfaces"].items()}


def load_files(path: Path = CEILING) -> dict[str, int]:
    """Each file's count when the ceilings were last written: for information, never a ceiling."""
    return {rel: n for s in json.loads(path.read_text(encoding="utf-8"))["surfaces"].values()
            for rel, n in s.get("files", {}).items()}


def by_surface(counts: dict[str, int]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {sid: {} for sid, *_ in SURFACES}
    for rel, n in sorted(counts.items()):
        if (sid := surface_of(rel)) is not None:
            out[sid][rel] = n
    return out


def totals(counts: dict[str, int]) -> dict[str, int]:
    """Each surface → the strings of its files that still read French."""
    return {sid: n for sid, files in by_surface(counts).items() if (n := sum(files.values()))}


def over_ceiling(total: dict[str, int], ceiling: dict[str, int], counts=None, files=None) -> list[str]:
    """Each surface over its ceiling (a surface absent is at 0), with the files that grew since the
    ceilings were written."""
    out = []
    for sid, n in sorted(total.items()):
        if n > ceiling.get(sid, 0):
            grew = [f"{rel} {k} (was {(files or {}).get(rel, 0)})" for rel, k in by_surface(counts or {})[sid].items()
                    if k > (files or {}).get(rel, 0)]
            out.append(f"{sid}: {n} string(s) that read French, over its ceiling of {ceiling.get(sid, 0)} — "
                       "write the product's output in English (CONTRIBUTING.md, « The product's output, in "
                       "English »); a ceiling is never raised" + (f". Grew: {', '.join(grew)}" if grew else ""))
    return out


def ceiling_to_lower(total: dict[str, int], ceiling: dict[str, int]) -> list[str]:
    """Each surface under its ceiling: its ceiling comes down to it, in the same change (the ratchet)."""
    return [f"{sid}: {total.get(sid, 0)} string(s) that read French, under its ceiling of {cap} — lower it "
            "(python scripts/french_output.py --lower): what is in English stays so"
            for sid, cap in sorted(ceiling.items()) if total.get(sid, 0) < cap]


def unknown_surfaces(ceiling: dict[str, int]) -> list[str]:
    known = {sid for sid, *_ in SURFACES}
    return [f"{sid}: no such surface (SURFACES, scripts/french_output.py)" for sid in sorted(ceiling)
            if sid not in known]


def lowered(total: dict[str, int], ceiling: dict[str, int]) -> dict[str, int]:
    """The ceilings, each lowered to its surface's count, never raised; a surface at 0 leaves, and stays
    at 0; a surface absent stays absent."""
    return {sid: low for sid, cap in ceiling.items() if (low := min(cap, total.get(sid, 0)))}


def write_ceiling(ceiling: dict[str, int], counts: dict[str, int], path: Path = CEILING) -> None:
    """The ceilings by surface, each with its files' counts beside it, for information."""
    files = by_surface(counts)
    data = {"_": "ENG1a (#1184): one ceiling per surface, the strings of its files that still read French "
                 "(scripts/french_output.py); only ever lowered, by --lower. A surface absent is at 0. The "
                 "files' counts are for information: a file may take what another of its surface gives up.",
            "surfaces": {sid: {"ceiling": ceiling[sid], "files": files.get(sid, {})}
                         for sid, *_ in SURFACES if sid in ceiling}}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def check(root: Path = ROOT, path: Path = CEILING) -> list[str]:
    """Everything the guard says: a surface over or under, a surface unknown, a file without a surface,
    a file unreadable, a text listed that left."""
    counts, unreadable = scan(root)
    ceiling, files, total = load_ceiling(path), load_files(path), totals(counts)
    return (over_ceiling(total, ceiling, counts, files)
            + ceiling_to_lower(total, ceiling) + unknown_surfaces(ceiling)
            + [f"{rel}: reads French and is in no surface (SURFACES, scripts/french_output.py)"
               for rel in sorted(counts) if surface_of(rel) is None]
            + unreadable + unfound(root))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The product's strings that still read French (ENG1a).")
    ap.add_argument("--count", action="store_true", help="every file that still reads French, by surface")
    ap.add_argument("--show", metavar="FILE", help="the strings of one file that read French")
    ap.add_argument("--lower", action="store_true", help="lower the ceilings to what is left, never raise one")
    args = ap.parse_args(argv)
    if args.show:
        for n, s in french_in(args.show, read(ROOT / args.show)):
            print(f"{args.show}:{n}: {s!r}")
        return 0
    if args.count:
        surfaces, ceiling = by_surface(count()), load_ceiling()
        for sid, lot, name, _globs in SURFACES:
            files = surfaces[sid]
            print(f"{sid} ({lot}, {name}): {sum(files.values())} in {len(files)} file(s), "
                  f"ceiling {ceiling.get(sid, 0)}")
            for rel, n in files.items():
                print(f"    {n:4}  {rel}")
        return 0
    if args.lower:
        counts = count()
        left = lowered(totals(counts), load_ceiling())
        write_ceiling(left, counts)
        print(f"{CEILING.relative_to(ROOT)}: {sum(left.values())} string(s) left, in {len(left)} surface(s)")
        return 0
    said = check()
    print("\n".join(said) if said else "✓ no surface over its ceiling, none under it")
    return 1 if said else 0


if __name__ == "__main__":
    sys.exit(main())
