import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  portfolioApi,
} from '../api/portfolio';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import {
  ApiErrorAlert,
  Card,
  Badge,
  ConfirmDialog,
  EmptyState,
  InlineAlert,
  AppPage,
  PageHeader,
} from '../components/common';
import { PortfolioOverview, PortfolioHoldings } from '../components/portfolio';
import { toDateInputValue } from '../utils/format';
import type {
  PortfolioAccountItem,
  PortfolioCashDirection,
  PortfolioCashLedgerListItem,
  PortfolioCorporateActionListItem,
  PortfolioCorporateActionType,
  PortfolioCostMethod,
  PortfolioFxRefreshResponse,
  PortfolioImportBrokerItem,
  PortfolioImportCommitResponse,
  PortfolioImportParseResponse,
  PortfolioPositionItem,
  PortfolioRiskResponse,
  PortfolioSide,
  PortfolioSnapshotResponse,
  PortfolioTradeListItem,
} from '../types/portfolio';

/* ------------------------------------------------------------------ */
/*  Types & Constants                                                 */
/* ------------------------------------------------------------------ */

type AccountOption = 'all' | number;
type EventType = 'trade' | 'cash' | 'corporate';
type TabKey = 'overview' | 'holdings' | 'entry' | 'csv-import' | 'events';

type FlatPosition = PortfolioPositionItem & {
  accountId: number;
  accountName: string;
};

type PendingDelete =
  | { eventType: 'trade'; id: number; message: string }
  | { eventType: 'cash'; id: number; message: string }
  | { eventType: 'corporate'; id: number; message: string };

type FxRefreshFeedback = {
  tone: 'neutral' | 'success' | 'warning';
  text: string;
};

type FxRefreshContext = {
  viewKey: string;
  requestId: number;
};

const DEFAULT_PAGE_SIZE = 20;
const FALLBACK_BROKERS: PortfolioImportBrokerItem[] = [
  { broker: 'huatai', aliases: [], displayName: '华泰' },
  { broker: 'citic', aliases: ['zhongxin'], displayName: '中信' },
  { broker: 'cmb', aliases: ['cmbchina', 'zhaoshang'], displayName: '招商' },
];

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: '概览' },
  { key: 'holdings', label: '持仓明细' },
  { key: 'entry', label: '数据录入' },
  { key: 'csv-import', label: 'CSV导入' },
  { key: 'events', label: '事件流水' },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

const INPUT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const SELECT_CLASS = `${INPUT_CLASS} appearance-none pr-10`;
const FILE_PICKER_CLASS =
  'input-surface input-focus-glow flex h-11 w-full cursor-pointer items-center justify-center rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

function getTodayIso(): string {
  return toDateInputValue(new Date());
}

