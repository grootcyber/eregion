# SEC-G (audit du 13/11) : le canal d'Orodruin journalisé, la source SSH une seule adresse publique.
# - V-39 : le plan de données du compte du canal (StorageRead, StorageWrite, StorageDelete) part vers le
#   workspace du banc, qu'aucune identité admise au canal ne peut effacer (main.tf, channel_blobs).
# - V-40 : operator_cidr, une adresse IPv4 publique en /32 ; une plage, une IPv6, une adresse privée ou
#   réservée refusée au plan.
# Planifié contre un faux azurerm, aucun appel à Azure ; tous les identifiants sont des exemples. À la main :
#   terraform -chdir=infra/orodruin init -backend=false -lockfile=readonly
#   terraform -chdir=infra/orodruin test

mock_provider "azurerm" {
  mock_data "azurerm_resource_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor"
    }
  }
  mock_data "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.OperationalInsights/workspaces/law-celebrimbor"
    }
  }
  mock_data "azurerm_subscription" {
    defaults = {
      id              = "/subscriptions/00000000-0000-0000-0000-000000000000"
      subscription_id = "00000000-0000-0000-0000-000000000000"
    }
  }
  mock_data "azurerm_client_config" {
    defaults = {
      object_id = "00000000-0000-0000-0000-0000000000ee"
    }
  }
}

mock_provider "azurerm" {
  alias = "stratus"
}

mock_provider "azuread" {}

override_resource {
  target          = azurerm_storage_account.channel
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Storage/storageAccounts/storodruinexample"
  }
}

override_resource {
  target          = azurerm_storage_container.exercises
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Storage/storageAccounts/storodruinexample/blobServices/default/containers/exercises"
  }
}

override_resource {
  target          = azurerm_storage_container.watch
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Storage/storageAccounts/storodruinexample/blobServices/default/containers/watch"
  }
}

override_resource {
  target          = azurerm_linux_virtual_machine.host
  override_during = plan
  values = {
    id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Compute/virtualMachines/vm-orodruin"
    identity = { principal_id = "00000000-0000-0000-0000-0000000000a0", tenant_id = "00000000-0000-0000-0000-0000000000f0" }
  }
}

variables {
  # Une clé jetable (celle du test d'ID1 : sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  operator_cidr        = "203.0.113.7/32"
  watch_principal_id   = "00000000-0000-0000-0000-0000000000b0"
  watch_subnet_id      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-glorfindel/providers/Microsoft.Network/virtualNetworks/vnet-glorfindel/subnets/snet-glorfindel"
}

run "the_channel_s_blobs_are_journaled_to_the_bench_workspace" {
  command = plan

  assert {
    condition     = azurerm_monitor_diagnostic_setting.channel_blobs.target_resource_id == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Storage/storageAccounts/storodruinexample/blobServices/default"
    error_message = "le réglage de diagnostic ne vise pas le service de blobs du compte du canal"
  }
  assert {
    condition     = azurerm_monitor_diagnostic_setting.channel_blobs.log_analytics_workspace_id == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.OperationalInsights/workspaces/law-celebrimbor"
    error_message = "le journal du canal ne part pas vers le workspace du banc"
  }
  assert {
    condition     = toset([for l in azurerm_monitor_diagnostic_setting.channel_blobs.enabled_log : l.category]) == toset(["StorageRead", "StorageWrite", "StorageDelete"])
    error_message = "le journal du canal ne garde pas chaque lecture, écriture et suppression"
  }
}

run "one_public_address_in_32_is_the_ssh_source" {
  command = plan

  assert {
    condition     = azurerm_network_security_rule.ssh_operator.source_address_prefix == "203.0.113.7/32"
    error_message = "la source SSH d'Orodruin n'est pas l'adresse de l'opérateur, en /32"
  }
}

run "the_whole_internet_is_refused" {
  command = plan
  variables {
    operator_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.operator_cidr]
}

run "half_of_the_internet_is_refused" {
  command = plan
  variables {
    operator_cidr = "128.0.0.0/1"
  }
  expect_failures = [var.operator_cidr]
}

run "a_range_of_public_addresses_is_refused" {
  command = plan
  variables {
    operator_cidr = "198.51.100.0/24"
  }
  expect_failures = [var.operator_cidr]
}

run "ipv6_everywhere_is_refused" {
  command = plan
  variables {
    operator_cidr = "::/0"
  }
  expect_failures = [var.operator_cidr]
}

run "a_private_address_is_refused" {
  command = plan
  variables {
    operator_cidr = "10.1.2.3/32"
  }
  expect_failures = [var.operator_cidr]
}

run "a_link_local_address_is_refused" {
  command = plan
  variables {
    operator_cidr = "169.254.169.254/32"
  }
  expect_failures = [var.operator_cidr]
}

run "an_octet_beyond_255_is_refused" {
  command = plan
  variables {
    operator_cidr = "203.0.113.256/32"
  }
  expect_failures = [var.operator_cidr]
}
