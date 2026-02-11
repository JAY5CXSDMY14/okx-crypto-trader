#!/usr/bin/env python3
"""
OKX加密货币交易机器人 - Python版
基于Lucky Trading Scripts设计理念

功能：
1. 账户查询
2. 下单交易
3. 移动止损
4. 价格警报

使用方法：
python3 okx_trader.py status      # 查看账户状态
python3 okx_trader.py buy BTC 5   # 买入5 USDT的BTC
python3 okx_trader.py sell BTC 0.001  # 卖出0.001 BTC
"""

import os
import sys
import json
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime

# ============ 配置 ============
API_KEY = os.environ.get('OKX_API_KEY', '')
API_SECRET = os.environ.get('OKX_API_SECRET', '')
PASSPHRASE = os.environ.get('OKX_PASSPHRASE', '')

BASE_URL = 'https://www.okx.com'

# 交易参数
TRADE_AMOUNT = 5  # 每次交易5 USDT
STOP_LOSS = 0.10   # 止损10%
TAKE_PROFIT = 0.30  # 止盈30%

# 支撑位
SUPPORT_LEVELS = {
    'BTC-USDT': [66000, 65000, 64000],
    'ETH-USDT': [1950, 1900, 1850],
}

# ============ API工具 ============
def sign(timestamp, method, path, body=''):
    """生成签名"""
    message = f"{timestamp}{method}{path}{body}"
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    return signature_b64

def get_timestamp():
    """获取ISO格式时间戳"""
    import datetime
    now = datetime.datetime.utcnow()
    return now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def request(method, path, body=None):
    """发送API请求"""
    timestamp = get_timestamp()
    signature = sign(timestamp, method, path, json.dumps(body) if body else '')
    
    headers = {
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json',
    }
    
    url = f"{BASE_URL}{path}"
    
    if body:
        headers['Content-Type'] = 'application/json'
    
    response = requests.request(
        method,
        url,
        headers=headers,
        json=body if body else None,
        timeout=15
    )
    
    return response.json()

# ============ 功能函数 ============
def get_balance():
    """获取账户余额"""
    return request('GET', '/api/v5/account/balance')

def get_ticker(symbol):
    """获取行情"""
    return request('GET', f'/api/v5/market/ticker?instId={symbol}')

def place_order(symbol, side, size, price=None):
    """下单"""
    path = '/api/v5/trade/order'
    body = {
        'instId': symbol,
        'tdMode': 'cash',
        'side': side,
        'ordType': 'limit' if price else 'market',
        'sz': size,
    }
    if price:
        body['px'] = price
    
    return request('POST', path, body)

def get_order(ord_id, symbol):
    """查询订单"""
    return request('GET', f'/api/v5/trade/order?ordId={ord_id}&instId={symbol}')

# ============ 移动止损 ============
class TrailingStop:
    """移动止损管理器"""
    
    def __init__(self, activation_price, trail_distance):
        self.activation_price = activation_price  # 激活价格
        self.trail_distance = trail_distance        # 追踪距离
        self.highest_price = 0                     # 最高价格
        self.triggered = False                     # 是否已触发
    
    def update(self, current_price):
        """更新价格，返回触发信号"""
        if self.triggered:
            return None
        
        if current_price >= self.activation_price:
            if current_price > self.highest_price:
                self.highest_price = current_price
                new_stop = self.highest_price - self.trail_distance
                return {
                    'action': 'update',
                    'stop_price': new_stop,
                    'message': f'止损更新到 ${new_stop:.2f}'
                }
            elif current_price <= self.highest_price - self.trail_distance:
                self.triggered = True
                return {
                    'action': 'trigger',
                    'stop_price': self.highest_price - self.trail_distance,
                    'message': f'触发止损！卖出价 ${current_price:.2f}'
                }
        
        return None

# ============ 价格警报 ============
class PriceAlert:
    """价格警报管理器"""
    
    def __init__(self, alerts_file='alerts.json'):
        self.alerts_file = alerts_file
        self.alerts = self.load_alerts()
    
    def load_alerts(self):
        """加载警报配置"""
        try:
            with open(self.alerts_file, 'r') as f:
                return json.load(f)
        except:
            return {'above': [], 'below': []}
    
    def save_alerts(self):
        """保存警报配置"""
        with open(self.alerts_file, 'w') as f:
            json.dump(self.alerts, f, indent=2)
    
    def add_alert(self, symbol, price, condition='above'):
        """添加警报"""
        alert = {
            'symbol': symbol,
            'price': price,
            'condition': condition,
            'created_at': datetime.now().isoformat()
        }
        self.alerts[condition].append(alert)
        self.save_alerts()
        return alert
    
    def check(self, symbol, current_price):
        """检查是否触发警报"""
        triggered = []
        
        for alert in self.alerts.get('above', []):
            if alert['symbol'] == symbol and current_price >= alert['price']:
                triggered.append(alert)
        
        for alert in self.alerts.get('below', []):
            if alert['symbol'] == symbol and current_price <= alert['price']:
                triggered.append(alert)
        
        return triggered

