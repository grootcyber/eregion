# Le banc complet : d'une attaque à sa preuve

[← README](../../README.md) · le guide d'avant : [observer en lecture seule](bleu.md) · ce qui reste à rejouer sur Azure : [a-rejouer.md](a-rejouer.md) · depuis le téléphone : [mobile.md](mobile.md)

**Pour qui.** Un ingénieur infra ou sécurité qui veut voir la boucle entière : une attaque réelle, publique et épinglée, lancée sur une cible jetable, et ce que Glorfindel en a fait. On le mesure par le verdict (`detected`, `missed` ou `unknown`), le rapport de la campagne et la console.

**Ce que tu construis.** Trois états Terraform séparés, chacun dans son groupe :

| Pièce | Ce que c'est | Module |
|---|---|---|
| **Celebrimbor** | le banc : la VM cible gondolin, inscrite en zone `bench` ; bree, la VM d'une vraie charge, jamais inscrite ; l'espace Log Analytics ; le coffre de sauvegarde | `infra/terraform/` |
| **Imladris (anciennement H0)** | Glorfindel hébergé : sa watch, sa console et son bot, sur une VM à lui | `infra/glorfindel-host/` |
| **Orodruin** | l'hôte jetable des injecteurs : le seul endroit d'où une attaque part | `infra/orodruin/` |

**Pourquoi Imladris.** Un injecteur n'agit que derrière une watch de Glorfindel vivante : avant toute action, il lit son battement (un fichier qu'elle réécrit chaque minute), signé par la clé de la watch, sur le canal retour, un conteneur de stockage partagé avec Orodruin. Sans battement de moins de 90 s, il refuse. Ce guide le fait écrire par Imladris ; sans Imladris, la watch de ton poste peut l'écrire (voir [sans Imladris](#sans-imladris--la-watch-de-ton-poste)).

**Comment lire ce guide.** Chaque étape dit d'où vient ce qu'elle affirme :
- *lu dans le code* : le fichier est cité ;
- *mesuré* : la date et la page de la mesure ;
- **non vérifiée** : ni l'un ni l'autre.

Rien de ce guide n'a été rejoué sur Azure pour l'écrire : [a-rejouer.md](a-rejouer.md) liste ce qu'on doit y voir.

## Le coût et le temps

| Étape | Région (défaut) | Temps | Coût | D'où |
|---|---|---|---|---|
| 1. Celebrimbor | `westeurope` (`infra/terraform/config.yaml`) | ~5 min | ~25–35 $/mois, VM éteinte à 23 h UTC ; **plus bree, allumée en continu : ~71 €/mois** | README ; `infra/terraform/config.yaml` |
| 3. Imladris | `francecentral` (`infra/glorfindel-host/variables.tf`) | la VM : **non mesuré** (cloud-init installe Docker et clone le dépôt) ; l'image construite sur Imladris en 2 min 44 s (16/10) | ~61 €/mois en continu (D2als_v6), plus le disque et l'IP | `infra/glorfindel-host/README.md`, `variables.tf` |
| 4. Orodruin | `francecentral` (`infra/orodruin/variables.tf`) | 5 min ; 30 min s'il faut le recréer | ~5–9 €/mois, désalloué entre les sessions | `docs/banc-bl1.md` ; `docs/design/orodruin-contract.md` |
| 7. La première attaque | — | détection en 44,7 s (20/10) à 144 s (31/10) ; le rapport ~25 min après | le modèle : ~0,05–0,10 $ par run | `docs/banc-bl1.md`, README |
| Chaos Studio (une panne, facultatif) | celle du banc | ~15 min | à l'usage : 11 à 42 €/mois estimés pour 2 à 4 campagnes | `docs/operations.md`, « Coûts réels » |
| **Total, tout en place** | | | **~160 à 175 €/mois** : bree ~71 + Imladris ~61 + le reste du banc ~23–32 (25–35 $) + Orodruin ~5–9, hors modèle et Chaos Studio | la somme des lignes ci-dessus |

