# -*- coding: utf-8 -*-
"""
交易执行器模块 / Trade Executor Module
=================================

本模块负责将策略信号转换为实际的交易操作，包括：
This module converts strategy signals into actual trading operations, including:

1. 信号解析和验证 / Signal parsing and validation
2. 风险检查和限制 / Risk checks and limits
3. 交易执行和记录 / Trade execution and recording
4. 止盈止损监控 / Take profit and stop loss monitoring
5. 加仓逻辑执行 / Add position logic execution

关联文件 / Related Files:
- strategies/pump_short_strategy.py: 策略信号生成 / Strategy signal generation
- core/portfolio.py: 投资组合管理 / Portfolio management
- core/position.py: 单个持仓管理 / Individual position management

主要功能 / Main Functions:
1. 接收策略信号并执行开仓操作 / Receive strategy signals and execute opening positions
2. 监控持仓状态并执行加仓操作 / Monitor position status and execute add positions
3. 检查止盈止损条件并执行平仓 / Check take profit/stop loss conditions and execute closing
4. 记录所有交易操作和结果 / Record all trading operations and results
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
import logging
from collections import defaultdict

from .portfolio import Portfolio
from .position import Position, PositionType, PositionStatus
from strategies.pump_short_strategy import PumpShortStrategy

class TradeExecutor:
    """
    交易执行器类 / Trade Executor Class
    
    负责将策略信号转换为实际的投资组合操作，管理整个交易执行流程。
    Responsible for converting strategy signals into actual portfolio operations, managing the entire trade execution process.
    """
    
    def __init__(self, portfolio: Portfolio, strategy: PumpShortStrategy, config: Dict[str, Any]):
        """
        初始化交易执行器 / Initialize trade executor
        
        Args:
            portfolio (Portfolio): 投资组合实例 / Portfolio instance
            strategy (PumpShortStrategy): 策略实例 / Strategy instance
            config (Dict): 执行器配置 / Executor configuration
        """
        # 核心组件 / Core components
        self.portfolio = portfolio
        self.strategy = strategy
        
        # 执行配置 / Execution configuration
        self.min_signal_strength = config.get('min_signal_strength', 0.6)  # 最小信号强度 / Minimum signal strength
        self.default_position_size_ratio = config.get('default_position_size_ratio', 0.08)  # 默认仓位大小比例8% / Default position size ratio 8%
        self.enable_add_positions = config.get('enable_add_positions', True)  # 启用加仓 / Enable add positions
        self.enable_auto_stop_loss = config.get('enable_auto_stop_loss', True)  # 启用自动止损 / Enable auto stop loss
        self.enable_auto_take_profit = config.get('enable_auto_take_profit', True)  # 启用自动止盈 / Enable auto take profit
        
        # 监控设置 / Monitoring settings
        self.check_interval = config.get('check_interval', 60)  # 检查间隔秒数 / Check interval seconds
        self.price_update_threshold = config.get('price_update_threshold', 0.001)  # 价格更新阈值0.1% / Price update threshold 0.1%
        
        # 执行记录 / Execution records
        self.trade_log: List[Dict[str, Any]] = []  # 交易日志 / Trade log
        self.signal_log: List[Dict[str, Any]] = []  # 信号日志 / Signal log
        self.last_prices: Dict[str, float] = {}  # 最后价格记录 / Last prices record
        self.position_add_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {'up': 0, 'down': 0})  # 加仓计数 / Add position counts
        
        # 性能统计 / Performance statistics
        self.total_signals = 0
        self.executed_signals = 0
        self.rejected_signals = 0
        self.auto_stops = 0
        self.auto_profits = 0
        
        self.logger = self._setup_logger()
        
        self.logger.info(f"🚀 初始化交易执行器 / Initialized trade executor: "
                        f"最小信号强度 {self.min_signal_strength:.2f}, 默认仓位 {self.default_position_size_ratio:.1%}")
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器 / Setup logger"""
        logger = logging.getLogger('TradeExecutor')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def process_signal(self, symbol: str, df: pd.DataFrame, config: Dict[str, Any], 
                      timestamp: Optional[datetime] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        处理策略信号 / Process strategy signal
        
        Args:
            symbol (str): 交易标的 / Trading symbol
            df (pd.DataFrame): K线数据 / Candlestick data
            config (Dict): 策略配置 / Strategy configuration
            timestamp (datetime, optional): 时间戳 / Timestamp
            
        Returns:
            Tuple[bool, str, Dict]: (是否执行, 结果信息, 执行详情) / (Whether executed, result info, execution details)
        """
        try:
            self.total_signals += 1
            signal_timestamp = timestamp if timestamp else datetime.now()
            
            # 生成策略信号 / Generate strategy signal
            signal = self.strategy.generate_short_signals(df, config)
            
            # 记录信号 / Record signal
            signal_record = {
                'timestamp': signal_timestamp,
                'symbol': symbol,
                'signal': signal.copy(),
                'executed': False,
                'rejection_reason': None
            }
            
            # 信号验证 / Signal validation
            if not signal.get('has_pump_signal', False) or not signal.get('has_reversal_signal', False):
                rejection_reason = "信号不完整 / Incomplete signal"
                signal_record['rejection_reason'] = rejection_reason
                self.signal_log.append(signal_record)
                self.rejected_signals += 1
                return False, rejection_reason, signal_record
            
            # 信号强度检查 / Signal strength check
            if signal.get('signal_strength', 0) < self.min_signal_strength:
                rejection_reason = f"信号强度不足 {signal.get('signal_strength', 0):.2f} < {self.min_signal_strength:.2f} / Signal strength insufficient"
                signal_record['rejection_reason'] = rejection_reason
                self.signal_log.append(signal_record)
                self.rejected_signals += 1
                return False, rejection_reason, signal_record
            
            # 检查是否已有该标的的持仓 / Check if position already exists for this symbol
            if symbol in self.portfolio.positions:
                rejection_reason = f"标的 {symbol} 已存在活跃持仓 / Active position already exists for symbol {symbol}"
                signal_record['rejection_reason'] = rejection_reason
                self.signal_log.append(signal_record)
                self.rejected_signals += 1
                return False, rejection_reason, signal_record
            
            # 计算建仓数量 / Calculate position quantity
            entry_price = signal.get('entry_price', 0)
            if entry_price <= 0:
                rejection_reason = "无效的入场价格 / Invalid entry price"
                signal_record['rejection_reason'] = rejection_reason
                self.signal_log.append(signal_record)
                self.rejected_signals += 1
                return False, rejection_reason, signal_record
            
            # 计算仓位大小 / Calculate position size
            portfolio_value = self.portfolio.get_portfolio_value()
            position_value = portfolio_value * self.default_position_size_ratio
            quantity = position_value / entry_price
            
            # 执行开仓 / Execute opening position
            success, create_reason = self.portfolio.create_position(
                symbol, PositionType.SHORT, entry_price, quantity, signal_timestamp
            )
            
            if not success:
                signal_record['rejection_reason'] = f"开仓失败: {create_reason} / Position creation failed: {create_reason}"
                self.signal_log.append(signal_record)
                self.rejected_signals += 1
                return False, f"开仓失败: {create_reason}", signal_record
            
            # 记录成功执行 / Record successful execution
            signal_record['executed'] = True
            signal_record['entry_price'] = entry_price
            signal_record['quantity'] = quantity
            signal_record['position_value'] = position_value
            
            self.signal_log.append(signal_record)
            self.executed_signals += 1
            
            # 初始化加仓计数 / Initialize add position counts
            self.position_add_counts[symbol] = {'up': 0, 'down': 0}
            
            # 记录交易日志 / Record trade log
            trade_record = {
                'timestamp': signal_timestamp,
                'symbol': symbol,
                'action': 'OPEN_SHORT',
                'price': entry_price,
                'quantity': quantity,
                'value': position_value,
                'reason': 'strategy_signal',
                'signal_strength': signal.get('signal_strength', 0),
                'metadata': signal.get('metadata', {})
            }
            
            self.trade_log.append(trade_record)
            self.last_prices[symbol] = entry_price
            
            self.logger.info(f"✅ 执行做空信号 / Executed short signal: {symbol} @ {entry_price:.6f} x {quantity:.2f}, "
                           f"强度 {signal.get('signal_strength', 0):.2f}")
            
            return True, "信号执行成功 / Signal executed successfully", signal_record
            
        except Exception as e:
            error_msg = f"处理信号失败 / Process signal failed: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            self.rejected_signals += 1
            return False, error_msg, {}
    
    def monitor_positions(self, current_prices: Dict[str, float], 
                         timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        监控持仓状态并执行相应操作 / Monitor position status and execute corresponding operations
        
        Args:
            current_prices (Dict[str, float]): 当前价格字典 / Current prices dictionary
            timestamp (datetime, optional): 时间戳 / Timestamp
            
        Returns:
            List[Dict]: 执行的操作列表 / List of executed operations
        """
        operations = []
        monitor_timestamp = timestamp if timestamp else datetime.now()
        
        try:
            # 更新投资组合状态 / Update portfolio status
            self.portfolio.update_portfolio(current_prices, monitor_timestamp)
            
            # 检查每个活跃持仓 / Check each active position
            positions_to_process = list(self.portfolio.positions.items())
            
            for symbol, position in positions_to_process:
                if not position.is_active():
                    continue
                
                current_price = current_prices.get(symbol)
                if current_price is None:
                    continue
                
                # 更新最后价格 / Update last price
                self.last_prices[symbol] = current_price
                
                # 1. 检查止损条件 / Check stop loss condition
                if self.enable_auto_stop_loss:
                    should_stop, stop_reason = self.strategy.check_stop_loss(position.average_price, current_price)
                    if should_stop:
                        success, close_reason = self.portfolio.close_position(
                            symbol, current_price, None, "stop_loss", monitor_timestamp
                        )
                        if success:
                            operations.append({
                                'timestamp': monitor_timestamp,
                                'symbol': symbol,
                                'action': 'STOP_LOSS',
                                'price': current_price,
                                'quantity': position.remaining_quantity,
                                'reason': stop_reason,
                                'pnl': position.realized_pnl
                            })
                            self.auto_stops += 1
                            self.logger.info(f"🛑 自动止损 / Auto stop loss: {symbol} @ {current_price:.6f}, 原因: {stop_reason}")
                        continue
                
                # 2. 检查止盈条件 / Check take profit condition
                if self.enable_auto_take_profit:
                    should_profit, profit_reason = self.strategy.check_take_profit(position.average_price, current_price)
                    if should_profit:
                        success, close_reason = self.portfolio.close_position(
                            symbol, current_price, None, "take_profit", monitor_timestamp
                        )
                        if success:
                            operations.append({
                                'timestamp': monitor_timestamp,
                                'symbol': symbol,
                                'action': 'TAKE_PROFIT',
                                'price': current_price,
                                'quantity': position.remaining_quantity,
                                'reason': profit_reason,
                                'pnl': position.realized_pnl
                            })
                            self.auto_profits += 1
                            self.logger.info(f"💰 自动止盈 / Auto take profit: {symbol} @ {current_price:.6f}, 原因: {profit_reason}")
                        continue
                
                # 3. 检查加仓条件 / Check add position conditions
                if self.enable_add_positions:
                    add_operations = self._check_add_positions(symbol, position, current_price, monitor_timestamp)
                    operations.extend(add_operations)
            
            return operations
            
        except Exception as e:
            self.logger.error(f"❌ 监控持仓失败 / Monitor positions failed: {str(e)}")
            return operations
    
    def _check_add_positions(self, symbol: str, position: Position, current_price: float, 
                           timestamp: datetime) -> List[Dict[str, Any]]:
        """
        检查加仓条件 / Check add position conditions
        
        Args:
            symbol (str): 交易标的 / Trading symbol
            position (Position): 持仓对象 / Position object
            current_price (float): 当前价格 / Current price
            timestamp (datetime): 时间戳 / Timestamp
            
        Returns:
            List[Dict]: 加仓操作列表 / List of add position operations
        """
        operations = []
        
        try:
            if symbol not in self.position_add_counts:
                self.position_add_counts[symbol] = {'up': 0, 'down': 0}
            
            # 检查上涨加仓 / Check add on up
            should_add_up, add_up_info = self.strategy.should_add_position(
                position.average_price, current_price, 
                self.position_add_counts[symbol]['up'], 'up'
            )
            
            if should_add_up and add_up_info:
                add_quantity = position.total_quantity * add_up_info.get('add_ratio', 0.5)
                
                success, add_reason = self.portfolio.add_to_position(
                    symbol, current_price, add_quantity, 'add_on_up', timestamp
                )
                
                if success:
                    self.position_add_counts[symbol]['up'] += 1
                    operations.append({
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'action': 'ADD_ON_UP',
                        'price': current_price,
                        'quantity': add_quantity,
                        'reason': add_up_info.get('description', ''),
                        'sequence': self.position_add_counts[symbol]['up']
                    })
                    self.logger.info(f"⬆️ 上涨加仓 / Add on up: {symbol} @ {current_price:.6f} x {add_quantity:.2f}")
            
            # 检查下跌加仓 / Check add on down
            should_add_down, add_down_info = self.strategy.should_add_position(
                position.average_price, current_price, 
                self.position_add_counts[symbol]['down'], 'down'
            )
            
            if should_add_down and add_down_info:
                add_quantity = position.total_quantity * add_down_info.get('add_ratio', 0.5)
                
                success, add_reason = self.portfolio.add_to_position(
                    symbol, current_price, add_quantity, 'add_on_down', timestamp
                )
                
                if success:
                    self.position_add_counts[symbol]['down'] += 1
                    operations.append({
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'action': 'ADD_ON_DOWN',
                        'price': current_price,
                        'quantity': add_quantity,
                        'reason': add_down_info.get('description', ''),
                        'sequence': self.position_add_counts[symbol]['down']
                    })
                    self.logger.info(f"⬇️ 下跌加仓 / Add on down: {symbol} @ {current_price:.6f} x {add_quantity:.2f}")
            
        except Exception as e:
            self.logger.error(f"❌ 检查加仓条件失败 / Check add position conditions failed: {str(e)}")
        
        return operations
    
    def force_close_position(self, symbol: str, current_price: float, reason: str = "manual",
                           timestamp: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        强制平仓 / Force close position
        
        Args:
            symbol (str): 交易标的 / Trading symbol
            current_price (float): 当前价格 / Current price
            reason (str): 平仓原因 / Close reason
            timestamp (datetime, optional): 时间戳 / Timestamp
            
        Returns:
            Tuple[bool, str]: (是否成功, 结果信息) / (Whether successful, result info)
        """
        try:
            if symbol not in self.portfolio.positions:
                return False, f"标的 {symbol} 不存在活跃持仓 / No active position exists for symbol {symbol}"
            
            close_timestamp = timestamp if timestamp else datetime.now()
            
            success, close_reason = self.portfolio.close_position(
                symbol, current_price, None, reason, close_timestamp
            )
            
            if success:
                # 记录交易日志 / Record trade log
                trade_record = {
                    'timestamp': close_timestamp,
                    'symbol': symbol,
                    'action': 'FORCE_CLOSE',
                    'price': current_price,
                    'quantity': 0,  # 已经在portfolio中处理 / Already handled in portfolio
                    'reason': reason,
                    'forced': True
                }
                
                self.trade_log.append(trade_record)
                
                # 清理加仓计数 / Clear add position counts
                if symbol in self.position_add_counts:
                    del self.position_add_counts[symbol]
                
                self.logger.info(f"🔒 强制平仓成功 / Force close successful: {symbol} @ {current_price:.6f}, 原因: {reason}")
                
                return True, "强制平仓成功 / Force close successful"
            
            return False, f"强制平仓失败: {close_reason} / Force close failed: {close_reason}"
            
        except Exception as e:
            error_msg = f"强制平仓失败 / Force close failed: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要 / Get execution summary
        
        Returns:
            Dict[str, Any]: 执行摘要字典 / Execution summary dictionary
        """
        try:
            # 计算执行统计 / Calculate execution statistics
            execution_rate = self.executed_signals / max(self.total_signals, 1)
            rejection_rate = self.rejected_signals / max(self.total_signals, 1)
            
            # 分析拒绝原因 / Analyze rejection reasons
            rejection_reasons = defaultdict(int)
            for signal_record in self.signal_log:
                if not signal_record.get('executed', False) and signal_record.get('rejection_reason'):
                    rejection_reasons[signal_record['rejection_reason']] += 1
            
            # 分析交易类型 / Analyze trade types
            trade_types = defaultdict(int)
            for trade_record in self.trade_log:
                trade_types[trade_record.get('action', 'UNKNOWN')] += 1
            
            summary = {
                # 信号统计 / Signal statistics
                'total_signals': self.total_signals,
                'executed_signals': self.executed_signals,
                'rejected_signals': self.rejected_signals,
                'execution_rate': execution_rate,
                'rejection_rate': rejection_rate,
                
                # 自动操作统计 / Auto operation statistics
                'auto_stops': self.auto_stops,
                'auto_profits': self.auto_profits,
                
                # 详细统计 / Detailed statistics
                'rejection_reasons': dict(rejection_reasons),
                'trade_types': dict(trade_types),
                
                # 配置信息 / Configuration info
                'min_signal_strength': self.min_signal_strength,
                'default_position_size_ratio': self.default_position_size_ratio,
                'enable_add_positions': self.enable_add_positions,
                'enable_auto_stop_loss': self.enable_auto_stop_loss,
                'enable_auto_take_profit': self.enable_auto_take_profit,
                
                # 监控状态 / Monitoring status
                'active_positions': len(self.portfolio.positions),
                'total_trades': len(self.trade_log),
                'total_signals_logged': len(self.signal_log)
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"❌ 获取执行摘要失败 / Get execution summary failed: {str(e)}")
            return {}
    
    def get_trade_log(self, symbol: Optional[str] = None, start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        获取交易日志 / Get trade log
        
        Args:
            symbol (str, optional): 过滤标的 / Filter symbol
            start_time (datetime, optional): 开始时间 / Start time
            end_time (datetime, optional): 结束时间 / End time
            
        Returns:
            List[Dict]: 过滤后的交易日志 / Filtered trade log
        """
        try:
            filtered_log = self.trade_log.copy()
            
            # 按标的过滤 / Filter by symbol
            if symbol:
                filtered_log = [record for record in filtered_log if record.get('symbol') == symbol]
            
            # 按时间过滤 / Filter by time
            if start_time:
                filtered_log = [record for record in filtered_log if record.get('timestamp', datetime.min) >= start_time]
            
            if end_time:
                filtered_log = [record for record in filtered_log if record.get('timestamp', datetime.max) <= end_time]
            
            return filtered_log
            
        except Exception as e:
            self.logger.error(f"❌ 获取交易日志失败 / Get trade log failed: {str(e)}")
            return []
    
    def export_trade_report(self, filepath: str) -> bool:
        """
        导出交易报告 / Export trade report
        
        Args:
            filepath (str): 报告文件路径 / Report file path
            
        Returns:
            bool: 是否成功导出 / Whether successfully exported
        """
        try:
            # 获取投资组合摘要 / Get portfolio summary
            portfolio_summary = self.portfolio.get_portfolio_summary()
            execution_summary = self.get_execution_summary()
            
            # 生成Markdown报告 / Generate Markdown report
            report_lines = [
                f"# 交易执行报告 / Trade Execution Report",
                f"",
                f"**生成时间 / Generated Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"",
                f"## 📊 投资组合摘要 / Portfolio Summary",
                f"",
                f"- **初始资金 / Initial Capital:** ${portfolio_summary.get('initial_capital', 0):,.2f}",
                f"- **当前价值 / Current Value:** ${portfolio_summary.get('current_value', 0):,.2f}",
                f"- **总盈亏 / Total P&L:** ${portfolio_summary.get('total_pnl', 0):,.2f} ({portfolio_summary.get('total_return', 0):.2%})",
                f"- **现金余额 / Cash Balance:** ${portfolio_summary.get('cash', 0):,.2f}",
                f"- **最大回撤 / Max Drawdown:** {portfolio_summary.get('max_drawdown', 0):.2%}",
                f"- **夏普比率 / Sharpe Ratio:** {portfolio_summary.get('sharpe_ratio', 0):.2f}",
                f"",
                f"## 🎯 执行统计 / Execution Statistics",
                f"",
                f"- **总信号数 / Total Signals:** {execution_summary.get('total_signals', 0)}",
                f"- **执行信号数 / Executed Signals:** {execution_summary.get('executed_signals', 0)}",
                f"- **执行成功率 / Execution Rate:** {execution_summary.get('execution_rate', 0):.2%}",
                f"- **自动止损次数 / Auto Stop Loss:** {execution_summary.get('auto_stops', 0)}",
                f"- **自动止盈次数 / Auto Take Profit:** {execution_summary.get('auto_profits', 0)}",
                f"",
                f"## 📋 交易记录 / Trade Records",
                f""
            ]
            
            # 添加交易记录表格 / Add trade records table
            if self.trade_log:
                report_lines.extend([
                    f"| 时间 / Time | 标的 / Symbol | 操作 / Action | 价格 / Price | 数量 / Quantity | 原因 / Reason |",
                    f"|-------------|---------------|---------------|--------------|-----------------|---------------|"
                ])
                
                for trade in self.trade_log[-20:]:  # 显示最近20条记录 / Show last 20 records
                    timestamp = trade.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M')
                    symbol = trade.get('symbol', 'N/A')
                    action = trade.get('action', 'N/A')
                    price = trade.get('price', 0)
                    quantity = trade.get('quantity', 0)
                    reason = trade.get('reason', 'N/A')
                    
                    report_lines.append(f"| {timestamp} | {symbol} | {action} | {price:.6f} | {quantity:.2f} | {reason} |")
            
            # 写入文件 / Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            self.logger.info(f"📄 交易报告导出成功 / Trade report exported: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 导出交易报告失败 / Export trade report failed: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """字符串表示 / String representation"""
        return (f"TradeExecutor(signals={self.total_signals}, executed={self.executed_signals}, "
                f"rejected={self.rejected_signals}, rate={self.executed_signals/max(self.total_signals,1):.2%})")
    
    def __repr__(self) -> str:
        """详细字符串表示 / Detailed string representation"""
        return self.__str__() 