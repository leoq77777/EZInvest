"""
Redis 客户端封装，支持在配置或连接失败时回退到 fakeredis（内存实现），
方便在开发/测试环境中使用而无需真实 Redis 服务。
"""
from typing import Optional, Any
import json
import logging

import redis
from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 客户端单例，支持自动回退到 fakeredis。"""

    _instance: Optional['RedisClient'] = None
    _client: Optional[Any] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, '_client', None) is not None:
            return

        self._connection_checked = False
        self._available = False
        self._using_fake = False

        # 优先根据配置决定是否使用 fakeredis
        if settings.USE_FAKE_REDIS:
            self._try_use_fakeredis(reason="configured")
            return

        # 否则尝试连接真实 Redis（延迟检测将在 ping 时执行）
        try:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # 不立即 ping，延迟到实际使用时检测
            self._available = True
        except Exception as e:
            logger.warning(f"Failed to instantiate redis client: {e}")
            # 尝试回退到 fakeredis
            self._try_use_fakeredis(reason="instantiate-failed")

    def _try_use_fakeredis(self, reason: str = "") -> None:
        """尝试使用 fakeredis 作为回退实现（按需导入）。"""
        try:
            import fakeredis

            self._client = fakeredis.FakeStrictRedis(decode_responses=True)
            self._available = True
            self._using_fake = True
            self._connection_checked = True
            logger.info(f"Using fakeredis as Redis fallback (reason={reason})")
        except Exception as ex:
            logger.warning(f"fakeredis not available or failed to init: {ex}")
            self._client = None
            self._available = False
            self._using_fake = False

    def _ensure_connection(self):
        """确保连接可用（延迟检查）。如果真实 Redis 不可达并且 fakeredis 可用，则自动回退。"""
        if self._connection_checked:
            return

        if self._client is None:
            # 没有客户端，尝试回退到 fakeredis
            self._try_use_fakeredis(reason="no-client")
            self._connection_checked = True
            return

        # 若已经是 fakeredis，不需要 ping
        if getattr(self, '_using_fake', False):
            self._connection_checked = True
            self._available = True
            return

        try:
            # 做一次轻量 ping 检查
            self._client.ping()
            self._connection_checked = True
            self._available = True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            # 尝试自动回退到 fakeredis（如果可用）
            self._try_use_fakeredis(reason="ping-failed")
            self._connection_checked = True

    @property
    def client(self) -> Any:
        """获取底层 Redis 客户端（真实或 fakeredis）。"""
        self._ensure_connection()
        return self._client

    def get(self, key: str) -> Optional[str]:
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return None
            return self._client.get(key)
        except Exception as e:
            logger.debug(f"Redis get error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return False
            return self._client.set(key, value, ex=ex)
        except Exception as e:
            logger.debug(f"Redis set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> int:
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return 0
            return self._client.delete(key)
        except Exception as e:
            logger.debug(f"Redis delete error for key {key}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return False
            return bool(self._client.exists(key))
        except Exception as e:
            logger.debug(f"Redis exists error for key {key}: {e}")
            return False

    def expire(self, key: str, time: int) -> bool:
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return False
            return self._client.expire(key, time)
        except Exception as e:
            logger.debug(f"Redis expire error for key {key}: {e}")
            return False

    def get_json(self, key: str) -> Optional[Any]:
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    def xadd(self, stream: str, fields: Dict[str, Any], maxlen: Optional[int] = None) -> Optional[str]:
        """
        向Redis Stream添加消息
        
        Args:
            stream: Stream名称
            fields: 消息字段字典
            maxlen: 最大长度（可选，用于限制Stream大小）
        
        Returns:
            消息ID或None
        """
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return None
            
            # 转换值为字符串
            str_fields = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v) 
                         for k, v in fields.items()}
            
            # 添加消息
            message_id = self._client.xadd(stream, str_fields, maxlen=maxlen)
            return message_id
        except Exception as e:
            logger.error(f"Redis xadd error for stream {stream}: {e}")
            return None
    
    def xread(self, streams: Dict[str, str], count: Optional[int] = None, block: Optional[int] = None) -> Dict[str, List]:
        """
        从Redis Stream读取消息
        
        Args:
            streams: {stream_name: last_id} 字典
            count: 每次读取的最大消息数
            block: 阻塞时间（毫秒）
        
        Returns:
            {stream_name: [messages]} 字典
        """
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return {}
            
            result = self._client.xread(streams, count=count, block=block)
            # 转换结果格式
            return {stream.decode() if isinstance(stream, bytes) else stream: messages 
                   for stream, messages in result}
        except Exception as e:
            logger.error(f"Redis xread error: {e}")
            return {}
    
    def xgroup_create(self, stream: str, group: str, id: str = "0", mkstream: bool = True) -> bool:
        """
        创建消费者组
        
        Args:
            stream: Stream名称
            group: 消费者组名称
            id: 起始ID（默认"0"表示从开始）
            mkstream: 如果Stream不存在是否创建
        
        Returns:
            是否成功
        """
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return False
            
            self._client.xgroup_create(stream, group, id=id, mkstream=mkstream)
            return True
        except Exception as e:
            # 如果组已存在，忽略错误
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer group {group} already exists")
                return True
            logger.error(f"Redis xgroup_create error: {e}")
            return False
    
    def xreadgroup(self, group: str, consumer: str, streams: Dict[str, str], 
                   count: Optional[int] = None, block: Optional[int] = None) -> Dict[str, List]:
        """
        从消费者组读取消息
        
        Args:
            group: 消费者组名称
            consumer: 消费者名称
            streams: {stream_name: ">"} 字典，">"表示读取未处理的消息
            count: 每次读取的最大消息数
            block: 阻塞时间（毫秒）
        
        Returns:
            {stream_name: [messages]} 字典
        """
        try:
            self._ensure_connection()
            if not getattr(self, '_available', False):
                return {}
            
            result = self._client.xreadgroup(group, consumer, streams, count=count, block=block)
            # 转换结果格式
            return {stream.decode() if isinstance(stream, bytes) else stream: messages 
                   for stream, messages in result}
        except Exception as e:
            logger.error(f"Redis xreadgroup error: {e}")
            return {}
    
    def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        return self.set(key, value, ex=ex)

    def close(self):
        if self._client and not getattr(self, '_using_fake', False):
            try:
                self._client.close()
            except Exception:
                pass


# 全局 Redis 客户端实例
redis_client = RedisClient()

