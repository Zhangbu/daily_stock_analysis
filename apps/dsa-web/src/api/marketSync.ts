import apiClient from './index';
import { toCamelCase } from './utils';

export interface MarketSyncStatus {
  running: boolean;
  startedAt?: string | null;
  finishedAt?: string | null;
  currentMarket?: string | null;
  currentCode?: string | null;
  processed: number;
  saved: number;
  skipped: number;
  errors: number;
  totalCandidates: number;
  priorityCandidates: number;
  priorityProcessed: number;
  priorityCompleted: number;
  message: string;
  markets: string[];
}

export interface MarketSyncRunResponse {
  accepted: boolean;
  message: string;
  status: MarketSyncStatus;
}

export const marketSyncApi = {
  async getStatus(): Promise<MarketSyncStatus> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/system/market-sync/status');
    return toCamelCase<MarketSyncStatus>(response.data);
  },

  async run(markets: Array<'cn' | 'us'>): Promise<MarketSyncRunResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/system/market-sync/run', {
      markets,
    });
    return toCamelCase<MarketSyncRunResponse>(response.data);
  },
};
