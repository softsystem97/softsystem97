# Incident 404 — Frappe Cloud / Soft System 97

## Constat du 20 novembre 2026

Les fichiers routes et scripts suivants existent dans la branche de livraison
`release/ss97-tech-cyber-pilot-20261118` du dépôt `softsystem97/softsystem97` :

- `softsystem97/www/ss97-cyberos.html` et `.py`
- `softsystem97/www/ss97-tech-cyber.html` et `.py`
- `softsystem97/www/ss97-cyber-entreprises.html` et `.py`
- `softsystem97/public/js/ss97_cyberos_v3.js`
- `softsystem97/public/js/ss97_n4_dashboard.js`

Un contrôle public du site a détecté `/ss97-cyberos` et
`/ss97-tech-cyber` en 404 ; le script N4 était accessible alors que le
script CyberOS v3 manquait. **Ces symptômes ne permettent pas de déterminer
avec certitude la version installée sans accéder aux détails du bench.**
La page N4 est protégée : son code `get_context` peut également refuser un
visiteur non connecté, il faut répéter le test avec un vrai utilisateur N4.

## Correction de production : ordre obligatoire

1. Dans **Frappe Cloud → Bench Group → Apps**, relever le dépôt et la
   **branche actuellement sélectionnée** pour `softsystem97`, ainsi que
   les sites du groupe (un changement de branche peut affecter tous les sites).
2. Comparer le commit installé à la branche de livraison vérifiée. Le
   commit **à installer doit être celui du HEAD de cette branche au moment
   du déploiement** ; ne pas supposer qu'il s'agit de `main` ou de
   `feature/ss97-final-integration`.
3. Effectuer une sauvegarde avec vérification de restauration et, de
   préférence, une migration sur un site de recette.
4. Sélectionner la bonne branche de `softsystem97`, puis **Deploy** la
   nouvelle version du **Bench Group**. Attendre le succès du build.
5. Depuis Frappe Cloud, lancer ensuite **Update** du **site concerné** ;
   le simple déploiement du bench ne suffit pas. Vérifier la migration
   des nouveaux DocTypes CyberOS et TECH OS.
6. Si des routes restent obsolètes malgré la bonne version et une migration
   réussie, contrôler les logs de route et les caches ; seulement après
   sauvegarde et avec l'accès autorisé, exécuter si nécessaire :
   `bench --site <site> clear-website-cache`,
   `bench --site <site> clear-cache`, et reconstruire les ressources de
   l'app sur le bench selon le mode de déploiement supporté.
7. Contrôler en **lecture seule** les routes et fichiers après déploiement :
   `python tools/check_ss97_web_release.py --site https://app.softsystem97.com`.
   La page publique CyberOS et ses scripts doivent répondre ; le portail
   N4 doit être testé avec un véritable technicien N4 habilité.
8. Vérifier séparément les flags privés, la banque d'examen N4 (40
   questions actives et validées), les rôles exclusifs, les contrats,
   la double approbation des missions, les tickets, le PDF et Stripe.
   **Ne pas activer Stripe LIVE ou une mission à distance sur la seule
   base d'un HTTP 200.**

## Contrôle CI préparatoire

`python tools/check_ss97_web_release.py` teste la présence des routes
et scripts dans les sources. Un job GitHub Actions construit le paquet Flit
et teste aussi que ces fichiers existent dans la wheel. Ceci évite une
livraison incompletement empaquetée, mais **ne met pas Frappe Cloud à jour**.

## Précautions

- Pas de `git pull` ou changement de branche à l'aveugle sur un bench mutualisé.
- Ne pas publier `site_config.json`, clés Stripe ou données clients.
- Ne pas contourner la page N4 protégée ni attribuer un rôle sans vérifications.
- Conserver `contact@softsystem97.com` et les réglages e-mail existants.

Sources techniques : documentation officielle de Frappe Cloud sur les apps
personnalisées et la mise à jour d'applications sur bench privé.
