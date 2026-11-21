# CyberExpert 360 CyberOS — intégration à Soft System 97 (v1)

## Livré dans cette branche

- \`/ss97-cyberos\` : espace client avec trois fonctionnalités : **inventaire**, **actions correctives déclarées** et **registre d'incidents déclarés**.
- Trois DocTypes privés : \`SS97 Cyber Asset\`, \`SS97 Cyber Action\`, \`SS97 Cyber Incident\`. Tous sont lisibles en Desk par les seuls System Managers. L'écriture client est *uniquement* possible par les méthodes ciblées, sous contrôle strict de la correspondance User → un Customer actif.
- Le tableau de bord est isolé par entreprise. Un client ne peut pas consulter ou modifier le dossier d'une autre entreprise, et une action client \`DONE_DECLARED\` ne signifie pas \`VERIFIED\`.
- Validation \`VERIFIED\` exclusivement par un responsable \`System Manager\` avec référence de preuve. Le compte client ne peut pas lui-même se certifier.
- Aucun scan réseau, aucun accès distant, aucun incident automatiquement traité, aucune astreinte 24/7, aucun paiement, création de crédits/tokens, ni appel d'IA externe.
- Raccordement avec la passerelle de tickets existante **sans** réécrire ses autorisations ni les modifier.
- \`contact@softsystem97.com\` et tous les réglages e-mails restent inchangés.

## Installation Frappe Cloud (non effectuée par le commit)

1. Sauvegarde complète et vérification de restauration, puis déploiement de la version examinée dans un environnement de recette Frappe v16/ERPNext v16.
2. \`bench migrate\` ou procédure de migration de Frappe Cloud, puis confirmation des trois nouveaux DocTypes.
3. Vérification explicite de l'isolation tenant : invité, deux comptes de deux Customer différents, compte désactivé, User ambigü et System Manager.
4. Contrôle du pont existant et des rôles sans court-circuiter les vérifications historiques.
5. Dans la configuration **privée** du site, uniquement après recette, activer :
   \`"ss97_cyberos": {"enabled": true}\`.
   Ce module exige également \`ss97_ticket_bridge.enabled=true\` et \`compatibility_confirmed=true\`.
   **Ne pas committer le site_config.json ni des secrets.**
6. Confirmer les créations, la modification d'action et l'impossibilité d'obtenir une validation manager depuis un compte client.
7. Suivre les logs; prévoir rollback si erreur, et confirmer les contrôles RGPD, conservation/purge et sécurité du déploiement.

## Plan des modules additionnels

| Nom | Objectif | État |
| --- | --- | --- |
| CyberAI, CyberPilot | Assistant IA et préparation de missions avec vérifications humaines | conception, **non connecté** |
| CyberTwin, AttackPath | Cartographie des actifs, dépendances et scénarios hypothétiques | inventaire v1; cartographie **à construire** |
| CyberPulse, CyberSentinel | Veille et surveillance **autorisée** | non connecté |
| CyberSOS, CyberRecovery | Incidents, crise et reprise | registre initial; intervention d'urgence **non activée** |
| CyberProof, CyberEvidence Ledger | Preuves confidentielles, intégrité et revues | champ référence, coffre **à construire** |
| CyberDirector, CyberFinance | Pilotage dirigeant, estimations et arbitrages | à construire |
| CyberLab | Exercices simulés et formation | à construire |
| CyberTrust | Partage contrôlé avec partenaires | à construire |
| CyberCompliance | Référentiels et contrôles applicables selon le secteur | à construire |
| CyberResilience Caraïbes | Continuité électrique, réseau et cyclonique | à construire |
| Abonnements / crédits / tokens | Solde et consommation dérivés de paiements réellement vérifiés | à construire; pas de jetons gratuits |
| Techniciens N4 | Mandats, affectations, revue et clôture | modules préexistants, recette réelle requise |

Le prédiagnostic, le PDF, les trois offres Basique/Premium/Ultra et les règlements Stripe font partie d'autres modules existants et doivent être testés séparément en production. Cette branche **ne prouve pas** leur activation.
