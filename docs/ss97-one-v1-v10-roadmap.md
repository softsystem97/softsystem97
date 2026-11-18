# SS97 ONE — trajectoire V1 à V10

## Périmètre et vérité du projet (17 novembre 2026)

**Produit** : plateforme Soft System 97 sur Frappe / ERPNext v16, avec
`SS97 Remote Assist` comme premier module. Le moteur d'écran distant envisagé
est MeshCentral, isolé de l'ERP. Ce document n'affirme ni partenariat, ni
déploiement, ni prise de contrôle réussie d'un ordinateur client.

La branche de développement contient un **coordinateur de sessions V1.1** :
ticket et technicien affecté, compte client vérifié, code à neuf chiffres,
fenêtre d'une heure, code à usage unique, accord/refus sur le portail,
révocation des demandes et journal d'événements. Le flux écran/clavier/souris
et la confirmation d'un consentement local MeshCentral **ne sont pas branchés**.
Les tests hors serveur ne remplacent pas une recette sur Frappe v16.

## Les dix versions, sans brûler les étapes

| Version | Capacité livrable | Situation |
|---|---|---|
| **V1 — Remote Assist** | Ticket, identité, code unique, accord du client, journal, puis contrôle écran/clavier/souris après accord local | Coordination codée ; moteur réel à raccorder |
| **V2 — Missions & techniciens** | Compétences, affectation, agenda, prestation d'une heure, transfert avec nouvel accord, rapport de fin | Conception |
| **V3 — Command Center** | Pré-diagnostic, IA d'aide au technicien, expertise et supervision sans action autonome de l'IA | Conception |
| **V4 — SS97 ONE** | Un seul compte entreprise et un parcours demande → devis → paiement → prestation → suivi | Conception |
| **V5 — SOS informatique** | Accueil public, qualification, estimation, réservation, notification, acquisition clients | Vision |
| **V6 — Passeport informatique** | Inventaire autorisé des postes, historique, risques, rapports et recommandations | Vision |
| **V7 — Maintenance proactive** | Contrats, surveillance consentie des équipements, alertes préventives, renouvellements | Vision |
| **V8 — Réseau de techniciens** | Planification multi-techniciens, spécialités, disponibilité, escalade, contrôle qualité | Vision |
| **V9 — Cyber & résilience** | Audit, plans de remédiation, sauvegarde, continuité des entreprises et cyberhygiène | Vision |
| **V10 — Écosystème SS97** | Annuaire qualifié de prestataires partenaires, interventions sous contrôle SS97, preuves et évaluations | Vision |

## Parcours unique d'une intervention

1. **Demande** : l'entreprise décrit l'incident dans son portail ou par SOS ;
   un ticket est créé. Aucun agent n'est installé automatiquement.
2. **Qualification** : catégorie, criticité, diagnostic initial et devis
   éventuel ; confirmation du paiement selon les règles SS97 existantes.
3. **Affectation** : un superviseur choisit un technicien habilité selon
   son niveau et sa disponibilité. Un transfert exige un nouvel accord client.
4. **Rendez-vous** : créneau de **60 minutes** et invitation à usage unique.
   La V1.1 permet seulement un créneau immédiat de préparation d'une heure ;
   l'agenda et les rendez-vous différés seront développés en V2.
5. **Identification** : client authentifié, ticket vérifié, technicien
   affecté ; code à neuf chiffres consommé lors de la première jonction.
6. **Consentement** : accord dans SS97, puis **accord séparé et local sur le
   poste** avant affichage d'écran. Le client peut refuser ou interrompre.
7. **Intervention** : début chronométré à la connexion réelle confirmée,
   journal d'événements, pause, escalade, prolongation uniquement sur accord.
8. **Clôture** : déconnexion réelle prouvée, rapport du technicien, validation
   du client, facture et recommandations ; dossier accessible dans SS97.

## Règles de sécurité non négociables

- Aucun accès distant non supervisé pour ce premier produit ; ni connexion
  silencieuse, ni transmission de mot de passe Windows, PIN ou clé d'API au
  navigateur. Les appareils sont liés côté serveur au bon client/ticket.
- `ACTIVE` est réservé à un événement authentifié du moteur distant ; un clic
  dans le navigateur ne prouve jamais le contrôle réel.
- Déconnecter le moteur distant avant d'afficher « terminé » ; confirmer les
  coupures par événement signé avec protection anti-rejeu et délai maximal.
- Isoler les entreprises entre elles : droits minimum, MFA des techniciens,
  journaux horodatés, conservation limitée, supervision et procédure d'incident.
- Activer en préproduction sur deux PC de laboratoire autorisés. Pas de
  déploiement sur `app.softsystem97.com` avant validation et sauvegarde.

## Construction, dans cet ordre

### Lot A — V1.1 : base Frappe (en cours)

- [x] Ticket + technicien affecté et client identifié.
- [x] Code à neuf chiffres HMAC, usage unique, fenêtre de 60 minutes.
- [x] Accord / refus sur le portail, historique, révocation en attente.
- [ ] Test d'intégration avec la vraie base de préproduction et des comptes
  client / technicien séparés.

### Lot B — V1 réelle : le passage obligé

- [ ] Serveur MeshCentral isolé, TLS, MFA, politique de consentement local.
- [ ] Installation volontaire d'un assistant signé sur **deux PC tests**.
- [ ] Association serveur de l'appareil à une entreprise et un ticket, sans
  identifiant d'appareil provenant du navigateur.
- [ ] Adaptateur authentifié : invitation éphémère, constat de la connexion,
  preuve de consentement local, états `ACTIVE` et déconnexion effective.
- [ ] Recette de refus, retrait du consentement, coupure réseau, expiration,
  révocation, doublon et franchissement de locataires.

### Lot C — V2 : exploitation multi-techniciens

- [ ] Planning et réservation de créneau ; éviter les conflits horaires.
- [ ] Chronomètre d'intervention **réelle** d'une heure, distinct de la
  fenêtre du code ; extension explicite acceptée par le client.
- [ ] Réaffectation après nouvelle autorisation, pause, reprise et escalade.
- [ ] Rapport de mission, validation client, indicateurs de qualité.

### Lot D — V3 à V5 : entreprise qui accueille ses clients

- [ ] Pré-diagnostic guidé ; suggestions IA sans exécution autonome.
- [ ] Portail SOS informatique mobile et devis / paiement intégré aux modules
  Stripe existants, sans créer de second canal financier parallèle.
- [ ] Parcours découverte → intervention → rapport et relance commerciale.

### Lot E — V6 à V10 : grandir sans perdre la confiance

- [ ] Passeport de parc, maintenance, supervision, offres cybersécurité.
- [ ] Réseau d'experts qualifiés, contrats, disponibilité et contrôle qualité.
- [ ] Mesurer le coût des interventions, les délais et la rétention avant
  tout investissement dans une plateforme de marché nationale.

## Critères d'acceptation du tout premier contrôle distant

Avec un compte client A, un technicien A et deux machines de test : le client
voit l'identité du technicien, consent localement, voit le curseur agir et
peut couper immédiatement. Le technicien ne peut pas voir le PC du client B,
ni reconnecter après clôture. Le serveur enregistre les preuves des états et
la révocation. Tant que ces critères ne sont pas démontrés, **on ne présente
pas SS97 Remote Assist comme un outil de prise en main opérationnel**.
