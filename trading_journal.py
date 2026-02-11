#!/usr/bin/env python3
"""
交易日志模块
功能：
1. 记录所有交易
2. 计算P&L
3. 统计分析
4. 导出报告
"""

import os
import json
import datetime
from pathlib import Path
from typing import List, Dict, Optional

# 配置
JOURNAL_DIR = 'trades'
JOURNAL_FILE = f'{JOURNAL_DIR}/trades.json'


class TradingJournal:
    """交易日志"""
    
    def __init__(self, journal_dir=JOURNAL_DIR):
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(exist_ok=True)
        self.journal_file = self.journal_dir / 'trades.json'
        
        # 初始化文件
        if not self.journal_file.exists():
            self._save([])
    
    def _load(self) -> List[Dict]:
        """加载交易记录"""
        try:
            with open(self.journal_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def _save(self, trades: List[Dict]):
        """保存交易记录"""
        with open(self.journal_file, 'w') as f:
            json.dump(trades, f, indent=2, ensure_ascii=False)
    
    def add_trade(self, trade: Dict):
        """
        添加交易记录
        
        trade = {
            'symbol': 'BTC-USDT',
            'side': 'buy',
            'size': 0.001,
            'price': 66000,
            'fee': 0.1,
            'pnl': None,  # 平仓时填写
            'status': 'open',  # open/closed
            'time': '2026-02-12T01:00:00.000Z',
            'note': '',
        }
        """
        trades = self._load()
        trades.append(trade)
        self._save(trades)
        print(f"✅ 交易已记录: {trade['symbol']} {trade['side']} {trade['size']}")
    
    def close_trade(self, symbol, close_price, status='closed'):
        """
        平仓
        
        Args:
            symbol: 交易对
            close_price: 平仓价格
            status: closed/cancelled
        """
        trades = self._load()
        
        for trade in reversed(trades):
            if trade['symbol'] == symbol and trade['status'] == 'open':
                trade['close_price'] = close_price
                trade['close_time'] = datetime.datetime.now().isoformat()
                trade['status'] = status
                
                # 计算P&L
                if trade['side'] == 'buy':
                    pnl = (close_price - trade['price']) * trade['size'] - trade.get('fee', 0)
                else:
                    pnl = (trade['price'] - close_price) * trade['size'] - trade.get('fee', 0)
                
                trade['pnl'] = round(pnl, 2)
                self._save(trades)
                print(f"✅ 已平仓: {symbol}, P&L: {pnl:.2f} USDT")
                return trade
        
        print(f"❌ 未找到未平仓交易: {symbol}")
        return None
    
    def get_open_positions(self) -> List[Dict]:
        """获取未平仓持仓"""
        return [t for t in self._load() if t['status'] == 'open']
    
    def get_closed_trades(self) -> List[Dict]:
        """获取已平仓交易"""
        return [t for t in self._load() if t['status'] == 'closed']
    
    def get_statistics(self) -> Dict:
        """获取统计数据"""
        trades = self._load()
        closed = self.get_closed_trades()
        
        total_trades = len(trades)
        closed_count = len(closed)
        open_count = len(self.get_open_positions())
        
        # 盈亏统计
        total_pnl = sum(t.get('pnl', 0) for t in closed)
        win_trades = [t for t in closed if t.get('pnl', 0) > 0]
        loss_trades = [t for t in closed if t.get('pnl', 0) < 0]
        
        win_rate = len(win_trades) / closed_count * 100 if closed_count > 0 else 0
        
        # 盈亏比
        avg_win = sum(t.get('pnl', 0) for t in win_trades) / len(win_trades) if win_trades else 0
        avg_loss = abs(sum(t.get('pnl', 0) for t in loss_trades) / len(loss_trades)) if loss_trades else 0
        profit_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        return {
            'total_trades': total_trades,
            'open_positions': open_count,
            'closed_trades': closed_count,
            'total_pnl': round(total_pnl, 2),
            'win_rate': round(win_rate, 2),
            'profit_ratio': round(profit_ratio, 2),
            'wins': len(win_trades),
            'losses': len(loss_trades),
        }
    
    def print_status(self):
        """打印状态"""
        print("\n📊 交易日志状态")
        print("=" * 50)
        
        stats = self.get_statistics()
        
        print(f"📈 总交易: {stats['total_trades']}笔")
        print(f"   - 已平仓: {stats['closed_trades']}笔")
        print(f"   - 未平仓: {stats['open_positions']}笔")
        
        print(f"\n💰 盈亏统计:")
        print(f"   - 总P&L: {stats['total_pnl']:.2f} USDT")
        print(f"   - 胜率: {stats['win_rate']:.1f}%")
        print(f"   - 盈亏比: {stats['profit_ratio']:.2f}")
        print(f"   - 盈利: {stats['wins']}笔")
        print(f"   - 亏损: {stats['losses']}笔")
        
        # 未平仓持仓
        open_pos = self.get_open_positions()
        if open_pos:
            print(f"\n📋 未平仓持仓:")
            for pos in open_pos:
                print(f"   {pos['symbol']}: {pos['size']:.8f} @ {pos['price']:,.2f} ({pos['side']})")
    
    def export_csv(self, filename='trades.csv'):
        """导出为CSV"""
        trades = self._load()
        
        if not trades:
            print("❌ 无交易记录可导出")
            return
        
        import csv
        
        with open(filename, 'w', newline='') as f:
            fieldnames = ['symbol', 'side', 'size', 'price', 'fee', 'pnl', 'status', 'time']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for trade in trades:
                writer.writerow({
                    'symbol': trade['symbol'],
                    'side': trade['side'],
                    'size': trade['size'],
                    'price': trade['price'],
                    'fee': trade.get('fee', 0),
                    'pnl': trade.get('pnl', ''),
                    'status': trade['status'],
                    'time': trade['time'],
                })
        
        print(f"✅ 已导出: {filename}")


# ============ 使用示例 ============
if __name__ == '__main__':
    journal = TradingJournal()
    
    # 查看状态
    journal.print_status()
    
    # 示例：添加交易
    # journal.add_trade({
    #     'symbol': 'BTC-USDT',
    #     'side': 'buy',
    #     'size': 0.001,
    #     'price': 66000,
    #     'fee': 0.1,
    #     'status': 'open',
    #     'time': datetime.datetime.now().isoformat(),
    # })
    
    # 示例：平仓
    # journal.close_trade('BTC-USDT', 66500)
    
    # 示例：导出
    # journal.export_csv()
