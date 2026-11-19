# SS97 Assistance à distance — N2 / bancaire / cybersécurité

**État : code d'orchestration prêt pour revue, PAS un service distant en production.**
**Application en production :** `https://app.softsystem97.com` (Frappe Cloud, ERPNext v16).
**Cible :** une seule plateforme SS97, sans nouveau site Frappe Cloud.

## Ce qui a déjà été validé

- Un essai réel **ASUS technicien → Dell client** a permis de voir et piloter
  l'écran du Dell à travers MeshCentral **sur le réseau local** le 18/11/2026.
  Il ne démontre ni une passerelle Internet SS97 en production, ni l'intégration
  du ticket à ce moteur, ni la révocation depuis le portail.
- Les espaces SS97 TECH OS existent pour L2 (N2 généraliste), BANK (N3 bancaire)
  et CYBER (N4 cybersécurité). Les parcours d'examen, justificatifs, contrat,
  activation humaine, missions et contrôles sensibles sont conservés.
- La branche de développement comportait une coordination Remote Assist V1
  (code de neuf chiffres, consentement portail, historique) et un **contrat**
  d'événements MeshCentral ; aucune connexion réelle n'était déclenchée.

## Ce que cette intégration prépare

1. Un **seul portail** `/ss97-remote-assist` pour L2, BANK et CYBER.
2. Un lien vers le formulaire depuis chaque mission **IN_PROGRESS** des trois
   espaces. Le ticket sert de référence de navigation, jamais de preuve d'accès.
3. Vérification, sur le serveur, de **toutes** les conditions : compte actif,
   profil ACTIVE/FREELANCE, rôle exact et non désactivé, spécialité correspondante,
   absence de rôles d'administration/comptabilité incompatibles, affectation
   du ticket approuvée, Customer/Portal User cohérents, mission
   IN_PROGRESS acceptée et propriétaire du ticket inchangé.
4. Pour BANK/CYBER : référence de périmètre écrite et deuxième approbateur
   distinct du coordinateur et du technicien. Les habilitations ne sont pas
   mutualisées entre les trois spécialités.
5. Code d'assistance 9 chiffres, usage unique, fenêtre d'une heure, empreinte
   HMAC stockée ; accord/refus portail, journal d'événements, arrêt de demande.
6. Invitation e-mail **facultative**, envoyée uniquement à l'utilisateur client
   vérifié du ticket et sans code de session. Le serveur demande la mise en
   file SMTP ; cela ne garantit pas la réception.
7. Retrait des invitations en attente lors de la clôture/modification du ticket,
   retrait d'affectation, suspension du profil ou arrêt de la mission.

Les réglages sont **désactivés par défaut**, et la fonction `engine_connected`
reste à `false`. Aucun ordinateur ne peut être contrôlé par ces seules API.

## Ce qu'il manque pour être réellement comparable à AnyDesk / TeamViewer

| Priorité | Livrable | Critère vérifiable |
|---|---|---|
| P0 | Déploiement N2 et activation TECH OS | Connexion du N2 habilité, profil réellement actif, aucune visibilité Comptabilité/Banque/Config non autorisée |
| P0 | Liaison tickets / missions | Affectation approuvée, statut IN_PROGRESS, autorisation et paiement vérifiés |
| P0 | Serveur MeshCentral Internet séparé | DNS, TLS vérifié, MFA administrateurs, groupes clients isolés, sauvegarde et supervision |
| P0 | Passerelle serveur SS97 ↔ MeshCentral | Liaison **côté serveur** appareil↔client↔ticket, partage à durée limitée, pas de secret MeshCentral dans le navigateur |
| P0 | Accord local et arrêt forcé | Le Dell autorise/refuse, le Dell peut arrêter, le backend confirme la coupure moteur avant de déclarer la session finie |
| P0 | Application Windows SS97 Assistance | Programme signé, édité sous l'identité SS97, vérifié Windows Defender, installation et désinstallation propre |
| P0 | Test réel Internet ASUS→Dell | Deux réseaux différents, invitation e-mail délivrée, consentement, contrôle bureau, refus, expiration et déconnexion testés |
| P1 | Rapports et qualité de service | Rapport ticket, temps exact confirmé par le moteur, retour client et incident réseau |
| P1 | Versions ES/EN/FR/HT | Traduction intégrale du parcours sans accès de données d'une autre spécialité |

## Activation future sur le seul site SS97

1. Sauvegarde Frappe Cloud ; vérification du commit réellement installé et de
   l'absence d'un déploiement déjà en cours.
2. Revue et fusion de ce code via PR, puis migration Frappe Cloud contrôlée.
3. Les DocTypes `SS97 Remote Session` et `SS97 Remote Event` restent accessibles
   en lecture administrative ; les mutations passent par les API sécurisées.
4. Après vérification du pont de tickets, du compte et des missions, activer
   `ss97_tech_os` et `ss97_remote_assist` avec validation métier réelle.
5. L'e-mail reste désactivé tant que le compte sortant et la réception réelle
   ne sont pas validés. Configurer `ss97_remote_assist.email_enabled=true`
   et un `email_account` seulement après test. Ne jamais inclure le code à neuf
   chiffres ni un secret de passerelle dans un e-mail.
6. Conserver la passerelle de **prise en main réelle** désactivée tant qu'elle
   ne sait pas attester l'accord LOCAL_CONSENT_GRANTED puis DESKTOP_CONNECTED,
   et confirmer DESKTOP_DISCONNECTED et la révocation à chaque arrêt.
7. Vérifier sur l'ASUS et le Dell le refus, l'acceptation, le retour à l'état
   normal, le changement de technicien, le retrait de mission et les coupures.

Les catégories BANK et CYBER peuvent manipuler des systèmes particulièrement
sensibles. Pour ces clients, définir la portée technique par écrit ; toute
prise en main sur un environnement réglementé doit respecter les contrôles de
sécurité propres au client (dont consentement et journalisation, et si requis
double validation opérationnelle).

## Vérification hors site

```bash
python -m unittest tools.test_remote_access_offline \
  tools.test_remote_api_offline tools.test_remote_assist_offline \
  tools.test_remote_gateway_protocol_offline tools.test_remote_invitation_offline
```

Ces tests ne constituent **pas** une recette Frappe Cloud ni un test distant.
