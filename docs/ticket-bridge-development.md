# Pont client–technicien de remplacement (développement)

Ce module est une reconstruction autorisée, pas la récupération du portail privé et pas une réparation de production. Il est **désactivé par défaut** : aucun hook, patch ou migration ne l’active, ne crée de rôle ni ne modifie un utilisateur. La migration ajoute le journal technique `SS97 Ticket Bridge Event` ; la correction de sécurité y ajoute `assignment`, `technician` et `revoked`, sans approbation automatique des anciennes affectations.

## Sources confirmées et choix du modèle

La recherche précédente a couvert les six branches distantes, les trois références de PR, les noms historiques avec renommages, les autres dossiers accessibles et les archives locales de code. Aucun des trois modules historiques ni aucune interface de `/espace-technicien/tickets` n’a été retrouvé. Le dossier Windows n’est pas monté dans l’environnement cloud Linux ; il n’a pas été inspecté.

Le correctif public `softsystem97/patches/fix_ticket_libre_submission.py` existe sur `fix/softsystem97-production-bugs`, mais pas sur cette branche. Il référence `ss97-ouvrir-ticket`, les Server Scripts `SS97 Issue After Insert Number Token`, `SS97 AI Agent Reception After Insert` et l’API `ss97_ticket_brevo_flush`. Leurs définitions complètes ne sont pas disponibles. Ce correctif n’est pas fusionné par cette reconstruction.

Modèles réellement utilisés :

- `Issue` ERPNext : identifiant natif conservé, `customer`, `raised_by`, `subject`, `description`, `status`, `modified` et validations natives.
- `Customer.portal_users` / `Portal User` : association explicite et unique du compte client ; aucun rapprochement approximatif par e-mail.
- `User.enabled` et `Role.disabled` : état actif contrôlé à chaque requête.
- `ToDo` : affectation native ouverte, `allocated_to`, `reference_type=Issue`, `reference_name`. Le cycle natif met à jour `_assign` et l’historique d’affectation.
- `Comment` : interventions partagées, texte échappé ; les commentaires privés historiques ne sont pas exposés par le pont.
- `SS97 Client Notification` existant et `Email Queue` natif : production de nouveaux événements seulement.
- Nouveau `SS97 Ticket Bridge Event` : reçu d’idempotence et historique partagé, **pas un second modèle de tickets**. Lecture native réservée à System Manager.

## Sécurité et périmètre

Les API ne sont jamais accessibles à Guest. Les lectures sont GET et les mutations POST, avec session et contrôle CSRF natifs Frappe. La page est sans cache. Aucun utilisateur, mot de passe, rôle attribué ou droit global Issue n’est créé par une requête du portail.

Le rôle historique reste inconnu. Pour le **nouveau module**, le rôle exact doit être explicitement configuré après revue ; `SS97 Technicien` est la proposition préparée. `Candidat SS97`, `System Manager`, `Guest`, `All`, `Administrator` et `Customer` sont refusés comme rôle technicien du pont. Le rôle choisi doit exister et être actif. Un profil technicien inconnu n’est jamais supposé actif : un profil requis impose un adaptateur ; l’absence de profil doit être explicitement confirmée.

Autorisations serveur :

| Acteur | Capacité |
|---|---|
| Client actif avec rôle Customer et lien Portal User unique | Créer et lire ses propres Issue, commenter ses tickets non clôturés |
| Technicien actif avec rôle configuré, ToDo ouvert et approbation administrative liée à ce ToDo/ticket/utilisateur | Lire ce ticket, publier une intervention partagée, appliquer une transition autorisée |
| Administrateur existant System Manager | Affecter à un technicien actif, sous réserve des permissions natives d’écriture Issue |
| Invité, compte désactivé, rôle absent/désactivé, technicien non attribué | Refus |

Le service effectue des lectures filtrées et des écritures privilégiées **strictement après** les contrôles ci-dessus. Les `insert/save(ignore_permissions=True)` sont des capacités internes bornées à des champs et destinataires calculés côté serveur ; elles ne confèrent pas de permissions natives au compte. Les validations et événements natifs restent exécutés. Il n’y a ni changement d’identité, ni droit Issue global, ni DocShare persistant. Les comptes portant déjà des rôles larges ou des partages hérités doivent faire l’objet d’une revue séparée : ce module ne réduit pas leurs droits natifs préexistants.

