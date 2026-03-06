# -*- coding: utf-8 -*-
"""
===================================
概率化支撑/压力位模块 - 历史反弹率统计
===================================

核心功能：
1. 关键位置识别（整数关口、前高/前低、均线位置、成交量密集区）
2. 历史统计（统计价格触及该位置后的反弹/突破概率）
3. 概率计算（基于历史数据计算支撑/压力强度）

目标：将固定支撑位升级为概率化描述：
"30.0元整数关口支撑强度高（历史此处反弹率70%）"
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LevelType(Enum):
    """支撑/压力类型"""
    SUPPORT = "support"
    RESISTANCE = "resistance"


class LevelSource(Enum):
    """价位来源"""
    INTEGER = "整数关口"           # 整数价位（10, 15, 20...）
    PREVIOUS_HIGH = "前高"        # 近期高点
    PREVIOUS_LOW = "前低"         # 近期低点
    MA5 = "MA5"                   # 5日均线
    MA10 = "MA10"                 # 10日均线
    MA20 = "MA20"                 # 20日均线
    MA60 = "MA60"                 # 60日均线
    MA120 = "MA120"               # 120日均线
    VOLUME_CLUSTER = "成交密集区"  # 成交量集中的价位
    BOLL_UPPER = "布林上轨"       # 布林带上轨
    BOLL_LOWER = "布林下轨"       # 布林带下轨
    GAP = "缺口"                  # 跳空缺口
    FIBONACCI = "斐波那契"         # 斐波那契回调位


class StrengthLevel(Enum):
    """强度等级"""
    VERY_STRONG = "极强"      # 反弹率 > 75%
    STRONG = "强"             # 反弹率 60-75%
    MODERATE = "中"           # 反弹率 45-60%
    WEAK = "弱"               # 反弹率 30-45%
    VERY_WEAK = "极弱"        # 反弹率 < 30%


@dataclass
class ProbabilityLevel:
    """概率化支撑/压力位"""
    price: float                      # 价位
    level_type: LevelType             # support/resistance
    source: LevelSource               # 来源
    
    # 概率统计
    hit_count: int = 0                # 历史触及次数
    bounce_count: int = 0             # 反弹次数（支撑位）
    break_count: int = 0              # 突破次数（压力位）
    bounce_rate: float = 0.0          # 反弹概率 (%)
    break_rate: float = 0.0           # 突破概率 (%)
    
    # 强度评级
    strength: StrengthLevel = StrengthLevel.MODERATE
    confidence: float = 0.0           # 统计置信度 (0-1)
    
    # 描述信息
    description: str = ""
    distance_pct: float = 0.0         # 距离当前价格百分比
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'price': round(self.price, 2),
            'level_type': self.level_type.value,
            'source': self.source.value,
            'hit_count': self.hit_count,
            'bounce_count': self.bounce_count,
            'break_count': self.break_count,
            'bounce_rate': round(self.bounce_rate, 1),
            'break_rate': round(self.break_rate, 1),
            'strength': self.strength.value,
            'confidence': round(self.confidence, 2),
            'description': self.description,
            'distance_pct': round(self.distance_pct, 2),
        }


@dataclass
class ProbabilityLevelsResult:
    """概率化支撑压力分析结果"""
    stock_code: str
    current_price: float
    
    # 支撑位列表（按价格从高到低）
    support_levels: List[ProbabilityLevel] = field(default_factory=list)
    
    # 压力位列表（按价格从低到高）
    resistance_levels: List[ProbabilityLevel] = field(default_factory=list)
    
    # 关键支撑位（最近且强度最高）
    key_support: Optional[ProbabilityLevel] = None
    
    # 关键压力位（最近且强度最高）
    key_resistance: Optional[ProbabilityLevel] = None
    
    # 分析摘要
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stock_code': self.stock_code,
            'current_price': round(self.current_price, 2),
            'support_levels': [lv.to_dict() for lv in self.support_levels],
            'resistance_levels': [lv.to_dict() for lv in self.resistance_levels],
            'key_support': self.key_support.to_dict() if self.key_support else None,
            'key_resistance': self.key_resistance.to_dict() if self.key_resistance else None,
            'summary': self.summary,
        }


class KeyLevelIdentifier:
    """
    关键价位识别器
    
    识别潜在支撑/压力位
    """
    
    # 整数关口步长映射
    INTEGER_STEPS = [
        (1, 10),      # 1-10元：步长1
        (10, 30),     # 10-30元：步长2
        (30, 100),    # 30-100元：步长5
        (100, 300),   # 100-300元：步长10
        (300, 1000),  # 300-1000元：步长50
        (1000, float('inf')),  # 1000元以上：步长100
    ]
    
    def identify_integer_levels(self, price: float) -> List[float]:
        """
        识别整数关口
        
        返回当前价格附近的整数关口（上下各2个）
        """
        levels = []
        
        # 确定步长
        step = 1
        for min_price, max_price in self.INTEGER_STEPS:
            if min_price <= price < max_price:
                step = 10 if min_price == 1 else (2 if min_price == 10 else (5 if min_price == 30 else (10 if min_price == 100 else (50 if min_price == 300 else 100))))
                break
        
        # 计算上下整数关口
        base = int(price / step) * step
        for i in range(-2, 3):
            level = base + i * step
            if level > 0 and level != price:
                levels.append(float(level))
        
        return sorted(set(levels))
    
    def identify_previous_highs_lows(
        self, 
        df: pd.DataFrame, 
        lookback: int = 60,
        min_distance: int = 5
    ) -> Tuple[List[float], List[float]]:
        """
        识别近期高点和低点
        
        Args:
            df: K线数据
            lookback: 回溯天数
            min_distance: 极值点之间的最小距离
            
        Returns:
            (高点列表, 低点列表)
        """
        if len(df) < lookback:
            lookback = len(df)
        
        recent = df.tail(lookback).copy()
        highs = []
        lows = []
        
        # 寻找局部极值
        for i in range(min_distance, len(recent) - min_distance):
            # 检查是否是局部高点
            window = recent['high'].iloc[i-min_distance:i+min_distance+1]
            if recent['high'].iloc[i] == window.max():
                highs.append(float(recent['high'].iloc[i]))
            
            # 检查是否是局部低点
            window = recent['low'].iloc[i-min_distance:i+min_distance+1]
            if recent['low'].iloc[i] == window.min():
                lows.append(float(recent['low'].iloc[i]))
        
        # 去重并排序
        highs = sorted(set(highs), reverse=True)
        lows = sorted(set(lows), reverse=True)
        
        return highs, lows
    
    def identify_ma_levels(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        识别均线位置
        
        Returns:
            {均线名称: 价格}
        """
        levels = {}
        
        if len(df) < 5:
            return levels
        
        close = df['close']
        
        if len(close) >= 5:
            levels['MA5'] = float(close.rolling(5).mean().iloc[-1])
        if len(close) >= 10:
            levels['MA10'] = float(close.rolling(10).mean().iloc[-1])
        if len(close) >= 20:
            levels['MA20'] = float(close.rolling(20).mean().iloc[-1])
        if len(close) >= 60:
            levels['MA60'] = float(close.rolling(60).mean().iloc[-1])
        if len(close) >= 120:
            levels['MA120'] = float(close.rolling(120).mean().iloc[-1])
        
        return levels
    
    def identify_volume_clusters(
        self, 
        df: pd.DataFrame, 
        num_bins: int = 10
    ) -> List[Tuple[float, float]]:
        """
        识别成交量密集区
        
        Returns:
            [(价位, 成交量权重)]
        """
        if len(df) < 20:
            return []
        
        # 按价格区间统计成交量
        price_min = df['low'].min()
        price_max = df['high'].max()
        
        if price_max <= price_min:
            return []
        
        bin_size = (price_max - price_min) / num_bins
        volume_profile = {}
        
        for _, row in df.iterrows():
            # 简化：使用收盘价
            price_bin = round(row['close'] / bin_size) * bin_size
            if price_bin not in volume_profile:
                volume_profile[price_bin] = 0
            volume_profile[price_bin] += row['volume']
        
        # 找出成交量最大的几个价位
        if not volume_profile:
            return []
        
        total_volume = sum(volume_profile.values())
        sorted_levels = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
        
        # 返回成交量前3的价位
        return [(price, vol / total_volume) for price, vol in sorted_levels[:3]]


