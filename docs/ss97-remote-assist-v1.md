# SS97 Remote Assist V1.1 — préparation et parcours sécurisé

Statut : **implémentation pilote non déployée**. Branche `feature/ss97-remote-assist-v1`,
basée sur `feature/ss97-final-integration`. Le laboratoire MeshCentral d'octobre
2026 n'est pas considéré comme un serveur de production.

## Ce que V1 implémente

1. Tech authentifié et affecté au `Issue` natif : `prepare_session` vérifie le
   pont de tickets existant, la politique métier et la règle de paiement déjà
   configurée. Aucun droit supplémentaire n'est donné aux techniciens.
2. Code aléatoire de **9 chiffres**, remis une seule fois au technicien. Seule
   son empreinte HMAC est conservée en base; fenêtre d'une **heure** à partir
   de sa préparation, à la demande du fondateur SS97. Le code est consommé
   dès que le client légitime le saisit correctement.
3. Client authentifié et propriétaire de ce même ticket : `join_session`
   valide le code, le Customer et le `Portal User` sans accès interclients.
   Limite applicative de cinq erreurs sur quinze minutes par utilisateur.
4. Accord/refus dans le portail, consultation de l'état, arrêt de la demande,
   journal append-only des transitions. L'acceptation du portail **ne remplace
   jamais l'autorisation locale** dans le logiciel client MeshCentral.
5. Invitations en attente révoquées si le ticket est clôturé ou si l'affectation
   est perdue; tâche de nettoyage des demandes expirées.
6. Interface web `/ss97-remote-assist` reliée aux méthodes Frappe.

La fenêtre d'une heure règle **l'invitation à rejoindre**, pas encore la durée
d'une prise en main réelle ni la facturation d'une prestation. La future durée
de travail commencera uniquement quand le moteur distant aura attesté une
connexion et un consentement local. Sa prolongation devra être expressément
acceptée par le client. Les rendez-vous à l'avance ne sont pas implémentés ici.

## Ce que V1 NE FAIT PAS

- Ne télécharge, n'installe et ne connecte aucun agent Windows.
- N'ouvre pas de flux écran, de clavier, de souris, de terminal ou de fichiers.
- Ne crée pas de partage ni de compte MeshCentral. Aucun état `ACTIVE` ne peut
  être obtenu via le portail.
- Ne fournit ni code à un anonyme, ni accès non supervisé, ni contournement des
  protections Windows/antivirus.
- Ne peut pas garantir l'arrêt d'une **vraie** session MeshCentral tant que
  l'adaptateur de révocation effective n'a pas été développé et testé.

## Installation uniquement sur une préproduction Frappe/ERPNext v16

1. Garder la production `app.softsystem97.com` et son code de paiement séparés.
2. Installer cette branche sur un **site de préproduction jetable** et exécuter
   la migration contrôlée (`bench --site <site-test> migrate`).
3. Vérifier les DocTypes `SS97 Remote Session` et `SS97 Remote Event` et leurs
   seules permissions natives `System Manager` (lecture). L'accès technique à
   ces documents passe exclusivement par les APIs à contrôles d'identité.
4. Auditer d'abord les prérequis de `ss97_ticket_bridge` existants : rôle
   technicien, lien Customer/Portal User, ToDo attribué et approuvé, compatibilité
   Issue et règles de paiement. Ce nouveau module **ne contourne aucun prérequis**.
5. Sur le site **de test uniquement**, déclarer dans `site_config.json` :

   ```json
   {
     "ss97_remote_assist": {"enabled": true}
   }
   ```

   Une clé `encryption_key` de site forte et existante est obligatoire. Ne
   jamais publier cette clé, un mot de passe, un code de session, ni de token
   MeshCentral dans Git.
6. Tester les deux rôles séparément dans `/ss97-remote-assist` : compte client
   titulaire du ticket et technicien approuvé. Effectuer les tests négatifs
   (autre client, technicien non affecté, ticket fermé, code erroné, expiration,
   répétition de l'accord, retrait de l'affectation) et contrôler les événements.
7. Exécuter `python -m unittest tools.test_remote_assist_offline` pour tester la
   génération des codes et la machine à états. Ces tests sont **insuffisants**
   pour certifier les autorisations réelles dans Frappe.

## Étapes restantes avant la prise de contrôle réelle

1. Disposer de `remote.softsystem97.com` sur un serveur **isolé**, HTTPS/WSS,
   sauvegardes, MFA et groupes MeshCentral séparés par entreprise.
2. Tester l'Assistant MeshCentral sur deux Windows de laboratoire, sans accès
   permanent ni autorisation automatique. L'utilisateur doit pouvoir refuser
   et couper l'accès depuis son propre poste.
3. Écrire un adaptateur serveur côté MeshCentral permettant de créer **un
   partage de bureau de durée limitée** pour un appareil associé de manière
   vérifiable au client/ticket. Aucune URL ni device ID arbitraire ne doit être
   accepté depuis le navigateur. Consentement natif à chaque connexion.
4. Ajouter un canal d'événements **authentifié et anti-rejeu** permettant de
   constater l'accord local, la connexion et la coupure. Activer l'état `ACTIVE`
   seulement après cette preuve, puis vérifier la révocation effective côté
   MeshCentral (et non uniquement côté Frappe).
5. Tester en préproduction la révocation, les coupures réseau, le redémarrage,
   la gestion des accès multi-clients, l'audit et l'absence de régression sur
   les tickets, paiements Stripe, notifications et le pont de domaine.
6. Préparer la signature et l'identification du logiciel Windows et les
   documents RGPD avant toute utilisation sur un poste d'entreprise cliente.

Documentation amont pour la suite : [MeshCentral](https://github.com/Ylianst/MeshCentral),
[exemple de configuration des invites de consentement](https://github.com/Ylianst/MeshCentral/blob/master/sample-config-advanced.json)
et [API LibMeshCtrl](https://github.com/Ylianst/LibMeshCtrl/blob/main/doc/api.md).
