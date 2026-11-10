# Piloter le banc depuis le téléphone (MOB1)

[← le banc](banc.md) · le rejeu du rançongiciel : [banc-t1486.md](../banc-t1486.md) · le modèle de menace : [frontière 9](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste)

**Le principe.** C'est toujours l'opérateur qui tape la commande **sur son poste**. Seul le chemin
entre le téléphone et le poste change :

```
téléphone ──(réseau privé : Tailscale)──► poste (WSL) : sshd, à clé seule ──► make bench-run / bench-restore
                                                      └─ tunnel SSH ──► H0 : la console (127.0.0.1:7007)
```

- Orodruin continue à n'écouter que le SSH du poste (DRL1). Rien n'est installé sur H0 ; sa
  configuration reçoit une ligne (`EREGION_CONSOLE_HOSTS`, plus bas).
- **Deux barrières indépendantes** : le réseau privé (le compte Tailscale avec MFA, une règle
  d'accès qui n'ouvre que téléphone → poste), puis le serveur SSH du poste, **à clé seule**, la clé
  gardée dans la puce sécurisée du téléphone et débloquée par biométrie. L'une tombée, l'autre tient.
- Le lot fournit les commandes et les modèles (`infra/poste/`) ; **Jonathan les applique**, aucune
  session ne le fait. Rien de ce guide n'a encore été joué sur le poste : chaque étape qui n'est ni
  lue dans le code ni testée sur des faux est marquée **non vérifié**.

## 0. Le Windows de l'hôte ne se met pas en veille

Un poste en veille ne répond plus, ni au téléphone ni à Orodruin, et une commande en cours (un
restore de 30 min) s'arrête avec lui. Sur Windows, branché sur secteur :

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

L'écran peut s'éteindre, pas la machine. WSL doit aussi rester démarré : garder un onglet WSL
ouvert dans Windows Terminal (la session `tmux`, plus bas, suffit). **Non vérifié** : que les seuls
services de systemd gardent la VM de WSL en vie, sans terminal ouvert.

## 1. Tailscale dans WSL (systemd)

Dans WSL, systemd allumé (`/etc/wsl.conf`, puis `wsl --shutdown` depuis Windows) :

```ini
[boot]
systemd=true
```

Puis Tailscale, depuis son dépôt (sa documentation, « Install Tailscale on Linux »), et :

```zsh
sudo systemctl enable --now tailscaled
sudo tailscale up                     # le compte de l'opérateur, avec MFA
sudo tailscale set --ssh=false        # Tailscale SSH fermé : le serveur SSH du poste, à clé, est le seul
tailscale ip -4                       # l'adresse privée du poste : une adresse de 100.64.0.0/10
```

Sur le téléphone : l'application Tailscale, sous le même compte. Garder l'expiration des clés de
chaque appareil (le défaut) : un appareil se ré-authentifie, il ne reste pas ouvert pour toujours.

**La règle d'accès.** Sans règle, Tailscale laisse chaque appareil joindre chaque autre. Le modèle
`infra/poste/tailscale-acl.hujson` la remplace, dans la console d'administration de Tailscale
(*Access controls*), les deux adresses remplacées par celles des appareils :
- téléphone → poste:22, le serveur SSH ;
- téléphone → poste:7007, la console de H0 par le tunnel du poste (étape 5) ;
- rien d'autre, et aucune règle `ssh` de Tailscale.

**Non vérifié** : la règle se lit dans la console de Tailscale, pas sur le poste ; `make
mobile-check` ne la voit pas.

## 2. Le serveur SSH du poste, durci

```zsh
sudo apt install openssh-server tmux
sudo install -m 644 infra/poste/sshd_config.d/00-eregion.conf /etc/ssh/sshd_config.d/00-eregion.conf
sudoedit /etc/ssh/sshd_config.d/00-eregion.conf      # ListenAddress <tailscale ip -4>, AllowUsers <toi>
sudo install -D -m 644 infra/poste/ssh.service.d/eregion.conf /etc/systemd/system/ssh.service.d/eregion.conf
sudo systemctl disable --now ssh.socket              # Ubuntu ≥ 22.10 : sshd écoute lui-même, pas le socket
sudo systemctl daemon-reload && sudo sshd -t && sudo systemctl enable --now ssh.service
```

- **Le fragment** (`infra/poste/sshd_config.d/00-eregion.conf`) : l'adresse privée seule ; aucun mot
  de passe, aucun clavier interactif, la clé seule (`AuthenticationMethods publickey`) ; pas de root ;
  aucune redirection (le téléphone n'a besoin que d'un terminal). Il s'appelle `00-` : `sshd` garde la
  **première** valeur qu'il lit, et un `50-cloud-init.conf` qui dirait `PasswordAuthentication yes`
  l'emporterait sur un `eregion.conf`.
- **L'ordre de systemd** (`infra/poste/ssh.service.d/eregion.conf`) : `sshd` attend que Tailscale ait
  son adresse avant d'écouter dessus, une minute au plus, et repart après un échec. **Non vérifié** sur
  le poste.
- **Le contrôle**, en lecture seule, chaque fois que la configuration change :

