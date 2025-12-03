"""
存储层测试
"""
import pytest
from datetime import datetime, timedelta
from app.database.storage import storage_manager


class TestStorageManager:
    """存储管理器测试"""
    
    @pytest.mark.unit
    def test_save_and_get_financial_data(self):
        """测试保存和获取金融数据"""
        symbol = "TEST001"
        market = "测试市场"
        data_type = "daily"
        date = datetime.now()
        data = {
            "open": 100.0,
            "close": 105.0,
            "high": 110.0,
            "low": 95.0,
            "volume": 1000000
        }
        
        # 保存数据
        result = storage_manager.save_financial_data(
            symbol=symbol,
            market=market,
            data_type=data_type,
            date=date,
            data=data
        )
        
        assert result is True
        
        # 获取数据
        retrieved_data = storage_manager.get_financial_data(
            symbol=symbol,
            data_type=data_type,
            date=date
        )
        
        assert retrieved_data is not None
        assert retrieved_data["open"] == 100.0
        assert retrieved_data["close"] == 105.0
    
    @pytest.mark.unit
    def test_hot_data_caching(self):
        """测试热数据缓存"""
        symbol = "TEST002"
        data_type = "daily"
        date = datetime.now()  # 当前时间，应该是热数据
        
        data = {"price": 100.0}
        
        # 保存数据
        storage_manager.save_financial_data(
            symbol=symbol,
            market="测试",
            data_type=data_type,
            date=date,
            data=data
        )
        
        # 第一次获取（应该从MySQL，然后回填到Redis）
        result1 = storage_manager.get_financial_data(symbol, data_type, date)
        assert result1 is not None
        
        # 第二次获取（应该从Redis）
        result2 = storage_manager.get_financial_data(symbol, data_type, date)
        assert result2 is not None
        assert result1 == result2
    
    @pytest.mark.unit
    def test_save_news_data(self):
        """测试保存新闻数据"""
        symbol = "TEST003"
        title = "测试新闻标题"
        content = "测试新闻内容"
        source = "测试来源"
        published_at = datetime.now()
        
        news_id = storage_manager.save_news_data(
            symbol=symbol,
            title=title,
            content=content,
            source=source,
            url=None,
            published_at=published_at
        )
        
        assert news_id is not None
        assert isinstance(news_id, int)
    
    @pytest.mark.unit
    def test_get_news_by_symbol(self):
        """测试根据股票代码获取新闻"""
        symbol = "TEST004"
        
        # 保存几条新闻
        for i in range(3):
            storage_manager.save_news_data(
                symbol=symbol,
                title=f"新闻标题{i}",
                content=f"新闻内容{i}",
                source="测试来源",
                url=None,
                published_at=datetime.now()
            )
        
        # 获取新闻
        news_list = storage_manager.get_news_by_symbol(symbol, limit=10)
        
        assert len(news_list) >= 3
        assert all(news["symbol"] == symbol for news in news_list)

