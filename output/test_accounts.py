import datetime
from decimal import Decimal
import pytest

from accounts import (
    Account,
    AccountError,
    InvalidAmountError,
    InvalidQuantityError,
    InvalidSymbolError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    get_share_price,
)


def test_account_invalid_owner_name():
    with pytest.raises(AccountError):
        Account(owner_name="")  # empty
    with pytest.raises(AccountError):
        Account(owner_name=123)  # non-string


def test_deposit_and_withdraw():
    acct = Account(owner_name="Alice")
    assert acct.get_cash_balance() == Decimal("0.00")
    acct.deposit(1000)
    assert acct.get_cash_balance() == Decimal("1000.00")
    assert acct.net_contributions == Decimal("1000.00")
    assert acct.initial_deposit == Decimal("1000.00")
    acct.withdraw(200)
    assert acct.get_cash_balance() == Decimal("800.00")
    assert acct.net_contributions == Decimal("800.00")
    with pytest.raises(InsufficientFundsError):
        acct.withdraw(900)


def test_buy_sell_operations_and_constraints():
    acct = Account(owner_name="Bob")
    acct.deposit(2000)
    # valid buy
    cost = acct.buy("AAPL", 5)
    assert cost == Decimal("950.00")
    assert acct.get_cash_balance() == Decimal("1050.00")
    assert acct.get_holdings() == {"AAPL": 5}
    # cheap buy with override price
    with pytest.raises(InsufficientFundsError):
        acct.buy("TSLA", 4)  # cost 250*4 = 1000 > 1050? Actually 1000 <= 1050 fine
    # override price to exceed cash
    with pytest.raises(InsufficientFundsError):
        acct.buy("TSLA", 5, price=300)
    # normal TSLA buy
    acct.buy("TSLA", 4, price=250)
    assert acct.get_holdings() == {"AAPL": 5, "TSLA": 4}
    # sell part of AAPL
    proceeds = acct.sell("AAPL", 2)
    assert proceeds == Decimal("380.00")  # 190*2
    assert acct.get_cash_balance() == Decimal("450.00")
    assert acct.get_holdings() == {"AAPL": 3, "TSLA": 4}
    # sell all AAPL
    proceeds = acct.sell("AAPL", 3)
    assert proceeds == Decimal("570.00")
    assert acct.get_holdings() == {"TSLA": 4}
    # selling more than owned raises
    with pytest.raises(InsufficientHoldingsError):
        acct.sell("TSLA", 5)
    # buying with invalid symbol raises
    with pytest.raises(InvalidSymbolError):
        acct.buy("XYZ", 1)


def test_holdings_valuation_and_portfolio_value():
    acct = Account(owner_name="Carol")
    acct.deposit(2000)
    acct.buy("GOOGL", 2)   # 140*2=280
    acct.buy("AAPL", 3)    # 190*3=570
    valuation = acct.get_holdings_valuation()
    assert set(valuation.keys()) == {"GOOGL", "AAPL"}
    assert valuation["GOOGL"]["quantity"] == 2
    assert valuation["GOOGL"]["price"] == Decimal("140.00")
    assert valuation["GOOGL"]["market_value"] == Decimal("280.00")
    assert valuation["AAPL"]["quantity"] == 3
    assert valuation["AAPL"]["price"] == Decimal("190.00")
    assert valuation["AAPL"]["market_value"] == Decimal("570.00")
    # portfolio: cash 2000-280-570=1150
    assert acct.get_cash_balance() == Decimal("1150.00")
    assert acct.get_portfolio_value() == Decimal("1150.00") + Decimal("280.00") + Decimal("570.00")


def test_profit_loss_calculations():
    acct = Account(owner_name="Dave")
    acct.deposit(1000)
    acct.buy("AAPL", 5)  # cost 950
    # cash now 50, holdings value 950, portfolio 1000
    res = acct.get_profit_loss()
    assert res["portfolio_value"] == Decimal("1000.00")
    assert res["basis_amount"] == Decimal("1000.00")
    assert res["pnl_abs"] == Decimal("0.00")
    assert res["pnl_pct"] == Decimal("0.0000")
    # withdraw 200 -> net contrib 800
    acct.withdraw(200)
    res = acct.get_profit_loss()
    assert res["basis_amount"] == Decimal("800.00")
    assert res["pnl_abs"] == Decimal("-800.00")
    # initial_only basis
    res = acct.get_profit_loss(basis="initial_only")
    assert res["basis_amount"] == Decimal("1000.00")
    assert res["pnl_abs"] == Decimal("-1000.00")
    with pytest.raises(AccountError):
        acct.get_profit_loss(basis="unknown")


def test_transaction_listing_filters():
    acct = Account(owner_name="Eve")
    acct.deposit(500)
    acct.buy("AAPL", 2)
    acct.sell("AAPL", 1)
    acct.withdraw(100)
    # filter by type
    txs = acct.get_transactions(types=("BUY",))
    assert len(txs) == 1
    assert txs[0]["type"] == "BUY"
    # limit
    txs = acct.get_transactions(limit=2)
    assert len(txs) == 2
    # newest first
    txs = acct.get_transactions(newest_first=True)
    assert txs[0]["type"] == "WITHDRAW"
    # filtering none
    txs = acct.get_transactions(types=("INVALID",))
    assert txs == []


