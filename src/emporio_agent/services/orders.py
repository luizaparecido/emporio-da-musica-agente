"""Consulta de pedidos com verificação de identidade.

A verificação fica aqui, não no prompt: sem o contato correto o service não devolve
nada, seja qual for o texto que o cliente mande ao LLM. A falha é igual para pedido
inexistente e contato errado, para não revelar quais pedidos existem.
"""

from __future__ import annotations

from dataclasses import dataclass

from emporio_agent.data.loader import digits_only
from emporio_agent.data.repository import StoreRepository
from emporio_agent.domain.models import Customer, Order

MIN_PHONE_DIGITS = 9
BRAZIL_PREFIX = "55"
INTERNATIONAL_PHONE_DIGITS = 13


class VerificationFailed(Exception):
    """Pedido ou contato não conferem. Não diz qual dos dois."""


def phone_matches(customer: Customer, provided: str) -> bool:
    digits = digits_only(provided)
    if digits.startswith(BRAZIL_PREFIX) and len(digits) == INTERNATIONAL_PHONE_DIGITS:
        digits = digits[len(BRAZIL_PREFIX):]
    if len(digits) < MIN_PHONE_DIGITS:
        return False
    return customer.phone_digits.endswith(digits)


def contact_matches(customer: Customer, contact: str) -> bool:
    contact = contact.strip()
    if "@" in contact:
        return customer.email == contact.casefold()
    return phone_matches(customer, contact)


@dataclass(frozen=True)
class VerifiedOrder:
    order: Order
    customer: Customer


class OrderService:
    def __init__(self, repo: StoreRepository) -> None:
        self._repo = repo

    def verified_order(self, order_id: int, contact: str) -> VerifiedOrder:
        order = self._repo.orders.get(order_id)
        customer = self._repo.customers.get(order.customer_id) if order else None
        if order is None or customer is None or not contact_matches(customer, contact):
            raise VerificationFailed
        return VerifiedOrder(order=order, customer=customer)

    def verified_customer_orders(self, phone: str, email: str) -> tuple[Customer, list[Order]]:
        """Exige telefone E e-mail: há e-mail duplicado na base e nenhum número de pedido aqui."""
        for customer in self._repo.customers.values():
            if phone_matches(customer, phone) and customer.email == email.strip().casefold():
                orders = self._repo.orders_of(customer.id)
                return customer, sorted(orders, key=lambda o: o.order_date, reverse=True)
        raise VerificationFailed
