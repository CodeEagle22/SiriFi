import requests
import praw
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class Sirifi_C_SentimentAnalyzer:
    def __init__(self, binance_key: str, binance_secret: str, reddit_id: str, reddit_secret: str, reddit_agent: str,
                 symbols: list[str] = None, min_marketcap: float = 0.0, reddit_limit: int = 25, interval: str = "1d", limit: int = 1):
        """
        Initialize the Crypto Sentiment Analyzer.

        Args:
            binance_key (str): Binance API Key.
            binance_secret (str): Binance API Secret.
            reddit_id (str): Reddit App Client ID.
            reddit_secret (str): Reddit App Secret Key.
            reddit_agent (str): Reddit user-agent string.
            symbols (list[str], optional): List of Binance trading symbols (e.g., ['ADA', 'XRP', 'BNB']).
            min_marketcap (float, optional): Minimum market cap filter in USD. Default is 0 (no filter).
            reddit_limit (int, optional): Number of Reddit posts to analyze per symbol. Default is 25.
            interval (str, optional): Kline interval (e.g., '1m', '5m', '1h', '1d'). Default is '1d'.
            limit (int, optional): Number of recent candles to fetch. Default is 1 (most recent).
        """
        # ✅ Assertions for type & value validation
        assert isinstance(binance_key, str) and binance_key.strip(), "Binance API key must be a non-empty string."
        assert isinstance(binance_secret, str) and binance_secret.strip(), "Binance API secret must be a non-empty string."
        assert isinstance(reddit_id, str) and reddit_id.strip(), "Reddit client ID must be a non-empty string."
        assert isinstance(reddit_secret, str) and reddit_secret.strip(), "Reddit secret must be a non-empty string."
        assert isinstance(reddit_agent, str) and reddit_agent.strip(), "Reddit user-agent must be a non-empty string."
        assert symbols is None or (isinstance(symbols, list) and all(isinstance(s, str) for s in symbols)), \
            "symbols must be a list of strings or None. Example: ['ADA', 'XRP', 'BNB']"
        assert isinstance(min_marketcap, (int, float)) and min_marketcap >= 0, \
            "min_marketcap must be a non-negative number. Example: 100000000 for $100M"
        assert isinstance(reddit_limit, int) and reddit_limit > 0, \
            "reddit_limit must be a positive integer. Example: 25"
        valid_intervals = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}
        assert isinstance(interval, str) and interval in valid_intervals, \
            f"interval must be a valid Binance interval. Example: '1d', '1h'. Valid options: {sorted(valid_intervals)}"
        assert isinstance(limit, int) and 1 <= limit <= 1000, \
            "limit must be an integer between 1 and 1000 (Binance max limit)."

        # ✅ Assign attributes
        self.binance_key = binance_key
        self.binance_secret = binance_secret
        self.reddit = praw.Reddit(client_id=reddit_id, client_secret=reddit_secret, user_agent=reddit_agent)
        self.analyzer = SentimentIntensityAnalyzer()
        self.symbols = symbols
        self.min_marketcap = min_marketcap
        self.reddit_limit = reddit_limit
        self.interval = interval
        self.limit = limit
        self.binance_api = "https://api.binance.com"
        self.base_currency = 'USDC'  # You can change this to any base currency (e.g., 'USDT', 'BTC')

    # ---------------------------- #
    # Safe JSON request
    # ---------------------------- #
    def safe_json_request(self, url, params=None, headers=None):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None
        except ValueError as e:
            print(f"Failed to parse JSON from {url}: {e}")
            return None

    # ---------------------------- #
    # Binance helpers
    # ---------------------------- #
    def get_usdc_symbols(self):
        """ Returns a list of USDC pairs (like ADAUSDC, XRPUSDC, etc.) """
        url = f"{self.binance_api}/api/v3/exchangeInfo"
        headers = {'X-MBX-APIKEY': self.binance_key}
        data = self.safe_json_request(url, headers=headers)
        if not data:
            return []
        return [s['symbol'] for s in data.get('symbols', []) if s['quoteAsset'] == self.base_currency and s['status'] == 'TRADING']

    def get_market_caps(self):
        """ Fetch market caps (where Binance provides circulating supply), fallback None. """
        url = "https://www.binance.com/bapi/asset/v2/public/asset-service/product/get-products"
        headers = {"User-Agent": "Mozilla/5.0"}
        data = self.safe_json_request(url, headers=headers)
        caps = {}
        if not data or "data" not in data:
            print("Failed to fetch market caps from Binance. Will fallback to trading volume.")
            return {s: None for s in self.symbols or self.get_usdc_symbols()}
        for item in data["data"]:
            symbol = item.get("s")
            try:
                price = float(item.get("c", 0))
                circ_supply = float(item.get("cs", 0))
                caps[symbol] = price * circ_supply if price and circ_supply else None
            except:
                caps[symbol] = None
        return caps

    def get_symbol_stats(self, symbol):
        """ Fetch OHLCV data for the most recent candle based on interval. """
        symbol_pair = symbol + self.base_currency  # Add the base currency to the symbol (e.g., ADA + USDC = ADAUSDC)
        url = f"{self.binance_api}/api/v3/klines"
        params = {"symbol": symbol_pair, "interval": self.interval, "limit": self.limit}
        headers = {'X-MBX-APIKEY': self.binance_key}
        data = self.safe_json_request(url, params=params, headers=headers)
        if not data:
            return None
        try:
            kline = data[-1]  # most recent candle
            open_price = float(kline[1])
            close_price = float(kline[4])
            volume = float(kline[7])  # quote asset volume (USDC)
            change = ((close_price - open_price) / open_price) * 100
            return {"price": close_price, "change": change, "volume": volume}
        except:
            return None

    # ---------------------------- #
    # Reddit sentiment
    # ---------------------------- #
    def reddit_sentiment(self, symbol):
        query = symbol  # Reddit search is based on the symbol itself (e.g., 'ADA', 'XRP')
        scores = []
        try:
            for post in self.reddit.subreddit("CryptoCurrency").search(query, limit=self.reddit_limit):
                scores.append(self.analyzer.polarity_scores(post.title + " " + post.selftext)['compound'])
        except Exception as e:
            print(f"Reddit error for {symbol}: {e}")
            return 0
        return sum(scores) / len(scores) if scores else 0

    @staticmethod
    def price_sentiment(change):
        if change > 1:
            return "Positive"
        elif change < -1:
            return "Negative"
        else:
            return "Neutral"

    @staticmethod
    def reddit_category(score):
        if score > 0.2:
            return "Positive"
        elif score < -0.2:
            return "Negative"
        else:
            return "Neutral"

    # ---------------------------- #
    # Main analysis
    # ---------------------------- #
    def run(self):
        symbols = self.symbols or self.get_usdc_symbols()
        if not symbols:
            print("No symbols found.")
            return pd.DataFrame()
        caps = self.get_market_caps()
        results = {}
        for s in symbols:
            stats = self.get_symbol_stats(s)
            if not stats:
                continue
            market_cap = caps.get(s + self.base_currency)
            size_value = market_cap if market_cap else stats["volume"]
            # Apply min_marketcap filter
            if self.min_marketcap > 0 and (size_value is None or size_value < self.min_marketcap):
                continue
            r_score = self.reddit_sentiment(s)
            results[s] = {
                "currentPrice": stats["price"],
                "priceChange": stats["change"],
                "priceSentiment": self.price_sentiment(stats["change"]),
                "redditScore": round(r_score, 3),
                "redditSentiment": self.reddit_category(r_score),
                "marketCap": size_value,
                "tradingVolume": stats["volume"]
            }
        df = pd.DataFrame.from_dict(results, orient="index").reset_index().rename(columns={"index": "Symbol"})
        df = df.sort_values('redditScore', ascending=False).reset_index(drop=True)
        return df