class ProbabilityCalculator:
    """
    概率计算器
    
    计算历史反弹/突破概率
    """
    
    # 触及阈值：价格在价位的 ±X% 范围内视为触及
    TOUCH_THRESHOLD_PCT = 1.0  # 1%
    
    # 反弹判断：触及后 X 日内反弹 Y% 视为有效反弹
    BOUNCE_DAYS = 5
    BOUNCE_THRESHOLD_PCT = 2.0  # 2%
    
    # 突破判断：触及后 X 日内突破 Y% 视为有效突破
    BREAK_DAYS = 5
    BREAK_THRESHOLD_PCT = 3.0  # 3%
    
    def calculate_bounce_probability(
        self,
        df: pd.DataFrame,
        level_price: float,
        level_type: LevelType,
    ) -> Tuple[int, int, float]:
        """
        计算反弹概率
        
        Args:
            df: K线数据
            level_price: 价位
            level_type: 支撑/压力类型
            
        Returns:
            (触及次数, 反弹次数, 反弹概率)
        """
        if len(df) < 20:
            return 0, 0, 0.0
        
        touch_count = 0
        bounce_count = 0
        
        # 计算触及阈值
        threshold = level_price * self.TOUCH_THRESHOLD_PCT / 100
        
        for i in range(len(df) - self.BOUNCE_DAYS):
            low = df['low'].iloc[i]
            high = df['high'].iloc[i]
            
            # 检查是否触及该价位
            if level_type == LevelType.SUPPORT:
                # 支撑位：最低价接近价位
                touched = abs(low - level_price) <= threshold or (low <= level_price <= high)
            else:
                # 压力位：最高价接近价位
                touched = abs(high - level_price) <= threshold or (low <= level_price <= high)
            
            if touched:
                touch_count += 1
                
                # 检查后续是否反弹/突破
                future = df.iloc[i+1:i+1+self.BOUNCE_DAYS]
                if len(future) < self.BOUNCE_DAYS:
                    continue
                
                if level_type == LevelType.SUPPORT:
                    # 支撑位反弹：后续最高价上涨超过阈值
                    max_price = future['high'].max()
                    entry_price = df['close'].iloc[i]
                    if (max_price - entry_price) / entry_price * 100 >= self.BOUNCE_THRESHOLD_PCT:
                        bounce_count += 1
                else:
                    # 压力位突破：后续收盘价突破价位
                    max_close = future['close'].max()
                    if max_close > level_price * (1 + self.BREAK_THRESHOLD_PCT / 100):
                        bounce_count += 1
        
        # 计算概率
        if touch_count > 0:
            probability = bounce_count / touch_count * 100
        else:
            probability = 0.0
        
        return touch_count, bounce_count, probability
    
    def calculate_strength(self, bounce_rate: float, hit_count: int) -> StrengthLevel:
        """
        计算强度等级
        
        考虑反弹率和样本数量
        """
        # 样本数量权重
        if hit_count < 3:
            # 样本太少，置信度低
            return StrengthLevel.WEAK
        
        if bounce_rate >= 75:
            return StrengthLevel.VERY_STRONG
        elif bounce_rate >= 60:
            return StrengthLevel.STRONG
        elif bounce_rate >= 45:
            return StrengthLevel.MODERATE
        elif bounce_rate >= 30:
            return StrengthLevel.WEAK
        else:
            return StrengthLevel.VERY_WEAK
    
    def calculate_confidence(self, hit_count: int, bounce_rate: float) -> float:
        """
        计算置信度
        
        基于样本数量和概率一致性
        """
        if hit_count == 0:
            return 0.0
        
        # 样本数量因子（样本越多越可信）
        sample_factor = min(1.0, hit_count / 10)
        
        # 概率偏离因子（概率越极端越可信）
        deviation = abs(bounce_rate - 50) / 50
        probability_factor = 0.5 + deviation * 0.5
        
        return min(1.0, sample_factor * probability_factor)


