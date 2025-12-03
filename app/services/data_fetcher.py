"""
akshare数据获取服务
"""
import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import time
import logging
from app.config import settings
from app.database.storage import storage_manager

logger = logging.getLogger(__name__)


class RateLimiter:
    """简单的限流器"""
    
    def __init__(self, max_calls: int, period: int = 60):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
    
    def wait_if_needed(self):
        """如果需要，等待直到可以调用"""
        now = time.time()
        # 移除过期记录
        self.calls = [call_time for call_time in self.calls if now - call_time < self.period]
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                self.calls = []
        
        self.calls.append(time.time())


class AkshareDataFetcher:
    """akshare数据获取器"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter(
            max_calls=settings.AKSHARE_RATE_LIMIT,
            period=60
        )
    
    def _retry_request(self, func, *args, **kwargs):
        """重试请求"""
        for attempt in range(settings.AKSHARE_RETRY_TIMES):
            try:
                self.rate_limiter.wait_if_needed()
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{settings.AKSHARE_RETRY_TIMES}): {e}")
                if attempt < settings.AKSHARE_RETRY_TIMES - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise
    
    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票基本信息"""
        try:
            # 获取股票实时行情
            df = self._retry_request(ak.stock_zh_a_spot_em)
            
            # 查找目标股票
            stock = df[df['代码'] == symbol]
            if stock.empty:
                return None
            
            stock_data = stock.iloc[0].to_dict()
            return {
                "symbol": symbol,
                "name": stock_data.get('名称', ''),
                "current_price": float(stock_data.get('最新价', 0)),
                "change_percent": float(stock_data.get('涨跌幅', 0)),
                "volume": float(stock_data.get('成交量', 0)),
                "turnover": float(stock_data.get('成交额', 0)),
                "market_cap": float(stock_data.get('总市值', 0)),
            }
        except Exception as e:
            logger.error(f"Failed to get stock info for {symbol}: {e}")
            return None
    
    def get_stock_daily(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """获取股票日线数据"""
        try:
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y%m%d")
            
            df = self._retry_request(
                ak.stock_zh_a_hist,
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=""
            )
            
            if df.empty:
                return None
            
            # 转换日期格式
            df['日期'] = pd.to_datetime(df['日期'])
            return df
        except Exception as e:
            logger.error(f"Failed to get stock daily data for {symbol}: {e}")
            return None
    
    def get_stock_realtime(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票实时行情"""
        try:
            df = self._retry_request(ak.stock_zh_a_spot_em)
            stock = df[df['代码'] == symbol]
            
            if stock.empty:
                return None
            
            stock_data = stock.iloc[0].to_dict()
            return {
                "symbol": symbol,
                "current_price": float(stock_data.get('最新价', 0)),
                "change": float(stock_data.get('涨跌额', 0)),
                "change_percent": float(stock_data.get('涨跌幅', 0)),
                "volume": float(stock_data.get('成交量', 0)),
                "turnover": float(stock_data.get('成交额', 0)),
                "high": float(stock_data.get('最高', 0)),
                "low": float(stock_data.get('最低', 0)),
                "open": float(stock_data.get('今开', 0)),
                "yesterday_close": float(stock_data.get('昨收', 0)),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get realtime data for {symbol}: {e}")
            return None
    
    def fetch_and_save_stock_data(self, symbol: str, market: str = "A股") -> bool:
        """获取并保存股票数据"""
        try:
            # 获取日线数据
            df = self.get_stock_daily(symbol)
            if df is None or df.empty:
                logger.warning(f"No data found for {symbol}")
                return False
            
            # 保存每日数据
            for _, row in df.iterrows():
                date = row['日期']
                data = {
                    "open": float(row.get('开盘', 0)),
                    "close": float(row.get('收盘', 0)),
                    "high": float(row.get('最高', 0)),
                    "low": float(row.get('最低', 0)),
                    "volume": float(row.get('成交量', 0)),
                    "turnover": float(row.get('成交额', 0)),
                    "amplitude": float(row.get('振幅', 0)),
                    "change_percent": float(row.get('涨跌幅', 0)),
                }
                
                storage_manager.save_financial_data(
                    symbol=symbol,
                    market=market,
                    data_type="daily",
                    date=date,
                    data=data
                )
            
            logger.info(f"Successfully saved {len(df)} days of data for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to fetch and save data for {symbol}: {e}")
            return False
    
    def get_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表"""
        try:
            df = self._retry_request(ak.stock_zh_a_spot_em)
            return [
                {
                    "symbol": row['代码'],
                    "name": row['名称']
                }
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"Failed to get stock list: {e}")
            return []


# 全局数据获取器实例
data_fetcher = AkshareDataFetcher()

