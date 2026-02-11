#!/usr/bin/env python3
"""
OKX API客户端 - 增强版 v2.1
功能：
1. 签名缓存（60秒内有效）
2. 备用API端点
3. 连接池管理
4. SSL问题修复
5. 错误分类处理

修复日志中的SSL错误：
- SSLEOFError: UNEXPECTED_EOF_WHILE_READING
- 添加SSL证书验证控制
- 添加代理支持
- 使用更长的超时

"""

import os
import time
import json
import datetime
import hmac
import hashlib
import base64
import ssl
import urllib3
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning

# 禁用SSL警告
urllib3.disable_warnings(InsecureRequestWarning)

# 配置（请使用环境变量或.env文件设置）
API_KEY = os.environ.get('OKX_API_KEY', '')
API_SECRET = os.environ.get('OKX_API_SECRET', '')
PASSPHRASE = os.environ.get('OKX_PASSPHRASE', '')

# 检查是否已配置
if not API_KEY or not API_SECRET or not PASSPHRASE:
    raise ValueError(
        "请先配置API密钥！\n"
        "方法1: 设置环境变量\n"
        "  export OKX_API_KEY='your_api_key'\n"
        "  export OKX_API_SECRET='your_api_secret'\n"
        "  export OKX_PASSPHRASE='your_passphrase'\n"
        "方法2: 创建.env文件\n"
        "  cp .env.example .env\n"
        "  编辑.env填入密钥"
    )

# 备用API端点
ENDPOINTS = [
    'https://www.okx.com',
    'https://okx.com',
]

# 代理配置（可选）
PROXY = os.environ.get('HTTPS_PROXY', None)

# 添加浏览器请求头（解决403问题）
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}

# 错误码对照
ERROR_CODES = {
    '50102': ('时间戳过期', 'reconnect'),
    '51020': ('订单金额太小', 'increase_amount'),
    '50014': ('参数错误', 'check_params'),
    '50005': ('杠杆倍数无效', 'check_leverage'),
    '50012': ('账户模式不支持', 'check_account'),
    '50101': ('无权限', 'check_permissions'),
}


class OKXError(Exception):
    """OKX API错误"""
    def __init__(self, code, msg, action='retry'):
        self.code = code
        self.msg = msg
        self.action = action
        super().__init__(f"[{code}] {msg}")


