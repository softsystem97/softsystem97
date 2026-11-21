# Contrôle privé du pont client–technicien

Le module `softsystem97.integrations.ticket_bridge.readiness` expose uniquement
une méthode GET pour un System Manager actif. Il ne renvoie aucune identité de
compte Support Team ni clé secrète, ne modifie aucun ticket et ne permet pas
de créer une habilitation N4.

- Pré-requis : rôles activés et configurés; un compte System User non
  Administrator avec rôle Support Team choisi comme writer_user; schéma de
  l'événement d'affectation; statuts natifs Issue compatibles; absence de
  Workflow/Server Script Issue contradictoire; adaptateur de profil
  explicitement validé.
- Le rapport compare les prérequis à la configuration privée du site.
- `activation_prerequisites_met` est un diagnostic technique et ne constitue
  PAS un mandat de sécurité, ni un accord professionnel N4.
- L'activation du pont reste sous le contrôle d'un administrateur habilité,
  après recette multi-utilisateurs et sauvegarde. Aucun rôle, contrat,
  signature, Stripe ou e-mail n'est modifié par la méthode.