class ProbabilityLevelsAnalyzer:
    """
    概率化支撑压力分析器
    
    整合关键价位识别和概率计算
    """
    
    def __init__(self):
        self.identifier = KeyLevelIdentifier()
        self.calculator = ProbabilityCalculator()
    
    def analyze(
        self,
        df: pd.DataFrame,
        stock_code: str,
        current_price: Optional[float] = None,
    ) -> ProbabilityLevelsResult:
        """
        执行概率化支撑压力分析
        
        Args:
            df: K线数据（需包含 open, high, low, close, volume）
            stock_code: 股票代码
            current_price: 当前价格（默认使用最新收盘价）
            
        Returns:
            ProbabilityLevelsResult 分析结果
        """
        if df is None or df.empty or len(df) < 20:
            logger.warning(f"{stock_code} 数据不足，无法进行支撑压力分析")
            return ProbabilityLevelsResult(
                stock_code=stock_code,
                current_price=current_price or 0,
                summary="数据不足，无法分析支撑压力位"
            )
        
        # 获取当前价格
        if current_price is None:
            current_price = float(df['close'].iloc[-1])
        
        result = ProbabilityLevelsResult(
            stock_code=stock_code,
            current_price=current_price,
        )
        
        # 识别所有潜在价位
        all_levels = self._identify_all_levels(df, current_price)
        
        # 计算每个价位的概率
        support_levels = []
        resistance_levels = []
        
        for level_price, source, level_type in all_levels:
            # 计算概率
            hit_count, bounce_count, bounce_rate = self.calculator.calculate_bounce_probability(
                df, level_price, level_type
            )
            
            # 计算强度和置信度
            strength = self.calculator.calculate_strength(bounce_rate, hit_count)
            confidence = self.calculator.calculate_confidence(hit_count, bounce_rate)
            
            # 计算距离
            distance_pct = (level_price - current_price) / current_price * 100
            
            # 生成描述
            description = self._generate_description(
                level_price, source, level_type, bounce_rate, 
                hit_count, strength, distance_pct
            )
            
            level = ProbabilityLevel(
                price=level_price,
                level_type=level_type,
                source=source,
                hit_count=hit_count,
                bounce_count=bounce_count,
                bounce_rate=bounce_rate,
                strength=strength,
                confidence=confidence,
                description=description,
                distance_pct=distance_pct,
            )
            
            if level_type == LevelType.SUPPORT:
                support_levels.append(level)
            else:
                resistance_levels.append(level)
        
        # 排序
        result.support_levels = sorted(support_levels, key=lambda x: x.price, reverse=True)
        result.resistance_levels = sorted(resistance_levels, key=lambda x: x.price)
        
        # 识别关键支撑/压力位
        result.key_support = self._select_key_level(result.support_levels)
        result.key_resistance = self._select_key_level(result.resistance_levels)
        
        # 生成摘要
        result.summary = self._generate_summary(result)
        
        return result
    
    def _identify_all_levels(
        self, 
        df: pd.DataFrame, 
        current_price: float
    ) -> List[Tuple[float, LevelSource, LevelType]]:
        """
        识别所有潜在价位
        
        Returns:
            [(价位, 来源, 类型)]
        """
        levels = []
        
        # 1. 整数关口
        integer_levels = self.identifier.identify_integer_levels(current_price)
        for lv in integer_levels:
            if lv < current_price:
                levels.append((lv, LevelSource.INTEGER, LevelType.SUPPORT))
            else:
                levels.append((lv, LevelSource.INTEGER, LevelType.RESISTANCE))
        
        # 2. 前高前低
        highs, lows = self.identifier.identify_previous_highs_lows(df)
        for high in highs[:5]:  # 只取前5个
            if high < current_price * 0.95:  # 排除太远的
                continue
            if high > current_price:
                levels.append((high, LevelSource.PREVIOUS_HIGH, LevelType.RESISTANCE))
        for low in lows[:5]:
            if low > current_price * 1.05:  # 排除太远的
                continue
            if low < current_price:
                levels.append((low, LevelSource.PREVIOUS_LOW, LevelType.SUPPORT))
        
        # 3. 均线位置
        ma_levels = self.identifier.identify_ma_levels(df)
        for ma_name, ma_price in ma_levels.items():
            source = LevelSource[ma_name]
            if ma_price < current_price:
                levels.append((ma_price, source, LevelType.SUPPORT))
            else:
                levels.append((ma_price, source, LevelType.RESISTANCE))
        
        # 4. 成交密集区
        volume_clusters = self.identifier.identify_volume_clusters(df)
        for price, _ in volume_clusters:
            if price < current_price:
                levels.append((price, LevelSource.VOLUME_CLUSTER, LevelType.SUPPORT))
            else:
                levels.append((price, LevelSource.VOLUME_CLUSTER, LevelType.RESISTANCE))
        
        # 去重（价格相近的只保留一个）
        unique_levels = []
        for price, source, level_type in levels:
            # 检查是否已存在相近价位
            is_duplicate = False
            for existing_price, _, existing_type in unique_levels:
                if abs(price - existing_price) / existing_price < 0.01:  # 1%差异内视为重复
                    if existing_type == level_type:
                        is_duplicate = True
                        break
            if not is_duplicate:
                unique_levels.append((price, source, level_type))
        
        return unique_levels
    
    def _generate_description(
        self,
        price: float,
        source: LevelSource,
        level_type: LevelType,
        bounce_rate: float,
        hit_count: int,
        strength: StrengthLevel,
        distance_pct: float
    ) -> str:
        """生成价位描述"""
        direction = "支撑" if level_type == LevelType.SUPPORT else "压力"
        
        if hit_count > 0:
            desc = f"{price:.2f}元（{source.value}）{direction}强度{strength.value}"
            desc += f"（历史触及{hit_count}次，反弹率{bounce_rate:.0f}%）"
        else:
            desc = f"{price:.2f}元（{source.value}）{direction}位（历史数据不足）"
        
        return desc
    
    def _select_key_level(self, levels: List[ProbabilityLevel]) -> Optional[ProbabilityLevel]:
        """
        选择关键价位
        
        策略：距离最近 + 强度最高
        """
        if not levels:
            return None
        
        # 按距离排序（绝对值最小）
        sorted_by_distance = sorted(levels, key=lambda x: abs(x.distance_pct))
        
        # 在前3个最近的价位中，选择强度最高的
        candidates = sorted_by_distance[:3]
        key_level = max(candidates, key=lambda x: x.bounce_rate)
        
        return key_level
    
    def _generate_summary(self, result: ProbabilityLevelsResult) -> str:
        """生成分析摘要"""
        lines = []
        
        lines.append(f"当前价格：{result.current_price:.2f}元")
        
        # 支撑位
        if result.support_levels:
            lines.append("\n支撑位：")
            for lv in result.support_levels[:3]:
                star = "⭐" if lv.strength in [StrengthLevel.VERY_STRONG, StrengthLevel.STRONG] else ""
                lines.append(f"  {star} {lv.description}")
        else:
            lines.append("\n支撑位：无明显支撑")
        
        # 压力位
        if result.resistance_levels:
            lines.append("\n压力位：")
            for lv in result.resistance_levels[:3]:
                warn = "⚠️" if lv.strength in [StrengthLevel.VERY_STRONG, StrengthLevel.STRONG] else ""
                lines.append(f"  {warn} {lv.description}")
        else:
            lines.append("\n压力位：无明显压力")
        
        # 关键价位
        if result.key_support:
            lines.append(f"\n关键支撑：{result.key_support.description}")
        if result.key_resistance:
            lines.append(f"关键压力：{result.key_resistance.description}")
        
        return "\n".join(lines)


