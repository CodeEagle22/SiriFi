

# SIRIFI

Smart Insights & Research for Investments in Financial Instruments


<img src="images/image.png" alt="Logo" height="180" width="180">


## 📋 Summary   

Sirifi is a comprehensive Python package for quantitative analysis of cryptocurrency data. It enables users to extract, clean, and transform raw data from sources such as Yahoo Finance and Binance, followed by advanced feature engineering to generate actionable insights. The package supports data visualization, sentiment analysis, and identification of potentially valuable investment coins using benchmarked analytical tools. While Sirifi provides detailed insights, it is intended for informational purposes only and not as financial advice.

A key feature of Sirifi is its backtesting and trading bot functionality, where users can evaluate strategies on value investment coins or any user-defined cryptocurrencies. Users can incorporate popular indicators such as RSI (Relative Strength Index) and MACD (Moving Average Convergence Divergence), and selectively enable or disable either or both indicators according to their strategy. Based on backtesting results, users can assess the potential of building automated trading bots for Binance or simulate trading with customizable parameters in a demo environment.

Looking ahead, Sirifi will be extended to support stock market data, bringing the same quantitative analysis, backtesting, and trading bot capabilities to equities in addition to cryptocurrencies. Sirifi is a versatile tool for data-driven research, strategy evaluation, and experimental trading across multiple financial markets.

## 📝 How to cite

Narwade, S., Desai, R. (2025), SIRIFI: Smart Insights & Research for Investments in Financial Instruments. Journal of Open Source Software, https://joss.theoj.org/papers/b51be70e9634e45d8035ee20b6147d76.

