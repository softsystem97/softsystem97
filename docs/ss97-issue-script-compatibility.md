# SS97 — débloquer le pont sans désactiver les scripts Issue

## Problème
Le contrôle de sécurité historique refusait **tout** Server Script Frappe
actif sur Issue. Soft System 97 possède déjà des automatisations natives
sur Issue (protections, notifications, affectations). Les désactiver
serait risqué.

## Modification
Le pont n'exige plus l'absence absolue de scripts. Il exige que
**chaque script actif** soit **explicitement examiné** et que son empreinte
exacte (nom, événement, source complète) soit approuvée côté
site_config privé. Toute création, modification, suppression d'un script
révoque la compatibilité et bloque les opérations du pont.

Le rapport System Manager (GET privé) renvoie la liste des noms,
événements et empreintes SHA-256 à contrôler. Il ne divulgue jamais
le code des scripts aux candidats, clients ou techniciens.

### Activation conditionnelle

Après sauvegarde, revue du comportement des scripts, tests de non-régression
sur les tickets et validation indépendante du compte Support Team :

1. Dans le Site Config de app.softsystem97.com, préparer un objet JSON privé
   \`ss97_ticket_bridge\` avec les paramètres existants \`enabled\`,
   \`compatibility_confirmed\`, \`writer_user\`, \`technician_role\`,
   \`profile_required\`, \`historical_integration\`, \`email_enabled\`.
2. Ajouter \`issue_scripts_reviewed: true\`,
   \`issue_scripts_review_reference: "SS97-ISSUE-REVIEW-2026"\`,
   \`approved_issue_scripts: {"Nom du script": "sha256", ...}\` avec
   la liste **exacte** du rapport d'audit.
3. Ne mettre \`enabled: true\` qu'après un test de création d'un ticket,
   d'attribution ToDo avec reçu, de révocation d'affectation et de
   refus de demande non autorisée sur un environnement de recette.
4. Garder \`email_enabled: false\` si des notifications natives existent.

**Ne pas remplir automatiquement l'allowlist depuis la base à chaque
opération.** Cela désactiverait le contrôle de modification.

Les profils N4, examens, mandats, contrats, paiements et autorisations
restent soumis à leurs propres contrôles ; aucun rôle ni paiement
n'est accordé par ce correctif.
