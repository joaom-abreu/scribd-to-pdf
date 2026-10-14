DEFAULT_LANGUAGE = "por"

LANGUAGES = {
    "por": "Português",
    "eng": "Inglês",
    "spa": "Espanhol",
    "fra": "Francês",
    "deu": "Alemão",
}


def normalize_languages(value: str) -> str:
    codes = [code.strip() for code in value.split("+")]

    if not all(codes):
        raise ValueError(
            "Informe um idioma válido, como por, eng, spa, fra, deu "
            "ou uma combinação como por+eng."
        )

    return "+".join(codes)


def describe_language(code: str) -> str:
    return f"{LANGUAGES[code]} ({code})" if code in LANGUAGES else code
