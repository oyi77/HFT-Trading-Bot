"""Pre-trade validation chain for order safety checks."""

from dataclasses import dataclass
from typing import List, Callable, Optional, Any
from abc import ABC, abstractmethod


@dataclass
class ValidationResult:
    """Result of a validation check."""

    valid: bool
    reason: str = ""
    validator_name: str = ""


class Validator(ABC):
    """Abstract validator for pre-trade checks."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Validator name for logging."""
        pass

    @abstractmethod
    def validate(self, signal: dict, context: dict) -> ValidationResult:
        """Validate the signal.

        Args:
            signal: Trading signal from strategy
            context: Current market context (price, balance, positions, etc.)

        Returns:
            ValidationResult with valid=True if check passes
        """
        pass


class PriceSanityValidator(Validator):
    """Validates that price is within reasonable bounds."""

    @property
    def name(self) -> str:
        return "price_sanity"

    def validate(self, signal: dict, context: dict) -> ValidationResult:
        price = context.get("price", 0)
        if price <= 0:
            return ValidationResult(False, f"Invalid price: {price}", self.name)
        if price > 100000:
            return ValidationResult(False, f"Price too high: {price}", self.name)
        return ValidationResult(True, "", self.name)


class PositionLimitValidator(Validator):
    """Validates position count doesn't exceed limit."""

    def __init__(self, max_positions: int = 2):
        self.max_positions = max_positions

    @property
    def name(self) -> str:
        return "position_limit"

    def validate(self, signal: dict, context: dict) -> ValidationResult:
        positions = context.get("positions", [])
        if len(positions) >= self.max_positions:
            return ValidationResult(
                False,
                f"Max positions reached: {len(positions)}/{self.max_positions}",
                self.name,
            )
        return ValidationResult(True, "", self.name)


class BalanceValidator(Validator):
    """Validates sufficient balance for trade."""

    def __init__(self, min_balance: float = 10.0):
        self.min_balance = min_balance

    @property
    def name(self) -> str:
        return "balance"

    def validate(self, signal: dict, context: dict) -> ValidationResult:
        balance = context.get("balance", 0)
        if balance < self.min_balance:
            return ValidationResult(
                False,
                f"Insufficient balance: {balance:.2f} < {self.min_balance:.2f}",
                self.name,
            )
        return ValidationResult(True, "", self.name)


class LotSizeValidator(Validator):
    """Validates lot size is within acceptable range."""

    def __init__(self, min_lot: float = 0.01, max_lot: float = 1.0):
        self.min_lot = min_lot
        self.max_lot = max_lot

    @property
    def name(self) -> str:
        return "lot_size"

    def validate(self, signal: dict, context: dict) -> ValidationResult:
        amount = signal.get("amount", 0)
        if amount < self.min_lot:
            return ValidationResult(
                False, f"Lot too small: {amount} < {self.min_lot}", self.name
            )
        if amount > self.max_lot:
            return ValidationResult(
                False, f"Lot too large: {amount} > {self.max_lot}", self.name
            )
        return ValidationResult(True, "", self.name)


class ValidatorChain:
    """Chain of validators that must all pass for trade execution."""

    def __init__(self):
        self._validators: List[Validator] = []

    def add(self, validator: Validator) -> "ValidatorChain":
        """Add a validator to the chain."""
        self._validators.append(validator)
        return self

    def validate(self, signal: dict, context: dict) -> ValidationResult:
        """Run all validators.

        Returns:
            First failed validation, or success if all pass
        """
        for validator in self._validators:
            result = validator.validate(signal, context)
            if not result.valid:
                return result
        return ValidationResult(True, "")

    def validate_all(self, signal: dict, context: dict) -> List[ValidationResult]:
        """Run all validators and return all results."""
        return [v.validate(signal, context) for v in self._validators]


def create_default_validator_chain(
    max_positions: int = 2,
    min_balance: float = 10.0,
    min_lot: float = 0.01,
    max_lot: float = 1.0,
) -> ValidatorChain:
    """Create a default validator chain with common checks."""
    return (
        ValidatorChain()
        .add(PriceSanityValidator())
        .add(PositionLimitValidator(max_positions))
        .add(BalanceValidator(min_balance))
        .add(LotSizeValidator(min_lot, max_lot))
    )
