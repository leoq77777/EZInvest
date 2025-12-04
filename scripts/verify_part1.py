"""验证Part 1: 项目基础结构"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("="*60)
print("Part 1: 项目基础结构验证")
print("="*60)

# 检查文件
files = ["requirements.txt", "README.md", ".gitignore", "app/__init__.py", "app/config.py", "app/main.py"]
for f in files:
    print(f"✅ {f}" if os.path.exists(f) else f"❌ {f}")

# 检查配置
try:
    from app.config import settings
    print("✅ 配置模块导入成功")
except Exception as e:
    print(f"❌ 配置模块: {e}")

print("\nPart 1验证完成")

