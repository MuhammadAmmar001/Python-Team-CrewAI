# accounts.md

Title: Design Plan for accounts Module (Class: Account) — Trading Simulation Account Management

1) Overview

This document specifies the complete design for a simple account management system intended for a trading simulation platform. It defines the Python module name (accounts), the primary class (Account), all supporting classes/types, the interface to a price provider (get_share_price(symbol)), error handling, transaction logging, reporting functions (holdings, portfolio value, profit/loss), constraints, and a simple command-line UI design to exercise the backend. The design ensures that the backend developer can implement the entire system in one Python module with a cohesive, testable architecture.

2) Goals and Scope

- Users can:
  - Create an account
  - Deposit funds
  - Withdraw funds
  - Buy/Sell shares by quantity
  - List holdings at any time
  - Get portfolio total value at any time
  - Get profit/loss since inception or relative to initial deposit
  - List transactions over time
- System enforces constraints:
  - No negative cash balances
  - Cannot buy more shares than cash can cover
  - Cannot sell more shares than held
- Price data:
  - A function get_share_price(symbol) returns current prices
  - A test implementation returns fixed prices for AAPL, TSLA, GOOGL
- Single-module implementation:
  - Module name: accounts
  - Primary class: Account
  - Include a simple CLI UI in the same module for manual testing

3) Architectural Overview

- Core entity: Account
- Data maintained by Account:
  - Owner info and identifiers
  - Cash balance
  - Net contributions (sum of deposits minus withdrawals)
  - Initial deposit amount (first deposit at account creation)
  - Holdings: mapping from symbol to share quantity
  - Transactions: append-only ordered list of all account events
- Services:
  - Price Provider: get_share_price(symbol) pluggable via dependency injection; a default test provider returns fixed prices
  - Time Provider: customizable via dependency injection for deterministic testing of timestamps
- Reporting:
  - Holdings and value on-demand based on current price provider
  - As-of (historical point-in-time) holdings and P/L by replaying transactions up to a given timestamp
- UI:
  - Simple CLI loop with commands: create, deposit, withdraw, buy, sell, holdings, value, pnl, txns, prices, help, quit

4) Key Design Decisions

- Currency precision: Use Decimal with ROUND_HALF_UP policy for money and prices; quantize money to 2 decimal places.
- Quantities: Integer share quantities; must be positive; zero is invalid for trade operations.
- P/L definitions:
  - Since inception (net contributions basis): portfolio_value_now - net_contributions_to_date
  - From initial deposit only: portfolio_value_now - initial_deposit (simple view)
- Historical reporting:
  - holdings_at and pnl_at are computed by replaying transactions through the given timestamp. Valuations use the current price provider (which may be static in tests).
- Transactions:
  - Append-only list with immutable records capturing event data and resulting cash balance.
- Validation:
  - Strict input validation on symbol, quantity, and monetary amounts.
- Extensibility:
  - Future support for fees, average cost basis, realized/unrealized P/L, and per-symbol cost tracking can be added without changing the external API.

5) Module Structure (accounts)

The module will contain:
- Imports
- Constants and configuration
- Exceptions
- Data types/models
- Price provider interface and default test implementation
- Utility functions (Decimal handling, time provider)
- Account class with full API
- CLI: main() to run an interactive command loop

6) Exceptions

Define precise exceptions for predictable error handling:
- AccountError(Exception): Base exception for account-related errors
- InvalidAmountError(AccountError): Amount <= 0 or invalid numeric format
- InvalidQuantityError(AccountError): Quantity <= 0 or non-integer
- InvalidSymbolError(AccountError): Unsupported or malformed symbol
- InsufficientFundsError(AccountError): Withdrawal or purchase exceeds available cash
- InsufficientHoldingsError(AccountError): Sell quantity exceeds holdings
- PriceUnavailableError(AccountError): Price provider cannot return a price

7) Data Models

7.1) Transaction record (dict structure or dataclass; stored internally as dicts)
- Fields:
  - id: str (unique transaction id, e.g., UUID or incrementing counter)
  - ts: datetime (UTC)
  - type: str in {'DEPOSIT', 'WITHDRAW', 'BUY', 'SELL'}
  - symbol: Optional[str] (None for deposits/withdrawals)
  - quantity: Optional[int] (None for deposits/withdrawals)
  - price: Optional[Decimal] (trade price; None for deposits/withdrawals)
  - cash_delta: Decimal (positive for deposit and sell proceeds; negative for withdrawal and buy cost)
  - cash_balance_after: Decimal (cash after transaction)
  - note: Optional[str]
