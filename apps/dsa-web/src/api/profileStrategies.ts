import apiClient from './index';
import { toCamelCase } from './utils';
import type { ProfileMeta, ProfileRunRequest, ProfileRunResponse } from '../types/profileStrategies';

export const profileStrategiesApi = {
  getMeta: async (profileName: string): Promise<ProfileMeta> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/analysis/profiles/${profileName}/meta`);
    return toCamelCase<ProfileMeta>(response.data);
  },

  run: async (profileName: string, data: ProfileRunRequest): Promise<ProfileRunResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(`/api/v1/analysis/profiles/${profileName}/run`, {
      strategy_name: data.strategyName,
      stock_codes: data.stockCodes,
    });
    return toCamelCase<ProfileRunResponse>(response.data);
  },
};
