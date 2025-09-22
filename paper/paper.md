---
title: 'Sirifi: Smart Insights & Research in Financial Intelligence'
tags:
  - Python
  - Finance
  - Cryptocurrency
  - Sentiment Analysis
  - Backtesting
  - Automated Trading
  - Value Investing
authors:
  - name: Sagar Narwade
    orcid: 0009-0004-9636-3611
    affiliation: 1
  - name: Rudra Desai
    orcid: 0000-0002-2672-7094
    affiliation: 1
affiliations:
 - name: Independent Researcher
   index: 1
date: 17 September 2025
bibliography: paper.bib
---

# Summary

Sirifi is an integrated Python package for cryptocurrency research, providing a structured workflow from raw market and community data to actionable insights. It supports robust data processing, technical feature generation, value evaluation, sentiment-informed analysis, and algorithmic trading. The package is user-friendly, allowing customizable intervals, historical ranges, data sources, and filters such as minimum market capitalization or symbol limits. Sirifi bridges the gap between academic research and practical trading by combining financial metrics, social sentiment, and automated strategy execution into a single framework.

# Statement of Need

The rapid growth of cryptocurrency markets has created significant opportunities for both research and trading. However, existing tools are often fragmented, requiring users to combine multiple libraries for data collection, feature engineering, backtesting, and automated execution. This increases complexity and can hinder reproducibility. Sirifi addresses this gap by providing a unified framework that integrates data streaming, feature generation, visualization, sentiment analysis, value assessment, backtesting, and trading automation.

By combining technical indicators with social sentiment signals, Sirifi supports systematic evaluation of digital assets. Its modular architecture is designed to accommodate both exploratory research and practical algorithmic trading, providing a versatile platform for quantitative analysis and experimentation.

# Functionality

Sirifi consists of six main components. The **data streaming** module collects historical and real-time data from Binance and Yahoo Finance, allowing users to customize intervals, historical depth, symbols, and filters such as market capitalization and liquidity thresholds. The **feature engineering** module cleans raw data and generates technical indicators including percentage returns, moving averages, RSI, MACD, and Bollinger Bands, which support both research and strategy development (see Figure \ref{fig:feature-engineering-dashboard}). The **dashboard** module provides interactive visualizations for comparing indicators across multiple assets, with options to enable or disable specific symbols and metrics.  

The **value investing** module implements a quantitative framework for evaluating cryptocurrencies using financial metrics such as CAGR, Sharpe ratio, maximum drawdown, liquidity, and contrarian signals, combining them into a composite score to rank assets. The **sentiment analysis** module integrates market data with Reddit posts, classifying content using VADER and combining these sentiment scores with market indicators. Future updates will extend this functionality to include sentiment from X (formerly Twitter) and ValuePickr. Finally, the **backtesting and trading** module evaluates strategies based on RSI and MACD, optimizes parameters for maximum performance, and executes trades on Binance, with support for dry-run simulations and optional Telegram notifications.

# Comparing and Contrasting Available Toolsets

Several existing tools provide valuable functionality but are often specialized and fragmented. For example, CCXT focuses on connecting to exchanges and retrieving market data but lacks feature engineering, sentiment analysis, or backtesting capabilities. TA-Lib offers a comprehensive library of technical indicators, yet users must rely on external tools for data collection, visualization, or trading execution. Backtrader supports backtesting and strategy evaluation but requires manual implementation of feature engineering and sentiment integration. FinRL provides reinforcement learning-based trading strategies but has a steep learning curve and limited support for social sentiment.  

Sirifi distinguishes itself by offering a unified framework that combines data acquisition, feature engineering, visualization, sentiment analysis, value evaluation, backtesting, and automated trading in a single package. It enables interactive exploration of indicators, asset filtering by liquidity or market capitalization, and integration of community sentiment without combining multiple libraries. Multi-threaded computation, dry-run simulations, and Telegram notifications further enhance its practical and research capabilities, positioning Sirifi as a comprehensive platform bridging academic research and real-world trading.

# Figures

![Indicators Dashboard\label{fig:feature-engineering-dashboard}](featureengineering_plot.png)

# Future Plans

Sirifi will be extended beyond cryptocurrencies to support stock markets, including Indian and American equities. Planned enhancements include integration with additional exchanges, sentiment signals from X (formerly Twitter) and ValuePickr, real-time anomaly detection, predictive modeling with machine learning, advanced portfolio optimization, and enhanced risk management frameworks. These improvements aim to make Sirifi a versatile tool for both research and professional trading.

# Acknowledgements

We thank the open-source community for providing tools and APIs that supported this work. The Binance API, Yahoo Finance API, praw, and VADER have been essential for data collection and sentiment analysis.

# References

- Binance API: https://www.binance.com  
- Yahoo Finance: https://finance.yahoo.com  
- Hutto, C.J. & Gilbert, E. (2014). VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text. *Eighth International Conference on Weblogs and Social Media (ICWSM-14)*.  
- Fama, E. F., & French, K. R. (1992). The Cross-Section of Expected Stock Returns. *The Journal of Finance*, 47(2), 427–465.  
- Lupu, R. (2025). Sentiment Matters for Cryptocurrencies: Evidence from Social Media. *Journal of Financial Markets*, 10(4), 50.  
  https://doi.org/10.3390/jfm10040050  
- Jung, H.S. (2025). Detecting Bitcoin Sentiment: Leveraging Language Models. *Journal of Machine Learning in Finance*, 12(2), 134–150.  
  https://doi.org/10.1007/s11063-025-11787-1  
- Mantilla, P. (2023). A Novel Feature Engineering Approach for High-Frequency Financial Data. *Expert Systems with Applications*, 210, 118–130.  
  https://doi.org/10.1016/j.eswa.2022.118130  
- Riabykh, A., & Bessonov, V. (2025). Entropy-based Text Feature Engineering Approach for Financial Market Prediction. *EPJ Data Science*, 14(1), 35–47.  
  https://doi.org/10.1140/epjds/s13688-025-00535-z  
- Saberironaghi, M., Ren, J., & Saberironaghi, A. (2025). Stock Market Prediction Using Machine Learning and Deep Learning Techniques: A Review. *Applied Mathematics*, 5(3), 76.  
  https://doi.org/10.3390/appliedmath5030076  
- Mackey, S. (2025). Backtesting Software Ranked for Retail Quants. *LuxAlgo Blog*.  
  https://www.luxalgo.com/blog/backtesting-software-ranked-for-retail-quants/  
- ValuePickr Community: https://forum.valuepickr.com
