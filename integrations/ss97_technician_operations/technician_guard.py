"""Login presentation only. Every data/API request is independently authorized."""


def technician_login_required_html(*, section_title=''):
    return '<p id="ss97-login-required">Session en cours de vérification. <a href="/login?redirect-to=%2Fespace-technicien%2Ftickets">Se connecter</a></p>'
