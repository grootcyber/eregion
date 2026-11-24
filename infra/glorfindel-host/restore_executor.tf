# L'exécuteur de restore (FS1g, #1127 ; docs/design/file-actions-signee.md §11) — son application dans
# Entra ID, son principal et ses rôles, rien d'autre. C'est le conteneur `restore` du compose, à qui le
# point de jeton de la VM sera coupé (FS1d) : il a son propre principal, jamais l'identité managée de la
# VM, qui est celle de la watch. La watch ne restaure jamais (SEC7) ; lui ne restaure que sur une
# demande signée d'un humain, ses gardes rejouées.
#
# Ce que ce fichier pose, et rien d'autre (décision de Jonathan, 24/11) :
#   - une application mono-tenant (AzureADMyOrg), sans secret, sans propriétaire nommé, et son
#     principal ;
#   - « Eregion Glorfindel Restore » sur le seul groupe du banc, et sur le groupe du coffre s'il est
#     distinct (restore_vault_resource_group) — jamais l'abonnement ;
#   - son object id ajouté à restore_principals (main.tf, local.restore_principals_all) : « Restore
#     Neutralize » par VM de restore_vms, « Restore Staging » sur le seul compte de transit ;
#   - la partie publique de son certificat, si elle est donnée (restore_executor_certificate) : la clé
#     est tirée sur l'hôte, dans un répertoire que lui seul monte, jamais ici ni dans l'état. Jamais
#     un secret client (un mot de passe d'application) : il vivrait dans l'état de Terraform.
#
# Désactivé par défaut : `restore_executor_enabled = true` dans restore_executor.auto.tfvars (ignoré par
# git ; restore_executor.auto.tfvars.example), puis `make imladris-plan`, relu, puis `make imladris-up`
# sans YES — par Jonathan, sous un az login qui peut créer une application et attribuer un rôle.
# Désactivé, rien ne s'exécute dans le tenant (`count`, `for_each`).

locals {
  restore_vault_distinct = var.restore_executor_enabled && var.restore_vault_resource_group != "" && lower(var.restore_vault_resource_group) != lower(var.bench_resource_group)
  restore_executor_groups = var.restore_executor_enabled ? merge(
    { bench = data.azurerm_resource_group.bench.id },
    local.restore_vault_distinct ? { vault = data.azurerm_resource_group.restore_vault[0].id } : {}
  ) : {}
  # Les principaux qui restaurent, l'exécuteur compris quand il est allumé (main.tf les lit).
  restore_principals_all = merge(var.restore_principals,
  var.restore_executor_enabled ? { executor = azuread_service_principal.restore_executor[0].object_id } : {})
}

data "azurerm_resource_group" "restore_vault" {
  count = local.restore_vault_distinct ? 1 : 0
  name  = var.restore_vault_resource_group
}

resource "azuread_application" "restore_executor" {
  count            = var.restore_executor_enabled ? 1 : 0
  display_name     = "eregion-glorfindel-restore-executor"
  sign_in_audience = "AzureADMyOrg"
}

resource "azuread_service_principal" "restore_executor" {
  count     = var.restore_executor_enabled ? 1 : 0
  client_id = azuread_application.restore_executor[0].client_id
}

resource "azuread_application_certificate" "restore_executor" {
  count          = var.restore_executor_enabled && var.restore_executor_certificate != "" ? 1 : 0
  application_id = azuread_application.restore_executor[0].id
  type           = "AsymmetricX509Cert"
  value          = var.restore_executor_certificate
}

resource "azurerm_role_assignment" "restore_executor_restore" {
  for_each             = local.restore_executor_groups
  scope                = each.value
  role_definition_name = "Eregion Glorfindel Restore"
  principal_id         = azuread_service_principal.restore_executor[0].object_id
  principal_type       = "ServicePrincipal"
}
