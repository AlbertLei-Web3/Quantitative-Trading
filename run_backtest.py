#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
暴涨做空策略回测主程序 / Pump Short Strategy Backtesting Main Program
=================================================================

本程序是暴涨做空策略系统的主入口，负责整合所有模块并执行完整的回测流程。
This program is the main entry point of the pump short strategy system, responsible for integrating 
all modules and executing the complete backtesting process.

功能说明 / Function Description:
1. 加载配置文件和历史数据 / Load configuration files and historical data
2. 初始化策略、投资组合和执行器 / Initialize strategy, portfolio and executor
3. 执行完整的回测流程 / Execute complete backtesting process
4. 生成详细的交易报告 / Generate detailed trading reports
5. 计算和输出性能指标 / Calculate and output performance metrics

关联文件 / Related Files:
- config/strategy.yaml: 策略配置文件 / Strategy configuration file
- strategies/pump_short_strategy.py: 核心策略逻辑 / Core strategy logic
- core/portfolio.py: 投资组合管理 / Portfolio management
- core/executor.py: 交易执行器 / Trade executor
- data/sample_kline.csv: 示例数据文件 / Sample data file

使用方法 / Usage:
python run_backtest.py [--config CONFIG_FILE] [--data DATA_FILE] [--symbol SYMBOL]

示例 / Examples:
python run_backtest.py
python run_backtest.py --config config/strategy.yaml --data data/sample_kline.csv --symbol TEST
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import warnings

# 添加项目根目录到Python路径 / Add project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入项目模块 / Import project modules
from strategies.pump_short_strategy import PumpShortStrategy
from core.portfolio import Portfolio
from core.position import PositionType
from core.executor import TradeExecutor
from utils.helpers import ConfigManager, DataValidator, FileManager, MathUtils, LoggingUtils

# 忽略警告信息 / Ignore warnings
warnings.filterwarnings('ignore')

