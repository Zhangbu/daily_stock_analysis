import apiClient from './index';
import { toCamelCase } from './utils';
import type { Mag7ProfileMeta, Mag7RunRequest, Mag7RunResponse } from '../types/mag7';

export const mag7Api = {
  getMeta: async (): Promise<Mag7ProfileMeta> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/analysis/mag7/meta');
    return toCamelCase<Mag7ProfileMeta>(response.data);
  },

  run: async (data: Mag7RunRequest): Promise<Mag7RunResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/analysis/mag7/run', {
      strategy_name: data.strategyName,
      stock_codes: data.stockCodes,
    });
    return toCamelCase<Mag7RunResponse>(response.data);
  },
};
