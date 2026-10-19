# Tests autorisés depuis PowerShell 7

Ces scripts effectuent uniquement des GET vers les API natives confirmées dans Frappe v16. Ils ne créent aucun ticket, ne génèrent aucune clé et ne modifient aucun utilisateur ou paramètre. Les résultats affichent des statuts et des compteurs, jamais les documents, noms de tickets, identité retournée ou identifiants API.

Le portail technicien personnalisé et la définition de son profil actif ne sont pas disponibles dans le dépôt. `SS97-Test-Technicien.ps1` vérifie uniquement le mécanisme natif ToDo → ticket accessible, pas ce portail. Il conserve `CustomTechnicianProfileValidated=False` et échoue si aucun dossier attribué ne permet le contrôle. Un compte Support Team peut disposer de droits plus larges que ses attributions : seul un test de refus avec un dossier connu permet de vérifier cette limite, et il ne faut pas inventer les règles métier.

## Installation et première exécution

1. Ouvrir PowerShell **7** (`pwsh`, pas Windows PowerShell 5.1). Vérifier `$PSVersionTable.PSVersion`.
2. Conserver ensemble les scripts `.ps1` et `SS97.ReadOnly.psm1`. Lire le code avant exécution ; si Windows indique un téléchargement bloqué, examiner la provenance et utiliser les mécanismes de confiance de votre organisation. Aucun contournement global d'ExecutionPolicy n'est nécessaire ou recommandé.
3. Utiliser uniquement un site et un compte pour lesquels le propriétaire a autorisé les lectures. L'exemple ci-dessous est un domaine fictif à remplacer, pas le site de production. Une lecture peut contenir des données privées en mémoire même si seule une synthèse est affichée.
4. Ne jamais mettre une API Key ou API Secret dans les commandes, l'historique, un fichier ou ce dépôt. Les deux valeurs sont demandées par `Read-Host -AsSecureString`, à chaque test authentifié. Le header n'existe qu'en mémoire pendant la requête HTTPS et le client est ensuite fermé. Ne pas activer le traçage des variables ou un débogueur sur cette saisie.

```powershell
Set-Location <dossier-des-scripts>
.\SS97-Diagnostic-API.ps1 -BaseUri https://site-autorise.example
.\SS97-Test-API.ps1 -BaseUri https://site-autorise.example
# Issue est le DocType natif confirmé dans le laboratoire ; confirmer celui du site avant ce test.
.\SS97-Test-Tickets.ps1 -BaseUri https://site-autorise.example -TicketDocType Issue -Limit 20
.\SS97-Test-Technicien.ps1 -BaseUri https://site-autorise.example -TicketDocType Issue -Limit 20
```

Le diagnostic est anonyme : un 403 sur `get_logged_user` est un refus normal sans authentification. `ping` ne démontre ni l'authentification ni l'autorisation d'accès aux tickets. `SS97-Test-API` exige une réponse 200 contenant une identité non Guest et n'affiche pas cette identité. Les tests authentifiés sortent avec un code non nul si le contrôle échoue. Le diagnostic affiche les codes HTTP ; un code 0 indique une erreur réseau ou une réponse inexploitable.

Le nombre de tickets affiché est limité à la page demandée ; ce n'est pas un total complet. Zéro ticket accessible n'établit pas que le parcours métier fonctionne. Les listes utilisent `/api/resource/<DocType>` avec les permissions natives ; aucune méthode `get_all` ni requête SQL n'est exposée.

### Vérifier un refus attendu

L'administrateur doit préparer en préproduction un vrai ticket témoin existant qui ne doit pas être visible au compte testé. Utiliser son **nom interne**, pas une référence publique personnalisée supposée équivalente :

```powershell
.\SS97-Test-Technicien.ps1 -BaseUri https://site-autorise.example -TicketDocType Issue `
  -ExpectedDeniedTicketName '<nom-interne-du-ticket-temoin>'
