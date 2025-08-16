# alpaca_spot.py
# AlpacaSpot - wrapper to match BitgetFutures interface, for spot trading using alpaca-py SDK

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestTradeRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime, timedelta
import pandas as pd
import pytz
import time
import sys
sys.path.append('../config')
import config

class AlpacaSpot:
    def __init__(self):
        # Initialize trading client (paper=True uses the paper API endpoint)
        self.trading_client = TradingClient(
            config.ALPACA_API_KEY,
            config.ALPACA_SECRET_KEY,
            paper=config.USE_PAPER_TRADING
        )

        # Historical data client for crypto
        self.crypto_data_client = CryptoHistoricalDataClient(
            config.ALPACA_API_KEY,
            config.ALPACA_SECRET_KEY
        )

        # Cache account object
        self.account = self.trading_client.get_account()

    def fetch_ticker(self, symbol):
        # Fetch latest trade price
        request = CryptoLatestTradeRequest(symbol_or_symbols=symbol)
        last_trade = self.crypto_data_client.get_crypto_latest_trade(request)[symbol]
        return {"symbol": symbol, "price": float(last_trade.price)}

    def fetch_balance(self):
        # Get USD cash balance and market value of open positions
        positions = self.trading_client.get_all_positions()
        balance = {"USD": {"total": float(self.account.cash)}}
        for pos in positions:
            balance[pos.symbol] = {"total": float(pos.market_value)}
        return balance

    def fetch_recent_ohlcv(self, symbol, timeframe, limit):
        # Map string timeframe to Alpaca TimeFrame object
        tf = config.ALPACA_TIMEFRAME_MAP.get(timeframe, TimeFrame.Hour)

        end_time = datetime.now(pytz.UTC)
        start_time = end_time - timedelta(minutes=limit * 5)  # estimate window

        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start_time,
            end=end_time
        )

        bars = self.crypto_data_client.get_crypto_bars(request).df.reset_index()
        bars = bars[bars['symbol'] == symbol].copy()
        bars.rename(columns={"timestamp": "timestamp"}, inplace=True)
        bars.set_index("timestamp", inplace=True)
        return bars[["open", "high", "low", "close", "volume"]]

    def fetch_open_orders(self, symbol):
        request = GetOrdersRequest(symbols=[symbol], status="open")
        return self.trading_client.get_orders(filter=request)

    def cancel_all_orders(self, symbol):
        orders = self.fetch_open_orders(symbol)
        for order in orders:
            self.trading_client.cancel_order_by_id(order.id)

    def place_order(self, symbol, side, qty, order_type="market", time_in_force="gtc", **kwargs):
        side_enum = OrderSide.BUY if side == "buy" else OrderSide.SELL

        # Reorder parameters if limit_price accidentally passed as time_in_force
        if isinstance(time_in_force, (int, float)):
            kwargs['limit_price'] = time_in_force
            time_in_force = "gtc"

        tif_enum = TimeInForce.GTC if time_in_force.lower() == "gtc" else TimeInForce.DAY

        order_type = order_type.lower()
        if order_type == "market":
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif_enum
            )
        elif order_type == "limit":
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                limit_price=kwargs.get("limit_price"),
                time_in_force=tif_enum
            )
        # Alpaca Cyrpto Does Not Allow Stop AUG2025
        elif order_type == "stop":
            order_data = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                stop_price=kwargs.get("stop_price"),
                time_in_force=tif_enum
            )
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        return self.trading_client.submit_order(order_data)
        
    def fetch_position(self, symbol):
        # Manually filter all positions since get_open_position is unreliable for crypto
        all_positions = self.trading_client.get_all_positions()
        for pos in all_positions:
            if pos.symbol.upper() == symbol.replace("/", "").upper():
                return pos
        return None

    def wait_for_filled_position(self, symbol, timeout=30, poll_interval=2):
        """
        Waits until the position is reflected in account or an order is confirmed as filled.
        Returns the position object or None.
        """
        elapsed = 0
        while elapsed < timeout:
            pos = self.fetch_position(symbol)
            if pos and float(pos.qty) > 0:
                return pos
            print(f"Checked after {elapsed}s: qty_available = {0 if not pos else pos.qty}")
            time.sleep(poll_interval)
            elapsed += poll_interval
        return None