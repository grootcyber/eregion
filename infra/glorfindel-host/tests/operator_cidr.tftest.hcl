# SEC-G (audit du 13/11, V-40) : la seule source SSH admise vers Imladris — une adresse IPv4 publique,
# en /32. Une plage, une IPv6, une adresse privée ou réservée est refusée par la validation de
# operator_cidr, au plan. Planifié contre un faux azurerm, aucun appel à Azure ; les adresses sont des
# exemples (les plages de documentation restent admises : 203.0.113.0/24, 198.51.100.0/24). À la main :
#   terraform -chdir=infra/glorfindel-host init -backend=false -lockfile=readonly
#   terraform -chdir=infra/glorfindel-host test
# scripts/operator_cidr.py fait le même contrôle avant tout plan (tests/unit/test_operator_cidr.py).

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
  mock_data "azurerm_resources" {
    defaults = {
      resources = [{
        id                  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborstaging"
        name                = "stcelebrimborstaging"
        type                = "Microsoft.Storage/storageAccounts"
        resource_group_name = "rg-celebrimbor"
        location            = "westeurope"
        tags                = {}
      }]
    }
  }
}

mock_provider "azuread" {}

override_data {
  target = data.azurerm_virtual_machine.session_drain["vm-celebrimbor-gondolin"]
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin"
  }
}

override_data {
  target = data.azurerm_virtual_machine.session_drain["vm-celebrimbor-bree"]
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-bree"
  }
}

variables {
  # Une clé jetable (celle du test d'ID1 : sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  operator_cidr        = "203.0.113.7/32"
}

run "one_public_address_in_32_is_the_ssh_source" {
  command = plan

  assert {
    condition     = [for r in azurerm_network_security_group.host.security_rule : r.source_address_prefix] == ["203.0.113.7/32"]
    error_message = "la source SSH du NSG d'Imladris n'est pas l'adresse de l'opérateur, en /32"
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
    operator_cidr = "0.0.0.0/1"
  }
  expect_failures = [var.operator_cidr]
}

run "a_range_of_public_addresses_is_refused" {
  command = plan
  variables {
    operator_cidr = "203.0.113.0/24"
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

run "one_ipv6_address_is_refused" {
  command = plan
  variables {
    operator_cidr = "2001:db8::7/128"
  }
  expect_failures = [var.operator_cidr]
}

run "a_private_address_is_refused" {
  command = plan
  variables {
    operator_cidr = "192.168.1.20/32"
  }
  expect_failures = [var.operator_cidr]
}

run "a_shared_address_cgnat_is_refused" {
  command = plan
  variables {
    operator_cidr = "100.100.1.2/32"
  }
  expect_failures = [var.operator_cidr]
}

run "the_loopback_is_refused" {
  command = plan
  variables {
    operator_cidr = "127.0.0.1/32"
  }
  expect_failures = [var.operator_cidr]
}

run "an_address_without_its_prefix_is_refused" {
  command = plan
  variables {
    operator_cidr = "203.0.113.7"
  }
  expect_failures = [var.operator_cidr]
}

run "an_empty_answer_suffixed_32_is_refused" {
  command = plan
  variables {
    operator_cidr = "/32"
  }
  expect_failures = [var.operator_cidr]
}
