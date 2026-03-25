#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for new features implemented from Sequoia project.
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_cache_manager():
    """Test CacheManager functionality."""
    print("\n" + "="*60)
    print("Testing CacheManager")
    print("="*60)
    
    try:
        from data_provider.cache_manager import CacheManager
        import pandas as pd
        
        # Initialize cache manager
        cache = CacheManager(cache_dir="data_cache", cache_format="parquet")
        print("✓ CacheManager initialized")
        
        # Get cache info
        info = cache.get_cache_info()
        print(f"✓ Cache info retrieved: {info['total_files']} files, {info['total_size_mb']:.2f} MB")
        
        # Test with sample data
        sample_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'close': range(100, 110),
            'volume': range(1000, 1010)
        })
        
        cache.save_data('TEST001', sample_data)
        print("✓ Sample data saved to cache")
        
        # Retrieve from cache - requires start_date and end_date parameters
        cached_data = cache.get_cached_data('TEST001', '2024-01-01', '2024-01-10')
        if cached_data is not None:
            print(f"✓ Data retrieved from cache: {len(cached_data)} rows")
        
        # Clean up test data
        cache.clear_cache('TEST001')
        print("✓ Test cache cleared")
        
        print("\n✅ CacheManager test PASSED")
        return True
    except Exception as e:
        print(f"\n❌ CacheManager test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_loader():
    """Test StrategyLoader functionality."""
    print("\n" + "="*60)
    print("Testing StrategyLoader")
    print("="*60)
    
    try:
        from strategies.strategy_loader import get_strategy_loader
        
        # Get global instance
        loader = get_strategy_loader()
        print("✓ StrategyLoader initialized")
        
        # Discover strategies
        strategies = loader.discover_strategies()
        print(f"✓ Discovered {len(strategies)} strategies")
        
        # Get enabled strategies
        enabled = loader.get_enabled_strategies()
        print(f"✓ Enabled strategies: {len(enabled)}")
        
        # Get statistics
        stats = loader.get_statistics()
        print(f"✓ Statistics: total={stats['total_strategies']}, enabled={stats['enabled_strategies']}")
        print(f"  Categories: {stats['categories']}")
        
        # List some strategies - strategies is a dict, need to iterate over values
        if strategies:
            print(f"  Sample strategies:")
            strategy_list = list(strategies.values())[:3]
            for s in strategy_list:
                name = s.get('name', 'Unknown') if isinstance(s, dict) else str(s)
                category = s.get('category', 'N/A') if isinstance(s, dict) else 'N/A'
                print(f"    - {name} ({category})")
        
        print("\n✅ StrategyLoader test PASSED")
        return True
    except Exception as e:
        print(f"\n❌ StrategyLoader test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backtest_engine():
    """Test BacktestEngine functionality."""
    print("\n" + "="*60)
    print("Testing BacktestEngine")
    print("="*60)
    
    try:
        from backtest.engine import BacktestEngine, create_ma_signals
        from data_provider.base import DataFetcherManager
        import pandas as pd
        
        # Initialize engine
        engine = BacktestEngine(initial_capital=100000.0)
        print("✓ BacktestEngine initialized")
        
        # Get sample data
        manager = DataFetcherManager()
        df, source = manager.get_daily_data('600519', days=90)
        print(f"✓ Got sample data: {len(df)} rows from {source}")
        
        # Create signals
        entry_signal, exit_signal = create_ma_signals(df, short_period=5, long_period=20)
        print(f"✓ Created signals: entry={len(entry_signal)}, exit={len(exit_signal)}")
        
        # Run backtest
        start_time = time.time()
        result = engine.run_backtest(
            data=df,
            entry_signal=entry_signal,
            exit_signal=exit_signal,
            profit_target=0.10,
            stop_loss=-0.05,
            commission=0.001,
            slippage=0.001
        )
        elapsed = time.time() - start_time
        
        print(f"✓ Backtest completed in {elapsed:.2f}s")
        print(f"  Total trades: {result.total_trades}")
        print(f"  Win rate: {result.win_rate:.2%}")
        print(f"  Total return: {result.total_profit_pct:.2f}%")
        
        # Print report
        print("\n--- Backtest Report ---")
        engine.print_report(result)
        
        print("\n✅ BacktestEngine test PASSED")
        return True
    except Exception as e:
        print(f"\n❌ BacktestEngine test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stock_filter():
    """Test StockFilter functionality."""
    print("\n" + "="*60)
    print("Testing StockFilter")
    print("="*60)
    
    try:
        from screening.filter import StockFilter
        from data_provider.base import DataFetcherManager
        
        # Initialize
        manager = DataFetcherManager()
        filter = StockFilter(manager)
        print("✓ StockFilter initialized")
        
        # Get all stocks
        all_stocks = filter._get_all_stocks()
        if not all_stocks.empty:
            print(f"✓ Got {len(all_stocks)} stocks from data source")
            
            # Test basic filtering
            filtered = filter.filter_stocks(
                min_market_cap=5_000_000_000,  # 5 billion
                min_turnover=100_000_000,      # 100 million
                target_count=5,                # Just get 5 for testing
                sort_by=['turnover']
            )
            
            print(f"✓ Filtered to {len(filtered)} stocks")
            
            if not filtered.empty:
                print("\n--- Top 5 Filtered Stocks ---")
                print(filtered[['code', 'name', 'price', 'turnover', 'turnover_rate']].head())
                
                # Get summary
                summary = filter.get_stock_screening_summary(filtered)
                print(f"\n--- Summary ---")
                print(f"  Average market cap: {summary['avg_market_cap']:,.0f}")
                print(f"  Average turnover: {summary['avg_turnover']:,.0f}")
        else:
            print("⚠ No stocks available for filtering (this may be expected)")
        
        print("\n✅ StockFilter test PASSED")
        return True
    except Exception as e:
        print(f"\n❌ StockFilter test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_structured_logger():
    """Test StructuredLogger functionality."""
    print("\n" + "="*60)
    print("Testing StructuredLogger")
    print("="*60)
    
    try:
        from utils.log_utils import StructuredLogger
        
        # Test stock logging
        StructuredLogger.stock_info("600519", "Test stock info", source="TestSource")
        print("✓ Stock info logged")
        
        StructuredLogger.stock_warning("600519", "Test stock warning", source="TestSource")
        print("✓ Stock warning logged")
        
        StructuredLogger.stock_error("600519", "Test stock error", source="TestSource")
        print("✓ Stock error logged")
        
        # Test strategy logging
        StructuredLogger.strategy_info("MA金叉", "Test strategy matched")
        print("✓ Strategy info logged")
        
        StructuredLogger.strategy_warning("MA金叉", "Test strategy warning")
        print("✓ Strategy warning logged")
        
        # Test cache logging
        StructuredLogger.cache_hit("600519", "2024-01-01 ~ 2024-12-31")
        print("✓ Cache hit logged")
        
        StructuredLogger.cache_miss("600519", "Cache expired")
        print("✓ Cache miss logged")
        
        StructuredLogger.cache_write("600519", 100)
        print("✓ Cache write logged")
        
        # Test batch logging
        StructuredLogger.batch_start("Test Batch", 10)
        StructuredLogger.batch_progress("Test Batch", 5, 10)
        StructuredLogger.batch_complete("Test Batch", 10, 8, 2)
        print("✓ Batch operations logged")
        
        # Test system logging
        StructuredLogger.system_info("Test system info")
        print("✓ System info logged")
        
        print("\n✅ StructuredLogger test PASSED")
        return True
    except Exception as e:
        print(f"\n❌ StructuredLogger test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_concurrent_fetching():
    """Test concurrent fetching functionality."""
    print("\n" + "="*60)
    print("Testing Concurrent Fetching")
    print("="*60)
    
    try:
        from data_provider.base import DataFetcherManager
        
        # Initialize manager
        manager = DataFetcherManager()
        print("✓ DataFetcherManager initialized")
        
        # Test batch fetch
        stock_codes = ['600519', '000001', '000002', '603193', '002594']
        print(f"✓ Testing batch fetch for {len(stock_codes)} stocks...")
        
        start_time = time.time()
        results = manager.batch_get_daily_data(
            stock_codes,
            days=30,
            max_workers=3,
            show_progress=True
        )
        elapsed = time.time() - start_time
        
        print(f"✓ Batch fetch completed in {elapsed:.2f}s")
        print(f"  Processed {len(results)} stocks")
        
        # Count successes and failures
        success_count = sum(1 for code, df, source in results if df is not None)
        failure_count = len(results) - success_count
        
        print(f"  Success: {success_count}, Failed: {failure_count}")
        
        # Show some results
        for code, df, source in results[:3]:
            if df is not None:
                print(f"  - {code}: {len(df)} rows from {source}")
            else:
                print(f"  - {code}: FAILED")
        
        print("\n✅ Concurrent Fetching test PASSED")
        return True
    except Exception as e:
        print(f"\n❌ Concurrent Fetching test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print(" " * 20 + "NEW FEATURES TEST SUITE")
    print("="*80)
    
    tests = [
        ("CacheManager", test_cache_manager),
        ("StrategyLoader", test_strategy_loader),
        ("BacktestEngine", test_backtest_engine),
        ("StockFilter", test_stock_filter),
        ("StructuredLogger", test_structured_logger),
        ("Concurrent Fetching", test_concurrent_fetching),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ {name} test CRASHED: {e}")
            results[name] = False
    
    # Print summary
    print("\n" + "="*80)
    print(" " * 25 + "TEST SUMMARY")
    print("="*80)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("\n" + "-"*80)
    print(f"Total: {passed}/{total} tests passed ({passed/total:.1%})")
    print("="*80 + "\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())