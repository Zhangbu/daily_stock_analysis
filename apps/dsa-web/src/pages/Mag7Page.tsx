import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, AppPage, Badge, Button, Card, Checkbox, EmptyState, InlineAlert, Select } from '../components/common';
import { mag7Api } from '../api/mag7';
import type { Mag7ProfileMeta, Mag7ResultItem, Mag7RunResponse, Mag7StrategyOption } from '../types/mag7';

const MAG7_RECENT_RESULT_STORAGE_KEY = 'dsa.mag7.recent-result.v1';
const MAG7_COMPARISON_STORAGE_KEY = 'dsa.mag7.comparison-result.v1';

type StoredMag7Snapshot = {
  strategyName: string;
  stockCodes: string[];
  results: Mag7ResultItem[];
  savedAt: string;
};

type ComparisonBucket = {
  strategyName: string;
  strategyDisplayName: string;
  itemsByCode: Record<string, Mag7ResultItem>;
};

type StoredComparisonSnapshot = {
  stockCodes: string[];
  buckets: ComparisonBucket[];
  savedAt: string;
};

const Mag7Page: React.FC = () => {
  const [meta, setMeta] = useState<Mag7ProfileMeta | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [selectedStocks, setSelectedStocks] = useState<string[]>([]);
  const [results, setResults] = useState<Mag7ResultItem[]>([]);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [comparisonSavedAt, setComparisonSavedAt] = useState<string | null>(null);
  const [isLoadingMeta, setIsLoadingMeta] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonBuckets, setComparisonBuckets] = useState<ComparisonBucket[]>([]);
  const [error, setError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    document.title = 'Mag7 策略 - DSA';
  }, []);

  useEffect(() => {
    const loadMeta = async () => {
      setIsLoadingMeta(true);
      setError(null);
      try {
        const payload = await mag7Api.getMeta();
        const storedSnapshot = readStoredSnapshot();
        const storedComparison = readStoredComparisonSnapshot();

        setMeta(payload);
        setSelectedStrategy(storedSnapshot?.strategyName || payload.defaultStrategy);
        setSelectedStocks(
          storedSnapshot?.stockCodes.length
            ? storedSnapshot.stockCodes
            : storedComparison?.stockCodes.length
              ? storedComparison.stockCodes
              : payload.stockUniverse
        );
        setResults(storedSnapshot?.results || []);
        setLastSavedAt(storedSnapshot?.savedAt || null);
        setComparisonBuckets(storedComparison?.buckets || []);
        setComparisonSavedAt(storedComparison?.savedAt || null);
      } catch (err) {
        setError(getParsedApiError(err));
      } finally {
        setIsLoadingMeta(false);
      }
    };

    void loadMeta();
  }, []);

  const strategyOptions = useMemo(
    () => (meta?.strategies || []).map((item) => ({ value: item.name, label: item.displayName })),
    [meta],
  );

  const currentStrategy = useMemo(
    () => meta?.strategies.find((item) => item.name === selectedStrategy),
    [meta, selectedStrategy],
  );

  const comparisonRows = useMemo(() => {
    if (!comparisonBuckets.length) {
      return [];
    }
    return selectedStocks.map((code) => ({
      code,
      strategies: comparisonBuckets.map((bucket) => ({
        strategyName: bucket.strategyName,
        strategyDisplayName: bucket.strategyDisplayName,
        item: bucket.itemsByCode[code] || null,
      })),
    }));
  }, [comparisonBuckets, selectedStocks]);

  const quickNavCodes = useMemo(() => {
    const seen = new Set<string>();
    const codes: string[] = [];
    for (const item of results) {
      if (!seen.has(item.code)) {
        seen.add(item.code);
        codes.push(item.code);
      }
    }
    if (!codes.length) {
      for (const row of comparisonRows) {
        if (!seen.has(row.code)) {
          seen.add(row.code);
          codes.push(row.code);
        }
      }
    }
    return codes;
  }, [comparisonRows, results]);

  const toggleStock = (code: string) => {
    setSelectedStocks((prev) =>
      prev.includes(code) ? prev.filter((item) => item !== code) : [...prev, code]
    );
  };

  const clearStoredSnapshot = () => {
    window.localStorage.removeItem(MAG7_RECENT_RESULT_STORAGE_KEY);
    window.localStorage.removeItem(MAG7_COMPARISON_STORAGE_KEY);
    setLastSavedAt(null);
    setComparisonSavedAt(null);
    setResults([]);
    setComparisonBuckets([]);
    if (meta) {
      setSelectedStrategy(meta.defaultStrategy);
      setSelectedStocks(meta.stockUniverse);
    }
  };

  const runAnalysis = async () => {
    if (!selectedStrategy || selectedStocks.length === 0) {
      return;
    }
    setIsRunning(true);
    setError(null);
    try {
      const payload = await mag7Api.run({
        strategyName: selectedStrategy,
        stockCodes: selectedStocks,
      });
      setResults(payload.results);
      const savedAt = new Date().toISOString();
      setLastSavedAt(savedAt);
      writeStoredSnapshot({
        strategyName: selectedStrategy,
        stockCodes: selectedStocks,
        results: payload.results,
        savedAt,
      });
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  const runComparison = async () => {
    if (!meta || selectedStocks.length === 0) {
      return;
    }
    setIsComparing(true);
    setError(null);
    try {
      const responses = await Promise.all(
        meta.strategies.map(async (strategy) => {
          const payload = await mag7Api.run({
            strategyName: strategy.name,
            stockCodes: selectedStocks,
          });
          return createComparisonBucket(strategy, payload);
        }),
      );
      setComparisonBuckets(responses);
      const savedAt = new Date().toISOString();
      setComparisonSavedAt(savedAt);
      writeStoredComparisonSnapshot({
        stockCodes: selectedStocks,
        buckets: responses,
        savedAt,
      });
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsComparing(false);
    }
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const scrollToStock = (code: string) => {
    const target = document.getElementById(`mag7-compare-${code}`) ?? document.getElementById(`mag7-result-${code}`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <AppPage className="space-y-6">
      <div className="space-y-6">
        <Card variant="gradient" title="Mag7 Strategy Lab" subtitle="US Big Tech">
          <div className="space-y-5">
            <p className="text-sm leading-6 text-secondary-text">
              {meta?.description || '针对美股七姐妹的专用策略入口，当前固定使用 yfinance 日K数据。'}
            </p>

            {lastSavedAt ? (
              <InlineAlert
                variant="info"
                title="最近一次分析结果已恢复"
                message={`保存时间：${formatSavedAt(lastSavedAt)}`}
              />
            ) : null}

            {comparisonSavedAt ? (
              <InlineAlert
                variant="info"
                title="最近一次对比结果已恢复"
                message={`保存时间：${formatSavedAt(comparisonSavedAt)}`}
              />
            ) : null}

            {error ? <ApiErrorAlert error={error} /> : null}

            {isLoadingMeta ? (
              <InlineAlert variant="info" title="加载中" message="正在读取 Mag7 策略配置..." />
            ) : meta ? (
              <>
                <Select
                  label="策略"
                  value={selectedStrategy}
                  onChange={setSelectedStrategy}
                  options={strategyOptions}
                />

                {currentStrategy ? (
                  <div className="rounded-2xl border border-border/70 bg-base/50 p-4">
                    <div className="text-sm font-semibold text-foreground">{currentStrategy.displayName}</div>
                    <div className="mt-1 text-sm leading-6 text-secondary-text">{currentStrategy.description}</div>
                  </div>
                ) : null}

                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-foreground">股票池</div>
                      <div className="text-xs text-secondary-text">默认七姐妹，可按需勾选子集。</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedStocks(meta.stockUniverse)}
                      >
                        全选
                      </Button>
                      {(lastSavedAt || comparisonSavedAt) ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={clearStoredSnapshot}
                        >
                          清空缓存
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {meta.stockUniverse.map((code) => (
                      <div key={code} className="rounded-xl border border-border/70 bg-base/40 px-3 py-2">
                        <Checkbox
                          label={code}
                          checked={selectedStocks.includes(code)}
                          onChange={() => toggleStock(code)}
                          containerClassName="justify-between"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <Button
                  variant="primary"
                  size="lg"
                  className="w-full"
                  isLoading={isRunning}
                  loadingText="策略运行中..."
                  disabled={!selectedStrategy || selectedStocks.length === 0}
                  onClick={() => void runAnalysis()}
                >
                  运行 Mag7 策略
                </Button>
                <Button
                  variant="secondary"
                  size="lg"
                  className="w-full"
                  isLoading={isComparing}
                  loadingText="对比中..."
                  disabled={selectedStocks.length === 0}
                  onClick={() => void runComparison()}
                >
                  对比三套策略
                </Button>
              </>
            ) : null}
          </div>
        </Card>

        <div className="space-y-4">
          {comparisonRows.length > 0 ? (
            <Card title="策略对比视图" subtitle="Compare Strategies" className="space-y-4">
              <div className="text-sm text-secondary-text">
                按股票横向查看三套策略的评级、评分和结论，方便快速判断当前更适合哪种打法。
              </div>
              <div className="space-y-4">
                {comparisonRows.map((row) => (
                  <div
                    key={row.code}
                    id={`mag7-compare-${row.code}`}
                    className="scroll-mt-24 rounded-2xl border border-border/70 bg-base/30 p-4"
                  >
                    <div className="mb-3 flex items-center gap-2">
                      <div className="text-base font-semibold text-foreground">{row.code}</div>
                      <Badge variant="default">{row.strategies.filter((entry) => entry.item?.signal.passed).length} / {row.strategies.length} 通过</Badge>
                    </div>
                    <div className="grid gap-3 xl:grid-cols-3">
                      {row.strategies.map(({ strategyName, strategyDisplayName, item }) => (
                        <div key={`${row.code}-${strategyName}`} className="rounded-xl border border-border/70 bg-base/40 p-4">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <div className="text-sm font-semibold text-foreground">{strategyDisplayName}</div>
                            {item ? (
                              <Badge variant={getGradeBadgeVariant(item.signal.grade)}>
                                {item.signal.grade} · {item.signal.score}
                              </Badge>
                            ) : (
                              <Badge variant="default">无结果</Badge>
                            )}
                          </div>
                          {item ? (
                            <div className="space-y-3">
                              <div className="text-sm text-secondary-text">{item.signal.verdict}</div>
                              <div className="flex flex-wrap gap-2">
                                <Badge variant={getTrendBadgeVariant(item.trend.trendStatus)}>{item.trend.trendStatus}</Badge>
                                <Badge variant={getSignalBadgeVariant(item.trend.buySignal)}>{item.trend.buySignal}</Badge>
                              </div>
                              <div className="text-xs text-secondary-text">
                                入场区：{item.signal.entryZone}
                              </div>
                              <div className="text-xs text-secondary-text">
                                止损位：{item.signal.stopLoss}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}

          {results.length === 0 ? (
            <EmptyState
              title="等待运行"
              description="选择策略和股票池后运行分析，这里会显示评级、入场区、止损位和核心理由。"
              className="h-full min-h-[340px]"
            />
          ) : (
            results.map((item) => (
              <div key={`${item.strategyName}-${item.code}`} id={`mag7-result-${item.code}`} className="scroll-mt-24">
                <Card
                  title={`${item.code} · ${item.signal.verdict}`}
                  subtitle={`Grade ${item.signal.grade} · Score ${item.signal.score}`}
                  className="space-y-4"
                >
                  <div className="grid gap-3 md:grid-cols-4">
                    <div className="rounded-xl border border-border/70 bg-base/40 p-3">
                      <div className="text-xs text-secondary-text">趋势</div>
                      <div className="mt-2">
                        <Badge variant={getTrendBadgeVariant(item.trend.trendStatus)}>{item.trend.trendStatus}</Badge>
                      </div>
                    </div>
                    <div className="rounded-xl border border-border/70 bg-base/40 p-3">
                      <div className="text-xs text-secondary-text">技术信号</div>
                      <div className="mt-2">
                        <Badge variant={getSignalBadgeVariant(item.trend.buySignal)}>{item.trend.buySignal}</Badge>
                      </div>
                    </div>
                    <div className="rounded-xl border border-border/70 bg-base/40 p-3">
                      <div className="text-xs text-secondary-text">入场区</div>
                      <div className="mt-1 text-sm font-semibold text-foreground">{item.signal.entryZone}</div>
                    </div>
                    <div className="rounded-xl border border-border/70 bg-base/40 p-3">
                      <div className="text-xs text-secondary-text">止损位</div>
                      <div className="mt-1 text-sm font-semibold text-foreground">{item.signal.stopLoss}</div>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-5">
                    {[
                      ['Price', item.signal.metrics.price],
                      ['MA5', item.trend.ma5],
                      ['MA10', item.trend.ma10],
                      ['MA20', item.trend.ma20],
                      ['Volume x5D', item.trend.volumeRatio5d],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-xl border border-border/70 bg-base/30 p-3">
                        <div className="text-xs text-secondary-text">{label}</div>
                        <div className="mt-1 text-sm font-semibold text-foreground">
                          {typeof value === 'number' ? value.toFixed(2) : value}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                      <div className="text-sm font-semibold text-foreground">策略理由</div>
                      <div className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
                        {item.signal.reasons.map((reason) => (
                          <div key={reason}>- {reason}</div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
                      <div className="text-sm font-semibold text-foreground">风险提示</div>
                      <div className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
                        {item.signal.risks.length > 0 ? (
                          item.signal.risks.map((risk) => <div key={risk}>- {risk}</div>)
                        ) : (
                          <div>- 当前未触发显著附加风险。</div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border/70 bg-base/30 p-4 text-sm text-secondary-text">
                    <div className="mb-3 flex flex-wrap gap-2">
                      <Badge variant={getGradeBadgeVariant(item.signal.grade)} size="md">
                        Grade {item.signal.grade}
                      </Badge>
                      <Badge variant={item.signal.passed ? 'success' : 'warning'} size="md">
                        {item.signal.passed ? '通过策略阈值' : '未过策略阈值'}
                      </Badge>
                    </div>
                    <span className="font-semibold text-foreground">目标提示：</span>
                    {item.signal.targetHint}
                  </div>
                </Card>
              </div>
            ))
          )}
        </div>
      </div>

      {quickNavCodes.length > 0 ? (
        <div className="fixed bottom-6 right-6 z-30 flex flex-col items-end gap-2">
          <div className="rounded-2xl border border-border/70 bg-base/80 p-2 shadow-soft-card backdrop-blur">
            <div className="mb-2 px-2 text-[11px] font-medium uppercase tracking-[0.16em] text-secondary-text">
              Quick Nav
            </div>
            <div className="flex max-w-[11rem] flex-wrap justify-end gap-2">
              {quickNavCodes.map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => scrollToStock(code)}
                  className="rounded-full border border-cyan/20 bg-cyan/8 px-2.5 py-1 text-xs font-medium text-cyan transition hover:bg-cyan/14"
                >
                  {code}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={scrollToTop}
            className="rounded-full border border-border/70 bg-base/85 px-3 py-2 text-xs font-medium text-foreground shadow-soft-card backdrop-blur transition hover:border-cyan/30 hover:text-cyan"
          >
            回到顶部
          </button>
        </div>
      ) : null}
    </AppPage>
  );
};

export default Mag7Page;

function readStoredSnapshot(): StoredMag7Snapshot | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(MAG7_RECENT_RESULT_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<StoredMag7Snapshot>;
    if (
      !parsed
      || typeof parsed.strategyName !== 'string'
      || !Array.isArray(parsed.stockCodes)
      || !Array.isArray(parsed.results)
      || typeof parsed.savedAt !== 'string'
    ) {
      return null;
    }

    return {
      strategyName: parsed.strategyName,
      stockCodes: parsed.stockCodes.filter((item): item is string => typeof item === 'string'),
      results: parsed.results as Mag7ResultItem[],
      savedAt: parsed.savedAt,
    };
  } catch {
    return null;
  }
}

function writeStoredSnapshot(snapshot: StoredMag7Snapshot): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(MAG7_RECENT_RESULT_STORAGE_KEY, JSON.stringify(snapshot));
}

function readStoredComparisonSnapshot(): StoredComparisonSnapshot | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(MAG7_COMPARISON_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<StoredComparisonSnapshot>;
    if (
      !parsed
      || !Array.isArray(parsed.stockCodes)
      || !Array.isArray(parsed.buckets)
      || typeof parsed.savedAt !== 'string'
    ) {
      return null;
    }

    return {
      stockCodes: parsed.stockCodes.filter((item): item is string => typeof item === 'string'),
      buckets: parsed.buckets as ComparisonBucket[],
      savedAt: parsed.savedAt,
    };
  } catch {
    return null;
  }
}

function writeStoredComparisonSnapshot(snapshot: StoredComparisonSnapshot): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(MAG7_COMPARISON_STORAGE_KEY, JSON.stringify(snapshot));
}

function formatSavedAt(savedAt: string): string {
  const parsed = new Date(savedAt);
  if (Number.isNaN(parsed.getTime())) {
    return savedAt;
  }
  return parsed.toLocaleString();
}

function createComparisonBucket(strategy: Mag7StrategyOption, payload: Mag7RunResponse): ComparisonBucket {
  const itemsByCode: Record<string, Mag7ResultItem> = {};
  for (const item of payload.results) {
    itemsByCode[item.code] = item;
  }
  return {
    strategyName: strategy.name,
    strategyDisplayName: strategy.displayName,
    itemsByCode,
  };
}

function getTrendBadgeVariant(trendStatus: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  if (trendStatus.includes('强势多头') || trendStatus.includes('多头')) {
    return 'success';
  }
  if (trendStatus.includes('盘整')) {
    return 'info';
  }
  if (trendStatus.includes('弱势空头')) {
    return 'warning';
  }
  if (trendStatus.includes('空头')) {
    return 'danger';
  }
  return 'default';
}

function getSignalBadgeVariant(signal: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  if (signal.includes('强烈买入') || signal.includes('买入')) {
    return 'success';
  }
  if (signal.includes('持有')) {
    return 'info';
  }
  if (signal.includes('观望')) {
    return 'warning';
  }
  if (signal.includes('卖出')) {
    return 'danger';
  }
  return 'default';
}

function getGradeBadgeVariant(grade: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  if (grade === 'A') {
    return 'success';
  }
  if (grade === 'B') {
    return 'info';
  }
  if (grade === 'C') {
    return 'warning';
  }
  if (grade === 'D') {
    return 'danger';
  }
  return 'default';
}
