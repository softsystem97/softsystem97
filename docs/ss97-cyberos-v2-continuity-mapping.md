# CyberOS V2 — périmètre réellement développé

- **CyberTwin initial** : dépendances déclaratives entre deux actifs appartenant au même Customer; les liens ne sont pas une analyse de chemins d'attaque vérifiée.
- **CyberRecovery / Résilience Caraïbes** : registre de continuité, scénario de cyclone, panne Internet ou électrique, perte de données et consignes de repli. Les plans ne sont ni testés ni approuvés automatiquement.
- **CyberLab initial** : préparation de scénarios d'exercice et enregistrement possible des enseignements via API; aucun moteur de simulation IA ni attaque réelle.
- **CyberDirector initial** : indicateurs déclaratifs sur les actifs, actions, incidents, dépendances, plans et exercices.
- Les trois DocTypes Frappe v16 sont privés. L'autorisation du client dépend du Customer unique lié à sa session. Les éléments liés à des actifs sont revalidés sur l'identifiant Customer.
- **Non inclus** : surveillance réelle, connecteurs Microsoft 365/EDR, IA active, service d'astreinte, contrat de signature, paiements, crédits, token ou scan actif.
- Feature flag privé `ss97_cyberos.enabled` déjà requis en V1, ainsi que le pont ticket validé.
- **Installation nécessaire** : sauvegarde, migration Frappe Cloud, vérification de l'isolation multi-entreprise, tests natifs ERPNext/Frappe et validation métier. La fusion GitHub n'est pas un déploiement.
- Messagerie conservée : `contact@softsystem97.com`.

**Livraison** : code de socle, pas un service certifié. Les alertes et décisions IA futures exigent contrats fournisseurs, évaluation RGPD et permissions explicites.
