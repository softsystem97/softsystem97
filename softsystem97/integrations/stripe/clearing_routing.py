"""Routage Stripe par mode, entreprise et devise."""


def select_account(mapping, mode, company,
                   currency, legacy=None):

    if mode not in ("test", "live"):
        raise ValueError("Mode Stripe invalide")

    if mapping is None:
        return legacy

    if not isinstance(mapping, dict):
        raise ValueError("Configuration invalide")

    modes = mapping.get(mode, {})

    if not isinstance(modes, dict):
        raise ValueError("Mode non configure")

    accounts = modes.get(company, {})

    if not isinstance(accounts, dict):
        raise ValueError("Entreprise non configuree")

    account = accounts.get(currency.upper())

    if not isinstance(account, str) or not account.strip():
        raise ValueError("Compte Stripe manquant")

    return account
