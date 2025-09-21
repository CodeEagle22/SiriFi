import numpy as np
import pandas as pd
import yfinance as yf

class ValueInvestorStock:
    """
    A class to fetch financial data and compute a value investment ranking
    based on various financial metrics like Free Cash Flow, Net Income, PE Ratio, ROE, and Debt/Assets.
    """

    def __init__(self, tickers):
        assert isinstance(tickers, list) and tickers, "Tickers must be a non-empty list of strings."
        self.tickers = tickers

    def fetch_financial_statements(self):
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

                df = df.T  # Transpose to have dates as rows
                df["Ticker"] = ticker
                df["Statement Type"] = statement_type
                df = df.reset_index().rename(columns={"index": "Date"})
                df = df.melt(id_vars=["Ticker", "Statement Type", "Date"],
                             var_name="Metric", value_name="Value")
                all_data.append(df)

        if not all_data:
            raise ValueError("No financial data fetched.")

        combined = pd.concat(all_data, ignore_index=True)
        combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce")

        latest_df = (
            combined.dropna(subset=["Value", "Date"])
            .sort_values("Date")
            .drop_duplicates(subset=["Ticker", "Metric"], keep="last")
        )

        pivot_df = latest_df.pivot(index="Ticker", columns="Metric", values="Value").reset_index()
        return pivot_df

    def add_pe_roe(self, df):
        pe_ratios = []
        roes = []

        for ticker in df["Ticker"]:
            info = yf.Ticker(ticker).info
            pe = info.get("trailingPE", np.nan)
            roe = info.get("returnOnEquity", np.nan)
            if pd.notnull(roe):
                roe = roe * 100  # Convert to percent
            pe_ratios.append(pe)
            roes.append(roe)

        df["PE Ratio"] = pe_ratios
        df["Return On Equity"] = roes
        return df

    def compute_debt_assets(self, df):
        liabilities_col = None

        if "Total Liabilities" in df.columns:
            liabilities_col = "Total Liabilities"
        elif "Total Liab" in df.columns:
            liabilities_col = "Total Liab"

        if liabilities_col and "Total Assets" in df.columns:
            df["Debt/Assets"] = df[liabilities_col] / df["Total Assets"]
        else:
            df["Debt/Assets"] = np.nan
        return df

    def calculate_value_rank(self, df):
        # Your original value rank method using multiple metrics
        value_metrics = [
            "Net Income",
            "Free Cash Flow",
            "Operating Income",
            "Cash And Cash Equivalents",
            "Gross Profit"
        ]

        available_metrics = [metric for metric in value_metrics if metric in df.columns]

        if not available_metrics:
            raise ValueError("None of the value metrics were found in the DataFrame.")

        df_rank = df.copy()

        for metric in available_metrics:
            df_rank[metric] = df_rank[metric].fillna(-np.inf)
            df_rank[f"{metric}_rank"] = df_rank[metric].rank(ascending=False, method="min")

        rank_cols = [f"{metric}_rank" for metric in available_metrics]
        df_rank["value_rank"] = df_rank[rank_cols].sum(axis=1)

        # Invert rank so highest score = best
        df_rank["value_rank"] = df_rank["value_rank"].max() - df_rank["value_rank"] + 1

        return df_rank

    def calculate_magic_formula(self, df):
        """
        Implements Joel Greenblatt's Magic Formula:
        Rank companies by Earnings Yield and Return on Capital (ROIC), then sum ranks.
        """

        df_magic = df.copy()

        ev = []
        ey = []
        roic = []

        for _, row in df_magic.iterrows():
            ticker = row["Ticker"]
            info = yf.Ticker(ticker).info
            market_cap = info.get("marketCap", np.nan)

            # Handle total debt with multiple column options
            total_debt = np.nan
            for col_name in ["Total Debt", "Total Liabilities", "Total Liab"]:
                if col_name in df_magic.columns:
                    total_debt = row.get(col_name, np.nan)
                    if pd.notna(total_debt):
                        break
            if pd.isna(total_debt):
                total_debt = 0

            cash = row.get("Cash And Cash Equivalents", 0)
            ebit = row.get("Operating Income", np.nan)

            enterprise_value = np.nan
            if pd.notna(market_cap) and pd.notna(cash):
                enterprise_value = market_cap + total_debt - cash

            ey_val = np.nan
            if pd.notna(ebit) and pd.notna(enterprise_value) and enterprise_value != 0:
                ey_val = ebit / enterprise_value
            ey.append(ey_val)

            total_assets = row.get("Total Assets", np.nan)

            # Try multiple possible column names for current liabilities:
            current_liabilities = np.nan
            for col_name in ["Total Current Liabilities", "Total Current Liab", "Current Liabilities"]:
                if col_name in df_magic.columns:
                    current_liabilities = row.get(col_name, np.nan)
                    if pd.notna(current_liabilities):
                        break

            invested_capital = np.nan
            if pd.notna(total_assets) and pd.notna(current_liabilities):
                invested_capital = total_assets - current_liabilities

            roic_val = np.nan
            if pd.notna(ebit) and pd.notna(invested_capital) and invested_capital != 0:
                roic_val = ebit / invested_capital
            roic.append(roic_val)

            ev.append(enterprise_value)

        df_magic["Earnings Yield"] = ey
        df_magic["ROIC"] = roic
        df_magic["Enterprise Value"] = ev

        df_magic["EY_rank"] = df_magic["Earnings Yield"].rank(ascending=False, method="min")
        df_magic["ROIC_rank"] = df_magic["ROIC"].rank(ascending=False, method="min")

        df_magic["value_rank"] = df_magic["EY_rank"] + df_magic["ROIC_rank"]
        df_magic["value_rank"] = df_magic["value_rank"].max() - df_magic["value_rank"] + 1

        cols = [
            "Ticker", "value_rank", "ROIC", "Earnings Yield", "ROIC_rank", "EY_rank",
            "Enterprise Value", "Operating Income", "Total Assets", "Cash And Cash Equivalents"
        ]

        # Only keep columns that exist in df_magic
        cols = [c for c in cols if c in df_magic.columns]

        return df_magic[cols]

    def rank(self, formula="value_rank"):
        """
        Rank tickers by selected formula.
        formula options:
          - "value_rank" : your original multi-metric value rank
          - "magic_formula" : Joel Greenblatt's Magic Formula (ROIC + Earnings Yield)
        """
        df = self.fetch_financial_statements()
        df = self.add_pe_roe(df)
        df = self.compute_debt_assets(df)

        if formula == "value_rank":
            df = self.calculate_value_rank(df)
            display_cols = [
                "Ticker", "value_rank", "Net Income", "Free Cash Flow", "Operating Income",
                "Cash And Cash Equivalents", "Gross Profit", "PE Ratio", "Return On Equity"
            ]
            df = df.sort_values("value_rank").reset_index(drop=True)
            return df[display_cols]

        elif formula == "magic_formula":
            return self.calculate_magic_formula(df).sort_values("value_rank").reset_index(drop=True)

        else:
            raise ValueError(f"Unknown formula '{formula}'. Choose 'value_rank' or 'magic_formula'.")

# ==============================
# ✅ USAGE
# ==============================

