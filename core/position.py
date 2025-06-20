# -*- coding: utf-8 -*-
"""
持仓管理模块 / Position Management Module
====================================

本模块负责管理单个交易持仓的完整生命周期，包括：
This module manages the complete lifecycle of individual trading positions, including:

1. 初始建仓记录 / Initial position recording
2. 加仓操作管理 / Add position operations management  
3. 持仓均价计算 / Average position price calculation
4. 实时盈亏计算 / Real-time P&L calculation
5. 止盈止损判断 / Take profit and stop loss judgment

关联文件 / Related Files:
- strategies/pump_short_strategy.py: 策略信号生成 / Strategy signal generation
- core/portfolio.py: 投资组合管理 / Portfolio management
- core/executor.py: 交易执行器 / Trade executor

主要功能 / Main Functions:
1. 记录每次加仓的价格、数量、时间 / Record price, quantity, time of each add
2. 动态计算持仓均价和总数量 / Dynamically calculate average price and total quantity
3. 实时监控盈亏状态 / Real-time P&L monitoring
4. 支持部分平仓和全部平仓 / Support partial and full position closing
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from enum import Enum

class PositionStatus(Enum):
    """持仓状态枚举 / Position Status Enum"""
    ACTIVE = "active"        # 活跃持仓 / Active position
    CLOSED = "closed"        # 已平仓 / Closed position
    STOPPED = "stopped"      # 止损平仓 / Stop loss closed
    PROFIT_TAKEN = "profit_taken"  # 止盈平仓 / Take profit closed

class PositionType(Enum):
    """持仓类型枚举 / Position Type Enum"""
    LONG = "long"    # 多头持仓 / Long position
    SHORT = "short"  # 空头持仓 / Short position

class Position:
    """
    持仓类 / Position Class
    
    管理单个交易持仓的完整生命周期，记录所有交易操作和盈亏状态。
    Manages the complete lifecycle of a single trading position, recording all trading operations and P&L status.
    """
    
    def __init__(self, symbol: str, position_type: PositionType, 
                 initial_price: float, initial_quantity: float, 
                 timestamp: Optional[datetime] = None):
        """
        初始化持仓实例 / Initialize position instance
        
        Args:
            symbol (str): 交易标的符号 / Trading symbol
            position_type (PositionType): 持仓类型（多头/空头） / Position type (long/short)
            initial_price (float): 初始建仓价格 / Initial position price
            initial_quantity (float): 初始建仓数量 / Initial position quantity
            timestamp (datetime, optional): 建仓时间 / Position timestamp
        """
        # 基本信息 / Basic information
        self.symbol = symbol
        self.position_type = position_type
        self.status = PositionStatus.ACTIVE
        self.created_at = timestamp if timestamp else datetime.now()
        
        # 持仓记录 / Position records
        self.entries = []  # 所有建仓记录 / All entry records
        self.exits = []    # 所有平仓记录 / All exit records
        
        # 添加初始建仓记录 / Add initial position record
        self._add_entry(initial_price, initial_quantity, self.created_at, "initial")
        
        # 统计信息 / Statistics
        self.total_quantity = initial_quantity
        self.remaining_quantity = initial_quantity
        self.average_price = initial_price
        self.realized_pnl = 0.0  # 已实现盈亏 / Realized P&L
        self.unrealized_pnl = 0.0  # 未实现盈亏 / Unrealized P&L
        
        # 加仓统计 / Add position statistics
        self.add_up_count = 0    # 上涨加仓次数 / Add on up count
        self.add_down_count = 0  # 下跌加仓次数 / Add on down count
        self.max_unrealized_profit = 0.0  # 最大未实现盈利 / Max unrealized profit
        self.max_unrealized_loss = 0.0    # 最大未实现亏损 / Max unrealized loss
        
        # 日志记录器 / Logger
        self.logger = self._setup_logger()
        
        self.logger.info(f"📊 创建{position_type.value}持仓 / Created {position_type.value} position: "
                        f"{symbol} @ {initial_price:.6f} x {initial_quantity:.2f}")
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器 / Setup logger"""
        logger = logging.getLogger(f'Position-{self.symbol}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _add_entry(self, price: float, quantity: float, timestamp: datetime, entry_type: str):
        """
        添加建仓记录 / Add entry record
        
        Args:
            price (float): 建仓价格 / Entry price
            quantity (float): 建仓数量 / Entry quantity
            timestamp (datetime): 建仓时间 / Entry timestamp
            entry_type (str): 建仓类型 / Entry type
        """
        entry_record = {
            'price': price,
            'quantity': quantity,
            'timestamp': timestamp,
            'entry_type': entry_type,
            'value': price * quantity
        }
        
        self.entries.append(entry_record)
        
        # 更新持仓统计 / Update position statistics
        if entry_type != "initial":
            if entry_type == "add_on_up":
                self.add_up_count += 1
            elif entry_type == "add_on_down":
                self.add_down_count += 1
    
    def add_position(self, price: float, quantity: float, add_type: str, 
                    timestamp: Optional[datetime] = None) -> bool:
        """
        加仓操作 / Add position operation
        
        Args:
            price (float): 加仓价格 / Add position price
            quantity (float): 加仓数量 / Add position quantity
            add_type (str): 加仓类型 ("add_on_up", "add_on_down") / Add type
            timestamp (datetime, optional): 加仓时间 / Add timestamp
            
        Returns:
            bool: 加仓是否成功 / Whether add position successful
        """
        try:
            if self.status != PositionStatus.ACTIVE:
                self.logger.warning(f"⚠️ 持仓已关闭，无法加仓 / Position closed, cannot add")
                return False
            
            if price <= 0 or quantity <= 0:
                self.logger.error(f"❌ 无效的加仓参数 / Invalid add parameters: price={price}, quantity={quantity}")
                return False
            
            # 记录加仓 / Record add position
            add_timestamp = timestamp if timestamp else datetime.now()
            self._add_entry(price, quantity, add_timestamp, add_type)
            
            # 更新持仓统计 / Update position statistics
            old_total_value = self.average_price * self.total_quantity
            new_total_value = old_total_value + (price * quantity)
            self.total_quantity += quantity
            self.remaining_quantity += quantity
            self.average_price = new_total_value / self.total_quantity
            
            self.logger.info(f"➕ 加仓成功 / Add position successful: {add_type} @ {price:.6f} x {quantity:.2f}, "
                           f"新均价 {self.average_price:.6f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 加仓失败 / Add position failed: {str(e)}")
            return False
    
    def close_position(self, price: float, quantity: Optional[float] = None, 
                      close_reason: str = "manual", timestamp: Optional[datetime] = None) -> bool:
        """
        平仓操作 / Close position operation
        
        Args:
            price (float): 平仓价格 / Close price
            quantity (float, optional): 平仓数量，None表示全部平仓 / Close quantity, None means close all
            close_reason (str): 平仓原因 / Close reason
            timestamp (datetime, optional): 平仓时间 / Close timestamp
            
        Returns:
            bool: 平仓是否成功 / Whether close position successful
        """
        try:
            if self.status != PositionStatus.ACTIVE:
                self.logger.warning(f"⚠️ 持仓已关闭 / Position already closed")
                return False
            
            if price <= 0:
                self.logger.error(f"❌ 无效的平仓价格 / Invalid close price: {price}")
                return False
            
            # 确定平仓数量 / Determine close quantity
            close_quantity = quantity if quantity is not None else self.remaining_quantity
            
            if close_quantity <= 0 or close_quantity > self.remaining_quantity:
                self.logger.error(f"❌ 无效的平仓数量 / Invalid close quantity: {close_quantity}")
                return False
            
            # 记录平仓 / Record close position
            close_timestamp = timestamp if timestamp else datetime.now()
            close_record = {
                'price': price,
                'quantity': close_quantity,
                'timestamp': close_timestamp,
                'close_reason': close_reason,
                'value': price * close_quantity
            }
            
            self.exits.append(close_record)
            
            # 计算平仓盈亏 / Calculate close P&L
            if self.position_type == PositionType.SHORT:
                # 空头：建仓价格高于平仓价格为盈利 / Short: profit when entry price > close price
                pnl = (self.average_price - price) * close_quantity
            else:
                # 多头：平仓价格高于建仓价格为盈利 / Long: profit when close price > entry price
                pnl = (price - self.average_price) * close_quantity
            
            self.realized_pnl += pnl
            self.remaining_quantity -= close_quantity
            
            # 更新持仓状态 / Update position status
            if self.remaining_quantity <= 1e-8:  # 基本为0 / Essentially zero
                self.remaining_quantity = 0
                if close_reason == "stop_loss":
                    self.status = PositionStatus.STOPPED
                elif close_reason == "take_profit":
                    self.status = PositionStatus.PROFIT_TAKEN
                else:
                    self.status = PositionStatus.CLOSED
            
            self.logger.info(f"➖ 平仓成功 / Close position successful: @ {price:.6f} x {close_quantity:.2f}, "
                           f"盈亏 {pnl:.2f}, 原因: {close_reason}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 平仓失败 / Close position failed: {str(e)}")
            return False
    
    def update_unrealized_pnl(self, current_price: float) -> float:
        """
        更新未实现盈亏 / Update unrealized P&L
        
        Args:
            current_price (float): 当前市价 / Current market price
            
        Returns:
            float: 未实现盈亏金额 / Unrealized P&L amount
        """
        try:
            if self.remaining_quantity <= 0:
                self.unrealized_pnl = 0.0
                return 0.0
            
            # 计算未实现盈亏 / Calculate unrealized P&L
            if self.position_type == PositionType.SHORT:
                # 空头：建仓价格高于当前价格为盈利 / Short: profit when entry price > current price
                self.unrealized_pnl = (self.average_price - current_price) * self.remaining_quantity
            else:
                # 多头：当前价格高于建仓价格为盈利 / Long: profit when current price > entry price
                self.unrealized_pnl = (current_price - self.average_price) * self.remaining_quantity
            
            # 更新最大盈亏记录 / Update max profit/loss records
            if self.unrealized_pnl > self.max_unrealized_profit:
                self.max_unrealized_profit = self.unrealized_pnl
            elif self.unrealized_pnl < self.max_unrealized_loss:
                self.max_unrealized_loss = self.unrealized_pnl
            
            return self.unrealized_pnl
            
        except Exception as e:
            self.logger.error(f"❌ 更新盈亏失败 / Update P&L failed: {str(e)}")
            return 0.0
    
    def get_total_pnl(self, current_price: Optional[float] = None) -> float:
        """
        获取总盈亏（已实现+未实现） / Get total P&L (realized + unrealized)
        
        Args:
            current_price (float, optional): 当前价格，用于计算未实现盈亏 / Current price for unrealized P&L
            
        Returns:
            float: 总盈亏金额 / Total P&L amount
        """
        total_pnl = self.realized_pnl
        
        if current_price is not None and self.remaining_quantity > 0:
            self.update_unrealized_pnl(current_price)
            total_pnl += self.unrealized_pnl
        
        return total_pnl
    
    def get_return_rate(self, current_price: Optional[float] = None) -> float:
        """
        获取收益率 / Get return rate
        
        Args:
            current_price (float, optional): 当前价格 / Current price
            
        Returns:
            float: 收益率（小数形式） / Return rate (decimal form)
        """
        try:
            total_investment = sum(entry['value'] for entry in self.entries)
            if total_investment <= 0:
                return 0.0
            
            total_pnl = self.get_total_pnl(current_price)
            return total_pnl / total_investment
            
        except Exception as e:
            self.logger.error(f"❌ 计算收益率失败 / Calculate return rate failed: {str(e)}")
            return 0.0
    
    def get_position_summary(self, current_price: Optional[float] = None) -> Dict[str, Any]:
        """
        获取持仓摘要信息 / Get position summary
        
        Args:
            current_price (float, optional): 当前价格 / Current price
            
        Returns:
            Dict[str, Any]: 持仓摘要字典 / Position summary dictionary
        """
        # 更新未实现盈亏 / Update unrealized P&L
        if current_price is not None:
            self.update_unrealized_pnl(current_price)
        
        summary = {
            # 基本信息 / Basic information
            'symbol': self.symbol,
            'position_type': self.position_type.value,
            'status': self.status.value,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            
            # 持仓数量 / Position quantity
            'total_quantity': self.total_quantity,
            'remaining_quantity': self.remaining_quantity,
            'average_price': self.average_price,
            
            # 盈亏信息 / P&L information
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'total_pnl': self.realized_pnl + self.unrealized_pnl,
            'return_rate': self.get_return_rate(current_price),
            
            # 统计信息 / Statistics
            'total_entries': len(self.entries),
            'total_exits': len(self.exits),
            'add_up_count': self.add_up_count,
            'add_down_count': self.add_down_count,
            'max_unrealized_profit': self.max_unrealized_profit,
            'max_unrealized_loss': self.max_unrealized_loss,
            
            # 成本信息 / Cost information
            'total_investment': sum(entry['value'] for entry in self.entries),
            'current_market_value': self.remaining_quantity * current_price if current_price else 0,
            
            # 当前价格 / Current price
            'current_price': current_price
        }
        
        return summary
    
    def get_trade_history(self) -> Dict[str, List[Dict]]:
        """
        获取完整的交易历史 / Get complete trade history
        
        Returns:
            Dict[str, List[Dict]]: 包含建仓和平仓记录的字典 / Dictionary containing entry and exit records
        """
        return {
            'entries': self.entries.copy(),
            'exits': self.exits.copy()
        }
    
    def is_active(self) -> bool:
        """
        判断持仓是否活跃 / Check if position is active
        
        Returns:
            bool: 持仓是否活跃 / Whether position is active
        """
        return self.status == PositionStatus.ACTIVE and self.remaining_quantity > 0
    
    def get_duration(self, end_time: Optional[datetime] = None) -> timedelta:
        """
        获取持仓持续时间 / Get position duration
        
        Args:
            end_time (datetime, optional): 结束时间，默认为当前时间 / End time, default to current time
            
        Returns:
            timedelta: 持仓持续时间 / Position duration
        """
        end_time = end_time if end_time else datetime.now()
        return end_time - self.created_at
    
    def __str__(self) -> str:
        """字符串表示 / String representation"""
        return (f"Position({self.symbol}, {self.position_type.value}, "
                f"avg_price={self.average_price:.6f}, qty={self.remaining_quantity:.2f}, "
                f"status={self.status.value})")
    
    def __repr__(self) -> str:
        """详细字符串表示 / Detailed string representation"""
        return self.__str__() 