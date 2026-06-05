import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { historyApi } from '../../api/history';
import type { ParsedApiError } from '../../api/error';
import { getParsedApiError } from '../../api/error';
import { ApiErrorAlert, Badge, Card, EmptyState, Pagination } from '../common';
import type { HistoryReviewItem, HistoryReviewSummary } from '../../types/analysis';

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const FILTER_INPUT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

const verdictBadge = (verdict?: string | null) => {
  switch (verdict) {
    case 'hit':
      return <Badge variant="success" glow>命中</Badge>;
    case 'partial':
      return <Badge variant="warning">部分命中</Badge>;
    case 'miss':
      return <Badge variant="danger">失效</Badge>;
    default:
      return <Badge variant="default">待观察</Badge>;
  }
};

function formatPct(value?: number | null): string {
  if (value == null) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function pctTone(value?: number | null): string {
  if (value == null) return 'text-secondary-text';
  if (value > 0) return 'text-success';
  if (value < 0) return 'text-danger';
  return 'text-warning';
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                    */
/* ------------------------------------------------------------------ */

const SummaryCard: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone }) => (
  <Card variant="gradient" padding="md" className="animate-fade-in">
    <div className="text-xs uppercase tracking-[0.24em] text-muted-text">{label}</div>
    <div className={`mt-3 text-2xl font-semibold ${tone ?? 'text-foreground'}`}>{value}</div>
  </Card>
);

/* ------------------------------------------------------------------ */
/*  Main Component                                                    */
/* ------------------------------------------------------------------ */

