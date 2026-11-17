"""Simulated payment provider (UML actor "Service de paiement").

No card data ever reaches this API. A real integration would receive a token
from the provider's front-end SDK and call the provider here.
"""

from dataclasses import dataclass

from app.models import PaymentMethod


@dataclass(frozen=True)
class PaymentResult:
    accepted: bool


def charge(
    amount_cents: int, method: PaymentMethod, simulate_refusal: bool = False
) -> PaymentResult:
    return PaymentResult(accepted=not simulate_refusal)