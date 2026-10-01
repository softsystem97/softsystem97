# SoftSystem 97 — Assistance à distance intégrée aux tickets

Statut : conception / non déployé — 1er octobre 2026  
Branche : `feature/ss97-remote-assistance-design`  
Application existante : Frappe/ERPNext `softsystem97`, domaine `app.softsystem97.com`.

## 1. Objectif

Un technicien autorisé ouvre un ticket et lance « Assistance à distance ». Le client télécharge l'Assistant SoftSystem97 sur Windows, l'exécute, voit l'identité du technicien et approuve explicitement la prise en main. La session et son historique sont liés au ticket. Le client peut refuser ou arrêter instantanément la session. Par défaut, aucun accès non supervisé.

## 2. Composants et frontières

```text
app.softsystem97.com [Frappe/ERPNext]
  Ticket (Issue ou DocType personnalisé À CONFIRMER depuis le site)
  SS97 Remote Session [DocType à ajouter]
  remote/api.py [API et autorisations Frappe à ajouter]
  Portail client / interface technicien [à ajouter]
       | HTTPS authentifié et contrôlé
       v
remote.softsystem97.com [MeshCentral sur serveur isolé SS97-REMOTE01]
  Groupes de périphériques par organisation
  Comptes de techniciens à privilèges minimaux + MFA
  Liens d'invitation ponctuels, MeshCentral Assistant personnalisé
  Viewer navigateur, journal MeshCentral
       ^ connexion WSS sortante HTTPS/443
       |
Windows du client [Assistant signé ; accord local avant prise de contrôle]

Infrastructure locale existante (séparée) :
  SS97-HOST01 → SS97-DC01, SS97-API01 BridgeWorker, SS97-PC01.
  L'API Bridge AD actuelle ne transporte PAS le flux bureau distant.
```

Serveur public recommandé : VPS Linux isolé avec nom DNS et HTTPS pour simplifier les accès externes; option VM Ubuntu `SS97-REMOTE01` seulement si IP publique / NAT / disponibilité / ressources vérifiés. Point de départ à tester : 2 vCPU, 2–4 Go RAM, 30–40 Go SSD et bande passante adaptée au nombre de sessions. La sauvegarde de `meshcentral-data`, la base et les clés/certificats est requise. Ne pas rendre publiques les VM du domaine AD.

## 3. Produit et distribution

MVP : MeshCentral open source + MeshCentral Assistant (outil léger; usage ponctuel à tester sous Windows 10/11). Le client ne doit pas installer de service permanent dans l'offre ponctuelle. Identité graphique SoftSystem97 dans la fenêtre d'accueil, assistant signé par un certificat d'éditeur avant lancement commercial; conserver mentions/licences amont applicables. L'absence de signature au stade laboratoire doit être explicitement affichée : ne pas conseiller de désactiver Defender ou SmartScreen. Sur appareil professionnel, déploiement uniquement avec l'accord de l'administrateur de l'entreprise.

Futur : application cliente spécifique / portail multi-OS; macOS exige ses permissions d'accessibilité/capture; aucun contrôle iOS n'est présumé.

## 4. Workflow (état de ticket séparé de l'état de session)

1. Le ticket existe; paiement ou accord de prise en charge selon le flux commercial.
2. Technicien connecté, rôle `SS97 Technician` ou manager, assignation au ticket vérifiée côté serveur.
3. Clic « Préparer assistance » : création d'une `SS97 Remote Session`, jeton de liaison à usage unique stocké sous forme de hash, expiration initiale 15 minutes, journal `CREATED`.
4. Le client connecté dans son portail voit le ticket et peut ouvrir le lien ponctuel associé; si un accès sans connexion est autorisé, prévoir validation secondaire et jeton à très courte durée. Ne jamais faire passer le jeton d'accès MeshCentral au client.
5. Le client télécharge depuis le domaine officiel une application propre au groupe/client et exécute l'assistant; l'association session ↔ périphérique doit être vérifiée côté serveur, et non fondée sur le seul nom de machine ou l'IP.
6. Le technicien voit « Client connecté — autorisation nécessaire », puis demande le contrôle. L'Assistant affiche une demande d'autorisation locale avec identité du technicien. Refus = zéro prise en main.
7. Après accord local explicite, MeshCentral ouvre le viewer et Frappe reçoit un événement fiable `ACTIVE`. Bannière visible côté client et bouton « Arrêter ».
8. Fin par client/technicien/expiration : fermer la session MeshCentral, invalider les jetons, supprimer le périphérique temporaire selon politique, fermer l'accès, journaliser `ENDED`.
9. Le technicien rédige compte rendu lié au ticket et clôture selon workflow existant.

