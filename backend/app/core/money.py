"""Money arithmetic and formatting, in one place.

Money is integer bani everywhere (1 MDL = 100 bani). These are the only
functions that turn bani into a display string or split out VAT, so the rules
live once rather than scattered across schemas.
"""

from __future__ import annotations

# Moldovan VAT, as a percentage. The price is VAT-inclusive; this only ever
# decomposes an existing price for display, never adds to it.
VAT_PERCENT = 20


def format_mdl(bani: int) -> str:
    """90000 -> "900". Negative amounts keep their sign, grouped by thousands."""
    sign = "-" if bani < 0 else ""
    return sign + f"{abs(bani) // 100:,}".replace(",", " ")


def vat_split(price_bani: int) -> tuple[int, int]:
    """Split a VAT-inclusive price into (net, vat), exactly, in bani.

    The price is the authority; net and vat are derived for display and never
    stored — a stored split is a third number that can disagree with the price.

    The order matters: compute VAT first and subtract to get net. Computing net
    first (``price * 100 // 120``) and subtracting the other way rounds
    differently, and the two parts must add back to exactly the price.

        >>> vat_split(90000)
        (75000, 15000)
    """
    vat_bani = price_bani - (price_bani * 100) // (100 + VAT_PERCENT)
    net_bani = price_bani - vat_bani
    return net_bani, vat_bani
