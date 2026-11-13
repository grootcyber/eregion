"""Shared core of Eregion's injectors and workshop — what Annatar, Gothmog and Orodruin
all go through (eighth pass): the inscription and scope of a target (O0).

HY2b (#791): imported first by every component that writes Glorfindel's state, it installs, in an
agent session only, the guard of the operator's real ~/.glorfindel — and ~/.eregion and ~/.annatar
since HY2c (#800) (eregion_core/store_guard.py)."""
from eregion_core import store_guard as _store_guard

_store_guard.install()
