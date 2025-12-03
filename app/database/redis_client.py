"""
Redis客户端封装
"""
import redis
from typing import Optional, Any
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端单例"""
    
    _instance: Optional['RedisClient'] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # 延迟连接检查，避免在导入时失败
            self._connection_checked = False
    
    def _ensure_connection(self):
        """确保连接可用（延迟检查）"""
        if not self._connection_checked:
            try:
                self._client.ping()
                self._connection_checked = True
            except redis.ConnectionError as e:
                logger.warning(f"Redis connection failed: {e}")
                self._connection_checked = True  # 标记为已检查，避免重复尝试
    
    @property
    def client(self) -> redis.Redis:
        """获取Redis客户端"""
        self._ensure_connection()
        return self._client
    
    def get(self, key: str) -> Optional[str]:
        """获取值"""
        return self._client.get(key)
    
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """设置值"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        return self._client.set(key, value, ex=ex)
    
    def delete(self, key: str) -> int:
        """删除键"""
        return self._client.delete(key)
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return bool(self._client.exists(key))
    
    def expire(self, key: str, time: int) -> bool:
        """设置过期时间"""
        return self._client.expire(key, time)
    
    def get_json(self, key: str) -> Optional[Any]:
        """获取JSON值"""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """设置JSON值"""
        return self.set(key, value, ex=ex)
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()


# 全局Redis客户端实例
redis_client = RedisClient()

