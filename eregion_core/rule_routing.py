"""What a detection rule's rows can be routed by, read in its query (SEC-A4, V-04).

A row of the data plane goes to the VM it names: its `_ResourceId`, which Azure writes, or the
private address that made a storage call (`CallerIpAddress`, which the storage service writes).
Never by `Computer`: root on a VM chooses its host name, and a row routed by it made Glorfindel
isolate or block in another VM's name (V-04). A rule whose rows carry neither key would route
nothing: refused at load, approval included.

`explain(query)` reads the query's text, the strictest reading — it refuses at the slightest
doubt rather than follow a value:

- a key is kept only while it holds the value Azure wrote. A table carries `_ResourceId`; a
  storage table (`STORAGE_TABLES`) carries `CallerIpAddress` too; `union`: what every operand
  carries. `project`, `distinct`, `summarize … by`, `arg_max`/`arg_min` keep a key only if they
  name it and it is still there; `project-away`, `project-keep`, `project-rename` drop it;
- a query that **writes** a key anywhere — whatever the case: `extend`, `project X = …`,
  `project-rename`, `summarize X = …`, a named output of `arg_*`, `parse … with … X:string`,
  `print`, `datatable`, a `let` — is refused, whatever it writes from. One form only is read as
  no write: the port taken off the storage caller's address, exactly
  `CallerIpAddress = tostring(split(CallerIpAddress, ":")[0])` (`data-exfiltration-blob`);
- an assignment of a form it does not read (a bracketed name `['…']`, a tuple `(a, b) = …`, any
  top-level `=` whose left is not a bare name), an operator it does not know, a source it cannot
  read (a `datatable`, a `print`, an `evaluate`, `union withsource=`), a string not closed: the
  empty set — refused, never assumed.

A reading of the text, not KQL's parser: a query it refuses can be one Log Analytics would run
(rewrite it so the last `project` or `summarize … by` names `_ResourceId` as the table wrote it).
"""
from __future__ import annotations

import fnmatch
import re

# What a row is routed by (detection_rules.RowAttribution): the resource Azure wrote, then the
# address that made the call. `ResourceId` is read by the row's attribution, never counted here.
RESOURCE_COLUMNS = ("_ResourceId", "ResourceId")
CALLER_COLUMNS = ("CallerIpAddress",)
ROUTING_COLUMNS = frozenset(RESOURCE_COLUMNS + CALLER_COLUMNS)
_ROUTING_LOWER = frozenset(c.lower() for c in ROUTING_COLUMNS)

# The tables where the storage service writes the caller's address (C1): anywhere else — a
# custom table fed from the VM — a `CallerIpAddress` would be root's word.
STORAGE_TABLES = frozenset({"StorageBlobLogs", "StorageFileLogs", "StorageQueueLogs", "StorageTableLogs"})

# Every table of Log Analytics carries `_ResourceId`, its standard column.
_TABLE = frozenset({"_ResourceId"})
_STORAGE = frozenset({"_ResourceId", "CallerIpAddress"})
_NONE: frozenset = frozenset()

# Stages that keep every column (they filter, order, add).
_KEEP = frozenset({
    "where", "filter", "order", "sort", "take", "limit", "top", "sample", "as", "render",
    "project-reorder", "lookup", "join",
})
# Stages that may write a column named in them (`parse … with * "x" _ResourceId:string`,
# `mv-expand _ResourceId`): refused when one names a key, or a name in brackets.
_WRITES = frozenset({"parse", "parse-where", "parse-kv", "mv-expand", "mv-apply", "serialize"})
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OP = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*)")
# A key written anywhere in the query, whatever the case: `Key = …` (not `==`, `=~`) or
# `Key:type` (parse, datatable, a function's parameter).
_KEY_WRITTEN = re.compile(
    r"(?<![\w.$])(" + "|".join(sorted(ROUTING_COLUMNS)) + r")\s*(=(?![=~])|:)", re.IGNORECASE)
