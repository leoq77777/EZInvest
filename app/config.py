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
    OLLAMA_MODEL: str = "gpt-oss-20b"
    
    # FAISS配置
    FAISS_INDEX_PATH: str = "./data/faiss_index"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    # 数据预取配置
    DATA_PREFETCH_ENABLED: bool = True
    DATA_PREFETCH_HOUR: int = 2  # 凌晨2点预取数据
    
    # API限流配置
    AKSHARE_RATE_LIMIT: int = 100  # 每分钟请求数
    AKSHARE_RETRY_TIMES: int = 3
    
    # 冷热数据配置
    HOT_DATA_TTL: int = 3600  # Redis热数据TTL（秒）
    COLD_DATA_THRESHOLD: int = 86400  # 超过24小时的数据视为冷数据
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

