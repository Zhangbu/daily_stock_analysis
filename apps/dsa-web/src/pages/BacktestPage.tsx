import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Minus, X } from 'lucide-react';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { profileStrategiesApi } from '../api/profileStrategies';
import { ApiErrorAlert, Badge, Card, Checkbox, EmptyState, Pagination, Select, StatusDot, Tooltip } from '../components/common';
import type {
  BacktestResultItem,
  BacktestRunResponse,
  PerformanceMetrics,
  ProfileBacktestRunResponse,
} from '../types/backtest';
import type { ProfileMeta } from '../types/profileStrategies';

const BACKTEST_INPUT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const BACKTEST_COMPACT_INPUT_CLASS =
  'input-surface input-focus-glow h-10 rounded-xl border bg-transparent px-3 py-2 text-xs transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

function pct(value?: number | null): string {
  if (value == null) return '--';
  return `${value.toFixed(1)}%`;
}

function outcomeBadge(outcome?: string) {
  if (!outcome) return <Badge variant="default">--</Badge>;
  switch (outcome) {
    case 'win':
      return <Badge variant="success" glow>WIN</Badge>;
    case 'loss':
      return <Badge variant="danger" glow>LOSS</Badge>;
    case 'neutral':
      return <Badge variant="warning">NEUTRAL</Badge>;
    default:
      return <Badge variant="default">{outcome}</Badge>;
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge variant="success">completed</Badge>;
    case 'insufficient':
    case 'insufficient_data':
      return <Badge variant="warning">insufficient</Badge>;
    case 'error':
      return <Badge variant="danger">error</Badge>;
    default:
      return <Badge variant="default">{status}</Badge>;
  }
}

function actualMovementBadge(movement?: string | null) {
  switch (movement) {
    case 'up':
      return <Badge variant="success">UP</Badge>;
    case 'down':
      return <Badge variant="danger">DOWN</Badge>;
    case 'flat':
      return <Badge variant="warning">FLAT</Badge>;
    default:
      return <Badge variant="default">--</Badge>;
  }
}

