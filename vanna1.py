from vanna.remote import VannaDefault

api_key = "35d688e1655847838c9d0e318168d4f0"
vanna_model_name = "chinook"  # 示例模型名，可替换为你的模型

vn = VannaDefault(model=vanna_model_name, api_key=api_key)

sql = vn.generate_sql(question="查询所有专辑的名称和艺术家")
print("生成的 SQL：", sql)