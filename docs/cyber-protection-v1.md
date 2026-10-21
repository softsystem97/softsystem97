# Soft System 97 Cyber Protection V1

Version de développement, Frappe 16.52.0 / ERPNext 16.51.1. Branche `feature/cyber-protection-v1`, basée sur `faaa188`. La phase 1 demeure distincte et non validée en production. Aucune dépendance Wazuh/EDR/agent/prise de contrôle n’est installée.

## Architecture et utilisation

Module Frappe **Cyber Protection**, déclaré dans `modules.txt`, stockage standard dans `softsystem97/cyber_protection/doctype/`. Contrôleurs natifs légers réutilisant `softsystem97/cyber/model.py` ; permissions communes dans `permissions.py`, API dans `api.py`, préparation administrative dans `install.py`. Le lien Customer est une référence ERPNext existante, pas une nouvelle base clients.

| DocType | Usage |
|---|---|
| SS97 Cyber Company | Extension unique par Customer ; contrat ERPNext Customer, responsable, statut/référence d’autorisation et habilitations nominatives |
| SS97 Cyber Member | Enfant Company ; technicien habilité ou contact sécurité ; ce contact seul ne donne pas d’accès |
| SS97 Cyber Asset | Ordinateur/serveur/réseau/autre, OS, maintenance, état de vérification de sauvegarde |
| SS97 Cyber Audit | Questionnaire et constats ; date d’achèvement calculée par le serveur |
| SS97 Cyber Check | Enfant Audit ; question, résultat, constat |
| SS97 Cyber Risk | Constat lié à l’audit/équipement, gravité, recommandation déterministe selon gravité, action corrective et suivi |
| SS97 Cyber Incident | Qualification, technicien habilité, cycle de résolution, liens facultatifs équipement et Issue natif |
| SS97 Cyber Event | Journal append-only applicatif : acteur, opération, référence et noms des champs modifiés, jamais le contenu des constats |

Interface de gestion : formulaires/listes Desk natifs, via recherche du nom du DocType ou `/app/ss97-cyber-company`, `/app/ss97-cyber-asset`, `/app/ss97-cyber-audit`, `/app/ss97-cyber-risk`, `/app/ss97-cyber-incident`. Tableau de bord authentifié `/ss97-cyber` : saisir la référence Customer. Le tableau affiche équipements, audits terminés, risques non résolus, incidents critiques non résolus, actions requises non résolues et répartition des vérifications de sauvegarde. Le nom de l’entreprise vient du Customer ERPNext ; aucune recherche d’entreprise globale n’est accordée au client.

Les questionnaires sont saisis dans le formulaire Audit ; les risques sont enregistrés séparément, avec recommandation automatique selon la gravité. Pas d’analyse automatique d’un poste ni de certification d’audit. Une sauvegarde `Verified` exige date passée et référence de preuve ; son contenu n’est pas vérifié par un fournisseur externe. `Unknown` reste inconnu. Un consentement saisi est une référence administrative, pas une autorisation technique de démarrer une session distante.

## Rôles et frontières serveur

- `SS97 Cyber Direction`, `SS97 Cyber Manager` : gestion globale Cyber, habilitations d’entreprise et affectation des incidents. Aucun droit général System Manager ni droit ERPNext financier ajouté.
- `SS97 Cyber Technician` : lecture des entreprises auxquelles il est explicitement habilité ; création/édition d’équipements, audits, risques ; création d’incidents et traitement uniquement des incidents qui lui sont affectés. Il ne peut pas s’habiliter ou affecter un incident.
- `SS97 Cyber Client` + rôle ERPNext `Customer` actif + association `Customer.portal_users` unique : lecture uniquement de son entreprise. Le cumul client/technicien ne remplace pas l’habilitation explicite requise pour écrire.
- Aucun rôle attribué à un utilisateur réel. Les rôles n’impliquent pas l’appartenance à une entreprise. Comptes/rôles désactivés et retrait d’habilitation refusent les accès suivants.

Hooks `permission_query_conditions` ET `has_permission` pour les six DocTypes principaux : listes, documents REST/Desk et dashboard filtrés côté serveur. Validation des liens Customer sur contrat, équipement, audit et Issue. Customer immuable après création. Les accès clients réutilisent uniquement la fonction stricte de résolution déjà disponible dans la phase 1, sans activer le pont. Aucun droit supplémentaire sur Issue et aucun paiement supposé : le lien incident–Issue ne démarre pas une intervention payante.

