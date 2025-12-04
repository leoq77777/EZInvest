"""验证Part 2: 数据层"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("="*60)
print("Part 2: 数据层验证")
print("="*60)

# 检查文件
files = ["app/database/__init__.py", "app/database/redis_client.py", 
         "app/database/mysql_client.py", "app/database/storage.py", "scripts/init_db.py"]
for f in files:
    print(f"✅ {f}" if os.path.exists(f) else f"❌ {f}")

# 检查模块
try:
    from app.database.redis_client import RedisClient, redis_client
    print("✅ Redis客户端导入成功")
except Exception as e:
    print(f"❌ Redis客户端: {e}")

try:
    from app.database.mysql_client import engine, SessionLocal, Base, FinancialData, NewsData
    print("✅ MySQL客户端导入成功")
except Exception as e:
    print(f"❌ MySQL客户端: {e}")

try:
    from app.database.storage import StorageManager, storage_manager
    print("✅ 存储管理器导入成功")
except Exception as e:
    print(f"❌ 存储管理器: {e}")

print("\nPart 2验证完成")

