import type { SystemConfigCategory } from '../types/systemConfig';

const categoryTitleMap: Record<SystemConfigCategory, string> = {
  base: '基础设置',
  data_source: '数据源',
  ai_model: 'AI 模型',
  notification: '通知渠道',
  system: '系统设置',
  agent: 'Agent 设置',
  backtest: '回测配置',
  uncategorized: '其他',
};

const categoryDescriptionMap: Partial<Record<SystemConfigCategory, string>> = {
  base: '管理自选股与基础运行参数。',
  data_source: '管理行情数据源与优先级策略。',
  ai_model: '管理模型供应商、模型名称与推理参数。',
  notification: '管理机器人、Webhook 和消息推送配置。',
  system: '管理调度、日志、端口等系统级参数。',
  agent: '管理 Agent 模式、技能与策略配置。',
  backtest: '管理回测开关、评估窗口和引擎参数。',
  uncategorized: '其他未归类的配置项。',
};

const fieldTitleMap: Record<string, string> = {
  STOCK_LIST: '自选股列表',
  US_STOCK_LIST: '美股同步池',
  TUSHARE_TOKEN: 'Tushare Token',
  TAVILY_API_KEYS: 'Tavily API Keys',
  SERPAPI_API_KEYS: 'SerpAPI API Keys',
  BRAVE_API_KEYS: 'Brave API Keys',
  REALTIME_SOURCE_PRIORITY: '实时数据源优先级',
  ENABLE_REALTIME_QUOTE: '启用实时行情',
  ENABLE_REALTIME_TECHNICAL_INDICATORS: '盘中实时技术面',
  ANALYSIS_STALE_DAYS_LIMIT: '行情最大滞后天数',
  GEMINI_API_KEY: 'Gemini API Key',
  GEMINI_MODEL: 'Gemini 模型',
  GEMINI_TEMPERATURE: 'Gemini 温度参数',
  OPENAI_API_KEY: 'OpenAI API Key',
  OPENAI_BASE_URL: 'OpenAI Base URL',
  OPENAI_MODEL: 'OpenAI 模型',
  TELEGRAM_BOT_TOKEN: 'Telegram Bot Token',
  TELEGRAM_CHAT_ID: 'Telegram Chat ID',
  TELEGRAM_MESSAGE_THREAD_ID: 'Telegram Topic ID',
  TELEGRAM_VERIFY_SSL: 'Telegram 证书校验',
  TELEGRAM_CA_BUNDLE: 'Telegram CA 证书路径',
  MARKET_SYNC_ENABLED: '启用市场同步',
  MARKET_SYNC_ON_STARTUP: '启动后自动同步',
  MARKET_SYNC_MARKETS: '同步市场范围',
  MARKET_SYNC_A_SHARE_FULL_ENABLED: '启用 A 股全市场慢同步',
  MARKET_SYNC_HISTORICAL_DAYS: '首次历史回补天数',
  MARKET_SYNC_INCREMENTAL_DAYS: '增量补数窗口',
  MARKET_SYNC_SLEEP_SECONDS: '同步间隔秒数',
  MARKET_SYNC_MAX_CODES_PER_RUN: '单次最多同步股票数',
  WECHAT_WEBHOOK_URL: '企业微信 Webhook',
  DINGTALK_APP_KEY: '钉钉 App Key',
  DINGTALK_APP_SECRET: '钉钉 App Secret',
  PUSHPLUS_TOKEN: 'PushPlus Token',
  REPORT_SUMMARY_ONLY: '仅分析结果摘要',
  SCHEDULE_TIME: '定时任务时间',
  HTTP_PROXY: 'HTTP 代理',
  LOG_LEVEL: '日志级别',
  WEBUI_PORT: 'WebUI 端口',
  AGENT_MODE: '启用 Agent 模式',
  AGENT_MAX_STEPS: 'Agent 最大步数',
  AGENT_SKILLS: 'Agent 激活技能',
  AGENT_STRATEGY_DIR: 'Agent 策略目录',
  BACKTEST_ENABLED: '启用回测',
  BACKTEST_EVAL_WINDOW_DAYS: '回测评估窗口（交易日）',
  BACKTEST_MIN_AGE_DAYS: '回测最小历史天数',
  BACKTEST_ENGINE_VERSION: '回测引擎版本',
  BACKTEST_NEUTRAL_BAND_PCT: '回测中性区间阈值（%）',
};

