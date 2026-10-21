# Intégration du portail historique : recette et déploiement contrôlé

> Mise à jour — les cinq sources historiques sont reçues : workflow_logic.py,
> specs.py, fix_priority.py et les composants client/types précédents sont intégrés.
> Le catalogue confirme `SS97 Technician`, `Issue.ss97_technician` Link → User,
> les SLA 72/24/8/2 heures et les actions de statuts déclarées. Cela décrit les sources,
> pas les métadonnées réellement installées sur Frappe Cloud.
>
> `business_policy.py` contient les contraintes de catalogue et la détection des
> incohérences ; il ne fournit pas `authorize_ticket_operation`, car les permissions
> par acteur et les preuves de paiement/consentement ne sont pas définies ici.
> Le fournisseur d’autorisation réel et le contrôleur commercial restent nécessaires.
> Aucun raccordement historique n’est activé par ces fichiers.
>
> Corrections : import du normaliseur sans SDK privé ; cohérence de « Normale »
> avec PRIORITY_MAP ; refus d’une priorité hors liste et des états non mappés ;
> suppression des clés masquées en préservant exactement la dernière valeur Python.
> Le script administratif de priorités prévisualise par défaut ; écritures et
> création de tickets de contrôle exigent des options explicites. Il n’est pas exécuté
> sur un serveur réel ; ses réécritures de formulaires doivent être revues avant usage.
>
> À confirmer : « Terminé » mappe vers Closed, mais son alias officiel vers Resolved ;
> « Suspendu — risque sécurité » n’a pas de mapping natif. Aucune décision inventée.
> Les helpers conservent aussi les corrections de copie de préparation, Comment
> natif autorisé et arrêt sur référence invérifiable. L’unicité concurrente exige
> une contrainte serveur, non prouvée par les lectures du client.
>
> Validation ciblée : 13 tests avec les vrais specs/normaliseur/SLA, 28 tests historiques
> avec runtime Frappe (certaines dépendances restent simulées dans ces anciens cas),
> et un nouveau test Frappe du refus d’activation sans fournisseur d’autorisation.
> Zéro échec final ; aucune recette de route commerciale ou de paiement réel revendiquée.
> Les mentions d’absence des fichiers plus bas décrivent les états antérieurs.



L’état courant du candidat unique, ses tests, dépendances et points d’arrêt est fixé dans [consolidated-release.md](consolidated-release.md). Les sections ci-dessous conservent les preuves des reprises précédentes.

## Composants existants retrouvés et sécurité du webhook

La recherche couvre les références locales et les branches distantes annoncées, un historique Git non tronqué (33 commits accessibles avant ce correctif), les chemins modifiés dans les anciens commits et les archives de travail accessibles. `Issue` existe dans ERPNext installé : `erpnext/support/doctype/issue/issue.json` et `issue.py`. Aucun second DocType de tickets n’est nécessaire. Les définitions SS97 de production ne sont pas fournies par les références de champs des trois sources importées ; les Custom Field des tests sont des fixtures synthétiques.

Composants réutilisés : API et politiques `ticket_bridge`, préparation idempotente de rôle dans `provisioning.py`, trois sources historiques importées, `stripe/payment_sync.py`, `stripe/webhook.py` et DocTypes SS97 Stripe Event/Config et Client Notification. L’ancien `softsystem97/integrations/bridge/api.py` traite des demandes techniques `SS97 Bridge Request`, pas un workflow Issue ; il n’est pas remplacé ni détourné en contrôleur de tickets.

Un correctif réel de création publique est conservé dans `origin/fix/softsystem97-production-bugs`, commits `6c1c70f` et `8dd9a01` : `softsystem97/patches/fix_ticket_libre_submission.py`. Il cible Web Form `ss97-ouvrir-ticket`, Server Scripts `SS97 Issue After Insert Number Token` et `SS97 AI Agent Reception After Insert`, et référence `ss97_ticket_brevo_flush`. Il ne fournit pas les définitions complètes de ces producteurs ni un contrôleur technicien. Il reste sur sa branche : aucune fusion ni activation automatique de scripts n’est faite. Aucun contrôleur de `/espace-technicien/tickets` ni `integrations/ss97_tickets/workflow_logic.py` n’a été retrouvé dans cet historique ou les archives accessibles.

