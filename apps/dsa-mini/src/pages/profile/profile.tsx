import React from 'react'
import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './profile.scss'

const ProfilePage: React.FC = () => {
  const handleFeedback = () => {
    Taro.showToast({
      title: '功能开发中',
      icon: 'none'
    })
  }

  const handleAbout = () => {
    Taro.navigateTo({
      url: '/pages/about/about'
    })
  }

  const menuItems = [
    { icon: '⚙️', label: '设置', path: '' },
    { icon: '📊', label: '订阅管理', path: '' },
    { icon: '🔔', label: '通知设置', path: '' },
    { icon: '❓', label: '帮助与反馈', action: handleFeedback },
    { icon: 'ℹ️', label: '关于我们', action: handleAbout }
  ]

  return (
    <View className='profile-page'>
      <View className='page-header'>
        <Text className='page-title'>我的</Text>
      </View>

      <View className='page-content'>
        {/* 用户信息卡片 */}
        <View className='user-card'>
          <View className='user-avatar'>
            <Text className='avatar-icon'>👤</Text>
          </View>
          <View className='user-info'>
            <Text className='user-name'>游客用户</Text>
            <Text className='user-desc'>登录后可同步历史记录</Text>
          </View>
        </View>

        {/* 功能菜单 */}
        <View className='menu-section'>
          {menuItems.map((item, index) => (
            <View
              key={index}
              className='menu-item'
              onClick={item.action || (() => {})}
            >
              <View className='menu-left'>
                <Text className='menu-icon'>{item.icon}</Text>
                <Text className='menu-label'>{item.label}</Text>
              </View>
              <View className='menu-arrow'>
                <Text className='arrow-icon'>›</Text>
              </View>
            </View>
          ))}
        </View>

        {/* 版本信息 */}
        <View className='version-section'>
          <Text className='version-text'>v1.0.0</Text>
          <Text className='version-hint'>每日Stock 分析助手</Text>
        </View>
      </View>
    </View>
  )
}

export default ProfilePage
