import apiClient from './index';
import { toCamelCase } from './utils';

export interface StrategySignalInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  supported: boolean;
  supportNote: string;
}

export interface StrategySignalTradeItem {
  entryDate: string;
  entryPrice: number;
  exitDate: string;
  exitPrice: number;
  shares: number;
  profit: number;
  profitPct: number;
}

export interface StrategySignalMetrics {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  avgProfit: number;
  avgWin: number;
  avgLoss: number;
  avgProfitPct: number;
  totalProfit: number;
  totalProfitPct: number;
  maxDrawdown: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
}

export interface StrategySignalBacktestItem {
  strategyId: string;
  strategyName: string;
  supported: boolean;
  note?: string;
  metrics: StrategySignalMetrics;
  trades: StrategySignalTradeItem[];
}

export interface StrategySignalBacktestRunResponse {
  code: string;
  dataSource: string;
  days: number;
  initialCapital: number;
  results: StrategySignalBacktestItem[];
  unsupportedStrategyIds: string[];
}

export const strategyBacktestApi = {
  async getStrategies(): Promise<StrategySignalInfo[]> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/strategy-backtest/strategies');
    const payload = toCamelCase<{ strategies: StrategySignalInfo[] }>(response.data);
    return payload.strategies || [];
  },

  async run(params: {
    code: string;
    strategyIds: string[];
    days: number;
    initialCapital: number;
  }): Promise<StrategySignalBacktestRunResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/strategy-backtest/run', {
      code: params.code,
      strategy_ids: params.strategyIds,
      days: params.days,
      initial_capital: params.initialCapital,
    });
    return toCamelCase<StrategySignalBacktestRunResponse>(response.data);
  },
};
