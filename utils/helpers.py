# -*- coding: utf-8 -*-
"""
辅助工具模块 / Helper Utilities Module
=================================

本模块提供策略系统所需的各种辅助功能，包括：
This module provides various helper functions needed by the strategy system, including:

1. 技术指标计算 / Technical indicator calculations
2. 数据验证和处理 / Data validation and processing
3. 文件I/O操作 / File I/O operations
4. 日期时间处理 / Date and time processing
5. 数学统计函数 / Mathematical and statistical functions

关联文件 / Related Files:
- strategies/pump_short_strategy.py: 使用技术指标 / Uses technical indicators
- run_backtest.py: 使用数据处理功能 / Uses data processing functions
- core/portfolio.py: 使用统计计算 / Uses statistical calculations

主要功能 / Main Functions:
1. 计算各种技术指标（RSI, MACD, SMA等）/ Calculate technical indicators
2. 数据清洗和验证 / Data cleaning and validation
3. 配置文件加载和保存 / Configuration file loading and saving
4. 日志记录辅助功能 / Logging helper functions
"""

import pandas as pd
import numpy as np
import yaml
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from pathlib import Path

class TechnicalIndicators:
    """
    技术指标计算类 / Technical Indicators Class
    
    提供各种常用技术指标的计算功能。
    Provides calculation functions for various common technical indicators.
    """
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """
        简单移动平均线 / Simple Moving Average
        
        Args:
            data (pd.Series): 价格数据 / Price data
            period (int): 周期 / Period
            
        Returns:
            pd.Series: SMA数据 / SMA data
        """
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """
        指数移动平均线 / Exponential Moving Average
        
        Args:
            data (pd.Series): 价格数据 / Price data
            period (int): 周期 / Period
            
        Returns:
            pd.Series: EMA数据 / EMA data
        """
        return data.ewm(span=period).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """
        相对强弱指数 / Relative Strength Index
        
        Args:
            data (pd.Series): 价格数据 / Price data
            period (int): 周期，默认14 / Period, default 14
            
        Returns:
            pd.Series: RSI数据 / RSI data
        """
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        """
        布林带 / Bollinger Bands
        
        Args:
            data (pd.Series): 价格数据 / Price data
            period (int): 周期，默认20 / Period, default 20
            std_dev (float): 标准差倍数，默认2.0 / Standard deviation multiplier, default 2.0
            
        Returns:
            Dict[str, pd.Series]: 包含上轨、中轨、下轨的字典 / Dictionary containing upper, middle, lower bands
        """
        sma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }
    
    @staticmethod
    def macd(data: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, pd.Series]:
        """
        MACD指标 / MACD Indicator
        
        Args:
            data (pd.Series): 价格数据 / Price data
            fast_period (int): 快线周期，默认12 / Fast period, default 12
            slow_period (int): 慢线周期，默认26 / Slow period, default 26
            signal_period (int): 信号线周期，默认9 / Signal period, default 9
            
        Returns:
            Dict[str, pd.Series]: 包含MACD线、信号线、柱状图的字典 / Dictionary containing MACD line, signal line, histogram
        """
        ema_fast = data.ewm(span=fast_period).mean()
        ema_slow = data.ewm(span=slow_period).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """
        随机振荡器 / Stochastic Oscillator
        
        Args:
            high (pd.Series): 最高价 / High prices
            low (pd.Series): 最低价 / Low prices
            close (pd.Series): 收盘价 / Close prices
            k_period (int): K周期，默认14 / K period, default 14
            d_period (int): D周期，默认3 / D period, default 3
            
        Returns:
            Dict[str, pd.Series]: 包含%K和%D线的字典 / Dictionary containing %K and %D lines
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'k_percent': k_percent,
            'd_percent': d_percent
        }
    
    @staticmethod
    def volume_weighted_average_price(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        成交量加权平均价 / Volume Weighted Average Price (VWAP)
        
        Args:
            high (pd.Series): 最高价 / High prices
            low (pd.Series): 最低价 / Low prices
            close (pd.Series): 收盘价 / Close prices
            volume (pd.Series): 成交量 / Volume
            
        Returns:
            pd.Series: VWAP数据 / VWAP data
        """
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        
        return vwap

