# Collecte de préproduction — métadonnées expurgées, Frappe v16

## Écran 1 : choisir le site, sans écriture

Ouvrir https://frappecloud.com/dashboard, puis **Sites**. Sélectionner un site de
préproduction distinct de `app.softsystem97.com`, sur un bench/groupe de déploiement
qui ne partage pas les mises à jour applicatives avec la production. Un autre
nom de domaine sur le même bench ne suffit pas pour isoler un déploiement. Vérifier avec le propriétaire
qu'il est réservé aux tests, sans clients réels et sans sorties Stripe Live/SMTP
commerciales. Ne pas sélectionner la production et ne pas créer de site, cloner,
restaurer, installer ou déployer à cette étape. Si aucun staging n'existe : arrêt,
le propriétaire doit autoriser sa création séparément.

## Écran 2 : identifier le déploiement et l'accès autorisé

Sur la fiche du staging, relever son nom technique, son bench, les applications,
versions et révision de déploiement affichées. Dans l'accès SSH/console officiel
fourni par le plan, ouvrir le bench du staging. Les libellés d'accès dépendent du
plan et de l'interface ; cette procédure ne prétend pas avoir observé votre écran.
Si aucune console n'est disponible, faire fournir l'accès au propriétaire ou au
support Frappe Cloud ; ne pas utiliser une console de production comme substitut.

Commandes de consultation, depuis le bench autorisé :

```sh
bench version
bench --site <nom-technique-staging> list-apps
```

Référence locale testée : Frappe **16.52.0**, ERPNext **16.51.1**, application
softsystem97 **1.0.0**, Python 3.14.8, MariaDB 11.8.6. Ce ne sont pas des versions
relevées sur votre site. Une différence impose une recette de compatibilité.

## Écran 3 : transférer et vérifier le paquet, sans installer l'application

Transférer le ZIP fourni vers `/tmp/SS97_PREPRODUCTION_METADATA_V2.zip` par votre
accès SSH autorisé, puis exécuter ce contrôle dans le shell du staging :

```sh
python3 - <<'PY'
import hashlib, json, os
from pathlib import Path
from zipfile import ZipFile
os.umask(0o077)
target = Path('/tmp/ss97-collecte-v2')
target.mkdir(mode=0o700, exist_ok=False)
allowed = {'ss97_route_metadata.py', 'INSTRUCTIONS.md', 'consolidated-release.md', 'SHA256.json'}
with ZipFile('/tmp/SS97_PREPRODUCTION_METADATA_V2.zip') as archive:
    assert len(archive.namelist()) == len(allowed)
    assert set(archive.namelist()) == allowed
    manifest = json.loads(archive.read('SHA256.json'))
    assert set(manifest) == allowed - {'SHA256.json'}
    for name in sorted(allowed - {'SHA256.json'}):
        data = archive.read(name)
        assert hashlib.sha256(data).hexdigest() == manifest[name]
        with (target / name).open('xb') as handle:
            handle.write(data)
print('Empreintes valides ; collecteur non exécuté')
PY
```

L'extraction refuse un répertoire existant et tout fichier hors liste. Une empreinte
prouve l'intégrité interne, pas l'identité du fournisseur : revoir le collecteur
et comparer aussi l'empreinte du ZIP communiquée avec le livrable avant exécution.

## Écran 4 : console administrative du staging, collecte seulement

```sh
bench --site <nom-technique-staging> console
```

Dans la console administrative autorisée, sans changer d'utilisateur :

```python
from pathlib import Path
import json
assert frappe.local.site == '<nom-technique-staging>'
collector = Path('/tmp/ss97-collecte-v2/ss97_route_metadata.py')
namespace = {'__name__': 'ss97_private_route_inventory'}
exec(compile(collector.read_text(), str(collector), 'exec'), namespace)
report = namespace['collect']()
assert report['format'] == 'ss97-route-metadata-v2'
assert report['privacy']['pseudonymized'] is True
print(json.dumps(report, ensure_ascii=False, indent=2))
```

Le remplacement de `<nom-technique-staging>` doit être identique dans les deux
commandes. Le collecteur exige System Manager dans la session administrative,
mais n'attribue ce rôle à personne. Aucune méthode HTTP n'est exposée.

## Rapport attendu et confidentialité

Format **ss97-route-metadata-v2** : routes client/technicien, applications et
versions disponibles, candidats de fichiers, présence de Web Pages, hooks,
champs Issue/Sales Invoice/Customer ciblés, DocTypes requis, permissions,
existence des rôles canoniques, workflows et présence de conditions privées,
identités pseudonymisées des Server Scripts et Client Scripts, Assignment Rules
Issue sans utilisateurs ni expressions privées, Property Setters Issue/Sales Invoice/Customer
sans valeurs ni valeurs par défaut, présence des API
historiques connues, références de priorité/type et compteurs de personnalisations.

Les valeurs et clés personnalisées non explicitement publiques sont remplacées
par des alias HMAC avec sel aléatoire non conservé. Les alias se correspondent à
l'intérieur d'un rapport, pas entre deux exécutions. Aucun dictionnaire inverse
n'est exporté ; les noms personnalisés, chemins et empreintes de sources restent
pseudonymisés. Les constantes publiques connues, types de champs et versions
syntaxiquement valides restent lisibles. Cela permet de comparer la structure
sans exposer de noms contenant une adresse personnelle ou un identifiant sensible.

Aucun enregistrement User, Issue, Customer, Sales Invoice, File ou e-mail n'est
exporté. Seules leurs métadonnées sont consultées. Aucun script, template,
condition, configuration, cookie, mot de passe ou clé n'est exporté. La vérification
lit des fichiers candidats uniquement pour calculer une empreinte ; aucun source
n'est exécuté, aucun résolveur n'est invoqué et les symlinks externes sont exclus.
Pas de commit, migration, installation ou envoi. Les lectures peuvent alimenter
les caches de métadonnées natifs Frappe.

Avant transmission : relire uniquement le JSON ; ne joindre ni capture complète
de console, ni traceback, ni fichier de configuration ni source. En cas d'erreur,
transmettre seulement une description expurgée. L'administrateur doit examiner
privément les éléments identifiés par route ; les alias ne permettent pas de
reconstituer automatiquement le chemin réel. Le rapport n'atteste ni le choix
effectif du contrôleur ni une connexion, un paiement ou un workflow exécuté.

## Installation et recette : étape distincte, après approbation

La collecte ne nécessite ni le SHA candidat ni une migration. Relever d'abord
le code réel. Pour installer ultérieurement le candidat autorisé en staging :
branche `release/phase1-cyber-validation`, SHA exact du compte rendu de livraison.
Ne pas utiliser la tête d'une branche sans revoir le SHA approuvé.

Avant installation : sauvegarde de la base, des fichiers publics/privés et de la
configuration nécessaire au déchiffrement dans un stockage privé, puis preuve de
restauration isolée. Les commandes d'installation et la recette complète sont
préparées dans `consolidated-release.md` inclus au paquet. Aucun déploiement n'est
autorisé par la seule exécution du collecteur.

Le raccordement réel nécessite le contrôleur `/espace-technicien/tickets`, les
API historiques, `integrations/ss97_tickets/workflow_logic.py`, le schéma réel de
Issue.ss97_technician, les permissions, le workflow et le lien facture-ticket.
`ticket_workspace.py` génère le détail client, pas le portail technicien.
Le mode historique reste désactivé tant que l'adaptateur métier réel est absent.