_KEY_NAMED = re.compile(r"(?<![\w.$])(" + "|".join(sorted(ROUTING_COLUMNS)) + r")\b", re.IGNORECASE)
_BRACKETED = re.compile(r"\[\s*\"")
# The port taken off the storage caller's address: the one rewrite read as none (masked text,
# its delimiter checked to be ":" in the strings kept aside).
_PORT_OFF = re.compile(
    r"(?<![\w.$])CallerIpAddress\s*=\s*tostring\(\s*split\(\s*CallerIpAddress\s*,\s*\"(\d+)\"\s*\)"
    r"\s*\[\s*0\s*\]\s*\)")


class Unreadable(ValueError):
    """The query's text cannot be read (a string or a comment not closed)."""


class _Refused(Exception):
    """A query refused for its routing: what it does, in words."""


def mask(query: str) -> tuple[str, list[str]]:
    """(the query without its comments, each string replaced by `"<n>"`; the strings, in order):
    a `|`, a `;`, a column's name inside a string or a regex is never read as the query's."""
    out: list[str] = []
    strings: list[str] = []
    i, n = 0, len(query)

    def keep(text: str) -> None:
        out.append(f'"{len(strings)}"')
        strings.append(text)

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
            keep(query[i + 3:end])
            i = end + 3
            continue
        if c == "@" and i + 1 < n and query[i + 1] in "\"'":
            q, j = query[i + 1], i + 2
            while True:
                end = query.find(q, j)
                if end < 0:
                    raise Unreadable("chaîne verbatim non fermée")
                if end + 1 < n and query[end + 1] == q:     # a doubled quote, inside
                    j = end + 2
                    continue
                break
            keep(query[i + 2:end].replace(q + q, q))
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
            keep(query[i + 1:j])
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out), strings


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
    """(name, expression) of `Name = expr` at the top level, None when the item assigns nothing
    (`==`, `!=`, `=~`, `!~`, `<=` and `>=` are no assignment). An assignment whose left is not a
    bare name (`['_ResourceId'] = …`, `(a, b) = …`, `hint.x = …`) is refused (B2)."""
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
            if not _IDENT.match(name):
                raise _Refused(f"une affectation de forme illisible (« {name[:40]} = … »)")
            return name, item[i + 1:].strip()
    return None


def _named(items: list[str], have: frozenset) -> tuple[set[str], bool]:
    """(the keys these items keep — named bare, and still there; whether one of them is `*`).
    An assignment keeps nothing: one of a key was refused before (`_KEY_WRITTEN`)."""
    out, star = set(), False
    for raw in items:
        item = raw.strip()
        if item == "*":
            star = True
            continue
        if _assignment(item) is None and item in have:
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
    out, _ = _named(split_top(keys, ",") if keys.strip() else [], have)
    for raw in split_top(aggs, ","):
        item = raw.strip()
        if _assignment(item) is not None:
            continue                          # a column of its own name: never a key (refused before)
        m = _KEEP_ALL_AGG.match(item)
        if not m:
            continue                          # count(), max(x)…: a column of its own name
        args = [x.strip() for x in split_top(m.group(2), ",")]
        kept = args[1:] if m.group(1).startswith("arg_") else args
        for a in kept:
            _assignment(a)                    # a named output of an unreadable form: refused
        if "*" in kept:
            out |= have                       # every column of the row it picks, as it is
        if m.group(1).startswith("arg_"):     # arg_max(T, _ResourceId): named as it is, if there
            out |= {k for k in kept if k in have}
    return frozenset(out)


def _matching(patterns: list[str], have: frozenset) -> set[str]:
    pats = [p.strip() for p in patterns if p.strip()]
    return {c for c in have for p in pats if fnmatch.fnmatchcase(c, p)}


def _table(name: str, lets: dict[str, str], depth: int) -> frozenset:
    if name in lets:
        return _columns(lets[name], lets, depth + 1)
    return _STORAGE if name in STORAGE_TABLES else _TABLE


