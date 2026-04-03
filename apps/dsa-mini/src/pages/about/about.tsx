import React from 'react'
import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './about.scss'

const AboutPage: React.FC = () => {
  const handleCopy = () => {
    Taro.setClipboardData({
      data: 'support@example.com'
    })
  }

  return (
    <View className='about-page'>
      <View className='page-header'>
        <Text className='page-title'>关于我们</Text>
      </View>

      <View className='page-content'>
        {/* Logo */}
        <View className='logo-section'>
          <View className='logo-icon'>📊</View>
          <Text className='app-name'>每日股票分析</Text>
          <Text className='app-slogan'>AI 驱动的智能投资助手</Text>
        </View>

        {/* 应用介绍 */}
        <View className='intro-section'>
          <Text className='section-title'>应用介绍</Text>
          <Text className='intro-text'>
            每日股票分析是一款基于人工智能的股票分析工具，
            通过深度学习模型对海量新闻、财报、社交媒体数据进行分析，
            为投资者提供专业的情感分析、趋势预测和操作建议。
          </Text>
        </View>

        {/* 主要功能 */}
        <View className='features-section'>
          <Text className='section-title'>主要功能</Text>
          <View className='feature-list'>
            <View className='feature-item'>
              <Text className='feature-icon'>🤖</Text>
              <View className='feature-info'>
                <Text className='feature-title'>AI 智能分析</Text>
                <Text className='feature-desc'>基于大语言模型的多维度股票分析</Text>
              </View>
            </View>
            <View className='feature-item'>
              <Text className='feature-icon'>📈</Text>
              <View className='feature-info'>
                <Text className='feature-title'>趋势预测</Text>
                <Text className='feature-desc'>基于情感分析的趋势走向预测</Text>
              </View>
            </View>
            <View className='feature-item'>
              <Text className='feature-icon'>💡</Text>
              <View className='feature-info'>
                <Text className='feature-title'>操作建议</Text>
                <Text className='feature-desc'>买入/卖出/持仓的专业建议</Text>
              </View>
            </View>
            <View className='feature-item'>
              <Text className='feature-icon'>💬</Text>
              <View className='feature-info'>
                <Text className='feature-title'>AI 对话</Text>
                <Text className='feature-desc'>与分析 AI 进行交互式问答</Text>
              </View>
            </View>
          </View>
        </View>

        {/* 联系方式 */}
        <View className='contact-section'>
          <Text className='section-title'>联系我们</Text>
          <View className='contact-item' onClick={handleCopy}>
            <Text className='contact-label'>客服邮箱</Text>
            <Text className='contact-value'>support@example.com</Text>
          </View>
        </View>

        {/* 版本信息 */}
        <View className='version-section'>
          <Text className='version-text'>当前版本：v1.0.0</Text>
          <Text className='copyright'>© 2026 每日股票分析</Text>
        </View>
      </View>
    </View>
  )
}

export default AboutPage
