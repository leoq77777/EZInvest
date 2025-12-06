"""
初始化数据库脚本
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.mysql_client import init_db
from app.database.redis_client import redis_client

def main():
    """初始化数据库"""
    print("Initializing database...")
    
    # 初始化MySQL表
    try:
        init_db()
        print("✓ MySQL tables created successfully")
    except Exception as e:
        print(f"✗ Failed to create MySQL tables: {e}")
        return
    
    # 测试Redis连接
    try:
        try:
            redis_client.client.ping()
            print("✓ Redis connection successful")
        except Exception as e:
            print(f"⚠️  Redis not available: {e}. Continuing without Redis.")
    
    print("\nDatabase initialization completed!")

if __name__ == "__main__":
    main()

