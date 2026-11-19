# Soft System 97 — CyberExpert 360 : déploiement progressif et recette

## Livré dans ce lot (code)

1. Page `/ss97-cyber-entreprises` : trois offres Basique/Premium/Ultra,
   questionnaire entreprise (implantation, secteur, taille, sites, postes,
   fonction, sensibilité) et 10 domaines de sécurité. Les clients connectés
   peuvent demander aussi une intervention N2 généraliste ou N3 bancaire.
2. `SS97 Cyber Pricing` : tarifs **indiqués HT**, stockés en configuration
   Single Frappe, publiés **uniquement** par un System Manager actif.
   Aucune valeur tarifaire n'est inventée, aucun prix par défaut n'est publié.
3. `SS97 Cyber Assessment` : données déclarées, snapshot immuable de la formule
   et du prix indicatif, identifiant de ticket et client propre au compte ;
   contrôle d'idempotence/réutilisation contre le pont Issue existant.
4. Rapport PDF au téléchargement : obtenu à la demande via un endpoint protégé
   et `frappe.utils.pdf.get_pdf`, jamais une URL publique ni une pièce jointe
   sur un répertoire web. Indicateur **déclaratif**, points forts, lacunes et
   questionnaire, avec avertissement explicite sur l'absence de vérification.
5. Revue via `/ss97-cyber-review` : **N4 actif de spécialité CYBER** seulement,
   mission même client/ticket en `REPORT_SUBMITTED` ou `CLIENT_ACCEPTED`, mandat
   écrit et approbation d'un second manager, ticket toujours attribué par le
   pont sécurisé, note et référence justificative exigées. Un N2/N3 ne peut
   pas transformer une déclaration en « revue N4 ».
6. Suivi commercial : le manager peut lier un **devis, une commande ou une
   facture déjà existants dans ERPNext**, si le Customer correspond. Aucun
   document commercial, facture ou paiement n'est créé automatiquement. Les
   références sont visibles au client propriétaire dans « Mes expertises ».

## Préparation Frappe Cloud / ERPNext v16

- Sauvegarder site et base ; vérifier restauration et rollback avant migration.
- Pousser la branche révisée puis déployer **l'application SoftSystem97
  uniquement** dans une fenêtre validée ; lancer `bench migrate` via le flux
  Frappe Cloud et vérifier les deux nouveaux DocTypes et la page.
- Vérifier que `SS97 Cyber Pricing` est accessible à la direction, et pas au
  compte client ou technicien. Les champs financiers ne sont éditables que
  par les responsables ; n'accorder aucune permission globale aux techniciens.
- Conserver initialement `ss97_cyber_assessment.enabled = false` dans la
  configuration privée du site. Confirmer d'abord les rôles, la compatibilité
  `ss97_ticket_bridge`, le service d'écriture Issue, la messagerie sortante,
  la gestion des Customer et les transactions d'idempotence.
- Saisir et approuver les **vrais** prix Basique/Premium/Ultra dans
  `/ss97-tech-admin`, puis publier. Les montants sont indicatifs, sous réserve
  de devis/TVA et ne prouvent pas qu'un paiement est accepté.
- Après une recette client/N4 négative/positive signée, activer séparément le
  dict `ss97_cyber_assessment` dans `site_config.json` avec `enabled: true`.
  Le paramètre `false` coupe les **nouvelles créations** sans retirer les
  rapports déjà enregistrés et accessibles à leur propriétaire.

## Tests impératifs avant ouverture

| Cas | Attendu |
| --- | --- |
| Visiteur anonyme | Catalogue visible, refus d'envoi, aucune donnée client divulguée |
| Client sans Customer unique | Envoi refusé |
| Prix non publiés | Demande cyber refusée, pas de paiement |
| Prix publiés | Estimation HT exacte, aucune facture ou commande automatique |
| Demande cyber + retransmission même identifiant | Un Issue et un seul dossier ; aucun double courriel |
| Questions modifiées avec identifiant réutilisé | Rejet de l'ancienne clé |
| Client B demande le PDF client A | 403, aucun PDF transmis |
| N2/N3 requiert l'API revue N4 | Rejet 403 |
| N4 sans mission, mandat, approbation ou attribution active | Rejet 403 |
| N4 avec toutes les validations requises | Décision journalisée, rapport marqué « revue N4 » |
| Manager lie devis autre client | Rejet 403 ; aucune écriture dans l'autre Customer |
| PDF avec texte contenant `<script>` | Contenu échappé, aucun HTML exécuté |
| Paramètre désactivé après réception | Anciens dossiers lisibles, nouvelles demandes refusées |

## Non livré / dépendances à ne pas confondre

- **OpenAI non connecté** : l'ancienne clé visible dans la conversation est
  compromise. Révoquer cette clé. Fournir une nouvelle clé par le coffre
  secrets du déploiement, jamais dans un ticket, le dépôt ou une discussion.
  Ne pas activer d'analyse IA avant validation des traitements, du périmètre
  de données et des coûts. Le PDF fonctionne **sans IA** à titre déclaratif.
- La **prise en main réelle à distance** exige un serveur relais public,
  logiciel agent ou navigateur compatible, contrôle de consentement, identité,
  journalisation et révocation. Ni le questionnaire ni ce lot ne l'activent.
- Ne sont pas automatiques : vérification réelle des actifs, certification
  cybersécurité, scan actif, devis accepté, paiement, commande, attribution N4,
  mission et courriel reçu.
- Les tests Python/JS hors Frappe vérifient le code et des contrats de sécurité,
  mais ne remplacent ni migration en staging, ni tests client/N4 **réels** en
  production. Consigner les numéros de ticket et les résultats sans données
  personnelles dans les journaux de recette.