```

Le script constate que ce nom n'est pas retourné, ou que le serveur répond 401/403 ; il n'affiche aucune référence. Une réponse vide peut également signifier que le document n'existe pas : confirmer son existence indépendamment avec l'administrateur, sans élargir les droits du technicien. Cette vérification ne couvre pas le statut actif du profil personnalisé, le suivi client, les changements de statut ni toute l'isolation multi-entreprises.

### Interpréter les erreurs

- 401/403 : vérifier identité, compte activé, rôles, permissions DocType, User Permissions et partages ; ne pas rendre l'API publique ou attribuer System Manager pour faire passer le test.
- 404 : vérifier le nom de DocType et la version des routes natives. Les noms d'API personnalisées restent à confirmer.
- 3xx : les redirections ne sont pas suivies ; confirmer l'origine HTTPS exacte pour ne pas envoyer les identifiants à une autre destination.
- 429 : attendre selon la politique du site ; aucun retry automatique ni augmentation de charge.
- 5xx/0 : faire examiner TLS/DNS/proxy et les journaux expurgés par l'exploitant. Aucun certificat n'est ignoré, aucun message privé d'erreur serveur n'est affiché.

## API Access et Generate Keys : procédure administrateur

Sur Frappe v16 inspecté, `frappe.core.doctype.user.user.generate_keys` exige **System Manager**. `api_key`, `api_secret` et `generate_keys` sont au **permlevel 1** de User. L'accès à sa propre fiche ne suffit pas si la session n'a pas ces permissions.

1. Un administrateur déjà autorisé ouvre le document User du compte concerné depuis Desk, avec une session System Manager. Vérifier que le compte est activé ; ne jamais modifier ou attribuer un rôle sans approbation du propriétaire.
2. Contrôler User dans Role Permission Manager, en particulier lecture/écriture au permlevel 1 et les éventuels Custom DocPerm. Examiner les Client Scripts User et les Property Setters `hidden`, `depends_on`, `permlevel` ou `read_only` des champs et de `api_access`. Aucun masquage de ces champs n'a été trouvé dans le code de l'application ; les personnalisations stockées dans la base restent inconnues. Ne pas réinitialiser toutes les permissions.
3. Si la section apparaît après ces vérifications, le propriétaire utilise Generate Keys dans l'interface autorisée. Une API Key existante est conservée, mais le Secret est renouvelé et les anciens clients utilisant celui-ci cessent de fonctionner : planifier la rotation avant de cliquer. Ne pas montrer ni transmettre les valeurs à un tiers.
4. Préférer un compte technique activé et nominativement géré, avec le seul rôle d'intégration nécessaire, ses User Permissions et un périmètre d'entreprise validé. System Manager est nécessaire à l'opérateur qui génère les identifiants, pas à tous les comptes qui les utilisent. Les droits Bridge minimaux doivent être approuvés explicitement ; le patch ne crée pas de rôle de production.
5. Le propriétaire teste la nouvelle paire avec `SS97-Test-API.ps1`, puis teste les ressources autorisées et les refus attendus en préproduction. Le script ne stocke aucun identifiant et n'extrait aucun secret existant.
6. Si les contrôles sont corrects mais la section reste invisible : demander au support de confirmer les versions exactes, la matrice User permlevel 1, les personnalisations et restrictions du tenant/plan. Les API REST natives existent dans le framework inspecté ; cela **ne démontre pas** leur disponibilité contractuelle sur le plan Frappe Cloud du site. La réponse du support ou un test autorisé est nécessaire. Aucune clé réelle n'a été générée par ces travaux.

## Découverte et export privé du code Windows

```powershell
.\SS97-Find-TechnicianSources.ps1 -Root 'C:\soft-system-97'
```

La découverte est en lecture seule. Elle retourne uniquement des chemins relatifs, sans lignes ni valeurs de code. Elle ignore les jonctions/liens, `.env*`, `sites`, fichiers privés, sauvegardes, caches et noms contenant secret/password/token/credential, ainsi que les extensions non autorisées. Les fichiers de plus de 2 Mio sont ignorés : l'absence dans la liste n'est donc pas une preuve exhaustive d'absence. Aucun fichier n'est automatiquement copié, zippé ou envoyé.

Rechercher en priorité les fichiers réels nommés `client_ticket_api.py`, `ticket_workspace.py`, `ticket_types.py`. Leurs sous-dossiers exacts sont inconnus : ne pas inventer un chemin. Identifier aussi les handlers de la page technicien, les fonctions qui émettent les deux messages de refus, les liens User/profil actif/entreprise et les fonctions de création/attribution/statut/suivi client.

Le propriétaire examine localement les candidats avant export : un fichier de code peut contenir un identifiant intégré malgré un nom banal, ce qu'un filtre de chemin ne peut garantir. Créer une copie expurgée des seuls fichiers utiles dans un dossier **privé hors dépôt public**, en conservant leurs chemins relatifs ; joindre les métadonnées anonymisées des DocTypes, Assignment Rules, Workflow, Web Form et Server Scripts concernés. Ne jamais copier `.env`, `site_config.json`, bases, sauvegardes, dossiers privés, clés ou données de comptes. Importer cette sélection via une pièce jointe privée autorisée ou un dépôt privé autorisé, jamais par une PR dans ce dépôt public. Conserver les originaux et comparer les fichiers avant intégration.

## Tests de ces outils

```powershell
pwsh -NoLogo -NoProfile -File .\tests\Test-SS97Scripts.ps1
```

Les tests utilisent un HttpMessageHandler hors ligne et des répertoires temporaires. Aucun identifiant, même fictif, n'est créé ou demandé ; la saisie est neutralisée uniquement dans ce processus de test et aucun appel réseau n'a lieu. Ils vérifient les contrats de réponse, les erreurs, le filtrage et les sorties. Ils ne prouvent pas une authentification par une vraie paire API ni la confiance TLS de Windows. L'exécution a été validée sur PowerShell 7 sous Linux ; le poste Windows et le site choisi restent à tester par leur propriétaire.

Le guide `docs/deployment-review.md` décrit les garde-fous de préproduction, sauvegarde, approbation, déploiement Frappe Cloud et retour arrière. Rien ici n'autorise un déploiement ou une modification de production.
