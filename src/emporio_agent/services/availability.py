"""Disponibilidade derivada de status E estoque.

O estoque sozinho engana: há produto descontinuado com 13 unidades e lançamento
com 2. Só produto ativo com estoque pode ser vendido (manual, §7.3).
"""

from __future__ import annotations

from enum import StrEnum

from emporio_agent.domain.models import Product, ProductStatus


class Availability(StrEnum):
    AVAILABLE = "disponivel"
    OUT_OF_STOCK = "temporariamente_indisponivel"
    DISCONTINUED = "descontinuado"
    COMING_SOON = "em_breve"


def availability_of(product: Product) -> Availability:
    if product.status is ProductStatus.DISCONTINUED:
        return Availability.DISCONTINUED
    if product.status is ProductStatus.COMING_SOON:
        return Availability.COMING_SOON
    return Availability.AVAILABLE if product.stock > 0 else Availability.OUT_OF_STOCK
