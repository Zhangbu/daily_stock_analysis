import React, { useEffect } from 'react'
import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

function Index() {
  useEffect(() => {
    // 跳转到首页
    Taro.redirectTo({
      url: '/pages/home/home'
    })
  }, [])

  return (
    <View className='index'>
      <Text className='title'>每日股票分析</Text>
      <Text className='subtitle'>AI 驱动的智能投资助手</Text>
    </View>
  )
}

export default Index
