import pandas as pd
import numpy as np

class FeatureEngineering:
    def __init__(
        self,
        df: pd.DataFrame,
        ma_windows: list[int] = [20, 50, 200],
        ema_windows: list[int] = [12, 26],
        rsi_window: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bollinger_window: int = 20,
        bollinger_std: int = 2,
        roc_window: int = 12,
        atr_window: int = 14,
        std_window: int = 14
    ):
        """
        Initialize the StockFeatureEngineer with stock price data and parameters.

        Args:
            df (pd.DataFrame): DataFrame with columns ['open', 'high', 'low', 'close', 'volume'] and datetime index.
            ma_windows (list[int], optional): Windows for simple moving averages. Defaults to [20, 50, 200].
            ema_windows (list[int], optional): Windows for exponential moving averages. Defaults to [12, 26].
            rsi_window (int, optional): Window size for RSI calculation. Defaults to 14.
            macd_fast (int, optional): Fast EMA period for MACD. Defaults to 12.
            macd_slow (int, optional): Slow EMA period for MACD. Defaults to 26.
            macd_signal (int, optional): Signal line EMA period for MACD. Defaults to 9.
            bollinger_window (int, optional): Window for Bollinger Bands. Defaults to 20.
            bollinger_std (int, optional): Number of standard deviations for Bollinger Bands. Defaults to 2.
            roc_window (int, optional): Window size for Rate of Change. Defaults to 12.
            atr_window (int, optional): Window size for Average True Range. Defaults to 14.
            std_window (int, optional): Window size for rolling std deviation of returns. Defaults to 14.

        Raises:
            AssertionError: If required columns are missing from df.
            AssertionError: If any window or parameter is not a positive integer.
            AssertionError: If bollinger_std is not a positive number.
        """
        # Validate input dataframe columns
        required_cols = {'open', 'high', 'low', 'close', 'volume'}
        assert isinstance(df, pd.DataFrame), "df must be a pandas DataFrame"
        assert required_cols.issubset(df.columns), f"df must contain columns {required_cols}"

        # Validate numeric params
        def check_pos_int(x, name):
            assert isinstance(x, int) and x > 0, f"{name} must be a positive integer"

        def check_pos_float_or_int(x, name):
            assert (isinstance(x, (int, float))) and x > 0, f"{name} must be positive number"

        for window_list, name in [(ma_windows, "ma_windows"), (ema_windows, "ema_windows")]:
            assert isinstance(window_list, list), f"{name} must be a list of positive integers"
            for w in window_list:
                check_pos_int(w, f"Each element of {name}")

        check_pos_int(rsi_window, "rsi_window")
        check_pos_int(macd_fast, "macd_fast")
        check_pos_int(macd_slow, "macd_slow")
        check_pos_int(macd_signal, "macd_signal")
        check_pos_int(bollinger_window, "bollinger_window")
        check_pos_float_or_int(bollinger_std, "bollinger_std")
        check_pos_int(roc_window, "roc_window")
        check_pos_int(atr_window, "atr_window")
        check_pos_int(std_window, "std_window")

        # Save attributes
        self.df = df.copy()
        self.ma_windows = ma_windows
        self.ema_windows = ema_windows
        self.rsi_window = rsi_window
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bollinger_window = bollinger_window
        self.bollinger_std = bollinger_std
        self.roc_window = roc_window
        self.atr_window = atr_window
        self.std_window = std_window

        self._prepare()

    def _prepare(self):
        self.df.sort_index(inplace=True)
        self._calculate_pct_return()
        self._calculate_moving_averages()
        self._calculate_emas()
        self._calculate_macd()
        self._calculate_rsi()
        self._calculate_bollinger_bands()
        self._calculate_obv()
        self._calculate_roc()
        self._calculate_atr()
        self._calculate_other_features()
        self._calculate_signals()

    def _calculate_pct_return(self):
        self.df['pct_return'] = self.df['close'].pct_change()

    def _calculate_moving_averages(self):
        for window in self.ma_windows:
            self.df[f'ma_{window}'] = self.df['close'].rolling(window=window).mean()

    def _calculate_emas(self):
        for window in self.ema_windows:
            self.df[f'ema_{window}'] = self.df['close'].ewm(span=window, adjust=False).mean()

    def _calculate_macd(self):
        ema_fast = self.df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        self.df['macd'] = ema_fast - ema_slow
        self.df['macd_signal'] = self.df['macd'].ewm(span=self.macd_signal, adjust=False).mean()
        self.df['macd_histogram'] = self.df['macd'] - self.df['macd_signal']

    def _calculate_rsi(self):
        delta = self.df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(self.rsi_window).mean()
        avg_loss = loss.rolling(self.rsi_window).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        self.df['rsi'] = 100 - (100 / (1 + rs))

    def _calculate_bollinger_bands(self):
        ma = self.df['close'].rolling(self.bollinger_window).mean()
        std = self.df['close'].rolling(self.bollinger_window).std()
        self.df['bollinger_middle'] = ma
        self.df['bollinger_upper'] = ma + self.bollinger_std * std
        self.df['bollinger_lower'] = ma - self.bollinger_std * std

    def _calculate_obv(self):
        obv = [0]
        for i in range(1, len(self.df)):
            if self.df['close'].iloc[i] > self.df['close'].iloc[i - 1]:
                obv.append(obv[-1] + self.df['volume'].iloc[i])
            elif self.df['close'].iloc[i] < self.df['close'].iloc[i - 1]:
                obv.append(obv[-1] - self.df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        self.df['obv'] = obv

    def _calculate_roc(self):
        self.df['roc'] = self.df['close'].pct_change(periods=self.roc_window)

    def _calculate_atr(self):
        high_low = self.df['high'] - self.df['low']
        high_close = np.abs(self.df['high'] - self.df['close'].shift())
        low_close = np.abs(self.df['low'] - self.df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.df['atr'] = tr.rolling(window=self.atr_window).mean()

    def _calculate_other_features(self):
        self.df['candle_range'] = self.df['high'] - self.df['low']
        self.df['price_gap'] = self.df['open'] - self.df['close'].shift()
        self.df['return_std'] = self.df['pct_return'].rolling(self.std_window).std()

    def _calculate_signals(self):
        self.df['signal_crossover'] = (
            (self.df['macd'] > self.df['macd_signal']) &
            (self.df['macd'].shift() <= self.df['macd_signal'].shift())
        )

        def rsi_label(rsi):
            if rsi > 70:
                return 'overbought'
            elif rsi < 30:
                return 'oversold'
            else:
                return 'neutral'

        self.df['rsi_signal'] = self.df['rsi'].apply(rsi_label)

        macd_cross = []
        for i in range(1, len(self.df)):
            prev_macd = self.df['macd'].iloc[i - 1]
            prev_signal = self.df['macd_signal'].iloc[i - 1]
            curr_macd = self.df['macd'].iloc[i]
            curr_signal = self.df['macd_signal'].iloc[i]

            if prev_macd < prev_signal and curr_macd > curr_signal:
                macd_cross.append('bullish')
            elif prev_macd > prev_signal and curr_macd < curr_signal:
                macd_cross.append('bearish')
            else:
                macd_cross.append('none')

        self.df['macd_cross'] = ['none'] + macd_cross

    def get_transformed_data(self) -> pd.DataFrame:
        """Return the DataFrame enriched with technical indicators."""
        return self.df
