# SS97 — Préparation du premier règlement réel

## Opérations effectuées après la demande de production

- Sauvegarde Frappe Cloud complète du 3 novembre : `Success` (base et fichiers).
- PR #6 fusionnée dans `feature/ss97-final-integration`, commit `82ea0c0e3fdf1c7c0eacca8f0c82cd5e70a82bbb`.
- Pipeline Cloud `59gsjvfqii` : `Success`, 7 min 53 s. Le site actif affiche ce commit pour SoftSystem97 ; Frappe/ERPNext conservent leurs versions précédentes.
- Le nouvel endpoint administrateur de préparation répond et confirme la présence du champ de transaction Payment Entry.
- Stripe confirme `charges_enabled=true`, `payouts_enabled=true`, sans exigence actuellement due pour le compte déjà raccordé.

La page client effectivement publiée diffère du générateur initial. Le premier installateur à quatre fonctions a donc été exécuté en lecture seule et n'a rien modifié. Il ne faut pas remplacer son HTML par celui du dépôt.

## Adaptation du portail existant

`runtime_install.console_script()` produit le correctif prévu pour la Console système officielle :

1. L'API existante `ss97_ticket_request_payment` appelle Checkout avec la facture liée au ticket du client authentifié. Le montant et la devise restent définis côté serveur.
2. `ss97_ticket_confirm_payment` consulte uniquement la preuve comptable. Elle ne crée plus de reçu ni de statut payé à partir de paramètres navigateur.
3. Un bloc JavaScript est ajouté à la page existante `espace-client/ticket`. Le HTML et le reste du JavaScript sont conservés. Le bouton utilise les nouvelles API serveur et n'accepte qu'une URL HTTPS d'origine exacte `checkout.stripe.com`.

Les deux API appellent le garde natif `require_write_session`, car le dispatcher Server Script ne vérifie pas lui-même les méthodes HTTP des fonctions qu'il appelle. Les permissions et validations restent dans les méthodes applicatives.

Contrôle préalable réussi, puis sauvegarde native des deux Server Scripts et du JavaScript de la page confirmée en production. Aucune activation Stripe, modification de clé ou écriture comptable n'est incluse. La console a été remise sans validation d'écriture après l'application.

Validation ciblée : deux nouvelles régressions Frappe/ERPNext sur le site local jetable réussissent. Un retour navigateur ne crée aucune écriture ; un véritable Payment Entry issu du webhook synthétique permet ensuite la confirmation. GET, Guest et ticket d'un autre acteur sont refusés. Les scénarios Node vérifient les paramètres navigateur, le POST, la preuve serveur, les erreurs et les URL de redirection.

## État bloquant vérifié sur le site

- `test_mode=1` et `payments_live_enabled=1` existaient déjà avant cette intervention. Aucun de ces deux champs n'a été modifié.
- `service_user` et `clearing_account` sont vides. Aucun compte de service dédié n'est actuellement disponible parmi les utilisateurs comptables consultés.
- Les comptes bancaires ERPNext actifs consultés sont en USD. Une facture EUR exige un compte bancaire de passage et un compte de tiers compatibles avec l'EUR ; la devise de base de la société ne doit pas être changée pour contourner ce problème.
- Les champs Password LIVE contiennent déjà des valeurs protégées, dont la validité et le remplacement des anciennes valeurs compromises restent à établir. Le contrôle courant porte sur le mode TEST et ne démontre pas l'absence de secrets LIVE.
- Douze Server Scripts Issue sont actifs, aucun Workflow Issue actif. La revue et le raccordement des permissions du portail technicien historique restent requis avant de déclarer la préparation globale validée. Les approbations de livraison n'ont pas été positionnées.

L'extension du webhook LIVE aux douze événements a été **refusée par la validation automatique** tant que les secrets et paramètres comptables ne sont pas vérifiés. La destination LIVE reste donc à un événement ; aucun autre chemin n'a été utilisé pour effectuer cette écriture.

## Suite nécessaire

1. Choisir la prestation ou la facture réelle, son client et son montant/devise. Ne pas inventer une vente ou utiliser une ancienne facture de démonstration pour simuler un règlement.
2. Préparer les comptes comptables et les utilisateurs de service limités adaptés à cette facture. Toute création ou extension de permissions doit être confirmée au moment de l'action.
3. Remplacer les anciennes clés LIVE et le secret de signature compromis dans les écrans protégés, sur le même compte Stripe. La saisie de nouveaux identifiants est effectuée par l'utilisateur ; aucun secret n'est envoyé dans le chat, Git ou la console.
4. Recontrôler la préparation, étendre la destination LIVE et basculer le mode après la configuration complète.
5. Le payeur saisit sa carte et valide le montant sur Checkout. Vérifier ensuite le même événement Stripe, un seul Payment Entry soumis, la facture soldée, la notification et les droits d'intervention.

**Aucun paiement réel n'a été exécuté et aucun fonctionnement de bout en bout en production n'est encore attesté.**
