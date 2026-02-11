#!/usr/bin/env python3
"""
回测框架
功能：
1. 基于历史数据测试策略
2. 计算收益率、最大回撤
3. 生成交易报告

使用方法:
    python3 backtest.py --data data.csv --strategy support_buy
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# 模拟交易数据格式
MOCK_DATA = """date,open,high,low,close,volume
2026-02-01,68000,68500,67500,68200,1000000000
2026-02-02,68200,69000,67800,68500,1100000000
2026-02-03,68500,68800,67200,67500,1200000000
2026-02-04,67500,68000,66500,66800,1300000000
2026-02-05,66800,67200,66000,66200,1400000000
2026-02-06,66200,67000,65500,65800,1500000000
2026-02-07,65800,66500,65000,65200,1600000000
2026-02-08,65200,66000,64500,64800,1700000000
2026-02-09,64800,65500,64000,64300,1800000000
2026-02-10,64300,65000,63500,63800,1900000000
2026-02-11,63800,64500,63000,63300,2000000000
2026-02-12,63300,64000,62500,62800,2100000000
"""


class Backtester:
    """
    回测引擎
    
    支持的策略:
    - support_buy: 支撑位买入
    - ma_crossover: MA金叉死叉
    - trend_following: 趋势跟踪
    """
    
    def __init__(self, initial_capital=1000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = []  # 持仓列表
        self.trades = []     # 交易记录
        self.data = []       # 价格数据
    
    def load_data(self, data_file):
        """加载历史数据"""
        if not Path(data_file).exists():
            print(f"⚠️ 数据文件不存在，创建模拟数据...")
            with open('mock_data.csv', 'w') as f:
                f.write(MOCK_DATA)
            data_file = 'mock_data.csv'
        
        self.data = []
        with open(data_file, 'r') as f:
            lines = f.readlines()
            for line in lines[1:]:  # 跳过表头
                parts = line.strip().split(',')
                if len(parts) >= 5:
                    self.data.append({
                        'date': parts[0],
                        'open': float(parts[1]),
                        'high': float(parts[2]),
                        'low': float(parts[3]),
                        'close': float(parts[4]),
                    })
        
        print(f"✅ 加载数据: {len(self.data)}条")
    
    def run_strategy(self, strategy_name='support_buy'):
        """运行回测策略"""
        if not self.data:
            print("❌ 请先加载数据")
            return
        
        print(f"\n🚀 开始回测: {strategy_name}")
        print("=" * 60)
        
        # 清空状态
        self.capital = self.initial_capital
        self.positions = []
        self.trades = []
        
        # 获取策略函数
        strategy = getattr(self, f'strategy_{strategy_name}', self.strategy_support_buy)
        
        # 遍历数据
        for i, bar in enumerate(self.data):
            # 执行策略
            signals = strategy(bar, i)
            
            # 处理信号
            for signal in signals:
                if signal['type'] == 'buy':
                    self._buy(bar['close'], bar['date'])
                elif signal['type'] == 'sell':
                    self._sell(bar['close'], bar['date'])
        
        # 平仓所有持仓
        if self.positions:
            last_close = self.data[-1]['close']
            self._sell(last_close, self.data[-1]['date'])
        
        # 计算结果
        self._calculate_stats()
    
    def strategy_support_buy(self, bar, index):
        """支撑位买入策略"""
        signals = []
        
        # 支撑位
        supports = [66000, 65000, 64000]
        
        # 检查是否接近支撑位
        for support in supports:
            if support * 0.99 <= bar['close'] <= support * 1.02:
                # 检查是否已有持仓
                if not self.positions:
                    signals.append({'type': 'buy', 'price': bar['close']})
                break
        
        # 阻力位卖出
        resistances = [67000, 68000, 70000]
        for resistance in resistances:
            if resistance * 0.98 <= bar['close'] <= resistance:
                if self.positions:
                    signals.append({'type': 'sell', 'price': bar['close']})
                break
        
        return signals
    
    def strategy_ma_crossover(self, bar, index):
        """MA金叉死叉策略"""
        signals = []
        
        if index < 5:
            return signals
        
        # 计算MA5和MA20
        closes = [d['close'] for d in self.data[max(0, index-19):index+1]]
        
        if len(closes) < 5:
            return signals
        
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else ma5
        
        # 金叉买入
        if ma5 > ma20 and not self.positions:
            signals.append({'type': 'buy', 'price': bar['close']})
        # 死叉卖出
        elif ma5 < ma20 and self.positions:
            signals.append({'type': 'sell', 'price': bar['close']})
        
        return signals
    
    def strategy_trend_following(self, bar, index):
        """趋势跟踪策略"""
        signals = []
        
        if index < 10:
            return signals
        
        # 计算简单趋势
        closes = [d['close'] for d in self.data[index-9:index+1]]
        
        if len(closes) < 5:
            return signals
        
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        
        # 上升趋势
        if ma5 > ma10 and not self.positions:
            signals.append({'type': 'buy', 'price': bar['close']})
        # 下降趋势
        elif ma5 < ma10 and self.positions:
            signals.append({'type': 'sell', 'price': bar['close']})
        
        return signals
    
    def _buy(self, price, date):
        """买入"""
        amount = self.capital * 0.5  # 每次用50%资金
        size = amount / price
        
        self.positions.append({
            'size': size,
            'entry_price': price,
            'entry_date': date,
        })
        
        self.capital -= amount
        
        self.trades.append({
            'type': 'buy',
            'price': price,
            'size': size,
            'date': date,
        })
        
        print(f"   🟢 买入: {date} @ ${price:,.2f} ({size:.8f} BTC)")
    
    def _sell(self, price, date):
        """卖出"""
        if not self.positions:
            return
        
        pos = self.positions.pop(0)
        value = pos['size'] * price
        
        self.capital += value
        
        profit = value - (pos['size'] * pos['entry_price'])
        profit_pct = profit / (pos['size'] * pos['entry_price']) * 100
        
        self.trades.append({
            'type': 'sell',
            'price': price,
            'size': pos['size'],
            'date': date,
            'profit': profit,
            'profit_pct': profit_pct,
        })
        
        print(f"   🔴 卖出: {date} @ ${price:,.2f} (盈利{profit:.2f} USDT, {profit_pct:.2f}%)")
    
    def _calculate_stats(self):
        """计算统计数据"""
        if not self.trades:
            print("\n❌ 无交易记录")
            return
        
        # 过滤平仓交易
        closed_trades = [t for t in self.trades if t['type'] == 'sell']
        
        if not closed_trades:
            print("\n⚠️ 无平仓交易")
            return
        
        # 计算收益
        total_profit = sum(t.get('profit', 0) for t in closed_trades)
        final_capital = self.capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100
        
        # 胜率
        wins = len([t for t in closed_trades if t.get('profit', 0) > 0])
        total = len(closed_trades)
        win_rate = wins / total * 100 if total > 0 else 0
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown()
        
        # 盈亏比
        avg_win = sum(t.get('profit', 0) for t in closed_trades if t.get('profit', 0) > 0) / wins if wins > 0 else 0
        avg_loss = abs(sum(t.get('profit', 0) for t in closed_trades if t.get('profit', 0) < 0) / (total - wins)) if total - wins > 0 else 1
        profit_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        # 打印结果
        print("\n" + "=" * 60)
        print("📊 回测结果")
        print("=" * 60)
        print(f"   初始资金: ${self.initial_capital:,.2f}")
        print(f"   最终资金: ${final_capital:,.2f}")
        print(f"   总收益率: {total_return:.2f}%")
        print(f"   交易次数: {total}笔")
        print(f"   盈利次数: {wins}笔 ({win_rate:.1f}%)")
        print(f"   亏损次数: {total - wins}笔 ({100-win_rate:.1f}%)")
        print(f"   总盈亏: ${total_profit:,.2f}")
        print(f"   盈亏比: {profit_ratio:.2f}")
        print(f"   最大回撤: {max_drawdown:.2f}%")
        
        # 保存结果
        result = {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_trades': total,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'profit_ratio': profit_ratio,
            'max_drawdown': max_drawdown,
            'trades': self.trades,
        }
        
        with open('backtest_result.json', 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 结果已保存: backtest_result.json")
    
    def _calculate_max_drawdown(self):
        """计算最大回撤"""
        if not self.trades:
            return 0
        
        # 模拟资金曲线
        capital = self.initial_capital
        peaks = [capital]
        
        for trade in self.trades:
            if trade['type'] == 'buy':
                capital -= self.capital * 0.5
            else:
                capital += trade.get('profit', 0) + (trade['size'] * trade['entry_price'])
            peaks.append(capital)
        
        max_dd = 0
        for i, peak in enumerate(peaks):
            for j in range(i, len(peaks)):
                dd = (peak - peaks[j]) / peak * 100
                if dd > max_dd:
                    max_dd = dd
        
        return max_dd
    
    def print_data_preview(self):
        """预览数据"""
        if not self.data:
            print("❌ 无数据")
            return
        
        print(f"\n📈 数据预览 (前5条)")
        print("=" * 60)
        for bar in self.data[:5]:
            print(f"   {bar['date']}: ${bar['close']:,.2f}")
        print(f"   ... 共{len(self.data)}条")


def main():
    parser = argparse.ArgumentParser(description='回测交易策略')
    parser.add_argument('--data', '-d', default='mock_data.csv', help='数据文件')
    parser.add_argument('--strategy', '-s', default='support_buy', 
                       choices=['support_buy', 'ma_crossover', 'trend_following'],
                       help='策略名称')
    parser.add_argument('--capital', '-c', type=float, default=1000, help='初始资金')
    
    args = parser.parse_args()
    
    # 创建回测器
    bt = Backtester(initial_capital=args.capital)
    
    # 预览数据
    bt.print_data_preview()
    
    # 运行回测
    bt.run_strategy(args.strategy)


if __name__ == '__main__':
    main()
