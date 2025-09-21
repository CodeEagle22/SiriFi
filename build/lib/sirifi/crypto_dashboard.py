import plotly.graph_objects as go
import pandas as pd

class Sirifi_C_Dashboard:
    """
    A robust interactive dashboard for comparing multiple stocks across various features.
    """

    def __init__(self, results, normalize=True):
        """
        Initialize the dashboard.
        
        Args:
            results (dict): Dictionary of dataframes for each asset, e.g. {"BTC": df_btc, "ETH": df_eth}.
            default_feature (str): Feature to display initially.
            normalize (bool): Whether to normalize values for comparison.
        """
        self.results = results
        self.default_feature = "Open"
        self.normalize = normalize
        self.selected_assets = list(results.keys())
        self.features = ['Open', 'High', 'Low', 'Close', 'Volume', 'pct_return', 'ma_20',
                         'ma_50', 'ma_200', 'ema_12', 'ema_26', 'macd', 'macd_signal',
                         'macd_histogram', 'rsi', 'bollinger_middle', 'bollinger_upper',
                         'bollinger_lower', 'obv', 'roc', 'atr', 'candle_range', 'price_gap',
                         'return_std', 'signal_crossover', 'rsi_signal', 'macd_cross']

    def create_figure(self):
        fig = go.Figure()

        # Add all traces
        for feature in self.features:
            for asset in self.selected_assets:
                df = self.results[asset].copy()
                y = df[feature]
                if self.normalize and feature == self.default_feature:
                    y = y / y.iloc[0] * 100

                visible_flag = True if feature == self.default_feature else False

                fig.add_trace(go.Scatter(
                    x=df["Date"],
                    y=y,
                    mode="lines",
                    name=asset,            # legend shows only asset
                    legendgroup=asset,      # group by asset
                    showlegend=True,        # always show legend
                    visible=visible_flag,
                    hovertemplate='%{x}<br>%{y:.2f}<extra></extra>'
                ))

        # Feature dropdown
        feature_menu = dict(
            buttons=[],
            direction="down",
            showactive=True,
            x=1.02,
            y=1.0,
            xanchor="left",
            yanchor="top",
            pad={"r": 10, "t": 10},
            font=dict(size=12)
        )
        for i, feature in enumerate(self.features):
            visibility = [False] * (len(self.features) * len(self.selected_assets))
            for j in range(len(self.selected_assets)):
                visibility[i*len(self.selected_assets) + j] = True
            feature_menu["buttons"].append(dict(
                label=feature,
                method="update",
                args=[{"visible": visibility},
                      {"title": f"{feature} Comparison Across Assets",
                       "yaxis": {"title": f"{feature} (Indexed)" if self.normalize else feature}}]
            ))

        # Log scale dropdown
        log_menu = dict(
            buttons=[
                dict(label="Linear Scale", method="relayout", args=[{"yaxis.type": "linear"}]),
                dict(label="Log Scale", method="relayout", args=[{"yaxis.type": "log"}])
            ],
            direction="down",
            showactive=True,
            x=1.02,
            y=0.88,
            xanchor="left",
            yanchor="top",
            pad={"r": 10, "t": 10},
            font=dict(size=12)
        )

        # Layout
        fig.update_layout(
            template="plotly_dark",
            title=f"{self.default_feature} Comparison Across Assets",
            xaxis_title="Date",
            yaxis_title=f"{self.default_feature} (Indexed)" if self.normalize else self.default_feature,
            updatemenus=[feature_menu, log_menu],
            hovermode="x unified",
            autosize=True,
            margin=dict(r=160, t=100),
            legend=dict(
                x=1.02,
                y=0.65,  # always below dropdowns
                xanchor="left",
                yanchor="top",
                bgcolor='rgba(0,0,0,0)',
                bordercolor='rgba(255,255,255,0.2)',
                borderwidth=1
            )
        )

        return fig

    def show(self):
        """
        Display the interactive dashboard.
        """
        fig = self.create_figure()
        fig.show()



