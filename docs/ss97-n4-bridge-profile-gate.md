# Pont N4 — profil réellement habilité obligatoire

Les accès ticket et l'attribution via le pont ne peuvent pas être acquis
avec le seul rôle SS97 Technicien N4. Ce rôle doit être exclusif parmi les
filières techniques; chaque appel revérifie la fiche SS97 Technician Profile
rattachée au vrai User, sa filière CYBER, son état ACTIVE et son engagement
FREELANCE. La suspension/révocation du profil supprime immédiatement
l'accès via l'API du pont.

Pour une configuration de pont réservée au N4, le Site Config privé doit
contenir `technician_role:"SS97 Technicien N4"` et
`profile_required:true`. La valeur false historique ne permet pas
de sécuriser le N4 et est donc refusée pour cette filière. Les autres
filières historiques continuent à exiger false tant que leur adaptateur
spécifique n'est pas développé.

Ce changement ne crée aucun profil, ne valide aucun examen ni contrat,
ne modifie aucun rôle et ne désactive aucun script ERPNext.
Une habilitation individuelle N4 reste une décision humaine indépendante.
