"""SUBN1 (#1190) : la watch lit le nom lisible de chaque abonnement qu'elle voit, pour la console.

Une watch n'agit que dans son abonnement (`AZURE_SUBSCRIPTION_ID`), mais ses workspaces découvrent des VM
d'autres abonnements. La console groupe sa carte par abonnement (GRP1) : sous le nom lisible quand la watch
l'a lu, sous l'identifiant masqué sinon.

- **Les abonnements vus** (`seen`) : le sien (`AZURE_SUBSCRIPTION_ID`) et ceux des `resource_id` des VM
  découvertes (`AssetRegistry`), en minuscules, une fois chacun. Seul un identifiant de la forme d'un GUID
  est pris : un `resource_id` vient de Log Analytics, un texte du dehors, jamais collé dans une URL.
- **La lecture** (glorfindel/providers/azure/subscriptions.py) : `GET /subscriptions/{id}`, son
  `displayName`, avec l'identité de la watch. Le rythme est borné : tous au démarrage, puis tous les
  `EVERY_S` (6 h), et un abonnement qui apparaît dès la passe suivante (la minute) ; au plus `PER_PASS`
  lectures par passe, le reste à la passe suivante. Dans un fil à elle (glorfindel/watch/name_tasks.py),
  jamais en dry-run.
- **Le nom est un texte du dehors**, choisi par les administrateurs du client (`clean_name`) : ses
  caractères de contrôle et de format retirés (les retours à la ligne, les marques de direction), un GUID
  qu'il porterait masqué, puis coupé à `NAME_MAX` (64). Il ne va qu'à la console : jamais au modèle, ni
  dans le signal, ni à Discord, ni dans le journal de la watch, qui dit au plus
  « subscription names: 3 of 4 read ». Une erreur est masquée comme celles de log_freshness (`short_error` :
  les GUID et les URL), avant d'être coupée.
- **L'état** (`state_file`, `~/.glorfindel/subscriptions.json`, écrit d'un coup) garde l'identifiant brut en
  clé, comme les fichiers d'isolation. Le masque est posé au moment de servir (`console_field`) : les
  8 premiers et les 4 derniers caractères, en minuscules, comme `/api/config` le montre. Un fichier
  illisible, ou d'une autre forme, fait disparaître le champ.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from glorfindel.log_freshness import _GUID, _iso, _scrubbed, short_error

EVERY_S = 6 * 3600.0               # tous les abonnements relus toutes les 6 h
PER_PASS = 10                      # au plus 10 lectures par passe : le reste, la minute suivante
NAME_MAX = 64
ERROR_MAX = 160
NO_NAME = "no display name in ARM's answer"
_SUB_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_SUB_IN_ID = re.compile(r"/subscriptions/([^/]+)", re.I)
_LINE_BREAKS = {" ", " "}


def state_file() -> Path:
    """Où la watch écrit ce qu'elle a lu, et où la console le lit."""
    return Path.home() / ".glorfindel" / "subscriptions.json"


def subscription_key(value) -> str | None:
    """Un identifiant d'abonnement en minuscules, ou None s'il n'a pas la forme d'un GUID."""
    key = str(value or "").strip().lower()
    return key if _SUB_ID.match(key) else None


def mask(key: str) -> str:
    """La clé servie : les 8 premiers et les 4 derniers caractères, en minuscules (`_mask` d'api.py)."""
    key = key.lower()
    return f"{key[:8]}…{key[-4:]}"


def clean_name(value) -> str | None:
    """Le nom d'un abonnement, prêt pour la console : sans caractère de contrôle ni de format (catégories
    Unicode C*, les séparateurs de ligne), un GUID masqué, coupé à NAME_MAX ; None quand il ne reste rien."""
    if not isinstance(value, str):
        return None
    text = "".join(c for c in value if unicodedata.category(c)[0] != "C" and c not in _LINE_BREAKS)
    text = _GUID.sub("<id>", text).strip()[:NAME_MAX].strip()
    return text or None


def seen(environ=None, assets=None) -> list[str]:
    """Les abonnements vus, en minuscules, une fois chacun : le sien d'abord, puis ceux des VM découvertes.
    `assets` : les `DiscoveredAsset` (par défaut, le registre de la découverte)."""
    env = os.environ if environ is None else environ
    if assets is None:
        from glorfindel.discovery import get_registry
        assets = get_registry().all()
    out: list[str] = []
    candidates = [env.get("AZURE_SUBSCRIPTION_ID", "")]
    for a in assets:
        m = _SUB_IN_ID.search(str(getattr(a, "resource_id", "") or ""))
        candidates.append(m.group(1) if m else "")
    for value in candidates:
        key = subscription_key(value)
        if key and key not in out:
            out.append(key)
    return out


