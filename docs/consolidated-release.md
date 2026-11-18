# Candidat consolidé Frappe / ERPNext v16

Branche de livraison unique : `consolidation/technician-frappe-v16`. Elle descend de `f0be9b5` et contient par ascendance les corrections `0ecc174`, `e2307a1`, `54d66a0`, `abdfa20` et `2ae1128`, sans réécriture, fusion de PR ou suppression d’une branche existante. Les deux rapports locaux non suivis ne sont pas inclus. La PR #3 reste distincte. Ce document fixe l’état courant ; les comptes rendus historiques restent des preuves de leurs exécutions respectives.

## Code et interfaces consolidés

- Les sources historiques client/types restent dans `integrations/ss97_client_support/` et `integrations/ss97_client_ops/`, avec leur API propriétaire et le garde POST natif.
- Le pont natif est dans `softsystem97/integrations/ticket_bridge/` : session/rôle, périmètre client, approbation protégée ToDo, contrôle de statut, journal d’idempotence et notifications. Son raccordement historique reste désactivé par défaut et exige un fournisseur métier réel. Aucun rôle ni User n’est attribué automatiquement.
- Le transport Stripe existant est réutilisé dans `stripe/payment_sync.py` et `stripe/webhook.py`. Une session Checkout `complete` avec `payment_status=unpaid` ne confirme plus un paiement. Un montant partiellement reçu ne remplace pas le statut `paid` d’une facture Stripe. Les états refusés et remboursés suivent les producteurs existants ; les événements d’annulation/expiration non pris en charge sont ignorés, sans marquage payé. Aucune règle privée d’annulation/remboursement d’intervention n’est inventée.
- Les livraisons d’un même événement sont sérialisées par un verrou transactionnel du journal `SS97 Stripe Event`, dont `stripe_event_id` est unique dans le DocType existant. Une collision d’insertion, un deadlock ou conflit de snapshot donne un conflit réessayable, jamais un acquittement de succès sans reçu. Une reprise correctement signée ne redispatche pas l’événement. Une erreur ancienne ne peut écraser le succès d’une reprise concurrente. Cela ne démontre pas un rapprochement comptable unique entre plusieurs événements Stripe distincts.
- La réussite du traitement exige une journalisation réussie ; une absence de journal/migration bloque le traitement. Les messages bruts d’exception ne sont plus recopiés dans les journaux Stripe concernés, et la réponse d’erreur publique ne chaîne pas l’exception amont. Les identifiants de facture/événement restent dans le journal administratif prévu, pas dans un export public.
- Paiements et tickets utilisent maintenant la même résolution client : compte et rôle Customer actifs, association Portal User explicite et unique vers un Customer actif. Les notifications Stripe n’utilisent plus un simple e-mail client comme solution de repli.

## Validation exécutée

Application Soft System 97 : version déclarée `1.0.0`. Environnement de laboratoire : Frappe 16.52.0 / ERPNext 16.51.1 ; uniquement données fictives. Depuis le bench, avec son interpréteur :

```sh
env/bin/python /workspace/softsystem97/tools/run_local_tests.py --site audit.localhost
env/bin/python /workspace/softsystem97/tools/test_historical_ticket_sources.py --frappe-site audit.localhost
env/bin/python /workspace/softsystem97/tools/validate_ticket_bridge_http.py --site audit.localhost
env/bin/python /workspace/softsystem97/tools/test_ticket_bridge_browser.py --chromium /usr/bin/chromium
env/bin/python /workspace/softsystem97/tools/validate_local_mail.py --site audit.localhost --bridge
env/bin/python /workspace/softsystem97/tools/validate_local_mail.py --site audit.localhost
```

La suite PowerShell hors ligne a aussi été exécutée avec PowerShell 7 local et ses répertoires XDG dans le workspace : `tools/powershell/tests/Test-SS97Scripts.ps1`.

