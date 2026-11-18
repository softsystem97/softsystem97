# SS97 Remote Assist — constat du test Asus / Dell

Date : 17 novembre 2026 (Guadeloupe). Environnement : laboratoire autorisé.

## Faits observés avec le fondateur

- Asus : poste du technicien ; Dell : poste client de test.
- MeshCentral indiquait `Connected` sur les captures fournies.
- Le bureau Windows du Dell, l'Explorateur de fichiers et la barre des tâches
  étaient visibles depuis l'Asus ; le fondateur a confirmé pouvoir naviguer.
- L'écran noir initial était principalement la marge de l'affichage distant.
  Une vue de bureau agrandie a ensuite été obtenue. Un vrai plein écran
  navigateur sans barre d'onglets n'est pas démontré par les captures.

**Résultat limité : transport visuel et interaction validés manuellement dans
le laboratoire.** Cela ne prouve ni la liaison automatique à un ticket ERPNext,
ni l'identité de l'appareil, ni le consentement local vérifié, ni une coupure
réelle sur révocation. Les captures montrent un accès `127.0.0.1` ; elles ne
prouvent pas non plus une connexion depuis Internet.

## Briques disponibles dans la branche

- `softsystem97.remote.api` : ticket, technicien, code 9 chiffres valable une
  heure et à usage unique, décision dans le portail, journal et révocation des
  demandes encore en attente. Aucune prise de contrôle automatique.
- `softsystem97.remote.gateway_protocol` : trois types d'événements distants
  signés, contrôle d'âge et protection anti-rejeu exigée.
- `softsystem97.remote.receipts` : vérification supplémentaire de la liaison
  serveur de l'appareil pour activer une session, et preuve de sa déconnexion
  avant de la déclarer terminée. Fonctions pures, non connectées au moteur.

## Prochaine recette V1 obligatoire avant déploiement

1. En préproduction Frappe v16, créer un ticket de test appartenant au client A
   et affecter un technicien A ; vérifier paiement et droits déjà en place.
2. Lier côté serveur l'appareil Dell au client A et au ticket, sans accepter un
   identifiant transmis par le navigateur.
3. Mettre un utilisateur physiquement devant le Dell ; afficher une demande
   d'accord local nominative ; vérifier qu'il peut refuser et interrompre.
4. Faire émettre par une passerelle MeshCentral isolée les événements
   authentifiés et anti-rejeu de consentement, connexion et déconnexion.
5. Vérifier un début `ACTIVE` seulement après consentement local et connexion,
   puis une fin `ENDED` seulement après coupure distante confirmée.
6. Tester refus, révocation, expiration, perte réseau, autre entreprise B,
   code réutilisé et fermeture de ticket ; vérifier les journaux.

Ne pas activer le contrôle distant sur `app.softsystem97.com` avant cette
recette. Aucun secret, compte Windows ou token MeshCentral ne doit être ajouté
au dépôt.

## Tests de sécurité exécutables sans serveur

```bash
python -m unittest tools.test_remote_gateway_protocol_offline tools.test_remote_receipts_offline
```

Ces tests ne simulent pas un vrai écran ni un consentement Windows. Ils
garantissent seulement les règles pures de validation des preuves signées.
