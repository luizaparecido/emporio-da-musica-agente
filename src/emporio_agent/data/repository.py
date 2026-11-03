"""Acesso de leitura aos dados da loja.

Mantido em memória porque são poucas linhas. Os services dependem só desta classe,
então trocar por um banco real não muda o restante do código.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from emporio_agent.data import loader
from emporio_agent.domain.models import (
    Category,
    Customer,
    Order,
    OrderItem,
    Product,
    Promotion,
)


class StoreRepository:
    def __init__(
        self,
        categories: list[Category],
        products: list[Product],
        promotions: list[Promotion],
        customers: list[Customer],
        orders: list[Order],
        order_items: list[OrderItem],
    ) -> None:
        self.categories = {c.id: c for c in categories}
        self.products = {p.id: p for p in products}
        self.promotions = promotions
        self.customers = {c.id: c for c in customers}
        self.orders = {o.id: o for o in orders}
        self._items_by_order: dict[int, list[OrderItem]] = defaultdict(list)
        for item in order_items:
            self._items_by_order[item.order_id].append(item)
        self._promos_by_product: dict[int, list[Promotion]] = defaultdict(list)
        for promo in promotions:
            self._promos_by_product[promo.product_id].append(promo)

    @classmethod
    def from_csv(cls, data_dir: Path) -> "StoreRepository":
        return cls(
            categories=loader.load_categories(data_dir),
            products=loader.load_products(data_dir),
            promotions=loader.load_promotions(data_dir),
            customers=loader.load_customers(data_dir),
            orders=loader.load_orders(data_dir),
            order_items=loader.load_order_items(data_dir),
        )

    def items_of(self, order_id: int) -> list[OrderItem]:
        return list(self._items_by_order.get(order_id, []))

    def promotions_of(self, product_id: int) -> list[Promotion]:
        return list(self._promos_by_product.get(product_id, []))

    def orders_of(self, customer_id: int) -> list[Order]:
        return [o for o in self.orders.values() if o.customer_id == customer_id]
