import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional
import uuid
import copy
import shlex

MONEY_PLACES = Decimal('0.01')
PRICE_PLACES = Decimal('0.01')
ROUNDING = ROUND_HALF_UP
SUPPORTED_SYMBOLS = {'AAPL', 'TSLA', 'GOOGL'}

class AccountError(Exception):
    pass

class InvalidAmountError(AccountError):
    pass

class InvalidQuantityError(AccountError):
    pass

class InvalidSymbolError(AccountError):
    pass

class InsufficientFundsError(AccountError):
    pass

class InsufficientHoldingsError(AccountError):
    pass

class PriceUnavailableError(AccountError):
    pass

def to_decimal(amount: Any, quantize_to: Optional[Decimal] = None) -> Decimal:
    try:
        if isinstance(amount, Decimal):
            d = amount
        elif isinstance(amount, (int,)):
            d = Decimal(amount)
        elif isinstance(amount, float):
            d = Decimal(str(amount))
        elif isinstance(amount, str):
            s = amount.strip()
            if not s:
                raise InvalidAmountError('Empty amount string')
            d = Decimal(s)
        else:
            raise InvalidAmountError('Unsupported amount type')
    except Exception as e:
        raise InvalidAmountError(f'Invalid amount: {amount}') from e
    if not d.is_finite():
        raise InvalidAmountError('Amount must be finite')
    if quantize_to is not None:
        d = d.quantize(quantize_to, rounding=ROUNDING)
    return d

def validate_amount_positive(amount: Decimal) -> None:
    if amount <= Decimal('0'):
        raise InvalidAmountError('Amount must be positive')

def validate_quantity_positive(quantity: int) -> None:
    if not isinstance(quantity, int):
        raise InvalidQuantityError('Quantity must be an integer')
    if quantity <= 0:
        raise InvalidQuantityError('Quantity must be positive')

def normalize_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise InvalidSymbolError('Symbol must be a string')
    s = symbol.strip().upper()
    if not s or not s.isalnum():
        raise InvalidSymbolError(f'Invalid symbol: {symbol}')
    return s

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def gen_txn_id() -> str:
    return uuid.uuid4().hex

def get_share_price(symbol: str) -> Decimal:
    s = normalize_symbol(symbol)
    mapping = {
        'AAPL': Decimal('190.00'),
        'TSLA': Decimal('250.00'),
        'GOOGL': Decimal('140.00'),
    }
    if s not in mapping:
        raise InvalidSymbolError(f'Unsupported symbol: {symbol}')
    return mapping[s]

