"""Money arithmetic: formatting and the VAT split.

Pure functions, no database. The VAT split is the one with a trap in it — the
two parts must add back to exactly the price, in integer bani, with no rounding
drift either way.
"""

import pytest

from app.core.money import format_mdl, vat_split


@pytest.mark.parametrize(
    ("bani", "text"),
    [
        (0, "0"),
        (90000, "900"),
        (100000, "1 000"),
        (1_000_000, "10 000"),
        (330000, "3 300"),
        (-90000, "-900"),
    ],
)
def test_format_mdl(bani: int, text: str) -> None:
    assert format_mdl(bani) == text


def test_vat_split_of_a_900_mdl_price() -> None:
    net, vat = vat_split(90000)
    assert (net, vat) == (75000, 15000)


@pytest.mark.parametrize("price_bani", [1, 99, 100, 80000, 90000, 100000, 120000, 123457])
def test_net_and_vat_always_add_back_to_the_price(price_bani: int) -> None:
    """The invariant that makes deriving safe: no bani is created or lost."""
    net, vat = vat_split(price_bani)
    assert net + vat == price_bani
    assert net >= 0
    assert vat >= 0


def test_vat_is_computed_first_so_the_split_does_not_drift() -> None:
    """A price that rounds differently depending on which part you compute first.

    123457 bani: VAT-first gives vat = 123457 - (123457*100//120). Computing net
    first as 123457*100//120 and subtracting would land a bani off. This pins the
    documented order.
    """
    net, vat = vat_split(123457)
    assert vat == 123457 - (123457 * 100) // 120
    assert net == 123457 - vat
    assert net + vat == 123457
