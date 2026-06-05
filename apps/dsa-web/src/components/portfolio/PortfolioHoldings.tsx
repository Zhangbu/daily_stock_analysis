import type React from 'react';
import { useMemo } from 'react';
import { Pie, PieChart, ResponsiveContainer, Tooltip, Legend, Cell } from 'recharts';
import { Card, EmptyState, Badge } from '../common';
import type {
  PortfolioPositionItem,
  PortfolioRiskResponse,
  PortfolioSnapshotResponse,
} from '../../types/portfolio';

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const PIE_COLORS = ['#00d4ff', '#00ff88', '#ffaa00', '#ff7a45', '#7f8cff', '#ff4466'];

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

type FlatPosition = PortfolioPositionItem & {
  accountId: number;
  accountName: string;
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Main component                                                    */
/* ------------------------------------------------------------------ */

export type PortfolioHoldingsProps = {
  snapshot: PortfolioSnapshotResponse;
  risk: PortfolioRiskResponse | null;
};

export const PortfolioHoldings: React.FC<PortfolioHoldingsProps> = ({ snapshot, risk }) => {
  const positionRows: FlatPosition[] = useMemo(() => {
    const rows: FlatPosition[] = [];
    for (const account of snapshot.accounts || []) {
      for (const position of account.positions || []) {
        rows.push({
          ...position,
          accountId: account.accountId,
          accountName: account.accountName,
        });
      }
    }
    rows.sort((a, b) => Number(b.marketValueBase || 0) - Number(a.marketValueBase || 0));
    return rows;
  }, [snapshot]);

  const sectorPieData = useMemo(() => {
    const sectors = risk?.sectorConcentration?.topSectors || [];
    return sectors
      .slice(0, 6)
      .map((item) => ({
        name: item.sector,
        value: Number(item.weightPct || 0),
      }))
      .filter((item) => item.value > 0);
  }, [risk]);

  const positionFallbackPieData = useMemo(() => {
    if (!risk?.concentration?.topPositions?.length) {
      return [];
    }
    return risk.concentration.topPositions
      .slice(0, 6)
      .map((item) => ({
        name: item.symbol,
        value: Number(item.weightPct || 0),
      }))
      .filter((item) => item.value > 0);
  }, [risk]);

  const concentrationPieData = sectorPieData.length > 0 ? sectorPieData : positionFallbackPieData;
  const concentrationMode = sectorPieData.length > 0 ? 'sector' : 'position';

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
      <Card className="xl:col-span-2" padding="md">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-foreground">持仓明细</h2>
          <span className="text-xs text-secondary-text">共 {positionRows.length} 项</span>
        </div>
        {positionRows.length === 0 ? (
          <EmptyState
            title="当前无持仓数据"
            description="录入交易或导入 CSV 后，这里会展示按账户汇总的持仓明细。"
            className="border-none bg-transparent px-4 py-8 shadow-none"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-secondary-text border-b border-border">
                <tr>
                  <th className="text-left py-2 pr-2">账户</th>
                  <th className="text-left py-2 pr-2">代码</th>
                  <th className="text-right py-2 pr-2">数量</th>
                  <th className="text-right py-2 pr-2">均价</th>
                  <th className="text-right py-2 pr-2">现价</th>
                  <th className="text-right py-2 pr-2">市值</th>
                  <th className="text-right py-2">未实现盈亏</th>
                </tr>
              </thead>
              <tbody>
                {positionRows.map((row) => (
                  <tr key={`${row.accountId}-${row.symbol}-${row.market}`} className="border-b border-border/40">
                    <td className="py-2 pr-2 text-secondary-text">{row.accountName}</td>
                    <td className="py-2 pr-2 font-mono text-foreground">{row.symbol}</td>
                    <td className="py-2 pr-2 text-right">{row.quantity.toFixed(2)}</td>
                    <td className="py-2 pr-2 text-right">{row.avgCost.toFixed(4)}</td>
                    <td className="py-2 pr-2 text-right">{row.lastPrice.toFixed(4)}</td>
                    <td className="py-2 pr-2 text-right">{formatMoney(row.marketValueBase, row.valuationCurrency)}</td>
                    <td className={`py-2 text-right ${row.unrealizedPnlBase >= 0 ? 'text-success' : 'text-danger'}`}>
                      {formatMoney(row.unrealizedPnlBase, row.valuationCurrency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card padding="md">
        <h2 className="text-sm font-semibold text-foreground mb-3">
          {concentrationMode === 'sector' ? '行业集中度分布' : '行业数据暂不可用，当前展示个股集中度'}
        </h2>
        {concentrationPieData.length > 0 ? (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={concentrationPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90}>
                  {concentrationPieData.map((entry, index) => (
                    <Cell key={`cell-${entry.name}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState
            title="暂无集中度数据"
            description="风险模块完成计算后，这里会展示行业或个股维度的集中度分布。"
            className="border-none bg-transparent px-4 py-10 shadow-none"
          />
        )}
        <div className="mt-3 text-xs text-secondary-text space-y-1">
          <div>展示口径: {concentrationMode === 'sector' ? '行业维度' : '个股维度（降级显示）'}</div>
          <div>板块集中度告警: {risk?.sectorConcentration?.alert ? '是' : '否'}</div>
          <div>Top1 权重: {formatPct(risk?.sectorConcentration?.topWeightPct ?? risk?.concentration?.topWeightPct)}</div>
        </div>
      </Card>
    </div>
  );
};
