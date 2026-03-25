import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestResultsResponse,
  BacktestResultItem,
  PerformanceMetrics,
} from '../types/backtest';

// ============ API ============

export const backtestApi = {
  /**
   * Trigger backtest evaluation
   */
  run: async (params: BacktestRunRequest = {}): Promise<BacktestRunResponse> => {
    const requestData: Record<string, unknown> = {};
    if (params.code) requestData.code = params.code;
    if (params.strategyIds?.length) requestData.strategy_ids = params.strategyIds;
    if (params.force) requestData.force = params.force;
    if (params.evalWindowDays) requestData.eval_window_days = params.evalWindowDays;
    if (params.minAgeDays != null) requestData.min_age_days = params.minAgeDays;
    if (params.limit) requestData.limit = params.limit;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/run',
      requestData,
    );
    return toCamelCase<BacktestRunResponse>(response.data);
  },

  /**
   * Get paginated backtest results
   */
  getResults: async (params: {
    code?: string;
    strategyIds?: string[];
    evalWindowDays?: number;
    page?: number;
    limit?: number;
  } = {}): Promise<BacktestResultsResponse> => {
    const { code, strategyIds, evalWindowDays, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (code) queryParams.code = code;
    if (strategyIds?.length) queryParams.strategy_ids = strategyIds.join(',');
    if (evalWindowDays) queryParams.eval_window_days = evalWindowDays;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/results',
      { params: queryParams },
    );

    const data = toCamelCase<BacktestResultsResponse>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: (data.items || []).map(item => toCamelCase<BacktestResultItem>(item)),
    };
  },

  /**
   * Get overall performance metrics
   */
  getOverallPerformance: async (evalWindowDays?: number, strategyIds?: string[]): Promise<PerformanceMetrics | null> => {
    try {
      const params: Record<string, number | string> = {};
      if (evalWindowDays) params.eval_window_days = evalWindowDays;
      if (strategyIds?.length) params.strategy_ids = strategyIds.join(',');
      const response = await apiClient.get<Record<string, unknown>>(
        '/api/v1/backtest/performance',
        { params },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },

  /**
   * Get per-stock performance metrics
   */
  getStockPerformance: async (code: string, evalWindowDays?: number, strategyIds?: string[]): Promise<PerformanceMetrics | null> => {
    try {
      const params: Record<string, number | string> = {};
      if (evalWindowDays) params.eval_window_days = evalWindowDays;
      if (strategyIds?.length) params.strategy_ids = strategyIds.join(',');
      const response = await apiClient.get<Record<string, unknown>>(
        `/api/v1/backtest/performance/${encodeURIComponent(code)}`,
        { params },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },
};
