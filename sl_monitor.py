import yfinance as yf
import json
import smtplib
import subprocess
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "sl_portfolio.json")
_raw_email = os.environ.get("GMAIL_USER", "chybajirka917@gmail.com")
EMAIL      = ''.join(c for c in _raw_email if ord(c) < 128).strip()
_raw_pw    = os.environ.get("GMAIL_PASS", "qwru mxtp moqw nnhh")
EMAIL_PW   = ''.join(c for c in _raw_pw if ord(c) < 128).strip()
ALERT_PCT = 0.025


def load_portfolio():
    with open(PORTFOLIO_FILE) as f:
        return json.load(f)

def save_portfolio(p):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=2)

def get_price_and_ma(ticker, ma_type):
    df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
    close = df["Close"].squeeze()
    price = float(close.iloc[-1])
    ma = float(close.ewm(span=21, adjust=False).mean().iloc[-1]) if ma_type == "EMA21" \
         else float(close.rolling(10).mean().iloc[-1])
    return price, ma

def send_email(subject, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL
    msg["To"]      = EMAIL
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL, EMAIL_PW)
        s.send_message(msg)

def run():
    portfolio = load_portfolio()
    if not portfolio:
        return

    date     = datetime.now().strftime("%d.%m.%Y %H:%M")
    hit      = []
    alerts   = []
    ok_rows  = []

    for ticker, pos in list(portfolio.items()):
        try:
            price, ma = get_price_and_ma(ticker, pos["ma"])
            sl        = pos["sl"]
            dist_pct  = (price - sl) / price * 100

            if price <= sl:
                hit.append((ticker, price, sl, pos["shares"]))
                del portfolio[ticker]
            elif dist_pct < ALERT_PCT * 100:
                alerts.append((ticker, price, sl, dist_pct, pos["ma"], ma))
            else:
                ok_rows.append((ticker, price, sl, dist_pct))
        except Exception as e:
            print(f"  {ticker}: chyba — {e}")

    save_portfolio(portfolio)

    for ticker, price, sl, shares in hit:
        html = f"""<html><body style='font-family:Arial,sans-serif'>
<h2 style='color:#c0392b'>🚨 SL HIT — {ticker}</h2>
<p>Cena: <b>${price:.2f}</b> | Stop: <b>${sl:.2f}</b> | Počet: {shares}<br>
Čas: {date}</p>
<p style='color:red'><b>Ticker odstraněn z monitoru.</b></p>
</body></html>"""
        send_email(f"🚨 SL HIT {ticker} ${price:.2f}", html)
        print(f"  🚨 {ticker} SL HIT — email odeslán, ticker smazán")

    if alerts:
        rows = "".join(
            f"<tr style='background:#e67e22;color:white'><td><b>{t}</b></td><td>${p:.2f}</td>"
            f"<td>${s:.2f}</td><td>{d:.1f}%</td></tr>"
            for t, p, s, d, *_ in alerts
        )
        rows += "".join(
            f"<tr><td>{t}</td><td>${p:.2f}</td><td>${s:.2f}</td><td>{d:.1f}%</td></tr>"
            for t, p, s, d in ok_rows
        )
        html = f"""<html><body style='font-family:Arial,sans-serif;max-width:600px;margin:auto'>
<h2>⚠️ Portfolio SL Alert — {date}</h2>
<table border='1' cellpadding='8' cellspacing='0' style='border-collapse:collapse;width:100%'>
<tr style='background:#1a1a2e;color:white'><th>Ticker</th><th>Cena</th><th>Stop</th><th>Vzdálenost</th></tr>
{rows}</table></body></html>"""
        send_email(f"⚠️ {len(alerts)} ticker(ů) blízko SL — {date}", html)

    if not portfolio:
        send_email("✅ Všechny SL hity — monitor ukončen",
                   f"<p>Všechny pozice uzavřeny. {date}</p>")
        print("  ✅ Portfolio prázdné.")

    print(f"  Hotovo — {len(portfolio)} aktivních, {len(hit)} SL hit")

if __name__ == "__main__":
    print(f"\nSL MONITOR — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    run()
