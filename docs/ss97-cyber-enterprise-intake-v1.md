# SS97 — Entreprises, cybersécurité et ticket libre (pilote)

## Périmètre livré dans le dépôt

- `/ss97-cyber-entreprises` : consultation publique de trois niveaux d'analyse.
- `get_catalog` : description de l'offre sans prix et sans engagement technique automatique.
- `request_assessment` : création d'un **Issue** via le pont sécurisé SS97,
  réservée à un client authentifié, lié de façon non ambiguë à un Customer.
- Deux types : `CYBER` avec formule `ESSENTIEL`, `SUPERIEUR`, `EXTREME` ;
  `LIBRE` sans formule. Idempotence et notifications du pont réutilisées.
- `/ss97-tech-admin` : revue de préparation et file d'entrées cyber,
  réservées à `System Manager` ; le client n'a pas accès à ces API.
- N4 cyber est la filière d'exécution prévue. Les N2 et N3 gardent leurs
  univers étanches ; toute sous-traitance requiert un ticket et une mission
  approuvés explicitement.

**Aucune infrastructure client n'est sondée.** Une demande, même avec accord
de contact, n'autorise aucune intrusion, prise de contrôle, capture réseau,
collecte de secrets ni scan. Le responsable doit obtenir un mandat écrit qui
décrit le périmètre, les horaires, les actifs, les personnes habilitées, les
exclusions, la conservation des preuves et les contacts d'urgence.

## Activer uniquement après recette Frappe v16

Code **désactivé par défaut** pour la réception. Configuration uniquement dans
`site_config.json` (pas dans le dépôt) :

```json
"ss97_cyber_assessment": {"enabled": true}
```

Le pont `ss97_ticket_bridge` doit **déjà** être vérifié, compatible avec le
ticket historique et configuré : `enabled`, `compatibility_confirmed`, rôle
technicien, compte de service, Issue, Workflow/Server Scripts, notifications.
Sinon la création est refusée, sans effet secondaire.

Les emails sont optionnels et restent désactivés tant que le paramètre
`ss97_ticket_bridge.email_enabled` et le compte sortant vérifié n'ont pas été
validés. La présence d'un bouton ne prouve jamais la réception d'un email.

### Recette requise (avant ouverture aux clients)

1. Migration Frappe/ERPNext v16 sur environnement isolé et comparaison de
   `hooks.py`, DocTypes, Issue, rôles et permissions ; disposer d'un rollback.
2. Inscription : compte créé, preuve de confirmation native vérifiée, association
   unique à Customer, pas de fusion entre dossiers d'organisations.
3. Ticket libre : dépôt et redépôt du même `request_id` (un seul Issue),
   notification en espace client, mail réellement reçu si activé.
4. Ticket cyber : trois offres, réutilisation du même canal sécurisé et ticket
   visible uniquement du bon Customer ; pas d'auto-attribution au N4.
5. Supervision : un System Manager voit les demandes ; un client, un N2 et un
   N3 ne peuvent ni ouvrir la file ni consulter le rapport d'un autre.
6. Mission cyber N4 : habilitation validée, ticket assigné, accord écrit,
   double validation et coupure effective si l'assignation est retirée.
7. SMTP : succès et échec de livraison, tests anti-doublons et non-divulgation
   d'identités et de secrets dans les notifications.
8. Tests de charge et politique de purge des demandes/rapports sous RGPD.

## Limites actuelles

- Ni création de compte client publique, ni validation d'email d'inscription ne
  sont ajoutées par ce lot. Il faut tester et raccorder le parcours déjà présent.
- Aucun devis, paiement, salaire, contrat, audit automatique ou contrat de
  cybersécurité n'est activé par ces endpoints.
- Les 20/30/40 questions d'examen ne sont pas fournies : banque privée à charger
  et à valider par des évaluateurs avant ouverture des examens.
- Les tests CI sont hors Frappe ; un succès CI ne constitue pas une recette
  de déploiement, ni une preuve d'envoi d'email en production.
