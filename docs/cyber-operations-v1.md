# Cyber Protection opérationnel V1 — livraison de développement

Branche `feature/cyber-operations-v1`, basée sur le module V1 `b117625`. Ce document est la référence de cette extension ; les résultats antérieurs restent historiques. Frappe 16.52.0 / ERPNext 16.51.1, Python 3.14.8 dans le laboratoire. La migration **de `audit.localhost` uniquement** a été explicitement autorisée dans la conversation et exécutée. Aucune installation, migration, donnée ou configuration Frappe Cloud/production modifiée.

## Périmètre livré

- `/ss97-cyber` : espaces Direction, responsable Cyber, technicien et client, proposés selon les rôles actifs. Entreprises, équipements, audits, risques/actions, incidents, rapports approuvés et demandes d’assistance sont filtrés côté serveur. Les modifications détaillées restent dans les formulaires Desk natifs et API autorisées.
- Indicateurs calculés : équipements, audits achevés, risques ouverts, incidents critiques/ouverts, actions requises/urgentes, alertes **importées**, vulnérabilités **classées manuellement**, contrats Cyber liés et actifs. Aucun résultat de surveillance n’est inventé. Les listes sont bornées à 50 lignes ; le périmètre global au-delà de 5 000 entreprises est explicitement signalé incomplet.
- Actions correctives : responsable/technicien habilité, échéance et notes de diagnostic dans Risk ; affectation par direction/responsable seulement, traitement d’une action affectée par son technicien.
- Entreprise : formules Cyber Audit / Essentiel / Professionnel / Entreprise, période, prestations incluses, périmètre et inclusion de préparation distante. Le contrat reste ERPNext Contract. Aucune Subscription, facture ou échéance de prélèvement créée.
- Rapport immutable généré depuis les données existantes, brouillon puis approbation de direction/responsable. Les clients voient seulement leurs rapports approuvés. Sortie imprimable `/ss97-cyber-report?name=<référence>` ; PDF via l’impression du navigateur, pas un moteur PDF serveur installé.
- Formulaire de génération de rapport pour direction/responsable, consentement/refus/révocation par boutons pour le client ; l’approbation des brouillons reste dans les formulaires Desk protégés.
- Gestion des demandes d’assistance : référence Issue du même Customer, technicien Cyber habilité, préparation contractuelle/financière vérifiée côté serveur, consentement/refus explicite du client, révocation/fermeture et compte rendu. **Pas de transport distant** et durée de connexion toujours nulle.

## Schémas et architecture

Six DocTypes ajoutés au Module Frappe **Cyber Protection** (14 au total avec les huit V1) :

| DocType ajouté | Contrôleur / usage |
|---|---|
| SS97 Cyber Wazuh Config | Configuration administrative unique par Customer, désactivée par défaut, Password Frappe chiffré, origine approuvée et règles explicites |
| SS97 Cyber Agent Map | Enfant Config ; correspondance agent–équipement dans la même entreprise |
| SS97 Cyber Sync Event | Reçu serveur unique par empreinte entreprise/origine/événement ; aucun payload brut |
| SS97 Cyber Sync Run | Historique de synchronisation : compteurs, statut, code d’erreur borné, indicateur de lot incomplet |
| SS97 Cyber Report | Période, snapshot généré, approbation et identité/date dérivées du serveur |
| SS97 Cyber Remote Request | Demande/consentement/fermeture, références contractuelles, horodatages et compte rendu ; aucun jeton ou identifiant de poste distant |

Ajouts aux schémas existants : Company (formule/période/périmètre/prestations/remote_included), Asset (résumé matériel), Risk (type de risque, technicien, échéance, notes). Ni nouvelle base Customer ni nouveau moteur de tickets/paiements. Le lien Issue ne donne aucun droit supplémentaire sur le ticket et ne change pas son statut.

Services : `cyber/workspace.py`, `reports.py`, `remote_requests.py`, `wazuh_sync.py`, contrôleurs `operations_model.py`. Le socle `model.py` et les hooks de permissions s’appliquent aussi aux nouveaux objets. Journal append-only applicatif existant réutilisé ; aucune trace brute de fournisseur, contenu d’écran ou secret dans ce journal.

## Interfaces réellement disponibles

Préfixe `/api/method/softsystem97.cyber.` ; mutations POST avec CSRF de session, lectures sous permissions natives :

