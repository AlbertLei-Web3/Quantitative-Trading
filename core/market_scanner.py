# 市场扫描器模块 - 专门用于从交易所筛选暴涨币种 / Market Scanner Module - Specialized for screening surging cryptocurrencies from exchanges
# 此文件负责连接交易所API、获取涨幅榜单、计算涨幅、筛选符合条件的币种 / This file handles exchange API connection, fetching gain rankings, calculating gains, and filtering qualifying coins
# 关联文件：config/scanner.yaml(配置), utils/exchange_client.py(交易所客户端), main.py(主程序) / Related files: config/scanner.yaml(config), utils/exchange_client.py(exchange client), main.py(main program)

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd
from dataclasses import dataclass, field

# 设置日志 / Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CoinInfo:
    """
    币种信息数据类 / Coin information data class
    存储单个币种的基本信息和涨幅数据 / Store basic information and gain data for a single coin
    """
    symbol: str  # 币种符号 / Coin symbol
    current_price: float  # 当前价格 / Current price
    rank_position: int  # 涨幅榜排名 / Ranking position in gain list
    gain_24h: float  # 24小时涨幅 / 24-hour gain
    gain_periods: Dict[str, float] = field(default_factory=dict)  # 各周期涨幅 / Gains for different periods
    volume_24h: float = 0.0  # 24小时交易量 / 24-hour volume
    is_trending_up: bool = False  # 是否单边上涨 / Whether it's in unilateral uptrend
    max_gain_days: int = 0  # 最大涨幅天数 / Maximum gain days
    max_gain_percent: float = 0.0  # 最大涨幅百分比 / Maximum gain percentage
    last_updated: datetime = field(default_factory=datetime.now)  # 最后更新时间 / Last update time

