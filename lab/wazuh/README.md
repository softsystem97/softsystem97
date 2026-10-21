# Wazuh de test indépendant

`test-config.json` est un modèle désactivé, pas une configuration Frappe activée.
Aucun serveur, agent, scheduler ou compte n'est créé. Utiliser un indexer Wazuh
DE TEST autorisé, isolé de la production, avec événements et équipements fictifs.
Le connecteur utilise OpenSearch `wazuh-alerts-4.x-*`, pas l'API Manager `/agents`.

L'administrateur fournit un compte limité à la recherche en lecture sur cet index,
un hostname et un certificat TLS valide. Les identifiants sont injectés dans
`SS97_WAZUH_TEST_USER` et `SS97_WAZUH_TEST_PASSWORD` par un moyen privé ; aucune
valeur dans Git ou dans la ligne de commande. Pour une CA privée, utiliser
`REQUESTS_CA_BUNDLE` vers le certificat CA public approuvé ; jamais désactiver TLS.

Depuis le dépôt, avec Python et requests installés (aucun bench requis) :

```sh
python tools/probe_wazuh_test.py \
  --url https://<hostname-indexer-test>:9200 \
  --host <hostname-indexer-test> \
  --since 2026-10-21T00:00:00Z --authorize-test-read
```

Ne lancer qu'après approbation de la lecture sur ce serveur. Le POST `_search`
est une recherche en lecture ; aucun document ni incident n'est écrit.
Sortie : compteurs seulement, aucun identifiant d'agent, événement ou secret.
Un résultat de 100 événements est tronqué : réduire la fenêtre, aucune pagination
ni preuve d'exhaustivité n'est revendiquée. Aucun résultat n'atteste la couverture
de protection des postes. Les tests locaux du transport restent simulés.

Après réussite : revoir les correspondances agent → équipement → Customer dans
un laboratoire Frappe séparé, conserver `create_incidents=0` pour la première
lecture, puis autoriser séparément la création d'incidents fictifs. Rejouer un
événement pour vérifier la déduplication et refuser toute association étrangère.
Aucune activation Cloud ni administration distante n'est couverte par ce probe.

Tests sans réseau : `python tools/test_wazuh_test_probe.py`.
