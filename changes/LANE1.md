### Changed
- **The grouped map's lanes that hold a VM come first** (LANE1, #1226; `docs/design/console.md`, « La carte groupée »). Jonathan's choice on a mockup (26/11): grouped by resource group, the lines from PROTECT and RECOVER to the VMs crossed the small lanes above them (the tenant, the control plane's). Now the lanes that hold a VM, a cluster or an NSG come first, the watch's subscription first among them; the tenant and a subscription's own tiles after.
  - Tests: `tests/unit/test_console_groups.py`; mutants M7841–M7842 (`scripts/mutants/LANE1.py`).