def read_one(reader, key: str) -> dict:
    """Un abonnement lu : {"name": texte, "error": None} — ou {"name": None, "error": texte court} quand
    la lecture a échoué (un 403, un 404, le réseau) ou que la réponse ne porte aucun nom."""
    try:
        raw = reader(key)
    except Exception as exc:
        return {"name": None, "error": short_error(exc)[:ERROR_MAX]}
    name = clean_name(raw)
    return {"name": name, "error": None if name else NO_NAME}


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def load(path: Path | None = None) -> dict:
    """Ce que la watch a écrit en dernier, ou {} (absent, illisible, d'une autre forme)."""
    try:
        doc = json.loads((path or state_file()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _field_of(doc: dict) -> dict | None:
    """Le champ de la console depuis le fichier, vérifié en entier : None dès qu'une partie n'a pas sa
    forme. Les clés masquées ici ; le nom nettoyé et l'erreur masquée à nouveau, au cas où."""
    names, read_at = doc.get("names"), doc.get("read_at")
    if not isinstance(names, dict) or not isinstance(read_at, str) or _iso(read_at) is None:
        return None
    out = {}
    for key, e in sorted(names.items()):
        if not (isinstance(key, str) and subscription_key(key) and isinstance(e, dict)):
            return None
        name, error = e.get("name"), e.get("error")
        if not (name is None or isinstance(name, str)) or not (error is None or isinstance(error, str)):
            return None
        out[mask(key)] = {"name": clean_name(name),
                          "error": _scrubbed(error)[:ERROR_MAX] if error is not None else None}
    return {"read_at": read_at, "names": out}


def console_field(path: Path | None = None) -> dict:
    """Le champ de `/api/watch/status` : {"subscriptions": {...}} — {} quand la watch n'a encore rien
    écrit, est d'avant SUBN1, ou que son fichier ne se lit pas : la console garde l'identifiant masqué.
    Ne lève jamais."""
    try:
        field = _field_of(load(path))
    except Exception:
        field = None
    return {"subscriptions": field} if field is not None else {}


def _default_reader():
    """Le lecteur d'ARM de l'adaptateur Azure (MC0 : aucun SDK hors de glorfindel/providers/azure/)."""
    from glorfindel.providers.azure.subscriptions import SubscriptionReader
    return SubscriptionReader()


class SubscriptionNames:
    """Les lectures des noms et la mémoire qu'elles gardent entre deux passes.

    `reader(key)` rend le `displayName` d'un abonnement (par défaut, l'adaptateur Azure, créé à la première
    lecture) ; `assets()` les VM découvertes ; `say`, une ligne du journal de la watch (des comptes, jamais
    un nom ni une erreur)."""

    def __init__(self, *, reader=None, assets=None, environ=None, clock=time.time, path: Path | None = None,
                 say=None) -> None:
        self._reader = reader
        self._assets = assets
        self._environ = environ
        self._clock = clock
        self._path = path
        self._say = say or (lambda line: None)
        doc = load(path)
        kept = doc.get("names") if isinstance(doc.get("names"), dict) else {}
        # Ce que la watch a lu avant de redémarrer reste servi jusqu'à sa relecture ; le démarrage relit tout.
        self._names = {k: e for k, e in kept.items() if subscription_key(k) == k and isinstance(e, dict)}
        self._read: set[str] = set()       # lus depuis le démarrage, ou depuis la dernière tournée
        self._round_at: float | None = None
        self._said: tuple[int, int] | None = None

    def seen(self) -> list[str]:
        return seen(self._environ, None if self._assets is None else self._assets())

    def due(self, now: float | None = None, keys: list[str] | None = None) -> list[str]:
        """Les abonnements à lire : tous au démarrage et toutes les 6 h (une tournée), sinon ceux qui sont
        apparus depuis ; au plus PER_PASS."""
        now = self._clock() if now is None else now
        keys = self.seen() if keys is None else keys
        if self._round_at is not None and now - self._round_at >= EVERY_S:
            self._read, self._round_at = set(), None          # une nouvelle tournée
        return [k for k in keys if k not in self._read][:PER_PASS]

    def has_work(self, now: float | None = None) -> bool:
        """Une passe à faire : un abonnement à lire, ou un qui n'est plus vu à retirer du fichier."""
        keys = self.seen()
        return bool(self.due(now, keys)) or bool(set(self._names) - set(keys))

    def pass_once(self) -> dict | None:
        """Les abonnements dus lus, le fichier écrit ; None quand rien n'était à faire."""
        now = self._clock()
        keys = self.seen()
        due = self.due(now, keys)
        if not due and not set(self._names) - set(keys):
            return None
        if due and self._reader is None:
            self._reader = _default_reader()
        for key in due:
            self._names[key] = {**read_one(self._reader, key), "read_at": _stamp(now)}
            self._read.add(key)
        if self._round_at is None and all(k in self._read for k in keys):
            self._round_at = now                               # la tournée faite : la suivante dans 6 h
        # Une entrée par abonnement vu : un abonnement qui n'est plus vu quitte le fichier ; un vu pas
        # encore lu y est, sans nom ni erreur.
        names = {k: self._names.get(k) or {"name": None, "error": None, "read_at": None} for k in keys}
        self._names = {k: e for k, e in names.items() if e.get("read_at")}
        doc = {"version": 1, "read_at": _stamp(now), "names": names}
        from glorfindel.response.state_files import _atomic_write_text
        _atomic_write_text(self._path or state_file(), json.dumps(doc, indent=1, sort_keys=True))
        self._say_count(names)
        return doc

    def _say_count(self, names: dict) -> None:
        """Le journal de la watch dit des comptes, quand ils changent — jamais un nom ni une erreur."""
        count = (sum(1 for e in names.values() if e.get("name")), len(names))
        if count != self._said:
            self._said = count
            self._say(f"subscription names: {count[0]} of {count[1]} read")
