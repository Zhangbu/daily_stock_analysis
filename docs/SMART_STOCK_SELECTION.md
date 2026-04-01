# 智能选股功能说明

## 功能概述

智能选股功能可以从已同步的市场数据中，根据预设策略自动选取表现优秀的股票，与手动配置的股票池合并后进行 AI 分析。

## 使用场景

- **补充选股**：在手动配置的股票池基础上，自动发现热门股票
- **策略选股**：根据技术面指标（涨幅、量比、均线等）筛选股票
- **节省配置时间**：无需手动维护股票列表，系统自动从同步数据中选取

## 配置项

在 `.env` 文件中添加以下配置：

```bash
# 智能选股配置（优化点 2 扩展：从同步数据中选取股票参与分析）
# 启用智能选股（默认 false）
MARKET_SYNC_STOCK_SELECTION_ENABLED=false

# 从同步数据中选取的股票数量（默认 10）
MARKET_SYNC_SELECT_COUNT=10

# 选股策略（可选：best_performer, volume_surge, ma_golden_cross, bottom_volume, all_strategies）
MARKET_SYNC_SELECTION_STRATEGY=best_performer
```

## 选股策略说明

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `best_performer` | 今日涨幅前 N 名 | 追涨热门股 |
| `volume_surge` | 量比前 N 名（放量） | 发现放量突破股票 |
| `ma_golden_cross` | MA5 上穿 MA10（金叉） | 技术面买入信号 |
| `bottom_volume` | 底部缩量（量比<0.5） | 寻找低吸机会 |
| `all_strategies` | 综合评分（绩效 + 量能 + 均线 + 动量） | 均衡选股 |

## 工作流程

```
1. 启动分析
   ↓
2. 加载手动配置的股票池（STOCK_LIST）
   ↓
3. 如果启用智能选股 → 从同步数据中选取股票
   ↓
4. 合并股票池（去重）
   ↓
5. 执行 AI 分析
   ↓
6. 推送结果
```

## 使用示例

### 示例 1：启用涨幅选股

```bash
# .env
MARKET_SYNC_STOCK_SELECTION_ENABLED=true
MARKET_SYNC_SELECT_COUNT=10
MARKET_SYNC_SELECTION_STRATEGY=best_performer
```

效果：在手动配置的股票池基础上，额外选取今日涨幅前 10 名的股票。

### 示例 2：启用综合策略选股

```bash
# .env
MARKET_SYNC_STOCK_SELECTION_ENABLED=true
MARKET_SYNC_SELECT_COUNT=15
MARKET_SYNC_SELECTION_STRATEGY=all_strategies
```

效果：综合评分选取 15 只股票，兼顾涨幅、量能、均线形态。

### 示例 3：只使用手动配置（默认）

```bash
# .env
MARKET_SYNC_STOCK_SELECTION_ENABLED=false  # 或不配置
```

效果：仅分析手动配置的股票池。

## 注意事项

1. **依赖同步数据**：智能选股需要从已同步的市场数据中选取，需要先运行市场同步服务或确保数据库中有足够的股票数据

2. **避免重复**：智能选出的股票会自动排除已在手动配置池中的股票，避免重复分析

3. **数据新鲜度**：选股效果取决于同步数据的及时性和质量

4. **策略选择**：不同策略适用于不同市场环境，建议根据实际效果调整

## 技术实现

- 服务层：`src/services/smart_stock_selector.py`
- 配置层：`src/config.py` 新增 3 个配置项
- 集成点：`src/core/pipeline.py:run_analysis()` 方法中合并选股结果

## 日志示例

```
INFO: 智能选股完成：策略=best_performer, 选中 10 只股票
INFO: 合并后股票数量：18 (基础池：8, 智能选股：10)
INFO: ===== 开始分析 18 只股票 =====
```
