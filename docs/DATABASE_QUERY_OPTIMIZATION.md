# 数据库查询优化实施总结

## 优化点 5：数据库查询优化

### 实施时间
2026-04-01

---

## 分析结果

### 当前数据库设计评估 ✅

**已有的优化**：
1. **索引设计完善**：
   - `StockDaily.code` - 单列索引 ✅
   - `StockDaily.date` - 单列索引 ✅
   - `ix_code_date` - 复合索引 (code, date) ✅

2. **批量查询已实现**：
   - `get_latest_trade_dates(codes)` - 批量查询多个股票的最新交易日期 ✅

### 发现的问题 ⚠️

**N+1 查询问题**：
- 位置：`market_data_sync_service.py`
- 场景：市场同步服务
- 问题：
  1. `_filter_fresh_codes()` 批量查询了所有股票的最新交易日期
  2. 但 `_sync_single_code()` 又对每只股票单独查询了一次 `get_latest_trade_date(code)`
  3. 导致每只股票被查询 2 次

**影响范围**：
- 同步 300 只股票 = 300 次额外查询
- 同步 5000 只股票 = 5000 次额外查询

---

## 已实施的优化

### 1. 消除 N+1 查询 ✅

**文件**: `src/services/market_data_sync_service.py`

**改动**：

1. **修改 `_get_market_universe` 返回值**：
   ```python
   # 优化前
   def _get_market_universe(self, market: str) -> List[str]:

   # 优化后
   def _get_market_universe(self, market: str) -> tuple[List[str], Dict[str, Optional[date]]]:
       """返回股票列表和最新日期映射"""
   ```

2. **新增 `_filter_fresh_codes_with_map` 方法**：
   ```python
   def _filter_fresh_codes_with_map(self, codes: List[str]) -> tuple[List[str], Dict[str, Optional[date]]]:
       """过滤已同步股票，同时返回最新日期映射"""
   ```

3. **修改 `_sync_single_code` 接受缓存参数**：
   ```python
   def _sync_single_code(self, code: str, cached_latest_date: Optional[date] = None) -> int:
       """同步单只股票

       Args:
           code: 股票代码
           cached_latest_date: 预查询的最新交易日期（可选）
       """
       # 使用缓存的最新日期，如果没有则查询数据库
       if cached_latest_date is not None:
           latest_trade_date = cached_latest_date
       else:
           latest_trade_date = self.stock_repo.get_latest_trade_date(code)
   ```

4. **修改 `_run_sync` 传递缓存数据**：
   ```python
   codes, latest_dates_map = self._get_market_universe(market)

   for code in codes:
       latest_date = latest_dates_map.get(code)
       saved = self._sync_single_code(code, cached_latest_date=latest_date)
   ```

**预期收益**：
- 数据库查询次数减少 50%（每只股票从 2 次降至 1 次）
- 同步 300 只股票减少 300 次查询
- 同步 5000 只股票减少 5000 次查询

---

## 数据库索引状态

### 当前索引（已优化）

```python
class StockDaily(Base):
    __tablename__ = 'stock_daily'

    id = Column(Integer, primary_key=True)
    code = Column(String(10), nullable=False, index=True)      # ✅ 单列索引
    date = Column(Date, nullable=False, index=True)            # ✅ 单列索引

    __table_args__ = (
        Index('ix_code_date', 'code', 'date'),  # ✅ 复合索引
    )
```

### 索引覆盖的查询场景

| 查询类型 | 使用索引 | 状态 |
|----------|---------|------|
| `WHERE code = ?` | `ix_code_date` | ✅ 覆盖 |
| `WHERE date = ?` | `ix_date` | ✅ 覆盖 |
| `WHERE code = ? AND date = ?` | `ix_code_date` | ✅ 覆盖 |
| `WHERE code IN (?)` | `ix_code_date` | ✅ 覆盖 |
| `GROUP BY code` | `ix_code_date` | ✅ 覆盖 |
| `ORDER BY date DESC` | `ix_date` | ✅ 覆盖 |

