import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from accounts import (
    Account,
    AccountError,
    InvalidAmountError,
    InvalidQuantityError,
    InvalidSymbolError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    get_share_price,
    SUPPORTED_SYMBOLS,
)


def fmt_money(d: Decimal) -> str:
    return f"{d:.2f}"


def ensure_account(acct: Optional[Account]) -> Account:
    if acct is None:
        raise AccountError("Please create or import an account first.")
    return acct


def summary_tuple(acct: Account) -> Tuple[str, str, str, str, str, str, str]:
    pv = acct.get_portfolio_value()
    return (
        acct.owner_name,
        acct.account_id,
        acct.created_at.isoformat(),
        fmt_money(acct.get_cash_balance()),
        fmt_money(pv),
        fmt_money(acct.net_contributions),
        fmt_money(acct.initial_deposit),
    )


def success_html(msg: str) -> str:
    return f"<div style='color:#065f46;background:#ecfdf5;padding:10px;border-radius:8px;border:1px solid #34d399;'>{msg}</div>"


def error_html(msg: str) -> str:
    return f"<div style='color:#7f1d1d;background:#fef2f2;padding:10px;border-radius:8px;border:1px solid #f87171;'>{msg}</div>"


def create_account(owner: str, state: Optional[Account]) -> Tuple[Optional[Account], str, str, str, str, str, str, str, str, str]:
    try:
        owner_clean = (owner or "").strip()
        if not owner_clean:
            raise AccountError("Owner name cannot be empty.")
        acct = Account(owner_clean)
        o, i, c, cash, pv, netc, init = summary_tuple(acct)
        return (
            acct,
            o,
            i,
            c,
            cash,
            pv,
            netc,
            init,
            success_html(f"Account created for {acct.owner_name}."),
            "",
        )
    except Exception as e:
        return (
            state,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            error_html(f"Error: {e}"),
            "",
        )


def reset_account(state: Optional[Account]) -> Tuple[Optional[Account], str, str, str, str, str, str, str, str, str]:
    return None, "", "", "", "", "", "", "", success_html("Account reset. Create or import a new account."), ""


def export_account(state: Optional[Account]) -> Tuple[str, str]:
    try:
        acct = ensure_account(state)
        data = acct.to_dict()
        return json.dumps(data, indent=2), success_html("Exported account JSON.")
    except Exception as e:
        return "", error_html(f"Error: {e}")


def import_account(json_text: str, state: Optional[Account]) -> Tuple[Optional[Account], str, str, str, str, str, str, str, str, str]:
    try:
        data = json.loads(json_text)
        acct = Account.from_dict(data)
        o, i, c, cash, pv, netc, init = summary_tuple(acct)
        return (
            acct,
            o,
            i,
            c,
            cash,
            pv,
            netc,
            init,
            success_html("Account imported successfully."),
            json.dumps(acct.to_dict(), indent=2),
        )
    except Exception as e:
        return (
            state,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            error_html(f"Error importing account: {e}"),
            "",
        )


def refresh_summary(state: Optional[Account]) -> Tuple[str, str, str, str, str, str, str, str]:
    try:
        acct = ensure_account(state)
        o, i, c, cash, pv, netc, init = summary_tuple(acct)
        return o, i, c, cash, pv, netc, init, success_html("Summary refreshed.")
    except Exception as e:
        return "", "", "", "", "", "", "", error_html(f"Error: {e}")


def do_deposit(amount: Optional[float], note: str, state: Optional[Account]) -> Tuple[str, str, str, str, str, str, str, str]:
    try:
        acct = ensure_account(state)
        if amount is None:
            raise InvalidAmountError("Enter a deposit amount.")
        acct.deposit(amount, note=note.strip() or None)
        o, i, c, cash, pv, netc, init = summary_tuple(acct)
        return o, i, c, cash, pv, netc, init, success_html(f"Deposited {fmt_money(Decimal(str(amount)))}.")
    except Exception as e:
        return "", "", "", "", "", "", "", error_html(f"Error: {e}")


