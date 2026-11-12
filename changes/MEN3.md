### Fixed
- **The workstation's commands work as written, under zsh as under bash** (MEN3, #734 ; `docs/operations.md`,
  its head ; `docs/demarrer/banc.md`, `infra/glorfindel-host/README.md`). Four traps the bench met on
  11/11, under Jonathan's login. `az role assignment list --role "<name>" --all` fails (« ValueError: No
  value for given attribute », in `_resolve_role_id`: without a scope, az cannot look the role up by its
  name), with or without `--assignee`: each one cited (Restore Staging, steps 2 and 5; SEC11, step 3;
  SEC17, step 5; removing a role) now filters the output,
  `az role assignment list --all --query "[?roleDefinitionName=='<name>']"`. `$SUB` was used by blocks that
  never set it: empty, the roles' `sed` wrote « /subscriptions/ » and az answered « InvalidSubscriptionId
  'providers' »; each block now reads it (`SUB=$(az account show --query id -o tsv)`) and checks it is a
  GUID without printing it (`grep -cE`, → 1). A `!` between double quotes is zsh's history (« event not
  found »): no query of the documents carries one, and the rule is written down. A Terraform plan is in
  colours, so `grep '^Plan:'` found nothing: where a document gives the plan's line, the target runs
  under `TF_CLI_ARGS_plan=-no-color` (Imladris' plan through `tee`, then `grep '^Plan:'`).
- **What the reviews of 11/11 left said** (MEN3, #734). `docs/operations.md`, « Ce qui est retenté »:
  the update reads HashiCorp's apt source alone (CI11, #728) and why; what `Error-Mode=any` did on the
  runner on 11/11 (exit 100, three attempts, then the failure), no longer « to be seen »; and that the
  `terraform` package depends on `git`, which the runners' image already carries. `docs/banc-t1486.md`:
  « on today's bench » becomes « without REC1 (on 0.5.8) ». `docs/azure.md` and `docs/operations.md`:
  hypothesis E2 is no longer « settled by the apply » — the sign-ins arrive (the canary's rows in
  `AADServicePrincipalSignInLogs`, 11/11, CAN3, #673) on a tenant without P2 (IDI1p, 06/11); whether it
  is also without P1 has not been read.
