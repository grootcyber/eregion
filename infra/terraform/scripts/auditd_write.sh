# WRT1 (#1275) — qui écrit sous Linux : des montres d'écriture auditd, bornées, vers Syslog.
#
# Pas un script à lui : la suite de scripts/auditd.sh, dans la même extension CustomScript
# (auditd.tf, local.auditd_script), seulement quand `auditd_enabled` et `auditd_write_watch_enabled`
# sont vrais (terraform.tfvars ; désactivés par défaut). Terraform écrit juste avant la ligne
# WRT1_DIRS="<les dossiers>" (auditd_write_watch_dirs, validés : des chemins absolus simples, sans
# espace ni motif). auditd est donc posé, ses règles chargées, son greffon syslog vers local6 actif.
# Idempotent : relancé, il réécrit les mêmes fichiers.
#
# Ce qu'il pose :
#   - /etc/audit/rules.d/55-eregion-wrt1.rules : pour chaque dossier présent sur la VM, une montre
#     `-a always,exit -F arch=b64|b32 -F dir=<dossier> -F perm=w -k eregion_write` — l'exécutable,
#     l'uid, l'auid et le pid de chaque ouverture en écriture, création, renommage, suppression ou
#     troncature sous le dossier, jamais de chaque write() ; un dossier absent est sauté, et dit ;
#   - le battement de la montre : un minuteur systemd (eregion-write-beat.timer) qui écrit toutes les
#     5 minutes /var/lib/eregion/write-watch/beat, sous sa propre montre (clé eregion_write_beat).
#     C'est lui qui dit au lecteur (glorfindel/auditd_write.py) que la montre est posée et que ses
#     lignes arrivent : sans battement, la lecture est sans objet, jamais « personne n'a écrit ».
#
# Ce qui reste des hypothèses, à mesurer au banc avec Jonathan (docs/operations.md, « Qui écrit sous
# Linux, par auditd (WRT1) », W1–W8) : la forme des enregistrements PATH, le chemin relatif d'un
# appel à un dirfd, le volume, que l'extension se relance quand son script change.
#
# Le défaire : retirer /etc/audit/rules.d/55-eregion-wrt1.rules, puis `augenrules --load` ;
# `systemctl disable --now eregion-write-beat.timer`, retirer ses deux unités et
# /var/lib/eregion/write-watch (éteindre le drapeau ne défait rien sur la VM, comme pour AUD1).

WRT1_RULES=/etc/audit/rules.d/55-eregion-wrt1.rules
WRT1_BEAT_DIR=/var/lib/eregion/write-watch
mkdir -p "$WRT1_BEAT_DIR"
chmod 0700 "$WRT1_BEAT_DIR"

{
  echo "## WRT1 (#1275) — Eregion, the bench. Written by infra/terraform/scripts/auditd_write.sh."
  echo "## The watch's beat first: a key of its own, never counted as a writer."
  echo "-a always,exit -F arch=b64 -F dir=$WRT1_BEAT_DIR -F perm=w -k eregion_write_beat"
  echo "-a always,exit -F arch=b32 -F dir=$WRT1_BEAT_DIR -F perm=w -k eregion_write_beat"
  echo "## The watched folders: one event per opening for write, creation, rename, unlink, truncation."
  for d in $WRT1_DIRS; do
    if [ -d "$d" ] && [ ! -L "$d" ]; then
      echo "-a always,exit -F arch=b64 -F dir=$d -F perm=w -k eregion_write"
      echo "-a always,exit -F arch=b32 -F dir=$d -F perm=w -k eregion_write"
    else
      echo "WRT1: $d is not on the VM (or is a link): not watched" >&2
    fi
  done
} > "$WRT1_RULES"
chmod 0640 "$WRT1_RULES"

cat > /etc/systemd/system/eregion-write-beat.service <<'EOF'
# WRT1 (#1275) — written by infra/terraform/scripts/auditd_write.sh: the write watch's beat, which
# glorfindel/auditd_write.py reads (without it, its reading says nothing).
[Unit]
Description=Eregion WRT1: the beat of the auditd write watch

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'date -u +%%s > /var/lib/eregion/write-watch/beat'
EOF
cat > /etc/systemd/system/eregion-write-beat.timer <<'EOF'
# WRT1 (#1275) — written by infra/terraform/scripts/auditd_write.sh: every 5 minutes.
[Unit]
Description=Eregion WRT1: the beat of the auditd write watch, every 5 minutes

[Timer]
OnCalendar=*:0/5
AccuracySec=1s

[Install]
WantedBy=timers.target
EOF
chmod 0644 /etc/systemd/system/eregion-write-beat.service /etc/systemd/system/eregion-write-beat.timer

augenrules --load
systemctl daemon-reload
systemctl enable --now eregion-write-beat.timer
systemctl start eregion-write-beat.service

# Dit ce qui est chargé : le battement (deux règles), puis les dossiers suivis.
auditctl -l | grep -E 'key=eregion_write(_beat)?$'
test "$(auditctl -l | grep -cE 'key=eregion_write_beat$')" -eq 2
