# WRT1 (#1275) : qui écrit sous Linux, par auditd — les montres d'écriture, posées par l'extension
# d'auditd (auditd.tf, scripts/auditd.sh puis scripts/auditd_write.sh), planifiées contre de faux
# azurerm, azapi, null et azuread : aucun appel à Azure. La CI le lance à chaque PR (ci.yml, job
# terraform-test, CI4) ; à la main :
#   terraform -chdir=infra/terraform init -backend=false -lockfile=readonly
#   terraform -chdir=infra/terraform test -filter=tests/auditd_write.tftest.hcl
# Éteintes (le défaut), le script de l'extension est celui d'AUD1, à l'octet : rien ne change sur le
# banc. Allumées sans auditd, rien n'est posé. Allumées avec auditd, le script d'AUD1, la ligne des
# dossiers, puis celui de WRT1, rien d'autre ; la DCR ne change pas. Des dossiers hors des bornes sont
# refusés au plan. tests/unit/test_auditd_write.py tient le même contrat en lisant les fichiers.

mock_provider "azurerm" {}
mock_provider "azapi" {}
mock_provider "null" {}
mock_provider "azuread" {}

variables {
  # La clé jetable du test d'ID1 (sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  # Hermétique face au terraform.tfvars de l'opérateur (qui peut les activer).
  activity_log_enabled        = false
  entra_logs_enabled          = false
  auditd_enabled              = true
  auditd_write_watch_enabled  = false
  auditd_write_watch_dirs     = ["/home", "/root", "/srv", "/var/www", "/var/backups", "/mnt/testdata"]
  cron_logs_enabled           = false
  process_io_enabled          = false
  entra_test_identity_enabled = false
  entra_bench_unit_enabled    = false
  bench_reader_enabled        = false
}

run "off_the_script_is_aud1_s_to_the_byte" {
  command = plan

  assert {
    condition = alltrue([for k, e in azurerm_virtual_machine_extension.auditd :
    base64decode(jsondecode(e.settings).script) == file("scripts/auditd.sh")])
    error_message = "montres éteintes, le script de l'extension n'est plus celui d'AUD1 : le banc changerait sans qu'on le demande"
  }
  assert {
    condition     = keys(azurerm_virtual_machine_extension.auditd) == keys(azurerm_linux_virtual_machine.baseline)
    error_message = "l'extension d'auditd n'est plus sur chaque VM du banc"
  }
}

run "on_without_auditd_nothing_is_posed" {
  command = plan

  variables {
    auditd_enabled             = false
    auditd_write_watch_enabled = true
  }

  assert {
    condition     = length(azurerm_virtual_machine_extension.auditd) == 0
    error_message = "des montres d'écriture sont posées sans auditd"
  }
  assert {
    condition     = toset(azurerm_monitor_data_collection_rule.celebrimbor.data_sources[0].syslog[0].facility_names) == toset(["auth", "authpriv", "syslog", "daemon"])
    error_message = "les montres d'écriture, sans auditd, changent les facilités de la DCR"
  }
}

run "on_aud1_s_script_the_dirs_then_wrt1_s_nothing_else" {
  command = plan

  variables {
    auditd_write_watch_enabled = true
  }

  assert {
    condition = alltrue([for k, e in azurerm_virtual_machine_extension.auditd :
      base64decode(jsondecode(e.settings).script) == join("", [file("scripts/auditd.sh"),
    "WRT1_DIRS=\"/home /root /srv /var/www /var/backups /mnt/testdata\"\n", file("scripts/auditd_write.sh")])])
    error_message = "montres allumées, le script n'est pas celui d'AUD1, la ligne des dossiers, puis celui de WRT1"
  }
  assert {
    condition = alltrue([for k, e in azurerm_virtual_machine_extension.auditd :
      strcontains(base64decode(jsondecode(e.settings).script), "-F dir=$d -F perm=w -k eregion_write\"")
    && strcontains(base64decode(jsondecode(e.settings).script), "-F perm=w -k eregion_write_beat\"")])
    error_message = "le script ne pose pas les montres d'écriture (eregion_write) et leur battement (eregion_write_beat)"
  }
  assert {
    condition     = keys(azurerm_virtual_machine_extension.auditd) == keys(azurerm_linux_virtual_machine.baseline)
    error_message = "les montres ne sont pas posées par l'extension d'auditd de chaque VM du banc"
  }
  assert {
    condition     = toset(azurerm_monitor_data_collection_rule.celebrimbor.data_sources[0].syslog[0].facility_names) == toset(["auth", "authpriv", "syslog", "daemon", "local6"])
    error_message = "les montres d'écriture changent les facilités de la DCR : leurs lignes vont dans local6, comme celles d'AUD1"
  }
}

run "the_dirs_are_the_operator_s_bounded" {
  command = plan

  variables {
    auditd_write_watch_enabled = true
    auditd_write_watch_dirs    = ["/data", "/opt/app-1"]
  }

  assert {
    condition = alltrue([for k, e in azurerm_virtual_machine_extension.auditd :
    strcontains(base64decode(jsondecode(e.settings).script), "\nWRT1_DIRS=\"/data /opt/app-1\"\n")])
    error_message = "les dossiers suivis ne sont pas ceux d'auditd_write_watch_dirs"
  }
}

run "refused_a_virtual_or_noisy_dir" {
  command = plan
  variables {
    auditd_write_watch_dirs = ["/home", "/var/log"]
  }
  expect_failures = [var.auditd_write_watch_dirs]
}

run "refused_the_root_or_a_relative_or_a_dotted_path" {
  command = plan
  variables {
    auditd_write_watch_dirs = ["/", "home", "/home/../etc", "/a b"]
  }
  expect_failures = [var.auditd_write_watch_dirs]
}

run "refused_more_than_eight_or_twice_the_same" {
  command = plan
  variables {
    auditd_write_watch_dirs = ["/a", "/b", "/c", "/d", "/e", "/f", "/g", "/h", "/i"]
  }
  expect_failures = [var.auditd_write_watch_dirs]
}

run "refused_the_same_dir_twice" {
  command = plan
  variables {
    auditd_write_watch_dirs = ["/srv", "/srv"]
  }
  expect_failures = [var.auditd_write_watch_dirs]
}

run "refused_the_beat_s_own_dir" {
  command = plan
  variables {
    auditd_write_watch_dirs = ["/var/lib/eregion"]
  }
  expect_failures = [var.auditd_write_watch_dirs]
}
