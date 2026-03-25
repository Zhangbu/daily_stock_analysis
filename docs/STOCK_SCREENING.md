# Stock Screening Guide / 股票筛选指南

## Overview / 概述

The stock screening feature allows you to filter and recommend stocks based on multiple criteria including market cap, turnover, price, and technical indicators.

股票筛选功能允许您根据多个条件（包括市值、成交额、价格和技术指标）来过滤和推荐股票。

## Recent Improvements / 最近改进

### 1. Optimized Default Parameters / 优化默认参数

**Problem / 问题**: Previous default parameters were too strict, resulting in no stocks being found.
**问题**: 之前的默认参数过于严格，导致无法找到股票。

**Solution / 解决方案**: Adjusted to more reasonable balanced defaults:
**解决方案**: 调整为更合理的平衡型默认值:

- **Minimum Market Cap**: Reduced from 100亿 to 50亿
  - **最小市值**: 从 100亿 降低到 50亿
- **Minimum Turnover**: Reduced from 200 million to 100 million
  - **最小成交额**: 从 2亿 降低到 1亿
- **Default exclude_prefixes**: Changed from `['688', '300']` to `[]` (include all boards)
  - **默认排除板块**: 从 `['688', '300']` 改为 `[]` (包含所有板块)

### 2. Quick Presets / 快速预设

Three preset configurations are now available for quick selection:
现在提供三种预设配置供快速选择:

#### Balanced / 平衡型
- **Description**: Balances quality and quantity
- **描述**: 质量与数量兼顾
- **Parameters**:
  - Min Market Cap: 50亿
  - Min Turnover: 1亿
  - Price: 5元以上
  - Target: 30 stocks

#### Aggressive / 激进型
- **Description**: High turnover, small-medium cap, includes growth boards
- **描述**: 高换手、中小市值、允许双创
- **Parameters**:
  - Min Market Cap: 20亿
  - Min Turnover: 5千万
  - Price: 3元以上
  - Turnover Rate: 2%-30%
  - Target: 50 stocks

#### Conservative / 稳健型
- **Description**: Only selects high-quality large-cap stocks
- **描述**: 只选优质大盘股
- **Parameters**:
  - Min Market Cap: 100亿
  - Min Turnover: 1.5亿
  - Price: 10元以上
  - Turnover Rate: 1%-10%
  - Target: 20 stocks

### 3. Enhanced UI Features / 增强UI功能

- **Maximum Value Fields**: Added max_market_cap and max_price fields
  - **最大值字段**: 添加了最大市值和最大价格字段
- **Board Selection**: Toggle to exclude/include STAR Market (688) and ChiNext (300)
  - **板块选择**: 可切换排除/包含科创板(688)和创业板(300)
- **Helpful Tips**: Added suggestion hints below key fields
  - **实用提示**: 在关键字段下方添加建议提示
- **Better Empty State**: Improved feedback when no stocks are found with actionable suggestions
  - **更好的空状态**: 当没有找到股票时提供可操作的建议

## Screening Parameters / 筛选参数

### Market Cap / 市值

| Parameter | Description | Recommended Range |
|-----------|-------------|-------------------|
| `min_market_cap` | Minimum market cap in yuan | 20亿 - 100亿 |
| `max_market_cap` | Maximum market cap in yuan (optional) | Optional |

**Tips / 提示**:
- Lower values for small-cap growth stocks
- Higher values for stable large-cap stocks
- Combine with turnover for better results

### Turnover / 成交额

| Parameter | Description | Recommended Range |
|-----------|-------------|-------------------|
| `min_turnover` | Minimum turnover in yuan | 5千万 - 2亿 |

**Tips / 提示**:
- Higher turnover indicates active trading
- Too low may indicate lack of market interest
- Too high may indicate speculative activity

### Turnover Rate / 换手率

| Parameter | Description | Recommended Range |
|-----------|-------------|-------------------|
| `min_turnover_rate` | Minimum turnover rate percentage | 1% - 5% |
| `max_turnover_rate` | Maximum turnover rate percentage | 10% - 25% |

**Tips / 提示**:
- 1%-5%: Normal trading activity
- 5%-15%: Active stocks, good attention
- 15%-25%: Very active, may be speculative
- >25%: High volatility, proceed with caution

### Price Range / 价格范围

| Parameter | Description | Recommended Range |
|-----------|-------------|-------------------|
| `min_price` | Minimum stock price in yuan | 3元 - 50元 |
| `max_price` | Maximum stock price in yuan (optional) | Optional |

**Tips / 提示**:
- 3-10元: Low-priced stocks, higher risk/reward
- 10-50元: Mid-priced stocks, balanced risk/reward
- >50元: High-priced stocks, typically high quality

### Change Percentage / 涨跌幅

| Parameter | Description | Recommended Range |
|-----------|-------------|-------------------|
| `min_change_pct` | Minimum change percentage | -5% to -2% |
| `max_change_pct` | Maximum change percentage | 8% to 10% |

**Tips / 提示**:
- Negative range: Find pullback opportunities
- Positive range: Find momentum stocks
- Wider range: More results

### Board Selection / 板块选择

| Parameter | Description |
|-----------|-------------|
| `exclude_prefixes` | Stock code prefixes to exclude. Examples: '688' (STAR Market), '300' (ChiNext). Empty list includes all boards. |

**Board Codes / 板块代码**:
- `000,001,002,003`: Main Board (主板)
- `300,301`: ChiNext (创业板)
- `688`: STAR Market (科创板)
- `8xx`: Beijing Stock Exchange (北交所)