function boolIcon(value?: boolean | null) {
  if (value === true) {
    return (
      <span className="backtest-status-chip backtest-status-chip-success" aria-label="yes">
        <StatusDot tone="success" className="backtest-status-chip-dot" />
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  }

  if (value === false) {
    return (
      <span className="backtest-status-chip backtest-status-chip-danger" aria-label="no">
        <StatusDot tone="danger" className="backtest-status-chip-dot" />
        <X className="h-3.5 w-3.5" />
      </span>
    );
  }

  return (
    <span className="backtest-status-chip backtest-status-chip-neutral" aria-label="unknown">
      <StatusDot tone="neutral" className="backtest-status-chip-dot" />
      <Minus className="h-3.5 w-3.5" />
    </span>
  );
}

const MetricRow: React.FC<{ label: string; value: string; accent?: boolean }> = ({ label, value, accent }) => (
  <div className="backtest-metric-row">
    <span className="label">{label}</span>
    <span className={`value ${accent ? 'accent' : ''}`}>{value}</span>
  </div>
);

const PerformanceCard: React.FC<{ metrics: PerformanceMetrics; title: string }> = ({ metrics, title }) => (
  <Card variant="gradient" padding="md" className="animate-fade-in">
    <div className="mb-3">
      <span className="label-uppercase">{title}</span>
    </div>
    <MetricRow label="Direction Accuracy" value={pct(metrics.directionAccuracyPct)} accent />
    <MetricRow label="Win Rate" value={pct(metrics.winRatePct)} accent />
    <MetricRow label="Avg Sim. Return" value={pct(metrics.avgSimulatedReturnPct)} />
    <MetricRow label="Avg Stock Return" value={pct(metrics.avgStockReturnPct)} />
    <MetricRow label="SL Trigger Rate" value={pct(metrics.stopLossTriggerRate)} />
    <MetricRow label="TP Trigger Rate" value={pct(metrics.takeProfitTriggerRate)} />
    <MetricRow label="Avg Days to Hit" value={metrics.avgDaysToFirstHit != null ? metrics.avgDaysToFirstHit.toFixed(1) : '--'} />
    <div className="backtest-metric-footer">
      <span className="text-xs text-muted-text">Evaluations</span>
      <span className="text-xs text-secondary-text font-mono">
        {Number(metrics.completedCount)} / {Number(metrics.totalEvaluations)}
      </span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted-text">W / L / N</span>
      <span className="text-xs font-mono">
        <span className="text-success">{metrics.winCount}</span>
        {' / '}
        <span className="text-danger">{metrics.lossCount}</span>
        {' / '}
        <span className="text-warning">{metrics.neutralCount}</span>
      </span>
    </div>
  </Card>
);

const RunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => (
  <div className="backtest-summary animate-fade-in">
    <span className="label">Processed: <span className="value">{data.processed}</span></span>
    <span className="label">Saved: <span className="value primary">{data.saved}</span></span>
    <span className="label">Completed: <span className="value success">{data.completed}</span></span>
    <span className="label">Insufficient: <span className="value warning">{data.insufficient}</span></span>
    {data.errors > 0 && (
      <span className="label">Errors: <span className="value danger">{data.errors}</span></span>
    )}
  </div>
);

const BacktestPage: React.FC = () => {
  useEffect(() => {
    document.title = '策略回测 - DSA';
  }, []);

  const [mode, setMode] = useState<'history' | 'profile'>('history');

  const [codeFilter, setCodeFilter] = useState('');
  const [analysisDateFrom, setAnalysisDateFrom] = useState('');
  const [analysisDateTo, setAnalysisDateTo] = useState('');
  const [evalDays, setEvalDays] = useState('');
  const [forceRerun, setForceRerun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const pageSize = 20;

  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);

  const [profileName, setProfileName] = useState('mag7');
  const [profileMeta, setProfileMeta] = useState<ProfileMeta | null>(null);
  const [profileStrategy, setProfileStrategy] = useState('');
  const [profileStocks, setProfileStocks] = useState<string[]>([]);
  const [profileOnlyPassed, setProfileOnlyPassed] = useState(true);
  const [profileBacktest, setProfileBacktest] = useState<ProfileBacktestRunResponse | null>(null);

  const effectiveWindowDays = evalDays ? parseInt(evalDays, 10) : overallPerf?.evalWindowDays;
  const isNextDayValidation = effectiveWindowDays === 1;
  const showNextDayActualColumns = isNextDayValidation;

  const fetchResults = useCallback(async (
    page = 1,
    code?: string,
    windowDays?: number,
    startDate?: string,
    endDate?: string,
  ) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({
        code: code || undefined,
        evalWindowDays: windowDays,
        analysisDateFrom: startDate || undefined,
        analysisDateTo: endDate || undefined,
        page,
        limit: pageSize,
      });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (err) {
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  const fetchPerformance = useCallback(async (
    code?: string,
    windowDays?: number,
    startDate?: string,
    endDate?: string,
  ) => {
    setIsLoadingPerf(true);
    try {
      const overall = await backtestApi.getOverallPerformance({
        evalWindowDays: windowDays,
        analysisDateFrom: startDate || undefined,
        analysisDateTo: endDate || undefined,
      });
      setOverallPerf(overall);

      if (code) {
        const stock = await backtestApi.getStockPerformance(code, {
          evalWindowDays: windowDays,
          analysisDateFrom: startDate || undefined,
          analysisDateTo: endDate || undefined,
        });
        setStockPerf(stock);
      } else {
        setStockPerf(null);
      }
      setPageError(null);
    } catch (err) {
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingPerf(false);
    }
  }, []);

  useEffect(() => {
    if (mode !== 'history') {
      return;
    }
    const init = async () => {
      const overall = await backtestApi.getOverallPerformance();
      setOverallPerf(overall);
      const windowDays = overall?.evalWindowDays;
      if (windowDays && !evalDays) {
        setEvalDays(String(windowDays));
      }
      fetchResults(1, undefined, windowDays, undefined, undefined);
    };
    void init();
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mode !== 'profile') {
      return;
    }
    const loadMeta = async () => {
      try {
        const payload = await profileStrategiesApi.getMeta(profileName);
        setProfileMeta(payload);
        setProfileStrategy(payload.defaultStrategy);
        setProfileStocks(payload.stockUniverse);
        setPageError(null);
      } catch (err) {
        setPageError(getParsedApiError(err));
      }
    };
    void loadMeta();
  }, [mode, profileName]);

  const handleRun = async () => {
    setIsRunning(true);
    setRunError(null);

    if (mode === 'profile') {
      try {
        const response = await backtestApi.runProfile({
          profileName,
          strategyName: profileStrategy,
          stockCodes: profileStocks,
          analysisDateFrom: analysisDateFrom || undefined,
          analysisDateTo: analysisDateTo || undefined,
          evalWindowDays: evalDays ? parseInt(evalDays, 10) : 10,
          onlyPassed: profileOnlyPassed,
        });
        setProfileBacktest(response);
      } catch (err) {
        setRunError(getParsedApiError(err));
      } finally {
        setIsRunning(false);
      }
      return;
    }

    setRunResult(null);
    try {
      const code = codeFilter.trim() || undefined;
      const evalWindowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const response = await backtestApi.run({
        code,
        force: forceRerun || undefined,
        minAgeDays: forceRerun ? 0 : undefined,
        evalWindowDays,
      });
      setRunResult(response);
      fetchResults(1, codeFilter.trim() || undefined, evalWindowDays, analysisDateFrom, analysisDateTo);
      fetchPerformance(codeFilter.trim() || undefined, evalWindowDays, analysisDateFrom, analysisDateTo);
    } catch (err) {
      setRunError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  const handleFilter = () => {
    if (mode !== 'history') {
      return;
    }
    const code = codeFilter.trim() || undefined;
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    setCurrentPage(1);
    fetchResults(1, code, windowDays, analysisDateFrom, analysisDateTo);
    fetchPerformance(code, windowDays, analysisDateFrom, analysisDateTo);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (mode === 'history' && e.key === 'Enter') {
      handleFilter();
    }
  };

  const handleShowNextDay = () => {
    if (mode !== 'history') {
      return;
    }
    const code = codeFilter.trim() || undefined;
    setEvalDays('1');
    setCurrentPage(1);
    fetchResults(1, code, 1, analysisDateFrom, analysisDateTo);
    fetchPerformance(code, 1, analysisDateFrom, analysisDateTo);
  };

  const totalPages = Math.ceil(totalResults / pageSize);
  const handlePageChange = (page: number) => {
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    fetchResults(page, codeFilter.trim() || undefined, windowDays, analysisDateFrom, analysisDateTo);
  };

  const profileStrategyOptions = useMemo(
    () => (profileMeta?.strategies || []).map((item) => ({ value: item.name, label: item.displayName })),
    [profileMeta],
  );

  const toggleSelectAllProfileStocks = () => {
    if (!profileMeta) {
      return;
    }
    const isAllSelected = profileStocks.length === profileMeta.stockUniverse.length;
    setProfileStocks(isAllSelected ? [] : profileMeta.stockUniverse);
  };

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      <header className="flex-shrink-0 border-b border-white/5 px-3 py-3 sm:px-4">
        <div className="mb-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => setMode('history')} className={`backtest-force-btn ${mode === 'history' ? 'active' : ''}`}>
            历史分析回测
          </button>
          <button type="button" onClick={() => setMode('profile')} className={`backtest-force-btn ${mode === 'profile' ? 'active' : ''}`}>
            Profile 策略回测
          </button>
        </div>

        <div className="flex max-w-6xl flex-wrap items-center gap-2">
          {mode === 'history' ? (
            <>
              <div className="relative min-w-0 flex-[1_1_220px]">
                <input
                  type="text"
                  value={codeFilter}
                  onChange={(e) => setCodeFilter(e.target.value.toUpperCase())}
                  onKeyDown={handleKeyDown}
                  placeholder="Filter by stock code (leave empty for all)"
                  disabled={isRunning}
                  className={BACKTEST_INPUT_CLASS}
                />
              </div>
              <button type="button" onClick={handleFilter} disabled={isLoadingResults} className="btn-secondary flex items-center gap-1.5 whitespace-nowrap">
                Filter
              </button>
            </>
          ) : (
            <>
              <div className="min-w-[12rem] flex-[0_1_12rem]">
                <Select
                  label="画像"
                  value={profileName}
                  onChange={setProfileName}
                  options={[
                    { value: 'mag7', label: 'Mag7' },
                    { value: 'nasdaq100', label: 'Nasdaq-100' },
                  ]}
                />
              </div>
              <div className="min-w-[15rem] flex-[1_1_15rem]">
                <Select
                  label="策略"
                  value={profileStrategy}
                  onChange={setProfileStrategy}
                  options={profileStrategyOptions}
                />
              </div>
            </>
          )}

          <div className="flex items-center gap-2 whitespace-nowrap lg:w-40 lg:justify-between">
            <span className="text-xs text-muted-text">Window</span>
            <input
              type="number"
              min={1}
              max={120}
              value={evalDays}
              onChange={(e) => setEvalDays(e.target.value)}
              placeholder="10"
              disabled={isRunning}
              className={`${BACKTEST_COMPACT_INPUT_CLASS} w-24 text-center tabular-nums`}
            />
          </div>

          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">From</span>
            <input
              type="date"
              aria-label="Analysis date from"
              value={analysisDateFrom}
              onChange={(e) => setAnalysisDateFrom(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRunning}
              className={`${BACKTEST_COMPACT_INPUT_CLASS} w-40 text-center tabular-nums`}
            />
          </div>

          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">To</span>
            <input
              type="date"
              aria-label="Analysis date to"
              value={analysisDateTo}
              onChange={(e) => setAnalysisDateTo(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRunning}
              className={`${BACKTEST_COMPACT_INPUT_CLASS} w-40 text-center tabular-nums`}
            />
          </div>

          {mode === 'history' ? (
            <button
              type="button"
              onClick={handleShowNextDay}
              disabled={isLoadingResults || isLoadingPerf}
              className={`backtest-force-btn ${isNextDayValidation ? 'active' : ''}`}
            >
              <span className="dot" />
              1D Validation
            </button>
          ) : null}

          <button
            type="button"
            onClick={() => setForceRerun(!forceRerun)}
            disabled={isRunning}
            className={`backtest-force-btn ${forceRerun ? 'active' : ''}`}
          >
            <span className="dot" />
            {mode === 'history' ? 'Force' : 'Refresh'}
          </button>

          <button type="button" onClick={handleRun} disabled={isRunning} className="btn-primary flex items-center gap-1.5 whitespace-nowrap">
            {isRunning ? 'Running...' : mode === 'history' ? 'Run Backtest' : 'Run Profile Backtest'}
          </button>
        </div>

        {mode === 'profile' && profileMeta ? (
          <div className="mt-3 rounded-2xl border border-white/5 bg-card/45 p-3">
            <div className="mb-2 text-xs text-muted-text">
              已选 {profileStocks.length} / {profileMeta.stockUniverse.length} 只股票
            </div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <button type="button" className="btn-secondary text-xs" onClick={toggleSelectAllProfileStocks}>
                {profileStocks.length === profileMeta.stockUniverse.length ? '全不选' : '全选'}
              </button>
              <button type="button" className="btn-secondary text-xs" onClick={() => setProfileStocks([])}>清空</button>
              <Checkbox
                label="仅统计通过策略阈值的信号"
                checked={profileOnlyPassed}
                onChange={() => setProfileOnlyPassed((prev) => !prev)}
              />
            </div>
            <div className="max-h-44 overflow-y-auto rounded-xl border border-white/5 p-2">
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {profileMeta.stockItems.map((item) => (
                  <label key={item.code} className="flex items-start gap-2 rounded-lg bg-base/40 px-2 py-2 text-sm">
                    <input
                      type="checkbox"
                      checked={profileStocks.includes(item.code)}
                      onChange={() => {
                        setProfileStocks((prev) => (
                          prev.includes(item.code)
                            ? prev.filter((code) => code !== item.code)
                            : [...prev, item.code]
                        ));
                      }}
                    />
                    <span>
                      <span className="font-medium text-foreground">{item.code}</span>
                      <span className="ml-1 text-secondary-text">{item.nameZh}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        ) : null}

        {runResult && mode === 'history' ? (
          <div className="mt-2 max-w-4xl">
            <RunSummary data={runResult} />
          </div>
        ) : null}

        {profileBacktest && mode === 'profile' ? (
          <div className="mt-2 max-w-5xl rounded-2xl border border-white/5 bg-card/45 px-4 py-3 text-sm text-secondary-text">
            <div className="flex flex-wrap gap-4">
              <span>Signals: <span className="text-foreground">{profileBacktest.summary.totalSignals}</span></span>
              <span>Win Rate: <span className="text-success">{pct(profileBacktest.summary.winRatePct)}</span></span>
              <span>Avg Return: <span className="text-foreground">{pct(profileBacktest.summary.avgReturnPct)}</span></span>
              <span>Avg Max: <span className="text-success">{pct(profileBacktest.summary.avgMaxReturnPct)}</span></span>
              <span>Avg Min: <span className="text-danger">{pct(profileBacktest.summary.avgMinReturnPct)}</span></span>
            </div>
          </div>
        ) : null}

        {runError ? <ApiErrorAlert error={runError} className="mt-2 max-w-4xl" /> : null}
        <p className="mt-2 text-xs text-muted-text">
          {mode === 'profile'
            ? 'Profile strategy backtest replays executable strategy signals on SQLite-backed daily bars for Mag7 and Nasdaq-100.'
            : isNextDayValidation
              ? 'Next-day validation mode compares AI predictions with the next trading day close.'
              : 'Use window = 1 to review AI predictions against the next trading day close.'}
        </p>
      </header>

      {mode === 'profile' ? (
        <main className="min-h-0 flex-1 overflow-y-auto p-3">
          {pageError ? <ApiErrorAlert error={pageError} className="mb-3" /> : null}
          {!profileBacktest || profileBacktest.items.length === 0 ? (
            <EmptyState
              title="No Profile Backtest Results"
              description="选择画像、策略和股票池后运行回测，这里会展示每次信号在持有窗口内的收益表现。"
              className="backtest-empty-state border-dashed"
            />
          ) : (
            <div className="animate-fade-in">
              <div className="mb-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {Object.entries(profileBacktest.summary.byCode).map(([code, item]) => (
                  <Card key={code} className="space-y-2">
                    <div className="text-sm font-semibold text-foreground">{code} · {item.stockName}</div>
                    <div className="text-xs text-secondary-text">Signals: {item.signals}</div>
                    <div className="text-xs text-secondary-text">Win Rate: {pct(item.winRatePct)}</div>
                    <div className="text-xs text-secondary-text">Avg Return: {pct(item.avgReturnPct)}</div>
                  </Card>
                ))}
              </div>
              <div className="backtest-table-wrapper">
                <table className="backtest-table min-w-[1080px] w-full text-sm">
                  <thead className="backtest-table-head">
                    <tr className="text-left">
                      <th className="backtest-table-head-cell">Stock</th>
                      <th className="backtest-table-head-cell">Signal Date</th>
                      <th className="backtest-table-head-cell">Entry / Exit</th>
                      <th className="backtest-table-head-cell">Grade</th>
                      <th className="backtest-table-head-cell">Verdict</th>
                      <th className="backtest-table-head-cell">Return</th>
                      <th className="backtest-table-head-cell">Max</th>
                      <th className="backtest-table-head-cell">Min</th>
                      <th className="backtest-table-head-cell">Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profileBacktest.items.map((row) => (
                      <tr key={`${row.code}-${row.analysisDate}-${row.entryDate}`} className="backtest-table-row">
                        <td className="backtest-table-cell backtest-table-code">
                          <div className="flex flex-col">
                            <span>{row.code}</span>
                            <span className="text-xs text-muted-text">{row.stockName}</span>
                          </div>
                        </td>
                        <td className="backtest-table-cell text-secondary-text">{row.analysisDate}</td>
                        <td className="backtest-table-cell text-secondary-text">
                          <div className="flex flex-col">
                            <span>{row.entryDate} @ {row.entryPrice.toFixed(2)}</span>
                            <span>{row.exitDate} @ {row.exitPrice.toFixed(2)}</span>
                          </div>
                        </td>
                        <td className="backtest-table-cell">
                          <Badge variant={row.grade === 'A' ? 'success' : row.grade === 'B' ? 'info' : row.grade === 'C' ? 'warning' : 'danger'}>
                            {row.grade} · {row.score}
                          </Badge>
                        </td>
                        <td className="backtest-table-cell max-w-[260px] text-secondary-text">{row.verdict}</td>
                        <td className="backtest-table-cell">
                          <span className={row.windowReturnPct > 0 ? 'text-success' : row.windowReturnPct < 0 ? 'text-danger' : 'text-secondary-text'}>
                            {pct(row.windowReturnPct)}
                          </span>
                        </td>
                        <td className="backtest-table-cell text-success">{pct(row.maxReturnPct)}</td>
                        <td className="backtest-table-cell text-danger">{pct(row.minReturnPct)}</td>
                        <td className="backtest-table-cell">{outcomeBadge(row.outcome)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      ) : (
        <main className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-3 lg:flex-row">
          <div className="flex max-h-[38vh] flex-col gap-3 overflow-y-auto lg:max-h-none lg:w-60 lg:flex-shrink-0">
            {isLoadingPerf ? (
              <div className="flex items-center justify-center py-8">
                <div className="backtest-spinner sm" />
              </div>
            ) : overallPerf ? (
              <PerformanceCard metrics={overallPerf} title="Overall Performance" />
            ) : (
              <EmptyState
                title="No Metrics Yet"
                description="Run a backtest to generate portfolio-level performance metrics."
                className="h-full min-h-[12rem] border-dashed bg-card/45 shadow-none"
              />
            )}

            {stockPerf ? <PerformanceCard metrics={stockPerf} title={`${stockPerf.code || codeFilter}`} /> : null}
          </div>

          <section className="min-h-0 flex-1 overflow-y-auto">
            {pageError ? <ApiErrorAlert error={pageError} className="mb-3" /> : null}
            {isLoadingResults ? (
              <div className="flex flex-col items-center justify-center h-64">
                <div className="backtest-spinner md" />
                <p className="mt-3 text-secondary-text text-sm">Loading results...</p>
              </div>
            ) : results.length === 0 ? (
              <EmptyState
                title="No Results"
                description="Run a backtest to evaluate historical analysis accuracy"
                className="backtest-empty-state border-dashed"
              />
            ) : (
              <div className="animate-fade-in">
                <div className="backtest-table-toolbar">
                  <div className="backtest-table-toolbar-meta">
                    <span className="label-uppercase">{isNextDayValidation ? 'Next-Day Validation' : 'Result Set'}</span>
                    <span className="text-xs text-secondary-text">
                      {codeFilter.trim() ? `Filtered by ${codeFilter.trim()}` : 'All stocks'}
                      {evalDays ? ` · ${evalDays} day window` : ''}
                      {analysisDateFrom ? ` · from ${analysisDateFrom}` : ''}
                      {analysisDateTo ? ` · to ${analysisDateTo}` : ''}
                    </span>
                  </div>
                  <span className="backtest-table-scroll-hint">Scroll horizontally on small screens</span>
                </div>
                <div className="backtest-table-wrapper">
                  <table className="backtest-table min-w-[840px] w-full text-sm">
                    <thead className="backtest-table-head">
                      <tr className="text-left">
                        <th className="backtest-table-head-cell">Stock</th>
                        <th className="backtest-table-head-cell">Analysis Date</th>
                        <th className="backtest-table-head-cell">AI Prediction</th>
                        <th className="backtest-table-head-cell">{showNextDayActualColumns ? 'Actual' : 'Window Return'}</th>
                        <th className="backtest-table-head-cell">{showNextDayActualColumns ? 'Accuracy' : 'Direction Match'}</th>
                        <th className="backtest-table-head-cell">Outcome</th>
                        <th className="backtest-table-head-cell">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.map((row) => (
                        <tr key={row.analysisHistoryId} className="backtest-table-row">
                          <td className="backtest-table-cell backtest-table-code">
                            <div className="flex flex-col">
                              <span>{row.code}</span>
                              <span className="text-xs text-muted-text">{row.stockName || '--'}</span>
                            </div>
                          </td>
                          <td className="backtest-table-cell text-secondary-text">{row.analysisDate || '--'}</td>
                          <td className="backtest-table-cell max-w-[220px] text-foreground">
                            {(row.trendPrediction || row.operationAdvice) ? (
                              <Tooltip content={[row.trendPrediction, row.operationAdvice].filter(Boolean).join(' / ')} focusable>
                                <div className="flex flex-col gap-1">
                                  <span className="block truncate">{row.trendPrediction || '--'}</span>
                                  <span className="block truncate text-xs text-secondary-text">{row.operationAdvice || '--'}</span>
                                </div>
                              </Tooltip>
                            ) : '--'}
                          </td>
                          <td className="backtest-table-cell">
                            <div className="flex items-center gap-2">
                              {actualMovementBadge(row.actualMovement)}
                              <span className={
                                row.actualReturnPct != null
                                  ? row.actualReturnPct > 0 ? 'text-success' : row.actualReturnPct < 0 ? 'text-danger' : 'text-secondary-text'
                                  : 'text-muted-text'
                              }>
                                {pct(row.actualReturnPct)}
                              </span>
                            </div>
                          </td>
                          <td className="backtest-table-cell">
                            <span className="flex items-center gap-2">
                              {boolIcon(row.directionCorrect)}
                              <span className="text-muted-text">{row.directionExpected || ''}</span>
                            </span>
                          </td>
                          <td className="backtest-table-cell">{outcomeBadge(row.outcome)}</td>
                          <td className="backtest-table-cell">{statusBadge(row.evalStatus)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4">
                  <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={handlePageChange} />
                </div>
                <p className="text-xs text-muted-text text-center mt-2">
                  {totalResults} result{totalResults !== 1 ? 's' : ''} total · page {currentPage} of {Math.max(totalPages, 1)}
                </p>
              </div>
            )}
          </section>
        </main>
      )}
    </div>
  );
};

export default BacktestPage;