class Account:
    def __init__(
        self,
        owner_name: str,
        account_id: Optional[str] = None,
        price_provider: Optional[Callable[[str], Decimal]] = None,
        time_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if not isinstance(owner_name, str) or not owner_name.strip():
            raise AccountError('owner_name must be a non-empty string')
        self.owner_name: str = owner_name.strip()
        self.account_id: str = account_id or uuid.uuid4().hex
        self.price_provider: Callable[[str], Decimal] = price_provider or get_share_price
        self.time_provider: Callable[[], datetime] = time_provider or now_utc
        self.created_at: datetime = self.time_provider()
        self.cash_balance: Decimal = Decimal('0.00').quantize(MONEY_PLACES)
        self.net_contributions: Decimal = Decimal('0.00').quantize(MONEY_PLACES)
        self.initial_deposit: Decimal = Decimal('0.00').quantize(MONEY_PLACES)
        self._initial_deposit_ts: Optional[datetime] = None
        self.holdings: Dict[str, int] = {}
        self.transactions: List[Dict[str, Any]] = []

    def _append_transaction(self, txn: Dict[str, Any]) -> None:
        expected = self.cash_balance
        cash_after = txn.get('cash_balance_after')
        if cash_after != expected:
            raise AccountError('Transaction cash balance mismatch')
        self.transactions.append(txn)

    def _get_price(self, symbol: str) -> Decimal:
        s = normalize_symbol(symbol)
        try:
            price = self.price_provider(s)
        except InvalidSymbolError:
            raise
        except Exception as e:
            raise PriceUnavailableError(f'Price unavailable for {s}') from e
        p = to_decimal(price, PRICE_PLACES)
        validate_amount_positive(p)
        return p

    def _replay_until(self, at: Optional[datetime]) -> Dict[str, Any]:
        cash = Decimal('0.00').quantize(MONEY_PLACES)
        holdings: Dict[str, int] = {}
        net_contrib = Decimal('0.00').quantize(MONEY_PLACES)
        initial_dep = Decimal('0.00').quantize(MONEY_PLACES)
        initial_dep_ts: Optional[datetime] = None
        for tx in self.transactions:
            ts = tx['ts']
            if at is not None and ts > at:
                break
            ttype = tx['type']
            if ttype == 'DEPOSIT':
                amt = tx['cash_delta']
                cash = (cash + amt).quantize(MONEY_PLACES)
                net_contrib = (net_contrib + amt).quantize(MONEY_PLACES)
                if initial_dep == Decimal('0.00'):
                    initial_dep = amt
                    initial_dep_ts = ts
            elif ttype == 'WITHDRAW':
                amt = tx['cash_delta']
                cash = (cash + amt).quantize(MONEY_PLACES)
                net_contrib = (net_contrib + amt).quantize(MONEY_PLACES)
            elif ttype == 'BUY':
                cash = (cash + tx['cash_delta']).quantize(MONEY_PLACES)
                sym = tx['symbol']
                qty = tx['quantity']
                holdings[sym] = holdings.get(sym, 0) + qty
                if holdings[sym] == 0:
                    holdings.pop(sym, None)
            elif ttype == 'SELL':
                cash = (cash + tx['cash_delta']).quantize(MONEY_PLACES)
                sym = tx['symbol']
                qty = tx['quantity']
                holdings[sym] = holdings.get(sym, 0) - qty
                if holdings[sym] == 0:
                    holdings.pop(sym, None)
        return {
            'cash': cash,
            'holdings': holdings,
            'net_contributions': net_contrib,
            'initial_deposit': initial_dep,
            'initial_deposit_ts': initial_dep_ts,
        }

    def deposit(self, amount: Any, note: Optional[str] = None) -> None:
        amt = to_decimal(amount, MONEY_PLACES)
        validate_amount_positive(amt)
        self.cash_balance = (self.cash_balance + amt).quantize(MONEY_PLACES)
        self.net_contributions = (self.net_contributions + amt).quantize(MONEY_PLACES)
        if self.initial_deposit == Decimal('0.00'):
            self.initial_deposit = amt
            self._initial_deposit_ts = self.time_provider()
            ts = self._initial_deposit_ts
        else:
            ts = self.time_provider()
        txn = {
            'id': gen_txn_id(),
            'ts': ts,
            'type': 'DEPOSIT',
            'symbol': None,
            'quantity': None,
            'price': None,
            'cash_delta': amt,
            'cash_balance_after': self.cash_balance,
            'note': note,
        }
        self._append_transaction(txn)

    def withdraw(self, amount: Any, note: Optional[str] = None) -> None:
        amt = to_decimal(amount, MONEY_PLACES)
        validate_amount_positive(amt)
        if self.cash_balance - amt < Decimal('0.00'):
            raise InsufficientFundsError('Insufficient cash for withdrawal')
        self.cash_balance = (self.cash_balance - amt).quantize(MONEY_PLACES)
        self.net_contributions = (self.net_contributions - amt).quantize(MONEY_PLACES)
        txn = {
            'id': gen_txn_id(),
            'ts': self.time_provider(),
            'type': 'WITHDRAW',
            'symbol': None,
            'quantity': None,
            'price': None,
            'cash_delta': -amt,
            'cash_balance_after': self.cash_balance,
            'note': note,
        }
        self._append_transaction(txn)

    def buy(self, symbol: str, quantity: int, price: Optional[Any] = None, note: Optional[str] = None) -> Decimal:
        sym = normalize_symbol(symbol)
        validate_quantity_positive(quantity)
        if price is None:
            trade_price = self._get_price(sym)
        else:
            trade_price = to_decimal(price, PRICE_PLACES)
            validate_amount_positive(trade_price)
        cost = (trade_price * Decimal(quantity)).quantize(MONEY_PLACES, rounding=ROUNDING)
        if cost > self.cash_balance:
            raise InsufficientFundsError('Insufficient cash to buy')
        self.cash_balance = (self.cash_balance - cost).quantize(MONEY_PLACES)
        self.holdings[sym] = self.holdings.get(sym, 0) + int(quantity)
        txn = {
            'id': gen_txn_id(),
            'ts': self.time_provider(),
            'type': 'BUY',
            'symbol': sym,
            'quantity': int(quantity),
            'price': trade_price,
            'cash_delta': -cost,
            'cash_balance_after': self.cash_balance,
            'note': note,
        }
        self._append_transaction(txn)
        return cost

    def sell(self, symbol: str, quantity: int, price: Optional[Any] = None, note: Optional[str] = None) -> Decimal:
        sym = normalize_symbol(symbol)
        validate_quantity_positive(quantity)
        held = self.holdings.get(sym, 0)
        if held < quantity:
            raise InsufficientHoldingsError('Not enough shares to sell')
        if price is None:
            trade_price = self._get_price(sym)
        else:
            trade_price = to_decimal(price, PRICE_PLACES)
            validate_amount_positive(trade_price)
        proceeds = (trade_price * Decimal(quantity)).quantize(MONEY_PLACES, rounding=ROUNDING)
        self.cash_balance = (self.cash_balance + proceeds).quantize(MONEY_PLACES)
        new_qty = held - int(quantity)
        if new_qty == 0:
            self.holdings.pop(sym, None)
        else:
            self.holdings[sym] = new_qty
        txn = {
            'id': gen_txn_id(),
            'ts': self.time_provider(),
            'type': 'SELL',
            'symbol': sym,
            'quantity': int(quantity),
            'price': trade_price,
            'cash_delta': proceeds,
            'cash_balance_after': self.cash_balance,
            'note': note,
        }
        self._append_transaction(txn)
        return proceeds

    def get_cash_balance(self) -> Decimal:
        return self.cash_balance

    def get_holdings(self) -> Dict[str, int]:
        return dict(self.holdings)

    def get_holdings_valuation(self) -> Dict[str, Dict[str, Decimal]]:
        result: Dict[str, Dict[str, Decimal]] = {}
        for sym, qty in self.holdings.items():
            price = self._get_price(sym)
            mv = (price * Decimal(qty)).quantize(MONEY_PLACES, rounding=ROUNDING)
            result[sym] = {
                'quantity': qty,
                'price': price,
                'market_value': mv,
            }
        return result

    def get_portfolio_value(self) -> Decimal:
        total = self.cash_balance
        for sym, qty in self.holdings.items():
            price = self._get_price(sym)
            total = (total + (price * Decimal(qty)).quantize(MONEY_PLACES, rounding=ROUNDING)).quantize(MONEY_PLACES)
        return total

    def get_profit_loss(self, basis: str = 'net_contributions', include_unrealized: bool = True) -> Dict[str, Optional[Decimal]]:
        pv = self.get_portfolio_value()
        if basis == 'net_contributions':
            basis_amount = self.net_contributions
        elif basis == 'initial_only':
            basis_amount = self.initial_deposit
        else:
            raise AccountError('Invalid basis')
        pnl_abs = (pv - basis_amount).quantize(MONEY_PLACES)
        pnl_pct = (pnl_abs / basis_amount).quantize(Decimal('0.0001')) if basis_amount > Decimal('0') else None
        return {
            'portfolio_value': pv,
            'basis_amount': basis_amount,
            'pnl_abs': pnl_abs,
            'pnl_pct': pnl_pct,
        }

    def get_transactions(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        types: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        newest_first: bool = False,
    ) -> List[Dict[str, Any]]:
        type_set = set(t.upper() for t in types) if types is not None else None
        txns = []
        for tx in self.transactions:
            ts = tx['ts']
            if since is not None and ts < since:
                continue
            if until is not None and ts > until:
                continue
            if type_set is not None and tx['type'] not in type_set:
                continue
            txns.append(copy.deepcopy(tx))
        txns.sort(key=lambda x: x['ts'], reverse=newest_first)
        if limit is not None and limit >= 0:
            txns = txns[:limit]
        return txns

    def get_holdings_at(self, at: Optional[datetime]) -> Dict[str, int]:
        snapshot = self._replay_until(at)
        return snapshot['holdings']

    def get_cash_balance_at(self, at: Optional[datetime]) -> Decimal:
        snapshot = self._replay_until(at)
        return snapshot['cash']

    def get_portfolio_value_at(self, at: Optional[datetime]) -> Decimal:
        snap = self._replay_until(at)
        total = snap['cash']
        for sym, qty in snap['holdings'].items():
            price = self._get_price(sym)
            total = (total + (price * Decimal(qty)).quantize(MONEY_PLACES, rounding=ROUNDING)).quantize(MONEY_PLACES)
        return total

    def get_profit_loss_at(self, at: Optional[datetime], basis: str = 'net_contributions') -> Dict[str, Optional[Decimal]]:
        pv = self.get_portfolio_value_at(at)
        snap = self._replay_until(at)
        if basis == 'net_contributions':
            basis_amount = snap['net_contributions']
        elif basis == 'initial_only':
            if snap['initial_deposit_ts'] is not None and (at is None or snap['initial_deposit_ts'] <= at):
                basis_amount = snap['initial_deposit']
            else:
                basis_amount = Decimal('0.00').quantize(MONEY_PLACES)
        else:
            raise AccountError('Invalid basis')
        pnl_abs = (pv - basis_amount).quantize(MONEY_PLACES)
        pnl_pct = (pnl_abs / basis_amount).quantize(Decimal('0.0001')) if basis_amount > Decimal('0') else None
        return {
            'portfolio_value': pv,
            'basis_amount': basis_amount,
            'pnl_abs': pnl_abs,
            'pnl_pct': pnl_pct,
        }

    def to_dict(self) -> Dict[str, Any]:
        def dec_str(d: Optional[Decimal]) -> Optional[str]:
            return None if d is None else format(d, 'f')
        data: Dict[str, Any] = {
            'account_id': self.account_id,
            'owner_name': self.owner_name,
            'created_at': self.created_at.isoformat(),
            'cash_balance': dec_str(self.cash_balance),
            'net_contributions': dec_str(self.net_contributions),
            'initial_deposit': dec_str(self.initial_deposit),
            'holdings': dict(self.holdings),
            'transactions': [],
        }
        for tx in self.transactions:
            data['transactions'].append({
                'id': tx['id'],
                'ts': tx['ts'].isoformat(),
                'type': tx['type'],
                'symbol': tx['symbol'],
                'quantity': tx['quantity'],
                'price': dec_str(tx['price']) if tx['price'] is not None else None,
                'cash_delta': dec_str(tx['cash_delta']),
                'cash_balance_after': dec_str(tx['cash_balance_after']),
                'note': tx['note'],
            })
        return data

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        price_provider: Optional[Callable[[str], Decimal]] = None,
        time_provider: Optional[Callable[[], datetime]] = None,
    ) -> 'Account':
        acct = cls(
            owner_name=data['owner_name'],
            account_id=data.get('account_id'),
            price_provider=price_provider,
            time_provider=time_provider,
        )
        acct.created_at = datetime.fromisoformat(data['created_at'])
        acct.cash_balance = to_decimal(data['cash_balance'], MONEY_PLACES)
        acct.net_contributions = to_decimal(data['net_contributions'], MONEY_PLACES)
        acct.initial_deposit = to_decimal(data.get('initial_deposit', '0.00'), MONEY_PLACES)
        acct.holdings = {normalize_symbol(k): int(v) for k, v in (data.get('holdings') or {}).items() if int(v) != 0}
        acct.transactions = []
        for tx in data.get('transactions', []):
            txn = {
                'id': tx['id'],
                'ts': datetime.fromisoformat(tx['ts']),
                'type': tx['type'],
                'symbol': tx['symbol'],
                'quantity': tx['quantity'],
                'price': to_decimal(tx['price'], PRICE_PLACES) if tx.get('price') is not None else None,
                'cash_delta': to_decimal(tx['cash_delta'], MONEY_PLACES),
                'cash_balance_after': to_decimal(tx['cash_balance_after'], MONEY_PLACES),
                'note': tx.get('note'),
            }
            acct.transactions.append(txn)
        for tx in acct.transactions:
            if tx['type'] == 'DEPOSIT':
                acct._initial_deposit_ts = tx['ts']
                break
        return acct