États recommandés : `CREATED`, `INVITED`, `CLIENT_ONLINE`, `AWAITING_CONSENT`, `ACTIVE`, `DECLINED`, `ENDED`, `EXPIRED`, `ERROR`. Le statut `ACTIVE` ne doit pas découler du seul bouton d'approbation Frappe : attendre une confirmation du moteur et l'accord de l'utilisateur local.

## 5. Modèle de données Frappe à créer

DocType `SS97 Remote Session` : 
- `session_id` (UUID unique), `ticket_doctype`, `ticket_name`, `customer` (Link Customer), `technician` (Link User), `state` (Select).
- `mesh_device_id` et `mesh_group_id` (Data; jamais exposer librement à un autre client).
- `invite_token_hash` (Data; aucun jeton en clair au repos), `invite_expires_at` (Datetime), `consented_at`, `started_at`, `ended_at`, `terminated_by`, `termination_reason`.
- `screen_control_allowed`, `clipboard_allowed`, `file_transfer_allowed`, `recording_allowed` (Check; opt-in distinct), `consent_version`.
- `created_by`, `audit_reference`, `client_os` minimal et facultatif.
- Permissions DocType : manager complet, technicien uniquement sessions assignées, client uniquement sessions de ses tickets; appliquer la sécurité **aussi** aux méthodes `@frappe.whitelist`.

DocType `SS97 Remote Event` append-only : `session`, `event_type`, `occurred_at`, `actor`, `source`, `event_id` idempotent, `metadata_json` redigé (jamais jetons/identifiants sensibles ni contenu écran).

Rattachement ticket : le dépôt ne définit pas encore le schéma de ticket; inspecter le DocType réel du site (Issue natif ou custom) et choisir un champ Link dynamique ou une relation contrôlée. Ne PAS inventer de champs dans les tickets déjà en production.

## 6. Contrat API prévisionnel (non implémenté)

Chemin Python visé : `softsystem97/remote/api.py`, exposé en Frappe `/api/method/softsystem97.remote.api.<method>`.

- `prepare_session(ticket_doctype,ticket_name)` : POST, technicien authentifié/assigné, crée session.
- `get_session(session_id)` : GET, technicien autorisé ou client propriétaire.
- `create_invitation(session_id)` : POST, serveur seul, crée une invitation courte et une instruction de téléchargement.
- `bind_device(session_id,device_proof)` : événement serveur vérifié, lie le vrai device ID; ne pas accepter un device_id arbitraire en provenance du navigateur.
- `request_control(session_id)` : POST, technicien autorisé, demande de consentement local via MeshCentral.
- `end_session(session_id)` : POST, client propriétaire ou technicien autorisé, révoque l'accès du viewer et ferme le ticket de session.
- `mesh_event_callback(...)` : réservé au serveur MeshCentral, authentification mTLS ou signature HMAC + horodatage + anti-rejeu, selon le mécanisme d'intégration réellement disponible. Ne pas présumer qu'un webhook existe nativement : si absent, construire un adaptateur meshctrl/API explicite et auditer ses droits.
- `get_ticket_remote_history(ticket_doctype,ticket_name)` : GET, filtrage serveur.

Le backend Frappe ne doit jamais diffuser ni proxyfier les octets de l'écran. Ces flux sont isolés sur MeshCentral.

## 7. Interface