Le webhook existant a été corrigé, sans création d’un nouveau producteur : la signature est vérifiée avant toute consultation/acquittement d’un événement déjà traité ; la fenêtre temporelle de 300 secondes refuse aussi les horodatages excessivement futurs. Une reprise correctement signée reste acquittée sans nouveau traitement ni écriture. Les deux défauts ont été reproduits (trois échecs de tests/sous-cas) dans `stripe-recovered-components-before.log`.

Après correction : **84 tests de la suite Frappe réussis**, dont trois nouveaux tests de signature/reprise, **17 tests des sources importées réussis** et **15 scénarios HTTP natifs réussis**. Journaux : `stripe-recovered-components-after.log`, `stripe-recovered-sources.log`, `stripe-recovered-http.log`. Les signatures sont calculées réellement par HMAC avec une clé et un corps synthétiques, l’horloge et la persistance du webhook sont simulées ; aucun secret du site n’est lu dans ces tests, aucun Stripe externe ou paiement réel n’est validé. Les tests natifs de cycle, permissions et réaffectation restent inclus ; leur politique métier demeure simulée.

Préproduction : (1) obtenir un export privé expurgé du contrôleur fichier ou document Web Page desservant la route, de ses Server Scripts/API et des Custom Field/Workflow/permissions Issue et Sales Invoice ; (2) préparer un site isolé compatible, avec ces schémas et uniquement des données fictives, sorties SMTP/webhooks contrôlées et restauration de sauvegarde testée ; (3) installer le SHA candidat, migrer/construire/vider les caches selon Frappe Cloud, sans activer de route historique automatiquement ; (4) implémenter `business_policy.authorize_ticket_operation` à partir du vrai workflow et du lien facture ↔ ticket, puis vérifier les conditions de rôle/profil et les garde-fous Workflow/Server Scripts sans les désactiver pour contourner un refus ; (5) recetter création, paiement Stripe de test, affectation administrative, accès A/refus B, intervention, clôture, suivi client et livraison SMTP contrôlée, y compris reprises/refus ; (6) conserver les preuves et répéter le retour arrière en staging. Un compte réel ou un déploiement de production exige toujours son autorisation séparée. Ces étapes serveur ne sont pas annoncées exécutées.

## Consolidation de la révocation et des contrôles de paiement

Deux régressions d’affectation et quatre sous-cas d’un test de paiement ont été reproduits avant correction (`bridge-consolidation-before.log`, 79 tests, six échecs comptabilisés). Lors d’une réaffectation historique approuvée, `api.assign_ticket` révoque maintenant définitivement les anciennes approbations du ticket dans la transaction de changement du champ ; restaurer `ss97_technician` ne suffit plus à les réactiver. Une nouvelle décision métier et une nouvelle clé d’affectation sont nécessaires pour réautoriser l’ancien technicien. La relecture d’un ancien reçu reste sans effet. Cette correction ne modifie pas les règles natives d’écriture Issue et ne remplace pas un hook de workflow privé pour les changements externes à ces API.

`payment_sync.verify_amount_currency` refuse désormais les devises absentes et les montants absents, non numériques ou non finis ; il applique aussi la comparaison existante lorsqu’un montant vaut zéro. La tolérance historique de 0,05 et la résolution de facture restent inchangées ; aucune exemption métier n’est inventée. Cela valide une comparaison comptable, pas l’existence d’un paiement Stripe réel.

Deux tests supplémentaires vérifient qu’une réaffectation refusée préserve l’ancien accès et qu’un échec de notification annule le changement de champ, la révocation et la nouvelle approbation à la frontière de rollback. Le contrôle de ces transactions utilise Frappe natif et des données fictives ; le fournisseur métier reste simulé.

Les commandes de consolidation sont exécutées depuis le bench jetable :

