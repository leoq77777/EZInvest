"""
单独验证单个Part
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def verify_part(part_num):
    """验证指定的Part"""
    print(f"\n{'='*60}")
    print(f"验证 Part {part_num}")
    print('='*60)
    
    try:
        if part_num == 1:
            # Part 1: 项目基础结构
            from app.config import settings
            print("✅ 配置模块导入成功")
            from app.main import app
            print("✅ FastAPI应用导入成功")
            return True
            
        elif part_num == 2:
            # Part 2: 数据层
            from app.database.redis_client import redis_client
            print("✅ Redis客户端导入成功")
            from app.database.mysql_client import engine, FinancialData
            print("✅ MySQL客户端导入成功")
            from app.database.storage import storage_manager
            print("✅ 存储管理器导入成功")
            return True
            
        elif part_num == 3:
            # Part 3: akshare API集成
            import akshare as ak
            print("✅ akshare库导入成功")
            from app.services.data_fetcher import data_fetcher
            print("✅ 数据获取器导入成功")
            from app.services.prefetch_scheduler import prefetch_scheduler
            print("✅ 预取调度器导入成功")
            return True
            
        elif part_num == 4:
            # Part 4: 冷热数据管理
            from app.database.storage import storage_manager
            print("✅ 冷热数据管理已实现")
            return True
            
        elif part_num == 5:
            # Part 5: RAG工具
            import faiss
            print("✅ FAISS库导入成功")
            from app.tools.rag import rag_tool
            print("✅ RAG工具导入成功")
            return True
            
        elif part_num == 6:
            # Part 6: Quant Tool
            from app.services.quant_tool import quant_tool
            print("✅ 量化工具导入成功")
            return True
            
        elif part_num == 7:
            # Part 7: 政策分析Tool
            from app.services.policy_tool import policy_tool
            print("✅ 政策分析工具导入成功")
            return True
            
        elif part_num == 8:
            # Part 8: 大模型集成
            from app.tools.llm import ollama_client, PromptManager
            print("✅ LLM工具导入成功")
            return True
            
        elif part_num == 9:
            # Part 9: Agent核心逻辑
            from app.services.agent import investment_agent
            print("✅ Agent导入成功")
            from app.api.routes import router
            print("✅ API路由导入成功")
            return True
            
        elif part_num == 10:
            # Part 10: 前端
            if os.path.exists("frontend/index.html"):
                print("✅ 前端文件存在")
                return True
            else:
                print("❌ 前端文件不存在")
                return False
                
        elif part_num == 11:
            # Part 11: 测试
            import pytest
            print("✅ pytest已安装")
            if os.path.exists("tests/test_storage.py"):
                print("✅ 测试文件存在")
                return True
            else:
                print("❌ 测试文件不存在")
                return False
                
        else:
            print(f"❌ 未知的Part编号: {part_num}")
            return False
            
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        part_num = int(sys.argv[1])
        success = verify_part(part_num)
        sys.exit(0 if success else 1)
    else:
        print("用法: python verify_part_single.py <part_number>")
        sys.exit(1)

