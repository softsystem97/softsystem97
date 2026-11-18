# SS97 TECH OS — parcours freelance N2 / N3 / N4 (préproduction)

## Portée de ce lot

Frappe/ERPNext v16. Route proposée : `/ss97-tech-os`.

Le code crée **trois DocTypes privés**, un module d'autorisation, un portail et
des endpoints vérifiés côté serveur. L'activation est explicitement désactivée
par défaut. Le portail ne signe pas les contrats et ne paie personne.

### Filières et comptes

| Filière | Rôle exact pour l'activation | Examen associé |
| --- | --- | --- |
| L2 — généraliste | `SS97 Technicien N2` | `L2` : 20 questions, 20 min |
| N3 — bancaire | `SS97 Technicien N3` | `BANK` : 30 questions, 25 min |
| N4 — cybersécurité | `SS97 Technicien N4` | `CYBER` : 40 questions, 20 min |

Les rôles sont **à créer et attribuer manuellement par un administrateur** après
contrôle; le code n'accorde jamais de rôle automatiquement. Un utilisateur avec
plusieurs rôles de filière est refusé. Le rôle `Candidat SS97` est requis pour
déposer une candidature. Les examens sont un composant séparé, avec banque de
questions privée, sans réponse dans le navigateur.

### Parcours de validation

1. Candidat connecté → `apply(track)` → profil `APPLIED`.
2. Responsable SS97 → `IN_REVIEW`.
3. Le responsable passe le candidat en `IN_REVIEW`, ce qui ouvre uniquement
   l'examen de sa propre filière si les examens ont été activés. Après résultat
   `PASSED` enregistré par le service d'examen → `EXAM_VALIDATED`.
4. Contrôle **humain** des documents hors de cette première tranche →
   `DOCUMENTS_VALIDATED`, avec référence externe de vérification.
5. Contrat de prestation signé **hors plateforme** et vérifié humainement →
   `CONTRACT_SIGNED`, référence externe conservée (aucune fausse e-signature).
6. Rôles de filière vérifiés, compte actif et, pour N3/N4, second validateur
   différent de celui ayant contrôlé les documents → `ACTIVE`.
7. Un responsable peut passer `ACTIVE` à `SUSPENDED` immédiatement.

La sélection initiale de filière par le candidat ne vaut aucune habilitation.
Aucune pièce d'identité, diplôme, RIB, numéro de compte ou mot de passe ne doit
être mis dans `reference`, `route_instructions` ou `report_summary`.

### Mission et validation

1. Le responsable doit d'abord utiliser la liaison de ticket approuvée par
   `softsystem97.integrations.ticket_bridge.policy.assigned`.
2. `offer_mission(...)` vérifie le lien Issue/Customer, l'affectation native
   approuvée, l'habilitation et la spécialité du freelance.
3. N2 : `OFFERED`. N3/N4 : `PENDING_APPROVAL` jusqu'à la validation par un
   **autre** responsable avec référence d'autorisation spécifique.
4. Technicien connecté, de la bonne filière, avec accès toujours valide au
   ticket : `ACCEPTED → IN_PROGRESS → REPORT_SUBMITTED`.
5. Client lié au ticket par `policy.authorize(..., "client")` :
   `CLIENT_ACCEPTED` ou `DISPUTED`; pas d'auto-validation par le technicien.
6. La rémunération annoncée est visible uniquement du technicien, jamais du
   client. `CLIENT_ACCEPTED` **ne crée ni virement ni facture**.

### Configuration de préproduction (site_config, jamais dans Git)

```json
{
  "ss97_tech_os": {"enabled": true},
  "ss97_technician_exams": {"enabled": true}
}
```

N'utiliser ceci **qu'après** migration des DocTypes, création/vérification des
rôles, banque d'examen contrôlée et configuration compatible du pont ticket.
L'activation de ces clés n'est pas effectuée par la livraison GitHub.

### Essais obligatoires avant exposition au public

- Isoler N2, N3 et N4 : un compte ne doit jamais voir les profils ni tickets
  des autres filières ou d'un autre client.
- Bloquer les candidats Guest, comptes désactivés, rôles multiples, rôles
  révoqués, tentatives de saut d'étape et documents/contrats non validés.
- Refuser une mission N3/N4 sans deuxième validation distincte.
- Refuser la création sur ticket fermé, mal lié, sans affectation approuvée,
  et après révocation de l'affectation.
- Vérifier concurrence (double inscription, double mission), CSRF, permissions
  natives Frappe, réponses JSON, restauration et migrations sur Frappe v16.
- Vérifier les pages réelles existantes du recrutement avant raccordement des
  comptes candidats; ne pas remplacer les formulaires live sans contrôle.

### Modules financiers contractuels à raccorder ensuite

Le lot suivant doit ajouter des DocTypes distincts pour : contrat signé,
vérification indépendante, identité/fichier privé, mandat tarifaire, facture du
prestataire, montant approuvé, échéance, paiement confirmé depuis le fournisseur
de paiement, remboursement, litige et rapprochement comptable.

La version financière requiert la confirmation de l'architecture Stripe Connect,
de la politique de commissions, de la prise en charge des remboursements et de
la disponibilité des comptes. La rémunération de salariés relève d'un autre
parcours de paie. **Aucun code de ce pilote ne déclenche un paiement, une
signature électronique, une action à distance ou l'envoi d'un document d'identité.**
