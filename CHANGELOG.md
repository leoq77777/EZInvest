# 更新日志

## [2.0.0] - 2024-12-19

### 新增功能

#### RL驱动的检索管道
- ✅ 实现RL环境（状态、动作、奖励）
- ✅ 实现策略网络（PyTorch）
- ✅ 实现训练框架（支持Ray）
- ✅ 集成到Agent（可选启用）
- ✅ 训练脚本模板

#### FinBERT金融文本分析
- ✅ 集成FinBERT模型（yiyanghkust/finbert-tone）
- ✅ 实现情感分析功能
- ✅ 实现财报电话会议分析
- ✅ 集成到政策分析工具

#### 混合FAISS索引
- ✅ 升级到HNSW+IVF_PQ混合索引
- ✅ 自动索引训练
- ✅ 向后兼容（fallback到IndexFlatL2）

#### Redis Streams
- ✅ 实现Redis Streams支持
- ✅ 新闻流处理器
- ✅ 低延迟新闻摄取
- ✅ 自动情感分析和向量化

### 改进

- ✅ 优化代码结构
- ✅ 删除无用文件（24个）
- ✅ 更新文档
- ✅ 改进错误处理
- ✅ 添加配置选项

### 依赖更新

- ✅ 添加transformers, torch（FinBERT）
- ✅ 添加ray[default]（RL分布式训练）
- ✅ 添加bitsandbytes, accelerate, peft（QLoRA，待使用）

## [1.0.0] - 2024-12-19

### 初始版本

- ✅ 基础项目结构
- ✅ 数据获取（akshare）
- ✅ 数据存储（Redis + MySQL）
- ✅ 量化分析工具
- ✅ 政策分析工具
- ✅ RAG工具（基础索引）
- ✅ LLM集成（Ollama）
- ✅ Agent核心逻辑
- ✅ 前端界面
- ✅ 测试框架

