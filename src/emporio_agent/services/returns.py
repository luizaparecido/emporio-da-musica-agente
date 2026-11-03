"""Elegibilidade de devolução e troca (manual §4 e §8), com datas calculadas em código.

A base não guarda a data de recebimento: `estimated_delivery` é a melhor aproximação,
e o resultado deixa isso explícito para o agente avisar o cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from emporio_agent.domain.models import Order, OrderStatus

REGRET_DAYS = 7
PREFERENCE_DAYS = 7
DEFECT_EXCHANGE_DAYS = 30
LEGAL_WARRANTY_DAYS = 90


class ReturnReason(StrEnum):
    REGRET = "arrependimento"
    DEFECT = "defeito"
    PREFERENCE = "troca_por_preferencia"


class Outcome(StrEnum):
    ELIGIBLE = "elegivel"
    EXPIRED = "prazo_vencido"
    NOT_DELIVERED = "pedido_ainda_nao_entregue"
    CANCELLED = "pedido_cancelado"
    WARRANTY = "fora_da_troca_mas_na_garantia_legal"
    MANUFACTURER = "somente_garantia_do_fabricante"


@dataclass(frozen=True)
class Eligibility:
    outcome: Outcome
    reason: ReturnReason
    reference_date: date | None = None
    deadline: date | None = None
    legal_warranty_until: date | None = None


def check_eligibility(order: Order, reason: ReturnReason, today: date) -> Eligibility:
    if order.status is OrderStatus.CANCELLED:
        return Eligibility(Outcome.CANCELLED, reason)
    if order.status is not OrderStatus.DELIVERED:
        return Eligibility(Outcome.NOT_DELIVERED, reason)

    received = order.estimated_delivery or order.order_date
    if reason is ReturnReason.DEFECT:
        return _defect(order, received, today)

    days = REGRET_DAYS if reason is ReturnReason.REGRET else PREFERENCE_DAYS
    deadline = received + timedelta(days=days)
    outcome = Outcome.ELIGIBLE if today <= deadline else Outcome.EXPIRED
    return Eligibility(outcome, reason, reference_date=received, deadline=deadline)


def _defect(order: Order, received: date, today: date) -> Eligibility:
    # §4.2 conta a troca a partir da compra; §8.1 conta a garantia legal a partir do recebimento.
    exchange_deadline = order.order_date + timedelta(days=DEFECT_EXCHANGE_DAYS)
    warranty_until = received + timedelta(days=LEGAL_WARRANTY_DAYS)
    if today <= exchange_deadline:
        outcome = Outcome.ELIGIBLE
    elif today <= warranty_until:
        outcome = Outcome.WARRANTY
    else:
        outcome = Outcome.MANUFACTURER
    return Eligibility(
        outcome,
        ReturnReason.DEFECT,
        reference_date=order.order_date,
        deadline=exchange_deadline,
        legal_warranty_until=warranty_until,
    )
