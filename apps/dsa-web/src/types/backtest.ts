/**
 * Backtest API type definitions
 * Mirrors api/v1/schemas/backtest.py
 */

// ============ Request / Response ============

export interface BacktestRunRequest {
  code?: string;
  force?: boolean;
  evalWindowDays?: number;
  minAgeDays?: number;
  limit?: number;
}

export interface ProfileBacktestRunRequest {
  profileName: string;
  strategyName: string;
  stockCodes?: string[];
  analysisDateFrom?: string;
  analysisDateTo?: string;
  evalWindowDays?: number;
  onlyPassed?: boolean;
}

export interface BacktestRunResponse {
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
}

export interface ProfileBacktestSummaryByCodeItem {
  stockName: string;
  signals: number;
  winRatePct?: number;
  avgReturnPct?: number;
}

export interface ProfileBacktestSummary {
  totalSignals: number;
  wins: number;
  losses: number;
  neutrals: number;
  winRatePct?: number;
  avgReturnPct?: number;
  avgMaxReturnPct?: number;
  avgMinReturnPct?: number;
  evalWindowDays: number;
  byCode: Record<string, ProfileBacktestSummaryByCodeItem>;
}

export interface ProfileBacktestResultItem {
  code: string;
  stockName: string;
  analysisDate: string;
  entryDate: string;
  exitDate: string;
  score: number;
  grade: string;
  verdict: string;
  entryPrice: number;
  exitPrice: number;
  maxReturnPct: number;
  minReturnPct: number;
  windowReturnPct: number;
  outcome: string;
}

export interface ProfileBacktestRunResponse {
  profileName: string;
  strategyName: string;
  displayName: string;
  evalWindowDays: number;
  summary: ProfileBacktestSummary;
  items: ProfileBacktestResultItem[];
}

// ============ Result Item ============

export interface BacktestResultItem {
  analysisHistoryId: number;
  code: string;
  stockName?: string;
  analysisDate?: string;
  evalWindowDays: number;
  engineVersion: string;
  evalStatus: string;
  evaluatedAt?: string;
  operationAdvice?: string;
  trendPrediction?: string;
  positionRecommendation?: string;
  startPrice?: number;
  endClose?: number;
  maxHigh?: number;
  minLow?: number;
  stockReturnPct?: number;
  actualReturnPct?: number;
  actualMovement?: string;
  directionExpected?: string;
  directionCorrect?: boolean;
  outcome?: string;
  stopLoss?: number;
  takeProfit?: number;
  hitStopLoss?: boolean;
  hitTakeProfit?: boolean;
  firstHit?: string;
  firstHitDate?: string;
  firstHitTradingDays?: number;
  simulatedEntryPrice?: number;
  simulatedExitPrice?: number;
  simulatedExitReason?: string;
  simulatedReturnPct?: number;
}

export interface BacktestResultsResponse {
  total: number;
  page: number;
  limit: number;
  items: BacktestResultItem[];
}

// ============ Performance Metrics ============

export interface PerformanceMetrics {
  scope: string;
  code?: string;
  evalWindowDays: number;
  engineVersion: string;
  computedAt?: string;

  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;

  directionAccuracyPct?: number;
  winRatePct?: number;
  neutralRatePct?: number;
  avgStockReturnPct?: number;
  avgSimulatedReturnPct?: number;

  stopLossTriggerRate?: number;
  takeProfitTriggerRate?: number;
  ambiguousRate?: number;
  avgDaysToFirstHit?: number;

  adviceBreakdown: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
}
