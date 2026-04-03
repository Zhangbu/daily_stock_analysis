# 每日股票分析 - 微信小程序

基于 Taro 框架开发的跨平台小程序，支持微信、支付宝、字节等平台。

## 目录结构

```
apps/dsa-mini/
├── src/
│   ├── pages/           # 页面目录
│   │   ├── index/       # 启动页（重定向到首页）
│   │   ├── home/        # 首页（股票分析输入 + 历史列表）
│   │   ├── history/     # 历史记录页
│   │   ├── report/      # 报告详情页
│   │   ├── tasks/       # 任务列表页
│   │   ├── profile/     # 个人中心页
│   │   ├── chat/        # AI 对话页
│   │   └── about/       # 关于我们页
│   ├── components/      # 公共组件
│   │   ├── HistoryList  # 历史列表组件
│   │   └── TaskPanel    # 任务面板组件
│   ├── services/        # API 服务层
│   │   └── api.ts       # API 接口定义
│   ├── store/           # 状态管理
│   │   └── analysisStore.ts  # 分析状态管理
│   ├── assets/          # 静态资源
│   │   └── icons/       # TabBar 图标
│   ├── app.config.ts    # 应用配置
│   ├── app.tsx          # 应用入口
│   └── app.scss         # 全局样式
├── package.json
├── project.config.json  # 项目配置
└── tsconfig.json        # TypeScript 配置
```

## 功能特性

### 首页
- 股票代码输入框（支持 A 股、港股、美股）
- 一键提交分析任务
- 历史记录列表展示
- 任务进度实时显示

### 历史记录
- 按时间倒序展示分析历史
- 支持筛选（全部/自选/推荐）
- 下拉刷新、上拉加载更多
- 情感分数可视化指示条

### 报告详情
- 股票基本信息展示
- 情感评分环形图（0-100 分）
- 操作建议、趋势预测
- 策略点位（理想买入、次优买入、止损位、目标位）
- 追问 AI 功能入口

### 任务管理
- 实时任务状态更新
- 进度条显示
- 失败任务重试
- 已完成任务查看报告

### AI 对话
- 与分析报告关联的问答功能
- 实时对话交互

## 技术栈

- **框架**: Taro 3.6.30
- **UI**: React 18
- **语言**: TypeScript
- **状态管理**: MobX
- **HTTP 请求**: Taro.request
- **样式**: SCSS

## 开发指南

### 环境准备

```bash
# 安装依赖
npm install

# 或使用 yarn
yarn install
```

### 开发模式

```bash
# 微信小程序
npm run dev:weapp

# H5
npm run dev:h5

# 支付宝小程序
npm run dev:alipay
```

### 构建

```bash
# 微信小程序
npm run build:weapp

# H5
npm run build:h5
```

## 配置

### API 地址配置

在 `project.config.json` 或环境变量中配置 API 基础地址：

```json
{
  "API_BASE_URL": "https://your-api-domain.com"
}
```

默认地址：`http://localhost:8000`

### 小程序 AppID 配置

在 `project.config.json` 中修改 `appid` 为你的小程序 AppID。

## 页面路由

| 路由 | 页面 | 说明 |
|------|------|------|
| /pages/index/index | 启动页 | 自动重定向到首页 |
| /pages/home/home | 首页 | 股票分析主页面 |
| /pages/history/history | 历史 | 分析历史记录 |
| /pages/report/report?id= | 报告 | 报告详情 |
| /pages/tasks/tasks | 任务 | 任务列表 |
| /pages/profile/profile | 我的 | 个人中心 |
| /pages/chat/chat?stock=&name=&recordId= | 对话 | AI 问答 |
| /pages/about/about | 关于 | 应用信息 |

## API 接口

### 历史记录
- `GET /api/v1/history` - 获取历史列表
- `GET /api/v1/history/:id` - 获取报告详情

### 股票分析
- `POST /api/v1/analysis/analyze` - 提交分析任务

### 任务管理
- `GET /api/v1/tasks` - 获取任务列表

### AI 对话
- `POST /api/v1/chat` - 发送对话消息

## 注意事项

1. **图标资源**: TabBar 需要图标资源，请确保 `assets/icons/` 目录下有对应的图标文件
2. **AppID**: 部署前请修改 `project.config.json` 中的 `appid`
3. **域名配置**: 在微信小程序后台配置合法的服务器域名
4. **HTTPS**: 生产环境请使用 HTTPS 协议

## 版本历史

- v1.0.0 (2026-04-01) - 初始版本
  - 首页股票分析功能
  - 历史记录查看
  - 报告详情展示
  - 任务进度跟踪
  - AI 对话功能
