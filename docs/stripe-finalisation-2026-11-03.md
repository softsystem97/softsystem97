# SS97 — Finalisation Stripe, 3 novembre 2026

Base inspectée : `feature/ss97-final-integration`, commit `a7254f2150259b26fd0da912cc49cd0e3d8375e4`.
Branche de correction : `fix/ss97-stripe-secure-accounting-20261103`.

Le code est préparé pour validation en préproduction. Une livraison signée **par Stripe** vers Frappe Cloud et le parcours de paiement externe complet restent obligatoires. Les signatures synthétiques des tests locaux ne prouvent pas cette livraison externe.

## Corrections

- Signature HMAC-SHA256 sur les octets bruts, fenêtre de cinq minutes, rejet des signatures incorrectes/expirées, types JSON stricts, codes HTTP réessayables préservés.
- Séparation explicite TEST/LIVE, clés API distinctes des secrets webhook, priorité configuration serveur/environnement puis champs Password du Single. Une clé restreinte `rk_test_`/`rk_live_` est acceptée. Les secrets ne sont pas retournés par les API de contrôle.
- Un événement TEST ne peut écrire que si `allow_tests=1` **et** `ss97_stripe_test_site=true` sur un site distinct de `app.softsystem97.com`. Le serveur de production ne doit donc pas recevoir les scénarios comptables TEST.
- Verrou transactionnel du journal par événement, verrou de facture entre événements distincts, identifiant de transaction unique sur Payment Entry, allocation exacte et absence de remise/écart automatique.
- ERPNext crée et soumet lui-même le Payment Entry et les écritures GL. Aucun champ `outstanding_amount` n'est forcé par SS97. Le compte de passage Stripe doit être bancaire, actif, de la société et de la devise de la facture.
- Utilisateur de service comptable configuré, actif, avec droits natifs Accounts User/Accounts Manager. Retour à l'identité HTTP initiale même en cas d'erreur. Aucun rôle comptable ajouté au client ou au technicien.
- Montants convertis selon l'unité mineure de la devise ; montant nul réellement reçu conservé ; plus de tolérance de cinq centimes. Les factures POS, avoirs, règlements multidevises et remises implicites sont refusés par ce parcours.
- Relations Stripe persistées prioritaires. Un fallback metadata doit correspondre au client Stripe et au mode de la facture ; les relations contradictoires sont rejetées. Les factures Stripe récentes passent par Invoice Payments pour retrouver le PaymentIntent ; les paiements mixtes/crédits exigent un rapprochement manuel.
- Notification portail durable dans la même transaction que le règlement. Une erreur de notification provoque rollback et reprise, sans seconde comptabilisation ni second reçu.
- Échec tardif ignoré sur facture déjà réglée. Remboursement/litige bloque les interventions ; aucune annulation de pièce soumise, aucun avoir inventé. Le comptable établit l'avoir et le règlement de remboursement dans ERPNext et les rapproche de Stripe. `refund_pending_review` indique ce travail restant.
- États d'abonnement conservés sur Customer ; contrat lié seulement si son client correspond. Les événements obsolètes ne ressuscitent pas un abonnement annulé. Un abonnement actif n'est jamais une preuve de règlement de facture.
- Le portail crée Checkout pour la facture reliée au ticket du client connecté. Le montant provient du serveur. Le retour navigateur ne marque aucune facture payée. Le rendu « payé » requiert la preuve serveur.
- Le hook natif Issue protège aussi les écritures Desk/REST des tickets liés à une facture. Le pont conserve ses contrôles d'acteur, d'affectation et de métier.
- ERPNext v16 protège les champs staff d'Issue : les écritures autorisées du pont utilisent un compte Support Team configuré, sans donner d'accès Desk aux utilisateurs portail. La clôture native des affectations lors de la résolution reste respectée ; le technicien perd alors sa capacité et la clôture finale appartient au personnel autorisé.

## Événements

