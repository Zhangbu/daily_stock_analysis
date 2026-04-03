import Taro from '@tarojs/taro'

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: Record<string, unknown>
  header?: Record<string, string>
}

export const request = async <T>(options: RequestOptions): Promise<T> => {
  const { url, method = 'GET', data, header = {} } = options

  try {
    const response = await Taro.request({
      url: `${API_BASE_URL}${url}`,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        ...header
      }
    })

    return response.data as T
  } catch (err) {
    console.error('API request failed:', err)
    Taro.showToast({
      title: '网络请求失败',
      icon: 'none'
    })
    throw err
  }
}

// History API
export interface HistoryItem {
  id: number
  queryId: string
  stockCode: string
  stockName?: string
  reportType?: string
  source?: 'manual' | 'smart_selection'
  sentimentScore?: number
  operationAdvice?: string
  createdAt: string
  changePct?: number
}

export interface HistoryResponse {
  items: HistoryItem[]
  total: number
}

export const historyApi = {
  getList: async (params: {
    page: number
    limit: number
    start_date?: string
    end_date?: string
  }): Promise<HistoryResponse> => {
    return request<HistoryResponse>({
      url: '/api/v1/history',
      method: 'GET',
      data: params
    })
  },

  getDetail: async (id: number): Promise<AnalysisReport> => {
    return request<AnalysisReport>({
      url: `/api/v1/history/${id}`,
      method: 'GET'
    })
  }
}

// Analysis API
export interface AnalysisRequest {
  stock_code: string
  report_type: 'simple' | 'detailed'
  is_test?: boolean
}

export interface AnalysisResponse {
  success: boolean
  message?: string
  taskId?: string
}

export const analysisApi = {
  analyze: async (data: AnalysisRequest): Promise<AnalysisResponse> => {
    return request<AnalysisResponse>({
      url: '/api/v1/analysis/analyze',
      method: 'POST',
      data
    })
  }
}

// Task API
export interface TaskInfo {
  taskId: string
  stockCode: string
  stockName?: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  message?: string
  reportType: string
  createdAt: string
  startedAt?: string
  completedAt?: string
  error?: string
}

export const taskApi = {
  getList: async (): Promise<TaskInfo[]> => {
    return request<TaskInfo[]>({
      url: '/api/v1/tasks',
      method: 'GET'
    })
  }
}

// Analysis Report Interface
export interface AnalysisReport {
  meta: {
    id?: number
    queryId: string
    stockCode: string
    stockName: string
    reportType: 'simple' | 'detailed'
    createdAt: string
    currentPrice?: number
    changePct?: number
  }
  summary: {
    analysisSummary: string
    operationAdvice: string
    trendPrediction: string
    sentimentScore: number
    sentimentLabel?: string
  }
  strategy?: {
    idealBuy?: string
    secondaryBuy?: string
    stopLoss?: string
    takeProfit?: string
  }
  details?: {
    newsContent?: string
    rawResult?: Record<string, unknown>
    contextSnapshot?: Record<string, unknown>
  }
}
