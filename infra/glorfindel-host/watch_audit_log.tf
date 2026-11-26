# LOGF2 (#1233) : la watch d'Imladris lit le journal d'audit d'Entra ID, par Microsoft Graph — la date du
# dernier événement d'Entra, pour juger le silence d'une table d'Entra dans le workspace
# (glorfindel/entra_freshness.py, glorfindel/providers/azure/entra_last.py). Une permission d'application,
# en lecture, attribuée à l'identité managée de la VM, celle de la watch (et de la console et du bot,
# qui partagent le point de jeton de la VM) :
#   AuditLog.Read.All   la liste des événements d'audit (directoryAudits) et des connexions (signIns) de
#                       tout le tenant : rien n'est écrit, mais tout l'annuaire audité se lit
#                       (docs/design/modele-de-menace.md, « La lecture du journal d'audit d'Entra »).
# Rien d'autre : la watch ne lit que `$top=1`, la date d'un événement ; aucun autre rôle de Graph ici
# (les quatre lectures d'IR1a restent un geste à la main, hors de cet état).
#
# Désactivé par défaut : `watch_audit_log_read_enabled = true` dans watch_audit_log.auto.tfvars (ignoré
# par git ; watch_audit_log.auto.tfvars.example), puis `make imladris-plan`, relu, puis `make imladris-up`
# sans YES — par Jonathan, sous un az login qui peut consentir une permission d'application de Microsoft
# Graph (Administrateur des rôles privilégiés) : attribuer un rôle d'application de Graph, c'est le
# consentement d'administrateur. Les gestes : docs/operations.md, « La fraîcheur des journaux », « Le
# droit de lire le journal d'audit d'Entra ». Sans ce droit, la watch lit un 403 et passe le seuil des
# tables d'Entra à 7 jours, en le disant. Graph est trouvé par son identifiant publié, jamais écrit ici.
# Désactivé, rien n'est lu ni écrit dans le tenant (`count`, `for_each`).

locals {
  watch_audit_log_permissions = var.watch_audit_log_read_enabled ? toset(["AuditLog.Read.All"]) : toset([])
}

data "azuread_application_published_app_ids" "watch_audit_log" {
  count = var.watch_audit_log_read_enabled ? 1 : 0
}

data "azuread_service_principal" "watch_audit_log_msgraph" {
  count     = var.watch_audit_log_read_enabled ? 1 : 0
  client_id = data.azuread_application_published_app_ids.watch_audit_log[0].result["MicrosoftGraph"]
}

resource "azuread_app_role_assignment" "watch_audit_log" {
  for_each            = local.watch_audit_log_permissions
  app_role_id         = data.azuread_service_principal.watch_audit_log_msgraph[0].app_role_ids[each.value]
  principal_object_id = azurerm_linux_virtual_machine.host.identity[0].principal_id
  resource_object_id  = data.azuread_service_principal.watch_audit_log_msgraph[0].object_id
}