# ============ 命令处理 ============
def cmd_status():
    """查看账户状态"""
    print("\n📊 账户状态")
    print("="*40)
    
    balance = get_balance()
    
    if balance.get('code') != '0':
        print(f"❌ 获取失败: {balance.get('msg')}")
        return
    
    details = balance.get('data', [{}])[0].get('details', [])
    
    assets = {}
    for asset in details:
        ccy = asset.get('ccy')
        avail = float(asset.get('availBal', 0))
        if avail > 0:
            assets[ccy] = avail
    
    print(f"💰 余额:")
    for ccy, amount in assets.items():
        print(f"   {ccy}: {amount}")
    
    # 检查BTC价格和持仓
    ticker = get_ticker('BTC-USDT')
    if ticker.get('code') == '0':
        price = float(ticker['data'][0]['last'])
        btc = assets.get('BTC', 0)
        print(f"\n📈 BTC当前价格: ${price:,.2f}")
        print(f"   BTC持仓: {btc}")
        print(f"   价值: ${btc * price:,.2f}")

def cmd_price(symbol):
    """查看价格"""
    ticker = get_ticker(f'{symbol}-USDT')
    
    if ticker.get('code') != '0':
        print(f"❌ 获取失败: {ticker.get('msg')}")
        return
    
    data = ticker['data'][0]
    price = float(data['last'])
    high24h = float(data['high24h'])
    low24h = float(data['low24h'])
    change24h = float(data['sodUtc8']) - price
    
    print(f"\n📈 {symbol}价格")
    print("="*40)
    print(f"   当前: ${price:,.2f}")
    print(f"   24h高: ${high24h:,.2f}")
    print(f"   24h低: ${low24h:,.2f}")
    print(f"   涨跌: ${change24h:,.2f}")
    
    # 检查支撑位
    supports = SUPPORT_LEVELS.get(f'{symbol}-USDT', [])
    for support in supports:
        if price > support:
            distance = (price - support) / price * 100
            print(f"\n   支撑位: ${support:,} (距离 {distance:.2f}%)")

def cmd_alert(symbol, price, condition='above'):
    """添加警报"""
    alert = PriceAlert()
    result = alert.add_alert(symbol, price, condition)
    print(f"\n🔔 警报已添加")
    print(f"   币种: {symbol}")
    print(f"   条件: {'高于' if condition == 'above' else '低于'} ${price:,.2f}")
    print(f"   时间: {result['created_at']}")

def cmd_check_alerts():
    """检查所有警报"""
    alert = PriceAlert()
    ticker = get_ticker('BTC-USDT')
    
    if ticker.get('code') != '0':
        print(f"❌ 获取价格失败")
        return
    
    price = float(ticker['data'][0]['last'])
    triggered = alert.check('BTC', price)
    
    print(f"\n🔔 BTC警报检查 (当前: ${price:,.2f})")
    print("="*40)
    
    if triggered:
        print("⚠️  触发的警报:")
        for t in triggered:
            print(f"   - {t['condition']} ${t['price']:,.2f}")
    else:
        print("   无警报触发")

# ============ 主程序 ============
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    if command == 'status':
        cmd_status()
    elif command == 'price':
        symbol = sys.argv[2] if len(sys.argv) > 2 else 'BTC'
        cmd_price(symbol)
    elif command == 'alert':
        symbol = sys.argv[2]
        price = float(sys.argv[3])
        condition = sys.argv[4] if len(sys.argv) > 4 else 'above'
        cmd_alert(symbol, price, condition)
    elif command == 'check-alerts':
        cmd_check_alerts()
    else:
        print(f"未知命令: {command}")
        print("可用命令:")
        print("  python3 okx_trader.py status       # 查看账户状态")
        print("  python3 okx_trader.py price BTC  # 查看价格")
        print("  python3 okx_trader.py alert BTC 70000 above  # 添加警报")
        print("  python3 okx_trader.py check-alerts # 检查警报")

if __name__ == '__main__':
    main()
