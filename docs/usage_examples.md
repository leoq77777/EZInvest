# 使用示例

## 基础使用

### 1. 启动服务

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（.env文件）
# 启动服务
uvicorn app.main:app --reload --port 8000
```

### 2. API调用示例

#### 查询投资建议
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "分析000001的投资价值",
    "stream": false
  }'
```

#### 流式查询
```bash
curl -X POST "http://localhost:8000/api/query/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "分析000001的投资价值",
    "stream": true
  }'
```

### 3. Python代码示例

#### 基础查询
```python
from app.services.agent import investment_agent

# 处理查询
result = investment_agent.process_query("分析000001的投资价值")

if result['success']:
    print(f"股票: {result['name']} ({result['symbol']})")
    print(f"建议: {result['advice']}")
    print(f"量化分析: {result['quant_analysis']}")
    print(f"新闻分析: {result['news_analysis']}")
else:
    print(f"错误: {result['error']}")
```

#### FinBERT情感分析
```python
from app.tools.finbert_analyzer import finbert_analyzer

# 分析文本情感
text = "公司发布季度财报，营收增长20%，净利润大幅提升"
sentiment = finbert_analyzer.analyze_sentiment(text)

print(f"情感: {sentiment['label']}")  # positive/negative/neutral
print(f"分数: {sentiment['sentiment_score']}")  # -1到1
print(f"置信度: {sentiment['score']}")

# 分析财报电话会议
transcript = """
Q: 公司本季度业绩如何？
A: 本季度营收增长强劲，主要得益于新产品线的成功推出...
"""
earnings_analysis = finbert_analyzer.analyze_earnings_call(transcript)
print(f"整体情感: {earnings_analysis['overall_sentiment']}")
print(f"关键点: {earnings_analysis['key_points']}")
```

#### RAG检索
```python
from app.tools.rag import get_rag_tool

rag_tool = get_rag_tool()

# 添加文档
rag_tool.add_documents([
    {
        'text': '平安银行发布2024年第一季度财报，净利润同比增长15%',
        'metadata': {
            'symbol': '000001',
            'source': '财报',
            'date': '2024-03-31'
        }
    }
])

# 搜索
results = rag_tool.search('平安银行财报', top_k=5)
for result in results:
    print(f"文本: {result['text']}")
    print(f"相似度: {result['score']}")
    print(f"元数据: {result['metadata']}")
```

#### Redis Streams新闻摄取
```python
from app.services.news_stream_processor import news_stream_processor
from datetime import datetime

# 添加新闻到Stream
message_id = news_stream_processor.ingest_news(
    symbol="000001",
    title="平安银行发布新产品",
    content="平安银行今日发布了一款新的理财产品...",
    source="财经网",
    url="https://example.com/news/123",
    published_at=datetime.now()
)

print(f"消息ID: {message_id}")

# 处理Stream中的新闻
processed = news_stream_processor.process_stream(count=10)
for item in processed:
    print(f"处理: {item['news_id']}, 情感: {item['sentiment']['label']}")
```

#### 量化分析
```python
from app.services.quant_tool import quant_tool

# 计算技术指标
indicators = quant_tool.calculate_technical_indicators("000001")

print(f"RSI: {indicators['rsi']['current']}")
print(f"MACD趋势: {indicators['macd']['trend']}")
print(f"趋势方向: {indicators['trend']['direction']}")

# 生成分析报告
report = quant_tool.generate_analysis_report("000001")
print(report)
```

#### 政策新闻分析
```python
from app.services.policy_tool import policy_tool

# 获取新闻
articles = policy_tool.fetch_news("000001", limit=10)

# 保存到数据库（使用Redis Streams）
news_ids = policy_tool.save_news_to_database("000001", articles, use_stream=True)

# 搜索相关新闻
results = policy_tool.search_news("000001", "新产品发布", top_k=5)
for result in results:
    print(f"标题: {result['title']}")
    print(f"情感: {result.get('sentiment', 'N/A')}")
```

## 高级使用

### 启用RL检索（需要训练模型）

```python
from app.services.agent import InvestmentAgent

# 创建使用RL的Agent
agent = InvestmentAgent(
    use_rl=True,
    rl_model_path="./models/rl_retrieval_agent.pt"
)

# 使用RL选择工具
result = agent.process_query("分析000001")
```

### 自定义配置

```python
from app.config import settings

# 修改配置
settings.USE_FINBERT = True
settings.USE_REDIS_STREAMS = True
settings.FAISS_INDEX_TYPE = "hybrid"
```

### 批量处理

```python
from app.services.data_fetcher import data_fetcher

# 批量获取股票数据
symbols = ["000001", "000002", "600519"]
for symbol in symbols:
    data_fetcher.fetch_and_save_stock_data(symbol)
    print(f"已获取 {symbol} 的数据")
```

## 前端使用

1. 打开浏览器访问 `http://localhost:8000`
2. 在聊天界面输入查询，例如："分析000001的投资价值"
3. 系统会自动：
   - 识别股票代码
   - 获取数据
   - 进行量化分析
   - 搜索相关新闻
   - 生成投资建议

## 测试示例

### 单元测试
```python
import pytest
from app.services.quant_tool import quant_tool

def test_quant_analysis():
    indicators = quant_tool.calculate_technical_indicators("TEST")
    assert "basic_stats" in indicators
```

### 集成测试
```python
from app.services.agent import investment_agent

def test_agent_query():
    result = investment_agent.process_query("测试查询")
    assert "success" in result
```

## 故障排除

### 常见问题

1. **Redis连接失败**
   - 检查Redis服务是否运行
   - 检查配置中的Redis地址和端口

2. **MySQL连接失败**
   - 检查MySQL服务是否运行
   - 检查数据库配置和权限

3. **Ollama连接失败**
   - 检查Ollama服务是否运行
   - 检查模型是否已下载

4. **FinBERT加载失败**
   - 检查transformers库是否安装
   - 检查网络连接（首次下载模型）

5. **FAISS索引错误**
   - 检查索引文件路径
   - 尝试删除旧索引重新创建

## 性能优化建议

1. **使用混合索引**: 大数据集时使用hybrid索引
2. **启用Redis Streams**: 提高新闻处理效率
3. **使用FinBERT**: 提高情感分析准确率
4. **配置数据预取**: 低峰期自动预取数据
5. **优化查询**: 提供明确的股票代码或名称

