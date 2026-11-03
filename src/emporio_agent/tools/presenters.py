"""Converte resultados de domínio no JSON em português que o LLM recebe."""

from __future__ import annotations

from datetime import date, datetime

from emporio_agent.domain.money import format_brl
from emporio_agent.services.availability import Availability
from emporio_agent.services.catalog import CatalogEntry

WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
LOW_STOCK = 2


def format_date(value: date | None) -> str | None:
    return value.strftime("%d/%m/%Y") if value else None


def format_moment(value: datetime) -> str:
    return f"{WEEKDAYS[value.weekday()]}, {value:%d/%m às %H:%M}"


def summary(entry: CatalogEntry) -> dict:
    """Versão curta para listas."""
    quote = entry.quote
    item = {
        "product_id": entry.product.id,
        "nome": entry.product.name,
        "categoria": entry.category_name,
        "disponibilidade": entry.availability.value,
    }
    if entry.availability is Availability.DISCONTINUED:
        return item
    item["preco"] = format_brl(quote.final_price)
    if quote.promotion:
        item["preco_original"] = format_brl(quote.list_price)
        item["desconto_percentual"] = quote.promotion.discount_percent
    return item


def full_quote(entry: CatalogEntry, expired_promotions: list[str]) -> dict:
    """Versão completa, com condições de pagamento só para o que pode ser comprado."""
    product, quote = entry.product, entry.quote
    data = summary(entry)
    data["descricao"] = product.description
    data["especificacoes"] = product.specs
    if expired_promotions:
        data["promocoes_encerradas"] = expired_promotions
    if entry.availability is not Availability.AVAILABLE:
        data.pop("preco_original", None)
        data.pop("desconto_percentual", None)
        return data

    data["estoque"] = product.stock
    data["ultimas_unidades"] = product.stock <= LOW_STOCK
    if quote.promotion:
        data["promocao"] = quote.promotion.name
        data["pix"] = "Preço promocional: o desconto de 5% no PIX não se aplica (não é cumulativo)."
    else:
        data["preco_pix"] = format_brl(quote.pix_price)
    if quote.installments > 1:
        data["parcelamento_maximo"] = (
            f"{quote.installments}x de {format_brl(quote.installment_value)} sem juros"
        )
    else:
        data["parcelamento_maximo"] = "Somente à vista: 2x ficaria abaixo da parcela mínima."
    return data
