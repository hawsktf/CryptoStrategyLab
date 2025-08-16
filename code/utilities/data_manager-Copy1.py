import ccxt
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import sys
sys.path.append('./config')
import config
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

class DataManager:
    def __init__(self, name: str, path: str = "../data") -> None:
        self.name = name
        self.path = Path(__file__).parent.joinpath(config.BASE_DATA_PATH).resolve()
        if name != 'alpaca':
            self.exchange = config.EXCHANGES[self.name]["exchange_object"]
        self._check_support()
        self._create_directory(self.path)
        self.markets = None
        self.available_symbols = None

    def _check_support(self) -> None:
        if self.name != 'alpaca' and self.name not in config.EXCHANGES:
            raise ValueError(f"The exchange {self.name} is not supported.")

    def fetch_markets(self):
        if self.name != 'alpaca':
            self.markets = self.exchange.load_markets()
            self.available_symbols = list(self.markets.keys())

    def fetch_symbol_markets_info(self, symbol: str) -> None:
        if not self.markets:
            self.fetch_markets()
        return self.markets[symbol]

    def fetch_symbol_markets_limits(self, symbol: str) -> None:
        if not self.markets:
            self.fetch_markets()
        return self.markets[symbol]['limits']

    def fetch_symbol_ticker_info(self, symbol: str, params={}) -> None:
        return self.exchange.fetch_ticker(symbol, params)

    def download(self, symbol: str, timeframe: str, start_date: Optional[str] = None,
                 end_date: Optional[str] = None) -> None:
        if self.name != 'alpaca' and not self.markets:
            self.fetch_markets()

        if self.name != 'alpaca' and symbol not in self.available_symbols:
            raise ValueError(f"The trading pair {symbol} either does not exist on {self.name} or the format is wrong.")

        if timeframe not in config.TIMEFRAMES:
            raise ValueError(f"The timeframe {timeframe} is not supported.")

        date_format = "%Y-%m-%d" if timeframe == '1d' else "%Y-%m-%d %H:%M:%S"
        if start_date is None:
            start_date = datetime(2017, 1, 1, 0, 0, 0)
        else:
            start_date = datetime.strptime(start_date, date_format)

        if end_date is None:
            end_date = datetime.now()
        else:
            end_date = datetime.strptime(end_date, date_format)

        if self.name == 'alpaca':
            alpaca_client = CryptoHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)
            bars_request = CryptoBarsRequest(
                symbol_or_symbols=symbol.replace('USDT', 'USD'),
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
            )
            bars = alpaca_client.get_crypto_bars(bars_request).df
            bars = bars.reset_index()
            bars.rename(columns={'timestamp': 'date'}, inplace=True)
            #bars['date'] = pd.to_datetime(bars['date'], utc=True).dt.tz_localize(None)
            bars['date'] = pd.to_datetime(bars['date'], utc=True).dt.tz_convert(None).dt.floor('D')
            ohlcv = bars[['date', 'open', 'high', 'low', 'close', 'volume']]
            ohlcv.set_index('date', inplace=True)
        else:
            ohlcv_raw = self._get_ohlcv(symbol, timeframe, start_date, end_date)
            ohlcv = pd.DataFrame(ohlcv_raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            ohlcv['date'] = pd.to_datetime(ohlcv['timestamp'], unit='ms')
            ohlcv = ohlcv[ohlcv['date'].notna()]
            ohlcv['close'] = pd.to_numeric(ohlcv['close'], errors='coerce')
            ohlcv = ohlcv[ohlcv['close'].notna()]
            ohlcv.set_index('date', inplace=True)
            ohlcv = ohlcv[~ohlcv.index.duplicated(keep='first')]
            del ohlcv['timestamp']
            ohlcv = ohlcv.sort_index()
            ohlcv = ohlcv.iloc[:-1]

        ohlcv = ohlcv.sort_index()
        ohlcv = self.fundamentals(ohlcv)
        self.save_to_master_db(ohlcv, symbol, timeframe)

    def load(self, symbol: str, timeframe: str, start_date: Optional[str] = None,
             end_date: Optional[str] = None) -> pd.DataFrame:
        file_path = self.path.joinpath(timeframe, symbol.replace('/', '-').replace(':', '-') + ".csv")
        if not file_path.exists():
            raise FileNotFoundError(f"No data found at {file_path}. Please run .download() first.")

        df = pd.read_csv(file_path, parse_dates=['date'])
        df.columns = df.columns.str.strip()

        if start_date:
            start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
            df = df[df['date'] >= start_date_dt]
        if end_date:
            end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
            df = df[df['date'] <= end_date_dt]

        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        return df

    def fundamentals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_index()

        for window in [20, 50, 200]:
            df[f'sma_{window}'] = df['close'].rolling(window=window).mean()
            df[f'ema_{window}'] = df['close'].ewm(span=window, adjust=False).mean()

        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        df['bb_middle'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (2 * df['bb_std'])
        df['bb_lower'] = df['bb_middle'] - (2 * df['bb_std'])

        return df

    def save_to_master_db(self, df: pd.DataFrame, symbol: str, timeframe: str):
        folder_path = self.path.joinpath(timeframe)
        folder_path.mkdir(parents=True, exist_ok=True)

        filename = symbol.replace('/', '-').replace(':', '-') + ".csv"
        file_path = folder_path.joinpath(filename)

        df = df.copy()
        df['exchange'] = self.name
        df['pair'] = symbol
        df['timeframe'] = timeframe
        df['date_downloaded'] = datetime.now()
        df.reset_index(inplace=True)

        if file_path.exists():
            existing_df = pd.read_csv(file_path, parse_dates=['date'])
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.drop_duplicates(subset=['pair', 'timeframe', 'date'], keep='last', inplace=True)

        else:
            combined_df = df

        combined_df['date'] = pd.to_datetime(combined_df['date'], errors='coerce', utc=True).dt.tz_localize(None)

        # Round numeric columns to 2 decimal places
        numeric_cols = combined_df.select_dtypes(include=['float64', 'float32', 'int']).columns
        combined_df[numeric_cols] = combined_df[numeric_cols].round(2)

        combined_df.sort_values(by='date', inplace=True)
        combined_df.to_csv(file_path, index=False)
        print(f"Saved {len(df)} new rows to {file_path.name}")

    def _create_directory(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _get_ohlcv(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> List[List[Any]]:
        current_date_ms = int(start_date.timestamp() * 1000)
        end_date_ms = int(end_date.timestamp() * 1000)
        ohlcv = []

        while current_date_ms < end_date_ms:
            fetched_data = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=current_date_ms,
                limit=EXCHANGES[self.name]["limit_size_request"]
            )
            if fetched_data:
                ohlcv.extend(fetched_data)
                current_date_ms = fetched_data[-1][0] + 1
                print(f"fetched {self.name} ohlcv data for {symbol} from {datetime.fromtimestamp(current_date_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                break

        return ohlcv