function formatMoney(value: number | undefined | null, currency = 'CNY'): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${currency} ${Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatSideLabel(value: PortfolioSide): string {
  return value === 'buy' ? '买入' : '卖出';
}

function formatCashDirectionLabel(value: PortfolioCashDirection): string {
  return value === 'in' ? '流入' : '流出';
}

function formatCorporateActionLabel(value: PortfolioCorporateActionType): string {
  return value === 'cash_dividend' ? '现金分红' : '拆并股调整';
}

function formatBrokerLabel(value: string, displayName?: string): string {
  if (displayName && displayName.trim()) return `${value}（${displayName.trim()}）`;
  if (value === 'huatai') return 'huatai（华泰）';
  if (value === 'citic') return 'citic（中信）';
  if (value === 'cmb') return 'cmb（招商）';
  return value;
}

function buildFxRefreshFeedback(data: PortfolioFxRefreshResponse): FxRefreshFeedback {
  if (data.refreshEnabled === false) {
    return { tone: 'neutral', text: '汇率在线刷新已被禁用。' };
  }
  if (data.pairCount === 0) {
    return { tone: 'neutral', text: '当前范围无可刷新的汇率对。' };
  }
  if (data.updatedCount > 0 && data.staleCount === 0 && data.errorCount === 0) {
    return { tone: 'success', text: `汇率已刷新，共更新 ${data.updatedCount} 对。` };
  }
  const summary = `更新 ${data.updatedCount} 对，仍过期 ${data.staleCount} 对，失败 ${data.errorCount} 对。`;
  if (data.staleCount > 0) {
    return { tone: 'warning', text: `已尝试刷新，但仍有部分货币对使用 stale/fallback 汇率。${summary}` };
  }
  return { tone: 'warning', text: `在线刷新未完全成功。${summary}` };
}

/* ------------------------------------------------------------------ */
/*  Tab: Overview                                                     */
/* ------------------------------------------------------------------ */

type OverviewTabProps = {
  snapshot: PortfolioSnapshotResponse | null;
  risk: PortfolioRiskResponse | null;
  isLoading: boolean;
  hasAccounts: boolean;
};

const OverviewTab: React.FC<OverviewTabProps> = ({ snapshot, risk, isLoading, hasAccounts }) => {
  if (isLoading) {
    return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" /></div>;
  }
  if (!hasAccounts) return null;
  if (!snapshot) return <EmptyState title="暂无持仓数据" description="创建账户并录入交易后，这里将展示概览。" />;
  return <PortfolioOverview snapshot={snapshot} risk={risk} />;
};

/* ------------------------------------------------------------------ */
/*  Tab: Holdings                                                     */
/* ------------------------------------------------------------------ */

type HoldingsTabProps = {
  snapshot: PortfolioSnapshotResponse | null;
  risk: PortfolioRiskResponse | null;
  isLoading: boolean;
  hasAccounts: boolean;
};

const HoldingsTab: React.FC<HoldingsTabProps> = ({ snapshot, risk, isLoading, hasAccounts }) => {
  if (isLoading) {
    return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-2xl border-2 border-cyan/20 border-t-cyan" /></div>;
  }
  if (!hasAccounts) return null;
  if (!snapshot) return <EmptyState title="暂无持仓数据" description="创建账户并录入交易后，这里将展示持仓明细。" />;
  return <PortfolioHoldings snapshot={snapshot} risk={risk} />;
};

/* ------------------------------------------------------------------ */
/*  Main Page                                                         */
/* ------------------------------------------------------------------ */

const PortfolioPage: React.FC = () => {
  useEffect(() => {
    document.title = '持仓管理 - DSA';
  }, []);

  /* ---- active tab ---- */
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  /* ---- shared account / snapshot state ---- */
  const [accounts, setAccounts] = useState<PortfolioAccountItem[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<AccountOption>('all');
  const [showCreateAccount, setShowCreateAccount] = useState(false);
  const [accountCreating, setAccountCreating] = useState(false);
  const [accountCreateError, setAccountCreateError] = useState<string | null>(null);
  const [accountCreateSuccess, setAccountCreateSuccess] = useState<string | null>(null);
  const [accountForm, setAccountForm] = useState({
    name: '',
    broker: 'Demo',
    market: 'cn' as 'cn' | 'hk' | 'us',
    baseCurrency: 'CNY',
  });
  const [costMethod, setCostMethod] = useState<PortfolioCostMethod>('fifo');
  const [snapshot, setSnapshot] = useState<PortfolioSnapshotResponse | null>(null);
  const [risk, setRisk] = useState<PortfolioRiskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [riskWarning, setRiskWarning] = useState<string | null>(null);
  const [writeWarning, setWriteWarning] = useState<string | null>(null);

  /* ---- FX refresh ---- */
  const [fxRefreshing, setFxRefreshing] = useState(false);
  const [fxRefreshFeedback, setFxRefreshFeedback] = useState<FxRefreshFeedback | null>(null);
  const refreshContextRef = useRef<FxRefreshContext>({ viewKey: '', requestId: 0 });

  /* ---- CSV import state ---- */
  const [brokers, setBrokers] = useState<PortfolioImportBrokerItem[]>([]);
  const [selectedBroker, setSelectedBroker] = useState('huatai');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvDryRun, setCsvDryRun] = useState(true);
  const [csvParsing, setCsvParsing] = useState(false);
  const [csvCommitting, setCsvCommitting] = useState(false);
  const [csvParseResult, setCsvParseResult] = useState<PortfolioImportParseResponse | null>(null);
  const [csvCommitResult, setCsvCommitResult] = useState<PortfolioImportCommitResponse | null>(null);
  const [brokerLoadWarning, setBrokerLoadWarning] = useState<string | null>(null);

  /* ---- Event state ---- */
  const [eventType, setEventType] = useState<EventType>('trade');
  const [eventDateFrom, setEventDateFrom] = useState('');
  const [eventDateTo, setEventDateTo] = useState('');
  const [eventSymbol, setEventSymbol] = useState('');
  const [eventSide, setEventSide] = useState<'' | PortfolioSide>('');
  const [eventDirection, setEventDirection] = useState<'' | PortfolioCashDirection>('');
  const [eventActionType, setEventActionType] = useState<'' | PortfolioCorporateActionType>('');
  const [eventPage, setEventPage] = useState(1);
  const [eventTotal, setEventTotal] = useState(0);
  const [eventLoading, setEventLoading] = useState(false);
  const [tradeEvents, setTradeEvents] = useState<PortfolioTradeListItem[]>([]);
  const [cashEvents, setCashEvents] = useState<PortfolioCashLedgerListItem[]>([]);
  const [corporateEvents, setCorporateEvents] = useState<PortfolioCorporateActionListItem[]>([]);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  /* ---- Entry form state ---- */
  const [tradeForm, setTradeForm] = useState({
    symbol: '',
    tradeDate: getTodayIso(),
    side: 'buy' as PortfolioSide,
    quantity: '',
    price: '',
    fee: '',
    tax: '',
    tradeUid: '',
    note: '',
  });
  const [cashForm, setCashForm] = useState({
    eventDate: getTodayIso(),
    direction: 'in' as PortfolioCashDirection,
    amount: '',
    currency: '',
    note: '',
  });
  const [corpForm, setCorpForm] = useState({
    symbol: '',
    effectiveDate: getTodayIso(),
    actionType: 'cash_dividend' as PortfolioCorporateActionType,
    cashDividendPerShare: '',
    splitRatio: '',
    note: '',
  });

  /* ---- Derived ---- */
  const queryAccountId = selectedAccount === 'all' ? undefined : selectedAccount;
  const refreshViewKey = `${selectedAccount === 'all' ? 'all' : `account:${selectedAccount}`}:cost:${costMethod}`;
  const hasAccounts = accounts.length > 0;
  const writableAccount = selectedAccount === 'all' ? undefined : accounts.find((item) => item.id === selectedAccount);
  const writableAccountId = writableAccount?.id;
  const writeBlocked = !writableAccountId;
  const totalEventPages = Math.max(1, Math.ceil(eventTotal / DEFAULT_PAGE_SIZE));
  const currentEventCount =
    eventType === 'trade' ? tradeEvents.length
    : eventType === 'cash' ? cashEvents.length
    : corporateEvents.length;

  const isActiveRefreshContext = (requestedViewKey: string, requestedRequestId: number) => (
    refreshContextRef.current.viewKey === requestedViewKey &&
    refreshContextRef.current.requestId === requestedRequestId
  );

  /* ---- Data loading ---- */
  const loadAccounts = useCallback(async () => {
    try {
      const response = await portfolioApi.getAccounts(false);
      const items = response.accounts || [];
      setAccounts(items);
      setSelectedAccount((prev) => {
        if (items.length === 0) return 'all';
        if (prev !== 'all' && !items.some((item) => item.id === prev)) return items[0].id;
        return prev;
      });
      if (items.length === 0) setShowCreateAccount(true);
    } catch (err) {
      setError(getParsedApiError(err));
    }
  }, []);

  const loadBrokers = useCallback(async () => {
    try {
      const response = await portfolioApi.listImportBrokers();
      const brokerItems = response.brokers || [];
      if (brokerItems.length === 0) {
        setBrokers(FALLBACK_BROKERS);
        setBrokerLoadWarning('券商列表接口返回为空，已回退为内置券商列表（华泰/中信/招商）。');
        if (!FALLBACK_BROKERS.some((item) => item.broker === selectedBroker)) {
          setSelectedBroker(FALLBACK_BROKERS[0].broker);
        }
        return;
      }
      setBrokers(brokerItems);
      setBrokerLoadWarning(null);
      if (!brokerItems.some((item) => item.broker === selectedBroker)) {
        setSelectedBroker(brokerItems[0].broker);
      }
    } catch {
      setBrokers(FALLBACK_BROKERS);
      setBrokerLoadWarning('券商列表接口不可用，已回退为内置券商列表（华泰/中信/招商）。');
      if (!FALLBACK_BROKERS.some((item) => item.broker === selectedBroker)) {
        setSelectedBroker(FALLBACK_BROKERS[0].broker);
      }
    }
  }, [selectedBroker]);

  const loadSnapshotAndRisk = useCallback(async () => {
    setIsLoading(true);
    setRiskWarning(null);
    try {
      const snapshotData = await portfolioApi.getSnapshot({
        accountId: queryAccountId,
        costMethod,
      });
      setSnapshot(snapshotData);
      setError(null);

      try {
        const riskData = await portfolioApi.getRisk({
          accountId: queryAccountId,
          costMethod,
        });
        setRisk(riskData);
      } catch (riskErr) {
        setRisk(null);
        const parsed = getParsedApiError(riskErr);
        setRiskWarning(parsed.message || '风险数据获取失败，已降级为仅展示快照数据。');
      }
    } catch (err) {
      setSnapshot(null);
      setRisk(null);
      setError(getParsedApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [queryAccountId, costMethod]);

  const loadEventsPage = useCallback(async (page: number) => {
    setEventLoading(true);
    try {
      if (eventType === 'trade') {
        const response = await portfolioApi.listTrades({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          side: eventSide || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setTradeEvents(response.items || []);
        setEventTotal(response.total || 0);
      } else if (eventType === 'cash') {
        const response = await portfolioApi.listCashLedger({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          direction: eventDirection || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCashEvents(response.items || []);
        setEventTotal(response.total || 0);
      } else {
        const response = await portfolioApi.listCorporateActions({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          actionType: eventActionType || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCorporateEvents(response.items || []);
        setEventTotal(response.total || 0);
      }
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setEventLoading(false);
    }
  }, [eventActionType, eventDateFrom, eventDateTo, eventDirection, eventSide, eventSymbol, eventType, queryAccountId]);

  const loadEvents = useCallback(async () => {
    await loadEventsPage(eventPage);
  }, [eventPage, loadEventsPage]);

  const refreshPortfolioData = useCallback(async (page = eventPage) => {
    await Promise.all([loadSnapshotAndRisk(), loadEventsPage(page)]);
  }, [eventPage, loadEventsPage, loadSnapshotAndRisk]);

  /* ---- Effects ---- */
  useEffect(() => {
    void loadAccounts();
    void loadBrokers();
  }, [loadAccounts, loadBrokers]);

  useEffect(() => {
    void loadSnapshotAndRisk();
  }, [loadSnapshotAndRisk]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    refreshContextRef.current = {
      viewKey: refreshViewKey,
      requestId: refreshContextRef.current.requestId + 1,
    };
    setFxRefreshing(false);
    setFxRefreshFeedback(null);
  }, [refreshViewKey]);

  useEffect(() => {
    setEventPage(1);
  }, [eventType, queryAccountId, eventDateFrom, eventDateTo, eventSymbol, eventSide, eventDirection, eventActionType]);

  useEffect(() => {
    if (!writeBlocked) setWriteWarning(null);
  }, [writeBlocked]);

  /* ---- Handlers ---- */
  const handleRefresh = async () => {
    await Promise.all([loadAccounts(), loadSnapshotAndRisk(), loadEvents(), loadBrokers()]);
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = accountForm.name.trim();
    if (!name) {
      setAccountCreateError('账户名称不能为空。');
      setAccountCreateSuccess(null);
      return;
    }
    try {
      setAccountCreating(true);
      setAccountCreateError(null);
      setAccountCreateSuccess(null);
      const created = await portfolioApi.createAccount({
        name,
        broker: accountForm.broker.trim() || undefined,
        market: accountForm.market,
        baseCurrency: accountForm.baseCurrency.trim() || 'CNY',
      });
      await loadAccounts();
      setSelectedAccount(created.id);
      setShowCreateAccount(false);
      setWriteWarning(null);
      setAccountForm({ name: '', broker: 'Demo', market: accountForm.market, baseCurrency: accountForm.baseCurrency });
      setAccountCreateSuccess('账户创建成功，已自动切换到该账户。');
    } catch (err) {
      const parsed = getParsedApiError(err);
      setAccountCreateError(parsed.message || '创建账户失败，请稍后重试。');
      setAccountCreateSuccess(null);
    } finally {
      setAccountCreating(false);
    }
  };

  const reloadSnapshotAndRiskForScope = useCallback(async (
    requestedViewKey: string,
    requestedRequestId: number,
    requestedAccountId: number | undefined,
    requestedCostMethod: PortfolioCostMethod,
  ): Promise<boolean> => {
    if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) return false;
    setRiskWarning(null);
    try {
      const snapshotData = await portfolioApi.getSnapshot({
        accountId: requestedAccountId, costMethod: requestedCostMethod,
      });
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) return false;
      setSnapshot(snapshotData);
      setError(null);
      try {
        const riskData = await portfolioApi.getRisk({
          accountId: requestedAccountId, costMethod: requestedCostMethod,
        });
        if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) return false;
        setRisk(riskData);
        setRiskWarning(null);
      } catch (riskErr) {
        if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) return false;
        setRisk(null);
        const parsed = getParsedApiError(riskErr);
        setRiskWarning(parsed.message || '风险数据获取失败，已降级为仅展示快照数据。');
      }
      return true;
    } catch (err) {
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) return false;
      setSnapshot(null);
      setRisk(null);
      setError(getParsedApiError(err));
      return false;
    }
  }, []);

  const handleRefreshFx = async () => {
    if (!hasAccounts || isLoading || fxRefreshing) return;
    const requestedViewKey = refreshViewKey;
    const requestedAccountId = queryAccountId;
    const requestedCostMethod = costMethod;
    const requestedRequestId = refreshContextRef.current.requestId + 1;
    refreshContextRef.current = { viewKey: requestedViewKey, requestId: requestedRequestId };
    try {
      setFxRefreshing(true);
      setFxRefreshFeedback(null);
      const result = await portfolioApi.refreshFx({ accountId: requestedAccountId });
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) return;
      const reloaded = await reloadSnapshotAndRiskForScope(
        requestedViewKey, requestedRequestId, requestedAccountId, requestedCostMethod,
      );
      if (!reloaded || !isActiveRefreshContext(requestedViewKey, requestedRequestId)) return;
      setFxRefreshFeedback(buildFxRefreshFeedback(result));
    } catch (err) {
      if (isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        setError(getParsedApiError(err));
      }
    } finally {
      if (isActiveRefreshContext(requestedViewKey, requestedRequestId)) setFxRefreshing(false);
    }
  };

  const handleTradeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) { setWriteWarning('请先选择一个具体账户，再进行录入。'); return; }
    try {
      setWriteWarning(null);
      await portfolioApi.createTrade({
        accountId: writableAccountId, symbol: tradeForm.symbol, tradeDate: tradeForm.tradeDate,
        side: tradeForm.side, quantity: Number(tradeForm.quantity), price: Number(tradeForm.price),
        fee: Number(tradeForm.fee || 0), tax: Number(tradeForm.tax || 0),
        tradeUid: tradeForm.tradeUid || undefined, note: tradeForm.note || undefined,
      });
      await refreshPortfolioData();
      setTradeForm((prev) => ({ ...prev, symbol: '', tradeUid: '', note: '' }));
    } catch (err) { setError(getParsedApiError(err)); }
  };

  const handleCashSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) { setWriteWarning('请先选择一个具体账户，再进行录入。'); return; }
    try {
      setWriteWarning(null);
      await portfolioApi.createCashLedger({
        accountId: writableAccountId, eventDate: cashForm.eventDate,
        direction: cashForm.direction, amount: Number(cashForm.amount),
        currency: cashForm.currency || undefined, note: cashForm.note || undefined,
      });
      await refreshPortfolioData();
      setCashForm((prev) => ({ ...prev, note: '' }));
    } catch (err) { setError(getParsedApiError(err)); }
  };

  const handleCorporateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) { setWriteWarning('请先选择一个具体账户，再进行录入。'); return; }
    try {
      setWriteWarning(null);
      await portfolioApi.createCorporateAction({
        accountId: writableAccountId, symbol: corpForm.symbol, effectiveDate: corpForm.effectiveDate,
        actionType: corpForm.actionType,
        cashDividendPerShare: corpForm.cashDividendPerShare ? Number(corpForm.cashDividendPerShare) : undefined,
        splitRatio: corpForm.splitRatio ? Number(corpForm.splitRatio) : undefined,
        note: corpForm.note || undefined,
      });
      await refreshPortfolioData();
      setCorpForm((prev) => ({ ...prev, symbol: '', note: '' }));
    } catch (err) { setError(getParsedApiError(err)); }
  };

  const handleParseCsv = async () => {
    if (!csvFile) return;
    try {
      setCsvParsing(true);
      const parsed = await portfolioApi.parseCsvImport(selectedBroker, csvFile);
      setCsvParseResult(parsed);
      setCsvCommitResult(null);
    } catch (err) { setError(getParsedApiError(err)); }
    finally { setCsvParsing(false); }
  };

  const handleCommitCsv = async () => {
    if (!csvFile) return;
    if (!writableAccountId) { setWriteWarning('请先选择一个具体账户，再进行导入提交。'); return; }
    try {
      setWriteWarning(null);
      setCsvCommitting(true);
      const committed = await portfolioApi.commitCsvImport(writableAccountId, selectedBroker, csvFile, csvDryRun);
      setCsvCommitResult(committed);
      if (!csvDryRun) await refreshPortfolioData();
    } catch (err) { setError(getParsedApiError(err)); }
    finally { setCsvCommitting(false); }
  };

  const openDeleteDialog = (item: PendingDelete) => {
    if (!writableAccountId) { setWriteWarning('请先选择一个具体账户，再进行删除操作。'); return; }
    setPendingDelete(item);
  };

  const handleConfirmDelete = async () => {
    if (!pendingDelete || deleteLoading) return;
    if (!writableAccountId) { setWriteWarning('请先选择一个具体账户。'); setPendingDelete(null); return; }
    const nextPage = currentEventCount === 1 && eventPage > 1 ? eventPage - 1 : eventPage;
    try {
      setDeleteLoading(true);
      setWriteWarning(null);
      if (pendingDelete.eventType === 'trade') await portfolioApi.deleteTrade(pendingDelete.id);
      else if (pendingDelete.eventType === 'cash') await portfolioApi.deleteCashLedger(pendingDelete.id);
      else await portfolioApi.deleteCorporateAction(pendingDelete.id);
      setPendingDelete(null);
      if (nextPage !== eventPage) setEventPage(nextPage);
      await refreshPortfolioData(nextPage);
    } catch (err) { setError(getParsedApiError(err)); }
    finally { setDeleteLoading(false); }
  };

  /* ---- Render ---- */
  return (
    <AppPage className="space-y-6">
      <PageHeader
        eyebrow="Portfolio"
        title="持仓管理"
        description="组合快照、手工录入、CSV 导入与风险分析，支持全组合/单账户切换。"
        actions={(
          <button type="button" className="btn-secondary text-sm" onClick={() => void handleRefresh()} disabled={isLoading}>
            {isLoading ? '刷新中...' : '刷新数据'}
          </button>
        )}
      />

      {/* ---- Alerts ---- */}
      {error ? <ApiErrorAlert error={error} onDismiss={() => setError(null)} /> : null}
      {riskWarning ? <InlineAlert variant="warning" title="风险模块降级" message={riskWarning} /> : null}
      {writeWarning ? <InlineAlert variant="warning" title="操作提示" message={writeWarning} /> : null}

      {/* ---- Account bar ---- */}
      <div className="rounded-xl border border-border/60 bg-card/40 p-4">
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_220px_auto] gap-3 items-end">
          <div>
            <p className="text-xs text-secondary-text mb-1">账户视图</p>
            <select
              value={String(selectedAccount)}
              onChange={(e) => setSelectedAccount(e.target.value === 'all' ? 'all' : Number(e.target.value))}
              className={SELECT_CLASS}
            >
              <option value="all">全部账户</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} (#{account.id})
                </option>
              ))}
            </select>
          </div>
          <div>
            <p className="text-xs text-secondary-text mb-1">成本口径</p>
            <select
              value={costMethod}
              onChange={(e) => setCostMethod(e.target.value as PortfolioCostMethod)}
              className={SELECT_CLASS}
            >
              <option value="fifo">先进先出（FIFO）</option>
              <option value="avg">均价成本（AVG）</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-secondary text-sm"
              onClick={() => { setShowCreateAccount((prev) => !prev); setAccountCreateError(null); setAccountCreateSuccess(null); }}
            >
              {showCreateAccount ? '收起新建' : '新建账户'}
            </button>
            {hasAccounts ? (
              <>
                {snapshot ? (
                  snapshot.fxStale ? (
                    <Badge variant="warning">过期</Badge>
                  ) : (
                    <Badge variant="success">最新</Badge>
                  )
                ) : null}
                <button
                  type="button"
                  className="btn-secondary text-sm"
                  onClick={() => void handleRefreshFx()}
                  disabled={!hasAccounts || isLoading || fxRefreshing}
                >
                  {fxRefreshing ? '刷新中...' : '刷新汇率'}
                </button>
              </>
            ) : null}
          </div>
        </div>

        {/* FX refresh feedback */}
        {fxRefreshFeedback ? (
          <InlineAlert
            variant={fxRefreshFeedback.tone === 'success' ? 'success' : fxRefreshFeedback.tone === 'warning' ? 'warning' : 'info'}
            title="汇率刷新结果"
            message={fxRefreshFeedback.text}
            className="mt-3 rounded-xl px-3 py-2 text-xs shadow-none"
          />
        ) : null}
      </div>

      {/* ---- Create account ---- */}
      {(showCreateAccount || !hasAccounts) ? (
        <Card padding="md">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-foreground">新建账户</h2>
            {hasAccounts ? (
              <button type="button" className="btn-secondary text-xs px-3 py-1" onClick={() => { setShowCreateAccount(false); setAccountCreateError(null); setAccountCreateSuccess(null); }}>
                收起
              </button>
            ) : <span className="text-xs text-secondary-text">创建后自动切换到该账户</span>}
          </div>
          {accountCreateError ? <InlineAlert variant="danger" title="创建账户失败" message={accountCreateError} className="mt-2" /> : null}
          {accountCreateSuccess ? <InlineAlert variant="success" title="创建账户成功" message={accountCreateSuccess} className="mt-2" /> : null}
          <form className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2" onSubmit={handleCreateAccount}>
            <input className={`${INPUT_CLASS} md:col-span-2`} placeholder="账户名称（必填）" value={accountForm.name}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, name: e.target.value }))} />
            <input className={INPUT_CLASS} placeholder="券商（可选，如 Demo/华泰）" value={accountForm.broker}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, broker: e.target.value }))} />
            <input className={INPUT_CLASS} placeholder="基准币（如 CNY/USD/HKD）" value={accountForm.baseCurrency}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, baseCurrency: e.target.value.toUpperCase() }))} />
            <select className={SELECT_CLASS} value={accountForm.market}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, market: e.target.value as 'cn' | 'hk' | 'us' }))}>
              <option value="cn">A 股（cn）</option>
              <option value="hk">港股（hk）</option>
              <option value="us">美股（us）</option>
            </select>
            <button type="submit" className="btn-secondary text-sm" disabled={accountCreating}>
              {accountCreating ? '创建中...' : '创建账户'}
            </button>
          </form>
        </Card>
      ) : null}

      {/* ---- Tabs ---- */}
      <div className="border-b border-border/60">
        <nav className="flex gap-1 overflow-x-auto" role="tablist">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              role="tab"
              aria-selected={activeTab === key}
              onClick={() => setActiveTab(key)}
              className={`relative px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === key
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-secondary-text hover:text-foreground'
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* ---- Tab panels ---- */}
      <div role="tabpanel">
        {activeTab === 'overview' ? (
          <OverviewTab snapshot={snapshot} risk={risk} isLoading={isLoading} hasAccounts={hasAccounts} />
        ) : activeTab === 'holdings' ? (
          <HoldingsTab snapshot={snapshot} risk={risk} isLoading={isLoading} hasAccounts={hasAccounts} />
        ) : activeTab === 'entry' ? (
          /* ---- 数据录入 ---- */
          !hasAccounts ? (
            <InlineAlert variant="info" message="请先创建账户后再录入交易。" />
          ) : (
            <>
              {writeBlocked && hasAccounts ? (
                <InlineAlert variant="warning" className="mb-4" message={'当前为“全部账户”视图。请先选择一个具体账户后再进行手工录入。'} />
              ) : null}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Trade entry */}
                <Card padding="md">
                  <h3 className="text-sm font-semibold text-foreground mb-3">交易</h3>
                  <form className="space-y-2" onSubmit={handleTradeSubmit}>
                    <input className={INPUT_CLASS} placeholder="股票代码" value={tradeForm.symbol}
                      onChange={(e) => setTradeForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
                    <div className="grid grid-cols-2 gap-2">
                      <input className={INPUT_CLASS} type="date" value={tradeForm.tradeDate}
                        onChange={(e) => setTradeForm((prev) => ({ ...prev, tradeDate: e.target.value }))} required />
                      <select className={SELECT_CLASS} value={tradeForm.side}
                        onChange={(e) => setTradeForm((prev) => ({ ...prev, side: e.target.value as PortfolioSide }))}>
                        <option value="buy">买入</option>
                        <option value="sell">卖出</option>
                      </select>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <input className={INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="数量" value={tradeForm.quantity}
                        onChange={(e) => setTradeForm((prev) => ({ ...prev, quantity: e.target.value }))} required />
                      <input className={INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="成交价" value={tradeForm.price}
                        onChange={(e) => setTradeForm((prev) => ({ ...prev, price: e.target.value }))} required />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <input className={INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="手续费" value={tradeForm.fee}
                        onChange={(e) => setTradeForm((prev) => ({ ...prev, fee: e.target.value }))} />
                      <input className={INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="税费" value={tradeForm.tax}
                        onChange={(e) => setTradeForm((prev) => ({ ...prev, tax: e.target.value }))} />
                    </div>
                    <p className="text-xs text-secondary-text">手续费和税费可留空。</p>
                    <button type="submit" className="btn-secondary w-full" disabled={!writableAccountId}>提交交易</button>
                  </form>
                </Card>

                {/* Cash entry */}
                <Card padding="md">
                  <h3 className="text-sm font-semibold text-foreground mb-3">资金流水</h3>
                  <form className="space-y-2" onSubmit={handleCashSubmit}>
                    <div className="grid grid-cols-2 gap-2">
                      <input className={INPUT_CLASS} type="date" value={cashForm.eventDate}
                        onChange={(e) => setCashForm((prev) => ({ ...prev, eventDate: e.target.value }))} required />
                      <select className={SELECT_CLASS} value={cashForm.direction}
                        onChange={(e) => setCashForm((prev) => ({ ...prev, direction: e.target.value as PortfolioCashDirection }))}>
                        <option value="in">流入</option>
                        <option value="out">流出</option>
                      </select>
                    </div>
                    <input className={INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="金额" value={cashForm.amount}
                      onChange={(e) => setCashForm((prev) => ({ ...prev, amount: e.target.value }))} required />
                    <input className={INPUT_CLASS} placeholder={`币种（可选，默认 ${writableAccount?.baseCurrency || 'CNY'}）`}
                      value={cashForm.currency} onChange={(e) => setCashForm((prev) => ({ ...prev, currency: e.target.value }))} />
                    <button type="submit" className="btn-secondary w-full" disabled={!writableAccountId}>提交资金流水</button>
                  </form>
                </Card>

                {/* Corporate action entry */}
                <Card padding="md">
                  <h3 className="text-sm font-semibold text-foreground mb-3">公司行为</h3>
                  <form className="space-y-2" onSubmit={handleCorporateSubmit}>
                    <input className={INPUT_CLASS} placeholder="股票代码" value={corpForm.symbol}
                      onChange={(e) => setCorpForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
                    <div className="grid grid-cols-2 gap-2">
                      <input className={INPUT_CLASS} type="date" value={corpForm.effectiveDate}
                        onChange={(e) => setCorpForm((prev) => ({ ...prev, effectiveDate: e.target.value }))} required />
                      <select className={SELECT_CLASS} value={corpForm.actionType}
                        onChange={(e) => setCorpForm((prev) => ({ ...prev, actionType: e.target.value as PortfolioCorporateActionType }))}>
                        <option value="cash_dividend">现金分红</option>
                        <option value="split_adjustment">拆并股调整</option>
                      </select>
                    </div>
                    {corpForm.actionType === 'cash_dividend' ? (
                      <input className={INPUT_CLASS} type="number" min="0" step="0.000001" placeholder="每股分红" value={corpForm.cashDividendPerShare}
                        onChange={(e) => setCorpForm((prev) => ({ ...prev, cashDividendPerShare: e.target.value, splitRatio: '' }))} required />
                    ) : (
                      <input className={INPUT_CLASS} type="number" min="0" step="0.000001" placeholder="拆并股比例" value={corpForm.splitRatio}
                        onChange={(e) => setCorpForm((prev) => ({ ...prev, splitRatio: e.target.value, cashDividendPerShare: '' }))} required />
                    )}
                    <button type="submit" className="btn-secondary w-full" disabled={!writableAccountId}>提交</button>
                  </form>
                </Card>
              </div>
            </>
          )
        ) : activeTab === 'csv-import' ? (
          /* ---- CSV导入 ---- */
          <Card padding="md">
            <h3 className="text-sm font-semibold text-foreground mb-3">券商 CSV 导入</h3>
            <div className="space-y-3 max-w-xl">
              {brokerLoadWarning ? (
                <InlineAlert variant="warning" className="rounded-lg px-2 py-1 text-xs shadow-none" message={brokerLoadWarning} />
              ) : null}
              {writeBlocked && hasAccounts ? (
                <InlineAlert variant="warning" className="rounded-lg px-2 py-1 text-xs shadow-none" message="请先选择一个具体账户后再提交导入。" />
              ) : null}
              <div className="grid grid-cols-2 gap-2">
                <select className={SELECT_CLASS} value={selectedBroker} onChange={(e) => setSelectedBroker(e.target.value)}>
                  {brokers.map((item) => (
                    <option key={item.broker} value={item.broker}>{formatBrokerLabel(item.broker, item.displayName)}</option>
                  ))}
                </select>
                <label className={FILE_PICKER_CLASS}>
                  选择 CSV
                  <input type="file" accept=".csv" className="hidden"
                    onChange={(e) => setCsvFile(e.target.files?.[0] || null)} />
                </label>
              </div>
              <label className="flex items-center gap-2 text-xs text-secondary-text cursor-pointer">
                <input type="checkbox" checked={csvDryRun} onChange={(e) => setCsvDryRun(e.target.checked)} className="h-3.5 w-3.5 rounded border-border accent-primary" />
                仅预演（不写入）
              </label>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary flex-1" disabled={!csvFile || csvParsing} onClick={() => void handleParseCsv()}>
                  {csvParsing ? '解析中...' : '解析文件'}
                </button>
                <button type="button" className="btn-secondary flex-1" disabled={!csvFile || !writableAccountId || csvCommitting}
                  onClick={() => void handleCommitCsv()}>
                  {csvCommitting ? '提交中...' : '提交导入'}
                </button>
              </div>
              {csvParseResult ? (
                <InlineAlert
                  variant={csvParseResult.errorCount > 0 || csvParseResult.skippedCount > 0 ? 'warning' : 'info'}
                  title="CSV 解析结果"
                  message={`有效 ${csvParseResult.recordCount} 条，跳过 ${csvParseResult.skippedCount} 条，错误 ${csvParseResult.errorCount} 条。`}
                  className="rounded-lg px-3 py-2 text-xs shadow-none"
                />
              ) : null}
              {csvCommitResult ? (
                <InlineAlert
                  variant={csvCommitResult.failedCount > 0 || csvCommitResult.duplicateCount > 0 ? 'warning' : 'success'}
                  title={csvDryRun ? 'CSV 预演结果' : 'CSV 提交结果'}
                  message={`${csvDryRun ? '预演' : '写入'}：写入 ${csvCommitResult.insertedCount} 条，重复 ${csvCommitResult.duplicateCount} 条，失败 ${csvCommitResult.failedCount} 条。`}
                  className="rounded-lg px-3 py-2 text-xs shadow-none"
                />
              ) : null}
            </div>
          </Card>
        ) : (
          /* ---- 事件流水 ---- */
          <Card padding="md">
            <h3 className="text-sm font-semibold text-foreground mb-3">事件记录</h3>
            <div className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <select className={SELECT_CLASS} value={eventType} onChange={(e) => setEventType(e.target.value as EventType)}>
                  <option value="trade">交易流水</option>
                  <option value="cash">资金流水</option>
                  <option value="corporate">公司行为</option>
                </select>
                <input className={INPUT_CLASS} type="date" value={eventDateFrom} onChange={(e) => setEventDateFrom(e.target.value)} placeholder="开始日期" />
                <input className={INPUT_CLASS} type="date" value={eventDateTo} onChange={(e) => setEventDateTo(e.target.value)} placeholder="结束日期" />
                <button type="button" className="btn-secondary text-sm" onClick={() => void loadEvents()} disabled={eventLoading}>
                  {eventLoading ? '加载中...' : '刷新'}
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {(eventType === 'trade' || eventType === 'corporate') ? (
                  <input className={INPUT_CLASS} placeholder="按代码筛选" value={eventSymbol}
                    onChange={(e) => setEventSymbol(e.target.value)} />
                ) : <div />}
                {eventType === 'trade' ? (
                  <select className={SELECT_CLASS} value={eventSide} onChange={(e) => setEventSide(e.target.value as '' | PortfolioSide)}>
                    <option value="">全部方向</option><option value="buy">买入</option><option value="sell">卖出</option>
                  </select>
                ) : null}
                {eventType === 'cash' ? (
                  <select className={SELECT_CLASS} value={eventDirection} onChange={(e) => setEventDirection(e.target.value as '' | PortfolioCashDirection)}>
                    <option value="">全部方向</option><option value="in">流入</option><option value="out">流出</option>
                  </select>
                ) : null}
                {eventType === 'corporate' ? (
                  <select className={SELECT_CLASS} value={eventActionType} onChange={(e) => setEventActionType(e.target.value as '' | PortfolioCorporateActionType)}>
                    <option value="">全部类型</option><option value="cash_dividend">现金分红</option><option value="split_adjustment">拆并股调整</option>
                  </select>
                ) : null}
              </div>

              <div className="text-xs text-secondary-text">
                {writeBlocked ? '删除操作请在单账户视图下进行。' : '如有错误流水，可直接删除后重新录入。'}
              </div>

              {/* Event list */}
              <div className="max-h-80 overflow-auto rounded-lg border border-border/60 p-2">
                {eventType === 'trade' && tradeEvents.map((item) => (
                  <div key={`t-${item.id}`} className="flex items-start justify-between gap-3 border-b border-border/40 py-2 text-xs text-secondary-text">
                    <span>{item.tradeDate} {formatSideLabel(item.side)} {item.symbol} 数量={item.quantity} 价格={item.price}</span>
                    {!writeBlocked ? (
                      <button type="button" className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                        onClick={() => openDeleteDialog({ eventType: 'trade', id: item.id, message: `确认删除 ${item.tradeDate} 的${formatSideLabel(item.side)}流水 ${item.symbol}？` })}>
                        删除
                      </button>
                    ) : null}
                  </div>
                ))}
                {eventType === 'cash' && cashEvents.map((item) => (
                  <div key={`c-${item.id}`} className="flex items-start justify-between gap-3 border-b border-border/40 py-2 text-xs text-secondary-text">
                    <span>{item.eventDate} {formatCashDirectionLabel(item.direction)} {item.amount} {item.currency}</span>
                    {!writeBlocked ? (
                      <button type="button" className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                        onClick={() => openDeleteDialog({ eventType: 'cash', id: item.id, message: `确认删除 ${item.eventDate} 的资金流水？` })}>
                        删除
                      </button>
                    ) : null}
                  </div>
                ))}
                {eventType === 'corporate' && corporateEvents.map((item) => (
                  <div key={`ca-${item.id}`} className="flex items-start justify-between gap-3 border-b border-border/40 py-2 text-xs text-secondary-text">
                    <span>{item.effectiveDate} {formatCorporateActionLabel(item.actionType)} {item.symbol}</span>
                    {!writeBlocked ? (
                      <button type="button" className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                        onClick={() => openDeleteDialog({ eventType: 'corporate', id: item.id, message: `确认删除 ${item.effectiveDate} 的公司行为 ${item.symbol}？` })}>
                        删除
                      </button>
                    ) : null}
                  </div>
                ))}
                {!eventLoading && (
                  (eventType === 'trade' && tradeEvents.length === 0) ||
                  (eventType === 'cash' && cashEvents.length === 0) ||
                  (eventType === 'corporate' && corporateEvents.length === 0)
                ) ? (
                  <EmptyState title="暂无流水" description="调整筛选条件或先录入一笔交易。" className="border-none bg-transparent px-3 py-6 shadow-none" />
                ) : null}
                {eventLoading ? (
                  <div className="flex justify-center py-8">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
                  </div>
                ) : null}
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between text-xs text-secondary-text">
                <span>第 {eventPage} / {totalEventPages} 页</span>
                <div className="flex gap-2">
                  <button type="button" className="btn-secondary text-xs px-3 py-1" disabled={eventPage <= 1}
                    onClick={() => setEventPage((prev) => Math.max(1, prev - 1))}>上一页</button>
                  <button type="button" className="btn-secondary text-xs px-3 py-1" disabled={eventPage >= totalEventPages}
                    onClick={() => setEventPage((prev) => Math.min(totalEventPages, prev + 1))}>下一页</button>
                </div>
              </div>
            </div>
          </Card>
        )}
      </div>

      {/* ---- Delete confirmation ---- */}
      <ConfirmDialog
        isOpen={Boolean(pendingDelete)}
        title="删除记录"
        message={pendingDelete?.message || '确认删除？'}
        confirmText={deleteLoading ? '删除中...' : '确认删除'}
        cancelText="取消"
        isDanger
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => { if (!deleteLoading) setPendingDelete(null); }}
      />
    </AppPage>
  );
};

export default PortfolioPage;
