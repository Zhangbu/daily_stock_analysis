import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, BriefcaseBusiness, CircleDollarSign, RefreshCw, ShieldAlert, TrendingUp } from 'lucide-react';
import { portfolioApi } from '../api/portfolio';
import { getParsedApiError } from '../api/error';
import type { ParsedApiError } from '../api/error';
import {
  ApiErrorAlert,
  AppPage,
  Badge,
  Button,
  EmptyState,
  InlineAlert,
  PageHeader,
  SectionCard,
  Select,
  StatCard,
} from '../components/common';
import type {
  PortfolioAccountItem,
  PortfolioCostMethod,
  PortfolioPositionItem,
  PortfolioRiskResponse,
  PortfolioSnapshotResponse,
} from '../types/portfolio';

type AccountOption = 'all' | string;
type MarketFilter = 'all' | 'cn' | 'hk' | 'us';
type ActionTone = 'success' | 'warning' | 'danger' | 'info';

type HoldingView = {
  symbol: string;
  market: string;
  quantity: number;
  avgCost: number;
  lastPrice: number;
  marketValueBase: number;
  unrealizedPnlBase: number;
  pnlPct: number | null;
  accountCount: number;
  accountNames: string[];
  concentrationWeightPct: number;
  stopLossTriggered: boolean;
  stopLossNear: boolean;
  maxLossPct: number | null;
  actionTitle: string;
  actionReason: string;
  actionTone: ActionTone;
  priority: number;
};

type PositionSeed = PortfolioPositionItem & {
  accountId: number;
  accountName: string;
};