- Invariants:
  - For deposits: symbol=None, quantity=None, price=None, cash_delta > 0
  - For withdrawals: symbol=None, quantity=None, price=None, cash_delta < 0
  - For buy: symbol set, quantity > 0, price > 0, cash_delta negative
  - For sell: symbol set, quantity > 0, price > 0, cash_delta positive

7.2) Holdings (dict[str, int])
- Keys: uppercased symbols
- Values: integer total shares owned
- Invariants: no negative quantities; zero-quantity symbols are removed from dict

7.3) Account State
- account_id: str
- owner_name: str
- created_at: datetime
- cash_balance: Decimal
- net_contributions: Decimal (sum deposits - withdrawals to date)
- initial_deposit: Decimal (first deposit; zero if none yet)
- holdings: dict[str, int]
- transactions: list[dict] (append-only)
- price_provider: Callable[[str], Decimal] returning Decimal price
- time_provider: Callable[[], datetime] returning aware datetime (UTC)

8) Constants and Config

- MONEY_PLACES = Decimal('0.01')
- PRICE_PLACES = Decimal('0.01')
- ROUNDING = decimal.ROUND_HALF_UP
- SUPPORTED_SYMBOLS for test provider: {'AAPL', 'TSLA', 'GOOGL'}

9) Price Provider Interface

9.1) get_share_price(symbol: str) -> Decimal
- Contract: Return the current price as Decimal for a symbol, uppercase-insensitive.
- Errors: Raise InvalidSymbolError or PriceUnavailableError if not found.

9.2) Default Test Implementation
- Fixed prices:
  - AAPL -> 190.00
  - TSLA -> 250.00
  - GOOGL -> 140.00
- Case-insensitive mapping; raises InvalidSymbolError for unsupported symbols.

10) Utility Functions (module-level)

- to_decimal(amount: Union[str, int, float, Decimal], quantize_to: Optional[Decimal] = MONEY_PLACES) -> Decimal
  - Convert input to Decimal, optional quantization, use ROUND_HALF_UP, validate finite and non-NaN

- validate_amount_positive(amount: Decimal) -> None
  - Raise InvalidAmountError if amount <= 0

- validate_quantity_positive(quantity: int) -> None
  - Raise InvalidQuantityError if quantity <= 0 or not int

- normalize_symbol(symbol: str) -> str
  - Strip/upper symbol; validate alphanumeric; raise InvalidSymbolError on empty/invalid

- now_utc() -> datetime
  - Return timezone-aware UTC datetime

- gen_txn_id() -> str
  - Return unique transaction id (e.g., uuid4 hex)

11) Account Class API

Class: Account

Constructor
def __init__(
    self,
    owner_name: str,
    account_id: Optional[str] = None,
    price_provider: Optional[Callable[[str], Decimal]] = None,
    time_provider: Optional[Callable[[], datetime]] = None,
) -> None

- Purpose: Initialize a new Account with zero balances and empty holdings/transactions.
- Behavior:
  - owner_name: required non-empty string
  - account_id: generated UUID if None
  - price_provider: default to module test provider if None
  - time_provider: default to module now_utc if None
  - cash_balance = Decimal('0.00')
  - net_contributions = Decimal('0.00')
  - initial_deposit = Decimal('0.00')
  - created_at = time_provider()
- Raises: AccountError for invalid owner_name

Deposit Funds
def deposit(self, amount: Union[str, int, float, Decimal], note: Optional[str] = None) -> None

- Purpose: Increase cash balance and net contributions
- Steps:
  1) Convert amount to Decimal; validate > 0; quantize to MONEY_PLACES
  2) Update cash_balance += amount
  3) Update net_contributions += amount
  4) If initial_deposit == 0 and there are no prior deposits, set initial_deposit = amount
  5) Append transaction:
     - type='DEPOSIT'
     - cash_delta=+amount
     - cash_balance_after=new balance
  6) Return None
- Raises: InvalidAmountError

Withdraw Funds
def withdraw(self, amount: Union[str, int, float, Decimal], note: Optional[str] = None) -> None

