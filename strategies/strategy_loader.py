# -*- coding: utf-8 -*-
"""
===================================
Dynamic Strategy Loader
===================================

This module provides automatic strategy discovery and loading from YAML files.
It enables runtime strategy management without code modifications.

Features:
1. Automatic discovery of YAML strategy files
2. Dynamic loading with metadata extraction
3. Runtime enable/disable strategies
4. Strategy metadata querying
5. Support for custom strategy directories
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)


class StrategyLoader:
    """
    Dynamic strategy loader for automatic strategy discovery.
    
    This class manages strategy YAML files, automatically discovering
    strategies from specified directories and providing runtime
    strategy management capabilities.
    """
    
    def __init__(self, strategy_dirs: Optional[List[str]] = None):
        """
        Initialize the strategy loader.
        
        Args:
            strategy_dirs: List of directories to scan for strategies.
                          Defaults to ["strategies"] if not specified.
        """
        self.strategy_dirs = strategy_dirs or ["strategies"]
        self._strategies: Dict[str, dict] = {}
        self._enabled_strategies: set = set()
        
        logger.info(f"StrategyLoader initialized with dirs: {self.strategy_dirs}")
    
    def discover_strategies(self, force_reload: bool = False) -> Dict[str, dict]:
        """
        Automatically discover all strategies from configured directories.
        
        This method scans all configured directories for YAML files,
        loads them, and caches the strategy metadata.
        
        Args:
            force_reload: If True, reload all strategies even if already cached.
            
        Returns:
            Dictionary mapping strategy names to their metadata
        """
        if self._strategies and not force_reload:
            logger.debug(f"Using cached strategies: {len(self._strategies)}")
            return self._strategies
        
        logger.info("Discovering strategies...")
        strategies = {}
        
        for strategy_dir in self.strategy_dirs:
            dir_path = Path(strategy_dir)
            
            if not dir_path.exists():
                logger.warning(f"Strategy directory not found: {strategy_dir}")
                continue
            
            logger.debug(f"Scanning directory: {strategy_dir}")
            
            for yaml_file in dir_path.glob("*.yaml"):
                try:
                    strategy = self._load_strategy(yaml_file)
                    if strategy:
                        strategy_name = strategy['name']
                        strategies[strategy_name] = strategy
                        logger.debug(f"Loaded strategy: {strategy_name}")
                except Exception as e:
                    logger.error(f"Failed to load strategy from {yaml_file}: {e}")
        
        self._strategies = strategies
        
        # Initialize enabled strategies (default all enabled)
        if not self._enabled_strategies:
            self._enabled_strategies = set(strategies.keys())
        
        logger.info(f"Discovered {len(strategies)} strategies: {list(strategies.keys())}")
        return strategies
    
    def _load_strategy(self, yaml_file: Path) -> Optional[dict]:
        """
        Load a single strategy YAML file.
        
        Args:
            yaml_file: Path to the YAML file
            
        Returns:
            Strategy metadata dictionary or None if loading fails
        """
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'name' not in data:
                logger.warning(f"Invalid strategy file (missing 'name'): {yaml_file}")
                return None
            
            # Add metadata
            data['file_path'] = str(yaml_file)
            data['file_name'] = yaml_file.name
            data['last_modified'] = yaml_file.stat().st_mtime
            
            return data
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {yaml_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading strategy from {yaml_file}: {e}")
            return None
    
    def get_all_strategies(self) -> Dict[str, dict]:
        """
        Get all discovered strategies.
        
        Returns:
            Dictionary of all strategies
        """
        if not self._strategies:
            self.discover_strategies()
        return self._strategies.copy()
    
    def get_enabled_strategies(self) -> List[dict]:
        """
        Get currently enabled strategies.
        
        Returns:
            List of enabled strategy dictionaries
        """
        if not self._strategies:
            self.discover_strategies()
        
        return [
            strategy for name, strategy in self._strategies.items()
            if name in self._enabled_strategies
        ]
    
    def get_strategy(self, strategy_name: str) -> Optional[dict]:
        """
        Get a specific strategy by name.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Strategy dictionary or None if not found
        """
        if not self._strategies:
            self.discover_strategies()
        
        return self._strategies.get(strategy_name)
    
    def enable_strategy(self, strategy_name: str) -> bool:
        """
        Enable a strategy.
        
        Args:
            strategy_name: Name of the strategy to enable
            
        Returns:
            True if successful, False if strategy not found
        """
        if not self._strategies:
            self.discover_strategies()
        
        if strategy_name in self._strategies:
            self._enabled_strategies.add(strategy_name)
            logger.info(f"Strategy enabled: {strategy_name}")
            return True
        
        logger.warning(f"Strategy not found: {strategy_name}")
        return False
    
    def disable_strategy(self, strategy_name: str) -> bool:
        """
        Disable a strategy.
        
        Args:
            strategy_name: Name of the strategy to disable
            
        Returns:
            True if successful, False if strategy not found
        """
        if strategy_name in self._enabled_strategies:
            self._enabled_strategies.discard(strategy_name)
            logger.info(f"Strategy disabled: {strategy_name}")
            return True
        
        logger.warning(f"Strategy not enabled or not found: {strategy_name}")
        return False
    
    def is_enabled(self, strategy_name: str) -> bool:
        """
        Check if a strategy is enabled.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            True if enabled, False otherwise
        """
        return strategy_name in self._enabled_strategies
    
    def enable_all(self) -> None:
        """Enable all strategies."""
        if not self._strategies:
            self.discover_strategies()
        
        self._enabled_strategies = set(self._strategies.keys())
        logger.info(f"All strategies enabled: {len(self._enabled_strategies)}")
    
    def disable_all(self) -> None:
        """Disable all strategies."""
        self._enabled_strategies.clear()
        logger.info("All strategies disabled")
    
    def get_strategy_names(self, enabled_only: bool = False) -> List[str]:
        """
        Get list of strategy names.
        
        Args:
            enabled_only: If True, only return enabled strategy names
            
        Returns:
            List of strategy names
        """
        if not self._strategies:
            self.discover_strategies()
        
        if enabled_only:
            return list(self._enabled_strategies)
        else:
            return list(self._strategies.keys())
    
    def get_strategy_by_category(self, category: str) -> List[dict]:
        """
        Get strategies by category.
        
        Args:
            category: Strategy category (trend, pattern, reversal, framework)
            
        Returns:
            List of strategies in the category
        """
        if not self._strategies:
            self.discover_strategies()
        
        return [
            strategy for name, strategy in self._strategies.items()
            if strategy.get('category') == category and name in self._enabled_strategies
        ]
    
    def reload_strategy(self, strategy_name: str) -> bool:
        """
        Reload a specific strategy from disk.
        
        Args:
            strategy_name: Name of the strategy to reload
            
        Returns:
            True if successful, False otherwise
        """
        if strategy_name not in self._strategies:
            logger.warning(f"Strategy not found: {strategy_name}")
            return False
        
        strategy = self._strategies[strategy_name]
        file_path = Path(strategy['file_path'])
        
        if not file_path.exists():
            logger.error(f"Strategy file not found: {file_path}")
            return False
        
        try:
            new_strategy = self._load_strategy(file_path)
            if new_strategy:
                self._strategies[strategy_name] = new_strategy
                logger.info(f"Strategy reloaded: {strategy_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to reload strategy {strategy_name}: {e}")
        
        return False
    
    def get_statistics(self) -> dict:
        """
        Get statistics about loaded strategies.
        
        Returns:
            Dictionary with statistics
        """
        if not self._strategies:
            self.discover_strategies()
        
        categories = {}
        for strategy in self._strategies.values():
            category = strategy.get('category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
        
        return {
            'total_strategies': len(self._strategies),
            'enabled_strategies': len(self._enabled_strategies),
            'disabled_strategies': len(self._strategies) - len(self._enabled_strategies),
            'categories': categories,
            'strategy_dirs': self.strategy_dirs
        }


# Global singleton instance
_global_loader: Optional[StrategyLoader] = None


def get_strategy_loader() -> StrategyLoader:
    """
    Get the global strategy loader instance.
    
    Returns:
        The global StrategyLoader instance
    """
    global _global_loader
    
    if _global_loader is None:
        _global_loader = StrategyLoader()
    
    return _global_loader