from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
from plotly.subplots import make_subplots

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
USER_AGENT = "Mozilla/5.0 (compatible; stock-compare-app/1.0)"
DEFAULT_PERIOD_DAYS = 31


@dataclass
class StockSnapshot:
    ticker: str
    company_name: str
    sector: str
    industry: str
    prices: pd.DataFrame
    stats: dict[str, float | str]
    vibe: str
    reasons: list[str]


class YahooFinanceError(RuntimeError):
    """Raised when Yahoo Finance returns an unexpected response."""


class StockComparer:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_history(self, ticker: str, period_days: int = DEFAULT_PERIOD_DAYS) -> pd.DataFrame:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=period_days * 2)
        params = {
            "period1": int(start.timestamp()),
            "period2": int(now.timestamp()),
            "interval": "1d",
            "includePrePost": "false",
            "events": "div,splits",
        }
        response = self.session.get(YAHOO_CHART_URL.format(ticker=ticker), params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()

        error = payload.get("chart", {}).get("error")
        if error:
            raise YahooFinanceError(f"{ticker}: {error.get('description', 'Unknown API error')}")

        result = payload.get("chart", {}).get("result")
        if not result:
            raise YahooFinanceError(f"{ticker}: missing historical price data.")

        result0 = result[0]
        timestamps = result0.get("timestamp")
        quotes = result0.get("indicators", {}).get("quote", [])
        if not timestamps or not quotes:
            raise YahooFinanceError(f"{ticker}: incomplete historical payload.")

        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None),
                "close": quotes[0].get("close", []),
            }
        )
        frame = frame.dropna(subset=["close"]).sort_values("date").drop_duplicates(subset=["date"])
        if frame.empty:
            raise YahooFinanceError(f"{ticker}: no usable closing prices were returned.")

        frame = frame.tail(period_days).reset_index(drop=True)
        frame["label"] = frame["date"].dt.strftime("%Y-%m-%d")
        return frame

    def fetch_profile(self, ticker: str) -> dict[str, str]:
        params = {"q": ticker, "quotesCount": 8, "newsCount": 0}
        response = self.session.get(YAHOO_SEARCH_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        quotes = payload.get("quotes", [])
        target = next(
            (item for item in quotes if str(item.get("symbol", "")).upper() == ticker.upper()),
            quotes[0] if quotes else {},
        )
        return {
            "company_name": target.get("longname") or target.get("shortname") or ticker.upper(),
            "sector": target.get("sectorDisp") or target.get("sector") or "未知",
            "industry": target.get("industryDisp") or target.get("industry") or "未知",
        }

    def build_snapshot(self, ticker: str) -> StockSnapshot:
        ticker = ticker.upper().strip()
        prices = self.fetch_history(ticker)
        profile = self.fetch_profile(ticker)
        stats = self.calculate_stats(prices)
        vibe = self.classify_vibe(stats)
        reasons = self.describe_reasons(prices, stats)
        return StockSnapshot(
            ticker=ticker,
            company_name=profile["company_name"],
            sector=profile["sector"],
            industry=profile["industry"],
            prices=prices,
            stats=stats,
            vibe=vibe,
            reasons=reasons,
        )

    @staticmethod
    def calculate_stats(prices: pd.DataFrame) -> dict[str, float | str]:
        closes = prices["close"]
        returns = closes.pct_change().dropna()
        start_price = float(closes.iloc[0])
        end_price = float(closes.iloc[-1])
        max_idx = closes.idxmax()
        min_idx = closes.idxmin()
        annualized_proxy = float(returns.std() * math.sqrt(252) * 100) if not returns.empty else 0.0
        range_pct = ((float(closes.max()) - float(closes.min())) / start_price * 100) if start_price else 0.0
        change_pct = ((end_price - start_price) / start_price * 100) if start_price else 0.0

        return {
            "start_price": start_price,
            "end_price": end_price,
            "change_pct": change_pct,
            "range_pct": range_pct,
            "annualized_vol_pct": annualized_proxy,
            "max_price": float(closes.max()),
            "max_date": prices.loc[max_idx, "label"],
            "min_price": float(closes.min()),
            "min_date": prices.loc[min_idx, "label"],
            "up_days": int((returns > 0).sum()),
            "down_days": int((returns < 0).sum()),
            "flat_days": int((returns == 0).sum()),
        }

    @staticmethod
    def classify_vibe(stats: dict[str, float | str]) -> str:
        vol = float(stats["annualized_vol_pct"])
        move = abs(float(stats["change_pct"]))
        span = float(stats["range_pct"])

        if vol < 18 and span < 8:
            return "平穩偏穩健"
        if vol < 30 and span < 15:
            return "有方向感的溫和波動"
        if vol < 45 and span < 22:
            return "明顯震盪"
        if move > 15 or span > 22:
            return "劇烈波動"
        return "高波動整理"

    @staticmethod
    def describe_reasons(prices: pd.DataFrame, stats: dict[str, float | str]) -> list[str]:
        closes = prices["close"]
        midpoint = len(closes) // 2
        first_half = float(closes.iloc[: midpoint + 1].mean())
        second_half = float(closes.iloc[midpoint:].mean())
        slope = closes.iloc[-1] - closes.iloc[0]
        reasons = []

        if second_half > first_half * 1.03:
            reasons.append("下半月均價高於上半月，代表資金願意追價，趨勢偏多。")
        elif second_half < first_half * 0.97:
            reasons.append("下半月均價低於上半月，代表月中後賣壓較重，趨勢偏空。")
        else:
            reasons.append("上下半月均價接近，顯示市場多空拉鋸，暫時沒有完全壓倒性的趨勢。")

        if abs(slope) < closes.mean() * 0.02:
            reasons.append("月底與月初收盤價差距不大，股價較像區間整理而不是單邊行情。")
        elif slope > 0:
            reasons.append("月末收盤高於月初，代表這一個月整體報酬仍偏正向。")
        else:
            reasons.append("月末收盤低於月初，代表這一個月整體報酬偏負向。")

        reasons.append(
            f"月內最高點出現在 {stats['max_date']}、最低點出現在 {stats['min_date']}，說明事件驅動的情緒轉折很可能集中在特定交易日。"
        )
        return reasons


def create_figure(first: StockSnapshot, second: StockSnapshot, output_path: Path) -> Path:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.16)
    colors = ["#2563eb", "#f97316"]

    for row, stock, color in [(1, first, colors[0]), (2, second, colors[1])]:
        fig.add_trace(
            go.Scatter(
                x=stock.prices["date"],
                y=stock.prices["close"],
                mode="lines+markers+text",
                text=stock.prices["label"],
                textposition="top center",
                line={"color": color, "width": 3},
                marker={"size": 9, "color": color, "line": {"width": 1, "color": "white"}},
                name=f"{stock.ticker} 收盤價",
                hovertemplate="%{text}<br>收盤價: %{y:.2f}<extra></extra>",
            ),
            row=row,
            col=1,
        )

        max_row = stock.prices.loc[stock.prices["close"].idxmax()]
        min_row = stock.prices.loc[stock.prices["close"].idxmin()]
        for point, label, marker_symbol in [
            (max_row, f"最高 {max_row['close']:.2f}", "star"),
            (min_row, f"最低 {min_row['close']:.2f}", "diamond"),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=[point["date"]],
                    y=[point["close"]],
                    mode="markers+text",
                    text=[label],
                    textposition="bottom center",
                    marker={"size": 16, "color": "#111827", "symbol": marker_symbol},
                    showlegend=False,
                    hovertemplate=f"{point['label']}<br>{label}<extra></extra>",
                ),
                row=row,
                col=1,
            )

        fig.update_xaxes(
            row=row,
            col=1,
            tickmode="array",
            tickvals=stock.prices["date"],
            ticktext=stock.prices["label"],
            tickangle=-45,
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.2)",
        )
        fig.update_yaxes(row=row, col=1, title_text="收盤價 (USD)", showgrid=True, gridcolor="rgba(148, 163, 184, 0.2)")

    fig.update_layout(
        title={
            "text": f"{first.ticker} vs {second.ticker} 過去一個月收盤價比較",
            "x": 0.5,
            "font": {"size": 24},
        },
        height=980,
        template="plotly_white",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
        margin={"t": 90, "l": 70, "r": 50, "b": 120},
    )
    fig.add_annotation(
        text="每個交易日都以標記點與日期標籤顯示，最高/最低點額外註記。",
        xref="paper",
        yref="paper",
        x=0.5,
        y=1.08,
        showarrow=False,
        font={"size": 13, "color": "#334155"},
    )

    fig.write_html(output_path, include_plotlyjs="cdn")
    return output_path


