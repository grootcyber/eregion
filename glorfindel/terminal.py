"""What Glorfindel writes to a terminal, and how text from outside is said there (SEC-F, #845).

The watch, the CLI, the bot and the TUI print with Rich, whose `print`, `rule`, table cells and
panel titles read their text as markup. A closing tag with no opening one (`[/x]`) raises
`MarkupError`; a tag that opens (`[blink]`, `[link=…]`) is obeyed; a terminal escape sequence
(`ESC [ …`) reaches the operator's terminal as it is. Text from outside can carry all three:

- what the model rendered — the action, the reasoning, the explanation;
- the fields of a line an injector wrote in runs/ (its signal id, gravity, resource type);
- the fields of the cards' store, which the bot and the console write too;
- a Discord member's display name, a channel's or a thread's name;
- an exception — it quotes what Azure, a file, a library or a value said.

This module holds four things:

- `outside(value)`: the text said as it is — its markup escaped, its control characters shown
  (`\\x1b`), never obeyed. Every such value goes through it where it is printed.
- `literal(value)`: the same for a Rich `Text` built by `append`, which never reads markup but
  hands an escape sequence to the terminal as it is — its control characters shown, its brackets
  kept (SEC-Fc: escaped, a `Text` would show their backslashes).
- `GlorfindelConsole`: a Rich console whose prints never raise on markup — a string Rich cannot
  read as markup is said without it, that string only. The last guard, never the first: a value
  from outside is escaped where it is printed, or a tag it holds that opens would be obeyed.
- `say_failure(console, head, exc)`: an error said, escaped, and never raising in turn — the
  console unusable, stderr; that too, nothing. An `except` on these paths prints through it: one
  that printed `{exc}` raw raised again on the tag it quoted, and left its thread (the watch's
  decision thread of a VM, the bot's loop) to die in silence.
"""
from __future__ import annotations

import contextlib
import re
import sys

from rich.console import Console
from rich.errors import MarkupError
from rich.markup import escape

# The C0 controls but tab and newline, DEL, and the C1 controls (0x9b is a one-byte CSI).
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _controls_shown(value: object) -> str:
    text = "" if value is None else (value if isinstance(value, str) else str(value))
    return _CONTROL.sub(lambda m: f"\\x{ord(m.group()):02x}", text)


def outside(value: object) -> str:
    """`value` as text, said as it is: its control characters shown, its markup escaped."""
    return escape(_controls_shown(value))


def literal(value: object) -> str:
    """`value` as text for a `Text` literal (`Text.append`, `Text(…)`): its control characters
    shown, never obeyed — its markup left as it is, a `Text` never reads it (SEC-Fc)."""
    return _controls_shown(value)


class GlorfindelConsole(Console):
    """A Rich console whose prints never raise on markup: a string Rich cannot read as markup is
    rendered without it — that string only, the rest keeps its style."""

    def render_str(self, text: str, **kwargs):
        try:
            return super().render_str(text, **kwargs)
        except MarkupError:
            return super().render_str(text, **{**kwargs, "markup": False})


def say_failure(console, head: str, exc: object, lock=None) -> None:
    """« head : exc » in red on `console`, both said as they are (`outside`), under `lock` when
    given. Never raises: the console failing, the line goes to stderr, plain; that failing too,
    nowhere — an error said must never be the one that stops a thread."""
    try:
        with lock if lock is not None else contextlib.nullcontext():
            console.print(f"[red]{outside(head)} :[/red] {outside(exc)}")
        return
    except Exception:
        pass
    try:
        sys.stderr.write(f"{_controls_shown(head)} : {_controls_shown(exc)}\n")
    except Exception:
        pass