```sh
env/bin/python /chemin/softsystem97/tools/run_local_tests.py --site audit.localhost
env/bin/python /chemin/softsystem97/tools/test_historical_ticket_sources.py --frappe-site audit.localhost
env/bin/python /chemin/softsystem97/tools/validate_ticket_bridge_http.py --site audit.localhost
```

Les journaux sont `bridge-consolidation-after.log`, `bridge-consolidation-sources.log` et `bridge-consolidation-http.log`. Aucun autre contrôleur historique n’a été reçu : l’unique archive accessible contient toujours les trois fichiers client/types déjà importés. Le fournisseur `business_policy.py`, le workflow privé, le SDK externe et les API historiques nommés ci-dessous restent absents. Le transport SMTP n’est pas relancé : le précédent échec demeure non validé, sans renvoi de messages. Aucun changement de compte réel ou de production.

Résultat final de ces commandes : **81 tests de la suite Frappe réussis**, **17 tests des sources importées réussis**, **15 scénarios HTTP natifs réussis**, sans échec final. Les cinq nouveaux tests de consolidation s’ajoutent aux 76 précédents ; les montants/devises et le fournisseur métier utilisent des contextes simulés explicitement décrits dans les modules de tests.

## Raccordement applicatif optionnel : contrat métier obligatoire

`softsystem97/integrations/ticket_bridge/historical.py` fournit maintenant un contrat serveur typé pour raccorder le pont existant au workflow privé, sans créer un contrôleur historique. Il ne confirme aucun paiement. Le mode reste désactivé tant que `ss97_ticket_bridge.historical_integration` n’est pas explicitement `true`. Les garde-fous existants du pont (activation, compatibilité, profil, schéma, Workflow/Server Scripts et producteurs concurrents) restent obligatoires.

Ce mode exige le rôle exact `SS97 Technician` et un véritable champ `Issue.ss97_technician` de type Link vers User. Un lien vers un profil différent impose un autre adaptateur ; aucun rapprochement e-mail/profil n’est inventé. L’affectation administrative écrit ce champ et conserve l’approbation ToDo protégée dans la même transaction. Le champ seul ne donne aucun accès ; les listes, détails, mutations et destinataires exigent également cette approbation. Après réaffectation, l’ancien technicien est exclu même si son ToDo demeure ouvert.

Le paramètre privé `business_authorizer` désigne une fonction serveur revue, sous `softsystem97.integrations.` (une application installée, comme l’exige Frappe v16). Interface à implémenter dans les vraies dépendances : `authorize_ticket_operation(request: AuthorizationRequest) -> AuthorizationDecision`. Le fournisseur d’intégration attendu `softsystem97/integrations/ticket_bridge/business_policy.py` reste à implémenter après récupération de `integrations/ss97_tickets/workflow_logic.py`. Ce dernier est un module externe historique, pas une application Frappe installée ; il ne doit pas être configuré directement comme fournisseur. Aucun exemple d’autorisation positive de remplacement n’est installé et aucune configuration n’est activée par migration.

Le fournisseur reçoit un instantané immuable (Issue, version modified, opération, acteur, client, technicien, statut actuel/cible). Il doit vérifier les vraies règles de création, paiement/exemption, remboursement et intervention, sans écrire ni committer dans cette décision. Il renvoie une décision typée liée à **tout** cet instantané, un booléen strict et une version de politique non sensible. Une décision absente, refusée, périmée ou destinée à un autre acteur/ticket/statut bloque l’opération. L’absence de fournisseur bloque aussi l’accès au mode intégré. Une référence Stripe ou le JavaScript ne constitue jamais cette preuve métier.

Les nouvelles créations, affectations, interventions techniques et transitions passent par ce contrat côté serveur avant leur mutation. Les commentaires clients ne constituent pas un démarrage d’intervention. Les transitions natives restent limitées même si le fournisseur répond positivement. Les versions de politique approuvées sont inscrites aux reçus/historiques existants ; une reprise idempotente acquitte seulement un ancien résultat, sans restaurer un accès ou refaire une opération. Les exceptions doivent laisser la frontière HTTP annuler la transaction, comme dans le pont existant.

