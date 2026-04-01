import { useEffect, useMemo, useState } from 'react';
import { screeningApi, type ScreeningSnapshotItem, type ScreeningTopAnalysisItem, type StockScreeningRequest, type StockInfo, type StockScreeningSummary } from '../api/screening';
import { marketSyncApi, type MarketSyncStatus } from '../api/marketSync';
import { systemConfigApi, SystemConfigConflictError } from '../api/systemConfig';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { Loading } from '../components/common/Loading';
import { Button } from '../components/common';

const ScreeningPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [stocks, setStocks] = useState<StockInfo[]>([]);
  const [summary, setSummary] = useState<StockScreeningSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<MarketSyncStatus | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncRunning, setSyncRunning] = useState(false);
  const [watchlistLoadingCode, setWatchlistLoadingCode] = useState<string | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [batchAnalyzeLoading, setBatchAnalyzeLoading] = useState(false);
  const [snapshots, setSnapshots] = useState<ScreeningSnapshotItem[]>([]);
  const [topAnalysisSummary, setTopAnalysisSummary] = useState<ScreeningTopAnalysisItem[]>([]);

  // Filter state - using balanced preset by default
  const [filters, setFilters] = useState<StockScreeningRequest>({
    market: 'cn',
    data_mode: 'database',
    min_market_cap: 5_000_000_000,  // 5 billion (more reasonable)
    max_market_cap: undefined,
    min_turnover: 100_000_000,     // 100 million (lower threshold)
    min_turnover_rate: 1.0,
    max_turnover_rate: 25.0,
    min_price: 5.0,
    max_price: undefined,
    min_change_pct: -3.0,
    max_change_pct: 10.0,
    exclude_st: true,
    exclude_prefixes: [],           // Empty by default (allow all boards)
    include_dragon_tiger: false,
    target_count: 30,
  });

  // Preset configurations
  const presets = {
    balanced: {
      name: '平衡型',
      description: '质量与数量兼顾',
      params: {
        min_market_cap: 5_000_000_000,
        market: 'cn' as const,
        data_mode: 'database' as const,
        max_market_cap: undefined,
        min_turnover: 100_000_000,
        min_turnover_rate: 1.0,
        max_turnover_rate: 25.0,
        min_price: 5.0,
        max_price: undefined,
        min_change_pct: -3.0,
        max_change_pct: 10.0,
        exclude_st: true,
        exclude_prefixes: [],
        include_dragon_tiger: false,
        target_count: 30,
      }
    },
    aggressive: {
      name: '激进型',
      description: '高换手、中小市值、允许双创',
      params: {
        min_market_cap: 2_000_000_000,
        market: 'cn' as const,
        data_mode: 'database' as const,
        max_market_cap: undefined,
        min_turnover: 50_000_000,
        min_turnover_rate: 2.0,
        max_turnover_rate: 30.0,
        min_price: 3.0,
        max_price: undefined,
        min_change_pct: -5.0,
        max_change_pct: 10.0,
        exclude_st: true,
        exclude_prefixes: [],
        include_dragon_tiger: false,
        target_count: 50,
      }
    },
    conservative: {
      name: '稳健型',
      description: '只选优质大盘股',
      params: {
        min_market_cap: 10_000_000_000,
        market: 'cn' as const,
        data_mode: 'database' as const,
        max_market_cap: undefined,
        min_turnover: 150_000_000,
        min_turnover_rate: 1.0,
        max_turnover_rate: 10.0,
        min_price: 10.0,
        max_price: undefined,
        min_change_pct: -2.0,
        max_change_pct: 8.0,
        exclude_st: true,
        exclude_prefixes: [],
        include_dragon_tiger: false,
        target_count: 20,
      }
    }
  };

  const applyPreset = (presetKey: keyof typeof presets) => {
    setFilters(prev => ({ ...prev, ...presets[presetKey].params }));
  };

  const handleScreen = async () => {
    setLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await screeningApi.screenStocks(filters);
      setStocks(response.stocks);
      setSummary(response.summary);
      const topCodes = response.stocks.slice(0, Math.min(5, response.stocks.length)).map((item) => item.code);
      if (topCodes.length > 0) {
        const analysisSummary = await screeningApi.getTopAnalysisSummary(topCodes);
        setTopAnalysisSummary(analysisSummary.items);
      } else {
        setTopAnalysisSummary([]);
      }
      
      // Show helpful message if no stocks found
      if (response.stocks.length === 0) {
        setError('未找到符合条件的股票，建议：\n1. 降低最小市值或成交额\n2. 放宽换手率范围\n3. 取消排除科创板或创业板\n4. 尝试使用预设方案');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail?.message || '筛选失败，请稍后重试');
      console.error('Screening failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toFixed(decimals);
  };

  const formatCurrency = (num: number): string => {
    if (num >= 1_000_000_000) {
      return `${(num / 1_000_000_000).toFixed(2)}亿`;
    } else if (num >= 10_000) {
      return `${(num / 10_000).toFixed(2)}万`;
    }
    return num.toFixed(2);
  };

  const getChangeColor = (change: number): string => {
    if (change > 0) return 'text-red-500';
    if (change < 0) return 'text-green-500';
    return 'text-gray-400';
  };

  const handleBoardToggle = (prefix: string) => {
    setFilters(prev => {
      const current = prev.exclude_prefixes || [];
      if (current.includes(prefix)) {
        return { ...prev, exclude_prefixes: current.filter(p => p !== prefix) };
      } else {
        return { ...prev, exclude_prefixes: [...current, prefix] };
      }
    });
  };

  const marketLabel = filters.market === 'us' ? '美股' : 'A股';
  const modeLabel = filters.data_mode === 'realtime' ? '实时筛选' : '数据库评分';
  const syncProgress = useMemo(() => {
    if (!syncStatus || syncStatus.totalCandidates <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((syncStatus.processed / syncStatus.totalCandidates) * 100));
  }, [syncStatus]);
  const priorityProgress = useMemo(() => {
    if (!syncStatus || syncStatus.priorityCandidates <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((syncStatus.priorityCompleted / syncStatus.priorityCandidates) * 100));
  }, [syncStatus]);

  const loadSyncStatus = async () => {
    setSyncLoading(true);
    try {
      const status = await marketSyncApi.getStatus();
      setSyncStatus(status);
    } catch (err) {
      console.error('Failed to load market sync status:', err);
    } finally {
      setSyncLoading(false);
    }
  };

  useEffect(() => {
    loadSyncStatus();
    screeningApi.getSnapshots(8).then((response) => setSnapshots(response.items)).catch((err) => {
      console.error('Failed to load screening snapshots:', err);
    });
    const timer = window.setInterval(() => {
      loadSyncStatus();
    }, 15000);
    return () => window.clearInterval(timer);
  }, []);

  const handleRunSync = async () => {
    setSyncRunning(true);
    try {
      const response = await marketSyncApi.run(filters.market === 'us' ? ['us'] : ['cn', 'us']);
      setSyncStatus(response.status);
    } catch (err) {
      console.error('Failed to start market sync:', err);
      setError('启动市场同步失败，请稍后重试');
    } finally {
      setSyncRunning(false);
    }
  };

  const handleExportCandidates = () => {
    if (!stocks.length) {
      setError('当前没有可导出的候选股票');
      return;
    }
    setActionMessage('候选池 CSV 已开始导出');

    const header = [
      'rank',
      'code',
      'name',
      'opportunity_tier',
      'score',
      'score_reason',
      'trend',
      'momentum',
      'pullback',
      'volume',
      'risk',
      'consistency',
      'price',
      'change_pct',
      'turnover',
    ];
    const rows = stocks.map((stock) => [
      stock.rank ?? '',
      stock.code,
      stock.name,
      stock.opportunity_tier ?? '',
      stock.score ?? '',
      stock.score_reason ?? '',
      stock.score_breakdown?.trend ?? '',
      stock.score_breakdown?.momentum ?? '',
      stock.score_breakdown?.pullback ?? '',
      stock.score_breakdown?.volume ?? '',
      stock.score_breakdown?.risk ?? '',
      stock.score_breakdown?.consistency ?? '',
      stock.price,
      stock.change_pct,
      stock.turnover,
    ]);

    const csv = [header, ...rows]
      .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
      .join('\n');

    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `screening-${filters.market || 'cn'}-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleSaveSnapshot = async () => {
    if (!summary || !stocks.length) {
      setError('当前没有可保存的候选池');
      return;
    }
    setSnapshotLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await screeningApi.saveSnapshot({
        filters,
        stocks,
        summary,
      });
      setActionMessage(`候选池已保存，快照 ID: ${response.snapshot_id}`);
      const refreshed = await screeningApi.getSnapshots(8);
      setSnapshots(refreshed.items);
    } catch (err) {
      console.error('Failed to save screening snapshot:', err);
      setError('保存候选池失败');
    } finally {
      setSnapshotLoading(false);
    }
  };

  const handleAnalyzeTopCandidates = async () => {
    if (!stocks.length) {
      setError('当前没有可分析的候选股票');
      return;
    }
    const topCodes = stocks.slice(0, Math.min(5, stocks.length)).map((stock) => stock.code);
    setBatchAnalyzeLoading(true);
    setError(null);
    setActionMessage(null);
    let accepted = 0;
    const duplicates: string[] = [];

    for (const code of topCodes) {
      try {
        await analysisApi.analyzeAsync({ stockCode: code, reportType: 'detailed' });
        accepted += 1;
      } catch (err) {
        if (err instanceof DuplicateTaskError) {
          duplicates.push(code);
        } else {
          console.error('Failed to submit analysis task:', code, err);
        }
      }
    }

    const duplicateText = duplicates.length ? `；重复任务: ${duplicates.join(', ')}` : '';
    setActionMessage(`已提交 ${accepted} 个 Top 候选分析任务${duplicateText}`);
    setBatchAnalyzeLoading(false);
  };

  const handleAddToWatchlist = async (code: string) => {
    setWatchlistLoadingCode(code);
    setError(null);
    setActionMessage(null);
    try {
      const config = await systemConfigApi.getConfig(true);
      const targetKey = filters.market === 'us' ? 'US_STOCK_LIST' : filters.market === 'hk' ? 'HK_STOCK_LIST' : 'STOCK_LIST';
      const stockListItem = config.items.find((item) => item.key === targetKey);
      const existing = (stockListItem?.value || '')
        .split(',')
        .map((entry) => entry.trim().toUpperCase())
        .filter(Boolean);

      if (existing.includes(code.toUpperCase())) {
        setActionMessage(`${code} 已经在自选股列表中`);
        return;
      }

      const nextValue = [...existing, code.toUpperCase()].join(',');
      await systemConfigApi.update({
        configVersion: config.configVersion,
        maskToken: config.maskToken,
        reloadNow: true,
        items: [{ key: targetKey, value: nextValue }],
      });
      setActionMessage(`${code} 已加入${filters.market === 'us' ? '美股' : filters.market === 'hk' ? '港股' : 'A股'}股票池`);
      await loadSyncStatus();
    } catch (err) {
      if (err instanceof SystemConfigConflictError) {
        setError('配置发生变化，请刷新后重试加入自选');
      } else {
        console.error('Failed to add stock to watchlist:', err);
        setError(`加入自选失败: ${code}`);
      }
    } finally {
      setWatchlistLoadingCode(null);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6 rounded-2xl border border-cyan/20 bg-gradient-to-r from-cyan/10 via-slate-900/70 to-emerald-500/10 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 text-xs font-semibold text-cyan">
                当前市场: {marketLabel}
              </span>
              <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-300">
                数据模式: {modeLabel}
              </span>
            </div>
            <h1 className="text-3xl font-bold text-white">市场筛选</h1>
            <p className="mt-2 text-sm text-gray-300">
              这里可以明确切换 A股 / 美股，并选择“数据库评分”或“实时筛选”两种工作模式。
            </p>
          </div>
          <div className="grid grid-cols-1 gap-2 text-sm text-gray-300 sm:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
              <div className="text-xs text-gray-500">数据库评分</div>
              <div className="mt-1">基于已同步的近一年历史数据打分，更适合慢筛和全市场候选池。</div>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
              <div className="text-xs text-gray-500">实时筛选</div>
              <div className="mt-1">沿用原来的实时行情筛选链路，适合快速看当天盘面。</div>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-6 rounded-2xl border border-emerald-400/20 bg-emerald-500/5 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-emerald-300">市场同步状态</h2>
            <p className="mt-1 text-sm text-gray-300">
              启动后会优先同步自选股，再慢速补齐市场历史数据。数据库评分模式依赖这里的本地日线积累。
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={handleSaveSnapshot}
              variant="secondary"
              isLoading={snapshotLoading}
              disabled={!stocks.length}
            >
              保存候选池
            </Button>
            <Button
              onClick={handleAnalyzeTopCandidates}
              variant="gradient"
              isLoading={batchAnalyzeLoading}
              disabled={!stocks.length}
            >
              分析 Top N
            </Button>
            <Button
              onClick={handleExportCandidates}
              variant="outline"
              disabled={!stocks.length}
            >
              导出候选池
            </Button>
            <Button
              onClick={() => void loadSyncStatus()}
              variant="secondary"
              isLoading={syncLoading}
            >
              刷新状态
            </Button>
            <Button
              onClick={handleRunSync}
              variant="gradient"
              isLoading={syncRunning}
            >
              立即同步
            </Button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="text-xs text-gray-500">运行状态</div>
            <div className="mt-2 text-lg font-semibold text-white">{syncStatus?.running ? '同步中' : '空闲'}</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="text-xs text-gray-500">处理进度</div>
            <div className="mt-2 text-lg font-semibold text-white">{syncStatus ? `${syncStatus.processed}/${syncStatus.totalCandidates}` : '--'}</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="text-xs text-gray-500">保存条数</div>
            <div className="mt-2 text-lg font-semibold text-white">{syncStatus?.saved ?? '--'}</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="text-xs text-gray-500">跳过条数</div>
            <div className="mt-2 text-lg font-semibold text-white">{syncStatus?.skipped ?? '--'}</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="text-xs text-gray-500">错误数</div>
            <div className="mt-2 text-lg font-semibold text-white">{syncStatus?.errors ?? '--'}</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="text-xs text-gray-500">同步市场</div>
            <div className="mt-2 text-lg font-semibold text-white">{syncStatus?.markets?.join(', ').toUpperCase() || '--'}</div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-cyan/10 bg-black/20 p-4">
            <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
              <span>整体同步进度</span>
              <span>{syncProgress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan" style={{ width: `${syncProgress}%` }} />
            </div>
          </div>
          <div className="rounded-xl border border-amber-400/10 bg-black/20 p-4">
            <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
              <span>自选股优先完成度</span>
              <span>{priorityProgress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-400" style={{ width: `${priorityProgress}%` }} />
            </div>
            <div className="mt-2 text-xs text-gray-500">
              {syncStatus ? `${syncStatus.priorityCompleted}/${syncStatus.priorityCandidates} 已完成，${syncStatus.priorityProcessed} 已处理` : '--'}
            </div>
          </div>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
            <span>{syncStatus?.message || '等待同步任务'}</span>
            <span>{syncProgress}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan transition-all"
              style={{ width: `${syncProgress}%` }}
            />
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
            <span>当前市场: {syncStatus?.currentMarket || '--'}</span>
            <span>当前代码: {syncStatus?.currentCode || '--'}</span>
            <span>开始时间: {syncStatus?.startedAt || '--'}</span>
            <span>结束时间: {syncStatus?.finishedAt || '--'}</span>
          </div>
        </div>
      </div>

      {/* Preset Selection */}
      <div className="bg-white/5 rounded-lg p-4 mb-4 border border-cyan/20">
        <h3 className="text-sm font-semibold text-cyan mb-3">快速预设方案</h3>
        <div className="flex gap-3">
          {(Object.keys(presets) as Array<keyof typeof presets>).map((key) => (
            <button
              key={key}
              onClick={() => applyPreset(key)}
              className="px-4 py-2 bg-black/30 border border-cyan/20 rounded-lg text-sm text-gray-300 hover:bg-cyan/10 hover:border-cyan transition-all"
            >
              <div className="font-semibold text-white">{presets[key].name}</div>
              <div className="text-xs text-gray-500 mt-1">{presets[key].description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Filter Panel */}
      <div className="bg-white/5 rounded-lg p-6 mb-6 border border-cyan/20">
        <h2 className="text-lg font-semibold text-cyan mb-4">筛选条件</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">市场</label>
            <select
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              value={filters.market || 'cn'}
              onChange={(e) => setFilters({ ...filters, market: e.target.value as 'cn' | 'us' })}
            >
              <option value="cn">A股</option>
              <option value="us">美股</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">数据模式</label>
            <select
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              value={filters.data_mode || 'database'}
              onChange={(e) => setFilters({ ...filters, data_mode: e.target.value as 'database' | 'realtime' })}
            >
              <option value="database">数据库评分</option>
              <option value="realtime">实时筛选</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">数据库评分更适合使用已同步的近一年历史数据</p>
          </div>

          {/* Market Cap */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">最小市值 (元)</label>
            <input
              type="number"
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              value={filters.min_market_cap || ''}
              onChange={(e) => setFilters({ ...filters, min_market_cap: Number(e.target.value) || 0 })}
            />
            <p className="text-xs text-gray-500 mt-1">建议: 20亿-100亿</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">最大市值 (元)</label>
            <input
              type="number"
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              placeholder="不限制"
              value={filters.max_market_cap || ''}
              onChange={(e) => setFilters({ ...filters, max_market_cap: Number(e.target.value) || undefined })}
            />
          </div>

          {/* Turnover */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">最小成交额 (元)</label>
            <input
              type="number"
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              value={filters.min_turnover || ''}
              onChange={(e) => setFilters({ ...filters, min_turnover: Number(e.target.value) || 0 })}
            />
            <p className="text-xs text-gray-500 mt-1">建议: 5千万-2亿</p>
          </div>

          {/* Turnover Rate */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">换手率范围 (%)</label>
            <div className="flex gap-2">
              <input
                type="number"
                className="w-1/2 bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
                value={filters.min_turnover_rate || ''}
                onChange={(e) => setFilters({ ...filters, min_turnover_rate: Number(e.target.value) || 0 })}
              />
              <span className="text-gray-400 self-center">-</span>
              <input
                type="number"
                className="w-1/2 bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
                value={filters.max_turnover_rate || ''}
                onChange={(e) => setFilters({ ...filters, max_turnover_rate: Number(e.target.value) || 0 })}
              />
            </div>
          </div>

          {/* Price Range */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">最小价格 (元)</label>
            <input
              type="number"
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              value={filters.min_price || ''}
              onChange={(e) => setFilters({ ...filters, min_price: Number(e.target.value) || 0 })}
            />
            <p className="text-xs text-gray-500 mt-1">建议: 3元-50元</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">最大价格 (元)</label>
            <input
              type="number"
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              placeholder="不限制"
              value={filters.max_price || ''}
              onChange={(e) => setFilters({ ...filters, max_price: Number(e.target.value) || undefined })}
            />
          </div>

          {/* Change Percentage */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">涨跌幅范围 (%)</label>
            <div className="flex gap-2">
              <input
                type="number"
                className="w-1/2 bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
                value={filters.min_change_pct || ''}
                onChange={(e) => setFilters({ ...filters, min_change_pct: Number(e.target.value) || 0 })}
              />
              <span className="text-gray-400 self-center">-</span>
              <input
                type="number"
                className="w-1/2 bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
                value={filters.max_change_pct || ''}
                onChange={(e) => setFilters({ ...filters, max_change_pct: Number(e.target.value) || 0 })}
              />
            </div>
          </div>

          {/* Target Count */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">目标数量</label>
            <input
              type="number"
              className="w-full bg-black/30 border border-cyan/20 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan"
              value={filters.target_count || ''}
              onChange={(e) => setFilters({ ...filters, target_count: Number(e.target.value) || 30 })}
            />
          </div>

          {/* Board Selection */}
          {filters.market !== 'us' ? (
            <div>
              <label className="block text-sm text-gray-400 mb-2">排除板块 (不勾选则包含)</label>
              <div className="flex gap-4">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="mr-2 w-4 h-4 accent-cyan"
                    checked={(filters.exclude_prefixes || []).includes('688')}
                    onChange={() => handleBoardToggle('688')}
                  />
                  <span className="text-sm text-gray-400">科创板 (688)</span>
                </label>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="mr-2 w-4 h-4 accent-cyan"
                    checked={(filters.exclude_prefixes || []).includes('300')}
                    onChange={() => handleBoardToggle('300')}
                  />
                  <span className="text-sm text-gray-400">创业板 (300)</span>
                </label>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-cyan/10 bg-black/20 px-4 py-3">
              <div className="text-sm text-cyan">当前是美股模式</div>
              <p className="mt-1 text-xs text-gray-400">
                美股不使用 A股板块前缀过滤，候选池来自自选股、`US_STOCK_LIST` 和已同步历史数据。
              </p>
            </div>
          )}

          {/* Exclude ST */}
          <div className="flex items-center">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="mr-2 w-4 h-4 accent-cyan"
                checked={filters.exclude_st}
                onChange={(e) => setFilters({ ...filters, exclude_st: e.target.checked })}
              />
              <span className="text-sm text-gray-400">排除 ST 股票</span>
            </label>
          </div>

          {/* Dragon Tiger List */}
          <div className="flex items-center">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="mr-2 w-4 h-4 accent-cyan"
                checked={filters.include_dragon_tiger}
                onChange={(e) => setFilters({ ...filters, include_dragon_tiger: e.target.checked })}
              />
              <span className="text-sm text-gray-400">仅包含龙虎榜</span>
            </label>
          </div>
        </div>

        <Button
          onClick={handleScreen}
          variant="gradient"
          isLoading={loading}
          className="mt-6"
        >
          开始筛选
        </Button>
      </div>

      {/* Error Message */}
      {error && (
        <div className={`rounded-lg p-4 mb-6 ${
          stocks.length === 0 && !loading 
            ? 'bg-yellow-500/10 border border-yellow-500/30' 
            : 'bg-red-500/10 border border-red-500/30'
        }`}>
          <p className={stocks.length === 0 && !loading ? 'text-yellow-400 whitespace-pre-line' : 'text-red-400'}>
            {error}
          </p>
        </div>
      )}

      {actionMessage && (
        <div className="rounded-lg p-4 mb-6 bg-emerald-500/10 border border-emerald-500/30">
          <p className="text-emerald-300">{actionMessage}</p>
        </div>
      )}

      {snapshots.length > 0 && (
        <div className="bg-white/5 rounded-lg p-4 mb-6 border border-cyan/20">
          <h2 className="text-lg font-semibold text-cyan mb-3">最近候选池快照</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            {snapshots.map((item) => (
              <div key={item.snapshot_id} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <div className="text-xs text-gray-500">{item.created_at || '--'}</div>
                <div className="mt-1 text-sm font-semibold text-white">
                  {item.market === 'us' ? '美股' : 'A股'} / {item.data_mode === 'realtime' ? '实时筛选' : '数据库评分'}
                </div>
                <div className="mt-2 text-xs text-gray-400">Top 候选: {String(item.summary?.top_candidates || '--')}</div>
                <div className="mt-1 text-xs text-gray-400">最高分: {String(item.summary?.top_score || '--')}</div>
                <div className="mt-1 text-xs text-gray-400">
                  平均跟踪收益: {String((item.performance_summary?.avg_return_pct as number | undefined) ?? '--')}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {topAnalysisSummary.length > 0 && (
        <div className="bg-white/5 rounded-lg p-4 mb-6 border border-cyan/20">
          <h2 className="text-lg font-semibold text-cyan mb-3">Top N 分析摘要</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {topAnalysisSummary.map((item) => (
              <div key={item.code} className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-white">{item.stock_name || item.code}</div>
                    <div className="text-xs text-gray-500">{item.code}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-cyan">{item.operation_advice || '--'}</div>
                    <div className="text-xs text-gray-500">{item.trend_prediction || '--'}</div>
                  </div>
                </div>
                <div className="mt-3 text-sm text-gray-300">{item.analysis_summary || '暂无分析摘要'}</div>
                <div className="mt-2 text-xs text-gray-500">
                  情绪分: {item.sentiment_score ?? '--'} | 更新时间: {item.created_at || '--'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      {summary && summary.count > 0 && (
        <div className="bg-white/5 rounded-lg p-6 mb-6 border border-cyan/20">
          <h2 className="text-lg font-semibold text-cyan mb-4">筛选结果摘要</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div>
              <p className="text-sm text-gray-400">股票数量</p>
              <p className="text-2xl font-bold text-cyan">{summary.count}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">平均市值</p>
              <p className="text-lg font-semibold text-white">{formatCurrency(summary.avg_market_cap)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">平均成交额</p>
              <p className="text-lg font-semibold text-white">{formatCurrency(summary.avg_turnover)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">平均换手率</p>
              <p className="text-lg font-semibold text-white">{formatNumber(summary.avg_turnover_rate)}%</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">平均价格</p>
              <p className="text-lg font-semibold text-white">{formatNumber(summary.avg_price)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">平均涨跌幅</p>
              <p className={`text-lg font-semibold ${getChangeColor(summary.avg_change_pct)}`}>
                {summary.avg_change_pct > 0 ? '+' : ''}{formatNumber(summary.avg_change_pct)}%
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-400">市场 / 模式</p>
              <p className="text-lg font-semibold text-white">
                {summary.market === 'us' ? '美股' : 'A股'} / {summary.data_mode === 'realtime' ? '实时筛选' : '数据库评分'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-400">最高评分</p>
              <p className="text-lg font-semibold text-white">{formatNumber(summary.top_score || 0)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">平均评分</p>
              <p className="text-lg font-semibold text-white">{formatNumber(summary.avg_score || 0)}</p>
            </div>
            <div className="col-span-2 md:col-span-3 lg:col-span-2">
              <p className="text-sm text-gray-400">Top 候选</p>
              <p className="text-sm font-semibold text-cyan">{summary.top_candidates?.join(' / ') || '--'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Stock List */}
      {loading ? (
        <Loading />
      ) : stocks.length > 0 ? (
        <div className="bg-white/5 rounded-lg border border-cyan/20 overflow-hidden">
          <table className="w-full">
            <thead className="bg-black/30">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold text-cyan">代码</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-cyan">名称</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">排名</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">等级</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">评分</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">价格</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">涨跌幅</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">市值</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">成交额</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">换手率</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-cyan">操作</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((stock, index) => (
                <tr key={`${stock.code}-${index}`} className="border-t border-cyan/10 hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 text-sm text-cyan font-mono">{stock.code}</td>
                  <td className="px-4 py-3 text-sm text-white font-medium">{stock.name}</td>
                  <td className="px-4 py-3 text-sm text-right text-white font-mono">{stock.rank ?? '--'}</td>
                  <td className="px-4 py-3 text-sm text-right">
                    <span className="inline-flex rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-xs font-semibold text-emerald-300">
                      {stock.opportunity_tier || '--'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-right">
                    <div className="font-mono text-cyan">{stock.score != null ? formatNumber(stock.score) : '--'}</div>
                    {stock.score_reason ? <div className="text-[11px] text-gray-500">{stock.score_reason}</div> : null}
                    {stock.score_breakdown ? (
                      <div className="mt-1 text-[11px] text-gray-500">
                        趋势 {formatNumber(stock.score_breakdown.trend || 0, 0)} /
                        动量 {formatNumber(stock.score_breakdown.momentum || 0, 0)} /
                        回撤 {formatNumber(stock.score_breakdown.pullback || 0, 0)} /
                        量能 {formatNumber(stock.score_breakdown.volume || 0, 0)} /
                        风险 {formatNumber(stock.score_breakdown.risk || 0, 0)} /
                        胜率代理 {formatNumber(stock.score_breakdown.consistency || 0, 0)}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-sm text-white text-right font-mono">{formatNumber(stock.price)}</td>
                  <td className={`px-4 py-3 text-sm text-right font-mono ${getChangeColor(stock.change_pct)}`}>
                    {stock.change_pct > 0 ? '+' : ''}{formatNumber(stock.change_pct)}%
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300 text-right">{formatCurrency(stock.market_cap)}</td>
                  <td className="px-4 py-3 text-sm text-gray-300 text-right">{formatCurrency(stock.turnover)}</td>
                  <td className="px-4 py-3 text-sm text-gray-300 text-right">{formatNumber(stock.turnover_rate)}%</td>
                  <td className="px-4 py-3 text-sm text-right">
                    <Button
                      onClick={() => void handleAddToWatchlist(stock.code)}
                      variant="secondary"
                      size="sm"
                      isLoading={watchlistLoadingCode === stock.code}
                    >
                      加入自选
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : !loading && (
        <div className="bg-white/5 rounded-lg p-12 border border-cyan/20 text-center">
          <p className="text-gray-400">点击"开始筛选"按钮获取推荐股票</p>
          <p className="text-sm text-gray-500 mt-2">建议先选择一个预设方案或调整筛选条件</p>
        </div>
      )}
    </div>
  );
};

export default ScreeningPage;