- Purpose: Decrease cash balance and net contributions; prevent negative cash
- Steps:
  1) Convert amount to Decimal; validate > 0; quantize
  2) Validate cash_balance - amount >= 0, else raise InsufficientFundsError
  3) Update cash_balance -= amount
  4) Update net_contributions -= amount
  5) Append transaction:
     - type='WITHDRAW'
     - cash_delta=-amount
     - cash_balance_after=new balance
- Raises: InvalidAmountError, InsufficientFundsError

Buy Shares
def buy(
    self,
    symbol: str,
    quantity: int,
    price: Optional[Union[str, int, float, Decimal]] = None,
    note: Optional[str] = None,
) -> Decimal

- Purpose: Purchase shares; reduce cash; record holdings; enforce affordability
- Inputs:
  - symbol: stock ticker (case-insensitive)
  - quantity: integer > 0
  - price: optional override; if None, fetch via price_provider
- Steps:
  1) Normalize symbol; validate quantity > 0
  2) Determine trade_price:
     - If price is None: price_provider(symbol)
     - Else: to_decimal(price, PRICE_PLACES); validate > 0
  3) Compute cost = (trade_price * quantity).quantize(MONEY_PLACES)
  4) Validate cost <= cash_balance; else raise InsufficientFundsError
  5) Update cash_balance -= cost
  6) Update holdings[symbol] += quantity (create key if missing)
  7) Append transaction:
     - type='BUY', symbol, quantity, price=trade_price, cash_delta=-cost
     - cash_balance_after=new balance
  8) Return cost
- Returns: Total cost as Decimal
- Raises: InvalidSymbolError, InvalidQuantityError, InvalidAmountError, InsufficientFundsError, PriceUnavailableError

Sell Shares
def sell(
    self,
    symbol: str,
    quantity: int,
    price: Optional[Union[str, int, float, Decimal]] = None,
    note: Optional[str] = None,
) -> Decimal

- Purpose: Sell shares; increase cash; reduce holdings; prevent short selling
- Steps:
  1) Normalize symbol; validate quantity > 0
  2) Validate holdings.get(symbol, 0) >= quantity; else InsufficientHoldingsError
  3) Determine trade_price:
     - If price is None: price_provider(symbol)
     - Else: to_decimal(price, PRICE_PLACES); validate > 0
  4) Compute proceeds = (trade_price * quantity).quantize(MONEY_PLACES)
  5) Update cash_balance += proceeds
  6) Update holdings[symbol] -= quantity; if zero, remove symbol key
  7) Append transaction:
     - type='SELL', symbol, quantity, price=trade_price, cash_delta=+proceeds
     - cash_balance_after=new balance
  8) Return proceeds
- Returns: Total proceeds as Decimal
- Raises: InvalidSymbolError, InvalidQuantityError, InvalidAmountError, InsufficientHoldingsError, PriceUnavailableError

Get Cash Balance
def get_cash_balance(self) -> Decimal

- Purpose: Return current cash balance (Decimal, quantized)

List Holdings (current)
def get_holdings(self) -> Dict[str, int]

- Purpose: Return shallow copy of holdings dict; symbols as uppercased strings

Holdings Valuation (per-symbol breakdown)
def get_holdings_valuation(self) -> Dict[str, Dict[str, Decimal]]

- Purpose: Valuate holdings per symbol using current price provider
- Returns: dict mapping symbol to:
  - quantity: int
  - price: Decimal
  - market_value: Decimal (quantity * price, quantized)
- Raises: InvalidSymbolError, PriceUnavailableError if provider cannot price a held symbol

Total Portfolio Value (cash + equities)
def get_portfolio_value(self) -> Decimal

- Purpose: Sum cash_balance and total market value of holdings
- Steps:
  1) total_value = cash_balance
  2) For each symbol in holdings, add quantity * get_share_price(symbol), quantized
  3) Return Decimal total_value
- Raises: Propagates price errors if any

Profit/Loss Reporting (current)
def get_profit_loss(
    self,
    basis: str = 'net_contributions',
    include_unrealized: bool = True,
) -> Dict[str, Decimal]

- Purpose: Report P/L vs chosen basis
- Parameters:
  - basis:
    - 'net_contributions': portfolio_value - net_contributions
    - 'initial_only': portfolio_value - initial_deposit
  - include_unrealized: kept for API symmetry; currently valuations are unrealized
- Returns:
  - dict with:
    - portfolio_value: Decimal
    - basis_amount: Decimal (net_contributions or initial_deposit)
    - pnl_abs: Decimal (portfolio_value - basis_amount)
    - pnl_pct: Decimal (pnl_abs / basis_amount) if basis_amount > 0 else None
