import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from binance.client import Client
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.stats import rankdata
import requests

# ------------------ Utility Functions ------------------
def fetch_coingecko_coins():
    """Fetch all coins from CoinGecko and map symbol -> id."""
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        coins = requests.get(url).json()
        symbol_to_id = {c['symbol'].lower(): c['id'] for c in coins}
        return symbol_to_id
    except Exception as e:
        print("Error fetching CoinGecko coins:", e)
        return {}

def base_from_binance(symbol, quote_asset='USDC'):
    """Extract base coin from Binance symbol."""
    if symbol.endswith(quote_asset):
        return symbol.replace(quote_asset, '').lower()
    return symbol.lower()

# ------------------ Main Class ------------------
class Sirifi_C_ValueInvest:
    def __init__(self, api_key, api_secret, quote_asset='USDC', max_symbols=30, threads=5, history_days=90):
        self.client = Client(api_key, api_secret)
        self.quote_asset = quote_asset
        self.max_symbols = max_symbols
        self.threads = threads
        self.history_days = history_days
        # Dynamic CoinGecko mapping
        self.symbol_to_id = fetch_coingecko_coins()

    # ----------------- Utilities -----------------
    def retry(self, func, *args, retries=3, delay=1, **kwargs):
        for _ in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception:
                time.sleep(delay)
        return None

    def winsorized_rank(self, series, lower=0.05, upper=0.95):
        q_low = series.quantile(lower)
        q_high = series.quantile(upper)
        series = series.clip(q_low, q_high)
        return rankdata(series, method='average') / len(series)

    # ----------------- Data Fetching -----------------
    def get_symbols(self):
        info = self.retry(self.client.get_exchange_info)
        if not info:
            return []
        return [
            s['symbol'] for s in info['symbols']
            if s['quoteAsset'] == self.quote_asset and s['status'] == 'TRADING'
        ][:self.max_symbols]

    def get_price_marketcap(self, symbol):
        ticker = self.retry(self.client.get_ticker, symbol=symbol)
        if not ticker:
            return 0, 0, 0

        try:
            price = float(ticker['lastPrice'])
            change_pct = float(ticker['priceChangePercent'])

            base_symbol = base_from_binance(symbol, self.quote_asset)
            cg_id = self.symbol_to_id.get(base_symbol)
            if not cg_id:
                return price, change_pct, 0

            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {'vs_currency': self.quote_asset.lower(), 'ids': cg_id}
            r = requests.get(url, params=params).json()
            if not r:
                return price, change_pct, 0

            market_cap = float(r[0]['market_cap'])
            return price, change_pct, market_cap
        except Exception as e:
            print(f"Error fetching price/marketcap for {symbol}: {e}")
            return 0, 0, 0

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

    def process_symbol(self, symbol):
        try:
            # Historical data
            cagr, sharpe, max_dd = self.historical_metrics(symbol)

            # Price and marketcap
            price, price_change_pct, market_cap = self.get_price_marketcap(symbol)
            if market_cap <= 0:
                return None

            # Agg trades last day
            start_ms = int((datetime.utcnow() - timedelta(days=1)).timestamp()*1000)
            end_ms = int(datetime.utcnow().timestamp()*1000)
            trades = self.get_agg_trades(symbol, start_ms, end_ms)
            total_buy = sum(float(t['p'])*float(t['q']) for t in trades if not t['m'])
            total_sell = sum(float(t['p'])*float(t['q']) for t in trades if t['m'])
            net_flow_ratio = (total_buy - total_sell)/market_cap
            total_volume = total_buy + total_sell

            return {
                'symbol': symbol,
                'price': round(price,4),
                'price_change_pct': price_change_pct,
                'total_volume': round(total_volume,2),
                'net_flow_ratio': round(net_flow_ratio,4),
                'market_cap': round(market_cap,2),
                'cagr': cagr,
                'sharpe': sharpe,
                'max_drawdown': max_dd
            }
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            return None

    # ----------------- Analysis -----------------
    def analyze(self):
        symbols = self.get_symbols()
        if not symbols:
            print("No symbols fetched")
            return pd.DataFrame()
        print(f"Analyzing {len(symbols)} symbols...")

        results = []
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self.process_symbol, s): s for s in symbols}
            for future in as_completed(futures):
                res = future.result()
                if res:
                    results.append(res)

        df = pd.DataFrame(results)
        if df.empty:
            return df

        # Liquidity filter
        df['volume_yield'] = df['total_volume']/(df['market_cap']*self.history_days)
        df['risk_adjusted'] = df['sharpe']/(abs(df['max_drawdown'])+1e-6)

        # Value score
        df['value_score'] = (
            (1 - self.winsorized_rank(df['price_change_pct']))*1.5 +
            self.winsorized_rank(df['net_flow_ratio'])*1.2 +
            self.winsorized_rank(df['volume_yield'])*1.0 +
            self.winsorized_rank(df['cagr'])*2.0 +
            self.winsorized_rank(df['sharpe'])*1.5 +
            (1 - self.winsorized_rank(df['max_drawdown']))*1.0 +
            self.winsorized_rank(df['risk_adjusted'])*1.0
        )
        df['rank'] = df['value_score'].rank(ascending=False).astype(int)
        df = df.sort_values('rank')
        return df.reset_index(drop=True)
