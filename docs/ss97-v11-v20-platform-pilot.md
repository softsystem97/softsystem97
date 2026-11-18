# SS97 ONE — extension V11 à V20, préproduction uniquement

Ce lot prolonge le socle V1–V10 de **Soft System 97**, Frappe/ERPNext v16.
Il ne modifie pas le serveur MeshCentral Asus/Dell, le site Frappe Cloud,
le système Stripe, ni les autres projets (LINGOMED, La Colombe Presta).

## Nouvelles fiches sécurisées

| Version | Type de fiche enregistré | Action externe non disponible |
| --- | --- | --- |
| V11 Remote Assist Pro | Symptôme d'affichage, appareil déclaré et note de résolution | Aucune connexion ni correction d'écran |
| V12 Prédiagnostic | Symptômes, composant et tests proposés | Aucun diagnostic automatique |
| V13 Réparation assistée | Procédure, risque, étapes et retour arrière | Aucune commande exécutée |
| V14 Portail premium | Besoin client et suivi | Aucun abonnement ou compte créé |
| V15 Dispatch | Compétence et proposition d'affectation | Aucun technicien réaffecté |
| V16 Supervision | Constat humain avec date UTC et site déclaré | Aucune télémétrie ni scan |
| V17 Continuité | Périmètre, état déclaré et preuve à vérifier | Aucune sauvegarde/restauration lancée |
| V18 Copilote | Synthèse, suggestions et avis humain | Aucun fournisseur IA connecté |
| V19 Entreprises/collectivités | Projet et secteur d'organisation | Aucun contrat ni message expédié |
| V20 Indicateurs | Définitions de métriques et sources à contrôler | Aucun calcul BI automatique |

Les fiches utilisent les mêmes DocTypes (`SS97 Platform Record` et
`SS97 Platform Event`) que V2–V10. Les données sont liées côté serveur à un
ticket et une entreprise. Seul le technicien effectivement autorisé peut
créer ces fiches ; le client peut consulter les fiches de son ticket mais
pas créer de fiche V11–V20. Les changements d'état sont journalisés.
Les fichiers affichent uniquement du texte ; ils ne sont pas une preuve que
le système distant a été observé ou qu'une intervention a été réalisée.

## Activation séparée et sécurisée

Les anciens modules restent soumis au drapeau existant :

```json
{"ss97_v1_v10": {"enabled": true}}
```

V11–V20 restent invisibles **par défaut** dans le catalogue, les listes et
les API de lecture/écriture. Sur un **site de préproduction isolé** et après
une migration Frappe contrôlée, on peut ajouter :

```json
{"ss97_v11_v20": {"enabled": true}}
```

Ce second drapeau ne contourne pas le premier : les deux sont nécessaires.
La désactivation du second masque aussi les fiches V11–V20 existantes dans
les listes et interdit leur consultation ou modification via l'API du portail.

## Vérifications de laboratoire

```bash
python -m unittest -v tools.test_ss97_platform_offline tools.test_ss97_platform_extended_offline
node --check softsystem97/public/js/ss97_platform.js
```

Vérifier encore sur un vrai site Frappe v16 : migration des options de Select,
installation sans conflit avec tickets et permissions, compte client B,
technicien non affecté, ticket fermé, session expirée, utilisateurs concurrents,
rollback et restauration réelle. Ne pas traiter un test hors Frappe comme
une preuve d'intégration en production.

## Blocage avant production commerciale

Les moteurs demandés par le propriétaire ne sont **pas implémentés** dans ce
lot : passerelle MeshCentral avec consentement client effectivement vérifié,
diagnostics/procédures contrôlées, moteur IA, supervision, réservations et
notifications automatiques, facturation, et tableaux de bord calculés.
La branche GitHub de déploiement et la préproduction Frappe doivent être
validées, puis seulement un lot de production réellement opérationnel pourra
être mis en service. **Aucune migration ou installation production automatique.**
