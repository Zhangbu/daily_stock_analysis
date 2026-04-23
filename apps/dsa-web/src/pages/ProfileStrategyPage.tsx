import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { profileStrategiesApi } from '../api/profileStrategies';
import { ApiErrorAlert, AppPage, Badge, Button, Card, Checkbox, Collapsible, EmptyState, InlineAlert, Input, Select } from '../components/common';
import type {
  ProfileMeta,
  ProfileResultItem,
  ProfileRunResponse,
  ProfileStockItem,
  ProfileStrategyOption,
} from '../types/profileStrategies';

type ProfileStrategyPageProps = {
  profileName: string;
  heroTitle: string;
  heroSubtitle: string;
};

type StoredProfileSnapshot = {
  strategyName: string;
  stockCodes: string[];
  results: ProfileResultItem[];
  savedAt: string;
};

type ComparisonBucket = {
  strategyName: string;
  strategyDisplayName: string;
  itemsByCode: Record<string, ProfileResultItem>;
};

type StockUniverseItem = {
  code: string;
  metadata: ProfileStockItem | null;
};

type StoredComparisonSnapshot = {
  stockCodes: string[];
  buckets: ComparisonBucket[];
  savedAt: string;
};

export const ProfileStrategyPage: React.FC<ProfileStrategyPageProps> = ({
  profileName,
  heroTitle,
  heroSubtitle,
}) => {
  const resultStorageKey = `dsa.profile.${profileName}.recent-result.v1`;
  const comparisonStorageKey = `dsa.profile.${profileName}.comparison-result.v1`;

  const [meta, setMeta] = useState<ProfileMeta | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [selectedStocks, setSelectedStocks] = useState<string[]>([]);
  const [results, setResults] = useState<ProfileResultItem[]>([]);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [comparisonSavedAt, setComparisonSavedAt] = useState<string | null>(null);
  const [isLoadingMeta, setIsLoadingMeta] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonBuckets, setComparisonBuckets] = useState<ComparisonBucket[]>([]);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [stockSearch, setStockSearch] = useState('');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [selectedOnly, setSelectedOnly] = useState(false);

  useEffect(() => {
    document.title = `${heroTitle} - DSA`;
  }, [heroTitle]);

  useEffect(() => {
    const loadMeta = async () => {
      setIsLoadingMeta(true);
      setError(null);
      try {
        const payload = await profileStrategiesApi.getMeta(profileName);
        const storedSnapshot = readStoredSnapshot(resultStorageKey);
        const storedComparison = readStoredComparisonSnapshot(comparisonStorageKey);

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
  }, [comparisonStorageKey, profileName, resultStorageKey]);

  const strategyOptions = useMemo(
    () => (meta?.strategies || []).map((item) => ({ value: item.name, label: item.displayName })),
    [meta],
  );

  const currentStrategy = useMemo(
    () => meta?.strategies.find((item) => item.name === selectedStrategy),
    [meta, selectedStrategy],
  );

  const stockMetadataMap = useMemo<Record<string, ProfileStockItem>>(
    () =>
      Object.fromEntries(
        (meta?.stockItems || []).map((item) => [item.code, item]),
      ),
    [meta],
  );

  const stockUniverseItems = useMemo<StockUniverseItem[]>(
    () =>
      (meta?.stockUniverse || []).map((code) => ({
        code,
        metadata: stockMetadataMap[code] || null,
      })),
    [meta, stockMetadataMap],
  );

  const sectorOptions = useMemo(() => {
    const sectors = Array.from(
      new Set(stockUniverseItems.map((item) => item.metadata?.sector).filter((item): item is string => Boolean(item))),
    );
    return [
      { value: 'all', label: '全部行业' },
      ...sectors.sort((left, right) => left.localeCompare(right, 'zh-CN')).map((sector) => ({
        value: sector,
        label: sector,
      })),
    ];
  }, [stockUniverseItems]);

  const filteredStockItems = useMemo(() => {
    const normalizedQuery = stockSearch.trim().toLowerCase();
    return stockUniverseItems.filter((item) => {
      if (selectedOnly && !selectedStocks.includes(item.code)) {
        return false;
      }
      if (sectorFilter !== 'all' && item.metadata?.sector !== sectorFilter) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      const haystack = [
        item.code,
        item.metadata?.nameEn || '',
        item.metadata?.nameZh || '',
        item.metadata?.sector || '',
        item.metadata?.industry || '',
      ].join(' ').toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [sectorFilter, selectedOnly, selectedStocks, stockSearch, stockUniverseItems]);

  const comparisonRows = useMemo(() => {
    if (!comparisonBuckets.length) {
      return [];
    }
    return selectedStocks.map((code) => ({
      code,
      metadata: stockMetadataMap[code] || null,
      strategies: comparisonBuckets.map((bucket) => ({
        strategyName: bucket.strategyName,
        strategyDisplayName: bucket.strategyDisplayName,
        item: bucket.itemsByCode[code] || null,
      })),
    }));
  }, [comparisonBuckets, selectedStocks, stockMetadataMap]);

  const groupedFilteredStockItems = useMemo(() => {
    const groups = new Map<string, StockUniverseItem[]>();
    for (const item of filteredStockItems) {
      const sector = item.metadata?.sector || '未分类';
      const bucket = groups.get(sector) || [];
      bucket.push(item);
      groups.set(sector, bucket);
    }

    return Array.from(groups.entries())
      .map(([sector, items]) => ({
        sector,
        items: items.sort((left, right) => left.code.localeCompare(right.code)),
      }))
      .sort((left, right) => {
        const selectedDelta = right.items.filter((item) => selectedStocks.includes(item.code)).length
          - left.items.filter((item) => selectedStocks.includes(item.code)).length;
        if (selectedDelta !== 0) {
          return selectedDelta;
        }
        return left.sector.localeCompare(right.sector, 'zh-CN');
      });
  }, [filteredStockItems, selectedStocks]);

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

  const selectFilteredStocks = () => {
    const filteredCodes = filteredStockItems.map((item) => item.code);
    setSelectedStocks((prev) => Array.from(new Set([...prev, ...filteredCodes])));
  };

  const clearSelectedStocks = () => {
    setSelectedStocks([]);
  };

  const clearStoredSnapshot = () => {
    window.localStorage.removeItem(resultStorageKey);
    window.localStorage.removeItem(comparisonStorageKey);
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
      const payload = await profileStrategiesApi.run(profileName, {
        strategyName: selectedStrategy,
        stockCodes: selectedStocks,
      });
      setResults(payload.results);
      const savedAt = new Date().toISOString();
      setLastSavedAt(savedAt);
      writeStoredSnapshot(resultStorageKey, {
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
          const payload = await profileStrategiesApi.run(profileName, {
            strategyName: strategy.name,
            stockCodes: selectedStocks,
          });
          return createComparisonBucket(strategy, payload);
        }),
      );
      setComparisonBuckets(responses);
      const savedAt = new Date().toISOString();
      setComparisonSavedAt(savedAt);
      writeStoredComparisonSnapshot(comparisonStorageKey, {
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
    const target = document.getElementById(`${profileName}-compare-${code}`) ?? document.getElementById(`${profileName}-result-${code}`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <AppPage className="space-y-6">
      <div className="space-y-6">
        <Card variant="gradient" title={heroTitle} subtitle={heroSubtitle}>
          <div className="space-y-5">
            <p className="text-sm leading-6 text-secondary-text">
              {meta?.description || '基于 yfinance 日K数据的策略画像分析入口。'}
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
              <InlineAlert variant="info" title="加载中" message="正在读取策略画像配置..." />
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
                      <div className="text-xs text-secondary-text">
                        已选 {selectedStocks.length} / {meta.stockUniverse.length}，当前筛选显示 {filteredStockItems.length} 只。
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedStocks(meta.stockUniverse)}
                      >
                        全选
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={selectFilteredStocks}
                        disabled={filteredStockItems.length === 0}
                      >
                        勾选筛选结果
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={clearSelectedStocks}
                        disabled={selectedStocks.length === 0}
                      >
                        清空已选
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
                  <div className="grid gap-3 lg:grid-cols-[minmax(0,1.3fr)_minmax(12rem,0.8fr)]">
                    <Input
                      label="搜索"
                      value={stockSearch}
                      onChange={(event) => setStockSearch(event.target.value)}
                      placeholder="搜索代码、中文名、英文名或行业"
                    />
                    <Select
                      label="行业"
                      value={sectorFilter}
                      onChange={setSectorFilter}
                      options={sectorOptions}
                      placeholder=""
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border/60 bg-base/30 px-4 py-3">
                    <Checkbox
                      label="只看已选"
                      checked={selectedOnly}
                      onChange={() => setSelectedOnly((prev) => !prev)}
                    />
                    {sectorFilter !== 'all' ? (
                      <Badge variant="info">{sectorFilter}</Badge>
                    ) : null}
                    {stockSearch.trim() ? (
                      <Badge variant="default">搜索: {stockSearch.trim()}</Badge>
                    ) : null}
                  </div>
                  <div className="space-y-3">
                    {groupedFilteredStockItems.map(({ sector, items }, index) => {
                      const selectedCount = items.filter((item) => selectedStocks.includes(item.code)).length;
                      return (
                        <Collapsible
                          key={sector}
                          title={`${sector} · ${items.length} 只`}
                          defaultOpen={index < 2 || selectedCount > 0 || sectorFilter !== 'all' || Boolean(stockSearch.trim())}
                          className="bg-base/20"
                          icon={<Badge variant={getSectorBadgeVariant(sector)}>{selectedCount} 已选</Badge>}
                        >
                          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-secondary-text">
                            <span>本组已选 {selectedCount} / {items.length}</span>
                            <Badge variant={getSectorBadgeVariant(sector)}>{sector}</Badge>
                          </div>
                          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                            {items.map(({ code, metadata }) => (
                              <div key={code} className="rounded-xl border border-border/70 bg-base/40 px-3 py-3">
                                <Checkbox
                                  label=""
                                  checked={selectedStocks.includes(code)}
                                  onChange={() => toggleStock(code)}
                                  containerClassName="items-start justify-between"
                                />
                                <div className="mt-2 space-y-2 pl-7">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-sm font-semibold text-foreground">{code}</span>
                                    {metadata?.sector ? (
                                      <Badge variant={getSectorBadgeVariant(metadata.sector)}>{metadata.sector}</Badge>
                                    ) : null}
                                  </div>
                                  {metadata ? (
                                    <>
                                      <div className="text-sm text-foreground">{metadata.nameZh}</div>
                                      <div className="text-xs text-secondary-text">
                                        {metadata.nameEn}
                                        {metadata.industry ? ` · ${metadata.industry}` : ''}
                                      </div>
                                    </>
                                  ) : (
                                    <div className="text-xs text-secondary-text">暂未配置名称和行业信息</div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </Collapsible>
                      );
                    })}
                  </div>
                  {filteredStockItems.length === 0 ? (
                    <EmptyState
                      title="没有匹配股票"
                      description="可以换个关键词、切换行业，或者关闭“只看已选”后再试。"
                      className="min-h-[180px]"
                    />
                  ) : null}
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
                  运行策略
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
                    id={`${profileName}-compare-${row.code}`}
                    className="scroll-mt-24 rounded-2xl border border-border/70 bg-base/30 p-4"
                  >
                    <div className="mb-3 flex items-center gap-2">
                      <div>
                        <div className="text-base font-semibold text-foreground">{formatStockHeadline(row.code, row.metadata)}</div>
                        {row.metadata ? (
                          <div className="mt-1 text-xs text-secondary-text">
                            {row.metadata.nameEn}
                            {row.metadata.industry ? ` · ${row.metadata.industry}` : ''}
                          </div>
                        ) : null}
                      </div>
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
                              <div className="text-xs text-secondary-text">入场区：{item.signal.entryZone}</div>
                              <div className="text-xs text-secondary-text">止损位：{item.signal.stopLoss}</div>
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
              <div key={`${item.strategyName}-${item.code}`} id={`${profileName}-result-${item.code}`} className="scroll-mt-24">
                <Card
                  title={`${formatStockHeadline(item.code, stockMetadataMap[item.code] || null)} · ${item.signal.verdict}`}
                  subtitle={`Grade ${item.signal.grade} · Score ${item.signal.score}`}
                  className="space-y-4"
                >
                  {stockMetadataMap[item.code] ? (
                    <div className="flex flex-wrap items-center gap-2 text-sm text-secondary-text">
                      <span>{stockMetadataMap[item.code]?.nameEn}</span>
                      {stockMetadataMap[item.code]?.sector ? (
                        <Badge variant={getSectorBadgeVariant(stockMetadataMap[item.code]?.sector || '')}>
                          {stockMetadataMap[item.code]?.sector}
                        </Badge>
                      ) : null}
                      {stockMetadataMap[item.code]?.industry ? (
                        <Badge variant="default">{stockMetadataMap[item.code]?.industry}</Badge>
                      ) : null}
                    </div>
                  ) : null}
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

function createComparisonBucket(strategy: ProfileStrategyOption, payload: ProfileRunResponse): ComparisonBucket {
  const itemsByCode: Record<string, ProfileResultItem> = {};
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

function getSectorBadgeVariant(sector: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  if (sector === '信息技术' || sector === '通信服务') {
    return 'info';
  }
  if (sector === '医疗保健') {
    return 'success';
  }
  if (sector === '能源') {
    return 'danger';
  }
  if (sector === '可选消费' || sector === '必需消费') {
    return 'warning';
  }
  return 'default';
}

function formatStockHeadline(code: string, metadata: ProfileStockItem | null): string {
  if (!metadata) {
    return code;
  }
  return `${code} · ${metadata.nameZh}`;
}

function readStoredSnapshot(storageKey: string): StoredProfileSnapshot | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<StoredProfileSnapshot>;
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
      results: parsed.results as ProfileResultItem[],
      savedAt: parsed.savedAt,
    };
  } catch {
    return null;
  }
}

function writeStoredSnapshot(storageKey: string, snapshot: StoredProfileSnapshot): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(snapshot));
}

function readStoredComparisonSnapshot(storageKey: string): StoredComparisonSnapshot | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(storageKey);
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

function writeStoredComparisonSnapshot(storageKey: string, snapshot: StoredComparisonSnapshot): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(snapshot));
}

function formatSavedAt(savedAt: string): string {
  const parsed = new Date(savedAt);
  if (Number.isNaN(parsed.getTime())) {
    return savedAt;
  }
  return parsed.toLocaleString();
}

export default ProfileStrategyPage;
