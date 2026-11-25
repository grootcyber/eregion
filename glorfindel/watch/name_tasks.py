"""Les noms des abonnements dans le ménage de la watch — SUBN1 (#1190) : le nom lisible de chaque
abonnement vu, pour la console (glorfindel/subscription_names.py).

Chaque minute, un coup d'œil en mémoire : un abonnement est dû au démarrage, toutes les 6 h, ou dès qu'il
apparaît. Puis une passe dans un fil à elle, une à la fois (`Solo`) : un ARM qui ne répond pas ne tient
jamais la boucle. Jamais en dry-run (pas d'Azure). Un mixin de `Housekeeping` : il lit sa console, son
verrou et son dry-run.
"""
from __future__ import annotations

from glorfindel.terminal import outside as _outside, say_failure as _say_failure
from glorfindel.watch.passes import Solo


class NameTasks:
    """La partie « noms des abonnements » de `Housekeeping`."""

    def _init_names(self) -> None:
        self._names = None
        self._names_thread = Solo("subscription-names")
        if self.dry_run:
            return
        try:
            from glorfindel.subscription_names import SubscriptionNames
            self._names = SubscriptionNames(say=self._say_names)
        except Exception as exc:      # dit, jamais la watch arrêtée : la console garde l'identifiant masqué
            _say_failure(self.console, "watch: subscription names not read", exc, self._output_lock)

    def _say_names(self, line: str) -> None:
        with self._output_lock:
            self.console.print(f"[dim]{_outside(line)}[/dim]")

    def _subscription_names(self) -> None:
        """SUBN1 : les abonnements dus lus dans leur fil — rien à faire, rien de lancé."""
        n = self._names
        if self.dry_run or n is None or self._names_thread.busy() or not n.has_work():
            return
        self._names_thread.start(self._names_run)

    def _names_run(self) -> None:
        try:
            self._names.pass_once()
        except Exception as exc:
            _say_failure(self.console, "watch: subscription names failed", exc, self._output_lock)
