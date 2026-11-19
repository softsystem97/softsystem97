# Correctif de connexion technicien — site Frappe

## Problème ciblé

Les Web Pages historiques vérifient le rôle du compte dans le navigateur via
`frappe.core.doctype.user.user.get_roles`, `frappe.client.get_list` sur les
`SS97 Technician Application` et `Employee`. Pour un compte de portail, ces
appels peuvent échouer faute de permission de lecture. Une erreur est parfois
interprétée comme un profil sans accès, même lorsque le rôle est attribué.

## Correction proposée

- `softsystem97.portal.technician_access.my_technician_access` est une méthode
  authentifiée sans paramètre `user`. Elle lit **uniquement le compte en cours**,
  vérifie qu'il est activé et qu'un des rôles techniciens reconnus existe et
  n'est pas désactivé. Elle ne consulte pas les profils d'autres utilisateurs.
- `technician_session_auth.js` remplace le résolveur global historique des
  pages `espace-technicien`, avec un appel serveur utilisant les cookies de
  session. Les erreurs HTTP échouent en mode fermé.
- `web_include_js` charge l'adaptateur depuis l'app installée. Les API métier
  de tickets et de contrôle distant continuent leurs propres vérifications de
  permission, indépendamment de l'affichage du portail.
- Ce correctif **ne crée ni ne modifie aucun rôle**, compte, profil, affectation
  de ticket ou consentement distant.

## Déploiement contrôlé

1. Installer la branche sur un site de staging approuvé, régénérer les assets
   selon la procédure Frappe Cloud et vérifier dans les outils réseau que le
   fichier `technician_session_auth.js` est chargé **après** les anciens scripts
   d'authentification du site. Contrôler la réponse JSON du nouvel endpoint.
2. Avec des identifiants fictifs, valider : utilisateur avec `SS97 Technician`
   actif → tableau de bord ; utilisateur sans rôle → refus ; compte désactivé,
   session Guest et rôle désactivé → refus ; erreur réseau → pas d'accès.
3. Vérifier séparément le comportement de `ss97_technician_login_v4.js`
   administré hors du dépôt. Si ce script possède un deuxième contrôle de rôle
   indépendant, le raccorder au même endpoint avant toute mise en production.
4. Confirmer la bonne isolation des données métier, l'expiration de session,
   la déconnexion, le changement d'utilisateur et la reprise sur un autre poste.
5. Préserver une sauvegarde et un plan de retour à l'ancienne version de
   `web_include_js`. Ne pas fusionner ni déployer sur le site commercial sans
   recette de staging et autorisation distincte.

## Tests locaux

```bash
python tools/test_technician_session_auth_offline.py
node tools/test_technician_session_auth_offline.js
node --check softsystem97/public/js/technician_session_auth.js
```

Les tests locaux ne démontrent ni une connexion sur le serveur commercial ni
une ouverture de session MeshCentral.
