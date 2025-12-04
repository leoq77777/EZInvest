"""
政策分析工具 - 网络爬虫和FAISS向量存储
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import re
from app.tools.rag import get_rag_tool
from app.database.storage import storage_manager
import time

logger = logging.getLogger(__name__)


class PolicyTool:
    """政策分析工具"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.sources = [
            {
                'name': '东方财富',
                'base_url': 'https://searchapi.eastmoney.com',
                'search_url': 'https://searchapi.eastmoney.com/bussiness/Web/GetCMSSearchList'
            },
            {
                'name': '新浪财经',
                'base_url': 'https://finance.sina.com.cn',
                'search_url': 'https://feed.mix.sina.com.cn/api/roll/get'
            }
        ]
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符
        text = text.strip()
        return text
    
    def _fetch_from_eastmoney(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """从东方财富获取新闻"""
        articles = []
        try:
            params = {
                'keyword': keyword,
                'pageindex': 1,
                'pagesize': limit,
                'type': 'cmsArticleWebOld'
            }
            
            response = requests.get(
                self.sources[0]['search_url'],
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('Data') and data['Data'].get('List'):
                    for item in data['Data']['List']:
                        articles.append({
                            'title': self._clean_text(item.get('ArtTitle', '')),
                            'content': self._clean_text(item.get('ArtSummary', '')),
                            'url': item.get('ArtUrl', ''),
                            'source': '东方财富',
                            'published_at': datetime.fromtimestamp(item.get('ShowTime', 0)) if item.get('ShowTime') else datetime.now()
                        })
        except Exception as e:
            logger.warning(f"Failed to fetch from EastMoney: {e}")
        
        return articles
    
    def _fetch_from_sina(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """从新浪财经获取新闻"""
        articles = []
        try:
            # 新浪财经的API可能需要不同的参数
            # 这里使用简化的方式
            search_url = f"https://feed.mix.sina.com.cn/api/roll/get"
            params = {
                'pageid': '153',
                'lid': '1686',
                'k': keyword,
                'num': limit
            }
            
            response = requests.get(
                search_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('result') and data['result'].get('data'):
                    for item in data['result']['data']:
                        articles.append({
                            'title': self._clean_text(item.get('title', '')),
                            'content': self._clean_text(item.get('intro', '')),
                            'url': item.get('url', ''),
                            'source': '新浪财经',
                            'published_at': datetime.fromtimestamp(int(item.get('ctime', 0))) if item.get('ctime') else datetime.now()
                        })
        except Exception as e:
            logger.warning(f"Failed to fetch from Sina: {e}")
    
    def _fetch_generic_news(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """通用新闻获取（使用百度搜索作为备选）"""
        articles = []
        try:
            # 使用简化的方式，实际项目中可以使用更专业的新闻API
            search_url = "https://www.baidu.com/s"
            params = {
                'wd': f'{keyword} 股票 新闻',
                'rn': limit
            }
            
            response = requests.get(
                search_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 解析搜索结果（简化版）
                # 实际应用中需要更复杂的解析逻辑
                results = soup.find_all('div', class_='result')
                for result in results[:limit]:
                    title_elem = result.find('h3')
                    content_elem = result.find('span', class_='content-right_8Zs40')
                    
                    if title_elem:
                        title = self._clean_text(title_elem.get_text())
                        content = self._clean_text(content_elem.get_text()) if content_elem else ""
                        url = title_elem.find('a').get('href', '') if title_elem.find('a') else ""
                        
                        articles.append({
                            'title': title,
                            'content': content,
                            'url': url,
                            'source': '百度搜索',
                            'published_at': datetime.now()
                        })
        except Exception as e:
            logger.warning(f"Failed to fetch generic news: {e}")
        
        return articles
    
    def fetch_news(self, symbol: str, keyword: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取股票相关新闻
        
        Args:
            symbol: 股票代码
            keyword: 搜索关键词（可选，默认使用股票代码）
            limit: 返回数量限制
        
        Returns:
            新闻列表
        """
        if not keyword:
            keyword = symbol
        
        all_articles = []
        
        # 从多个来源获取
        try:
            articles = self._fetch_from_eastmoney(keyword, limit // 2)
            all_articles.extend(articles)
        except Exception as e:
            logger.warning(f"EastMoney fetch failed: {e}")
        
        try:
            articles = self._fetch_from_sina(keyword, limit // 2)
            all_articles.extend(articles)
        except Exception as e:
            logger.warning(f"Sina fetch failed: {e}")
        
        # 如果结果不足，使用通用方法
        if len(all_articles) < limit:
            try:
                articles = self._fetch_generic_news(keyword, limit - len(all_articles))
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"Generic fetch failed: {e}")
        
        # 去重（基于标题）
        seen_titles = set()
        unique_articles = []
        for article in all_articles:
            if article['title'] and article['title'] not in seen_titles:
                seen_titles.add(article['title'])
                unique_articles.append(article)
        
        return unique_articles[:limit]
    
    def save_news_to_database(self, symbol: str, articles: List[Dict[str, Any]]) -> List[int]:
        """
        保存新闻到数据库和向量数据库
        
        Args:
            symbol: 股票代码
            articles: 新闻列表
        
        Returns:
            保存的新闻ID列表
        """
        saved_ids = []
        
        for article in articles:
            try:
                # 保存到MySQL
                news_id = storage_manager.save_news_data(
                    symbol=symbol,
                    title=article['title'],
                    content=article['content'],
                    source=article['source'],
                    url=article.get('url'),
                    published_at=article['published_at']
                )
                saved_ids.append(news_id)
                
                # 添加到向量数据库
                get_rag_tool().add_documents([{
                    'text': f"{article['title']}\n{article['content']}",
                    'metadata': {
                        'symbol': symbol,
                        'news_id': news_id,
                        'source': article['source'],
                        'url': article.get('url', ''),
                        'published_at': article['published_at'].isoformat()
                    }
                }])
                
            except Exception as e:
                logger.error(f"Failed to save news: {e}")
        
        logger.info(f"Saved {len(saved_ids)} news articles for {symbol}")
        return saved_ids
    
    def search_news(self, symbol: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        从向量数据库搜索相关新闻
        
        Args:
            symbol: 股票代码
            query: 搜索查询
            top_k: 返回数量
        
        Returns:
            相关新闻列表
        """
        results = get_rag_tool().search_by_symbol(symbol, query, top_k=top_k)
        
        # 格式化结果
        news_list = []
        for result in results:
            news_list.append({
                'text': result['text'],
                'metadata': result['metadata'],
                'relevance_score': result['score'],
                'rank': result['rank']
            })
        
        return news_list
    
    def get_news_analysis(self, symbol: str, query: str = None) -> str:
        """
        获取新闻分析摘要
        
        Args:
            symbol: 股票代码
            query: 查询关键词（可选）
        
        Returns:
            新闻分析摘要
        """
        if not query:
            query = f"{symbol} 投资 市场 政策"
        
        # 搜索相关新闻
        news_results = self.search_news(symbol, query, top_k=10)
        
        if not news_results:
            return f"未找到与{symbol}相关的新闻和政策信息。"
        
        # 生成摘要
        analysis = f"## {symbol} 新闻政策分析\n\n"
        analysis += f"共找到 {len(news_results)} 条相关新闻：\n\n"
        
        for i, news in enumerate(news_results[:5], 1):
            analysis += f"### {i}. {news['metadata'].get('source', '未知来源')}\n"
            analysis += f"**标题**: {news['text'][:100]}...\n"
            analysis += f"**相关性**: {news['relevance_score']:.4f}\n"
            analysis += f"**发布时间**: {news['metadata'].get('published_at', '未知')}\n\n"
        
        # 总结
        analysis += "### 分析总结\n"
        analysis += "基于以上新闻和政策信息，建议关注：\n"
        analysis += "- 政策变化对市场的影响\n"
        analysis += "- 行业发展趋势\n"
        analysis += "- 公司重大事件\n"
        analysis += "- 市场情绪变化\n"
        
        return analysis
    
    def update_news_for_symbol(self, symbol: str, limit: int = 20) -> bool:
        """
        更新指定股票的新闻数据
        
        Args:
            symbol: 股票代码
            limit: 获取数量
        
        Returns:
            是否成功
        """
        try:
            # 获取新闻
            articles = self.fetch_news(symbol, limit=limit)
            
            if not articles:
                logger.warning(f"No news found for {symbol}")
                return False
            
            # 保存到数据库
            saved_ids = self.save_news_to_database(symbol, articles)
            
            logger.info(f"Updated {len(saved_ids)} news articles for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to update news for {symbol}: {e}")
            return False


# 全局政策工具实例
policy_tool = PolicyTool()

