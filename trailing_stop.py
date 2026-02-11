#!/usr/bin/env python3
"""
移动止损模块
功能：
1. 移动止损（Trailing Stop）
2. 自动止盈跟踪
3. 条件触发执行

参考Lucky Trading Scripts设计
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from enum import Enum

sys.path.insert(0, '.')
from okx_api import OKXClient

# 移动止损配置
DEFAULT_CONFIG = {
    'activation_price_ratio': 0.02,  # 盈利2%后激活
    'trail_distance_ratio': 0.01,    # 追踪距离1%
    'check_interval': 5,             # 检查间隔5秒
    'auto_execute': False,           # 默认不自动执行
}


class TrailingStop:
    """
    移动止损管理器
    
    用法:
    1. 创建实例
    2. 设置激活价格和追踪距离
    3. 启动监控（可选自动执行）
    """
    
    def __init__(self, config=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.client = OKXClient()
        
        # 状态
        self.positions = {}  # {symbol: position_info}
        self.running = False
        self.monitor_thread = None
        
        # 回调函数
        self.on_update = None   # 止损更新时调用
        self.on_trigger = None  # 止损触发时调用
    
    def add_position(self, symbol, entry_price, size, side='long'):
        """
        添加需要跟踪的持仓
        
        Args:
            symbol: 交易对
            entry_price: 入场价格
            size: 持仓数量
            side: long(做多)/short(做空)
        """
        activation_price = self._calc_activation(entry_price, side)
        trail_distance = self._calc_trail_distance(entry_price)
        
        self.positions[symbol] = {
            'entry_price': entry_price,
            'size': size,
            'side': side,
            'entry_time': datetime.now().isoformat(),
            'activation_price': activation_price,
            'trail_distance': trail_distance,
            'highest_price': entry_price if side == 'long' else 0,
            'lowest_price': entry_price if side == 'short' else float('inf'),
            'stop_price': None,
            'status': 'pending',  # pending/active/triggered
        }
        
        print(f"✅ 添加持仓: {symbol} {side} {size} @ {entry_price:,.2f}")
        print(f"   激活价: {activation_price:,.2f} (盈利{self.config['activation_price_ratio']*100:.0f}%)")
        print(f"   追踪距离: {trail_distance:,.2f}")
    
    def remove_position(self, symbol):
        """移除持仓"""
        if symbol in self.positions:
            del self.positions[symbol]
            print(f"✅ 移除持仓: {symbol}")
    
    def _calc_activation(self, entry_price, side):
        """计算激活价格"""
        ratio = self.config['activation_price_ratio']
        if side == 'long':
            return entry_price * (1 + ratio)
        else:
            return entry_price * (1 - ratio)
    
    def _calc_trail_distance(self, entry_price):
        """计算追踪距离"""
        return entry_price * self.config['trail_distance_ratio']
    
    def check_price(self, symbol, current_price):
        """
        检查价格，更新止损
        
        Returns:
            (triggered, info)
        """
        if symbol not in self.positions:
            return False, None
        
        pos = self.positions[symbol]
        side = pos['side']
        entry_price = pos['entry_price']
        
        # 更新最高/最低价
        if side == 'long':
            if current_price > pos['highest_price']:
                pos['highest_price'] = current_price
        else:
            if current_price < pos['lowest_price']:
                pos['lowest_price'] = current_price
        
        # 检查是否激活
        if pos['status'] == 'pending':
            if side == 'long' and current_price >= pos['activation_price']:
                pos['status'] = 'active'
                pos['stop_price'] = current_price - pos['trail_distance']
                print(f"🟢 激活止损: {symbol} @ {pos['stop_price']:,.2f}")
            elif side == 'short' and current_price <= pos['activation_price']:
                pos['status'] = 'active'
                pos['stop_price'] = current_price + pos['trail_distance']
                print(f"🟢 激活止损: {symbol} @ {pos['stop_price']:,.2f}")
        
        # 检查是否触发
        if pos['status'] == 'active':
            if side == 'long' and current_price <= pos['stop_price']:
                pos['status'] = 'triggered'
                return True, pos
            elif side == 'short' and current_price >= pos['stop_price']:
                pos['status'] = 'triggered'
                return True, pos
            
            # 更新止损价
            if side == 'long':
                new_stop = current_price - pos['trail_distance']
                if new_stop > pos['stop_price']:
                    old_stop = pos['stop_price']
                    pos['stop_price'] = new_stop
                    if self.on_update:
                        self.on_update(symbol, old_stop, new_stop)
            else:
                new_stop = current_price + pos['trail_distance']
                if new_stop < pos['stop_price']:
                    old_stop = pos['stop_price']
                    pos['stop_price'] = new_stop
                    if self.on_update:
                        self.on_update(symbol, old_stop, new_stop)
        
        return False, None
    
    def start_monitor(self, symbol, check_interval=None):
        """启动监控线程"""
        if self.running:
            print("⚠️ 监控已在运行中")
            return
        
        self.running = True
        interval = check_interval or self.config['check_interval']
        
        def run():
            print(f"🚀 启动移动止损监控: {symbol}, 间隔{interval}秒")
            while self.running:
                try:
                    # 获取当前价格
                    result = self.client.get_ticker(symbol)
                    if result and result.get('code') == '0':
                        current_price = float(result['data'][0]['last'])
                        triggered, pos = self.check_price(symbol, current_price)
                        
                        if triggered:
                            print(f"\n🚨 止损触发: {symbol} @ {pos['stop_price']:,.2f}")
                            if self.on_trigger:
                                self.on_trigger(symbol, pos)
                            
                            # 自动平仓（如果配置）
                            if self.config['auto_execute']:
                                self._close_position(symbol, pos)
                                self.running = False
                                break
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    print(f"❌ 监控错误: {e}")
                    time.sleep(interval)
            
            print("👋 监控已停止")
        
        self.monitor_thread = threading.Thread(target=run, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitor(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        print("✅ 监控已停止")
    
    def _close_position(self, symbol, pos):
        """平仓（需要API Key）"""
        try:
            side = 'sell' if pos['side'] == 'long' else 'buy'
            result = self.client.place_order(symbol, side, pos['size'], td_mode='cash')
            
            if result and result.get('code') == '0':
                print(f"✅ 自动平仓成功: {symbol}")
                self.remove_position(symbol)
            else:
                print(f"❌ 自动平仓失败: {result.get('msg')}")
        except Exception as e:
            print(f"❌ 平仓错误: {e}")
    
    def get_status(self):
        """获取状态"""
        return {
            'running': self.running,
            'positions': self.positions,
            'config': self.config,
        }
    
    def print_status(self):
        """打印状态"""
        print("\n🎯 移动止损状态")
        print("=" * 60)
        print(f"运行状态: {'✅ 运行中' if self.running else '❌ 已停止'}")
        print(f"持仓数量: {len(self.positions)}")
        
        for symbol, pos in self.positions.items():
            print(f"\n📋 {symbol}:")
            print(f"   方向: {pos['side']} ({'做多' if pos['side']=='long' else '做空'})")
            print(f"   入场价: {pos['entry_price']:,.2f}")
            print(f"   数量: {pos['size']}")
            print(f"   状态: {pos['status']}")
            
            if pos['stop_price']:
                print(f"   当前止损: {pos['stop_price']:,.2f}")
            
            if pos['status'] == 'active':
                if pos['side'] == 'long':
                    profit = (pos['highest_price'] - pos['entry_price']) / pos['entry_price'] * 100
                else:
                    profit = (pos['entry_price'] - pos['lowest_price']) / pos['entry_price'] * 100
                print(f"   浮动盈利: {profit:.2f}%")


# ============ 使用示例 ============
if __name__ == '__main__':
    # 创建实例
    ts = TrailingStop({
        'activation_price_ratio': 0.02,  # 盈利2%激活
        'trail_distance_ratio': 0.01,    # 追踪1%
        'check_interval': 5,
    })
    
    # 添加回调
    def on_update(symbol, old_stop, new_stop):
        print(f"📈 止损更新: {symbol} ${old_stop:,.2f} → ${new_stop:,.2f}")
    
    def on_trigger(symbol, pos):
        print(f"🚨 触发止损！{symbol} ${pos['stop_price']:,.2f}")
    
    ts.on_update = on_update
    ts.on_trigger = on_trigger
    
    # 添加持仓（模拟）
    # ts.add_position('BTC-USDT', 66000, 0.001, 'long')
    
    # 查看状态
    ts.print_status()
    
    # 启动监控（需要先添加持仓）
    # ts.start_monitor('BTC-USDT')
    
    # 使用完成后停止
    # ts.stop_monitor()
