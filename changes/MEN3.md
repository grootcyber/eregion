### Fixed
- **The workstation's commands work as written, under zsh as under bash** (MEN3, #734 ; `docs/operations.md`,
  its head ; `docs/demarrer/banc.md`, `infra/glorfindel-host/README.md`, `docs/design/modele-de-menace.md`,
  `README.md`). Four traps the bench met on 11/11, under Jonathan's login. `az role assignment list --role
  "<name>" --all` fails (« ValueError: No value for given attribute », in `_resolve_role_id`: without a
  scope, az cannot look the role up by its name) — measured without `--assignee`, deduced from az's code
  with it; and `--role` without `--all` nor `--scope` lists the subscription's scope alone, never a VM's (az's help; not measured).
  Each one cited (Restore Staging, steps 2 and 5; SEC11, step 3; SEC17, step 5; removing a role; the
  threat model) now filters the output, `az role assignment list --all --query
  "[?roleDefinitionName=='<name>']"`. `$SUB` was used by blocks that never set it: empty, the roles' `sed`
  wrote « /subscriptions/ » and az answered « InvalidSubscriptionId 'providers' »; each block now reads it
  (`SUB=$(az account show --query id -o tsv)`, the README's too, no longer typed) and runs what uses it
  inside an `if` that checks it is a GUID without printing it — pasted at once, an `if … fi` is read whole
  before it runs, where `return`/`exit` would close the terminal under bash and do nothing under zsh. A `!`
  between double quotes is the shell's history (« event not found »), a backquote a command substitution
  (`` "[?a == `false`]" `` becomes `[?a == ]`): a query carrying either goes between single quotes, or
  escapes each backquote; no query of the documents carries one. A Terraform plan is in colours, so `grep
  '^Plan:'` found nothing: where a document gives the plan's line, the target runs under
  `TF_CLI_ARGS_plan=-no-color` (Imladris' plan through `tee`, then `grep '^Plan:'`).
- **SEC17's plan said six creations: it makes eight** (MEN3, #734 ; `docs/operations.md`, « Depuis un rôle
  Restore d'avant SEC17 »). With `restore_staging_storage` committed (RST1), filling `restore_principals`
  also gives « Eregion Glorfindel Restore Staging » to the console and the bot on the staging account:
  four `restore_neutralize`, two `session_drain_principals`, two `restore_staging` — `Plan: 8 to add`,
  seven when the console's hand-made assignment was imported first, and the apply fails without the
  Restore Staging role, which must exist before. The block copies `principals.auto.tfvars.example` with
  `cp -n`: a filled file stays.
- **What the reviews of 11/11 left said** (MEN3, #734). `docs/operations.md`, « Ce qui est retenté »:
  the update reads HashiCorp's apt source alone (CI11, #728) and why; what `Error-Mode=any` did on the
  runner on 11/11 (exit 100, three attempts, then the failure), no longer « to be seen »; and that the
  `terraform` package depends on `git`, which the runners' image already carries. `docs/banc-t1486.md`:
  « on today's bench » becomes « without REC1 (on 0.5.8) ». `docs/azure.md` and `docs/operations.md`:
  hypothesis E2 is no longer « settled by the apply » — the sign-ins arrive (the canary's rows in
  `AADServicePrincipalSignInLogs`, 11/11, CAN3, #673) on a tenant without P2 (IDI1p, 06/11); whether it
  is also without P1 has not been read.