```zsh
sudo -v && make mobile-check
```

`make mobile-check` (`scripts/mobile.py`) dit une ligne ✓/⚠/✗ par point, sans afficher aucune
adresse, et sort en 1 sur un ✗ :
- le réseau privé : une adresse du tailnet, et Tailscale SSH fermé ;
- le serveur SSH (`sshd -T`, ce qu'il applique vraiment) : `PasswordAuthentication no`,
  `KbdInteractiveAuthentication no`, `PermitEmptyPasswords no`, `HostbasedAuthentication no`,
  `GSSAPIAuthentication no`, `PubkeyAuthentication yes`, `AuthenticationMethods` à clé seule ;
  `PermitRootLogin no` (un ⚠ sinon) ;
- les écoutes (`ss -Hltn`) : le port du serveur SSH sur l'adresse privée **seule** — toutes les
  interfaces (`0.0.0.0`, `[::]`, `*`), la boucle locale ou une autre adresse sont un ✗ ; le port de la
  console exposé nulle part ailleurs que sur l'adresse privée (la boucle locale, le tunnel du bureau,
  est un ⚠ : WSL la partage avec Windows) ;
- les clés admises (`~/.ssh/authorized_keys`) : combien, de quels types — jamais une clé affichée.

Il lit la configuration globale : un bloc `Match` peut la changer pour une connexion. Le fragment
n'en a pas ; n'en ajouter aucun.

## 3. La clé, dans la puce du téléphone

Dans **Blink Shell** (iOS) ou **Termius** (iOS, Android) : une clé créée **dans la puce sécurisée**
(Secure Enclave sur iOS, le Keystore matériel sur Android), non exportable, débloquée par biométrie.
Le type est ECDSA P-256 : c'est celui que la puce sait garder. **Non vérifié** : le nom exact du menu
dans chaque application.

Sa clé **publique** va sur le poste, une ligne par appareil, avec le nom de l'appareil en
commentaire et des options qui la bornent :

```
from="100.64.0.0/10",no-port-forwarding,no-agent-forwarding,no-X11-forwarding ecdsa-sha2-nistp256 AAAA… telephone-de-l-operateur
```

`chmod 600 ~/.ssh/authorized_keys`. La clé privée ne quitte jamais le téléphone : elle n'est ni
copiée, ni sauvegardée, ni synchronisée.

## 4. `tmux` : le terminal qu'on retrouve

Le téléphone perd la connexion (un tunnel, un écran qui se verrouille). Une commande lancée dans
`tmux` continue sur le poste, et on la retrouve :

```zsh
tmux new -A -s banc          # crée la session, ou la reprend
# Ctrl+b d : la quitter sans rien arrêter ; Ctrl+b c : une deuxième fenêtre (la console)
```

**Toujours lancer `make bench-run` et `make bench-restore` dans `tmux`.** Dans la session : `cd
~/eregion && source .envrc`, avec `HOST_SSH_FINGERPRINT` et `ORO_SSH_FINGERPRINT` posées.

## 5. La console de H0, sur le téléphone

Par le poste, rien sur H0 : téléphone → réseau privé → poste → le tunnel SSH vers H0. Une fois,
avant :

