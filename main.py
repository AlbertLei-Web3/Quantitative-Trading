# 暴涨币种筛选器主程序 / Surging Coin Screener Main Program
# 此文件是系统入口，负责启动市场扫描、筛选暴涨币种、输出监控名单、持续更新列表 / This file is the system entry point, responsible for starting market scanning, filtering surging coins, outputting monitoring lists, and continuously updating lists
# 关联文件：core/market_scanner.py(扫描器), utils/exchange_client.py(交易所客户端), config/scanner.yaml(配置) / Related files: core/market_scanner.py(scanner), utils/exchange_client.py(exchange client), config/scanner.yaml(config)

import asyncio
import logging
import sys
import os
import yaml
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd
from pathlib import Path

# 添加项目根目录到路径 / Add project root directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.market_scanner import MarketScanner, CoinInfo
from utils.exchange_client import ExchangeManager
from utils.helpers import setup_logging, create_results_directory

# 设置日志 / Setup logging
logger = logging.getLogger(__name__)

class SurgingCoinScreener:
    """
    暴涨币种筛选器主类 / Surging Coin Screener Main Class
    整合市场扫描、币种筛选、名单维护等核心功能 / Integrate market scanning, coin filtering, list maintenance and other core functions
    """
    
    def __init__(self, config_file: str = "config/scanner.yaml"):
        """
        初始化筛选器 / Initialize screener
        Args:
            config_file: 配置文件路径 / Configuration file path
        """
        self.config_file = config_file
        self.config = self.load_config()
        self.market_scanner = None
        self.exchange_manager = None
        self.running = False
        
        # 设置日志 / Setup logging
        setup_logging(self.config.get('logging', {}))
        
        # 创建结果目录 / Create results directory
        create_results_directory(self.config.get('output', {}).get('results_directory', 'results'))
        
        logger.info("暴涨币种筛选器初始化完成 / Surging coin screener initialized")
    
    def load_config(self) -> Dict:
        """
        加载配置文件 / Load configuration file
        Returns:
            Dict: 配置字典 / Configuration dictionary
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"配置文件加载成功: {self.config_file} / Configuration file loaded successfully: {self.config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"配置文件不存在: {self.config_file} / Configuration file not found: {self.config_file}")
            return self.get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"配置文件格式错误 / Configuration file format error: {str(e)}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """
        获取默认配置 / Get default configuration
        Returns:
            Dict: 默认配置字典 / Default configuration dictionary
        """
        return {
            'screening': {
                'top_rank_limit': 10,
                'min_gain_percent': 80.0,
                'max_gain_days': 6,
                'min_volume_24h': 100000,
                'trend_check_days': 3
            },
            'exchanges': {
                'bitget': {'enabled': True}
            },
            'scanning': {
                'interval_minutes': 30,
                'auto_update': True
            },
            'output': {
                'console_display': True,
                'export_csv': True,
                'results_directory': 'results'
            }
        }
    
    async def initialize_components(self):
        """
        初始化组件 / Initialize components
        """
        try:
            # 初始化交易所管理器 / Initialize exchange manager
            exchange_config = self.config.get('exchanges', {})
            self.exchange_manager = ExchangeManager(exchange_config)
            
            # 初始化市场扫描器 / Initialize market scanner
            scanner_config = self.config.get('screening', {})
            self.market_scanner = MarketScanner(scanner_config)
            
            # 设置交易所客户端 / Set exchange client
            self.market_scanner.exchange_client = self.exchange_manager
            
            logger.info("所有组件初始化完成 / All components initialized")
            
        except Exception as e:
            logger.error(f"组件初始化失败 / Component initialization failed: {str(e)}")
            raise
    
    async def run_single_scan(self) -> List[CoinInfo]:
        """
        执行单次扫描 / Execute single scan
        Returns:
            List[CoinInfo]: 符合条件的币种列表 / List of qualifying coins
        """
        try:
            logger.info("=" * 60)
            logger.info("🚀 开始执行暴涨币种筛选 / Starting surging coin screening 🚀")
            logger.info("=" * 60)
            
            # 获取涨幅榜数据 / Get gain ranking data
            top_rank_limit = self.config['screening']['top_rank_limit']
            logger.info(f"📊 正在获取涨幅榜前{top_rank_limit}名... / Fetching top {top_rank_limit} gainers...")
            
            top_gainers = await self.exchange_manager.get_aggregated_gainers(top_rank_limit)
            
            if not top_gainers:
                logger.warning("⚠️ 未获取到涨幅榜数据 / No gain ranking data obtained")
                return []
            
            logger.info(f"✅ 成功获取{len(top_gainers)}个币种数据 / Successfully fetched {len(top_gainers)} coin data")
            
            # 逐个分析币种 / Analyze coins one by one
            qualifying_coins = []
            min_gain_percent = self.config['screening']['min_gain_percent']
            max_gain_days = self.config['screening']['max_gain_days']
            
            for i, coin_data in enumerate(top_gainers, 1):
                try:
                    symbol = coin_data['symbol']
                    current_gain = coin_data['gain_24h']
                    
                    logger.info(f"🔍 [{i}/{len(top_gainers)}] 分析币种: {symbol} (24h涨幅: {current_gain:.2f}%) / Analyzing coin: {symbol} (24h gain: {current_gain:.2f}%)")
                    
                    # 获取多周期涨幅数据 / Get multi-period gain data
                    period_gains = await self.exchange_manager.get_coin_multi_period_gains(symbol)
                    
                    if not period_gains:
                        logger.warning(f"⚠️ {symbol} 无法获取历史数据，跳过 / Cannot get historical data for {symbol}, skipping")
                        continue
                    
                    # 检查是否符合筛选条件 / Check if meets screening criteria
                    max_gain = 0.0
                    max_gain_days_found = 0
                    
                    # 检查各个周期的涨幅 / Check gains for each period
                    for period, gain in period_gains.items():
                        days = int(period.replace('d', ''))
                        if days <= max_gain_days and gain > max_gain:
                            max_gain = gain
                            max_gain_days_found = days
                    
                    # 检查单边上涨趋势 / Check unilateral uptrend
                    is_trending_up = self.check_unilateral_uptrend(period_gains)
                    
                    # 判断是否符合所有条件 / Check if meets all criteria
                    conditions_met = (
                        max_gain >= min_gain_percent and  # 涨幅大于80% / Gain > 80%
                        max_gain_days_found <= max_gain_days and  # 天数不超过6天 / Days <= 6
                        max_gain_days_found > 0 and  # 有有效的涨幅数据 / Has valid gain data
                        is_trending_up  # 单边上涨 / Unilateral uptrend
                    )
                    
                    if conditions_met:
                        # 创建币种信息对象 / Create coin info object
                        coin_info = CoinInfo(
                            symbol=symbol,
                            current_price=coin_data['price'],
                            rank_position=coin_data['rank'],
                            gain_24h=current_gain,
                            gain_periods=period_gains,
                            volume_24h=coin_data.get('volume', 0),
                            is_trending_up=is_trending_up,
                            max_gain_days=max_gain_days_found,
                            max_gain_percent=max_gain
                        )
                        
                        qualifying_coins.append(coin_info)
                        
                        logger.info(f"✅ {symbol} 符合条件！{max_gain_days_found}天涨幅{max_gain:.2f}% / {symbol} qualifies! {max_gain_days_found}-day gain {max_gain:.2f}%")
                    else:
                        logger.info(f"❌ {symbol} 不符合条件 (最大涨幅: {max_gain:.2f}%, 天数: {max_gain_days_found}, 单边上涨: {is_trending_up}) / {symbol} does not qualify (max gain: {max_gain:.2f}%, days: {max_gain_days_found}, trending up: {is_trending_up})")
                    
                except Exception as e:
                    logger.error(f"❌ 分析币种{coin_data.get('symbol', 'unknown')}失败 / Failed to analyze coin {coin_data.get('symbol', 'unknown')}: {str(e)}")
                    continue
            
            logger.info("=" * 60)
            logger.info(f"🎯 筛选完成！共找到 {len(qualifying_coins)} 个暴涨币种 / Screening completed! Found {len(qualifying_coins)} surging coins")
            logger.info("=" * 60)
            
            return qualifying_coins
            
        except Exception as e:
            logger.error(f"单次扫描失败 / Single scan failed: {str(e)}")
            return []
    
    def check_unilateral_uptrend(self, period_gains: Dict[str, float]) -> bool:
        """
        检查单边上涨趋势 / Check unilateral uptrend
        Args:
            period_gains: 各周期涨幅数据 / Period gain data
        Returns:
            bool: 是否为单边上涨 / Whether it's unilateral uptrend
        """
        try:
            # 检查至少连续3天都是上涨的 / Check at least 3 consecutive days of uptrend
            trend_check_days = self.config['screening'].get('trend_check_days', 3)
            consecutive_up_days = 0
            
            # 按天数排序 / Sort by days
            sorted_periods = sorted(
                [(int(k.replace('d', '')), v) for k, v in period_gains.items()],
                key=lambda x: x[0]
            )
            
            for days, gain in sorted_periods:
                if gain > 0:
                    consecutive_up_days += 1
                else:
                    break
            
            return consecutive_up_days >= trend_check_days
            
        except Exception as e:
            logger.error(f"检查单边上涨趋势失败 / Failed to check unilateral uptrend: {str(e)}")
            return False
    
    def display_results(self, qualifying_coins: List[CoinInfo]):
        """
        显示筛选结果 / Display screening results
        Args:
            qualifying_coins: 符合条件的币种列表 / List of qualifying coins
        """
        if not qualifying_coins:
            logger.info("📝 暂无符合条件的币种 / No qualifying coins found")
            return
        
        logger.info("📋 符合条件的暴涨币种名单 / List of qualifying surging coins:")
        logger.info("-" * 80)
        
        for i, coin in enumerate(qualifying_coins, 1):
            logger.info(f"{i:2d}. {coin.symbol:<15} | "
                       f"排名: {coin.rank_position:2d} | "
                       f"当前价格: ${coin.current_price:<10.6f} | "
                       f"24h涨幅: {coin.gain_24h:6.2f}% | "
                       f"{coin.max_gain_days}天涨幅: {coin.max_gain_percent:6.2f}%")
            logger.info(f"    {coin.symbol:<15} | "
                       f"Rank: {coin.rank_position:2d} | "
                       f"Price: ${coin.current_price:<10.6f} | "
                       f"24h: {coin.gain_24h:6.2f}% | "
                       f"{coin.max_gain_days}d gain: {coin.max_gain_percent:6.2f}%")
        
        logger.info("-" * 80)
    
    def export_results(self, qualifying_coins: List[CoinInfo]) -> str:
        """
        导出筛选结果 / Export screening results
        Args:
            qualifying_coins: 符合条件的币种列表 / List of qualifying coins
        Returns:
            str: 导出文件路径 / Exported file path
        """
        try:
            if not qualifying_coins:
                logger.info("无数据可导出 / No data to export")
                return ""
            
            # 准备数据 / Prepare data
            export_data = []
            for coin in qualifying_coins:
                coin_dict = {
                    '序号/No.': len(export_data) + 1,
                    '币种符号/Symbol': coin.symbol,
                    '涨幅榜排名/Rank': coin.rank_position,
                    '当前价格/Current Price': coin.current_price,
                    '24小时涨幅%/24h Gain%': round(coin.gain_24h, 2),
                    '最大涨幅天数/Max Gain Days': coin.max_gain_days,
                    '最大涨幅%/Max Gain%': round(coin.max_gain_percent, 2),
                    '24小时交易量/24h Volume': coin.volume_24h,
                    '单边上涨/Trending Up': '是/Yes' if coin.is_trending_up else '否/No',
                    '更新时间/Update Time': coin.last_updated.strftime('%Y-%m-%d %H:%M:%S')
                }
                export_data.append(coin_dict)
            
            # 生成文件名 / Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"surging_coins_{timestamp}.csv"
            results_dir = self.config.get('output', {}).get('results_directory', 'results')
            filepath = os.path.join(results_dir, filename)
            
            # 导出CSV / Export CSV
            df = pd.DataFrame(export_data)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"📄 筛选结果已导出: {filepath} / Screening results exported: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"导出结果失败 / Failed to export results: {str(e)}")
            return ""
    
    async def run_continuous_scan(self):
        """
        运行持续扫描模式 / Run continuous scanning mode
        """
        try:
            self.running = True
            interval_minutes = self.config.get('scanning', {}).get('interval_minutes', 30)
            
            logger.info(f"🔄 开始持续扫描模式，间隔{interval_minutes}分钟 / Starting continuous scan mode, interval {interval_minutes} minutes")
            
            while self.running:
                try:
                    # 执行扫描 / Execute scan
                    qualifying_coins = await self.run_single_scan()
                    
                    # 显示结果 / Display results
                    if self.config.get('output', {}).get('console_display', True):
                        self.display_results(qualifying_coins)
                    
                    # 导出结果 / Export results
                    if self.config.get('output', {}).get('export_csv', True):
                        self.export_results(qualifying_coins)
                    
                    # 等待下一次扫描 / Wait for next scan
                    if self.running:
                        logger.info(f"⏱️ 等待{interval_minutes}分钟后进行下一次扫描... / Waiting {interval_minutes} minutes for next scan...")
                        await asyncio.sleep(interval_minutes * 60)
                    
                except KeyboardInterrupt:
                    logger.info("接收到停止信号 / Received stop signal")
                    break
                except Exception as e:
                    logger.error(f"扫描过程中发生错误 / Error during scanning: {str(e)}")
                    await asyncio.sleep(60)  # 出错后等待1分钟 / Wait 1 minute after error
            
        except Exception as e:
            logger.error(f"持续扫描模式失败 / Continuous scan mode failed: {str(e)}")
        finally:
            self.running = False
    
    def stop_scanning(self):
        """停止扫描 / Stop scanning"""
        self.running = False
        logger.info("扫描已停止 / Scanning stopped")
    
    async def cleanup(self):
        """清理资源 / Cleanup resources"""
        try:
            if self.exchange_manager:
                await self.exchange_manager.close_all_sessions()
            logger.info("资源清理完成 / Resource cleanup completed")
        except Exception as e:
            logger.error(f"资源清理失败 / Resource cleanup failed: {str(e)}")

async def main():
    """
    主函数 / Main function
    """
    screener = None
    try:
        # 创建筛选器实例 / Create screener instance
        screener = SurgingCoinScreener()
        
        # 初始化组件 / Initialize components
        await screener.initialize_components()
        
        # 检查运行模式 / Check running mode
        if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
            # 持续扫描模式 / Continuous scan mode
            await screener.run_continuous_scan()
        else:
            # 单次扫描模式 / Single scan mode
            qualifying_coins = await screener.run_single_scan()
            
            # 显示和导出结果 / Display and export results
            screener.display_results(qualifying_coins)
            screener.export_results(qualifying_coins)
        
    except KeyboardInterrupt:
        logger.info("程序被用户中断 / Program interrupted by user")
    except Exception as e:
        logger.error(f"程序运行失败 / Program execution failed: {str(e)}")
    finally:
        # 清理资源 / Cleanup resources
        if screener:
            await screener.cleanup()

if __name__ == "__main__":
    # 运行主程序 / Run main program
    asyncio.run(main()) 