| Méthode | Fonction |
|---|---|
| workspace.available_views / workspace.load(view, customer=None) | Espaces et projections du périmètre effectivement autorisé |
| api.assign_action(name, technician, expected_modified, due_date=None) | Affectation d’une action corrective |
| reports.generate(customer, from_date, to_date) | Nouveau brouillon dérivé, période ordonnée de 367 jours maximum |
| reports.approve(name, expected_modified) / reports.detail(name) | Approbation réservée et consultation filtrée |
| remote_requests.request(customer, issue) | Demande initiale, sans consentement ni moteur |
| remote_requests.prepare(name, technician, billing_basis, expected_modified, invoice=None) | Préparation par direction/responsable |
| remote_requests.transition(name, state, expected_modified, report=None) | Consentement/refus client et révocation/fermeture, jamais démarrage |
| wazuh_sync.sync(configuration, since) | Import manuel borné ; réservé à direction/responsable, aucune injection de transport par HTTP |

Les interfaces V1 `api.create_record`, `dashboard`, `assign_incident`, `transition_incident` restent disponibles. Les méthodes documentaires Frappe appliquent les mêmes contrôles. Les révisions périmées refusent l’écriture.

## Wazuh : adaptateur d’indexeur, pas déploiement de supervision

`cyber/connectors/wazuh.py` utilise le moteur OpenSearch de **Wazuh indexer**, `POST /wazuh-alerts-4.x-*/_search`. L’API manager `/agents` n’est pas présentée comme une API d’alertes. La compatibilité du motif d’index et de l’authentification Basic doit être vérifiée sur le serveur réel avant activation.

Conditions avant tout appel : administrateur de bench ayant approuvé le hostname exact dans `ss97_wazuh_allowed_hosts`, origine HTTPS sans identifiants/query/fragment/chemin arbitraire, port 443 ou 9200, configuration activée par responsable, entreprise autorisée avec référence de preuve, correspondance agent–Asset explicite. Les IP littérales loopback/link-local/non spécifiées sont refusées ; la résolution DNS et la confiance du réseau de l’origine approuvée restent à contrôler par l’administrateur. Aucun hostname client ne choisit la destination.

Identifiants : champ Password Frappe, clé de chiffrement privée du site, jamais de secret en Git, dans une URL, le rapport ou la console partagée. Configuration et journaux de synchronisation réservés à direction/responsable. Prévoir un compte indexeur en lecture minimale. TLS vérifié, redirections refusées, timeout connexion/lecture, réponse bornée à 2 Mo. Seuls agent.id/rule.level/timestamp et l’identifiant de document sont utilisés.

Import volontaire : 100 alertes maximum depuis `since` explicite. **Un lot plein est marqué truncated ; aucune pagination complète ni couverture continue n’est revendiquée, aucun curseur n’est avancé automatiquement.** Ne pas avancer aveuglément la fenêtre tant qu’un lot plein n’est pas réconcilié. Aucun scheduler installé.

Règle V1 explicite : seuls les agents mappés à un équipement du même Customer sont acceptés. Un incident est créé uniquement si `create_incidents` est activé et si rule.level atteint `minimum_level`. Gravités : Critical ≥15, High ≥12, Medium ≥7, Low sinon. Les autres alertes reconnues restent des reçus sans incident. Aucun agent inconnu ne choisit son Customer. Pas de modification automatique d’équipement ou de confinement.

Unicité et concurrence : empreinte SHA256, index unique, verrous transactionnels configuration/autorisation et lecture courante du reçu. Un conflit/deadlock produit HTTP **409**, sans succès ni tentative de rollback vers un savepoint disparu. Le client doit rollback/recommencer la requête ; aucune reprise financière automatique. Les autres erreurs annulent le lot et produisent un Sync Run avec code borné, sans texte d’exception amont. Aucun commit interne du service.

## EDR et assistance distante

`connectors/edr.py` définit un port read-only `EDRAdapter` et `ProtectionState` : équipement, état, dernière communication, version/état d’agent, références d’alertes et propositions. Aucun fournisseur connecté ; l’état reste explicitement Unknown. Aucun antivirus, agent, action disruptive ou remédiation automatique.

`connectors/remote.py` définit un moteur déconnecté : `can_start=False`, `start()` refuse. Les états des dossiers sont Requested → Awaiting consent → Consented/Declined → Revoked/Closed ; aucun état Active/Started. Le client propriétaire seul peut consentir/refuser ; les métadonnées de consentement sont dérivées côté serveur et ne peuvent être déclarées par le navigateur. La révocation est ici celle du **dossier**, pas la preuve d’une coupure RustDesk réelle puisqu’aucun moteur n’existe.

Préparation : rôle/habilitation du technicien, autorisation d’entreprise et inclusion distante explicites ; soit Contract ERPNext actif du Customer dans ses dates, soit facture ERPNext soumise, positive, non retournée et sans solde. La facture n’est pas assimilée à une preuve Stripe, et ce contrôle **ne remplace pas le workflow historique**. Les périodes de service et la révocation d’autorisation sont revérifiées avant consentement. Aucun consentement antérieur ne doit être réutilisé pour un futur moteur sans nouveau contrôle d’éligibilité, d’affectation, d’expiration et de consentement local. Aucun téléchargement, agent permanent, viewer, invitation ou accès non supervisé n’est créé.

