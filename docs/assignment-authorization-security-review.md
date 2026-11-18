# Isolation des tickets : approbations d’affectation protégées

## Défaut et correction

La branche du pont utilisait un ToDo Open comme autorisation. Or le ToDo natif Frappe v16 autorise la création pour All et la modification par l’assignee. Le champ assigned_by est éditable : sa valeur ne prouve pas une décision administrative.

Trois régressions ont reproduit le défaut sur le site jetable avant correction :

1. Un technicien créait un ToDo à son nom pour un Issue non autorisé et pouvait le lire.
2. Un ToDo approuvé pouvait être déplacé vers un autre Issue, transférant indûment l’accès.
3. Un technicien créant son propre ToDo recevait une notification de statut non autorisée.

Les trois tests échouaient avant correction. Ils réussissent après correction.

Le serveur exige maintenant une approbation administrative liée à l’ID du ToDo, à l’Issue et au technicien dans SS97 Ticket Bridge Event, dont les permissions natives sont réservées à System Manager. Le rôle administrateur n’est jamais ajouté à un technicien. Aucun droit global Issue ou nouveau DocShare n’est créé.

Un utilisateur peut continuer à créer ou modifier ses ToDo selon les règles natives ; ces actions ne créent aucune approbation du pont. Fermer, annuler, déplacer ou supprimer un ToDo révoque ses approbations. La réouverture et le rétablissement de l’ancien lien ne les réactivent pas. Le hook est limité à la révocation des approbations déjà liées à ce ToDo, y compris lorsque le pont est désactivé. Une réautorisation administrative explicite reste possible et ne duplique pas les notifications d’une approbation toujours active.

`assignment` conserve l’identifiant approuvé comme Data indexé : une suppression native de ToDo reste possible sans perdre le reçu de révocation. `technician` est un Link User ; `revoked` est un Check. Ces champs ne sont pas renseignés automatiquement pour les anciennes affectations. Les API refusent de fonctionner avec un schéma d’approbation non migré.

## Sources et branches réellement examinées

| Branche / composant | Résultat |
|---|---|
| main, bc6995b | Bridge général, Stripe, customer/contracts/finance/notifications ; pas du portail historique |
| fix/ss97-audit-v16-20261019, 2df98ad | Permissions bridge/notifications et tests antérieurs ; correspond à la référence de la PR existante |
| fix/technician-access-diagnostics, ac64d73 | Diagnostics en lecture seule et préparation idempotente du rôle |
| feature/client-technician-bridge, 1c392ea | API/policy/install du pont, route de développement, JavaScript et validateurs réutilisés |
| fix/softsystem97-production-bugs, 8dd9a01 | Correctif Ticket libre, distinct du portail technicien |

Les fichiers existants concernés par le périmètre sont `hooks.py`, `diagnostics.py`, `provisioning.py`, `integrations/bridge/api.py`, `integrations/ticket_bridge/{api,policy,install}.py`, `portal/{customer,contracts,finance,notifications}.py`, `integrations/stripe/webhook.py`, les DocTypes Bridge Request/Client Notification/Ticket Bridge Event, les pages `www/ss97*`, `public/js/ticket_bridge.js` et leurs tests/validateurs. Le code finance/contrats/Stripe n’est pas déclaré entièrement audité par cette correction ciblée.

## Vérification effective

- Suite Frappe : 60 tests réussis sur audit.localhost, dont huit régressions supplémentaires concernant les affectations, la révocation et les anciens reçus.
- HTTP natif : 15 scénarios réussis, dont création réelle d’un ToDo via frappe.client.insert suivie du refus de lecture du ticket non approuvé. Connexion, cookie, CSRF, mutations, refus étrangers et logout également vérifiés.
- Migration native Frappe : réussie en laboratoire, nouveaux champs et index installés.
- Aucun test SMTP supplémentaire : la file réelle et ses destinataires sont couverts par la suite Frappe ; le transport SMTP n’a pas changé. Aucune recette de production annoncée.

Commandes exécutées depuis le bench isolé :

```sh
bench --site audit.localhost migrate
python /workspace/softsystem97/tools/run_local_tests.py --site audit.localhost
python /workspace/softsystem97/tools/validate_ticket_bridge_http.py --site audit.localhost
```

Les journaux privés sont conservés sous logs/assignment-security-before.log (trois échecs reproduits), assignment-security-suite.log, assignment-security-http.log et assignment-security-migrate.log. Les scénarios avant correction ne sont pas des échecs restant dans le code final.

## Intégration et limites

Migrer et vider le cache sur staging avant de réautoriser les affectations contrôlées avec une nouvelle clé de requête. Ne pas créer une permission globale ni reprendre aveuglément les ToDo existants. Le pont reste désactivé par défaut. Les comptes synthétiques sont supprimés après les tests.

Les sources Windows restent une dépendance pour le **portail historique**, son champ ss97_technician et ses règles de paiement/intervention. Le rôle canonique SS97 Technician est une information fournie par l’utilisateur, pas une politique historique lue dans ces sources. Cette correction utilise la politique de rôle configurée du pont disponible et ne remplace pas automatiquement la route de production. Aucun compte réel, mot de passe, rôle attribué, donnée commerciale ou serveur de production modifié. Ni main ni la PR existante ne sont fusionnées ou réécrites.