| Événement | Traitement |
|---|---|
| `checkout.session.completed` | Paiement seulement si `payment_status=paid`, facture liée et montant/devise exacts |
| `payment_intent.succeeded` | Règlement ERPNext avec `amount_received` et transaction unique |
| `payment_intent.payment_failed` | Échec et notification, sans rétrograder un règlement confirmé |
| `invoice.paid` | Facture ERPNext liée ; PaymentIntent via Invoice Payments ; paiement hors ligne/mixte à rapprocher |
| `invoice.payment_failed` | Échec informatif, sans faux règlement |
| `charge.refunded` | Blocage, notification et rapprochement comptable requis |
| `customer.subscription.created` | Identifiant/état sur le client et contrat autorisé |
| `customer.subscription.updated` | Mise à jour avec protection contre événements obsolètes |
| `customer.subscription.deleted` | État annulé, sans annuler de pièce comptable |
| `checkout.session.async_payment_succeeded` | Même contrôle comptable que Checkout payé |
| `checkout.session.async_payment_failed` | Échec différé |
| `charge.dispute.created` | Blocage et revue comptable |

Les trois derniers complètent les neuf événements demandés pour les moyens de paiement différés et les litiges. Ne souscrire que les événements traités.

## Constats externes vérifiés

- Compte Stripe consulté : `acct_1Tz8rBIahdtPkkQZ`.
- Destination TEST `we_1UX3FCIahdtPkkQZD2cBFtVN` : activée, neuf événements demandés, snapshot API `2026-06-24.dahlia`.
- Destination LIVE `we_1UWzr0IahdtPkkQZ23sAqkc3` : activée, uniquement `checkout.session.completed`, même version de snapshot.
- Les deux pointent actuellement vers `https://app.softsystem97.com/api/method/softsystem97.integrations.stripe.webhook.stripe_webhook`.
- Lecture Stripe uniquement : destinations, clés et activation LIVE inchangées.
- HTTP public : accueil 200 ; requête webhook sans événement valide 403. Ce refus ne valide pas le parcours de paiement.
- Aucun événement `payment_intent.succeeded` ou `checkout.session.completed` trouvé dans la lecture des événements TEST récents au moment de l'audit.
- Frappe ouvre l'écran de connexion ; aucune session administrateur disponible, aucun identifiant Frappe fourni à cet environnement. Journal de production, secrets et version réellement déployée non consultables.

## Déploiement Frappe Cloud — préproduction d'abord

1. Créer/sélectionner un site jetable `audit.…` ou `test_…` avec base séparée. Déployer la branche de cette PR sur ce site, avec Frappe/ERPNext v16. Installer la dépendance Python Stripe définie dans `pyproject.toml` via le déploiement habituel. Ne pas remplacer le framework ni la branche de production.
2. Exécuter `bench --site <site-test> migrate`, puis `bench build --app softsystem97` et `bench --site <site-test> clear-cache`, ou les étapes équivalentes du déploiement Frappe Cloud. Le patch post-model-sync est idempotent ; `after_install` couvre une installation neuve. En cas de valeurs de transaction déjà dupliquées, arrêter et rapprocher les données ; ne pas supprimer les pièces.
3. Configurer sur **ce site de test** `STRIPE_MODE="test"`, `PAYMENTS_LIVE_ENABLED=0`, `allow_tests=1`, `ss97_stripe_test_site=true`. Préserver les autres paramètres serveur.
4. Dans `SS97 Stripe Config`, renseigner le compte bancaire de passage et un utilisateur de service comptable existant avec les droits natifs nécessaires. Vérifier la société, la devise et les User Permissions. Dans le dictionnaire serveur existant `ss97_ticket_bridge`, ajouter `writer_user` (compte Support Team actif, System User) et conserver/valider les autres paramètres et le fournisseur métier. `enforce_paid_interventions=true` est requis pour la validation de livraison du pont.
5. Remplacer les clés TEST et secrets TEST anciennement exposés. Saisir les nouvelles valeurs directement dans les champs Password / configuration protégée Frappe Cloud. Ne jamais les envoyer dans le chat, un commit ou une commande historisée. `test_secret_key` / `STRIPE_TEST_SECRET_KEY` est la clé API ; `test_webhook_secret` / `STRIPE_TEST_WEBHOOK_SECRET` est le secret de la destination signant pour **ce site**. Les identifiants clients Stripe issus d'une copie LIVE doivent être revus avant toute tentative TEST.
6. Créer une destination Stripe TEST dédiée au site de test, snapshot `2026-06-24.dahlia`, avec les douze événements du tableau. Le secret d'une autre destination ou celui de Stripe CLI n'est pas interchangeable. La clé API TEST doit permettre les opérations utilisées : Checkout Sessions et Customers en écriture, PaymentIntents / Invoice Payments en lecture pour rapprochement.
7. Mettre à jour les quatre fonctions de paiement de la page ticket existante, sans remplacer son HTML :

   ```sh
   bench --site <site-test> execute softsystem97.integrations.stripe.portal_install.patch_existing_page --kwargs '{"dry_run":true}'
   bench --site <site-test> execute softsystem97.integrations.stripe.portal_install.patch_existing_page --kwargs '{"dry_run":false}'
   ```

   Si la page ne correspond pas au script connu, arrêter et revoir sa version courante. Ce correctif ne republie aucune autre page.

