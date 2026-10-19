# Validation du pont de remplacement — 19 octobre 2026

Branche de développement : `feature/client-technician-bridge`, issue de `fix/technician-access-diagnostics`. Aucun merge, déploiement ou changement du compte réel. La PR existante reste inchangée.

Environnement réellement utilisé : site jetable `audit.localhost`, Frappe 16.52.0, ERPNext 16.51.1, Python 3.14.8, MariaDB 11.8.6. Toutes les données et adresses de test sont synthétiques. Le module reste désactivé dans la configuration persistante du site ; les tests injectent une activation locale temporaire.

| Vérification | Résultat réel | Preuve / portée |
|---|---|---|
| Migration du nouveau DocType technique | Réussi | `bench --site audit.localhost migrate`, code 0 |
| Construction des ressources | Réussi | `bench build --app softsystem97`, code 0 |
| Tests Frappe | Réussi | 51 tests, dont 22 nouveaux tests du pont et 29 régressions existantes, code 0 |
| Désactivation par défaut, compatibilité/profil/rôle explicites | Réussi | Refus et absence d’écritures testés |
| Client autorisé, client étranger, lien client ambigu | Réussi | Vrais User/Customer/Portal User et Issue du laboratoire |
| Technicien attribué, non attribué, sans rôle, candidat, invité | Réussi | Contrôles serveur et absence de droits natifs Issue globaux |
| Compte/rôle désactivé et affectation annulée | Réussi | Accès révoqué sans DocShare résiduel créé par le pont |
| Statuts, conflits de version, historique partagé | Réussi | Parcours Open → Replied → On Hold → Resolved → Closed ; transitions invalides refusées |
| Reprises et créations concurrentes | Réussi | Deux connexions DB indépendantes, rollback/reprise des conflits ; un seul Issue et une confirmation |
| E-mails applicatifs réels | Réussi | Ouverture, attribution, résolution et clôture avec répétition des requêtes : six Email Queue attendus, six reçus par SMTP local, une seule fois chacun |
| Scheduler et worker | Réussi | Traitement autonome des six messages par le job natif de vidage de file |
| Interface Chromium | Réussi | 10 scénarios : mot de passe, erreurs, liste/détail, texte échappé, conflit, reprise après rechargement, création client, clôture et mobile |
| Connexion native du compte réel, SSO/2FA et session de production | Non exécuté | Aucun accès administratif/session réelle ; les réponses HTTP du test navigateur sont contrôlées |
| Portail historique, profils personnalisés et workflows réels | Non exécuté | Sources et métadonnées privées indisponibles ; adaptateurs nécessaires si présents |
| Déploiement et attribution au compte réel | Non exécuté | Exigent recette, sauvegarde et autorisation explicite |

Commandes réellement exécutées depuis le bench du laboratoire :

```sh
bench --site audit.localhost migrate
bench build --app softsystem97
python /workspace/softsystem97/tools/run_local_tests.py --site audit.localhost
python /workspace/softsystem97/tools/validate_local_mail.py --site audit.localhost --bridge
python /workspace/softsystem97/tools/test_ticket_bridge_browser.py --screenshot /workspace/ticket-bridge-mobile.png
node --check /workspace/softsystem97/softsystem97/public/js/ticket_bridge.js
```

Journaux de l’environnement, non publiés : `ticket-bridge-migrate.log`, `ticket-bridge-build.log`, `ticket-bridge-tests.log`, `ticket-bridge-smtp.log`, `ticket-bridge-browser.log` dans le dossier logs du bench. Les vérifications PowerShell antérieures n’ont pas été relancées : aucun de leurs fichiers n’a changé.

Un conflit de transaction observé sur MariaDB avec isolation snapshot a été traité par une réponse HTTP 409 et des reprises conservant la clé d’idempotence ; il n’est pas masqué par un commit anticipé. Les tests simultanés vérifient la convergence après rollback. Les scénarios Chromium utilisent le navigateur système : le téléchargement du navigateur Playwright était refusé par le réseau ; cela n’a pas empêché l’exécution avec Chromium installé.

Les écritures privilégiées internes restent un point de revue explicite avant activation : elles sont bornées par l’identité active, l’affectation ou l’association client et les listes de champs autorisés. Aucun résultat local ne prouve les permissions ou le fonctionnement du portail de production.

Procédure complète de mise en service et retour arrière : [ticket-bridge-development.md](ticket-bridge-development.md).
