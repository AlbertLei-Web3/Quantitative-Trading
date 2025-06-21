# 交易所客户端模块 - 专门处理与交易所API的交互 / Exchange Client Module - Specialized for handling exchange API interactions
# 此文件负责连接Bitget等交易所，获取实时行情数据、涨幅榜单、历史K线数据 / This file handles connections to exchanges like Bitget, fetching real-time market data, gain rankings, historical kline data
# 关联文件：core/market_scanner.py(市场扫描器), config/scanner.yaml(配置文件), .env(环境变量) / Related files: core/market_scanner.py(market scanner), config/scanner.yaml(config file), .env(environment variables)

import asyncio
import aiohttp
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import time
import hashlib
import base64
import hmac
from urllib.parse import urlencode
from dotenv import load_dotenv

# 加载环境变量 / Load environment variables
load_dotenv()

# 设置日志 / Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BitgetClient:
    """
    Bitget交易所客户端 / Bitget Exchange Client
    提供获取涨幅榜、历史数据、实时价格等功能 / Provides functions for fetching gain rankings, historical data, real-time prices
    """
    
    def __init__(self, api_key: str = "", secret_key: str = "", passphrase: str = ""):
        """
        初始化Bitget客户端 / Initialize Bitget client
        Args:
            api_key: API密钥 / API key
            secret_key: 密钥 / Secret key  
            passphrase: 口令 / Passphrase
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = "https://api.bitget.com"  # Bitget API基础URL / Bitget API base URL
        self.session = None
        
        logger.info("Bitget客户端初始化完成 / Bitget client initialized")
    
    async def create_session(self):
        """创建HTTP会话 / Create HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """关闭HTTP会话 / Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def generate_signature(self, timestamp: str, method: str, request_path: str, query_string: str = "", body: str = "") -> str:
        """
        生成API签名 / Generate API signature
        Args:
            timestamp: 时间戳 / Timestamp
            method: HTTP方法 / HTTP method
            request_path: 请求路径 / Request path
            query_string: 查询字符串 / Query string
            body: 请求体 / Request body
        Returns:
            str: 签名字符串 / Signature string
        """
        if query_string:
            request_path = request_path + '?' + query_string
        
        message = timestamp + method.upper() + request_path + body
        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return signature
    
    def get_headers(self, method: str, request_path: str, query_string: str = "", body: str = "") -> Dict[str, str]:
        """
        获取请求头 / Get request headers
        Args:
            method: HTTP方法 / HTTP method
            request_path: 请求路径 / Request path
            query_string: 查询字符串 / Query string
            body: 请求体 / Request body
        Returns:
            Dict[str, str]: 请求头字典 / Request headers dictionary
        """
        timestamp = str(int(time.time() * 1000))
        
        headers = {
            'Content-Type': 'application/json',
            'ACCESS-KEY': self.api_key,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.passphrase,
        }
        
        if self.api_key and self.secret_key:
            signature = self.generate_signature(timestamp, method, request_path, query_string, body)
            headers['ACCESS-SIGN'] = signature
        
        return headers
    
    async def make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """
        发起API请求 / Make API request
        Args:
            method: HTTP方法 / HTTP method
            endpoint: API端点 / API endpoint
            params: 查询参数 / Query parameters
            data: 请求数据 / Request data
        Returns:
            Dict: API响应数据 / API response data
        """
        try:
            await self.create_session()
            
            url = f"{self.base_url}{endpoint}"
            query_string = urlencode(params) if params else ""
            body = json.dumps(data) if data else ""
            
            headers = self.get_headers(method, endpoint, query_string, body)
            
            async with self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=10
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get('code') == '00000':
                    return result.get('data', {})
                else:
                    logger.error(f"API请求失败 / API request failed: {result}")
                    return {}
                
        except asyncio.TimeoutError:
            logger.error("API请求超时 / API request timeout")
            return {}
        except Exception as e:
            logger.error(f"API请求异常 / API request exception: {str(e)}")
            return {}
    
    async def get_top_gainers(self, limit: int = 10) -> List[Dict]:
        """
        获取涨幅榜前N名 / Get top N gainers
        Args:
            limit: 返回数量限制 / Return count limit
        Returns:
            List[Dict]: 涨幅榜币种列表 / List of top gainer coins
        """
        try:
            logger.info(f"正在获取Bitget涨幅榜前{limit}名... / Fetching top {limit} gainers from Bitget...")
            
            # 获取现货涨幅榜 / Get spot gain rankings
            endpoint = "/api/spot/v1/market/tickers"
            result = await self.make_request("GET", endpoint)
            
            if not result:
                logger.warning("未获取到Bitget涨幅榜数据 / No Bitget gain ranking data obtained")
                return []
            
            # 处理数据并排序 / Process data and sort
            gainers = []
            for ticker in result:
                try:
                    symbol = ticker.get('symbol', '')
                    if not symbol.endswith('USDT'):  # 只关注USDT交易对 / Only focus on USDT pairs
                        continue
                    
                    change_24h = float(ticker.get('change24h', 0))
                    if change_24h <= 0:  # 只要上涨的币种 / Only rising coins
                        continue
                    
                    coin_data = {
                        'symbol': symbol,
                        'price': float(ticker.get('close', 0)),
                        'gain_24h': change_24h,
                        'volume': float(ticker.get('baseVolume', 0)),
                        'quote_volume': float(ticker.get('quoteVolume', 0)),
                        'high_24h': float(ticker.get('high24h', 0)),
                        'low_24h': float(ticker.get('low24h', 0))
                    }
                    
                    gainers.append(coin_data)
                    
                except (ValueError, TypeError) as e:
                    logger.debug(f"跳过无效数据 / Skip invalid data: {ticker}")
                    continue
            
            # 按24小时涨幅排序并取前N名 / Sort by 24h gain and take top N
            gainers.sort(key=lambda x: x['gain_24h'], reverse=True)
            top_gainers = gainers[:limit]
            
            # 添加排名信息 / Add ranking information
            for i, gainer in enumerate(top_gainers):
                gainer['rank'] = i + 1
            
            logger.info(f"成功获取Bitget涨幅榜前{len(top_gainers)}名 / Successfully fetched top {len(top_gainers)} gainers from Bitget")
            return top_gainers
            
        except Exception as e:
            logger.error(f"获取Bitget涨幅榜失败 / Failed to fetch Bitget gainers: {str(e)}")
            return []
    
    async def get_kline_data(self, symbol: str, interval: str = '1D', limit: int = 100) -> List[Dict]:
        """
        获取K线历史数据 / Get kline historical data
        Args:
            symbol: 交易对符号 / Trading pair symbol
            interval: 时间间隔 / Time interval
            limit: 数据数量限制 / Data count limit
        Returns:
            List[Dict]: K线数据列表 / List of kline data
        """
        try:
            logger.debug(f"正在获取{symbol}的{interval}K线数据... / Fetching {interval} kline data for {symbol}...")
            
            endpoint = "/api/spot/v1/market/candles"
            params = {
                'symbol': symbol,
                'granularity': interval,
                'limit': limit
            }
            
            result = await self.make_request("GET", endpoint, params=params)
            
            if not result:
                logger.warning(f"未获取到{symbol}的K线数据 / No kline data obtained for {symbol}")
                return []
            
            # 转换数据格式 / Convert data format
            klines = []
            for kline in result:
                try:
                    kline_data = {
                        'timestamp': int(kline[0]),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5]),
                        'datetime': datetime.fromtimestamp(int(kline[0]) / 1000)
                    }
                    klines.append(kline_data)
                except (ValueError, TypeError, IndexError) as e:
                    logger.debug(f"跳过无效K线数据 / Skip invalid kline data: {kline}")
                    continue
            
            logger.debug(f"成功获取{symbol}的{len(klines)}条K线数据 / Successfully fetched {len(klines)} kline records for {symbol}")
            return klines
            
        except Exception as e:
            logger.error(f"获取{symbol}K线数据失败 / Failed to fetch kline data for {symbol}: {str(e)}")
            return []
    
    async def calculate_period_gains(self, symbol: str, periods: List[int] = [1, 2, 3, 4, 5, 6]) -> Dict[str, float]:
        """
        计算多周期涨幅 / Calculate multi-period gains
        Args:
            symbol: 交易对符号 / Trading pair symbol
            periods: 周期天数列表 / List of period days
        Returns:
            Dict[str, float]: 各周期涨幅 / Gains for different periods
        """
        try:
            # 获取足够的历史数据 / Get sufficient historical data
            klines = await self.get_kline_data(symbol, '1D', max(periods) + 5)
            
            if len(klines) < max(periods):
                logger.warning(f"{symbol}历史数据不足，无法计算多周期涨幅 / Insufficient historical data for {symbol}, cannot calculate multi-period gains")
                return {}
            
            # 按时间排序（最新的在前） / Sort by time (newest first)
            klines.sort(key=lambda x: x['timestamp'], reverse=True)
            
            current_price = klines[0]['close']  # 当前价格 / Current price
            gains = {}
            
            for days in periods:
                if days < len(klines):
                    past_price = klines[days]['close']  # N天前的价格 / Price N days ago
                    gain_percent = ((current_price - past_price) / past_price) * 100
                    gains[f'{days}d'] = gain_percent
                    
                    logger.debug(f"{symbol} {days}天涨幅: {gain_percent:.2f}% / {symbol} {days}-day gain: {gain_percent:.2f}%")
            
            return gains
            
        except Exception as e:
            logger.error(f"计算{symbol}多周期涨幅失败 / Failed to calculate multi-period gains for {symbol}: {str(e)}")
            return {}

class ExchangeManager:
    """
    交易所管理器 / Exchange Manager
    管理多个交易所的连接和数据获取 / Manage connections and data fetching from multiple exchanges
    """
    
    def __init__(self, config: Dict):
        """
        初始化交易所管理器 / Initialize exchange manager
        Args:
            config: 配置字典 / Configuration dictionary
        """
        self.config = config
        self.exchanges = {}
        
        # 初始化支持的交易所 / Initialize supported exchanges
        if config.get('bitget', {}).get('enabled', True):
            bitget_config = config.get('bitget', {})
            
            # 从环境变量获取API密钥 / Get API keys from environment variables
            if bitget_config.get('use_env', False):
                api_key = os.getenv(bitget_config.get('api_key_env', 'BITGET_API_KEY'), '')
                secret_key = os.getenv(bitget_config.get('secret_key_env', 'BITGET_SECRET_KEY'), '')
                passphrase = os.getenv(bitget_config.get('passphrase_env', 'BITGET_PASSPHRASE'), '')
                
                logger.info(f"从环境变量加载Bitget API配置 / Loading Bitget API config from environment variables")
                if api_key and secret_key and passphrase:
                    logger.info("✅ Bitget API密钥加载成功 / Bitget API keys loaded successfully")
                else:
                    logger.warning("⚠️ Bitget API密钥未完全配置，将使用公开API / Bitget API keys not fully configured, will use public API")
            else:
                # 从配置文件获取API密钥（旧方式）/ Get API keys from config file (legacy)
                api_key = bitget_config.get('api_key', '')
                secret_key = bitget_config.get('secret_key', '')
                passphrase = bitget_config.get('passphrase', '')
            
            self.exchanges['bitget'] = BitgetClient(
                api_key=api_key,
                secret_key=secret_key,
                passphrase=passphrase
            )
        
        # 初始化币安交易所（如果启用）/ Initialize Binance exchange (if enabled)
        if config.get('binance', {}).get('enabled', False):
            binance_config = config.get('binance', {})
            
            if binance_config.get('use_env', False):
                api_key = os.getenv(binance_config.get('api_key_env', 'BINANCE_API_KEY'), '')
                secret_key = os.getenv(binance_config.get('secret_key_env', 'BINANCE_SECRET_KEY'), '')
                logger.info("从环境变量加载Binance API配置 / Loading Binance API config from environment variables")
            else:
                api_key = binance_config.get('api_key', '')
                secret_key = binance_config.get('secret_key', '')
            
            # 这里可以添加Binance客户端初始化 / Binance client initialization can be added here
            logger.info("Binance交易所支持待实现 / Binance exchange support to be implemented")
        
        # 初始化欧易交易所（如果启用）/ Initialize OKX exchange (if enabled)
        if config.get('okx', {}).get('enabled', False):
            okx_config = config.get('okx', {})
            
            if okx_config.get('use_env', False):
                api_key = os.getenv(okx_config.get('api_key_env', 'OKX_API_KEY'), '')
                secret_key = os.getenv(okx_config.get('secret_key_env', 'OKX_SECRET_KEY'), '')
                passphrase = os.getenv(okx_config.get('passphrase_env', 'OKX_PASSPHRASE'), '')
                logger.info("从环境变量加载OKX API配置 / Loading OKX API config from environment variables")
            else:
                api_key = okx_config.get('api_key', '')
                secret_key = okx_config.get('secret_key', '')
                passphrase = okx_config.get('passphrase', '')
            
            # 这里可以添加OKX客户端初始化 / OKX client initialization can be added here
            logger.info("OKX交易所支持待实现 / OKX exchange support to be implemented")
        
        logger.info(f"交易所管理器初始化完成，支持{len(self.exchanges)}个交易所 / Exchange manager initialized, supporting {len(self.exchanges)} exchanges")
    
    async def get_aggregated_gainers(self, limit: int = 10) -> List[Dict]:
        """
        获取聚合的涨幅榜 / Get aggregated gain rankings
        Args:
            limit: 返回数量限制 / Return count limit
        Returns:
            List[Dict]: 聚合的涨幅榜 / Aggregated gain rankings
        """
        all_gainers = []
        
        # 从所有交易所获取数据 / Fetch data from all exchanges
        for exchange_name, exchange_client in self.exchanges.items():
            try:
                logger.info(f"正在从{exchange_name}获取涨幅榜... / Fetching gain rankings from {exchange_name}...")
                gainers = await exchange_client.get_top_gainers(limit * 2)  # 获取更多数据以便聚合 / Fetch more data for aggregation
                
                for gainer in gainers:
                    gainer['exchange'] = exchange_name  # 标记数据来源 / Mark data source
                    all_gainers.append(gainer)
                    
            except Exception as e:
                logger.error(f"从{exchange_name}获取数据失败 / Failed to fetch data from {exchange_name}: {str(e)}")
                continue
        
        # 去重并聚合（以币种符号为准） / Deduplicate and aggregate (based on coin symbol)
        unique_gainers = {}
        for gainer in all_gainers:
            symbol = gainer['symbol']
            if symbol not in unique_gainers or gainer['gain_24h'] > unique_gainers[symbol]['gain_24h']:
                unique_gainers[symbol] = gainer
        
        # 排序并返回前N名 / Sort and return top N
        sorted_gainers = sorted(unique_gainers.values(), key=lambda x: x['gain_24h'], reverse=True)
        top_gainers = sorted_gainers[:limit]
        
        # 重新分配排名 / Reassign rankings
        for i, gainer in enumerate(top_gainers):
            gainer['rank'] = i + 1
        
        logger.info(f"聚合完成，返回前{len(top_gainers)}名涨幅币种 / Aggregation completed, returning top {len(top_gainers)} gaining coins")
        return top_gainers
    
    async def get_coin_multi_period_gains(self, symbol: str, exchange: str = 'bitget') -> Dict[str, float]:
        """
        获取币种的多周期涨幅 / Get multi-period gains for a coin
        Args:
            symbol: 币种符号 / Coin symbol
            exchange: 交易所名称 / Exchange name
        Returns:
            Dict[str, float]: 多周期涨幅 / Multi-period gains
        """
        if exchange in self.exchanges:
            return await self.exchanges[exchange].calculate_period_gains(symbol)
        else:
            logger.error(f"不支持的交易所: {exchange} / Unsupported exchange: {exchange}")
            return {}
    
    async def close_all_sessions(self):
        """关闭所有交易所会话 / Close all exchange sessions"""
        for exchange_name, exchange_client in self.exchanges.items():
            try:
                await exchange_client.close_session()
                logger.info(f"{exchange_name}会话已关闭 / {exchange_name} session closed")
            except Exception as e:
                logger.error(f"关闭{exchange_name}会话失败 / Failed to close {exchange_name} session: {str(e)}") 