Une correction indépendante dans `stripe/payment_sync.py` fait désormais respecter le contrôle montant/devise existant : son échec interrompt le traitement avant création de Payment Entry, marquage paid ou notification. Le code Stripe accessible travaille sur Sales Invoice, pas sur Issue : le lien facture/ticket, les exemptions et la politique privée restent à fournir. Cette correction n’implémente pas ce lien ni une vérification Stripe en ligne.

Validation de cette livraison : **76 tests de la suite Frappe réussis**, dont huit nouveaux tests sur de vrais Issue/ToDo/journaux avec fournisseur métier simulé et schéma Link User synthétique, plus deux tests de validation de paiement avec contexte facture simulé ; **17 tests des sources importées réussis** et **15 scénarios HTTP natifs réussis**. Journaux privés : `historical-lifecycle-tests.log`, `lifecycle-historical-source-tests.log`, `lifecycle-http-tests.log`. Aucun appel Stripe, paiement réel ou test de la route historique. L’échec SMTP de la revue précédente reste non résolu ; aucun renvoi supplémentaire n’est effectué ici.

Staging : installer le SHA candidat sur une copie isolée, maintenir les routes/activations inchangées, récupérer le vrai schéma et implémenter le fournisseur dans les dépendances privées, puis recetter H01–H09 et le transport de notifications avec destinataires approuvés. Aucune migration de production n’est ajoutée : le champ historique doit déjà exister et être vérifié, pas être créé automatiquement. Les tests créent leur propre fixture Custom Field/Role dans le laboratoire puis en retirent les métadonnées ; ce n’est pas un schéma constaté en production. Retour arrière : maintenir le pont désactivé, préserver reçus et données ; ne pas revenir à une version active qui omettrait le contrôle métier. Les étapes de sauvegarde/restauration et l’approbation ci-dessous restent requises.

## Sources reçues — état qui remplace l’absence d’import ci-dessous

L’archive a maintenant été reçue et les trois fichiers lus sans exécution de leur code de déploiement. Les originaux restent hors Git dans un dossier privé. Aucun littéral correspondant aux signatures de secrets recherchées n’a été détecté ; ce contrôle ne constitue pas une garantie universelle. Les copies corrigées sont dans `integrations/ss97_client_support/` et `integrations/ss97_client_ops/`.

Le contenu réel est différent d’un contrôleur technicien complet : `ticket_workspace.py` génère `/espace-client/ticket`, `client_ticket_api.py` installe un Server Script client et `ticket_types.py` utilise un workflow externe. L’archive ne fournit ni le contrôleur `/espace-technicien/tickets`, ni la définition du champ `ss97_technician`, ni `integrations.ss97_tickets.workflow_logic`, ni `migrate_odoo_erpnext.erpnext_client`. Les API Stripe/public-detail/agent appelées depuis la page ne sont pas incluses. Le rôle `SS97 Technician` est bien cité dans le JavaScript, mais aucune autorisation serveur technicien ne peut être déduite de ce seul contrôle d’interface.

Corrections appliquées : compte client désactivé refusé ; commentaires internes/non classifiés non renvoyés ; fichiers soumis aux permissions natives ; messages clients échappés sans commit anticipé ; garde POST/session native pour l’écriture ; page client raccordée à son API cloisonnée, affichage effacé sur refus/session perdue ; rôle technicien seul ne donnant plus accès visuel aux tickets d’autrui ; paiement affiché confirmé uniquement pour une valeur positive explicite (pas une référence seule ou une sous-chaîne comme « non confirmé »). La préparation métier de création doit réussir et une insertion incertaine n’est jamais répétée automatiquement.

Validation ciblée : **15 tests réussis, zéro échec**, exécutés avec Frappe 16.52.0 sur le site jetable `audit.localhost`. Les actions du script sont exécutées par `safe_exec` réel avec une façade de données fictives ; le test du garde emploie la fonction Frappe native et des contextes requête/session synthétiques ; deux tests Node exécutent les fonctions JavaScript extraites. Ce ne sont pas des essais de bout en bout avec les DocTypes personnalisés ou Stripe. Le comportement positif de préparation métier est simulé, pas une preuve de paiement réel. Les 66 tests et 15 scénarios HTTP antérieurs ne sont pas relancés dans cette livraison.

