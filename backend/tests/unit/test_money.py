import pytest

from app.common.money import Money


def test_money_adds_and_subtracts_minor_units() -> None:
    amount = Money(65_000, "inr")

    assert amount.currency == "INR"
    assert amount + Money(10_000, "INR") == Money(75_000, "INR")
    assert amount - Money(5_000, "INR") == Money(60_000, "INR")


def test_money_rejects_fractional_minor_units() -> None:
    with pytest.raises(TypeError, match="integer"):
        Money(1.5, "INR")  # type: ignore[arg-type]


def test_money_rejects_invalid_currency() -> None:
    with pytest.raises(ValueError, match="three-letter"):
        Money(100, "US")


def test_money_rejects_arithmetic_across_currencies() -> None:
    with pytest.raises(ValueError, match="different currencies"):
        Money(100, "INR") + Money(100, "USD")

