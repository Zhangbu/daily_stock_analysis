export interface ProfileStrategyOption {
  name: string;
  displayName: string;
  description: string;
}

export interface ProfileStockItem {
  code: string;
  nameEn: string;
  nameZh: string;
  sector: string;
  industry?: string | null;
}

export interface ProfileMeta {
  profileName: string;
  displayName: string;
  description: string;
  defaultStrategy: string;
  stockUniverse: string[];
  stockItems: ProfileStockItem[];
  strategies: ProfileStrategyOption[];
}

export interface ProfileRunRequest {
  strategyName: string;
  stockCodes?: string[];
}

export interface ProfileTrendSnapshot {
  trendStatus: string;
  buySignal: string;
  ma5: number;
  ma10: number;
  ma20: number;
  ma60: number;
  biasMa5: number;
  volumeRatio5d: number;
}

export interface ProfileSignal {
  strategyName: string;
  score: number;
  grade: string;
  passed: boolean;
  verdict: string;
  entryZone: string;
  stopLoss: string;
  targetHint: string;
  reasons: string[];
  risks: string[];
  metrics: Record<string, number>;
}

export interface ProfileResultItem {
  code: string;
  profileName: string;
  strategyName: string;
  trend: ProfileTrendSnapshot;
  signal: ProfileSignal;
}

export interface ProfileRunResponse {
  profileName: string;
  strategyName: string;
  stockCodes: string[];
  results: ProfileResultItem[];
}