- Notes: If basis_amount == 0 (no deposits yet), pct is None

Transactions Listing
def get_transactions(
    self,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    types: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
    newest_first: bool = False,
) -> List[Dict[str, Any]]

- Purpose: Filter and return transaction records
- Behavior:
  - Apply time window [since, until]
  - Filter by types if provided
  - Order ascending by ts unless newest_first
  - Apply limit to the resulting list
- Returns: Deep copies of transactions (or safe read-only dicts)

As-of Holdings (historical)
def get_holdings_at(self, at: Optional[datetime]) -> Dict[str, int]

- Purpose: Reconstruct holdings at a given timestamp
- Steps:
  1) Initialize empty holdings dict
  2) Replay transactions in ascending order where ts <= at
  3) For BUY: holdings[symbol] += quantity; for SELL: -= quantity; remove symbol if zero
  4) Ignore DEPOSIT/WITHDRAW for holdings
  5) Return holdings snapshot

As-of Cash Balance (historical)
def get_cash_balance_at(self, at: Optional[datetime]) -> Decimal

- Purpose: Reconstruct cash balance at a given timestamp
- Steps:
  1) Initialize cash = Decimal('0.00')
  2) Replay transactions with ts <= at
  3) Update cash using cash_delta for each txn
  4) Return cash

As-of Portfolio Value (historical)
def get_portfolio_value_at(self, at: Optional[datetime]) -> Decimal

- Purpose: Valuate holdings at time 'at' using current price provider
- Steps:
  1) holdings = get_holdings_at(at)
  2) cash = get_cash_balance_at(at)
  3) For each symbol in holdings: value += quantity * get_share_price(symbol)
  4) total = cash + equities_value
  5) Return total

As-of Profit/Loss
def get_profit_loss_at(
    self,
    at: Optional[datetime],
    basis: str = 'net_contributions',
) -> Dict[str, Decimal]

- Purpose: P/L at a given time 'at'
- Steps:
  1) portfolio_value = get_portfolio_value_at(at)
  2) Compute basis_amount:
     - net_contributions_at: sum of deposits minus withdrawals with ts <= at
     - initial_only: initial_deposit if initial deposit timestamp <= at else Decimal('0.00')
  3) pnl_abs = portfolio_value - basis_amount
  4) pnl_pct = pnl_abs / basis_amount if basis_amount > 0 else None
  5) Return dict as in get_profit_loss

Serialization (optional but helpful)
def to_dict(self) -> Dict[str, Any]

- Purpose: Serialize account state for persistence
- Content: account_id, owner_name, created_at ISO, cash_balance, net_contributions, initial_deposit, holdings, transactions (with Decimals as strings), etc.

Deserialization
@classmethod
def from_dict(
    cls,
    data: Dict[str, Any],
    price_provider: Optional[Callable[[str], Decimal]] = None,
    time_provider: Optional[Callable[[], datetime]] = None,
) -> 'Account'

- Purpose: Re-create an Account from serialized data
- Steps: Validate fields, parse Decimals, datetimes; reconstruct transactions and holdings; set providers

Internal Helpers (private methods)
- _append_transaction(self, txn: Dict[str, Any]) -> None
  - Adds txn to list; may enforce that cash_balance_after equals current balance

- _get_price(self, symbol: str) -> Decimal
  - Calls price_provider and enforces Decimal and quantization

- _replay_until(self, at: Optional[datetime]) -> Tuple[Decimal, Dict[str, int]]
  - Utility to reconstruct cash and holdings up to time at

12) Method Signatures Summary (Skeleton)

The module will expose the following signatures for implementation clarity:

# Module: accounts

from decimal import Decimal
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

# Exceptions
class AccountError(Exception): ...
class InvalidAmountError(AccountError): ...
class InvalidQuantityError(AccountError): ...
class InvalidSymbolError(AccountError): ...
class InsufficientFundsError(AccountError): ...
class InsufficientHoldingsError(AccountError): ...
class PriceUnavailableError(AccountError): ...

# Price provider (default test)
def get_share_price(symbol: str) -> Decimal: ...

# Utilities
def to_decimal(amount: Any, quantize_to: Optional[Decimal] = None) -> Decimal: ...
def validate_amount_positive(amount: Decimal) -> None: ...
def validate_quantity_positive(quantity: int) -> None: ...
def normalize_symbol(symbol: str) -> str: ...
def now_utc() -> datetime: ...
def gen_txn_id() -> str: ...

