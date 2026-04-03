import React, { useState, useEffect } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { historyApi } from '@/services/api'
import './report.scss'

interface ReportMeta {
  id?: number
  queryId: string
  stockCode: string
  stockName: string
  reportType: 'simple' | 'detailed'
  createdAt: string
  currentPrice?: number
  changePct?: number
}

interface ReportSummary {
  analysisSummary: string
  operationAdvice: string
  trendPrediction: string
  sentimentScore: number
  sentimentLabel?: string
}

interface ReportStrategy {
  idealBuy?: string
  secondaryBuy?: string
  stopLoss?: string
  takeProfit?: string
}

interface AnalysisReport {
  meta: ReportMeta
  summary: ReportSummary
  strategy?: ReportStrategy
  details?: {
    newsContent?: string
    rawResult?: Record<string, unknown>
    contextSnapshot?: Record<string, unknown>
  }
}

const ReportPage: React.FC = () => {
  const router = useRouter()
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const id = router.params.id
    if (id) {
      fetchReport(parseInt(id))
    }
  }, [])

  const fetchReport = async (recordId: number) => {
    setIsLoading(true)
    try {
      const response = await Taro.request({
        url: `${process.env.API_BASE_URL || 'http://localhost:8000'}/api/v1/history/${recordId}`,
        method: 'GET'
      })
      setReport(response.data)
    } catch (err) {
      console.error('Failed to fetch report:', err)
      Taro.showToast({
        title: '加载报告失败',
        icon: 'none'
      })
    } finally {
      setIsLoading(false)
    }
  }

  const getSentimentLabel = (score: number): string => {
    if (score <= 20) return '极度悲观'
    if (score <= 40) return '悲观'
    if (score <= 60) return '中性'
    if (score <= 80) return '乐观'
    return '极度乐观'
  }

  const getSentimentColor = (score: number): string => {
    if (score <= 20) return '#ff4d4f'
    if (score <= 40) return '#ff7a45'
    if (score <= 60) return '#ffc107'
    if (score <= 80) return '#52c41a'
    return '#13c2c2'
  }

  const formatChangePct = (value?: number): string => {
    if (value === undefined || value === null || Number.isNaN(value)) return '--'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
  }

  const getChangePctColor = (value?: number): string => {
    if (value === undefined || value === null || Number.isNaN(value)) return '#999999'
    if (value > 0) return '#ff4d4f'
    if (value < 0) return '#52c41a'
    return '#999999'
  }

  const handleFollowUp = () => {
    if (report?.meta.id) {
      Taro.navigateTo({
        url: `/pages/chat/chat?stock=${report.meta.stockCode}&name=${report.meta.stockName}&recordId=${report.meta.id}`
      })
    }
  }

  if (isLoading) {
    return (
      <View className='report-page loading'>
        <View className='loading-container'>
          <View className='loading-spinner' />
          <Text className='loading-text'>加载报告中...</Text>
        </View>
      </View>
    )
  }

  if (!report) {
    return (
      <View className='report-page empty'>
        <Text className='empty-text'>未找到报告</Text>
      </View>
    )
  }

  const sentimentColor = getSentimentColor(report.summary.sentimentScore)

  return (
    <View className='report-page'>
      <ScrollView className='report-scroll' scrollY>
        {/* 股票头部 */}
        <View className='report-header'>
          <View className='stock-info'>
            <Text className='stock-name'>{report.meta.stockName}</Text>
            <Text className='stock-code'>({report.meta.stockCode})</Text>
          </View>
          <View className='stock-meta'>
            {report.meta.currentPrice && (
              <Text className='stock-price'>
                ¥{report.meta.currentPrice.toFixed(2)}
              </Text>
            )}
            {report.meta.changePct !== undefined && (
              <Text
                className='stock-change'
                style={{ color: getChangePctColor(report.meta.changePct) }}
              >
                {formatChangePct(report.meta.changePct)}
              </Text>
            )}
          </View>
        </View>

        {/* 情感评分卡片 */}
        <View className='sentiment-card'>
          <View
            className='sentiment-circle'
            style={{
              background: `conic-gradient(${sentimentColor} ${report.summary.sentimentScore * 3.6}deg, #f0f0f0 0deg)`
            }}
          >
            <View className='sentiment-inner'>
              <Text className='sentiment-value'>{report.summary.sentimentScore}</Text>
              <Text className='sentiment-label'>
                {getSentimentLabel(report.summary.sentimentScore)}
              </Text>
            </View>
          </View>
          <View className='sentiment-info'>
            <View className='info-item'>
              <Text className='info-label'>操作建议</Text>
              <Text className='info-value'>{report.summary.operationAdvice}</Text>
            </View>
            <View className='info-item'>
              <Text className='info-label'>趋势预测</Text>
              <Text className='info-value'>{report.summary.trendPrediction}</Text>
            </View>
          </View>
        </View>

        {/* 分析摘要 */}
        <View className='section'>
          <View className='section-header'>
            <Text className='section-title'>分析摘要</Text>
          </View>
          <View className='section-content'>
            <Text className='summary-text'>{report.summary.analysisSummary}</Text>
          </View>
        </View>

        {/* 策略点位 */}
        {report.strategy && (
          <View className='section'>
            <View className='section-header'>
              <Text className='section-title'>策略点位</Text>
            </View>
            <View className='strategy-grid'>
              {report.strategy.idealBuy && (
                <View className='strategy-item'>
                  <Text className='strategy-label'>理想买入</Text>
                  <Text className='strategy-value'>{report.strategy.idealBuy}</Text>
                </View>
              )}
              {report.strategy.secondaryBuy && (
                <View className='strategy-item'>
                  <Text className='strategy-label'>次优买入</Text>
                  <Text className='strategy-value'>{report.strategy.secondaryBuy}</Text>
                </View>
              )}
              {report.strategy.stopLoss && (
                <View className='strategy-item'>
                  <Text className='strategy-label'>止损位</Text>
                  <Text className='strategy-value'>{report.strategy.stopLoss}</Text>
                </View>
              )}
              {report.strategy.takeProfit && (
                <View className='strategy-item'>
                  <Text className='strategy-label'>目标位</Text>
                  <Text className='strategy-value'>{report.strategy.takeProfit}</Text>
                </View>
              )}
            </View>
          </View>
        )}

        {/* 追问 AI 按钮 */}
        <View className='followup-section'>
          <View className='followup-btn' onClick={handleFollowUp}>
            <Text className='followup-icon'>💬</Text>
            <Text className='followup-text'>追问 AI</Text>
          </View>
        </View>

        <View className='bottom-safe-area' />
      </ScrollView>
    </View>
  )
}

export default ReportPage
