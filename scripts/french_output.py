"""ENG1a (#1184): the product's output in English — the strings that still read French, counted file by
file, under a ceiling that only comes down (the maintainer's decision, 25/11: « tout en anglais, cli,
discord, console, titre comme message, la totale »; the docs, the comments and the docstrings stay as
they are).

What is counted, in each file of the product:
- Python: each string the code writes (an f-string is one), never a docstring nor a comment;
- JavaScript: each string literal (a template is one), comments and regular expressions aside;
- HTML: each text and each attribute a reader sees, comments, styles and scripts aside;
- shell, the Makefile, the workflows: each line outside a comment;
- the rules' YAML: each value outside a `query:`.

A string reads French when it holds an accent, « », an elision (« l'IP », « n'offre »), a word only French
writes (« jamais », « aucun »), two French function words (« la carte est … ») or, outside a line of
shell, the French spacing before a colon (« Resource : »). Out of the count, by name: what the model sees
(MODEL: lots of their own, with a run end to end), the texts some code reads back (READ_BACK: they stay
French while their reader knows one language), the files that copy the product's text on purpose
(NOT_PRODUCT).

    python scripts/french_output.py                 # each file over or under its ceiling
    python scripts/french_output.py --count         # every file that still reads French, by surface
    python scripts/french_output.py --show FILE     # the strings of one file that read French
    python scripts/french_output.py --lower         # lower the ceilings to what is left (never raises one)

The ceilings: tests/unit/french_ceiling.json, by surface, a file → its count; a file absent is at 0, and
stays there. The guard: tests/unit/test_french_output.py. The convention: CONTRIBUTING.md, « The
product's output, in English ».
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
           "analysis/**", "scripts/**", "infra/**", "Makefile", ".github/workflows/*.yml")

# Out of the product: they copy its text on purpose, or are this detector.
NOT_PRODUCT = {
    "scripts/mutation_check.py": "its mutants' anchors copy the product's text, and move with it",
    "scripts/mutants/*": "the same: each lot's mutants, anchored on the product's text",
    "scripts/french_output.py": "this detector: its patterns are French by definition",
    "**/tests/**": "the tests: they compare the product's text, and follow it",
}

# What the model sees: out of ENG1's count, translated in lots of their own with a run end to end
# (CLAUDE.md, « Edit de few_shot_examples.yaml, _SYSTEM_PROMPT ou _build_user_message() »). Each entry:
# a glob, and the functions or assignments whose strings are out (None: the whole file).
MODEL = {
    "glorfindel/agent.py": ("_build_user_message", "_SYSTEM_PROMPT", "_DECISION_TOOL"),
    "glorfindel/enquiry/**": None,                # the enquiry: its prompt, its fiches, its catalogue
    "glorfindel/memory_keys.py": None,            # the verdicts, given back to the model with each cycle
    "glorfindel/memory.py": ("_cycle_to_text",),  # a past cycle, as the model reads it
    "glorfindel/few_shot_examples.yaml": None,
    "analysis/campaign_report.py": ("_SYSTEM",),  # the reports' prompts: they ask for French (ENG1k)
    "analysis/triage.py": ("_SYSTEM",),
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
    ("S11", "ENG1l", "the rules' descriptions", RULE_FILES),
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


def yaml_strings(source: str) -> list[tuple[int, str]]:
    """Each value of a rules' file outside a `query:` (line 0: the YAML reader keeps none)."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k != "query":
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            out.append((0, node))
    walk(yaml.safe_load(source))
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
    if any(match(rel, g) for g in RULE_FILES):
        return yaml_strings(source)
    return None


def read_back(rel: str, text: str) -> bool:
    """A text some code reads back: the string itself, or a part of a line of shell."""
    return any(path == rel and (said in text if is_lines(rel) else said == text) for path, said, _ in READ_BACK)


def french_in(rel: str, source: str) -> list[tuple[int, str]]:
    """The strings of a file that read French, the texts read back aside."""
    spacing = not is_lines(rel)
    return [(n, s) for n, s in (strings_of(rel, source) or [])
            if reads_french(s, spacing) and not read_back(rel, s)]


def product_files(root: Path = ROOT):
    """Each file of the product the guard reads (rel, path); a hidden directory, a cache aside."""
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")[:-1]
        if not path.is_file() or "__pycache__" in parts or "node_modules" in parts \
                or any(p.startswith(".") and p != ".github" for p in parts):
            continue
        if is_product(rel) and strings_of(rel, "") is not None:
            yield rel, path


def count(root: Path = ROOT) -> dict[str, int]:
    """Each product file that still reads French → its count."""
    out = {}
    for rel, path in product_files(root):
        if n := len(french_in(rel, path.read_text(encoding="utf-8"))):
            out[rel] = n
    return out


