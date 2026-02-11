#!/usr/bin/env python3
"""
OKX现货自动交易监控脚本
功能：
1. 价格监控（支撑位/阻力位）
2. 自动现货买入/卖出
3. 网络重试机制
4. 日志记录

使用方法：
    python3 monitor.py status     # 查看状态
    python3 monitor.py buy 5      # 买入5 USDT BTC
    python3 monitor.py sell 0.001 # 卖出0.001 BTC
    python3 monitor.py loop       # 持续监控模式
"""

import os
import sys
import json
import time
import logging
import datetime
from pathlib import Path
import hmac
import hashlib
import base64
import requests

# ============ 配置 ============
API_KEY = os.environ.get('OKX_API_KEY', '')
API_SECRET = os.environ.get('OKX_API_SECRET', '')
PASSPHRASE = os.environ.get('OKX_PASSPHRASE', '')

BASE_URL = 'https://www.okx.com'
BACKUP_URLS = [
    'https://www.okx.com',
    'https://okx.com',
]

# 交易参数
TRADE_AMOUNT = 5        # 每次买入金额
STOP_LOSS = 0.05        # 止损5%
TAKE_PROFIT = 0.10      # 止盈10%

# 支撑/阻力位
SUPPORTS = {
    'BTC-USDT': [66000, 65000, 64000],
    'ETH-USDT': [1950, 1900, 1850],
}
RESISTANCES = {
    'BTC-USDT': [67000, 68000, 70000],
    'ETH-USDT': [2000, 2050, 2100],
}

# 日志配置
LOG_FILE = 'trading.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============ 工具函数 ============
def sign(timestamp, method, path, body=''):
    """生成签名"""
    message = f"{timestamp}{method}{path}{body}"
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode('utf-8')


