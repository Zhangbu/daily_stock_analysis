import React, { useState, useEffect } from 'react'
import { View, Text, ScrollView, RefreshControl } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { taskApi, type TaskInfo } from '@/services/api'
import './tasks.scss'

const TasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<TaskInfo[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const fetchTasks = async (refresh = false) => {
    if (refresh) {
      setIsRefreshing(true)
    } else {
      setIsLoading(true)
    }

    try {
      const data = await taskApi.getList()
      setTasks(data)
    } catch (err) {
      console.error('Failed to fetch tasks:', err)
      Taro.showToast({
        title: '加载任务列表失败',
        icon: 'none'
      })
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    fetchTasks()

    // Poll for task updates every 3 seconds
    const interval = setInterval(() => {
      fetchTasks()
    }, 3000)

    return () => clearInterval(interval)
  }, [])

  const handleRefresh = () => {
    fetchTasks(true)
  }

  const getStatusText = (status: string): string => {
    const map: Record<string, string> = {
      pending: '等待中',
      processing: '分析中',
      completed: '已完成',
      failed: '失败'
    }
    return map[status] || status
  }

  const getStatusColor = (status: string): string => {
    const map: Record<string, string> = {
      pending: '#999999',
      processing: '#1890ff',
      completed: '#52c41a',
      failed: '#ff4d4f'
    }
    return map[status] || '#999999'
  }

  const formatTime = (dateStr?: string): string => {
    if (!dateStr) return '--'
    const date = new Date(dateStr)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    return `${month}-${day} ${hour}:${minute}`
  }

  const handleRetry = (task: TaskInfo) => {
    Taro.showModal({
      title: '提示',
      content: `重新分析 ${task.stockCode}？`,
      success: async (res) => {
        if (res.confirm) {
          try {
            await Taro.request({
              url: `${process.env.API_BASE_URL || 'http://localhost:8000'}/api/v1/analysis/analyze`,
              method: 'POST',
              data: {
                stock_code: task.stockCode,
                report_type: task.reportType
              }
            })
            Taro.showToast({
              title: '已重新提交',
              icon: 'success'
            })
            fetchTasks(true)
          } catch (err) {
            Taro.showToast({
              title: '重新提交失败',
              icon: 'none'
            })
          }
        }
      }
    })
  }

  const handleViewReport = (task: TaskInfo) => {
    if (task.status === 'completed') {
      // Find the history record ID for this task
      Taro.navigateTo({
        url: `/pages/history/history?taskId=${task.taskId}`
      })
    }
  }

  const activeTasks = tasks.filter(t => t.status === 'pending' || t.status === 'processing')
  const completedTasks = tasks.filter(t => t.status === 'completed' || t.status === 'failed')

  return (
    <View className='tasks-page'>
      <View className='page-header'>
        <Text className='page-title'>分析任务</Text>
      </View>

      <View className='page-content'>
        <ScrollView className='task-scroll' scrollY>
          <RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh}>
            {/* 进行中的任务 */}
            {activeTasks.length > 0 && (
              <View className='task-section'>
                <Text className='section-title'>进行中</Text>
                {activeTasks.map((task) => (
                  <View key={task.taskId} className='task-item active'>
                    <View className='task-header'>
                      <View className='task-stock'>
                        <Text className='stock-name'>{task.stockName || task.stockCode}</Text>
                        <Text className='stock-code'>({task.stockCode})</Text>
                      </View>
                      <Text
                        className='task-status'
                        style={{ color: getStatusColor(task.status) }}
                      >
                        {getStatusText(task.status)}
                      </Text>
                    </View>

                    <View className='task-meta'>
                      <Text className='meta-label'>报告类型</Text>
                      <Text className='meta-value'>
                        {task.reportType === 'detailed' ? '详细版' : '简易版'}
                      </Text>
                    </View>

                    <View className='task-meta'>
                      <Text className='meta-label'>提交时间</Text>
                      <Text className='meta-value'>{formatTime(task.createdAt)}</Text>
                    </View>

                    {task.status === 'processing' && task.progress > 0 && (
                      <View className='task-progress'>
                        <View className='progress-bar'>
                          <View
                            className='progress-fill'
                            style={{ width: `${task.progress}%` }}
                          />
                        </View>
                        <Text className='progress-text'>{task.progress}%</Text>
                      </View>
                    )}

                    {task.message && (
                      <View className='task-message'>
                        <Text>{task.message}</Text>
                      </View>
                    )}
                  </View>
                ))}
              </View>
            )}

            {/* 已完成的任务 */}
            {completedTasks.length > 0 && (
              <View className='task-section'>
                <Text className='section-title'>历史记录</Text>
                {completedTasks.map((task) => (
                  <View key={task.taskId} className='task-item'>
                    <View className='task-header'>
                      <View className='task-stock'>
                        <Text className='stock-name'>{task.stockName || task.stockCode}</Text>
                        <Text className='stock-code'>({task.stockCode})</Text>
                      </View>
                      <View className='task-actions'>
                        {task.status === 'failed' && (
                          <View className='action-btn' onClick={() => handleRetry(task)}>
                            <Text className='action-text'>重试</Text>
                          </View>
                        )}
                        <Text
                          className='task-status'
                          style={{ color: getStatusColor(task.status) }}
                        >
                          {getStatusText(task.status)}
                        </Text>
                      </View>
                    </View>

                    <View className='task-meta'>
                      <Text className='meta-label'>报告类型</Text>
                      <Text className='meta-value'>
                        {task.reportType === 'detailed' ? '详细版' : '简易版'}
                      </Text>
                    </View>

                    <View className='task-meta'>
                      <Text className='meta-label'>完成时间</Text>
                      <Text className='meta-value'>{formatTime(task.completedAt)}</Text>
                    </View>

                    {task.status === 'completed' && (
                      <View
                        className='view-report-btn'
                        onClick={() => handleViewReport(task)}
                      >
                        <Text>查看报告</Text>
                      </View>
                    )}

                    {task.error && (
                      <View className='task-error'>
                        <Text>{task.error}</Text>
                      </View>
                    )}
                  </View>
                ))}
              </View>
            )}

            {/* 空状态 */}
            {tasks.length === 0 && !isLoading && (
              <View className='empty-state'>
                <Text className='empty-icon'>📋</Text>
                <Text className='empty-text'>暂无分析任务</Text>
                <Text className='empty-hint'>在首页提交股票分析请求</Text>
              </View>
            )}

            {isLoading && tasks.length === 0 && (
              <View className='loading-state'>
                <Text>加载中...</Text>
              </View>
            )}
          </RefreshControl>
        </ScrollView>
      </View>
    </View>
  )
}

export default TasksPage
