# T1486 au banc — rejouer le rançongiciel, et dater ses chiffres (RAN1)

[← le banc](demarrer/banc.md) · le modèle : [la session de BL1](banc-bl1.md) · [ce qui reste à rejouer](demarrer/a-rejouer.md) · [ce qui s'automatise autour (conception)](design/banc-autonome.md)

Le README disait : « ~1 min to contain a ransomware VM, 21m29s to restored service ». Ces chiffres
venaient du run `20260609T190824Z` (09/06, l'ancienne sandbox ; `ROADMAP.md`,
`docs/historique.md`). Ce jour-là, la watch, le restore et la levée tournaient sur le même poste.
Depuis le 12/11, le README donne ceux du rejeu de cette page (« Les chiffres du 12/11 », plus bas).
Depuis, Glorfindel vit sur Imladris (anciennement H0), l'attaque part d'Orodruin et se demande dans Dagorlad. Cette page
rejoue le rançongiciel sur gondolin, avec la release publiée sur Imladris et Orodruin (la 0.5.8 quand la
page a été écrite, le 09/11), et en
mesure trois temps. Une version d'Imladris qui porte REC1 (#668) change la levée, et seulement elle :
chaque endroit qui en dépend dit les deux cas (« La levée », plus bas, et l'étape 7).

- **la détection** : de T0 à la détection de la watch, puis à sa carte ;
- **le confinement** : de T0 à l'isolement relu sur Azure ;
- **le service rendu** : de T0 à la restauration finie, puis à la levée.

La page a été écrite sans Azure (RAN1, #665). Chaque commande existe ; ce qu'elle affirme est
marqué ainsi :
- *lu dans le code* : le fichier et la ligne sont cités ;
- *vérifié à blanc* : la commande a tourné sans Azure (`make -n`, `--dry-run`, un `HOME` jetable),
  et sa sortie est celle qui est citée ;
- **non vérifié** : ni l'un ni l'autre, à voir pendant la session.

Les lignes citées sont celles de la 0.5.8 (`v0.5.8`), la version en service quand la page a été écrite
(09/11) ; une release plus récente peut les décaler. REC1 décale celles de
`glorfindel/cli.py` (+64) et de `glorfindel/providers/azure/restore.py` (+4), sans changer ce qu'elles
font ; ce que REC1 ajoute est cité par son fichier.

Jonathan lance chaque geste.

**Le 09/11, cette page a été jouée une fois au banc** : environ 4 h, chaque vérification tapée à la
main (`docs/operations.md`, « Le banc lisible » ; RAN1, #665). Ce qui s'y est vu, ce qui a cassé, et
ce qui l'a corrigé depuis (le CHANGELOG de la 0.5.9 et de la 0.5.10) :
- **la détection**, à 70,3 s de T0, puis **l'isolement autonome** de gondolin, son NSG posé et tenu.
  Rien n'y a cassé ; la source de ces chiffres est le test de BNC1 (#682), qui recompose ce run sur
  ses formes mesurées (`tests/unit/test_bench_report.py`), pas un correctif ;
- **la coupure des sessions**, 302 s sous la quarantaine : la watch, qui l'attendait 300 s, a dit
  l'isolement non vérifié, 2 s avant que la coupure aboutisse. Corrigé par DRN1 (#677, 0.5.9) : la
  coupure est suivie sur Azure, la carte « session cut pending » le dit ;
- **le restore depuis le poste, sous le principal de la console**, refusé au déclenchement (`listKeys` manquait sur le compte de
  transit), après la neutralisation et la désallocation : la VM est restée arrêtée trois heures, sans
  le dire. Puis Azure a refusé `restoreDiskLunList` sur un restore en place (code `400625`). Corrigé
  par RST1 (#680, 0.5.9) : le rôle « Restore Staging », les droits lus avant de toucher la VM, le refus
  dit entier, le champ retiré. Le job a ensuite abouti en 15 min 17 ; la neutralisation avait pris
  152 s sous la quarantaine ;
- **la levée par la watch d'Imladris**, qui portait REC1 sans REC1b : elle a attendu la parole de
  l'invité, que la vue d'instance ne porte jamais, et a retenu la levée par une carte. Corrigé par
  REC1b (#679, 0.5.9) : la neutralisation se décide par le journal d'activité seul ;
- **les gestes tapés et recopiés à la main** : `make bench-preflight` et `make bench-report` (BNC1,
  0.5.9) lisent l'étape 0 et l'étape 8 ; `make bench-run` et `make bench-restore` (MOB1, #686, 0.5.10)
  font le lancement et le restore en une commande chacun.

**Le 12/11, la page a été rejouée de bout en bout avec ces corrections**, sur la v0.5.10 d'Imladris
et d'Orodruin : `make bench-run`, puis `make bench-restore`, la levée par la watch d'Imladris seule.
Le restore sous RST1, la coupure suivie de DRN1, la levée seule de REC1b, `make bench-run` et
`make bench-restore` ont tourné sur Azure. Les chiffres suivent.

### Les chiffres du 12/11

Run `20261112T091448Z-b218` (la demande `r-20261112T091418Z-f94891`), gondolin en `non_disruptive`,
heures UTC. La source : le rapport de `make bench-report`, recomposé après la levée (v3, 10:08 UTC),
qui lit l'état d'Imladris, ses cycles, le journal d'activité, le coffre et la vue d'instance (sa v2,
composée avant la levée, pour `isolated_at`, que la v3 ne lit plus : l'état d'Imladris était levé) ; le
`restore_time`, à la sortie de `make bench-restore` ; le compte rendu de la session Tests (hors du
dépôt) ; les chiffres sont aussi sur #665.

| Étape | Heure | Depuis T0 | Le 09/11 | Où c'est lu |
|---|---|---|---|---|
| T0 | 09:16:04 | — | — | `attack_time` du run |
| la détection | 09:18:25 | **141,6 s** | 70,3 s | `detection_latency_s`, verdict `detected` |
| le NSG de quarantaine posé | 09:18:45,2 | 161,1 s | — | `isolated_at`, l'état d'Imladris (rapport v2) ; la v3 lit 09:18:47, 163,3 s : la première écriture d'Imladris sur la carte, au journal d'activité |
| la coupure des sessions, par Imladris | 09:18:45 → 09:23:49 | 304,2 s de Run Command | 302 s | le journal d'activité |
| **l'isolement vérifié** | 09:23:47,2 | **463,1 s** | jamais : la vérification en échec (DRN1) | le cycle `isolate_vm`, `verified=True`, `action_s` 305 |
| le restore lancé par Jonathan | vers 09:41:43 | 25 min 39 s d'attente humaine | — | un `date -u` tapé juste avant le « o » |
| la neutralisation de Run Command (la console) | 09:41:41 → 09:44:13 | 152 s | 152 s | le journal d'activité |
| le démarrage de la VM restaurée | 10:00:38 | — | — | le journal d'activité (`start/action`) |
| **la levée**, par la watch d'Imladris | 10:06:23 | **3019,9 s** | à la main | le cycle `recovery_complete` (REC1), `verified=True` |

- **Le confinement** : 463,1 s de T0 à l'isolement relu sur Azure, soit 7 min 43 s. Le NSG de
  quarantaine est posé à 161,1 s, 19,5 s après la détection ; la vérification attend la fin de la
  coupure des sessions, 304,2 s sous la quarantaine. La confiance de l'isolement : 75 % (82 % le 09/11).
- **La restauration** : `restore_time` de 25 min 14 s, du point de 08:29:59 (le point propre de
  l'étape 2, au niveau du coffre, le plus récent avant T0). Le job Azure seul a duré 917 s. La
  neutralisation a été faite avant (« ✓ Run Command neutralisée avant le restore »).
- **Au sens du README** (la détection, puis l'isolement, puis `restore_time`, sans le temps des
  décisions humaines) : 141,6 + 19,5 + 1514 = 1675,1 s, soit 27 min 55 s. Le 09/11 : environ
  33 min 57 ; le 09/06, sur l'ancienne architecture : 21 min 29 s.
- **Le service rendu**, l'attente humaine comprise : à la levée, T0 + 50 min 20 s, dont 25 min 39 s
  entre T0 et le restore lancé. Du démarrage de la VM restaurée à la levée : 5 min 45 s.
- **La détection a pris 141,6 s, contre 70,3 s le 09/11.** L'écart n'est pas expliqué ici : il est
  à mesurer, par ING5 (RH1, [`design/mesure-en-retard.md`](design/mesure-en-retard.md)).
- **Ce qui ne s'est pas lu comme prévu** : la carte Discord de l'isolement (09:23) dit encore
  « coupure en attente », sans message de clôture, alors que le cycle s'est clos vérifié ; aucune
  carte n'est venue dans TO JUDGE pour le run (étape 7) ; un rapport composé 7 s après la détection
  ne montre pas encore l'isolement (étape 8).

## Ce que le code décide avant la session

### La cible : gondolin, et elle seule

bree n'est pas inscrite (`enrolled: false`, `infra/terraform/config.yaml:52-55`) : aucun injecteur
ne la vise, et Dagorlad ne lui donne pas de carte bleue (`docs/dagorlad.md`, « Ce que c'est »). Le
rançongiciel se rejoue sur gondolin, inscrite `bench`, qu'Imladris tient en `non_disruptive`.

### Le chemin : une demande de Dagorlad, puis `make orodruin-exercise`

T1486 est une technique **destructive** du catalogue (`destructive: true`,
`technique_catalog.yaml:78-96`). Trois chemins existent ; un seul est le chemin prévu.

| Chemin | Ce qu'il fait | Verdict |
|---|---|---|
| **Dagorlad** : le fil T1486 → gondolin, « Request run from Orodruin », puis `make orodruin-exercise REQUEST=…` | le nom de la cible tapé sur le poste, comparé par Orodruin au nom qu'Azure lui donne (`annatar/runner/engine.py:267-274`) ; le scénario construit depuis le catalogue, son `setup` compris (`annatar/campaign/synthesizer.py:188-196`) ; l'identifiant de la demande dans la fenêtre et le rapport ; la chronologie de Dagorlad | **le chemin prévu, mesuré** |
| `annatar run annatar/scenarios/azure/ransomware-vm.yaml --yes` dans le `docker run` durci d'Orodruin (`make orodruin-ssh`) | les mêmes gardes d'inscription, de zone et de watch, la fenêtre et le rapport publiés (`annatar/cli.py:89`) ; **pas** de nom tapé (la garde ne joue que pour une demande, `engine.py:267`), pas de chronologie dans Dagorlad | un repli, mesuré aussi, moins gardé |
| **`make bench-run TARGET=… SCENARIO=T1486`** (MOB1, #686) : depuis le poste, au clavier ou depuis le téléphone ([le guide](demarrer/mobile.md)) | le préflight d'abord (un ✗ : rien ne part), la demande d'un fil écrite sur le poste par le même lecteur que celles de Dagorlad, le nom de la cible tapé, puis le même lancement que `make orodruin-exercise` et `make bench-report` pour le run (`scripts/bench_run.py`) ; la demande n'est pas dans le répertoire de la console : **pas** de chronologie de la demande dans Dagorlad (le run, ses cartes et son rapport, si) | le même chemin gardé, en une commande |
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
  (`ago(10m)`, `glorfindel/rules/azure/detection_rules.yaml:55-80`), et le RulePoller d'Imladris la
  relit toutes les 30 s, sans rien savoir de T0. Une écriture forte avant le fil serait vue :
  - hors de la fenêtre, comme un incident réel, et gondolin, en `non_disruptive`, serait isolée
    avant l'attaque ;
  - dans la fenêtre, avant T0, et le T0 du run ne serait plus cru (la watch a vu la VM avant lui :
    `analysis/containment.py`, `t0_refusal`).

  Deux sources connues : le démarrage de la VM (le rattrapage d'apt et de snap, 52,2 MB/s mesurés
  le 05/10, `detection_rules.yaml:36-38`) et un run précédent. D'où : 10 minutes de calme après le
  démarrage de gondolin, et après tout run précédent. L'ancienne consigne (10 min après
  `annatar clean`, `docs/operations.md`) visait le même piège.

### Le point de restauration propre : depuis Imladris

Imladris a le droit d'un instantané : le rôle « Eregion Glorfindel Response » porte l'action de
sauvegarde du coffre (`infra/identities/glorfindel-response.json`), et le coffre est dans le groupe
du banc (`infra/terraform/backup.tf:1-4`), où Imladris tient ce rôle. `glorfindel snapshot` se lance donc
dans le conteneur de la console d'Imladris, comme ses boutons (SEC18 : il écrit `runs/console/`).

Le poste le peut aussi, sous le principal de la console. Mais Imladris suffit, sans secret sur la ligne de
commande. Le point à la demande est gardé 30 jours (`glorfindel/providers/azure/backup.py:45`).

### La restauration : sur le poste, sous le principal de la console

- **Imladris ne restaure jamais.** Son identité n'a pas le rôle Restore, et son Terraform refuse de le
  lui donner (`infra/glorfindel-host/README.md`, « Ce que la VM est »). Les boutons 🔄 Restore de sa
  console et de son bot partent sous cette identité : Azure les refuse, et la carte le dit.
- **Le restore part donc du poste**, par la CLI, avec la paire de la console pour cette commande
  seulement (`docs/operations.md`, « Identités Azure ») :
  `AZURE_CLIENT_ID=$EREGION_CONSOLE_AZURE_CLIENT_ID AZURE_CLIENT_SECRET=$EREGION_CONSOLE_AZURE_CLIENT_SECRET`.
  Ce principal tient `Reader`, Response et Restore sur le groupe du banc, et la neutralisation sur
  gondolin.
- **`--before` est obligatoire sur le poste.** Sans lui, la commande prend le moment de la carte en
  attente de la VM ; mais les cartes sont sur Imladris, pas sur le poste. Elle refuse alors, avant tout
  appel à Azure (`glorfindel/cli.py:2287-2312`). *Vérifié à blanc* : « Moment de l'attaque inconnu
  pour vm-celebrimbor-gondolin : aucune carte en attente de cette VM n'en donne un ». On lui donne
  le moment noté juste après le point propre (`AVANT`, étape 2) : le point le plus récent avant
  lui est celui-là. Un instantané qu'Imladris prendrait seul après l'isolement est postérieur, donc écarté.
- **La neutralisation (SEC17)** se fait sur gondolin, par le principal qui restaure, avant
  l'échange des disques (`glorfindel/providers/azure/restore.py:145-150`). Une Run Command sans
  effet devient la dernière : un disque restauré rejouerait sinon `ransomware_sim.sh` au démarrage
  (vu le 05/10). Il faut « Eregion Glorfindel Restore Neutralize » sur gondolin, pour la console
  (`restore_vms`, `restore_principals` ; `docs/operations.md`, « Depuis un rôle Restore d'avant
  SEC17 »). La sortie du restore dit si elle a eu lieu.
- **`--keep-isolated`, toujours** (pourquoi : la section suivante).

### La levée

**Quel cas s'applique : la version qu'Imladris fait tourner.** REC1 (#668) fait lever l'isolement
par la watch d'Imladris ; la 0.5.8, en service quand la page a été écrite, ne le porte pas ; la 0.5.9 le
porte (CHANGELOG). Depuis le poste :

```zsh
make glorfindel-host-status        # « référence déployée : <ref> (<sha>) »
SHA=<le sha affiché>
git fetch -q origin && git cat-file -e ${SHA}:glorfindel/recovery_watch.py && print -r -- "avec REC1" || print -r -- "sans REC1"
```

- **sans REC1** (0.5.8, ou toute version d'avant la release qui porte REC1) : **deux gestes humains**,
  le restore sur le poste puis la levée sur Imladris ; la levée se lit dans `runs/console/manual_actions.jsonl` ;
- **avec REC1** : un seul geste, le restore ; la watch d'Imladris lève, ou écrit une carte qui dit
  pourquoi, et la levée se fait alors à la main comme sans REC1.

#### Sans REC1 (0.5.8) : sur Imladris, par un humain

- **`restore --wait` lève l'isolement dans son propre processus.** Il construit le
  `recovery_complete`, le garantit pour ce processus et le passe aussitôt au graphe
  (`cli.py:1517-1530`). La levée autonome n'est permise que pour ce signal-là, ou pour celui relu par
  `glorfindel respond` dans `~/.glorfindel/recovery_signals/` du même hôte
  (`glorfindel/signal_origin.py:29-35`, `glorfindel/agent.py:1449-1478`). **La watch d'Imladris ne lit
  jamais ce répertoire d'elle-même**, et celui du poste encore moins.
- **Sur le poste, ce processus déciderait seul.** Il appellerait le modèle avec la clé du poste et
  la configuration du poste (le mode de gondolin, sa préparation). Puis, s'il levait l'isolement,
  il le ferait sans l'état d'isolation d'Imladris.
- **Imladris reposerait l'isolement.** Sa réaffirmation relit chaque minute les isolations de son état.
  Elle trouverait les règles disparues et les reposerait une fois, gondolin étant en
  `non_disruptive` (`glorfindel/reassert.py:271-290`).
- D'où `--keep-isolated` sur le poste (`cli.py:1517`). La levée se fait ensuite sur Imladris :
  - **↩️ Release** dans sa console ;
  - ou `docker exec eregion-war-room glorfindel release …`, dans le conteneur de la console
    (`docs/banc-bl1.md`, étape 5).

  La levée est relue sur Azure, et l'état d'Imladris suit. Elle n'est pas reposée : elle marque la levée
  en cours (`releasing_at`) sous le verrou de la VM, que la réaffirmation prend aussi avant de la
  sauter (`glorfindel/reassert.py:141`, `:239-240`).

#### Avec REC1 : par la watch d'Imladris

- **La watch d'Imladris lit la reprise sur Azure, et lève elle-même** (`docs/glorfindel.md`, « La reprise
  lue sur Azure »). Chaque minute, pour gondolin isolée, elle lit sur le plan de contrôle :
  - le dernier job de restore de gondolin depuis l'isolement, fini, `Completed` ;
  - **sur place** : le type « Replace disks », et le disque OS de gondolin créé pendant le job ;
  - son point, antérieur à l'incident ;
  - la VM qui tourne ;
  - **la neutralisation, par ce seul journal** (REC1b, #679) : dans le journal d'activité, la
    dernière Run Command sur gondolin avant le restore vient du principal qui restaure, et aucune
    d'un autre après elle, quel que soit son statut. **Un refus de la plateforme ne compte pas** :
    une Run Command tentée sur gondolin désallouée (`Failed`, `Conflict`, `OperationNotAllowed`,
    comme les trois essais de la console le 09/11) n'a jamais atteint l'invité, qu'elle vienne de
    la console ou d'un autre. Tout autre échec d'un autre principal retient la levée.
  - **la parole de l'invité n'est qu'une information** : la vue d'instance ne porte jamais Run
    Command v1 (mesuré le 09/11), et la watch ne l'attend pas. Si elle était là et disait une autre
    commande que l'inoffensive, la levée serait retenue.

  Ce principal, `GLORFINDEL_RESTORE_PRINCIPALS`, est l'object id de la console, celui de
  `restore_principals`. Le lire, `.envrc` chargé :
  `az ad sp show --id "$EREGION_CONSOLE_AZURE_CLIENT_ID" --query id -o tsv`. Le poser sur le poste :
  dans le `.envrc`, et, Imladris étant en place, à la main dans `infra/glorfindel-host/host.env` (le
  `host.env` existant n'est jamais réécrit : son jeton changerait), puis `make glorfindel-host-push`.
  Il est pris au démarrage de la watch qui porte REC1. Sans lui, chaque levée est une carte. Le
  journal d'activité nomme la console par son object id dans `caller` et dans `claims.oid`, son
  appId dans `claims.appid` (mesuré le 09/11, la même forme que pour Imladris et Orodruin).

  Elle émet alors son propre `recovery_complete`, et la levée suit : seule en `non_disruptive`, une
  carte en `human_only`. Elle ne lit jamais un fichier du poste. Ses droits : Reader sur le groupe
  du banc, où est le coffre.
- **Une version qui porte REC1 sans REC1b retient chaque levée** : elle attend la parole de
  l'invité 15 min, ne la trouve jamais, et écrit une carte « levée retenue ». La levée se fait
  alors à la main. Le dire, depuis le poste, le `SHA` de « La levée » en main :
  `git show ${SHA}:glorfindel/providers/azure/recovery.py | grep -q _refused_operations && print -r -- "avec REC1b" || print -r -- "sans REC1b"`.
- **La lecture d'intégrité par Run Command se fait après la levée**, ou sous un principal qui
  restaure. Faite avant la levée sous l'`az login` d'un humain, c'est une Run Command d'un autre
  principal après la neutralisation : elle retient la levée automatique, qui se fait alors à la
  main. Run Command est lente sous la quarantaine (le 09/11 : 152 s pour la neutralisation, 302 s
  pour la coupure) ; hors quarantaine, après la levée, la lecture d'intégrité a pris 11 s.
- **`--keep-isolated` reste de rigueur sur le poste** : la levée est celle d'Imladris, pas du poste.
- Une carte « Reprise à revoir » ou « levée retenue » à la place dit pourquoi. La levée se fait
  alors à la main, comme sans REC1, après la vérification de l'étape 7.

## Le manque : la boucle ne se ferme pas seule sur le banc (sans REC1)

Le README décrit une boucle où la seule étape humaine est d'approuver le restore, la levée
autonome suivant le `recovery_complete`. **Sans REC1 (sur la 0.5.8), ce n'est pas vrai.** Il y a
deux gestes humains, sur deux hôtes :
- le restore, sur le poste, puisqu'Imladris n'en a pas le droit ;
- la levée, sur Imladris, puisque sa watch ne voit pas la reprise.

Le temps du « service rendu » mesuré ici inclut donc le temps de ces deux gestes. On le donne aussi
au sens du README, sans le temps de décision humaine (étape 8).

Porter à la main le signal du poste dans `~/.glorfindel/recovery_signals/` d'Imladris, puis lancer
`glorfindel respond`, passerait la précondition. Ce serait pourtant un humain qui écrit, dans le
répertoire du défenseur, un signal que celui-ci croit sien (SEC3) : cette page ne le fait pas.

**Proposition de lot** (non construite) : que la watch d'Imladris constate elle-même la reprise d'une VM
qu'elle a isolée, plutôt que d'attendre un signal d'un autre hôte. Elle lirait sur Azure, avec ses
droits de lecture :
- le job de restore fini ;
- le point restauré, antérieur à l'isolement ;
- la VM démarrée ;
- la dernière Run Command, celle de la neutralisation.

Puis elle émettrait son propre `recovery_complete`. L'autre piste : la file d'actions signée (FS1,
`docs/design/file-actions-signee.md`), où le poste déposerait la reprise.

**Avec REC1, ce lot est construit** (#668) : il ne reste qu'un geste humain, le restore. La levée
est celle de la watch d'Imladris (« La levée », ci-dessus). Non mesuré avant cette session : ce que
le coffre écrit d'un job de restore (« Job Type », le point restauré), et l'identifiant que le
journal d'activité donne au principal qui restaure. Si l'un manque, la watch écrit une carte qui le
dit, sans lever ; la levée se fait alors à la main.

Un second manque, plus petit : `make glorfindel-host-containment` ne calcule le temps pour contenir
que d'une campagne (`Makefile:1042`). Pour un fil de Dagorlad, `make bench-report RUN=…` le compose
(BNC1, étape 8) ; on le lit aussi dans sa chronologie de Dagorlad.

## Le déroulé (environ 1 h à 1 h 30)

Les commandes du poste sont en zsh, `.envrc` chargé, à la racine du dépôt. Celles d'Imladris sont tapées
après `make glorfindel-host-ssh` (bash). `ORO_SSH_FINGERPRINT` et `HOST_SSH_FINGERPRINT` doivent
être dans l'environnement : `make orodruin-exercise` les exige toutes deux (`Makefile:1455-1470`).

### 0. Avant (5 min, lecture seule)

```zsh
source .envrc
make bench-preflight TARGET=vm-celebrimbor-gondolin   # une ligne ✓/⚠/✗ par contrôle, puis le verdict
```

*Vérifié sur des faux* (BNC1, #682 : `tests/unit/test_bench_preflight.py`). La cible lit tout ce que
cette étape lisait à la main, sans rien écrire nulle part, et n'affiche aucun identifiant : ni
abonnement, ni object id, ni appId, ni IP, ni UPN. Elle sort en 0 si aucune ligne n'est ✗ ; un ⚠
ne bloque pas. Ses contrôles (`scripts/bench_preflight.py`) :
- **Imladris** : la référence déployée et les trois conteneurs, tels que `make glorfindel-host-status`
  les dit, et ce qu'il marque ✗ ; le CD, par `make glorfindel-host-cd-status` (le minuteur, la
  release qui tourne face à la dernière publiée) ;
- **le poste** : aucune watch locale d'Eregion (`docker ps --no-trunc`). Est une watch :
  - tout conteneur dont la commande est `glorfindel watch …`, quels que soient son image et son nom :
    le service du `docker-compose.yml`, `make glorfindel-watch` (un nom tiré par docker, sans label),
    une instance d'un autre nom sur une image reconstruite ;
  - le service `watch` de l'image `eregion-glorfindel` (son label compose et son image) ;
  - un conteneur `eregion-watch` / `eregion-<équipe>-watch`.

  Le « …-watcher » d'un autre projet n'en est pas une (BNC1b, mesuré le 11/11). Une `glorfindel
  watch` tapée dans `make glorfindel-shell` ne se voit pas : la commande du conteneur est son shell ;
  docker qui ne répond pas, c'est un ⚠ ;
- **Orodruin** : son contrat lu sur lui, sans être publié (`check()` dans son conteneur durci),
  armé et son plafond. Désallouée, c'est un ⚠ : son contrat se lit après `make orodruin-start`. Sans
  `ORO_SSH_FINGERPRINT`, rien ne part vers Orodruin, ni vers Imladris sans `HOST_SSH_FINGERPRINT` ;
- **les paires** : celles de `make azure-pairs-expiry` (RST1). Celle de la console est exigée : absente
  ou incomplète, c'est un ✗. Chaque secret se lit sur l'application et sur le principal de service,
  et se dit là où il vit (PAIR1 : le 12/11, celui de la console était sur son principal de service,
  dit « aucun secret » jusque-là) ; aucun secret sur les deux, ou un objet illisible, c'est un ✗ ;
- **la cible** : une seule VM de ce nom, son groupe, son état ; sur Imladris, son mode (configuré et
  effectif), sa préparation et la quarantaine, et aucune isolation déjà posée ;
- **le point de restauration** : l'âge du plus récent au coffre, ⚠ au-delà de 24 h
  (`POINT_MAX_H=…`). Le conteneur (`-c`) et l'item (`-i`) se lisent dans l'`id` de l'item : le segment
  entre `/protectionContainers/` et `/protectedItems/` (`IaasVMContainer;…`), puis le dernier. Le
  `containerName` en trois segments est refusé par `az backup recoverypoint list`
  (`BMSUserErrorContainerNameIncorrectFormat`) ; la forme de l'`id` répond (mesuré le 11/11). Un `id`
  sans ces segments : un ✗ « illisible », jamais un repli ;
- **les droits effectifs** :
  - la console, sous sa paire, par `Microsoft.Authorization/permissions`, avec le lecteur du restore
    (`glorfindel/providers/azure/restore_rights.py`) : le restore sur le coffre, `deallocate` et
    `start` sur la VM, `listKeys` sur le compte de transit, et la neutralisation (Run Command) ;
  - Imladris et Orodruin, par leurs attributions et les définitions de leurs rôles, jokers et
    `notActions` compris : l'isolement, la coupure, le point de restauration et la lecture du journal
    pour Imladris ; l'attaque (Run Command sur la cible) pour Orodruin. Leurs identifiants sont lus dans les
    sorties Terraform d'`infra/glorfindel-host` et d'`infra/orodruin`, jamais affichés. Une attribution
    sur un groupe d'administration n'est pas lue : la ligne le dit, à vérifier à la main ;
- **les dérives connues** : le rôle « Eregion Glorfindel Restore » du tenant qui porte encore
  `runCommand/action` (d'avant SEC17) donne un ⚠ ; « Eregion Glorfindel Restore Staging » absent de la
  console sur le compte de transit donne un ✗, le droit qui manquait le 09/11.

**Deux passes.** À cette étape, Orodruin et gondolin sont souvent désallouées : leurs lignes sont des
⚠. Relancer `make bench-preflight` à la fin de l'étape 1, Orodruin armé et gondolin démarrée, avant
la demande de l'étape 3 : là, tout doit être ✓.

Ce que la cible ne lit pas : les deny assignments, les verrous, les conditions ABAC et PIM (l'API des
droits ne les rend pas), ni l'audit de la console sous sa paire (`glorfindel audit`, à la main).
Les commandes qu'elle remplace restent en annexe, pour un dépannage (« Annexe A »).

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

Sur Imladris :

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
- **sur Imladris** : « ✓ Backup complete. Time: … », puis « ✓ Recovery point verified in vault. »
  (`cli.py:1327-1341`) ;
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

*Vérifié à blanc* (`make -n`) : la cible tire la demande d'Imladris par SSH, la fait confirmer sur le
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

Le confinement, lui, peut se lire plus tard qu'en 0.5.8 : sous la quarantaine, la coupure des
sessions a pris 302 s le 09/11, et une coupure qui dépasse 300 s est suivie sur Azure, puis dite
(étape 5, DRN1). Le NSG est posé et vérifié avant.

### 5. Ce qu'on doit voir : la détection, l'isolement, la carte (pendant l'étape 4)

- **Dagorlad, la chronologie de la demande** : le fil `RUNNING`, puis « ✓ detected +… · contained
  … ». Les temps portent `≈` jusqu'au rapport du run, puis sont recalculés comme sur l'accueil
  (`docs/dagorlad.md`, « Suivre une demande »).
- **Console, page Glorfindel** : la carte de l'action autonome, `isolate_vm` vérifiée ; gondolin
  `ISOLATED`. Une carte de restauration peut suivre, recommandée et jamais autonome. Elle est
  marquée exercice. Elle demande un cycle suivant, donc une nouvelle détection de gondolin, qui peut
  ne pas venir sous la quarantaine : le 09/11, aucune n'a suivi (`docs/glorfindel.md`, « La coupure
  suivie sur Azure ») ; le 12/11 non plus, et l'isolement vérifié n'a fait aucune carte dans TO JUDGE
  (`docs/observation.md`, « Juger chaque carte »).
- **La coupure des sessions (DRN1)** : sous la quarantaine, elle a pris 302 s le 09/11, 304,2 s le
  12/11 (la notification a dit « coupure en attente », puis le cycle s'est clos vérifié). La watch
  l'attend 300 s. Finie avant, la carte de l'action autonome est vérifiée. Sinon, la notification
  dit « coupure en attente », `glorfindel list` dit « session cut pending », et, dans la minute, une
  carte **« session cut pending »** (`drain_pending`) apparaît, sans rien à approuver. Elle se ferme
  seule quand la coupure aboutit : sa note dit « isolement vérifié ». Si une carte
  `verification_failed` la remplace, sa raison dit le cas : « coupure refusée » (le rôle Session
  Drain manque sur gondolin), « sessions restées ouvertes », ou « coupure jamais aboutie » (toujours
  en cours 30 min après, ou la watch redémarrée, ou la VM isolée par un autre processus entre-temps). À noter dans l'issue, avec la durée
  lue au journal d'activité (Started → Succeeded).
- **Discord** : l'action autonome, par le bot.
- **Sur Imladris** (`make glorfindel-host-ssh`, puis `exit`) : `docker exec eregion-watch glorfindel
  list` montre gondolin `ISOLATED`, vérifiée.

Autres issues, qui sont des mesures et non des échecs du banc :
- une action retenue (`mode_hold`, la préparation, une confiance sous 0,7, des tirages en désaccord) ;
- une simple recommandation.

La noter. Approuver l'isolement dans la console reste possible, mais ce serait un confinement
humain, et il se mesure comme tel. **Ne pas cliquer 🔄 Restore**, ni dans la console d'Imladris ni dans
Discord : refusé, ce n'est pas son hôte.

### 6. La restauration, depuis le poste (15 à 30 min)

**En une commande (MOB1)** : `make bench-restore TARGET=vm-celebrimbor-gondolin RUN=<run_id> [DRY_RUN=1]`, dans un terminal, fait ce qui suit — la
paire de la console exigée, `--before` le T0 du run (`runs/bench/<run_id>.json`, que `make bench-report` écrit ;
`BEFORE=${AVANT}` pour le point de l'étape 2), `--keep-isolated`, le nom de la VM tapé, l'essai à blanc, puis « [o/N] »
(`scripts/bench_restore.py`, [le guide](demarrer/mobile.md)). Le prérequis du poste et le job du coffre, ci-dessous, restent
à vérifier avant.

**Le prérequis du poste.** Le restore lit le coffre (`azure_backup_vault`) et son compte de transit
(`restore_staging_storage`) dans la `glorfindel-config.yaml` du poste, à la racine du dépôt
(`cli.py:1435`, `glorfindel/providers/azure/restore.py:124-139`). Sans compte de transit, le vrai
run échoue, alors que l'essai à blanc ne le lit pas. Le fragment de `make celebrimbor-output` porte
les deux :

```zsh
grep -A5 'type: azure_backup_vault' glorfindel-config.yaml   # vault_name, resource_group: rg-celebrimbor, restore_staging_storage
```

Ensuite, aucun job du coffre en cours sur gondolin. Si un cycle suivant d'Imladris a choisi `snapshot`
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

**La sortie affiche l'id complet de la VM, l'abonnement compris, et le nom du coffre** (la ligne
`Resource :` de `glorfindel restore`, `glorfindel/cli.py:1609` ; relevé au banc le 12/11, à blanc comme
pour de vrai) : ne pas la coller telle quelle dans une issue ou un fil. La masquer demande du code.

*Vérifié à blanc*, dans un `HOME` jetable : la première commande dit le coffre, `Before : <AVANT>
(--before)`, puis « DRY RUN — no changes made. ». Elle dit aussi son identité (RST1) : `Identity :
la paire de la console (AZURE_CLIENT_ID = EREGION_CONSOLE_AZURE_CLIENT_ID)` ; toute autre ligne
(aucune paire, une paire incomplète, celle de la watch), arrêter et relire l'étape 0. La seconde, sur
Azure (**non vérifiée**) :
- avant tout geste sur la VM, la lecture de ses droits (RST1) : un droit qui manque arrête le restore
  en le nommant, avec son rôle, la VM ni neutralisée ni désallouée ; « Droits du restore illisibles »
  dit qu'elle n'a pas pu les lire, et le restore continue (**à mesurer** : la lecture sous `Reader`) ;
- « Using pre-attack recovery point: … », qui doit être le point de l'étape 2 ;
- « Still restoring… », minute par minute ;
- « ✓ Restore complete. restore_time: … » : **le noter** ;
- « ✓ Run Command neutralisée avant le restore » ;
- « --keep-isolated: VM stays isolated. » (`cli.py:1490-1518`).

La VM est désallouée, ses disques remplacés, puis redémarrée. Elle reste isolée : le NSG est sur
ses cartes réseau, pas sur ses disques.

### 7. La levée, sur Imladris (5 à 20 min)

Le cas : `make glorfindel-host-status`, puis le test de « La levée » (plus haut).

**Avec REC1**, rien à faire d'abord : la watch d'Imladris lit la reprise sur Azure. Elle attend 5 min
après la fin du job (`GLORFINDEL_RECOVERY_GRACE_S`), puis décide par le journal d'activité
(REC1b : la parole de l'invité n'est plus attendue ; sans REC1b, elle l'attendait 15 min, puis
retenait la levée). Aucune lecture d'intégrité par Run Command avant la levée, sauf sous un
principal qui restaure : elle la retiendrait. Sur Imladris :

```bash
docker logs --since 30m eregion-watch 2>&1 | grep -E "reprise|recovery_complete|release_isolation"
docker exec eregion-watch glorfindel list                     # gondolin n'est plus ISOLATED
```

Attendu : « reprise vm-celebrimbor-gondolin job-… → emitted », puis le cycle du `recovery_complete`,
`release_isolation` exécuté et vérifié. Une carte « Reprise à revoir » ou « levée retenue » à la
place : la noter dans l'issue avec sa raison, puis suivre la suite de cette étape, comme sans REC1.

**Sans REC1 (0.5.8)**, ou après une telle carte : la levée humaine, ci-dessous.

**Si la sortie disait « ⚠ Run Command non neutralisée »**, ne pas lever. Le disque restauré a pu
rejouer le chiffrement au démarrage. Le lire d'abord, avec ton `az login` :

```zsh
az vm run-command invoke -g rg-celebrimbor -n vm-celebrimbor-gondolin --command-id RunShellScript --scripts 'ls -la --time-style=full-iso /mnt/testdata'
```

Attendu : le disque tel qu'il était au point de l'étape 2. `setup_testdata.sh` ne nettoie que dans
le fil : un `seed.dat` ou des `enc_*.dat` datés d'avant ce point sont les restes d'un run précédent,
restaurés avec lui. Datés d'après le redémarrage du restore, le chiffrement a été rejoué : ne pas
lever. Cette commande devient la dernière Run Command, inoffensive.

Puis la levée : **↩️ Release** sur gondolin, dans la console d'Imladris, ou en ligne de commande. On se
connecte d'abord depuis le poste :

```zsh
make glorfindel-host-ssh
```

Puis, sur Imladris (le nom court suffit : `release` le résout par l'état d'Imladris, `cli.py:172-202`) :

```bash
docker exec eregion-war-room glorfindel release vm-celebrimbor-gondolin --yes   # « ✓ Isolation released. »
docker exec eregion-watch glorfindel list                     # gondolin n'est plus ISOLATED
docker exec eregion-watch glorfindel pending                  # la carte de restauration, encore en attente
docker exec eregion-war-room glorfindel ack <son id>          # le restore du poste n'a résolu que les cartes du poste (cli.py:1513)
```

Cette levée-là n'est pas reposée. Elle note `releasing_at` dans l'état d'Imladris sous le verrou de la
VM, et la réaffirmation, qui prend le même verrou, saute une levée en cours
(`glorfindel/reassert.py:141`, `:239-240`). Seule une levée faite hors d'Imladris le serait.

Dans la console, juger les cartes de l'exercice qui sont dans TO JUDGE (une recommandation, une
vérification en échec). Un isolement autonome vérifié n'y fait aucune carte : le 12/11, aucune carte
à juger pour le run (`docs/observation.md`, « Juger chaque carte » ; JUG1, à venir). Le Heartbeat de
gondolin revient en quelques minutes (la requête de l'étape 1).

### 8. Mesurer (10 min)

Depuis le poste, une fois la levée faite :

```zsh
make bench-report RUN=<run_id>     # TARGET=vm-celebrimbor-gondolin par défaut ; OUT=… pour le JSON ailleurs
```

*Vérifié sur des faux* (BNC1 : `tests/unit/test_bench_report.py`, sur les formes mesurées le 09/11).
La cible compose la chronologie du run, dans la forme du compte rendu du 09/11, sans rien écrire sur
Azure, sur Imladris ni sur Orodruin (`scripts/bench_report.py`) :
- **« Les chiffres »**, depuis T0 : la détection, l'isolement, la coupure demandée et aboutie, la
  vérification relue, la neutralisation, le job de restore, le démarrage, la levée et l'agent invité ;
- **le `restore_time` en deux nombres** : le job, puis le démarrage, et s'il a été retenu par la
  quarantaine jusqu'à la levée ;
- **« La chronologie »**, puis **les Run Command de la cible** : leur début, leur fin, leur statut,
  leur durée, et leur appelant par son rôle (la console, le bot, Imladris, Orodruin, un humain, inconnu) ;
- **les jobs du coffre**, et ce qui n'a pas pu être lu.

Ses sources :
- sur Imladris, par ssh, la clé d'hôte vérifiée par son empreinte (sinon rien ne part) : le rapport du run
  (`runs/glorfindel/<run_id>.json`, son T0, sa détection, la demande de Dagorlad dont il est un fil),
  les cycles du run, le `recovery_complete` de la watch (REC1), les levées de `manual_actions.jsonl`
  et l'état d'isolement de la cible s'il est encore là. `scripts/bench_h0_reader.py` les lit dans un
  conteneur jetable de l'image déployée, jamais dans la watch : sans réseau, sans capacité, chaque
  montage en lecture seule (`docs/operations.md`, « Le banc lisible ») ;
- le journal d'activité de la cible et de ses cartes réseau, chacune lue à part : ses Run Command,
  l'écriture d'Imladris sur une de ses cartes (l'isolement, quand l'état d'Imladris est levé ; une isolation par
  les seules règles d'un NSG n'y paraît pas), les désallocations et les démarrages ; une lecture qui
  atteint le plafond est dite coupée ;
- les jobs du coffre et la vue d'instance (l'agent `Ready`, relu au moment de composer).

Le Markdown s'affiche, et s'écrit à côté du JSON (`runs/bench/<run_id>.json` et `.md`, ou `OUT=`) : le JSON
alimentera plus tard `docs/proofs.json`. Un appelant devient un rôle, une ressource un nom du banc
déjà public. Le `restore_time` de la CLI du poste ne se lit qu'à sa sortie (étape 6) : le noter à
part. Le calcul à la main reste en annexe, pour un dépannage (« Annexe B »).

**Mesuré le 12/11.** `make bench-run` compose le rapport juste après la détection : composé 7 s
après elle, il ne montrait ni l'isolement ni le cycle `isolate_vm`. Le relancer après la coupure,
puis après la levée (`make bench-report RUN=…`) : la v3, composée après la levée, porte tous les
chiffres. Deux manques y restent, à corriger dans le code : les jobs du coffre se lisent avec
`--end-date` à la date du jour (`scripts/bench_report.py:410`), qui exclut ceux du jour ; le rapport a
montré le job de sauvegarde de la veille comme « point de restauration pris », sans le point de
l'étape 2 ni le job du restore (« aucun job de restore de la cible après T0 dans le coffre »). Le point choisi et le
`restore_time` se lisent donc à la sortie de `make bench-restore`.

| Le chiffre | Sa définition | Où le lire |
|---|---|---|
| **T0** | le début de l'étape d'attaque, `record: T0` : la graine de 512 Mo puis le chiffrement (`engine.py:412-425`) | `attack_time` du rapport ; Orodruin, `Run:` |
| **la détection** | T0 → la première détection de la watch pour ce run, lue sur le canal retour (`annatar/runner/detection.py:67-75`) | `detection_latency_s` ; « ✓ Glorfindel detected the attack N s » ; la chronologie de Dagorlad |
| **la carte** | T0 → la carte de l'action, dans la console | le cycle `isolate_vm` (son horodatage) ; Discord |
| **le confinement** | T0 → l'isolement relu sur Azure (`verified_at`), la définition de BL1 (`analysis/containment.py`) | la ligne `isolate_vm … verified=True T0+…` ; Dagorlad, « contained … » ; la page Annatar, « TIME TO CONTAIN · EXERCISES » (une médiane sur la période ; la tuile de l'accueil, « · REAL », exclut les exercices) |
| **la restauration finie** | la fin de `restore --wait`, et sa durée | `restore_time` et l'heure notée à l'étape 6 |
| **le service rendu** | T0 → la levée relue sur Azure, les gestes humains compris (deux sans REC1, le restore seul avec) | la ligne `levée … T0+…` ; avec REC1, `levée watch … T0+…` |
| **au sens du README** | détection + isolement + `restore_time`, sans le temps de décision humaine (`cli.py:1510`) | la somme des trois |

Les chiffres vont dans l'issue #665, datés, avec le `run_id` et l'identifiant de la demande : ils
remplaceront ceux du README, et la ligne T1486 de son tableau.

### 9. Remettre le banc en état (5 min)

Depuis le poste :

```zsh
make glorfindel-host-ssh
```

Puis, sur Imladris :

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
  local ; `--from-azure` lit les NSG (`cli.py:2057-2095`).

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
| « Restore refusé avant de toucher la VM : il manque … » | un droit du restore manque au principal de la console, lu avant tout geste (RST1) : le rôle nommé | poser ce rôle (`docs/operations.md`, « Identités Azure ») ; la VM n'a pas été touchée |
| « Restore trigger failed — 403 … » et « la VM … reste désallouée » | Azure a refusé le déclenchement après la désallocation (un refus explicite que l'API des droits ne rend pas). Il ne laisse **aucune trace** au journal d'activité : seule la sortie le garde | la garder ; `az vm start -g rg-celebrimbor -n vm-celebrimbor-gondolin` ; poser le droit nommé, relancer |
| « Restore job … Failed : code … » ou « not found after trigger » | le job a échoué tout de suite (son erreur est dite), ou n'est pas apparu en 2 min | lire les jobs du coffre (`az backup job list …`) **avant** de relancer ; la VM est désallouée : la redémarrer une fois sûr qu'aucun restore ne tourne |
| quelque chose part de travers sur Orodruin | — | `make orodruin-kill` : il révoque l'identité d'Orodruin, annule le chaos, désalloue sa VM et ferme les fenêtres. Il ne lève rien sur gondolin. Ensuite, `make orodruin-lock` (plan relu) lui rend ses droits (`infra/orodruin/README.md`, « Urgence ») |
| `make celebrimbor-up`, l'apply complet | un apply retire les règles `glorfindel-*` des NSG à règles en ligne. Le plan complet du 12/11 montrait aussi les dérives du banc : 42 des 44 règles du NSG partagé sont des `glorfindel-*`, posées par Glorfindel, et le plan veut rattacher à gondolin, au LUN 10, son disque de données d'origine, que le restore a remplacé | **jamais d'apply complet** tant que ces dérives tiennent, même `glorfindel list` vide : seulement un apply ciblé, son plan relu ([`demarrer/banc.md`](demarrer/banc.md), étape 1) |

`make orodruin-kill DRY_RUN=1` dit ce que le kill arrêterait, sans rien arrêter (*vérifié à blanc*,
`make -n` : `kill.py … --dry-run`).

## Le coût et la durée

| Poste | Estimation | D'où |
|---|---|---|
| gondolin allumée ~1 h 30 | ~0,15 € | 71 €/mois en continu pour la même taille (bree, `docs/demarrer/banc.md`), soit ~0,10 €/h |
| Orodruin, le temps de la session | quelques centimes | ~5–9 €/mois désalloué entre les sessions (`docs/demarrer/banc.md`) |
| Azure Backup | le stockage du point à la demande, incrémental, 30 jours ; la VM est déjà protégée (`backup.tf`) | **non mesuré** |
| le modèle, sur Imladris | la détection, les tirages avant l'isolement (3 par défaut, `GLORFINDEL_DECISION_DRAWS`), la recommandation de restore : de l'ordre de 0,10 à 0,30 $ | ~0,05–0,10 $ par run (`docs/operations.md`, « Coûts réels ») ; **non mesuré** pour T1486 sur Imladris |

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
4. **La levée** : sans REC1 à la main ; avec REC1 par la watch d'Imladris, ou à la main avec la carte
   qui l'a retenue ; relue sur Azure, gondolin plus `ISOLATED` ; le service rendu à T0+…, et la somme
   au sens du README, à comparer à 21m29s.
5. **Rien hors du périmètre** : aucune action sur bree, aucune carte inattendue. Sinon, la carte et
   sa ligne.
6. **Les identifiants** : la demande, le `run_id`, la date. Puis la décision : les chiffres du README
   remplacés (avec leur source), ou le run à rejouer.

## Annexe A — l'étape 0 à la main (dépannage)

Ce que `make bench-preflight` lit, commande par commande, quand une ligne de la cible demande d'y
regarder de plus près. Ces sorties-là affichent des identifiants : ne pas les recopier.

```zsh
source .envrc
make glorfindel-host-status        # « ✓ référence déployée : v<la release publiée> », les trois conteneurs ✓, aucune erreur
make glorfindel-host-cd-status     # actif : ne publie aucune release pendant la session (ou make glorfindel-host-cd-disable)
docker ps --no-trunc --format '{{.Names}}\t{{.Image}}\t{{.Label "com.docker.compose.service"}}\t{{.Command}}'
                                   # aucun "glorfindel watch …" ni service watch d'eregion-glorfindel :
                                   # une watch du poste répondrait aussi
az role assignment list --assignee ${EREGION_CONSOLE_AZURE_CLIENT_ID} --all -o table
terraform -chdir=infra/glorfindel-host output restore_neutralize
terraform -chdir=infra/glorfindel-host output restore_staging
```

Ce qu'on doit voir :
- **pour le principal de la console** : `Reader`, « Eregion Glorfindel Response » et « Eregion
  Glorfindel Restore » sur `rg-celebrimbor` ; `Log Analytics Reader` sur le workspace du banc ;
  « Eregion Glorfindel Restore Neutralize » et « Eregion Glorfindel Session Drain » à la portée de
  gondolin ; « Eregion Glorfindel Restore Staging » à la portée du seul compte de transit
  (`stcelebrimborstaging`), jamais du groupe (`docs/operations.md`, « Identités Azure ») ;
- **dans la sortie Terraform** : la console et le bot, sur gondolin et bree ; puis `bot`, `console`
  pour le compte de transit.

**La paire de la console, sur ce poste** (RST1) : le restore de l'étape 6 la prend pour sa seule
commande. Vide, il ne fait pas échouer : il prend une autre identité, sans le dire (le 09/11, elle
était restée commentée dans `.envrc`). Trois vérifications, en lecture seule :

```zsh
echo ${#EREGION_CONSOLE_AZURE_CLIENT_ID} ${#EREGION_CONSOLE_AZURE_CLIENT_SECRET}   # deux longueurs non nulles, jamais les valeurs
make azure-pairs-expiry            # « ✓ console : secret valable jusqu'au … (… j), sur son … », une seule date
AZURE_CLIENT_ID=${EREGION_CONSOLE_AZURE_CLIENT_ID} AZURE_CLIENT_SECRET=${EREGION_CONSOLE_AZURE_CLIENT_SECRET} \
  .venv/bin/glorfindel audit $(az vm show -g rg-celebrimbor -n vm-celebrimbor-gondolin --query id -o tsv)   # lecture seule
```

Ce qu'on doit voir :
- **les longueurs** : 36 pour l'identifiant, une quarantaine pour le secret ; `0`, la paire n'est
  pas chargée (`.envrc`, puis `source .envrc`) ;
- **la date de fin** : une seule, à plus de 14 jours (un avertissement en dessous ; plusieurs
  secrets sur l'application : la cible le dit, un seul est attendu) ;
- **l'audit** : il répond sans erreur d'authentification. Le droit qui manque à un restore, lui, se
  lit à l'étape 6 : le restore lit ses droits avant de toucher la VM et nomme celui qui manque.

## Annexe B — la mesure de l'étape 8 à la main (dépannage)

Ce que `make bench-report` compose, lu directement sur Imladris, quand le journal d'activité ou le coffre
ne se lisent pas depuis le poste.

Toujours sur Imladris (sinon, `make glorfindel-host-ssh` d'abord) :

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
            o = d.get("outcome") or {}   # REC1 : la levée de la watch ; sans REC1, aucune ligne
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
arrive sur Imladris quand le fil a fini ; sur Orodruin, le même est dans `~/runs/annatar/<run_id>.json`.
