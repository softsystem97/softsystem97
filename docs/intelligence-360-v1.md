# Soft System 97 Intelligence 360 — première intégration

Branche : feature/ss97-intelligence-360-v1. Base : feature/ss97-final-integration.
**Aucun déploiement ni paiement réel n'est effectué par ce commit.**

## Périmètre codé

- Portail séparé : /ss97-intelligence (ne remplace aucune URL existante).
- 5 familles de prestations : business, cyber, digital, operations, transformation.
- 3 formules (15 prix EUR administrés par catalogue en code).
- Secteur d'activité libre : aucun métier exclu par défaut. Des indications spécialisées
  couvrent notamment commerce, restauration, transport, BTP, santé, associations et IT.
- Commandes privées SS97 Intelligence Order : client, demandeur, société, secteur,
  questionnaire, catégorie, tarif, facture, état de paiement opérationnel, rapport, plan.
- Moteur déterministe, sans dépendance à un fournisseur externe d'IA :
  actions progressives et scénarios financiers explicitement hypothétiques lorsque
  le client communique CA et charges. Aucun audit indépendant inventé.
- Vérification de paiement côté serveur par rapprochement Stripe -> ERPNext,
  facture client et montant strict, événements Stripe authentifiés et Payment Entries.
  Remboursements et litiges bloquent l'accès même après livraison.
- Rapport Expert en état Review ; seule la direction System Manager peut l'approuver.
- Génération PDF privée en A4 via Frappe, accès limité au client connecté, no-store.
- Plan d'action : états À faire / En cours / Terminée, rattachés au rapport et au client.

## Préconditions non négociables avant activation

1. **Tester sur un site Frappe v16 isolé**, sauvegarder données et fichiers.
   Installer la branche et exécuter migrate ; le nouveau DocType doit exister.
2. Valider les permissions Customer / Portal User ; chaque utilisateur doit être lié à
   un unique Customer actif, sans pouvoir lire les dossiers des autres.
3. Configurer et tester Stripe **existant** : secret webhook, mode, clés, compte
   de passage, comptes comptables et facturation. Ne jamais exposer de clé à la page.
4. Vérifier le montant final du catalogue par rapport aux taxes applicables,
   réductions et modalités de facturation du commerce. Les prix codés ici ne
   doivent être utilisés en production qu'après validation légale et comptable.
5. Le lancement V1 conserve une **étape comptable manuelle** : System Manager
   crée/soumet d'abord une Sales Invoice EUR dédiée, du montant exactement égal
   au prix de l'offre et au même Customer. Ensuite il appelle :
   /api/method/softsystem97.intelligence.api.link_submitted_invoice (POST)
   avec order_name et invoice_name. Aucun ticket Issue ne peut partager la facture.
6. Le client peut alors cliquer « Payer » : le code Checkout Stripe existant est réutilisé.
   Le rapport n'est disponible qu'après authentification et preuve comptable complète.
7. Pour activer le module **après vérification du site** :
   site_config.json : "ss97_intelligence_enabled": true (booléen, pas chaîne).
   La fonctionnalité est désactivée par défaut ; ne jamais ouvrir tant que les tests
   d'accès, de TVA/prix, de facturation et de paiement réel ne passent pas.
8. Tester un scénario payé, un impayé, un paiement contesté, une facture d'un autre
   client, deux commandes partageant une facture, deux comptes sur un Customer
   et les trois formules ; confirmer l'isolation et la revue Expert.
9. Vérifier à la fois la qualité/longueur du PDF et le moteur Chromium du site.
   Toute collecte de données nécessite une information RGPD et une politique
   de conservation adaptée.

## Parcours API

GET get_catalog ; POST create_order ; GET my_orders ;
POST link_submitted_invoice (System Manager seulement) ;
POST start_checkout ; POST generate_report ;
POST approve_expert (System Manager seulement) ;
GET report_detail ; POST update_action ; GET download_pdf.
Toutes sous softsystem97.intelligence.api.

## Limitations explicites

- Catalogue/périmètre transversal opérationnel **dans le code**, sous réserve de
  déploiement et validations ; pas de recherche publique vérifiée/IA générative.
