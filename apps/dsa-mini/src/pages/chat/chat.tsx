import React, { useState, useEffect } from 'react'
import { View, Text, ScrollView, Input, Button } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import './chat.scss'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

const ChatPage: React.FC = () => {
  const router = useRouter()
  const [stockCode, setStockCode] = useState('')
  const [stockName, setStockName] = useState('')
  const [recordId, setRecordId] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const { stock, name, recordId: id } = router.params
    if (stock) setStockCode(stock)
    if (name) setStockName(decodeURIComponent(name))
    if (id) setRecordId(id)
    setIsLoading(false)
  }, [])

  const handleSend = async () => {
    if (!inputValue.trim() || isSending) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsSending(true)

    try {
      // TODO: Call chat API
      const response = await Taro.request({
        url: `${process.env.API_BASE_URL || 'http://localhost:8000'}/api/v1/chat`,
        method: 'POST',
        data: {
          record_id: parseInt(recordId),
          message: userMessage.content
        }
      })

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.reply || '收到您的问题，正在分析...',
        timestamp: new Date().toISOString()
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      console.error('Chat failed:', err)
      Taro.showToast({
        title: '发送失败',
        icon: 'none'
      })
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyDown = (e: any) => {
    if (e.detail?.value && inputValue.trim() && !isSending) {
      handleSend()
    }
  }

  if (isLoading) {
    return (
      <View className='chat-page loading'>
        <Text>加载中...</Text>
      </View>
    )
  }

  return (
    <View className='chat-page'>
      {/* 头部股票信息 */}
      <View className='chat-header'>
        <View className='stock-info'>
          <Text className='stock-name'>{stockName || stockCode}</Text>
          <Text className='stock-code'>({stockCode})</Text>
        </View>
      </View>

      {/* 消息列表 */}
      <ScrollView className='message-scroll' scrollY scrollIntoView='message-end'>
        <View className='message-list'>
          {messages.length === 0 && (
            <View className='empty-message'>
              <Text className='empty-icon'>💬</Text>
              <Text className='empty-text'>开始与 AI 对话</Text>
              <Text className='empty-hint'>
                您可以询问关于 {stockName || stockCode} 的任何问题
              </Text>
            </View>
          )}

          {messages.map((msg) => (
            <View
              key={msg.id}
              className={`message-item ${msg.role === 'user' ? 'user' : 'assistant'}`}
            >
              <View className='message-avatar'>
                {msg.role === 'user' ? '👤' : '🤖'}
              </View>
              <View className='message-content'>
                <Text className='message-text'>{msg.content}</Text>
                <Text className='message-time'>
                  {new Date(msg.timestamp).toLocaleTimeString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </Text>
              </View>
            </View>
          ))}
          <View id='message-end' />
        </View>
      </ScrollView>

      {/* 输入框 */}
      <View className='chat-input-area'>
        <View className='input-wrapper'>
          <Input
            className='chat-input'
            type='text'
            value={inputValue}
            onChange={(e) => setInputValue(e.detail.value)}
            onConfirm={handleKeyDown}
            placeholder='输入您的问题...'
            disabled={isSending}
          />
          <Button
            className='send-btn'
            onClick={handleSend}
            disabled={!inputValue.trim() || isSending}
          >
            {isSending ? '发送中' : '发送'}
          </Button>
        </View>
      </View>
    </View>
  )
}

export default ChatPage