## Rapports et confidentialité

Les snapshots sont immuables ; l’approbateur/date sont calculés. Les équipements/risques/KPIs sont des états au moment de génération ; les listes d’audits/incidents portent sur la date de création dans la période, pas sur un historique reconstruit. Limite 500 éléments par section avec avertissement de troncature. Sauvegardes : uniquement état déclaré, date et référence de preuve ; EDR non connecté = Unknown ; absence d’import Wazuh = absence d’information, pas une conformité. Les vulnérabilités proviennent du type de risque saisi manuellement. Toutes les valeurs HTML sont échappées et les rapports privés ne sont pas mis en cache.

Le portail efface les données après refus/session perdue et ignore les réponses tardives lors d’un changement de vue. L’authentification/MFA reste celle de Frappe ; aucun contournement ajouté. La MFA réelle n’a pas été validée faute de site externe configuré. Les notifications existantes de phase 1 sont conservées ; aucune livraison automatique Cyber ou facturation d’abonnement n’est activée.

## Recette locale reproductible, sans migration automatique

Préconditions déjà satisfaites sur le laboratoire : frappe + erpnext + softsystem97, schémas migrés après approbation explicite ; dépendances requests gérées par Frappe, outils de laboratoire Playwright/Chromium, aiosmtpd, redis-server et Ruff. Pas de dépendance Wazuh/EDR/RustDesk installée.

```sh
# Depuis le bench, avec son Python : uniquement audit.* / test_* et allow_tests.
env/bin/python /workspace/softsystem97/tools/validate_cyber_operations.py \
  --site audit.localhost --chromium /usr/bin/chromium --with-regressions
```

Ce runner réutilise la file Redis temporaire du test SMTP, sans purger/exécuter le backlog existant. Il n’installe rien et ne migre aucun schéma. Les tests créent des comptes/Customer fictifs ; les tests de concurrence nettoient uniquement leurs propres fixtures. Aucune clé réelle n’est utilisée. Les cas de contrat utilisent ERPNext réel ; le cas financier Sales Invoice et le transport Wazuh sont simulés.

## Staging : opérations préparées seulement

Aucun staging administrateur disponible. Avant installation : autorisation distincte, sauvegarde base/fichiers/configuration dans un stockage privé et preuve de restauration ; relever versions réelles, applications, SHA ; pas de données ou comptes de production dans les fixtures. Prévoir l’application softsystem97 au SHA de cette branche, Frappe/ERPNext compatibles avec 16.52.0/16.51.1 testés. Revoir les personnalisations, les six nouveaux DocTypes et les trois extensions de schéma.

Après approbation seulement, dans le staging : `bench --site <staging> clear-cache`, migration via Frappe Cloud/`bench --site <staging> migrate`, build et redémarrage prévus par la plateforme. Préparer des utilisateurs fictifs avec les quatre rôles Cyber ; ne pas accorder System Manager au technicien. Réutiliser les liens Customer.portal_users. Aucun champ de secret dans les exports de recette.

Critères d’acceptation : isolation sur listes, documents, rapports et API avec deux entreprises ; écritures CSRF et révisions contrôlées ; affectations correctes ; rapport client approuvé/imprimable ; données de sauvegarde non inventées ; Wazuh désactivé tant qu’origine/permissions/index/TLS réels non validés ; aucun engine distant ni facture/prélèvement. Les tests HTTP/browsers locaux ne prouvent pas une recette Cloud. Arrêter en cas de métadonnée incompatible, accès croisé, doublon ou absence de restauration démontrée.

Retour arrière : suspendre d’abord l’accès Cyber et les imports par un administrateur autorisé. **Ne pas simplement remettre un ancien code sans les hooks des nouveaux DocTypes alors que leurs permissions restent en base.** Restaurer un ensemble code/base cohérent après approbation, ou conserver les protections de périmètre et désactiver les fonctionnalités nouvelles. Préserver événements et écritures postérieures ; aucune suppression automatique de tables, aucun renvoi massif.

## Chantier technicien séparé

Branche `fix/technician-final-validation` au commit existant `faaa188` : collecteur privé et corrections phase 1 préservés. Pas de nouveau contrôleur original récupéré. `ticket_workspace.py` concerne `/espace-client/ticket` ; `/ss97-dev-technician` est distinct de `/espace-technicien/tickets`.