| Suite | Résultat | Portée et preuve locale dans les logs du bench |
|---|---|---|
| Frappe unitaire/intégration | 94 réussis, 0 échec | `phase1-frappe.log` ; vrais Issue, ToDo, journal Stripe, concurrence sur connexions MariaDB distinctes. Politique métier et traitement financier simulés. |
| Sources historiques | 17 réussis, 0 échec | `phase1-historical.log` ; safe_exec réel avec façade fictive et assertions Node. |
| HTTP natif | 15 réussis | `phase1-http.log` ; sessions/CSRF/routage/API du pont, pas la route historique. |
| Chromium | 13 réussis | `phase1-browser.log` ; interface réelle, réponses HTTP simulées. |
| PowerShell | 29 assertions réussies | `phase1-powershell.log` ; entièrement hors ligne. |
| Stripe externe en mode Test | Non exécuté | Aucune clé API/secrète Test disponible dans l’environnement ou la configuration du laboratoire ; présence vérifiée sans afficher/déchiffrer de clé. |
| Livraison SMTP autonome du pont | 6 messages reçus une seule fois | `phase1-smtp.log` ; vrai scheduler → worker → SMTP local, sujets et destinataires contrôlés, nouvelle exécution complète de `frappe.email.queue.flush`. |
| Notification native SMTP | 1 message reçu une seule fois | `phase1-native-smtp.log` ; même chaîne réelle, sans appel manuel à flush. |

Toutes les suites du tableau ont été réexécutées pour cette livraison ; les journaux sont dans `/workspace/.audit-v16/logs/`. Le contrôle SMTP utilise un Redis temporaire sur boucle locale sans persistance, refuse une file mail préexistante non vide et un compte sortant actif, puis vérifie que la file Redis d’origine et la configuration sont inchangées. Il ne purge ni ne renvoie les anciens travaux. Le défaut antérieur du banc SMTP (travaux anciens dans sa file partagée) est ainsi isolé ; cela ne valide pas le fournisseur SMTP de staging ou de production. Exécuter ces deux sondes exclusivement sur un site jetable `audit.*` ou `test_*` avec `allow_tests`, sans autre test simultané.

Les premières exécutions historiques des nouveaux tests avaient révélé deux contextes de réponse manquants dans les fixtures et un conflit de snapshot MariaDB. Les fixtures utilisent désormais une réponse par requête ; le test de snapshot vérifie explicitement rollback/reprise sans dispatch. Les résultats ci-dessus sont ceux de la version finale corrigée. Aucun de ces tests ne valide un paiement Stripe externe ou le compte réel.

## Dépendances restantes et état par étape

| Étape | Disponible et intégré | Validation restante |
|---|---|---|
| Client → Issue | API client historique et création bornée du pont | Parcours sécurisé historique de création : le Server Script client interdit sa création directe. Workflow privé requis. |
| Stripe → facture | Webhook signé, contrôles montant/devise, journal et producteurs existants | Stripe Test réel, schéma personnalisé Sales Invoice et rapprochement fiable facture ↔ Issue. |
| Paiement → affectation | Contrat serveur obligatoire du mode historique | `softsystem97/integrations/ticket_bridge/business_policy.py`, à implémenter depuis le vrai `integrations/ss97_tickets/workflow_logic.py`. |
| Affectation → technicien | Rôle canonique et double contrôle champ/approbation en mode historique | Schéma réel `Issue.ss97_technician` : seul Link User est pris en charge ; tout profil différent impose une adaptation revue. |
| Intervention → clôture | API natives bornées, transactions, reçus et historique | Statuts/règles du workflow privé et contrôleur de `/espace-technicien/tickets`. Aucun fichier de ce contrôleur n’a été retrouvé ; son nom ne peut pas être inventé. |
| Notifications | Destinataires bornés et création/file testées | Chaîne scheduler/worker/SMTP local effective validée ; fournisseur et destinataires de staging encore à approuver et tester. |