# Account class
class Account:
    def __init__(
        self,
        owner_name: str,
        account_id: Optional[str] = None,
        price_provider: Optional[Callable[[str], Decimal]] = None,
        time_provider: Optional[Callable[[], datetime]] = None,
    ) -> None: ...

    def deposit(self, amount: Any, note: Optional[str] = None) -> None: ...
    def withdraw(self, amount: Any, note: Optional[str] = None) -> None: ...
    def buy(self, symbol: str, quantity: int, price: Optional[Any] = None, note: Optional[str] = None) -> Decimal: ...
    def sell(self, symbol: str, quantity: int, price: Optional[Any] = None, note: Optional[str] = None) -> Decimal: ...
    def get_cash_balance(self) -> Decimal: ...
    def get_holdings(self) -> Dict[str, int]: ...
    def get_holdings_valuation(self) -> Dict[str, Dict[str, Decimal]]: ...
    def get_portfolio_value(self) -> Decimal: ...
    def get_profit_loss(self, basis: str = 'net_contributions', include_unrealized: bool = True) -> Dict[str, Optional[Decimal]]: ...
    def get_transactions(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        types: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        newest_first: bool = False,
    ) -> List[Dict[str, Any]]: ...
    def get_holdings_at(self, at: Optional[datetime]) -> Dict[str, int]: ...
    def get_cash_balance_at(self, at: Optional[datetime]) -> Decimal: ...
    def get_portfolio_value_at(self, at: Optional[datetime]) -> Decimal: ...
    def get_profit_loss_at(self, at: Optional[datetime], basis: str = 'net_contributions') -> Dict[str, Optional[Decimal]]: ...
    def to_dict(self) -> Dict[str, Any]: ...
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        price_provider: Optional[Callable[[str], Decimal]] = None,
        time_provider: Optional[Callable[[], datetime]] = None,
    ) -> 'Account': ...
    # Internal helpers
    def _append_transaction(self, txn: Dict[str, Any]) -> None: ...
    def _get_price(self, symbol: str) -> Decimal: ...
    def _replay_until(self, at: Optional[datetime]) -> Dict[str, Any]: ...

# CLI entry point
def main() -> None: ...

if __name__ == '__main__':
    main()

13) Detailed Behaviors and Validation Rules

- owner_name must be a non-empty trimmed string; raise AccountError otherwise.
- Amounts:
  - deposit/withdraw amounts must be > 0
  - Withdraw cannot exceed current cash_balance
- Quantities:
  - Integers only; > 0
- Symbols:
  - Alphanumeric, uppercased; validated via normalize_symbol
- Prices:
  - If provided externally, must be > 0 Decimal; else resolved via price provider
- Cash arithmetic:
  - Always quantize to MONEY_PLACES after arithmetic
  - After each transaction, cash_balance_after must equal current cash
- Holdings arithmetic:
  - No negative holdings; remove symbols with zero holdings
- Transactions:
  - Each append must include consistent derived fields

14) Reporting Logic Details

- get_holdings_valuation:
  - For each symbol, call price provider once per call
  - Values quantized to MONEY_PLACES
- get_portfolio_value:
  - cash_balance + sum(market_values)
- get_profit_loss:
  - portfolio_value = get_portfolio_value()
  - basis_amount:
    - net_contributions: track continuously within account
    - initial_only: use initial_deposit captured at first deposit
- Historical as-of:
  - Recompute state by replay (functional reconstruction), assuring correctness regardless of mutations since

15) Command-Line UI (Simple Interactive Shell)

15.1) Goals
- Provide a simple way to test backend flows end-to-end in the same module
- Single account per session (create command)

15.2) Commands and Usage
- help
  - List commands and brief usage
- create <owner_name>
  - Initialize a new Account; error if account already exists (confirm override)
- deposit <amount> [note...]
- withdraw <amount> [note...]
- buy <symbol> <quantity> [price] [note...]
  - If price omitted, uses provider price
- sell <symbol> <quantity> [price] [note...]
  - If price omitted, uses provider price
- holdings
  - Print current holdings
- value
  - Print portfolio value and cash
- pnl [basis]
  - basis in {net_contributions, initial_only}; default net_contributions
- txns [limit] [types...]
  - Print recent transactions; types optional subset of DEPOSIT WITHDRAW BUY SELL