- La facturation n'est pas entièrement automatique : obligation fiscale, TVA,
  configuration Item/Company et mise en facturation SS97 doivent être validées.
- La cybersécurité opérationnelle est développée sur une autre branche
  feature/cyber-operations-v1 ; elle n'est **pas fusionnée ni activée ici**.
- MeshCentral est à l'état de conception, sans session de prise en main réelle.
- Pas encore d'annuaire d'experts, de réservation, d'abonnement, de benchmark
  externe, de connecteurs ERP client ou de surveillance réelle.
- Les documents générés à partir de déclarations ne sont pas des audits certifiés.
  Une revue Expert ne remplace pas les professions réglementées.

## Prochaines évolutions

1. Intégration comptable éprouvée pour émission automatique de factures en tenant
   compte du régime fiscal, des taxes et des produits ERPNext configurés.
2. Révision humaine des données et ajout de justificatifs / sources, puis versionnement.
3. Fusion contrôlée des modules cyber (compatibilité branches et autorisations).
4. Sessions distantes avec consentement et moteur externe isolé.
5. Réseau d'experts, devis projets et abonnements de transformation avec leurs
   propres conditions contractuelles et indicateurs de suivi.

## Extension de facturation autonome — 5 novembre 2026

- **Nouvelle API POST** `softsystem97.intelligence.api.prepare_invoice`.
- Le client commande, puis clique **Préparer ma facture** avant l'étape Checkout.
- Verrou transactionnel sur la commande : un même dossier ne doit pas créer deux factures.
- Prix final TTC contrôlé exactement en EUR sur le catalogue côté serveur.
- L'article de vente ERPNext doit être un service actif et non un stock.
- Le compte de service comptable Stripe est réutilisé pour créer/soumettre la facture.
- Une TVA ou une exonération n'est **jamais déduite du secteur** par le logiciel.

**Configuration obligatoire en site_config.json, exemple de structure uniquement (identifiants fictifs) :**

```json
{
  "ss97_intelligence_enabled": true,
  "ss97_intelligence_auto_invoice": true,
  "ss97_intelligence_billing": {
    "company": "NOM-EXACT-COMPANY-ERPNext",
    "item_code": "REFERENCE-SERVICE-SS97",
    "tax_template": "TEMPLATE-TTC-VERIFIE"
  }
}
```

Pour un dossier effectivement exempté, utiliser `"tax_exempt": true` et omettre
`tax_template`, mais uniquement après validation du régime fiscal et des paramètres
ERPNext par le comptable. L'exemple ci-dessus n'est **pas** une configuration
à copier tel quel : chaque valeur doit être vérifiée sur le vrai site.

Les modèles de taxes autorisés par cette V1 doivent être simples, inclus dans le prix
et appliqués au total net. Les règles complexes, la remise, les commissions facturées
au client et les taxes supplémentaires sont bloquées par contrôle du total.
Le rapprochement Stripe vers ERPNext reste celui de la branche existante.

**Attention :** le compte Stripe réel n'est pas configuré ou activé par cette
extension ; aucun paiement n'a été déclenché. Contrôles et paiements TEST
sur bench isolé avant le moindre basculement LIVE. Aucun changement de
site_config.json de production n'a été effectué.

### Recette restante avant activation

1. Confirmer Company, Item non-stock, compte de revenus, centre de coûts et
   Sales Taxes and Charges Template en production.
2. Tester double-clics, demandes parallèles, échec de soumission de facture,
   facture d'un autre client et désactivation du compte de service.
3. Tester la facture TTC exacte, les écritures ERPNext et les événements Stripe
   réellement signés sur un site de test indépendant.
4. Vérifier le PDF, sa confidentialité, la revue Expert, les remboursements et
   le téléchargement après litige.
5. Installer la branche sur le site Frappe Cloud via procédure validée,
   puis activer les deux feature flags uniquement après recette complète.

L'annuaire d'experts, l'intégration cyber, le monitoring actif, l'accès distant
et les abonnements sont des chantiers distincts, pas des capacités déjà en production.