L’archive reçue contient toujours uniquement `client_ticket_api.py`, `ticket_workspace.py` et `ticket_types.py` ; `ticket_workspace.py` génère le détail client. Les API `ss97_ticket_confirm_payment`, `ss97_ticket_public_detail`, `ss97_ticket_public_message`, `ss97_ai_agent_dialogue_turn` et le SDK `migrate_odoo_erpnext/erpnext_client.py` restent absents. Le patch public Ticket Libre de `fix/softsystem97-production-bugs` reste sur sa branche, avec ses dépendances Server Script non fournies. Le contrôleur de développement `/ss97-dev-technician` ne remplace pas la route historique.

## Validation Frappe Cloud et retour arrière

1. Un administrateur autorisé doit rendre disponible un staging isolé du site réel avec son code et ses schémas exportés sans données clients/secrets : contrôleur fichier ou Web Page de la route, API/Server Scripts, Workflow, Custom Field Issue/Sales Invoice, rôles/DocPerm et profils. Un inventaire de laboratoire ne suffit pas.
2. Vérifier versions/installations et SHA de référence ; sauvegarder base/fichiers/configurations privés hors Git et vérifier une restauration isolée. Le staging doit employer des données fictives, une sortie mail contrôlée et uniquement les clés Stripe Test configurées dans son interface privée. Ne pas transmettre ces clés dans une PR ou une conversation.
3. Installer le SHA de consolidation approuvé en staging ; `bench --site <staging> migrate`, construction des ressources, cache et redémarrage selon Frappe Cloud. Vérifier le journal protégé du pont et l’index unique `SS97 Stripe Event.stripe_event_id`. Aucun nouveau patch de migration n’est ajouté par rapport à `f0be9b5`, ni aucune activation automatique. Le lot complet ajoute toutefois le DocType SS97 Ticket Bridge Event et ses champs d’approbation par rapport à main : la migration et la vérification des permissions sont obligatoires.
4. Fournir le vrai adaptateur métier/lien facture-ticket et raccorder le vrai contrôleur. Ne pas désactiver les garde-fous Workflow/Server Scripts pour passer une recette. Confirmer le rôle et le type réel du champ avant toute activation du mode historique sur staging.
5. Avec comptes fictifs : création → paiement Stripe Test effectivement reçu et rapproché → affectation administrative → accès technicien A/refus B → intervention → clôture → suivi client et livraison mail contrôlée. Tester aussi paiement refusé/annulé/remboursé, doublons/reprises concurrentes, CSRF/session expirée et échec de notification. Conserver SHA, résultats et identifiants synthétiques.
6. Retour arrière : suspendre les nouveaux parcours et désactiver le pont ; conserver reçus, tickets et files, sans purge ni renvoi massif. Revenir au SHA sûr revu seulement si le schéma est compatible. Sinon approuver une restauration tenant compte des écritures postérieures ; ne pas réactiver une ancienne version vulnérable aux ToDo seuls ou dépourvue du contrôle métier. Tester ce retour en staging avant de demander une approbation de production distincte.

État de livraison : candidat cohérent pour revue de code et validation technique isolée ; portail historique, Stripe Test externe et production non validés. Aucun compte réel, mot de passe, clé API ou donnée de production modifié ; aucune fusion ni aucun déploiement.

### Recette administrative précise (à exécuter seulement après autorisation)

Aucune session administrative Frappe Cloud, URL de staging ou configuration Stripe Test n’est disponible dans cet environnement. Les commandes ci-dessous sont préparées, pas exécutées sur Frappe Cloud. Dans le tableau de bord officiel `https://frappecloud.com/dashboard`, sélectionner le staging autorisé ; utiliser son accès SSH/console officiel si le plan le permet. `<staging>` désigne son nom technique réel, pas le domaine de production.

1. Consigner l’application `softsystem97` version `1.0.0`, la branche `consolidation/technician-frappe-v16` et le SHA approuvé de livraison. Avant installation, relever les versions et la révision actuellement installées :

   ```sh
   bench version
   bench --site <staging> list-apps
   git -C apps/softsystem97 rev-parse HEAD
   ```

   Si Frappe Cloud ne conserve pas `.git`, relever la révision du déploiement dans le tableau de bord. La référence de laboratoire est Frappe 16.52.0 / ERPNext 16.51.1 ; une autre version impose une validation de compatibilité, pas une affirmation automatique.

