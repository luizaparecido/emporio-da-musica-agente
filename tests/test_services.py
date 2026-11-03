from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from emporio_agent.config import STORE_TZ
from emporio_agent.domain.money import format_brl
from emporio_agent.services.availability import Availability, availability_of
from emporio_agent.services.catalog import CatalogService
from emporio_agent.services.orders import OrderService, VerificationFailed
from emporio_agent.services.pricing import max_installments
from emporio_agent.services.returns import Outcome, ReturnReason, check_eligibility
from emporio_agent.services.store_hours import store_status


@pytest.fixture
def catalog(repo):
    return CatalogService(repo)


@pytest.fixture
def orders(repo):
    return OrderService(repo)


# --- Disponibilidade -------------------------------------------------------
@pytest.mark.parametrize(
    "product_id, expected",
    [
        (95, Availability.AVAILABLE),
        (96, Availability.OUT_OF_STOCK),
        (113, Availability.DISCONTINUED),
        (136, Availability.DISCONTINUED),  # descontinuado com 13 em estoque
        (130, Availability.COMING_SOON),  # lançamento com 2 em estoque
    ],
)
def test_availability_uses_status_and_stock(repo, product_id, expected):
    assert availability_of(repo.products[product_id]) is expected


# --- Preço ------------------------------------------------------------------
def test_quote_without_promotion_has_pix_and_12x(catalog):
    quote = catalog.entry(95).quote  # Takamine GD20; sua promoção está inativa
    assert quote.promotion is None
    assert quote.final_price == Decimal("2199.00")
    assert quote.pix_price == Decimal("2089.05")
    assert (quote.installments, quote.installment_value) == (12, Decimal("183.25"))


def test_promotion_does_not_stack_with_pix(catalog):
    quote = catalog.entry(121).quote  # Ohana CK-20, 20% ativo
    assert quote.promotion.discount_percent == 20
    assert quote.final_price == Decimal("439.20")
    assert quote.pix_price is None


def test_inactive_promotion_is_ignored(catalog):
    quote = catalog.entry(102).quote  # Crafter CE-15: Black Friday inativa
    assert quote.promotion is None and quote.final_price == Decimal("3899.00")


@pytest.mark.parametrize(
    "amount, expected",
    [
        ("90", 1),  # 2x daria R$ 45, abaixo do mínimo de R$ 50
        ("100", 2),
        ("159.90", 3),
        ("319.99", 3),  # 4x daria R$ 79,99
        ("320", 4),
        ("480", 6),
        ("699.99", 6),  # 7x daria R$ 99,99
        ("700", 7),
        ("1200", 12),
    ],
)
def test_installment_tiers(amount, expected):
    assert max_installments(Decimal(amount)) == expected


def test_format_brl():
    assert format_brl(Decimal("2089.05")) == "R$ 2.089,05"
    assert format_brl(Decimal("439.2")) == "R$ 439,20"


# --- Busca ------------------------------------------------------------------
def test_acoustic_guitars_up_to_1000_match_data(catalog):
    result = catalog.search(category_id=5, max_price=Decimal("1000"), limit=50)
    assert result.total_found == 12
    prices = [e.quote.final_price for e in result.entries]
    assert prices == sorted(prices)
    assert all(e.availability is Availability.AVAILABLE for e in result.entries)
    assert 96 not in {e.product.id for e in result.entries}


@pytest.mark.parametrize(
    "query, product_id",
    [
        ("Takamine GD20", 95),
        ("takamine gd 20", 95),
        ("Takamyne GD20", 95),
        ("Telecaster", 134),
        ("les paul", 131),
        ("Yamaha C40", 81),
    ],
)
def test_search_finds_product_by_loose_name(catalog, query, product_id):
    assert catalog.find_by_name(query)[0].product.id == product_id


def test_search_by_plural_without_accent_finds_category(catalog):
    names = {e.category_name for e in catalog.search(query="violoes", limit=50).entries}
    assert names == {"Violões"}


def test_max_price_uses_promotional_price(catalog):
    ids = {e.product.id for e in catalog.search(max_price=Decimal("440"), limit=60).entries}
    assert 121 in ids  # R$ 549 de tabela, R$ 439,20 com promoção


def test_categories_without_products_return_nothing(catalog):
    assert catalog.search(category_id=6).total_found == 0


def test_unrelated_query_returns_nothing(catalog):
    assert catalog.search(query="pizza de calabresa").total_found == 0


def test_alternatives_are_available_and_exclude_reference(catalog):
    alternatives = catalog.alternatives(96)
    assert len(alternatives) == 3
    assert all(a.availability is Availability.AVAILABLE and a.product.id != 96 for a in alternatives)


def test_active_promotions_match_data(catalog):
    assert {e.product.id for e in catalog.active_promotions()} == {90, 94, 121, 127}


