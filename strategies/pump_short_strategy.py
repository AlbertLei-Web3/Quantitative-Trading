# -*- coding: utf-8 -*-
"""
暴涨做空策略核心模块 / Pump Short Strategy Core Module
==================================================

本模块实现暴涨山寨币的做空策略逻辑，包含三个核心模型：
This module implements the short strategy logic for pumping altcoins, containing three core models:

1. Mean Reversion + Anti-Bubble Filter - 均值回归+反泡沫过滤器
2. Volatility Breakout Reversal - 波动率突破反转
3. 反转捕捉网格模型 - Reversal Capture Grid Model

关联文件 / Related Files:
- core/position.py: 持仓管理，记录加仓信息 / Position management, record adding positions
- core/portfolio.py: 投资组合管理 / Portfolio management  
- core/executor.py: 交易执行器 / Trade executor
- config/strategy.yaml: 策略配置参数 / Strategy configuration parameters

主要功能 / Main Functions:
1. 暴涨信号识别：3天内涨幅≥80% / Pump signal detection: ≥80% gain in 3 days
2. 顶部反转信号：放量阴线、上影线判断 / Top reversal signals: volume bearish candles, upper shadows
3. 加仓点位生成：上涨10%/下跌6.5%的网格加仓 / Add position points: 10% up/6.5% down grid
4. 止盈止损判断：35%止损、12%止盈 / Stop loss/profit: 35% stop loss, 12% take profit
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging

class PumpShortStrategy:
    """
    暴涨做空策略类 / Pump Short Strategy Class
    
    该类封装了完整的暴涨做空策略逻辑，支持信号生成、加仓管理、止盈止损判断。
    This class encapsulates complete pump short strategy logic, supporting signal generation, 
    position adding management, and stop loss/profit judgment.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化策略实例 / Initialize strategy instance
        
        Args:
            config (Dict): 策略配置参数字典 / Strategy configuration parameters dictionary
                包含 / Contains:
                - pump_threshold: 暴涨阈值，默认0.8(80%) / Pump threshold, default 0.8(80%)
                - lookback_days: 回望天数，默认3天 / Lookback days, default 3
                - add_up_threshold: 上涨加仓阈值，默认0.1(10%) / Add on up threshold, default 0.1(10%)
                - add_down_threshold: 下跌加仓阈值，默认0.065(6.5%) / Add on down threshold, default 0.065(6.5%)
                - max_add_times: 最大加仓次数，默认3次 / Max add times, default 3
                - stop_loss_threshold: 止损阈值，默认0.35(35%) / Stop loss threshold, default 0.35(35%)
                - take_profit_threshold: 止盈阈值，默认0.12(12%) / Take profit threshold, default 0.12(12%)
        """
        # 策略配置参数 / Strategy configuration parameters
        self.pump_threshold = config.get('pump_threshold', 0.8)  # 暴涨阈值80% / Pump threshold 80%
        self.lookback_days = config.get('lookback_days', 3)  # 回望天数3天 / Lookback period 3 days
        self.add_up_threshold = config.get('add_up_threshold', 0.1)  # 上涨加仓10% / Add on up 10%
        self.add_down_threshold = config.get('add_down_threshold', 0.065)  # 下跌加仓6.5% / Add on down 6.5%
        self.max_add_times = config.get('max_add_times', 3)  # 最大加仓次数3次 / Max add times 3
        self.stop_loss_threshold = config.get('stop_loss_threshold', 0.35)  # 止损阈值35% / Stop loss 35%
        self.take_profit_threshold = config.get('take_profit_threshold', 0.12)  # 止盈阈值12% / Take profit 12%
        
        # 技术指标参数 / Technical indicator parameters
        self.volume_multiplier = config.get('volume_multiplier', 1.5)  # 成交量倍数 / Volume multiplier
        self.upper_shadow_ratio = config.get('upper_shadow_ratio', 0.3)  # 上影线比例 / Upper shadow ratio
        
        # 内部状态 / Internal state
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """
        设置日志记录器 / Setup logger
        
        Returns:
            logging.Logger: 配置好的日志记录器 / Configured logger
        """
        logger = logging.getLogger('PumpShortStrategy')
        logger.setLevel(logging.INFO)
        
        # 避免重复添加处理器 / Avoid duplicate handlers
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    def generate_short_signals(self, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """
        生成做空信号的主入口函数 / Main entry function for generating short signals
        
        集成三个核心模型，生成完整的做空信号字典
        Integrates three core models to generate complete short signal dictionary
        
        Args:
            df (pd.DataFrame): K线数据，包含columns: ['open', 'high', 'low', 'close', 'volume', 'timestamp']
            config (Dict): 运行时配置参数 / Runtime configuration parameters
            
        Returns:
            Dict[str, Any]: 信号字典，包含 / Signal dictionary containing:
                - has_pump_signal: bool, 是否有暴涨信号 / Whether has pump signal
                - has_reversal_signal: bool, 是否有反转信号 / Whether has reversal signal  
                - entry_price: float, 建议入场价格 / Suggested entry price
                - add_positions: List[Dict], 加仓点位列表 / Add position points list
                - stop_loss_price: float, 止损价格 / Stop loss price
                - take_profit_price: float, 止盈价格 / Take profit price
                - signal_strength: float, 信号强度0-1 / Signal strength 0-1
                - metadata: Dict, 额外信息 / Additional metadata
        """
        try:
            # 数据验证 / Data validation
            if df.empty or len(df) < self.lookback_days:
                return self._generate_empty_signal("数据不足 / Insufficient data")
            
            # 模型1: Mean Reversion + Anti-Bubble Filter
            pump_result = self._detect_pump_signal(df)
            
            # 模型2: Volatility Breakout Reversal  
            reversal_result = self._detect_reversal_signal(df)
            
            # 模型3: 反转捕捉网格模型
            grid_result = self._generate_grid_positions(df)
            
            # 综合信号判断 / Combined signal judgment
            has_signal = pump_result['detected'] and reversal_result['detected']
            
            if not has_signal:
                return self._generate_empty_signal("未满足信号条件 / Signal conditions not met")
            
            # 构建完整信号 / Build complete signal
            current_price = float(df.iloc[-1]['close'])
            
            signal = {
                'has_pump_signal': pump_result['detected'],
                'has_reversal_signal': reversal_result['detected'],
                'entry_price': current_price,
                'add_positions': grid_result['add_positions'],
                'stop_loss_price': current_price * (1 + self.stop_loss_threshold),
                'take_profit_price': current_price * (1 - self.take_profit_threshold),
                'signal_strength': self._calculate_signal_strength(pump_result, reversal_result),
                'metadata': {
                    'pump_gain': pump_result['gain_rate'],
                    'reversal_type': reversal_result['type'],
                    'volume_ratio': reversal_result['volume_ratio'],
                    'timestamp': df.index[-1] if hasattr(df.index[-1], 'strftime') else str(df.index[-1])
                }
            }
            
            self.logger.info(f"🎯 生成做空信号 / Generated short signal: 强度 {signal['signal_strength']:.2f}, "
                           f"入场价 {signal['entry_price']:.6f}")
            
            return signal
            
        except Exception as e:
            self.logger.error(f"❌ 信号生成失败 / Signal generation failed: {str(e)}")
            return self._generate_empty_signal(f"错误: {str(e)} / Error: {str(e)}")
    
    def _detect_pump_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        模型1: Mean Reversion + Anti-Bubble Filter
        检测暴涨信号和反泡沫过滤
        
        Args:
            df (pd.DataFrame): K线数据 / Candlestick data
            
        Returns:
            Dict[str, Any]: 暴涨检测结果 / Pump detection result
        """
        try:
            # 计算指定天数内的涨幅 / Calculate gain within specified days
            current_price = float(df.iloc[-1]['close'])
            
            # 确保有足够的历史数据 / Ensure sufficient historical data
            if len(df) <= self.lookback_days * 24:  # 修复：考虑小时级数据 / Fix: consider hourly data
                past_price = float(df.iloc[0]['close'])
            else:
                # 修复：计算正确的回望期间 / Fix: calculate correct lookback period
                lookback_hours = self.lookback_days * 24
                past_price = float(df.iloc[-(lookback_hours)]['close'])
            
            gain_rate = (current_price - past_price) / past_price
            
            # 反泡沫过滤：检查成交量是否跟上 / Anti-bubble filter: check if volume follows
            lookback_hours = min(self.lookback_days * 24, len(df) // 2)
            recent_volume = df.tail(lookback_hours)['volume'].mean()
            historical_volume = df.head(len(df) - lookback_hours)['volume'].mean() if len(df) > lookback_hours else recent_volume
            
            volume_ratio = recent_volume / historical_volume if historical_volume > 0 else 1.0
            
            # 暴涨判断：涨幅超过阈值且成交量有支撑 / Pump judgment: gain exceeds threshold with volume support
            is_pump = gain_rate >= self.pump_threshold and volume_ratio >= self.volume_multiplier
            
            result = {
                'detected': is_pump,
                'gain_rate': gain_rate,
                'volume_ratio': volume_ratio,
                'bubble_risk': volume_ratio < self.volume_multiplier,  # 泡沫风险 / Bubble risk
                'debug_info': {
                    'current_price': current_price,
                    'past_price': past_price,
                    'data_length': len(df),
                    'lookback_hours': lookback_hours
                }
            }
            
            # 详细调试日志 / Detailed debug logging
            self.logger.info(f"🔍 暴涨检测调试 / Pump detection debug:")
            self.logger.info(f"  - 当前价格 / Current price: {current_price:.6f}")
            self.logger.info(f"  - 过去价格 / Past price: {past_price:.6f}")
            self.logger.info(f"  - 涨幅 / Gain rate: {gain_rate:.2%}")
            self.logger.info(f"  - 阈值 / Threshold: {self.pump_threshold:.2%}")
            self.logger.info(f"  - 成交量比 / Volume ratio: {volume_ratio:.2f}")
            self.logger.info(f"  - 是否检测到暴涨 / Pump detected: {is_pump}")
            
            if is_pump:
                self.logger.info(f"🚨 检测到暴涨信号 / Pump signal detected: 涨幅 {gain_rate:.2%}, 成交量比 {volume_ratio:.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 暴涨检测失败 / Pump detection failed: {str(e)}")
            return {'detected': False, 'gain_rate': 0, 'volume_ratio': 0, 'bubble_risk': True}
    
    def _detect_reversal_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        模型2: Volatility Breakout Reversal
        检测顶部反转信号：放量阴线、上影线等
        
        Args:
            df (pd.DataFrame): K线数据 / Candlestick data
            
        Returns:
            Dict[str, Any]: 反转信号检测结果 / Reversal signal detection result
        """
        try:
            if len(df) < 2:
                return {'detected': False, 'type': 'none', 'volume_ratio': 0}
            
            latest_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            
            open_price = float(latest_candle['open'])
            high_price = float(latest_candle['high'])
            low_price = float(latest_candle['low'])
            close_price = float(latest_candle['close'])
            volume = float(latest_candle['volume'])
            
            # 计算K线特征 / Calculate candlestick features
            body_size = abs(close_price - open_price)
            upper_shadow = high_price - max(open_price, close_price)
            lower_shadow = min(open_price, close_price) - low_price
            total_range = high_price - low_price
            
            # 成交量比较 / Volume comparison
            prev_volume = float(prev_candle['volume'])
            volume_ratio = volume / prev_volume if prev_volume > 0 else 1.0
            
            # 反转信号类型检测 / Reversal signal type detection
            reversal_type = 'none'
            detected = False
            
            # 1. 放量阴线检测 / Volume bearish candle detection
            is_bearish = close_price < open_price
            is_high_volume = volume_ratio >= self.volume_multiplier
            
            if is_bearish and is_high_volume:
                reversal_type = 'volume_bearish'
                detected = True
            
            # 2. 上影线检测 / Upper shadow detection
            if total_range > 0:
                upper_shadow_ratio = upper_shadow / total_range
                if upper_shadow_ratio >= self.upper_shadow_ratio:
                    reversal_type = 'upper_shadow' if reversal_type == 'none' else 'volume_bearish_upper_shadow'
                    detected = True
            
            # 3. 顶部十字星检测 / Top doji detection
            if total_range > 0 and body_size / total_range < 0.1:
                reversal_type = 'doji' if reversal_type == 'none' else f"{reversal_type}_doji"
                detected = True
            
            # 修复：在暴涨行情中降低反转信号门槛 / Fix: lower reversal signal threshold in pump scenarios
            # 检查是否在高位（最近价格明显高于历史） / Check if at high levels
            if len(df) >= 10:
                recent_high = df.tail(10)['high'].max()
                historical_avg = df.head(len(df) - 10)['close'].mean() if len(df) > 10 else close_price
                
                if recent_high > historical_avg * 1.5:  # 如果最近高点比历史均价高50%以上 / If recent high is 50%+ above historical average
                    # 放宽反转条件 / Relax reversal conditions
                    if is_bearish or upper_shadow_ratio >= 0.2:  # 降低上影线要求 / Lower upper shadow requirement
                        reversal_type = 'high_level_reversal'
                        detected = True
            
            result = {
                'detected': detected,
                'type': reversal_type,
                'volume_ratio': volume_ratio,
                'upper_shadow_ratio': upper_shadow / total_range if total_range > 0 else 0,
                'body_ratio': body_size / total_range if total_range > 0 else 0,
                'debug_info': {
                    'is_bearish': is_bearish,
                    'is_high_volume': is_high_volume,
                    'upper_shadow_ratio': upper_shadow / total_range if total_range > 0 else 0
                }
            }
            
            # 详细调试日志 / Detailed debug logging
            self.logger.info(f"🔍 反转信号检测调试 / Reversal signal debug:")
            self.logger.info(f"  - 是否阴线 / Is bearish: {is_bearish}")
            self.logger.info(f"  - 成交量比 / Volume ratio: {volume_ratio:.2f}")
            self.logger.info(f"  - 上影线比例 / Upper shadow ratio: {result['upper_shadow_ratio']:.2%}")
            self.logger.info(f"  - 反转类型 / Reversal type: {reversal_type}")
            self.logger.info(f"  - 是否检测到反转 / Reversal detected: {detected}")
            
            if detected:
                self.logger.info(f"🔄 检测到反转信号 / Reversal signal detected: 类型 {reversal_type}, 成交量比 {volume_ratio:.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 反转检测失败 / Reversal detection failed: {str(e)}")
            return {'detected': False, 'type': 'error', 'volume_ratio': 0}
    
    def _generate_grid_positions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        模型3: 反转捕捉网格模型
        生成基于当前价格的加仓网格点位
        
        Args:
            df (pd.DataFrame): K线数据 / Candlestick data
            
        Returns:
            Dict[str, Any]: 网格加仓点位 / Grid add position points
        """
        try:
            current_price = float(df.iloc[-1]['close'])
            
            # 生成上涨加仓点位 / Generate upward add position points
            up_positions = []
            for i in range(1, self.max_add_times + 1):
                add_price = current_price * (1 + self.add_up_threshold * i)
                up_positions.append({
                    'type': 'add_on_up',
                    'trigger_price': add_price,
                    'add_ratio': 0.5,  # 每次加仓50%的初始仓位 / Add 50% of initial position each time
                    'sequence': i,
                    'description': f"上涨{self.add_up_threshold * i:.1%}加仓 / Add on {self.add_up_threshold * i:.1%} up"
                })
            
            # 生成下跌加仓点位 / Generate downward add position points  
            down_positions = []
            for i in range(1, self.max_add_times + 1):
                add_price = current_price * (1 - self.add_down_threshold * i)
                down_positions.append({
                    'type': 'add_on_down',
                    'trigger_price': add_price,
                    'add_ratio': 0.5,  # 每次加仓50%的初始仓位 / Add 50% of initial position each time
                    'sequence': i,
                    'description': f"下跌{self.add_down_threshold * i:.1%}加仓 / Add on {self.add_down_threshold * i:.1%} down"
                })
            
            # 合并所有加仓点位 / Combine all add position points
            all_positions = up_positions + down_positions
            
            # 按触发价格排序 / Sort by trigger price
            all_positions.sort(key=lambda x: x['trigger_price'])
            
            result = {
                'add_positions': all_positions,
                'up_positions': up_positions,
                'down_positions': down_positions,
                'total_positions': len(all_positions)
            }
            
            self.logger.info(f"📊 生成网格加仓点位 / Generated grid positions: 共 {len(all_positions)} 个点位")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 网格生成失败 / Grid generation failed: {str(e)}")
            return {'add_positions': [], 'up_positions': [], 'down_positions': [], 'total_positions': 0}
    
    def _calculate_signal_strength(self, pump_result: Dict, reversal_result: Dict) -> float:
        """
        计算信号强度 / Calculate signal strength
        
        Args:
            pump_result (Dict): 暴涨检测结果 / Pump detection result
            reversal_result (Dict): 反转检测结果 / Reversal detection result
            
        Returns:
            float: 信号强度，0-1之间 / Signal strength, between 0-1
        """
        try:
            strength = 0.0
            
            # 基础信号强度 / Base signal strength
            if pump_result['detected']:
                strength += 0.4
                
            if reversal_result['detected']:
                strength += 0.4
            
            # 暴涨幅度加成 / Pump magnitude bonus
            gain_bonus = min(pump_result.get('gain_rate', 0) / self.pump_threshold, 2.0) * 0.1
            strength += gain_bonus
            
            # 成交量确认加成 / Volume confirmation bonus
            volume_bonus = min(reversal_result.get('volume_ratio', 0) / self.volume_multiplier, 2.0) * 0.1
            strength += volume_bonus
            
            # 限制在0-1范围内 / Limit to 0-1 range
            return min(max(strength, 0.0), 1.0)
            
        except Exception as e:
            self.logger.error(f"❌ 信号强度计算失败 / Signal strength calculation failed: {str(e)}")
            return 0.0
    
    def _generate_empty_signal(self, reason: str) -> Dict[str, Any]:
        """
        生成空信号 / Generate empty signal
        
        Args:
            reason (str): 原因说明 / Reason description
            
        Returns:
            Dict[str, Any]: 空信号字典 / Empty signal dictionary
        """
        return {
            'has_pump_signal': False,
            'has_reversal_signal': False,
            'entry_price': 0.0,
            'add_positions': [],
            'stop_loss_price': 0.0,
            'take_profit_price': 0.0,
            'signal_strength': 0.0,
            'metadata': {
                'reason': reason,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
    
    def check_stop_loss(self, entry_price: float, current_price: float) -> Tuple[bool, str]:
        """
        检查止损条件 / Check stop loss condition
        
        Args:
            entry_price (float): 入场价格 / Entry price
            current_price (float): 当前价格 / Current price
            
        Returns:
            Tuple[bool, str]: (是否触发止损, 原因) / (Whether triggered stop loss, reason)
        """
        try:
            if entry_price <= 0:
                return False, "无效入场价格 / Invalid entry price"
            
            # 计算价格变化率 / Calculate price change rate
            price_change = (current_price - entry_price) / entry_price
            
            # 做空止损：当前价格超过入场价35% / Short stop loss: current price exceeds entry price by 35%
            if price_change >= self.stop_loss_threshold:
                return True, f"价格止损触发: 上涨 {price_change:.2%} / Price stop loss: up {price_change:.2%}"
            
            return False, "未达到止损条件 / Stop loss condition not met"
            
        except Exception as e:
            self.logger.error(f"❌ 止损检查失败 / Stop loss check failed: {str(e)}")
            return False, f"错误: {str(e)} / Error: {str(e)}"
    
    def check_take_profit(self, entry_price: float, current_price: float) -> Tuple[bool, str]:
        """
        检查止盈条件 / Check take profit condition
        
        Args:
            entry_price (float): 入场价格 / Entry price
            current_price (float): 当前价格 / Current price
            
        Returns:
            Tuple[bool, str]: (是否触发止盈, 原因) / (Whether triggered take profit, reason)
        """
        try:
            if entry_price <= 0:
                return False, "无效入场价格 / Invalid entry price"
            
            # 计算价格变化率 / Calculate price change rate
            price_change = (entry_price - current_price) / entry_price
            
            # 做空止盈：当前价格低于入场价12% / Short take profit: current price below entry price by 12%
            if price_change >= self.take_profit_threshold:
                return True, f"止盈触发: 下跌 {price_change:.2%} / Take profit: down {price_change:.2%}"
            
            return False, "未达到止盈条件 / Take profit condition not met"
            
        except Exception as e:
            self.logger.error(f"❌ 止盈检查失败 / Take profit check failed: {str(e)}")
            return False, f"错误: {str(e)} / Error: {str(e)}"
    
    def should_add_position(self, entry_price: float, current_price: float, 
                          existing_adds: int, position_type: str = 'up') -> Tuple[bool, Dict]:
        """
        判断是否应该加仓 / Determine if should add position
        
        Args:
            entry_price (float): 入场价格 / Entry price
            current_price (float): 当前价格 / Current price
            existing_adds (int): 已有加仓次数 / Existing add times
            position_type (str): 加仓类型 'up' 或 'down' / Add type 'up' or 'down'
            
        Returns:
            Tuple[bool, Dict]: (是否加仓, 加仓信息) / (Whether add position, add info)
        """
        try:
            if entry_price <= 0 or existing_adds >= self.max_add_times:
                return False, {}
            
            # 计算价格变化率 / Calculate price change rate
            price_change = (current_price - entry_price) / entry_price
            
            # 计算应该触发的加仓级别 / Calculate add level that should trigger
            if position_type == 'up':
                # 上涨加仓 / Add on up
                required_change = self.add_up_threshold * (existing_adds + 1)
                if price_change >= required_change:
                    add_info = {
                        'type': 'add_on_up',
                        'trigger_price': current_price,
                        'add_ratio': 0.5,
                        'sequence': existing_adds + 1,
                        'price_change': price_change,
                        'description': f"第{existing_adds + 1}次上涨加仓 / {existing_adds + 1}th add on up"
                    }
                    return True, add_info
            else:
                # 下跌加仓 / Add on down
                required_change = -self.add_down_threshold * (existing_adds + 1)
                if price_change <= required_change:
                    add_info = {
                        'type': 'add_on_down',
                        'trigger_price': current_price,
                        'add_ratio': 0.5,
                        'sequence': existing_adds + 1,
                        'price_change': price_change,
                        'description': f"第{existing_adds + 1}次下跌加仓 / {existing_adds + 1}th add on down"
                    }
                    return True, add_info
            
            return False, {}
            
        except Exception as e:
            self.logger.error(f"❌ 加仓判断失败 / Add position judgment failed: {str(e)}")
            return False, {} 