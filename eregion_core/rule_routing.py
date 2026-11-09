"""What a detection rule's rows can be routed by, read in its query (SEC-A4, V-04).

A row of the data plane goes to the VM it names: its `_ResourceId` (or `ResourceId`), which
Azure writes, or the private address that made a call (`CallerIpAddress`, a storage call made
from a VM, which the storage service writes). Never by `Computer`: root on a VM chooses its host
name, and a row routed by it made Glorfindel isolate or block in another VM's name (V-04). A rule
whose rows carry neither key would route nothing: refused at load, approval included.

`routing_columns(query)` reads the query's last statement, stage by stage, and keeps the set of
these keys its rows are sure to carry: a table carries `_ResourceId`; a `project`, a `summarize`,
a `distinct`, a `project-keep` keep only what they name; a `project-away`, a `project-rename`
drop what they name; an `extend` (or an assignment) that writes a key from anything but itself
drops it — `extend _ResourceId = Computer` routes by the host name again. An operator it does not
know, a source it cannot read (a `datatable`, a `print`, an `evaluate`), a string not closed: the
empty set — refused, never assumed. A reading of the text, not KQL's parser: a query it refuses
can be one Log Analytics would run (rewrite it with a `project` that names `_ResourceId`).
"""
from __future__ import annotations

import fnmatch
import re

# What a row is routed by (detection_rules.RowAttribution): the resource Azure wrote, then the
# address that made the call.
RESOURCE_COLUMNS = ("_ResourceId", "ResourceId")
CALLER_COLUMNS = ("CallerIpAddress",)
ROUTING_COLUMNS = frozenset(RESOURCE_COLUMNS + CALLER_COLUMNS)

# Every table of Log Analytics carries `_ResourceId`, its standard column.
_TABLE = frozenset({"_ResourceId"})
_NONE: frozenset = frozenset()

# Stages that keep every column (they filter, order, add): an `extend`, a `parse` may still
# overwrite a key, read below.
_KEEP = frozenset({
    "where", "filter", "order", "sort", "take", "limit", "top", "sample", "serialize", "as",
    "render", "mv-expand", "mv-apply", "parse", "parse-where", "parse-kv", "extend",
    "project-reorder", "lookup", "join",
})
# Of those, the ones that may write a column of their own (`parse … with _ResourceId:string`).
_WRITES = frozenset({"parse", "parse-where", "parse-kv", "mv-expand", "mv-apply", "serialize"})
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WORD = re.compile(r"(?<![\w.$])[A-Za-z_][A-Za-z0-9_]*")
_OP = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*)")
_NOT_COLUMNS = frozenset({"and", "or", "true", "false", "null", "asc", "desc", "nulls", "first", "last"})


class Unreadable(ValueError):
    """The query's text cannot be read (a string or a comment not closed)."""


def mask(query: str) -> str:
    """The query without its comments, each string emptied (`""`): a `|`, a `;`, a column's name
    inside a string or a regex is never read as the query's."""
    out: list[str] = []
    i, n = 0, len(query)
    while i < n:
        c = query[i]
        if query.startswith("//", i):
            end = query.find("\n", i)
            i = n if end < 0 else end
            continue
        if query.startswith("```", i):
            end = query.find("```", i + 3)
            if end < 0:
                raise Unreadable("chaîne ``` non fermée")
            out.append('""')
            i = end + 3
            continue
        if c in "@" and i + 1 < n and query[i + 1] in "\"'":
            q, j = query[i + 1], i + 2
            while True:
                end = query.find(q, j)
                if end < 0:
                    raise Unreadable("chaîne verbatim non fermée")
                if end + 1 < n and query[end + 1] == q:     # a doubled quote, inside
                    j = end + 2
                    continue
                break
            out.append('""')
            i = end + 1
            continue
        if c in "\"'":
            j = i + 1
            while j < n and query[j] != c:
                if query[j] == "\\":
                    j += 1
                elif query[j] == "\n":
                    raise Unreadable("chaîne non fermée")
                j += 1
            if j >= n:
                raise Unreadable("chaîne non fermée")
            out.append('""')
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def split_top(text: str, sep: str) -> list[str]:
    """`text` split on `sep` outside any parenthesis, bracket or brace."""
    parts, depth, start = [], 0, 0
    for i, c in enumerate(text):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def _assignment(item: str) -> tuple[str, str] | None:
    """(name, expression) of `Name = expr` at the top level, else None (`==`, `!=`, `=~`, `<=`
    and `>=` are no assignment)."""
    depth = 0
    for i, c in enumerate(item):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "=" and depth == 0:
            before = item[i - 1] if i else ""
            after = item[i + 1] if i + 1 < len(item) else ""
            if before in "=!<>~" or after in "=~":
                continue
            name = item[:i].strip()
            return (name, item[i + 1:].strip()) if _IDENT.match(name) else None
    return None