def _fmt_money(d: Decimal) -> str:
    return f"{d.quantize(MONEY_PLACES):.2f}"

def main() -> None:
    print('Trading Simulation Account CLI. Type "help" for commands.')
    account: Optional[Account] = None
    while True:
        try:
            line = input('> ').strip()
        except EOFError:
            break
        if not line:
            continue
        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f'Parse error: {e}')
            continue
        cmd = parts[0].lower()
        args = parts[1:]
        try:
            if cmd in ('quit', 'exit'):
                break
            elif cmd == 'help':
                print('Commands:')
                print('  create <owner_name>')
                print('  deposit <amount> [note...]')
                print('  withdraw <amount> [note...]')
                print('  buy <symbol> <quantity> [price] [note...]')
                print('  sell <symbol> <quantity> [price] [note...]')
                print('  holdings')
                print('  value')
                print('  pnl [net_contributions|initial_only]')
                print('  txns [limit] [types...]')
                print('  prices')
                print('  quit/exit')
            elif cmd == 'create':
                if not args:
                    print('Usage: create <owner_name>')
                    continue
                owner_name = ' '.join(args)
                account = Account(owner_name)
                print(f'Created account {account.account_id} for {account.owner_name}')
            elif cmd == 'deposit':
                if account is None:
                    print('Create an account first')
                    continue
                if not args:
                    print('Usage: deposit <amount> [note...]')
                    continue
                amount = args[0]
                note = ' '.join(args[1:]) if len(args) > 1 else None
                account.deposit(amount, note=note)
                print(f'Cash: {_fmt_money(account.get_cash_balance())}')
            elif cmd == 'withdraw':
                if account is None:
                    print('Create an account first')
                    continue
                if not args:
                    print('Usage: withdraw <amount> [note...]')
                    continue
                amount = args[0]
                note = ' '.join(args[1:]) if len(args) > 1 else None
                account.withdraw(amount, note=note)
                print(f'Cash: {_fmt_money(account.get_cash_balance())}')
            elif cmd == 'buy':
                if account is None:
                    print('Create an account first')
                    continue
                if len(args) < 2:
                    print('Usage: buy <symbol> <quantity> [price] [note...]')
                    continue
                symbol = args[0]
                quantity = int(args[1])
                price = None
                note = None
                if len(args) >= 3:
                    try:
                        price = Decimal(args[2])
                        note = ' '.join(args[3:]) if len(args) > 3 else None
                    except Exception:
                        price = None
                        note = ' '.join(args[2:]) if len(args) > 2 else None
                cost = account.buy(symbol, quantity, price=price, note=note)
                print(f'Bought {quantity} {symbol} for {cost:.2f}. Cash: {_fmt_money(account.get_cash_balance())}')
            elif cmd == 'sell':
                if account is None:
                    print('Create an account first')
                    continue
                if len(args) < 2:
                    print('Usage: sell <symbol> <quantity> [price] [note...]')
                    continue
                symbol = args[0]
                quantity = int(args[1])
                price = None
                note = None
                if len(args) >= 3:
                    try:
                        price = Decimal(args[2])
                        note = ' '.join(args[3:]) if len(args) > 3 else None
                    except Exception:
                        price = None
                        note = ' '.join(args[2:]) if len(args) > 2 else None
                proceeds = account.sell(symbol, quantity, price=price, note=note)
                print(f'Sold {quantity} {symbol} for {proceeds:.2f}. Cash: {_fmt_money(account.get_cash_balance())}')
            elif cmd == 'holdings':
                if account is None:
                    print('Create an account first')
                    continue
                print(account.get_holdings())
            elif cmd == 'value':
                if account is None:
                    print('Create an account first')
                    continue
                pv = account.get_portfolio_value()
                print(f'Portfolio value: {_fmt_money(pv)} (Cash: {_fmt_money(account.get_cash_balance())})')
            elif cmd == 'pnl':
                if account is None:
                    print('Create an account first')
                    continue
                basis = args[0] if args else 'net_contributions'
                res = account.get_profit_loss(basis=basis)
                pct = 'None' if res['pnl_pct'] is None else f"{res['pnl_pct']}"
                print({'portfolio_value': _fmt_money(res['portfolio_value']), 'basis_amount': _fmt_money(res['basis_amount']), 'pnl_abs': _fmt_money(res['pnl_abs']), 'pnl_pct': pct})
            elif cmd == 'txns':
                if account is None:
                    print('Create an account first')
                    continue
                limit = int(args[0]) if args and args[0].isdigit() else None
                types = None
                if limit is not None:
                    types = [t.upper() for t in args[1:]] if len(args) > 1 else None
                else:
                    types = [t.upper() for t in args] if args else None
                txns = account.get_transactions(types=types, newest_first=True, limit=limit)
                for tx in txns:
                    price = tx['price']
                    price_str = '' if price is None else f" @{price:.2f}"
                    sym = '' if tx['symbol'] is None else f" {tx['symbol']}"
                    qty = '' if tx['quantity'] is None else f" x{tx['quantity']}"
                    note = f" note='{tx['note']}'" if tx['note'] else ''
                    print(f"{tx['ts'].isoformat()} {tx['type']}{sym}{qty}{price_str} cash_delta={tx['cash_delta']:.2f} cash_after={tx['cash_balance_after']:.2f}{note}")
            elif cmd == 'prices':
                print({'AAPL': str(get_share_price('AAPL')), 'TSLA': str(get_share_price('TSLA')), 'GOOGL': str(get_share_price('GOOGL'))})
            else:
                print('Unknown command. Type help for commands.')
        except Exception as e:
            print(f'Error: {e}')

if __name__ == '__main__':
    main()