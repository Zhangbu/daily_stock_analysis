import React, { useState } from 'react'
import { View, Text, Input, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { historyApi } from '@/services/api'
import HistoryList from '@/components/HistoryList'
import TaskPanel from '@/components/TaskPanel'
import './home.scss'

interface HistoryItem {
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

const HomePage: React.FC = () => {
  const [stockCode, setStockCode] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [inputError, setInputError] = useState<string>()
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedId, setSelectedId] = useState<number>()
  const [duplicateError, setDuplicateError] = useState<string | null>(null)
  const [activeTasks, setActiveTasks] = useState<any[]>([])
  const pageSize = 20

  // 验证股票代码
  const validateStockCode = (code: string): { valid: boolean; message?: string; normalized?: string } => {
    const trimmed = code.trim().toUpperCase()
    const cnPattern = /^[0-3]\d{5}$/
    const hkPattern = /^HK\d{5}$/i
    const usPattern = /^[A-Z]{1,5}$/

    if (cnPattern.test(trimmed) || hkPattern.test(trimmed) || usPattern.test(trimmed)) {
      return { valid: true, normalized: trimmed }
    }

    if (trimmed.length < 3) {
      return { valid: false, message: '代码长度不足' }
    }

    return { valid: false, message: '请输入有效的股票代码' }
  }

  // 加载历史记录
  const fetchHistory = async (reset = true, silent = false) => {
    if (!silent) {
      if (reset) {
        setIsLoadingHistory(true)
        setCurrentPage(1)
      }
    }

    const page = reset ? 1 : currentPage + 1

    try {
      const tomorrowDate = new Date()
      tomorrowDate.setDate(tomorrowDate.getDate() + 1)

      const startDate = new Date()
      startDate.setDate(startDate.getDate() - 30)

      const response = await historyApi.getList({
        page,
        limit: pageSize,
        start_date: startDate.toISOString().split('T')[0],
        end_date: tomorrowDate.toISOString().split('T')[0]
      })

      const items = response.items || []

      if (silent && reset) {
        setHistoryItems(prev => {
          const existingIds = new Set(prev.map(item => item.id))
          const newItems = items.filter((item: HistoryItem) => !existingIds.has(item.id))
          return newItems.length > 0 ? [...newItems, ...prev] : prev
        })
      } else if (reset) {
        setHistoryItems(items)
        setCurrentPage(1)
      } else {
        setHistoryItems(prev => [...prev, ...items])
        setCurrentPage(page)
      }

      if (!silent) {
        const totalLoaded = reset ? items.length : historyItems.length + items.length
        setHasMore(totalLoaded < response.total)
      }
    } catch (err) {
      console.error('Failed to fetch history:', err)
    } finally {
      setIsLoadingHistory(false)
    }
  }

  // 加载更多历史记录
  const handleLoadMore = () => {
    if (!isLoadingHistory && hasMore) {
      fetchHistory(false)
    }
  }

  // 分析股票
  const handleAnalyze = async () => {
    const { valid, message, normalized } = validateStockCode(stockCode)
    if (!valid) {
      setInputError(message || '请输入有效的股票代码')
      return
    }

    setInputError(undefined)
    setDuplicateError(null)
    setIsAnalyzing(true)

    try {
      const response = await Taro.request({
        url: `${process.env.API_BASE_URL || 'http://localhost:8000'}/api/v1/analysis/analyze`,
        method: 'POST',
        data: {
          stock_code: normalized,
          report_type: 'detailed',
          async_mode: true
        }
      })

      if (response.statusCode === 202 || response.statusCode === 200) {
        setStockCode('')
        Taro.showToast({
          title: '分析任务已提交',
          icon: 'success'
        })
        // Refresh history after successful submission
        fetchHistory(true, false)
      }
    } catch (err: any) {
      console.error('Analysis failed:', err)
      if (err.errMsg?.includes('409')) {
        setDuplicateError(`股票 ${normalized} 正在分析中，请等待完成`)
      } else {
        Taro.showToast({
          title: '分析失败，请稍后重试',
          icon: 'none'
        })
      }
    } finally {
      setIsAnalyzing(false)
    }
  }

  // 点击历史项
  const handleHistoryClick = async (recordId: number) => {
    setSelectedId(recordId)
    Taro.navigateTo({ url: `/pages/report/report?id=${recordId}` })
  }

  // 回车提交
  const handleKeyDown = (e: any) => {
    if (e.detail?.value && stockCode && !isAnalyzing) {
      handleAnalyze()
    }
  }

  return (
    <View className='home-page'>
      {/* 顶部输入栏 */}
      <View className='header-input'>
        <View className='input-container'>
          <Input
            className='stock-input'
            type='text'
            value={stockCode}
            onChange={(e) => {
              setStockCode(e.detail.value.toUpperCase())
              setInputError(undefined)
            }}
            onConfirm={handleKeyDown}
            placeholder='输入股票代码，如 600519、00700、AAPL'
            disabled={isAnalyzing}
          />
          {inputError && <Text className='error-text'>{inputError}</Text>}
          {duplicateError && <Text className='warning-text'>{duplicateError}</Text>}
        </View>
        <Button
          className='analyze-btn'
          onClick={handleAnalyze}
          disabled={!stockCode || isAnalyzing}
        >
          {isAnalyzing ? '分析中' : '分析'}
        </Button>
      </View>

      {/* 任务面板 */}
      {activeTasks.length > 0 && (
        <TaskPanel
          tasks={activeTasks}
          onTaskComplete={() => fetchHistory(true, true)}
        />
      )}

      {/* 历史列表 */}
      <View className='history-section'>
        <View className='section-header'>
          <Text className='section-title'>历史记录</Text>
        </View>
        <HistoryList
          items={historyItems}
          isLoading={isLoadingHistory}
          isLoadingMore={false}
          hasMore={hasMore}
          selectedId={selectedId}
          onItemClick={handleHistoryClick}
          onLoadMore={handleLoadMore}
        />
      </View>
    </View>
  )
}

export default HomePage
