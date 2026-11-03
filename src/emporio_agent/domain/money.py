"""Formatação e arredondamento de valores em reais."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def round_brl(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def format_brl(value: Decimal) -> str:
    """Decimal('2089.05') -> 'R$ 2.089,05'."""
    text = f"{round_brl(value):,.2f}"
    return "R$ " + text.replace(",", "_").replace(".", ",").replace("_", ".")
