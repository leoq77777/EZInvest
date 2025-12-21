# 新需求分析与实现计划

## 分析时间
2024-12-19

## 一、需求分析

### 需求1: Reinforcement Learning-Driven Retrieval Pipeline with Ray
**描述**: 使用Ray构建强化学习驱动的检索管道，优化金融查询的工具选择，在基准测试中减少35%的无关数据检索。

**当前状态**:
- ❌ 没有强化学习机制
- ❌ 没有Ray框架集成
- ❌ 工具选择是硬编码的（agent.py中直接调用工具）
- ✅ 有多个工具（data_fetcher, quant_tool, policy_tool）

**可行性**: ⭐⭐⭐⭐ (高)
- Ray是成熟的分布式计算框架
- 强化学习可以优化工具选择策略
- 需要定义奖励函数和状态空间

**实现要点**:
1. 集成Ray框架
2. 定义RL环境（状态、动作、奖励）
3. 实现工具选择策略网络
4. 训练和部署RL模型
5. 集成到Agent工作流

---

### 需求2: FinBERT for Financial Text Analysis
**描述**: 集成FinBERT作为专门的金融文本分析模块，在财报电话会议中的情感提取准确率比基线LLM提高15%。

**当前状态**:
- ❌ 使用通用的sentence-transformers模型
- ❌ 没有专门的金融领域模型
- ✅ 有政策分析工具（policy_tool.py）
- ✅ 有文本分析功能

**可行性**: ⭐⭐⭐⭐⭐ (非常高)
- FinBERT是开源的预训练模型
- 可以直接替换现有的embedding模型
- 可以用于情感分析和文本分类

**实现要点**:
1. 安装和集成FinBERT
2. 替换RAG工具中的embedding模型
3. 添加情感分析功能
4. 用于财报和新闻分析
5. 评估性能提升

---

### 需求3: Fine-tuned gpt-oss:20B with QLoRA and 4-bit Quantization
**描述**: 使用QLoRA和4-bit量化在单个消费级GPU上微调gpt-oss:20B，在保持分析质量的同时将内存使用减少65%。

**当前状态**:
- ❌ 只是使用Ollama的gpt-oss:20b，没有微调
- ❌ 没有量化
- ❌ 没有QLoRA
- ✅ 有LLM集成（llm.py）

**可行性**: ⭐⭐⭐ (中等)
- QLoRA需要大量金融数据
- 需要GPU支持
- 微调过程复杂
- 但技术上是可行的

**实现要点**:
1. 准备金融领域微调数据
2. 集成bitsandbytes（4-bit量化）
3. 实现QLoRA微调脚本
4. 导出微调后的模型
5. 集成到Ollama或直接使用

---

### 需求4: Hybrid FAISS (HNSW+IVF_PQ) and Redis Streams
**描述**: 实现混合FAISS（HNSW+IVF_PQ）和Redis Streams数据管道，用于低延迟金融新闻摄取。

**当前状态**:
- ❌ 使用IndexFlatL2（简单平面索引）
- ❌ 没有HNSW（近似最近邻搜索）
- ❌ 没有IVF_PQ（倒排文件+乘积量化）
- ❌ Redis只用于简单缓存，没有Streams
- ✅ 有FAISS集成
- ✅ 有Redis集成

**可行性**: ⭐⭐⭐⭐⭐ (非常高)
- FAISS支持HNSW和IVF_PQ
- Redis Streams是成熟功能
- 可以直接升级现有实现

**实现要点**:
1. 升级FAISS索引到HNSW+IVF_PQ
2. 实现Redis Streams用于新闻摄取
3. 优化索引参数
4. 实现流式数据处理
5. 性能测试和优化

---

## 二、实现优先级

### 高优先级（立即实现）
1. **需求4: Hybrid FAISS + Redis Streams** - 影响最大，实现相对简单
2. **需求2: FinBERT集成** - 直接提升文本分析质量

### 中优先级（近期实现）
3. **需求1: RL Retrieval Pipeline** - 需要更多设计和开发

### 低优先级（长期优化）
4. **需求3: QLoRA微调** - 需要大量数据和计算资源

---

## 三、实现计划

### Phase 1: 基础设施升级（1-2周）
- [ ] 升级FAISS索引到HNSW+IVF_PQ
- [ ] 实现Redis Streams
- [ ] 集成FinBERT
- [ ] 更新依赖和配置

### Phase 2: RL Pipeline（2-3周）
- [ ] 集成Ray框架
- [ ] 设计RL环境
- [ ] 实现工具选择策略
- [ ] 训练和评估模型

### Phase 3: 模型微调（3-4周）
- [ ] 准备微调数据
- [ ] 实现QLoRA微调
- [ ] 模型导出和部署
- [ ] 性能评估

### Phase 4: 测试和优化（1-2周）
- [ ] 端到端测试
- [ ] 性能基准测试
- [ ] 文档更新

---

## 四、技术细节

### 1. FAISS HNSW+IVF_PQ配置
```python
# HNSW参数
M = 32  # 每个节点的连接数
ef_construction = 200  # 构建时的搜索范围
ef_search = 50  # 搜索时的搜索范围

# IVF参数
nlist = 100  # 聚类中心数
nprobe = 10  # 搜索时的聚类中心数

# PQ参数
m = 8  # 子向量数
bits = 8  # 每个子向量的量化位数
```

### 2. Redis Streams结构
```
news_stream:
  - 消息ID: timestamp-sequence
  - 字段: symbol, title, content, source, published_at
  - 消费者组: news_processors
```

### 3. FinBERT集成
- 模型: `yiyanghkust/finbert-tone`
- 用途: 情感分析、文本分类
- 替换: RAG embedding + 独立情感分析模块

### 4. RL环境设计
- 状态: 查询特征、历史工具使用、数据质量反馈
- 动作: 选择工具（data_fetcher, quant_tool, policy_tool）
- 奖励: 数据相关性、响应时间、用户满意度

---

## 五、预期收益

1. **检索效率**: 减少35%无关数据检索
2. **情感分析**: 准确率提升15%
3. **内存使用**: 减少65%
4. **延迟**: 新闻摄取延迟降低

---

## 六、风险评估

1. **技术风险**: RL训练可能不稳定
2. **资源风险**: QLoRA需要GPU
3. **兼容性风险**: 新依赖可能与现有系统冲突
4. **性能风险**: 复杂索引可能影响查询速度

---

## 七、下一步行动

1. 立即开始实现需求4（FAISS升级）
2. 同时集成FinBERT
3. 设计RL环境架构
4. 准备微调数据收集

