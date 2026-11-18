# SS97 TECH OS — candidature, justificatifs, notifications et revue financière V2

## État de livraison

Ajouts au pilote Frappe/ERPNext v16 : profils séparés N2/N3/N4, inscription
depuis un compte web **non client**, six modules de préparation par filière,
dépôt privé de deux justificatifs, double contrôle documentaire, outbox email
et dossier d'approbation financière sans versement. Le catalogue cybersécurité
est lisible en mode visiteur, mais les demandes restent désactivées.

**Important : ce code n'est pas un recrutement autonome validé en production.**
Il ne crée aucun compte Frappe, ne donne aucun rôle métier, ne vérifie aucune
identité, n'effectue aucune signature ni aucun paiement.

## Configuration de sécurité (valeurs absentes = désactivées)

```json
{
  "ss97_tech_os": {"enabled": false},
  "ss97_technician_exams": {"enabled": false},
  "ss97_tech_email_notifications": {"enabled": false},
  "ss97_cyber_assessment": {"enabled": false}
}
```

Les valeurs `true` ne doivent **jamais** être commitées dans Git. L'activation
doit être effectuée uniquement sur un site contrôlé après validation métier,
sécurité et juridique, par un responsable disposant des permissions Frappe.

## Contrôles obligatoires avant ouverture réelle

1. Confirmer le parcours Frappe `/signup` puis la connexion avec un vrai compte
   `Website User`, un second compte `Customer` et un compte `System User`.
   Seul le premier doit pouvoir déposer une candidature, sans rôle technicien.
2. Vérifier en environnement de recette la migration des six DocTypes privés
   (`Profile`, `Mission`, `OS Event`, `Document`, `Notice`, `Settlement`), leur
   visibilité uniquement en administration et la séparation N2/N3/N4.
3. Tester `/api/method/upload_file` avec `is_private=1` sur Frappe v16. Le
   document doit appartenir au candidat, être local, privé, non rattaché, en
   PDF/JPG/PNG et inférieur ou égal à 8 Mo. Un contrôle antivirus serveur, une
   politique de conservation et une procédure d'effacement RGPD doivent être
   définis avant dépôt d'identités réelles.
4. Vérifier que la validation `DOCUMENTS_VALIDATED` est impossible tant que
   les justificatifs identité **et** diplôme ne sont pas tous deux `VERIFIED`.
   N3/N4 demandent toujours un second validateur distinct pour l'habilitation.
   Une pièce devenue publique, supprimée, déplacée ou réattribuée après dépôt
   bloque également sa validation et l'activation du technicien.
5. Importer les banques de questions confidentielles dans Frappe, pas dans
   GitHub (dépôt public). Confirmer : N2 20 questions/20 min, N3 30/25 min,
   N4 40/20 min, réponses jamais envoyées au navigateur.
6. Configurer un véritable compte SMTP sortant, contrôler les permissions
   d'expédition et un test de réception. Le statut `QUEUED` dans l'outbox SS97
   signifie seulement « accepté par Frappe Email Queue », pas « délivré ».
   `ss97_tech_email_notifications.enabled` reste faux tant que ce test manque.
7. Rédiger et faire valider les modèles de contrat freelance propres aux
   juridictions applicables ; choisir un prestataire de signature et vérifier
   sa preuve. Le portail n'exécute pas de signature électronique.
8. Tester le ticket client, les affectations, le mandat de sécurité, la double
   validation N3/N4, les rapports, la clôture client et la révocation en cours
   de mission, avec trois comptes de test distincts. La deuxième approbation
   N3/N4 revérifie le ticket ouvert, l'affectation, l'habilitation active et
   l'indépendance du responsable avant toute proposition au technicien.

### Gestion d'un rapport contesté

- Le client lié au ticket fournit un motif de contestation (500 caractères au
  maximum), sans divulguer de secret ni de mot de passe.
- Une mission `DISPUTED` ne peut pas être relancée directement par le
  technicien : un responsable vérifie à nouveau le ticket, l'affectation et
  l'habilitation freelance. Il peut aussi annuler la mission.
- Pour N2, la reprise est une décision explicite du responsable, journalisée.
- Pour N3 et N4, la reprise attend un **nouveau mandat écrit** et une
  **deuxième validation indépendante** avant le retour à `IN_PROGRESS`.
- Le technicien doit soumettre un nouveau compte rendu ; le client décide de
  nouveau de son acceptation. Une contestation ne déclenche jamais de paiement.
9. Choisir et confirmer les responsabilités Stripe Connect (accès des
   prestataires, frais, soldes négatifs et flux). Vérifier les obligations
   d'identification, le compte bancaire et les webhooks en sandbox isolée.
   **Aucun virement automatique n'est prévu dans cette version** :
   `Settlement` stocke uniquement `REVIEW_REQUIRED` ou `APPROVED`.
10. Exécuter les tests d'intégration sur la même version Frappe/ERPNext que la
    production, avec sauvegarde, restauration et surveillance SMTP/queues.

## Principes de confidentialité

- Le candidat ne reçoit que la catégorie et le statut de ses documents ; ni
  chemin privé ni justificatif d'un autre dossier.
- Seul `System Manager` peut obtenir une URL de fichier privé après contrôle
  d'appartenance au candidat et de confidentialité du fichier.
- Les messages d'état sont génériques, sans justificatif ou coordonnées
  bancaires en pièce jointe, et ne sont expédiés que si le drapeau SMTP est actif.
- La rémunération enregistrée n'est jamais affichée au client, et une seconde
  personne valide l'approbation interne. Le code ne stocke pas de RIB et
  n'appelle pas les API de transfert/payout d'un fournisseur financier.

## Tests automatiques

```bash
python -m unittest discover -s tools -p 'test_ss97_*_offline.py' -q
python -m compileall -q softsystem97/technician_os softsystem97/technician_exams
node --check softsystem97/public/js/ss97_tech_os.js
node --check softsystem97/public/js/ss97_tech_admin.js
```

Ces tests hors production protègent les invariants du code ; ils ne remplacent
pas un test d'inscription, de transfert de fichier ou d'Email Queue sur un
véritable site Frappe.
