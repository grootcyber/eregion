# T1486 au banc — rejouer le rançongiciel, et dater ses chiffres (RAN1)

[← le banc](demarrer/banc.md) · le modèle : [la session de BL1](banc-bl1.md) · [ce qui reste à rejouer](demarrer/a-rejouer.md)

Le README dit : « ~1 min to contain a ransomware VM, 21m29s to restored service ». Ces chiffres
viennent du run `20260609T190824Z` (09/06, l'ancienne sandbox ; `ROADMAP.md`,
`docs/historique.md`). Ce jour-là, la watch, le restore et la levée tournaient sur le même poste.
Depuis, Glorfindel vit sur H0, l'attaque part d'Orodruin et se demande dans Dagorlad. Cette page
rejoue le rançongiciel sur gondolin, avec la version en service (0.5.8 sur H0 et Orodruin), et en
mesure trois temps :

- **la détection** : de T0 à la détection de la watch, puis à sa carte ;
- **le confinement** : de T0 à l'isolement relu sur Azure ;
- **le service rendu** : de T0 à la restauration finie, puis à la levée.

La page a été écrite sans Azure (RAN1, #665). Chaque commande existe ; ce qu'elle affirme est
marqué ainsi :
- *lu dans le code* : le fichier et la ligne sont cités ;
- *vérifié à blanc* : la commande a tourné sans Azure (`make -n`, `--dry-run`, un `HOME` jetable),
  et sa sortie est celle qui est citée ;
- **non vérifié** : ni l'un ni l'autre, à voir pendant la session.

Jonathan lance chaque geste ; rien de cette page n'a encore été joué au banc.

## Ce que le code décide avant la session

### La cible : gondolin, et elle seule

bree n'est pas inscrite (`enrolled: false`, `infra/terraform/config.yaml:52-55`) : aucun injecteur
ne la vise, et Dagorlad ne lui donne pas de carte bleue (`docs/dagorlad.md`, « Ce que c'est »). Le
rançongiciel se rejoue sur gondolin, inscrite `bench`, que H0 tient en `non_disruptive`.

### Le chemin : une demande de Dagorlad, puis `make orodruin-exercise`

T1486 est une technique **destructive** du catalogue (`destructive: true`,
`technique_catalog.yaml:78-96`). Trois chemins existent ; un seul est le chemin prévu.

| Chemin | Ce qu'il fait | Verdict |
|---|---|---|
| **Dagorlad** : le fil T1486 → gondolin, « Request run from Orodruin », puis `make orodruin-exercise REQUEST=…` | le nom de la cible tapé sur le poste, comparé par Orodruin au nom qu'Azure lui donne (`annatar/runner/engine.py:267-274`) ; le scénario construit depuis le catalogue, son `setup` compris (`annatar/campaign/synthesizer.py:188-196`) ; l'identifiant de la demande dans la fenêtre et le rapport ; la chronologie de Dagorlad | **le chemin prévu, mesuré** |
| `annatar run annatar/scenarios/azure/ransomware-vm.yaml --yes` dans le `docker run` durci d'Orodruin (`make orodruin-ssh`) | les mêmes gardes d'inscription, de zone et de watch, la fenêtre et le rapport publiés (`annatar/cli.py:89`) ; **pas** de nom tapé (la garde ne joue que pour une demande, `engine.py:267`), pas de chronologie dans Dagorlad | un repli, mesuré aussi, moins gardé |
| une campagne déclarée (`make orodruin-campaign-plan CAMPAIGN_DECLARED=…`) | refusée deux fois : T1486 est un script maison et destructif (`annatar/campaign/declared.py:119-122`) ; `orodruin-campaign-plan` ne passe jamais `--allow-destructive` (`Makefile:1546`) | **écartée** |

Aucun de ces chemins n'est un run de développement tant que `--without-glorfindel` n'est pas donné.
Le script de T1486 (`scripts/vm/ransomware_sim.sh`, son empreinte épinglée au catalogue) est
antérieur à la règle « des bibliothèques publiques seulement » : Dagorlad le joue, une campagne
déclarée le refuse.

### Le nettoyage du disque, et les 10 minutes

- **`setup_testdata.sh` tourne dans le fil**, sur gondolin, par Run Command, juste avant l'attaque,
  sous la fenêtre d'exercice déjà ouverte ; puis vient le contrôle d'intégrité du disque
  (`engine.py:388-404`). Il ne fait que retirer les fichiers d'un run précédent et poser le marqueur
  (`scripts/vm/setup_testdata.sh`). Sur ce chemin, **`annatar clean` n'est pas nécessaire**.
- **Les 10 minutes.** La règle `ransomware-disk-write` lit les 10 dernières minutes de `Perf`
  (`ago(10m)`, `glorfindel/rules/azure/detection_rules.yaml:55-80`), et le RulePoller de H0 la
  relit toutes les 30 s, sans rien savoir de T0. Une écriture forte avant le fil serait vue :
  - hors de la fenêtre, comme un incident réel, et gondolin, en `non_disruptive`, serait isolée
    avant l'attaque ;
  - dans la fenêtre, avant T0, et le T0 du run ne serait plus cru (la watch a vu la VM avant lui :
    `analysis/containment.py`, `t0_refusal`).

  Deux sources connues : le démarrage de la VM (le rattrapage d'apt et de snap, 52,2 MB/s mesurés
  le 05/10, `detection_rules.yaml:36-38`) et un run précédent. D'où : 10 minutes de calme après le
  démarrage de gondolin, et après tout run précédent. L'ancienne consigne (10 min après
  `annatar clean`, `docs/operations.md`) visait le même piège.

### Le point de restauration propre : depuis H0

H0 a le droit d'un instantané : le rôle « Eregion Glorfindel Response » porte l'action de
sauvegarde du coffre (`infra/identities/glorfindel-response.json`), et le coffre est dans le groupe
du banc (`infra/terraform/backup.tf:1-4`), où H0 tient ce rôle. `glorfindel snapshot` se lance donc
dans le conteneur de la console de H0, comme ses boutons (SEC18 : il écrit `runs/console/`).

Le poste le peut aussi, sous le principal de la console. Mais H0 suffit, sans secret sur la ligne de
commande. Le point à la demande est gardé 30 jours (`glorfindel/providers/azure/backup.py:45`).

### La restauration : sur le poste, sous le principal de la console

- **H0 ne restaure jamais.** Son identité n'a pas le rôle Restore, et son Terraform refuse de le
  lui donner (`infra/glorfindel-host/README.md`, « Ce que la VM est »). Les boutons 🔄 Restore de sa
  console et de son bot partent sous cette identité : Azure les refuse, et la carte le dit.
- **Le restore part donc du poste**, par la CLI, avec la paire de la console pour cette commande
  seulement (`docs/operations.md`, « Identités Azure ») :
  `AZURE_CLIENT_ID=$EREGION_CONSOLE_AZURE_CLIENT_ID AZURE_CLIENT_SECRET=$EREGION_CONSOLE_AZURE_CLIENT_SECRET`.
  Ce principal tient `Reader`, Response et Restore sur le groupe du banc, et la neutralisation sur
  gondolin.
- **`--before` est obligatoire sur le poste.** Sans lui, la commande prend le moment de la carte en
  attente de la VM ; mais les cartes sont sur H0, pas sur le poste. Elle refuse alors, avant tout
  appel à Azure (`glorfindel/cli.py:2351-2376`). *Vérifié à blanc* : « Moment de l'attaque inconnu
  pour vm-celebrimbor-gondolin : aucune carte en attente de cette VM n'en donne un ». On lui donne
  le moment noté juste après le point propre (`AVANT`, étape 2) : le point le plus récent avant
  lui est celui-là. Un instantané que H0 prendrait seul après l'isolement est postérieur, donc écarté.
- **La neutralisation (SEC17)** se fait sur gondolin, par le principal qui restaure, avant
  l'échange des disques (`glorfindel/providers/azure/restore.py:149-154`). Une Run Command sans
  effet devient la dernière : un disque restauré rejouerait sinon `ransomware_sim.sh` au démarrage
  (vu le 05/10). Il faut « Eregion Glorfindel Restore Neutralize » sur gondolin, pour la console
  (`restore_vms`, `restore_principals` ; `docs/operations.md`, « Depuis un rôle Restore d'avant
  SEC17 »). La sortie du restore dit si elle a eu lieu.
- **`--keep-isolated`, toujours** (pourquoi : la section suivante).

### La levée : sur H0, par sa watch (REC1)

- **La watch de H0 lit la reprise sur Azure, et lève elle-même** (REC1, #668 ; `docs/glorfindel.md`,
  « La reprise lue sur Azure »). À chaque minute, pour gondolin isolée, elle lit dans le coffre le
  dernier job de restore depuis l'isolement. Elle vérifie qu'il est fini et `Completed`, que son
  point précède l'incident (l'isolement, ou la première détection de la carte en attente si elle
  est avant), que la VM tourne, et que la dernière parole de Run Command, **datée après le
  restore**, est la commande inoffensive. Elle émet alors son propre `recovery_complete`, et la
  levée suit : seule en `non_disruptive`, une carte en `human_only`. Elle ne lit jamais un fichier
  du poste, et n'a besoin que de son Reader sur le groupe du banc, où est le coffre.