Statuts du remplacement : Open → Replied / On Hold / Resolved ; Replied → On Hold / Resolved ; On Hold → Replied / Resolved ; Resolved → Closed. Closed est terminal. La fermeture conserve le ToDo ouvert comme trace d’autorisation afin que l’intervenant puisse encore lire la clôture ; fermer/annuler ce ToDo révoque durablement son approbation ; le déplacer ou le supprimer la révoque aussi. Le rouvrir ou restaurer son ancien lien ne rétablit pas cet accès. Le hook conserve cette révocation même quand le pont est désactivé. L’API d’affectation est additive, pas une opération de remplacement d’un intervenant. Une réaffectation avec révocation demande de fermer/annuler explicitement l’ancien ToDo depuis l’administration.

Le pont refuse un Workflow Issue actif, des Server Scripts DocType Event Issue actifs, un schéma de statuts différent ou, si ses e-mails sont activés, des Notifications e-mail Issue déjà actives. Ces cas demandent une adaptation revue, pas une désactivation aveugle des workflows existants.

Chaque mutation exige `request_id`. Le reçu est unique par acteur/clé, vérifie le contenu et reste dans la même transaction que le ticket, les notifications et la file d’e-mails. Une requête concurrente peut recevoir HTTP 409 : après rollback de la transaction HTTP, réessayer avec la même clé retrouve le résultat sans doublon. Le navigateur conserve la clé après une erreur réseau et un rechargement, dans sessionStorage : seulement un hash du contenu et une clé opaque, jamais les champs du formulaire, le mot de passe ou un jeton de session. Les statuts exigent aussi `expected_modified` et verrouillent l’Issue ; un conflit impose de recharger. Les appels depuis une console doivent aussi laisser remonter les erreurs ou effectuer un rollback avant de poursuivre, jamais capturer une exception puis committer partiellement.

## Routes et API

La route **`/ss97-dev-technician`** est séparée de la route de production et renvoie une page indisponible tant que le module est désactivé. La connexion utilise l’API de session native Frappe, sans stockage de clés. Le mot de passe est masqué par défaut, affichable temporairement, remasqué après dix secondes ou perte de focus. Les valeurs saisies ne vont jamais dans une URL ni dans un journal. Le lien vers la connexion Frappe reste disponible pour SSO/2FA ; ces parcours n’ont pas été validés sur le serveur réel.

Préfixe API : `softsystem97.integrations.ticket_bridge.api`.

| Méthode | Fonction | Paramètres utiles |
|---|---|---|
| GET | session_info | audience=technician ou client |
| GET | list_tickets | audience, offset ; pages de 50 |
| GET | get_ticket | name interne Issue, audience ; 200 derniers événements partagés |
| GET | get_notifications | audience, offset ; destinataire et ticket revérifiés |
| POST | create_ticket | subject, description, request_id ; client dérivé de la session |
| POST | assign_ticket | name, technician, request_id ; administration seulement |
| POST | update_status | name, status, expected_modified, request_id |
| POST | add_intervention | name, content, request_id, audience |

Le nom interne Issue est toujours utilisé ; aucune référence publique `SS97-TKT-*` n’est interprétée comme un identifiant interne sans adaptateur validé. Aucun ticket historique n’est renommé ni réimporté. Un ticket client historique sans `customer` fiable et `raised_by` correspondant reste inaccessible au client via ce module, jusqu’à une réconciliation administrative revue.

## Préparation idempotente, sans attribution

Dans une console **de staging**, ouverte par un administrateur autorisé :

```python
from softsystem97.integrations.ticket_bridge.install import prepare
prepare()  # simulation uniquement
# Après validation du rôle et autorisation de la création en staging :
prepare(dry_run=False, compatibility_confirmed=True, role_name="SS97 Technicien")
```

