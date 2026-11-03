"""Guardrail de saída: todo valor em reais precisa ter origem conhecida.

Aplica em código a regra do manual "nunca fornecer informações sobre preços sem consultar
o sistema" (§7.1). Valores por extenso ("mil reais") não são detectados.
"""

from __future__ import annotations

import re
from decimal import Decimal

AMOUNT_PATTERN = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?")


def extract_amounts(text: str) -> set[str]:
    """Valores normalizados: 'R$ 1.299,00', 'R$ 1299' e 'R$1299,0' viram '1299.00'."""
    amounts = set()
    for integer, cents in AMOUNT_PATTERN.findall(text):
        value = Decimal(f"{integer.replace('.', '')}.{(cents or '0').ljust(2, '0')}")
        amounts.add(f"{value:.2f}")
    return amounts


def ungrounded_amounts(reply: str, grounded: set[str]) -> set[str]:
    return extract_amounts(reply) - grounded