function formatMoney(value: number | undefined | null, currency = 'CNY'): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${currency} ${Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatPct(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}%`;
}

function formatMarketLabel(value: string): string {
  if (value === 'cn') return 'A股';
  if (value === 'hk') return '港股';
  if (value === 'us') return '美股';
  return value || '未知';
}

function normalizeValue(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

function getActionVariant(tone: ActionTone): 'success' | 'warning' | 'danger' | 'info' {
  return tone;
}

function buildHoldingView(snapshot: PortfolioSnapshotResponse, risk?: PortfolioRiskResponse | null): HoldingView[] {
  const seeds: PositionSeed[] = [];
  for (const account of snapshot.accounts || []) {
    for (const position of account.positions || []) {
      seeds.push({
        ...position,
        accountId: account.accountId,
        accountName: account.accountName,
      });
    }
  }

  const concentrationMap = new Map<string, number>();
  for (const item of risk?.concentration.topPositions || []) {
    concentrationMap.set(item.symbol.toUpperCase(), normalizeValue(item.weightPct));
  }

  const stopLossMap = new Map<string, { triggered: boolean; near: boolean; maxLossPct: number | null }>();
  for (const item of risk?.stopLoss.items || []) {
    const key = item.symbol.toUpperCase();
    const current = stopLossMap.get(key) || { triggered: false, near: false, maxLossPct: null };
    const lossPct = normalizeValue(item.lossPct);
    stopLossMap.set(key, {
      triggered: current.triggered || Boolean(item.isTriggered),
      near: current.near || (!item.isTriggered && normalizeValue(item.nearThresholdPct) > 0),
      maxLossPct: current.maxLossPct == null ? lossPct : Math.min(current.maxLossPct, lossPct),
    });
  }

  const grouped = new Map<string, HoldingView>();
  for (const seed of seeds) {
    const key = seed.symbol.toUpperCase();
    const positionCost = normalizeValue(seed.totalCost);
    const positionQty = normalizeValue(seed.quantity);
    const current = grouped.get(key);
    if (!current) {
      grouped.set(key, {
        symbol: key,
        market: seed.market,
        quantity: positionQty,
        avgCost: normalizeValue(seed.avgCost),
        lastPrice: normalizeValue(seed.lastPrice),
        marketValueBase: normalizeValue(seed.marketValueBase),
        unrealizedPnlBase: normalizeValue(seed.unrealizedPnlBase),
        pnlPct: seed.avgCost > 0 ? ((normalizeValue(seed.lastPrice) - normalizeValue(seed.avgCost)) / normalizeValue(seed.avgCost)) * 100 : null,
        accountCount: 1,
        accountNames: [seed.accountName],
        concentrationWeightPct: concentrationMap.get(key) || 0,
        stopLossTriggered: Boolean(stopLossMap.get(key)?.triggered),
        stopLossNear: Boolean(stopLossMap.get(key)?.near),
        maxLossPct: stopLossMap.get(key)?.maxLossPct ?? null,
        actionTitle: '',
        actionReason: '',
        actionTone: 'info',
        priority: 0,
      });
      continue;
    }

    const totalQuantity = current.quantity + positionQty;
    const mergedTotalCost = current.avgCost * current.quantity + positionCost;
    current.quantity = totalQuantity;
    current.avgCost = totalQuantity > 0 ? mergedTotalCost / totalQuantity : current.avgCost;
    current.lastPrice = normalizeValue(seed.lastPrice) || current.lastPrice;
    current.marketValueBase += normalizeValue(seed.marketValueBase);
    current.unrealizedPnlBase += normalizeValue(seed.unrealizedPnlBase);
    current.accountCount += 1;
    current.accountNames.push(seed.accountName);
    current.stopLossTriggered = current.stopLossTriggered || Boolean(stopLossMap.get(key)?.triggered);
    current.stopLossNear = current.stopLossNear || Boolean(stopLossMap.get(key)?.near);
    current.maxLossPct = current.maxLossPct == null
      ? (stopLossMap.get(key)?.maxLossPct ?? null)
      : Math.min(current.maxLossPct, stopLossMap.get(key)?.maxLossPct ?? current.maxLossPct);
    current.pnlPct = current.avgCost > 0 ? ((current.lastPrice - current.avgCost) / current.avgCost) * 100 : null;
  }

  const rows = Array.from(grouped.values());
  for (const row of rows) {
    if (row.stopLossTriggered || (row.pnlPct != null && row.pnlPct <= -10)) {
      row.actionTitle = '优先减亏处理';
      row.actionReason = '已接近或触发止损区间，先确认是否需要执行纪律，避免继续被动扩大亏损。';
      row.actionTone = 'danger';
      row.priority = 100;
      continue;
    }
    if (row.stopLossNear || (row.pnlPct != null && row.pnlPct <= -5)) {
      row.actionTitle = '等待反弹减压';
      row.actionReason = '当前浮亏已进入敏感区，先防冲动补仓，优先观察承接和反弹后的减仓机会。';
      row.actionTone = 'warning';
      row.priority = 80;
      continue;
    }
    if (row.concentrationWeightPct >= 35) {
      row.actionTitle = '控制单票仓位';
      row.actionReason = '单票仓位占比较高，哪怕走势未破坏，也应预先准备分批减仓和风险对冲计划。';
      row.actionTone = 'warning';
      row.priority = 70;
      continue;
    }
    if (row.pnlPct != null && row.pnlPct >= 15) {
      row.actionTitle = '分批锁盈';
      row.actionReason = '已有较可观浮盈，适合结合趋势强弱考虑分批锁盈，而不是把盈利重新回吐。';
      row.actionTone = 'success';
      row.priority = 60;
      continue;
    }
    if (row.pnlPct != null && Math.abs(row.pnlPct) <= 3) {
      row.actionTitle = '观察成本位得失';
      row.actionReason = '当前处于成本附近，先看量价与趋势是否重新站稳，再决定持有还是减仓。';
      row.actionTone = 'info';
      row.priority = 50;
      continue;
    }
    row.actionTitle = row.pnlPct != null && row.pnlPct > 0 ? '继续持有跟踪' : '保守跟踪';
    row.actionReason = row.pnlPct != null && row.pnlPct > 0
      ? '当前仍保有盈利缓冲，优先观察趋势是否延续，并预设移动止盈位。'
      : '当前并无明确止损触发，但也不适合激进处理，先跟踪趋势和资金修复情况。';
    row.actionTone = row.pnlPct != null && row.pnlPct > 0 ? 'success' : 'info';
    row.priority = row.pnlPct != null && row.pnlPct > 0 ? 40 : 30;
  }

  return rows.sort((a, b) => {
    if (b.priority !== a.priority) return b.priority - a.priority;
    return b.marketValueBase - a.marketValueBase;
  });
}

const PortfolioWorkbenchPage: React.FC = () => {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState<PortfolioAccountItem[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<AccountOption>('all');
  const [costMethod, setCostMethod] = useState<PortfolioCostMethod>('fifo');
  const [marketFilter, setMarketFilter] = useState<MarketFilter>('all');
  const [onlyActionNeeded, setOnlyActionNeeded] = useState(false);
  const [snapshot, setSnapshot] = useState<PortfolioSnapshotResponse | null>(null);
  const [risk, setRisk] = useState<PortfolioRiskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [riskWarning, setRiskWarning] = useState<string | null>(null);

  useEffect(() => {
    document.title = '持仓工作台 - DSA';
  }, []);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setRiskWarning(null);
    try {
      const accountId = selectedAccount === 'all' ? undefined : Number(selectedAccount);
      const [accountsResponse, snapshotResponse] = await Promise.all([
        portfolioApi.getAccounts(false),
        portfolioApi.getSnapshot({ accountId, costMethod }),
      ]);
      setAccounts(accountsResponse.accounts || []);
      setSnapshot(snapshotResponse);

      try {
        const riskResponse = await portfolioApi.getRisk({ accountId, costMethod });
        setRisk(riskResponse);
      } catch (riskErr) {
        setRisk(null);
        const parsed = getParsedApiError(riskErr);
        setRiskWarning(parsed.message || '风险数据获取失败，工作台已降级为仅展示持仓快照。');
      }
    } catch (err) {
      setAccounts([]);
      setSnapshot(null);
      setRisk(null);
      setError(getParsedApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [costMethod, selectedAccount]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const holdings = useMemo(() => {
    if (!snapshot) return [];
    return buildHoldingView(snapshot, risk);
  }, [risk, snapshot]);

  const filteredHoldings = useMemo(() => {
    return holdings.filter((item) => {
      if (marketFilter !== 'all' && item.market !== marketFilter) return false;
      if (!onlyActionNeeded) return true;
      return item.priority >= 50;
    });
  }, [holdings, marketFilter, onlyActionNeeded]);

  const focusHoldings = useMemo(() => filteredHoldings.slice(0, 5), [filteredHoldings]);

  const actionSummary = useMemo(() => {
    const highRisk = holdings.filter((item) => item.priority >= 80).length;
    const lockProfit = holdings.filter((item) => item.actionTitle === '分批锁盈').length;
    const nearCost = holdings.filter((item) => item.actionTitle === '观察成本位得失').length;
    return { highRisk, lockProfit, nearCost };
  }, [holdings]);

  const sectorHighlights = risk?.sectorConcentration.topSectors || [];
  const hasAccounts = accounts.length > 0;

  return (
    <AppPage className="space-y-6">
      <PageHeader
        eyebrow="Portfolio"
        title="持仓工作台"
        description="把持仓快照、风险暴露和下一步动作放在同一个视图里，优先看到最该处理的仓位。"
        actions={(
          <>
            <Button variant="secondary" size="sm" onClick={() => navigate('/portfolio')}>
              <BriefcaseBusiness className="h-4 w-4" />
              管理持仓
            </Button>
            <Button variant="outline" size="sm" onClick={() => void loadData()} isLoading={isLoading} loadingText="刷新中">
              <RefreshCw className="h-4 w-4" />
              刷新
            </Button>
          </>
        )}
      />

      {error ? <ApiErrorAlert error={error} /> : null}
      {riskWarning ? (
        <InlineAlert
          variant="warning"
          title="风险模块降级"
          message={riskWarning}
        />
      ) : null}

      {!hasAccounts && !isLoading ? (
        <EmptyState
          title="还没有持仓账户"
          description="先去持仓页创建账户并录入交易，工作台才能识别你的真实仓位和风险。"
          action={(
            <Button onClick={() => navigate('/portfolio')}>
              去配置 Portfolio
            </Button>
          )}
        />
      ) : null}

      {hasAccounts ? (
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Select
            label="账户范围"
            value={selectedAccount}
            onChange={(value) => setSelectedAccount(value as AccountOption)}
            options={[
              { value: 'all', label: '全部账户' },
              ...accounts.map((account) => ({ value: String(account.id), label: `${account.name} · ${formatMarketLabel(account.market)}` })),
            ]}
          />
          <Select
            label="成本法"
            value={costMethod}
            onChange={(value) => setCostMethod(value as PortfolioCostMethod)}
            options={[
              { value: 'fifo', label: 'FIFO' },
              { value: 'avg', label: '平均成本' },
            ]}
          />
          <Select
            label="市场筛选"
            value={marketFilter}
            onChange={(value) => setMarketFilter(value as MarketFilter)}
            options={[
              { value: 'all', label: '全部市场' },
              { value: 'cn', label: 'A股' },
              { value: 'hk', label: '港股' },
              { value: 'us', label: '美股' },
            ]}
          />
          <div className="flex flex-col justify-end">
            <label className="flex h-11 cursor-pointer items-center gap-2 rounded-xl border border-subtle bg-card/60 px-4 text-sm text-secondary-text">
              <input
                type="checkbox"
                checked={onlyActionNeeded}
                onChange={(e) => setOnlyActionNeeded(e.target.checked)}
                className="h-4 w-4 rounded border-border accent-primary"
              />
              只看需要动作的持仓
            </label>
          </div>
        </section>
      ) : null}

      {snapshot ? (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="总权益"
            value={formatMoney(snapshot.totalEquity, snapshot.currency)}
            hint={`持仓市值 ${formatMoney(snapshot.totalMarketValue, snapshot.currency)}`}
            icon={<CircleDollarSign className="h-5 w-5" />}
            tone="primary"
          />
          <StatCard
            label="浮动盈亏"
            value={formatMoney(snapshot.unrealizedPnl, snapshot.currency)}
            hint={`已实现 ${formatMoney(snapshot.realizedPnl, snapshot.currency)}`}
            icon={<TrendingUp className="h-5 w-5" />}
            tone={snapshot.unrealizedPnl >= 0 ? 'success' : 'warning'}
          />
          <StatCard
            label="高优先级仓位"
            value={String(actionSummary.highRisk)}
            hint="触发止损/明显浮亏/需要减压的仓位数"
            icon={<ShieldAlert className="h-5 w-5" />}
            tone={actionSummary.highRisk > 0 ? 'danger' : 'success'}
          />
          <StatCard
            label="风险提醒"
            value={risk?.concentration.alert || risk?.stopLoss.nearAlert ? '有' : '无'}
            hint={`锁盈候选 ${actionSummary.lockProfit} · 成本位观察 ${actionSummary.nearCost}`}
            icon={<AlertTriangle className="h-5 w-5" />}
            tone={risk?.concentration.alert || risk?.stopLoss.nearAlert ? 'warning' : 'default'}
          />
        </section>
      ) : null}

      {risk?.concentration.alert || risk?.stopLoss.nearAlert || snapshot?.fxStale ? (
        <div className="space-y-3">
          {risk?.concentration.alert ? (
            <InlineAlert
              variant="warning"
              title="仓位集中度偏高"
              message={`当前最大单票仓位约 ${formatPct(risk.concentration.topWeightPct)}，建议为高占比持仓预设减仓和风控计划。`}
            />
          ) : null}
          {risk?.stopLoss.nearAlert ? (
            <InlineAlert
              variant="warning"
              title="有仓位接近止损区间"
              message={`当前有 ${risk.stopLoss.nearCount} 只仓位接近止损区间，另有 ${risk.stopLoss.triggeredCount} 只已触发止损阈值。`}
            />
          ) : null}
          {snapshot?.fxStale ? (
            <InlineAlert
              variant="info"
              title="汇率估值存在 stale 数据"
              message="跨市场仓位的人民币口径估值可能使用了 stale/fallback 汇率，建议在持仓页刷新汇率后再做精确比较。"
            />
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <SectionCard
          title="优先关注"
          subtitle="Action Board"
          actions={holdings.length > 0 ? <Badge variant="info">{focusHoldings.length} 项焦点</Badge> : null}
        >
          {focusHoldings.length === 0 ? (
            <p className="text-sm text-secondary-text">当前筛选条件下暂无持仓。</p>
          ) : (
            <div className="space-y-3">
              {focusHoldings.map((item) => (
                <div key={item.symbol} className="rounded-2xl border border-subtle bg-card/55 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-foreground">{item.symbol}</h3>
                        <Badge variant="default">{formatMarketLabel(item.market)}</Badge>
                        <Badge variant={getActionVariant(item.actionTone)}>{item.actionTitle}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-secondary-text">{item.actionReason}</p>
                    </div>
                    <div className="text-right text-sm text-secondary-text">
                      <div>浮盈亏 {formatPct(item.pnlPct)}</div>
                      <div>仓位占比 {formatPct(item.concentrationWeightPct)}</div>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-secondary-text">
                    <span>账户：{item.accountNames.join('、')}</span>
                    <span>持股：{item.quantity.toLocaleString('zh-CN')}</span>
                    <span>成本：{item.avgCost.toFixed(2)}</span>
                    <span>现价：{item.lastPrice.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="风险分布" subtitle="Exposure">
          <div className="space-y-4">
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground">行业集中度</h3>
                <Badge variant={risk?.sectorConcentration.alert ? 'warning' : 'default'}>
                  Top {formatPct(risk?.sectorConcentration.topWeightPct ?? 0)}
                </Badge>
              </div>
              <div className="space-y-2">
                {sectorHighlights.length > 0 ? sectorHighlights.slice(0, 5).map((item) => (
                  <div key={item.sector} className="flex items-center justify-between rounded-xl border border-subtle/80 bg-card/40 px-3 py-2 text-sm">
                    <div>
                      <div className="font-medium text-foreground">{item.sector}</div>
                      <div className="text-xs text-secondary-text">{item.symbolCount} 只标的</div>
                    </div>
                    <div className="text-right">
                      <div className="text-foreground">{formatPct(item.weightPct)}</div>
                      <div className="text-xs text-secondary-text">{formatMoney(item.marketValueBase, 'CNY')}</div>
                    </div>
                  </div>
                )) : (
                  <p className="text-sm text-secondary-text">当前没有可展示的行业集中度数据。</p>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-subtle bg-card/40 p-4 text-sm text-secondary-text">
              <div className="flex items-center justify-between">
                <span>止损触发数</span>
                <span className="font-medium text-foreground">{risk?.stopLoss.triggeredCount ?? 0}</span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span>接近止损数</span>
                <span className="font-medium text-foreground">{risk?.stopLoss.nearCount ?? 0}</span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span>最大回撤</span>
                <span className="font-medium text-foreground">{formatPct(risk?.drawdown.maxDrawdownPct ?? null)}</span>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="持仓清单"
        subtitle="Holdings"
        actions={<Badge variant="default">{filteredHoldings.length} 只标的</Badge>}
      >
        {filteredHoldings.length === 0 ? (
          <p className="text-sm text-secondary-text">当前筛选条件下没有持仓数据。</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.18em] text-secondary-text">
                <tr>
                  <th className="px-3 py-3 font-medium">标的</th>
                  <th className="px-3 py-3 font-medium">持仓</th>
                  <th className="px-3 py-3 font-medium">成本 / 现价</th>
                  <th className="px-3 py-3 font-medium">浮盈亏</th>
                  <th className="px-3 py-3 font-medium">仓位占比</th>
                  <th className="px-3 py-3 font-medium">建议</th>
                </tr>
              </thead>
              <tbody>
                {filteredHoldings.map((item) => (
                  <tr key={item.symbol} className="border-t border-subtle/70 align-top">
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-foreground">{item.symbol}</span>
                        <Badge variant="default">{formatMarketLabel(item.market)}</Badge>
                      </div>
                      <div className="mt-1 text-xs text-secondary-text">{item.accountNames.join('、')}</div>
                    </td>
                    <td className="px-3 py-3 text-secondary-text">
                      <div>{item.quantity.toLocaleString('zh-CN')}</div>
                      <div className="mt-1 text-xs">市值 {formatMoney(item.marketValueBase, 'CNY')}</div>
                    </td>
                    <td className="px-3 py-3 text-secondary-text">
                      <div>成本 {item.avgCost.toFixed(2)}</div>
                      <div className="mt-1 text-xs">现价 {item.lastPrice.toFixed(2)}</div>
                    </td>
                    <td className="px-3 py-3">
                      <div className={item.unrealizedPnlBase >= 0 ? 'text-success' : 'text-warning'}>
                        {formatMoney(item.unrealizedPnlBase, 'CNY')}
                      </div>
                      <div className="mt-1 text-xs text-secondary-text">{formatPct(item.pnlPct)}</div>
                    </td>
                    <td className="px-3 py-3 text-secondary-text">
                      <div>{formatPct(item.concentrationWeightPct)}</div>
                      <div className="mt-1 text-xs">
                        {item.stopLossTriggered ? '已触发止损' : item.stopLossNear ? '接近止损' : '正常'}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <Badge variant={getActionVariant(item.actionTone)}>{item.actionTitle}</Badge>
                      <p className="mt-2 max-w-xs text-xs leading-5 text-secondary-text">{item.actionReason}</p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </AppPage>
  );
};

export default PortfolioWorkbenchPage;