def _columns_read(expr: str) -> set[str]:
    """The columns an expression reads: its words, but the functions it calls."""
    out = set()
    for m in _WORD.finditer(expr):
        rest = expr[m.end():].lstrip()
        if rest.startswith("(") or m.group(0).lower() in _NOT_COLUMNS:
            continue
        out.add(m.group(0))
    return out


def _passes_through(name: str, expr: str) -> bool:
    """A key written from itself alone (`CallerIpAddress = tostring(split(CallerIpAddress, ":")[0])`,
    `_ResourceId = take_any(_ResourceId)`) — never from another column (`_ResourceId = Computer`)."""
    return _columns_read(expr) == {name}


def _named(items: list[str]) -> tuple[set[str], bool]:
    """(the keys these items output, whether one of them is `*`): `Key`, or `Key = <itself>`."""
    out, star = set(), False
    for raw in items:
        item = raw.strip()
        if item == "*":
            star = True
            continue
        a = _assignment(item)
        if a is not None:
            if a[0] in ROUTING_COLUMNS and _passes_through(*a):
                out.add(a[0])
        elif item in ROUTING_COLUMNS:
            out.add(item)
    return out, star


def _by(rest: str) -> tuple[str, str]:
    """A summarize's aggregates and its `by` keys."""
    depth = 0
    for m in re.finditer(r"[()\[\]{}]|\bby\b", rest):
        t = m.group(0)
        if t in "([{":
            depth += 1
        elif t in ")]}":
            depth -= 1
        elif depth == 0:
            return rest[:m.start()], rest[m.end():]
    return rest, ""


_KEEP_ALL_AGG = re.compile(r"^(arg_max|arg_min|take_any|any)\s*\((.*)\)\s*$", re.S)


def _summarize(rest: str, have: frozenset) -> frozenset:
    aggs, keys = _by(rest)
    out, _ = _named(split_top(keys, ",") if keys.strip() else [])
    for raw in split_top(aggs, ","):
        item = raw.strip()
        a = _assignment(item)
        if a is not None:
            if a[0] in ROUTING_COLUMNS and _passes_through(*a):
                out.add(a[0])
            continue
        m = _KEEP_ALL_AGG.match(item)
        if not m:
            continue                          # count(), max(x)…: a column of its own name
        args = [x.strip() for x in split_top(m.group(2), ",")]
        kept = args[1:] if m.group(1).startswith("arg_") else args
        if "*" in kept:
            out |= have                       # every column of the row it picks
        if m.group(1).startswith("arg_"):     # arg_max(T, _ResourceId): named as it is
            out |= {k for k in kept if k in ROUTING_COLUMNS}
    return frozenset(out)


def _matching(patterns: list[str], have: frozenset) -> set[str]:
    pats = [p.strip() for p in patterns if p.strip()]
    return {c for c in have | ROUTING_COLUMNS for p in pats if fnmatch.fnmatchcase(c, p)}


def _source(head: str, lets: dict[str, str], depth: int) -> frozenset:
    head = head.strip()
    if head.startswith("(") and head.endswith(")"):
        return _columns(head[1:-1], lets, depth + 1)
    if _IDENT.match(head):
        if head in lets:
            return _columns(lets[head], lets, depth + 1)
        return _TABLE
    m = _OP.match(head)
    if m and m.group(1) == "union":
        operands = [x.strip() for x in split_top(head[m.end():], ",")]
        operands = [x for x in operands if not x.startswith(("kind", "withsource", "isfuzzy"))]
        if operands and all(_IDENT.match(x) and x not in lets for x in operands):
            return _TABLE
    return _NONE


