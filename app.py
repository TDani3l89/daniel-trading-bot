import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(
    page_title="Daniel Trading Bot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Daniel Trading Bot")
st.caption(
    "MVP de paper trading — backtest multi-asset, fără bani reali "
    "și fără conectare la exchange."
)

# -----------------------------
# Setări
# -----------------------------
with st.sidebar:
    st.header("⚙️ Setări")

    assets = st.multiselect(
        "Monede",
        ["BTC-USD", "ETH-USD", "SOL-USD"],
        default=["BTC-USD", "ETH-USD", "SOL-USD"]
    )

    period = st.selectbox(
        "Perioadă",
        ["6mo", "1y", "2y", "5y", "10y"],
        index=1
    )

    starting_balance = st.number_input(
        "Capital inițial (£)",
        min_value=10.0,
        value=100.0,
        step=10.0
    )

    fast = st.number_input(
        "Media rapidă",
        min_value=2,
        max_value=200,
        value=20,
        step=1
    )

    slow = st.number_input(
        "Media lentă",
        min_value=3,
        max_value=400,
        value=50,
        step=1
    )

    fee = st.number_input(
        "Comision per tranzacție (%)",
        min_value=0.0,
        max_value=5.0,
        value=0.10,
        step=0.01
    )

    slippage = st.number_input(
        "Slippage per tranzacție (%)",
        min_value=0.0,
        max_value=5.0,
        value=0.05,
        step=0.01
    )

    run = st.button(
        "▶️ Rulează backtest",
        type="primary",
        use_container_width=True
    )

# -----------------------------
# Funcții
# -----------------------------
def download_data(ticker, period):
    df = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Close"]].copy()
    df.columns = ["Close"]
    df = df.dropna()

    return df


def run_single_asset_backtest(
    prices,
    initial_capital,
    fast_window,
    slow_window,
    fee_pct,
    slippage_pct
):
    df = prices.copy()

    df["Fast MA"] = df["Close"].rolling(fast_window).mean()
    df["Slow MA"] = df["Close"].rolling(slow_window).mean()

    df["Signal"] = (
        df["Fast MA"] > df["Slow MA"]
    ).astype(int)

    df["Position"] = df["Signal"].shift(1).fillna(0)

    df["Market Return"] = df["Close"].pct_change().fillna(0)

    df["Strategy Return"] = (
        df["Market Return"] * df["Position"]
    )

    trades = (
        df["Position"].diff().abs().fillna(0)
    )

    total_cost_pct = (fee_pct + slippage_pct) / 100

    df["Costs"] = trades * total_cost_pct

    df["Net Return"] = (
        df["Strategy Return"] - df["Costs"]
    )

    df["Equity"] = (
        1 + df["Net Return"]
    ).cumprod() * initial_capital

    df["Buy Hold Equity"] = (
        df["Close"] / df["Close"].iloc[0]
    ) * initial_capital

    closed_trades = int(
        ((df["Position"].diff() == -1).sum())
    )

    total_fees = (
        df["Costs"].sum() * initial_capital
    )

    return df, closed_trades, total_fees


def calculate_drawdown(equity):
    peak = equity.cummax()
    drawdown = (equity / peak) - 1
    return drawdown.min() * 100


