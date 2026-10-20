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

Environnement de laboratoire : Frappe 16.52.0 / ERPNext 16.51.1 ; uniquement données fictives. Depuis le bench, avec son interpréteur :

```sh
env/bin/python /workspace/softsystem97/tools/run_local_tests.py --site audit.localhost
env/bin/python /workspace/softsystem97/tools/test_historical_ticket_sources.py --frappe-site audit.localhost
env/bin/python /workspace/softsystem97/tools/validate_ticket_bridge_http.py --site audit.localhost
env/bin/python /workspace/softsystem97/tools/test_ticket_bridge_browser.py --chromium /usr/bin/chromium
```

La suite PowerShell hors ligne a aussi été exécutée avec PowerShell 7 local et ses répertoires XDG dans le workspace : `tools/powershell/tests/Test-SS97Scripts.ps1`.

| Suite | Résultat | Portée et preuve locale dans les logs du bench |
|---|---|---|
| Frappe unitaire/intégration | 94 réussis, 0 échec | `consolidated-frappe.log` ; vrais Issue, ToDo, journal Stripe, concurrence sur connexions MariaDB distinctes. Politique métier et traitement financier simulés. |
| Sources historiques | 17 réussis, 0 échec | `consolidated-historical.log` ; safe_exec réel avec façade fictive et assertions Node. |
| HTTP natif | 15 réussis | `consolidated-http.log` ; sessions/CSRF/routage/API du pont, pas la route historique. |
| Chromium | 13 réussis | `consolidated-browser.log` ; interface réelle, réponses HTTP simulées. |
| PowerShell | 29 assertions réussies | `consolidated-powershell.log` ; entièrement hors ligne. |
| Stripe externe en mode Test | Non exécuté | Aucune clé API/secrète Test disponible dans l’environnement ou la configuration du laboratoire ; présence vérifiée sans afficher/déchiffrer de clé. |
| Livraison SMTP autonome | Non validée | Échec antérieur conservé : six messages en file, zéro reçu dans le délai. Pas de nouveau renvoi. |

Les premières exécutions des nouveaux tests ont révélé deux contextes de réponse manquants dans les fixtures et un conflit de snapshot MariaDB. Les fixtures utilisent désormais une réponse par requête ; le test de snapshot vérifie explicitement rollback/reprise sans dispatch. Les résultats ci-dessus sont ceux de la version finale corrigée. Aucun de ces tests ne valide un paiement Stripe externe ou le compte réel.

## Dépendances restantes et état par étape

| Étape | Disponible et intégré | Validation restante |
|---|---|---|
| Client → Issue | API client historique et création bornée du pont | Parcours sécurisé historique de création : le Server Script client interdit sa création directe. Workflow privé requis. |
| Stripe → facture | Webhook signé, contrôles montant/devise, journal et producteurs existants | Stripe Test réel, schéma personnalisé Sales Invoice et rapprochement fiable facture ↔ Issue. |
| Paiement → affectation | Contrat serveur obligatoire du mode historique | `softsystem97/integrations/ticket_bridge/business_policy.py`, à implémenter depuis le vrai `integrations/ss97_tickets/workflow_logic.py`. |
| Affectation → technicien | Rôle canonique et double contrôle champ/approbation en mode historique | Schéma réel `Issue.ss97_technician` : seul Link User est pris en charge ; tout profil différent impose une adaptation revue. |
| Intervention → clôture | API natives bornées, transactions, reçus et historique | Statuts/règles du workflow privé et contrôleur de `/espace-technicien/tickets`. Aucun fichier de ce contrôleur n’a été retrouvé ; son nom ne peut pas être inventé. |
| Notifications | Destinataires bornés et création/file testées | Scheduler/worker/SMTP effectifs et destinataires de staging approuvés. |

L’archive reçue contient toujours uniquement `client_ticket_api.py`, `ticket_workspace.py` et `ticket_types.py` ; `ticket_workspace.py` génère le détail client. Les API `ss97_ticket_confirm_payment`, `ss97_ticket_public_detail`, `ss97_ticket_public_message`, `ss97_ai_agent_dialogue_turn` et le SDK `migrate_odoo_erpnext/erpnext_client.py` restent absents. Le patch public Ticket Libre de `fix/softsystem97-production-bugs` reste sur sa branche, avec ses dépendances Server Script non fournies. Le contrôleur de développement `/ss97-dev-technician` ne remplace pas la route historique.

## Validation Frappe Cloud et retour arrière

1. Un administrateur autorisé doit rendre disponible un staging isolé du site réel avec son code et ses schémas exportés sans données clients/secrets : contrôleur fichier ou Web Page de la route, API/Server Scripts, Workflow, Custom Field Issue/Sales Invoice, rôles/DocPerm et profils. Un inventaire de laboratoire ne suffit pas.
2. Vérifier versions/installations et SHA de référence ; sauvegarder base/fichiers/configurations privés hors Git et vérifier une restauration isolée. Le staging doit employer des données fictives, une sortie mail contrôlée et uniquement les clés Stripe Test configurées dans son interface privée. Ne pas transmettre ces clés dans une PR ou une conversation.
3. Installer le SHA de consolidation approuvé en staging ; `bench --site <staging> migrate`, construction des ressources, cache et redémarrage selon Frappe Cloud. Vérifier le journal protégé du pont et l’index unique `SS97 Stripe Event.stripe_event_id`. Aucun nouveau patch de migration n’est ajouté par rapport à `f0be9b5`, ni aucune activation automatique. Le lot complet ajoute toutefois le DocType SS97 Ticket Bridge Event et ses champs d’approbation par rapport à main : la migration et la vérification des permissions sont obligatoires.
4. Fournir le vrai adaptateur métier/lien facture-ticket et raccorder le vrai contrôleur. Ne pas désactiver les garde-fous Workflow/Server Scripts pour passer une recette. Confirmer le rôle et le type réel du champ avant toute activation du mode historique sur staging.
5. Avec comptes fictifs : création → paiement Stripe Test effectivement reçu et rapproché → affectation administrative → accès technicien A/refus B → intervention → clôture → suivi client et livraison mail contrôlée. Tester aussi paiement refusé/annulé/remboursé, doublons/reprises concurrentes, CSRF/session expirée et échec de notification. Conserver SHA, résultats et identifiants synthétiques.
6. Retour arrière : suspendre les nouveaux parcours et désactiver le pont ; conserver reçus, tickets et files, sans purge ni renvoi massif. Revenir au SHA sûr revu seulement si le schéma est compatible. Sinon approuver une restauration tenant compte des écritures postérieures ; ne pas réactiver une ancienne version vulnérable aux ToDo seuls ou dépourvue du contrôle métier. Tester ce retour en staging avant de demander une approbation de production distincte.

État de livraison : candidat cohérent pour revue de code et validation technique isolée ; portail historique, Stripe Test externe et production non validés. Aucun compte réel, mot de passe, clé API ou donnée de production modifié ; aucune fusion ni aucun déploiement.