Côté ticket technicien : `Préparer assistance`, `Envoyer le lien`, `Client connecté`, `Demander l'autorisation`, `Prendre la main`, `Terminer`, `Compte rendu`.

Côté client : `Télécharger l'Assistant SoftSystem97`, `Je suis prêt`, nom du technicien, permissions détaillées, `Autoriser`, `Refuser`, voyant de prise en main, `Arrêter immédiatement`. L'accord d'interface portail ne remplace **pas** le dialogue local de consentement du logiciel.

Étape 1 : viewer MeshCentral ouvert dans un onglet sécurisé; étape 2 : intégrer un viewer `iframe` avec `allowFraming` et jetons de connexion MeshCentral créés côté serveur pour un technicien nominatif aux droits limités. Tester CSP `frame-ancestors`, cookies navigateur, durée de vie, protection des URL de jeton et logout.

## 8. Sécurité et exploitation

- HTTPS/WSS, DNS, certificats valides, sauvegardes chiffrées, mises à jour, MFA techniciens, journalisation, chiffrement en transit, limites de sessions simultanées, quotas et supervision.
- Groupes MeshCentral séparés par Customer / entreprise; ne jamais exposer l'accès au domaine AD ou à `SS97-API01` aux clients.
- Autorisation locale non implicite, jamais d'auto-accept sur expiration, arrêt côté client effectif sur serveur; aucun mode silencieux/par défaut ni accès non supervisé.
- Limiter transfert de fichiers, presse-papiers, terminal, élévation admin et enregistrement au strict nécessaire et demander autorisation granulaire.
- Conditions de service, politique de confidentialité, durées de conservation, minimisation des données, vérification contractuelle/RGPD avant production.
- Éviter les URLs administrateur avec jeton 1 h copiées en dur. Secret `loginTokenKey` exclusivement dans le serveur d'intégration et coffre de secrets, jamais dans GitHub.

## 9. Découpage de réalisation

**Étape 0 (présente branche) :** architecture documentée et dépôt confirmé. Aucun agent, aucun tunnel, aucune prise en main active.

**Étape 1 :** labo MeshCentral isolé; DNS `remote.softsystem97.com`; TLS; compte technicien avec MFA; groupes de tests; Assistant Windows ; consentement + arrêt + audit validés sur SS97-PC01 hors environnement client réel.

**Étape 2 :** créer les DocTypes, rôles et API Frappe; tests automatisés des permissions (client A ≠ client B, technicien non assigné, jeton expiré et rejoué, arrêt immédiat); intégrer bouton au DocType de ticket effectivement installé.

**Étape 3 :** adaptateur MeshCentral, association invitation/ticket ↔ device réelle, historique et viewer en onglet avec droits limités; vérifier le comportement réel d'invitation Assistant et le cycle de vie de l'agent.

**Étape 4 :** branding, signature du binaire Windows, liens de téléchargement authentiques et interface française, intégration viewer dans le ticket, multi-clients, suivi opérationnel et conformité.

## 10. Critères de recette

- Aucun technicien ne peut ouvrir un poste sans affectation ticket **et** consentement local.
- Aucune session d'un client n'est visible par un autre; tests négatifs automatisés.
- Un téléchargement au mauvais ticket ne permet jamais de se connecter à la machine d'autrui.
- Fermeture côté client coupe réellement la session et invalide invitation et viewer.
- Déconnexion internet, expiration et redémarrage n'activent pas d'accès automatique.
- Historique ticket : initiateur, technicien, accord, durée, fin et compte rendu.
- Aucune régression Stripe, contrat, notifications, Bridge API/AD.

## Références techniques

- https://docs.meshcentral.com/meshcentral/ (notamment « Embedding MeshCentral »)
- https://docs.meshcentral.com/meshcentral/assistant/
- https://github.com/Ylianst/MeshCentralAssistant
- https://www.cnil.fr/fr/securite-encadrer-la-maintenance-et-la-fin-de-vie-des-materiels-et-logiciels
- https://github.com/softsystem97/softsystem97