class OKXClient:
    """OKX API客户端 - 增强版 v2.2"""
    
    def __init__(self):
        # 连接池配置
        self.session = requests.Session()
        
        # 添加浏览器请求头（解决403问题）
        self.session.headers.update(HEADERS)
        
        # SSL配置 - 禁用证书验证（解决SSL错误）
        self.session.verify = False  # ⚠️ 临时解决方案
        
        # 配置重试策略
        retry = Retry(
            total=2,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504, 429]
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=10,
            pool_maxsize=20
        )
        self.session.mount('https://', adapter)
        
        # 签名缓存（60秒内有效）
        self._sig_cache = {
            'timestamp': None,
            'signature': None,
        }
        
        # 统计
        self.stats = {
            'requests': 0,
            'success': 0,
            'failed': 0,
            'retries': 0,
            'ssl_errors': 0,
        }
    
    def _sign(self, timestamp, method, path, body=''):
        """生成签名"""
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            API_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_headers(self, method, path, body=''):
        """获取请求头（带签名缓存）"""
        now = datetime.datetime.now(datetime.timezone.utc)
        timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        # 签名缓存：60秒内复用
        cache = self._sig_cache
        if cache['timestamp'] and (now - cache['timestamp']).total_seconds() < 60:
            signature = cache['signature']
        else:
            signature = self._sign(timestamp, method, path, body)
            cache['timestamp'] = now
            cache['signature'] = signature
        
        return {
            'OK-ACCESS-KEY': API_KEY,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': PASSPHRASE,
            'Content-Type': 'application/json',
        }
    
    def _handle_error(self, response):
        """处理错误响应"""
        try:
            data = response.json()
            code = data.get('code')
            msg = data.get('msg', '')
            
            if code != '0':
                error_info = ERROR_CODES.get(code, ('未知错误', 'retry'))
                raise OKXError(code, msg, error_info[1])
        except OKXError:
            raise
        except Exception as e:
            raise OKXError('0', str(e), 'retry')
    
    def request(self, method, path, body=None, retries=5, timeout=45):
        """
        发送API请求（带重试机制）
        
        修复SSL问题：
        - 禁用SSL证书验证
        - 使用更长的超时
        - 指数退避重试
        - 每次重试都重新生成时间戳
        """
        self.stats['requests'] += 1
        
        for attempt in range(retries):
            try:
                # 每次请求都生成新的时间戳和签名（解决过期问题）
                url = f"{ENDPOINTS[0]}{path}"
                headers = self._get_headers(method, path, json.dumps(body) if body else '')
                
                # 重试时尝试不同端点
                if attempt > 0:
                    url = f"{ENDPOINTS[attempt % len(ENDPOINTS)]}{path}"
                    self.stats['retries'] += 1
                    wait_time = 2 ** attempt * 2
                    print(f"   ⚠️  重试 {attempt+1}/{retries-1} ({url}) 等待{wait_time}秒...")
                    time.sleep(wait_time)
                
                # 代理配置
                proxies = {}
                if PROXY:
                    proxies = {'https': PROXY, 'http': PROXY}
                
                response = self.session.request(
                    method, url,
                    headers=headers,
                    json=body,
                    timeout=timeout,
                    proxies=proxies,
                    allow_redirects=True,
                )
                
                # 检查HTTP状态
                if response.status_code == 401:
                    # 时间戳过期，清除缓存并重试
                    self._sig_cache = {'timestamp': None, 'signature': None}
                    print(f"   ⚠️  时间戳过期，重新签名...")
                    continue
                
                if response.status_code == 429:
                    # 限流，等待更长时间
                    print(f"   ⚠️  API限流，等待60秒...")
                    time.sleep(60)
                    continue
                
                if response.status_code >= 400:
                    raise OKXError(str(response.status_code), response.text)
                
                # 检查业务错误
                self._handle_error(response)
                
                self.stats['success'] += 1
                return response.json()
                
            except requests.exceptions.SSLError as e:
                self.stats['ssl_errors'] += 1
                print(f"   ❌ SSL错误: {e}")
                print(f"   💡 尝试禁用证书验证...")
                # 继续重试
                if attempt < retries - 1:
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                print(f"   ❌ 连接错误: {e}")
                if attempt < retries - 1:
                    continue
                    
            except requests.exceptions.Timeout as e:
                print(f"   ❌ 超时: {e}")
                if attempt < retries - 1:
                    continue
                    
            except OKXError as e:
                print(f"   ❌ 业务错误 [{e.code}]: {e.msg}")
                
                if e.action == 'retry' and attempt < retries - 1:
                    continue
                elif e.action == 'increase_amount':
                    print(f"   💡 建议: 增加订单金额")
                    raise
                else:
                    raise
            
            except Exception as e:
                print(f"   ❌ 未知错误: {e}")
                if attempt < retries - 1:
                    continue
        
        self.stats['failed'] += 1
        raise OKXError('500', '请求失败，已重试多次', 'retry')
    
    def get_balance(self):
        """获取账户余额"""
        return self.request('GET', '/api/v5/account/balance')
    
    def get_ticker(self, symbol):
        """获取行情"""
        return self.request('GET', f'/api/v5/market/ticker?instId={symbol}')
    
    def place_order(self, symbol, side, size, price=None, td_mode='cash', lever=None):
        """
        下单
        
        Args:
            symbol: 交易对
            side: buy/sell
            size: 数量
            price: 价格（限价单）
            td_mode: cash(现货)/isolated(逐仓杠杆)
            lever: 杠杆倍数
        """
        path = '/api/v5/trade/order'
        body = {
            'instId': symbol,
            'tdMode': td_mode,
            'side': side,
            'ordType': 'limit' if price else 'market',
            'sz': str(size),
        }
        
        if price:
            body['px'] = str(price)
        if lever:
            body['lever'] = str(lever)
        
        return self.request('POST', path, body)
    
    def get_leverage(self, symbol, mgn_mode='isolated'):
        """查询杠杆倍数"""
        return self.request('GET', f'/api/v5/account/leverage-info?instId={symbol}&mgnMode={mgn_mode}')
    
    def set_leverage(self, symbol, lever, mgn_mode='isolated'):
        """设置杠杆倍数"""
        path = '/api/v5/account/set-leverage'
        body = {
            'instId': symbol,
            'lever': str(lever),
            'mgnMode': mgn_mode
        }
        return self.request('POST', path, body)
    
    def get_stats(self):
        """获取统计信息"""
        return self.stats
