"""
配置管理模块
"""
import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        # Fallback for older pydantic
        from pydantic import BaseModel as BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # MySQL配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "ezinvest"
    
    # Ollama配置
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gpt-oss:20b"
    
    # FAISS配置
    FAISS_INDEX_PATH: str = "./data/faiss_index"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # FAISS索引类型: "flat", "hnsw", "ivf_pq", "hybrid"
    FAISS_INDEX_TYPE: str = "hybrid"  # 使用混合索引（HNSW+IVF_PQ）
    # 可选的 SQLite URL（用于本地开发/测试），例如：sqlite:///./dev.db 或 sqlite:///:memory:
    SQLITE_URL: str = ""
    # 是否使用轻量级 fallback 嵌入（当环境中缺少或无法安全加载 heavy ML 库时启用）
    EMBEDDING_FALLBACK: bool = True
    
    # FinBERT配置
    USE_FINBERT: bool = True  # 是否使用FinBERT进行情感分析
    FINBERT_MODEL: str = "yiyanghkust/finbert-tone"
    
    # Redis Streams配置
    NEWS_STREAM_NAME: str = "financial_news_stream"
    NEWS_STREAM_MAXLEN: int = 10000  # Stream最大长度
    USE_REDIS_STREAMS: bool = True  # 是否使用Redis Streams
    
    # RL检索配置
    USE_RL_RETRIEVAL: bool = False  # 是否使用RL驱动的工具选择
    RL_MODEL_PATH: Optional[str] = None  # RL模型路径（如果使用RL）
    
    # 数据预取配置
    DATA_PREFETCH_ENABLED: bool = True
    DATA_PREFETCH_HOUR: int = 2  # 凌晨2点预取数据
    
    # API限流配置
    AKSHARE_RATE_LIMIT: int = 100  # 每分钟请求数
    AKSHARE_RETRY_TIMES: int = 3
    
    # 冷热数据配置
    HOT_DATA_TTL: int = 3600  # Redis热数据TTL（秒）
    COLD_DATA_THRESHOLD: int = 86400  # 超过24小时的数据视为冷数据

    # 是否在开发/测试环境使用 fakeredis（内存版 Redis）作为回退或替代。
    # 设置环境变量 `USE_FAKE_REDIS=1` 可启用。默认关闭，以免影响生产环境。
    USE_FAKE_REDIS: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