def _columns(expr: str, lets: dict[str, str], depth: int = 0) -> frozenset:
    if depth > 8:
        return _NONE
    stages = split_top(expr, "|")
    have = _source(stages[0], lets, depth)
    for stage in stages[1:]:
        m = _OP.match(stage)
        if not m:
            return _NONE
        op, rest = m.group(1).lower(), stage[m.end():]
        if op == "join" and re.search(r"\bkind\s*=\s*right(anti|semi)\b", rest):
            return _NONE                      # the right side's rows: not read
        if op == "extend":
            items = [_assignment(x.strip()) for x in split_top(rest, ",")]
            for a in items:
                if a is not None and a[0] in ROUTING_COLUMNS:
                    have = have | {a[0]} if _passes_through(*a) else have - {a[0]}
            continue
        if op in _KEEP:
            if op in _WRITES:                 # a key it may write: no longer the one Azure wrote
                have = have - {c for c in ROUTING_COLUMNS if re.search(rf"(?<![\w.]){c}\b", rest)}
            continue
        if op == "project":
            have = frozenset(_named(split_top(rest, ","))[0])
        elif op == "project-away":
            have = have - _matching(split_top(rest, ","), have)
        elif op == "project-keep":
            have = have & _matching(split_top(rest, ","), have)
        elif op == "project-rename":
            for raw in split_top(rest, ","):
                a = _assignment(raw.strip())
                if a is None or a[0] != a[1]:
                    have = have - {a[1] if a else ""} - {a[0] if a else ""}
        elif op == "summarize":
            have = _summarize(rest, have)
        elif op == "distinct":
            named, star = _named(split_top(rest, ","))
            have = have if star else frozenset(named)
        else:
            return _NONE                      # count, make-series, evaluate, invoke…: not read
    return frozenset(have)


def routing_columns(query: str) -> frozenset:
    """The routing keys (`ROUTING_COLUMNS`) every row of `query` carries; the empty set when it
    cannot tell. Raises Unreadable on a string or a comment not closed."""
    statements = [s.strip() for s in split_top(mask(query or ""), ";")]
    statements = [s for s in statements if s]
    lets: dict[str, str] = {}
    main = ""
    for s in statements:
        m = re.match(r"^let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", s, re.S)
        if m:
            lets[m.group(1)] = m.group(2)
        elif not re.match(r"^(set|declare|alias)\b", s):
            main = s
    return _columns(main, lets) if main else _NONE


# The sources of the planes that are not the data plane, and the tables that make a query of
# another source one of them — Glorfindel's reading (`RulePoller._plane`: the detectors'
# `plane`, `_reads_entra_table`, `_reads_activity_table`), copied for whoever cannot import
# glorfindel (analysis/triage.py). tests/unit/test_rule_routing.py compares both.
NOT_DATA_SOURCES = frozenset({"azure_activity", "azure_entra"})
_NOT_DATA_TABLE = re.compile(
    r"\b(azureactivity|auditlogs|signinlogs|aadserviceprincipalsigninlogs|aadnoninteractiveusersigninlogs|"
    r"aadmanagedidentitysigninlogs)\b", re.IGNORECASE)


def data_plane(source: str, query: str) -> bool:
    """Whether a rule of this source and query is of the data plane (its rows routed to a VM)."""
    if (source or "azure_monitor") in NOT_DATA_SOURCES:
        return False
    code = "\n".join(line.split("//", 1)[0] for line in (query or "").splitlines())
    return not _NOT_DATA_TABLE.search(code)


def refusal(query: str) -> str:
    """Why a rule of the data plane with this query cannot load ('' when it can)."""
    try:
        keys = routing_columns(query)
    except Unreadable as exc:
        return f"requête illisible ({exc}) : ses lignes ne disent pas quelle VM elles visent"
    if keys:
        return ""
    return ("ses lignes ne portent ni `_ResourceId` ni `CallerIpAddress` — une ligne n'est jamais "
            "rattachée à une VM par son `Computer`, que root sur la VM choisit (SEC-A4) : garder "
            "`_ResourceId` dans le dernier `project` ou `summarize … by`")