2. Sauvegarder et tester une restauration isolée avant toute migration : `bench --site <staging> backup --with-files`, ou sauvegarde équivalente du tableau de bord. Conserver base, fichiers publics/privés et configuration nécessaire au déchiffrement dans un stockage administratif privé hors Git. Consigner le SHA de retour, la sauvegarde et la preuve de restauration. Aucun export contenant des clients ou secrets ne doit être joint à une PR.

3. Dans `bench --site <staging> console`, relever uniquement les métadonnées utiles :

   ```python
   frappe.db.get_value("Custom Field", {"dt": "Issue", "fieldname": "ss97_technician"}, ["fieldtype", "options"], as_dict=True)
   frappe.db.exists("Role", "SS97 Technician")
   frappe.get_all("Web Page", filters={"route": "espace-technicien/tickets"}, fields=["name", "route"])
   ```

   Si le champ n’est pas un Custom Field, consulter `frappe.get_meta("Issue").get_field("ss97_technician")` et seulement ses attributs `fieldtype`/`options`. Le mode historique exige Link → User ; un lien vers un profil exige son adaptateur réel. L’absence de Web Page ne prouve pas l’absence d’une route fichier : inspecter le vrai `www` et les hooks des applications installées. Récupérer aussi le workflow et les API historiques énumérés plus haut. Ne pas transmettre d’enregistrements clients ni le contenu des erreurs/e-mails.

4. Après approbation du déploiement **en staging uniquement**, installer le SHA via le mécanisme Frappe Cloud prévu, puis exécuter ou vérifier les opérations équivalentes :

   ```sh
   bench --site <staging> migrate
   bench build --app softsystem97
   bench --site <staging> clear-cache
   ```

   Redémarrer les processus via la plateforme ; vérifier permissions du journal protégé et unicité Stripe. Le pont reste désactivé tant que le vrai fournisseur métier, le lien facture-ticket, le contrôleur et le schéma ne sont pas compatibles. Pour examiner la préparation du rôle sans écriture :

   ```python
   from softsystem97.integrations.ticket_bridge.install import prepare
   prepare(role_name="SS97 Technician")  # dry_run par défaut
   ```

   Création du rôle et attribution uniquement à des utilisateurs fictifs sur staging après revue des changements ; aucun rôle administratif pour le technicien. Ne pas désactiver les garde-fous de compatibilité des Workflow, Server Scripts et notifications pour forcer l’activation.

5. Configurer Stripe **Test** et la signature webhook dans l’interface privée de staging ; aucun secret dans les commandes, Git ou la conversation. Choisir un compte sortant de test ou une boîte de capture approuvée. Vérifier Send After, compte sortant, Email Queue, scheduler, worker et livraison ; ne jamais vider ni relancer massivement une file existante. Les sondes locales ci-dessus ont des garde-fous de site jetable : ne pas les contourner sur un site Cloud.

6. Recette avec deux techniciens fictifs et un client fictif : création/accusé, paiement absent refusé, paiement Stripe Test confirmé et rapproché, affectation administrative unique, ticket visible uniquement pour A, refus pour B/anonyme/sans rôle/désactivé, intervention autorisée, transitions interdites refusées, clôture et historique client. Contrôler session expirée/CSRF, événements répétés/concurrents, paiement refusé/annulé/remboursé et notifications sans doublon aux seuls destinataires approuvés. Les événements non pris en charge ne doivent jamais autoriser une intervention. Conserver SHA, identifiants fictifs et résultats sans corps de messages.

7. Critère d’acceptation : aucun accès croisé, aucune intervention sans preuve serveur fiable de paiement, aucun double traitement, toutes les transitions métier réelles respectées, notifications effectivement reçues, restauration démontrée. Une politique métier simulée ne satisfait pas ce critère. En cas d’échec, désactiver le pont et suivre le retour arrière ci-dessus ; toute restauration doit tenir compte des écritures depuis la sauvegarde. La production reste soumise à une approbation distincte.
