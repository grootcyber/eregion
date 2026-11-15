"""What Annatar writes to the operator's terminal, and how text from the outside is said (SEC-Fa, #852).

Annatar prints with Rich, whose `print`, `rule` and table cells read their text as markup. A
closing tag with no opening one (`[/x]`) raises `MarkupError`, and a terminal escape sequence
(`ESC [ …`) reaches the operator's terminal as it is. Text from the outside can carry both:

- what a command answered on a target (Run Command's output, Stratus's output and errors);
- an exception — it quotes what the cloud, a command or a file said;
- what the cloud says (a name, a tag, a rule a preflight found) and what the reasons built on it
  quote (the inscription's refusal, the preflight's issues);
- what the channel says (the watch's refusal, a verdict, a detection);
- what a model or a public library wrote (a campaign's plan, an atomic's command, a scenario's
  step), and what the operator typed.

So this module holds two things:

- `outside(value)`: the text said as it is. Its markup is escaped, and its control characters are
  shown (`\\x1b`), never obeyed. Every such value goes through it where it is printed.
- `console`: the one console of Annatar. A print never fails a run: a string that is not valid
  markup is said without markup (`render_str`, where Rich reads every string — a print, a rule's
  title, a table's cell). Its emoji codes are off: `:x:` in a value stays `:x:`.

Every module of Annatar prints through `console`, and never builds another `Console`; no exception
is printed without `outside` (tests/unit/test_annatar_console.py reads the whole package).
"""
from __future__ import annotations

import re

from rich.console import Console
from rich.errors import MarkupError
from rich.markup import escape

# The C0 controls but tab, newline and carriage return (Rich drops the carriage return itself),
# DEL, and the C1 controls (0x9b is a one-byte CSI).
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def outside(value: object) -> str:
    """`value` as text, said as it is: its control characters shown, its markup escaped."""
    text = value if isinstance(value, str) else str(value)
    text = _CONTROL.sub(lambda m: f"\\x{ord(m.group()):02x}", text)
    return escape(text)


class AnnatarConsole(Console):
    """A Rich console whose prints never raise on markup: a string Rich cannot read as markup is
    rendered without it — that string only, the rest of the line keeps its style."""

    def render_str(self, text: str, **kwargs):
        try:
            return super().render_str(text, **kwargs)
        except MarkupError:
            return super().render_str(text, **{**kwargs, "markup": False})


console = AnnatarConsole(emoji=False)
