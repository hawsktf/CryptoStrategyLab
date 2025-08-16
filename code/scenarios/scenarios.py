import os
import pandas as pd
import ast
from dotenv import load_dotenv

# Load .env if exists
load_dotenv()

# Environment variable for scenario path
SCENARIO_PATH = os.getenv("SCENARIO_PATH", "/home/spoonbill/Projects/RobotTraders/CryptoStrategyLab/code/scenarios")
SCENARIO_FILE = os.path.join(SCENARIO_PATH, "scenarios.csv")

class StrategyScenario:
    def __init__(self, scenario_row):
        self.raw = scenario_row.to_dict()
        self.strategy_id = self.raw.get('strategy_id')
        self.symbol = self.raw.get('symbol')
        self.timeframe = self.raw.get('timeframe')
        self.start_date = self.raw.get('start_date') or None
        self.average_type = self.raw.get('average_type')
        self.strategy_params = {}

        if self.average_type == 'MACD':
            for key in ['fast_ma', 'slow_ma', 'signal_ma', 'stop_loss_pct']:
                if key in self.raw and self.raw[key] != "":
                    self.strategy_params[key] = float(self.raw[key]) if 'pct' in key else int(self.raw[key])
        else:
            if 'average_period' in self.raw and self.raw['average_period']:
                self.strategy_params['average_period'] = int(self.raw['average_period'])
            if 'stop_loss_pct' in self.raw and self.raw['stop_loss_pct']:
                self.strategy_params['stop_loss_pct'] = float(self.raw['stop_loss_pct'])
            if 'average_type' in self.raw:
                self.strategy_params['average_type'] = self.raw['average_type']

            envelopes = [
                float(self.raw[k]) for k in ['deviation_pct_1', 'deviation_pct_2', 'deviation_pct_3', 'deviation_pct_4']
                if k in self.raw and self.raw[k] != ""
            ]
            if envelopes:
                self.strategy_params['envelopes'] = envelopes

        # Dynamically include other optional strategy parameters
        optional_keys = [
            'price_jump_pct', 'position_size_percentage', 'position_size_fixed_amount', 'mode'
        ]
        for key in optional_keys:
            if key in self.raw and self.raw[key] != "":
                val = float(self.raw[key]) if 'pct' in key or 'amount' in key or 'percentage' in key else self.raw[key]
                self.strategy_params[key] = val

        # Execution parameters
        self.initial_balance = float(self.raw.get('initial_balance', 1000))
        self.leverage = float(self.raw.get('leverage', 1))
        self.open_fee_rate = float(self.raw.get('open_fee_rate', 0.0002))
        self.close_fee_rate = float(self.raw.get('close_fee_rate', 0.0006))

def load_scenario(strategy_id):
    df = pd.read_csv(SCENARIO_FILE)
    scenario_row = df[df["strategy_id"] == strategy_id].iloc[0].fillna("")
    scenario = StrategyScenario(scenario_row)
    return scenario

# Example usage:
# scenario = load_scenario("btc_sma_daily")
# ohlcv = data.load(scenario.symbol, timeframe=scenario.timeframe, start_date=scenario.start_date)
# strategy = strat.Strategy(scenario.strategy_params, ohlcv)
# strategy.run_backtest(scenario.initial_balance, scenario.leverage, scenario.open_fee_rate, scenario.close_fee_rate)
