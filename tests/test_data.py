from decimal import Decimal

from emporio_agent.domain.models import OrderStatus, ProductStatus


def test_tables_load_with_expected_sizes(repo):
    assert len(repo.products) == 65
    assert len(repo.customers) == 50
    assert len(repo.orders) == 20
    assert len(repo.promotions) == 25
    assert len(repo.categories) == 9


def test_csv_quirks_are_preserved_as_data(repo):
    assert repo.products[136].status is ProductStatus.DISCONTINUED and repo.products[136].stock == 13
    assert repo.products[130].status is ProductStatus.COMING_SOON and repo.products[130].stock == 2
    assert repo.products[96].status is ProductStatus.ACTIVE and repo.products[96].stock == 0


def test_money_is_decimal(repo):
    assert repo.products[81].price == Decimal("599.9")


def test_customer_contact_is_normalized(repo):
    assert repo.customers[1].phone_digits == "67998123456"
    assert repo.customers[1].first_name == "Lucas"


def test_optional_order_fields_become_none(repo):
    order = repo.orders[9]
    assert order.status is OrderStatus.CONFIRMED
    assert order.tracking_code is None and order.estimated_delivery is None and order.notes is None


def test_order_with_multiple_items(repo):
    assert [i.product_id for i in repo.items_of(15)] == [82, 106]


def test_product_with_several_promotions(repo):
    assert sorted(p.discount_percent for p in repo.promotions_of(96)) == [18, 40]
