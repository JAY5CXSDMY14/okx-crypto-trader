# 使用指南

## 测试Python交易系统

### 方法1: 手动设置环境变量
```bash
cd ~/crypto-trader-python
source .venv/bin/activate

export OKX_API_KEY="6224f399-d4c3-4599-81e0-8b8249481393"
export OKX_API_SECRET="A49B66461E5482637DFADF50DD28A134"
export OKX_PASSPHRASE="HAZYC2004chen!"

# 测试
python3 trader.py status
python3 trader.py price BTC
python3 trader.py alerts
```

### 方法2: 写入.env文件
```bash
cd ~/crypto-trader-python

# 编辑.env
nano .env
```

填入：
```
OKX_API_KEY=6224f399-d4c3-4599-81e0-8b8249481393
OKX_API_SECRET=A49B66461E5482637DFADF50DD28A134
OKX_PASSPHRASE=HAZYC2004chen!
```

然后运行：
```bash
source .env
python3 trader.py status
```

## 常用命令速查

| 命令 | 功能 |
|------|------|
| `python3 trader.py status` | 查看账户 |
| `python3 trader.py price BTC` | BTC价格 |
| `python3 trader.py buy BTC 5` | 买入5 USDT |
| `python3 trader.py sell BTC 0.001` | 卖出 |
| `python3 trader.py alert BTC 70000` | 高于70000报警 |
| `python3 trader.py alerts` | 查看警报 |
| `python3 trader.py tpsl BTC` | 止损止盈 |

## 问题排查

### SSL连接错误
- 可能是网络波动，重试几次
- 检查API密钥是否正确

### 权限错误
- 确保API Key有交易权限
- 确保已开通杠杆账户（如需杠杆）