**结论**：当前索引设计已足够，无需额外索引。

---

## 其他已实现的优化

### 1. 批量查询优化 ✅

**已有实现**：
```python
# 批量查询多个股票的最新交易日期
def get_latest_trade_dates(self, codes: List[str]) -> Dict[str, Optional[date]]:
    rows = session.execute(
        select(StockDaily.code, func.max(StockDaily.date).label("latest_date"))
        .where(StockDaily.code.in_(normalized))
        .group_by(StockDaily.code)
    ).all()
```

**优点**：
- 使用 `IN` 查询替代多次单条查询
- 使用 `GROUP BY` 一次性获取所有结果
- 返回字典映射便于快速查找

---

## 性能对比

### 市场同步场景（300 只股票）

| 优化项 | 优化前 | 优化后 | 提升 |
|--------|--------|--------|------|
| 数据库查询次数 | 600 次 | 300 次 | 50% |
| 查询耗时（估计） | 6 秒 | 3 秒 | 50% |
| 总同步时间 | 包含 API 调用 | 包含 API 调用 | - |

### 全量同步场景（5000 只股票）

| 优化项 | 优化前 | 优化后 | 提升 |
|--------|--------|--------|------|
| 数据库查询次数 | 10000 次 | 5000 次 | 50% |
| 查询耗时（估计） | 100 秒 | 50 秒 | 50% |

---

## 修改的文件

1. **修改**: `src/services/market_data_sync_service.py`
   - `_get_market_universe` - 返回股票列表 + 日期映射
   - `_filter_fresh_codes_with_map` - 新增方法
   - `_sync_single_code` - 接受缓存日期参数
   - `_run_sync` - 传递缓存数据

---

## 兼容性

### 向后兼容 ✅

`_sync_single_code` 方法设计了默认参数：
```python
def _sync_single_code(self, code: str, cached_latest_date: Optional[date] = None) -> int:
```

- 调用时可以不传 `cached_latest_date`
- 方法内部会自动查询数据库
- 现有调用代码无需修改

---

## 监控建议

### 查询性能监控

```python
# 添加性能日志
import time

start = time.time()
latest_dates = self.stock_repo.get_latest_trade_dates(codes_to_check)
elapsed = time.time() - start
logger.info(f"批量查询 {len(codes_to_check)} 只股票耗时 {elapsed:.3f} 秒")
```

### 缓存命中率监控

```python
# 在 _sync_single_code 中添加计数
if cached_latest_date is not None:
    logger.debug(f"[{code}] 使用缓存的最新日期")
else:
    logger.debug(f"[{code}] 查询数据库获取最新日期")
```

---

## 后续优化建议

### 1. 连接池优化（可选）

如果数据库连接成为瓶颈：
```python
# SQLAlchemy 连接池配置
engine = create_engine(
    'sqlite:///...',
    pool_size=50,         # 连接池大小
    max_overflow=100,     # 最大溢出连接数
    pool_pre_ping=True,   # 自动检测失效连接
)
```

### 2. 批量保存优化（可选）

当前 `save_daily_data` 可能逐条插入，可以优化为批量插入：
```python
# 使用 SQLAlchemy bulk_insert
session.bulk_insert_mappings(StockDaily, data_list)
session.commit()
```

### 3. 读写分离（高级）

如果查询压力较大：
- 主库：写操作（保存数据）
- 从库：读操作（查询最新日期）

---

## 总结

**优化成果**：
- ✅ 消除了 N+1 查询问题
- ✅ 数据库查询次数减少 50%
- ✅ 保持了向后兼容性
- ✅ 索引设计已足够完善

**建议**：
1. 监控实际运行效果
2. 如有其他 N+1 场景，采用相同的缓存传递策略
3. 考虑批量保存优化
