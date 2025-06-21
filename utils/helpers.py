# 工具函数模块 - 为市场扫描器提供基础工具函数 / Utility Functions Module - Provides basic utility functions for market scanner
# 此文件包含日志设置、目录创建、数据处理等基础工具函数 / This file contains basic utility functions such as logging setup, directory creation, data processing
# 关联文件：main.py(主程序), core/market_scanner.py(市场扫描器), config/scanner.yaml(配置文件) / Related files: main.py(main program), core/market_scanner.py(market scanner), config/scanner.yaml(config file)

import os
import logging
import yaml
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path

def setup_logging(logging_config: Dict = None):
    """
    设置日志系统 / Setup logging system
    Args:
        logging_config: 日志配置字典 / Logging configuration dictionary
    """
    try:
        # 默认日志配置 / Default logging configuration
        if not logging_config:
            logging_config = {
                'level': 'INFO',
                'file_enabled': True,
                'file_path': 'logs/scanner.log'
            }
        
        # 获取日志级别 / Get log level
        log_level = getattr(logging, logging_config.get('level', 'INFO').upper())
        
        # 创建日志目录 / Create log directory
        if logging_config.get('file_enabled', True):
            log_path = logging_config.get('file_path', 'logs/scanner.log')
            log_dir = os.path.dirname(log_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
        
        # 配置日志格式 / Configure log format
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 创建日志处理器 / Create log handlers
        handlers = []
        
        # 控制台处理器 / Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)
        
        # 文件处理器 / File handler
        if logging_config.get('file_enabled', True):
            file_handler = logging.FileHandler(
                logging_config.get('file_path', 'logs/scanner.log'),
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)
        
        # 配置根日志器 / Configure root logger
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=handlers,
            force=True
        )
        
        logger = logging.getLogger(__name__)
        logger.info("日志系统初始化完成 / Logging system initialized")
        
    except Exception as e:
        print(f"设置日志系统失败 / Failed to setup logging system: {str(e)}")

def create_results_directory(results_dir: str = 'results'):
    """
    创建结果目录 / Create results directory
    Args:
        results_dir: 结果目录路径 / Results directory path
    """
    try:
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            logger = logging.getLogger(__name__)
            logger.info(f"结果目录已创建: {results_dir} / Results directory created: {results_dir}")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"创建结果目录失败 / Failed to create results directory: {str(e)}")

