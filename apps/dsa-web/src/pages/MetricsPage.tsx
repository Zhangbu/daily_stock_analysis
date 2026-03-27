import type React from 'react';
import { useEffect, useState } from 'react';
import { Card } from '../components/common';
import { systemMetricsApi, type MetricBucket, type SystemMetricsResponse } from '../api/systemMetrics';

function formatValue(value?: number): string {
  if (value == null) return '--';
  return String(value);
}

function formatBucketTime(bucketTs: number): string {
  return new Date(bucketTs * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

const TrendList: React.FC<{ title: string; items: Record<string, Array<MetricBucket & { bucketTs: number }>> }> = ({ title, items }) => (
  <Card variant="gradient" padding="md" className="animate-fade-in lg:col-span-2">
    <div className="mb-3">
      <span className="label-uppercase">{title}</span>
    </div>
    <div className="space-y-3">
      {Object.entries(items).map(([name, points]) => {
        const latest = points[points.length - 1];
        return (
          <div key={name} className="rounded-xl border border-white/8 bg-black/20 p-3">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold text-white">{name}</span>
              <span className="text-xs text-slate-400">最近 {points.length} 个时间桶</span>
            </div>
            <div className="grid gap-2 md:grid-cols-5">
              {points.map((point) => (
                <div key={`${name}-${point.bucketTs}`} className="rounded-lg border border-white/8 bg-black/20 px-3 py-2 text-xs text-slate-300">
                  <div className="mb-1 text-slate-400">{formatBucketTime(point.bucketTs)}</div>
                  <div>count: {formatValue(point.count)}</div>
                  <div>avg ms: {formatValue(point.avgDurationMs)}</div>
                  <div>p50 ms: {formatValue(point.p50DurationMs)}</div>
                  <div>p95 ms: {formatValue(point.p95DurationMs)}</div>
                  <div>ok: {formatValue(point.success)}</div>
                  <div>err: {formatValue(point.error)}</div>
                </div>
              ))}
            </div>
            {latest ? (
              <div className="mt-3 text-xs text-cyan-300">
                当前窗口 avg {formatValue(latest.avgDurationMs)} ms / p95 {formatValue(latest.p95DurationMs)} ms / max {formatValue(latest.maxDurationMs)} ms
              </div>
            ) : null}
          </div>
        );
      })}
      {Object.keys(items).length === 0 ? <div className="text-sm text-slate-400">暂无趋势数据</div> : null}
    </div>
  </Card>
);

const MetricList: React.FC<{ title: string; items: Record<string, MetricBucket> }> = ({ title, items }) => (
  <Card variant="gradient" padding="md" className="animate-fade-in">
    <div className="mb-3">
      <span className="label-uppercase">{title}</span>
    </div>
    <div className="space-y-3">
      {Object.entries(items).map(([name, metric]) => (
        <div key={name} className="rounded-xl border border-white/8 bg-black/20 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold text-white">{name}</span>
            <span className="text-xs text-cyan-300">hit {formatValue(metric.hitRatePct)}%</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-300 md:grid-cols-4">
            <span>count: {formatValue(metric.count)}</span>
            <span>success: {formatValue(metric.success)}</span>
            <span>error: {formatValue(metric.error)}</span>
            <span>avg ms: {formatValue(metric.avgDurationMs)}</span>
            <span>p50 ms: {formatValue(metric.p50DurationMs)}</span>
            <span>p95 ms: {formatValue(metric.p95DurationMs)}</span>
            <span>max ms: {formatValue(metric.maxDurationMs)}</span>
            <span>hits: {formatValue(metric.hits ?? metric.cacheHits)}</span>
            <span>misses: {formatValue(metric.misses ?? metric.cacheMisses)}</span>
            <span>writes: {formatValue(metric.writes)}</span>
          </div>
        </div>
      ))}
      {Object.keys(items).length === 0 ? <div className="text-sm text-slate-400">暂无指标数据</div> : null}
    </div>
  </Card>
);

const MetricsPage: React.FC = () => {
  const [data, setData] = useState<SystemMetricsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshSeconds, setRefreshSeconds] = useState(10);
  const [clearingNamespace, setClearingNamespace] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  const loadMetrics = async (showLoading = true) => {
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const payload = await systemMetricsApi.getMetrics();
      setData(payload);
      setLastUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载运行指标失败');
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    let active = true;
    const load = async (showLoading = true) => {
      if (!active) return;
      if (showLoading) {
        setIsLoading(true);
      }
      setError(null);
      try {
        const payload = await systemMetricsApi.getMetrics();
        if (active) {
          setData(payload);
          setLastUpdatedAt(new Date());
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : '加载运行指标失败');
        }
      } finally {
        if (active && showLoading) {
          setIsLoading(false);
        }
      }
    };

    load(true);
    if (refreshSeconds <= 0) {
      return () => {
        active = false;
      };
    }

    const timer = window.setInterval(() => {
      void load(false);
    }, refreshSeconds * 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [refreshSeconds]);

  const handleClearCache = async (namespace: string) => {
    setClearingNamespace(namespace);
    setError(null);
    try {
      const payload = await systemMetricsApi.clearCache(namespace);
      setData((current) => (current ? { ...current, cache: payload.cache } : current));
      setLastUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : '清理缓存失败');
    } finally {
      setClearingNamespace(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 md:px-6">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <span className="label-uppercase">Runtime</span>
          <h1 className="mt-2 text-3xl font-semibold text-white">运行指标面板</h1>
          <p className="mt-2 text-sm text-slate-400">查看缓存命中率、关键链路耗时和搜索缓存分层效果。</p>
          <p className="mt-2 text-xs text-slate-500">
            最近刷新：{lastUpdatedAt ? lastUpdatedAt.toLocaleTimeString('zh-CN') : '--'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs text-slate-400">
            刷新间隔
            <select
              value={refreshSeconds}
              onChange={(e) => setRefreshSeconds(Number(e.target.value))}
              className="ml-2 rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-sm text-white"
            >
              <option value={0}>暂停</option>
              <option value={5}>5s</option>
              <option value={10}>10s</option>
              <option value={30}>30s</option>
              <option value={60}>60s</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => void loadMetrics(true)}
            disabled={isLoading || clearingNamespace !== null}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            手动刷新
          </button>
          <button
            type="button"
            onClick={() => handleClearCache('market_data')}
            disabled={clearingNamespace !== null}
            className="rounded-lg border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-sm text-emerald-200 disabled:opacity-50"
          >
            {clearingNamespace === 'market_data' ? '清理中...' : '清行情缓存'}
          </button>
          <button
            type="button"
            onClick={() => handleClearCache('search')}
            disabled={clearingNamespace !== null}
            className="rounded-lg border border-blue-300/20 bg-blue-300/10 px-3 py-1.5 text-sm text-blue-200 disabled:opacity-50"
          >
            {clearingNamespace === 'search' ? '清理中...' : '清搜索缓存'}
          </button>
          <button
            type="button"
            onClick={() => handleClearCache('article_content')}
            disabled={clearingNamespace !== null}
            className="rounded-lg border border-cyan/20 bg-cyan/10 px-3 py-1.5 text-sm text-cyan disabled:opacity-50"
          >
            {clearingNamespace === 'article_content' ? '清理中...' : '清正文缓存'}
          </button>
          <button
            type="button"
            onClick={() => handleClearCache('all')}
            disabled={clearingNamespace !== null}
            className="rounded-lg border border-amber-300/20 bg-amber-300/10 px-3 py-1.5 text-sm text-amber-200 disabled:opacity-50"
          >
            {clearingNamespace === 'all' ? '清理中...' : '清全部缓存'}
          </button>
        </div>
      </div>

      {isLoading ? <div className="text-sm text-slate-400">加载中...</div> : null}
      {error ? <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{error}</div> : null}

      {data ? (
        <div className="grid gap-5 lg:grid-cols-2">
          <MetricList title="Operation Metrics" items={data.observability} />
          <MetricList title="Provider Metrics" items={data.observabilityByProvider} />
          <TrendList title="Operation Trends" items={data.observabilityTrends} />
          <MetricList title="Market Data Cache" items={{ marketData: data.cache.marketData }} />
          <MetricList title="Search Cache" items={data.cache.search} />
          <Card variant="gradient" padding="md" className="animate-fade-in lg:col-span-2">
            <div className="mb-3">
              <span className="label-uppercase">Slow Operations</span>
            </div>
            <div className="space-y-2">
              {data.recentSlowest.map((item, index) => (
                <div key={`${item.operation}-${index}`} className="flex items-center justify-between rounded-xl border border-white/8 bg-black/20 px-3 py-2 text-sm">
                  <span className="text-white">
                    {item.operation}
                    {item.provider ? <span className="ml-2 text-xs text-cyan-300">[{item.provider}]</span> : null}
                  </span>
                  <span className="font-mono text-slate-300">{item.durationMs} ms</span>
                </div>
              ))}
              {data.recentSlowest.length === 0 ? <div className="text-sm text-slate-400">暂无慢操作记录</div> : null}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
};

export default MetricsPage;