Écritures HTTP Cyber : session native et CSRF requis, méthodes POST/PUT/PATCH ; API de mutation POST. Les endpoints Cyber n’activent pas l’authentification machine pour les futurs fournisseurs. Les jetons futurs ne sont pas gérés ici. Un client ne peut pas écrire via l’API native. Les événements refusent création manuelle, édition et suppression ; les documents Cyber ne sont pas supprimables en V1. La rétention/export légal et un éventuel archivage administratif restent à définir avant production. Ce journal applicatif ne remplace pas une preuve externe résistante à un administrateur de base de données.

Incidents : Open → Investigating → Contained ou Resolved → Closed ; retour Contained/Resolved vers Investigating autorisé, Closed terminal. Résolution obligatoire avant Resolved/Closed. L’affectation exige un compte technicien actif, le rôle et l’habilitation exacte à l’entreprise. Les API vérifient la révision `expected_modified` ; une requête périmée est refusée par Frappe. La soumission de création n’est pas un endpoint d’ingestion idempotent : ne pas retenter à l’aveugle après une réponse réseau incertaine.

## API disponible

Préfixe `/api/method/softsystem97.cyber.api.` :

| Méthode | HTTP | Contrat |
|---|---|---|
| dashboard(customer) | GET | Indicateurs du périmètre autorisé |
| create_record(kind, values) | POST | kind asset/audit/risk/incident ; champs explicitement bornés ; retourne name/doctype |
| assign_incident(name, technician, expected_modified) | POST | Direction/responsable ; habilitation contrôlée, horodatage retourné |
| transition_incident(name, status, expected_modified, resolution=None) | POST | Technicien affecté ou direction/responsable ; transition et résolution contrôlées |

Les modifications détaillées des questionnaires/risques/équipements utilisent les formulaires et API documentaires Frappe natifs sous les mêmes contrôles. Les corps ne doivent contenir ni mots de passe, clés, jetons ni données privées inutiles.

## Développement et démonstration

Uniquement sur un laboratoire autorisé et jetable, après sauvegarde si nécessaire :

```sh
# Depuis le bench contenant frappe, erpnext et softsystem97, avec cette branche.
bench --site audit.localhost clear-cache
bench --site audit.localhost execute softsystem97.cyber.install.prepare
# Écriture explicite de rôles seulement, aucun compte modifié :
bench --site audit.localhost execute softsystem97.cyber.install.prepare --kwargs '{"dry_run":False}'
bench --site audit.localhost migrate
# Démonstration volontaire, deux Customer fictifs et leurs enregistrements :
bench --site audit.localhost execute softsystem97.cyber.demo.seed
```

Le seed exige `allow_tests` et un nom `audit.*`/`test_*`, refuse les autres sites et ne crée aucun utilisateur. Il ne s’exécute pas lors d’une installation. Les tests créent leurs propres utilisateurs fictifs ; aucun mot de passe réel utilisé.

Commandes exécutées dans ce bench (file Redis temporaire isolée pour ne pas exécuter le backlog existant) :

```sh
env/bin/python /workspace/softsystem97/tools/run_local_tests.py --site audit.localhost
env/bin/python /workspace/softsystem97/tools/validate_cyber_http.py --site audit.localhost
```

Le runner comprend la phase 1 et `softsystem97.tests.test_cyber`. Les tests Cyber utilisent les vraies tables, permissions, documents et transactions Frappe, pas un moteur Cyber simulé. Les tests financiers/métier historiques gardent leurs simulations existantes. Les tests HTTP utilisent le dispatcher WSGI natif, de vrais comptes synthétiques, sessions, CSRF, REST et Jinja ; ils ne prouvent pas une session Cloud ni le fonctionnement JavaScript dans un navigateur réel.

## Futures intégrations — contrats non activés

Aucun endpoint d’ingestion, registre de fournisseurs, secret, tâche planifiée ni abonnement n’est activé. Avant implémentation, chaque adaptateur doit vérifier l’origine, résoudre Customer/Asset côté serveur, borner le contenu, journaliser une référence expurgée et dédupliquer transactionnellement `(provider, event_id)` ; les IDs transmis ne sont pas une preuve de périmètre.

