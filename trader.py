#!/usr/bin/env python3
"""
OKX加密货币交易机器人 - Python版
功能：账户查询、下单、止损止盈、价格警报

使用方式：
    python3 trader.py status        # 查看账户
    python3 trader.py price BTC    # 查看价格
    python3 trader.py buy BTC 5    # 买入5 USDT
    python3 trader.py sell BTC 0.001  # 卖出0.001 BTC
    python3 trader.py alert BTC 70000 above  # 添加警报
    python3 trader.py alerts        # 查看警报
"""

import os
import sys
import json
import time
from datetime import datetime
from okx_api import OKXClient

# 配置
client = OKXClient()

# 交易参数
TRADE_AMOUNT = 5      # 每次5 USDT
STOP_LOSS = 0.10      # 止损10%
TAKE_PROFIT = 0.30    # 止盈30%

# 支撑位
SUPPORTS = {
    'BTC-USDT': [66000, 65000, 64000],
    'ETH-USDT': [1950, 1900, 1850],
}

# 警报文件
ALERTS_FILE = 'alerts.json'


# ============ 工具函数 ============
def print_header(text):
    print(f"\n{text}")
    print("=" * 50)

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_info(text):
    print(f"ℹ️  {text}")


# ============ 账户功能 ============
def cmd_status():
    """查看账户状态"""
    print_header("账户状态")
    
    result = client.get_balance()
    
    if result.get('code') != '0':
        print_error(f"获取失败: {result.get('msg')}")
        return
    
    details = result.get('data', [{}])[0].get('details', [])
    assets = {}
    
    for item in details:
        ccy = item.get('ccy')
        avail = float(item.get('availBal', 0))
        if avail > 0:
            assets[ccy] = avail
    
    print_info(f"账户余额:")
    for ccy, amount in assets.items():
        print(f"   {ccy}: {amount}")
    
    # BTC价格
    ticker = client.get_ticker('BTC-USDT')
    if ticker.get('code') == '0':
        price = float(ticker['data'][0]['last'])
        btc = assets.get('BTC', 0)
        print_info(f"\nBTC价格: ${price:,.2f}")
        print(f"   BTC持仓: {btc}")
        print(f"   价值: ${btc * price:,.2f}")


# ============ 行情功能 ============
def cmd_price(symbol='BTC'):
    """查看价格"""
    print_header(f"{symbol}行情")
    
    ticker = client.get_ticker(f'{symbol}-USDT')
    
    if ticker.get('code') != '0':
        print_error(f"获取失败: {ticker.get('msg')}")
        return
    
    data = ticker['data'][0]
    price = float(data['last'])
    high24h = float(data['high24h'])
    low24h = float(data['low24h'])
    
    print_info(f"当前价格: ${price:,.2f}")
    print(f"   24h高: ${high24h:,.2f}")
    print(f"   24h低: ${low24h:,.2f}")
    
    # 支撑位
    supports = SUPPORTS.get(f'{symbol}-USDT', [])
    for support in supports:
        if price > support:
            distance = (price - support) / price * 100
            print(f"\n   支撑位 ${support:,} (距离 {distance:.2f}%)")


# ============ 交易功能 ============
def cmd_buy(symbol, usdt_amount):
    """买入"""
    print_header(f"买入 {symbol}")
    
    # 获取价格
    ticker = client.get_ticker(f'{symbol}-USDT')
    if ticker.get('code') != '0':
        print_error(f"获取价格失败")
        return
    
    price = float(ticker['data'][0]['last'])
    size = usdt_amount / price
    
    print_info(f"买入金额: {usdt_amount} USDT")
    print(f"   价格: ${price:,.2f}")
    print(f"   数量: {size:.8f} {symbol.replace('-USDT', '')}")
    
    # 下单
    result = client.place_order(f'{symbol}-USDT', 'buy', size)
    
    if result.get('code') == '0':
        print_success(f"下单成功!")
        print(f"   订单ID: {result['data'][0]['ordId']}")
    else:
        print_error(f"下单失败: {result.get('msg')}")


def cmd_sell(symbol, size):
    """卖出"""
    print_header(f"卖出 {symbol}")
    
    ticker = client.get_ticker(f'{symbol}-USDT')
    if ticker.get('code') != '0':
        print_error(f"获取价格失败")
        return
    
    price = float(ticker['data'][0]['last'])
    
    print_info(f"卖出数量: {size} {symbol.replace('-USDT', '')}")
    print(f"   当前价格: ${price:,.2f}")
    print(f"   价值: ${size * price:,.2f}")
    
    result = client.place_order(f'{symbol}-USDT', 'sell', size)
    
    if result.get('code') == '0':
        print_success(f"卖出成功!")
    else:
        print_error(f"卖出失败: {result.get('msg')}")


