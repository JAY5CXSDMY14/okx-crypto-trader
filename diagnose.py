#!/usr/bin/env python3
"""
网络诊断脚本
帮助诊断OKX API连接问题
"""

import os
import sys
import json
import time
import socket
import ssl
import urllib.request
import urllib.error

# 测试配置
TEST_URLS = [
    'https://www.okx.com',
    'https://okx.com',
    'https://api.okx.com',
]

def test_connection():
    """测试网络连接"""
    print("🌐 网络连接测试")
    print("=" * 60)
    
    # 测试DNS解析
    print("\n1. DNS解析测试:")
    try:
        ip = socket.gethostbyname('www.okx.com')
        print(f"   ✅ OKX IP: {ip}")
    except Exception as e:
        print(f"   ❌ DNS失败: {e}")
    
    # 测试HTTPS连接
    print("\n2. HTTPS连接测试:")
    for url in TEST_URLS:
        try:
            start = time.time()
            context = ssl.create_default_context()
            # 禁用证书验证（临时解决方案）
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=30, context=context) as resp:
                elapsed = time.time() - start
                print(f"   ✅ {url}: {resp.status} ({elapsed:.2f}秒)")
        except Exception as e:
            print(f"   ❌ {url}: {e}")
    
    # 测试API端点
    print("\n3. API端点测试:")
    api_endpoints = [
        'https://www.okx.com/api/v5/public/time',
        'https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT',
    ]
    
    for url in api_endpoints:
        try:
            start = time.time()
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=30, context=context) as resp:
                elapsed = time.time() - start
                data = resp.read().decode()
                print(f"   ✅ {url.split('/')[-1]}: {resp.status} ({elapsed:.2f}秒)")
        except Exception as e:
            print(f"   ❌ {url.split('/')[-1]}: {e}")


def test_api_connection():
    """测试API连接（带签名）"""
    print("\n🔐 API连接测试")
    print("=" * 60)
    
    API_KEY = os.environ.get('OKX_API_KEY', '')
    API_SECRET = os.environ.get('OKX_API_SECRET', '')
    PASSPHRASE = os.environ.get('OKX_PASSPHRASE', '')
    
    if not API_KEY:
        print("   ⚠️  未配置API密钥")
        print("   请设置环境变量:")
        print("   export OKX_API_KEY='your_key'")
        print("   export OKX_API_SECRET='your_secret'")
        print("   export OKX_PASSPHRASE='your_passphrase'")
        return
    
    print(f"   API Key: {API_KEY[:8]}...")
    
    import hmac
    import hashlib
    import base64
    import datetime
    
    # 测试获取时间
    def sign(timestamp, method, path, body=''):
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            API_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode()
    
    # 获取服务器时间（公开API）
    print("\n   测试公开API:")
    try:
        import requests
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        resp = requests.get(
            'https://www.okx.com/api/v5/public/time',
            timeout=30,
            verify=False
        )
        data = resp.json()
        if data.get('code') == '0':
            print(f"   ✅ 服务器时间: {data['data'][0]['ts']}")
        else:
            print(f"   ❌ 失败: {data}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")


def test_with_cooldown():
    """测试带冷却时间的请求"""
    print("\n⏱️ 冷却时间测试")
    print("=" * 60)
    print("   测试不同冷却时间的效果...")
    
    import requests
    
    API_KEY = os.environ.get('OKX_API_KEY', '')
    if not API_KEY:
        print("   ⚠️  未配置API密钥")
        return
    
    test_intervals = [0, 3, 10, 30]  # 秒
    
    for interval in test_intervals:
        if interval > 0:
            print(f"\n   等待{interval}秒...")
            time.sleep(interval)
        
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # 生成签名
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            path = '/api/v5/market/ticker?instId=BTC-USDT'
            
            # 简单GET请求不需要签名
            resp = requests.get(
                f'https://www.okx.com{path}',
                timeout=30,
                verify=False
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == '0':
                    price = float(data['data'][0]['last'])
                    print(f"   ✅ {interval}秒冷却: ${price:,.2f}")
                else:
                    print(f"   ❌ {interval}秒冷却: API错误")
            else:
                print(f"   ❌ {interval}秒冷却: HTTP {resp.status_code}")
                
        except Exception as e:
            print(f"   ❌ {interval}秒冷却: {e}")


def main():
    """主函数"""
    print("🔧 OKX API 网络诊断工具")
    print("=" * 60)
    print(f"   时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1: 基本连接
    test_connection()
    
    # 测试2: API连接
    test_api_connection()
    
    # 测试3: 冷却时间
    test_with_cooldown()
    
    # 建议
    print("\n💡 建议:")
    print("   1. 如果DNS失败: 检查网络/切换DNS")
    print("   2. 如果HTTPS失败: 使用代理或VPN")
    print("   3. 如果API失败: 等待更长时间再试")
    print("   4. 考虑使用备用交易所")


if __name__ == '__main__':
    main()
