"""验证Part 10: 前端Web界面"""
import sys
import os

print("="*60)
print("Part 10: 前端Web界面验证")
print("="*60)

# 检查文件
files = ["frontend/index.html", "frontend/static/style.css", "frontend/static/script.js"]
for f in files:
    if os.path.exists(f):
        print(f"✅ {f}")
        # 检查文件大小
        size = os.path.getsize(f)
        print(f"   文件大小: {size} bytes")
    else:
        print(f"❌ {f}")

# 检查HTML内容
try:
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        content = f.read()
        if "EZInvest" in content:
            print("✅ 前端HTML文件内容正确")
        else:
            print("⚠️  前端HTML文件可能不完整")
except Exception as e:
    print(f"❌ 读取前端文件失败: {e}")

print("\nPart 10验证完成")

