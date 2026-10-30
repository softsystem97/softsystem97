# Validation du pont de remplacement — 19 octobre 2026

Branche de développement : `feature/client-technician-bridge`, issue de `fix/technician-access-diagnostics`. Aucun merge, déploiement ou changement du compte réel. La PR existante reste inchangée.

Environnement réellement utilisé : site jetable `audit.localhost`, Frappe 16.52.0, ERPNext 16.51.1, Python 3.14.8, MariaDB 11.8.6. Toutes les données et adresses de test sont synthétiques. Le module reste désactivé dans la configuration persistante du site ; les tests injectent une activation locale temporaire.

| Vérification | Résultat réel | Preuve / portée |
|---|---|---|
| Migration du nouveau DocType technique | Réussi | `bench --site audit.localhost migrate`, code 0 |
| Construction des ressources | Réussi | `bench build --app softsystem97`, code 0 |
| Tests Frappe | Réussi | 52 tests, dont 23 tests du pont et 29 régressions existantes, code 0 |
| Désactivation par défaut, compatibilité/profil/rôle explicites | Réussi | Refus et absence d’écritures testés |
| Client autorisé, client étranger, lien client ambigu | Réussi | Vrais User/Customer/Portal User et Issue du laboratoire |
| Technicien attribué, non attribué, sans rôle, candidat, invité | Réussi | Contrôles serveur et absence de droits natifs Issue globaux |
| Compte/rôle désactivé et affectation annulée | Réussi | Accès révoqué sans DocShare résiduel créé par le pont |
| Statuts, conflits de version, historique partagé | Réussi | Parcours Open → Replied → On Hold → Resolved → Closed ; transitions invalides refusées |
| Reprises et créations concurrentes | Réussi | Deux connexions DB indépendantes, rollback/reprise des conflits ; un seul Issue et une confirmation |
| E-mails applicatifs réels | Réussi | Ouverture, attribution, résolution et clôture avec répétition des requêtes : six Email Queue attendus, six reçus par SMTP local, une seule fois chacun |
| Scheduler et worker | Réussi | Traitement autonome des six messages par le job natif de vidage de file |
| Interface Chromium | Réussi | 13 scénarios : connexions Website User/System User, mot de passe, erreurs, liste/détail, texte échappé, conflit, reprise après rechargement, création client, clôture et mobile |
| Session HTTP native en laboratoire | Réussi | 14 scénarios WSGI Frappe réels : connexion Website User, cookies, route/page Jinja, CSRF, méthodes HTTP, interventions, statuts, refus et compte désactivé |
| Connexion du compte réel, SSO/2FA et session de production | Non exécuté | Aucun accès administratif/session réelle au serveur de production |
| Portail historique, profils personnalisés et workflows réels | Non exécuté | Sources et métadonnées privées indisponibles ; adaptateurs nécessaires si présents |
| Déploiement et attribution au compte réel | Non exécuté | Exigent recette, sauvegarde et autorisation explicite |

Commandes réellement exécutées depuis le bench du laboratoire :

```sh
bench --site audit.localhost migrate
bench build --app softsystem97
python /workspace/softsystem97/tools/run_local_tests.py --site audit.localhost
python /workspace/softsystem97/tools/validate_local_mail.py --site audit.localhost --bridge
python /workspace/softsystem97/tools/validate_ticket_bridge_http.py --site audit.localhost
python /workspace/softsystem97/tools/test_ticket_bridge_browser.py --screenshot /workspace/ticket-bridge-mobile.png
node --check /workspace/softsystem97/softsystem97/public/js/ticket_bridge.js
```

Journaux de l’environnement, non publiés : `ticket-bridge-migrate.log`, `ticket-bridge-build.log`, `ticket-bridge-tests.log`, `ticket-bridge-smtp.log`, `ticket-bridge-browser.log`, `ticket-bridge-http.log` dans le dossier logs du bench. Les vérifications PowerShell antérieures n’ont pas été relancées : aucun de leurs fichiers n’a changé.

Un conflit de transaction observé sur MariaDB avec isolation snapshot a été traité par une réponse HTTP 409 et des reprises conservant la clé d’idempotence ; il n’est pas masqué par un commit anticipé. Les tests simultanés vérifient la convergence après rollback. Les scénarios Chromium utilisent le navigateur système : le téléchargement du navigateur Playwright était refusé par le réseau ; cela n’a pas empêché l’exécution avec Chromium installé.

