"""Entidades de domínio. Dinheiro é sempre Decimal para evitar erro de ponto flutuante."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProductStatus(StrEnum):
    ACTIVE = "active"
    DISCONTINUED = "discontinued"
    COMING_SOON = "coming_soon"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Category(_Frozen):
    id: int
    name: str
    description: str


class Product(_Frozen):
    id: int
    name: str
    price: Decimal
    category_id: int
    description: str
    stock: int
    status: ProductStatus
    specs: dict[str, str]


class Promotion(_Frozen):
    id: int
    product_id: int
    discount_percent: int
    name: str
    is_active: bool


class Customer(_Frozen):
    id: int
    name: str
    phone_digits: str
    email: str
    city: str

    @property
    def first_name(self) -> str:
        return self.name.split()[0]


class OrderItem(_Frozen):
    order_id: int
    product_id: int
    quantity: int


class Order(_Frozen):
    id: int
    customer_id: int
    order_date: date
    status: OrderStatus
    total: Decimal
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