Ce helper réutilise la préparation existante, préserve les rôles déjà présents, inventorie leurs éventuels droits Issue et n’ajoute aucun DocPerm ni Has Role. Les permissions minimales du nouveau rôle sur Issue sont **aucun accès natif global** : les fonctions bornées du pont assurent la délégation. Le helper n’active pas le site et ne committe pas à la place de l’opérateur.

Pour le compte existant, l’administrateur doit ouvrir sa fiche User, vérifier l’identifiant exact, `Enabled`, les rôles actuels et tout profil personnalisé, puis ajouter **uniquement le rôle technicien validé**, enregistrer et faire reconnecter l’utilisateur. Ne pas créer un autre User, cliquer sur réinitialisation du mot de passe, générer des clés ou attribuer System Manager. Une correction du nom de famille doit être validée séparément ; elle n’est pas nécessaire au contrôle d’accès.

## Activation uniquement après recette de staging

1. Sauvegarder base et fichiers publics/privés ; noter les versions, les branches, les règles de notification et les permissions à restaurer. Aucun export client ni secret dans Git.
2. Installer la branche sur une copie de staging avec données synthétiques ; exécuter `bench --site <staging> migrate`, puis `bench build --app softsystem97`, vider le cache et redémarrer selon la plateforme.
3. Revoir le schéma réel Issue, les liens client, les rôles, les profils, les scripts et les producteurs existants. Adapter les modèles non pris en charge avant toute activation. Ne pas utiliser le paramètre de confirmation pour ignorer cette revue.
4. Préparer le rôle et une matrice client/technicien/administrateur. Vérifier qu’aucun rôle ou partage hérité ne donne un accès transversal. Ne pas modifier le compte réel à ce stade.
5. Configurer explicitement sur **staging** (interface de configuration privée, jamais committée) :

```json
{
  "ss97_ticket_bridge": {
    "enabled": true,
    "compatibility_confirmed": true,
    "technician_role": "SS97 Technicien",
    "profile_required": false,
    "email_enabled": false
  }
}
```

`profile_required=false` signifie que la revue a confirmé qu’aucun modèle de profil supplémentaire n’est nécessaire. Pour tester les e-mails, utiliser un compte sortant de test contrôlé, définir `email_enabled=true` et `email_account` à son nom exact. Aucun compte implicite n’est accepté. La production conserve le module désactivé.

6. Recetter création → affectation → connexion → lecture → intervention → résolution → clôture, puis vérifier le refus d’un autre client/technicien, les comptes/rôles inactifs et la révocation d’affectation. Vérifier les versions mobiles et les erreurs 401/403/409.
7. Vérifier Email Queue, Send After, compte sortant, scheduler, worker et réception réelle avec des destinataires contrôlés. Le pont n’appelle jamais flush, Send Now ou une purge ; les anciens e-mails restent intacts. Les reprises de requête n’ajoutent pas de messages, mais une livraison SMTP reste soumise aux garanties habituelles du transport.
8. Obtenir l’autorisation explicite avant tout déploiement ou attribution au compte réel. L’intégration de la route historique demande une décision de migration et une vérification des collisions ; cette branche ne la remplace pas automatiquement.

Retour arrière : désactiver `ss97_ticket_bridge.enabled`, vider le cache, rétablir les rôles/permissions/configurations revus si nécessaire, puis revenir à la branche applicative validée selon la plateforme. Ne pas supprimer les Issue historiques ni purger les reçus d’idempotence : supprimer ces reçus rendrait une ancienne clé réutilisable. Restaurer une sauvegarde seulement selon une procédure administrative validée tenant compte des écritures intervenues depuis.

## Vérification reproductible

Depuis un bench Frappe v16 isolé dont le site commence par `audit.` ou `test_` et `allow_tests=true` :

```sh
python /chemin/softsystem97/tools/run_local_tests.py --site audit.localhost
python /chemin/softsystem97/tools/validate_local_mail.py --site audit.localhost --bridge
python /chemin/softsystem97/tools/test_ticket_bridge_browser.py --chromium /usr/bin/chromium
python /chemin/softsystem97/tools/validate_ticket_bridge_http.py --site audit.localhost
node --check /chemin/softsystem97/softsystem97/public/js/ticket_bridge.js
```

