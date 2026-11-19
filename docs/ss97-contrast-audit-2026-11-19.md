# SS97 — audit d'accessibilité du contraste (19 novembre 2026)

## Constats vérifiés sur le site public

- `/espace-technicien/login` : les champs `#ss97-login-usr` et `#ss97-login-pwd`
  ont une couleur de texte calculée `rgb(15, 23, 42)` sur un fond
  `rgb(7, 17, 29)`, soit un rapport de contraste d'environ **1,12:1**.
  Les textes saisis sont donc pratiquement invisibles. Ce problème dépasse
  le champ de mot de passe.
- Sur cette page, le lien « Support technicien » hérite lui aussi d'un texte
  sombre alors que le fond est sombre (`.ss97-tl-assist a`).
- `/recrutement` : le bouton « Voir les offres » (`.ss-btn-contour`) emploie
  un texte bleu sombre transparent sur le fond bleu sombre du bandeau.
- Les pages `/contact`, `/devis-gratuit`, `/ticket-libre`, `/connexion-client`
  et `/recrutement` ont été parcourues sans compte de test ni soumission.
  Aucun contrôle de saisie visible n'apparaissait au premier écran lors de
  cette revue; les formulaires secondaires/dynamiques restent à vérifier.

## Correctifs proposés

1. Sur les pages Web SS97 : appliquer **ensemble** un fond clair `#f7fbff`
   et une écriture foncée `#142b3e` aux champs texte, e-mail, recherche,
   téléphone, URL, nombres, dates, listes et zones de texte. Garder les
   cases à cocher, boutons radio, fichiers et boutons d'action intacts.
2. Sur les portails et le Desk : même paire de couleurs pour les mots de
   passe, avec gestion de l'auto-remplissage Chromium/Android.
3. Sur les portails : ajout d'une commande facultative pour dévoiler un mot
   de passe pendant dix secondes au maximum, avec remasquage sur perte de
   focus, soumission ou passage de l'onglet en arrière-plan. Aucun secret
   n'est envoyé, imprimé ou conservé par cette commande.
4. Renforcer les couleurs des liens d'assistance et boutons contour concernés.

## Vérification / limite

- Tests unitaires hors ligne pour présence des styles, contrastes (WCAG AA
  4,5:1 pour ces paires), contrôle d'affichage temporaire et non-régression.
- Après installation sur un **site Frappe v16 de préproduction**, vérifier
  sur mobile et ordinateur : login technicien, login client, récupération
  de mot de passe, formulaires, recrutement, ticket libre et Desk.
- L'application historique de production pourrait contenir d'autres styles
  propres à ses Web Pages. Tant que le correctif n'est pas déployé et que
  les chemins réels ne sont pas testés, ne pas annoncer tous les contrastes
  comme résolus.
- Le message « Votre compte ne possède pas l'accès Technicien » concerne
  une autorisation **distincte** et n'est pas corrigé par du CSS.
