import logging
import time
import requests
import praw
import pandas as pd
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf


# ✅ Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)


class Sirifi_C_SentimentAnalyzer:
    def __init__(self, binance_key: str, binance_secret: str,
                reddit_id: str, reddit_secret: str, reddit_agent: str,
                symbols: list[str] = None,
                min_marketcap: int = 0,
                reddit_limit: int = 25,
                interval: str = "1d",
                limit: int = 1,
                quote_asset: str = "USDC",
                min_agedays: int = 0):
        """
        Crypto Sentiment Analyzer combining Binance, Reddit, and Yahoo Finance.

        Args:
            binance_key (str): Binance API Key. Required for accessing Binance data.
            binance_secret (str): Binance API Secret. Required for accessing Binance data.
            reddit_id (str): Reddit App Client ID for authentication.
            reddit_secret (str): Reddit App Secret Key for authentication.
            reddit_agent (str): Reddit user-agent string (e.g., "my-bot/0.1").
            symbols (list[str], optional): List of cryptocurrency base symbols 
                (e.g., ["ADA", "BNB", "XRP"]). 
                If None, fetches all available trading symbols for the given quote asset. 
                Default is None.
            min_marketcap (int, optional): Minimum market cap filter in USD. 
                Symbols with lower market caps will be excluded. Default is 0 (no filter).
            reddit_limit (int, optional): Number of Reddit posts to analyze per symbol 
                when calculating sentiment. Default is 25.
            interval (str, optional): Binance Kline interval (e.g., "1m", "5m", "1h", "1d"). 
                Default is "1d".
            limit (int, optional): Number of recent candles (klines) to fetch for price data. 
                Default is 1 (most recent).
            quote_asset (str, optional): Base currency for pairs (e.g., "USDT", "USDC"). 
                Default is "USDC".
            min_agedays (int, optional): Minimum coin listing age on Binance (in days). 
                Coins listed more recently than this threshold are excluded. 
                Default is 0 (no filter).
        """

        # ✅ Argument validation
        if not binance_key:
            raise ValueError("Missing required argument: binance_key")
        if not binance_secret:
            raise ValueError("Missing required argument: binance_secret")
        if not reddit_id:
            raise ValueError("Missing required argument: reddit_id")
        if not reddit_secret:
            raise ValueError("Missing required argument: reddit_secret")
        if not reddit_agent:
            raise ValueError("Missing required argument: reddit_agent")

        if not isinstance(min_marketcap, (int, float)) or min_marketcap < 0:
            raise ValueError("min_marketcap must be >= 0")
        if not isinstance(reddit_limit, int) or reddit_limit <= 0:
            raise ValueError("reddit_limit must be > 0")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be > 0")
        if not isinstance(min_agedays, int) or min_agedays < 0:
            raise ValueError("min_agedays must be >= 0")

        # ✅ Assign attributes
        self.binance_key = binance_key
        self.binance_secret = binance_secret
        self.reddit = praw.Reddit(client_id=reddit_id, client_secret=reddit_secret, user_agent=reddit_agent)
        self.analyzer = SentimentIntensityAnalyzer()
        self.symbols = symbols
        self.reddit_limit = reddit_limit
        self.interval = interval
        self.limit = limit
        self.quote_asset = quote_asset
        self.binance_api = "https://api.binance.com"
        self.min_marketcap = min_marketcap
        self.min_agedays = min_agedays

    # ---------------------------- #
    # Safe JSON request (with retries)
    # ---------------------------- #
    def safe_json_request(self, url, params=None, headers=None, retries=3, backoff=2):
        """
        Make a safe JSON request with retry + backoff on failure.
        """
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                logging.error(f"Timeout when calling {url} (attempt {attempt}/{retries})")
            except requests.exceptions.HTTPError as e:
                if attempt == retries:
                    logging.error(f"HTTP Error {e.response.status_code} for {url}")
                else:
                    logging.info(f"Retrying {url} after HTTP error {e.response.status_code}...")
            except requests.exceptions.RequestException as e:
                if attempt == retries:
                    logging.error(f"Request failed: {e}")
                else:
                    logging.info(f"Retrying {url} after error...")

            if attempt < retries:
                time.sleep(backoff ** attempt)

        return None

    # ---------------------------- #
    # Binance helpers
    # ---------------------------- #
    def get_symbols(self):
        """Return all trading symbols for the given quote asset (e.g., ADA, BNB, XRP)."""
        url = f"{self.binance_api}/api/v3/exchangeInfo"
        headers = {'X-MBX-APIKEY': self.binance_key}
        data = self.safe_json_request(url, headers=headers)
        if not data:
            return []
        symbols = []
        for s in data.get('symbols', []):
            if s['quoteAsset'] == self.quote_asset and s['status'] == 'TRADING':
                symbols.append(s['baseAsset'])
        return symbols

    def get_symbol_stats(self, symbol):
        """Fetch OHLCV data for the most recent candle based on interval."""
        symbol_pair = symbol + self.quote_asset
        url = f"{self.binance_api}/api/v3/klines"
        params = {"symbol": symbol_pair, "interval": self.interval, "limit": self.limit}
        headers = {'X-MBX-APIKEY': self.binance_key}
        data = self.safe_json_request(url, params=params, headers=headers)
        if not data:
            return None
        try:
            kline = data[-1]
            open_price = float(kline[1])
            close_price = float(kline[4])
            volume = float(kline[7])  # quote asset volume
            change = ((close_price - open_price) / open_price) * 100
            return {"price": close_price, "change": change, "volume": volume}
        except Exception:
            return None

    def get_age_days(self, symbol):
        """Estimate coin age in days since listing on Binance."""
        symbol_pair = symbol + self.quote_asset
        url = f"{self.binance_api}/api/v3/klines"
        params = {"symbol": symbol_pair, "interval": "1d", "limit": 1, "startTime": 0}
        data = self.safe_json_request(url, params=params)
        if not data:
            return 0
        try:
            first_ts = int(data[0][0]) / 1000
            first_date = datetime.utcfromtimestamp(first_ts)
            return (datetime.utcnow() - first_date).days
        except Exception:
            return 0

    # ---------------------------- #
    # Market cap via yfinance
    # ---------------------------- #
    def get_market_cap_and_supply(self, symbol, price, volume=None, cache={}):
        """
        Get market cap and circulating supply from Yahoo Finance, with silent fallbacks.
        """
        yf_symbol = f"{symbol}-USD"
        market_cap, circulating_supply = 0, 0
        try:
            if yf_symbol not in cache:
                cache[yf_symbol] = yf.Ticker(yf_symbol)
            ticker = cache[yf_symbol]

            fi = getattr(ticker, "fast_info", None)
            if fi:
                market_cap = getattr(fi, "market_cap", 0) or 0
                circulating_supply = getattr(fi, "shares_outstanding", 0) or 0

            if not market_cap or not circulating_supply:
                info = getattr(ticker, "info", {}) or {}
                market_cap = info.get("marketCap") or market_cap
                circulating_supply = info.get("circulatingSupply") or circulating_supply

        except Exception:
            return 0, 0  # ignore Yahoo warnings silently

        # ✅ Fallbacks
        if (not market_cap or not circulating_supply) and price > 0:
            if circulating_supply and not market_cap:
                market_cap = circulating_supply * price
            elif market_cap and not circulating_supply:
                circulating_supply = market_cap / price
            elif volume and volume > 0:
                market_cap = volume * 5
                circulating_supply = market_cap / price if price > 0 else 0

        return round(market_cap, 2), round(circulating_supply, 2)

    # ---------------------------- #
    # Reddit sentiment
    # ---------------------------- #
    def reddit_sentiment(self, symbol):
        scores = []
        try:
            for post in self.reddit.subreddit("CryptoCurrency").search(symbol, limit=self.reddit_limit):
                scores.append(self.analyzer.polarity_scores(post.title + " " + post.selftext)['compound'])
        except Exception:
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
        symbols = self.symbols or self.get_symbols()
        if not symbols:
            logging.error("No symbols found.")
            return pd.DataFrame()

        results = {}
        for s in symbols:
            stats = self.get_symbol_stats(s)
            if not stats:
                continue

            # Market cap & age
            market_cap, circ_supply = self.get_market_cap_and_supply(s, stats["price"], stats["volume"])
            age_days = self.get_age_days(s)

            # Sentiment
            r_score = self.reddit_sentiment(s)

            results[s] = {
                "currentPrice": stats["price"],
                "priceChange": stats["change"],
                "priceSentiment": self.price_sentiment(stats["change"]),
                "redditScore": round(r_score, 3),
                "redditSentiment": self.reddit_category(r_score),
                "marketCap": market_cap,
                "circulatingSupply": circ_supply,
                "tradingVolume": stats["volume"],
                "age_days": age_days,
                "status": "ok" if market_cap > 0 else "yf_failed"
            }

        df = pd.DataFrame.from_dict(results, orient="index").reset_index().rename(columns={"index": "Symbol"})
        df = df[df['marketCap'] > 0]
        df = df[df['marketCap'] > self.min_marketcap]
        df = df[df['age_days'] > self.min_agedays].reset_index(drop=True)
        if not df.empty:
            df = df.sort_values('redditScore', ascending=False).reset_index(drop=True)
        return df
