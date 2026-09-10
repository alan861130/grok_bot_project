"""Reports: identical section layout in Markdown and HTML."""

from __future__ import annotations

from pathlib import Path
import html

from quantframe.backtest.commission import Commission
from quantframe.backtest.engine import Backtester
from quantframe.metrics.calc import compute_metrics
from quantframe.report.layout import REPORT_SECTIONS, SECTION_IDS
from quantframe.report.render import render_html, render_markdown, write_reports
from quantframe.strategy.sma import SMACrossoverStrategy
from tests.helpers import ScriptedStrategy, trending_ohlcv


def _sample_result():
    bars = trending_ohlcv(periods=40, start_price=20.0, step=0.4)
    engine = Backtester(initial_cash=10_000.0, commission=Commission("bps", 0.0))
    result = engine.run_bars(
        bars=bars,
        strategy=SMACrossoverStrategy(fast=3, slow=8),
        symbol="SYN",
    )
    result.metrics = compute_metrics(result.equity_curve, result.initial_cash, result.round_trips)
    return result


def test_markdown_and_html_share_fixed_sections() -> None:
    result = _sample_result()
    md = render_markdown(result, "2026-01-01 00:00:00 UTC")
    html_doc = render_html(result, "2026-01-01 00:00:00 UTC")
    for _sid, title in REPORT_SECTIONS:
        assert f"## {title}" in md
        assert html.escape(title) in html_doc
    for sid in SECTION_IDS:
        assert f'id="{sid}"' in html_doc
    # Order: each title appears in the same sequence.
    md_pos = [md.index(f"## {title}") for _sid, title in REPORT_SECTIONS]
    assert md_pos == sorted(md_pos)
    html_pos = [html_doc.index(html.escape(title)) for _sid, title in REPORT_SECTIONS]
    assert html_pos == sorted(html_pos)


def test_write_reports_creates_both_files(tmp_path: Path) -> None:
    result = _sample_result()
    md_path, html_path = write_reports(result, tmp_path)
    assert md_path.exists() and html_path.exists()
    assert md_path.name == "sma_crossover_SYN.md"
    assert html_path.name == "sma_crossover_SYN.html"
    assert "Performance Summary" in md_path.read_text(encoding="utf-8")
    assert "<table>" in html_path.read_text(encoding="utf-8")


def test_empty_trade_list_still_renders() -> None:
    bars = trending_ohlcv(periods=5, start_price=10.0, step=0.0)
    # flat signal → no fills
    engine = Backtester(initial_cash=1000.0, commission=Commission("fixed", 1.0))
    result = engine.run_bars(
        bars=bars,
        strategy=ScriptedStrategy([0.0] * 5),
        symbol="FLAT",
    )
    result.metrics = compute_metrics(result.equity_curve, result.initial_cash, result.round_trips)
    md = render_markdown(result, "t")
    assert "no trades" in md
    assert "8. Trade List" in md