class StrategyBacktester:
    """
    策略回测器类 / Strategy Backtester Class
    
    负责执行完整的策略回测流程，包括数据处理、信号生成、交易执行和结果分析。
    Responsible for executing the complete strategy backtesting process, including data processing, 
    signal generation, trade execution, and result analysis.
    """
    
    def __init__(self, config_file: str = "config/strategy.yaml"):
        """
        初始化回测器 / Initialize backtester
        
        Args:
            config_file (str): 配置文件路径 / Configuration file path
        """
        # 加载配置 / Load configuration
        self.config = ConfigManager.load_yaml_config(config_file)
        if not self.config:
            raise ValueError(f"无法加载配置文件 / Cannot load configuration file: {config_file}")
        
        # 设置日志 / Setup logging
        self.logger = LoggingUtils.setup_logger(
            'StrategyBacktester',
            self.config.get('logging', {}).get('log_file', 'logs/backtest.log'),
            getattr(logging, self.config.get('logging', {}).get('level', 'INFO'))
        )
        
        # 初始化组件 / Initialize components
        self.strategy = None
        self.portfolio = None
        self.executor = None
        self.data = pd.DataFrame()
        
        # 回测结果 / Backtesting results
        self.results = {}
        self.performance_metrics = {}
        
        self.logger.info("🚀 策略回测器初始化完成 / Strategy backtester initialized")
    
    def load_data(self, data_file: str) -> bool:
        """
        加载历史数据 / Load historical data
        
        Args:
            data_file (str): 数据文件路径 / Data file path
            
        Returns:
            bool: 是否加载成功 / Whether loaded successfully
        """
        try:
            self.logger.info(f"📊 开始加载数据 / Starting to load data: {data_file}")
            
            # 加载CSV数据 / Load CSV data
            self.data = FileManager.load_csv_data(data_file, parse_dates=['timestamp'])
            
            if self.data.empty:
                self.logger.error("❌ 数据文件为空 / Data file is empty")
                return False
            
            # 数据验证 / Data validation
            is_valid, errors = DataValidator.validate_kline_data(self.data)
            if not is_valid:
                self.logger.error(f"❌ 数据验证失败 / Data validation failed:")
                for error in errors:
                    self.logger.error(f"  - {error}")
                return False
            
            # 数据清洗 / Data cleaning
            if self.config.get('data', {}).get('remove_outliers', True):
                self.data = DataValidator.clean_data(
                    self.data,
                    remove_outliers=True,
                    fill_missing=self.config.get('data', {}).get('fill_missing_data', True)
                )
            
            # 设置时间索引 / Set time index
            if 'timestamp' in self.data.columns:
                self.data.set_index('timestamp', inplace=True)
                self.data.sort_index(inplace=True)
            
            self.logger.info(f"✅ 数据加载成功 / Data loaded successfully: {len(self.data)} 条记录 / records, "
                           f"时间范围 / Time range: {self.data.index[0]} 到 / to {self.data.index[-1]}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 加载数据失败 / Failed to load data: {str(e)}")
            return False
    
    def initialize_components(self) -> bool:
        """
        初始化策略组件 / Initialize strategy components
        
        Returns:
            bool: 是否初始化成功 / Whether initialized successfully
        """
        try:
            self.logger.info("⚙️ 开始初始化策略组件 / Starting to initialize strategy components")
            
            # 初始化策略 / Initialize strategy
            strategy_config = self.config.get('strategy', {})
            self.strategy = PumpShortStrategy(strategy_config)
            self.logger.info("✅ 策略初始化完成 / Strategy initialized")
            
            # 初始化投资组合 / Initialize portfolio
            portfolio_config = self.config.get('portfolio', {})
            initial_capital = portfolio_config.get('initial_capital', 10000.0)
            self.portfolio = Portfolio(initial_capital, self.config)
            self.logger.info(f"✅ 投资组合初始化完成 / Portfolio initialized: ${initial_capital:,.2f}")
            
            # 初始化执行器 / Initialize executor
            executor_config = self.config.get('executor', {})
            self.executor = TradeExecutor(self.portfolio, self.strategy, executor_config)
            self.logger.info("✅ 交易执行器初始化完成 / Trade executor initialized")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 初始化组件失败 / Failed to initialize components: {str(e)}")
            return False
    
    def run_backtest(self, symbol: str = "TEST") -> bool:
        """
        执行回测 / Run backtest
        
        Args:
            symbol (str): 交易标的符号 / Trading symbol
            
        Returns:
            bool: 是否执行成功 / Whether executed successfully
        """
        try:
            self.logger.info(f"🎯 开始执行回测 / Starting backtest for symbol: {symbol}")
            
            if self.data.empty:
                self.logger.error("❌ 没有数据可供回测 / No data available for backtesting")
                return False
            
            # 回测统计 / Backtesting statistics
            total_bars = len(self.data)
            processed_bars = 0
            signals_generated = 0
            trades_executed = 0
            
            self.logger.info(f"📊 回测数据概览 / Backtest data overview:")
            self.logger.info(f"  - 总K线数量 / Total bars: {total_bars}")
            self.logger.info(f"  - 数据范围 / Data range: {self.data.index[0]} 到 / to {self.data.index[-1]}")
            
            # 滑动窗口回测 / Rolling window backtesting
            min_window = max(10, self.config.get('strategy', {}).get('lookback_days', 3) + 5)
            
            for i in range(min_window, len(self.data)):
                processed_bars += 1
                current_timestamp = self.data.index[i]
                
                # 获取当前窗口数据 / Get current window data
                window_data = self.data.iloc[:i+1].copy()
                current_price = float(window_data.iloc[-1]['close'])
                
                # 构建当前价格字典 / Build current price dictionary
                current_prices = {symbol: current_price}
                
                # 检查是否需要生成新信号 / Check if need to generate new signal
                if symbol not in self.portfolio.positions:
                    # 尝试生成新的做空信号 / Try to generate new short signal
                    executed, reason, signal_detail = self.executor.process_signal(
                        symbol, window_data, self.config.get('strategy', {}), current_timestamp
                    )
                    
                    if executed:
                        signals_generated += 1
                        trades_executed += 1
                        self.logger.info(f"📈 {current_timestamp}: 执行做空信号 / Executed short signal @ {current_price:.6f}")
                
                # 监控现有持仓 / Monitor existing positions
                operations = self.executor.monitor_positions(current_prices, current_timestamp)
                
                for operation in operations:
                    if operation['action'] in ['STOP_LOSS', 'TAKE_PROFIT', 'ADD_ON_UP', 'ADD_ON_DOWN']:
                        self.logger.info(f"🔄 {current_timestamp}: {operation['action']} @ {operation['price']:.6f}")
                        trades_executed += 1
                
                # 定期输出进度 / Periodic progress output
                if processed_bars % 100 == 0 or processed_bars == total_bars - min_window:
                    progress = processed_bars / (total_bars - min_window) * 100
                    portfolio_value = self.portfolio.get_portfolio_value(current_prices)
                    self.logger.info(f"⏳ 回测进度 / Progress: {progress:.1f}% ({processed_bars}/{total_bars - min_window}), "
                                   f"组合价值 / Portfolio Value: ${portfolio_value:,.2f}")
            
            # 强制平仓所有持仓 / Force close all positions
            final_price = float(self.data.iloc[-1]['close'])
            for symbol_name in list(self.portfolio.positions.keys()):
                self.executor.force_close_position(symbol_name, final_price, "backtest_end", self.data.index[-1])
                trades_executed += 1
            
            self.logger.info(f"✅ 回测执行完成 / Backtest completed:")
            self.logger.info(f"  - 处理K线数量 / Processed bars: {processed_bars}")
            self.logger.info(f"  - 生成信号数量 / Signals generated: {signals_generated}")
            self.logger.info(f"  - 执行交易数量 / Trades executed: {trades_executed}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 回测执行失败 / Backtest execution failed: {str(e)}")
            return False
    
    def calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        计算性能指标 / Calculate performance metrics
        
        Returns:
            Dict[str, Any]: 性能指标字典 / Performance metrics dictionary
        """
        try:
            self.logger.info("📊 开始计算性能指标 / Starting to calculate performance metrics")
            
            # 获取投资组合摘要 / Get portfolio summary
            portfolio_summary = self.portfolio.get_portfolio_summary()
            
            # 获取执行摘要 / Get execution summary
            execution_summary = self.executor.get_execution_summary()
            
            # 计算基础指标 / Calculate basic metrics
            initial_capital = self.portfolio.initial_capital
            final_value = portfolio_summary.get('current_value', initial_capital)
            total_return = (final_value - initial_capital) / initial_capital
            
            # 计算年化收益率 / Calculate annualized return
            if len(self.portfolio.daily_returns) > 0:
                daily_returns = pd.Series(self.portfolio.daily_returns)
                annualized_return = (1 + daily_returns.mean()) ** 252 - 1
                volatility = MathUtils.calculate_volatility(daily_returns, annualize=True)
                sharpe_ratio = MathUtils.calculate_sharpe_ratio(daily_returns)
                max_drawdown = MathUtils.calculate_max_drawdown(pd.Series(self.portfolio.equity_curve))
                calmar_ratio = MathUtils.calculate_calmar_ratio(daily_returns)
            else:
                annualized_return = 0.0
                volatility = 0.0
                sharpe_ratio = 0.0
                max_drawdown = 0.0
                calmar_ratio = 0.0
            
            # 计算交易统计 / Calculate trading statistics
            total_trades = portfolio_summary.get('total_trades', 0)
            winning_trades = portfolio_summary.get('winning_trades', 0)
            losing_trades = portfolio_summary.get('losing_trades', 0)
            win_rate = portfolio_summary.get('win_rate', 0)
            
            # 平均盈亏 / Average profit/loss
            avg_win = 0.0
            avg_loss = 0.0
            if self.portfolio.closed_positions:
                wins = [pos.realized_pnl for pos in self.portfolio.closed_positions if pos.realized_pnl > 0]
                losses = [pos.realized_pnl for pos in self.portfolio.closed_positions if pos.realized_pnl < 0]
                
                avg_win = np.mean(wins) if wins else 0.0
                avg_loss = np.mean(losses) if losses else 0.0
            
            # 盈亏比 / Profit/Loss ratio
            profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
            
            # 组装性能指标 / Assemble performance metrics
            self.performance_metrics = {
                # 基础收益指标 / Basic return metrics
                'returns': {
                    'initial_capital': initial_capital,
                    'final_value': final_value,
                    'total_return': total_return,
                    'annualized_return': annualized_return,
                    'total_pnl': final_value - initial_capital
                },
                
                # 风险指标 / Risk metrics
                'risk': {
                    'volatility': volatility,
                    'max_drawdown': max_drawdown,
                    'sharpe_ratio': sharpe_ratio,
                    'calmar_ratio': calmar_ratio
                },
                
                # 交易统计 / Trading statistics
                'trading': {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'win_rate': win_rate,
                    'avg_win': avg_win,
                    'avg_loss': avg_loss,
                    'profit_loss_ratio': profit_loss_ratio
                },
                
                # 执行统计 / Execution statistics
                'execution': {
                    'total_signals': execution_summary.get('total_signals', 0),
                    'executed_signals': execution_summary.get('executed_signals', 0),
                    'execution_rate': execution_summary.get('execution_rate', 0),
                    'auto_stops': execution_summary.get('auto_stops', 0),
                    'auto_profits': execution_summary.get('auto_profits', 0)
                },
                
                # 费用统计 / Cost statistics
                'costs': {
                    'total_fees': portfolio_summary.get('total_fees', 0),
                    'fee_ratio': portfolio_summary.get('total_fees', 0) / initial_capital
                }
            }
            
            self.logger.info("✅ 性能指标计算完成 / Performance metrics calculation completed")
            return self.performance_metrics
            
        except Exception as e:
            self.logger.error(f"❌ 计算性能指标失败 / Failed to calculate performance metrics: {str(e)}")
            return {}
    
    def generate_report(self, output_dir: str = "results") -> bool:
        """
        生成回测报告 / Generate backtest report
        
        Args:
            output_dir (str): 输出目录 / Output directory
            
        Returns:
            bool: 是否生成成功 / Whether generated successfully
        """
        try:
            self.logger.info(f"📄 开始生成回测报告 / Starting to generate backtest report: {output_dir}")
            
            # 确保输出目录存在 / Ensure output directory exists
            FileManager.ensure_directory(output_dir)
            
            # 生成时间戳 / Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 导出交易记录 / Export trade records
            trade_log = self.executor.get_trade_log()
            if trade_log:
                trade_df = pd.DataFrame(trade_log)
                trade_file = os.path.join(output_dir, f"trades_{timestamp}.csv")
                FileManager.save_csv_data(trade_df, trade_file)
                self.logger.info(f"✅ 交易记录导出 / Trade records exported: {trade_file}")
            
            # 导出持仓记录 / Export position records
            if self.portfolio.closed_positions:
                positions_data = []
                for pos in self.portfolio.closed_positions:
                    pos_summary = pos.get_position_summary()
                    positions_data.append(pos_summary)
                
                positions_df = pd.DataFrame(positions_data)
                positions_file = os.path.join(output_dir, f"positions_{timestamp}.csv")
                FileManager.save_csv_data(positions_df, positions_file)
                self.logger.info(f"✅ 持仓记录导出 / Position records exported: {positions_file}")
            
            # 导出净值曲线 / Export equity curve
            if self.portfolio.equity_curve:
                equity_data = {
                    'timestamp': self.portfolio.timestamps,
                    'equity_value': self.portfolio.equity_curve
                }
                equity_df = pd.DataFrame(equity_data)
                equity_file = os.path.join(output_dir, f"equity_curve_{timestamp}.csv")
                FileManager.save_csv_data(equity_df, equity_file)
                self.logger.info(f"✅ 净值曲线导出 / Equity curve exported: {equity_file}")
            
            # 生成详细报告 / Generate detailed report
            report_file = os.path.join(output_dir, f"backtest_report_{timestamp}.md")
            success = self.executor.export_trade_report(report_file)
            
            if success:
                self.logger.info(f"✅ 详细报告生成 / Detailed report generated: {report_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 生成报告失败 / Failed to generate report: {str(e)}")
            return False
    
    def print_summary(self):
        """打印回测摘要 / Print backtest summary"""
        try:
            print("\n" + "="*80)
            print("🎯 暴涨做空策略回测结果摘要 / Pump Short Strategy Backtest Summary")
            print("="*80)
            
            if not self.performance_metrics:
                print("❌ 没有性能指标数据 / No performance metrics data available")
                return
            
            # 基础收益指标 / Basic return metrics
            returns = self.performance_metrics.get('returns', {})
            print(f"💰 收益指标 / Return Metrics:")
            print(f"   初始资金 / Initial Capital: ${returns.get('initial_capital', 0):,.2f}")
            print(f"   最终价值 / Final Value: ${returns.get('final_value', 0):,.2f}")
            print(f"   总收益率 / Total Return: {returns.get('total_return', 0):.2%}")
            print(f"   年化收益率 / Annualized Return: {returns.get('annualized_return', 0):.2%}")
            print(f"   总盈亏 / Total P&L: ${returns.get('total_pnl', 0):,.2f}")
            
            # 风险指标 / Risk metrics
            risk = self.performance_metrics.get('risk', {})
            print(f"\n⚠️ 风险指标 / Risk Metrics:")
            print(f"   年化波动率 / Annualized Volatility: {risk.get('volatility', 0):.2%}")
            print(f"   最大回撤 / Max Drawdown: {risk.get('max_drawdown', 0):.2%}")
            print(f"   夏普比率 / Sharpe Ratio: {risk.get('sharpe_ratio', 0):.2f}")
            print(f"   卡尔玛比率 / Calmar Ratio: {risk.get('calmar_ratio', 0):.2f}")
            
            # 交易统计 / Trading statistics
            trading = self.performance_metrics.get('trading', {})
            print(f"\n📊 交易统计 / Trading Statistics:")
            print(f"   总交易次数 / Total Trades: {trading.get('total_trades', 0)}")
            print(f"   盈利次数 / Winning Trades: {trading.get('winning_trades', 0)}")
            print(f"   亏损次数 / Losing Trades: {trading.get('losing_trades', 0)}")
            print(f"   胜率 / Win Rate: {trading.get('win_rate', 0):.2%}")
            print(f"   平均盈利 / Average Win: ${trading.get('avg_win', 0):.2f}")  
            print(f"   平均亏损 / Average Loss: ${trading.get('avg_loss', 0):.2f}")
            print(f"   盈亏比 / Profit/Loss Ratio: {trading.get('profit_loss_ratio', 0):.2f}")
            
            # 执行统计 / Execution statistics
            execution = self.performance_metrics.get('execution', {})
            print(f"\n🎯 执行统计 / Execution Statistics:")
            print(f"   总信号数 / Total Signals: {execution.get('total_signals', 0)}")
            print(f"   执行信号数 / Executed Signals: {execution.get('executed_signals', 0)}")
            print(f"   执行成功率 / Execution Rate: {execution.get('execution_rate', 0):.2%}")
            print(f"   自动止损次数 / Auto Stop Loss: {execution.get('auto_stops', 0)}")
            print(f"   自动止盈次数 / Auto Take Profit: {execution.get('auto_profits', 0)}")
            
            print("="*80)
            
        except Exception as e:
            print(f"❌ 打印摘要失败 / Failed to print summary: {str(e)}")

def main():
    """主函数 / Main function"""
    # 命令行参数解析 / Command line argument parsing
    parser = argparse.ArgumentParser(
        description="暴涨做空策略回测系统 / Pump Short Strategy Backtesting System",
        epilog="示例 / Example: python run_backtest.py --config config/strategy.yaml --data data/sample_kline.csv --symbol TEST"
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config/strategy.yaml',
        help='配置文件路径 / Configuration file path (default: config/strategy.yaml)'
    )
    
    parser.add_argument(
        '--data', '-d',
        type=str,
        default='data/sample_kline.csv',
        help='数据文件路径 / Data file path (default: data/sample_kline.csv)'
    )
    
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        default='TEST',
        help='交易标的符号 / Trading symbol (default: TEST)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='results',
        help='结果输出目录 / Results output directory (default: results)'
    )
    
    args = parser.parse_args()
    
    try:
        print("🚀 暴涨做空策略回测系统启动 / Pump Short Strategy Backtesting System Starting")
        print(f"📁 配置文件 / Config file: {args.config}")
        print(f"📊 数据文件 / Data file: {args.data}")
        print(f"💰 交易标的 / Trading symbol: {args.symbol}")
        print(f"📄 输出目录 / Output directory: {args.output}")
        print("-" * 80)
        
        # 初始化回测器 / Initialize backtester
        backtester = StrategyBacktester(args.config)
        
        # 加载数据 / Load data
        if not backtester.load_data(args.data):
            print("❌ 数据加载失败，程序退出 / Data loading failed, program exit")
            sys.exit(1)
        
        # 初始化组件 / Initialize components
        if not backtester.initialize_components():
            print("❌ 组件初始化失败，程序退出 / Component initialization failed, program exit")
            sys.exit(1)
        
        # 执行回测 / Run backtest
        if not backtester.run_backtest(args.symbol):
            print("❌ 回测执行失败，程序退出 / Backtest execution failed, program exit")
            sys.exit(1)
        
        # 计算性能指标 / Calculate performance metrics
        backtester.calculate_performance_metrics()
        
        # 生成报告 / Generate report
        backtester.generate_report(args.output)
        
        # 打印摘要 / Print summary
        backtester.print_summary()
        
        print(f"\n✅ 回测完成！结果已保存到 / Backtest completed! Results saved to: {args.output}")
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断程序 / User interrupted the program")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序执行出错 / Program execution error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 