- prices
  - Show test provider prices for known symbols
- quit/exit
  - Exit program

15.3) UI Implementation Outline
- Maintain a global or closure-scoped Account instance (None until created)
- Parse input line by space; handle quoted notes via shlex.split
- Convert numeric inputs robustly; print human-readable errors on exceptions
- Show Decimal values with 2 decimal places
- For txns printing, include timestamp, type, symbol, qty, price, cash_delta, cash_after, note

16) Test Price Provider Details

- Function: get_share_price(symbol: str) -> Decimal
- Internals:
  - mapping = {'AAPL': Decimal('190.00'), 'TSLA': Decimal('250.00'), 'GOOGL': Decimal('140.00')}
  - Normalize input symbol; if not in mapping: raise InvalidSymbolError(f"Unsupported symbol: {symbol}")
  - Return mapping[symbol]

17) Edge Cases and Handling

- Deposits/withdrawals of fractional cents: amount is quantized to 2 decimals; fractions beyond are rounded with ROUND_HALF_UP
- Zero deposits/withdrawals/trades: reject with InvalidAmountError/InvalidQuantityError
- Selling all holdings of a symbol: remove symbol entry from holdings
- Case-insensitive symbols: normalize to uppercase
- Fetching holdings/value when there are no holdings: return empty valuations, portfolio equals cash
- P/L when basis_amount is zero: P/L percent = None (avoid division by zero)
- Transactions filters with no match: return empty list
- Historical at times before account creation: everything zero
- Negative price or zero price provided externally: InvalidAmountError

18) Performance Considerations

- The design is in-memory and single-account per process for UI. For small transaction counts, replay for as-of queries is acceptable.
- If transaction volume grows, caching or snapshotting could be introduced later without changing public API.

19) Security and Integrity

- Transactions are append-only; no in-place edits
- Cash and holdings invariants enforced at method boundaries
- Input validation to prevent inconsistent state
- Future enhancement: external persistence with integrity checks

20) Examples (Intended Behavior)

Example Flow:
- create Alice
- deposit 10000
- buy AAPL 10
  - Price 190.00 -> cost 1900.00; cash -> 8100.00
- buy TSLA 5
  - Price 250.00 -> cost 1250.00; cash -> 6850.00
- sell AAPL 3
  - Proceeds 570.00; cash -> 7420.00
- holdings -> {'AAPL': 7, 'TSLA': 5}
- value:
  - AAPL: 7 * 190.00 = 1330.00
  - TSLA: 5 * 250.00 = 1250.00
  - Equities total = 2580.00; cash = 7420.00; portfolio = 10000.00
- pnl net_contributions:
  - net_contributions = 10000.00
  - portfolio = 10000.00
  - pnl_abs = 0.00, pnl_pct = 0.00

21) Testing Plan

- Unit tests:
  - deposit/withdraw validations and balances
  - buy/sell constraints and holdings changes
  - price provider mapping and errors
  - P/L calculations with and without additional deposits/withdrawals
  - As-of functions with a controlled time_provider and deterministic sequence
  - Transactions listing filters, ordering, and limits
- UI tests:
  - Simulate sequences via stdin, assert printed results

22) Implementation Notes

- Use Decimal consistently; wrap all incoming numeric values via to_decimal
- Centralize price fetching via _get_price
- Ensure all externally returned Decimals are quantized and not Context-dependent
- Implement robust error messages to aid UI and debugging

23) Acceptance Criteria Mapping

- Create account: Account.__init__
- Deposit: deposit
- Withdraw: withdraw with no negative cash allowed
- Buy/Sell: buy / sell with validations (affordability and holdings availability)
- Portfolio value: get_portfolio_value (and per-symbol via get_holdings_valuation)
- P/L: get_profit_loss (and at-time variant)
- Holdings report: get_holdings (and at-time variant)
- Transactions list: get_transactions
- Constraints enforced: InsufficientFundsError, InsufficientHoldingsError, InvalidSymbolError, InvalidAmountError
- Price provider with fixed prices for AAPL, TSLA, GOOGL: get_share_price

24) Future Extensions (Out of Scope but Noted)

- Realized vs. unrealized P/L
- Cost basis tracking (FIFO/LIFO/Avg)
- Order fees/commissions/slippage
- Multi-currency support
- Persistent storage (files/database)
- Multi-account management in the same process

End of accounts module design.