def load_yaml_config(file_path: str) -> Dict:
    """
    加载YAML配置文件 / Load YAML configuration file
    Args:
        file_path: 配置文件路径 / Configuration file path
    Returns:
        Dict: 配置字典 / Configuration dictionary
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger = logging.getLogger(__name__)
        logger.info(f"配置文件加载成功: {file_path} / Configuration file loaded successfully: {file_path}")
        return config
        
    except FileNotFoundError:
        logger = logging.getLogger(__name__)
        logger.error(f"配置文件不存在: {file_path} / Configuration file not found: {file_path}")
        return {}
    except yaml.YAMLError as e:
        logger = logging.getLogger(__name__)
        logger.error(f"配置文件格式错误 / Configuration file format error: {str(e)}")
        return {}

def save_to_csv(data: List[Dict], filename: str, directory: str = 'results') -> str:
    """
    保存数据到CSV文件 / Save data to CSV file
    Args:
        data: 要保存的数据列表 / List of data to save
        filename: 文件名 / Filename
        directory: 保存目录 / Save directory
    Returns:
        str: 保存的文件路径 / Saved file path
    """
    try:
        if not data:
            logger = logging.getLogger(__name__)
            logger.warning("没有数据可保存 / No data to save")
            return ""
        
        # 确保目录存在 / Ensure directory exists
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        # 生成完整文件路径 / Generate full file path
        filepath = os.path.join(directory, filename)
        
        # 转换为DataFrame并保存 / Convert to DataFrame and save
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        logger = logging.getLogger(__name__)
        logger.info(f"数据已保存到CSV文件: {filepath} / Data saved to CSV file: {filepath}")
        return filepath
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"保存CSV文件失败 / Failed to save CSV file: {str(e)}")
        return ""

def format_currency(value: float, currency: str = '$') -> str:
    """
    格式化货币显示 / Format currency display
    Args:
        value: 数值 / Numeric value
        currency: 货币符号 / Currency symbol
    Returns:
        str: 格式化后的货币字符串 / Formatted currency string
    """
    try:
        if value >= 1:
            return f"{currency}{value:.4f}"
        elif value >= 0.01:
            return f"{currency}{value:.6f}"
        else:
            return f"{currency}{value:.8f}"
    except:
        return f"{currency}0.00"

def format_percentage(value: float, decimal_places: int = 2) -> str:
    """
    格式化百分比显示 / Format percentage display
    Args:
        value: 百分比数值 / Percentage value
        decimal_places: 小数位数 / Decimal places
    Returns:
        str: 格式化后的百分比字符串 / Formatted percentage string
    """
    try:
        return f"{value:.{decimal_places}f}%"
    except:
        return "0.00%"

def get_current_timestamp() -> str:
    """
    获取当前时间戳字符串 / Get current timestamp string
    Returns:
        str: 时间戳字符串 / Timestamp string
    """
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def validate_symbol(symbol: str) -> bool:
    """
    验证币种符号格式 / Validate coin symbol format
    Args:
        symbol: 币种符号 / Coin symbol
    Returns:
        bool: 是否有效 / Whether valid
    """
    try:
        # 基本格式检查 / Basic format check
        if not symbol or len(symbol) < 3:
            return False
        
        # 检查是否包含USDT交易对 / Check if contains USDT pair
        if not symbol.upper().endswith('USDT'):
            return False
        
        # 检查是否包含特殊字符 / Check for special characters
        allowed_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/')
        if not all(c in allowed_chars for c in symbol.upper()):
            return False
        
        return True
        
    except Exception:
        return False

def calculate_gain_percentage(current_price: float, past_price: float) -> float:
    """
    计算涨幅百分比 / Calculate gain percentage
    Args:
        current_price: 当前价格 / Current price
        past_price: 过去价格 / Past price
    Returns:
        float: 涨幅百分比 / Gain percentage
    """
    try:
        if past_price <= 0:
            return 0.0
        return ((current_price - past_price) / past_price) * 100
    except:
        return 0.0

def print_banner():
    """
    打印程序横幅 / Print program banner
    """
    banner = """
    ╔══════════════════════════════════════════════════════════════════╗
    ║                    暴涨币种筛选器 v1.0                           ║
    ║                Surging Coin Screener v1.0                       ║
    ║                                                                  ║
    ║  🚀 从真实市场筛选暴涨币种，助力量化交易                         ║
    ║  🚀 Screen surging coins from real markets for quant trading    ║
    ║                                                                  ║
    ║  📊 支持多交易所数据源 / Multi-exchange data sources            ║
    ║  🎯 智能筛选算法 / Intelligent screening algorithm             ║
    ║  📈 实时监控更新 / Real-time monitoring updates               ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    print(banner)

# 工具函数测试 / Utility functions test
if __name__ == "__main__":
    # 测试各种工具函数 / Test various utility functions
    print_banner()
    
    # 测试格式化函数 / Test formatting functions
    print("格式化测试 / Formatting Tests:")
    print(f"货币格式化 / Currency: {format_currency(0.00001234)}")
    print(f"百分比格式化 / Percentage: {format_percentage(156.78)}")
    
    # 测试符号验证 / Test symbol validation
    print("\n符号验证测试 / Symbol Validation Tests:")
    print(f"PEPE/USDT: {validate_symbol('PEPE/USDT')}")
    print(f"INVALID: {validate_symbol('INVALID')}")
    
    # 测试涨幅计算 / Test gain calculation
    print("\n涨幅计算测试 / Gain Calculation Tests:")
    print(f"涨幅: {calculate_gain_percentage(1.5, 1.0):.2f}%") 