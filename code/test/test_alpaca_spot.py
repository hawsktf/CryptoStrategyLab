# test_alpaca_spot.py
from interfaces.alpaca_spot import AlpacaSpot
import time

# Initialize Alpaca client
alpaca = AlpacaSpot()

# Choose a crypto symbol listed on Alpaca (e.g. 'BTC/USD', 'ETH/USD')
symbol = "BTC/USD"
timeframe = "1h"

# Fetch ticker
print("\n=== Ticker ===")
ticker = alpaca.fetch_ticker(symbol)
print(ticker)

# Fetch balance
print("\n=== Balance ===")
balance = alpaca.fetch_balance()
print(balance)

# Fetch recent OHLCV data
print("\n=== OHLCV ===")
ohlcv = alpaca.fetch_recent_ohlcv(symbol, timeframe, limit=20)
print(ohlcv.tail())

# Cancel any open orders
print("\n=== Canceling Open Orders ===")
alpaca.cancel_all_orders(symbol)
print("All open orders cancelled.")

# Place a test limit order (use very low amount to avoid issues)
print("\n=== Place Limit Order ===")
limit_price = round(ticker["price"] * 0.9, 2)  # set well below current price to avoid fill
try:
    order = alpaca.place_limit_order(symbol, "buy", amount=0.0001, price=limit_price)
    print(f"Limit order placed: {order}")
except Exception as e:
    print(f"Failed to place limit order: {e}")

# Pause to let order appear
time.sleep(2)

# Fetch open orders
print("\n=== Open Orders ===")
orders = alpaca.fetch_open_orders(symbol)
for o in orders:
    print(f"Order: {o.symbol} | Qty: {o.qty} | Type: {o.order_type} | Status: {o.status}")

# Cancel again to clean up
print("\n=== Cleanup ===")
alpaca.cancel_all_orders(symbol)
print("Cleanup done.")