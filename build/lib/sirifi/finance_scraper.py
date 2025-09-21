import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf

class YahooFinanceScraper:
    """
    A class to scrape financial data from Yahoo Finance (via web scraping and yfinance library)
    and process it into a clean DataFrame ready for analysis.

    Attributes:
    -----------
    tickers : list of str
        List of stock ticker symbols to fetch data for.

    Methods:
    --------
    fetch_and_process():
        Fetches financial data for the tickers and returns a processed DataFrame
        containing key financial metrics with the latest date values.
    """

    def __init__(self, tickers):
        """
        Initializes the scraper with a list of ticker symbols.

        Parameters:
        -----------
        tickers : list of str
            List of ticker symbols, e.g., ["AAPL", "MSFT"]

        Raises:
        -------
        AssertionError: If tickers is not a list of strings or is empty.
        """
        assert isinstance(tickers, list), "Tickers must be a list of strings."
        assert all(isinstance(t, str) for t in tickers), "Each ticker must be a string."
        assert len(tickers) > 0, "Tickers list cannot be empty."
        self.tickers = tickers

    def _scrape_yahoo_balance_sheet(self, ticker):
        """Scrape Yahoo Finance balance sheet page for a ticker and return key-value pairs."""
        url = f'https://finance.yahoo.com/quote/{ticker}/balance-sheet?p={ticker}'
        headers = {'User-Agent': "Mozilla/5.0"}
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.content, 'html.parser')
        data = {}
        tables = soup.find_all("div", {"class": "M(0) Whs(n) BdEnd Bdc($seperatorColor) D(itb)"})
        for table in tables:
            rows = table.find_all("div", {"class": "D(tbr) fi-row Bgc($hoverBgColor):h"})
            for row in rows:
                text = row.get_text(separator='|').split("|")
                if len(text) > 1:
                    data[text[0]] = text[1]
        return data

    def _scrape_yahoo_financials(self, ticker):
        """Scrape Yahoo Finance income statement page for a ticker and return key-value pairs."""
        url = f'https://finance.yahoo.com/quote/{ticker}/financials?p={ticker}'
        headers = {'User-Agent': "Mozilla/5.0"}
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.content, 'html.parser')
        data = {}
        tables = soup.find_all("div", {"class": "M(0) Whs(n) BdEnd Bdc($seperatorColor) D(itb)"})
        for table in tables:
            rows = table.find_all("div", {"class": "D(tbr) fi-row Bgc($hoverBgColor):h"})
            for row in rows:
                text = row.get_text(separator='|').split("|")
                if len(text) > 1:
                    data[text[0]] = text[1]
        return data

    def _scrape_yahoo_cashflow(self, ticker):
        """Scrape Yahoo Finance cash flow page for a ticker and return key-value pairs."""
        url = f'https://finance.yahoo.com/quote/{ticker}/cash-flow?p={ticker}'
        headers = {'User-Agent': "Mozilla/5.0"}
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.content, 'html.parser')
        data = {}
        tables = soup.find_all("div", {"class": "M(0) Whs(n) BdEnd Bdc($seperatorColor) D(itb)"})
        for table in tables:
            rows = table.find_all("div", {"class": "D(tbr) fi-row Bgc($hoverBgColor):h"})
            for row in rows:
                text = row.get_text(separator='|').split("|")
                if len(text) > 1:
                    data[text[0]] = text[1]
        return data

    def _scrape_yahoo_key_statistics(self, ticker):
        """Scrape Yahoo Finance key statistics page for a ticker and return key-value pairs."""
        url = f'https://finance.yahoo.com/quote/{ticker}/key-statistics?p={ticker}'
        headers = {'User-Agent': "Mozilla/5.0"}
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.content, 'html.parser')
        data = {}
        tables = soup.findAll("table", {"class": "W(100%) Bdcl(c) "})
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                text = row.get_text(separator='|').split("|")
                if len(text) >= 2:
                    data[text[0]] = text[-1]
        return data

    def _scrape_all(self):
        """Scrape all Yahoo Finance pages and combine data into a dictionary for each ticker."""
        financial_dir = {}
        for ticker in self.tickers:
            temp_dir = {}
            temp_dir.update(self._scrape_yahoo_balance_sheet(ticker))
            temp_dir.update(self._scrape_yahoo_financials(ticker))
            temp_dir.update(self._scrape_yahoo_cashflow(ticker))
            temp_dir.update(self._scrape_yahoo_key_statistics(ticker))
            financial_dir[ticker] = temp_dir
        return financial_dir

    def _clean_scraped_data(self, financial_dir):
        """Convert scraped data dictionary to cleaned pandas DataFrame."""
        combined_financials = pd.DataFrame(financial_dir)
        tickers = combined_financials.columns
        for ticker in tickers:
            combined_financials[ticker] = combined_financials[ticker].astype(str)
            combined_financials = combined_financials[~combined_financials[ticker].str.contains("[a-z]", na=False)]
        return combined_financials

    def _fetch_yfinance_data(self):
        """
        Use yfinance library to fetch financial statements for each ticker
        and combine into a structured DataFrame.
        """
        all_data = []

        for ticker in self.tickers:
            stock = yf.Ticker(ticker)
            statements = {
                "Income Statement": stock.financials,
                "Balance Sheet": stock.balance_sheet,
                "Cash Flow": stock.cashflow
            }

            for statement_type, df in statements.items():
                if df is None or df.empty:
                    continue
                df = df.T  # Dates as rows
                df["Ticker"] = ticker
                df["Statement Type"] = statement_type
                df = df.reset_index().rename(columns={"index": "Date"})
                df = df.melt(id_vars=["Ticker", "Statement Type", "Date"], var_name="Metric", value_name="Value")
                all_data.append(df)

        if all_data:
            financials_df = pd.concat(all_data, ignore_index=True)
            financials_df = financials_df[["Ticker", "Statement Type", "Metric", "Date", "Value"]]
            return financials_df
        else:
            return pd.DataFrame(columns=["Ticker", "Statement Type", "Metric", "Date", "Value"])

    def fetch_and_process(self):
        """
        Main method to fetch and process financial data.

        Returns:
        --------
        pd.DataFrame:
            A processed DataFrame with the latest values for important financial metrics,
            indexed by ticker.

        Steps:
        ------
        1. Fetch financial data via yfinance.
        2. Parse and filter data for latest dates.
        3. Pivot data for easy consumption.
        4. Prioritize important financial metrics.
        """
        # 1. Fetch raw financials using yfinance
        financials_df = self._fetch_yfinance_data()

        if financials_df.empty:
            raise ValueError("No financial data fetched for tickers.")

        # 2. Convert 'Date' to datetime and filter out rows with missing values
        financials_df['Date'] = pd.to_datetime(financials_df['Date'], errors='coerce')
        financials_df = financials_df.dropna(subset=['Date', 'Value'])
        financials_df = financials_df.sort_values('Date')

        # Keep the last/latest entry per Ticker and Metric
        latest_df = financials_df.drop_duplicates(subset=['Ticker', 'Metric'], keep='last')

        # 3. Pivot data to have Metrics as columns
        pivot_df = latest_df.pivot(index='Ticker', columns='Metric', values='Value').reset_index()

        # 4. Define important metrics to prioritize columns
        important_metrics = [
            'Total Revenue',
            'EBITDA',
            'Net Income',
            'Total Assets',
            'Total Liabilities',
            'Operating Income',
            'Cash And Cash Equivalents',
            'Free Cash Flow',
            'Gross Profit',
            'Earnings Per Share',
            'Current Ratio',
            'Return On Equity',
        ]

        actual_metrics = list(pivot_df.columns)
        non_important_metrics = [col for col in actual_metrics if col not in important_metrics and col != 'Ticker']

        # Sort non-important columns by count of non-null values descending (fewest NaNs first)
        non_important_metrics_sorted = sorted(non_important_metrics, key=lambda col: pivot_df[col].isna().sum())

        # Final columns order: Ticker, important_metrics (in order), then rest sorted by NaNs
        final_cols = ['Ticker'] + [m for m in important_metrics if m in pivot_df.columns] + non_important_metrics_sorted
        pivot_df = pivot_df[final_cols]

        return pivot_df