def do_withdraw(amount: Optional[float], note: str, state: Optional[Account]) -> Tuple[str, str, str, str, str, str, str, str]:
    try:
        acct = ensure_account(state)
        if amount is None:
            raise InvalidAmountError("Enter a withdrawal amount.")
        acct.withdraw(amount, note=note.strip() or None)
        o, i, c, cash, pv, netc, init = summary_tuple(acct)
        return o, i, c, cash, pv, netc, init, success_html(f"Withdrew {fmt_money(Decimal(str(amount)))}.")
    except Exception as e:
        return "", "", "", "", "", "", "", error_html(f"Error: {e}")


def do_buy(symbol: str, quantity: Optional[float], price: Optional[float], note: str, state: Optional[Account]) -> Tuple[str, str, str, str, str, str, str, str]:
    try:
        acct = ensure_account(state)
        sym = (symbol or "").strip().upper()
        if not sym:
            raise InvalidSymbolError("Select a symbol.")
        if quantity is None:
            raise InvalidQuantityError("Enter quantity.")
        qty_int = int(quantity)
        trade_price = None if price in (None, "") else float(price)
        cost = acct.buy(sym, qty_int, price=trade_price, note=(note.strip() or None))
        o, i, c, cash, pv, netc, init = summary_tuple(acct)
        return o, i, c, cash, pv, netc, init, success_html(f"Bought {qty_int} {sym} for {fmt_money(cost)}.")
    except Exception as e:
        return "", "", "", "", "", "", "", error_html(f"Error: {e}")


def do_sell(symbol: str, quantity: Optional[float], price: Optional[float], note: str, state: Optional[Account]) -> Tuple[str, str, str, str, str, str, str, str]:
    try:
        acct = ensure_account(state)
        sym = (symbol or "").strip().upper()
        if not sym:
            raise InvalidSymbolError("Select a symbol.")
        if quantity is None:
            raise InvalidQuantityError("Enter quantity.")
        qty_int = int(quantity)
        trade_price = None if price in (None, "") else float(price)
        proceeds = acct.sell(sym, qty_int, price=trade_price, note=(note.strip() or None))
        o, i, c, cash, pv, netc, init = summary_tuple(acct)
        return o, i, c, cash, pv, netc, init, success_html(f"Sold {qty_int} {sym} for {fmt_money(proceeds)}.")
    except Exception as e:
        return "", "", "", "", "", "", "", error_html(f"Error: {e}")


def build_valuation_table(state: Optional[Account]) -> Tuple[List[List[Any]], str, str]:
    try:
        acct = ensure_account(state)
        val = acct.get_holdings_valuation()
        rows: List[List[Any]] = []
        for sym, data in val.items():
            rows.append([
                sym,
                int(data["quantity"]),
                fmt_money(data["price"]),
                fmt_money(data["market_value"]),
            ])
        rows.sort(key=lambda r: r[0])
        cash = fmt_money(acct.get_cash_balance())
        pv = fmt_money(acct.get_portfolio_value())
        return rows, cash, pv
    except Exception as e:
        return [], "", ""


def pnl_compute(basis: str, state: Optional[Account]) -> Tuple[str, str, str, str, str]:
    try:
        acct = ensure_account(state)
        res = acct.get_profit_loss(basis=basis)
        pv = fmt_money(res["portfolio_value"])
        basis_amt = fmt_money(res["basis_amount"])
        pnl_abs = fmt_money(res["pnl_abs"])
        pnl_pct = "N/A" if res["pnl_pct"] is None else f"{res['pnl_pct']}"
        return pv, basis_amt, pnl_abs, pnl_pct, success_html("PnL computed.")
    except Exception as e:
        return "", "", "", "", error_html(f"Error: {e}")