Dépendances à collecter : contrôleur fichier/Web Page et hooks de la route réelle, schéma/profil `Issue.ss97_technician`, workflow et règles de paiement/intervention, `integrations/ss97_tickets/workflow_logic.py`, API historiques dont `ss97_ticket_confirm_payment`. Le collecteur n’exécute ni n’exporte les sources potentiellement secrètes ; son manifeste sert à localiser les sources à revoir en privé. Procédure exacte dans `route-metadata-collection.md` ; exécution par console administrative autorisée sur staging distinct. Aucun rôle attribué à servermoses@gmail.com et aucun mot de passe utilisé/modifié.

La phase 1 reste bloquée pour son portail historique et les tests Stripe Test externes, sans bloquer la livraison locale Cyber. Son contrôle métier refuse l’absence d’adaptateur réel. Aucune simulation des règles historiques n’est présentée comme une validation de production.

## Résultats réellement exécutés pour cette livraison

| Suite | Résultat final | Portée / journal local dans le bench |
|---|---|---|
| Frappe complète | **151 réussis, 0 échec** | 97 tests préexistants + 30 Cyber V1 + 24 nouveaux ; `operations-validation-frappe.log` |
| Cyber HTTP natif | **13 réussis** | Sessions, CSRF, REST, espaces par rôle, rapports privés/imprimables, demande d’assistance ; `operations-validation-http.log` |
| Cyber Chromium | **8 réussis** | Template réel, réponses API fictives : affichage, XSS, lien rapport, consentement/révocation, génération de brouillon, réponses tardives et perte de session ; `operations-validation-browser.log` |
| Sources historiques | **17 réussis** | Safe-exec/façades de données fictives ; `operations-validation-historical.log` |
| HTTP technicien | **15 réussis** | Dispatcher Frappe natif du pont de développement, pas le portail historique ; `operations-validation-technician-http.log` |
| Navigateur technicien | **13 réussis** | Réponses HTTP simulées ; `operations-validation-technician-browser.log` |
| SMTP local | **6 messages pont + 1 notification native**, chacun reçu une fois | Scheduler/worker réels et boîte SMTP locale ; `operations-validation-smtp.log`, `operations-validation-native-smtp.log` |
| PowerShell | **29 assertions réussies** | Hors ligne ; `operations-final-powershell.log` |
| Ruff | **Réussi** | Nouveaux fichiers Cyber, contrôleurs et outils concernés ; `cyber-operations-lint.log` |
| Dépendances Python | **158 paquets compatibles** | `uv pip check`, sans installation ; `operations-dependencies.log`. Ce contrôle ne constitue pas un audit CVE. |

La commande `validate_cyber_operations.py --with-regressions` a été exécutée, puis les suites Frappe/HTTP/Chromium Cyber ont été relancées après le dernier renforcement de la révocation. Une révocation de consentement reste possible pour le client même si le technicien affecté a depuis été désactivé ; elle ne réactive aucun droit technique.

Erreurs initiales corrigées : valeur par défaut de Select qui préremplissait une base contractuelle à tort ; gestion d’un conflit MariaDB avec savepoint disparu ; fixtures de facturation, assertions de HTML déjà assaini par Frappe et encodage UTF-8/sélecteurs des tests navigateur. Le test de concurrence utilise deux connexions MariaDB et prouve un seul incident après rollback/reprise. Les cas Wazuh utilisent un **transport HTTP fictif** ; le cas Sales Invoice utilise des valeurs financières simulées, tandis que Contract est réellement exercé dans Frappe.

Non exécuté : staging Frappe Cloud, Stripe Test externe, indexeur Wazuh réel, EDR réel, moteur RustDesk, livraison SMTP externe et MFA d’un site réel. Ces résultats ne sont pas des preuves de production.

## Livraison Git et prochaines opérations

- Technicien : branche `fix/technician-final-validation`, commit existant `faaa188`, même contenu vérifié que le collecteur déjà livré. Aucun commit de documentation créé pour prétendre compléter le contrôleur absent.
- Cyber : branche `feature/cyber-operations-v1`, conserve `feature/cyber-protection-v1` et `b117625` par ascendance ; seules les adaptations applicatives/testées de cette extension sont ajoutées.
- PR #3 préservée. L’API GitHub refuse la lecture des permissions du dépôt (`Forbidden`) ; aucun contournement ni fusion. Les corps des deux PR sont préparés hors dépôt. La possibilité de pousser des branches Git ne prouve pas le droit de créer une PR via API.

**Prochaine action A :** administrateur autorisé, exécuter le collecteur existant de `route-metadata-collection.md` sur le staging distinct et transmettre le JSON expurgé pour localiser le contrôleur/workflow réels.

**Prochaine action B :** faire approuver la recette du SHA Cyber livré sur un staging isolé avec deux entreprises et comptes fictifs, en gardant Wazuh/EDR/transport distant désactivés tant que leurs validations séparées n’ont pas eu lieu. Pas d’autorisation de production implicite.
