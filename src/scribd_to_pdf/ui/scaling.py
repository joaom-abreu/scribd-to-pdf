REFERENCE_DPI = 96
SCALE_VARIABLE = "SCRIBD_TO_PDF_SCALE"
MIN_SCALE = 0.5
MAX_SCALE = 4.0


def interface_scale(pixels_per_inch: float, override: str | None = None) -> float:
    screen_scale = max(1.0, pixels_per_inch / REFERENCE_DPI)
    return screen_scale * _parse_override(override)


def scaled(value: int, scale: float) -> int:
    return max(1, round(value * scale))


def _parse_override(value: str | None) -> float:
    try:
        factor = float(value.replace(",", ".")) if value else 1.0
    except ValueError:
        return 1.0

    return factor if MIN_SCALE <= factor <= MAX_SCALE else 1.0
