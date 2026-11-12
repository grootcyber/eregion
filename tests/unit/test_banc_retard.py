"""ING5 (#758): the bench protocol of the lateness of each source (docs/banc-retard.md).

The design of ING1 (docs/design/mesure-en-retard.md, §10) lists the hypotheses RH1 to RH12; the
protocol gives each one its section, its query, its window in absolute dates, its deadline when its
data leaves first, and what confirms it, refutes it, and where its result goes. Nothing here runs a
query: the page is read as text.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "docs" / "banc-retard.md"
DESIGN = ROOT / "docs" / "design" / "mesure-en-retard.md"
RECORD = ROOT / "docs" / "design" / "dossier-isolation.md"

_spec = importlib.util.spec_from_file_location("doc_anchors", ROOT / "scripts" / "doc_anchors.py")
doc_anchors = importlib.util.module_from_spec(_spec)
sys.modules["doc_anchors"] = doc_anchors
_spec.loader.exec_module(doc_anchors)

TEXT = PROTOCOL.read_text(encoding="utf-8")
# The columns that carry an identifier: never projected nor grouped by in a query of the page.
IDENTIFIERS = ("_ResourceId", "ResourceId", "Computer", "CorrelationId", "Caller", "CallerIpAddress",
               "AccountName", "SubscriptionId", "TenantId", "HostIP", "HostName", "OperationId")
GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
IPV4 = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def _design_hypotheses() -> list[str]:
    """The RH of the design's §10 table, in its order."""
    section = DESIGN.read_text(encoding="utf-8").split("## 10.", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\| \*\*(RH\d+)\*\* \|", section, re.M)


def _sections() -> dict[str, str]:
    """Each `## ` section of the protocol, by its heading."""
    parts = re.split(r"^## ", TEXT, flags=re.M)[1:]
    return {p.split("\n", 1)[0]: p for p in parts}


def _section_of(rh: str) -> str:
    found = [body for head, body in _sections().items() if re.search(rf"\b{rh}\b", head)]
    assert len(found) == 1, f"{rh} : {len(found)} section(s) dont le titre le nomme"
    return found[0]


def _queries(text: str) -> list[str]:
    """The KQL of the page: each body written by a `<<'KQL'` heredoc."""
    return [body for _, body in _named_queries(text)]


def _named_queries(text: str) -> list[tuple[str, str]]:
    """Each KQL heredoc with the name of its file (`cat > ${RET}/<name>.kql <<'KQL'`)."""
    return re.findall(r"cat > \$\{RET\}/([\w-]+)\.kql <<'KQL'\n(.*?)\nKQL\n", text, re.S)


# The bodies whose bounds come before them, written by a shell line: `rh <body> <name> <vm> <dates>`
# for the quarantines, the moment the lines were sent for RH9.
SHARED_BODIES = ("phases", "tranches")


def test_the_design_lists_twelve_hypotheses():
    assert _design_hypotheses() == [f"RH{n}" for n in range(1, 13)]


@pytest.mark.parametrize("rh", [f"RH{n}" for n in range(1, 13)])
def test_every_hypothesis_of_the_design_has_its_section_its_measure_and_its_verdict(rh):
    body = _section_of(rh)
    assert "```zsh" in body, f"{rh} : aucune commande"
    lowered = body.lower()
    for said in ("tient si", "tombe si", "si elle tombe", "reporter"):
        assert said in lowered, f"{rh} : « {said} » manque"
    assert "#758" in body, f"{rh} : son résultat ne va nulle part"


@pytest.mark.parametrize("rh", [f"RH{n}" for n in range(1, 12 + 1) if n not in (9, 10)])
def test_every_read_on_kept_data_has_its_query_and_an_absolute_window(rh):
    body = _section_of(rh)
    queries = _named_queries(body)
    assert queries, f"{rh} : aucune requête"
    for name, query in queries:
        # Each query bounds its own lines by a date, or is a shared body whose `rh` calls give them.
        assert "datetime(2026-" in query or name in SHARED_BODIES, f"{rh} : {name} sans date absolue\n{query}"
    for name in SHARED_BODIES:
        if any(n == name for n, _ in queries):
            calls = re.findall(rf"^rh {name} +[\w-]+ +vm-celebrimbor-\w+((?: +2026-\d\d-\d\dT\d\d:\d\d:\d\dZ){{3}})$", body, re.M)
            assert calls, f"{rh} : le corps {name} sans ses bornes"
    # A shared body used in another section has its calls here.
    for name in SHARED_BODIES:
        if re.search(rf"^rh {name} ", body, re.M):
            assert re.findall(rf"^rh {name} .*2026-\d\d-\d\dT", body, re.M)


def test_rh9_is_a_gesture_whose_read_is_anchored_on_the_moment_it_was_sent():
    body = _section_of("RH9")
    assert "run-command invoke" in body and "/dev/log" in body
    assert 'datetime(${SENT})' in body and "sent - 4h" in body


def test_rh10_waits_for_ing3_and_reads_the_rules_as_the_watch_runs_them():
    body = _section_of("RH10")
    assert "ING3" in body and "rules check --live" in body


def test_only_the_estimate_of_rh10_reads_a_relative_window():
    """Every other query bounds its lines by dates: run on 8 December, it reads the same lines."""
    for head, body in _sections().items():
        if re.search(r"\bRH10\b", head):
            continue
        for query in _queries(body):
            assert "ago(" not in query, f"{head} : une fenêtre relative\n{query}"


def test_the_four_first_come_first_in_the_order_the_retention_imposes():
    order = _sections()["L'ordre et les échéances"]
    assert "RH5, RH3, RH4, puis RH6 d'abord" in order
    rows = [r for r in order.splitlines() if r.startswith("| ")]
    first = {rh: next(i for i, r in enumerate(rows) if f"**{rh}**" in r) for rh in ("RH5", "RH3", "RH4", "RH6")}
    assert first["RH5"] < first["RH3"] < first["RH4"] < first["RH6"]
    # The others come after the four.
    # By the « Quoi » cell: a deadline may name another hypothesis.
    later = [i for i, r in enumerate(rows) if re.search(r"\bRH(1|2|7|8|11|12)\b", r.split("|")[2])]
    assert later and min(later) > first["RH6"]
    # The deadlines the design gives: 09/12 (the T1486 of 09/11), 10/12 (bree's quarantine), 11/12 (the lift).
    for date in ("09/12", "10/12", "11/12"):
        assert date in order


@pytest.mark.parametrize("rh", ["RH3", "RH4", "RH5", "RH6"])
def test_the_reads_whose_data_leaves_first_say_their_deadline(rh):
    assert "au plus tard" in _section_of(rh).lower()


def test_the_isolation_record_s_dh2_and_dh11_join_the_sitting():
    sections = _sections()
    joined = next(body for head, body in sections.items() if "DH2" in head and "DH11" in head)
    assert "### DH11" in joined and "### DH2" in joined and "#727" in joined
    assert "az backup job list" in joined


def _stages(query: str) -> list[str]:
    """The pipe stages of a query, comments removed: a stage runs from one `|` to the next."""
    code = "\n".join(line.split("//", 1)[0] for line in query.splitlines())
    return [s.strip() for s in re.split(r"\n\s*\|", "\n" + code) if s.strip()]


def test_every_query_ends_by_choosing_what_it_shows():
    """The last stage that shapes the rows (past an `order by`, a `where` on the result) is a
    `project`, a `summarize` or a `print`: a query that ends on a filter returns every column."""
    for name, query in _named_queries(TEXT):
        stages = _stages(query)
        while stages and re.match(r"(order|sort) by\b|where\b", stages[-1]):
            stages.pop()
        assert stages and re.match(r"(project|summarize|print)\b", stages[-1]), f"{name} :\n{query}"


def test_no_query_shows_every_column():
    for name, query in _named_queries(TEXT):
        for stage in _stages(query):
            if re.match(r"(project|summarize)\b", stage):
                assert "*" not in stage, f"{name} : « * »\n{stage}"


def test_a_union_names_each_line_s_table_by_its_type():
    """`withsource` names a parenthesised argument « union_arg0 », not its table: a union with one
    reads the table from `Type`, the column every table carries."""
    for name, query in _named_queries(TEXT):
        code = "\n".join(line.split("//", 1)[0] for line in query.splitlines())
        if re.search(r"union\b[^\n]*\n?\s*\(", code):
            assert "withsource" not in code, f"{name} : withsource sur une parenthèse"
            if re.search(r"\bTable\b", code):
                assert "extend Table = Type" in code, f"{name} : la table de la ligne n'est pas lue"


def test_no_query_returns_an_identifier():
    """A projected or grouped-by column of the page is never one that names a resource or a caller."""
    queries = _queries(TEXT)
    assert len(queries) >= 15
    for query in queries:
        for stage in _stages(query):
            if stage.startswith("project-away"):
                continue
            if stage.startswith("project "):
                shown = stage[len("project "):]
            elif stage.startswith("summarize"):
                shown = stage.split(" by ", 1)[1] if " by " in stage else ""
            else:
                continue
            for column in IDENTIFIERS:
                assert not re.search(rf"(?<![\w.]){column}\b(?!\s*=)", shown), f"{column} rendu :\n{stage}"


def test_the_az_reads_show_no_identifier():
    """The `--query` of an az read keeps fields that name nothing; one that reads an id or a job's
    name puts it in a variable, never on the screen."""
    for projection in re.findall(r'--query "(\[[^"]*)"', TEXT):
        assert "resourceId" not in projection and "caller" not in projection.lower(), projection
    commands = re.sub(r"\\\n\s*", " ", TEXT).splitlines()
    reading_an_id = [c for c in commands if re.search(r'--query (id\b|"[^"]*\]\.name\b)', c)]
    assert len(reading_an_id) >= 2
    for command in reading_an_id:
        assert re.match(r"\s*[A-Z]+=\$\(", command), command


def test_dh11_never_reads_an_absence_as_a_refutation():
    joined = next(body for head, body in _sections().items() if "DH2" in head and "DH11" in head)
    dh11 = joined.split("### DH11", 1)[1].split("### DH2", 1)[0]
    assert "tasksList" in dh11 and "Take Snapshot" in dh11
    assert "**Illisible**, jamais « tombe »" in dh11


def test_the_page_carries_no_real_identifier():
    assert not GUID.search(TEXT)
    assert not IPV4.search(TEXT)


def test_the_page_names_the_host_imladris():
    """H0 only as « anciennement H0 », at the first mention of Imladris (IML1, scripts/host_name.py)."""
    assert re.findall(r"\bH0\b", TEXT) == ["H0"]
    assert "Imladris (anciennement H0)" in TEXT


def test_the_design_and_the_record_lead_to_the_protocol():
    design = DESIGN.read_text(encoding="utf-8")
    section_10 = design.split("## 10.", 1)[1].split("\n## 11.", 1)[0]
    section_11 = design.split("## 11.", 1)[1].split("\n## 12.", 1)[0]
    assert "](../banc-retard.md)" in section_10 and "](../banc-retard.md)" in section_11
    assert "](../banc-retard.md)" in RECORD.read_text(encoding="utf-8")


def test_every_internal_link_of_the_protocol_resolves():
    assert doc_anchors.broken(PROTOCOL) == []
