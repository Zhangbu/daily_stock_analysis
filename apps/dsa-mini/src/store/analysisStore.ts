import { makeAutoObservable, runInAction } from 'mobx'
import { analysisApi, taskApi, type TaskInfo, type AnalysisRequest } from '@/services/api'

class AnalysisStore {
  tasks: TaskInfo[] = []
  isAnalyzing = false
  error: string | null = null

  constructor() {
    makeAutoObservable(this)
  }

  setTasks(tasks: TaskInfo[]) {
    this.tasks = tasks
  }

  addTask(task: TaskInfo) {
    const existingIndex = this.tasks.findIndex(t => t.taskId === task.taskId)
    if (existingIndex >= 0) {
      this.tasks[existingIndex] = task
    } else {
      this.tasks.unshift(task)
    }
  }

  updateTask(taskId: string, updates: Partial<TaskInfo>) {
    const task = this.tasks.find(t => t.taskId === taskId)
    if (task) {
      Object.assign(task, updates)
    }
  }

  setIsAnalyzing(value: boolean) {
    this.isAnalyzing = value
  }

  setError(error: string | null) {
    this.error = error
  }

  async submitAnalysis(params: AnalysisRequest) {
    this.setIsAnalyzing(true)
    this.setError(null)

    try {
      const response = await analysisApi.analyze(params)
      if (response.success && response.taskId) {
        // Add new task to the list
        const newTask: TaskInfo = {
          taskId: response.taskId,
          stockCode: params.stock_code,
          reportType: params.report_type,
          status: 'pending',
          progress: 0,
          createdAt: new Date().toISOString()
        }
        this.addTask(newTask)
        return { success: true, taskId: response.taskId }
      } else {
        this.setError(response.message || '分析失败')
        return { success: false, message: response.message }
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '网络错误'
      this.setError(errorMsg)
      return { success: false, message: errorMsg }
    } finally {
      runInAction(() => {
        this.setIsAnalyzing(false)
      })
    }
  }

  async refreshTasks() {
    try {
      const tasks = await taskApi.getList()
      runInAction(() => {
        this.setTasks(tasks)
      })
    } catch (err) {
      console.error('Failed to refresh tasks:', err)
    }
  }

  clearError() {
    this.setError(null)
  }
}

export const analysisStore = new AnalysisStore()

// Hook for React components
export const useAnalysisStore = () => {
  return analysisStore
}