Commande reproductible depuis le bench isolé :

```sh
env/bin/python /chemin/softsystem97/tools/test_historical_ticket_sources.py --frappe-site audit.localhost
```

Intégration interdite en production en l’état : retrouver les dépendances ci-dessus, vérifier schéma et workflow de paiement en staging, puis exécuter la recette H01–H09 ci-dessous. Le nouveau module `softsystem97.integrations.historical_ticket_guard` doit être installé **avant** toute mise à jour manuelle du Server Script client ; sans lui, l’écriture échoue volontairement. Aucun hook n’installe ces scripts ni ne modifie les routes. Les signatures de commentaires partagés sont une liste fermée à confronter aux producteurs réels ; les anciennes notes non classifiées restent masquées. Les refus File renvoient une liste vide, sans contournement. La correction d’affichage du paiement ne remplace jamais un contrôle métier serveur.

Déploiement/retour : appliquer les points d’arrêt ci-dessous, conserver une copie privée du Server Script et de la Web Page avant modification, installer le SHA applicatif validé, puis mettre à jour explicitement les composants historiques en staging avec les outils originaux retrouvés. Ne pas exécuter les fichiers importés avec des identifiants de production. En cas d’échec, suspendre le parcours concerné ; restaurer uniquement les versions revues et sûres des pages/scripts, sans réintroduire la divulgation de notes, sans supprimer reçus/tickets et sans renvoi de file. Aucun compte réel ni aucune production n’a été modifié.

## État et séparation des composants

### Revue d’intégration après réception

La revue des six fichiers a révélé un raccordement incomplet : l’API client ne retournait pas `ss97_stripe_checkout_url`, pourtant consommé par la page. Ce champ est maintenant conservé dans sa réponse bornée au propriétaire, sans création de paiement. Une réponse client arrivée après changement d’identité/session est également rejetée avant rendu. Deux tests supplémentaires couvrent ces régressions.

Exécution complète disponible lors de cette revue : **66 tests Frappe réussis**, **17 tests ciblés des sources importées réussis** après corrections, **15 scénarios HTTP natifs réussis**, **13 scénarios Chromium avec réponses HTTP simulées réussis**, **29 assertions PowerShell hors ligne réussies**. Syntaxes Python/JavaScript et `git diff --check` vérifiés. Les journaux privés du bench sont `final-review-frappe.log`, `final-review-historical.log`, `final-review-http.log`, `final-review-browser.log` et `final-review-powershell.log`.

**Échec réel :** `final-review-smtp.log` observe six Email Queue Not Sent sans doublons, puis zéro livraison au SMTP loopback dans les 50 secondes imparties. `audit-mail-processes.log` montre le worker occupé par des jobs de fixtures antérieures, dont des créations de Contact référant des utilisateurs déjà supprimés. Cela ne prouve pas un défaut du transport SMTP, mais cette exécution ne valide pas la livraison autonome scheduler → worker → SMTP. Aucun message historique n’a été renvoyé et les fixtures/configurations de l’essai ont été nettoyées/restaurées.

Le portail historique n’est **pas prêt pour une recette fonctionnelle complète Frappe Cloud**. Le seul contrôleur technicien du dépôt est `softsystem97/www/ss97_dev_technician.py`, pour `/ss97-dev-technician`, distinct et désactivé par défaut. Aucun contrôleur de `/espace-technicien/tickets` n’est fourni. À récupérer : la Web Page/le contrôleur et ses API réellement déployés, `integrations/ss97_tickets/workflow_logic.py` (`next_ss97_ticket_ref`, `prepare_new_issue`), la définition Custom Field de `Issue.ss97_technician` et du profil lié, les producteurs `ss97_ticket_confirm_payment`, `ss97_ticket_public_detail`, `ss97_ticket_public_message`, `ss97_ai_agent_dialogue_turn`. Le SDK `migrate_odoo_erpnext/erpnext_client.py` manque aussi pour utiliser les scripts de déploiement originaux, sans être nécessaire au runtime du garde applicatif. Les dépendances ne doivent pas être remplacées par des simulations en production.

