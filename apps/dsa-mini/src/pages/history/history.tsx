import React, { useState, useEffect } from 'react'
import { View, Text, ScrollView, RefreshControl } from '@tarojs/components'
import Taro from '@tarojs/taro'
import HistoryList from '@/components/HistoryList'
import './history.scss'

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

const HistoryPage: React.FC = () => {
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedId, setSelectedId] = useState<number>()
  const pageSize = 20

  const fetchHistory = async (reset = true, silent = false) => {
    if (!silent) {
      if (reset) {
        setIsLoading(true)
        setCurrentPage(1)
      } else {
        setIsLoadingMore(true)
      }
    }

    const page = reset ? 1 : currentPage + 1

    try {
      const tomorrowDate = new Date()
      tomorrowDate.setDate(tomorrowDate.getDate() + 1)
      const startDate = new Date()
      startDate.setDate(startDate.getDate() - 30)

      const response = await Taro.request({
        url: `${process.env.API_BASE_URL || 'http://localhost:8000'}/api/v1/history`,
        method: 'GET',
        data: {
          page,
          limit: pageSize,
          start_date: startDate.toISOString().split('T')[0],
          end_date: tomorrowDate.toISOString().split('T')[0]
        }
      })

      const { data } = response
      const items = data.items || []

      if (reset) {
        setHistoryItems(items)
        setCurrentPage(1)
      } else {
        setHistoryItems(prev => [...prev, ...items])
        setCurrentPage(page)
      }

      if (!silent) {
        const totalLoaded = reset ? items.length : historyItems.length + items.length
        setHasMore(totalLoaded < data.total)
      }
    } catch (err) {
      console.error('Failed to fetch history:', err)
    } finally {
      setIsLoading(false)
      setIsLoadingMore(false)
    }
  }

  useEffect(() => {
    fetchHistory()
  }, [])

  const handleLoadMore = () => {
    if (!isLoadingMore && hasMore) {
      fetchHistory(false)
    }
  }

  const handleItemClick = async (recordId: number) => {
    setSelectedId(recordId)
    try {
      await Taro.navigateTo({
        url: `/pages/report/report?id=${recordId}`
      })
    } catch (err) {
      console.error('Failed to navigate to report:', err)
    }
  }

  const handleRefresh = async () => {
    await fetchHistory(true, false)
  }

  return (
    <View className='history-page'>
      <View className='page-header'>
        <Text className='page-title'>分析历史</Text>
      </View>
      <View className='page-content'>
        <HistoryList
          items={historyItems}
          isLoading={isLoading}
          isLoadingMore={isLoadingMore}
          hasMore={hasMore}
          selectedId={selectedId}
          onItemClick={handleItemClick}
          onLoadMore={handleLoadMore}
        />
      </View>
    </View>
  )
}

export default HistoryPage
