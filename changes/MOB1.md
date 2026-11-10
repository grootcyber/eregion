### Added
- **The bench driven from the phone, always by commands typed on the workstation** (MOB1, #686;
  `docs/demarrer/mobile.md`, `docs/operations.md`, the threat model's frontier 9). Only the path between
  the phone and the workstation changes: Orodruin still listens to the workstation's SSH alone, nothing
  is installed on H0. Two independent barriers: a private network (Tailscale, an access rule that opens
  only phone → workstation), then the workstation's SSH server in WSL, by a key alone, kept in the phone's
  secure chip.
  - `make bench-run TARGET=<vm> SCENARIO=<id> [DRY_RUN=1]` (`scripts/bench_run.py`): the preflight first
    (one ✗ and nothing leaves), a one-wire request read by the requests' one reader, the target's name
    typed — destructive or not — then the launch by Orodruin as `make orodruin-exercise` does it (the
    name typed removed from Orodruin at the end), then `make bench-report` for each run named.
  - `make bench-restore TARGET=<vm> [BEFORE=…] [RUN=…] [DRY_RUN=1]` (`scripts/bench_restore.py`): under
    the console's pair alone (required), `--before` the run's T0 (its `attack_started`, as
    `make bench-report` wrote it in `runs/bench/`) unless `BEFORE=`, always `--keep-isolated` (the lift is
    H0's), the VM's name typed, a dry run, then « [o/N] ».
  - Both refuse inside an agent session (`EREGION_AGENT_SESSION`, a lot's worktree), the guard alone
    first, before any command towards H0 or Orodruin is expanded; `TARGET`, `SCENARIO`, `BEFORE` and `RUN`
    from the environment are refused.
  - `make glorfindel-host-tunnel-private`: H0's console tunnel bound to the workstation's private address
    alone (`tailscale ip -4`, an address of 100.64.0.0/10), H0's host key pinned; without that address
    nothing opens — never every interface, never the loopback WSL shares with Windows.
  - `make mobile-check` (`scripts/mobile.py`), read-only: the SSH server listening on the private address
    alone, password and keyboard-interactive closed, the key alone, the console's port exposed nowhere
    else, Tailscale SSH off; no address printed.
  - The workstation's models, applied by the operator: `infra/poste/sshd_config.d/00-eregion.conf`,
    `infra/poste/ssh.service.d/eregion.conf`, `infra/poste/tailscale-acl.hujson`.
  - Tests: `tests/unit/test_bench_run.py`, `tests/unit/test_bench_restore.py`, `tests/unit/test_mobile.py`;
    mutants M4696–M4705 (`scripts/mutants/MOB1.py`).
