---
name: dsa
description: Chinese A-shares stock analysis with AI insights. Analyze trends, quotes, patterns, news, and generate comprehensive AI-powered analysis reports for stocks like 茅台 (600519), 平安银行 (000001), etc.
homepage: https://github.com/Zhangbu/daily_stock_analysis
metadata:
  {
    "openclaw":
      {
        "emoji": "📈",
        "requires": { "bins": ["dsa-cli"] }
      }
  }
---

# Daily Stock Analysis (DSA)

A comprehensive A-share stock analysis tool with AI-powered insights.

## When to use (trigger phrases)

Use this skill immediately when the user asks any of:

- "分析茅台" / "分析 600519" — Full AI analysis
- "茅台现在多少钱" / "600519 行情" — Real-time quote
- "茅台走势怎么样" / "600519 趋势分析" — Technical trend analysis
- "茅台有什么新闻" / "600519 新闻" — Stock news search
- "分析 600519,000858" — Batch analysis (multiple stocks)
- "600519 的均线" / "茅台 MA" — Moving average analysis
- "600519 成交量" / "茅台量能" — Volume analysis
- "600519 支撑位阻力位" — Support/resistance levels
- "600519 K线形态" — K-line pattern recognition

## Commands

### Full AI Analysis (Recommended)

```bash
dsa-cli analyze <stock_code> --json
```

Returns comprehensive AI analysis including:
- Sentiment score (0-100)
- Operation advice (买入/观望/卖出)
- Trend prediction
- Strategy (buy points, stop loss, take profit)
- Detailed analysis summary

Example:
```bash
dsa-cli analyze 600519 --json
```

### Real-time Quote

```bash
dsa-cli quote <stock_code> --json
```

Returns current price, change %, volume, turnover rate.

Example:
```bash
dsa-cli quote 600519 --json
```

### Technical Trend Analysis

```bash
dsa-cli trend <stock_code> --json
```

Returns:
- Trend status (上涨趋势/下跌趋势/震荡整理)
- MA alignment (多头排列/空头排列)
- MACD status and signal
- RSI levels
- Buy/sell signal with score

Example:
```bash
dsa-cli trend 600519 --json
```

### Stock News Search

```bash
dsa-cli news <stock_code> --json --days 7
```

Returns recent news articles about the stock.

Example:
```bash
dsa-cli news 600519 --json --days 7
```

### Moving Average Analysis

```bash
dsa-cli ma <stock_code> --json
```

Returns MA5/MA10/MA20/MA60/MA120/MA250 values with bias percentages.

Example:
```bash
dsa-cli ma 600519 --json
```

### K-line Pattern Recognition

```bash
dsa-cli pattern <stock_code> --json
```

Detects patterns like:
- Doji (十字星)
- Hammer (锤子线)
- Morning/Evening Star (早晨之星/黄昏之星)
- Engulfing (吞没形态)
- Double Bottom (双底)
- Box oscillation (箱体震荡)

Example:
```bash
dsa-cli pattern 600519 --json
```

### Volume-Price Analysis

```bash
dsa-cli volume <stock_code> --json
```

Analyzes volume-price relationship, detecting distribution/accumulation phases.

Example:
```bash
dsa-cli volume 600519 --json
```

### Support/Resistance Levels

```bash
dsa-cli levels <stock_code> --json
```

Returns probability-based support and resistance levels.

Example:
```bash
dsa-cli levels 600519 --json
```

### Batch Analysis

```bash
dsa-cli batch <stock_codes> --json
```

Analyze multiple stocks at once (comma-separated).

Example:
```bash
dsa-cli batch 600519,000858,000001 --json
```

## Output Modes

- `--json` — Structured JSON output (recommended for OpenClaw)
- `--brief` — Brief output for reduced token consumption
- (default) — Human-readable detailed output

## Stock Code Format

Supports both numeric and letter codes:
- A-shares: `600519`, `000001`, `300750`
- US stocks: `AAPL`, `TSLA`, `NVDA`
- Hong Kong stocks: `00700`, `03690`

## Examples for OpenClaw

### User: "帮我分析一下茅台"

```bash
dsa-cli analyze 600519 --json
```

Parse the JSON response and present:
- Sentiment score and advice
- Trend prediction
- Key strategy levels

### User: "茅台现在多少钱？"

```bash
dsa-cli quote 600519 --json
```

Return the price and change percentage.

### User: "分析茅台和平安银行"

```bash
dsa-cli batch 600519,000001 --json
```

Return quotes for both stocks.

### User: "茅台最近有什么新闻？"

```bash
dsa-cli news 600519 --json --days 7
```

Summarize the recent news articles.

## Notes

- All analysis uses AI (Gemini/OpenAI) for comprehensive insights
- Technical indicators include MA, MACD, RSI, KDJ
- News search requires API keys (Tavily/SerpAPI/Bocha)
- Cache is enabled to avoid redundant API calls