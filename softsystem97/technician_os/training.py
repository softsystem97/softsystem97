"""Track-separated induction curriculum. Training is not a certification."""


COURSES = {
    "L2": (
        ("Diagnostic initial", "Interroger l'utilisateur, reproduire la panne et recueillir les symptômes sans demander ses mots de passe."),
        ("Postes et systèmes", "Vérifier stockage, mémoire, pilotes, mises à jour et démarrage Windows/Linux avant toute modification."),
        ("Réseau local", "Identifier adressage IP, DNS, DHCP, Wi-Fi et câblage ; isoler la source du problème."),
        ("Sauvegarde et restauration", "Obtenir le consentement, vérifier les sauvegardes et préparer un retour arrière documenté."),
        ("Assistance à distance", "Utiliser seulement une session autorisée, journaliser le ticket et fermer l'accès à la fin."),
        ("Rapport d'intervention", "Consigner diagnostic, actions, résultat, durée et recommandations sans divulguer de données privées."),
    ),
    "BANK": (
        ("Contexte bancaire", "Distinguer environnement bureautique, données clients, cœur bancaire et services critiques."),
        ("Contrôle des accès", "Appliquer le moindre privilège, MFA, comptes nominatifs et séparation des tâches."),
        ("Gestion du changement", "Obtenir une fenêtre d'intervention et une autorisation écrite ; prévoir restauration et validation."),
        ("Continuité d'activité", "Évaluer RTO, RPO, dépendances et procédure d'escalade en cas d'indisponibilité."),
        ("Traçabilité et conformité", "Éviter l'extraction de données sensibles, conserver les preuves autorisées et respecter les règles du client."),
        ("Gestion d'incident", "Qualifier l'impact, préserver les éléments probants et alerter le responsable habilité."),
    ),
    "CYBER": (
        ("Mandat et périmètre", "Aucun scan ni test sans autorisation écrite, périmètre, dates et règles d'engagement validés."),
        ("Analyse de risques", "Identifier actifs, menaces, vraisemblance, impact et mesures proportionnées."),
        ("Défense des identités", "Évaluer MFA, accès privilégiés, comptes de service et journaux sans collecter les secrets."),
        ("Surveillance et réponse", "Organiser détection, triage, confinement et préservation des preuves avec escalade."),
        ("Sécurité des infrastructures", "Examiner segmentation, sauvegardes, durcissement, mises à jour et gestion des vulnérabilités."),
        ("Rapport responsable", "Classer les constats, proposer remédiations, vérifier les preuves et séparer confidentialité et synthèse."),
    ),
}


def course_for_track(track):
    if track not in COURSES:
        raise ValueError("Parcours de formation inconnu.")
    return [{"number": index, "title": title, "objective": objective}
            for index, (title, objective) in enumerate(COURSES[track], 1)]
