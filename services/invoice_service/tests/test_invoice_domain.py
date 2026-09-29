import pytest

from services.invoice_service.app.domain import (
    InvoiceStatus,
    InvalidInvoiceTransition,
    calculate_total_cents,
    transition_invoice,
)


def test_calculates_total_in_integer_cents() -> None:
    assert calculate_total_cents([(2, 199), (1, 550)]) == 948


def test_rejects_empty_invoice_lines() -> None:
    with pytest.raises(ValueError, match="at least one line"):
        calculate_total_cents([])


@pytest.mark.parametrize(
    "lines",
    [
        [(0, 100)],
        [(-1, 100)],
        [(1, -1)],
        [(1, 1.5)],
    ],
)
def test_rejects_invalid_line_values(lines: list[tuple[int, int]]) -> None:
    with pytest.raises(ValueError):
        calculate_total_cents(lines)


def test_allows_draft_to_approved() -> None:
    assert transition_invoice(
        InvoiceStatus.DRAFT, InvoiceStatus.APPROVED
    ) == InvoiceStatus.APPROVED


def test_rejects_draft_to_paid() -> None:
    with pytest.raises(InvalidInvoiceTransition):
        transition_invoice(InvoiceStatus.DRAFT, InvoiceStatus.PAID)


def test_partially_paid_invoice_can_only_become_paid() -> None:
    with pytest.raises(InvalidInvoiceTransition):
        transition_invoice(
            InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.VOID
        )