#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API修复测试脚本
用于验证DeepSeek API调用是否正常工作
"""

import requests
import json

def test_deepseek_api():
    """测试DeepSeek API连接"""
    print("🧪 开始测试DeepSeek API...")
    
    api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "请生成一个简单的SQL查询：SELECT 1 as test"}],
        "temperature": 0.1,
        "max_tokens": 2000
    }
    
    try:
        print("🌐 发送测试请求...")
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"📡 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ API测试成功!")
            print(f"📝 响应内容: {content}")
            return True
        else:
            print(f"❌ API测试失败: HTTP {response.status_code}")
            print(f"📄 错误详情: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API测试异常: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_deepseek_api()
    if success:
        print("\n🎉 API连接正常，可以继续使用text2sql系统")
    else:
        print("\n⚠️ API连接失败，请检查网络和API密钥") 