def format_stock_report(stock: StockSnapshot) -> str:
    stats = stock.stats
    lines = [
        f"{stock.company_name} ({stock.ticker})",
        f"- 產業資訊：{stock.sector} / {stock.industry}",
        f"- 本月 Vibe：{stock.vibe}",
        f"- 月初收盤：{stats['start_price']:.2f}",
        f"- 月末收盤：{stats['end_price']:.2f}",
        f"- 月漲跌幅：{stats['change_pct']:.2f}%",
        f"- 月內振幅：{stats['range_pct']:.2f}%",
        f"- 波動代理值（年化）：{stats['annualized_vol_pct']:.2f}%",
        f"- 上漲日 / 下跌日 / 持平日：{stats['up_days']} / {stats['down_days']} / {stats['flat_days']}",
        f"- 最高點：{stats['max_price']:.2f} ({stats['max_date']})",
        f"- 最低點：{stats['min_price']:.2f} ({stats['min_date']})",
        "- 趨勢解讀：",
    ]
    lines.extend([f"  - {reason}" for reason in stock.reasons])
    return "\n".join(lines)


def compare_stocks(first: StockSnapshot, second: StockSnapshot) -> str:
    same_sector = first.sector == second.sector and first.sector != "未知"
    same_industry = first.industry == second.industry and first.industry != "未知"
    relation = "同產業" if same_industry else "同大產業" if same_sector else "不同產業"

    change_gap = float(first.stats["change_pct"]) - float(second.stats["change_pct"])
    vol_gap = float(first.stats["annualized_vol_pct"]) - float(second.stats["annualized_vol_pct"])
    stronger = first.ticker if change_gap >= 0 else second.ticker
    steadier = first.ticker if vol_gap <= 0 else second.ticker

    lines = [
        f"兩家公司屬於：{relation}。",
        f"相對強勢的是 {stronger}，因為它本月漲跌幅更高（差距 {abs(change_gap):.2f}%）。",
        f"相對穩定的是 {steadier}，因為它的波動代理值較低（差距 {abs(vol_gap):.2f}%）。",
    ]

    if same_industry or same_sector:
        lines.append(
            "由於兩者所處供應鏈與市場情緒相近，若走勢同步，通常代表資金是在交易共同的產業敘事，例如需求循環、財報預期、或整體風險偏好。"
        )
        if stronger == first.ticker:
            winner, laggard = first, second
        else:
            winner, laggard = second, first
        lines.append(
            f"不過 {winner.ticker} 比 {laggard.ticker} 強，常見原因是市場認為 {winner.company_name} 在產品組合、獲利能力、AI/雲端/資本支出受惠程度，或短線消息面上更有優勢。"
        )
    else:
        lines.append(
            "因為兩家公司並非同產業，背後驅動因素可能不同；若兩者同漲或同跌，更可能反映總體利率、美元、或美股風險偏好的共同影響。"
        )

    if first.vibe == second.vibe:
        lines.append(f"兩檔股票的 Vibe 都偏向「{first.vibe}」，代表市場對它們的定價節奏相近。")
    else:
        lines.append(
            f"Vibe 差異方面，{first.ticker} 偏向「{first.vibe}」，而 {second.ticker} 偏向「{second.vibe}」，這通常代表資金對兩家公司短期敘事的確信度不同。"
        )

    return "\n".join(f"- {line}" for line in lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比較兩家公司過去一個月的收盤價走勢。")
    parser.add_argument("ticker1", nargs="?", help="第一個股票代號，例如 AAPL")
    parser.add_argument("ticker2", nargs="?", help="第二個股票代號，例如 MSFT")
    parser.add_argument(
        "--output",
        default="stock_comparison.html",
        help="輸出的 Plotly HTML 檔案路徑，預設為 stock_comparison.html",
    )
    return parser.parse_args()


def prompt_if_missing(value: str | None, prompt: str) -> str:
    return value if value else input(prompt).strip()


def main() -> None:
    args = parse_args()
    ticker1 = prompt_if_missing(args.ticker1, "請輸入第一個股票代號：")
    ticker2 = prompt_if_missing(args.ticker2, "請輸入第二個股票代號：")

    comparer = StockComparer()
    first = comparer.build_snapshot(ticker1)
    second = comparer.build_snapshot(ticker2)
    output_path = create_figure(first, second, Path(args.output))

    print("=" * 80)
    print("股價分析報告")
    print("=" * 80)
    print(format_stock_report(first))
    print("-" * 80)
    print(format_stock_report(second))
    print("-" * 80)
    print("兩家公司比較")
    print(compare_stocks(first, second))
    print("-" * 80)
    print(f"互動式圖表已輸出至：{output_path.resolve()}")


if __name__ == "__main__":
    main()
