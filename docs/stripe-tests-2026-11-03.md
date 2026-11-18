# Résultats de validation Stripe SS97 — 3 novembre 2026

## Exécutions locales

| Vérification | Résultat |
|---|---|
| Suite Frappe complète, `tools/run_local_tests.py --site test_stripe` | **119 tests réussis**, 0 échec, 0 erreur |
| Tests hors Frappe, `python -m unittest discover -s tools -p 'test_*.py' -q` | **110 exécutés : 107 réussis, 3 ignorés** (contexte Frappe requis) |
| Sous-ensemble Stripe après les derniers ajustements | **22 tests réussis**, dont les 7 tests comptables |
| Migration exécutée deux fois et contrainte unique SQL | Réussies |
| Contrôles historiques Node et syntaxe du JavaScript de la page ticket | Réussis |
| Ruff, compilation Python, `git diff --check` | Réussis |
| Recherche de secrets Stripe dans le contenu Git préparé | Aucun secret détecté |

Environnement comptable réel : Python 3.14.8, Frappe 16.55.0 (`90c8b61afd60ee49f982ca1a9751008e4ae1e24c`), ERPNext 16.53.0 (`9cd11b19575bfc34f092a24f6c8b368c4dd69481`), MariaDB 10.11.14, Redis 7.0.15, SDK Stripe 16.1.0. Site et base jetables, aucun livre de production utilisé. Le workflow GitHub épingle ces sources Frappe/ERPNext pour reproduire les tests.

## Preuves natives couvertes

- Facture soumise de 100 EUR, client et ticket contrôlés, réception signée en mode TEST.
- Payment Entry soumis sous utilisateur de service, compte de passage explicite, allocation de 100 EUR, écritures GL natives et solde facture nul.
- Même événement livré deux fois : acquittement du doublon, un seul règlement et une seule notification portail.
- Deux événements différents concurrents pour le même paiement : un seul Payment Entry.
- Écart d'un centime ou mauvaise devise : aucun règlement comptabilisé et intervention refusée.
- Signature incorrecte et signature expirée rejetées avant traitement.
- Paiement échoué tardif : règlement confirmé conservé ; remboursement partiel : travail bloqué, rapprochement par avoir/règlement conservé à la comptabilité.
- Démarrage par modification native d'Issue refusé avant règlement, accepté après preuve comptable.
- Checkout lié à la facture du client autorisé ; utilisateur de service comptable refusé dans l'API client ; le montant ne vient pas du navigateur.
- Tests natifs du journal : concurrence, reprise, verrou courant, absence de fuite du texte d'erreur et protection d'un succès concurrent.
- Permissions clients/techniciens, révocation d'affectation, notifications et files e-mail : suite existante exécutée avec les validations ERPNext v16 conservées.

## HTTP réellement exercé sur le serveur local Frappe

| Requête POST | HTTP | Contrôle |
|---|---|---|
| Signature incorrecte | 403 | Aucun règlement |
| Signature HMAC expirée | 403 | Aucun règlement |
| Événement TEST correctement signé avec le secret de la configuration locale | 200 | Journal Success, Payment Entry et GL natifs |
| Même événement signé livré de nouveau | 200 | `duplicate=true`, un seul Payment Entry |

Les signatures de ces tests sont créées localement avec un secret synthétique conservé dans le Password du site jetable. Ce sont de vraies réponses HTTP et une vraie comptabilité ERPNext de test, **pas une preuve de livraison externe générée et signée par Stripe**.

## Limites restantes

Aucun accès administrateur Frappe Cloud actif ; pas de lecture du journal distant, de nouveau secret injecté ni de déploiement. La consultation Stripe confirme neuf événements sur TEST et un seul sur LIVE. La réception Stripe → Frappe Cloud, le paiement navigateur dans Checkout TEST et le rapprochement de ce paiement réel de sandbox restent à exécuter sur une préproduction séparée. Le rapprochement comptable des remboursements est volontairement explicite, sans annulation automatique d'une pièce soumise.
