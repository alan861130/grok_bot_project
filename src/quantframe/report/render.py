"""Render a BacktestResult to Markdown and HTML with a fixed section layout."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from quantframe.backtest.result import BacktestResult
from quantframe.metrics.calc import LOCKED_METRIC_KEYS, METRIC_LABELS, format_metric
from quantframe.report.layout import REPORT_SECTIONS

METRIC_ORDER = LOCKED_METRIC_KEYS


def _month_end_equity(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return equity
    for freq in ("ME", "M"):
        try:
            out = equity.resample(freq).last()
            if not out.empty:
                return out
        except ValueError:
            continue
    return equity.iloc[[0, -1]]


def write_reports(result: BacktestResult, output_dir: str | Path) -> tuple[Path, Path]:
    """Write Markdown and HTML reports. Returns ``(md_path, html_path)``."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{result.strategy_name}_portfolio"
    md_path = out / f"{stem}.md"
    html_path = out / f"{stem}.html"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    md_path.write_text(render_markdown(result, generated), encoding="utf-8")
    html_path.write_text(render_html(result, generated), encoding="utf-8")
    return md_path, html_path


def render_markdown(result: BacktestResult, generated: str) -> str:
    ctx = _context(result, generated)
    parts: list[str] = [
        f"# Backtest Report — Portfolio ({result.universe_label})",
        "",
        "Fixed layout (Phase 1). Every run uses the same nine sections below.",
        "",
    ]
    for sid, title in REPORT_SECTIONS:
        parts.append(f"## {title}")
        parts.append("")
        parts.extend(_section_md(sid, ctx))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def render_html(result: BacktestResult, generated: str) -> str:
    ctx = _context(result, generated)
    body: list[str] = []
    for sid, title in REPORT_SECTIONS:
        body.append(f'<section id="{html.escape(sid)}">')
        body.append(f"<h2>{html.escape(title)}</h2>")
        body.extend(_section_html(sid, ctx, result))
        body.append("</section>")

    nav = " · ".join(
        f'<a href="#{html.escape(sid)}">{html.escape(title)}</a>'
        for sid, title in REPORT_SECTIONS
    )
    title = f"Backtest Report — Portfolio ({result.universe_label})"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; max-width: 980px;
           margin: 2rem auto; padding: 0 1.25rem 3rem; line-height: 1.45; }}
    h1 {{ margin-bottom: 0.25rem; }}
    nav {{ font-size: 0.9rem; margin: 1rem 0 2rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1rem; font-size: 0.95rem; }}
    th, td {{ border: 1px solid #8884; padding: 0.35rem 0.55rem; text-align: left; }}
    th {{ background: #8882; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .muted {{ opacity: 0.75; font-size: 0.9rem; }}
    svg.chart {{ width: 100%; height: 220px; background: #8881; border-radius: 6px; }}
    ul {{ margin-top: 0.4rem; }}
    code {{ font-size: 0.92em; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="muted">Fixed layout (Phase 1). Every run uses the same nine sections below.</p>
  <nav>{nav}</nav>
  {"".join(body)}
</body>
</html>
"""


def _context(result: BacktestResult, generated: str) -> dict:
    month_end = _month_end_equity(result.equity_curve)
    peak = result.equity_curve.cummax()
    dd = result.equity_curve / peak - 1.0
    return {
        "result": result,
        "generated": generated,
        "month_end": month_end,
        "drawdown": dd,
    }


def _last_long_set(result: BacktestResult) -> str:
    if result.signals.empty:
        return "(none)"
    row = result.signals.iloc[-1]
    names = [str(c) for c, v in row.items() if bool(v)]
    return ", ".join(f"`{n}`" for n in names) if names else "(flat / cash)"


def _section_md(sid: str, ctx: dict) -> list[str]:
    r: BacktestResult = ctx["result"]
    n_sessions = len(r.equity_curve)
    if sid == "run_metadata":
        return [
            f"- Generated: {ctx['generated']}",
            "- Framework: quantframe 0.1.0 (Phase 1)",
            "- Market: US equities · Bar size: daily OHLCV · Mode: portfolio (equal-weight long set)",
        ]
    if sid == "universe_data":
        lines = [
            f"- Universe: {', '.join(f'`{s}`' for s in r.universe)}",
            f"- Session range (aligned inner join): {r.start.isoformat()} → {r.end.isoformat()}",
            f"- Sessions: {n_sessions}",
            "- Prices: adjusted (splits/dividends) when the data provider supplies them",
            "- Bars per symbol:",
        ]
        for sym, frame in r.bars.items():
            first_c = float(frame["close"].iloc[0])
            last_c = float(frame["close"].iloc[-1])
            lines.append(f"  - `{sym}`: {len(frame)} bars · first close {first_c:.4f} · last close {last_c:.4f}")
        return lines
    if sid == "strategy":
        params = ", ".join(f"{k}={v}" for k, v in r.strategy_params.items()) or "(none)"
        return [
            f"- Name: `{r.strategy_name}`",
            f"- Parameters: {params}",
            "- Signal contract: boolean long set at close t (per symbol SMA golden/death cross).",
            "- Weights: equal-weight the long set (override `generate_target_weights` later for other schemes).",
            f"- Long set on last session: {_last_long_set(r)}",
        ]
    if sid == "settings":
        return [
            f"- Initial cash: ${r.initial_cash:,.2f}",
            f"- Commission: {r.commission.label()}",
            "- Slippage: none (Phase 1; configurable hook defaults to zero)",
            "- Execution: same-session close fill (optimistic)",
            "- Position sizing: whole shares, equal-weight among names currently long; cash when flat",
            "- Shorting: disabled (long / flat only)",
        ]
    if sid == "performance":
        lines = ["| Metric | Value |", "| --- | --- |"]
        for key in METRIC_ORDER:
            if key not in r.metrics:
                continue
            label = METRIC_LABELS.get(key, key)
            lines.append(f"| {label} | {format_metric(key, r.metrics[key])} |")
        return lines
    if sid == "equity_curve":
        eq = r.equity_curve
        lines = [
            f"- Start equity: ${float(eq.iloc[0]):,.2f}",
            f"- End equity: ${float(eq.iloc[-1]):,.2f}",
            f"- Min / max: ${float(eq.min()):,.2f} / ${float(eq.max()):,.2f}",
            "",
            "Month-end equity:",
            "",
            "| Month | Equity |",
            "| --- | ---: |",
        ]
        for ts, val in ctx["month_end"].items():
            month = pd.Timestamp(ts).strftime("%Y-%m")
            lines.append(f"| {month} | ${float(val):,.2f} |")
        return lines
    if sid == "drawdown":
        dd = ctx["drawdown"]
        return [
            f"- Worst drawdown: {format_metric('max_drawdown', r.metrics.get('max_drawdown'))}",
            f"- Peak date: {r.metrics.get('max_drawdown_start') or 'n/a'}",
            f"- Trough date: {r.metrics.get('max_drawdown_end') or 'n/a'}",
            f"- Drawdown at last bar: {float(dd.iloc[-1]):.2%}",
        ]
    if sid == "trades":
        lines = [
            f"Round trips: {len(r.round_trips)} · Fills: {len(r.fills)}",
            "",
            "| Symbol | Entry | Exit | Shares | Entry px | Exit px | PnL | Return | Status |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        if not r.round_trips:
            lines.append("| — | — | — | — | — | — | — | — | no trades |")
        for t in r.round_trips:
            row = t.as_row()
            pnl = format_metric("pnl", row["pnl"])
            ret = format_metric("return_pct", row["return_pct"])
            exit_px = "n/a" if row["exit_price"] is None else f"{row['exit_price']:.4f}"
            lines.append(
                f"| {row['symbol']} | {row['entry_date']} | {row['exit_date'] or '—'} | {row['shares']} | "
                f"{row['entry_price']:.4f} | {exit_px} | {pnl} | {ret} | {row['status']} |"
            )
        lines.extend(["", "Fills (same-session close):", ""])
        lines.extend(
            [
                "| Date | Symbol | Side | Shares | Price | Commission | Cash after | Position after |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        if not r.fills:
            lines.append("| — | — | — | — | — | — | — | — |")
        for f in r.fills:
            lines.append(
                f"| {f.date.date().isoformat()} | {f.symbol} | {f.side} | {f.shares} | "
                f"{f.price:.4f} | ${f.commission:.2f} | ${f.cash_after:,.2f} | {f.position_after} |"
            )
        return lines
    if sid == "assumptions":
        bullets = [f"- {n}" for n in r.notes]
        bullets.extend(
            [
                "- Same-close fills are optimistic: the close used to form the signal is also the fill price.",
                "- Not investment advice. Past backtests do not predict live results.",
                "- Phase 1 has no web dashboard and no live broker / order APIs.",
            ]
        )
        return bullets
    return ["(empty)"]


def _section_html(sid: str, ctx: dict, result: BacktestResult) -> list[str]:
    md_lines = _section_md(sid, ctx)
    if sid == "equity_curve":
        svg = _equity_svg(result.equity_curve)
        listing = _md_list_and_tables_to_html(md_lines)
        return [svg, *listing]
    return _md_list_and_tables_to_html(md_lines)


def _md_list_and_tables_to_html(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("| "):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_md_table_to_html(rows))
            continue
        if line.lstrip().startswith("- "):
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                text = lines[i].lstrip()[2:]
                items.append(f"<li>{_inline_md(text)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if line.strip() == "":
            i += 1
            continue
        out.append(f"<p>{_inline_md(line)}</p>")
        i += 1
    return out


def _inline_md(text: str) -> str:
    """Escape HTML, then turn `backticks` into <code>."""
    escaped = html.escape(text)
    parts = escaped.split("`")
    if len(parts) < 2 or len(parts) % 2 == 0:
        return escaped
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(f"<code>{part}</code>")
        else:
            out.append(part)
    return "".join(out)


def _md_table_to_html(rows: list[str]) -> str:
    parsed = []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        parsed.append(cells)
    if len(parsed) < 2:
        return ""
    header, rest = parsed[0], parsed[2:] if _is_sep(parsed[1]) else parsed[1:]
    thead = "<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in header) + "</tr>"
    body = []
    for r in rest:
        tds = []
        for cell in r:
            cls = " class=\"num\"" if _looks_numeric(cell) else ""
            tds.append(f"<td{cls}>{html.escape(cell)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><thead>{thead}</thead><tbody>{''.join(body)}</tbody></table>"


def _is_sep(cells: list[str]) -> bool:
    return all(set(c.replace(":", "").replace("-", "").replace(" ", "")) == set() for c in cells)


def _looks_numeric(cell: str) -> bool:
    s = cell.replace(",", "").replace("$", "").replace("%", "").replace("—", "").strip()
    if s in {"", "n/a", "-"}:
        return True
    try:
        float(s)
        return True
    except ValueError:
        return False


def _equity_svg(equity: pd.Series) -> str:
    vals = [float(v) for v in equity.tolist()]
    if len(vals) < 2:
        return "<p class=\"muted\">Not enough points to chart.</p>"
    w, h, pad = 900, 200, 16
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)

    def xy(i: int, v: float) -> tuple[float, float]:
        x = pad + (w - 2 * pad) * (i / (n - 1))
        y = pad + (h - 2 * pad) * (1.0 - (v - lo) / span)
        return x, y

    pts = " ".join(f"{xy(i, v)[0]:.1f},{xy(i, v)[1]:.1f}" for i, v in enumerate(vals))
    baseline = pad + (h - 2 * pad)
    return (
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Equity curve">'
        f'<polyline fill="none" stroke="#2f6fed" stroke-width="2" points="{pts}"/>'
        f'<line x1="{pad}" y1="{baseline}" x2="{w - pad}" y2="{baseline}" '
        f'stroke="#8888" stroke-width="1"/>'
        f'<text x="{pad}" y="14" font-size="12" fill="currentColor">'
        f"${hi:,.0f}</text>"
        f'<text x="{pad}" y="{h - 4}" font-size="12" fill="currentColor">'
        f"${lo:,.0f}</text>"
        f"</svg>"
        f'<p class="muted">Equity from ${vals[0]:,.2f} to ${vals[-1]:,.2f} '
        f"(y-axis min/max of the curve).</p>"
    )