# 便捷函数
_probability_analyzer: Optional[ProbabilityLevelsAnalyzer] = None


def get_probability_analyzer() -> ProbabilityLevelsAnalyzer:
    """获取概率化分析器单例"""
    global _probability_analyzer
    if _probability_analyzer is None:
        _probability_analyzer = ProbabilityLevelsAnalyzer()
    return _probability_analyzer


def analyze_probability_levels(
    df: pd.DataFrame,
    stock_code: str,
    current_price: Optional[float] = None,
) -> ProbabilityLevelsResult:
    """
    便捷函数：执行概率化支撑压力分析
    
    Args:
        df: K线数据
        stock_code: 股票代码
        current_price: 当前价格
        
    Returns:
        ProbabilityLevelsResult 分析结果
    """
    analyzer = get_probability_analyzer()
    return analyzer.analyze(df, stock_code, current_price)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 模拟数据
    np.random.seed(42)
    dates = pd.date_range(start='2025-01-01', periods=120, freq='D')
    
    base_price = 30.0
    prices = [base_price]
    for i in range(119):
        change = np.random.randn() * 0.02
        prices.append(prices[-1] * (1 + change))
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * (1 + np.random.uniform(0, 0.03)) for p in prices],
        'low': [p * (1 - np.random.uniform(0, 0.03)) for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in prices],
    })
    
    result = analyze_probability_levels(df, 'TEST001')
    
    print("\n=== 概率化支撑压力分析 ===")
    print(result.summary)