# quantframe — Phase 1

US equities quantitative trading framework: **daily OHLCV**, research backtests, and fixed-layout reports.

Phase 1 is a Python library + CLI. There is **no web dashboard** and **no live broker / order API**.

---

## English

### What you get

| Piece | Role |
| --- | --- |
| `quantframe.data` | `DataProvider` ABC; default `YFinanceDataProvider` (US daily bars) |
| `quantframe.strategy` | Strategy contract: price history → target weights |
| `quantframe.backtest` | Long/flat engine, next-open fills, cash + commission |
| `quantframe.metrics` | Return, CAGR, Sharpe, max DD, win rate, trade count, … |
| `quantframe.report` | Same result → Markdown **and** HTML, same nine sections every run |
| Sample strategy | SMA crossover (long when fast SMA > slow SMA) |

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

### Run the sample backtest

One command (needs network once, to download SPY via Yahoo Finance):

```bash
quantframe run-sample
```

Equivalent:

```bash
python -m quantframe run-sample
```

This runs **SMA 50/200** on **SPY**, **2019-01-01 → 2024-12-31**, **$100,000** starting cash, **1 bp** commission, and writes:

- `outputs/sma_crossover_SPY.md`
- `outputs/sma_crossover_SPY.html`

`outputs/` is gitignored.

Custom run:

```bash
quantframe backtest \
  --symbol SPY \
  --start 2019-01-01 \
  --end 2024-12-31 \
  --fast 50 \
  --slow 200 \
  --cash 100000 \
  --commission-bps 1 \
  --output-dir outputs
```

Use `--commission-fixed 1` for $1 per fill instead of bps.

### Strategy contract

A strategy maps **already-known** daily bars onto a **target weight** for the symbol:

- Input: OHLCV DataFrame, columns `open, high, low, close, volume`, DatetimeIndex.
- Output: `pd.Series` aligned to that index. Value at `t` uses **only data through the close of bar t**.
- `1.0` = fully long, `0.0` = flat. Phase 1 clips to `[0, 1]` (long-only / long-flat).
- The **engine** fills the signal from bar `t` at the **open of bar t+1** (no same-bar close fill, no look-ahead on the fill price).
- Positions are resized only when the target weight **changes** (all-in / all-out). Whole shares; leftover cash stays in the account.

See `src/quantframe/strategy/base.py` for the full contract.

### Report format (fixed)

Every Markdown and HTML report uses this section order:

1. **Run Metadata** — generated time, framework, market / bar size  
2. **Universe & Data** — symbol, session range, bar count  
3. **Strategy** — name and parameters  
4. **Backtest Settings** — cash, commission, sizing rules  
5. **Performance Summary** — metrics table  
6. **Equity Curve** — stats + month-end equity (HTML adds a simple SVG)  
7. **Drawdown** — max DD and dates  
8. **Trade List** — round trips and next-open fills  
9. **Assumptions & Disclaimers**

### Phase 1 boundaries

**In scope:** US equities, daily bars, research backtests, file reports, one sample SMA strategy, offline unit tests (synthetic data, no network).

**Out of scope (later phases):** localhost / web dashboard, live brokers, order routing, intraday bars, shorting, portfolio of many names, walk-forward / optimizer UI.

Adding a strategy later: implement `Strategy` (`name`, `params()`, `generate_signals(bars)`), then pass it to `Backtester.run` / `run_bars`.

### Tests

```bash
pytest
```

CI / local tests must not call the network. `YFinanceDataProvider` is exercised only by the documented sample command.

---

## 繁體中文（zh-TW）

### 這是什麼

Phase 1 是美股、**日線 OHLCV** 的量化回測骨架：資料層、策略介面、回測引擎、績效指標、固定版型報告，以及一支可跑通的 SMA 交叉範例。

**沒有**網頁儀表板，**沒有**實盤券商 / 下單 API。

### 安裝

需 Python **3.11+**：

```bash
pip install -e .
pip install -e ".[dev]"   # 若要跑測試
pytest
```

### 跑範例回測

```bash
quantframe run-sample
# 或
python -m quantframe run-sample
```

預設：SPY、SMA 50/200、2019-01-01～2024-12-31、本金 10 萬美元、手續費 1 bp。報告寫入：

- `outputs/sma_crossover_SPY.md`
- `outputs/sma_crossover_SPY.html`

（`outputs/` 已加入 `.gitignore`。）

### 策略契約（重點）

- `generate_signals(bars)` 回傳與 K 線對齊的目標權重；**時點 t 只能用到 t 收盤（含）以前的資料**。
- `1.0` = 滿倉做多，`0.0` = 空手。
- 引擎在 **t+1 開盤** 成交 t 收盤的訊號，避免用收盤價當日成交造成的前瞻偏差。
- 權重沒變就持有，不因價格漂移每日再平衡；美股以整股成交。

### 報告版型

每次跑都是同一組九個章節（Markdown / HTML 相同順序）：執行資訊、標的與資料、策略、回測設定、績效摘要、權益曲線、回撤、交易明細、假設與聲明。

### Phase 1 界線

| 有 | 沒有（之後） |
| --- | --- |
| 美股日線、檔案報告、範例 SMA、離線單元測試 | 網頁 dashboard、實盤券商、即時下單、盤中 K 線、放空、多標的組合優化 UI |

之後加策略：實作 `Strategy` 即可接到同一套 `Backtester` 與報告。之後加本機 dashboard 或券商，也不需要改這層契約。
