"""验证Part 11: 测试"""
import sys
import os

print("="*60)
print("Part 11: 测试验证")
print("="*60)

# 检查文件
files = [
    "pytest.ini",
    "tests/__init__.py",
    "tests/test_storage.py",
    "tests/test_quant_tool.py",
    "tests/test_rag_tool.py",
    "tests/test_api.py",
    "tests/test_e2e.py",
    "tests/test_integration.py"
]

for f in files:
    print(f"✅ {f}" if os.path.exists(f) else f"⚠️  {f}")

# 检查pytest
try:
    import pytest
    print(f"✅ pytest库已安装 (版本: {pytest.__version__})")
except ImportError:
    print("❌ pytest库未安装")

print("\nPart 11验证完成")