def unfound(root: Path = ROOT) -> list[str]:
    """Each text of READ_BACK no longer in its file, or no longer French: take it out of the list."""
    out = []
    for rel, said, _why in READ_BACK:
        path = root / rel
        texts = [s for _, s in strings_of(rel, path.read_text(encoding="utf-8")) or []] if path.is_file() else []
        if not reads_french(said) or not any(said in s if is_lines(rel) else said == s for s in texts):
            out.append(f"{rel}: « {said} » is no longer read back there — take it out of READ_BACK "
                       "(scripts/french_output.py)")
    return out


# ── the ceilings ────────────────────────────────────────────────────────────────────────────────

def load_ceiling(path: Path = CEILING) -> dict[str, dict[str, int]]:
    """The ceilings by surface, as written."""
    return json.loads(path.read_text(encoding="utf-8"))["surfaces"]


def flat(ceiling: dict[str, dict[str, int]]) -> dict[str, int]:
    return {rel: n for files in ceiling.values() for rel, n in files.items()}


def over_ceiling(counts: dict[str, int], ceiling: dict[str, int]) -> list[str]:
    """Each file over its ceiling (a file absent is at 0), said with what to do."""
    return [f"{rel}: {n} string(s) that read French, over its ceiling of {ceiling.get(rel, 0)} — write the "
            "product's output in English (CONTRIBUTING.md, « The product's output, in English »); a ceiling "
            "is never raised" for rel, n in sorted(counts.items()) if n > ceiling.get(rel, 0)]


def ceiling_to_lower(counts: dict[str, int], ceiling: dict[str, int]) -> list[str]:
    """Each file under its ceiling: its ceiling comes down to it, in the same change (the ratchet)."""
    return [f"{rel}: {counts.get(rel, 0)} string(s) that read French, under its ceiling of {cap} — lower it "
            "(python scripts/french_output.py --lower): what is in English stays so"
            for rel, cap in sorted(ceiling.items()) if counts.get(rel, 0) < cap]


def misfiled(ceiling: dict[str, dict[str, int]]) -> list[str]:
    """Each file of the ceilings under another surface than its own, or under none."""
    return [f"{rel}: under {sid}, its surface is {surface_of(rel)} (python scripts/french_output.py --lower)"
            for sid, files in ceiling.items() for rel in files if surface_of(rel) != sid]


def by_surface(counts: dict[str, int]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {sid: {} for sid, *_ in SURFACES}
    for rel, n in sorted(counts.items()):
        if (sid := surface_of(rel)) is not None:
            out[sid][rel] = n
    return out


def lowered(counts: dict[str, int], ceiling: dict[str, int]) -> dict[str, int]:
    """The ceilings, each lowered to its count, never raised; a file at 0 leaves, and stays at 0."""
    return {rel: min(cap, counts.get(rel, 0)) for rel, cap in ceiling.items() if counts.get(rel, 0)}


def write_ceiling(ceiling: dict[str, int], path: Path = CEILING) -> None:
    data = {"_": "ENG1a (#1184): each product file's strings that still read French, by surface "
                 "(scripts/french_output.py); only ever lowered, by --lower. A file absent is at 0.",
            "surfaces": {sid: files for sid, files in by_surface(ceiling).items() if files}}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def check(root: Path = ROOT, path: Path = CEILING) -> list[str]:
    """Everything the guard says: over, under, misfiled, without a surface, a text read back gone."""
    counts, ceiling = count(root), load_ceiling(path)
    return (over_ceiling(counts, flat(ceiling)) + ceiling_to_lower(counts, flat(ceiling)) + misfiled(ceiling)
            + [f"{rel}: reads French and is in no surface (SURFACES, scripts/french_output.py)"
               for rel in sorted(counts) if surface_of(rel) is None]
            + unfound(root))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The product's strings that still read French (ENG1a).")
    ap.add_argument("--count", action="store_true", help="every file that still reads French, by surface")
    ap.add_argument("--show", metavar="FILE", help="the strings of one file that read French")
    ap.add_argument("--lower", action="store_true", help="lower the ceilings to what is left, never raise one")
    args = ap.parse_args(argv)
    if args.show:
        for n, s in french_in(args.show, (ROOT / args.show).read_text(encoding="utf-8")):
            print(f"{args.show}:{n}: {s!r}")
        return 0
    if args.count:
        surfaces = by_surface(count())
        for sid, lot, name, _globs in SURFACES:
            files = surfaces[sid]
            print(f"{sid} ({lot}, {name}): {sum(files.values())} in {len(files)} file(s)")
            for rel, n in files.items():
                print(f"    {n:4}  {rel}")
        return 0
    if args.lower:
        left = lowered(count(), flat(load_ceiling()))
        write_ceiling(left)
        print(f"{CEILING.relative_to(ROOT)}: {sum(left.values())} string(s) left, in {len(left)} file(s)")
        return 0
    said = check()
    print("\n".join(said) if said else "✓ no file over its ceiling, none under it")
    return 1 if said else 0


if __name__ == "__main__":
    sys.exit(main())
