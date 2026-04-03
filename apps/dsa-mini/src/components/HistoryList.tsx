import React, { useState, useCallback, useRef, useEffect } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './history-list.scss'

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

interface HistoryListProps {
  items: HistoryItem[]
  isLoading: boolean
  isLoadingMore: boolean
  hasMore: boolean
  selectedId?: number
  onItemClick: (recordId: number) => void
  onLoadMore: () => void
  manualCount?: number
  smartCount?: number
}

type SourceFilter = 'all' | 'manual' | 'smart_selection'

// 获取情感颜色
const getSentimentColor = (score: number): string => {
  if (score <= 20) return '#ff4d4f'
  if (score <= 40) return '#ff7a45'
  if (score <= 60) return '#ffc107'
  if (score <= 80) return '#52c41a'
  return '#13c2c2'
}

// 格式化日期时间
const formatDateTime = (value: string): string => {
  if (!value) return '--'
  const date = new Date(value)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

// 格式化涨跌幅
const formatChangePct = (value?: number): string => {
  if (value === undefined || value === null || Number.isNaN(value)) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

// 获取涨跌幅颜色
const getChangePctColor = (value?: number): string => {
  if (value === undefined || value === null || Number.isNaN(value)) return '#999999'
  if (value > 0) return '#ff4d4f'
  if (value < 0) return '#52c41a'
  return '#999999'
}

const HistoryList: React.FC<HistoryListProps> = ({
  items,
  isLoading,
  isLoadingMore,
  hasMore,
  selectedId,
  onItemClick,
  onLoadMore,
  manualCount = 0,
  smartCount = 0
}) => {
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')
  const lowerThreshold = 50

  // 根据筛选条件过滤历史项
  const filteredItems = items.filter(item => {
    if (sourceFilter === 'all') return true
    if (sourceFilter === 'manual') return !item.source || item.source === 'manual'
    if (sourceFilter === 'smart_selection') return item.source === 'smart_selection'
    return true
  })

  // 计算手动和智能选股数量
  const computedManualCount = manualCount || items.filter(i => !i.source || i.source === 'manual').length
  const computedSmartCount = smartCount || items.filter(i => i.source === 'smart_selection').length

  // 滚动到底部加载更多
  const handleScrollToLower = useCallback(() => {
    if (hasMore && !isLoading && !isLoadingMore) {
      onLoadMore()
    }
  }, [hasMore, isLoading, isLoadingMore, onLoadMore])

  // 渲染空状态
  const renderEmpty = () => (
    <View className='empty-state'>
      <View className='empty-icon'>
        <View className='icon-clock' />
      </View>
      <Text className='empty-text'>
        {items.length === 0
          ? '暂无历史记录'
          : sourceFilter === 'manual'
            ? '暂无自选股记录'
            : sourceFilter === 'smart_selection'
              ? '暂无推荐股记录'
              : '该分类下暂无记录'}
      </Text>
      {items.length === 0 && (
        <Text className='empty-hint'>在上方输入股票代码开始分析</Text>
      )}
    </View>
  )

  return (
    <View className='history-list-container'>
      {/* 筛选标签 */}
      <View className='filter-tabs'>
        <View
          className={`filter-tab ${sourceFilter === 'all' ? 'active' : ''}`}
          onClick={() => setSourceFilter('all')}
        >
          <Text>全部 ({items.length})</Text>
        </View>
        <View
          className={`filter-tab ${sourceFilter === 'manual' ? 'active manual' : ''}`}
          onClick={() => setSourceFilter('manual')}
        >
          <Text>自选 ({computedManualCount})</Text>
        </View>
        <View
          className={`filter-tab ${sourceFilter === 'smart_selection' ? 'active smart' : ''}`}
          onClick={() => setSourceFilter('smart_selection')}
        >
          <Text>推荐 ({computedSmartCount})</Text>
        </View>
      </View>

      {/* 列表内容 */}
      {isLoading ? (
        <View className='loading-state'>
          <View className='loading-spinner' />
          <Text className='loading-text'>加载中...</Text>
        </View>
      ) : filteredItems.length === 0 ? (
        renderEmpty()
      ) : (
        <ScrollView
          className='history-scroll'
          scrollY
          lowerThreshold={lowerThreshold}
          onScrollToLower={handleScrollToLower}
        >
          <View className='history-items'>
            {filteredItems.map((item) => (
              <View
                key={item.id}
                className={`history-item ${selectedId === item.id ? 'active' : ''}`}
                onClick={() => onItemClick(item.id)}
              >
                <View className='item-content'>
                  {/* 情感分数指示条 */}
                  {item.sentimentScore !== undefined && (
                    <View
                      className='sentiment-bar'
                      style={{
                        backgroundColor: getSentimentColor(item.sentimentScore),
                        boxShadow: `0 0 12px ${getSentimentColor(item.sentimentScore)}40`
                      }}
                    />
                  )}
                  <View className='item-main'>
                    <View className='item-header'>
                      <View className='item-title-wrapper'>
                        <Text className='item-title'>
                          {item.stockName || item.stockCode}
                        </Text>
                        {/* 智能选股标识 */}
                        {item.source === 'smart_selection' && (
                          <View className='smart-badge'>
                            <Text className='smart-text'>荐</Text>
                          </View>
                        )}
                      </View>
                      {item.sentimentScore !== undefined && (
                        <View
                          className='sentiment-score'
                          style={{
                            color: getSentimentColor(item.sentimentScore),
                            backgroundColor: `${getSentimentColor(item.sentimentScore)}15`
                          }}
                        >
                          <Text>{item.sentimentScore}</Text>
                        </View>
                      )}
                    </View>
                    <View className='item-footer'>
                      <Text className='item-code'>{item.stockCode}</Text>
                      <Text className='item-dot'>·</Text>
                      <Text className='item-time'>{formatDateTime(item.createdAt)}</Text>
                      {/* 涨跌幅显示 */}
                      {item.changePct !== undefined && (
                        <>
                          <Text className='item-dot'>·</Text>
                          <Text
                            className='item-change'
                            style={{ color: getChangePctColor(item.changePct) }}
                          >
                            {formatChangePct(item.changePct)}
                          </Text>
                        </>
                      )}
                    </View>
                  </View>
                </View>
              </View>
            ))}

            {/* 加载更多状态 */}
            {isLoadingMore && (
              <View className='loading-more'>
                <View className='loading-spinner small' />
              </View>
            )}

            {/* 没有更多数据提示 */}
            {!hasMore && filteredItems.length > 0 && (
              <View className='no-more-text'>
                <Text>{sourceFilter === 'all' ? '已加载全部' : '当前分类下已加载全部'}</Text>
              </View>
            )}
          </View>
        </ScrollView>
      )}
    </View>
  )
}

export default HistoryList
