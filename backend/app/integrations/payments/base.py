"""The payment provider interface.

Everything that talks to an acquirer goes through this. Today the only
implementation is a mock that always succeeds; a real Moldovan acquirer (MAIB,
Paynet) arrives in phase 10.

**Nothing outside app.integrations.payments may import a concrete provider.**
Depend on PaymentProvider; take the implementation as an argument. The moment a
service imports MockPaymentProvider by name, the interface stops buying us
anything and the "swap in a real acquirer without touching business logic"
promise quietly becomes false.

The mock is also what the test suite uses, permanently. Tests must never reach
a real acquirer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class PaymentError(Exception):
    """A charge or refund could not be completed."""


class CardDeclined(PaymentError):
    """The acquirer refused the card. Not our bug — the customer's problem to fix."""


@dataclass(frozen=True)
class CardToken:
    """What we are allowed to keep after tokenising a card.

    Note what is absent: the PAN, the CVV, the cardholder name. `last4` and
    `brand` exist only so the UI can say "Visa •••• 3382". Storing anything
    more would put this system in PCI-DSS scope — an enormous obligation to
    take on by accident.
    """

    token: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int


@dataclass(frozen=True)
class ChargeResult:
    charge_id: str
    amount_bani: int


@dataclass(frozen=True)
class RefundResult:
    refund_id: str
    amount_bani: int


@runtime_checkable
class PaymentProvider(Protocol):
    def tokenise_card(
        self, *, number: str, exp_month: int, exp_year: int, cvv: str
    ) -> CardToken:
        """Exchange raw card details for a token.

        **In production this call must not happen on our server.** A real
        acquirer gives the browser a hosted field or an iframe, and the PAN goes
        straight from the customer to them — our backend never sees it, which is
        what keeps us out of PCI-DSS scope.

        It exists on the mock because there is no third party to talk to yet.
        Replacing the mock means deleting this from the flow, not reimplementing
        it. See MockPaymentProvider for the full warning.
        """
        ...

    def charge(self, *, amount_bani: int, card_token: str, description: str) -> ChargeResult:
        """Take money. Raises CardDeclined or PaymentError on failure."""
        ...

    def refund(self, *, charge_id: str, amount_bani: int) -> RefundResult:
        """Give it back."""
        ...