class DataValidator:
    """
    数据验证器类 / Data Validator Class
    
    提供数据质量检查和验证功能。
    Provides data quality checking and validation functions.
    """
    
    @staticmethod
    def validate_kline_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        验证K线数据格式和质量 / Validate candlestick data format and quality
        
        Args:
            df (pd.DataFrame): K线数据 / Candlestick data
            
        Returns:
            Tuple[bool, List[str]]: (是否通过验证, 错误信息列表) / (Whether passed validation, error messages list)
        """
        errors = []
        
        try:
            # 检查必需列 / Check required columns
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                errors.append(f"缺少必需列 / Missing required columns: {missing_columns}")
            
            # 检查数据类型 / Check data types
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                if col in df.columns:
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        errors.append(f"列 {col} 不是数值类型 / Column {col} is not numeric")
            
            # 检查数据完整性 / Check data integrity
            if not df.empty:
                # 检查价格逻辑 / Check price logic
                invalid_prices = df[df['high'] < df['low']]
                if not invalid_prices.empty:
                    errors.append(f"发现 {len(invalid_prices)} 条最高价低于最低价的记录 / Found {len(invalid_prices)} records where high < low")
                
                invalid_ohlc = df[(df['open'] > df['high']) | (df['open'] < df['low']) | 
                                (df['close'] > df['high']) | (df['close'] < df['low'])]
                if not invalid_ohlc.empty:
                    errors.append(f"发现 {len(invalid_ohlc)} 条开盘价或收盘价超出最高最低价范围的记录 / Found {len(invalid_ohlc)} records with open/close outside high/low range")
                
                # 检查负值 / Check negative values
                negative_prices = df[(df['open'] <= 0) | (df['high'] <= 0) | (df['low'] <= 0) | (df['close'] <= 0)]
                if not negative_prices.empty:
                    errors.append(f"发现 {len(negative_prices)} 条价格为负或零的记录 / Found {len(negative_prices)} records with negative or zero prices")
                
                negative_volume = df[df['volume'] < 0]
                if not negative_volume.empty:
                    errors.append(f"发现 {len(negative_volume)} 条成交量为负的记录 / Found {len(negative_volume)} records with negative volume")
            
            # 检查数据量 / Check data volume
            if len(df) < 10:
                errors.append(f"数据量过少 / Insufficient data: {len(df)} rows (minimum 10 required)")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"数据验证异常 / Data validation exception: {str(e)}")
            return False, errors
    
    @staticmethod
    def clean_data(df: pd.DataFrame, remove_outliers: bool = True, fill_missing: bool = True) -> pd.DataFrame:
        """
        清洗数据 / Clean data
        
        Args:
            df (pd.DataFrame): 原始数据 / Raw data
            remove_outliers (bool): 是否移除异常值 / Whether to remove outliers
            fill_missing (bool): 是否填补缺失值 / Whether to fill missing values
            
        Returns:
            pd.DataFrame: 清洗后的数据 / Cleaned data
        """
        cleaned_df = df.copy()
        
        try:
            # 填补缺失值 / Fill missing values
            if fill_missing:
                numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in numeric_columns:
                    if col in cleaned_df.columns:
                        # 使用前向填充和后向填充 / Use forward fill and backward fill
                        cleaned_df[col] = cleaned_df[col].fillna(method='ffill').fillna(method='bfill')
            
            # 移除异常值 / Remove outliers
            if remove_outliers:
                price_columns = ['open', 'high', 'low', 'close']
                for col in price_columns:
                    if col in cleaned_df.columns:
                        # 使用IQR方法检测异常值 / Use IQR method to detect outliers
                        Q1 = cleaned_df[col].quantile(0.25)
                        Q3 = cleaned_df[col].quantile(0.75)
                        IQR = Q3 - Q1
                        
                        lower_bound = Q1 - 1.5 * IQR
                        upper_bound = Q3 + 1.5 * IQR
                        
                        # 将异常值替换为边界值 / Replace outliers with boundary values
                        cleaned_df[col] = cleaned_df[col].clip(lower=lower_bound, upper=upper_bound)
            
            # 确保价格逻辑正确 / Ensure price logic is correct
            if all(col in cleaned_df.columns for col in ['open', 'high', 'low', 'close']):
                # 修正最高价和最低价 / Correct high and low prices
                cleaned_df['high'] = cleaned_df[['open', 'high', 'low', 'close']].max(axis=1)
                cleaned_df['low'] = cleaned_df[['open', 'high', 'low', 'close']].min(axis=1)
            
            return cleaned_df
            
        except Exception as e:
            logging.error(f"数据清洗失败 / Data cleaning failed: {str(e)}")
            return df

class ConfigManager:
    """
    配置管理器类 / Configuration Manager Class
    
    提供配置文件的加载、保存和管理功能。
    Provides configuration file loading, saving, and management functions.
    """
    
    @staticmethod
    def load_yaml_config(file_path: str) -> Dict[str, Any]:
        """
        加载YAML配置文件 / Load YAML configuration file
        
        Args:
            file_path (str): 配置文件路径 / Configuration file path
            
        Returns:
            Dict[str, Any]: 配置字典 / Configuration dictionary
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            logging.info(f"✅ 配置文件加载成功 / Configuration loaded successfully: {file_path}")
            return config
            
        except FileNotFoundError:
            logging.error(f"❌ 配置文件不存在 / Configuration file not found: {file_path}")
            return {}
        except yaml.YAMLError as e:
            logging.error(f"❌ YAML解析错误 / YAML parsing error: {str(e)}")
            return {}
        except Exception as e:
            logging.error(f"❌ 加载配置文件失败 / Failed to load configuration: {str(e)}")
            return {}
    
    @staticmethod
    def save_yaml_config(config: Dict[str, Any], file_path: str) -> bool:
        """
        保存YAML配置文件 / Save YAML configuration file
        
        Args:
            config (Dict[str, Any]): 配置字典 / Configuration dictionary
            file_path (str): 配置文件路径 / Configuration file path
            
        Returns:
            bool: 是否保存成功 / Whether saved successfully
        """
        try:
            # 确保目录存在 / Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, default_flow_style=False, allow_unicode=True, indent=2)
            
            logging.info(f"✅ 配置文件保存成功 / Configuration saved successfully: {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"❌ 保存配置文件失败 / Failed to save configuration: {str(e)}")
            return False
    
    @staticmethod
    def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并配置字典 / Merge configuration dictionaries
        
        Args:
            base_config (Dict[str, Any]): 基础配置 / Base configuration
            override_config (Dict[str, Any]): 覆盖配置 / Override configuration
            
        Returns:
            Dict[str, Any]: 合并后的配置 / Merged configuration
        """
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = ConfigManager.merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged

class FileManager:
    """
    文件管理器类 / File Manager Class
    
    提供文件和目录操作的辅助功能。
    Provides helper functions for file and directory operations.
    """
    
    @staticmethod
    def ensure_directory(directory_path: str) -> bool:
        """
        确保目录存在 / Ensure directory exists
        
        Args:
            directory_path (str): 目录路径 / Directory path
            
        Returns:
            bool: 是否成功 / Whether successful
        """
        try:
            os.makedirs(directory_path, exist_ok=True)
            return True
        except Exception as e:
            logging.error(f"❌ 创建目录失败 / Failed to create directory: {str(e)}")
            return False
    
    @staticmethod
    def load_csv_data(file_path: str, parse_dates: Optional[List[str]] = None) -> pd.DataFrame:
        """
        加载CSV数据文件 / Load CSV data file
        
        Args:
            file_path (str): 文件路径 / File path
            parse_dates (List[str], optional): 需要解析为日期的列 / Columns to parse as dates
            
        Returns:
            pd.DataFrame: 数据框 / DataFrame
        """
        try:
            df = pd.read_csv(file_path, parse_dates=parse_dates)
            logging.info(f"✅ CSV数据加载成功 / CSV data loaded successfully: {file_path}, 形状: {df.shape}")
            return df
        except Exception as e:
            logging.error(f"❌ 加载CSV数据失败 / Failed to load CSV data: {str(e)}")
            return pd.DataFrame()
    
    @staticmethod
    def save_csv_data(df: pd.DataFrame, file_path: str, index: bool = False) -> bool:
        """
        保存CSV数据文件 / Save CSV data file
        
        Args:
            df (pd.DataFrame): 数据框 / DataFrame
            file_path (str): 文件路径 / File path
            index (bool): 是否保存索引 / Whether to save index
            
        Returns:
            bool: 是否保存成功 / Whether saved successfully
        """
        try:
            # 确保目录存在 / Ensure directory exists
            FileManager.ensure_directory(os.path.dirname(file_path))
            
            df.to_csv(file_path, index=index, encoding='utf-8')
            logging.info(f"✅ CSV数据保存成功 / CSV data saved successfully: {file_path}")
            return True
        except Exception as e:
            logging.error(f"❌ 保存CSV数据失败 / Failed to save CSV data: {str(e)}")
            return False

class MathUtils:
    """
    数学工具类 / Math Utilities Class
    
    提供数学和统计计算功能。
    Provides mathematical and statistical calculation functions.
    """
    
    @staticmethod
    def calculate_returns(prices: pd.Series) -> pd.Series:
        """
        计算收益率 / Calculate returns
        
        Args:
            prices (pd.Series): 价格序列 / Price series
            
        Returns:
            pd.Series: 收益率序列 / Returns series
        """
        return prices.pct_change().dropna()
    
    @staticmethod
    def calculate_volatility(returns: pd.Series, annualize: bool = True) -> float:
        """
        计算波动率 / Calculate volatility
        
        Args:
            returns (pd.Series): 收益率序列 / Returns series
            annualize (bool): 是否年化 / Whether to annualize
            
        Returns:
            float: 波动率 / Volatility
        """
        vol = returns.std()
        if annualize:
            vol *= np.sqrt(252)  # 假设一年252个交易日 / Assume 252 trading days per year
        return vol
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        计算夏普比率 / Calculate Sharpe ratio
        
        Args:
            returns (pd.Series): 收益率序列 / Returns series
            risk_free_rate (float): 无风险利率 / Risk-free rate
            
        Returns:
            float: 夏普比率 / Sharpe ratio
        """
        if returns.std() == 0:
            return 0.0
        
        excess_returns = returns - risk_free_rate / 252  # 日收益率 / Daily returns
        return excess_returns.mean() / returns.std() * np.sqrt(252)
    
    @staticmethod
    def calculate_max_drawdown(prices: pd.Series) -> float:
        """
        计算最大回撤 / Calculate maximum drawdown
        
        Args:
            prices (pd.Series): 价格序列 / Price series
            
        Returns:
            float: 最大回撤比例 / Maximum drawdown ratio
        """
        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        return drawdown.min()
    
    @staticmethod
    def calculate_calmar_ratio(returns: pd.Series) -> float:
        """
        计算卡尔玛比率 / Calculate Calmar ratio
        
        Args:
            returns (pd.Series): 收益率序列 / Returns series
            
        Returns:
            float: 卡尔玛比率 / Calmar ratio
        """
        if len(returns) < 2:
            return 0.0
        
        cumulative_returns = (1 + returns).cumprod()
        annual_return = cumulative_returns.iloc[-1] ** (252 / len(returns)) - 1
        max_dd = MathUtils.calculate_max_drawdown(cumulative_returns)
        
        if max_dd == 0:
            return float('inf')
        
        return annual_return / abs(max_dd)

class LoggingUtils:
    """
    日志工具类 / Logging Utilities Class
    
    提供日志记录的辅助功能。
    Provides helper functions for logging.
    """
    
    @staticmethod
    def setup_logger(name: str, log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
        """
        设置日志记录器 / Setup logger
        
        Args:
            name (str): 记录器名称 / Logger name
            log_file (str, optional): 日志文件路径 / Log file path
            level (int): 日志级别 / Log level
            
        Returns:
            logging.Logger: 配置好的记录器 / Configured logger
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # 避免重复添加处理器 / Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # 创建格式器 / Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器 / Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器 / File handler
        if log_file:
            FileManager.ensure_directory(os.path.dirname(log_file))
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    @staticmethod
    def log_performance_metrics(logger: logging.Logger, metrics: Dict[str, Any]):
        """
        记录性能指标 / Log performance metrics
        
        Args:
            logger (logging.Logger): 日志记录器 / Logger
            metrics (Dict[str, Any]): 性能指标字典 / Performance metrics dictionary
        """
        logger.info("📊 ===== 性能指标报告 / Performance Metrics Report =====")
        
        for category, values in metrics.items():
            if isinstance(values, dict):
                logger.info(f"📋 {category}:")
                for key, value in values.items():
                    if isinstance(value, float):
                        logger.info(f"  {key}: {value:.4f}")
                    else:
                        logger.info(f"  {key}: {value}")
            else:
                if isinstance(values, float):
                    logger.info(f"📊 {category}: {values:.4f}")
                else:
                    logger.info(f"📊 {category}: {values}")
        
        logger.info("📊 ===== 报告结束 / End of Report =====")

# 导出所有工具类 / Export all utility classes
__all__ = [
    'TechnicalIndicators',
    'DataValidator', 
    'ConfigManager',
    'FileManager',
    'MathUtils',
    'LoggingUtils'
] 