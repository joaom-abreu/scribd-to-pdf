import re
from dataclasses import dataclass
from typing import Self
from urllib.parse import urlsplit

ALLOWED_HOSTS = frozenset({"scribd.com", "www.scribd.com"})
DOCUMENT_PATH = re.compile(r"/document/([0-9]+)(?:/[^/]+)?/?")


@dataclass(frozen=True)
class Document:
    document_id: str
    url: str

    @classmethod
    def from_url(cls, url: str) -> Self:
        url = url.strip()

        if any(character.isspace() for character in url):
            raise ValueError("O link não pode conter espaços ou quebras de linha.")

        try:
            parsed = urlsplit(url)
        except ValueError as error:
            raise ValueError("O link informado é inválido.") from error

        if parsed.scheme != "https" or parsed.netloc.lower() not in ALLOWED_HOSTS:
            raise ValueError("Use um link HTTPS de scribd.com ou www.scribd.com.")

        match = DOCUMENT_PATH.fullmatch(parsed.path)

        if match is None:
            raise ValueError("Use um link de documento no formato /document/ID/titulo.")

        return cls(
            document_id=match.group(1),
            url=f"https://www.scribd.com{parsed.path.rstrip('/')}",
        )
