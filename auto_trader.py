#!/usr/bin/env python3
"""
自动交易策略模块
功能：
1. 支撑位自动买入
2. 阻力位自动卖出
3. 网格交易策略
4. 定期定额投资
"""

import os
import sys
import time
import json
import datetime
from pathlib import Path

# 导入核心模块
sys.path.insert(0, '.')
from okx_api import OKXClient
from risk_manager import RiskManager
from trading_journal import TradingJournal

# 配置
STRATEGY_CONFIG = {
    # 定期定额投资
    'dca': {
        'enabled': True,
        'amount': 5,          # 每次5 USDT
        'interval_days': 7,   # 每周一次
        'last_run': None,
    },
    
    # 支撑位买入
    'support_buy': {
        'enabled': True,
        'amount': 10,         # 10 USDT
        'supports': [66000, 65000, 64000],
        'min_distance': 0.02, # 距离支撑位2%以内
    },
    
    # 阻力位卖出
    'resistance_sell': {
        'enabled': True,
        'min_profit': 0.05,   # 最小盈利5%
        'resistances': [67000, 68000, 70000],
        'min_distance': 0.02, # 距离阻力位2%以内
    },
    
    # 网格交易
    'grid': {
        'enabled': False,
        'upper': 70000,
        'lower': 60000,
        'grid_size': 10,      # 10个网格
        'amount_per_grid': 10, # 每个网格10 USDT
    },
}


