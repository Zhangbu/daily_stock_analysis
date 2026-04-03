pages: [
  'pages/index/index',
  'pages/home/home',
  'pages/analysis/analysis',
  'pages/history/history',
  'pages/report/report',
  'pages/tasks/tasks',
  'pages/profile/profile',
  'pages/chat/chat',
  'pages/about/about'
],
window: {
  backgroundTextStyle: 'dark',
  navigationBarBackgroundColor: '#6B57FF',
  navigationBarTitleText: '股票智能分析',
  navigationBarTextStyle: 'white',
  backgroundColor: '#f5f5f5'
},
tabBar: {
  color: '#999999',
  selectedColor: '#6B57FF',
  backgroundColor: '#ffffff',
  borderStyle: 'black',
  list: [
    {
      pagePath: 'pages/home/home',
      text: '首页',
      iconPath: 'src/assets/icons/home.png',
      selectedIconPath: 'src/assets/icons/home-active.png'
    },
    {
      pagePath: 'pages/history/history',
      text: '历史',
      iconPath: 'src/assets/icons/history.png',
      selectedIconPath: 'src/assets/icons/history-active.png'
    },
    {
      pagePath: 'pages/tasks/tasks',
      text: '任务',
      iconPath: 'src/assets/icons/task.png',
      selectedIconPath: 'src/assets/icons/task-active.png'
    },
    {
      pagePath: 'pages/profile/profile',
      text: '我的',
      iconPath: 'src/assets/icons/profile.png',
      selectedIconPath: 'src/assets/icons/profile-active.png'
    }
  ]
},
sitemapLocation: 'sitemap.json',
styleIsolation: 'apply-single'
