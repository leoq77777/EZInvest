# Part 5: RAG工具实现

## 完成时间
2024-12-19

## 完成内容

### 1. RAG工具 (`app/tools/rag.py`)
- 实现了基于FAISS的向量数据库
- 使用sentence-transformers进行文本嵌入
- 支持文档添加、相似度搜索
- 支持基于metadata的过滤搜索
- 自动持久化索引到磁盘

### 2. LLM集成 (`app/tools/llm.py`)
- 实现了Ollama客户端
- 支持同步和流式生成
- 实现了Prompt管理器
- 包含系统提示、查询扩展提示、分析提示等

## 主要功能

### RAG工具
- `add_documents()`: 添加文档到向量数据库
- `search()`: 通用相似度搜索
- `search_by_symbol()`: 按股票代码搜索
- `get_stats()`: 获取索引统计信息

### LLM客户端
- `generate()`: 同步生成文本
- `generate_stream()`: 流式生成文本
- 自动连接检查和错误处理

### Prompt管理
- 系统提示：定义AI助手的角色和能力
- 查询扩展提示：帮助识别金融标的和扩展问题
- 分析提示：整合多源信息生成投资建议

## 技术细节

### 向量数据库
- 使用FAISS L2距离索引
- 支持多语言嵌入模型（paraphrase-multilingual-MiniLM-L12-v2）
- 索引自动持久化

### 嵌入模型
- 默认使用sentence-transformers的多语言模型
- 支持中文和英文
- 可配置其他模型

## 下一步
- Part 6: 实现Quant Tool（量化分析工具）