export const ReviewPanel: React.FC = () => {
  const [stockCode, setStockCode] = useState('');
  const [operationAdvice, setOperationAdvice] = useState('');
  const [verdict, setVerdict] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [items, setItems] = useState<HistoryReviewItem[]>([]);
  const [summary, setSummary] = useState<HistoryReviewSummary | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(20);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / limit)), [limit, total]);

  const fetchData = useCallback(async (nextPage = 1) => {
    setIsLoading(true);
    try {
      const params = {
        stockCode: stockCode.trim() || undefined,
        operationAdvice: operationAdvice || undefined,
        verdict: (verdict || undefined) as 'hit' | 'partial' | 'miss' | undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      };
      const [listResponse, summaryResponse] = await Promise.all([
        historyApi.getReviewList({ ...params, page: nextPage, limit }),
        historyApi.getReviewSummary(params),
      ]);
      setItems(listResponse.items);
      setTotal(listResponse.total);
      setPage(listResponse.page);
      setSummary(summaryResponse);
      setError(null);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [endDate, limit, operationAdvice, startDate, stockCode, verdict]);

  useEffect(() => {
    void fetchData(1);
  }, [fetchData]);

  const handleSubmit = useCallback((event: React.FormEvent) => {
    event.preventDefault();
    void fetchData(1);
  }, [fetchData]);

  const handleReset = useCallback(() => {
    setStockCode('');
    setOperationAdvice('');
    setVerdict('');
    setStartDate('');
    setEndDate('');
  }, []);

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      {summary ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <SummaryCard label="复盘样本" value={`${summary.total}`} />
          <SummaryCard label="命中率" value={summary.hitRatePct != null ? `${summary.hitRatePct.toFixed(1)}%` : '--'} tone="text-primary" />
          <SummaryCard label="平均 T+1" value={formatPct(summary.avgT1ReturnPct)} tone={pctTone(summary.avgT1ReturnPct)} />
          <SummaryCard label="平均 T+5" value={formatPct(summary.avgT5ReturnPct)} tone={pctTone(summary.avgT5ReturnPct)} />
          <SummaryCard label="平均 T+10" value={formatPct(summary.avgT10ReturnPct)} tone={pctTone(summary.avgT10ReturnPct)} />
          <SummaryCard label="平均最大回撤" value={formatPct(summary.avgMaxDrawdownPct)} tone={pctTone(summary.avgMaxDrawdownPct)} />
        </div>
      ) : null}

      {/* Filters */}
      <Card variant="bordered" padding="lg">
        <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-5" onSubmit={handleSubmit}>
          <input
            className={FILTER_INPUT_CLASS}
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            placeholder="股票代码，如 600519 / AAPL"
          />
          <select
            className={FILTER_INPUT_CLASS}
            value={operationAdvice}
            onChange={(e) => setOperationAdvice(e.target.value)}
          >
            <option value="">全部建议</option>
            <option value="买入">买入</option>
            <option value="加仓">加仓</option>
            <option value="持有">持有</option>
            <option value="观望">观望</option>
            <option value="减仓">减仓</option>
            <option value="卖出">卖出</option>
          </select>
          <select
            className={FILTER_INPUT_CLASS}
            value={verdict}
            onChange={(e) => setVerdict(e.target.value)}
          >
            <option value="">全部结果</option>
            <option value="hit">命中</option>
            <option value="partial">部分命中</option>
            <option value="miss">失效</option>
          </select>
          <input
            type="date"
            className={FILTER_INPUT_CLASS}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <input
            type="date"
            className={FILTER_INPUT_CLASS}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
          <div className="flex gap-3 xl:col-span-5">
            <button type="submit" className="btn-primary h-11 px-5" disabled={isLoading}>
              {isLoading ? '加载中...' : '筛选复盘'}
            </button>
            <button type="button" className="btn-secondary h-11 px-5" onClick={handleReset} disabled={isLoading}>
              重置筛选
            </button>
          </div>
        </form>
      </Card>

      {error ? <ApiErrorAlert error={error} onDismiss={() => setError(null)} /> : null}

      {/* Results table */}
      <Card variant="bordered" padding="lg">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground">复盘明细</h2>
            <p className="text-sm text-secondary-text">
              当前筛选下共 {total} 条记录，表格展示当时建议与后续 10 个交易日表现。
            </p>
          </div>
          {summary ? (
            <div className="flex flex-wrap gap-2 text-xs text-secondary-text">
              <span>命中 {summary.verdictCounts?.hit ?? 0}</span>
              <span>部分命中 {summary.verdictCounts?.partial ?? 0}</span>
              <span>失效 {summary.verdictCounts?.miss ?? 0}</span>
            </div>
          ) : null}
        </div>

        {items.length === 0 && !isLoading ? (
          <EmptyState
            title="暂无复盘数据"
            description="调整筛选条件，或先积累更多历史分析记录后再复盘。"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border/60 text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.24em] text-muted-text">
                  <th className="px-3 py-3">标的</th>
                  <th className="px-3 py-3">分析日</th>
                  <th className="px-3 py-3">建议</th>
                  <th className="px-3 py-3">结论</th>
                  <th className="px-3 py-3">入场价</th>
                  <th className="px-3 py-3">T+1</th>
                  <th className="px-3 py-3">T+5</th>
                  <th className="px-3 py-3">T+10</th>
                  <th className="px-3 py-3">最大浮盈</th>
                  <th className="px-3 py-3">最大回撤</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {items.map((item) => (
                  <tr key={item.id} className="align-top">
                    <td className="px-3 py-3">
                      <div className="font-medium text-foreground">{item.stockName || item.stockCode}</div>
                      <div className="text-xs text-secondary-text">{item.stockCode}</div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="text-foreground">{item.analysisDate || '--'}</div>
                      <div className="text-xs text-secondary-text">{item.createdAt?.slice(0, 10) || '--'}</div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="text-foreground">{item.operationAdvice || '--'}</div>
                      <div className="text-xs text-secondary-text">评分 {item.sentimentScore ?? '--'}</div>
                    </td>
                    <td className="px-3 py-3">{verdictBadge(item.verdict)}</td>
                    <td className="px-3 py-3 text-foreground">{item.entryPrice != null ? item.entryPrice.toFixed(2) : '--'}</td>
                    <td className={`px-3 py-3 font-medium ${pctTone(item.t1ReturnPct)}`}>{formatPct(item.t1ReturnPct)}</td>
                    <td className={`px-3 py-3 font-medium ${pctTone(item.t5ReturnPct)}`}>{formatPct(item.t5ReturnPct)}</td>
                    <td className={`px-3 py-3 font-medium ${pctTone(item.t10ReturnPct)}`}>{formatPct(item.t10ReturnPct)}</td>
                    <td className={`px-3 py-3 font-medium ${pctTone(item.maxUpsidePct)}`}>{formatPct(item.maxUpsidePct)}</td>
                    <td className={`px-3 py-3 font-medium ${pctTone(item.maxDrawdownPct)}`}>{formatPct(item.maxDrawdownPct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Pagination
          className="mt-6"
          currentPage={page}
          totalPages={totalPages}
          onPageChange={(nextPage) => void fetchData(nextPage)}
        />
      </Card>
    </div>
  );
};
