#!/usr/bin/env python3
"""
风险管理模块
功能：
1. 仓位管理
2. 自动止损
3. 风险敞口控制
4. 杠杆倍数限制
"""

import os
import json
import datetime
from enum import Enum

# 配置
MAX_POSITION_RATIO = 0.2      # 单个仓位不超过总资金20%
MAX_LEVERAGE = 5              # 最大杠杆5倍
STOP_LOSS_DEFAULT = 0.05      # 默认止损5%
TAKE_PROFIT_DEFAULT = 0.10    # 默认止盈10%
RISK_PER_TRADE = 0.02         # 每笔交易风险2%


class OrderType(Enum):
    SPOT = "spot"
    LEVERAGE = "leverage"


class RiskManager:
    """风险管理器"""
    
    def __init__(self, total_balance=0):
        """
        Args:
            total_balance: 总资金（USDT）
        """
        self.total_balance = total_balance
        self.positions = {}  # 当前持仓
        self.daily_pnl = 0   # 今日盈亏
        self.daily_trades = 0  # 今日交易次数
    
    def update_balance(self, balance):
        """更新总资金"""
        self.total_balance = balance
    
    def check_order_size(self, symbol, size, price, order_type=OrderType.SPOT):
        """
        检查订单大小是否合理
        
        Returns:
            (is_valid, message, suggested_size)
        """
        order_value = size * price
        
        # 检查是否超过单笔最大金额
        max_order = self.total_balance * MAX_POSITION_RATIO
        if order_value > max_order:
            suggested = max_order / price
            return False, f"订单金额 ${order_value:.2f} 超过限制 ${max_order:.2f}", suggested
        
        # 检查是否低于最小金额
        if order_value < 5:
            return False, f"订单金额 ${order_value:.2f} 低于最小限制 $5", None
        
        return True, "OK", None
    
    def check_leverage(self, leverage):
        """
        检查杠杆倍数
        
        Returns:
            (is_valid, message)
        """
        if leverage > MAX_LEVERAGE:
            return False, f"杠杆 {leverage}x 超过限制 {MAX_LEVERAGE}x"
        
        return True, "OK"
    
    def calculate_position_size(self, entry_price, stop_loss, risk_ratio=RISK_PER_TRADE):
        """
        根据风险计算仓位大小
        
        公式: size = (total_balance * risk_ratio) / (entry_price - stop_loss) / entry_price
        
        Args:
            entry_price: 入场价格
            stop_loss: 止损价格
            risk_ratio: 风险比例
        
        Returns:
            建议仓位大小
        """
        risk_amount = self.total_balance * risk_ratio
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return 0
        
        # 仓位 = 风险金额 / 价格波动比例
        size = risk_amount / price_risk
        
        return size
    
    def calculate_stop_loss(self, entry_price, side, ratio=STOP_LOSS_DEFAULT):
        """
        计算止损价格
        
        Args:
            entry_price: 入场价格
            side: buy(做多) / sell(做空)
            ratio: 止损比例
        
        Returns:
            止损价格
        """
        if side == "buy":
            return entry_price * (1 - ratio)
        else:
            return entry_price * (1 + ratio)
    
    def calculate_take_profit(self, entry_price, side, ratio=TAKE_PROFIT_DEFAULT):
        """
        计算止盈价格
        """
        if side == "buy":
            return entry_price * (1 + ratio)
        else:
            return entry_price * (1 - ratio)
    
    def get_risk_reward_ratio(self, entry_price, stop_loss, take_profit):
        """
        计算风险收益比
        
        Returns:
            ratio: 风险:收益
        """
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        
        if risk == 0:
            return 0
        
        return reward / risk
    
    def can_open_new_position(self, symbol):
        """
        检查是否可以开新仓位
        
        Returns:
            (can_open, reason)
        """
        # 检查今日交易次数
        if self.daily_trades >= 10:
            return False, "今日交易次数已达上限(10次)"
        
        # 检查今日盈亏
        if self.daily_pnl < -self.total_balance * 0.1:
            return False, "今日亏损已达10%，暂停交易"
        
        # 检查总持仓数量
        if len(self.positions) >= 3:
            return False, "持仓数量已达上限(3个)"
        
        return True, "OK"
    
    def add_position(self, symbol, size, entry_price, side):
        """添加持仓记录"""
        self.positions[symbol] = {
            'size': size,
            'entry_price': entry_price,
            'side': side,
            'time': datetime.datetime.now().isoformat()
        }
        self.daily_trades += 1
    
    def remove_position(self, symbol):
        """移除持仓记录"""
        if symbol in self.positions:
            del self.positions[symbol]
    
    def update_pnl(self, pnl):
        """更新盈亏"""
        self.daily_pnl += pnl
    
    def get_status(self):
        """获取风险状态"""
        return {
            'total_balance': self.total_balance,
            'positions_count': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'can_trade': self.can_open_new_position('BTC-USDT')[0]
        }
    
    def print_status(self):
        """打印状态"""
        print("\n🛡️ 风险管理状态")
        print("=" * 50)
        print(f"💰 总资金: {self.total_balance:.2f} USDT")
        print(f"📊 持仓数量: {len(self.positions)}")
        print(f"📈 今日盈亏: {self.daily_pnl:.2f} USDT")
        print(f"🔢 今日交易: {self.daily_trades}次")
        
        can_trade, reason = self.can_open_new_position('BTC-USDT')
        print(f"\n{'✅' if can_trade else '❌'} 交易状态: {reason}")
        
        if self.positions:
            print("\n📋 当前持仓:")
            for symbol, pos in self.positions.items():
                print(f"   {symbol}: {pos['size']:.8f} @ {pos['entry_price']:,.2f} ({pos['side']})")


# ============ 使用示例 ============
if __name__ == '__main__':
    # 创建风险管理器
    risk = RiskManager(total_balance=100)
    
    # 检查订单
    is_valid, msg, suggested = risk.check_order_size('BTC-USDT', 0.001, 66000)
    print(f"订单检查: {msg}")
    
    # 检查杠杆
    is_valid, msg = risk.check_leverage(3)
    print(f"杠杆检查: {msg}")
    
    # 计算仓位
    size = risk.calculate_position_size(66000, 62700)
    print(f"建议仓位: {size:.8f} BTC")
    
    # 计算止损止盈
    sl = risk.calculate_stop_loss(66000, 'buy', 0.05)
    tp = risk.calculate_take_profit(66000, 'buy', 0.10)
    print(f"止损: ${sl:,.2f}, 止盈: ${tp:,.2f}")
    
    # 查看状态
    risk.print_status()
