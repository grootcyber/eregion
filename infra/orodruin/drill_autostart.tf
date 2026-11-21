# DRL1c (#613, docs/design/drill-banc.md §5.1, §11) — Orodruin allumé à l'heure du drill de la semaine, et
# éteint chaque soir. Le minuteur du drill (DRL1a) vit sur Orodruin, qui est désallouée entre les
# sessions : un démarrage planifié côté Azure la réveille 20 min avant l'heure du drill, et l'extinction
# de 23:00 UTC la rendort, tous les jours (décision 1 du 06/11).
#
# Le contrat, fixé par DRL1a (§11) et lu par infra/orodruin/drill_ops.py :
#   - la sortie drill_autostart_id : l'id d'un Microsoft.Logic/workflows ;
#   - son seul déclencheur : une Recurrence hebdomadaire en UTC, un jour, une heure, une minute — le
#     schedule du drill moins 20 min (drill_autostart_at, « tue 18:40 » pour « tue 19:00 ») ;
#   - créée Disabled, et Terraform ne la réactive jamais : seul orodruin-drill-arm l'active (POST …/enable),
#     orodruin-drill-disarm et le kill la désactivent (POST …/disable), par l'identité de l'opérateur.
#
# Pourquoi un modèle ARM, et non azurerm_logic_app_workflow et ses composants : dans azurerm 4.81.0, le
# déclencheur et l'action (azurerm_logic_app_trigger_recurrence, azurerm_logic_app_action_custom) se posent
# en réécrivant tout le workflow par un PUT qui ne porte pas son état (logic_apps.go,
# resourceLogicAppComponentUpdate — lu dans la source du fournisseur, pas mesuré). `ignore_changes =
# [enabled]` sur le workflow n'y peut rien : le premier apply, et chaque apply qui change l'heure,
# laisseraient la Logic App dans l'état qu'ARM donne à un PUT sans état. Ici, le modèle porte l'état
# lui-même, « Disabled », en un seul PUT ; et Terraform ne relit jamais l'état de la Logic App (il ne suit
# que le déploiement) : l'armement qui l'active ne fait aucun écart au plan. C'est l'équivalent de
# `ignore_changes = [enabled]` que le contrat admet, fermé de plus : un apply qui redéploie (une heure,
# une VM, un nom changés) la remet Disabled — un armement suspendu, jamais un réveil sans armement ; il
# faut réarmer, comme le §5.1 le dit déjà d'un schedule changé.
#
# Rien de plus pour l'identité d'Orodruin : son droit `start` sur une cible est déjà au contrat
# (injector_vm, main.tf). L'identité de la Logic App est la sienne, et n'allume qu'Orodruin.

locals {
  autostart_name = "logic-${local.name}-drill"
  autostart_days = {
    mon = "Monday", tue = "Tuesday", wed = "Wednesday", thu = "Thursday", fri = "Friday", sat = "Saturday", sun = "Sunday"
  }
  autostart_at = split(" ", var.drill_autostart_at)
  autostart_hm = split(":", local.autostart_at[1])
}

resource "azurerm_resource_group_template_deployment" "drill_autostart" {
  name                = "eregion-orodruin-drill-autostart"
  resource_group_name = azurerm_resource_group.host.name
  deployment_mode     = "Incremental"
  template_content    = file("${path.module}/drill_autostart.json")
  tags                = local.tags

  parameters_content = jsonencode({
    name     = { value = local.autostart_name }
    location = { value = azurerm_resource_group.host.location }
    tags     = { value = local.tags }
    vmId     = { value = azurerm_linux_virtual_machine.host.id }
    weekDay  = { value = local.autostart_days[local.autostart_at[0]] }
    hour     = { value = tonumber(local.autostart_hm[0]) }
    minute   = { value = tonumber(local.autostart_hm[1]) }
  })
}

locals {
  autostart_outputs = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.output_content)
}

# Une seule action, démarrer une VM ; assignable dans le seul groupe d'Orodruin, jamais au banc. C'est
# une hypothèse à mesurer (§6.2, point 2) : l'action HTTP de la Logic App n'attend pas la fin du démarrage
# (DisableAsyncPattern : elle ne suit pas l'opération, qu'il faudrait lire), et ARM ne demanderait alors
# rien d'autre que start/action. Si la mesure dit qu'il faut virtualMachines/read, on l'ajoute ici, à la
# même portée, et la mesure le dit.
resource "azurerm_role_definition" "drill_autostart" {
  name        = "eregion-orodruin-autostart"
  scope       = azurerm_resource_group.host.id
  description = "Orodruin (Eregion DRL1c) : la Logic App du drill démarre la VM d'Orodruin, et rien d'autre."

  permissions {
    actions = [
      "Microsoft.Compute/virtualMachines/start/action",
    ]
    not_actions = []
  }

  assignable_scopes = [azurerm_resource_group.host.id]
}

# À la portée de la VM d'Orodruin seule : compromise, l'identité de la Logic App n'allume qu'Orodruin, dont
# le minuteur ne joue qu'à son heure, sous son contrat, et seulement armé (le permis du canal).
resource "azurerm_role_assignment" "drill_autostart" {
  scope              = azurerm_linux_virtual_machine.host.id
  role_definition_id = azurerm_role_definition.drill_autostart.role_definition_resource_id
  principal_id       = local.autostart_outputs.principalId.value
  principal_type     = "ServicePrincipal"
}

# L'extinction de 23:00 UTC, chaque jour (le planning DevTest, qui désalloue), comme le banc
# (infra/terraform/vm.tf) : elle protège d'un Orodruin oublié allumé la nuit, et coupe une session tardive
# de l'opérateur (décision 1). Une occurrence à 19:00 UTC la laisse allumée de 18:40 à 23:00.
resource "azurerm_dev_test_global_vm_shutdown_schedule" "host" {
  virtual_machine_id    = azurerm_linux_virtual_machine.host.id
  location              = azurerm_resource_group.host.location
  enabled               = true
  daily_recurrence_time = "2300"
  timezone              = "UTC"
  tags                  = local.tags

  notification_settings {
    enabled = false
  }
}