1. **Le nom sous lequel la console répond.** La console de H0 ne répond qu'aux noms qu'elle connaît
   (SEC1, `EREGION_CONSOLE_HOSTS`) : depuis le téléphone, son `Host` est l'adresse privée du poste.
   L'ajouter dans `infra/glorfindel-host/host.env` (`EREGION_CONSOLE_HOSTS=<tailscale ip -4 du
   poste>`), puis `make glorfindel-host-push`, puis sur H0 `cd eregion && docker compose up -d
   war-room` : la console relit son environnement (`restart` ne le relit pas,
   `infra/glorfindel-host/README.md`). Sans lui, le téléphone a un 403, et la cible le dit.
2. **Le tunnel**, dans une deuxième fenêtre de `tmux` :

```zsh
make glorfindel-host-tunnel-private    # « Console (téléphone) → http://<adresse privée>:7007/?token=… »
```

La cible (`Makefile`, `glorfindel-host-tunnel-private`) :
- exige la clé d'hôte épinglée de H0 (`HOST_SSH_FINGERPRINT`), jamais `accept-new` ;
- lie le port 7007 à la **seule adresse privée** du poste, celle que donne `tailscale ip -4`
  (`scripts/mobile.py private-ip`). Introuvable, ou hors de la plage de Tailscale : **rien ne
  s'ouvre** — jamais `0.0.0.0`, jamais la boucle locale (WSL la partage avec Windows) ;
- `ExitOnForwardFailure=yes` : un port qui ne se lie pas ferme le tunnel.

Le jeton de la console reste exigé : l'URL le porte une fois, la console le retire et pose un cookie
de session (12 h). Un restore depuis la console reste refusé sur H0 (elle n'a pas le rôle Restore) ;
il demandera le nom tapé et le code à usage unique avec TOT1 (#685). En attendant, le restore passe
par le terminal du poste (étape 6).

## 6. Un run depuis le téléphone

Le déroulé reste celui de [banc-t1486.md](../banc-t1486.md) ; deux commandes y remplacent des
étapes.

```zsh
make bench-run TARGET=vm-celebrimbor-gondolin SCENARIO=T1486 DRY_RUN=1    # tout, sauf l'envoi
make bench-run TARGET=vm-celebrimbor-gondolin SCENARIO=T1486              # tape vm-celebrimbor-gondolin, puis o
```

`make bench-run` (`scripts/bench_run.py`) enchaîne, chaque étape arrêtant la suivante :
1. **le préflight** (`make bench-preflight`, BNC1) : un ✗, rien n'est demandé, rien n'est lancé ;
2. **la demande** : un fil `SCENARIO` → `TARGET`, l'id de la VM lu sur Azure sous ton `az login`
   (une seule VM de ce nom), lue par le seul lecteur des demandes, comme celles de Dagorlad ;
3. **le nom de la cible, tapé**, destructif ou non, puis « [o/N] » : un autre nom, rien, ou pas de
   terminal, rien n'est envoyé ;
4. **le lancement** : la demande et le nom tapé portés sur Orodruin par son SSH épinglé, puis lancés
   par `eregion_core.exercise_runner`, qui la rejuge (contrat, watch, inscription, zone, le nom tapé
   comparé à celui qu'il lit, son plafond), comme `make orodruin-exercise` ; le nom tapé est retiré
   d'Orodruin à la fin, quelle qu'elle soit ;
5. **le rapport** : `make bench-report` pour chaque run de la sortie (« Run: … »).

Puis le restore, depuis le poste, sous la paire de la console :

```zsh
make bench-restore TARGET=vm-celebrimbor-gondolin DRY_RUN=1   # la paire, le moment, la VM, le nom tapé, l'essai à blanc
make bench-restore TARGET=vm-celebrimbor-gondolin             # tape vm-celebrimbor-gondolin, puis o
```

`make bench-restore` (`scripts/bench_restore.py`) :
- exige la paire de la console (`EREGION_CONSOLE_AZURE_CLIENT_ID`, `…_SECRET`) : vide, le restore
  prendrait une autre identité sans le dire (RST1) ;
- prend pour `--before` le T0 du run, son `attack_started` (la règle de SEC4c), tel que `make
  bench-report` l'a écrit dans `runs/bench/<run_id>.json` : `RUN=`, sinon le dernier run de
  `TARGET` ; `BEFORE=<instant>` l'emporte. Sans moment, rien n'est restauré ;
- passe **toujours** `--keep-isolated` : la levée est celle de H0 (REC1, REC1b ; LEV1 changera la
  règle) ;
- fait taper le nom de la VM, lance l'essai à blanc, puis demande « [o/N] » avant le vrai restore.
  Le restore lit ses droits avant de toucher la VM (RST1). La clé matérielle du SSH tient lieu de
  second facteur, en attendant FS1g et TOT1.

Ensuite, la levée par H0 (étape 7 de banc-t1486.md), puis `make bench-report RUN=<run_id>`.

**Les deux commandes refusent dans une session d'agent** (`EREGION_AGENT_SESSION`, le worktree d'un
lot), avant toute commande vers H0 ou Orodruin : une session ne lance jamais une attaque, ni un
restore. Elles refusent aussi `TARGET`, `SCENARIO`, `BEFORE` ou `RUN` venus de l'environnement : sur
la ligne de commande, toujours. Le T1486 reste lancé de la main de l'opérateur : aucun créneau
automatique ne joue de destructif (#684).

## 7. La perte du téléphone

Les deux barrières se ferment l'une sans l'autre ; fermer les deux, puis ce que le téléphone a vu :

1. **Le réseau** : dans la console de Tailscale, retirer l'appareil (*Remove*), ou le désactiver.
   Le téléphone ne joint plus le poste.
2. **La clé** : retirer sa ligne de `~/.ssh/authorized_keys` sur le poste (son commentaire la
   nomme). Même revenu sur le réseau, il n'entre plus.
3. **Le jeton de la console**, que le navigateur du téléphone a vu : un nouveau
   `EREGION_CONSOLE_TOKEN` dans `infra/glorfindel-host/host.env`, `make glorfindel-host-push`, puis
   sur H0 `cd eregion && docker compose up -d war-room` ; le cookie de session tombe avec lui (SEC10).
   **Non vérifié** comme enchaînement.
4. `make mobile-check` : une clé de moins.

## Ce qui reste ouvert

- La règle d'accès de Tailscale ne se lit pas sur le poste ; seule sa console la montre.
- Un téléphone déverrouillé, l'application ouverte et la session `tmux` reprise, est l'opérateur :
  la biométrie débloque la clé, pas chaque commande. Les gestes qui comptent font taper un nom.
- La session `tmux` vit sur le poste, sous l'utilisateur de l'opérateur, comme son terminal.
- Le Windows de l'hôte n'est pas lu par `make mobile-check` : son pare-feu, et le réseau de WSL en
  mode *mirrored*, où une écoute de WSL sur toutes les interfaces le serait aussi sur celles de
  Windows. Le contrôle des écoutes de WSL le couvre en partie.
- Le détail : le [modèle de menace, frontière 9](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste).
