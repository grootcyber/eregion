# SEC17 : les VM du banc que le restore défend — « Eregion Glorfindel Restore Neutralize » sur chacune,
# pour chaque principal de restore_principals (la console, le bot), jamais sur le groupe (main.tf).
# Commité : chaque plan de H0 la relit, un `make imladris-up` ordinaire ne retire rien. Une VM
# ôtée d'ici perd la neutralisation au prochain apply (le plan le montre) ; restaurée, elle l'est quand
# même, la neutralisation refusée et dite sur la carte.
restore_vms = ["vm-celebrimbor-gondolin", "vm-celebrimbor-bree"]

# RST1 : le compte de transit du restore du banc (restore_staging_storage, `make celebrimbor-output`),
# dans le groupe du banc — « Eregion Glorfindel Restore Staging » (listKeys) sur ce seul compte, pour
# chaque principal de restore_principals, jamais sur le groupe (main.tf).
restore_staging_storage = "stcelebrimborstaging"