- **`restore --wait` lève l'isolement dans son propre processus.** Il construit le
  `recovery_complete`, le garantit pour ce processus et le passe aussitôt au graphe
  (`cli.py:1581-1594`). La levée autonome n'est permise que pour ce signal-là, ou pour celui relu par
  `glorfindel respond` dans `~/.glorfindel/recovery_signals/` du même hôte
  (`glorfindel/signal_origin.py:29-35`, `glorfindel/agent.py:1449-1478`). **La watch de H0 ne lit
  jamais ce répertoire d'elle-même**, et celui du poste encore moins.
- **Sur le poste, ce processus déciderait seul.** Il appellerait le modèle avec la clé du poste et
  la configuration du poste (le mode de gondolin, sa préparation). Puis, s'il levait l'isolement,
  il le ferait sans l'état d'isolation de H0.
- **H0 reposerait l'isolement.** Sa réaffirmation relit chaque minute les isolations de son état.
  Elle trouverait les règles disparues et les reposerait une fois, gondolin étant en
  `non_disruptive` (`glorfindel/reassert.py:271-290`).
- D'où `--keep-isolated` sur le poste (`cli.py:1581`) : le poste ne lève pas, la watch de H0 lève
  (ci-dessus, et l'étape 7). Si elle écrit une carte au lieu de lever (la neutralisation non
  constatée, un point d'après l'isolement), la levée se fait à la main sur H0, après la vérification
  de l'étape 7 :
  - **↩️ Release** dans sa console ;
  - ou `docker exec eregion-war-room glorfindel release …`, dans le conteneur de la console
    (`docs/banc-bl1.md`, étape 5).

  La levée est relue sur Azure, et l'état de H0 suit. Elle n'est pas reposée : elle marque la levée
  en cours (`releasing_at`) sous le verrou de la VM, que la réaffirmation prend aussi avant de la
  sauter (`glorfindel/reassert.py:141`, `:239-240`).

