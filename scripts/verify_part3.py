"""验证Part 3: akshare API集成"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("="*60)
print("Part 3: akshare API集成验证")
print("="*60)

# 检查文件
files = ["app/services/data_fetcher.py", "app/services/prefetch_scheduler.py"]
for f in files:
    print(f"✅ {f}" if os.path.exists(f) else f"❌ {f}")

# 检查akshare
try:
    import akshare as ak
    print("✅ akshare库导入成功")
except Exception as e:
    print(f"❌ akshare库: {e}")

# 检查数据获取器
try:
    from app.services.data_fetcher import AkshareDataFetcher, RateLimiter, data_fetcher
    print("✅ 数据获取器导入成功")
except Exception as e:
    print(f"❌ 数据获取器: {e}")

# 检查预取调度器
try:
    from app.services.prefetch_scheduler import PrefetchScheduler, prefetch_scheduler
    print("✅ 预取调度器导入成功")
except Exception as e:
    print(f"❌ 预取调度器: {e}")

print("\nPart 3验证完成")

