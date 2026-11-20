# SS97 — Parcours client et recrutement : constat et recette

## Constat vérifié dans le navigateur de production

Le 20 novembre 2026 (UTC), les pages publiques suivantes sont accessibles :

| Page | Constat réel avant ce lot | Ce lot de code |
|---|---|---|
| `/portail-client` | Page existante, accès au dashboard, profil, entreprise, factures, messages, tickets ; beaucoup d'entrées à lire | Met le parcours d'ouverture/suivi de ticket en avant, sans reconstruire le portail ERPNext |
| `/ticket-libre` | Page existante, qui renvoie au formulaire `/ouvrir-ticket/new` | Ajoute les étapes et précautions pratiques |
| `/ouvrir-ticket/new` | Formulaire public visible : identité, email, téléphone, société, pays, langue, catégorie, urgence, appareil, description, pièce jointe, CGV | Ajoute consignes de saisie et consentement distant ; ne change pas le modèle Frappe |
| `/espace-client/dashboard` | Lien présent sur le portail ; accès par compte à vérifier | Inchangé |

L'existence d'un formulaire **ne prouve pas** que la création du ticket, son numéro, les e-mails, son rattachement au Customer et l'affectation dans Issue fonctionnent correctement. La branche historique `fix/softsystem97-production-bugs` contient un patch ancien du Web Form, mais ses Server Scripts et API de production ne sont pas tous présents dans ce dépôt. Aucun code de réception alternatif n'est activé par ce lot.

## Candidat N2 / N3 / N4 — conservation de l'existant

Le code actuel comprend une sélection de filière, un examen chronométré par filière, une vérification humaine des justificatifs, une validation du contrat freelance par référence externe, une formation par spécialité et une habilitation distincte du résultat de l'examen. La période d'essai n'est **pas** un mécanisme d'habilitation.

Ce lot ajoute trois sortes de notifications d'examen :

- `EXAM_PASSED_PROVISIONAL` : seuil atteint, mais examen à valider par le responsable.
- `EXAM_FAILED` : seuil non atteint ; le candidat peut consulter les suites possibles ; refus définitif non automatique.
- `EXAM_EXPIRED` : délai dépassé, sans habilitation.

Elles sont dédupliquées par identifiant d'épreuve et ne sont produites que lorsque TECH OS et un dossier en cours d'examen de la même filière existent. Leur transmission suit **l'opt-in site existant** `ss97_tech_email_notifications.enabled` ; `HELD` signifie pas d'envoi, `QUEUED` signifie seulement accepté par Frappe Email Queue, jamais arrivé dans la boîte destinataire.

## Sandrine Gob et protection des rôles

Conserver l'accord de principe : Sandrine ne doit accéder qu'aux évaluations/vidéos, rendez-vous/entretiens, agenda, notifications, historique et profil. Pas de tickets, devis, aide, administration ni paramètres, **y compris via les URL/API**. Organisateur de recrutement prévu : `recrutement@softsystem97.com` ; entretien de 40 minutes avec créneau interne bloqué 60 minutes. Ce lot ne lui crée aucun utilisateur ni privilège. Vérifier l'implémentation réellement installée avant une validation humaine.

## Suite de recette — aucune case automatiquement validée

- [ ] Réaliser sauvegarde complète dans Frappe Cloud immédiatement avant le nouveau déploiement.
- [ ] Déployer le commit testé, vérifier l'application, la migration du DocType Notice et purger le cache Frappe Cloud.
- [ ] Contrôler à l'écran FR/EN/ES/HT sur `/portail-client`, `/ticket-libre` et `/ouvrir-ticket/new` : affichage, liens, formulaire, mobile.
- [ ] Sous un compte de test non privilégié, soumettre **un ticket de test maîtrisé** ; relever la référence, la présence dans ERPNext Issue, le bon Customer, la notification SMTP réellement reçue et la visibilité dans le tableau de bord.
- [ ] Vérifier que le client B et le technicien non affecté ne voient ni ce ticket ni ses pièces jointes.
- [ ] Tester la reprise d'une erreur de formulaire, un doublon, une pièce volumineuse, un champ obligatoire et un compte déconnecté.
- [ ] Sur site de test, candidats N2/N3/N4 : valider banques de questions, seuils, expiration, échec, réussite, limite de tentatives, un email chacun et l'absence d'auto-activation.
- [ ] Contrôler les dossiers privés et la décision humaine distincte des contrôles de format.
- [ ] Vérifier avec Sandrine, dans son **vrai compte de test**, menus autorisés, refus URL/API hors périmètre, invitation Calendar/Meet ; ne pas la contacter automatiquement.
- [ ] Tester les types de contrats CDI/CDD séparément du circuit freelance ; les conditions et signatures sont examinées par la direction/les RH, puis par les parties, pas par une IA.
- [ ] Essai réel Asus + Dell : client ouvre le ticket, consent à la session précise, le technicien approuvé ouvre la connexion, constate l'écran distant, ferme la session et consigne la traçabilité. Ne jamais utiliser un accès distant persistant non consenti.
- [ ] Vérifier les formations continues, les comptes N2/N3/N4, les permissions des menus et une intervention métier de bout en bout.

## Protection juridique et documentaire

- La période d'essai commence dans le cadre d'un contrat de travail, et sa durée dépend notamment du CDI/CDD et du poste (source : service-public.fr/particuliers/vosdroits/F1643). Pas de « deux mois gratuits » avant contrat.
- Les pièces d'identité des postulants, si nécessaires, restent privées, à accès limité ; une vérification automatique de type ou format ne prouve pas l'authenticité (source : cnil.fr/fr/le-guide-du-recrutement).
- La signature du responsable et du candidat est une opération explicite et tracée ; aucun nom ni paraphe n'est généré automatiquement.

## Contrôles locaux exécutables

```bash
python -m unittest discover -s tools -p 'test_*.py' -q
node --check softsystem97/public/js/ss97_client_journey.js
node tools/test_ss97_human_experience.cjs
node tools/test_technician_language_release.cjs
git diff --check
```

Les tests hors production ne certifient pas les e-mails SMTP, la création d'une Issue, la prise en main MeshCentral ni les décisions humaines.
