import yfinance as yf
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
from datetime import datetime, timedelta
import time


class DataStreamer:
    def __init__(self, binance_api_key=None, binance_api_secret=None):
        self.binance_client = None
        if binance_api_key and binance_api_secret:
            self.binance_client = Client(binance_api_key, binance_api_secret)
        self._binance_symbols_cache = None

    def _map_interval_binance(self, interval):
        mapping = {
            '1m': '1m', '5m': '5m', '15m': '15m',
            '30m': '30m', '1h': '1h', '4h': '4h',
            '1d': '1d', '1w': '1w', '1M': '1M'
        }
        iv = interval.lower()
        if iv not in mapping:
            raise ValueError(f"Interval '{interval}' not supported.")
        return mapping[iv]

    def _adjust_dates(self, source, interval, start_date, end_date):
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        if end_date is None:
            end_date = pd.Timestamp.today()
        if start_date is None:
            if source == "yfinance":
                start_date = end_date - pd.Timedelta(days=730)
            elif source == "binance":
                start_date = end_date - pd.Timedelta(days=365)
        return start_date, end_date

    def _is_valid_binance_symbol(self, symbol):
        try:
            if not self._binance_symbols_cache:
                info = self.binance_client.get_exchange_info()
                self._binance_symbols_cache = {s["symbol"] for s in info["symbols"]}
            return symbol in self._binance_symbols_cache
        except Exception as e:
            print(f"[Binance] Could not validate symbol {symbol}: {e}")
            return True  # Fail-safe assumption

    def map_ticker_for_source(self, base_asset, currency, source):
        base_asset = base_asset.upper()
        currency = currency.upper()

        if source == "yfinance":
            return f"{base_asset}-{currency}"
        elif source == "binance":
            # Try direct pair first (BTCUSD), fallback to BTCUSDT if currency is USD
            primary = f"{base_asset}{currency}"
            fallback = f"{base_asset}USDC" if currency == "USD" else None

            if self._is_valid_binance_symbol(primary):
                return primary
            elif fallback and self._is_valid_binance_symbol(fallback):
                print(f"[Binance] Falling back to {fallback} for {base_asset}")
                return fallback
            else:
                print(f"[Binance] No valid pair found for {base_asset} in {currency}")
                return None
        else:
            raise ValueError(f"Unknown source: {source}")

    def _fetch_yfinance(self, ticker, interval, start_date, end_date):
        try:
            start_date, end_date = self._adjust_dates('yfinance', interval, start_date, end_date)
            data = yf.download(ticker, start=start_date, end=end_date, interval=interval, progress=False)
            if data.empty:
                print(f"[Yahoo Finance] No data for {ticker}")
                return None
            return data
        except Exception as e:
            print(f"[Yahoo Finance] Failed for {ticker}: {e}")
            return None

    def _fetch_binance(self, ticker, interval, start_date, end_date):
        if not self.binance_client:
            print("[Binance] API credentials not provided.")
            return None

        interval = self._map_interval_binance(interval)
        start_date, end_date = self._adjust_dates("binance", interval, start_date, end_date)
        try:
            start_str = start_date.strftime("%d %b, %Y")
            end_str = (end_date + timedelta(days=1)).strftime("%d %b, %Y")

            klines = self.binance_client.get_historical_klines(ticker, interval, start_str, end_str)
            if not klines:
                print(f"[Binance] No data for {ticker} @ {interval}")
                return None

            df = pd.DataFrame(klines, columns=[
                "OpenTime", "Open", "High", "Low", "Close", "Volume",
                "CloseTime", "QuoteAssetVolume", "NumberOfTrades",
                "TakerBuyBaseAssetVolume", "TakerBuyQuoteAssetVolume", "Ignore"
            ])
            df["OpenTime"] = pd.to_datetime(df["OpenTime"], unit='ms')
            df.set_index("OpenTime", inplace=True)
            df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
            return df

        except BinanceAPIException as e:
            print(f"[Binance] API error: {e}")
            return None
        except Exception as e:
            print(f"[Binance] Failed to fetch {ticker} @ {interval}: {e}")
            return None

    def fetch(self, base_assets, currency="USD", interval="1d", source="yfinance", start_date=None, end_date=None):
        results = {}
        for asset in base_assets:
            print(f"[Fetching] {asset}{currency} ...")
            ticker = self.map_ticker_for_source(asset, currency, source)
            if not ticker:
                print(f"[Failure] No valid ticker for {asset}")
                results[asset] = None
                continue

            if source == "yfinance":
                df = self._fetch_yfinance(ticker, interval, start_date, end_date)
            elif source == "binance":
                df = self._fetch_binance(ticker, interval, start_date, end_date)
            else:
                print(f"[Error] Unsupported source: {source}")
                df = None

            if df is not None:
                print(f"[Success] {asset}{currency} data loaded from {source}")
            else:
                print(f"[Failure] No data found for {asset}{currency}")
            results[asset] = df
        return results