# ============ 警报功能 ============
def load_alerts():
    """加载警报"""
    try:
        with open(ALERTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'above': [], 'below': []}

def save_alerts(alerts):
    """保存警报"""
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f, indent=2)

def cmd_alert(symbol, price, condition='above'):
    """添加警报"""
    alerts = load_alerts()
    
    new_alert = {
        'symbol': symbol,
        'price': float(price),
        'condition': condition,
        'created': datetime.now().isoformat()
    }
    
    alerts[condition].append(new_alert)
    save_alerts(alerts)
    
    cond_text = '高于' if condition == 'above' else '低于'
    print_success(f"警报已添加: {symbol} {cond_text} ${price:,.2f}")

def cmd_alerts():
    """查看所有警报"""
    print_header("价格警报")
    
    alerts = load_alerts()
    
    # 检查BTC
    ticker = client.get_ticker('BTC-USDT')
    if ticker.get('code') == '0':
        price = float(ticker['data'][0]['last'])
        print_info(f"BTC当前价格: ${price:,.2f}\n")
    
    # 显示警报
    if alerts['above']:
        print("🔔 高于警报:")
        for a in alerts['above']:
            print(f"   {a['symbol']} > ${a['price']:,.2f}")
    
    if alerts['below']:
        print("🔕 低于警报:")
        for a in alerts['below']:
            print(f"   {a['symbol']} < ${a['price']:,.2f}")
    
    if not alerts['above'] and not alerts['below']:
        print("暂无警报")


# ============ 止损止盈 ============
def cmd_tp_sl(symbol, stop_loss=STOP_LOSS, take_profit=TAKE_PROFIT):
    """计算止损止盈"""
    print_header(f"{symbol} 止损止盈设置")
    
    ticker = client.get_ticker(f'{symbol}-USDT')
    if ticker.get('code') != '0':
        print_error("获取价格失败")
        return
    
    price = float(ticker['data'][0]['last'])
    
    sl_price = price * (1 - stop_loss)
    tp_price = price * (1 + take_profit)
    
    print_info(f"当前价格: ${price:,.2f}")
    print(f"\n🛡️ 止损 (-{stop_loss*100:.0f}%): ${sl_price:,.2f}")
    print(f"   触发条件: 价格跌至 ${sl_price:,.2f}")
    print(f"\n🎯 止盈 (+{take_profit*100:.0f}%): ${tp_price:,.2f}")
    print(f"   触发条件: 价格涨至 ${tp_price:,.2f}")


# ============ 主程序 ============
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == 'status':
        cmd_status()
    elif cmd == 'price':
        symbol = sys.argv[2] if len(sys.argv) > 2 else 'BTC'
        cmd_price(symbol)
    elif cmd == 'buy':
        if len(sys.argv) < 4:
            print("用法: python3 trader.py buy BTC 5")
            return
        symbol = sys.argv[2] + '-USDT'
        amount = float(sys.argv[3])
        cmd_buy(symbol, amount)
    elif cmd == 'sell':
        if len(sys.argv) < 4:
            print("用法: python3 trader.py sell BTC 0.001")
            return
        symbol = sys.argv[2] + '-USDT'
        size = float(sys.argv[3])
        cmd_sell(symbol, size)
    elif cmd == 'alert':
        if len(sys.argv) < 4:
            print("用法: python3 trader.py alert BTC 70000 above")
            return
        symbol = sys.argv[2]
        price = float(sys.argv[3])
        condition = sys.argv[4] if len(sys.argv) > 4 else 'above'
        cmd_alert(symbol, price, condition)
    elif cmd == 'alerts':
        cmd_alerts()
    elif cmd == 'tpsl':
        symbol = sys.argv[2] + '-USDT' if len(sys.argv) > 2 else 'BTC-USDT'
        cmd_tp_sl(symbol)
    else:
        print(f"未知命令: {cmd}")
        print("\n可用命令:")
        print("  status       # 查看账户状态")
        print("  price BTC    # 查看价格")
        print("  buy BTC 5    # 买入5 USDT")
        print("  sell BTC 0.001  # 卖出0.001 BTC")
        print("  alert BTC 70000 above  # 添加警报")
        print("  alerts        # 查看所有警报")
        print("  tpsl BTC     # 计算止损止盈")


if __name__ == '__main__':
    main()
