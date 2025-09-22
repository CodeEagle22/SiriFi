from binance.client import Client
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from itertools import product
import time


class Sirifi_C_Backtester:
    def __init__(self, symbol: str, intervals=None, days: int = 30,
                 fee: float = 0.001, slippage_pct: float = 0.0005,
                 use_rsi: bool = True, use_macd: bool = True,
                 fast_vals=None, slow_vals=None, signal_vals=None,
                 rsi_periods=None, rsi_oversold_vals=None, rsi_overbought_vals=None,
                 stop_loss_vals=None, take_profit_vals=None):
        """
        symbol: trading pair symbol like 'BTCUSDC'
        intervals: list of intervals to test e.g. ['5m','15m','1h','4h']
        days: how many days of historical data to fetch
        fee: trading fee percentage (e.g. 0.001 for 0.1%)
        slippage_pct: slippage percentage on entry/exit prices
        use_rsi: whether to include RSI condition
        use_macd: whether to include MACD condition
        parameter ranges: user can override defaults by passing lists
        """
        if intervals is None:
            intervals = ['15m', '1h', '4h']

        assert isinstance(symbol, str) and symbol.endswith("USDC"), "Symbol must be a valid USDC pair string"
        assert all(i in ['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d'] for i in intervals), \
            "Intervals must be valid Binance intervals"

        self.symbol = symbol
        self.intervals = intervals
        self.days = days
        self.fee = fee
        self.slippage_pct = slippage_pct
        self.use_rsi = use_rsi
        self.use_macd = use_macd

        if not self.use_rsi and not self.use_macd:
            print("⚠️ Both RSI and MACD are disabled. Defaulting to MACD.")
            self.use_macd = True

        # ✅ Default parameter ranges if user doesn't supply their own
        self.fast_vals = fast_vals or [8, 12, 16, 20]
        self.slow_vals = slow_vals or [26, 35, 50]
        self.signal_vals = signal_vals or [6, 9, 12]
        self.rsi_periods = rsi_periods or [10, 14, 20]
        self.rsi_oversold_vals = rsi_oversold_vals or [25, 30, 35]
        self.rsi_overbought_vals = rsi_overbought_vals or [60, 65, 70]
        self.stop_loss_vals = stop_loss_vals or [0.01, 0.02, 0.03]
        self.take_profit_vals = take_profit_vals or [0.01,0.02,0.03,0.04, 0.05,0.06, 0.07,0.08]

        self.client = Client()
        self.best_result = None
        self.best_interval = None
        self.best_result_df = None
        self.data_cache = {}

    def _fetch_data(self, interval):
        """Fetch and cache historical klines from Binance"""
        key = f"{self.symbol}_{interval}"
        if key in self.data_cache:
            return self.data_cache[key]

        start_time = (datetime.utcnow() - timedelta(days=self.days)).strftime('%d %b %Y %H:%M:%S')
        klines = self.client.get_historical_klines(self.symbol, interval, start_time)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        df = df[['timestamp', 'open', 'high', 'low', 'close']]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        df['Returns'] = df['close'].pct_change()
        df.dropna(inplace=True)

        self.data_cache[key] = df
        return df

    def _compute_indicators(self, df, fast, slow, signal, rsi_period):
        """Compute MACD and RSI indicators"""
        if self.use_macd:
            ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal, adjust=False).mean()
            df['MACD'] = macd
            df['Signal'] = signal_line

        if self.use_rsi:
            delta = df['close'].diff()
            gain = delta.clip(lower=0).rolling(window=rsi_period).mean()
            loss = -delta.clip(upper=0).rolling(window=rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            df['RSI'] = rsi

        return df.dropna()

    def _apply_strategy(self, df, rsi_oversold, rsi_overbought, stop_loss_pct, take_profit_pct):
        """Vectorized strategy application"""
        df['Position'] = 0

        # Entry conditions
        if self.use_macd and self.use_rsi:
            df['Entry'] = (df['MACD'] > df['Signal']) & (df['RSI'] < rsi_oversold)
        elif self.use_macd:
            df['Entry'] = df['MACD'] > df['Signal']
        elif self.use_rsi:
            df['Entry'] = df['RSI'] < rsi_oversold
        else:
            df['Entry'] = False

        df['Position'] = df['Entry'].replace(False, np.nan).ffill().fillna(0).astype(int)
        df['Market_Returns'] = df['close'].pct_change().fillna(0)
        df['Strategy_Returns'] = df['Market_Returns'] * df['Position']
        df.loc[df['Entry'], 'Strategy_Returns'] -= (self.fee + self.slippage_pct)

        # Cumulative performance
        df['Cumulative'] = (1 + df['Strategy_Returns']).cumprod()
        df['Peak'] = df['Cumulative'].cummax()
        df['Drawdown'] = df['Cumulative'] / df['Peak'] - 1

        # Exit condition (stop-loss / take-profit)
        df['Exit'] = (df['Drawdown'] <= -stop_loss_pct) | \
                     ((df['Cumulative'] - 1) >= take_profit_pct)
        df.loc[df['Exit'], 'Position'] = 0
        df['Position'] = df['Position'].where(df['Position'].shift().notna(), 0).ffill()
        df['Strategy_Returns'] = df['Market_Returns'] * df['Position']
        df.loc[df['Exit'], 'Strategy_Returns'] -= (self.fee + self.slippage_pct)
        df['Cumulative'] = (1 + df['Strategy_Returns']).cumprod()

        # Metrics
        total_return = df['Cumulative'].iloc[-1] - 1
        max_drawdown = (df['Cumulative'] / df['Cumulative'].cummax() - 1).min()
        std = df['Strategy_Returns'].std()
        sharpe = df['Strategy_Returns'].mean() / std * np.sqrt(24 * 365) if std > 0 else np.nan
        trades = df['Entry'].sum()
        buy_hold_return = df['close'].iloc[-1] / df['close'].iloc[0] - 1

        metrics = {
            'Total Return': total_return * 100,
            'Max Drawdown': max_drawdown * 100,
            'Sharpe Ratio': sharpe,
            'Buy & Hold Return': buy_hold_return * 100,
            'Trades': trades
        }
        return metrics, df

    def _optimize(self):
        """Brute-force optimization over parameter grid"""
        best_result = None
        best_df = None
        best_sharpe = -np.inf
        best_interval = None

        for interval in self.intervals:
            try:
                df_raw = self._fetch_data(interval)
            except Exception as e:
                print(f"Error fetching data for {self.symbol} interval {interval}: {e}")
                continue

            for params in product(self.fast_vals, self.slow_vals, self.signal_vals,
                                  self.rsi_periods, self.rsi_oversold_vals, self.rsi_overbought_vals,
                                  self.stop_loss_vals, self.take_profit_vals):
                fast, slow, signal, rsi_p, rsi_oversold, rsi_overbought, sl, tp = params
                if fast >= slow or rsi_oversold >= rsi_overbought:
                    continue
                try:
                    df = self._compute_indicators(df_raw.copy(), fast, slow, signal, rsi_p)
                    metrics, result_df = self._apply_strategy(df, rsi_oversold, rsi_overbought, sl, tp)
                    if metrics['Sharpe Ratio'] > best_sharpe:
                        best_sharpe = metrics['Sharpe Ratio']
                        best_result = {
                            'Symbol': self.symbol,
                            'Interval': interval,
                            'macd_fast': fast,
                            'macd_slow': slow,
                            'macd_signal': signal,
                            'rsi_period': rsi_p,
                            'rsi_oversold': rsi_oversold,
                            'rsi_overbought': rsi_overbought,
                            'stop_loss': sl,
                            'take_profit': tp,
                            'use_rsi': self.use_rsi,
                            'use_macd': self.use_macd,
                            **metrics
                        }
                        best_df = result_df
                        best_interval = interval
                except Exception:
                    continue

        self.best_result = best_result
        self.best_interval = best_interval
        self.best_result_df = best_df
        return best_result, best_df



##############################################################################################################
import pandas as pd
import numpy as np
import requests
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from datetime import datetime
import time
import html
import os


class Sirifi_C_TradingBot:
    def __init__(self, symbol: str, interval: str, params: dict,
                 api_key: str = None, api_secret: str = None,
                 fee: float = 0.001, slippage_pct: float = 0.0005,
                 enable_telegram: bool = False,
                 telegram_token: str = None, telegram_chat_id: str = None,
                 max_budget: float = 100.0,
                 dry_run: bool = True):

        assert symbol.endswith(('USDT', 'USDC')), "Only USDT or USDC pairs supported"
        self.entry_qty = 0.0
        self.realized_pnl = 0.0

        self.symbol = symbol
        self.interval = interval
        self.params = params
        self.fee = fee
        self.slippage_pct = slippage_pct
        self.allocated_usdc = 0
        self.client = Client(api_key, api_secret)
        self.enable_telegram = enable_telegram
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.position = 0
        self.entry_price = None
        self.max_budget = max_budget
        self.dry_run = dry_run
        self.start_date = datetime.now()
        self.initial_capital = None

    def interval_to_seconds(self):
        unit = self.interval[-1]
        amount = int(self.interval[:-1])
        return {'m': 60, 'h': 3600, 'd': 86400}.get(unit, 3600) * amount

    def fetch_ohlcv(self, lookback=200):
        try:
            klines = self.client.get_klines(symbol=self.symbol, interval=self.interval, limit=lookback)
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('open_time', inplace=True)
            return df
        except Exception as e:
            self.notify(f"⚠️ Failed to fetch OHLCV: {e}")
            return None

    def compute_indicators(self, df):
        ema_fast = df['close'].ewm(span=self.params['macd_fast'], adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.params['macd_slow'], adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=self.params['macd_signal'], adjust=False).mean()

        delta = df['close'].diff()
        gain = delta.clip(lower=0).rolling(window=self.params['rsi_period']).mean()
        loss = -delta.clip(upper=0).rolling(window=self.params['rsi_period']).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        df['MACD'] = macd
        df['Signal'] = signal
        df['RSI'] = rsi
        return df.dropna()

    def notify(self, message: str):
        print(f"[BOT] {message}")
        if not self.enable_telegram:
            return
        message = html.escape(message)
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            'chat_id': self.telegram_chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        try:
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                print(f"Telegram error: {response.text}")
        except Exception as e:
            print(f"Telegram send error: {e}")

    def get_balance(self, asset: str) -> float:
        try:
            balances = self.client.get_account()['balances']
            for b in balances:
                if b['asset'] == asset:
                    return float(b['free'])
            return 0.0
        except Exception as e:
            self.notify(f"⚠️ Balance fetch failed: {e}")
            return 0.0

    def get_price(self) -> float:
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except Exception as e:
            self.notify(f"⚠️ Price fetch failed: {e}")
            return None

    def get_min_notional(self):
        try:
            info = self.client.get_exchange_info()
            for sym in info['symbols']:
                if sym['symbol'] == self.symbol:
                    for f in sym['filters']:
                        if f['filterType'] == 'MIN_NOTIONAL':
                            return float(f['minNotional'])
            return 10
        except Exception as e:
            self.notify(f"⚠️ Failed to get min notional: {e}")
            return 10

    def get_lot_size_info(self):
        try:
            info = self.client.get_exchange_info()
            for sym in info['symbols']:
                if sym['symbol'] == self.symbol:
                    for f in sym['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            return {
                                'stepSize': float(f['stepSize']),
                                'minQty': float(f['minQty']),
                                'maxQty': float(f['maxQty'])
                            }
            return {'stepSize': 0.0001, 'minQty': 0.0001, 'maxQty': 1000000}
        except Exception as e:
            self.notify(f"⚠️ Failed to get LOT_SIZE info: {e}")
            return {'stepSize': 0.0001, 'minQty': 0.0001, 'maxQty': 1000000}

    def round_step_size(self, quantity, step_size):
        precision = int(round(-np.log10(step_size)))
        return round(quantity - (quantity % step_size), precision)

    def place_order(self, side: str, quantity: float):
        if self.dry_run:
            self.notify(f"[DRY RUN] Would place {side} order for {quantity}")
            return {"status": "dry_run", "side": side, "quantity": quantity}

        try:
            order = self.client.create_order(
                symbol=self.symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            return order
        except Exception as e:
            self.notify(f"⚠️ Order error: {e}")
            return None

    def get_portfolio_value(self):
        quote_asset = 'USDC' if 'USDC' in self.symbol else 'USDT'
        base_asset = self.symbol.replace(quote_asset, '')
        quote_balance = self.get_balance(quote_asset)
        base_balance = self.get_balance(base_asset)
        price = self.get_price()
        return quote_balance + base_balance * price if price else 0

    def _sell(self, price, reason):
        base_asset = self.symbol.replace('USDC', '').replace('USDT', '')
        lot_info = self.get_lot_size_info()
        qty = self.round_step_size(self.get_balance(base_asset), lot_info['stepSize'])

        if qty < lot_info['minQty']:
            self.notify(f"⚠️ Cannot sell: Quantity {qty} < minQty {lot_info['minQty']}")
            return

        order = self.place_order(SIDE_SELL, qty)
        if order:
            net_qty = qty * (1 - self.fee)
            realized = (price - self.entry_price) * net_qty
            self.realized_pnl += realized

            self.position = 0
            self.entry_price = None
            self.entry_qty = 0.0
            self.allocated_usdc = 0

            self.notify(f"{reason} - Sold {qty} {base_asset} at ~{price:.4f}. Realized PnL: ${realized:.2f}. Total PnL: ${self.realized_pnl:.2f}")

    def run_loop(self):
        sleep_sec = self.interval_to_seconds()
        self.notify(f"Bot started for {self.symbol} @ {self.interval}. Dry-run={self.dry_run}")
        while True:
            try:
                df = self.fetch_ohlcv()
                if df is None:
                    time.sleep(sleep_sec)
                    continue

                df = self.compute_indicators(df)
                macd = df['MACD'].iloc[-1]
                signal = df['Signal'].iloc[-1]
                rsi = df['RSI'].iloc[-1]
                close = df['close'].iloc[-1]

                if self.initial_capital is None:
                    self.initial_capital = self.get_portfolio_value()

                base_asset = self.symbol.replace('USDC', '').replace('USDT', '')
                quote_asset = 'USDC' if 'USDC' in self.symbol else 'USDT'

                if self.position == 0:
                    enter_macd = (macd > signal) if self.params.get('use_macd', True) else True
                    enter_rsi = (rsi < self.params['rsi_oversold']) if self.params.get('use_rsi', True) else True

                    if enter_macd and enter_rsi:
                        balance = self.get_balance(quote_asset)
                        amount = min(self.max_budget, balance)
                        lot_info = self.get_lot_size_info()
                        qty = self.round_step_size(amount / close, lot_info['stepSize'])

                        if qty < lot_info['minQty']:
                            self.notify(f"Trade skipped: Qty {qty:.6f} < minQty {lot_info['minQty']}")
                        elif qty * close < self.get_min_notional():
                            self.notify(f"Trade skipped: Notional {qty * close:.2f} < minNotional {self.get_min_notional()}")
                        else:
                            order = self.place_order(SIDE_BUY, qty)
                            if order:
                                self.position = 1
                                self.entry_price = close * (1 + self.slippage_pct)
                                self.entry_qty = qty * (1 - self.fee)  # assume fee is deducted
                                self.allocated_usdc = self.entry_price * self.entry_qty
                                self.notify(f"Bought {qty} {base_asset} @ ~{self.entry_price:.4f}. Portfolio: ${self.get_portfolio_value():.2f}")

                else:
                    pnl = (close - self.entry_price) / self.entry_price
                    if pnl <= -self.params['stop_loss']:
                        self._sell(close, "Stop Loss triggered")
                    elif pnl >= self.params['take_profit']:
                        self._sell(close, "Take Profit triggered")

                self.status_report()
            except Exception as e:
                self.notify(f"⚠️ Error in run loop: {e}")
            time.sleep(sleep_sec)

    def status_report(self):
        port_val = self.get_portfolio_value()
        quote_asset = 'USDC' if 'USDC' in self.symbol else 'USDT'
        base_asset = self.symbol.replace(quote_asset, '')
        base_qty = self.get_balance(base_asset)
        quote_qty = self.get_balance(quote_asset)
        price = self.get_price()
        current_value = base_qty * price + quote_qty if price else 0

        #pnl = ((current_value - self.allocated_usdc) / self.allocated_usdc * 100) if self.allocated_usdc > 0 else 0.0

        if self.position == 1 and self.entry_qty > 0:
            current_price = self.get_price()
            unrealized_pnl = ((current_price - self.entry_price) * self.entry_qty) if current_price else 0.0
        else:
            unrealized_pnl = 0.0

        total_pnl = self.realized_pnl + unrealized_pnl

        status = "📈 BUY (Holding)" if self.position == 1 else "⏸️ HOLD (No Position)"

        msg = (
            f"📅 Start: {self.start_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"💰 Max Budget: {self.max_budget:.2f} {quote_asset}\n"
            f"📊 Portfolio Value: {port_val:.2f} {quote_asset}\n"
            f"📈 Realized PnL: {self.realized_pnl:.2f} {quote_asset}\n"
            f"📉 Unrealized PnL: {unrealized_pnl:.2f} {quote_asset}\n"
            f"📊 Total PnL: {total_pnl:.2f} {quote_asset}\n"  # 👈 ADD THIS LINE
            f"📌 Position: {status}\n"
            f"🔹 {base_asset} Balance: {base_qty:.5f}\n"
            f"🔹 {quote_asset} Balance: {quote_qty:.2f}\n"
            f"🔹 Allocated: {self.allocated_usdc:.2f} {quote_asset}\n"
        )
        print("\n===== 📊 BOT STATUS REPORT =====")
        print(msg)
        print("================================\n")

        if self.enable_telegram:
            self.notify(msg)
