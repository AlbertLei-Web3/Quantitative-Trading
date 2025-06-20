# -*- coding: utf-8 -*-
"""
投资组合管理模块 / Portfolio Management Module
==========================================

本模块负责管理整个投资组合的资金分配、风险控制和多持仓协调，包括：
This module manages portfolio fund allocation, risk control and multi-position coordination, including:

1. 多持仓统一管理 / Unified multi-position management
2. 资金分配和风险控制 / Fund allocation and risk control
3. 整体盈亏统计 / Overall P&L statistics
4. 持仓集合操作 / Position set operations
5. 风险指标监控 / Risk indicator monitoring

关联文件 / Related Files:
- core/position.py: 单个持仓管理 / Individual position management
- strategies/pump_short_strategy.py: 策略信号生成 / Strategy signal generation
- core/executor.py: 交易执行器 / Trade executor

主要功能 / Main Functions:
1. 统一管理多个交易标的的持仓 / Manage multiple trading symbol positions
2. 动态分配资金给不同持仓 / Dynamically allocate funds to different positions
3. 监控整体风险敞口 / Monitor overall risk exposure
4. 计算组合级别的绩效指标 / Calculate portfolio-level performance metrics
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from collections import defaultdict

from .position import Position, PositionType, PositionStatus

class RiskManager:
    """
    风险管理器 / Risk Manager
    
    负责控制投资组合的整体风险，包括单个持仓限制、总体敞口控制等。
    Responsible for controlling overall portfolio risk, including individual position limits, total exposure control, etc.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化风险管理器 / Initialize risk manager
        
        Args:
            config (Dict): 风险管理配置 / Risk management configuration
        """
        # 风险控制参数 / Risk control parameters
        self.max_position_size_ratio = config.get('max_position_size_ratio', 0.1)  # 单个持仓最大资金比例10% / Max single position ratio 10%
        self.max_total_exposure_ratio = config.get('max_total_exposure_ratio', 0.8)  # 总敞口最大比例80% / Max total exposure ratio 80%
        self.max_concurrent_positions = config.get('max_concurrent_positions', 5)  # 最大同时持仓数 / Max concurrent positions
        self.max_correlation_positions = config.get('max_correlation_positions', 3)  # 最大相关性持仓数 / Max correlated positions
        
        # 风险监控阈值 / Risk monitoring thresholds
        self.portfolio_stop_loss_ratio = config.get('portfolio_stop_loss_ratio', 0.15)  # 组合止损比例15% / Portfolio stop loss ratio 15%
        self.single_position_max_loss_ratio = config.get('single_position_max_loss_ratio', 0.05)  # 单持仓最大亏损5% / Single position max loss ratio 5%
        
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器 / Setup logger"""
        logger = logging.getLogger('RiskManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def check_position_size_limit(self, portfolio_value: float, position_value: float) -> Tuple[bool, str]:
        """
        检查单个持仓大小限制 / Check individual position size limit
        
        Args:
            portfolio_value (float): 投资组合总价值 / Portfolio total value
            position_value (float): 持仓价值 / Position value
            
        Returns:
            Tuple[bool, str]: (是否通过检查, 原因) / (Whether passed check, reason)
        """
        if portfolio_value <= 0:
            return False, "投资组合价值无效 / Invalid portfolio value"
        
        position_ratio = position_value / portfolio_value
        
        if position_ratio > self.max_position_size_ratio:
            return False, f"持仓超过最大比例限制 {self.max_position_size_ratio:.1%} / Position exceeds max ratio limit {self.max_position_size_ratio:.1%}"
        
        return True, "通过单持仓大小检查 / Passed single position size check"
    
    def check_total_exposure_limit(self, portfolio_value: float, total_exposure: float) -> Tuple[bool, str]:
        """
        检查总敞口限制 / Check total exposure limit
        
        Args:
            portfolio_value (float): 投资组合总价值 / Portfolio total value
            total_exposure (float): 总敞口 / Total exposure
            
        Returns:
            Tuple[bool, str]: (是否通过检查, 原因) / (Whether passed check, reason)
        """
        if portfolio_value <= 0:
            return False, "投资组合价值无效 / Invalid portfolio value"
        
        exposure_ratio = total_exposure / portfolio_value
        
        if exposure_ratio > self.max_total_exposure_ratio:
            return False, f"总敞口超过限制 {self.max_total_exposure_ratio:.1%} / Total exposure exceeds limit {self.max_total_exposure_ratio:.1%}"
        
        return True, "通过总敞口检查 / Passed total exposure check"

class Portfolio:
    """
    投资组合类 / Portfolio Class
    
    管理整个投资组合的所有持仓、资金分配和风险控制。
    Manages all positions, fund allocation, and risk control of the entire portfolio.
    """
    
    def __init__(self, initial_capital: float, config: Dict[str, Any]):
        """
        初始化投资组合 / Initialize portfolio
        
        Args:
            initial_capital (float): 初始资金 / Initial capital
            config (Dict): 投资组合配置 / Portfolio configuration
        """
        # 基本信息 / Basic information
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.created_at = datetime.now()
        
        # 持仓管理 / Position management
        self.positions: Dict[str, Position] = {}  # 活跃持仓 symbol -> Position / Active positions
        self.closed_positions: List[Position] = []  # 已平仓持仓历史 / Closed positions history
        
        # 风险管理 / Risk management
        self.risk_manager = RiskManager(config.get('risk_management', {}))
        
        # 统计信息 / Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_fees = 0.0
        self.max_drawdown = 0.0
        self.peak_value = initial_capital
        
        # 性能指标 / Performance metrics
        self.daily_returns = []  # 每日收益率 / Daily returns
        self.equity_curve = [initial_capital]  # 净值曲线 / Equity curve
        self.timestamps = [datetime.now()]  # 时间戳 / Timestamps
        
        # 配置参数 / Configuration parameters
        self.fee_rate = config.get('fee_rate', 0.001)  # 手续费率0.1% / Fee rate 0.1%
        self.slippage_rate = config.get('slippage_rate', 0.0005)  # 滑点0.05% / Slippage rate 0.05%
        
        self.logger = self._setup_logger()
        
        self.logger.info(f"💼 创建投资组合 / Created portfolio: 初始资金 ${initial_capital:,.2f}")
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器 / Setup logger"""
        logger = logging.getLogger('Portfolio')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def get_portfolio_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        获取投资组合当前价值 / Get current portfolio value
        
        Args:
            current_prices (Dict[str, float], optional): 当前价格字典 / Current prices dictionary
            
        Returns:
            float: 投资组合总价值 / Total portfolio value
        """
        total_value = self.cash
        
        for symbol, position in self.positions.items():
            if position.is_active():
                current_price = current_prices.get(symbol) if current_prices else None
                if current_price is not None:
                    # 更新持仓市值 / Update position market value
                    market_value = position.remaining_quantity * current_price
                    total_value += market_value
                else:
                    # 使用平均价格作为估值 / Use average price as valuation
                    total_value += position.remaining_quantity * position.average_price
        
        return total_value
    
    def get_available_cash(self, reserved_ratio: float = 0.1) -> float:
        """
        获取可用现金 / Get available cash
        
        Args:
            reserved_ratio (float): 保留现金比例 / Reserved cash ratio
            
        Returns:
            float: 可用现金金额 / Available cash amount
        """
        portfolio_value = self.get_portfolio_value()
        reserved_cash = portfolio_value * reserved_ratio
        return max(self.cash - reserved_cash, 0)
    
    def create_position(self, symbol: str, position_type: PositionType, 
                       entry_price: float, quantity: float, 
                       timestamp: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        创建新持仓 / Create new position
        
        Args:
            symbol (str): 交易标的 / Trading symbol
            position_type (PositionType): 持仓类型 / Position type
            entry_price (float): 入场价格 / Entry price
            quantity (float): 持仓数量 / Position quantity
            timestamp (datetime, optional): 时间戳 / Timestamp
            
        Returns:
            Tuple[bool, str]: (是否成功, 原因) / (Whether successful, reason)
        """
        try:
            # 检查是否已有该标的的持仓 / Check if position already exists for this symbol
            if symbol in self.positions:
                return False, f"标的 {symbol} 已存在活跃持仓 / Active position already exists for symbol {symbol}"
            
            # 计算持仓价值 / Calculate position value
            position_value = entry_price * quantity
            
            # 风险检查 / Risk checks
            portfolio_value = self.get_portfolio_value()
            
            # 1. 检查持仓大小限制 / Check position size limit
            size_check, size_reason = self.risk_manager.check_position_size_limit(portfolio_value, position_value)
            if not size_check:
                return False, size_reason
            
            # 2. 检查现金是否充足 / Check if cash is sufficient
            total_cost = position_value * (1 + self.fee_rate + self.slippage_rate)
            if total_cost > self.cash:
                return False, f"现金不足 / Insufficient cash: 需要 ${total_cost:,.2f}, 可用 ${self.cash:,.2f}"
            
            # 3. 检查总敞口限制 / Check total exposure limit
            current_exposure = sum(pos.remaining_quantity * pos.average_price for pos in self.positions.values())
            total_exposure = current_exposure + position_value
            exposure_check, exposure_reason = self.risk_manager.check_total_exposure_limit(portfolio_value, total_exposure)
            if not exposure_check:
                return False, exposure_reason
            
            # 4. 检查最大持仓数限制 / Check max concurrent positions limit
            if len(self.positions) >= self.risk_manager.max_concurrent_positions:
                return False, f"超过最大持仓数限制 {self.risk_manager.max_concurrent_positions} / Exceeds max concurrent positions {self.risk_manager.max_concurrent_positions}"
            
            # 创建持仓 / Create position
            position = Position(symbol, position_type, entry_price, quantity, timestamp)
            self.positions[symbol] = position
            
            # 更新现金和统计 / Update cash and statistics
            self.cash -= total_cost
            self.total_trades += 1
            self.total_fees += position_value * self.fee_rate
            
            self.logger.info(f"🎯 创建持仓成功 / Position created successfully: {symbol} {position_type.value} @ {entry_price:.6f} x {quantity:.2f}")
            
            return True, "持仓创建成功 / Position created successfully"
            
        except Exception as e:
            error_msg = f"创建持仓失败 / Position creation failed: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def add_to_position(self, symbol: str, price: float, quantity: float, 
                       add_type: str, timestamp: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        向现有持仓加仓 / Add to existing position
        
        Args:
            symbol (str): 交易标的 / Trading symbol
            price (float): 加仓价格 / Add price
            quantity (float): 加仓数量 / Add quantity
            add_type (str): 加仓类型 / Add type
            timestamp (datetime, optional): 时间戳 / Timestamp
            
        Returns:
            Tuple[bool, str]: (是否成功, 原因) / (Whether successful, reason)
        """
        try:
            # 检查持仓是否存在 / Check if position exists
            if symbol not in self.positions:
                return False, f"标的 {symbol} 不存在活跃持仓 / No active position exists for symbol {symbol}"
            
            position = self.positions[symbol]
            
            if not position.is_active():
                return False, f"持仓 {symbol} 已关闭 / Position {symbol} is closed"
            
            # 计算加仓成本 / Calculate add cost
            add_value = price * quantity
            total_cost = add_value * (1 + self.fee_rate + self.slippage_rate)
            
            # 检查现金是否充足 / Check if cash is sufficient
            if total_cost > self.cash:
                return False, f"现金不足 / Insufficient cash: 需要 ${total_cost:,.2f}, 可用 ${self.cash:,.2f}"
            
            # 风险检查：加仓后的持仓大小 / Risk check: position size after adding
            new_total_value = (position.remaining_quantity * position.average_price) + add_value
            portfolio_value = self.get_portfolio_value()
            size_check, size_reason = self.risk_manager.check_position_size_limit(portfolio_value, new_total_value)
            if not size_check:
                return False, size_reason
            
            # 执行加仓 / Execute add position
            success = position.add_position(price, quantity, add_type, timestamp)
            if not success:
                return False, "持仓加仓操作失败 / Position add operation failed"
            
            # 更新现金和统计 / Update cash and statistics
            self.cash -= total_cost
            self.total_fees += add_value * self.fee_rate
            
            self.logger.info(f"➕ 加仓成功 / Add position successful: {symbol} {add_type} @ {price:.6f} x {quantity:.2f}")
            
            return True, "加仓成功 / Add position successful"
            
        except Exception as e:
            error_msg = f"加仓失败 / Add position failed: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def close_position(self, symbol: str, price: float, quantity: Optional[float] = None,
                      close_reason: str = "manual", timestamp: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        平仓操作 / Close position operation
        
        Args:
            symbol (str): 交易标的 / Trading symbol
            price (float): 平仓价格 / Close price
            quantity (float, optional): 平仓数量 / Close quantity
            close_reason (str): 平仓原因 / Close reason
            timestamp (datetime, optional): 时间戳 / Timestamp
            
        Returns:
            Tuple[bool, str]: (是否成功, 原因) / (Whether successful, reason)
        """
        try:
            # 检查持仓是否存在 / Check if position exists
            if symbol not in self.positions:
                return False, f"标的 {symbol} 不存在活跃持仓 / No active position exists for symbol {symbol}"
            
            position = self.positions[symbol]
            
            if not position.is_active():
                return False, f"持仓 {symbol} 已关闭 / Position {symbol} is closed"
            
            # 确定平仓数量 / Determine close quantity
            close_quantity = quantity if quantity is not None else position.remaining_quantity
            
            # 计算平仓收入 / Calculate close proceeds
            close_value = price * close_quantity
            net_proceeds = close_value * (1 - self.fee_rate - self.slippage_rate)
            
            # 执行平仓 / Execute close position
            success = position.close_position(price, close_quantity, close_reason, timestamp)
            if not success:
                return False, "持仓平仓操作失败 / Position close operation failed"
            
            # 更新现金和统计 / Update cash and statistics
            self.cash += net_proceeds
            self.total_fees += close_value * self.fee_rate
            
            # 如果完全平仓，移动到历史持仓 / If fully closed, move to closed positions
            if position.remaining_quantity <= 1e-8:
                self.closed_positions.append(position)
                del self.positions[symbol]
                
                # 更新交易统计 / Update trade statistics
                if position.realized_pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
            
            self.logger.info(f"➖ 平仓成功 / Close position successful: {symbol} @ {price:.6f} x {close_quantity:.2f}, "
                           f"原因: {close_reason}")
            
            return True, "平仓成功 / Close position successful"
            
        except Exception as e:
            error_msg = f"平仓失败 / Close position failed: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def update_portfolio(self, current_prices: Dict[str, float], timestamp: Optional[datetime] = None):
        """
        更新投资组合状态 / Update portfolio status
        
        Args:
            current_prices (Dict[str, float]): 当前价格字典 / Current prices dictionary
            timestamp (datetime, optional): 时间戳 / Timestamp
        """
        try:
            # 更新所有持仓的未实现盈亏 / Update unrealized P&L for all positions
            for symbol, position in self.positions.items():
                if symbol in current_prices:
                    position.update_unrealized_pnl(current_prices[symbol])
            
            # 计算当前组合价值 / Calculate current portfolio value
            current_value = self.get_portfolio_value(current_prices)
            
            # 更新净值曲线 / Update equity curve
            self.equity_curve.append(current_value)
            self.timestamps.append(timestamp if timestamp else datetime.now())
            
            # 计算日收益率 / Calculate daily return
            if len(self.equity_curve) > 1:
                daily_return = (current_value - self.equity_curve[-2]) / self.equity_curve[-2]
                self.daily_returns.append(daily_return)
            
            # 更新最大回撤 / Update max drawdown
            if current_value > self.peak_value:
                self.peak_value = current_value
            
            current_drawdown = 1 - (current_value / self.peak_value)
            if current_drawdown > self.max_drawdown:
                self.max_drawdown = current_drawdown
            
        except Exception as e:
            self.logger.error(f"❌ 更新投资组合失败 / Update portfolio failed: {str(e)}")
    
    def get_portfolio_summary(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        获取投资组合摘要 / Get portfolio summary
        
        Args:
            current_prices (Dict[str, float], optional): 当前价格字典 / Current prices dictionary
            
        Returns:
            Dict[str, Any]: 投资组合摘要 / Portfolio summary
        """
        try:
            # 更新投资组合状态 / Update portfolio status
            if current_prices:
                self.update_portfolio(current_prices)
            
            current_value = self.get_portfolio_value(current_prices)
            total_pnl = current_value - self.initial_capital
            total_return = total_pnl / self.initial_capital
            
            # 计算性能指标 / Calculate performance metrics
            win_rate = self.winning_trades / max(self.winning_trades + self.losing_trades, 1)
            
            # 计算夏普比率 / Calculate Sharpe ratio
            sharpe_ratio = 0.0
            if len(self.daily_returns) > 1:
                returns_array = np.array(self.daily_returns)
                if returns_array.std() > 0:
                    sharpe_ratio = returns_array.mean() / returns_array.std() * np.sqrt(252)  # 年化夏普比率 / Annualized Sharpe ratio
            
            # 活跃持仓统计 / Active positions statistics
            active_positions = []
            total_unrealized_pnl = 0.0
            for symbol, position in self.positions.items():
                if position.is_active():
                    current_price = current_prices.get(symbol) if current_prices else None
                    position_summary = position.get_position_summary(current_price)
                    active_positions.append(position_summary)
                    total_unrealized_pnl += position.unrealized_pnl
            
            # 已平仓持仓统计 / Closed positions statistics
            total_realized_pnl = sum(pos.realized_pnl for pos in self.closed_positions)
            
            summary = {
                # 基本信息 / Basic information
                'initial_capital': self.initial_capital,
                'current_value': current_value,
                'cash': self.cash,
                'total_pnl': total_pnl,
                'total_return': total_return,
                
                # 持仓统计 / Position statistics
                'active_positions_count': len(self.positions),
                'closed_positions_count': len(self.closed_positions),
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': win_rate,
                
                # 盈亏统计 / P&L statistics
                'realized_pnl': total_realized_pnl,
                'unrealized_pnl': total_unrealized_pnl,
                'total_fees': self.total_fees,
                
                # 风险指标 / Risk indicators
                'max_drawdown': self.max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                
                # 详细持仓 / Detailed positions
                'active_positions': active_positions,
                
                # 时间信息 / Time information
                'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'last_updated': self.timestamps[-1].strftime('%Y-%m-%d %H:%M:%S') if self.timestamps else None
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"❌ 获取投资组合摘要失败 / Get portfolio summary failed: {str(e)}")
            return {}
    
    def get_risk_metrics(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        获取风险指标 / Get risk metrics
        
        Args:
            current_prices (Dict[str, float], optional): 当前价格字典 / Current prices dictionary
            
        Returns:
            Dict[str, Any]: 风险指标字典 / Risk metrics dictionary
        """
        try:
            portfolio_value = self.get_portfolio_value(current_prices)
            
            # 计算总敞口 / Calculate total exposure
            total_exposure = sum(pos.remaining_quantity * pos.average_price for pos in self.positions.values())
            exposure_ratio = total_exposure / portfolio_value if portfolio_value > 0 else 0
            
            # 计算单个持仓最大占比 / Calculate max single position ratio
            max_position_ratio = 0.0
            if self.positions and portfolio_value > 0:
                max_position_value = max(pos.remaining_quantity * pos.average_price for pos in self.positions.values())
                max_position_ratio = max_position_value / portfolio_value
            
            # 计算VaR (Value at Risk) / Calculate VaR
            var_95 = 0.0
            if len(self.daily_returns) > 20:
                returns_array = np.array(self.daily_returns)
                var_95 = np.percentile(returns_array, 5) * portfolio_value
            
            risk_metrics = {
                'portfolio_value': portfolio_value,
                'total_exposure': total_exposure,
                'exposure_ratio': exposure_ratio,
                'max_position_ratio': max_position_ratio,
                'max_drawdown': self.max_drawdown,
                'var_95': var_95,
                'active_positions_count': len(self.positions),
                'risk_limits': {
                    'max_position_size_ratio': self.risk_manager.max_position_size_ratio,
                    'max_total_exposure_ratio': self.risk_manager.max_total_exposure_ratio,
                    'max_concurrent_positions': self.risk_manager.max_concurrent_positions
                },
                'risk_status': {
                    'exposure_warning': exposure_ratio > self.risk_manager.max_total_exposure_ratio * 0.8,
                    'position_count_warning': len(self.positions) >= self.risk_manager.max_concurrent_positions * 0.8,
                    'drawdown_warning': self.max_drawdown > self.risk_manager.portfolio_stop_loss_ratio * 0.8
                }
            }
            
            return risk_metrics
            
        except Exception as e:
            self.logger.error(f"❌ 获取风险指标失败 / Get risk metrics failed: {str(e)}")
            return {}
    
    def should_stop_trading(self, current_prices: Optional[Dict[str, float]] = None) -> Tuple[bool, str]:
        """
        判断是否应该停止交易 / Determine if should stop trading
        
        Args:
            current_prices (Dict[str, float], optional): 当前价格字典 / Current prices dictionary
            
        Returns:
            Tuple[bool, str]: (是否停止交易, 原因) / (Whether stop trading, reason)
        """
        try:
            # 检查组合级别止损 / Check portfolio level stop loss
            current_value = self.get_portfolio_value(current_prices)
            total_loss = (self.initial_capital - current_value) / self.initial_capital
            
            if total_loss >= self.risk_manager.portfolio_stop_loss_ratio:
                return True, f"触发组合止损 {self.risk_manager.portfolio_stop_loss_ratio:.1%} / Portfolio stop loss triggered {self.risk_manager.portfolio_stop_loss_ratio:.1%}"
            
            # 检查最大回撤 / Check max drawdown
            if self.max_drawdown >= self.risk_manager.portfolio_stop_loss_ratio:
                return True, f"最大回撤超限 {self.max_drawdown:.1%} / Max drawdown exceeded {self.max_drawdown:.1%}"
            
            return False, "未触发停止交易条件 / No stop trading condition triggered"
            
        except Exception as e:
            self.logger.error(f"❌ 检查停止交易条件失败 / Check stop trading condition failed: {str(e)}")
            return True, f"风险检查错误 / Risk check error: {str(e)}"
    
    def __str__(self) -> str:
        """字符串表示 / String representation"""
        current_value = self.get_portfolio_value()
        return (f"Portfolio(value=${current_value:,.2f}, cash=${self.cash:,.2f}, "
                f"positions={len(self.positions)}, pnl=${current_value - self.initial_capital:,.2f})")
    
    def __repr__(self) -> str:
        """详细字符串表示 / Detailed string representation"""
        return self.__str__() 