import apiClient from './index';
import { toCamelCase } from './utils';

export interface MetricBucket {
  hits?: number;
  misses?: number;
  writes?: number;
  evictions?: number;
  entries?: number;
  stale?: number;
  clears?: number;
  readErrors?: number;
  count?: number;
  success?: number;
  error?: number;
  cacheHits?: number;
  cacheMisses?: number;
  totalDurationMs?: number;
  maxDurationMs?: number;
  avgDurationMs?: number;
  hitRatePct?: number;
}

export interface SystemMetricsResponse {
  observability: Record<string, MetricBucket>;
  observabilityByProvider: Record<string, MetricBucket>;
  observabilityTrends: Record<string, Array<MetricBucket & { bucketTs: number }>>;
  recentSlowest: Array<{
    operation: string;
    provider: string;
    status: string;
    durationMs: number;
  }>;
  cache: Record<string, Record<string, MetricBucket>>;
}

export interface CacheClearResponse {
  success: boolean;
  namespace: string;
  clearedNamespaces: string[];
  cache: Record<string, Record<string, MetricBucket>>;
}

export const systemMetricsApi = {
  async getMetrics(): Promise<SystemMetricsResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/system/metrics');
    return toCamelCase<SystemMetricsResponse>(response.data);
  },

  async clearCache(namespace: string): Promise<CacheClearResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/system/metrics/cache/clear', null, {
      params: { namespace },
    });
    return toCamelCase<CacheClearResponse>(response.data);
  },
};