Markdown:
[![DOI](https://joss.theoj.org/papers/10.21105/joss.06243/status.svg)](https://doi.org/10.21105/joss.06243)

HTML:
<a style="border-width:0" href="https://doi.org/10.21105/joss.06243">
  <img src="https://joss.theoj.org/papers/10.21105/joss.06243/status.svg" alt="DOI badge" >
</a>





## Advisory

- Ensure Python version '>=3.10, <3.11'.
- Utilize IDEs like Visual Studio or platforms like Google Colab for enhanced plot visualization.
- Refer to the provided [sample dataset](https://github.com/CodeEagle22/SIRITVIS/tree/main/sample_dataset) for better comprehension.

## 💡 Features

- Data Streaming 💾
- Data Cleaning 🧹
- Topic Model Training and Evaluation :dart:
- Topic Visual Insights 🔍
- Trending Topic Geo Visualisation 🌏

## 🛠 Installation

Attention: SIRITVIS is specifically tailored for operation on Python 3.10, and its visualization capabilities are optimized for Python notebooks. Extensive testing has been conducted under these specifications. For the best compatibility and performance, we advise setting up a fresh (conda) environment utilizing Python 3.10.10.

The package can be installed via pip:

```bash
pip install sirifi
```

## 👩‍💻 Usage ([documentation])

### Import Libraries

```python
from sirifi import Sirifi_C_DataStreamer
```

### Streaming Raw Data

```python
# Run the streaming process to retrieve raw data based on the specified assets

# Binance → Profile → API Management → Create API → Verify → Copy Key & Secret → Enable “Spot & Margin Trading” (Futures optional, Withdrawals ❌) → (Optional) Restrict IP → Store keys safely.
BINANCE_API_KEY = "XXXXXXXX"
BINANCE_API_SECRET = "XXXXXXXX"

# ✅ Initialize the data fetcher with your Binance API credentials
# First, ensure you have securely loaded your API Key and Secret (e.g., from environment variables or .env file).
fetcher = Sirifi_C_DataStreamer(
    binance_api_key=BINANCE_API_KEY,       # Replace with your actual Binance API Key
    binance_api_secret=BINANCE_API_SECRET  # Replace with your actual Binance API Secret
)

# ✅ Define the list of base assets (cryptocurrencies) you want to fetch data for
# In this example, we are fetching data for Bitcoin (BTC), Ethereum (ETH), Cardano (ADA), Ripple (XRP), and Dogecoin (DOGE).
base_assets = ['BTC', 'ETH', 'ADA', 'XRP', 'DOGE']  

# ✅ Fetch historical OHLCV (Open, High, Low, Close, Volume) data from Binance
results = fetcher.fetch(
    base_assets=base_assets,       # List of coins for which you want to fetch data
    currency='USDC',               # Quote currency: USD stablecoins like USD, USDT, USDC, BUSD, EUR, GBP (can be changed as needed)
    interval='1d',                 # Timeframe for the data: '1m', '5m', '1h', '1d', '1w', etc. ('1d' means daily data)
    source='binance',              # Data source: 'yfinance' & 'binance' means we are pulling data directly from Binance
    start_date='2024-09-01',       # Start date for the data range (format: 'YYYY-MM-DD')
    end_date='2025-09-23'          # End date for the data range (format: 'YYYY-MM-DD')
)

# ✅ Example: Access and print the first few rows of data for BTC and ETH

results['BTC'].head()
results['ETH'].head()


```


### Feature Engineering on Raw Data

```python
# Run the feature engineering process to retrieve more data insights from raw data
# Add up indicators and features
for asset in base_assets:
    sfe = Sirifi_C_FeatureEngineering(results[asset])
    results[asset] = sfe.get_transformed_data()

results['ETH'].head()

''' Columns: 
'Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'pct_return', 'ma_20',
'ma_50', 'ma_200', 'ema_12', 'ema_26', 'macd', 'macd_signal',
'macd_histogram', 'rsi', 'bollinger_middle', 'bollinger_upper',
'bollinger_lower', 'obv', 'roc', 'atr', 'candle_range', 'price_gap',
'return_std', 'signal_crossover', 'rsi_signal', 'macd_cross'
'''

```

### Feature Dash Board

```python

# Robust Plotly Dashboard
# Comparative Interactive Dashboard
dashboard = Sirifi_C_Dashboard(results, normalize=False) # Keep normalisation True for better comparison
dashboard.show()

```

### Feature Sentiment Analysis

```python


# =======================
# Initialize Sentiment Analyzer
# =======================
cs = Sirifi_C_SentimentAnalyzer(
    # Binance API keys for market data access
    # Binance API credentials: used to access Binance account data and market information
    binance_key=BINANCE_API_KEY,
    binance_secret=BINANCE_API_SECRET,
    
    # Reddit credentials to pull social sentiment data
    # Reddit API credentials: used to fetch posts/comments for sentiment analysis
    reddit_id=REDDIT_CLIENT_ID,
    reddit_secret=REDDIT_CLIENT_SECRET,
    reddit_agent=REDDIT_USER_AGENT,
    
    # List of cryptocurrency symbols to analyze (base coins only, no quote currency)
    symbols=['ADA', 'XRP', 'BNB'],  
    
    # Optional: You can set a quote asset, e.g., "USDC", default is "USDT"
    # quote_asset="USDC",
    
    # Filter coins by market cap (or trading volume) to focus on significant coins
    min_marketcap=10_000_000_000,  # 10B USD
    
    # Candlestick interval: "1d" means daily candles
    interval="1d",  
    
    # Limit the number of candles to fetch; 1 here will fetch the most recent candle
    limit=1  
)

# =======================
# Run analysis
# =======================
df = cs.run()  # Executes the sentiment analysis and returns a DataFrame with results

# Display the resulting DataFrame
df


```
### Feature Back Test Trading

```python

import pandas as pd

# Define the trading pairs (symbols) to backtest
symbols = ['LTCUSDC', 'TRXUSDC', 'ENAUSDC']

# Define the candlestick intervals to test strategies on
intervals = ['30m','1h','2h']

# Store best parameter results for each symbol
results = []

for symbol in symbols:
    print(f"\n🔍 Backtesting {symbol}")
    
    # Initialize the backtester for the given symbol
    backtester = Sirifi_C_Backtester(
        symbol=symbol,
        intervals=intervals,   # Multiple timeframes to test
        days=7,                # Lookback period (past 7 days)
        fee=0.001,             # Trading fee (0.1%)
        slippage_pct=0.0005,   # Slippage assumption (0.05%)
        use_rsi=False,         # Disable RSI indicator
        use_macd=True          # Enable MACD indicator
        # 👉 Custom parameter ranges could be added here (e.g. MACD fast/slow periods)
    )

    # Run optimization to find the best-performing parameters
    best_params, df = backtester._optimize()

    if best_params:
        # Save the best parameters for this symbol
        results.append(best_params)
        print(f"✅ Best Params for {symbol}:\n", best_params)
    else:
        # If no profitable strategy is found
        print(f"❌ No valid strategy found for {symbol}")

# Combine all results into a single DataFrame for comparison
results_df = pd.DataFrame(results)
results_df

```
## 📣 Community guidelines

We encourage and welcome contributions to the sirifi package. If you have any questions, want to report bugs, or have ideas for new features, please file an issue. 

Additionally, we appreciate pull requests via GitHub. There are several areas where potential contributions can make a significant impact, such as enhancing the quality of features in topic models when dealing with noisy data from Reddit, Instagram or any external data sources, and improving the topic_mapper function to make it more interactive and independent from the notebook.

## 🖊️ Authors

- Sagar Narwade
- Rudra Desai

## 🎓 References
In our project, we utilised the "OCTIS" [^1^] tool, a fantastic library by Terragni et al., which provided essential functionalities. Additionally, we incorporated the "pyLDAvis" [^2^] by Ben Mabey Python library for interactive topic model visualisation, enriching our application with powerful data insights. The seamless integration of these resources significantly contributed to the project's success, offering an enhanced user experience and valuable research capabilities.

[^1^]: [OCTIS](https://github.com/MIND-Lab/OCTIS).
[^2^]: [pyLDAvis](https://github.com/bmabey/pyLDAvis)

## 📜 License

This project is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0). See the [LICENSE](./LICENSE) file for details.




