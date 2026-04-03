import apiClient from './index';

export interface StockScreeningRequest {
  market?: 'cn' | 'us' | 'hk';
  data_mode?: 'database' | 'realtime';
  min_market_cap?: number;
  max_market_cap?: number;
  min_turnover?: number;
  min_turnover_rate?: number;
  max_turnover_rate?: number;
  min_price?: number;
  max_price?: number;
  min_change_pct?: number;
  max_change_pct?: number;
  exclude_st?: boolean;
  exclude_prefixes?: string[];
  include_dragon_tiger?: boolean;
  target_count?: number;
  sort_by?: string[];
}

export interface StockInfo {
  code: string;
  name: string;
  price: number;
  market_cap: number;
  turnover: number;
  turnover_rate: number;
  change_pct: number;
  rank?: number;
  score?: number;
  score_reason?: string;
  score_breakdown?: Record<string, number>;
  opportunity_tier?: string;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
  amount?: number;
}

export interface StockScreeningSummary {
  count: number;
  avg_market_cap: number;
  avg_turnover: number;
  avg_turnover_rate: number;
  avg_price: number;
  avg_change_pct: number;
  market: string;
  data_mode: string;
  top_score: number;
  avg_score: number;
  top_candidates: string[];
}

export interface StockScreeningResponse {
  stocks: StockInfo[];
  summary: StockScreeningSummary;
}

export interface ScreeningSnapshotItem {
  snapshot_id: string;
  market: string;
  data_mode: string;
  created_at?: string;
  summary: Record<string, unknown>;
  performance_summary: Record<string, unknown>;
}

export interface ScreeningTopAnalysisItem {
  code: string;
  stock_name?: string;
  operation_advice?: string;
  trend_prediction?: string;
  sentiment_score?: number;
  analysis_summary?: string;
  created_at?: string;
}

export interface StockBatchAnalyzeRequest {
  stocks: StockInfo[];
  reportType?: string;
}

export interface StockBatchAnalyzeResponse {
  task_ids: string[];
  message: string;
}

export const screeningApi = {
  async screenStocks(request: StockScreeningRequest): Promise<StockScreeningResponse> {
    const response = await apiClient.post('/api/v1/screening/filter', request);
    return response.data;
  },

  async saveSnapshot(payload: StockScreeningResponse & { filters: StockScreeningRequest }): Promise<{ success: boolean; snapshot_id: string; record_id: number }> {
    const response = await apiClient.post('/api/v1/screening/snapshot', payload);
    return response.data;
  },

  async getSnapshots(limit = 10): Promise<{ items: ScreeningSnapshotItem[] }> {
    const response = await apiClient.get('/api/v1/screening/snapshots', { params: { limit } });
    return response.data;
  },

  async getTopAnalysisSummary(codes: string[]): Promise<{ items: ScreeningTopAnalysisItem[] }> {
    const response = await apiClient.post('/api/v1/screening/top-analysis-summary', { codes });
    return response.data;
  },

  async batchAnalyze(request: StockBatchAnalyzeRequest): Promise<StockBatchAnalyzeResponse> {
    const response = await apiClient.post('/api/v1/screening/batch-analyze', request);
    return response.data;
  },
};
