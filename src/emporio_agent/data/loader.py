"""Leitura e limpeza dos CSVs fornecidos pela loja."""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from emporio_agent.domain.models import (
    Category,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    Promotion,
)


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def _read(data_dir: Path, table: str) -> list[dict[str, str]]:
    """Aceita tanto `products.csv` quanto o nome original `... - products.csv`."""
    matches = sorted(data_dir.glob(f"*{table}.csv"))
    if not matches:
        raise FileNotFoundError(f"CSV da tabela {table!r} não encontrado em {data_dir}")
    with matches[0].open(encoding="utf-8", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def _optional(value: str) -> str | None:
    return value or None


def _optional_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def load_categories(data_dir: Path) -> list[Category]:
    return [
        Category(id=int(r["category_id"]), name=r["name"], description=r["description"])
        for r in _read(data_dir, "categories")
    ]


def load_products(data_dir: Path) -> list[Product]:
    return [
        Product(
            id=int(r["product_id"]),
            name=r["name"],
            price=Decimal(r["price_brl"]),
            category_id=int(r["category_id"]),
            description=r["description"],
            stock=int(r["stock_quantity"]),
            status=ProductStatus(r["status"]),
            specs={k: str(v) for k, v in json.loads(r["specs"]).items()},
        )
        for r in _read(data_dir, "products")
    ]


def load_promotions(data_dir: Path) -> list[Promotion]:
    return [
        Promotion(
            id=int(r["promotion_id"]),
            product_id=int(r["product_id"]),
            discount_percent=int(r["discount_percent"]),
            name=r["description"],
            is_active=r["is_active"] == "1",
        )
        for r in _read(data_dir, "promotions")
    ]


def load_customers(data_dir: Path) -> list[Customer]:
    return [
        Customer(
            id=int(r["customer_id"]),
            name=r["name"],
            phone_digits=digits_only(r["phone"]),
            email=r["email"].casefold(),
            city=r["city"],
        )
        for r in _read(data_dir, "customers")
    ]


def load_orders(data_dir: Path) -> list[Order]:
    return [
        Order(
            id=int(r["order_id"]),
            customer_id=int(r["customer_id"]),
            order_date=date.fromisoformat(r["order_date"]),
            status=OrderStatus(r["status"]),
            total=Decimal(r["total_brl"]),
            payment_method=r["payment_method"],
            tracking_code=_optional(r["tracking_code"]),
            estimated_delivery=_optional_date(r["estimated_delivery"]),
            notes=_optional(r["notes"]),
        )
        for r in _read(data_dir, "orders")
    ]


def load_order_items(data_dir: Path) -> list[OrderItem]:
    return [
        OrderItem(
            order_id=int(r["order_id"]),
            product_id=int(r["product_id"]),
            quantity=int(r["quantity"]),
        )
        for r in _read(data_dir, "order_items")
    ]