Base vérifiée : `c5f0be1` sur `fix/ticket-notification-privacy` (la référence fournie `c5f9eb1` n’est pas résolue localement). La PR #3 reste indépendante. Les 66 tests Frappe et 15 scénarios HTTP déjà réussis concernent le pont de développement, pas `/espace-technicien/tickets`. Ils ne sont pas relancés pour cette préparation documentaire.

État antérieur désormais dépassé par les sections ci-dessus : les trois sources sont importées et le raccordement optionnel lit et écrit `ss97_technician` uniquement après vérification d’un schéma Link User. Le rôle et le schéma réels de production ne sont pas confirmés ; le fournisseur métier et le contrôleur historique restent absents. **Ne pas activer le raccordement sur la route historique sans recette et approbation.**

La revue des sources accessibles confirme : contrôle de session et de rôle serveur, contrôle d’affectation sur liste/détail/mutation, refus d’auto-affectation par ToDo seul, notifications filtrées par autorisation actuelle. Les écritures internes privilégiées sont bornées après ces contrôles ; elles restent à revoir avec les hooks et permissions réellement déployés. Les droits natifs hérités ne sont pas retirés par ce module.

## Tests historiques à implémenter après import

Statut de tous les cas ci-dessous : **NON EXÉCUTÉ — sources et contrat de données requis**. Ce tableau est un cahier de recette, pas une suite automatisée réussie. Utiliser deux techniciens fictifs A/B, deux clients fictifs C/D et des tickets synthétiques distincts. Aucune fixture ne référence un compte réel.

| Cas | Action serveur et preuve attendue |
|---|---|
| H01 Session | Connexion native avec A ; session reconnue. Guest, session expirée et ancien cookie après logout : aucune donnée ni mutation autorisée. Ne pas désactiver CSRF. |
| H02 Rôle | `SS97 Technician` actif autorise le parcours prévu ; rôle absent, désactivé ou compte désactivé : refus. Tester la variante française séparément selon la politique historique réellement trouvée, sans supposer son équivalence. |
| H03 Affectation | Déterminer depuis le schéma si `ss97_technician` référence User ou un profil. Une affectation serveur valide rend le ticket visible à A seulement ; un paramètre HTTP d’identité falsifié ne change pas ce périmètre. |
| H04 Lecture | Tester liste, pagination, détail par identifiant direct et notifications avec A/B/C/D ; aucun ticket, historique ou contenu d’un autre périmètre ne doit être retourné. |
| H05 Paiement | Identifier la source de vérité, les états et les exemptions depuis le code réel. Pour chaque état non éligible, une tentative directe d’affectation/intervention doit échouer sans effet métier ; un paiement éligible permet uniquement le parcours prévu. Ne pas inventer un champ `paid` ou des statuts. |
| H06 Concurrence paiement | Rejouer un événement de paiement et tenter deux affectations simultanées ; aucun doublon d’affectation, d’intervention ou de notification. Tester annulation/remboursement selon les règles réellement présentes. |
| H07 Intervention | Ticket affecté à A : transition autorisée réussie ; transition interdite, statut périmé et tentative de B refusés. Revérifier les conditions de paiement au point où le code les exige, même pour un appel direct sans interface. |
| H08 Révocation | Réaffecter de A vers B par la procédure autorisée ; vérifier immédiatement listes, détails, mutations et futurs destinataires. Une ancienne clé ou session ne rétablit pas A. |
| H09 Notifications | Avec un collecteur SMTP de staging, vérifier confirmation, affectation et changements prévus : destinataires approuvés, Email Queue, Send After, scheduler/worker, réception unique observée. Les reprises ne créent pas de nouveaux messages ; pas de renvoi des files historiques. |

Après lecture des sources, rattacher chaque cas à la vraie fonction, au DocType et au test automatisé correspondant. Un test simulant une règle inventée ne valide pas l’intégration. Conserver uniquement identifiants synthétiques, résultats et références de commits dans les preuves publiques.

