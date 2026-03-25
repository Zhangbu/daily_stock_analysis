import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Card, Badge } from '../components/common';
import { strategyBacktestApi, type StrategySignalBacktestRunResponse, type StrategySignalInfo } from '../api/strategyBacktest';

function percent(value?: number | null): string {
  if (value == null) return '--';
  return `${(value * 100).toFixed(2)}%`;
}

function fixed(value?: number | null): string {
  if (value == null) return '--';
  return value.toFixed(2);
}

const StrategyBacktestPage: React.FC = () => {
  const [code, setCode] = useState('600519');
  const [days, setDays] = useState(240);
  const [initialCapital, setInitialCapital] = useState(100000);
  const [strategies, setStrategies] = useState<StrategySignalInfo[]>([]);
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(['ma_golden_cross']);
  const [result, setResult] = useState<StrategySignalBacktestRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    strategyBacktestApi.getStrategies()
      .then((items) => setStrategies(items))
      .catch((err) => setError(err instanceof Error ? err.message : '加载策略列表失败'));
  }, []);

  const supportedStrategies = useMemo(
    () => strategies.filter((item) => item.supported),
    [strategies],
  );

  const toggleStrategy = (strategyId: string) => {
    setSelectedStrategies((prev) => (
      prev.includes(strategyId)
        ? prev.filter((item) => item !== strategyId)
        : [...prev, strategyId]
    ));
  };

  const runBacktest = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload = await strategyBacktestApi.run({
        code: code.trim().toUpperCase(),
        strategyIds: selectedStrategies,
        days,
        initialCapital,
      });
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : '运行策略回测失败');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 md:px-6">
      <div className="mb-6">
        <span className="label-uppercase">Signal Backtest</span>
        <h1 className="mt-2 text-3xl font-semibold text-white">策略信号回测</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">
          这里运行的是基于技术规则生成买卖信号的真正策略回测，和“历史建议评估”页是两条独立能力线。
        </p>
      </div>

      <Card variant="gradient" padding="md" className="mb-5">
        <div className="grid gap-4 lg:grid-cols-[220px_120px_160px_1fr]">
          <label className="text-sm text-slate-300">
            股票代码
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="input-terminal mt-2 w-full"
              placeholder="600519 / AAPL / hk00700"
            />
          </label>
          <label className="text-sm text-slate-300">
            回看天数
            <input
              type="number"
              min={60}
              max={1000}
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="input-terminal mt-2 w-full"
            />
          </label>
          <label className="text-sm text-slate-300">
            初始资金
            <input
              type="number"
              min={1000}
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="input-terminal mt-2 w-full"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={runBacktest}
              disabled={isLoading || selectedStrategies.length === 0 || !code.trim()}
              className="btn-primary w-full"
            >
              {isLoading ? '回测中...' : '运行策略回测'}
            </button>
          </div>
        </div>
      </Card>

      <Card variant="gradient" padding="md" className="mb-5">
        <div className="mb-3 flex items-center justify-between">
          <span className="label-uppercase">Supported Strategies</span>
          <span className="text-xs text-slate-400">可多选比较</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {supportedStrategies.map((strategy) => {
            const active = selectedStrategies.includes(strategy.id);
            return (
              <button
                key={strategy.id}
                type="button"
                onClick={() => toggleStrategy(strategy.id)}
                className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                  active
                    ? 'border-cyan/40 bg-cyan/10 text-cyan'
                    : 'border-white/10 text-slate-300 hover:text-white'
                }`}
                title={strategy.supportNote}
              >
                {strategy.name}
              </button>
            );
          })}
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {strategies.filter((item) => !item.supported).slice(0, 6).map((strategy) => (
            <div key={strategy.id} className="rounded-xl border border-white/8 bg-black/20 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-white">{strategy.name}</span>
                <Badge variant="warning">待实现</Badge>
              </div>
              <p className="text-xs text-slate-400">{strategy.supportNote}</p>
            </div>
          ))}
        </div>
      </Card>

      {error ? <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{error}</div> : null}

      {result ? (
        <>
          <Card variant="gradient" padding="md" className="mb-5">
            <div className="flex flex-wrap items-center gap-4 text-sm text-slate-300">
              <span>标的: <span className="font-mono text-white">{result.code}</span></span>
              <span>数据源: <span className="text-cyan">{result.dataSource}</span></span>
              <span>窗口: <span className="text-white">{result.days}</span> 天</span>
              <span>资金: <span className="text-white">{fixed(result.initialCapital)}</span></span>
            </div>
            {result.unsupportedStrategyIds.length > 0 ? (
              <p className="mt-3 text-xs text-amber-300">
                以下策略尚未实现信号生成，已跳过：{result.unsupportedStrategyIds.join(', ')}
              </p>
            ) : null}
          </Card>

          <div className="mb-5 overflow-x-auto rounded-xl border border-white/5">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-elevated text-left">
                  <th className="px-3 py-2.5 text-xs uppercase tracking-wider text-secondary">Strategy</th>
                  <th className="px-3 py-2.5 text-xs uppercase tracking-wider text-secondary">Trades</th>
                  <th className="px-3 py-2.5 text-xs uppercase tracking-wider text-secondary">Win Rate</th>
                  <th className="px-3 py-2.5 text-xs uppercase tracking-wider text-secondary">Total Return</th>
                  <th className="px-3 py-2.5 text-xs uppercase tracking-wider text-secondary">Avg Trade</th>
                  <th className="px-3 py-2.5 text-xs uppercase tracking-wider text-secondary">Max DD</th>
                  <th className="px-3 py-2.5 text-xs uppercase tracking-wider text-secondary">Sharpe</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((item) => (
                  <tr key={item.strategyId} className="border-t border-white/5 hover:bg-hover">
                    <td className="px-3 py-2.5 text-white">{item.strategyName}</td>
                    <td className="px-3 py-2.5 font-mono text-cyan">{item.metrics.totalTrades}</td>
                    <td className="px-3 py-2.5">{percent(item.metrics.winRate)}</td>
                    <td className="px-3 py-2.5">{fixed(item.metrics.totalProfitPct)}%</td>
                    <td className="px-3 py-2.5">{percent(item.metrics.avgProfitPct)}</td>
                    <td className="px-3 py-2.5">{percent(item.metrics.maxDrawdownPct)}</td>
                    <td className="px-3 py-2.5">{fixed(item.metrics.sharpeRatio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            {result.results.map((item) => (
              <Card key={item.strategyId} variant="gradient" padding="md" className="animate-fade-in">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-white">{item.strategyName}</h2>
                    <p className="mt-1 text-xs text-slate-400">{item.note}</p>
                  </div>
                  <Badge variant={item.metrics.totalProfitPct >= 0 ? 'success' : 'danger'}>
                    {fixed(item.metrics.totalProfitPct)}%
                  </Badge>
                </div>
                <div className="grid gap-2 text-sm text-slate-300 md:grid-cols-2">
                  <div>总交易数: <span className="font-mono text-white">{item.metrics.totalTrades}</span></div>
                  <div>胜率: <span className="font-mono text-white">{percent(item.metrics.winRate)}</span></div>
                  <div>总收益: <span className="font-mono text-white">{fixed(item.metrics.totalProfit)}</span></div>
                  <div>平均单笔: <span className="font-mono text-white">{fixed(item.metrics.avgProfit)}</span></div>
                  <div>最大回撤: <span className="font-mono text-white">{percent(item.metrics.maxDrawdownPct)}</span></div>
                  <div>夏普比率: <span className="font-mono text-white">{fixed(item.metrics.sharpeRatio)}</span></div>
                </div>
                <div className="mt-4">
                  <div className="mb-2 text-xs uppercase tracking-wider text-secondary">Recent Trades</div>
                  <div className="space-y-2">
                    {item.trades.slice(0, 6).map((trade, index) => (
                      <div key={`${item.strategyId}-${index}`} className="rounded-lg border border-white/8 bg-black/20 px-3 py-2 text-xs text-slate-300">
                        <div className="flex items-center justify-between">
                          <span>{trade.entryDate} {'->'} {trade.exitDate}</span>
                          <span className={trade.profitPct >= 0 ? 'text-emerald-300' : 'text-red-300'}>
                            {percent(trade.profitPct)}
                          </span>
                        </div>
                        <div className="mt-1 font-mono text-slate-400">
                          entry {fixed(trade.entryPrice)} / exit {fixed(trade.exitPrice)}
                        </div>
                      </div>
                    ))}
                    {item.trades.length === 0 ? <div className="text-xs text-slate-500">当前窗口内没有形成完整交易。</div> : null}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
};

export default StrategyBacktestPage;
