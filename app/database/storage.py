"""
数据存储管理 - 冷热数据分离
"""
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
from app.database.redis_client import redis_client
from app.database.mysql_client import SessionLocal, FinancialData, NewsData
from app.config import settings
import json


class StorageManager:
    """存储管理器 - 处理冷热数据分离"""
    
    @staticmethod
    def _get_redis_key(symbol: str, data_type: str, date: str = None) -> str:
        """生成Redis键"""
        if date:
            return f"financial:{symbol}:{data_type}:{date}"
        return f"financial:{symbol}:{data_type}"
    
    @staticmethod
    def _is_hot_data(date: datetime) -> bool:
        """判断是否为热数据"""
        age = (datetime.now() - date).total_seconds()
        return age < settings.COLD_DATA_THRESHOLD
    
    def save_financial_data(
        self,
        symbol: str,
        market: str,
        data_type: str,
        date: datetime,
        data: Dict[str, Any]
    ) -> bool:
        """保存金融数据（自动判断冷热）"""
        date_str = date.strftime("%Y-%m-%d")
        
        # 判断是否为热数据
        is_hot = self._is_hot_data(date)
        
        if is_hot:
            # 保存到Redis（热数据）
            key = self._get_redis_key(symbol, data_type, date_str)
            redis_client.set_json(
                key,
                {
                    "symbol": symbol,
                    "market": market,
                    "data_type": data_type,
                    "date": date_str,
                    "data": data
                },
                ex=settings.HOT_DATA_TTL
            )
        
        # 同时保存到MySQL（持久化）
        db = SessionLocal()
        try:
            # 检查是否已存在
            existing = db.query(FinancialData).filter(
                FinancialData.symbol == symbol,
                FinancialData.data_type == data_type,
                FinancialData.date == date
            ).first()
            
            if existing:
                existing.data = json.dumps(data, ensure_ascii=False)
                existing.updated_at = datetime.utcnow()
            else:
                new_data = FinancialData(
                    symbol=symbol,
                    market=market,
                    data_type=data_type,
                    date=date,
                    data=json.dumps(data, ensure_ascii=False)
                )
                db.add(new_data)
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_financial_data(
        self,
        symbol: str,
        data_type: str,
        date: datetime
    ) -> Optional[Dict[str, Any]]:
        """获取金融数据（优先从Redis，再从MySQL）"""
        date_str = date.strftime("%Y-%m-%d")
        
        # 先尝试从Redis获取（热数据）
        key = self._get_redis_key(symbol, data_type, date_str)
        hot_data = redis_client.get_json(key)
        
        if hot_data:
            return hot_data.get("data")
        
        # 从MySQL获取（冷数据）
        db = SessionLocal()
        try:
            result = db.query(FinancialData).filter(
                FinancialData.symbol == symbol,
                FinancialData.data_type == data_type,
                FinancialData.date == date
            ).first()
            
            if result:
                data = json.loads(result.data)
                # 如果是热数据，回填到Redis
                if self._is_hot_data(result.date):
                    redis_client.set_json(key, {
                        "symbol": symbol,
                        "market": result.market,
                        "data_type": data_type,
                        "date": date_str,
                        "data": data
                    }, ex=settings.HOT_DATA_TTL)
                return data
            return None
        finally:
            db.close()
    
    def save_news_data(
        self,
        symbol: str,
        title: str,
        content: str,
        source: str,
        url: Optional[str],
        published_at: datetime,
        embedding_id: Optional[int] = None
    ) -> int:
        """保存新闻数据"""
        db = SessionLocal()
        try:
            news = NewsData(
                symbol=symbol,
                title=title,
                content=content,
                source=source,
                url=url,
                published_at=published_at,
                embedding_id=embedding_id
            )
            db.add(news)
            db.commit()
            db.refresh(news)
            return news.id
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_news_by_symbol(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """根据股票代码获取新闻"""
        db = SessionLocal()
        try:
            results = db.query(NewsData).filter(
                NewsData.symbol == symbol
            ).order_by(
                NewsData.published_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "content": r.content,
                    "source": r.source,
                    "url": r.url,
                    "published_at": r.published_at.isoformat(),
                    "embedding_id": r.embedding_id
                }
                for r in results
            ]
        finally:
            db.close()


# 全局存储管理器实例
storage_manager = StorageManager()