def list_transactions(
    state: Optional[Account],
    limit: Optional[float],
    types: List[str],
    since_iso: str,
    until_iso: str,
    newest_first: bool,
) -> Tuple[List[List[Any]], str]:
    try:
        acct = ensure_account(state)
        limit_int = None
        if limit is not None:
            li = int(limit)
            if li >= 0:
                limit_int = li
        type_list = [t.upper() for t in types] if types else None
        since_dt = datetime.fromisoformat(since_iso.strip()) if since_iso and since_iso.strip() else None
        until_dt = datetime.fromisoformat(until_iso.strip()) if until_iso and until_iso.strip() else None
        items = acct.get_transactions(since=since_dt, until=until_dt, types=type_list, limit=limit_int, newest_first=newest_first)
        rows: List[List[Any]] = []
        for tx in items:
            rows.append([
                tx["ts"].isoformat(),
                tx["type"],
                "" if tx["symbol"] is None else tx["symbol"],
                "" if tx["quantity"] is None else int(tx["quantity"]),
                "" if tx["price"] is None else fmt_money(tx["price"]),
                fmt_money(tx["cash_delta"]),
                fmt_money(tx["cash_balance_after"]),
                "" if tx.get("note") in (None, "") else tx["note"],
            ])
        return rows, success_html(f"Loaded {len(rows)} transaction(s).")
    except Exception as e:
        return [], error_html(f"Error: {e}")


def current_prices() -> Tuple[str, str, str]:
    try:
        aapl = fmt_money(get_share_price("AAPL"))
        tsla = fmt_money(get_share_price("TSLA"))
        googl = fmt_money(get_share_price("GOOGL"))
        return aapl, tsla, googl
    except Exception:
        return "", "", ""


def historical_snapshot(state: Optional[Account], at_iso: str, basis: str) -> Tuple[str, str, str, str, str]:
    try:
        acct = ensure_account(state)
        at_dt = datetime.fromisoformat(at_iso.strip()) if at_iso and at_iso.strip() else None
        cash = fmt_money(acct.get_cash_balance_at(at_dt))
        pv = fmt_money(acct.get_portfolio_value_at(at_dt))
        pnl = acct.get_profit_loss_at(at_dt, basis=basis)
        pnl_abs = fmt_money(pnl["pnl_abs"])
        pnl_pct = "N/A" if pnl["pnl_pct"] is None else f"{pnl['pnl_pct']}"
        return cash, pv, pnl_abs, pnl_pct, success_html("Historical snapshot computed.")
    except Exception as e:
        return "", "", "", "", error_html(f"Error: {e}")


theme = gr.themes.Soft(primary_hue="sky", secondary_hue="emerald", neutral_hue="slate")


