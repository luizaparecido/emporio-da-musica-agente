"""Regras de preço do manual (§3 e §6), calculadas em código e nunca pelo LLM."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from emporio_agent.domain.models import Promotion
from emporio_agent.domain.money import round_brl

PIX_DISCOUNT = Decimal("0.05")
MAX_INSTALLMENTS = 12


def _minimum_installment(installments: int) -> Decimal:
    """Faixas do §3.1, que prevalecem sobre o resumo da tabela do §3.

    "Até 3x: sem valor mínimo (exceto abaixo de R$ 50,00)" é lido como parcela mínima
    de R$ 50,00 para 2x e 3x. Pagamento em 1x não tem mínimo.
    """
    if installments == 1:
        return Decimal("0")
    if installments <= 3:
        return Decimal("50")
    if installments <= 6:
        return Decimal("80")
    return Decimal("100")


def max_installments(amount: Decimal) -> int:
    for installments in range(MAX_INSTALLMENTS, 0, -1):
        if amount / installments >= _minimum_installment(installments):
            return installments
    return 1


@dataclass(frozen=True)
class Quote:
    list_price: Decimal
    promotion: Promotion | None
    final_price: Decimal
    pix_price: Decimal | None
    installments: int
    installment_value: Decimal


def build_quote(list_price: Decimal, promotions: list[Promotion]) -> Quote:
    active = [p for p in promotions if p.is_active]
    promotion = max(active, key=lambda p: p.discount_percent, default=None)
    final = (
        round_brl(list_price * (100 - promotion.discount_percent) / 100)
        if promotion
        else round_brl(list_price)
    )
    # §6.2: o desconto do PIX não se aplica sobre preço promocional.
    pix = None if promotion else round_brl(list_price * (1 - PIX_DISCOUNT))
    installments = max_installments(final)
    return Quote(
        list_price=round_brl(list_price),
        promotion=promotion,
        final_price=final,
        pix_price=pix,
        installments=installments,
        installment_value=round_brl(final / installments),
    )
