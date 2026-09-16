
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="Daniel Trading Bot", page_icon="🤖", layout="wide")
st.title("🤖 Daniel Trading Bot")
st.caption("MVP de paper trading — fără bani reali și fără conectare la exchange.")

with st.sidebar:
    st.header("Setări")
    asset = st.selectbox("Monedă", ["BTC-USD", "ETH-USD", "SOL-USD"])
    period = st.selectbox("Perioadă", ["6mo", "1y", "2y", "5y"], index=2)
    starting_balance = st.number_input("Capital virtual (£)", min_value=10.0, value=100.0, step=10.0)
    fast = st.number_input("Media rapidă", min_value=2, max_value=100, value=20)
    slow = st.number_input("Media lentă", min_value=fast+1, max_value=300, value=50)
    fee = st.number_input("Comision per ordin (%)", min_value=0.0, max_value=2.0, value=0.10, step=0.01)/100
    slippage = st.number_input("Slippage per ordin (%)", min_value=0.0, max_value=2.0, value=0.05, step=0.01)/100
    invest_pct = st.slider("Capital folosit la intrare (%)", 10, 100, 95)/100
    run = st.button("▶ Rulează backtest", type="primary")

def download_data(ticker, period):
    df = yf.download(ticker, period=period, interval="1d", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Close"]].dropna()

def backtest(df):
    d=df.copy()
    d["fast"]=d["Close"].rolling(int(fast)).mean()
    d["slow"]=d["Close"].rolling(int(slow)).mean()
    d["signal"]=(d["fast"]>d["slow"]).astype(int)
    d["change"]=d["signal"].diff()

    cash=float(starting_balance); units=0.0; trades=[]; equity=[]
    for dt,row in d.iterrows():
        price=float(row["Close"])
        if pd.isna(row["slow"]):
            equity.append(cash+units*price); continue
        if row["change"]==1 and units==0 and cash>0:
            gross=cash*invest_pct
            buy_price=price*(1+slippage)
            fee_paid=gross*fee
            units=max((gross-fee_paid)/buy_price,0)
            cash-=gross
            trades.append([dt,"BUY",buy_price,gross,fee_paid])
        elif row["change"]==-1 and units>0:
            sell_price=price*(1-slippage)
            gross=units*sell_price
            fee_paid=gross*fee
            cash += gross-fee_paid
            trades.append([dt,"SELL",sell_price,gross,fee_paid])
            units=0
        equity.append(cash+units*price)

    last=float(d["Close"].iloc[-1])
    final=cash+units*last*(1-fee-slippage)
    eq=pd.Series(equity,index=d.index)
    eq.iloc[-1]=final
    peak=eq.cummax()
    dd=(eq/peak-1)*100
    sells=[x for x in trades if x[1]=="SELL"]
    buys=[x for x in trades if x[1]=="BUY"]
    wins=0
    for b,s in zip(buys,sells):
        if s[3]-s[4] > b[3]:
            wins+=1
    closed=len(sells)
    total_fees=sum(x[4] for x in trades)
    return d,eq,trades,final,float((final/starting_balance-1)*100),float(dd.min()),closed,(wins/closed*100 if closed else 0),total_fees

if run or "result" not in st.session_state:
    with st.spinner("Descarc date și rulez simularea..."):
        try:
            data=download_data(asset,period)
            if len(data)<int(slow)+5:
                st.error("Nu sunt suficiente date pentru această perioadă.")
            else:
                result=backtest(data)
                st.session_state.result=result
                st.session_state.asset=asset
        except Exception as e:
            st.error(f"Eroare la date: {e}")

if "result" in st.session_state:
    d,eq,trades,final,ret,dd,closed,winrate,total_fees=st.session_state.result
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Sold final", f"£{final:,.2f}")
    c2.metric("Profit / pierdere", f"£{final-starting_balance:,.2f}", f"{ret:.2f}%")
    c3.metric("Drawdown maxim", f"{dd:.2f}%")
    c4.metric("Tranzacții închise", str(closed))
    c5.metric("Comisioane", f"£{total_fees:.2f}")

    fig=go.Figure()
    fig.add_trace(go.Scatter(x=eq.index,y=eq.values,name="Equity"))
    fig.update_layout(title="Evoluția capitalului virtual", xaxis_title="Data", yaxis_title="£")
    st.plotly_chart(fig,use_container_width=True)

    st.subheader("Semnale și tranzacții")
    log=pd.DataFrame(trades,columns=["Data","Tip","Preț","Valoare brută","Comision"])
    if len(log):
        st.dataframe(log, use_container_width=True)
    else:
        st.info("Strategia nu a găsit tranzacții în perioada aleasă.")

    st.warning("Acesta este un backtest istoric. Nu garantează profit viitor și nu execută tranzacții reale.")
st.divider()

st.subheader("🔒 Daniel Trading Bot Premium")
st.write("Accesează funcțiile Premium printr-un abonament lunar.")

st.link_button(
    "💳 Abonează-te pentru £9.99/lună",
    "https://buy.stripe.com/00waEZfwP2MVcof0eaeIw00"
)
