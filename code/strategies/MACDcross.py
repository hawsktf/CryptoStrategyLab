import sys
import ta
import pandas as pd
from datetime import datetime

from . import tools as ut

class Strategy:
    def __init__(self, params, ohlcv) -> None:
        self.params = params
        self.data = ohlcv.copy()

        self.populate_indicators()
        self.set_trade_mode()
        self.good_to_trade = True
        self.position_was_closed = False
        self.last_position_side = None

    # --- Trade Mode ---
    def set_trade_mode(self):
        self.params.setdefault("mode", "both")

        valid_modes = ("long", "short", "both")
        if self.params["mode"] not in valid_modes:
            raise ValueError(f"Wrong strategy mode. Can either be {', '.join(valid_modes)}.")

        self.ignore_shorts = self.params["mode"] == "long"
        self.ignore_longs = self.params["mode"] == "short"

        if not self.ignore_longs:
            self.populate_long_signals()
        if not self.ignore_shorts:
            self.populate_short_signals()

    # --- Indicators ---
    def populate_indicators(self):
        """
        Populates MACD indicators for trade decisions.
        """
        self.data["macd"] = ta.trend.macd(self.data["close"], 
                                          window_slow=self.params.get("slow_ma", 26), 
                                          window_fast=self.params.get("fast_ma", 12))
        
        self.data["macd_signal"] = ta.trend.macd_signal(self.data["close"], 
                                                        window_slow=self.params.get("slow_ma", 26), 
                                                        window_fast=self.params.get("fast_ma", 12), 
                                                        window_sign=self.params.get("signal_ma", 9))
        
        self.data["macd_hist"] = ta.trend.macd_diff(self.data["close"], 
                                                    window_slow=self.params.get("slow_ma", 26), 
                                                    window_fast=self.params.get("fast_ma", 12), 
                                                    window_sign=self.params.get("signal_ma", 9))


    # --- Long Entry (Golden Cross) ---
    def populate_long_signals(self):
        """
        Detects a MACD Golden Cross as a long entry signal.
        """
        self.data["long_entry"] = (self.data["macd"] > self.data["macd_signal"]) & \
                                  (self.data["macd"].shift(1) <= self.data["macd_signal"].shift(1))

    def calculate_long_sl_price(self, avg_open_price):
        return avg_open_price * (1 - self.params["stop_loss_pct"])

    # --- Short Entry (Death Cross) ---
    def populate_short_signals(self):
        """
        Detects a MACD Death Cross as a short entry signal.
        """
        self.data["short_entry"] = (self.data["macd"] < self.data["macd_signal"]) & \
                                   (self.data["macd"].shift(1) >= self.data["macd_signal"].shift(1))

    def calculate_short_sl_price(self, avg_open_price):
        return avg_open_price * (1 + self.params["stop_loss_pct"])

    # --- Order Evaluation (Entry & Exit) ---
    def evaluate_orders(self, time, row):
        """
        Evaluates trading conditions for entries, exits, and stop-loss handling.
        """
        self.position_was_closed = False

        if not self.good_to_trade:
            if self.last_position_side == "long" and row["macd"] > row["macd_signal"]:
                self.good_to_trade = True
            elif self.last_position_side == "short" and row["macd"] < row["macd_signal"]:
                self.good_to_trade = True

        # --- Long Position Handling (Golden Cross Buy) ---
        if self.position.side == "long":
            if row["short_entry"]:
                self.close_trade(time, row["close"], "MACD Death Cross")
                self.position_was_closed = True
            elif self.position.check_for_sl(row):
                self.close_trade(time, self.position.sl_price, "Stop Loss")
                self.good_to_trade = False

        # --- Short Position Handling (Death Cross Sell) ---
        elif self.position.side == "short":
            if row["long_entry"]:
                self.close_trade(time, row["close"], "MACD Golden Cross")
                self.position_was_closed = True
            elif self.position.check_for_sl(row):
                self.close_trade(time, self.position.sl_price, "Stop Loss")
                self.good_to_trade = False

        # --- Open New Position ---
        if self.good_to_trade and not self.position_was_closed:
            balance = self.balance
            if not self.ignore_longs and self.position.side != "short" and row["long_entry"]:
                side = "long"
                price = row["close"]
                sl_price = price * (1 - self.params["stop_loss_pct"])
            elif not self.ignore_shorts and self.position.side != "long" and row["short_entry"]:
                side = "short"
                price = row["close"]
                sl_price = price * (1 + self.params["stop_loss_pct"])
            else:
                return

            self.last_position_side = side
            if "position_size_percentage" in self.params:
                initial_margin = balance * (self.params["position_size_percentage"] / 100)
            elif "position_size_fixed_amount" in self.params:
                initial_margin = self.params["position_size_fixed_amount"]
            else:
                raise ValueError("Position size parameter missing: Define either 'position_size_percentage' or 'position_size_fixed_amount'.")


            self.balance -= initial_margin
            self.position.open(time, side, initial_margin, price, f"Open {side}", sl_price=sl_price)

    # --- Trade Closing ---
    def close_trade(self, time, price, reason):
        self.position.close(time, price, reason)
        open_balance = self.balance
        self.balance += self.position.initial_margin + self.position.net_pnl
        trade_info = self.position.info()
        trade_info["open_balance"] = open_balance
        trade_info["close_balance"] = self.balance
        del trade_info["tp_price"]
        self.trades_info.append(trade_info)

    # --- Backtest Execution ---
    def run_backtest(self, initial_balance, leverage, open_fee_rate, close_fee_rate):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = ut.Position(leverage=leverage, open_fee_rate=open_fee_rate, close_fee_rate=close_fee_rate)
        self.equity_update_interval = pd.Timedelta(hours=6)

        self.previous_equity_update_time = datetime(1900, 1, 1)
        self.trades_info = []
        self.equity_record = []

        for time, row in self.data.iterrows():
            self.evaluate_orders(time, row)
            self.previous_equity_update_time = ut.update_equity_record(
                time, self.position, self.balance, row["close"], 
                self.previous_equity_update_time, self.equity_update_interval, self.equity_record
            )

        self.trades_info = pd.DataFrame(self.trades_info)
        self.equity_record = pd.DataFrame(self.equity_record).set_index("time")
        self.final_equity = round(self.equity_record.iloc[-1]["equity"], 2)

    # --- Save results ---
    def save_equity_record(self, path):
        self.equity_record.to_csv(path+'_equity_record.csv', header=True, index=True)

    def save_trades_info(self, path):
        self.trades_info.to_csv(path+'_trades_info.csv', header=True, index=True)
