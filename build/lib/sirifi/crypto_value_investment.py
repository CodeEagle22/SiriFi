import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from binance.client import Client
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.stats import rankdata
import yfinance as yf


class Sirifi_C_ValueInvest:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        quote_asset: str = 'USDC',
        max_symbols: int = 100,
        threads: int = 5,
        history_days: int = 90,
        min_marketcap: float = 0,
        min_agedays: int = 0
    ):
        """
        Args:
            api_key (str): Binance API key.
            api_secret (str): Binance API secret.
            quote_asset (str): Quote asset for trading pairs (e.g., "USDC").
            max_symbols (int): Maximum number of symbols to fetch.
            threads (int): Number of threads for parallel processing.
            history_days (int): Number of days of historical data to analyze.
            min_marketcap (float): Minimum market capitalization filter.
            min_agedays (int): Minimum age of coin in days.
        """
        # ---- Assertions ----
        assert isinstance(api_key, str) and api_key, "api_key must be a non-empty string"
        assert isinstance(api_secret, str) and api_secret, "api_secret must be a non-empty string"
        assert isinstance(quote_asset, str) and quote_asset, "quote_asset must be a non-empty string"
        assert isinstance(max_symbols, int) and max_symbols > 0, "max_symbols must be positive int"
        assert isinstance(threads, int) and threads > 0, "threads must be positive int"
        assert isinstance(history_days, int) and history_days > 0, "history_days must be positive int"
        assert isinstance(min_marketcap, (int, float)) and min_marketcap >= 0, "min_marketcap must be >= 0"
        assert isinstance(min_agedays, int) and min_agedays >= 0, "min_agedays must be >= 0"

        self.client = Client(api_key, api_secret)
        self.quote_asset = quote_asset
        self.max_symbols = max_symbols
        self.threads = threads
        self.history_days = history_days
        self.min_marketcap = min_marketcap
        self.min_agedays = min_agedays

    # ----------------- Utilities -----------------
    def retry(self, func, *args, retries=3, delay=1, **kwargs):
        """
        Retry a function call with delay on failure.

        Args:
            func (callable): Function to call.
            *args: Positional arguments for the function.
            retries (int): Number of retry attempts.
            delay (int or float): Delay in seconds between retries.
            **kwargs: Keyword arguments for the function.

        Returns:
            Any: Result of the function call or None if failed.
        """
        assert callable(func), "func must be callable"
        assert isinstance(retries, int) and retries >= 0, "retries must be non-negative int"
        assert isinstance(delay, (int, float)) and delay >= 0, "delay must be non-negative number"

        for _ in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception:
                time.sleep(delay)
        return None

    def winsorized_rank(self, series, lower=0.05, upper=0.95):
        """
        Compute winsorized rank of a Pandas series.

        Args:
            series (pd.Series): Series to rank.
            lower (float): Lower quantile cutoff.
            upper (float): Upper quantile cutoff.

        Returns:
            np.ndarray: Normalized ranks between 0 and 1.
        """
        assert isinstance(series, pd.Series), "series must be a pandas Series"
        assert 0 <= lower < upper <= 1, "lower and upper must be between 0 and 1"

        q_low = series.quantile(lower)
        q_high = series.quantile(upper)
        series = series.clip(q_low, q_high)
        return rankdata(series, method='average') / len(series)

    # ----------------- Data Fetching -----------------
    def get_symbols(self):
        info = self.retry(self.client.get_exchange_info)
        if not info:
            return []
        symbols = []
        for s in info['symbols']:
            if s['quoteAsset'] == self.quote_asset and s['status'] == 'TRADING':
                listing_date = s.get('onboardDate')  # in milliseconds
                if listing_date:
                    listing_date = datetime.utcfromtimestamp(listing_date / 1000)
                symbols.append({
                    'symbol': s['symbol'],
                    'listing_date': listing_date
                })
        return symbols[:self.max_symbols]

    def get_listing_date(self, symbol):
        """Estimate listing date from first available kline."""
        try:
            # Request earliest kline (daily interval, going back far)
            klines = self.retry(
                self.client.get_historical_klines,
                symbol,
                Client.KLINE_INTERVAL_1DAY,
                "1 Jan, 2017",  # very early start date
                limit=1
            )
            if not klines:
                return None
            first_timestamp = int(klines[0][0])  # ms timestamp of first candle
            return datetime.utcfromtimestamp(first_timestamp / 1000)
        except Exception:
            return None

    def get_price(self, symbol):
        ticker = self.retry(self.client.get_ticker, symbol=symbol)
        if not ticker:
            return 0, 0
        try:
            price = float(ticker['lastPrice'])
            change_pct = float(ticker['priceChangePercent'])
            return price, change_pct
        except:
            return 0, 0

    def get_agg_trades(self, symbol, start_ms, end_ms):
        trades = []
        while True:
            batch = self.retry(
                self.client.get_aggregate_trades,
                symbol=symbol,
                startTime=start_ms,
                endTime=end_ms,
                limit=1000
            )
            if not batch:
                break
            trades.extend(batch)
            last_time = batch[-1]['T']
            if last_time >= end_ms:
                break
            start_ms = last_time + 1
            time.sleep(0.05)
        return trades

    # ----------------- Metrics -----------------
    def historical_metrics(self, symbol):
        end = datetime.utcnow()
        start = end - timedelta(days=self.history_days)
        start_str = start.strftime("%d %b, %Y %H:%M:%S")
        end_str = end.strftime("%d %b, %Y %H:%M:%S")

        klines = self.retry(
            self.client.get_historical_klines,
            symbol,
            Client.KLINE_INTERVAL_1DAY,
            start_str,
            end_str
        )
        if not klines:
            return 0, 0, 0

        df = pd.DataFrame(klines, columns=[
            'timestamp','open','high','low','close','volume','close_time',
            'quote_volume','num_trades','taker_buy_base','taker_buy_quote','ignore'
        ])
        df['close'] = df['close'].astype(float)
        df['returns'] = df['close'].pct_change().fillna(0)
        df['log_returns'] = np.log(df['close']/df['close'].shift(1)).fillna(0)

        cagr = (df['close'].iloc[-1] / df['close'].iloc[0]) ** (365/len(df)) - 1
        sharpe = df['log_returns'].mean()/df['log_returns'].std()*np.sqrt(365) if df['log_returns'].std() != 0 else 0
        cum = (1+df['returns']).cumprod()
        drawdown = (cum - cum.cummax())/cum.cummax()
        max_dd = drawdown.min()
        return round(cagr,4), round(sharpe,4), round(max_dd,4)

    # ----------------- Market Cap via yfinance -----------------
    def get_market_cap_and_supply(self, symbol, price, volume=None, cache={}):
        base_symbol = symbol.replace(self.quote_asset, "")
        yf_symbol = f"{base_symbol}-USD"

        market_cap, circulating_supply = 0, 0

        try:
            # Cache yfinance lookups
            if yf_symbol not in cache:
                cache[yf_symbol] = yf.Ticker(yf_symbol)
            ticker = cache[yf_symbol]

            # Use fast_info when available
            if hasattr(ticker, "fast_info"):
                fi = ticker.fast_info
                market_cap = getattr(fi, "market_cap", 0) or 0
                circulating_supply = getattr(fi, "shares_outstanding", 0) or 0

            # Fallback: slower info dict
            if (not market_cap or not circulating_supply):
                info = getattr(ticker, "info", {}) or {}
                market_cap = info.get("marketCap") or market_cap
                circulating_supply = info.get("circulatingSupply") or circulating_supply

        except Exception:
            # Handle gracefully → no spammy warnings
            # Just skip silently instead of noisy logs
            return 0, 0

        # Extra fallback if yfinance didn’t provide enough
        if (not market_cap or not circulating_supply) and price > 0:
            if circulating_supply and not market_cap:
                market_cap = circulating_supply * price
            elif market_cap and not circulating_supply:
                circulating_supply = market_cap / price if price > 0 else 0
            elif volume and volume > 0:
                # Approximate fallback: market cap ≈ 2 * volume
                market_cap = volume * 2
                circulating_supply = market_cap / price if price > 0 else 0

        return round(market_cap, 2), round(circulating_supply, 2)


    # ----------------- Symbol Processing -----------------
    def process_symbol(self, sym_info):
        try:
            symbol = sym_info['symbol']
            listing_date = self.get_listing_date(symbol)
            coin_age_days = (datetime.utcnow() - listing_date).days if listing_date else 0

            

            # Price and change
            price, price_change_pct = self.get_price(symbol)
            if price <= 0:
                return None

            # Historical metrics
            cagr, sharpe, max_dd = self.historical_metrics(symbol)

            # Market cap and supply
            market_cap, circulating_supply = self.get_market_cap_and_supply(symbol, price)

            # Aggregate trades last day
            start_ms = int((datetime.utcnow() - timedelta(days=1)).timestamp()*1000)
            end_ms = int(datetime.utcnow().timestamp()*1000)
            trades = self.get_agg_trades(symbol, start_ms, end_ms)
            total_buy = sum(float(t['p'])*float(t['q']) for t in trades if not t['m'])
            total_sell = sum(float(t['p'])*float(t['q']) for t in trades if t['m'])
            net_flow_ratio = (total_buy - total_sell)/market_cap if market_cap > 0 else 0
            total_volume = total_buy + total_sell

            return {
                'symbol': symbol,
                'price': round(price,4),
                'price_change_pct': price_change_pct,
                'total_volume': round(total_volume,2),
                'net_flow_ratio': round(net_flow_ratio,4),
                'market_cap': round(market_cap,2),
                'circulating_supply': round(circulating_supply,2),
                'cagr': cagr,
                'sharpe': sharpe,
                'max_drawdown': max_dd,
                'age_days': coin_age_days
            }

        except Exception as e:
            print(f"Error processing {sym_info['symbol']}: {e}")
            return None


    # ----------------- Analysis -----------------
    def analyze(self):
        symbols_info = self.get_symbols()
        if not symbols_info:
            print("No symbols fetched")
            return pd.DataFrame()
        print(f"Analyzing {len(symbols_info)} symbols...")

        results = []
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self.process_symbol, s): s['symbol'] for s in symbols_info}
            for future in as_completed(futures):
                res = future.result()
                if res:
                    results.append(res)

        df = pd.DataFrame(results)
        if df.empty:
            return df

        # ---- Handle 0 market cap fallback ----
        missing_caps = (df['market_cap'] == 0) & (df['total_volume'] > 0) & (df['price'] > 0)
        df.loc[missing_caps, 'market_cap'] = df.loc[missing_caps, 'total_volume'] * 5
        df.loc[missing_caps, 'circulating_supply'] = df.loc[missing_caps, 'market_cap'] / df.loc[missing_caps, 'price']

        df = df[df['market_cap'] > 0].reset_index(drop=True)
        df = df[df['market_cap'] > self.min_marketcap].reset_index(drop=True)
        df = df[df['age_days'] > self.min_agedays].reset_index(drop=True)

        # ---- Extra metrics ----
        df['volume_yield'] = df['total_volume'] / (df['market_cap'] * self.history_days)
        df['risk_adjusted'] = df['sharpe'] / (abs(df['max_drawdown']) + 1e-6)

        # ---- Value score ----
        df['value_score'] = (
            (1 - self.winsorized_rank(df['price_change_pct'])) * 1.5 +
            self.winsorized_rank(df['net_flow_ratio']) * 1.2 +
            self.winsorized_rank(df['volume_yield']) * 1.0 +
            self.winsorized_rank(df['cagr']) * 2.0 +
            self.winsorized_rank(df['sharpe']) * 1.5 +
            (1 - self.winsorized_rank(df['max_drawdown'])) * 1.0 +
            self.winsorized_rank(df['risk_adjusted']) * 1.0
        )
        df['rank'] = df['value_score'].rank(ascending=False).astype(int)
        df = df.sort_values('rank')
        return df.reset_index(drop=True)