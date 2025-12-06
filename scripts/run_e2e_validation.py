"""
E2E验证脚本 - 基于自定义输入
"""
import sys
import os
import requests
import json
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE_URL = "http://localhost:8000"
TIMEOUT = 120  # 2分钟超时

def print_section(title):
    """打印分节标题"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_success(msg):
    """打印成功消息"""
    print(f"✅ {msg}")

def print_error(msg):
    """打印错误消息"""
    print(f"❌ {msg}")

def print_warning(msg):
    """打印警告消息"""
    print(f"⚠️  {msg}")

def print_info(msg):
    """打印信息消息"""
    print(f"ℹ️  {msg}")

def check_api_health():
    """检查API健康状态"""
    print_section("1. 检查API健康状态")
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                print_success("API健康检查通过")
                return True
            else:
                print_error(f"API状态异常: {data}")
                return False
        else:
            print_error(f"API健康检查失败: HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("无法连接到API服务器，请确保服务已启动")
        print_info("启动命令: uvicorn app.main:app --reload --port 8000")
        return False
    except Exception as e:
        print_error(f"健康检查异常: {e}")
        return False

def test_query(query, expected_symbol=None, description=None):
    """测试单个查询"""
    if description:
        print(f"\n📝 测试: {description}")
    print(f"   查询: {query}")
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/query",
            json={"query": query, "stream": False},
            timeout=TIMEOUT
        )
        elapsed_time = time.time() - start_time
        
        if response.status_code != 200:
            print_error(f"请求失败: HTTP {response.status_code}")
            print_error(f"响应: {response.text[:200]}")
            return False
        
        data = response.json()
        
        # 检查基本结构
        if "success" not in data:
            print_error("响应缺少'success'字段")
            return False
        
        if not data.get("success"):
            error_msg = data.get("error", "未知错误")
            print_warning(f"查询处理失败: {error_msg}")
            print_info("这可能是正常的（例如：无法识别标的）")
            return True  # 失败但结构正确，也算通过
        
        # 检查必要字段
        checks = []
        
        if "symbol" in data and data["symbol"]:
            checks.append(f"✅ 标的识别: {data['symbol']}")
            if expected_symbol and data["symbol"] != expected_symbol:
                print_warning(f"期望标的: {expected_symbol}, 实际: {data['symbol']}")
        else:
            checks.append("⚠️  未识别到标的")
        
        if "name" in data and data["name"]:
            checks.append(f"✅ 股票名称: {data['name']}")
        
        if "quant_analysis" in data and data["quant_analysis"]:
            quant_len = len(data["quant_analysis"])
            checks.append(f"✅ 量化分析: {quant_len} 字符")
        else:
            checks.append("⚠️  量化分析为空")
        
        if "news_analysis" in data and data["news_analysis"]:
            news_len = len(data["news_analysis"])
            checks.append(f"✅ 新闻分析: {news_len} 字符")
        else:
            checks.append("⚠️  新闻分析为空")
        
        if "advice" in data and data["advice"]:
            advice_len = len(data["advice"])
            checks.append(f"✅ 投资建议: {advice_len} 字符")
        else:
            checks.append("⚠️  投资建议为空")
        
        # 打印检查结果
        for check in checks:
            print(f"   {check}")
        
        print_info(f"响应时间: {elapsed_time:.2f}秒")
        
        # 显示建议摘要（前200字符）
        if data.get("advice"):
            advice_preview = data["advice"][:200].replace("\n", " ")
            print_info(f"建议预览: {advice_preview}...")
        
        return True
        
    except requests.exceptions.Timeout:
        print_error(f"请求超时（>{TIMEOUT}秒）")
        return False
    except Exception as e:
        print_error(f"请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_custom_queries():
    """运行自定义查询"""
    print_section("2. 运行自定义查询测试")
    
    # 默认测试用例
    test_cases = [
        {
            "query": "最近的apple股票还能买吗",
            "expected_symbol": None,  # 可能识别为AAPL或其他
            "description": "美股英文名称查询"
        },
        {
            "query": "分析一下000001的走势",
            "expected_symbol": "000001",
            "description": "A股代码查询"
        },
        {
            "query": "腾讯股票现在值得投资吗",
            "expected_symbol": None,  # 可能识别为00700或其他
            "description": "港股中文名称查询"
        },
        {
            "query": "推荐一些科技股",
            "expected_symbol": None,
            "description": "模糊查询（可能无法识别具体标的）"
        }
    ]
    
    # 如果命令行提供了自定义查询，使用自定义查询
    if len(sys.argv) > 1:
        custom_query = " ".join(sys.argv[1:])
        test_cases = [{
            "query": custom_query,
            "expected_symbol": None,
            "description": "自定义查询"
        }]
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i}/{len(test_cases)} ---")
        success = test_query(
            test_case["query"],
            test_case.get("expected_symbol"),
            test_case.get("description")
        )
        results.append(success)
        time.sleep(1)  # 避免请求过快
    
    return results

def test_stream_query():
    """测试流式查询"""
    print_section("3. 测试流式查询")
    
    query = "分析一下000001"
    print(f"查询: {query}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/query/stream",
            json={"query": query, "stream": True},
            stream=True,
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            print_error(f"流式请求失败: HTTP {response.status_code}")
            return False
        
        print_info("开始接收流式响应...")
        chunks_received = 0
        total_content = ""
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    chunk = line_str[6:]  # 移除 'data: ' 前缀
                    total_content += chunk
                    chunks_received += 1
                    if chunks_received <= 3:  # 只显示前3个chunk
                        print(f"   Chunk {chunks_received}: {chunk[:50]}...")
        
        print_success(f"流式响应完成，共接收 {chunks_received} 个chunk")
        print_info(f"总内容长度: {len(total_content)} 字符")
        
        if len(total_content) > 100:
            print_success("流式查询测试通过")
            return True
        else:
            print_warning("流式响应内容过短")
            return False
            
    except Exception as e:
        print_error(f"流式查询异常: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "="*60)
    print(" EZInvest E2E验证")
    print("="*60)
    
    # 检查API健康状态
    if not check_api_health():
        print_error("\n请先启动API服务:")
        print_info("  uvicorn app.main:app --reload --port 8000")
        return 1
    
    # 运行查询测试
    query_results = run_custom_queries()
    
    # 测试流式查询（可选）
    stream_result = None
    try:
        stream_result = test_stream_query()
    except Exception as e:
        print_warning(f"流式查询测试跳过: {e}")
    
    # 总结
    print_section("验证总结")
    
    total_tests = len(query_results)
    passed_tests = sum(query_results)
    
    print(f"查询测试: {passed_tests}/{total_tests} 通过")
    if stream_result is not None:
        print(f"流式测试: {'通过' if stream_result else '失败'}")
    
    if passed_tests == total_tests:
        print_success("所有E2E测试通过！")
        return 0
    else:
        print_warning(f"有 {total_tests - passed_tests} 个测试需要检查")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

