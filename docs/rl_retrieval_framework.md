# RL检索管道框架文档

## 概述

实现了基于强化学习的工具选择框架，用于优化金融查询的检索管道。该框架可以减少无关数据检索，提高系统效率。

## 架构

### 1. 环境 (Environment)
**文件**: `app/services/rl_retrieval/environment.py`

定义了RL环境：
- **状态空间**: 15维向量
  - 查询特征（5维）：长度、关键词类型等
  - 历史工具使用（4维）：每个工具的使用次数
  - 数据质量反馈（4维）：每个工具的结果质量
  - 步骤信息（2维）：当前步骤、是否接近结束

- **动作空间**: 5个动作
  - 0: data_fetcher - 数据获取工具
  - 1: quant_tool - 量化分析工具
  - 2: policy_tool - 政策分析工具
  - 3: rag_tool - RAG检索工具
  - 4: none - 不选择任何工具

- **奖励函数**:
  - 数据相关性奖励（基于结果质量）
  - 时间惩罚（执行时间越长，奖励越少）
  - 工具选择合理性奖励（基于查询类型）

### 2. Agent (策略网络)
**文件**: `app/services/rl_retrieval/agent.py`

实现了策略梯度Agent：
- **网络结构**: 3层全连接网络
  - 输入层: 15维（状态维度）
  - 隐藏层: 64维（可配置）
  - 输出层: 5维（动作维度）

- **算法**: REINFORCE（策略梯度）
- **功能**:
  - 动作选择（训练/测试模式）
  - 策略更新
  - 模型保存/加载

### 3. 训练器 (Trainer)
**文件**: `app/services/rl_retrieval/trainer.py`

训练框架（不包含实际训练）：
- 支持Ray分布式训练（可选）
- Episode训练
- 模型评估
- 训练数据准备框架

## 集成

### Agent集成
RL检索已集成到 `InvestmentAgent`：
- 可通过配置启用/禁用
- 自动fallback到规则选择
- 支持模型加载

### 配置
在 `app/config.py` 中：
```python
USE_RL_RETRIEVAL: bool = False  # 是否使用RL
RL_MODEL_PATH: Optional[str] = None  # 模型路径
```

## 使用

### 1. 启用RL检索
```python
# 在配置中启用
USE_RL_RETRIEVAL = True
RL_MODEL_PATH = "./models/rl_retrieval_agent.pt"
```

### 2. 训练模型（需要单独执行）
```bash
# 准备训练数据（JSON格式）
# [
#   {"query": "分析000001的价格走势", "symbol": "000001"},
#   ...
# ]

# 运行训练脚本
python scripts/train_rl_retrieval.py \
    --episodes 1000 \
    --data_path ./data/training_data.json \
    --model_path ./models/rl_retrieval_agent.pt \
    --save_interval 100
```

### 3. 使用训练好的模型
```python
from app.services.agent import InvestmentAgent

agent = InvestmentAgent(
    use_rl=True,
    rl_model_path="./models/rl_retrieval_agent.pt"
)

result = agent.process_query("分析000001的投资价值")
```

## 训练要求

### 数据准备
1. **训练数据格式**: JSON文件
   ```json
   [
     {
       "query": "用户查询文本",
       "symbol": "股票代码（可选）"
     }
   ]
   ```

2. **数据量**: 建议至少1000+样本
3. **数据质量**: 需要多样化的查询类型

### 超参数
- 学习率: 0.001（默认）
- 折扣因子: 0.99
- 隐藏层维度: 64
- 最大步骤数: 5

### 计算资源
- CPU训练: 可行但较慢
- GPU训练: 推荐（如果可用）
- Ray分布式: 可选，用于大规模训练

## 预期效果

- **减少无关数据检索**: 目标35%
- **提高响应效率**: 通过智能工具选择
- **改善用户体验**: 更相关的检索结果

## 注意事项

1. **训练需要额外步骤**: 
   - 准备大量训练数据
   - 配置训练超参数
   - 运行独立训练脚本

2. **模型未训练时**: 
   - 使用随机策略（探索）
   - 性能可能不如规则选择
   - 需要训练后才能体现优势

3. **Fallback机制**: 
   - RL失败时自动使用规则选择
   - 确保系统稳定性

## 下一步

1. **准备训练数据**: 从实际使用中收集查询数据
2. **训练模型**: 运行训练脚本
3. **评估性能**: 对比RL和规则选择的性能
4. **优化**: 根据结果调整超参数和奖励函数

