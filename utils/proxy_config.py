# 代理配置工具模块 - 安全管理代理设置 / Proxy Configuration Utility Module - Securely manage proxy settings
# 此文件负责从环境变量安全地读取代理配置，支持多种代理协议 / This file securely reads proxy configuration from environment variables, supports multiple proxy protocols
# 关联文件：utils/exchange_client.py(交易所客户端), .env(环境变量) / Related files: utils/exchange_client.py(exchange client), .env(environment variables)

import os
import logging
from typing import Optional, Dict, Any
import aiohttp
from dotenv import load_dotenv

# 加载环境变量 / Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ProxyConfig:
    """
    代理配置管理类 / Proxy Configuration Manager Class
    安全地管理代理设置，支持SOCKS5和HTTP代理 / Securely manage proxy settings, support SOCKS5 and HTTP proxy
    """
    
    def __init__(self):
        """
        初始化代理配置 / Initialize proxy configuration
        从环境变量安全读取代理设置 / Securely read proxy settings from environment variables
        """
        # 从环境变量读取代理配置 / Read proxy configuration from environment variables
        self.use_proxy = self._get_bool_env('USE_PROXY', False)
        self.proxy_host = os.getenv('PROXY_HOST', '127.0.0.1')
        self.proxy_port = os.getenv('PROXY_PORT', '10808')
        self.proxy_protocol = os.getenv('PROXY_PROTOCOL', 'socks5').lower()
        
        # 验证代理配置 / Validate proxy configuration
        self._validate_config()
        
        if self.use_proxy:
            logger.info(f"🌐 代理配置已启用 / Proxy configuration enabled: {self.get_proxy_info()}")
        else:
            logger.info("🌐 直连模式 / Direct connection mode")
    
    def _get_bool_env(self, key: str, default: bool = False) -> bool:
        """
        安全地获取布尔型环境变量 / Safely get boolean environment variable
        Args:
            key: 环境变量键名 / Environment variable key
            default: 默认值 / Default value
        Returns:
            bool: 布尔值 / Boolean value
        """
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _validate_config(self):
        """
        验证代理配置的有效性 / Validate proxy configuration
        """
        if not self.use_proxy:
            return
            
        # 验证端口号 / Validate port number
        try:
            port = int(self.proxy_port)
            if not (1 <= port <= 65535):
                raise ValueError(f"端口号无效 / Invalid port number: {port}")
        except ValueError as e:
            logger.error(f"❌ 代理端口配置错误 / Proxy port configuration error: {e}")
            self.use_proxy = False
            return
        
        # 验证协议类型 / Validate protocol type
        if self.proxy_protocol not in ['socks5', 'http', 'https']:
            logger.warning(f"⚠️ 不支持的代理协议: {self.proxy_protocol}，使用默认SOCKS5 / Unsupported proxy protocol: {self.proxy_protocol}, using default SOCKS5")
            self.proxy_protocol = 'socks5'
        
        # 验证主机地址 / Validate host address
        if not self.proxy_host:
            logger.error("❌ 代理主机地址不能为空 / Proxy host address cannot be empty")
            self.use_proxy = False
    
    def get_proxy_info(self) -> str:
        """
        获取代理信息字符串（用于日志显示）/ Get proxy info string (for logging display)
        Returns:
            str: 代理信息 / Proxy information
        """
        if not self.use_proxy:
            return "直连 / Direct connection"
        return f"{self.proxy_protocol}://{self.proxy_host}:{self.proxy_port}"
    
    def get_proxy_url(self) -> Optional[str]:
        """
        获取代理URL / Get proxy URL
        Returns:
            Optional[str]: 代理URL或None / Proxy URL or None
        """
        if not self.use_proxy:
            return None
        return f"{self.proxy_protocol}://{self.proxy_host}:{self.proxy_port}"
    
    async def create_connector(self) -> aiohttp.BaseConnector:
        """
        创建HTTP连接器，支持代理 / Create HTTP connector with proxy support
        Returns:
            aiohttp.BaseConnector: HTTP连接器 / HTTP connector
        """
        if not self.use_proxy:
            return aiohttp.TCPConnector(
                limit=100,
                limit_per_host=10,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
        
        try:
            if self.proxy_protocol == 'socks5':
                # 使用SOCKS5代理 / Use SOCKS5 proxy
                try:
                    from aiohttp_socks import ProxyConnector
                    proxy_url = self.get_proxy_url()
                    connector = ProxyConnector.from_url(
                        proxy_url,
                        limit=100,
                        limit_per_host=10,
                        ttl_dns_cache=300,
                        use_dns_cache=True
                    )
                    logger.info("✅ SOCKS5代理连接器创建成功 / SOCKS5 proxy connector created successfully")
                    return connector
                except ImportError:
                    logger.warning("⚠️ aiohttp-socks未安装，回退到TCP连接器 / aiohttp-socks not installed, fallback to TCP connector")
                    return aiohttp.TCPConnector()
            else:
                # HTTP/HTTPS代理 / HTTP/HTTPS proxy
                return aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=10,
                    ttl_dns_cache=300,
                    use_dns_cache=True
                )
                
        except Exception as e:
            logger.error(f"❌ 创建代理连接器失败，使用默认连接器 / Failed to create proxy connector, using default: {e}")
            return aiohttp.TCPConnector()
    
    def get_session_kwargs(self) -> Dict[str, Any]:
        """
        获取aiohttp会话的参数 / Get aiohttp session parameters
        Returns:
            Dict[str, Any]: 会话参数 / Session parameters
        """
        kwargs = {
            'timeout': aiohttp.ClientTimeout(total=30, connect=10),
            'trust_env': True,
            'headers': {
                'User-Agent': 'Surging-Coin-Screener/1.0'
            }
        }
        
        # 如果使用HTTP代理，添加代理参数 / If using HTTP proxy, add proxy parameters
        if self.use_proxy and self.proxy_protocol in ['http', 'https']:
            kwargs['proxy'] = self.get_proxy_url()
        
        return kwargs
    
    def is_proxy_enabled(self) -> bool:
        """
        检查代理是否启用 / Check if proxy is enabled
        Returns:
            bool: 代理是否启用 / Whether proxy is enabled
        """
        return self.use_proxy
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        获取配置摘要（用于调试）/ Get configuration summary (for debugging)
        Returns:
            Dict[str, Any]: 配置摘要 / Configuration summary
        """
        return {
            'use_proxy': self.use_proxy,
            'proxy_info': self.get_proxy_info(),
            'proxy_protocol': self.proxy_protocol if self.use_proxy else None,
            'proxy_host': self.proxy_host if self.use_proxy else None,
            'proxy_port': self.proxy_port if self.use_proxy else None
        }

# 全局代理配置实例 / Global proxy configuration instance
proxy_config = ProxyConfig()

def get_proxy_config() -> ProxyConfig:
    """
    获取全局代理配置实例 / Get global proxy configuration instance
    Returns:
        ProxyConfig: 代理配置实例 / Proxy configuration instance
    """
    return proxy_config 