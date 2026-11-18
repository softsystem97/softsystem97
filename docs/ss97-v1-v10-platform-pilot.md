# SS97 ONE — socle V1 à V10, lot de préproduction

**Périmètre** : Soft System 97 uniquement, Frappe/ERPNext v16.
**Machines du laboratoire** : Asus technicien, Dell client, MeshCentral déjà installé.
**Ne concerne pas** LINGOMED ni La Colombe Presta.

## Ce qui est construit

- V1 : le système existant de ticket / code d'assistance à 9 chiffres, usage
  unique et fenêtre de 60 minutes reste séparé. Test manuel Asus–Dell réalisé,
  sans preuve automatique du consentement local ou de la fin distante.
- V2 : fiches de missions, horaires UTC, durée et vérification des chevauchements
  de planning pour un technicien affecté au ticket.
- V3 : fiches de prédiagnostic, niveau de risque et avis humain. **Pas de moteur
  IA branché**, pas d'exécution automatique de commandes.
- V4 : notes de coordination et vue d'ensemble d'un ticket, de ses fiches et
  des sessions V1 connues. Les devis/paiements utilisent toujours les modules
  ERPNext/Stripe existants, sans nouveau circuit de paiement.
- V5 : déclaration SOS rattachée à un ticket client existant, catégorisation,
  urgence et annulation par le client. Ce n'est pas encore une entrée anonyme
  ouvrant automatiquement un nouveau ticket.
- V6 : fiches de passeport informatique avec déclaration d'autorisation
  d'inventaire **à confirmer auprès du client** ; aucun inventaire de machine
  n'est effectué par ce module.
- V7 : échéance et périodicité de maintenance liées à une fiche V6 appartenant
  au **même** client et au **même** ticket. Pas encore d'exécution planifiée.
- V8 : demandes d'escalade vers un spécialiste ; pas de redistribution
  automatique des droits d'accès à distance.
- V9 : constats et recommandations de cybersécurité ; **pas de scan de réseau**
  ni action de remédiation automatique.
- V10 : propositions de partenaires à examiner ; **pas d'annuaire public** ni
  habilitation automatique d'un prestataire.

## Infrastructure et accès

L'interface web est `/ss97-platform`. Le lien V1 existant reste
`/ss97-remote-assist`. Les neuf modules opérationnels utilisent deux nouveaux
DocTypes :

- `SS97 Platform Record` : entreprise, ticket, rôle, version, données validées,
  état du dossier, horaires ; écriture réservée à l'API.
- `SS97 Platform Event` : identifiant unique, dossier, acteur, action et heure ;
  lecture réservée au gestionnaire système.

Les dossiers utilisent les autorisations du pont client–technicien existant.
Les clients ne peuvent créer que des demandes V5 sur **leur ticket** et en
annuler une non encore traitée. Les autres fiches requièrent un technicien
effectivement affecté à ce ticket. Le client peut lire les fiches de son ticket,
pas celles d'une autre entreprise. Un navigateur ne peut ni choisir une autre
entreprise ni attribuer arbitrairement un appareil.

Les états de dossier sont `SUBMITTED → IN_REVIEW → COMPLETED` ou `CANCELLED`.
Ce sont des états *administratifs*, pas des preuves de contrôle d'écran, de
paiement, de réalisation de maintenance ni d'approbation d'un partenaire.

## Mise en service uniquement en préproduction

1. Effectuer une revue humaine des champs, des droits, des flux Stripe/tickets
   et des scripts existants. Préparer une sauvegarde et un site de test Frappe
   v16 isolé disposant de l'app SS97 et d'ERPNext.
2. Ajouter la branche dans ce **site de test uniquement**, puis exécuter une
   migration Frappe contrôlée afin de créer les deux DocTypes.
3. Valider auparavant la configuration du pont SS97 existant
   (`ss97_ticket_bridge`) et les comptes de test client/technicien distincts.
4. Activer cette seule option sur le site de test dans `site_config.json` :

   ```json
   {"ss97_v1_v10": {"enabled": true}}
   ```

   Sur le site en production, le paramètre doit rester absent/désactivé.
5. Ouvrir `/ss97-platform` et tester les versions V2 à V10 depuis un ticket
   de laboratoire ; vérifier la création, la consultation, les transitions
   d'états et le journal d'événements.
6. Tester impérativement les tentatives client B, la création hors ticket,
   un technicien non affecté, un horaire V2 en doublon, une fiche de matériel
   d'une autre entreprise, un ticket fermé, et une session V1 non autorisée.

### Tests locaux sans serveur

```bash
python -m unittest tools.test_ss97_platform_offline
node --check softsystem97/public/js/ss97_platform.js
```

## Limites avant de déclarer « V10 terminée »

Cette livraison pose un **socle de données et d'interface utilisable sous
contrôle**, pas neuf moteurs métier aboutis. L'hébergement Frappe Cloud et
les deux PC Asus/Dell n'ont pas été modifiés depuis ce dépôt. Il manque encore :

- La passerelle réelle MeshCentral associant appareil, ticket, consentement
  local, connexion et coupure vérifiée ; hébergement HTTPS distinct et MFA.
- La recette réelle sur Frappe/ERPNext v16, les tests multi-utilisateurs et les
  migrations supervisées.
- La réservation et notification automatisées, le moteur IA et les diagnostics
  utiles, le portail SOS public, l'inventaire consenti, les tâches de maintenance,
  la gestion formelle des partenaires et les contrats/rapports complets.
- Les tests de charge, la supervision, les sauvegardes/restaurations et
  l'homologation avant tout déploiement commercial.

**Pas de déploiement automatique sur `app.softsystem97.com`, pas d'activation
de paiement et pas d'accès distant silencieux.**