## Déploiement : points d’arrêt obligatoires

1. **Contrat réel.** Importer les sources et dépendances ; relever versions Frappe/ERPNext/apps, commits installés, schémas, hooks, Workflow/Server Scripts, permissions et producteurs de notifications. Comparer avec le commit candidat immuable, pas seulement un nom de branche. Aucune activation tant que paiement, profil et mapping d’affectation restent inconnus.
2. **Sauvegarde vérifiée.** Dans une session administrateur autorisée, exécuter `bench --site <site-technique> backup --with-files` selon les capacités Frappe Cloud ; conserver base, fichiers publics/privés et configuration nécessaire chiffrés hors Git. Vérifier intégrité et restauration dans un staging isolé compatible. Une sauvegarde seulement créée, sans restauration testée, ne valide pas ce point.
3. **Staging isolé.** Neutraliser les sorties réelles et les webhooks commerciaux avant démarrage ; utiliser comptes, données et SMTP de test. Installer le SHA candidat, comparer dépendances, exécuter migrations, construction des ressources et nettoyage du cache suivant la plateforme. Conserver les résultats des migrations et la matrice de permissions avant/après. Le pont reste désactivé sauf recette distincte explicitement approuvée.
4. **Recette.** Exécuter H01–H09 sur les sources intégrées et les seuls tests existants affectés par les modifications. Vérifier les refus via appels serveur et interfaces natives accessibles, pas seulement par masquage JavaScript. Tout échec de confidentialité, paiement, migration ou restauration bloque la livraison.
5. **Approbation.** Présenter le SHA, les différences, migrations, permissions, routes modifiées, preuves de staging, fenêtre d’intervention et procédure de retour. Toute modification du compte existant nécessite une approbation séparée indiquant exactement le rôle/profil à ajouter ; aucune réinitialisation, duplication ou attribution de System Manager. Aucun script de ce document ne modifie ce compte.
6. **Production autorisée seulement.** Refaire une sauvegarde vérifiée et capturer le SHA initial avant installation du SHA approuvé. Appliquer uniquement les migrations validées. Après redémarrage, vérifier versions/commit, route et session, refus Guest, permissions, état du scheduler et des files. Un parcours avec ticket et destinataires approuvés exige son autorisation propre ; l’authentification du technicien se fait par lui-même sans transmettre son mot de passe.

## Retour arrière et preuve finale

Déclencheurs : accès transversal, intervention sans condition de paiement requise, migration échouée, erreur de session bloquante ou notifications inattendues. Suspendre le nouveau parcours par le mécanisme revu en staging ; pour le pont distinct, désactiver `ss97_ticket_bridge.enabled`. Conserver journaux expurgés et reçus, ne pas purger les tickets, affectations ou e-mails et ne pas vider la file.

Revenir au SHA sûr identifié avant livraison par le mécanisme Frappe Cloud validé. Un retour de code ne constitue pas une migration inverse : si le schéma n’est plus compatible, maintenir le parcours indisponible et faire approuver une restauration avec traitement explicite des écritures intervenues depuis la sauvegarde. Ne jamais réactiver une version du pont qui fait confiance aux ToDo seuls. Restaurer uniquement les permissions/configurations effectivement modifiées, après revue administrative.

Après retour : vérifier commit, cache, disponibilité du parcours antérieur, refus d’accès, données conservées et état des files sans renvoi massif. La décision finale doit distinguer tests de laboratoire, staging et production, avec résultat, SHA et preuve pour chacun. Aucune de ces opérations serveur n’a été exécutée par cette préparation.

## Sources technicien reçues le 21 octobre 2026

L’archive privée de 104 fichiers identifie enfin le générateur de la route commerciale : les spécifications de `/espace-technicien/tickets` délèguent à `integrations.ss97_technician_etape6.deploy.page_tickets(P)`. Ce module est absent de l’archive ; aucune équivalence avec `/ss97-dev-technician` n’est présumée. Le registre récupéré est importable sans charger les dépendances de toutes les pages.

