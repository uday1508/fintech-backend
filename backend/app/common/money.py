from dataclasses import dataclass
import re


_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int):
            raise TypeError("amount_minor must be an integer")
        normalized_currency = self.currency.upper()
        if not _CURRENCY_PATTERN.fullmatch(normalized_currency):
            raise ValueError("currency must be a three-letter currency code")
        object.__setattr__(self, "currency", normalized_currency)

    def __add__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def _ensure_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError("Cannot combine money values with different currencies")