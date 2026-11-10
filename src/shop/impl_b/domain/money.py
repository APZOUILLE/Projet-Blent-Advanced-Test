"""A value object for money, used everywhere inside implementation B.

Implementation A moves plain `int` cents around. Both are perfectly fine
designs; neither leaks through the HTTP contract, which speaks integers of
cents and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Money:
    """An amount in cents. Never negative in this application."""

    cents: int

    @classmethod
    def zero(cls) -> "Money":
        return cls(0)

    def __add__(self, other: "Money") -> "Money":
        return Money(self.cents + other.cents)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.cents - other.cents)

    def times(self, quantity: int) -> "Money":
        return Money(self.cents * quantity)

    def percentage(self, percent: int) -> "Money":
        """Return `percent` % of this amount, rounded down to the cent."""
        return Money(self.cents * percent // 100)
