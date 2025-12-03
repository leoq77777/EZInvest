"""
数据预取调度器 - 在低峰期预取数据
"""
import schedule
import time
import logging
from datetime import datetime
from typing import List
from app.services.data_fetcher import data_fetcher
from app.config import settings

logger = logging.getLogger(__name__)


class PrefetchScheduler:
    """数据预取调度器"""
    
    def __init__(self):
        self.is_running = False
        self.symbols_to_prefetch: List[str] = []
    
    def add_symbol(self, symbol: str):
        """添加需要预取的股票代码"""
        if symbol not in self.symbols_to_prefetch:
            self.symbols_to_prefetch.append(symbol)
            logger.info(f"Added {symbol} to prefetch list")
    
    def remove_symbol(self, symbol: str):
        """移除预取股票代码"""
        if symbol in self.symbols_to_prefetch:
            self.symbols_to_prefetch.remove(symbol)
            logger.info(f"Removed {symbol} from prefetch list")
    
    def prefetch_data(self):
        """执行数据预取"""
        if not settings.DATA_PREFETCH_ENABLED:
            return
        
        logger.info(f"Starting data prefetch for {len(self.symbols_to_prefetch)} symbols")
        
        for symbol in self.symbols_to_prefetch:
            try:
                logger.info(f"Prefetching data for {symbol}")
                success = data_fetcher.fetch_and_save_stock_data(symbol)
                if success:
                    logger.info(f"Successfully prefetched data for {symbol}")
                else:
                    logger.warning(f"Failed to prefetch data for {symbol}")
            except Exception as e:
                logger.error(f"Error prefetching data for {symbol}: {e}")
        
        logger.info("Data prefetch completed")
    
    def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        if not settings.DATA_PREFETCH_ENABLED:
            logger.info("Data prefetch is disabled")
            return
        
        # 在配置的时间执行预取
        schedule.every().day.at(f"{settings.DATA_PREFETCH_HOUR:02d}:00").do(self.prefetch_data)
        
        self.is_running = True
        logger.info(f"Scheduler started, will prefetch data at {settings.DATA_PREFETCH_HOUR:02d}:00 daily")
        
        # 在后台线程中运行
        import threading
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
    
    def _run(self):
        """运行调度循环"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def stop(self):
        """停止调度器"""
        self.is_running = False
        schedule.clear()
        logger.info("Scheduler stopped")


# 全局调度器实例
prefetch_scheduler = PrefetchScheduler()