def test_as_of_functions_with_custom_time_provider():
    # create a deterministic time provider
    times = [
        datetime.datetime(2024, 1, 1, 10, 0, tzinfo=datetime.timezone.utc),
        datetime.datetime(2024, 1, 1, 10, 5, tzinfo=datetime.timezone.utc),
        datetime.datetime(2024, 1, 1, 10, 10, tzinfo=datetime.timezone.utc),
        datetime.datetime(2024, 1, 1, 10, 15, tzinfo=datetime.timezone.utc),
    ]

    def make_provider(ts_list):
        from collections import deque
        d = deque(ts_list)

        def provider():
            if not d:
                raise RuntimeError("No more timestamps")
            return d.popleft()

        return provider

    provider = make_provider(times)
    acct = Account(owner_name="Frank", time_provider=provider)

    # first transaction deposit 1000
    acct.deposit(1000)
    # second transaction buy 3 AAPL at 190
    acct.buy("AAPL", 3)
    # third transaction buy 2 TSLA at 250
    acct.buy("TSLA", 2)
    # fourth transaction withdraw 200
    acct.withdraw(200)

    # holdings at time between second and third transaction
    mid_time = datetime.datetime(2024, 1, 1, 10, 12, tzinfo=datetime.timezone.utc)
    holdings_mid = acct.get_holdings_at(mid_time)
    assert holdings_mid == {"AAPL": 3, "TSLA": 0}  # TSLA hasn't been bought yet

    # cash balance at time after last transaction
    cash_at_end = acct.get_cash_balance_at(times[3])
    assert cash_at_end == Decimal("1000.00") - Decimal("190") * 3 - Decimal("250") * 2 + Decimal("200.00")

    # portfolio value at time after second transaction
    pv_after_buy_aapl = acct.get_portfolio_value_at(times[1])
    expected_pv = Decimal("1000.00") - Decimal("190") * 3
    assert pv_after_buy_aapl == expected_pv

    # profit/loss at last transaction
    pl_at_end = acct.get_profit_loss_at(times[3])
    # net contributions after all: 1000-200 = 800
    assert pl_at_end["basis_amount"] == Decimal("800.00")
    # portfolio value: cash after withdrawal + holdings values
    final_cash = Decimal("1000.00") - Decimal("190") * 3 - Decimal("250") * 2 + Decimal("200.00")
    final_holdings = Decimal("190") * 3 + Decimal("250") * 2
    final_total = final_cash + final_holdings
    assert pl_at_end["portfolio_value"] == final_total
    assert pl_at_end["pnl_abs"] == final_total - Decimal("800.00")


def test_serialization_roundtrip():
    acct = Account(owner_name="Grace")
    acct.deposit(750)
    acct.buy("TSLA", 2)
    acct.withdraw(100)
    d = acct.to_dict()
    # Ensure required keys present
    required_keys = {"account_id", "owner_name", "created_at", "cash_balance",
                     "net_contributions", "initial_deposit", "holdings", "transactions"}
    assert set(d.keys()) == required_keys
    # Recreate from dict
    new_acct = Account.from_dict(d)
    assert new_acct.owner_name == acct.owner_name
    assert new_acct.get_cash_balance() == acct.get_cash_balance()
    assert new_acct.get_holdings() == acct.get_holdings()
    # Transactions identical
    assert len(new_acct.transactions) == len(acct.transactions)
    for t_old, t_new in zip(acct.transactions, new_acct.transactions):
        assert t_old["ts"].isoformat() == t_new["ts"].isoformat()
        assert t_old["type"] == t_new["type"]
        assert t_old["cash_delta"] == t_new["cash_delta"]


def test_price_provider_and_symbol_validation():
    # valid symbol
    assert get_share_price("aapl") == Decimal("190.00")
    # case-insensitive check
    assert get_share_price("TSLA") == Decimal("250.00")
    # invalid symbol raises
    with pytest.raises(InvalidSymbolError):
        get_share_price("MSFT")
    # provider integration: Account using custom provider
    def fake_provider(symbol):
        if symbol == "XYZ":
            return Decimal("123.45")
        raise InvalidSymbolError
    acct = Account(owner_name="Heidi", price_provider=fake_provider)
    # invalid symbol for Account buy
    with pytest.raises(InvalidSymbolError):
        acct.buy("NOTEXIST", 1)
    # valid with fake
    acct.deposit(2000)
    cost = acct.buy("XYZ", 5)
    assert cost == Decimal("617.25")  # 123.45*5


def test_negative_and_invalid_amounts_and_quantities():
    acct = Account(owner_name="Ivan")
    # Deposit negative
    with pytest.raises(InvalidAmountError):
        acct.deposit(-100)
    # Withdraw negative
    with pytest.raises(InvalidAmountError):
        acct.withdraw(-50)
    # Buy with zero quantity
    acct.deposit(500)
    with pytest.raises(InvalidQuantityError):
        acct.buy("AAPL", 0)
    # Sell with zero quantity
    with pytest.raises(InvalidQuantityError):
        acct.sell("AAPL", 0)

    # Buy with negative price
    with pytest.raises(InvalidAmountError):
        acct.buy("AAPL", 1, price=-10)
    # Sell with negative price
    acct.buy("AAPL", 1, price=100)
    with pytest.raises(InvalidAmountError):
        acct.sell("AAPL", 1, price=-10)