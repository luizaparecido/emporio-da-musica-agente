"""Tools de produtos, promoções, loja e políticas."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from emporio_agent.config import Clock
from emporio_agent.data.repository import StoreRepository
from emporio_agent.domain.money import format_brl
from emporio_agent.policies.retriever import PolicyRetriever
from emporio_agent.services.availability import Availability
from emporio_agent.services.catalog import CatalogEntry, CatalogService
from emporio_agent.services.pricing import build_quote
from emporio_agent.services.store_hours import store_status
from emporio_agent.tools import presenters
from emporio_agent.tools.registry import Tool


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchProductsArgs(_Args):
    query: str | None = Field(None, description="Marca, modelo ou característica, como 'Yamaha' ou 'iniciante'.")
    category: str | None = Field(None, description="Categoria exata, quando o cliente indicar o tipo de instrumento.")
    min_price: float | None = Field(None, description="Preço mínimo em reais.")
    max_price: float | None = Field(None, description="Preço máximo em reais.")
    strings: Literal["nylon", "steel"] | None = Field(None, description="Violões e ukuleles: cordas de nylon ou aço.")
    electric: bool | None = Field(None, description="Violões e ukuleles: true para eletroacústico, false para acústico.")
    on_promotion: bool = Field(False, description="true para listar só produtos em promoção ativa.")
    limit: int = Field(8, ge=1, le=20, description="Quantos resultados devolver.")


class ProductQuoteArgs(_Args):
    product_id: int | None = Field(None, description="ID, quando já veio de outra tool.")
    name: str | None = Field(None, description="Nome ou modelo, como 'Takamine GD20'.")


class AlternativesArgs(_Args):
    product_id: int


class PromotionsArgs(_Args):
    name: str | None = Field(None, description="Nome da campanha perguntada, como 'Black Friday'. Omita para listar as ativas.")


class PolicyArgs(_Args):
    section_ids: list[str] = Field(description="Seções do manual a consultar.", min_length=1)


class StoreStatusArgs(_Args):
    pass


def build_catalog_tools(
    repo: StoreRepository, catalog: CatalogService, retriever: PolicyRetriever, clock: Clock
) -> list[Tool]:
    categories = {c.name: c.id for c in repo.categories.values()}

    def expired_names(product_id: int) -> list[str]:
        names = {p.name for p in repo.promotions_of(product_id) if not p.is_active}
        return sorted(names)

    def quote_of(entry: CatalogEntry) -> dict:
        data = presenters.full_quote(entry, expired_names(entry.product.id))
        if entry.availability is not Availability.AVAILABLE:
            data["alternativas"] = [presenters.summary(a) for a in catalog.alternatives(entry.product.id)]
        return data

    def search_products(args: SearchProductsArgs, _session: str) -> dict:
        if args.category and args.category not in categories:
            return {"erro": f"Categoria inválida. Use uma destas: {sorted(categories)}"}
        result = catalog.search(
            query=args.query,
            category_id=categories.get(args.category) if args.category else None,
            min_price=Decimal(str(args.min_price)) if args.min_price is not None else None,
            max_price=Decimal(str(args.max_price)) if args.max_price is not None else None,
            strings=args.strings,
            electric=args.electric,
            on_promotion=args.on_promotion,
            limit=args.limit,
        )
        payload = {
            "total_encontrado": result.total_found,
            "exibidos": len(result.entries),
            "ordenacao": "menor preço" if not args.query else "relevância",
            "produtos": [presenters.summary(e) for e in result.entries],
        }
        if result.approximate:
            payload["correspondencia_aproximada"] = True
        if result.total_found == 0:
            payload["observacao"] = "Nenhum produto disponível no sistema com esses critérios."
        return payload

    def get_product_quote(args: ProductQuoteArgs, _session: str) -> dict:
        if args.product_id is not None:
            entry = catalog.entry(args.product_id)
            return {"produtos": [quote_of(entry)]} if entry else {"produtos": [], "observacao": "Produto não encontrado."}
        if not args.name:
            return {"erro": "Informe product_id ou name."}
        result = catalog.search(query=args.name, include_unavailable=True, limit=3)
        if not result.entries:
            return {"produtos": [], "observacao": "Produto não encontrado no catálogo."}
        payload = {"produtos": [quote_of(e) for e in result.entries]}
        if result.approximate:
            payload["correspondencia_aproximada"] = True
        return payload

    def suggest_alternatives(args: AlternativesArgs, _session: str) -> dict:
        return {"alternativas": [presenters.summary(a) for a in catalog.alternatives(args.product_id)]}

    def list_promotions(args: PromotionsArgs, _session: str) -> dict:
        if not args.name:
            active = catalog.active_promotions()
            return {
                "promocoes_ativas": [
                    {**presenters.summary(e), "promocao": e.quote.promotion.name} for e in active
                ]
            }
        ativas, encerradas = [], []
        for promo, product in catalog.promotions_named(args.name):
            if promo.is_active:
                ativas.append({"campanha": promo.name, "produto": product.name, "desconto_percentual": promo.discount_percent})
            else:
                current = build_quote(product.price, repo.promotions_of(product.id))
                encerradas.append({"campanha": promo.name, "produto": product.name, "preco_atual": format_brl(current.final_price)})
        payload: dict = {"ativas": ativas, "encerradas": encerradas}
        if not ativas:
            payload["observacao"] = "Nenhuma promoção ativa com esse nome. Não prometa desconto."
        return payload

    def consult_policy(args: PolicyArgs, _session: str) -> dict:
        sections = retriever.get(args.section_ids)
        if not sections:
            return {"erro": "Seção inexistente.", "secoes_validas": [sid for sid, _ in retriever.table_of_contents()]}
        return {"secoes": [{"secao": s.id, "titulo": s.title, "texto": s.text} for s in sections]}

    def get_store_status(_args: StoreStatusArgs, _session: str) -> dict:
        now = clock.now()
        status = store_status(now)
        payload: dict = {
            "agora": presenters.format_moment(now),
            "aberta_agora": status.is_open,
            "horario_regular": "Segunda a sexta, 09:00 às 18:00. Sábado, 09:00 às 13:00. Domingos e feriados, fechada.",
        }
        if status.closes_at:
            payload["fecha_as"] = status.closes_at.strftime("%H:%M")
        if status.next_opening:
            payload["proxima_abertura"] = presenters.format_moment(status.next_opening)
        if status.holiday:
            payload["feriado_hoje"] = status.holiday
        return payload

    def patch_category(schema: dict) -> None:
        schema["properties"]["category"]["anyOf"][0]["enum"] = sorted(categories)

    table_of_contents = "; ".join(f"{sid} {title}" for sid, title in retriever.table_of_contents())

    def patch_sections(schema: dict) -> None:
        schema["properties"]["section_ids"]["items"]["enum"] = [sid for sid, _ in retriever.table_of_contents()]

    return [
        Tool(
            "search_products",
            "Busca no catálogo produtos disponíveis para compra. Use para perguntas abertas, como opções por tipo, "
            "marca ou faixa de preço. A faixa de preço já considera promoções ativas.",
            SearchProductsArgs,
            search_products,
            patch_category,
        ),
        Tool(
            "get_product_quote",
            "Devolve preço, promoção ativa, valor no PIX, parcelamento máximo e disponibilidade de um produto "
            "específico, inclusive indisponível ou descontinuado. Se não estiver disponível, já traz alternativas.",
            ProductQuoteArgs,
            get_product_quote,
        ),
        Tool(
            "suggest_alternatives",
            "Sugere produtos disponíveis parecidos com um produto já identificado.",
            AlternativesArgs,
            suggest_alternatives,
        ),
        Tool(
            "list_promotions",
            "Lista as promoções ativas ou verifica se uma campanha específica ainda vale.",
            PromotionsArgs,
            list_promotions,
        ),
        Tool(
            "consult_policy",
            "Lê seções do manual da loja: endereço e contatos, pagamento, trocas, frete, garantia, privacidade. "
            f"Seções: {table_of_contents}.",
            PolicyArgs,
            consult_policy,
            patch_sections,
        ),
        Tool(
            "get_store_status",
            "Informa se a loja está aberta agora, o horário regular e a próxima abertura.",
            StoreStatusArgs,
            get_store_status,
        ),
    ]
