"""Busca de produtos, alternativas e promoções."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz import fuzz

from emporio_agent.data.repository import StoreRepository
from emporio_agent.domain.models import Product, Promotion
from emporio_agent.services.availability import Availability, availability_of
from emporio_agent.services.pricing import Quote, build_quote

FUZZY_TOKEN_THRESHOLD = 85
FUZZY_NAME_THRESHOLD = 72
STOPWORDS = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "um", "uma", "para", "pra", "com", "e"}
STRINGS_SYNONYMS = {"steel": "aco", "nylon": "nylon"}


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _stem(token: str) -> str:
    """Plural simples do português: violões -> violao, guitarras -> guitarra."""
    if token.endswith("oes") and len(token) > 4:
        return token[:-3] + "ao"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", normalize(text)) if t not in STOPWORDS]


@dataclass(frozen=True)
class CatalogEntry:
    product: Product
    category_name: str
    availability: Availability
    quote: Quote


@dataclass(frozen=True)
class SearchResult:
    entries: list[CatalogEntry]
    total_found: int
    approximate: bool


class CatalogService:
    def __init__(self, repo: StoreRepository) -> None:
        self._repo = repo

    def entry(self, product_id: int) -> CatalogEntry | None:
        product = self._repo.products.get(product_id)
        return self._to_entry(product) if product else None

    def _to_entry(self, product: Product) -> CatalogEntry:
        return CatalogEntry(
            product=product,
            category_name=self._repo.categories[product.category_id].name,
            availability=availability_of(product),
            quote=build_quote(product.price, self._repo.promotions_of(product.id)),
        )

    def search(
        self,
        query: str | None = None,
        category_id: int | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        strings: str | None = None,
        electric: bool | None = None,
        on_promotion: bool = False,
        include_unavailable: bool = False,
        limit: int = 8,
    ) -> SearchResult:
        """Filtra por atributos e casa o texto. Faixa de preço considera o preço com promoção."""
        pool: list[CatalogEntry] = []
        for product in self._repo.products.values():
            entry = self._to_entry(product)
            if category_id is not None and product.category_id != category_id:
                continue
            if strings and product.specs.get("strings") != strings:
                continue
            if electric is not None and (product.specs.get("electronics") == "yes") != electric:
                continue
            if on_promotion and entry.quote.promotion is None:
                continue
            if min_price is not None and entry.quote.final_price < min_price:
                continue
            if max_price is not None and entry.quote.final_price > max_price:
                continue
            if not include_unavailable and entry.availability is not Availability.AVAILABLE:
                continue
            pool.append(entry)

        approximate = False
        if query and query.strip():
            # Nome e categoria têm prioridade: a descrição de um ukulele pode citar "violão".
            matches = [e for e in pool if self._matches_all_tokens(query, e, use_description=False)]
            matches = matches or [e for e in pool if self._matches_all_tokens(query, e, use_description=True)]
            if matches:
                pool = self._rank_by_name(query, matches)
            else:
                pool = self._closest_names(query, pool)
                approximate = bool(pool)
        else:
            pool.sort(key=lambda e: e.quote.final_price)
        return SearchResult(entries=pool[:limit], total_found=len(pool), approximate=approximate)

    def find_by_name(self, name: str) -> list[CatalogEntry]:
        """Busca sem filtro de disponibilidade: serve para perguntas sobre um produto específico."""
        return self.search(query=name, include_unavailable=True, limit=5).entries

    def _matches_all_tokens(self, query: str, entry: CatalogEntry, use_description: bool) -> bool:
        product = entry.product
        strong = _tokens(f"{product.name} {entry.category_name}")
        weak = (
            set(
                _tokens(
                    f"{product.description} {product.specs.get('color', '')} "
                    f"{STRINGS_SYNONYMS.get(product.specs.get('strings', ''), '')}"
                )
            )
            if use_description
            else set()
        )
        compact_query = "".join(_tokens(query))
        if len(compact_query) >= 4 and compact_query in "".join(_tokens(product.name)):
            return True
        for token in _tokens(query):
            if token in strong or token in weak:
                continue
            # Tolerância a erro de digitação só em palavras: "GD20" não pode casar com "GD30".
            if any(c.isdigit() for c in token):
                return False
            if not any(fuzz.ratio(token, word) >= FUZZY_TOKEN_THRESHOLD for word in strong):
                return False
        return True

    def _rank_by_name(self, query: str, pool: list[CatalogEntry]) -> list[CatalogEntry]:
        normalized = normalize(query)
        return sorted(
            pool,
            key=lambda e: (-fuzz.token_set_ratio(normalized, normalize(e.product.name)), e.quote.final_price),
        )

    def _closest_names(self, query: str, pool: list[CatalogEntry]) -> list[CatalogEntry]:
        normalized = normalize(query)
        scored = [(fuzz.token_set_ratio(normalized, normalize(e.product.name)), e) for e in pool]
        hits = [item for item in scored if item[0] >= FUZZY_NAME_THRESHOLD]
        hits.sort(key=lambda item: -item[0])
        return [entry for _, entry in hits]

    def alternatives(self, product_id: int, limit: int = 3) -> list[CatalogEntry]:
        """Produtos disponíveis da mesma categoria: mesmo tipo primeiro, depois preço próximo."""
        reference = self._repo.products.get(product_id)
        if reference is None:
            return []
        candidates = [
            self._to_entry(p)
            for p in self._repo.products.values()
            if p.id != product_id
            and p.category_id == reference.category_id
            and availability_of(p) is Availability.AVAILABLE
        ]

        def rank(entry: CatalogEntry) -> tuple[int, Decimal]:
            specs = entry.product.specs
            differences = sum(
                specs.get(key) != reference.specs.get(key) for key in ("strings", "electronics")
            )
            return differences, abs(entry.quote.final_price - reference.price)

        return sorted(candidates, key=rank)[:limit]

    def active_promotions(self) -> list[CatalogEntry]:
        return self.search(on_promotion=True, limit=50).entries

    def promotions_named(self, name: str) -> list[tuple[Promotion, Product]]:
        wanted = normalize(name)
        return [
            (promo, self._repo.products[promo.product_id])
            for promo in self._repo.promotions
            if fuzz.partial_ratio(wanted, normalize(promo.name)) >= FUZZY_TOKEN_THRESHOLD
        ]
