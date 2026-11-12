# LEV2 au banc — ce que le journal d'activité dit des gestes sur une VM (H7, H9, H12 ; H1, H2)

[← le banc](demarrer/banc.md) · la conception : [la levée après un restore](design/levee-probation.md) (§4, §14) · [ce qui reste à rejouer](demarrer/a-rejouer.md)

LEV2 (#690) lit qui a agi sur une VM par le plan de contrôle (`observed_actors`) et si ce tiers garde
ses droits (`observed_rights`) : `docs/glorfindel.md`, « La porte, pour information ». Ces lectures
reposent sur des formes que personne n'a mesurées. Cette page les mesure sur gondolin, **avant LEV3**,
qui en fera une règle de levée :

| # | La question | Ce que la mesure change |
|---|---|---|
| **H7** | chaque opération de la table du §4.1 s'écrit-elle sous la ressource que la table nomme ? Une Run Command v1 écrit-elle aussi une extension (`RunCommandLinux`), sous le même appelant, au même moment ? | la table ; une opération jamais rendue devient un vecteur dans l'invité |
| **H9** | le filtre `resourceUri eq '<vm>'` est-il exact, ou rend-il les enfants ? Combien de pages la lecture du groupe demande-t-elle ? | la lecture des enfants ; une borne de 20 pages trop courte retient trop |
| **H12** | combien de temps entre une écriture et sa lecture par l'API REST du journal ? | `lift.log_settle_s` (LEV3, 15 min par défaut) |
| **H1** | le Reader d'Imladris (anciennement H0) lit-il les attributions héritées de l'abonnement, à la portée de la VM ? | l'abonnement devient une portée illisible |
| **H2** | les éligibilités PIM (`roleEligibilityScheduleInstances`) se lisent-elles sous `*/read` ? | illisibles : toute lecture des droits l'est |

**La page a été jouée au banc le 12/11**, sur gondolin (« Joué le 12/11 », à la fin ; le rapport et
le verdict par hypothèse sont sur #690). Les commandes ci-dessous sont celles qui ont marché ce
jour-là ; les gestes 13 et 16 n'ont pas été joués. Jonathan lance chaque geste ; aucune session de
code ne le fait. Il n'y a pas d'outil qui écrit ces gestes : ils se tapent à la main, un par un, et
chacun a son retour en arrière.

## Les règles de la session

- **gondolin seulement** (`vm-celebrimbor-gondolin`, `rg-celebrimbor`), zone `bench`. Le lecteur
  refuse une autre zone.
- **Chaque écriture est sans effet** : une commande `true`, un tag `eregion-lev2` posé puis retiré,
  une règle de **refus**, jamais une allow. La valeur d'un tag posé par `az … update --set` est un
  texte (`eregion-lev2=lev2`) : `=1` se lit comme un entier, et az le refuse (« Expect <class 'str'>,
  got 1 », mesuré le 12/11). Les tags `eregion-target` et `eregion-zone` ne sont
  **jamais** touchés.
- **reimage** et **redeploy** ne se jouent pas : l'un remplace le disque OS, l'autre déplace la VM. Ils
  restent dans la table, non mesurés.
- **AL1 peut lever des cartes** sur Imladris pendant la session : une extension, une règle, une carte
  changée par un humain sont des détections du plan de contrôle (des cartes, jamais une action).
  C'est attendu ; elles s'acquittent à la fin.
- Le coût : une IP publique Standard quelques minutes, un disque de 4 Gio quelques minutes (les gestes
  facultatifs) ; le reste est gratuit.

## 0. Avant (5 min, lecture seule)

```bash
make bench-preflight                 # le banc tel qu'il est, rien n'est écrit
export LEV2=~/eregion-banc/lev2-$(date -u +%Y%m%d) RG=rg-celebrimbor VM=vm-celebrimbor-gondolin
mkdir -p "$LEV2"
note() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LEV2/gestures.txt"; }
NIC=$(az vm show -g $RG -n $VM --query 'networkProfile.networkInterfaces[0].id' -o tsv)
NSG=$(az network nic show --ids $NIC --query 'networkSecurityGroup.id' -o tsv)   # vide : celui du sous-réseau
SUBNET=$(az network nic show --ids $NIC --query 'ipConfigurations[0].subnet.id' -o tsv)
SUBNET_NSG=$(az network vnet subnet show --ids "$SUBNET" --query 'networkSecurityGroup.id' -o tsv)
az vm extension list -g $RG --vm-name $VM --query '[].{name:name, type:typePropertiesType}' -o table   # geste 3
IP=$(az network nic show --ids $NIC --query 'ipConfigurations[0].privateIPAddress' -o tsv)
DISK=$(az vm show -g $RG -n $VM --query 'storageProfile.osDisk.name' -o tsv)
```

`note` écrit l'heure, puis l'opération : on l'appelle **juste avant** chaque écriture. Le dossier
`$LEV2` reste sur le poste : les lectures brutes portent des identifiants.

## 1. Le lecteur, dans un second terminal (il tourne pendant toute la session)

```bash
python3 scripts/bench_lev2.py fetch --vm $VM --out "$LEV2/reads" \
  --since "$(date -u -d '-1 hour' +%Y-%m-%dT%H:%M:%SZ)" --every 30 --for 3600
```

Il lit, toutes les 30 s pendant une heure, comme Glorfindel lit : chaque ressource exactement (la VM,
sa carte, ses disques, ses NSG), puis chaque groupe en entier, jusqu'à 40 pages pour savoir où la
borne de 20 tombe. Il n'écrit rien sur Azure (`az … show`, `az rest --method get`) et refuse dans une
session de code. Le lancer d'un terminal neuf du poste, sous le `az login` de Jonathan.

## 2. Les gestes (20 à 30 min), chacun puis son retour

| # | Opération (ARM) | L'écriture | Le retour en arrière |
|---|---|---|---|
| 1 | `…/virtualMachines/runCommand/action` | `note Microsoft.Compute/virtualMachines/runCommand/action run-command-v1-true` puis `az vm run-command invoke -g $RG -n $VM --command-id RunShellScript --scripts true` | rien : la commande `true` reste le dernier script du modèle de la VM, inoffensif (c'est aussi H7 : une extension écrite ?) |
| 2 | `…/virtualMachines/runCommands/write` | `note Microsoft.Compute/virtualMachines/runCommands/write managed-true` puis `az vm run-command create -g $RG --vm-name $VM --name eregion-lev2 --script true` | `note Microsoft.Compute/virtualMachines/runCommands/delete managed-delete` puis `az vm run-command delete -g $RG --vm-name $VM --name eregion-lev2 --yes` |
| 3 | `…/virtualMachines/extensions/write` | la liste de l'étape 0 lue d'abord : **un type absent** de la VM, jamais `CustomScript` (une seule par VM Linux : c'est celle d'**`eregion-auditd`**, AUD1, `infra/terraform/auditd.tf`, quand `auditd_enabled` la pose ; la viser remplacerait son script, et le retour la supprimerait). Par exemple l'agent de Network Watcher, s'il est absent : `note Microsoft.Compute/virtualMachines/extensions/write nw-agent` puis `az vm extension set -g $RG --vm-name $VM --publisher Microsoft.Azure.NetworkWatcher --name NetworkWatcherAgentLinux` | `note Microsoft.Compute/virtualMachines/extensions/delete nw-agent-delete` puis `az vm extension delete -g $RG --vm-name $VM --name NetworkWatcherAgentLinux` ; la liste relue : la même qu'au début (`eregion-auditd` toujours là, si elle y était) |
| 4 | `…/virtualMachines/write` | `note Microsoft.Compute/virtualMachines/write vm-tag` puis `az vm update -g $RG -n $VM --set tags.eregion-lev2=lev2` | `az vm update -g $RG -n $VM --remove tags.eregion-lev2` |
| 5 | `Microsoft.Resources/tags/write` | `note Microsoft.Resources/tags/write tags-api` puis `az tag update --resource-id $(az vm show -g $RG -n $VM --query id -o tsv) --operation merge --tags eregion-lev2=2` | `az tag update --resource-id … --operation delete --tags eregion-lev2=2` |
| 6 | `…/resourceGroups/write` | `note Microsoft.Resources/subscriptions/resourceGroups/write group-tag` puis `az group update -n $RG --set tags.eregion-lev2=lev2` | par l'API des tags : `az tag update --resource-id $(az group show -n $RG --query id -o tsv) --operation delete --tags eregion-lev2=lev2`, noté (`note Microsoft.Resources/tags/write group-tag-delete`). `az group update --remove tags.eregion-lev2` échoue avec cet az (« Unexpected 'properties_to_remove' was not empty », 12/11) |
| 7 | `Microsoft.Compute/disks/write` | `note Microsoft.Compute/disks/write disk-tag` puis `az disk update -g $RG -n $DISK --set tags.eregion-lev2=lev2` | `az disk update -g $RG -n $DISK --remove tags.eregion-lev2` |
| 8 | `…/disks/beginGetAccess/action` | `note Microsoft.Compute/disks/beginGetAccess/action disk-sas` puis `az disk grant-access -g $RG -n $DISK --duration-in-seconds 60 --access-level Read` | attendu : **refusé** (un disque attaché à une VM qui tourne). Le rapport donne le statut et le code de l'échec tels qu'Azure les écrit, et ce qu'en fait Glorfindel : seul `Conflict` **sous le code** `OperationNotAllowed`, son `Started` avant lui, est un refus de la plateforme, **écarté** (REC1b, mesuré sur une Run Command) ; tout autre, **un échec qui compte**. Le 12/11, le disque a répondu `Conflict` sous le code `Conflict` : Glorfindel le compte, et le rapport le dit (LEV2b). Passé : `az disk revoke-access -g $RG -n $DISK` aussitôt |
| 9 | `…/networkInterfaces/write` | `note Microsoft.Network/networkInterfaces/write nic-tag` puis `az network nic update --ids $NIC --set tags.eregion-lev2=lev2` | `az network nic update --ids $NIC --remove tags.eregion-lev2` |
| 10 | `…/networkSecurityGroups/securityRules/write` | `note Microsoft.Network/networkSecurityGroups/securityRules/write deny-rule` puis `az network nsg rule create --nsg-name ${NSG##*/} -g ${${NSG#*/resourceGroups/}%%/*} -n eregion-lev2-deny --priority 4090 --direction Inbound --access Deny --protocol Tcp --source-address-prefixes 192.0.2.1/32 --destination-address-prefixes $IP --destination-port-ranges 9` (le NSG de la carte, sinon `$SUBNET_NSG`) | `note Microsoft.Network/networkSecurityGroups/securityRules/delete deny-rule-delete` puis `az network nsg rule delete … -n eregion-lev2-deny` : le retrait d'une règle est un geste aussi (Q16) |
| 11 | idem, sur le NSG **partagé** du sous-réseau, visant une **autre** adresse | `note Microsoft.Network/networkSecurityGroups/securityRules/write deny-rule-other-vm` puis la même règle sur `$SUBNET_NSG`, `--destination-address-prefixes 10.255.255.254/32` (aucune VM) | `az network nsg rule delete …` ; à lire : le corps de la requête est-il dans l'événement (`properties.requestbody`) ? Sinon la règle se juge sur ce qu'elle est sur Azure, ou compte |
| 12 | `…/networkSecurityGroups/write` | `note Microsoft.Network/networkSecurityGroups/write nsg-tag` puis `az network nsg update --ids ${NSG:-$SUBNET_NSG} --set tags.eregion-lev2=lev2` | `az network nsg update --ids … --remove tags.eregion-lev2` |
| 13 | `…/publicIPAddresses/join/action` (facultatif) | **Pas tant que la carte porte l'IP du banc** : le 12/11, la carte de gondolin portait `pip-celebrimbor-gondolin` (`infra/terraform/network.tf`) ; ce geste la remplacerait, et son retour la retirerait. Le geste n'a pas été joué. Sinon, **seulement la carte en quarantaine**, posé et retiré **pendant l'étape 5** de [`banc-t1486.md`](banc-t1486.md) (gondolin isolée par Imladris, avant tout restore) : `az network public-ip create -g $RG -n eregion-lev2-pip --sku Standard`, puis `note Microsoft.Network/publicIPAddresses/join/action pip-join` et `az network nic ip-config update --ids $NIC/ipConfigurations/<nom> --public-ip-address eregion-lev2-pip` | dans la même étape 5 : `az network nic ip-config update --ids … --remove publicIPAddress`, puis `az network public-ip delete -g $RG -n eregion-lev2-pip`. **Avant l'étape 6 (le restore)**, relire `az network nic show --ids $NIC --query 'ipConfigurations[].publicIPAddress' -o tsv` : rien d'autre que `pip-celebrimbor-gondolin`, celle du banc, sinon ne pas restaurer. L'étape 7 lève seule : une IP restée sortirait de quarantaine avec gondolin (H8 tombée le 12/11 : [la conception](design/levee-probation.md), §14). Un doute : sauter ce geste |
| 14 | `…/userAssignedIdentities/assign/action` (facultatif) | `az identity create -g $RG -n eregion-lev2-id`, puis `note Microsoft.ManagedIdentity/userAssignedIdentities/assign/action identity-assign` et `az vm identity assign -g $RG -n $VM --identities eregion-lev2-id` | `az vm identity remove -g $RG -n $VM --identities eregion-lev2-id`, puis `az identity delete -g $RG -n eregion-lev2-id` |
| 15 | `…/attachDetachDataDisks/action` (facultatif) | `note Microsoft.Compute/disks/write disk-create` puis `az disk create -g $RG -n eregion-lev2-disk --size-gb 4 --sku Standard_LRS` (noté : sinon, à moins d'une heure du geste 7, le rapport range la création sous `disk-tag`, comme le 12/11), puis `note Microsoft.Compute/virtualMachines/attachDetachDataDisks/action disk-attach` et `az vm disk attach -g $RG --vm-name $VM --name eregion-lev2-disk` | `az vm disk detach -g $RG --vm-name $VM --name eregion-lev2-disk`, puis `az disk delete -g $RG -n eregion-lev2-disk --yes` |
| 16 | `Microsoft.SerialConsole/serialPorts/connect/action` (H6, facultatif) | si la console série est active : `note Microsoft.SerialConsole/serialPorts/connect/action serial` puis `az serial-console connect -g $RG -n $VM`, et la quitter aussitôt | rien |
| 17 | `…/virtualNetworks/subnets/write` (Q16) | une écriture du sous-réseau qui ne change rien : `note Microsoft.Network/virtualNetworks/subnets/write subnet-same` puis `az network vnet subnet update --ids "$SUBNET" --network-security-group "$SUBNET_NSG"` (le NSG qu'il porte déjà ; sans NSG de sous-réseau, sauter ce geste : n'en poser aucun) | rien : rien n'a changé. Relire `az network vnet subnet show --ids "$SUBNET" --query 'networkSecurityGroup.id' -o tsv` : le même |

Le geste 8 dit comment un échec se lit : son statut et son code, et s'il compte (§4.1). Le geste 11 répond à la
question du NSG partagé : une règle qui ne couvre pas gondolin ne doit pas compter.

**Pourquoi le geste 13 reste couplé à l'exercice T1486.** Il demande une carte déjà en quarantaine,
et seul un isolement par Imladris la met là. Aucun exercice non destructif du banc n'isole gondolin à coup
sûr : le T1136.001 mesuré le 31/10 a escaladé un instantané à 35 %, sans isolement
(`docs/banc-bl1.md`). Le geste se pose et se retire donc dans l'étape 5, et se relit avant le restore.

Deux gestes d'une même opération (10 et 11, l'écriture d'une règle) se notent **à une minute d'écart
au moins** : le rapport borne chacun au suivant de la même opération.

## 3. La lecture, puis le rapport (10 min)

Laisser le lecteur finir son heure (ou l'arrêter 30 min après le dernier geste : H12), puis :

```bash
python3 scripts/bench_lev2.py report --dir "$LEV2/reads" --gestures "$LEV2/gestures.txt" --out "$LEV2/rapport.md"
```

Le rapport ne porte **aucun identifiant** (des sortes de ressources, des opérations, des durées) :

- **les gestes (H7, H12)** : pour chacun, lu ou non ; la ressource de l'événement (la VM, un enfant
  de la VM, une carte, une règle…, ou une autre ressource, dite par son type et sa place : du groupe
  de la VM hors de la VM, d'un autre groupe, d'un autre abonnement ; jamais par son nom) ; la lecture
  qui l'a rendu (exacte, ou le groupe) ; ses statuts ; un échec, son statut et son code tels
  qu'Azure les écrit, et ce qu'en fait Glorfindel (chaque événement jugé une fois, quel que soit le
  nombre de tours qui l'ont relu) ; la latence de sa première lecture, l'écart entre l'heure notée et
  `eventTimestamp`, et entre `eventTimestamp` et `submissionTimestamp`. Le nom d'une opération
  (`microsoft.resources/subscriptions/resourcegroups/write`) n'est pas un identifiant : il reste ;
- **H7, la Run Command v1** : une écriture d'extension du même appelant, au même moment, ou non ;
- **H9** : le filtre exact rend-il d'autres ressources que la sienne ; le nombre de pages de chaque
  lecture, et si le groupe dépasse la borne de 20.

## 4. H1 et H2, sous l'identité d'Imladris (2 min, un `GET` chacun)

Sur Imladris (`make imladris-ssh`, puis `exit`) :

```bash
docker exec eregion-watch glorfindel door vm-celebrimbor-gondolin --days 1
```

La commande lit, sans rien écrire, comme la watch lit pour la carte d'isolement. Ses dernières
lignes disent, à chaque portée, les attributions lues et **combien viennent d'une autre portée**
(H1 : celles de l'abonnement, lues à la portée de la VM ; zéro alors que l'abonnement en porte :
H1 tombe), et les éligibilités PIM lues ou refusées (H2 : `HTTP 403` : H2 tombe ; le 12/11, un
`HTTP 400 AadPremiumLicenseRequired` : le tenant du banc n'a pas la licence de PIM). Recopier ces
lignes dans le rapport, sans identifiant.

## 5. Remettre en état (5 min)

- Chaque retour en arrière du tableau fait ; `az vm show -g $RG -n $VM --query tags` ne porte plus
  `eregion-lev2` ; la liste des extensions (`az vm extension list`) la même qu'à l'étape 0. Le
  contrôle « `eregion-auditd` toujours là » ne vaut que si `auditd_enabled` la pose : le 12/11,
  gondolin ne portait que `AzureMonitorLinuxAgent`. Sur la carte, aucune IP publique **autre que
  celle du banc** (`pip-celebrimbor-gondolin`, posée par Celebrimbor, `infra/terraform/network.tf`) ;
  ni règle `eregion-lev2-*`, ni IP, ni identité, ni disque `eregion-lev2-*` dans `$RG`.
- Les cartes d'AL1 levées par la session : acquittées sur la console d'Imladris.
- `make bench-preflight` : le banc comme au début.

## Ce que Jonathan note à la fin

Le rapport (`$LEV2/rapport.md`, sans identifiant) va dans l'issue #690. LEV3 part de là : la table
du §4.1 corrigée si un geste ne se lit pas où elle le dit, la lecture des enfants si le filtre n'est
pas exact, la borne si le groupe la dépasse, `lift.log_settle_s` réglé sur la latence mesurée.

## Joué le 12/11

Sur gondolin, de 10:21 à 11:25 UTC environ, avant et après l'exercice T1486 du même jour. Le
rapport (`bench_lev2.py report`) : 19 gestes notés, 95 tours de lecture, aucun identifiant ; le
détail et le verdict par hypothèse sont sur #690. En bref :

- **H1 tient** pour les attributions héritées : 19 lues à la portée de la VM, dont 14 d'une autre
  portée ; 14 sur 14 sur la carte, les disques, le NSG et le sous-réseau. L'abonnement et le groupe
  ne s'y distinguent pas.
- **H2 tombe dans sa forme** : ni lues ni « 403 », mais `HTTP 400 AadPremiumLicenseRequired` à
  chaque portée. Ce que LEV3 en fait (« aucune éligibilité possible », ou « droits illisibles ») est
  une décision de Jonathan.
- **H7 est lue** : la Run Command v1 n'écrit pas d'extension ; les runcommands, les extensions et
  les tags posés par l'API des tags (`providers/tags`) s'écrivent comme enfants de la VM ;
  `identity-assign` (geste 14) et `disk-attach` (geste 15) ne se lisent pas sous leur opération.
- **H9 tombe** : le filtre `resourceUri eq` rend aussi les enfants (de la VM, les règles du NSG) ;
  une page au plus par lecture exacte, deux pour le groupe, loin de la borne de 20. Sous l'identité
  d'Imladris, la lecture du journal du groupe a rendu un `HTTP 500 MultipleErrorsOccurred` (étape 4).
- **H12 est lue** : la première lecture vient 61,8 à 142,6 s après le geste ; `submissionTimestamp`
  suit `eventTimestamp` de 39 à 537,9 s. Les cartes d'AL1 sont arrivées 2 à 11 min après le geste.

À ne pas mal lire, et ce que la page en a gardé :
- **`vm-tag` est une note sans écriture** : `=1` refusé par az ; le geste refait sous `vm-tag-texte`,
  avec une valeur texte (la forme du tableau ci-dessus).
- **Le retour du geste 6** a été fait par l'API des tags, sans note : le rapport range cette écriture
  sous `tags-api`, qui porte donc aussi « le groupe ». La note `group-tag-delete` du tableau l'évite.
- **Un blocage autonome de Glorfindel** sur gondolin (un vrai brute force SSH venu d'Internet, 11:18
  UTC) a écrit une règle sur le NSG partagé pendant les dernières minutes du lecteur : une écriture
  d'un autre appelant, qui n'est pas un geste.
- **Les cartes d'AL1** attribuent une règle du NSG partagé à chaque VM derrière lui (« couvre bree,
  gondolin »), y compris la règle du geste 11, qui ne couvre aucune VM.
- **Trois défauts de l'outil**, corrigés par LEV2b (#763). Le rapport, recomposé sur les lectures
  du 12/11, ne change qu'en ces trois lignes :
  - `disk-sas` disait « Conflict conflict : un échec, il compte », le code mis en minuscules, et se
    lisait comme une comparaison selon la casse. Il n'y en a pas : le code était `Conflict`, pas
    `OperationNotAllowed`. Glorfindel ne reconnaît que ce refus-là (REC1b, mesuré sur une Run Command
    d'une VM désallouée) ; il **compte** donc le refus du disque, et le verdict de l'outil était le
    sien. C'est le guide qui attendait un refus écarté. Le rapport dit maintenant « `Conflict`
    `Conflict` : un échec, il compte : Glorfindel n'écarte un `Conflict` que sous le code
    `OperationNotAllowed` ». Faut-il écarter aussi ce refus du disque ? La question va à LEV3.
  - le masquage réécrivait l'opération du geste 6 (`microsoft.resources<ressource>`) : le nom d'une
    opération de `Microsoft.Resources` reste, un identifiant est toujours masqué ;
  - `disk-tag` disait « une autre ressource » : c'était un disque du groupe, hors de la VM, celui que
    le geste 15 crée (`az disk create`, sans note, dans l'heure du geste 7). Le rapport dit
    « une autre ressource (`microsoft.compute/disks`, du groupe de la VM, hors de la VM) », et le
    geste 15 note maintenant la création.
  - En corrigeant, un quatrième, sans effet le 12/11 : chaque tour relit les mêmes événements, et l'outil jugeait chaque
    copie. Un `Started` relu un tour de plus que son refus restait en trop, et le refus n'en était
    plus un. Chaque événement est maintenant jugé une fois, comme Glorfindel le lit.