Le générateur `integrations/ss97_technician_operations/cockpit_start_api.py` est récupéré et durci : garde POST/session active, rôle canonique et affectation approuvée via le pont, décision métier liée à chaque action, refus d’auto-affectation, suppression du raccourci de clôture « test », durée calculée côté serveur et absence de commit intermédiaire. Les codes de session distante ne sont ni retournés ni journalisés. Effacer les champs d’une session ne prouve pas sa révocation par un outil distant. Le Server Script généré reste **désactivé**, sans installation automatique.

Dépendances encore requises : `integrations/ss97_technician_etape6/deploy.py` (`page_tickets`), `integrations/ss97_gwen_notifications/wa_block.py` (`WA_FUNCS`), et, pour le module de pages fourni dans l’archive privée, `integrations/ss97_notifications/center.py` (`notif_assets`) et `integrations/ss97_website/mission5_recruit.py` (`THEME`). Le fournisseur métier du pont doit encore être raccordé aux règles réelles de paiement et aux autorisations de transition ; le catalogue seul ne peut pas autoriser une intervention.

Validation locale ciblée : 18 tests natifs du cycle historique, 14 scénarios du générateur sous RestrictedPython avec façade fictive et 28 tests historiques. Les scénarios simulés ne valident ni un paiement, ni la livraison Gwen/WhatsApp, ni le rendu de la route commerciale. Les scripts d’administration des comptes et les données personnelles de l’archive restent hors Git. Aucune modification Frappe Cloud, installation ou migration n’a été effectuée. Les points d’arrêt et le retour arrière ci-dessus restent obligatoires.

## Dernier lot reçu : contrôleur de page effectivement retrouvé

`SS97_DERNIER_LOT.zip` contient 19 fichiers, dont le rapport. Contrairement au chemin recherché par ce rapport (`deploy/page_tickets.py`), `page_tickets(P)` existe dans `ss97_technician_etape6/deploy.py`. La fonction originale est récupérée dans le dépôt sans les effets de bord du module de déploiement (création de répertoire, modification de stdout, SDK et commandes de publication). Son rendu est testé avec un contrat P et un shell simulés ; aucun rendu commercial complet n’est revendiqué.

Trois modules applicatifs sont intégrés sélectivement : le générateur ci-dessus, le thème THEME de `ss97_website/mission5_recruit.py`, et la présentation/routage de `ss97_notifications/center.py`. Les notifications de consultation utilisent uniquement `ticket_bridge.api.get_notifications`, dont le serveur revérifie utilisateur et tickets autorisés. Les routes externes, chemins ambigus et injections de paramètres dans les identifiants sont refusés/encodés. Le JavaScript utilise textContent, efface les résultats après refus et ne modifie ni ToDo ni User. Les producteurs SDK historiques et les écritures génériques ne sont pas importés. Cette présentation ne prouve pas l’envoi automatique d’un e-mail.

Les nouvelles copies de workflow_logic.py, specs.py et fix_priority.py ne remplacent pas les versions déjà corrigées. Le tableau de bord privé historique contient des écritures directes `frappe.client.save` sur Issue ; son module `portals` et son JavaScript ne sont pas activés par ce lot. Le raccordement de ses lectures et mutations aux API autorisées reste nécessaire, ainsi que les règles réelles de paiement/transition et la dépendance `integrations/ss97_gwen_notifications/wa_block.py`. Le rapport mentionne `ss97_pwon_notifications` : ce nom ne remplace pas le chemin importé par le cockpit.

Tests de ce lot : `python tools/test_last_technician_dependencies.py` (8 tests, dont exécution JavaScript Node avec DOM simulé, succès puis session refusée) ; `tools/test_recovered_technician_portal.py` (14 tests isolés, également sous RestrictedPython sur audit.localhost). Aucun essai sur Cloud, SMTP, Stripe Test ou session commerciale. Le candidat reste bloqué pour activation ; aucune sauvegarde/restauration du serveur n’est confirmée et aucune approbation de déploiement n’est sollicitée à ce stade.
