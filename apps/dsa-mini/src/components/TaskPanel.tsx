import React from 'react'
import { View, Text, Progress } from '@tarojs/components'
import './task-panel.scss'

interface TaskInfo {
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

interface TaskPanelProps {
  tasks: TaskInfo[]
  onTaskComplete?: () => void
}

const TaskPanel: React.FC<TaskPanelProps> = ({ tasks, onTaskComplete }) => {
  if (tasks.length === 0) {
    return null
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '等待中'
      case 'processing':
        return '分析中'
      case 'completed':
        return '已完成'
      case 'failed':
        return '失败'
      default:
        return status
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return '#999999'
      case 'processing':
        return '#1890ff'
      case 'completed':
        return '#52c41a'
      case 'failed':
        return '#ff4d4f'
      default:
        return '#999999'
    }
  }

  return (
    <View className='task-panel'>
      <View className='panel-header'>
        <Text className='panel-title'>分析任务</Text>
        <Text className='task-count'>{tasks.length} 个任务</Text>
      </View>
      <View className='task-list'>
        {tasks.map((task) => (
          <View key={task.taskId} className='task-item'>
            <View className='task-info'>
              <View className='task-stock'>
                <Text className='task-stock-name'>
                  {task.stockName || task.stockCode}
                </Text>
                <Text className='task-stock-code'>({task.stockCode})</Text>
              </View>
              <View className='task-status'>
                <Text
                  className='task-status-text'
                  style={{ color: getStatusColor(task.status) }}
                >
                  {getStatusText(task.status)}
                </Text>
                {task.progress > 0 && (
                  <Text className='task-progress-text'>{task.progress}%</Text>
                )}
              </View>
            </View>
            {task.status === 'processing' && task.progress > 0 && (
              <View className='task-progress'>
                <Progress
                  percent={task.progress}
                  activeColor='#1890ff'
                  backgroundColor='#f0f0f0'
                  strokeWidth={4}
                />
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
    </View>
  )
}

export default TaskPanel
