#!/bin/bash
# 自动监控脚本 - 每5分钟检查BTC价格
# 使用方法: ./auto_monitor.sh start

cd ~/crypto-trader-python

# 检查是否已有运行中的监控
if pgrep -f "monitor.py loop" > /dev/null; then
    echo "⚠️  监控已在运行中"
    exit 1
fi

echo "🚀 启动自动监控..."
echo "   每5分钟检查BTC价格"
echo "   支撑位: \$66,000, \$65,000, \$64,000"
echo "   日志: trading.log"
echo ""

# 激活环境并运行监控
source .venv/bin/activate
nohup python3 monitor.py loop BTC-USDT 300 > monitor.log 2>&1 &

echo "✅ 监控已启动 (PID: $!)"
echo "   查看日志: tail -f monitor.log"
echo "   停止: kill \$(pgrep -f 'monitor.py loop')"
