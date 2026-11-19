# SS97 — correction du recrutement N2, N3, N4 et contrôle documentaire

## Défaut confirmé en production

`/ss97-job-apply/new` exposait un champ obligatoire `technician_type`
sans aucune option HTML. L'envoi échouait donc sur « Parcours technicien ».

## Correctifs de la version

1. Migration de la liste `N2`, `N3`, `N4` sur le Web Form
   `ss97-job-apply` et le `Custom Field` associé, sans modifier les autres
   candidatures ou octroyer de rôle.
2. Aide contextuelle pour les cinq types de pièces et les parcours.
3. Validation serveur des vrais octets PDF/JPEG/PNG (8 Mo maximum), extension,
   PDF lisible, image décodable. Formats par rubrique : CV/lettre en PDF,
   photo en image, diplôme/identité en PDF ou image.
4. Sur les PDF avec texte exploitable, détection prudente de CV, facture,
   identité ou diplôme ; rejet d'un type manifestement contradictoire.
   Les documents scannés ou indéterminés restent **à vérifier humainement**.
5. Tout nouveau `File` lié à `Job Applicant` est marqué privé **avant**
   insertion. Les documents privés de l'espace TECH OS sont recontrôlés par
   leurs octets à la soumission et à la vérification avant activation.

## Limites à respecter

- Ce contrôle n'authentifie pas un passeport ni un diplôme. Aucun OCR externe,
  appel OpenAI ou service tiers n'est effectué. Une revue humaine documentée
  reste obligatoire pour qualifier les pièces et la personne.
- La migration ne traite **pas rétroactivement** les anciennes pièces.
  Les anciennes candidatures avec fichiers potentiellement publics demandent
  un audit d'exposition et un transfert privé contrôlé, sans changer
  directement le drapeau d'anciens fichiers.
- Le Web Form n'est pas le même objet que l'espace TECH OS. Une candidature
  à une offre ERPNext n'octroie ni profil actif ni droit de prendre un ticket.

## Recette production après déploiement

- Vérifier que `Parcours technicien` contient un placeholder, N2, N3 et N4.
- Sans soumettre de données personnelles : vérifier l'aide de chaque pièce.
- Sur site de test avec fichiers **fictifs uniquement** : refuser PDF déguisé
  en JPG, facture déposée comme identité/diplôme, CV JPEG ; accepter un
  vrai PDF de CV, un JPG de photo, un PDF ou JPG de diplôme/identité.
- Confirmer par `File` que les nouveaux uploads du recrutement ont
  `is_private=1` et un chemin `/private/files/`.
- Tester revue manuelle `SUBMITTED` → `VERIFIED`/`REJECTED` par un responsable
  distinct du candidat. Contrôler l'absence d'habilitation N2/N3/N4 avant
  validation du parcours complet.
- Auditer les anciennes pièces d'identité avant toute promotion du parcours.

**Preuve disponible à ce stade :** tests unitaires hors ligne ; ni OCR réel
ni essai de soumission avec une identité privée en production.
