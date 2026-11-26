# SS97 MeshCentral Gateway — laboratoire et sécurité

**Statut : contrat logiciel expérimental, pas une prise en main active.**
Cette branche n'installe ni agent Windows, ni compte MeshCentral, ni route
publique de contrôle distant. La production SS97 et les paiements restent
inchangés.

## Contrat ajouté

- `softsystem97.remote.gateway_protocol` définit les événements de la future
  passerelle isolée : `LOCAL_CONSENT_GRANTED`, `DESKTOP_CONNECTED`,
  `DESKTOP_DISCONNECTED`.
- Les événements sont authentifiés en HMAC-SHA256, horodatés et dotés d'un UUID
  unique. La vérification exige un stockage central anti-rejeu **atomique**.
- L'état `ACTIVE` ne doit jamais résulter d'un clic portail : il exige les
  événements vérifiés **d'accord local et de connexion**, sur la même session
  et le même appareil, dans cet ordre.
- Le futur service doit en outre recontrôler l'entreprise, l'affectation du
  technicien, le ticket, l'appareil lié côté serveur et la durée autorisée.

## Pour passer de ce contrat à un vrai essai sur deux PC

1. Préparer **un serveur MeshCentral de laboratoire isolé** et configuré pour
   l'accord local obligatoire, sans acceptation automatique ou accès permanent.
2. Installer volontairement l'agent de test sur le poste client ; ouvrir une
   session sous contrôle d'un utilisateur présent sur ce poste.
3. Enregistrer la liaison entre l'entreprise test, le ticket SS97 et l'appareil
   uniquement côté serveur, après vérification du propriétaire.
4. Exécuter une passerelle MeshCentral avec identité de service dédiée et MFA
   pour les techniciens, secrets hors Git et TLS avec vérification stricte.
5. Générer un partage de bureau limité dans le temps ; vérifier la politique
   de consentement local de MeshCentral et la durée de 60 minutes.
6. Implémenter l'échange d'événements réel, la révocation côté moteur et le
   contrôle de confirmation de coupure, avec un état `ERROR` si incertain.
7. Répéter les tests de refus, déconnexion, coupure réseau, autre client,
   transfert de technicien, code réutilisé, expiration et prolongation.

## Tests hors serveur

`python -m unittest tools.test_remote_gateway_protocol_offline`

Ils vérifient le **contrat cryptographique**, pas l'intégration MeshCentral.
Ne pas activer l'état `ACTIVE` à partir de ce seul module ni exposer sa fonction
de signature dans une API accessible à un client ou un technicien.

Sources techniques à vérifier lors de l'adaptation :

- [MeshCentral — configuration avancée](https://github.com/Ylianst/MeshCentral/blob/master/sample-config-advanced.json)
- [LibMeshCtrl — API partage de bureau et consentement](https://github.com/Ylianst/LibMeshCtrl/blob/main/doc/api.md)