## Le manque, comblé : un seul geste humain (REC1)

Le README décrit une boucle où la seule étape humaine est d'approuver le restore, la levée
autonome suivant le `recovery_complete`. Avant REC1, ce n'était pas vrai sur le banc : il fallait
restaurer depuis le poste, puis lever sur H0, dont la watch ne voyait pas la reprise. **Depuis REC1,
il ne reste qu'un geste humain** : le restore, sur le poste, puisque H0 n'en a pas le droit. La levée
est celle de la watch de H0, une fois la reprise lue sur Azure. Le temps du « service rendu »
mesuré ici inclut le temps de ce geste ; on le donne aussi au sens du README, sans le temps de
décision humaine (étape 8).

Porter à la main le signal du poste dans `~/.glorfindel/recovery_signals/` de H0, puis lancer
`glorfindel respond`, passerait la précondition. Ce serait pourtant un humain qui écrit, dans le
répertoire du défenseur, un signal que celui-ci croit sien (SEC3) : cette page ne le fait pas, et
REC1 le rend inutile.

**Non mesuré avant cette session** : ce que le coffre écrit d'un job de restore (le point restauré,
dans son sac de propriétés), et la parole de Run Command après le démarrage d'un disque restauré.
Si l'un manque, la watch écrit une carte qui le dit, sans lever : la levée se fait alors à la main
(étape 7), et la carte va dans l'issue.

Un second manque, plus petit : `make glorfindel-host-containment` ne calcule le temps pour contenir
que d'une campagne (`Makefile:1042`). Pour un fil de Dagorlad, on le lit dans sa chronologie, ou
dans les lignes de la watch (étape 8).

## Le déroulé (environ 1 h à 1 h 30)

Les commandes du poste sont en zsh, `.envrc` chargé, à la racine du dépôt. Celles de H0 sont tapées
après `make glorfindel-host-ssh` (bash). `ORO_SSH_FINGERPRINT` et `HOST_SSH_FINGERPRINT` doivent
être dans l'environnement : `make orodruin-exercise` les exige toutes deux (`Makefile:1455-1470`).

### 0. Avant (5 min, lecture seule)

```zsh
source .envrc
make glorfindel-host-status        # « ✓ référence déployée : v0.5.8 », les trois conteneurs ✓, aucune erreur
make glorfindel-host-cd-status     # actif : ne publie aucune release pendant la session (ou make glorfindel-host-cd-disable)
docker ps --format '{{.Names}}'    # aucun eregion-watch : une watch du poste répondrait aussi
az role assignment list --assignee ${EREGION_CONSOLE_AZURE_CLIENT_ID} --all -o table
terraform -chdir=infra/glorfindel-host output restore_neutralize
```

Ce qu'on doit voir :
- **pour le principal de la console** : `Reader`, « Eregion Glorfindel Response » et « Eregion
  Glorfindel Restore » sur `rg-celebrimbor` ; `Log Analytics Reader` sur le workspace du banc ;
  « Eregion Glorfindel Restore Neutralize » et « Eregion Glorfindel Session Drain » à la portée de
  gondolin (`docs/operations.md`, « Identités Azure ») ;
- **dans la sortie Terraform** : la console et le bot, sur gondolin et bree.

Si la neutralisation manque, le restore restaure quand même, mais sans neutraliser : voir l'étape
7. Les gestes qui la donnent sont dans `docs/operations.md`, « Depuis un rôle Restore d'avant
SEC17 ».

### 1. Orodruin, gondolin, et le calme (15 min)