def test_promotions_named_reports_inactive_ones(catalog):
    found = catalog.promotions_named("black friday")
    assert {p.product_id for p, _ in found} == {102, 91, 113}
    assert not any(p.is_active for p, _ in found)


# --- Pedidos e identidade ---------------------------------------------------
@pytest.mark.parametrize(
    "contact",
    [
        "(67) 99654-7821",
        "67996547821",
        "+55 67 99654-7821",
        "99654-7821",
        "anacarol.ferreira@coldmail.com",
        "ANACAROL.FERREIRA@COLDMAIL.COM",
    ],
)
def test_order_accepts_valid_contact_formats(orders, contact):
    assert orders.verified_order(8, contact).customer.first_name == "Ana"


@pytest.mark.parametrize(
    "order_id, contact",
    [(8, "(67) 91111-1111"), (8, "lucas.mendes@jmail.com"), (999, "67996547821"), (8, "7821")],
)
def test_order_verification_fails_the_same_way(orders, order_id, contact):
    with pytest.raises(VerificationFailed):
        orders.verified_order(order_id, contact)


def test_duplicate_email_does_not_cross_customers(repo, orders):
    assert repo.customers[11].email == repo.customers[43].email
    assert orders.verified_order(10, repo.customers[11].email).customer.id == 11
    with pytest.raises(VerificationFailed):
        orders.verified_customer_orders("(67) 99456-3456", "outra@pessoa.com")
    customer, found = orders.verified_customer_orders("(67) 98543-2109", repo.customers[11].email)
    assert customer.id == 11 and [o.id for o in found] == [10]
    customer, found = orders.verified_customer_orders("(67) 99456-3456", repo.customers[43].email)
    assert customer.id == 43 and found == []


# --- Devolução --------------------------------------------------------------
TODAY = date(2026, 3, 25)


def test_regret_expired_for_old_delivery(repo):
    result = check_eligibility(repo.orders[7], ReturnReason.REGRET, TODAY)
    assert result.outcome is Outcome.EXPIRED
    assert result.deadline == date(2026, 2, 24)


def test_regret_window_boundaries(repo):
    order = repo.orders[7]
    deadline = order.estimated_delivery + timedelta(days=7)
    assert check_eligibility(order, ReturnReason.REGRET, deadline).outcome is Outcome.ELIGIBLE
    after = deadline + timedelta(days=1)
    assert check_eligibility(order, ReturnReason.REGRET, after).outcome is Outcome.EXPIRED


def test_preference_uses_seven_days(repo):
    order = repo.orders[7]
    within = order.estimated_delivery + timedelta(days=3)
    assert check_eligibility(order, ReturnReason.PREFERENCE, within).outcome is Outcome.ELIGIBLE


def test_defect_goes_through_exchange_warranty_and_manufacturer(repo):
    order = repo.orders[7]  # compra 03/02/2026, entrega prevista 17/02/2026
    assert check_eligibility(order, ReturnReason.DEFECT, date(2026, 3, 5)).outcome is Outcome.ELIGIBLE
    result = check_eligibility(order, ReturnReason.DEFECT, TODAY)
    assert result.outcome is Outcome.WARRANTY
    assert result.legal_warranty_until == date(2026, 5, 18)
    late = check_eligibility(order, ReturnReason.DEFECT, date(2026, 6, 1))
    assert late.outcome is Outcome.MANUFACTURER


def test_undelivered_and_cancelled_orders(repo):
    assert check_eligibility(repo.orders[8], ReturnReason.REGRET, TODAY).outcome is Outcome.NOT_DELIVERED
    assert check_eligibility(repo.orders[17], ReturnReason.REGRET, TODAY).outcome is Outcome.CANCELLED


# --- Horário ----------------------------------------------------------------
def _at(*args):
    return datetime(*args, tzinfo=STORE_TZ)


def test_open_on_weekday():
    status = store_status(_at(2026, 3, 25, 10, 30))
    assert status.is_open and status.closes_at.hour == 18


def test_closing_time_is_exclusive():
    status = store_status(_at(2026, 3, 25, 18, 0))
    assert not status.is_open and status.next_opening == _at(2026, 3, 26, 9, 0)


def test_saturday_afternoon_points_to_monday():
    status = store_status(_at(2026, 3, 28, 14, 0))
    assert not status.is_open and status.next_opening == _at(2026, 3, 30, 9, 0)


def test_before_opening_points_to_same_day():
    assert store_status(_at(2026, 3, 25, 7, 0)).next_opening == _at(2026, 3, 25, 9, 0)


def test_good_friday_is_closed():
    status = store_status(_at(2026, 4, 3, 11, 0))
    assert not status.is_open and status.holiday
    assert status.next_opening == _at(2026, 4, 4, 9, 0)
