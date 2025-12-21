"""
新闻流处理器 - 使用Redis Streams实现低延迟金融新闻摄取
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.database.redis_client import redis_client
from app.database.storage import storage_manager
from app.tools.rag import get_rag_tool
from app.tools.finbert_analyzer import finbert_analyzer

logger = logging.getLogger(__name__)


class NewsStreamProcessor:
    """新闻流处理器 - 处理Redis Streams中的新闻数据"""
    
    def __init__(self):
        self.stream_name = "financial_news_stream"
        self.consumer_group = "news_processors"
        self.consumer_name = f"processor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._ensure_consumer_group()
    
    def _ensure_consumer_group(self):
        """确保消费者组存在"""
        try:
            redis_client.xgroup_create(
                self.stream_name,
                self.consumer_group,
                id="0",
                mkstream=True
            )
            logger.info(f"Consumer group {self.consumer_group} ready")
        except Exception as e:
            logger.warning(f"Failed to create consumer group: {e}")
    
    def ingest_news(self, symbol: str, title: str, content: str, 
                   source: str, url: Optional[str] = None, 
                   published_at: Optional[datetime] = None) -> Optional[str]:
        """
        将新闻添加到Redis Stream
        
        Args:
            symbol: 股票代码
            title: 新闻标题
            content: 新闻内容
            source: 新闻来源
            url: 新闻URL（可选）
            published_at: 发布时间（可选）
        
        Returns:
            消息ID或None
        """
        if not published_at:
            published_at = datetime.now()
        
        fields = {
            "symbol": symbol,
            "title": title,
            "content": content,
            "source": source,
            "url": url or "",
            "published_at": published_at.isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
        # 限制Stream大小（保留最近10000条消息）
        message_id = redis_client.xadd(
            self.stream_name,
            fields,
            maxlen=10000
        )
        
        if message_id:
            logger.info(f"Ingested news for {symbol} with message ID: {message_id}")
        
        return message_id
    
    def process_stream(self, count: int = 10, block: int = 1000) -> List[Dict[str, Any]]:
        """
        处理Stream中的新闻消息
        
        Args:
            count: 每次处理的消息数
            block: 阻塞时间（毫秒）
        
        Returns:
            处理的消息列表
        """
        streams = {self.stream_name: ">"}  # ">" 表示读取未处理的消息
        
        messages = redis_client.xreadgroup(
            self.consumer_group,
            self.consumer_name,
            streams,
            count=count,
            block=block
        )
        
        processed = []
        
        for stream_name, stream_messages in messages.items():
            for message_id, fields in stream_messages:
                try:
                    # 解析字段
                    symbol = fields.get(b'symbol', fields.get('symbol', '')).decode() if isinstance(fields.get(b'symbol', ''), bytes) else fields.get('symbol', '')
                    title = fields.get(b'title', fields.get('title', '')).decode() if isinstance(fields.get(b'title', ''), bytes) else fields.get('title', '')
                    content = fields.get(b'content', fields.get('content', '')).decode() if isinstance(fields.get(b'content', ''), bytes) else fields.get('content', '')
                    source = fields.get(b'source', fields.get('source', '')).decode() if isinstance(fields.get(b'source', ''), bytes) else fields.get('source', '')
                    url = fields.get(b'url', fields.get('url', '')).decode() if isinstance(fields.get(b'url', ''), bytes) else fields.get('url', '')
                    published_at_str = fields.get(b'published_at', fields.get('published_at', '')).decode() if isinstance(fields.get(b'published_at', ''), bytes) else fields.get('published_at', '')
                    
                    # 解析时间
                    try:
                        published_at = datetime.fromisoformat(published_at_str)
                    except:
                        published_at = datetime.now()
                    
                    # 处理新闻
                    result = self._process_news_item(
                        symbol=symbol,
                        title=title,
                        content=content,
                        source=source,
                        url=url,
                        published_at=published_at,
                        message_id=message_id.decode() if isinstance(message_id, bytes) else str(message_id)
                    )
                    
                    processed.append(result)
                    
                except Exception as e:
                    logger.error(f"Failed to process message {message_id}: {e}")
        
        return processed
    
    def _process_news_item(self, symbol: str, title: str, content: str,
                          source: str, url: Optional[str], published_at: datetime,
                          message_id: str) -> Dict[str, Any]:
        """
        处理单个新闻项
        
        Args:
            symbol: 股票代码
            title: 标题
            content: 内容
            source: 来源
            url: URL
            published_at: 发布时间
            message_id: 消息ID
        
        Returns:
            处理结果
        """
        # 1. 情感分析（使用FinBERT）
        sentiment = finbert_analyzer.analyze_sentiment(f"{title}\n{content}")
        
        # 2. 保存到MySQL
        news_id = storage_manager.save_news_data(
            symbol=symbol,
            title=title,
            content=content,
            source=source,
            url=url,
            published_at=published_at
        )
        
        # 3. 添加到向量数据库
        get_rag_tool().add_documents([{
            'text': f"{title}\n{content}",
            'metadata': {
                'symbol': symbol,
                'news_id': news_id,
                'source': source,
                'url': url or '',
                'published_at': published_at.isoformat(),
                'sentiment': sentiment['label'],
                'sentiment_score': sentiment['sentiment_score']
            }
        }])
        
        return {
            'message_id': message_id,
            'news_id': news_id,
            'symbol': symbol,
            'sentiment': sentiment,
            'processed_at': datetime.now().isoformat()
        }
    
    def start_processing_loop(self, interval: int = 1):
        """
        启动处理循环（后台任务）
        
        Args:
            interval: 处理间隔（秒）
        """
        import time
        import threading
        
        def loop():
            logger.info(f"Starting news stream processing loop (interval: {interval}s)")
            while True:
                try:
                    processed = self.process_stream(count=10, block=interval * 1000)
                    if processed:
                        logger.info(f"Processed {len(processed)} news items")
                except Exception as e:
                    logger.error(f"Error in processing loop: {e}")
                time.sleep(interval)
        
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logger.info("News stream processing loop started")


# 全局新闻流处理器实例
news_stream_processor = NewsStreamProcessor()