const fieldDescriptionMap: Record<string, string> = {
  STOCK_LIST: '使用逗号分隔股票代码，例如：600519,300750。',
  US_STOCK_LIST: '额外参与美股同步或筛选的股票池，例如：AAPL,MSFT,NVDA。',
  TUSHARE_TOKEN: '用于接入 Tushare Pro 数据服务的凭据。',
  TAVILY_API_KEYS: '用于新闻检索的 Tavily 密钥，支持逗号分隔多个。',
  SERPAPI_API_KEYS: '用于新闻检索的 SerpAPI 密钥，支持逗号分隔多个。',
  BRAVE_API_KEYS: '用于新闻检索的 Brave Search 密钥，支持逗号分隔多个。',
  REALTIME_SOURCE_PRIORITY: '按逗号分隔填写实时行情调用优先级，例如：tencent,akshare_sina,efinance,akshare_em,yfinance。港股/美股兜底可加入 yfinance。',
  ENABLE_REALTIME_QUOTE: '开启后使用实时行情补充价格、涨跌幅等信息；关闭则只使用历史收盘数据。',
  ENABLE_REALTIME_TECHNICAL_INDICATORS: '盘中分析时用实时价计算 MA5/MA10/MA20 与多头排列（Issue #234）；关闭则用昨日收盘。',
  ANALYSIS_STALE_DAYS_LIMIT: '当最新行情超过该天数未更新时，系统会自动将建议降级为观望。',
  GEMINI_API_KEY: '用于 Gemini 服务调用的密钥。',
  GEMINI_MODEL: '设置 Gemini 分析模型名称。',
  GEMINI_TEMPERATURE: '控制模型输出随机性，范围通常为 0.0 到 2.0。',
  OPENAI_API_KEY: '用于 OpenAI 兼容服务调用的密钥。',
  OPENAI_BASE_URL: 'OpenAI 兼容 API 地址，例如 https://api.deepseek.com/v1。',
  OPENAI_MODEL: 'OpenAI 兼容模型名称，例如 gpt-4o-mini、deepseek-chat。',
  TELEGRAM_BOT_TOKEN: 'Telegram 机器人 Token，可从 @BotFather 获取。',
  TELEGRAM_CHAT_ID: 'Telegram 接收消息的 Chat ID。',
  TELEGRAM_MESSAGE_THREAD_ID: '如果要发到群组话题，可填写 Topic ID。',
  TELEGRAM_VERIFY_SSL: '默认开启。若本机证书链异常，可临时关闭排障，但仅建议在可信环境使用。',
  TELEGRAM_CA_BUNDLE: 'Telegram 专用 CA 证书路径。推荐优先配置它来修复 CERTIFICATE_VERIFY_FAILED。',
  MARKET_SYNC_ENABLED: '启用后台市场日线同步服务，用于补齐本地数据库历史数据。',
  MARKET_SYNC_ON_STARTUP: '服务启动后自动开始后台同步。',
  MARKET_SYNC_MARKETS: '填写需要同步的市场，支持 cn、hk、us，例如：cn,hk,us。',
  MARKET_SYNC_A_SHARE_FULL_ENABLED: '开启后会慢速回补 A 股全市场；关闭时仅同步自选股及配置池。',
  MARKET_SYNC_HISTORICAL_DAYS: '首次同步时回补的历史日线天数。',
  MARKET_SYNC_INCREMENTAL_DAYS: '已有历史数据时，每次补抓的最近窗口天数。',
  MARKET_SYNC_SLEEP_SECONDS: '单只股票同步后的休眠秒数，用于降低被限流风险。',
  MARKET_SYNC_MAX_CODES_PER_RUN: '单次同步最多处理多少只股票，0 表示不限制。',
  WECHAT_WEBHOOK_URL: '企业微信机器人 Webhook 地址。',
  DINGTALK_APP_KEY: '钉钉应用模式 App Key。',
  DINGTALK_APP_SECRET: '钉钉应用模式 App Secret。',
  PUSHPLUS_TOKEN: 'PushPlus 推送令牌。',
  REPORT_SUMMARY_ONLY: '仅推送分析结果摘要，不包含个股详情。多股时适合快速浏览。',
  SCHEDULE_TIME: '每日定时任务执行时间，格式为 HH:MM。',
  HTTP_PROXY: '网络代理地址，可留空。',
  LOG_LEVEL: '设置日志输出级别。',
  WEBUI_PORT: 'Web 页面服务监听端口。',
  AGENT_MODE: '是否启用 ReAct Agent 进行股票分析。',
  AGENT_MAX_STEPS: 'Agent 思考和调用工具的最大步数。',
  AGENT_SKILLS: '逗号分隔的激活技能/策略列表，例如：trend_following,value_investing。',
  AGENT_STRATEGY_DIR: '存放 Agent 策略 YAML 文件的目录路径。',
  BACKTEST_ENABLED: '是否启用回测功能（true/false）。',
  BACKTEST_EVAL_WINDOW_DAYS: '回测评估窗口长度，单位为交易日。',
  BACKTEST_MIN_AGE_DAYS: '仅回测早于该天数的分析记录。',
  BACKTEST_ENGINE_VERSION: '回测引擎版本标识，用于区分结果版本。',
  BACKTEST_NEUTRAL_BAND_PCT: '中性区间阈值百分比，例如 2 表示 -2%~+2%。',
};

