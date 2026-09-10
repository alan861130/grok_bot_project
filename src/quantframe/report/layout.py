"""Fixed report section layout (Markdown + HTML share this order)."""

from __future__ import annotations

# Do not reorder: both renderers emit these sections in this sequence every run.
REPORT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("run_metadata", "1. Run Metadata"),
    ("universe_data", "2. Universe & Data"),
    ("strategy", "3. Strategy"),
    ("settings", "4. Backtest Settings"),
    ("performance", "5. Performance Summary"),
    ("equity_curve", "6. Equity Curve"),
    ("drawdown", "7. Drawdown"),
    ("trades", "8. Trade List"),
    ("assumptions", "9. Assumptions & Disclaimers"),
)

SECTION_IDS = tuple(s[0] for s in REPORT_SECTIONS)
