# OKX加密货币交易机器人 - Python版

基于Lucky Trading Scripts设计理念的OKX交易系统。

## 📁 文件结构

```
crypto-trader-python/
├── trader.py           # 主交易程序
├── okx_api.py         # API客户端 (v2.0 - 增强版)
├── monitor.py         # 自动监控脚本
├── risk_manager.py    # 风险管理模块
├── trading_journal.py # 交易日志模块
├── alerts.json        # 价格警报配置
├── .env.example       # API配置模板
├── .gitignore         # Git忽略配置
└── README.md          # 本文档
```

## 🚀 快速开始

### 1. 安装依赖
```bash
cd ~/crypto-trader-python
python3 -m venv .venv
source .venv/bin/activate
pip install requests cryptography
```

### 2. 配置API密钥
```bash
# 方法1: 环境变量
export OKX_API_KEY="your_api_key"
export OKX_API_SECRET="your_api_secret"
export OKX_PASSPHRASE="your_passphrase"

# 方法2: .env文件
cp .env.example .env
# 编辑.env填入密钥
```

### 3. 运行
```bash
# 激活环境
source .venv/bin/activate

# 查看账户状态
python3 trader.py status

# 查看价格
python3 trader.py price BTC
python3 trader.py price ETH

# 买入
python3 trader.py buy BTC 5      # 买入5 USDT的BTC
python3 trader.py sell BTC 0.001 # 卖出0.001 BTC

# 警报
python3 trader.py alert BTC 70000 above  # 高于70000报警
python3 trader.py alert BTC 65000 below  # 低于65000报警
python3 trader.py alerts               # 查看所有警报

# 止损止盈
python3 trader.py tpsl BTC     # 计算BTC的止损止盈

# 持续监控
python3 monitor.py loop

# 测试连接
python3 monitor.py test
```

## 📊 功能列表

| 模块 | 功能 | 说明 |
|------|------|------|
| trader.py | 账户查询 | 余额、持仓 |
| trader.py | 实时价格 | 支撑/阻力位 |
| trader.py | 买卖下单 | 现货交易 |
| trader.py | 价格警报 | 持久化存储 |
| trader.py | 止损止盈 | 自动计算 |
| okx_api.py | 签名缓存 | 60秒内复用 |
| okx_api.py | 备用端点 | 3个自动切换 |
| okx_api.py | 错误处理 | 详细错误码 |
| monitor.py | 自动监控 | 每60秒检查 |
| monitor.py | 日志记录 | trading.log |
| risk_manager.py | 仓位管理 | 单笔≤20% |
| risk_manager.py | 自动止损 | 5%止损 |
| risk_manager.py | 杠杆限制 | ≤5倍 |
| trading_journal.py | 交易记录 | 自动保存 |
| trading_journal.py | P&L统计 | 胜率/盈亏比 |
| trading_journal.py | 导出CSV | 数据分析 |

## 🛡️ 风险管理

### 配置参数
```python
MAX_POSITION_RATIO = 0.2    # 单笔不超过20%
MAX_LEVERAGE = 5            # 最大5倍
STOP_LOSS_DEFAULT = 0.05    # 默认5%止损
TAKE_PROFIT_DEFAULT = 0.10  # 默认10%止盈
RISK_PER_TRADE = 0.02       # 每笔风险2%
```

### 使用示例
```python
from risk_manager import RiskManager

risk = RiskManager(total_balance=100)
risk.print_status()

# 检查订单
valid, msg = risk.check_order_size('BTC-USDT', 0.001, 66000)

# 计算仓位
size = risk.calculate_position_size(66000, 62700)

# 计算止损止盈
sl = risk.calculate_stop_loss(66000, 'buy', 0.05)
tp = risk.calculate_take_profit(66000, 'buy', 0.10)
```

## 📈 交易日志

### 使用示例
```python
from trading_journal import TradingJournal

journal = TradingJournal()

# 添加交易
journal.add_trade({
    'symbol': 'BTC-USDT',
    'side': 'buy',
    'size': 0.001,
    'price': 66000,
    'fee': 0.1,
    'status': 'open',
})

# 平仓
journal.close_trade('BTC-USDT', 66500)

# 查看统计
journal.print_status()

# 导出
journal.export_csv('trades.csv')
```

## 🔔 价格警报

警报会自动保存到 `alerts.json`，支持：
- 高于某价格报警
- 低于某价格报警
- 持久化存储

## 🛡️ 止损止盈

自动计算：
- 止损价 = 当前价 × (1 - 5%)
- 止盈价 = 当前价 × (1 + 10%)

## 📖 参考项目

- [Lucky Trading Scripts](https://github.com/xqliu/lucky-trading-scripts)
- [OKX API文档](https://www.okx.com/docs-v5/zh/)

## ⚠️ 风险提示

1. 加密货币交易有风险
2. 请先用小资金测试
3. 设置合理的止损
4. 不要追涨杀跌
5. 遵守风险管理规则

## 📝 License

MIT

---

## 🤖 自动交易策略 (auto_trader.py)

### 功能
- 📅 **DCA定期定额投资**：每周自动买入
- 🛡️ **支撑位买入**：价格接近支撑位时买入
- 📈 **阻力位卖出**：价格接近阻力位时卖出
- 🔄 **网格交易**：价格在区间内自动低买高卖

### 使用方法
```bash
# 查看状态
python3 auto_trader.py status

# 运行一次检查
python3 auto_trader.py run

# 持续监控（每5分钟）
python3 auto_trader.py loop

# 执行DCA
python3 auto_trader.py dca

# 执行支撑位买入
python3 auto_trader.py support

# 执行阻力位卖出
python3 auto_trader.py resistance
```

### 配置
```python
STRATEGY_CONFIG = {
    'dca': {
        'enabled': True,
        'amount': 5,          # 每次5 USDT
        'interval_days': 7,   # 每周一次
    },
    'support_buy': {
        'enabled': True,
        'amount': 10,
        'supports': [66000, 65000, 64000],
    },
    'resistance_sell': {
        'enabled': True,
        'min_profit': 0.05,
    },
}
```

---

## 🔧 工具脚本

### diagnose.py - 网络诊断
```bash
python3 diagnose.py
```

### 功能
- DNS解析测试
- HTTPS连接测试
- API端点测试
- 冷却时间测试

---

## 📊 版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v2.2 | 2026-02-12 | 添加浏览器请求头，解决403问题 |
| v2.1 | 2026-02-12 | 禁用SSL验证，延长超时 |
| v2.0 | 2026-02-12 | 签名缓存，备用端点 |
| v1.0 | 2026-02-12 | 初始版本 |

---

## 💡 常见问题

### Q: SSL错误怎么办？
A: 运行 `python3 diagnose.py` 进行网络诊断

### Q: 403 Forbidden怎么办？
A: v2.2已修复，添加了浏览器请求头

### Q: 如何做空？
A: 使用 `side='sell'` 参数

### Q: 最小订单金额是多少？
A: 现货约5 USDT，杠杆约10-20 USDT