```zsh
make orodruin-start                # mis à jour à la dernière release s'il le faut (OI3) ; attendu : armed
make orodruin-check                # armed
make celebrimbor-start VM=gondolin # elle s'éteint à 23 h UTC
RID=$(az vm show -g rg-celebrimbor -n vm-celebrimbor-gondolin --query id -o tsv); print -r -- ${RID}
WS=$(terraform -chdir=infra/terraform output -raw law_workspace_id)
make glorfindel-host-tunnel        # dans un autre terminal : la console, l'URL affichée
```

Puis, après 10 minutes, le calme de gondolin :

```zsh
az monitor log-analytics query -w ${WS} --analytics-query "Heartbeat | where TimeGenerated > ago(5m) | where _ResourceId endswith '/vm-celebrimbor-gondolin' | count" -o table
az monitor log-analytics query -w ${WS} --analytics-query "Perf | where TimeGenerated > ago(10m) | where _ResourceId endswith '/vm-celebrimbor-gondolin' | where CounterName == 'Disk Write Bytes/sec' | summarize MaxMBs = max(CounterValue) / 1000000" -o table
```

Ce qu'on doit voir :
- **le Heartbeat** : un compte non nul ;
- **les écritures** : `MaxMBs` sous 25. Au-dessus, attendre encore. Le banc échantillonne toutes
  les 10 s (`perf_sampling_frequency`, `infra/terraform/config.yaml:115`) : la règle prend alors
  une moyenne sur 20 s au-dessus de 45 MB/s. 25 est une marge prudente sous ce seuil (c'est aussi
  celui d'un échantillonnage de 60 s) ;
- **dans la console, page Glorfindel** : gondolin en `non_disruptive`, sa préparation `ready`, ni
  `ISOLATED` ni blocage. Une préparation qui n'est pas `ready` ferait retenir l'isolement
  (`mode_hold`) : ce serait une mesure, pas le confinement.

### 2. Le point de restauration propre (5 à 20 min)

```zsh
print -r -- ${RID}                 # à copier
make glorfindel-host-ssh
```

Sur H0 :

```bash
RID=<la ligne copiée>              # snapshot veut l'id complet ; release et reset prennent le nom
docker exec eregion-war-room glorfindel snapshot "$RID" --yes --wait
exit
```

Puis, de retour sur le poste :

```zsh
AVANT=$(date -u +%Y-%m-%dT%H:%M:%S+00:00); print -r -- ${AVANT}   # le moment du point propre : le --before de l'étape 6
```

Ce qu'on doit voir :
- **sur H0** : « ✓ Backup complete. Time: … », puis « ✓ Recovery point verified in vault. »
  (`cli.py:1391-1405`) ;
- **dans la console** : aucune carte, puisque c'est l'identité de Glorfindel qui sauvegarde (A2,
  mesuré le 05/11 : `docs/operations.md`).

Le premier point après un restore est complet, et peut prendre ~40 min (Annatar, 30/06). Rien ne
se lance entre ce point et l'étape 4 : un fil qui toucherait gondolin entre les deux fausserait le
point.

### 3. La demande, dans Dagorlad (5 min)

Dans la console, page **Dagorlad** (`/dagorlad`), vue Board :

1. Tirer un fil de la carte rouge **T1486 Data Encrypted for Impact (ransomware)** vers gondolin,
   et rien d'autre. Un second fil sur gondolin attendrait sa levée 20 min au plus, puis serait sauté
   (`eregion_core/exercise_runner.py:55`) : un fil par demande.
2. La pastille doit dire **MAY RUN · ⚠** avec `typed_name` (une technique destructive : son nom
   sera tapé). Elle dit aussi la règle `ransomware-disk-write`, et ce que Glorfindel fera en
   `non_disruptive`. Un `isolated_now` ou un `not_seen` : revenir à l'étape 1.
3. **« Request run from Orodruin »** : la page donne la commande, avec l'identifiant de la demande
   (`r-<heure UTC>-<6 hex>`). La demande vaut 6 h (`exercise_runner.py:62`).

### 4. Le lancement (10 min)

```zsh
make orodruin-exercise REQUEST=r-… DRY_RUN=1   # le fil affiché, le nom tapé, puis « DRY_RUN : rien n'est envoyé »
make orodruin-exercise REQUEST=r-…             # taper vm-celebrimbor-gondolin, puis y
```

*Vérifié à blanc* (`make -n`) : la cible tire la demande de H0 par SSH, la fait confirmer sur le
poste, puis la porte à Orodruin (`Makefile:1455-1502`). `DRY_RUN=1` s'arrête avant l'envoi : la
demande n'est pas consommée. Le nom se tape tel qu'Azure l'écrit (`eregion_core/exercise_request.py:274-307`) :
« Wire 1: type the name of its target VM to run it », puis « Run these 1 wire(s) from Orodruin?
[y/N] ».

Ce qu'on doit voir sur Orodruin, dans l'ordre (`engine.py:368-470`) :
1. le contrôle de la cible, puis le `setup` (`setup_testdata.sh`) ;
2. « Pre-run integrity check… » ;
3. l'attaque (512 Mo écrits, puis 45 s de chiffrement simulé) ;
4. « Signal 'attack_started' emitted » ;
5. `Run: <run_id>` : **le noter** ;
6. « ✓ Glorfindel detected the attack N s after it », dans les 330 s (le délai du catalogue, 90 s +
   120, plus 120 s d'attente : `synthesizer.py:220-225`, `engine.py:1160`).

### 5. Ce qu'on doit voir : la détection, l'isolement, la carte (pendant l'étape 4)

- **Dagorlad, la chronologie de la demande** : le fil `RUNNING`, puis « ✓ detected +… · contained
  … ». Les temps portent `≈` jusqu'au rapport du run, puis sont recalculés comme sur l'accueil
  (`docs/dagorlad.md`, « Suivre une demande »).
- **Console, page Glorfindel** : la carte de l'action autonome, `isolate_vm` vérifiée ; gondolin
  `ISOLATED`. Une carte de restauration peut suivre, recommandée et jamais autonome. Elle est
  marquée exercice.
- **Discord** : l'action autonome, par le bot.
- **Sur H0** (`make glorfindel-host-ssh`, puis `exit`) : `docker exec eregion-watch glorfindel
  list` montre gondolin `ISOLATED`, vérifiée.

Autres issues, qui sont des mesures et non des échecs du banc :
- une action retenue (`mode_hold`, la préparation, une confiance sous 0,7, des tirages en désaccord) ;
- une simple recommandation.

La noter. Approuver l'isolement dans la console reste possible, mais ce serait un confinement
humain, et il se mesure comme tel. **Ne pas cliquer 🔄 Restore**, ni dans la console de H0 ni dans
Discord : refusé, ce n'est pas son hôte.

### 6. La restauration, depuis le poste (15 à 30 min)

**Le prérequis du poste.** Le restore lit le coffre (`azure_backup_vault`) et son compte de transit
(`restore_staging_storage`) dans la `glorfindel-config.yaml` du poste, à la racine du dépôt
(`cli.py:1499`, `glorfindel/providers/azure/restore.py:128-143`). Sans compte de transit, le vrai
run échoue, alors que l'essai à blanc ne le lit pas. Le fragment de `make celebrimbor-output` porte
les deux :

```zsh
grep -A5 'type: azure_backup_vault' glorfindel-config.yaml   # vault_name, resource_group: rg-celebrimbor, restore_staging_storage
```

Ensuite, aucun job du coffre en cours sur gondolin. Si un cycle suivant de H0 a choisi `snapshot`
(`glorfindel/agent.py:1971-1988`), sa sauvegarde peut encore tourner, et Azure refuse un restore
pendant une sauvegarde :

```zsh
az backup job list -g rg-celebrimbor -v rsv-celebrimbor-erebor -o table     # aucun InProgress sur gondolin
```

Puis le restore, à blanc d'abord :

```zsh
AZURE_CLIENT_ID=${EREGION_CONSOLE_AZURE_CLIENT_ID} AZURE_CLIENT_SECRET=${EREGION_CONSOLE_AZURE_CLIENT_SECRET} GLORFINDEL_READ_ONLY=0 \
  .venv/bin/glorfindel restore ${RID} --before ${AVANT} --keep-isolated --dry-run
AZURE_CLIENT_ID=${EREGION_CONSOLE_AZURE_CLIENT_ID} AZURE_CLIENT_SECRET=${EREGION_CONSOLE_AZURE_CLIENT_SECRET} GLORFINDEL_READ_ONLY=0 \
  .venv/bin/glorfindel restore ${RID} --before ${AVANT} --keep-isolated --wait --yes
date -u +%H:%M:%S                  # la fin du restore
```

*Vérifié à blanc*, dans un `HOME` jetable : la première commande dit le coffre, `Before : <AVANT>
(--before)`, puis « DRY RUN — no changes made. ». La seconde, sur Azure (**non vérifiée**) :
- « Using pre-attack recovery point: … », qui doit être le point de l'étape 2 ;
- « Still restoring… », minute par minute ;
- « ✓ Restore complete. restore_time: … » : **le noter** ;
- « ✓ Run Command neutralisée avant le restore » ;
- « --keep-isolated: VM stays isolated. » (`cli.py:1554-1582`).

La VM est désallouée, ses disques remplacés, puis redémarrée. Elle reste isolée : le NSG est sur
ses cartes réseau, pas sur ses disques.

### 7. La levée, par la watch de H0 (5 à 20 min)

Rien à faire d'abord : la watch de H0 lit la reprise sur Azure (REC1). Elle attend 5 min après la
fin du job, le temps que `restore --wait` finisse sur le poste
(`GLORFINDEL_RECOVERY_GRACE_S`). Elle attend aussi que le disque restauré ait démarré et rejoué la
dernière Run Command, au plus 15 min (`GLORFINDEL_RECOVERY_REPLAY_WAIT_S`). Sur H0 :

```bash
docker logs --since 30m eregion-watch 2>&1 | grep -E "reprise|recovery_complete|release_isolation"
docker exec eregion-watch glorfindel list                     # gondolin n'est plus ISOLATED
```

Attendu : « reprise vm-celebrimbor-gondolin job-… → emitted », puis le cycle du
`recovery_complete`, `release_isolation` exécuté et vérifié. Discord dit la levée autonome.

**Si une carte « Reprise à revoir » ou « levée retenue » arrive à la place**, elle dit pourquoi : le
job pas `Completed`, un point qui ne précède pas l'incident, un point illisible, la VM arrêtée, ou
la neutralisation non constatée. La noter dans l'issue, avec sa raison. Puis faire la vérification
ci-dessous et lever à la main.

**Si la sortie du restore disait « ⚠ Run Command non neutralisée »**, la watch ne lève pas seule, et
il ne faut pas lever. Le disque restauré a pu
rejouer le chiffrement au démarrage. Le lire d'abord, avec ton `az login` :

```zsh
az vm run-command invoke -g rg-celebrimbor -n vm-celebrimbor-gondolin --command-id RunShellScript --scripts 'ls -la --time-style=full-iso /mnt/testdata'
```

Attendu : le disque tel qu'il était au point de l'étape 2. `setup_testdata.sh` ne nettoie que dans
le fil : un `seed.dat` ou des `enc_*.dat` datés d'avant ce point sont les restes d'un run précédent,
restaurés avec lui. Datés d'après le redémarrage du restore, le chiffrement a été rejoué : ne pas
lever. Cette commande devient la dernière Run Command, inoffensive.

Puis la levée à la main, si la watch ne l'a pas faite : **↩️ Release** sur gondolin, dans la console
de H0, ou en ligne de commande. On se connecte d'abord depuis le poste :

```zsh
make glorfindel-host-ssh
```

Puis, sur H0 (le nom court suffit : `release` le résout par l'état de H0, `cli.py:172-202`) :

```bash
docker exec eregion-war-room glorfindel release vm-celebrimbor-gondolin --yes   # « ✓ Isolation released. »
docker exec eregion-watch glorfindel list                     # gondolin n'est plus ISOLATED
docker exec eregion-watch glorfindel pending                  # la carte de restauration, encore en attente
docker exec eregion-war-room glorfindel ack <son id>          # le restore du poste n'a résolu que les cartes du poste (cli.py:1577)
```

Cette levée-là n'est pas reposée. Elle note `releasing_at` dans l'état de H0 sous le verrou de la
VM, et la réaffirmation, qui prend le même verrou, saute une levée en cours
(`glorfindel/reassert.py:141`, `:239-240`). Seule une levée faite hors de H0 le serait.

Dans la console, juger les cartes de l'exercice (TO JUDGE) : l'isolement, et la recommandation de
restore. Le Heartbeat de gondolin revient en quelques minutes (la requête de l'étape 1).

### 8. Mesurer (10 min)

Les trois temps se lisent à un seul endroit, sur H0, depuis les fichiers que la watch tient :
- **le rapport du run**, tiré du canal : `runs/glorfindel/<run_id>.json`, son `attack_time` (T0)
  et `detection_latency_s` ;
- **ses cycles** : `*_debug.jsonl`, ceux qui portent `exercise_run = <run_id>`, avec
  `outcome.verified_at` ;
- **la levée** : le cycle du `recovery_complete` de la watch, dans ses `*_debug.jsonl` (REC1) ; à la
  main, `runs/console/manual_actions.jsonl`.

Toujours sur H0 (sinon, `make glorfindel-host-ssh` d'abord) :

```bash
docker exec -i -e RUN=<run_id> -e VM=vm-celebrimbor-gondolin eregion-watch python - <<'EOF'
import glob, json, os, sys
from datetime import datetime, timezone
run, vm = os.environ.get("RUN", "").strip(), os.environ.get("VM", "").strip().lower()
if not run or not vm or run.startswith("<"):
    sys.exit("RUN ou VM vide : rien à mesurer")
def t(s): return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
def hm(e): return datetime.fromtimestamp(e, timezone.utc).strftime("%H:%M:%S")
m = json.load(open(f"runs/glorfindel/{run}.json"))["metrics"]
t0 = float(m["attack_time"])
print(f"T0          {hm(t0)} UTC (attack_time du run)")
print(f"détection   {m.get('detection')}, {m.get('detection_latency_s')} s après T0")
for f in sorted(glob.glob("runs/glorfindel/*_debug.jsonl")):
    if os.path.getmtime(f) < t0 - 600:
        continue
    for line in open(f):
        d = json.loads(line)
        s = d.get("signal") or {}
        if (s.get("event") == "recovery_complete" and t(d["timestamp"]) > t0
                and str(s.get("resource_id", "")).rstrip("/").rsplit("/", 1)[-1].lower() == vm):
            o = d.get("outcome") or {}
            print(f"levée watch {hm(t(d['timestamp']))}  {d.get('action') or '-'}  escalate={d.get('escalate')}"
                  f"  verified={o.get('verified')}  T0+{t(o.get('verified_at') or d['timestamp']) - t0:.0f} s")
            continue
        if d.get("exercise_run") != run:
            continue
        o = d.get("outcome") or {}
        end = o.get("verified_at") or d["timestamp"]
        print(f"cycle       {hm(t(d['timestamp']))}  {d.get('action') or '-'}  escalate={d.get('escalate')}"
              f"  verified={o.get('verified')}  T0+{t(end) - t0:.0f} s")
f = "runs/console/manual_actions.jsonl"
for line in (open(f) if os.path.exists(f) else []):
    d = json.loads(line)
    if (d.get("action") == "release_isolation" and t(d["timestamp"]) > t0
            and str(d["signal"]["resource_id"]).rstrip("/").rsplit("/", 1)[-1].lower() == vm):
        print(f"levée       {hm(t(d['timestamp']))}  T0+{t(d['timestamp']) - t0:.0f} s  {d['outcome'].get('status')}")
EOF
```

*Vérifié à blanc* sur des fichiers fictifs de même forme (`RunReport.to_dict`,
`agent.py:2500-2555`, `cli.py:24-54`) : une ligne T0, une ligne détection, une ligne par cycle du
run (l'isolement : `isolate_vm escalate=False verified=True T0+…`), une ligne de levée. Le rapport
arrive sur H0 quand le fil a fini ; sur Orodruin, le même est dans `~/runs/annatar/<run_id>.json`.

| Le chiffre | Sa définition | Où le lire |
|---|---|---|
| **T0** | le début de l'étape d'attaque, `record: T0` : la graine de 512 Mo puis le chiffrement (`engine.py:412-425`) | `attack_time` du rapport ; Orodruin, `Run:` |
| **la détection** | T0 → la première détection de la watch pour ce run, lue sur le canal retour (`annatar/runner/detection.py:67-75`) | `detection_latency_s` ; « ✓ Glorfindel detected the attack N s » ; la chronologie de Dagorlad |
| **la carte** | T0 → la carte de l'action, dans la console | le cycle `isolate_vm` (son horodatage) ; Discord |
| **le confinement** | T0 → l'isolement relu sur Azure (`verified_at`), la définition de BL1 (`analysis/containment.py`) | la ligne `isolate_vm … verified=True T0+…` ; Dagorlad, « contained … » ; la page Annatar, « TIME TO CONTAIN · EXERCISES » (une médiane sur la période ; la tuile de l'accueil, « · REAL », exclut les exercices) |
| **la restauration finie** | la fin de `restore --wait`, et sa durée | `restore_time` et l'heure notée à l'étape 6 |
| **le service rendu** | T0 → la levée relue sur Azure, le geste humain du restore compris | la ligne `levée watch … T0+…` (REC1), ou `levée … T0+…` à la main |
| **au sens du README** | détection + isolement + `restore_time`, sans le temps de décision humaine (`cli.py:1574`) | la somme des trois |

Les chiffres vont dans l'issue #665, datés, avec le `run_id` et l'identifiant de la demande : ils
remplaceront ceux du README, et la ligne T1486 de son tableau.

### 9. Remettre le banc en état (5 min)

Depuis le poste :

```zsh
make glorfindel-host-ssh
```

Puis, sur H0 :

```bash
docker exec eregion-watch glorfindel list                                 # gondolin : ni ISOLATED ni BLOCKED
docker exec eregion-war-room glorfindel reset vm-celebrimbor-gondolin --from-azure --dry-run   # « Aucune règle Glorfindel de vm-celebrimbor-gondolin sur ses NSG. »
docker exec eregion-watch glorfindel pending                              # les cartes de l'exercice jugées ou acquittées
exit
```

Puis sur le poste :

```zsh
az backup job list -g rg-celebrimbor -v rsv-celebrimbor-erebor -o table  # aucun job en cours
make orodruin-stop
make celebrimbor-stop              # bree (always-on) épargnée
make glorfindel-host-cd-enable     # seulement s'il a été mis en pause à l'étape 0
```

- **Le point de restauration** expire seul : 30 jours pour le point à la demande, 7 jours pour ceux
  de la politique (`backup.py:45`, `infra/terraform/config.yaml:106`).
- **Le disque de gondolin** est celui d'avant l'attaque. Le prochain fil refera son `setup` et son
  contrôle d'intégrité.
- **Le reste à vérifier** : `glorfindel reset --dry-run` (sans `--from-azure`) ne lit que l'état
  local ; `--from-azure` lit les NSG (`cli.py:2121-2159`).

## Ce qui peut mal tourner

| Ce qu'on voit | Pourquoi | Que faire |
|---|---|---|
| le fil refusé `no_watch`, ou le run `unknown` | la watch muette : un battement de plus de 90 s, une clé non épinglée, une watch arrêtée en cours de run. `unknown` ne veut jamais dire « manqué » (`docs/design/orodruin-contract.md`) | `make glorfindel-host-status` ; une nouvelle demande |
| `busy` | un autre run tient le verrou d'Orodruin (une campagne, un `annatar run`, un `clean`, une panne). La demande n'est pas consommée | attendre sa fin, relancer la même commande |
| `expired` ou `replayed` | une demande vaut 6 h et ne se joue qu'une fois. Refusée ou coupée, elle est consommée (`exercise_runner.py:58-62`) | en écrire une nouvelle dans Dagorlad |
| `isolated_now`, ou le fil sauté `isolated` | gondolin isolée d'avant : un fil attend 20 min sa levée, puis est sauté, sans jamais la lever | l'étape 7, puis une nouvelle demande |
| gondolin isolée avant l'attaque | une écriture forte dans les 10 min avant le fil, vue comme réelle | la lever, juger la carte ✗ Wrong, attendre 10 min (l'étape 1) |
| une nouvelle isolation juste après la levée | **non vérifié** : la VM, isolée depuis son redémarrage, rattrape apt et snap à la levée ; une écriture forte serait une détection réelle | la juger ✗ Wrong, lever de nouveau ; la noter dans l'issue |
| des cartes `control_plane_change` après le restore | **non vérifié** (hypothèse A3, `docs/operations.md`) : le restore, sous le principal de la console, peut écrire des opérations que les règles du journal d'activité lisent | les noter avec la sortie de la requête A2 ; ne pas changer la règle à la main |
| la neutralisation refusée ou en échec | le rôle manque sur gondolin, ou Run Command ne répond pas sur une VM isolée (**non vérifié**) | l'étape 7, avant toute levée |
| « Restore refusé » sur le poste | un autre restore de gondolin réclamé ou en cours, ou un job de sauvegarde | `az backup job list …` ; attendre |
| quelque chose part de travers sur Orodruin | — | `make orodruin-kill` : il révoque l'identité d'Orodruin, annule le chaos, désalloue sa VM et ferme les fenêtres. Il ne lève rien sur gondolin. Ensuite, `make orodruin-lock` (plan relu) lui rend ses droits (`infra/orodruin/README.md`, « Urgence ») |
| `make celebrimbor-up` pendant l'isolement | un apply retire les règles `glorfindel-*` des NSG à règles en ligne | ne pas l'appliquer tant que `glorfindel list` n'est pas vide |

`make orodruin-kill DRY_RUN=1` dit ce que le kill arrêterait, sans rien arrêter (*vérifié à blanc*,
`make -n` : `kill.py … --dry-run`).

## Le coût et la durée

| Poste | Estimation | D'où |
|---|---|---|
| gondolin allumée ~1 h 30 | ~0,15 € | 71 €/mois en continu pour la même taille (bree, `docs/demarrer/banc.md`), soit ~0,10 €/h |
| Orodruin, le temps de la session | quelques centimes | ~5–9 €/mois désalloué entre les sessions (`docs/demarrer/banc.md`) |
| Azure Backup | le stockage du point à la demande, incrémental, 30 jours ; la VM est déjà protégée (`backup.tf`) | **non mesuré** |
| le modèle, sur H0 | la détection, les tirages avant l'isolement (3 par défaut, `GLORFINDEL_DECISION_DRAWS`), la recommandation de restore : de l'ordre de 0,10 à 0,30 $ | ~0,05–0,10 $ par run (`docs/operations.md`, « Coûts réels ») ; **non mesuré** pour T1486 sur H0 |

**La durée.** Les étapes 0 et 1 prennent 20 min (le calme compris), le point propre 5 à 20 min, la
demande et le fil 15 min. Le restore prend 15 à 30 min (`cli.py`, `--wait`), la levée et la mesure
15 min. Au total, environ **1 h à 1 h 30**.

## Ce que Jonathan note à la fin

1. **La détection** : le verdict `detected`, `detection_latency_s` ; à comparer aux 55–71 s du
   README.
2. **Le confinement** : `isolate_vm` exécuté seul, `verified=True`, T0+… ; à comparer à « ~1 min ».
   Sinon, ce qui l'a retenu.
3. **La restauration** : le point choisi (celui de l'étape 2), `restore_time`, la neutralisation
   faite.
4. **La levée** : par la watch de H0 (REC1) ou, à défaut, à la main, avec la carte qui l'a retenue ;
   relue sur Azure, gondolin plus `ISOLATED` ; le service rendu à T0+…, et la somme au sens du
   README, à comparer à 21m29s.
5. **Rien hors du périmètre** : aucune action sur bree, aucune carte inattendue. Sinon, la carte et
   sa ligne.
6. **Les identifiants** : la demande, le `run_id`, la date. Puis la décision : les chiffres du README
   remplacés (avec leur source), ou le run à rejouer.