def get_timestamp():
    """获取ISO时间戳"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def request_with_retry(method, path, body=None, max_retries=5, timeout=30):
    """
    带重试机制的API请求
    解决网络波动问题
    """
    url = f"{BASE_URL}{path}"
    headers = {
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': sign(get_timestamp(), method, path, json.dumps(body) if body else ''),
        'OK-ACCESS-TIMESTAMP': get_timestamp(),
        'OK-ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json',
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.request(
                method, url,
                headers=headers,
                json=body,
                timeout=timeout
            )
            
            # 检查时间戳错误
            if response.status_code == 401:
                error_data = response.json()
                if 'Timestamp' in str(error_data):
                    logger.warning(f"时间戳过期，尝试重新签名...")
                    time.sleep(1)
                    continue
            
            return response.json()
            
        except requests.exceptions.SSLError as e:
            logger.warning(f"SSL错误 (尝试 {attempt+1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)  # 指数退避
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"连接错误 (尝试 {attempt+1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)
        except requests.exceptions.Timeout as e:
            logger.warning(f"超时 (尝试 {attempt+1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"未知错误: {e}")
            time.sleep(2 ** attempt)
    
    logger.error(f"请求失败，已重试 {max_retries} 次")
    return None


# ============ API功能 ============
def get_balance():
    """获取账户余额"""
    return request_with_retry('GET', '/api/v5/account/balance')


def get_ticker(symbol):
    """获取行情"""
    return request_with_retry('GET', f'/api/v5/market/ticker?instId={symbol}')


def place_order(symbol, side, size, price=None, td_mode='cash'):
    """下单"""
    path = '/api/v5/trade/order'
    body = {
        'instId': symbol,
        'tdMode': td_mode,  # cash=现货, isolated=逐仓杠杆
        'side': side,
        'ordType': 'limit' if price else 'market',
        'sz': str(size),
    }
    if price:
        body['px'] = str(price)
    
    return request_with_retry('POST', path, body)


def get_order_status(ord_id, symbol):
    """查询订单状态"""
    return request_with_retry('GET', f'/api/v5/trade/order?ordId={ord_id}&instId={symbol}')


# ============ 交易策略 ============
class TradingBot:
    """交易机器人"""
    
    def __init__(self):
        self.positions = {}  # 持仓
        self.alerts = {}     # 价格警报
    
    def get_current_price(self, symbol):
        """获取当前价格"""
        ticker = get_ticker(symbol)
        if ticker and ticker.get('code') == '0':
            return float(ticker['data'][0]['last'])
        return None
    
    def check_support_resistance(self, symbol, price):
        """检查支撑/阻力位"""
        supports = SUPPORTS.get(symbol, [])
        resistances = RESISTANCES.get(symbol, [])
        
        result = {'symbol': symbol, 'price': price}
        
        # 检查支撑位
        for support in supports:
            if price >= support and price < support * 1.02:
                distance = (price - support) / price * 100
                result['nearest_support'] = support
                result['support_distance'] = f"-{distance:.2f}%"
                break
        
        # 检查阻力位
        for resistance in resistances:
            if price <= resistance and price > resistance * 0.98:
                distance = (resistance - price) / price * 100
                result['nearest_resistance'] = resistance
                result['resistance_distance'] = f"+{distance:.2f}%"
                break
        
        return result
    
    def spot_buy(self, symbol, usdt_amount):
        """现货买入"""
        price = self.get_current_price(symbol)
        if not price:
            logger.error("无法获取价格")
            return None
        
        size = usdt_amount / price
        logger.info(f"现货买入 {symbol}: {usdt_amount} USDT @ ${price:,.2f}")
        
        result = place_order(symbol, 'buy', size, td_mode='cash')
        
        if result and result.get('code') == '0':
            logger.info(f"✅ 买入成功: {result['data'][0]['ordId']}")
            return result
        else:
            logger.error(f"❌ 买入失败: {result}")
            return result
    
    def spot_sell(self, symbol, size):
        """现货卖出"""
        price = self.get_current_price(symbol)
        if not price:
            logger.error("无法获取价格")
            return None
        
        logger.info(f"现货卖出 {symbol}: {size} @ ${price:,.2f}")
        
        result = place_order(symbol, 'sell', size, td_mode='cash')
        
        if result and result.get('code') == '0':
            logger.info(f"✅ 卖出成功: {result['data'][0]['ordId']}")
            return result
        else:
            logger.error(f"❌ 卖出失败: {result}")
            return result
    
    def check_buy_signal(self, symbol):
        """
        检查买入信号
        策略：价格接近支撑位
        """
        price = self.get_current_price(symbol)
        if not price:
            return False, "无法获取价格"
        
        supports = SUPPORTS.get(symbol, [])
        for support in supports:
            if support * 0.99 <= price <= support * 1.02:
                return True, f"价格接近支撑位 ${support:,}"
        
        return False, "未到买入时机"
    
    def check_sell_signal(self, symbol):
        """
        检查卖出信号
        策略：价格达到止盈或止损
        """
        return False, "需要实现持仓检查"
    
    def monitor_loop(self, symbol='BTC-USDT', interval=60):
        """
        持续监控循环
        """
        logger.info(f"开始监控 {symbol}，间隔 {interval}秒")
        
        while True:
            try:
                price = self.get_current_price(symbol)
                
                if price:
                    # 检查支撑/阻力
                    levels = self.check_support_resistance(symbol, price)
                    
                    logger.info(f"📈 {symbol}: ${price:,.2f}")
                    
                    if 'nearest_support' in levels:
                        logger.info(f"   支撑位: ${levels['nearest_support']:,} {levels['support_distance']}")
                    
                    if 'nearest_resistance' in levels:
                        logger.info(f"   阻力位: ${levels['nearest_resistance']:,} {levels['resistance_distance']}")
                    
                    # 检查买入信号
                    should_buy, reason = self.check_buy_signal(symbol)
                    if should_buy:
                        logger.info(f"🟢 买入信号: {reason}")
                        self.spot_buy(symbol, TRADE_AMOUNT)
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("监控已停止")
                break
            except Exception as e:
                logger.error(f"监控错误: {e}")
                time.sleep(interval)


# ============ 命令处理 ============
def cmd_status():
    """查看状态"""
    print("\n📊 交易机器人状态")
    print("=" * 50)
    
    # 余额
    balance = get_balance()
    if balance and balance.get('code') == '0':
        details = balance.get('data', [{}])[0].get('details', [])
        for item in details:
            ccy = item.get('ccy')
            avail = float(item.get('availBal', 0))
            if avail > 0:
                print(f"   {ccy}: {avail}")
    
    # BTC价格
    ticker = get_ticker('BTC-USDT')
    if ticker and ticker.get('code') == '0':
        price = float(ticker['data'][0]['last'])
        print(f"\n📈 BTC: ${price:,.2f}")
    
    # 支撑位
    print(f"\n🛡️ 支撑位: $66,000, $65,000, $64,000")
    print(f"   当前距离: {(price - 66000) / price * 100:.2f}%")


def cmd_buy(amount):
    """现货买入"""
    bot = TradingBot()
    result = bot.spot_buy('BTC-USDT', float(amount))
    if result and result.get('code') == '0':
        print(f"\n✅ 买入成功!")
    else:
        print(f"\n❌ 买入失败")


def cmd_sell(size):
    """现货卖出"""
    bot = TradingBot()
    result = bot.spot_sell('BTC-USDT', float(size))
    if result and result.get('code') == '0':
        print(f"\n✅ 卖出成功!")
    else:
        print(f"\n❌ 卖出失败")


def cmd_monitor(symbol='BTC-USDT', interval=60):
    """启动监控"""
    bot = TradingBot()
    bot.monitor_loop(symbol, interval)


def cmd_test():
    """测试连接"""
    print("\n🧪 测试API连接...")
    
    for attempt in range(3):
        print(f"   尝试 {attempt+1}/3...")
        
        ticker = get_ticker('BTC-USDT')
        
        if ticker and ticker.get('code') == '0':
            price = float(ticker['data'][0]['last'])
            print(f"✅ 连接成功! BTC价格: ${price:,.2f}")
            return True
        else:
            print(f"   失败: {ticker}")
            time.sleep(2)
    
    print("❌ 多次连接失败，请检查网络")
    return False


# ============ 主程序 ============
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    if command == 'status':
        cmd_status()
    elif command == 'buy':
        amount = sys.argv[2] if len(sys.argv) > 2 else '5'
        cmd_buy(amount)
    elif command == 'sell':
        size = sys.argv[2] if len(sys.argv) > 2 else '0.001'
        cmd_sell(size)
    elif command == 'monitor':
        symbol = sys.argv[2] if len(sys.argv) > 2 else 'BTC-USDT'
        interval = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        cmd_monitor(symbol, interval)
    elif command == 'test':
        cmd_test()
    elif command == 'loop':
        cmd_monitor()
    else:
        print(f"未知命令: {command}")
        print("\n可用命令:")
        print("  python3 monitor.py status      # 查看状态")
        print("  python3 monitor.py buy 5       # 买入5 USDT")
        print("  python3 monitor.py sell 0.001  # 卖出0.001 BTC")
        print("  python3 monitor.py monitor     # 持续监控")
        print("  python3 monitor.py test        # 测试连接")


if __name__ == '__main__':
    main()
