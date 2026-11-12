### Fixed
- **The bench tool that measures the lift says what the bench of 12/11 read, without the three defects seen there** (LEV2b, #763; `docs/banc-lev2.md`).
  `scripts/bench_lev2.py report` said the disk's refused `grant-access` as « Conflict conflict : un
  échec, il compte », the code lowercased, which read as a comparison by case. There is none: the code
  was `Conflict`, not `OperationNotAllowed`, the only refusal Glorfindel leaves out (REC1b), so
  Glorfindel counts it and the verdict was right; it is the guide that expected it left out. The
  report now says the status and the code as Azure wrote them, and why a `Conflict` under another code
  counts; the guide's gesture 8 says the same, and whether the door should leave this refusal out goes
  to LEV3. The mask no longer rewrites the name of a Microsoft.Resources operation
  (`microsoft.resources/subscriptions/resourcegroups/write` read `microsoft.resources<ressource>`): a
  path of letters right after its namespace is kept, an ARM id is still masked
  (`scripts/bench_shared.py`, every bench report). A resource that is none of the VM's is named by its
  type and its place (of the VM's group outside the VM, of another group, of another subscription),
  never by its name: on 12/11 it was the disk gesture 15 creates, which the guide now notes. Found
  while fixing: each round reads the same events again, and each copy was judged; a `Started` read one
  round more than its refusal was left over, and the refusal was no longer one. Each event is now
  judged once, as Glorfindel reads it, and a refusal whose operation Glorfindel still keeps is never
  said « écarté ». Recomposed on the reads of 12/11, the report changes in those three lines only.
  - Tests: `tests/unit/test_bench_lev2.py` (fakes on the PATH that refuse `az`, `ssh`, `docker`,
    `terraform`). Mutants M4960–M4969 (`scripts/mutants/LEV2b.py`), 10/10 caught.
