### Added
- **The pinned control-plane injector tool and its offline provisioning toolchain can be staged
  onto the execution host** (`scripts/`, `Makefile`): one command downloads and verifies them
  against their recorded checksums, then lays them out so the injector image carries them
  read-only. The execution host keeps no Internet access; staging is the operator's only networked
  step. In CI nothing is staged, so the image still builds and no control-plane technique runs.

### Changed
- **A control-plane injection builds a writable, run-scoped home and re-checks the staged
  provisioning tool before it runs** (`annatar/executors/`, `annatar/engines/`): the injector
  container has a read-only root, so the tool's working state goes to a fresh per-run directory;
  the staged tool's checksum is re-verified before a run, like the injector binary, and a tool
  absent or changed since it was staged makes the run refuse.
