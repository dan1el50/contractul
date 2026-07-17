"""A payment provider that always succeeds.

Lets the whole purchase flow be built and tested without merchant credentials,
which take weeks to obtain and cannot be used from a laptop anyway.

This is a stand-in, and it is worth being precise about what it does not teach
us. A real acquirer will bring 3-D Secure redirects, webhook timing, settlement
delay, partial refunds, and currency handling. The interface limits how much
code those touch; it does not make them go away. Do not read "the purchase flow
works" as "payments work".

Test cards, so failure paths are reachable:
    4242 4242 4242 4242  succeeds  (Visa)
    5555 5555 5555 4444  succeeds  (Mastercard)
    4000 0000 0000 0002  declines
"""

from __future__ import annotations

import logging
import secrets

from app.integrations.payments.base import (
    CardDeclined,
    CardToken,
    ChargeResult,
    PaymentError,
    RefundResult,
)

logger = logging.getLogger(__name__)

DECLINE_CARD = "4000000000000002"

_BRANDS = [
    ("4", "visa"),
    ("51", "mastercard"),
    ("52", "mastercard"),
    ("53", "mastercard"),
    ("54", "mastercard"),
    ("55", "mastercard"),
    ("34", "amex"),
    ("37", "amex"),
]


def _brand_of(number: str) -> str:
    for prefix, brand in _BRANDS:
        if number.startswith(prefix):
            return brand
    return "card"


class MockPaymentProvider:
    """In-memory, deterministic, no network."""

    def __init__(self) -> None:
        # Charges we have "taken", so refunds can be validated against them.
        self._charges: dict[str, int] = {}

    def tokenise_card(
        self, *, number: str, exp_month: int, exp_year: int, cvv: str
    ) -> CardToken:
        """**Development only.**

        A real acquirer tokenises in the browser so the PAN never touches our
        server. This method exists because there is no third party to talk to
        yet, and it is the single reason raw card numbers reach this process at
        all.

        When a real provider lands, this does not get reimplemented — the whole
        server-side path disappears, and the frontend talks to the acquirer
        directly.
        """
        digits = "".join(c for c in number if c.isdigit())

        if len(digits) < 13 or len(digits) > 19:
            raise PaymentError("Numărul cardului este invalid.")

        # The CVV is used for nothing and stored nowhere. It is accepted only
        # so the mock's signature matches what a real tokeniser expects.
        if not cvv.isdigit() or not 3 <= len(cvv) <= 4:
            raise PaymentError("CVV invalid.")

        if digits == DECLINE_CARD:
            raise CardDeclined("Cardul a fost refuzat.")

        return CardToken(
            token=f"mock_tok_{secrets.token_hex(12)}",
            brand=_brand_of(digits),
            last4=digits[-4:],
            exp_month=exp_month,
            exp_year=exp_year,
        )

    def charge(self, *, amount_bani: int, card_token: str, description: str) -> ChargeResult:
        if amount_bani <= 0:
            raise PaymentError("Suma trebuie să fie pozitivă.")

        if not card_token.startswith("mock_tok_"):
            raise PaymentError(f"Unknown card token: {card_token!r}")

        charge_id = f"mock_ch_{secrets.token_hex(12)}"
        self._charges[charge_id] = amount_bani

        logger.info("Mock charge %s for %s bani (%s)", charge_id, amount_bani, description)
        return ChargeResult(charge_id=charge_id, amount_bani=amount_bani)

    def refund(self, *, charge_id: str, amount_bani: int) -> RefundResult:
        original = self._charges.get(charge_id)

        if original is None:
            raise PaymentError(f"Unknown charge: {charge_id!r}")

        if amount_bani > original:
            raise PaymentError("Refund exceeds the original charge.")

        return RefundResult(refund_id=f"mock_rf_{secrets.token_hex(12)}", amount_bani=amount_bani)
