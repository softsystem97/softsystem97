# Intégration du portail historique : recette et déploiement contrôlé

## État et séparation des composants

Base vérifiée : `c5f0be1` sur `fix/ticket-notification-privacy` (la référence fournie `c5f9eb1` n’est pas résolue localement). La PR #3 reste indépendante. Les 66 tests Frappe et 15 scénarios HTTP déjà réussis concernent le pont de développement, pas `/espace-technicien/tickets`. Ils ne sont pas relancés pour cette préparation documentaire.

Les trois sources historiques ne sont pas importées. `SS97 Technician` et `ss97_technician` sont des exigences communiquées, pas des modèles vérifiés ici. Le pont utilise une configuration de rôle explicite et un ToDo lié à une approbation protégée ; il ne lit pas ce champ personnalisé et ne contrôle pas le paiement. **Ne pas le brancher sur la route historique ni l’activer comme solution de paiement.**

La revue des sources accessibles confirme : contrôle de session et de rôle serveur, contrôle d’affectation sur liste/détail/mutation, refus d’auto-affectation par ToDo seul, notifications filtrées par autorisation actuelle. Les écritures internes privilégiées sont bornées après ces contrôles ; elles restent à revoir avec les hooks et permissions réellement déployés. Les droits natifs hérités ne sont pas retirés par ce module.

## Tests historiques à implémenter après import

Statut de tous les cas ci-dessous : **NON EXÉCUTÉ — sources et contrat de données requis**. Ce tableau est un cahier de recette, pas une suite automatisée réussie. Utiliser deux techniciens fictifs A/B, deux clients fictifs C/D et des tickets synthétiques distincts. Aucune fixture ne référence un compte réel.

| Cas | Action serveur et preuve attendue |
|---|---|
| H01 Session | Connexion native avec A ; session reconnue. Guest, session expirée et ancien cookie après logout : aucune donnée ni mutation autorisée. Ne pas désactiver CSRF. |
| H02 Rôle | `SS97 Technician` actif autorise le parcours prévu ; rôle absent, désactivé ou compte désactivé : refus. Tester la variante française séparément selon la politique historique réellement trouvée, sans supposer son équivalence. |
| H03 Affectation | Déterminer depuis le schéma si `ss97_technician` référence User ou un profil. Une affectation serveur valide rend le ticket visible à A seulement ; un paramètre HTTP d’identité falsifié ne change pas ce périmètre. |
| H04 Lecture | Tester liste, pagination, détail par identifiant direct et notifications avec A/B/C/D ; aucun ticket, historique ou contenu d’un autre périmètre ne doit être retourné. |
| H05 Paiement | Identifier la source de vérité, les états et les exemptions depuis le code réel. Pour chaque état non éligible, une tentative directe d’affectation/intervention doit échouer sans effet métier ; un paiement éligible permet uniquement le parcours prévu. Ne pas inventer un champ `paid` ou des statuts. |
| H06 Concurrence paiement | Rejouer un événement de paiement et tenter deux affectations simultanées ; aucun doublon d’affectation, d’intervention ou de notification. Tester annulation/remboursement selon les règles réellement présentes. |
| H07 Intervention | Ticket affecté à A : transition autorisée réussie ; transition interdite, statut périmé et tentative de B refusés. Revérifier les conditions de paiement au point où le code les exige, même pour un appel direct sans interface. |
| H08 Révocation | Réaffecter de A vers B par la procédure autorisée ; vérifier immédiatement listes, détails, mutations et futurs destinataires. Une ancienne clé ou session ne rétablit pas A. |
| H09 Notifications | Avec un collecteur SMTP de staging, vérifier confirmation, affectation et changements prévus : destinataires approuvés, Email Queue, Send After, scheduler/worker, réception unique observée. Les reprises ne créent pas de nouveaux messages ; pas de renvoi des files historiques. |

Après lecture des sources, rattacher chaque cas à la vraie fonction, au DocType et au test automatisé correspondant. Un test simulant une règle inventée ne valide pas l’intégration. Conserver uniquement identifiants synthétiques, résultats et références de commits dans les preuves publiques.

## Déploiement : points d’arrêt obligatoires

1. **Contrat réel.** Importer les sources et dépendances ; relever versions Frappe/ERPNext/apps, commits installés, schémas, hooks, Workflow/Server Scripts, permissions et producteurs de notifications. Comparer avec le commit candidat immuable, pas seulement un nom de branche. Aucune activation tant que paiement, profil et mapping d’affectation restent inconnus.
2. **Sauvegarde vérifiée.** Dans une session administrateur autorisée, exécuter `bench --site <site-technique> backup --with-files` selon les capacités Frappe Cloud ; conserver base, fichiers publics/privés et configuration nécessaire chiffrés hors Git. Vérifier intégrité et restauration dans un staging isolé compatible. Une sauvegarde seulement créée, sans restauration testée, ne valide pas ce point.
3. **Staging isolé.** Neutraliser les sorties réelles et les webhooks commerciaux avant démarrage ; utiliser comptes, données et SMTP de test. Installer le SHA candidat, comparer dépendances, exécuter migrations, construction des ressources et nettoyage du cache suivant la plateforme. Conserver les résultats des migrations et la matrice de permissions avant/après. Le pont reste désactivé sauf recette distincte explicitement approuvée.
4. **Recette.** Exécuter H01–H09 sur les sources intégrées et les seuls tests existants affectés par les modifications. Vérifier les refus via appels serveur et interfaces natives accessibles, pas seulement par masquage JavaScript. Tout échec de confidentialité, paiement, migration ou restauration bloque la livraison.
5. **Approbation.** Présenter le SHA, les différences, migrations, permissions, routes modifiées, preuves de staging, fenêtre d’intervention et procédure de retour. Toute modification du compte existant nécessite une approbation séparée indiquant exactement le rôle/profil à ajouter ; aucune réinitialisation, duplication ou attribution de System Manager. Aucun script de ce document ne modifie ce compte.
6. **Production autorisée seulement.** Refaire une sauvegarde vérifiée et capturer le SHA initial avant installation du SHA approuvé. Appliquer uniquement les migrations validées. Après redémarrage, vérifier versions/commit, route et session, refus Guest, permissions, état du scheduler et des files. Un parcours avec ticket et destinataires approuvés exige son autorisation propre ; l’authentification du technicien se fait par lui-même sans transmettre son mot de passe.

## Retour arrière et preuve finale

Déclencheurs : accès transversal, intervention sans condition de paiement requise, migration échouée, erreur de session bloquante ou notifications inattendues. Suspendre le nouveau parcours par le mécanisme revu en staging ; pour le pont distinct, désactiver `ss97_ticket_bridge.enabled`. Conserver journaux expurgés et reçus, ne pas purger les tickets, affectations ou e-mails et ne pas vider la file.

Revenir au SHA sûr identifié avant livraison par le mécanisme Frappe Cloud validé. Un retour de code ne constitue pas une migration inverse : si le schéma n’est plus compatible, maintenir le parcours indisponible et faire approuver une restauration avec traitement explicite des écritures intervenues depuis la sauvegarde. Ne jamais réactiver une version du pont qui fait confiance aux ToDo seuls. Restaurer uniquement les permissions/configurations effectivement modifiées, après revue administrative.

Après retour : vérifier commit, cache, disponibilité du parcours antérieur, refus d’accès, données conservées et état des files sans renvoi massif. La décision finale doit distinguer tests de laboratoire, staging et production, avec résultat, SHA et preuve pour chacun. Aucune de ces opérations serveur n’a été exécutée par cette préparation.