def _source(head: str, lets: dict[str, str], depth: int) -> frozenset:
    head = head.strip()
    if head.startswith("(") and head.endswith(")"):
        return _columns(head[1:-1], lets, depth + 1)
    if _IDENT.match(head):
        return _table(head, lets, depth)
    m = _OP.match(head)
    if m and m.group(1) == "union":
        rest = head[m.end():]
        if re.search(r"\bwithsource\b", rest, re.IGNORECASE):
            return _NONE                      # a column it names and writes: never read
        rest = re.sub(r"^\s*((kind|isfuzzy)\s*=\s*\w+\s*)+", "", rest, flags=re.IGNORECASE)
        operands = [x.strip() for x in split_top(rest, ",")]
        if operands and all(_IDENT.match(x) for x in operands):
            out = None
            for x in operands:                # what EVERY operand carries
                cols = _table(x, lets, depth)
                out = cols if out is None else out & cols
            return frozenset(out or ())
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
        if op == "join" and re.search(r"\bkind\s*=\s*right(anti|semi)\b", rest, re.IGNORECASE):
            return _NONE                      # the right side's rows: not read
        if op == "extend":
            for raw in split_top(rest, ","):
                _assignment(raw.strip())      # an unreadable form refused; a key, refused before
            continue
        if op in _WRITES:
            if _KEY_NAMED.search(rest) or _BRACKETED.search(rest):
                raise _Refused(f"`{op}` y nomme une clé de routage ou un nom entre crochets")
            continue
        if op in _KEEP:
            continue
        if op == "project":
            have = frozenset(_named(split_top(rest, ","), have)[0])
        elif op == "project-away":
            have = have - _matching(split_top(rest, ","), have)
        elif op == "project-keep":
            have = have & _matching(split_top(rest, ","), have)
        elif op == "project-rename":
            for raw in split_top(rest, ","):
                a = _assignment(raw.strip())
                if a is None:
                    raise _Refused("un `project-rename` illisible")
                have = have - {a[1]}
        elif op == "summarize":
            have = _summarize(rest, have)
        elif op == "distinct":
            named, star = _named(split_top(rest, ","), have)
            have = have if star else frozenset(named)
        else:
            return _NONE                      # count, make-series, evaluate, invoke…: not read
    return frozenset(have)


def explain(query: str) -> tuple[frozenset, str]:
    """(the routing keys every row of `query` carries as Azure wrote them, why none when the
    query writes one or cannot be read — '' otherwise). Raises Unreadable on a string or a
    comment not closed."""
    text, strings = mask(query or "")
    # The one rewrite read as none: the port off the storage caller's address.
    text = _PORT_OFF.sub(lambda m: "CallerIpAddress" if strings[int(m.group(1))] == ":" else m.group(0), text)
    written = _KEY_WRITTEN.search(text)
    if written:
        return _NONE, f"la requête écrit la clé de routage `{written.group(1)}`"
    statements = [s.strip() for s in split_top(text, ";")]
    statements = [s for s in statements if s]
    lets: dict[str, str] = {}
    main = ""
    for s in statements:
        m = re.match(r"^let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", s, re.S)
        if m:
            lets[m.group(1)] = m.group(2)
        elif not re.match(r"^(set|declare|alias)\b", s):
            main = s
    try:
        return (_columns(main, lets) if main else _NONE), ""
    except _Refused as exc:
        return _NONE, str(exc)


def routing_columns(query: str) -> frozenset:
    """The routing keys (`ROUTING_COLUMNS`) every row of `query` carries as Azure wrote them;
    the empty set when it cannot tell. Raises Unreadable on a string or a comment not closed."""
    return explain(query)[0]


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
        keys, why = explain(query)
    except Unreadable as exc:
        return f"requête illisible ({exc}) : ses lignes ne disent pas quelle VM elles visent"
    if keys:
        return ""
    return ((f"{why} : " if why else "")
            + "ses lignes ne portent ni `_ResourceId` ni `CallerIpAddress` tels qu'Azure les écrit — "
            "une ligne n'est jamais rattachée à une VM par son `Computer`, que root sur la VM choisit "
            "(SEC-A4) : garder `_ResourceId` dans le dernier `project` ou `summarize … by`, sans le réécrire")
