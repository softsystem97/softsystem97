# SS97 — reprise de l'accès technicien N2 (19 novembre 2026)

## Constats et limites des preuves

- Captures fournies : `/espace-technicien/dashboard` affiche « Accès refusé — rôle technicien actif requis », et `/espace-technicien/login` affiche « Votre compte ne possède pas l'accès Technicien ».
- La récupération de mot de passe s'affiche dans le panneau `login#forgot` ; une capture ultérieure montre une navigation vers `/desk/home#forgot` avec « Page d'accueil introuvable ». **L'origine de cette redirection est à récupérer dans la page/JS effectivement déployé, sans réinitialiser un mot de passe ni supposer que l'e-mail est parti.**
- Les contrôleurs historiques récupérés du dépôt exigent le rôle `SS97 Technician` ; `SS97 Technicien` est le nom de préparation du *pont de développement distinct*. Ces deux noms ne sont pas des alias automatiques.
- Le code de Web Page pour `/espace-technicien/login` et `/espace-technicien/dashboard`, les règles de profil actif et l'état du compte visé ne sont pas fournis par le dépôt. Aucun changement de ce dépôt ne peut, seul, lever le refus d'accès sur le site commercial.
- Les comptes N2/N3/N4 de test avaient été envisagés ; ni leur création réelle, ni leur invitation, ni leur première connexion ne sont confirmées.

## Correctif préparatoire conservateur dans cette branche

1. `softsystem97.technician_readiness.administrator_n2_access_report` inspecte, en lecture seule et **uniquement en console System Manager**, un User déterminé et les deux rôles. Il indique pourquoi les préconditions historiques sont bloquées, ou l'état `ROLE_CHECKS_PASSED_PROFILE_UNVERIFIED` si elles passent. Il ne promet jamais que la Web Page ou le profil est autorisé.
2. `softsystem97.provisioning.prepare_historical_technician_role()` prépare par défaut, sans écriture, **le rôle exact** `SS97 Technician`. Le programme français existant, séparé, reste inchangé. Aucune attribution utilisateur, invitation, permission globale ou création en production n'est faite.
3. L'inventaire privé `portal_route_metadata` inclut maintenant les routes `espace-technicien/login` et `espace-technicien/dashboard` en plus des routes de tickets. Il permet à l'opérateur de rechercher la véritable implémentation sans copier secrets/HTML clients.

### Utilisation, après installation de cette branche en staging approuvé

```bash
bench --site <staging-autorise> execute softsystem97.technician_readiness.administrator_n2_access_report --kwargs '{"user":"<utilisateur-N2-fictif>"}'
bench --site <staging-autorise> execute softsystem97.provisioning.prepare_historical_technician_role
bench --site <staging-autorise> execute softsystem97.diagnostics.portal_route_metadata
```

Résultats à examiner localement, sans publier comptes réels, scripts de connexion, jetons, cookies, secrets SMTP ou données clients.

## Ordre de résolution sur le staging

1. Identifier le SHA installé, la source Web Page/Client Script du login/dashboard et le modèle réel de « technicien actif ». Recueillir champs et type de profil, nom du rôle vérifié et logique de redirection du lien de récupération. Séparer session Guest, rôle absent et profil inactif.
2. Vérifier le compte N2 de test : présent, `enabled=1`, rôle historique `SS97 Technician` existant et activé, liaison vers le **profil réellement exigé**, actif, et périmètre de tickets limité. Appliquer dans l'interface administrative de staging les seuls droits confirmés après revue. Ne pas attribuer System Manager ni élargir Issue globalement.
3. Tester le login normal, le refus d'un autre compte, la déconnexion et la récupération sur une boîte de test contrôlée. Corriger le JS ou le paramètre de redirection de la **vraie** Web Page : jamais de redirection de récupération vers `/desk/home#forgot` si ce chemin n'existe pas. Vérifier que le mail est réellement reçu une seule fois, sans relancer les anciennes files.
4. Tester les profils N2/N3/N4 avec utilisateur, client et tickets fictifs, sans paiements réels et sans contrats signés. Valider tickets affectés, transitions permises, refus hors périmètre, notifications et historique.
5. Pour l'assistance à distance ASUS technicien → Dell client : code à usage unique, durée maximale d'une heure, consentement du client dans le portail **et** consentement local MeshCentral, connexion/déconnexion effective et révocation contrôlée. Les tests 22/22 du protocole ne démontrent pas cette connexion réelle. Ne pas activer l'automatisation ni présenter `engine_connected=False` comme un bureau distant opérationnel.

Le producteur d'invitation e-mail optionnel (`softsystem97.remote.invitation`) est prêt pour une validation contrôlée : destinataire dérivé du ticket, compte sortant explicite, lien HTTPS, aucun code/session appareil transmis et file demandée avec la transaction du ticket. Il reste désactivé tant que `ss97_remote_assist.email_enabled` n'est pas explicitement vrai sur staging. Les 7 tests unitaires additionnels sont hors réseau ; aucune livraison SMTP réelle n'est confirmée.

## Validation et livraison

```bash
python tools/test_technician_readiness_offline.py
python -m compileall -q softsystem97/technician_readiness.py softsystem97/provisioning.py softsystem97/route_metadata.py
git diff --check
```

Ces contrôles sont **hors ligne**. Ils ne valident pas l'accès commercial, la réception SMTP de production, l'intervention réelle, un déploiement ou une restauration de sauvegarde.

Repli : aucun état utilisateur/site n'étant modifié par ces diagnostics, ne pas les exécuter en cas de doute sur les permissions ; revenir au commit précédent de staging. Toute modification de Web Page, rôle ou profil exige sa sauvegarde préalable, une recette isolée et l'autorisation de déploiement en production distincte.