L’essai SMTP nécessite `aiosmtpd==1.4.6`, une file en attente vide, aucun compte sortant existant, un SMTP local sur loopback et les processus locaux de scheduler/worker. Il crée puis supprime ses données `.invalid` et restaure sa configuration. Ne pas le lancer en parallèle avec les tests DB. Le test navigateur nécessite `playwright==1.58.0` et Chromium ; il utilise du HTML et du JavaScript réels avec des réponses HTTP contrôlées. Il ne remplace pas un test de session sur le site Frappe ni une recette de production.

Les tests de cette branche couvrent aussi les permissions corrigées précédemment. Les résultats effectifs et limites sont consignés dans `ticket-bridge-validation.md`.

Le validateur HTTP utilise le vrai point d’entrée WSGI de Frappe, les vrais cookies de session, le routage/Jinja et les contrôles CSRF/méthodes HTTP natifs. Il reste limité au site jetable ; il ne démarre pas de serveur public et ne contacte pas la production. Il faut le lancer séparément des autres essais DB/SMTP. Le contrôleur de la route à tirets doit s’appeler `www/ss97_dev_technician.py`, conformément à la résolution native Frappe. Après correction ou installation, vider le cache du site pour retirer les anciennes pages rendues.

La déconnexion de l’interface utilise `/api/method/logout` par POST avec le jeton CSRF natif. Le tableau est vidé pendant l’opération et le navigateur revient à la page de connexion après succès. Le validateur HTTP contrôle aussi le refus d’accès après déconnexion et après réutilisation de l’ancien cookie ; ces essais concernent uniquement un utilisateur synthétique du site jetable.

## Affectations : exigence de sécurité supplémentaire

Un ToDo natif seul ne suffit jamais à autoriser l’accès : les permissions natives All/create et assignee/write permettent de le créer ou de modifier son ticket. Le service exige désormais une approbation protégée dans SS97 Ticket Bridge Event, créée par l’API d’affectation administrative et liée à l’ID exact du ToDo, au ticket et au technicien. Les listes, détails, mutations et destinataires des notifications utilisent cette même condition. Le hook ToDo peut seulement révoquer une approbation, jamais en créer une ; il ne change pas les permissions ou le fonctionnement des ToDo ordinaires.

Avant activation d’une ancienne installation : migrer, vider le cache, faire revoir chaque affectation nécessaire par un administrateur et appeler `assign_ticket` avec une **nouvelle clé de requête**. Un simple ToDo créé depuis Desk, ou un reçu antérieur sans les nouveaux champs, ne suffit plus. Aucune reprise automatique n’est sûre. L’API refuse l’attribution de tickets Closed ; les accès à ces historiques demandent une revue administrative avant activation, pas un contournement du contrôle. Les anciens clients qui réutilisent une clé d’attribution déjà consommée retrouvent le reçu historique, sans nouvelle autorisation implicite.

Retour arrière de cette correction : garder le pont désactivé. Ne pas réactiver une ancienne version qui faisait confiance aux ToDo seuls. Conserver les tickets et les reçus ; restaurer du code ou une base uniquement après revue des écritures postérieures et approbation.

Après clôture, une nouvelle affectation ou un nouveau commentaire reste interdit. La répétition exacte d’une requête déjà acceptée peut néanmoins retrouver son reçu, après vérification des autorisations actuelles. Un tel acquittement ne crée ni affectation, ni commentaire, ni notification et ne réactive pas une approbation révoquée. La nouvelle tentative doit conserver la même clé et le même contenu.

Pour intégrer cette correction d’idempotence : sauvegarde et restauration contrôlée en staging, vérification de la migration d’approbations déjà requise, recette des accès/permissions et des nouvelles tentatives après clôture, puis approbation séparée avant production. Aucun nouveau changement de schéma ou de rôle n’est ajouté par cette correction. Retour arrière : désactiver le pont, vider le cache, revenir à une version approuvée qui conserve la protection des affectations (au minimum la correction 7b85288), puis recetter avant toute réactivation. Ne pas supprimer de tickets ou de reçus.