with gr.Blocks(title="Accounts UI", theme=theme, css="footer {visibility: hidden}") as app:
    gr.Markdown("<h1 style='text-align:center;'>WELCOME Ammar</h1>")

    state = gr.State(None)

    with gr.Tab("Account"):
        with gr.Row():
            with gr.Column(scale=1, min_width=300):
                owner_in = gr.Textbox(label="Owner Name", value="Ammar", placeholder="Enter owner name")
                create_btn = gr.Button("Create Account", variant="primary")
                reset_btn = gr.Button("Reset Account", variant="secondary")
                gr.Markdown("Import Account")
                import_json_in = gr.Textbox(label="Account JSON (paste to import)", lines=8, placeholder="{ ... }")
                import_btn = gr.Button("Import JSON")
            with gr.Column(scale=2):
                gr.Markdown("Summary")
                owner_out = gr.Textbox(label="Owner", interactive=False)
                id_out = gr.Textbox(label="Account ID", interactive=False)
                created_out = gr.Textbox(label="Created At", interactive=False)
                cash_out = gr.Textbox(label="Cash Balance", interactive=False)
                pv_out = gr.Textbox(label="Portfolio Value", interactive=False)
                netc_out = gr.Textbox(label="Net Contributions", interactive=False)
                init_dep_out = gr.Textbox(label="Initial Deposit", interactive=False)
                refresh_btn = gr.Button("Refresh Summary")
                status_html = gr.HTML()
                gr.Markdown("Export Account")
                export_btn = gr.Button("Export JSON")
                export_json_out = gr.Textbox(label="Account JSON (copy to save)", lines=8, interactive=False)

        create_btn.click(
            create_account,
            inputs=[owner_in, state],
            outputs=[state, owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, status_html, export_json_out],
        )
        reset_btn.click(
            reset_account,
            inputs=[state],
            outputs=[state, owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, status_html, export_json_out],
        )
        refresh_btn.click(
            refresh_summary,
            inputs=[state],
            outputs=[owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, status_html],
        )
        export_btn.click(
            export_account,
            inputs=[state],
            outputs=[export_json_out, status_html],
        )
        import_btn.click(
            import_account,
            inputs=[import_json_in, state],
            outputs=[state, owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, status_html, export_json_out],
        )

    with gr.Tab("Actions"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("Deposit")
                dep_amount = gr.Number(label="Amount", value=100.00)
                dep_note = gr.Textbox(label="Note", placeholder="Optional note")
                dep_btn = gr.Button("Deposit", variant="primary")
            with gr.Column():
                gr.Markdown("Withdraw")
                wd_amount = gr.Number(label="Amount", value=50.00)
                wd_note = gr.Textbox(label="Note", placeholder="Optional note")
                wd_btn = gr.Button("Withdraw", variant="secondary")
        with gr.Row():
            with gr.Column():
                gr.Markdown("Buy")
                buy_symbol = gr.Dropdown(choices=sorted(SUPPORTED_SYMBOLS), label="Symbol")
                buy_qty = gr.Number(label="Quantity", value=1, precision=0)
                buy_price = gr.Number(label="Price (leave blank for market)", value=None)
                buy_note = gr.Textbox(label="Note", placeholder="Optional note")
                buy_btn = gr.Button("Buy", variant="primary")
            with gr.Column():
                gr.Markdown("Sell")
                sell_symbol = gr.Dropdown(choices=sorted(SUPPORTED_SYMBOLS), label="Symbol")
                sell_qty = gr.Number(label="Quantity", value=1, precision=0)
                sell_price = gr.Number(label="Price (leave blank for market)", value=None)
                sell_note = gr.Textbox(label="Note", placeholder="Optional note")
                sell_btn = gr.Button("Sell", variant="secondary")
        action_status = gr.HTML()

        dep_btn.click(
            do_deposit,
            inputs=[dep_amount, dep_note, state],
            outputs=[owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, action_status],
        )
        wd_btn.click(
            do_withdraw,
            inputs=[wd_amount, wd_note, state],
            outputs=[owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, action_status],
        )
        buy_btn.click(
            do_buy,
            inputs=[buy_symbol, buy_qty, buy_price, buy_note, state],
            outputs=[owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, action_status],
        )
        sell_btn.click(
            do_sell,
            inputs=[sell_symbol, sell_qty, sell_price, sell_note, state],
            outputs=[owner_out, id_out, created_out, cash_out, pv_out, netc_out, init_dep_out, action_status],
        )

    with gr.Tab("Portfolio"):
        with gr.Row():
            with gr.Column(scale=3):
                holdings_table = gr.Dataframe(
                    headers=["Symbol", "Quantity", "Price", "Market Value"],
                    datatype=["str", "number", "str", "str"],
                    row_count=(0, "dynamic"),
                    col_count=(4, "fixed"),
                    label="Holdings Valuation",
                    interactive=False,
                )
            with gr.Column(scale=1):
                cash_label = gr.Textbox(label="Cash Balance", interactive=False)
                pv_label = gr.Textbox(label="Total Portfolio Value", interactive=False)
                prices_box = gr.Group()
                with prices_box:
                    gr.Markdown("Current Prices")
                    price_aapl = gr.Textbox(label="AAPL", interactive=False)
                    price_tsla = gr.Textbox(label="TSLA", interactive=False)
                    price_googl = gr.Textbox(label="GOOGL", interactive=False)
                refresh_port_btn = gr.Button("Refresh Portfolio", variant="primary")

        refresh_port_btn.click(
            build_valuation_table,
            inputs=[state],
            outputs=[holdings_table, cash_label, pv_label],
        )
        refresh_port_btn.click(
            current_prices,
            inputs=None,
            outputs=[price_aapl, price_tsla, price_googl],
        )

    with gr.Tab("PnL"):
        basis_radio = gr.Radio(choices=["net_contributions", "initial_only"], value="net_contributions", label="Basis")
        pnl_pv = gr.Textbox(label="Portfolio Value", interactive=False)
        pnl_basis = gr.Textbox(label="Basis Amount", interactive=False)
        pnl_abs = gr.Textbox(label="PnL (Absolute)", interactive=False)
        pnl_pct = gr.Textbox(label="PnL (Percent)", interactive=False)
        pnl_status = gr.HTML()
        pnl_btn = gr.Button("Compute PnL", variant="primary")

        pnl_btn.click(
            pnl_compute,
            inputs=[basis_radio, state],
            outputs=[pnl_pv, pnl_basis, pnl_abs, pnl_pct, pnl_status],
        )

    with gr.Tab("Transactions"):
        with gr.Row():
            types_ck = gr.CheckboxGroup(choices=["DEPOSIT", "WITHDRAW", "BUY", "SELL"], label="Types")
            limit_in = gr.Number(label="Limit (leave empty for all)", value=50, precision=0)
            newest_first_ck = gr.Checkbox(label="Newest first", value=True)
        with gr.Row():
            since_in = gr.Textbox(label="Since (ISO datetime, optional)", placeholder="YYYY-MM-DDTHH:MM:SS+00:00")
            until_in = gr.Textbox(label="Until (ISO datetime, optional)", placeholder="YYYY-MM-DDTHH:MM:SS+00:00")
        tx_table = gr.Dataframe(
            headers=["Timestamp", "Type", "Symbol", "Quantity", "Price", "Cash Delta", "Cash After", "Note"],
            datatype=["str", "str", "str", "number", "str", "str", "str", "str"],
            row_count=(0, "dynamic"),
            col_count=(8, "fixed"),
            label="Transactions",
            interactive=False,
        )
        tx_status = gr.HTML()
        tx_btn = gr.Button("Load Transactions", variant="primary")

        tx_btn.click(
            list_transactions,
            inputs=[state, limit_in, types_ck, since_in, until_in, newest_first_ck],
            outputs=[tx_table, tx_status],
        )

    with gr.Tab("History"):
        at_in = gr.Textbox(label="At (ISO datetime, optional for current)", placeholder="YYYY-MM-DDTHH:MM:SS+00:00")
        hist_basis = gr.Radio(choices=["net_contributions", "initial_only"], value="net_contributions", label="Basis")
        cash_at = gr.Textbox(label="Cash Balance at time", interactive=False)
        pv_at = gr.Textbox(label="Portfolio Value at time", interactive=False)
        pnl_abs_at = gr.Textbox(label="PnL (Absolute) at time", interactive=False)
        pnl_pct_at = gr.Textbox(label="PnL (Percent) at time", interactive=False)
        hist_status = gr.HTML()
        hist_btn = gr.Button("Get Snapshot", variant="primary")

        hist_btn.click(
            historical_snapshot,
            inputs=[state, at_in, hist_basis],
            outputs=[cash_at, pv_at, pnl_abs_at, pnl_pct_at, hist_status],
        )


if __name__ == "__main__":
    app.launch()