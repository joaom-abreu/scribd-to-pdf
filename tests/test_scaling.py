import pytest

from scribd_to_pdf.ui.scaling import interface_scale, scaled


@pytest.mark.parametrize(
    "pixels_per_inch, expected",
    [(96, 1.0), (72, 1.0), (144, 1.5), (192, 2.0)],
    ids=["padrao", "dpi-baixo", "150%", "200%"],
)
def test_scale_follows_screen_density(pixels_per_inch, expected):
    assert interface_scale(pixels_per_inch) == pytest.approx(expected)


@pytest.mark.parametrize("override, expected", [("1.5", 1.5), ("1,25", 1.25), ("2", 2.0)])
def test_override_multiplies_screen_scale(override, expected):
    assert interface_scale(96, override) == pytest.approx(expected)
    assert interface_scale(192, override) == pytest.approx(2 * expected)


@pytest.mark.parametrize("override", ["", "grande", "0", "-1", "10", "nan"])
def test_invalid_override_is_ignored(override):
    assert interface_scale(96, override) == 1.0


@pytest.mark.parametrize("value, scale, expected", [(15, 1.0, 15), (15, 1.5, 22), (1, 0.4, 1), (0, 2.0, 1)])
def test_scaled_rounds_and_never_reaches_zero(value, scale, expected):
    assert scaled(value, scale) == expected
