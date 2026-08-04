"""Tests for payment.py — run with: python test_payment.py"""

from payment import calculate_bill, generate_bill_text, applied_offer, OFFERS

CART = [
    {"item": "Cappuccino", "size": "Large", "price": 250},
    {"item": "Latte", "size": "Medium", "price": 200},
    {"item": "Brownie", "size": "-", "price": 160},
]
TOTAL = 610


def test_percent_offer():
    final, discount, msg = applied_offer("SAVE20", CART, TOTAL)
    assert discount == 122, f"expected 122, got {discount}"
    assert final == TOTAL - 122


def test_flat_offer():
    final, discount, msg = applied_offer("NOVA50", CART, TOTAL)
    assert discount == 50
    assert final == TOTAL - 50


def test_item_offer_in_cart():
    final, discount, msg = applied_offer("LATTE_OFF", CART, TOTAL)
    assert discount == 50, "Latte is in cart, discount should apply"


def test_item_offer_not_in_cart():
    no_latte = [i for i in CART if i["item"] != "Latte"]
    final, discount, msg = applied_offer("LATTE_OFF", no_latte, 410)
    assert discount == 0, "Latte not in cart, no discount"
    assert final == 410


def test_invalid_code():
    final, discount, msg = applied_offer("HELLO", CART, TOTAL)
    assert discount == 0
    assert final == TOTAL


def test_case_and_spaces():
    final, discount, _ = applied_offer("  save20  ", CART, TOTAL)
    assert discount == 122, "lowercase + spaces should still work"


def test_discount_never_below_zero():
    final, discount, _ = applied_offer("NOVA100", CART, 50)
    assert final == 0, "total must never go below 0"


def test_calculate_bill_items():
    bill = calculate_bill([{"items": [{"item": "Latte", "size": "Medium", "price": 200}]}])
    assert bill["total"] == 200
    assert bill["items"][0]["item"] == "Latte (Medium)"


def test_generate_bill_text():
    bill = {"items": [{"item": "Latte", "price": 200}], "total": 200}
    text = generate_bill_text(bill)
    assert "Total: ₹200" in text


def test_offers_registry_is_not_empty():
    assert len(OFFERS) > 0


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"  FAIL  {name} -> {e}")
    print("-" * 40)
    if failures:
        print(f"{failures} test(s) FAILED")
    else:
        print("All tests passed!")