**Tips / 提示**:
- Include STAR Market and ChiNext for growth stocks
- Exclude them for more conservative selections
- Different boards have different risk profiles

### Other Options / 其他选项

| Parameter | Description | Default |
|-----------|-------------|---------|
| `exclude_st` | Exclude ST stocks | true |
| `include_dragon_tiger` | Only include dragon-tiger list stocks | false |
| `target_count` | Target number of stocks (max 500) | 30 |

## Usage Examples / 使用示例

### Example 1: Find Active Small-Cap Stocks / 示例1: 查找活跃小盘股

```json
{
  "min_market_cap": 2000000000,
  "min_turnover": 50000000,
  "min_turnover_rate": 2.0,
  "max_turnover_rate": 20.0,
  "min_price": 3.0,
  "min_change_pct": -5.0,
  "max_change_pct": 9.9,
  "exclude_st": true,
  "exclude_prefixes": [],
  "target_count": 50
}
```

### Example 2: Find Stable Large-Cap Stocks / 示例2: 查找稳健大盘股

```json
{
  "min_market_cap": 10000000000,
  "min_turnover": 150000000,
  "min_turnover_rate": 1.0,
  "max_turnover_rate": 8.0,
  "min_price": 10.0,
  "min_change_pct": -2.0,
  "max_change_pct": 6.0,
  "exclude_st": true,
  "exclude_prefixes": ["688", "300"],
  "target_count": 20
}
```

### Example 3: Find Pullback Opportunities / 示例3: 查找回调机会

```json
{
  "min_market_cap": 5000000000,
  "min_turnover": 100000000,
  "min_turnover_rate": 1.5,
  "max_turnover_rate": 15.0,
  "min_price": 5.0,
  "min_change_pct": -5.0,
  "max_change_pct": 0.0,
  "exclude_st": true,
  "exclude_prefixes": [],
  "target_count": 30
}
```

## Troubleshooting / 故障排除

### No Stocks Found / 没有找到股票

If you get zero results, try these adjustments:
如果没有结果，尝试以下调整:

1. **Lower thresholds**: Reduce min_market_cap and min_turnover
   - **降低阈值**: 减小最小市值和最小成交额
2. **Widen ranges**: Increase max_turnover_rate and max_change_pct
   - **放宽范围**: 增加最大换手率和最大涨跌幅
3. **Include more boards**: Remove prefixes from exclude_prefixes
   - **包含更多板块**: 从排除列表中移除板块前缀
4. **Use presets**: Try the "Aggressive" preset for more results
   - **使用预设**: 尝试"激进型"预设获得更多结果

### Too Many Results / 结果太多

If you get too many results, try these adjustments:
如果结果太多，尝试以下调整:

1. **Raise thresholds**: Increase min_market_cap and min_turnover
   - **提高阈值**: 增加最小市值和最小成交额
2. **Narrow ranges**: Decrease max_turnover_rate and max_change_pct
   - **缩小范围**: 减小最大换手率和最大涨跌幅
3. **Exclude volatile boards**: Add '688' and '300' to exclude_prefixes
   - **排除波动板块**: 添加 '688' 和 '300' 到排除列表
4. **Use presets**: Try the "Conservative" preset for fewer, higher-quality results
   - **使用预设**: 尝试"稳健型"预设获得更少但质量更高的结果

## API Endpoint / API端点

```
POST /api/v1/screening/filter
```

### Request Body / 请求体

```json
{
  "min_market_cap": 5000000000,
  "max_market_cap": null,
  "min_turnover": 100000000,
  "min_turnover_rate": 1.0,
  "max_turnover_rate": 25.0,
  "min_price": 5.0,
  "max_price": null,
  "min_change_pct": -3.0,
  "max_change_pct": 10.0,
  "exclude_st": true,
  "exclude_prefixes": [],
  "include_dragon_tiger": false,
  "target_count": 30,
  "sort_by": null
}
```

### Response / 响应

```json
{
  "stocks": [
    {
      "code": "000001",
      "name": "平安银行",
      "price": 12.34,
      "market_cap": 240000000000,
      "turnover": 120000000,
      "turnover_rate": 0.5,
      "change_pct": 2.34,
      "open": 12.10,
      "high": 12.45,
      "low": 12.05,
      "volume": 10000000,
      "amount": 123000000
    }
  ],
  "summary": {
    "count": 30,
    "avg_market_cap": 50000000000,
    "avg_turnover": 150000000,
    "avg_turnover_rate": 3.5,
    "avg_price": 15.67,
    "avg_change_pct": 1.23
  }
}
```

## Best Practices / 最佳实践

1. **Start with presets**: Use the built-in presets as a starting point
   - **从预设开始**: 使用内置预设作为起点
2. **Adjust gradually**: Make small adjustments to avoid over-filtering
   - **逐步调整**: 小幅度调整以避免过度过滤
3. **Consider market conditions**: Adjust parameters based on overall market activity
   - **考虑市场环境**: 根据整体市场活跃度调整参数
4. **Review results carefully**: Always do your own research before investing
   - **仔细审查结果**: 投资前务必自行研究
5. **Diversify**: Don't rely on a single screening criteria
   - **多样化**: 不要依赖单一筛选标准

## Risk Disclaimer / 风险提示

Stock screening results are for informational purposes only and do not constitute investment advice. Always conduct your own research and consider your risk tolerance before making investment decisions.

股票筛选结果仅供参考，不构成投资建议。在做出投资决策前，请务必自行研究并考虑您的风险承受能力。