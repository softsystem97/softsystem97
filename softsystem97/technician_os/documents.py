"""Pure validation for privately uploaded technician credentials.

Public websites must never receive identity images from these helpers. The
Frappe File owner and private path are checked again by the server endpoint.
"""

from pathlib import PurePosixPath
from urllib.parse import unquote


REQUIRED_DOCUMENTS = {
    "IDENTITY": "Pièce d'identité",
    "DIPLOMA": "Diplôme ou justificatif de compétence",
}
ALLOWED_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg"})
MAX_FILE_BYTES = 8 * 1024 * 1024


def safe_private_file_url(url):
    """Accept only a single local Frappe private filename, never a path escape."""
    prefix = "/private/files/"
    if not isinstance(url, str) or not url.startswith(prefix):
        return False
    tail = url[len(prefix):]
    # Encoded separators/dot segments can be interpreted later by a proxy.
    decoded = unquote(unquote(tail))
    return bool(tail and decoded and decoded not in {".", ".."}
                and not any(char in decoded for char in "/\\?#\x00")
                and not any(ord(char) < 32 for char in decoded))


def check_private_upload(file_data, expected_owner):
    """Only private, owner-controlled Frappe Files below the size limit."""
    if not file_data or file_data.get("owner") != expected_owner:
        raise ValueError("Fichier inaccessible pour ce candidat.")
    if int(file_data.get("is_private") or 0) != 1:
        raise ValueError("Le document doit être enregistré en mode privé.")
    url = file_data.get("file_url")
    if not safe_private_file_url(url):
        raise ValueError("Seuls les fichiers privés locaux sont acceptés.")
    filename = file_data.get("file_name")
    if (not isinstance(filename, str) or len(filename) > 180
            or PurePosixPath(filename).suffix.lower() not in ALLOWED_EXTENSIONS):
        raise ValueError("Format accepté : PDF, JPG ou PNG.")
    size = file_data.get("file_size")
    try:
        size = int(size)
    except (TypeError, ValueError) as exc:
        raise ValueError("Taille du fichier inconnue.") from exc
    if not 0 < size <= MAX_FILE_BYTES:
        raise ValueError("Document vide ou supérieur à 8 Mo.")
    if file_data.get("attached_to_doctype") or file_data.get("attached_to_name"):
        raise ValueError("Ce fichier est déjà rattaché à un autre dossier.")
    return True
