# Collecte privée du contrôleur technicien — Frappe v16

Le collecteur existant `softsystem97.diagnostics` expose désormais `portal_route_metadata()` pour une console administrative ; aucune méthode HTTP n’est créée. Son implémentation autonome `softsystem97/route_metadata.py` peut aussi être transférée seule dans `/tmp/ss97_route_metadata.py` sur un bench autorisé, sans installer l’application candidate ni migrer le site.

## Opération administrative à réaliser

Depuis le tableau de bord officiel https://frappecloud.com/dashboard, sélectionner **le staging distinct autorisé**, puis ouvrir l’accès SSH/console proposé par le plan. S’il n’existe pas ou si le plan n’expose pas de console, l’administrateur doit faire fournir cet accès par Frappe Cloud ; ne pas créer un site ni utiliser la production comme banc de test. Remplacer `<nom-technique-staging>` par le nom technique affiché, pas par le domaine de production.

Après transfert du fichier unique, exécuter depuis le bench :

```sh
bench --site <nom-technique-staging> console
```

Puis dans cette console (session administrative autorisée) :

```python
from pathlib import Path
import json
collector = Path('/tmp/ss97_route_metadata.py')
namespace = {'__name__': 'ss97_private_route_inventory'}
exec(compile(collector.read_text(), str(collector), 'exec'), namespace)
report = namespace['collect']()
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
```

Cette commande exécute uniquement le collecteur revu, pas les contrôleurs du portail. Elle n’effectue aucune écriture applicative, aucun commit, aucune impersonation, aucun rendu, aucune migration ni envoi de mail. Les lectures de métadonnées Frappe peuvent alimenter les caches natifs. Si l’application candidate est déjà installée avec autorisation, l’équivalent est `from softsystem97.diagnostics import portal_route_metadata; report = portal_route_metadata()`.

## Rapport JSON attendu et limites

Format `ss97-route-metadata-v1` : applications installées ; candidats Python/templates `www` aux deux routes et empreintes SHA256 ; Web Pages correspondantes sans corps ; hooks de résolution/rendering/permissions et événements Issue ; nombre de règles de réécriture ; métadonnées des champs Issue ciblés ; permissions natives/personnalisées ; présence des deux rôles ; états/transitions/autorités du workflow et présence de conditions privées ; identité des Server Scripts Issue.

Un candidat n’est **pas** la preuve du contrôleur effectif. Les résolveurs personnalisés et règles de réécriture ne sont pas exécutés ; des routes dynamiques restent possibles. Le résultat indique à l’administrateur les sources exactes à examiner, sans exporter leurs contenus. Aucun fichier de configuration, source/template, condition brute, compte User, ticket, clé, cookie, destinataire ou corps d’e-mail n’est lu pour export. Les symlinks sortant d’une application sont exclus. Le rapport ne prouve aucun paiement ni permission sur un ticket réel.

Avant transmission : vérifier visuellement que les noms et métadonnées personnalisés ne contiennent pas de donnée personnelle ou secret ; ne joindre ni sortie complète de console, ni traceback, ni configuration. Transmettre seulement le JSON expurgé. Les sources identifiées devront ensuite être revues et expurgées dans un canal privé avant importation ; ne pas exporter automatiquement du code potentiellement secret.

## Preuves accessibles et contrat requis

`ticket_workspace.py` génère le détail **client**, pas le portail technicien. Aucun chemin `espace-technicien` n’est présent dans les fichiers suivis ni dans les chemins de leur historique Git accessible. La route de développement `/ss97-dev-technician` reste distincte. Un contrôleur stocké en base ne peut pas être exclu par cette recherche Git.

Le raccordement historique exige : rôle canonique `SS97 Technician`, champ Issue `ss97_technician` Link → User (autre profil : adaptateur nécessaire), résolution de Customer côté serveur, affectation approuvée, politique serveur depuis `integrations/ss97_tickets/workflow_logic.py`, et lien fiable facture ↔ Issue. L’interface existante est `AuthorizationRequest` → `AuthorizationDecision` dans `ticket_bridge/historical.py` ; elle vérifie le rattachement exact à la requête et la version de politique, sans inventer les conditions métier. Son fournisseur réel reste absent.

Après réception du JSON et revue des sources identifiées : confirmer versions/contrôleur/schéma, raccorder le fournisseur métier, puis suivre `consolidated-release.md`. Arrêt obligatoire si schéma incompatible, workflow manquant, paiement non rapproché ou accès croisé. Toute installation, migration, activation, création de staging ou déploiement exige une approbation distincte. Stripe Test externe et SMTP de staging restent non exécutés ici.

## Tests exécutés pour cette extension

97 tests Frappe réussis, dont trois nouveaux : refus non-administrateur ; inventaire sans résolution de route ; exclusion des symlinks externes et absence du texte source dans le manifeste. Journal local `logs/route-collection-frappe.log` du bench. Les fixtures sont fictives ; la politique privée et certains traitements financiers restent simulés. Aucun test Cloud n’est revendiqué.
