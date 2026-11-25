### Added
- **Entra ID and the control plane are always on the infrastructure map while their rules run, as a VM is** (IDT1, #1182; `docs/design/console.md`, « Entra ID et le plan de contrôle sur la carte »). Jonathan's choices on a mockup (25/11). Their tile only came with a card, then went: its absence said nothing.
  - Shown as soon as a rule of their source (`azure_entra`, `azure_activity`) is enabled and bound to a backend, first in the row, linked to DETECT only.
  - Their health on their dot: red, a rule's poll in error or their logs unreadable; grey, no log for the watch's threshold (`log_freshness` in `/api/watch/status`, LOGF1); green otherwise. A watch before LOGF1: green or red, never grey. A read that hangs (`read_at` older than 30 min): grey, never a stale green.
  - Unfolded as a VM's identity block: the tenant (masked), the workspace, each table's last log, each rule's state, the managed identities' certificates set aside (MID1).
  - Tests: `tests/unit/test_console_watched_tiles.py`; mutants M7601–M7610 (`scripts/mutants/IDT1.py`).
