import type React from 'react';
import { useRef, useCallback, useEffect, useState } from 'react';
import type { HistoryItem } from '../../types/analysis';
import { getSentimentColor } from '../../types/analysis';
import { formatDateTime, formatChangePct, getChangePctColor } from '../../utils/format';

type SourceFilter = 'all' | 'manual' | 'smart_selection';

interface HistoryListProps {
  items: HistoryItem[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  selectedId?: number;  // Selected history record ID
  onItemClick: (recordId: number) => void;  // Callback with record ID
  onLoadMore: () => void;
  className?: string;
  manualCount?: number;  // 手动选股数量
  smartCount?: number;  // 智能选股数量
}

/**
 * 历史记录列表组件
 * 显示最近的股票分析历史，支持点击查看详情和滚动加载更多
 */
export const HistoryList: React.FC<HistoryListProps> = ({
  items,
  isLoading,
  isLoadingMore,
  hasMore,
  selectedId,
  onItemClick,
  onLoadMore,
  className = '',
  manualCount,
  smartCount,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');

  // 根据筛选条件过滤历史项
  const filteredItems = items.filter(item => {
    if (sourceFilter === 'all') return true;
    if (sourceFilter === 'manual') return !item.source || item.source === 'manual';
    if (sourceFilter === 'smart_selection') return item.source === 'smart_selection';
    return true;
  });

  // 计算手动和智能选股数量（仅当未传入时）
  const computedManualCount = manualCount ?? items.filter(i => !i.source || i.source === 'manual').length;
  const computedSmartCount = smartCount ?? items.filter(i => i.source === 'smart_selection').length;

  // 使用 IntersectionObserver 检测滚动到底部
  const handleObserver = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const target = entries[0];
      // 只有当触发器真正可见且有更多数据时才加载
      if (target.isIntersecting && hasMore && !isLoading && !isLoadingMore) {
        // 确保容器有滚动能力（内容超过容器高度）
        const container = scrollContainerRef.current;
        if (container && container.scrollHeight > container.clientHeight) {
          onLoadMore();
        }
      }
    },
    [hasMore, isLoading, isLoadingMore, onLoadMore, sourceFilter]
  );

  useEffect(() => {
    const trigger = loadMoreTriggerRef.current;
    const container = scrollContainerRef.current;
    if (!trigger || !container) return;

    const observer = new IntersectionObserver(handleObserver, {
      root: container,
      rootMargin: '20px', // 减小预加载距离
      threshold: 0.1, // 触发器至少 10% 可见时才触发
    });

    observer.observe(trigger);

    return () => {
      observer.disconnect();
    };
  }, [handleObserver]);

  return (
    <aside className={`glass-card overflow-hidden flex flex-col ${className}`}>
      <div ref={scrollContainerRef} className="p-3 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-medium text-purple uppercase tracking-wider flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            历史记录
          </h2>
        </div>

        {/* 来源筛选标签页 */}
        <div className="flex gap-1 mb-3 pb-2 border-b border-white/5">
          <button
            type="button"
            onClick={() => setSourceFilter('all')}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              sourceFilter === 'all'
                ? 'bg-purple/20 text-purple border border-purple/30'
                : 'text-muted hover:text-white hover:bg-white/5'
            }`}
          >
            全部 ({items.length})
          </button>
          <button
            type="button"
            onClick={() => setSourceFilter('manual')}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              sourceFilter === 'manual'
                ? 'bg-cyan/20 text-cyan border border-cyan/30'
                : 'text-muted hover:text-white hover:bg-white/5'
            }`}
          >
            自选 ({computedManualCount})
          </button>
          <button
            type="button"
            onClick={() => setSourceFilter('smart_selection')}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              sourceFilter === 'smart_selection'
                ? 'bg-amber/20 text-amber border border-amber/30'
                : 'text-muted hover:text-white hover:bg-white/5'
            }`}
          >
            推荐 ({computedSmartCount})
          </button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-6">
            <div className="w-5 h-5 border-2 border-cyan/20 border-t-cyan rounded-full animate-spin" />
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-10 h-10 mb-3 rounded-xl bg-white/5 flex items-center justify-center mx-auto">
              <svg className="w-5 h-5 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm text-muted mb-1">
              {items.length === 0
                ? '暂无历史记录'
                : sourceFilter === 'manual'
                  ? '暂无自选股记录'
                  : sourceFilter === 'smart_selection'
                    ? '暂无推荐股记录'
                    : '该分类下暂无记录'}
            </p>
            {items.length === 0 && (
              <p className="text-xs text-muted/70">
                在上方输入股票代码开始分析
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-1.5">
            {filteredItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onItemClick(item.id)}
                className={`history-item w-full text-left ${selectedId === item.id ? 'active' : ''
                  }`}
              >
                <div className="flex items-center gap-2 w-full">
                  {/* 情感分数指示条 */}
                  {item.sentimentScore !== undefined && (
                    <span
                      className="w-0.5 h-8 rounded-full flex-shrink-0"
                      style={{
                        backgroundColor: getSentimentColor(item.sentimentScore),
                        boxShadow: `0 0 6px ${getSentimentColor(item.sentimentScore)}40`
                      }}
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1.5">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="font-medium text-white truncate text-xs">
                          {item.stockName || item.stockCode}
                        </span>
                        {/* 智能选股标识 */}
                        {item.source === 'smart_selection' && (
                          <span className="flex-shrink-0 px-1 py-0.5 text-[10px] rounded bg-amber/20 text-amber border border-amber/30 font-medium">
                            荐
                          </span>
                        )}
                      </div>
                      {item.sentimentScore !== undefined && (
                        <span
                          className="text-xs font-mono font-semibold px-1 py-0.5 rounded"
                          style={{
                            color: getSentimentColor(item.sentimentScore),
                            backgroundColor: `${getSentimentColor(item.sentimentScore)}15`
                          }}
                        >
                          {item.sentimentScore}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-xs text-muted font-mono">
                        {item.stockCode}
                      </span>
                      <span className="text-xs text-muted/50">·</span>
                      <span className="text-xs text-muted">
                        {formatDateTime(item.createdAt)}
                      </span>
                      {/* 涨跌幅显示 */}
                      {item.changePct !== undefined && (
                        <>
                          <span className="text-xs text-muted/50">·</span>
                          <span
                            className="text-xs font-mono font-medium"
                            style={{ color: getChangePctColor(item.changePct) }}
                          >
                            {formatChangePct(item.changePct)}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            ))}

            {/* 加载更多触发器 */}
            <div ref={loadMoreTriggerRef} className="h-4" />

            {/* 加载更多状态 */}
            {isLoadingMore && (
              <div className="flex justify-center py-3">
                <div className="w-4 h-4 border-2 border-cyan/20 border-t-cyan rounded-full animate-spin" />
              </div>
            )}

            {/* 没有更多数据提示 */}
            {!hasMore && filteredItems.length > 0 && (
              <div className="text-center py-2 text-muted/50 text-xs">
                {sourceFilter === 'all' ? '已加载全部' : '当前分类下已加载全部'}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
