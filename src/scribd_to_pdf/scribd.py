import re
from urllib.parse import urlsplit

from scribd_to_pdf.models import Document


def parse_document_url(url: str) -> Document:
    url = url.strip()

    if any(character.isspace() for character in url):
        raise ValueError("O link não pode conter espaços ou quebras de linha.")

    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise ValueError("O link informado é inválido.") from error

    allowed_hosts = {"scribd.com", "www.scribd.com"}

    if parsed.scheme != "https" or parsed.netloc.lower() not in allowed_hosts:
        raise ValueError("Use um link HTTPS de scribd.com ou www.scribd.com.")

    match = re.fullmatch(
        r"/document/([0-9]+)(?:/[^/]+)?/?",
        parsed.path,
    )

    if match is None:
        raise ValueError("Use um link de documento no formato /document/ID/titulo.")

    normalized_url = f"https://www.scribd.com{parsed.path.rstrip('/')}"

    return Document(
        document_id=match.group(1),
        url=normalized_url,
    )