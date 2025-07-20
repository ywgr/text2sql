import vanna as vn

# 向注册邮箱发送验证码（你的邮箱是 ywgr@163.com）
api_key = vn.get_api_key(email="ywgr@163.com")

# 运行后，查看你的 163 邮箱，会收到一封来自 Vanna 的邮件，包含验证码
# 输入验证码后，函数会返回 API Key，并自动保存（后续可直接使用）
print("获取到的 API Key：", api_key)  # 建议保存到环境变量或安全地方