const fieldExampleMap: Record<string, string> = {
  STOCK_LIST: '600519,300750,00700.HK',
  US_STOCK_LIST: 'AAPL,MSFT,NVDA',
  REALTIME_SOURCE_PRIORITY: 'tencent,akshare_sina,efinance,akshare_em,yfinance',
  ANALYSIS_STALE_DAYS_LIMIT: '3',
  OPENAI_BASE_URL: 'https://api.deepseek.com/v1',
  OPENAI_MODEL: 'gpt-4o-mini',
  TELEGRAM_CHAT_ID: '-1001234567890',
  TELEGRAM_MESSAGE_THREAD_ID: '88',
  TELEGRAM_VERIFY_SSL: 'true',
  TELEGRAM_CA_BUNDLE: '/home/zjxfun/miniconda3/envs/stock_project/lib/python3.13/site-packages/certifi/cacert.pem',
  MARKET_SYNC_MARKETS: 'cn,hk,us',
  MARKET_SYNC_HISTORICAL_DAYS: '365',
  MARKET_SYNC_INCREMENTAL_DAYS: '30',
  MARKET_SYNC_SLEEP_SECONDS: '0.5',
  MARKET_SYNC_MAX_CODES_PER_RUN: '200',
  SCHEDULE_TIME: '18:30',
  HTTP_PROXY: 'http://127.0.0.1:7890',
  WEBUI_PORT: '8501',
  AGENT_SKILLS: 'trend_following,value_investing',
  BACKTEST_EVAL_WINDOW_DAYS: '20',
  BACKTEST_MIN_AGE_DAYS: '5',
  BACKTEST_NEUTRAL_BAND_PCT: '2',
};

export function getCategoryTitleZh(category: SystemConfigCategory, fallback?: string): string {
  return categoryTitleMap[category] || fallback || category;
}

export function getCategoryDescriptionZh(category: SystemConfigCategory, fallback?: string): string {
  return categoryDescriptionMap[category] || fallback || '';
}

export function getFieldTitleZh(key: string, fallback?: string): string {
  return fieldTitleMap[key] || fallback || key;
}

export function getFieldDescriptionZh(key: string, fallback?: string): string {
  return fieldDescriptionMap[key] || fallback || '';
}

export function getFieldExampleZh(key: string): string {
  return fieldExampleMap[key] || '';
}