class MarketScanner:
    """
    市场扫描器类 / Market Scanner Class
    主要功能：连接交易所、获取涨幅榜、筛选暴涨币种、维护监控列表
    Main functions: Connect to exchanges, fetch gain rankings, filter surging coins, maintain monitoring list
    """
    
    def __init__(self, config: Dict):
        """
        初始化市场扫描器 / Initialize market scanner
        Args:
            config: 配置字典，包含交易所信息、筛选条件等 / Config dictionary containing exchange info, filtering criteria, etc.
        """
        self.config = config
        self.exchange_client = None  # 交易所客户端 / Exchange client
        self.monitored_coins: List[CoinInfo] = []  # 监控的币种列表 / List of monitored coins
        self.scanning_history: List[Dict] = []  # 扫描历史记录 / Scanning history records
        
        # 筛选条件 / Filtering criteria
        self.top_rank_limit = config.get('top_rank_limit', 10)  # 涨幅榜前N名 / Top N in gain ranking
        self.min_gain_percent = config.get('min_gain_percent', 80.0)  # 最小涨幅百分比 / Minimum gain percentage
        self.max_gain_days = config.get('max_gain_days', 6)  # 最大涨幅天数 / Maximum gain days
        
        logger.info(f"市场扫描器初始化完成 / Market scanner initialized - Top {self.top_rank_limit}, Min gain: {self.min_gain_percent}%, Max days: {self.max_gain_days}")
    
    async def connect_to_exchange(self) -> bool:
        """
        连接到交易所 / Connect to exchange
        Returns:
            bool: 连接是否成功 / Whether connection is successful
        """
        try:
            # 这里将连接到实际的交易所API / Here we will connect to actual exchange API
            # 暂时使用模拟数据 / Temporarily use mock data
            logger.info("正在连接交易所... / Connecting to exchange...")
            await asyncio.sleep(1)  # 模拟网络延迟 / Simulate network delay
            logger.info("交易所连接成功 / Exchange connection successful")
            return True
        except Exception as e:
            logger.error(f"交易所连接失败 / Exchange connection failed: {str(e)}")
            return False
    
    async def fetch_top_gainers(self) -> List[Dict]:
        """
        获取涨幅榜前N名 / Fetch top N gainers
        Returns:
            List[Dict]: 涨幅榜币种列表 / List of top gainer coins
        """
        try:
            logger.info(f"正在获取涨幅榜前{self.top_rank_limit}名... / Fetching top {self.top_rank_limit} gainers...")
            
            # 模拟从交易所获取数据 / Simulate fetching data from exchange
            # 实际使用时需要调用真实的API / In actual use, need to call real API
            mock_data = [
                {"symbol": "PEPE/USDT", "price": 0.00001234, "gain_24h": 156.78, "volume": 1000000, "rank": 1},
                {"symbol": "SHIB/USDT", "price": 0.00002345, "gain_24h": 134.56, "volume": 800000, "rank": 2},
                {"symbol": "DOGE/USDT", "price": 0.12345, "gain_24h": 98.76, "volume": 1200000, "rank": 3},
                {"symbol": "FLOKI/USDT", "price": 0.00003456, "gain_24h": 87.65, "volume": 600000, "rank": 4},
                {"symbol": "BONK/USDT", "price": 0.00004567, "gain_24h": 76.54, "volume": 500000, "rank": 5},
            ]
            
            logger.info(f"成功获取{len(mock_data)}个币种数据 / Successfully fetched {len(mock_data)} coin data")
            return mock_data
            
        except Exception as e:
            logger.error(f"获取涨幅榜失败 / Failed to fetch gainers: {str(e)}")
            return []
    
    async def calculate_multi_period_gains(self, symbol: str) -> Dict[str, float]:
        """
        计算多周期涨幅 / Calculate multi-period gains
        Args:
            symbol: 币种符号 / Coin symbol
        Returns:
            Dict[str, float]: 各周期涨幅数据 / Gain data for different periods
        """
        try:
            logger.debug(f"正在计算{symbol}的多周期涨幅... / Calculating multi-period gains for {symbol}...")
            
            # 模拟获取历史数据并计算涨幅 / Simulate fetching historical data and calculating gains
            periods = ['1d', '2d', '3d', '4d', '5d', '6d']
            gains = {}
            
            # 模拟数据：随机生成一些涨幅数据 / Mock data: randomly generate some gain data
            base_gain = 50.0
            for i, period in enumerate(periods):
                gains[period] = base_gain + (i * 15.0)  # 递增涨幅 / Incremental gains
            
            return gains
            
        except Exception as e:
            logger.error(f"计算{symbol}多周期涨幅失败 / Failed to calculate multi-period gains for {symbol}: {str(e)}")
            return {}
    
    def check_unilateral_uptrend(self, symbol: str, gains: Dict[str, float]) -> bool:
        """
        检查是否为单边上涨行情 / Check if it's in unilateral uptrend
        Args:
            symbol: 币种符号 / Coin symbol
            gains: 各周期涨幅数据 / Gain data for different periods
        Returns:
            bool: 是否为单边上涨 / Whether it's in unilateral uptrend
        """
        try:
            # 检查连续上涨的天数 / Check consecutive days of uptrend
            consecutive_days = 0
            sorted_periods = sorted(gains.keys(), key=lambda x: int(x[:-1]))
            
            for period in sorted_periods:
                if gains[period] > 0:
                    consecutive_days += 1
                else:
                    break
            
            # 至少连续3天上涨才算单边上涨 / At least 3 consecutive days of uptrend to be considered unilateral
            is_trending = consecutive_days >= 3
            logger.debug(f"{symbol} 连续上涨天数: {consecutive_days}, 单边上涨: {is_trending} / {symbol} consecutive uptrend days: {consecutive_days}, unilateral uptrend: {is_trending}")
            
            return is_trending
            
        except Exception as e:
            logger.error(f"检查{symbol}单边上涨失败 / Failed to check unilateral uptrend for {symbol}: {str(e)}")
            return False
    
    def find_max_gain_period(self, gains: Dict[str, float]) -> Tuple[int, float]:
        """
        找到最大涨幅周期 / Find maximum gain period
        Args:
            gains: 各周期涨幅数据 / Gain data for different periods
        Returns:
            Tuple[int, float]: (天数, 涨幅百分比) / (days, gain percentage)
        """
        try:
            max_gain = 0.0
            max_days = 0
            
            for period, gain in gains.items():
                days = int(period[:-1])  # 提取天数 / Extract days
                if gain > max_gain and days <= self.max_gain_days:
                    max_gain = gain
                    max_days = days
            
            return max_days, max_gain
            
        except Exception as e:
            logger.error(f"查找最大涨幅周期失败 / Failed to find max gain period: {str(e)}")
            return 0, 0.0
    
    async def filter_qualifying_coins(self, top_gainers: List[Dict]) -> List[CoinInfo]:
        """
        筛选符合条件的币种 / Filter qualifying coins
        Args:
            top_gainers: 涨幅榜币种列表 / List of top gainer coins
        Returns:
            List[CoinInfo]: 符合条件的币种列表 / List of qualifying coins
        """
        qualifying_coins = []
        
        for coin_data in top_gainers:
            try:
                symbol = coin_data['symbol']
                logger.info(f"正在分析币种: {symbol} / Analyzing coin: {symbol}")
                
                # 获取多周期涨幅数据 / Get multi-period gain data
                gains = await self.calculate_multi_period_gains(symbol)
                
                # 检查单边上涨 / Check unilateral uptrend
                is_trending = self.check_unilateral_uptrend(symbol, gains)
                
                # 找到最大涨幅周期 / Find maximum gain period
                max_days, max_gain = self.find_max_gain_period(gains)
                
                # 筛选条件检查 / Filtering criteria check
                conditions_met = (
                    coin_data['rank'] <= self.top_rank_limit and  # 涨幅榜前N名 / Top N in gain ranking
                    is_trending and  # 单边上涨 / Unilateral uptrend
                    max_gain >= self.min_gain_percent and  # 涨幅大于80% / Gain > 80%
                    max_days <= self.max_gain_days  # 天数不超过6天 / Days <= 6
                )
                
                if conditions_met:
                    coin_info = CoinInfo(
                        symbol=symbol,
                        current_price=coin_data['price'],
                        rank_position=coin_data['rank'],
                        gain_24h=coin_data['gain_24h'],
                        gain_periods=gains,
                        volume_24h=coin_data['volume'],
                        is_trending_up=is_trending,
                        max_gain_days=max_days,
                        max_gain_percent=max_gain
                    )
                    
                    qualifying_coins.append(coin_info)
                    logger.info(f"✅ {symbol} 符合条件 / {symbol} qualifies - {max_days}天涨幅{max_gain:.2f}% / {max_days}-day gain {max_gain:.2f}%")
                else:
                    logger.info(f"❌ {symbol} 不符合条件 / {symbol} does not qualify")
                    
            except Exception as e:
                logger.error(f"分析币种{coin_data.get('symbol', 'unknown')}失败 / Failed to analyze coin {coin_data.get('symbol', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"筛选完成，共找到{len(qualifying_coins)}个符合条件的币种 / Filtering completed, found {len(qualifying_coins)} qualifying coins")
        return qualifying_coins
    
    async def scan_market(self) -> List[CoinInfo]:
        """
        执行市场扫描 / Execute market scanning
        Returns:
            List[CoinInfo]: 符合条件的币种列表 / List of qualifying coins
        """
        try:
            logger.info("=== 开始市场扫描 / Starting market scan ===")
            
            # 连接交易所 / Connect to exchange
            if not await self.connect_to_exchange():
                logger.error("无法连接交易所，扫描终止 / Cannot connect to exchange, scan terminated")
                return []
            
            # 获取涨幅榜 / Fetch gain rankings
            top_gainers = await self.fetch_top_gainers()
            if not top_gainers:
                logger.warning("未获取到涨幅榜数据 / No gain ranking data obtained")
                return []
            
            # 筛选符合条件的币种 / Filter qualifying coins
            qualifying_coins = await self.filter_qualifying_coins(top_gainers)
            
            # 更新监控列表 / Update monitoring list
            self.monitored_coins = qualifying_coins
            
            # 记录扫描历史 / Record scanning history
            scan_record = {
                'timestamp': datetime.now(),
                'total_scanned': len(top_gainers),
                'qualifying_count': len(qualifying_coins),
                'qualifying_symbols': [coin.symbol for coin in qualifying_coins]
            }
            self.scanning_history.append(scan_record)
            
            logger.info("=== 市场扫描完成 / Market scan completed ===")
            return qualifying_coins
            
        except Exception as e:
            logger.error(f"市场扫描失败 / Market scan failed: {str(e)}")
            return []
    
    def get_monitoring_list(self) -> List[Dict]:
        """
        获取当前监控名单 / Get current monitoring list
        Returns:
            List[Dict]: 监控币种的详细信息 / Detailed information of monitored coins
        """
        monitoring_list = []
        
        for coin in self.monitored_coins:
            coin_dict = {
                'symbol': coin.symbol,
                'current_price': coin.current_price,
                'rank_position': coin.rank_position,
                'gain_24h': coin.gain_24h,
                'max_gain_days': coin.max_gain_days,
                'max_gain_percent': coin.max_gain_percent,
                'volume_24h': coin.volume_24h,
                'is_trending_up': coin.is_trending_up,
                'last_updated': coin.last_updated.strftime('%Y-%m-%d %H:%M:%S')
            }
            monitoring_list.append(coin_dict)
        
        return monitoring_list
    
    def export_monitoring_list(self, filename: str = None) -> str:
        """
        导出监控名单到文件 / Export monitoring list to file
        Args:
            filename: 文件名，如果不指定则自动生成 / Filename, auto-generated if not specified
        Returns:
            str: 导出的文件路径 / Path of exported file
        """
        try:
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"monitoring_list_{timestamp}.csv"
            
            monitoring_data = self.get_monitoring_list()
            
            if not monitoring_data:
                logger.warning("监控列表为空，无法导出 / Monitoring list is empty, cannot export")
                return ""
            
            # 转换为DataFrame并导出 / Convert to DataFrame and export
            df = pd.DataFrame(monitoring_data)
            filepath = f"results/{filename}"
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"监控名单已导出到: {filepath} / Monitoring list exported to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"导出监控名单失败 / Failed to export monitoring list: {str(e)}")
            return "" 