Entre deux sessions : `make orodruin-stop` et `make celebrimbor-stop` (bree épargnée ; `ALL=1` l'arrête aussi).

## 0. Avant (10 min)

- **Sur Azure.**
  - `Owner` sur l'abonnement : les rôles personnalisés et leurs attributions l'exigent.
  - Le quota de la famille de VM, dans chaque région : D2as_v6 pour le banc, en `westeurope` ; D2als_v6 pour Imladris et Orodruin, en `francecentral` par défaut (`location` de leur `variables.tf`).

    ```bash
    az vm list-usage -l westeurope -o table      # le banc
    az vm list-usage -l francecentral -o table   # Imladris et Orodruin
    ```
- **Sur le poste.**
  - `terraform` 1.5 ou plus, `az` (`az login`), `ssh` et une paire de clés SSH ;
  - `make install` : `imladris-env`, `-push` et `watch-key` lancent le venv.
- **Une clé du modèle** : `ANTHROPIC_API_KEY` dans `.envrc`. `make imladris-env` l'exige (`infra/glorfindel-host/host_env.py`).

```bash
git clone https://github.com/grootcyber/eregion && cd eregion && make install
cp .envrc.example .envrc       # AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, ANTHROPIC_API_KEY ; puis direnv allow
make doctor PROFILE=bench      # les outils doivent être verts ; le reste se remplit au fil des étapes
```

Toutes les commandes suivantes se lancent depuis le poste, `.envrc` chargé.

## 1. Celebrimbor, le banc

```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars   # ta clé SSH publique, ton e-mail
make celebrimbor-plan          # lecture seule : relire
make celebrimbor-up            # le plan est montré, « yes » l'applique (YES=1 l'appliquerait sans le relire)
make celebrimbor-output        # le fragment de glorfindel-config.yaml : l'espace, le coffre, le compte de transit
```

- **Un banc qui tourne déjà : jamais d'apply complet.** `make celebrimbor-up` ne se lance que pour créer
  le banc. Ensuite, tant que les dérives tiennent, seul un apply ciblé se fait (`make celebrimbor-flows-up`,
  `-logs-up`, `-identity-up`, `-auditd-up`…, chacun après son plan) : le plan complet du 12/11 retirait
  42 des 44 règles du NSG partagé, posées par Glorfindel (les règles du NSG sont en ligne,
  `infra/terraform/network.tf`), et voulait rattacher à gondolin, au LUN 10, son disque de données
  d'origine, que le restore du T1486 a remplacé. `make celebrimbor-plan` se lit, il ne s'applique pas.
- **La configuration.** Copie le fragment dans `glorfindel-config.yaml`, à la racine du dépôt. `make imladris-push` l'envoie sur Imladris, le défaut forcé en `human_only` (`infra/glorfindel-host/host_config.py`).
- **Le fichier partagé.** `terraform.tfvars` sert aussi aux modules d'Imladris et d'Orodruin (`-var-file=../terraform/terraform.tfvars`, Makefile).

*Lu dans le code : Makefile, `celebrimbor-*` ; `infra/terraform/outputs.tf`, `glorfindel_config_fragment`.*

## 2. Les identités de Glorfindel

**Sur Imladris, pas de principal de service.** Ses trois conteneurs partagent l'identité managée de la VM (`docs/operations.md`, « Identités Azure ») :
- son Terraform lui donne `Reader` sur le groupe du banc et `Log Analytics Reader` sur son espace ;
- il donne aussi « Eregion Glorfindel Session Drain » sur chaque VM de `session_drain_vms` (gondolin et bree, `infra/glorfindel-host/session_drain.auto.tfvars`).

Ce rôle personnalisé doit exister avant le plan d'Imladris : le Terraform le nomme. Une fois par tenant, les cinq rôles de `infra/identities/` (le Terraform d'Imladris nomme aussi « Restore Neutralize » et « Restore Staging », dès que `principals.auto.tfvars` donne les principaux qui restaurent) :