# -----------------------------
# Backtest
# -----------------------------
if run:
    if not assets:
        st.error("Selectează cel puțin o monedă.")
        st.stop()

    if fast >= slow:
        st.error("Media rapidă trebuie să fie mai mică decât media lentă.")
        st.stop()

    with st.spinner("Se descarcă datele și se rulează backtestul..."):
        all_data = {}
        results = []

        allocation = 1 / len(assets)

        for ticker in assets:
            data = download_data(ticker, period)

            if data.empty:
                st.warning(f"Nu s-au găsit date pentru {ticker}.")
                continue

            capital_for_asset = starting_balance * allocation

            result_df, trades, fees = run_single_asset_backtest(
                data,
                capital_for_asset,
                fast,
                slow,
                fee,
                slippage
            )

            all_data[ticker] = result_df

            final_equity = result_df["Equity"].iloc[-1]
            final_buy_hold = result_df["Buy Hold Equity"].iloc[-1]

            results.append({
                "Monedă": ticker,
                "Capital alocat": capital_for_asset,
                "Sold final": final_equity,
                "Profit/Pierdere": final_equity - capital_for_asset,
                "Randament %": (
                    final_equity / capital_for_asset - 1
                ) * 100,
                "Buy & Hold %": (
                    final_buy_hold / capital_for_asset - 1
                ) * 100,
                "Drawdown maxim %": calculate_drawdown(
                    result_df["Equity"]
                ),
                "Tranzacții închise": trades,
                "Comisioane + slippage": fees
            })

    if not results:
        st.error("Nu s-au putut descărca datele.")
        st.stop()

    results_df = pd.DataFrame(results)

    # -----------------------------
    # Portofoliu comun
    # -----------------------------
    portfolio = pd.DataFrame(index=all_data[assets[0]].index)

    portfolio["Equity"] = 0.0
    portfolio["Buy Hold Equity"] = 0.0

    for ticker in all_data:
        asset_df = all_data[ticker]

        portfolio["Equity"] += asset_df["Equity"].reindex(
            portfolio.index
        ).ffill().fillna(0)

        portfolio["Buy Hold Equity"] += asset_df[
            "Buy Hold Equity"
        ].reindex(portfolio.index).ffill().fillna(0)

    final_balance = portfolio["Equity"].iloc[-1]
    final_buy_hold = portfolio["Buy Hold Equity"].iloc[-1]

    total_profit = final_balance - starting_balance

    total_return = (
        final_balance / starting_balance - 1
    ) * 100

    buy_hold_return = (
        final_buy_hold / starting_balance - 1
    ) * 100

    max_drawdown = calculate_drawdown(
        portfolio["Equity"]
    )

    total_trades = int(
        results_df["Tranzacții închise"].sum()
    )

    total_fees = results_df[
        "Comisioane + slippage"
    ].sum()

    # -----------------------------
    # Indicatori principali
    # -----------------------------
    st.subheader("📊 Rezultate portofoliu")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Sold final",
        f"£{final_balance:,.2f}"
    )

    col2.metric(
        "Profit/Pierdere",
        f"£{total_profit:,.2f}",
        f"{total_return:.2f}%"
    )

    col3.metric(
        "Drawdown maxim",
        f"{max_drawdown:.2f}%"
    )

    col4.metric(
        "Tranzacții închise",
        total_trades
    )

    st.metric(
        "Comisioane + slippage",
        f"£{total_fees:,.2f}"
    )

    # -----------------------------
    # Grafic
    # -----------------------------
    st.subheader("📈 Evoluția portofoliului")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=portfolio.index,
            y=portfolio["Equity"],
            mode="lines",
            name="Strategie"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=portfolio.index,
            y=portfolio["Buy Hold Equity"],
            mode="lines",
            name="Buy & Hold"
        )
    )

    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Sold (£)",
        hovermode="x unified",
        height=500
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # -----------------------------
    # Rezultate pe monede
    # -----------------------------
    st.subheader("🪙 Rezultate pe monede")

    display_df = results_df.copy()

    for column in [
        "Capital alocat",
        "Sold final",
        "Profit/Pierdere",
        "Comisioane + slippage"
    ]:
        display_df[column] = display_df[column].map(
            lambda x: f"£{x:,.2f}"
        )

    for column in [
        "Randament %",
        "Buy & Hold %",
        "Drawdown maxim %"
    ]:
        display_df[column] = display_df[column].map(
            lambda x: f"{x:.2f}%"
        )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------
    # Date brute și export
    # -----------------------------
    st.subheader("📥 Export rezultate")

    csv = results_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Descarcă rezultatele CSV",
        data=csv,
        file_name="daniel_trading_multi_asset_results.csv",
        mime="text/csv"
    )

else:
    st.info(
        "Alege monedele și parametrii din meniul din stânga, "
        "apoi apasă «Rulează backtest»."
    )
