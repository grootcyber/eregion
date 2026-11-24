"""What the watch says of the client's network at its start (SEC2b, #1089): each named network, what
it holds and where it serves, the names that serve nowhere, the overlaps between the layers — said,
never refused —, and the state of the list the discovery read (glorfindel/client_network_watch.py).
A list that can't be trusted is said loudly: blocks outside the Internet stay refused.
"""
from __future__ import annotations

from rich.markup import escape as _esc_markup

_STYLE = {"info": "[dim]{}[/dim]", "note": "  [yellow]·[/yellow] {}", "loud": "[bold red]⚠ {}[/bold red]"}


def say_networks(console, dry_run: bool) -> None:
    """The lines of `client_network_watch.start_lines`, on the watch's console; a config refused is
    said elsewhere (the watch does not start on it, A3), a dry run reads nothing."""
    if dry_run:
        return
    from glorfindel.client_network_watch import start_lines
    from glorfindel.config import load_glorfindel_config
    try:
        lines = start_lines(load_glorfindel_config())
    except Exception as exc:          # never stops the watch
        console.print(f"[yellow]Réseau du client non dit : {_esc_markup(str(exc))}[/yellow]")
        return
    for level, text in lines:
        console.print(_STYLE[level].format(_esc_markup(text)))