```bash
SUB=$AZURE_SUBSCRIPTION_ID                   # .envrc chargé ; vide, le sed écrit « /subscriptions/ » et az refuse chaque rôle
GUID='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
if printf %s "$SUB" | grep -qE "$GUID"; then    # sans l'afficher ; pas un GUID : rien ne part
  for r in response restore session-drain restore-neutralize restore-staging; do
    sed "s|<SUBSCRIPTION_ID>|$SUB|" infra/identities/glorfindel-$r.json > /tmp/eregion-role-$r.json
    az role definition create --role-definition @/tmp/eregion-role-$r.json
  done
else echo "SUB n'est pas un GUID : source .envrc, puis relancer le bloc"; fi
```

- **Pour une première attaque, Imladris observe** : `GLORFINDEL_READ_ONLY=1` et `human_only` sont ce qu'écrit `make imladris-env`. La détection se mesure ainsi. Le confinement, non : Glorfindel recommande et escalade, il n'agit pas.
- **Pour qu'il contienne seul**, il faut trois choses, dans l'étape 3 de [`docs/banc-bl1.md`](../banc-bl1.md) :
  - le rôle « Eregion Glorfindel Response » attribué à la main, sur `rg-celebrimbor` ;
  - `GLORFINDEL_READ_ONLY=0` dans `host.env` ;
  - gondolin passée en `non_disruptive` dans la console.
- **Un principal par service** (la watch, la console, le bot) ne sert qu'à un Glorfindel lancé sur un poste : [`docs/operations.md`](../operations.md), « Identités Azure ». Un restore se fait depuis la console ou la CLI du poste, sous le principal de la console. Imladris ne restaure jamais.

## 3. Glorfindel : la VM d'Imladris

```bash
make imladris-plan             # lecture seule ; OPERATOR_CIDR=<ton ip>/32, sinon ton IP du moment
make imladris-up               # la VM ; confirmation demandée
```

