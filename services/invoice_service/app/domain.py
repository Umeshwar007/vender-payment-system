from enum import StrEnum
from typing import Iterable


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"


ALLOWED_TRANSITIONS: dict[InvoiceStatus, frozenset[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: frozenset(
        {InvoiceStatus.APPROVED, InvoiceStatus.VOID}
    ),
    InvoiceStatus.APPROVED: frozenset(
        {InvoiceStatus.SCHEDULED, InvoiceStatus.VOID}
    ),
    InvoiceStatus.SCHEDULED: frozenset(
        {
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PAID,
            InvoiceStatus.VOID,
        }
    ),
    InvoiceStatus.PARTIALLY_PAID: frozenset({InvoiceStatus.PAID}),
    InvoiceStatus.PAID: frozenset(),
    InvoiceStatus.VOID: frozenset(),
}


class InvalidInvoiceTransition(ValueError):
    pass


def transition_invoice(
    current: InvoiceStatus,
    requested: InvoiceStatus,
) -> InvoiceStatus:
    if requested not in ALLOWED_TRANSITIONS[current]:
        raise InvalidInvoiceTransition(
            f"Cannot move invoice from {current.value} to {requested.value}"
        )
    return requested


def calculate_total_cents(
    lines: Iterable[tuple[int, int]],
) -> int:
    """Sum (quantity, unit_price_cents) pairs using integer arithmetic."""
    line_items = list(lines)
    if not line_items:
        raise ValueError("An invoice must have at least one line")

    total = 0
    for quantity, unit_price_cents in line_items:
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("Quantity must be an integer")
        if isinstance(unit_price_cents, bool) or not isinstance(
            unit_price_cents, int
        ):
            raise ValueError("Unit price must be an integer number of cents")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if unit_price_cents < 0:
            raise ValueError("Unit price cannot be negative")

        total += quantity * unit_price_cents

    return total