class AutoTrader:
    """自动交易机器人"""
    
    def __init__(self):
        self.client = OKXClient()
        self.risk = RiskManager()
        self.journal = TradingJournal()
        self.config = STRATEGY_CONFIG
        self.load_config()
    
    def load_config(self):
        """加载配置"""
        config_file = Path('auto_trader_config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                saved = json.load(f)
                self.config.update(saved)
    
    def save_config(self):
        """保存配置"""
        with open('auto_trader_config.json', 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_price(self, symbol='BTC-USDT'):
        """获取当前价格"""
        try:
            result = self.client.get_ticker(symbol)
            if result and result.get('code') == '0':
                return float(result['data'][0]['last'])
        except:
            pass
        return None
    
    def get_balance(self):
        """获取余额"""
        try:
            result = self.client.get_balance()
            if result and result.get('code') == '0':
                return float(result['data'][0]['details'][0]['availBal'])
        except:
            pass
        return None
    
    # ========== 策略1: 定期定额投资 (DCA) ==========
    def check_dca(self, symbol='BTC-USDT'):
        """检查是否需要DCA"""
        config = self.config['dca']
        if not config['enabled']:
            return False, "DCA未启用"
        
        # 检查间隔
        last_run = config.get('last_run')
        if last_run:
            last = datetime.datetime.fromisoformat(last_run)
            if (datetime.datetime.now() - last).days < config['interval_days']:
                days_left = config['interval_days'] - (datetime.datetime.now() - last).days
                return False, f"还需{days_left}天"
        
        # 获取价格和余额
        price = self.get_price(symbol)
        balance = self.get_balance()
        
        if not price:
            return False, "无法获取价格"
        if not balance or balance < config['amount']:
            return False, f"余额不足 ({balance:.2f} USDT)"
        
        return True, f"DCA时机: 买入{config['amount']} USDT"
    
    def execute_dca(self, symbol='BTC-USDT'):
        """执行DCA"""
        config = self.config['dca']
        can_trade, reason = self.check_dca(symbol)
        
        if not can_trade:
            print(f"❌ DCA失败: {reason}")
            return False
        
        price = self.get_price(symbol)
        amount = config['amount']
        size = amount / price
        
        # 检查风险
        valid, msg = self.risk.check_order_size(symbol, size, price)
        if not valid:
            print(f"❌ 风险检查失败: {msg}")
            return False
        
        # 下单
        try:
            result = self.client.place_order(symbol, 'buy', size, td_mode='cash')
            
            if result and result.get('code') == '0':
                # 记录交易
                self.journal.add_trade({
                    'symbol': symbol,
                    'side': 'buy',
                    'size': size,
                    'price': price,
                    'fee': 0.1,
                    'pnl': None,
                    'status': 'open',
                    'time': datetime.datetime.now().isoformat(),
                    'note': 'DCA定期定额',
                })
                
                # 更新配置
                self.config['dca']['last_run'] = datetime.datetime.now().isoformat()
                self.save_config()
                
                print(f"✅ DCA成功: 买入{amount} USDT @ ${price:,.2f}")
                return True
            else:
                print(f"❌ DCA失败: {result.get('msg')}")
                return False
        except Exception as e:
            print(f"❌ DCA错误: {e}")
            return False
    
    # ========== 策略2: 支撑位买入 ==========
    def check_support_buy(self, symbol='BTC-USDT'):
        """检查支撑位买入信号"""
        config = self.config['support_buy']
        if not config['enabled']:
            return False, "支撑买入未启用"
        
        price = self.get_price(symbol)
        if not price:
            return False, "无法获取价格"
        
        for support in config['supports']:
            # 检查是否接近支撑位（2%以内）
            distance = (support - price) / price
            if 0 >= distance >= -config['min_distance']:
                return True, f"价格接近支撑位 ${support:,} (距离{distance*100:.1f}%)"
        
        return False, "未到支撑位"
    
    def execute_support_buy(self, symbol='BTC-USDT'):
        """执行支撑位买入"""
        config = self.config['support_buy']
        can_trade, reason = self.check_support_buy(symbol)
        
        if not can_trade:
            return False
        
        price = self.get_price(symbol)
        amount = config['amount']
        size = amount / price
        
        # 风险检查
        valid, msg = self.risk.check_order_size(symbol, size, price)
        if not valid:
            return False
        
        # 检查是否已持仓
        positions = self.journal.get_open_positions()
        for pos in positions:
            if pos['symbol'] == symbol and pos['side'] == 'buy':
                return False  # 已有持仓
        
        try:
            result = self.client.place_order(symbol, 'buy', size, td_mode='cash')
            
            if result and result.get('code') == '0':
                self.journal.add_trade({
                    'symbol': symbol,
                    'side': 'buy',
                    'size': size,
                    'price': price,
                    'fee': 0.1,
                    'status': 'open',
                    'time': datetime.datetime.now().isoformat(),
                    'note': '支撑位买入',
                })
                print(f"✅ 支撑位买入成功: ${price:,.2f}")
                return True
        except Exception as e:
            print(f"❌ 支撑位买入失败: {e}")
        
        return False
    
    # ========== 策略3: 阻力位卖出 ==========
    def check_resistance_sell(self, symbol='BTC-USDT'):
        """检查阻力位卖出信号"""
        config = self.config['resistance_sell']
        if not config['enabled']:
            return False, "阻力卖出未启用"
        
        price = self.get_price(symbol)
        if not price:
            return False, "无法获取价格"
        
        # 检查是否有盈利持仓
        positions = self.journal.get_open_positions()
        for pos in positions:
            if pos['symbol'] == symbol and pos['side'] == 'buy':
                profit = (price - pos['price']) / pos['price']
                if profit >= config['min_profit']:
                    # 检查是否接近阻力位
                    for resistance in config['resistances']:
                        distance = (resistance - price) / price
                        if 0 <= distance <= config['min_distance']:
                            return True, f"接近阻力位 ${resistance:,} (盈利{profit*100:.1f}%)"
        
        return False, "无卖出信号"
    
    def execute_resistance_sell(self, symbol='BTC-USDT'):
        """执行阻力位卖出"""
        config = self.config['resistance_sell']
        can_trade, reason = self.check_resistance_sell(symbol)
        
        if not can_trade:
            return False
        
        price = self.get_price(symbol)
        
        # 找出需要平仓的持仓
        positions = self.journal.get_open_positions()
        for pos in positions:
            if pos['symbol'] == symbol and pos['side'] == 'buy':
                try:
                    result = self.client.place_order(symbol, 'sell', pos['size'], td_mode='cash')
                    
                    if result and result.get('code') == '0':
                        self.journal.close_trade(symbol, price)
                        print(f"✅ 阻力位卖出成功: ${price:,.2f}")
                        return True
                except Exception as e:
                    print(f"❌ 阻力位卖出失败: {e}")
        
        return False
    
    # ========== 策略4: 网格交易 ==========
    def check_grid(self, symbol='BTC-USDT'):
        """检查网格交易"""
        config = self.config['grid']
        if not config['enabled']:
            return False, "网格交易未启用"
        
        price = self.get_price(symbol)
        if not price:
            return False, "无法获取价格"
        
        if price < config['lower'] or price > config['upper']:
            return False, "价格超出网格范围"
        
        return True, "价格在网格范围内"
    
    # ========== 主循环 ==========
    def run_once(self, symbol='BTC-USDT'):
        """运行一次检查"""
        print(f"\n🔄 自动交易检查 - {symbol}")
        print("=" * 60)
        
        price = self.get_price(symbol)
        balance = self.get_balance()
        
        print(f"📈 价格: ${price:,.2f}" if price else "❌ 无法获取价格")
        print(f"💰 余额: {balance:.2f} USDT" if balance else "❌ 无法获取余额")
        
        # 检查各策略
        strategies = [
            ('DCA定期定额', self.check_dca),
            ('支撑位买入', self.check_support_buy),
            ('阻力位卖出', self.check_resistance_sell),
        ]
        
        for name, check_func in strategies:
            can_trade, reason = check_func(symbol)
            status = "✅" if can_trade else "⏳"
            print(f"   {status} {name}: {reason}")
        
        # 执行策略
        results = []
        results.append(('支撑位买入', self.execute_support_buy(symbol)))
        results.append(('阻力位卖出', self.execute_resistance_sell(symbol)))
        results.append(('DCA定期定额', self.execute_dca(symbol)))
        
        return results
    
    def run_loop(self, symbol='BTC-USDT', interval=300):
        """运行监控循环"""
        print(f"🚀 启动自动交易监控")
        print(f"   交易对: {symbol}")
        print(f"   间隔: {interval}秒")
        print(f"   按Ctrl+C停止")
        
        try:
            while True:
                self.run_once(symbol)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
    
    def print_status(self):
        """打印状态"""
        print("\n🎯 自动交易状态")
        print("=" * 60)
        
        price = self.get_price('BTC-USDT')
        print(f"📈 BTC价格: ${price:,.2f}" if price else "❌ 无法获取价格")
        
        print("\n📋 策略配置:")
        for name, config in self.config.items():
            status = "✅" if config.get('enabled') else "❌"
            print(f"   {status} {name}")
        
        print("\n📊 交易统计:")
        self.journal.print_status()


# ============ 使用示例 ============
if __name__ == '__main__':
    trader = AutoTrader()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'status':
            trader.print_status()
        elif command == 'run':
            trader.run_once()
        elif command == 'loop':
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            trader.run_loop(interval=interval)
        elif command == 'dca':
            trader.execute_dca()
        elif command == 'support':
            trader.execute_support_buy()
        elif command == 'resistance':
            trader.execute_resistance_sell()
        else:
            print("可用命令:")
            print("  python3 auto_trader.py status    # 查看状态")
            print("  python3 auto_trader.py run       # 运行一次检查")
            print("  python3 auto_trader.py loop      # 持续监控")
            print("  python3 auto_trader.py dca       # 执行DCA")
            print("  python3 auto_trader.py support   # 执行支撑位买入")
            print("  python3 auto_trader.py resistance # 执行阻力位卖出")
    else:
        trader.print_status()
