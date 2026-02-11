# 🚀 快速开始 - OKX加密货币交易机器人

## 安装

```bash
cd ~/crypto-trader-python
python3 -m venv .venv
source .venv/bin/activate
pip install requests cryptography
```

## 配置API密钥

```bash
export OKX_API_KEY="your_api_key"
export OKX_API_SECRET="your_api_secret"
export OKX_PASSPHRASE="your_passphrase"
```

或创建`.env`文件：
```
OKX_API_KEY=your_key
OKX_API_SECRET=your_secret
OKX_PASSPHRASE=your_passphrase
```

## 快速使用

### 1. 查看价格
```bash
python3 trader.py price BTC
python3 trader.py price ETH
```

### 2. 现货交易
```bash
# 买入5 USDT BTC
python3 trader.py buy BTC 5

# 卖出0.001 BTC
python3 trader.py sell BTC 0.001
```

### 3. 自动监控
```bash
# 查看状态
python3 auto_trader.py status

# 持续监控（每5分钟）
python3 auto_trader.py loop

# 运行一次检查
python3 auto_trader.py run
```

### 4. 网络诊断
```bash
python3 diagnose.py
```

### 5. 查看交易统计
```bash
python3 -c "from trading_journal import TradingJournal; j = TradingJournal(); j.print_status()"
```

### 6. 风险管理
```bash
python3 -c "from risk_manager import RiskManager; r = RiskManager(100); r.print_status()"
```

## 支持的交易类型

| 类型 | 操作 | 说明 |
|------|------|------|
| 现货做多 | `buy` | 支撑位买入 |
| 现货做空 | `sell` | 阻力位卖出 |
| 杠杆做多 | `buy` + `leverage` | 最高5x |
| 杠杆做空 | `sell` + `leverage` | 最高5x |

## 文件说明

```
├── trader.py          # 主交易程序
├── okx_api.py        # API客户端（增强版v2.2）
├── monitor.py        # 自动监控脚本
├── auto_trader.py    # 自动交易策略
├── risk_manager.py   # 风险管理
├── trading_journal.py # 交易日志
├── diagnose.py       # 网络诊断
└── README.md         # 完整文档
```

## 常见问题

### Q: SSL错误怎么办？
A: 运行 `python3 diagnose.py` 诊断

### Q: 403 Forbidden怎么办？
A: v2.2已修复，添加了浏览器请求头

### Q: 最小订单金额？
A: 现货5 USDT，杠杆10-20 USDT

### Q: 能做空吗？
A: ✅ 能！使用 `side='sell'`

## 故障排除

1. **无法连接**：
   ```bash
   python3 diagnose.py
   ```

2. **SSL错误**：
   - 检查网络
   - 尝试使用代理

3. **API错误**：
   - 检查API密钥
   - 检查账户权限

---

*最后更新: 2026-02-12*
