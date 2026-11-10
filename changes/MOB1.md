### Added
- **The bench driven from the phone, always by commands typed on the workstation** (MOB1, #686;
  `docs/demarrer/mobile.md`, `docs/operations.md`, the threat model's frontier 9). Only the path between
  the phone and the workstation changes: Orodruin still listens to the workstation's SSH alone, nothing
  changes on H0. Two independent barriers, for the terminal as for the console: a private network
  (Tailscale, an access rule that opens only phone → workstation:22), then the workstation's SSH server
  in WSL, by a key alone, kept in the phone's secure chip. The console of H0 reaches the phone through
  the phone's own SSH tunnel to the workstation's 127.0.0.1:7007, where `make glorfindel-host-tunnel`
  holds H0's: the console's `Host` stays `localhost`, its token still required.
  - `make bench-run TARGET=<vm> SCENARIO=<id> [DRY_RUN=1]` (`scripts/bench_run.py`): a terminal on stdin
    first (a name piped is no name typed), the preflight (one ✗ and nothing leaves), a one-wire request
    read by the requests' one reader, the target's name typed — destructive or not — then the launch by
    Orodruin as `make orodruin-exercise` does it (the name typed removed from Orodruin at the end), then
    `make bench-report` for each run named, and the restore's command with its `RUN=`.
  - `make bench-restore TARGET=<vm> [RUN=…] [BEFORE=…] [DRY_RUN=1]` (`scripts/bench_restore.py`): a
    terminal, the console's pair (required), `--before` the run's T0 (its `attack_started`, as
    `make bench-report` wrote it in `runs/bench/`: `RUN=`, else the target's one report — two or more are
    listed and refused) unless `BEFORE=`, always `--keep-isolated` (the lift is H0's), the VM's name
    typed, a dry run, then « [o/N] »; the repository's own `glorfindel`, under the console's pair alone.
  - Both refuse inside an agent session (`EREGION_AGENT_SESSION`, a lot's worktree), the guard alone
    first, before any command towards H0 or Orodruin is expanded; the internal `-go` targets check the
    variables' origin again; `TARGET`, `SCENARIO`, `BEFORE`, `RUN` and `POINT_MAX_H` from the environment
    are refused. A long-lived `tmux` session can be driven by any process of the same user: said in the
    guide and the threat model, with the advice not to keep the pair loaded in it.
  - `make mobile-check` (`scripts/mobile.py`), read-only: the SSH server listening on the private address
    alone; password and keyboard-interactive closed, the key alone, from `.ssh/authorized_keys` alone, no
    `AuthorizedKeysCommand`, no `TrustedUserCAKeys`; `AllowTcpForwarding local`, `PermitOpen
    127.0.0.1:7007` alone, `GatewayPorts no`, no socket, agent nor X11 forwarding; the console's port on
    127.0.0.1 alone; Tailscale SSH off (unread: a ✗); no address printed. These bound sshd's own
    forwarding only: with a shell, the phone relays as the operator does.
  - The workstation's models, applied by the operator: `infra/poste/sshd_config.d/00-eregion.conf`,
    `infra/poste/ssh.service.d/eregion.conf`, `infra/poste/tailscale-acl.hujson`.
  - Tests: `tests/unit/test_bench_run.py`, `tests/unit/test_bench_restore.py`, `tests/unit/test_mobile.py`;
    mutants M4696–M4705, M4737–M4744 and M4756–M4758 (`scripts/mutants/MOB1.py`).

### Security
- **`make orodruin-exercise` wants a terminal for the names it has typed** (MOB1, #686): its first
  prerequisite, `orodruin-exercise-guard`, refuses without one before `glorfindel-host-known` and
  `orodruin-known` — nothing read from H0, nor a drill's VMs from Azure, nor Terraform's state; a name
  piped into `eregion_core.exercise_request confirm` is refused too, nothing shown nor written.
  - Tests: `tests/unit/test_exercise_request.py`, `tests/unit/test_makefile_exercise.py` (now run under
    a pseudo-terminal).
