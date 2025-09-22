import time
from datetime import datetime, timedelta
from binance.client import Client
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np


class Sirifi_C_FlowAnalyzer:
    def __init__(self,
                 api_key,
                 api_secret,
                 quote_asset='USDC',
                 timeframe='1h',
                 max_symbols=50,
                 threads=10,
                 small_thresh=10,
                 mid_thresh=100):
        
        self.client = Client(api_key, api_secret)
        self.quote_asset = quote_asset
        self.timeframe = timeframe
        self.max_symbols = max_symbols
        self.threads = threads
        self.small_thresh = small_thresh
        self.mid_thresh = mid_thresh

        self.timeframe_map = {
            '30m': timedelta(minutes=30),
            '1h': timedelta(hours=1),
            '1d': timedelta(days=1),
        }

        assert self.timeframe in self.timeframe_map, "Timeframe must be one of '30m', '1h', '1d'"
        assert small_thresh < mid_thresh, "small_thresh must be less than mid_thresh"

    def get_start_time_ms(self):
        delta = self.timeframe_map[self.timeframe]
        return int((datetime.utcnow() - delta).timestamp() * 1000)

    def fetch_all_symbols(self):
        exchange_info = self.client.get_exchange_info()
        return [
            s['symbol'] for s in exchange_info['symbols']
            if s['quoteAsset'] == self.quote_asset and s['status'] == 'TRADING'
        ][:self.max_symbols]

    def fetch_price_data(self, symbol):
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            price_change_pct = float(ticker.get('priceChangePercent', 0))
            last_price = float(ticker.get('lastPrice', 0))
            return price_change_pct, last_price
        except Exception as e:
            print(f"[!] Error fetching price data for {symbol}: {e}")
            return 0.0, 0.0

    def fetch_agg_trades(self, symbol, start_time_ms, end_time_ms):
        trades = []
        while True:
            try:
                batch = self.client.get_aggregate_trades(
                    symbol=symbol,
                    startTime=start_time_ms,
                    endTime=end_time_ms,
                    limit=1000
                )
                if not batch:
                    break
                trades.extend(batch)

                last_trade_time = batch[-1]['T']
                if last_trade_time >= end_time_ms:
                    break
                start_time_ms = last_trade_time + 1
                time.sleep(0.05)  # avoid rate limits
            except Exception as e:
                print(f"[!] Error fetching trades for {symbol}: {e}")
                break
        return trades

    def fetch_volatility(self, symbol):
        # Fetch last n candles according to timeframe to calculate volatility
        interval = self.timeframe
        limit = 20  # number of candles to analyze volatility, ~20 periods
        
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            closes = [float(k[4]) for k in klines]
            if len(closes) < 2:
                return 0.0
            volatility = np.std(closes) / np.mean(closes)  # coefficient of variation
            return volatility
        except Exception as e:
            print(f"[!] Error fetching volatility for {symbol}: {e}")
            return 0.0

    def categorize_order_size(self, trade_value):
        if trade_value < self.small_thresh:
            return 'small'
        elif trade_value < self.mid_thresh:
            return 'mid'
        else:
            return 'large'

    def analyze_agg_trades(self, trades):
        counts = {'buy': {'small': 0, 'mid': 0, 'large': 0}, 'sell': {'small': 0, 'mid': 0, 'large': 0}}
        values = {'buy': {'small': 0, 'mid': 0, 'large': 0}, 'sell': {'small': 0, 'mid': 0, 'large': 0}}
        total_buy = 0
        total_sell = 0

        for trade in trades:
            price = float(trade['p'])
            qty = float(trade['q'])
            value = price * qty
            side = 'sell' if trade['m'] else 'buy'
            size = self.categorize_order_size(value)

            counts[side][size] += 1
            values[side][size] += value

            if side == 'buy':
                total_buy += value
            else:
                total_sell += value

        return counts, values, total_buy, total_sell

    def process_symbol(self, symbol, start_time_ms, end_time_ms):
        trades = self.fetch_agg_trades(symbol, start_time_ms, end_time_ms)
        if not trades:
            return None

        counts, values, total_buy, total_sell = self.analyze_agg_trades(trades)

        total_volume = total_buy + total_sell
        net_flow_pct = (total_buy - total_sell) / total_volume if total_volume > 0 else 0
        buy_sell_ratio = total_buy / total_sell if total_sell > 0 else float('inf')
        price_change_pct, current_price = self.fetch_price_data(symbol)
        volatility = self.fetch_volatility(symbol)

        return {
            'ticker': symbol,
            'current_price': round(current_price, 6),
            'small_buy_orders': counts['buy']['small'],
            'mid_buy_orders': counts['buy']['mid'],
            'large_buy_orders': counts['buy']['large'],
            'small_sell_orders': counts['sell']['small'],
            'mid_sell_orders': counts['sell']['mid'],
            'large_sell_orders': counts['sell']['large'],
            'small_buy_value': round(values['buy']['small'], 2),
            'mid_buy_value': round(values['buy']['mid'], 2),
            'large_buy_value': round(values['buy']['large'], 2),
            'small_sell_value': round(values['sell']['small'], 2),
            'mid_sell_value': round(values['sell']['mid'], 2),
            'large_sell_value': round(values['sell']['large'], 2),
            'total_buy_volume': round(total_buy, 2),
            'total_sell_volume': round(total_sell, 2),
            'buy_sell_diff': round(total_buy - total_sell, 2),
            'total_volume': round(total_volume, 2),
            'net_flow_pct': round(net_flow_pct, 4),
            'buy_sell_ratio': round(buy_sell_ratio, 4),
            'price_change_pct': round(price_change_pct, 2),
            'volatility': round(volatility, 6)
        }

    def create_summary(self):
        symbols = self.fetch_all_symbols()
        print(f"🔍 Analyzing {len(symbols)} symbols on {self.timeframe} timeframe...")

        start_time_ms = self.get_start_time_ms()
        end_time_ms = int(datetime.utcnow().timestamp() * 1000)

        results = []
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {
                executor.submit(self.process_symbol, symbol, start_time_ms, end_time_ms): symbol
                for symbol in symbols
            }
            for i, future in enumerate(as_completed(futures), 1):
                symbol = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"[!] Error processing {symbol}: {e}")
                print(f"[{i}/{len(symbols)}] Processed {symbol}")

        df = pd.DataFrame(results)
        if df.empty:
            print("No data processed.")
            return df

        # Normalize scores (rank percentile)
        df['net_flow_score'] = df['net_flow_pct'].rank(pct=True)
        df['price_change_score'] = df['price_change_pct'].rank(pct=True)
        df['volume_score'] = df['total_volume'].rank(pct=True)
        df['volatility_score'] = 1 - df['volatility'].rank(pct=True)  # less volatility = higher score
        # Balanced buy/sell ratio score, best near 1
        df['balanced_ratio_score'] = 1 - abs(df['buy_sell_ratio'] - 1)
        df['balanced_ratio_score'] = df['balanced_ratio_score'].clip(lower=0)  # no negative scores

        # Combine scores with weights (adjust weights as you want)
        df['sirifi_ranking_score'] = (
            df['net_flow_score'] * 3 +
            df['price_change_score'] * 2 +
            df['volume_score'] * 1.5 +
            df['balanced_ratio_score'] * 2 +
            df['volatility_score'] * 2
        )

        df['rank'] = df['sirifi_ranking_score'].rank(ascending=False).astype(int)
        df = df.sort_values('rank')

        # Select columns to show
        return df[[
            'rank',
            'ticker',
            'current_price',
            'total_sell_volume',
            'total_buy_volume',
            'buy_sell_diff',
            'total_volume',
            'net_flow_pct',
            'buy_sell_ratio',
            'balanced_ratio_score',
            'price_change_pct',
            'volatility',
            'sirifi_ranking_score'
        ]].reset_index(drop=True)


