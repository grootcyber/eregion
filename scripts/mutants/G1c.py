"""G1c (Partie de #76): the benign noise declared on gondolin in the tracked config, applied by its
own targeted Make targets behind the bench's subscription guard — never terraform by hand, never
a full celebrimbor-up. M6768–M6779, measured by tests/unit/test_gothmog_noise.py; M6831–M6832, the
same guard on DCR1's targets, measured by tests/unit/test_bench_perf_counters.py."""
MK = "Makefile"
CFG = "infra/terraform/config.yaml"
TFTEST = "infra/terraform/tests/chaos_noise.tftest.hcl"
_T = "tests/unit/test_gothmog_noise.py"
_DCR = "tests/unit/test_bench_perf_counters.py"
_REFUSED = f"{_T}::test_off_the_bench_s_subscription_terraform_is_never_run"

MUTANTS = [
    ("M6768", "an empty AZURE_SUBSCRIPTION_ID is not said: the refusal blames az instead (G1c)", MK,
     '\t[ -n "$$want" ] || { echo "✗ AZURE_SUBSCRIPTION_ID est vide : terraform n\'est pas lancé (source .envrc)." >&2; exit 1; }; \\\n',
     ""),
    ("M6769", "ARM_SUBSCRIPTION_ID never compared: terraform on the subscription azurerm reads, another "
     "one (G1c)", MK,
     '\t[ "$$arm" = "$$want" ] || { echo "✗ ARM_SUBSCRIPTION_ID est vide ou n\'est pas AZURE_SUBSCRIPTION_ID',
     '\ttrue || { echo "✗ ARM_SUBSCRIPTION_ID est vide ou n\'est pas AZURE_SUBSCRIPTION_ID'),
    ("M6770", "az's active subscription never compared: the 20/11 apply on Stratus's subscription "
     "again (G1c)", MK,
     '\t[ "$$active" = "$$want" ] || { echo "✗ L\'abonnement actif d\'az n\'est pas AZURE_SUBSCRIPTION_ID',
     '\ttrue || { echo "✗ L\'abonnement actif d\'az n\'est pas AZURE_SUBSCRIPTION_ID'),
    ("M6771", "az's subscription compared with its case: the bench, written otherwise, refused (G1c)", MK,
     "\tactive=$$(az account show --query id -o tsv 2>/dev/null | tr A-Z a-z); \\\n",
     "\tactive=$$(az account show --query id -o tsv 2>/dev/null); \\\n"),
    ("M6772", "celebrimbor-noise-up without the guard: an apply on whatever subscription az holds "
     "(G1c)", MK,
     "celebrimbor-noise-up:\n\t$(CELEBRIMBOR_SUB_GUARD)\n",
     "celebrimbor-noise-up:\n"),
    ("M6773", "celebrimbor-noise-plan without the guard: a plan read as the bench's, on another "
     "subscription (G1c)", MK,
     "celebrimbor-noise-plan:\n\t$(CELEBRIMBOR_SUB_GUARD)\n",
     "celebrimbor-noise-plan:\n"),
    ("M6774", "the guard after terraform's first call: terraform run before the refusal (G1c)", MK,
     "celebrimbor-noise-plan:\n\t$(CELEBRIMBOR_SUB_GUARD)\n\t@$(TF) init\n",
     "celebrimbor-noise-plan:\n\t@$(TF) init\n\t$(CELEBRIMBOR_SUB_GUARD)\n"),
    ("M6775", "the refusal prints the subscription's value, not the variable's name (G1c)", MK,
     "n'est pas AZURE_SUBSCRIPTION_ID : terraform n'est pas lancé (az account set",
     "n'est pas $$want : terraform n'est pas lancé (az account set"),
    ("M6776", "a resource of G1 left out of the targets: its experiment's role never applied (G1c)", MK,
     "-target=azurerm_role_assignment.chaos_cpu_read -target=azurerm_role_assignment.chaos_restart\n",
     "-target=azurerm_role_assignment.chaos_cpu_read\n"),
    ("M6777", "celebrimbor-noise-up applies without confirmation, YES=1 or not (G1c)", MK,
     "\t@$(TF) apply$(if $(YES), -auto-approve) $(NOISE_TARGETS)\n",
     "\t@$(TF) apply -auto-approve $(NOISE_TARGETS)\n"),
    ("M6778", "the « noise off » case of terraform test reads the tracked config again: it plans the "
     "noise and says nothing of off (G1c)", TFTEST,
     "    chaos_noise_vms = [] # le bruit éteint, quelle que soit la config\n",
     "    chaos_noise_vms = null # le bruit éteint, quelle que soit la config\n"),
    ("M6779", "the noise taken out of the tracked config: the next plan destroys what was applied "
     "(G1c)", CFG,
     "  noise_vms:         [gondolin]\n",
     "  noise_vms:         []\n"),
    ("M6831", "celebrimbor-dcr-plan without the guard: the DCR's plan read on whatever subscription "
     "az holds (G1c, DCR1's targets)", MK,
     "celebrimbor-dcr-plan:\n\t$(CELEBRIMBOR_SUB_GUARD)\n",
     "celebrimbor-dcr-plan:\n"),
    ("M6832", "celebrimbor-dcr-up without the guard: the DCR applied on whatever subscription az "
     "holds (G1c, DCR1's targets)", MK,
     "celebrimbor-dcr-up:\n\t$(CELEBRIMBOR_SUB_GUARD)\n",
     "celebrimbor-dcr-up:\n"),
]

TESTS = {
    "M6768": _REFUSED,
    "M6769": _REFUSED,
    "M6770": _REFUSED,
    "M6771": f"{_T}::test_the_subscriptions_are_compared_without_their_case",
    "M6772": _REFUSED,
    "M6773": _REFUSED,
    "M6774": _REFUSED,
    "M6775": _REFUSED,
    "M6776": f"{_T}::test_the_targets_name_every_resource_of_g1_and_nothing_else",
    "M6777": f"{_T}::test_noise_up_applies_g1_alone_confirmed_unless_yes",
    "M6778": f"{_T}::test_the_noise_is_declared_on_gondolin_and_never_on_an_unenrolled_vm",
    "M6779": f"{_T}::test_the_noise_is_declared_on_gondolin_and_never_on_an_unenrolled_vm",
    "M6831": f"{_DCR}::test_dcr_targets_never_run_terraform_off_the_bench_s_subscription",
    "M6832": f"{_DCR}::test_dcr_targets_never_run_terraform_off_the_bench_s_subscription",
}
