export interface Mag7StrategyOption {
  name: string;
  displayName: string;
  description: string;
}

export interface Mag7ProfileMeta {
  profileName: string;
  displayName: string;
  description: string;
  defaultStrategy: string;
  stockUniverse: string[];
  strategies: Mag7StrategyOption[];
}

export interface Mag7RunRequest {
  strategyName: string;
  stockCodes?: string[];
}

export interface Mag7TrendSnapshot {
  trendStatus: string;
  buySignal: string;
  ma5: number;
  ma10: number;
  ma20: number;
  ma60: number;
  biasMa5: number;
  volumeRatio5d: number;
}

export interface Mag7Signal {
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

export interface Mag7ResultItem {
  code: string;
  profileName: string;
  strategyName: string;
  trend: Mag7TrendSnapshot;
  signal: Mag7Signal;
}

export interface Mag7RunResponse {
  profileName: string;
  strategyName: string;
  stockCodes: string[];
  results: Mag7ResultItem[];
}
