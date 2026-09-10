# quantframe — Phase 1

US equities quantitative trading framework: **daily OHLCV**, **portfolio** backtests, and fixed-layout reports.

Phase 1 is a Python library + CLI. There is **no web dashboard** and **no live broker / order API**.

---

## English

### What you get

| Piece | Role |
| --- | --- |
| `quantframe.data` | `DataProvider` ABC; default `YFinanceDataProvider` (US daily **adjusted** bars, **multi-ticker** universes) |
| `quantframe.strategy` | Long-set contract (dates × symbols) → default **equal-weight**; overridable target weights later |
| `quantframe.backtest` | True **portfolio** engine: equal-weight names currently long, cash when flat |
| `quantframe.metrics` | Locked set: total return, CAGR, Sharpe, max drawdown, win rate, trade count, ending equity, time-in-market / exposure |
| `quantframe.report` | Same result → Markdown **and** HTML, same nine sections every run |
| Demo strategy | Multi-asset SMA crossover (golden cross → include, death cross → drop) |

### Install

Python **3.11+**. From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
# tests:
pip install -e ".[dev]"
pytest
```

### Run the demo portfolio backtest

One command (needs network once, to download the universe via Yahoo Finance):

```bash
quantframe run-sample
```

Equivalent:

```bash
python -m quantframe run-sample
```

Defaults:

| Setting | Value |
| --- | --- |
| Universe | `SPY, QQQ, AAPL, MSFT, GOOGL` |
| Strategy | SMA crossover **20 / 50** per name |
| Lookback | about the **last 5 years** (from the run date) |
| Initial cash | **100,000 USD** |
| Commission | **5 bps** of traded notional |
| Slippage | **none** (hook exists, default is zero) |
| Execution | **same-session close** (optimistic — see below) |

Writes:

- `outputs/sma_crossover_portfolio.md`
- `outputs/sma_crossover_portfolio.html`

`outputs/` is gitignored.

Custom run:

```bash
quantframe backtest \
  --universe SPY,QQQ,AAPL,MSFT,GOOGL \
  --start 2021-09-10 \
  --end 2026-09-10 \
  --fast 20 \
  --slow 50 \
  --cash 100000 \
  --commission-bps 5 \
  --output-dir outputs
```

### Strategy contract

A strategy maps a **universe** of daily bars onto a **long set**:

- Input: `dict[symbol, OHLCV DataFrame]` (columns `open, high, low, close, volume`).
- `generate_signals(bars)` → boolean `DataFrame` (index = sessions, columns = symbols). Value at `(t, symbol)` uses **only data through the close of bar t**. `True` = include in the long set.
- `generate_target_weights(bars)` — **default** equal-weights the long set (row sums to 1, or 0 = 100% cash). Later strategies can **override this method** for non-equal target weights without changing the engine.
- Phase 1 is **long-only / flat** (no shorting).

The engine rebalances when the target-weight vector **changes** (for the demo SMA, that is a membership change). Whole shares; leftover cash stays in the account. Universe calendars are **inner-joined**.

See `src/quantframe/strategy/base.py`.

### Execution assumption (important)

Fills use the **same day's close** as the signal. That is **optimistic**: in live trading you generally cannot compute a close-based signal and still transact at that close. There is **no slippage model** in Phase 1.

Prices from the default provider are **adjusted** (`yfinance` `auto_adjust=True`).

### Report format (fixed)

Every Markdown and HTML report uses this section order:

1. **Run Metadata**
2. **Universe & Data**
3. **Strategy**
4. **Backtest Settings**
5. **Performance Summary** (locked metric set)
6. **Equity Curve**
7. **Drawdown**
8. **Trade List**
9. **Assumptions & Disclaimers**

### Phase 1 boundaries

**In scope:** US equities, daily bars, multi-name equal-weight portfolio backtests, file reports, SMA 20/50 demo, offline unit tests (synthetic data, no network).

**Out of scope (later phases):** localhost / web dashboard, live brokers, order routing, intraday bars, shorting, slippage calibration, walk-forward / optimizer UI.

Adding a long-set strategy: implement `Strategy.generate_signals`. Adding a target-weight strategy later: override `generate_target_weights`.

### Tests

```bash
pytest
```

CI / local tests must not call the network. `YFinanceDataProvider` is exercised only by the documented sample command.

---

## 繁體中文（zh-TW）

### 這是什麼

Phase 1 是美股、**日線 OHLCV** 的**投資組合**量化回測骨架：抽象資料層（預設 yfinance、**還原權息價**、支援**多標的宇宙**）、策略介面（多空集合 / 之後可改目標權重）、等權長倉組合引擎、固定指標、固定版型 Markdown + HTML 報告，以及 SMA 20/50 多資產範例。

**沒有**網頁儀表板，**沒有**實盤券商 / 下單 API。

### 安裝

需 Python **3.11+**：

```bash
pip install -e .
pip install -e ".[dev]"   # 若要跑測試
pytest
```

### 跑範例組合回測

```bash
quantframe run-sample
# 或
python -m quantframe run-sample
```

預設宇宙：`SPY, QQQ, AAPL, MSFT, GOOGL`；每股 SMA **20/50**（金叉納入、死叉剔除）；約**近 5 年**；本金 **10 萬美元**；手續費 **5 bps**；**無滑價模型**。報告：

- `outputs/sma_crossover_portfolio.md`
- `outputs/sma_crossover_portfolio.html`

### 策略契約（重點）

- `generate_signals(bars)` 回傳「日期 × 標的」的布林 **long set**；**時點 t 只能用到該標的 t 收盤（含）以前的資料**。
- 引擎對當日 long set **等權**；集合為空則 100% 現金。之後若要自訂權重，覆寫 `generate_target_weights` 即可。
- 成交價為**當日收盤**（偏樂觀，README / 報告會註明）。不做空。

### 報告版型

每次跑都是同一組九個章節（Markdown / HTML 相同順序）：執行資訊、宇宙與資料、策略、回測設定、績效摘要、權益曲線、回撤、交易明細、假設與聲明。

績效摘要的固定欄位：總報酬、CAGR、Sharpe、最大回撤、勝率、交易次數、期末權益、在場時間 / 曝險。

### Phase 1 界線

| 有 | 沒有（之後） |
| --- | --- |
| 美股日線、多標的等權組合、檔案報告、SMA 20/50 範例、離線單元測試 | 網頁 dashboard、實盤券商、即時下單、盤中 K 線、放空、滑價校準 |