| Port prévu | Entrée vérifiée à concevoir | Sortie prévue / garde-fou |
|---|---|---|
| Wazuh | Événement signé/authentifié, id, équipement connu, date, gravité | Proposition d’incident dédupliquée, pas d’affectation automatique |
| Protection des postes | Source EDR authentifiée, id d’inventaire, constat daté | État/risque ; aucune installation d’agent ou remédiation distante |
| Sauvegardes | Fournisseur authentifié, id de tâche, date, résultat et référence de preuve | Vérification datée ; absence/péremption explicitement inconnue |
| Assistance distante | Ticket autorisé, conditions de facturation serveur, consentement explicite borné et révocable | Référence de session ; confirmation locale du moteur requise avant démarrage, aucun moteur actuellement raccordé |
| Notifications | Événement métier accepté, destinataires résolus par périmètre, clé de déduplication | Mise en file transactionnelle future ; aucun envoi Cyber automatique V1 |
| Abonnements | Références ERPNext Contract/Sales Invoice et preuve financière serveur | Éligibilité du service ; aucun prélèvement, clé Stripe ou activation de facturation V1 |

Ne pas réutiliser le journal append-only Cyber comme un reçu de déduplication amont : le contrat d’ingestion et ses contraintes uniques restent à implémenter. Les consentements/agents/flux distants de la conception historique ne sont pas installés.

## Staging et limites

À valider après autorisation distincte : migration sur versions exactes du staging, rôles et lien Portal User réels sans modifier les comptes de production, formulaires Desk, JavaScript du dashboard, volumes et performances, politique de rétention, sauvegarde/restauration et compatibilité des personnalisations du site. Les adaptateurs externes, livraison de notifications Cyber et facturation ne sont pas implémentés ni validés.

Avant toute installation Cloud : sauvegarde base/fichiers et preuve de restauration, relever SHA et versions ; approuver la migration des huit nouveaux DocTypes. En cas d’échec, suspendre l’accès Cyber, préserver les événements et revenir au SHA précédent après vérification de compatibilité ; restaurer une sauvegarde seulement avec plan approuvé tenant compte des nouvelles écritures. Ne pas supprimer automatiquement les tables. La phase 1 et PR #3 restent préservées ; aucun déploiement ou fusion autorisé par cette livraison.

## Preuves de livraison locale

Migration effectuée uniquement sur `audit.localhost` ; les huit DocTypes appartiennent au Module Def **Cyber Protection** (`logs/cyber-migrate.log`). Les modifications Frappe préexistantes ne sont pas fusionnées dans main.

| Validation exécutée | Résultat | Journal du bench |
|---|---|---|
| Suite Frappe complète | 127 réussis, dont 30 Cyber, 0 échec | `cyber-final-frappe.log` |
| Cyber HTTP natif | 9 scénarios | `cyber-final-http.log` |
| Sources historiques phase 1 | 17 réussis | `cyber-final-historical.log` |
| HTTP phase 1 | 15 réussis | `cyber-final-phase1-http.log` |
| Navigateur phase 1 | 13 réussis, réponses HTTP simulées | `cyber-final-phase1-browser.log` |
| PowerShell | 29 assertions réussies, hors ligne | `cyber-final-powershell.log` |
| SMTP local phase 1 | 6 messages pont + 1 notification native reçus une seule fois | `cyber-final-smtp.log`, `cyber-final-native-smtp.log` |
| Analyse statique des nouveaux fichiers Python | Ruff réussi | `cyber-lint.log` |

Les premiers essais ont trouvé des fixtures à recharger après un refus de validation et un défaut d’initialisation CSRF de la nouvelle page. Ces points ont été corrigés. L’introduction du Module Def indépendant a nécessité l’invalidation du cache de modules avant migration, intégrée à la procédure. Le dernier renforcement teste aussi l’impossibilité de réutiliser une ligne de questionnaire d’une autre entreprise. Les échecs initiaux ne sont pas présentés comme des tests réussis.

Démonstration persistée dans ce laboratoire seulement : `SS97 Cyber DEMO A 8ac21b` et `SS97 Cyber DEMO B 8ac21b`, chacune avec un serveur, un audit achevé, un risque High et un incident Critical non affecté. Références et sortie du seed dans `logs/cyber-demo.log`. Aucun utilisateur créé par le seed, aucune connexion externe et aucune sauvegarde déclarée vérifiée automatiquement.

La base de tests n’est pas un staging Cloud. La connexion/déconnexion HTTP concerne uniquement des comptes fictifs à mot de passe aléatoire en mémoire. Aucun secret, mot de passe ou cookie n’est imprimé dans les rapports.