Les écritures privilégiées internes restent un point de revue explicite avant activation : elles sont bornées par l’identité active, l’affectation ou l’association client et les listes de champs autorisés. Aucun résultat local ne prouve les permissions ou le fonctionnement du portail de production.

Procédure complète de mise en service et retour arrière : [ticket-bridge-development.md](ticket-bridge-development.md).

## Corrections de la reprise finale

Le test HTTP natif a révélé des défauts que les réponses HTTP simulées ne couvraient pas :

- Le contrôleur Python avait des tirets. Le routeur Frappe recherche une version avec underscores ; le fichier est désormais `www/ss97_dev_technician.py`. La désactivation renvoie réellement 404 et la page invitée affiche réellement le formulaire de connexion.
- Le contrôleur initialise maintenant le jeton CSRF natif de la session authentifiée avant le rendu. Une mutation sans jeton est effectivement refusée après ouverture de la page ; avec le jeton natif et le cookie de session, elle réussit.
- Le JavaScript accepte `No App`, qui représente une connexion Website User réussie, ainsi que `Logged In` pour System User. Les autres réponses restent soumises au parcours natif, notamment pour SSO/2FA.

La suite HTTP utilise des comptes synthétiques jetables et un mot de passe aléatoire uniquement en mémoire pour un compte de laboratoire ; aucun mot de passe ni jeton n’est imprimé ou committé. Elle n’intercepte pas les réponses applicatives et ne désactive pas CSRF. L’activation du pont est injectée dans le contexte des requêtes de test, pas dans la configuration persistante. Les objets de test sont supprimés ensuite.

Lors de cette reprise, les 52 tests Frappe, 13 scénarios HTTP réels, 12 scénarios Chromium et la construction des ressources ont été exécutés. La preuve SMTP de six messages reçus une seule fois est conservée de la livraison précédente : le producteur n’a pas changé et aucun renvoi supplémentaire n’a été demandé. La vérification de création idempotente du rôle exact SS97 Technicien est nouvelle et s’effectue dans une transaction de laboratoire annulée après le test.

## Déconnexion — reprise ciblée

Un bouton de déconnexion manquait dans l’interface de développement. Il appelle désormais le logout natif par POST avec CSRF, efface l’affichage des tickets et revient au formulaire de connexion. Les réponses de chargement encore en vol ne repeuplent pas le tableau pendant la déconnexion.

Les validateurs ciblés ont été exécutés : **14 scénarios HTTP Frappe réels**, dont refus d’accès après logout et après réutilisation de l’ancien cookie ; **13 scénarios Chromium**, dont bouton POST et retour au formulaire. La suite de 52 tests Frappe et l’essai SMTP antérieurs n’ont pas été relancés : aucun producteur, rôle, modèle de données ou migration n’a changé. Ces nouveaux résultats restent exclusivement locaux.

Aucun résultat de collecte de production n’est disponible. Le paquet privé de collecte est distinct du dépôt public et ne contient aucun changement de compte ou déploiement automatique.

## Revue des affectations depuis GitHub

La correction détaillée dans [assignment-authorization-security-review.md](assignment-authorization-security-review.md) remplace la confiance dans un ToDo natif par une approbation administrative protégée. Résultats courants : 60 tests Frappe et 15 scénarios HTTP natifs réussis en laboratoire ; les trois failles d’affectation ont été reproduites avant correction. La vérification des anciens reçus fait partie des huit nouvelles régressions. Aucune validation du champ historique ss97_technician, des règles de paiement privées ou de la production n’est annoncée.

## Reprise des reçus après clôture

La revue suivante a identifié deux défauts d’idempotence : une affectation ou un commentaire déjà acceptés ne pouvaient plus être acquittés si la réponse avait été perdue puis le ticket clôturé avant la nouvelle tentative. Deux tests ciblés échouaient avant correction et réussissent après.

Les contrôles d’identité, de rôle et d’accès actuels restent exécutés avant toute lecture de reçu. Une requête identique déjà acceptée retrouve son résultat sans écriture ni notification supplémentaire. Une nouvelle requête de commentaire ou d’affectation reste refusée sur un ticket Closed. Une affectation révoquée reste révoquée, même si un administrateur redemande son ancien reçu ; un technicien révoqué ne peut pas relire le reçu d’intervention.

Exécution de cette reprise :