La VM seule, pour l'instant. Glorfindel y démarre à l'étape 5, une fois les canaux d'Orodruin connus.
- **Orodruin lit l'état d'Imladris** : son identité et son sous-réseau, pour lui ouvrir le canal. `orodruin-plan`, `-up` et `-lock` refusent sans cet état (`orodruin-watch-guard`), sauf `NO_WATCH=1` (sans Imladris : [la watch de ton poste](#sans-imladris--la-watch-de-ton-poste)).
- **Imladris a besoin des canaux d'Orodruin** dans son `host.env`.

Facultatif, recommandé : l'empreinte de sa clé d'hôte dans `.envrc` (`HOST_SSH_FINGERPRINT`, relevée sur la VM : [`infra/glorfindel-host/README.md`](../../infra/glorfindel-host/README.md), « SSH »). Sans elle, chaque commande vers Imladris dit qu'elle accepte la première clé vue.

## 4. Orodruin

```bash
make orodruin-plan             # relire : ce plan est celui de la sortie FERMÉE (egress_locked=true)
make orodruin-up               # 1er apply : il OUVRE la sortie (egress_locked=false), le temps d'installer Docker ;
                               # son plan, différent de celui d'orodruin-plan, est montré : le relire, puis « yes »
make orodruin-fingerprint      # l'empreinte de sa clé d'hôte, lue par Azure (Run Command)
export ORO_SSH_FINGERPRINT=SHA256:…    # la ligne affichée, aussi dans .envrc : sans elle, rien ne part vers Orodruin
make orodruin-ssh              # attendre ~/.orodruin-ready, puis exit
make orodruin-lock             # 2e apply : la sortie se referme ; son plan montré, « yes »
cp infra/orodruin/orodruin.env.example infra/orodruin/orodruin.env
```

Remplis `infra/orodruin/orodruin.env`, ignoré par git, depuis les sorties de son Terraform :

| Variable | Sa valeur |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | celui du banc ; il doit être celui de la watch : le battement porte un condensé de l'abonnement qu'elle lit, et l'injecteur refuse celui d'un autre |
| `EREGION_EXERCISE_CHANNEL` | `terraform -chdir=infra/orodruin output -raw channel_url` |
| `EREGION_CHANNEL_SCOPE` | `… output -raw channel_scope` |
| `EREGION_WATCH_CHANNEL` | `… output -raw watch_channel_url` |
| `EREGION_WATCH_CHANNEL_SCOPE` | `… output -raw watch_channel_scope` |
| `EREGION_WATCH_KEY` | à l'étape 5 |

Pas d'`AZURE_CLIENT_*` dans ce fichier : elles masqueraient l'identité managée. `make doctor PROFILE=bench` le refuse.

Chaque apply d'Orodruin, `up` comme `lock`, relit les VM inscrites et donne à son identité ses droits sur chacune (`vm_injector`, qui ne dépend pas de la sortie). `YES=1` appliquerait sans montrer le plan : à ne pas utiliser ici, surtout pour `orodruin-up`, dont le plan n'est pas celui d'`orodruin-plan`.

*Lu dans le code : Makefile, `orodruin-*` ; `infra/orodruin/main.tf` ; `infra/orodruin/README.md`, « Déroulé ». Mesuré le 19/10 : la sortie fermée, `armed`, un premier run.*

## 5. Glorfindel démarre, et sa clé s'épingle chez Orodruin

```bash
export EREGION_EXERCISE_CHANNEL=$(terraform -chdir=infra/orodruin output -raw channel_url)
export EREGION_WATCH_CHANNEL=$(terraform -chdir=infra/orodruin output -raw watch_channel_url)
make imladris-env              # host.env : ton environnement (les deux canaux compris), READ_ONLY=1, un jeton de console
make imladris-push             # host.env et glorfindel-config.yaml sur la VM
make imladris-start REF=<tag ou commit>          # un tag publié (git tag -l 'v*'), jamais une branche
make imladris-logs             # « heartbeat → N VM(s) », « Canal retour : … », « Clé de la watch : SHA256:… »
make imladris-watch-key # export EREGION_WATCH_KEY=ed25519:… et son empreinte
```

- **La clé.** La watch tire sa clé à son premier démarrage (`~/.eregion/watch-key` sur Imladris).
- **Où l'épingler.** La ligne `EREGION_WATCH_KEY=ed25519:…` va dans `orodruin.env`. Mets-la aussi dans `host.env` : la console d'Imladris vérifie alors le battement comme Orodruin le vérifie, et sa page d'exercice dit d'avance si un run serait refusé. `make imladris-push` ne fait que copier le fichier ; la console relit son environnement quand on la recrée, pas quand on la redémarre :

  ```bash
  make imladris-push
  make imladris-ssh              # puis, sur Imladris :
  cd eregion && docker compose up -d war-room && exit
  ```
- **Puis l'image d'Annatar sur Orodruin, et le contrat :**

```bash
make orodruin-push REF=<le même tag>   # l'image publiée, digest, signature et provenance vérifiés ici ; + orodruin.env
make orodruin-check                    # attendu : armed
make doctor PROFILE=bench              # tout vert
```

- **`host-env` refuse d'écraser** un `host.env` existant : son jeton changerait. Pour un `host.env` déjà écrit, ajoute les deux canaux à la main.
- **Le battement d'Imladris.** Il part sur le canal retour toutes les 60 s, signé (`eregion_core/watch_channel.py`). Orodruin le croit s'il a moins de 90 s, si la clé épinglée le vérifie, et s'il porte le même abonnement (`eregion_core/watch_gate.py`).

*Lu dans le code : Makefile, `imladris-*`, `orodruin-push`, `watch-key` ; `docs/design/watch-key.md`. Le passage de la clé d'Imladris à Orodruin : **non vérifié** sur ce chemin de zéro, fait par Jonathan à la 0.5.3 (`docs/operations.md`, « Le battement signé, l'attestation signée — les gestes »).*

## 6. L'inscription des cibles

Rien à faire de plus : Celebrimbor inscrit ses VM à leur construction.
- **Les tags.** gondolin et son groupe portent `eregion-target=celebrimbor` et `eregion-zone=bench` (`infra/terraform/locals.tf`). bree ne les porte pas (`enrolled: false`) : aucun injecteur ne la vise.
- **Les droits.** Chaque apply d'Orodruin (`make orodruin-up`, `make orodruin-lock`) relit les VM inscrites et donne à son identité ses droits sur chacune, et seulement elles. Une VM inscrite plus tard : un nouveau `make orodruin-lock`.

Le vérifier, c'est la vraie lecture de la zone :

```bash
az vm show -g rg-celebrimbor -n vm-celebrimbor-gondolin --query tags
az group show -n rg-celebrimbor --query tags
```

Les injecteurs relisent l'inscription et la zone avant chaque action (`eregion_core/inscription.py`). Tout ce qui est inconnu est refusé.

## 7. La première attaque, puis sa preuve (30 à 45 min)

La technique : T1136.001, la création d'un compte local, par le test épinglé d'Atomic Red Team. Elle ne détruit rien, et son nettoyage retire le compte. La campagne déclarée la joue sur gondolin.

**Ce qui compte ici : le verdict de détection.** `bl1-reponse.yaml` attend `contain` (Glorfindel isole ou bloque seul) : cette attente ne peut pas être tenue dans ce guide, par construction. Imladris y tourne en `human_only`, en lecture seule : il détecte, recommande, et **retient** l'action. Le rapport dira donc « non contenu » : ce n'est pas un échec. Pour mesurer le confinement, voir l'étape 2, « Pour qu'il contienne seul ».

```bash
make celebrimbor-start VM=gondolin       # elle s'éteint à 23 h UTC
make orodruin-check                      # armed
make orodruin-campaign-plan CAMPAIGN_TARGET=$(az vm show -g rg-celebrimbor -n vm-celebrimbor-gondolin --query id -o tsv) \
  CAMPAIGN_DECLARED=annatar/campaign/declared/bl1-reponse.yaml       # rend l'id de la campagne
make orodruin-campaign-run CAMPAIGN=<id>
```

La preuve, à trois endroits :
- **Le verdict.** La fin de la campagne, sur Orodruin, le compte : `executed=1 detected=… missed=…` (`annatar/cli.py`). Le rapport du run dit `detected`, `missed` ou `unknown`.
  - `unknown` ne veut jamais dire « manqué » : le canal était muet, la watch ne connaissait pas la fenêtre du run, ou ce qu'il disait n'était pas signé par la clé épinglée (une watch d'avant SEC21 : « unsigned … update Glorfindel ») (`docs/design/orodruin-contract.md`, « Échec vers `unknown` »).
  - Le rapport du run part ensuite vers Imladris par le canal des fenêtres.
- **Le rapport de la campagne**, écrit seul sur Imladris, environ 25 min après : `make imladris-campaign-report CAMPAIGN=<id>`.
- **La console d'Imladris** : `make imladris-tunnel-on` (le tunnel du poste, 12 h au plus ; `make imladris-tunnel-install` une fois avant), puis l'URL de `make imladris-url` ; au premier plan, sans armer les 12 h : `make imladris-tunnel`.
  - La page **Annatar** : la campagne, son run, et ce que Glorfindel en a fait.
  - La page **Glorfindel** : la carte de la détection, l'action recommandée et retenue.
  - L'**accueil** : la preuve de la technique, datée.

*Mesuré le 31/10 (`docs/banc-bl1.md`) : T1136.001 détectée en 144 s. Ce jour-là, Imladris répondait en `non_disruptive` : un instantané recommandé à 35 %, escaladé sous le seuil de 0,7. Ce guide part en `human_only` : la carte retient l'action. Ce que l'accueil affiche après une seule campagne est **non vérifié**.*

**Sans cible Make pour un run seul.** Un scénario seul se lance de la VM : `make orodruin-ssh`, puis le `docker run` d'un injecteur, durci (`infra/orodruin/README.md`). La campagne déclarée, elle, passe par des cibles Make.

**Le rançongiciel (T1486)**, une technique destructive, se rejoue par une demande de Dagorlad, avec son restore et sa levée : [`banc-t1486.md`](../banc-t1486.md).

**Ce que le journal d'activité dit des gestes sur une VM** (LEV2, avant la règle de levée de LEV3) : des écritures sans effet sur gondolin, chacune avec son retour, puis un rapport sans identifiant : [`banc-lev2.md`](../banc-lev2.md).

## 8. Tout démonter

Dans cet ordre : Orodruin lit encore l'état d'Imladris, et les trois modules lisent `terraform.tfvars`.

```bash
# rien d'isolé ni de bloqué : la console d'Imladris, ou
make imladris-ssh              # puis : docker exec eregion-watch glorfindel list   (vide), exit
make orodruin-down             # la VM, son identité, ses rôles, le compte des canaux
make imladris-down             # la VM d'Imladris et son état (sa mémoire comprise : make imladris-pull avant, pour la garder)
make celebrimbor-down CONFIRM=default    # le banc entier, baseline compris (sans CONFIRM, refusé)
for r in "Eregion Glorfindel Response" "Eregion Glorfindel Restore" "Eregion Glorfindel Session Drain" \
         "Eregion Glorfindel Restore Neutralize" "Eregion Glorfindel Restore Staging"; do az role definition delete --name "$r"; done
rm -f infra/orodruin/orodruin.env infra/glorfindel-host/host.env ~/.eregion/orodruin_known_hosts ~/.eregion/h0_known_hosts
```

- **Le rôle de la réponse.** S'il a été attribué à la main (étape 2), retire-le d'abord : [`docs/banc-bl1.md`](../banc-bl1.md), étape 7.
- **Un rôle encore attribué** quelque part n'est pas supprimé : `az role assignment list --all --query "[?roleDefinitionName=='<nom>']" -o table` (jamais `--role "<nom>" --all` : sans portée, az plante, `docs/operations.md`, en tête).
- **Le reste** (Discord, la clé du modèle) : le README, « Remove Eregion ».

## Sans Imladris : la watch de ton poste

Une watch qui tourne sur ton poste peut écrire le canal retour à la place d'Imladris (WC1, #523) :

```bash
az ad sp show --id "$GLORFINDEL_AZURE_CLIENT_ID" --query id -o tsv   # l'object id du principal de ta watch
make orodruin-plan WATCH_PRINCIPALS=<object id> NO_WATCH=1
make orodruin-lock WATCH_PRINCIPALS=<object id> NO_WATCH=1          # les mêmes options à chaque -up et -lock
```

- **Ce qu'elle reçoit.** La lecture des fenêtres et l'écriture du canal retour, rien d'autre. Sans les mêmes options, un apply suivant les lui retire.
- **Sur ton poste.** `EREGION_WATCH_CHANNEL` et `EREGION_EXERCISE_CHANNEL` (`terraform -chdir=infra/orodruin output`), puis `make glorfindel-start`.
- **Dans `orodruin.env`.** La clé de ta watch (`make watch-key`), puis `make orodruin-push`. Un battement ou une détection d'une autre clé reste refusé (SEC19, SEC21).
- **Le réseau.** Elle passe par ton IP, que le pare-feu du compte du canal admet déjà. Ton IP a changé depuis le dernier apply : le canal ne se lit plus, et chaque run est refusé.

Détail : [`infra/orodruin/README.md`](../../infra/orodruin/README.md), « Sans Imladris ». Le profil « plusieurs équipes » ([`equipes.md`](../profils/equipes.md)) prend ce même chemin.

*Lu dans le code et testé sans Azure (`infra/orodruin/tests/watch_writers.tftest.hcl`, `tests/unit/test_makefile_bench.py`, `tests/unit/test_watch_key.py`) : **la mesure au banc reste à faire**.*