8. Préparer une facture de test EUR soumise, non POS, reliée à un ticket du même client par `Sales Invoice.ss97_linked_issue`. Les relations et le mode Stripe sont gérés côté serveur. Pour un abonnement, lier explicitement chaque facture de période à son identifiant de facture Stripe ; ce lot ne fabrique pas de factures de renouvellement à partir d'un simple événement.
9. Lancer les tests natifs depuis le bench : `env/bin/python apps/softsystem97/tools/run_local_tests.py --site <site-test>`. Ce lanceur refuse les noms de sites non jetables. Les fixtures comptables de test restent consultables dans cette base uniquement.
10. Effectuer un paiement via le vrai Checkout TEST. Relever dans Stripe l'identifiant d'événement et le code de livraison ; dans Frappe relever le même événement `Success`, un seul Payment Entry soumis, ses écritures GL, la facture soldée et la notification. Réexpédier le même événement puis vérifier la concurrence de deux événements du même paiement. Vérifier le refus de démarrage avant règlement, l'autorisation après règlement et le blocage après remboursement.
11. Consulter les endpoints administrateur `softsystem97.integrations.ticket_bridge.readiness.get_stripe_readiness` et `…readiness.get_readiness`. Le premier ne vérifie que la configuration. Le second exige aussi les revues métier et les preuves externes ; ne jamais positionner les approbations sur la seule base des tests locaux.

## Opérations externes restant à effectuer / autoriser

- Accès administrateur au site de test Frappe Cloud pour déploiement, migration, comptes de service, configuration protégée et inspection du journal.
- Remplacement sécurisé des anciennes clés et signatures TEST exposées et destination TEST vers la préproduction.
- Validation d'un paiement envoyé par Stripe, livraison HTTP réelle vers Frappe Cloud, notification portail, comptabilité et autorisation technicien sur cette préproduction.
- Revue des Server Scripts / Workflows historiques, notamment les écritures directes `frappe.db.set_value`, qui ne déclenchent pas les hooks Document. Le code ne contourne aucun 403.
- Avoir et règlement de remboursement : traitement comptable explicite et rapprochement humain conservés.
- Validation explicite distincte pour la fusion puis le déploiement LIVE. Après cette validation seulement : remplacement des secrets LIVE compromis, extension de la destination LIVE, configuration du mode LIVE et éventuelle activation de `PAYMENTS_LIVE_ENABLED`. Rien de cela n'a été effectué.

Pour les abonnements, conserver la fiscalité portée par les factures ERPNext et vérifier les obligations de taxe. Aucune activation Stripe Tax ni modification de taxe n'est incluse.

Références primaires : [signatures et livraisons Stripe](https://docs.stripe.com/webhooks), [devises](https://docs.stripe.com/currencies), [Invoice Payment](https://docs.stripe.com/api/invoice-payment/object). Le contrat de snapshot existant est conservé ; pas de mise à niveau automatique du format d'événements.