- `test_comment_retry_after_closure_keeps_receipt_and_checks_revocation` : réussi.
- `test_assignment_retry_after_closure_does_not_restore_revoked_access` : réussi.
- Validateur HTTP natif : 15 scénarios réussis sur audit.localhost.
- Les 60 tests Frappe antérieurs sont conservés ; la suite complète n’a pas été réexécutée. Deux nouveaux tests sont ajoutés au module existant et seront inclus dans son exécution complète ultérieure.

Les journaux de laboratoire sont closure-retry-before.log (deux défauts reproduits), closure-retry-after.log (deux tests réussis) et closure-retry-http.log. Cette correction ne modifie ni schéma, ni permissions, ni configuration de rôle. Aucun compte réel ni serveur de production consulté ou modifié.

## Confidentialité des destinataires après changement d’autorisation

Deux cas non couverts ont été reproduits : un utilisateur encore actif, mais lié à plusieurs Customer ou à un Customer désactivé, recevait encore les nouvelles notifications de statut. L’ancien producteur vérifiait seulement la présence d’un lien et l’activation du User. Il n’appliquait pas la politique d’accès client complète.

Le routage utilise maintenant la même résolution que l’accès au portail : User actif, rôle Customer présent et actif, lien Portal User unique et Customer actif correspondant au ticket. Aucun rapprochement approximatif par e-mail ni privilège administratif implicite. Les contrôles des techniciens et des approbations d’affectation restent inchangés.

Exécution ciblée sur audit.localhost : **cinq tests réussis**, dont quatre nouveaux (rôle client retiré, lien client ambigu, Customer désactivé, rôle Customer désactivé) et un test positif existant de la file d’e-mails. Les tests contrôlent les destinataires réels des Email Queue et les notifications applicatives ; le technicien autorisé conserve sa notification, le client révoqué n’en reçoit pas de nouvelle. Le scénario de retrait du rôle tient compte du hook ERPNext qui le réattribue depuis Contact ; les associations fictives sont préparées par les API natives. Le cache de compte sortant propre à la requête est réinitialisé entre les transactions de test pour ne pas réutiliser un compte annulé par rollback.

**15 scénarios HTTP Frappe natifs réussis** après correction. Les résultats complets antérieurs (60 tests) et les deux régressions de clôture sont conservés, sans relance complète. Les journaux sont notification-privacy-before.log (reproduction, avec un cas de fixture corrigé ensuite), notification-privacy-after.log et notification-privacy-http.log. Aucun SMTP externe ni envoi réel effectué ; les files de test restent Not Sent et les transactions sont annulées.

Cette correction ne rappelle ni ne supprime les messages déjà créés ou mis en file et ne modifie pas les notifications d’autres applications. Elle porte sur les futurs événements du pont de développement. Aucun compte réel, permission native, migration ou configuration de production modifié.

## Validation intégrée des corrections cumulées

La suite complète a ensuite été exécutée sur `audit.localhost`, avec Frappe 16.52.0 et ERPNext 16.51.1 : **66 tests réussis**, puis **15 scénarios HTTP natifs réussis**. Cette exécution intègre les huit régressions d’affectation, les deux régressions de reprise après clôture et les quatre régressions de confidentialité des destinataires ; ces résultats remplacent la réserve précédente sur l’absence de relance complète.

Commandes exécutées depuis le bench de laboratoire :

```sh
env/bin/python /workspace/softsystem97/tools/run_local_tests.py --site audit.localhost
env/bin/python /workspace/softsystem97/tools/validate_ticket_bridge_http.py --site audit.localhost
```

Preuves locales : `logs/final-portal-integration-tests.log` et `logs/final-portal-integration-http.log`. Les utilisateurs et tickets sont fictifs. La suite HTTP couvre notamment la connexion native, CSRF, la portée des tickets, le refus d’auto-affectation non approuvée et l’invalidation de session après déconnexion. Aucun envoi SMTP externe ni accès à la production n’a été effectué.

Les procédures de sauvegarde, staging, activation et retour arrière existent déjà dans [ticket-bridge-development.md](ticket-bridge-development.md). Aucun ajout applicatif n’a été nécessaire pour cette validation intégrée. L’archive historique `SOURCES_TECHNICIEN_PRIVE.zip` n’est toujours pas importée dans cet environnement : le rôle historique `SS97 Technician`, le champ `ss97_technician` et les règles privées de paiement/intervention ne sont pas validés par ces tests du pont distinct, désactivé par défaut. Aucune fusion, attribution de rôle réel ou mise en production n’est réalisée.
