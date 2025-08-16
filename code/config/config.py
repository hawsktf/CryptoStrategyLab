# Default
EXCHANGE_NAME = "binance" # "bitget" (binance requires non-US IP Address, enable VPN)

# Environment variable for scenario path
# ./config/config.py
SCENARIO_PATH = "/home/spoonbill/Projects/RobotTraders/CryptoStrategyLab/code/scenarios"
SCENARIO_FILE = "scenarios.csv"
SCENARIO_FILEPATH = SCENARIO_PATH + '/' + SCENARIO_FILE

# Results
RESULTS_PATH = "/home/spoonbill/Projects/RobotTraders/CryptoStrategyLab/code/results"
RESULTS_FILE = "results.csv"
RESULTS_FILEPATH = RESULTS_PATH + '/' + RESULTS_FILE

from datetime import timedelta
import ccxt

# Path to the base data folder
BASE_DATA_PATH = "../data"

# Exchange configuration
EXCHANGES = {
    "bitget": {
        "exchange_object": ccxt.bitget(config={'enableRateLimit': True}),
        "limit_size_request": 200,
    },
    "binance": {
        "exchange_object": ccxt.binance(config={'enableRateLimit': True}),
        "limit_size_request": 9999,
    },
    "binanceusdm": {
        "exchange_object": ccxt.binanceusdm(config={'enableRateLimit': True}),
        "limit_size_request": 1000,
    },
    "kucoin": {
        "exchange_object": ccxt.kucoin(config={'enableRateLimit': True}),
        "limit_size_request": 1000,
    },
    "bybit": {
        "exchange_object": ccxt.bybit(config={'enableRateLimit': True}),
        "limit_size_request": 1000,
    },
    "kraken": {
        "exchange_object": ccxt.kraken(config={'enableRateLimit': True}),
        "limit_size_request": 1000,
    },

    "alpaca": {
        "exchange_object": ccxt.alpaca(config={'enableRateLimit': True}),
        "limit_size_request": 999999,
    },
}

# Supported timeframes
TIMEFRAMES = {
    "1m": {"timedelta": timedelta(minutes=1), "interval_ms": 60000},
    "2m": {"timedelta": timedelta(minutes=2), "interval_ms": 120000},
    "5m": {"timedelta": timedelta(minutes=5), "interval_ms": 300000},
    "15m": {"timedelta": timedelta(minutes=15), "interval_ms": 900000},
    "30m": {"timedelta": timedelta(minutes=30), "interval_ms": 1800000},
    "1h": {"timedelta": timedelta(hours=1), "interval_ms": 3600000},
    "2h": {"timedelta": timedelta(hours=2), "interval_ms": 7200000},
    "4h": {"timedelta": timedelta(hours=4), "interval_ms": 14400000},
    "12h": {"timedelta": timedelta(hours=12), "interval_ms": 43200000},
    "1d": {"timedelta": timedelta(days=1), "interval_ms": 86400000},
    "1w": {"timedelta": timedelta(weeks=1), "interval_ms": 604800000},
    "1M": {"timedelta": timedelta(days=30), "interval_ms": 2629746000},
}

# Alpaca
ALPACA_API_KEY = "PKDHPHU621HPIIVIIY7U"
ALPACA_SECRET_KEY = "eh2iaSmlqdTIKRRnmQRZMTFAbdbjsBesbJuNBuBo"

USE_PAPER_TRADING = True
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_URL = "https://api.alpaca.markets"

# Timeframe mapping for Alpaca
from alpaca.data.timeframe import TimeFrame
ALPACA_TIMEFRAME_MAP = {
    "1m": TimeFrame.Minute,
    "5m": TimeFrame(5, TimeFrame.Minute),
    "15m": TimeFrame(15, TimeFrame.Minute),
    "1h": TimeFrame.Hour,
    "1d": TimeFrame.Day,
}