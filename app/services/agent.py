"""
Agent核心逻辑 - 工作流编排和工具调用
"""
import re
import logging
from typing import Dict, Any, Optional, List
from app.tools.llm import ollama_client, PromptManager
from app.services.data_fetcher import data_fetcher
from app.services.quant_tool import quant_tool
from app.services.policy_tool import policy_tool
from app.database.storage import storage_manager

logger = logging.getLogger(__name__)


class InvestmentAgent:
    """投资助手Agent"""
    
    def __init__(self):
        self.prompt_manager = PromptManager()
    
    def _extract_symbol(self, query: str, expanded_query: str = None) -> Optional[str]:
        """
        从查询中提取股票代码或名称
        
        Args:
            query: 原始查询
            expanded_query: 扩展后的查询（可选）
        
        Returns:
            股票代码或None
        """
        # 使用LLM提取标的
        extraction_prompt = f"""从以下用户问题中提取股票代码或股票名称。

用户问题：{query}

请只返回股票代码（如：000001）或股票名称（如：平安银行），如果没有找到，返回"未找到"。

输出格式：
标的: [股票代码或名称]"""
        
        try:
            response = ollama_client.generate(
                extraction_prompt,
                system_prompt="你是一个专业的金融信息提取助手。",
                temperature=0.1
            )
            
            # 解析响应
            match = re.search(r'标的[：:]\s*([^\n]+)', response)
            if match:
                symbol = match.group(1).strip()
                if symbol and symbol != "未找到":
                    return symbol
        except Exception as e:
            logger.warning(f"Failed to extract symbol using LLM: {e}")
        
        # 备选方案：使用正则表达式匹配
        # 匹配股票代码（6位数字）
        code_match = re.search(r'\b(\d{6})\b', query)
        if code_match:
            return code_match.group(1)
        
        # 匹配常见股票名称关键词
        common_stocks = {
            'apple': 'AAPL',
            '苹果': 'AAPL',
            '腾讯': '00700',
            '阿里巴巴': '09988',
            '平安': '000001',
            '茅台': '600519',
        }
        
        query_lower = query.lower()
        for keyword, code in common_stocks.items():
            if keyword in query_lower:
                return code
        
        return None
    
    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        try:
            info = data_fetcher.get_stock_info(symbol)
            if info:
                return info.get('name', symbol)
        except Exception as e:
            logger.warning(f"Failed to get stock name for {symbol}: {e}")
        return symbol
    
    def _expand_query(self, query: str) -> Dict[str, Any]:
        """扩展用户查询"""
        try:
            prompt = self.prompt_manager.get_query_expansion_prompt(query)
            response = ollama_client.generate(
                prompt,
                system_prompt=self.prompt_manager.get_system_prompt(),
                temperature=0.3
            )
            
            # 解析响应
            result = {
                'original_query': query,
                'expanded_query': query,
                'symbol': None,
                'focus_points': []
            }
            
            # 提取标的
            symbol_match = re.search(r'标的[：:]\s*([^\n]+)', response)
            if symbol_match:
                result['symbol'] = symbol_match.group(1).strip()
            
            # 提取扩展问题
            expanded_match = re.search(r'扩展问题[：:]\s*([^\n]+)', response)
            if expanded_match:
                result['expanded_query'] = expanded_match.group(1).strip()
            
            # 提取关注点
            focus_match = re.search(r'关注点[：:]\s*([^\n]+)', response)
            if focus_match:
                result['focus_points'] = [p.strip() for p in focus_match.group(1).split(',')]
            
            return result
        except Exception as e:
            logger.warning(f"Failed to expand query: {e}")
            return {
                'original_query': query,
                'expanded_query': query,
                'symbol': None,
                'focus_points': []
            }
    
    def _get_data_summary(self, symbol: str) -> str:
        """获取数据摘要"""
        try:
            # 获取实时数据
            realtime = data_fetcher.get_stock_realtime(symbol)
            if not realtime:
                return "无法获取实时数据"
            
            summary = f"实时价格: {realtime.get('current_price', 'N/A')}\n"
            summary += f"涨跌幅: {realtime.get('change_percent', 'N/A')}%\n"
            summary += f"成交量: {realtime.get('volume', 'N/A')}\n"
            
            # 获取最近几天的数据趋势
            from datetime import datetime, timedelta
            from app.database.mysql_client import SessionLocal, FinancialData
            import json
            
            db = SessionLocal()
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)
                
                results = db.query(FinancialData).filter(
                    FinancialData.symbol == symbol,
                    FinancialData.data_type == "daily",
                    FinancialData.date >= start_date,
                    FinancialData.date <= end_date
                ).order_by(FinancialData.date.desc()).limit(5).all()
                
                if results:
                    summary += "\n最近5天价格趋势:\n"
                    for result in results:
                        data = json.loads(result.data)
                        summary += f"{result.date.strftime('%Y-%m-%d')}: {data.get('close', 'N/A')}\n"
            finally:
                db.close()
            
            return summary
        except Exception as e:
            logger.error(f"Failed to get data summary: {e}")
            return "数据获取失败"
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        处理用户查询 - 端到端工作流
        
        Args:
            query: 用户查询
        
        Returns:
            处理结果，包含分析报告和建议
        """
        logger.info(f"Processing query: {query}")
        
        try:
            # 步骤1: 扩展查询并识别标的
            expanded = self._expand_query(query)
            symbol = expanded.get('symbol')
            
            # 如果LLM未识别，尝试直接提取
            if not symbol:
                symbol = self._extract_symbol(query)
            
            if not symbol:
                return {
                    'success': False,
                    'error': '无法识别问题中的股票代码或名称，请提供更明确的信息。',
                    'query': query
                }
            
            logger.info(f"Identified symbol: {symbol}")
            
            # 步骤2: 获取股票基本信息
            stock_info = data_fetcher.get_stock_info(symbol)
            if not stock_info:
                # 如果实时获取失败，尝试从数据库获取
                stock_name = symbol
            else:
                stock_name = stock_info.get('name', symbol)
            
            # 步骤3: 确保数据存在（如果不存在则获取）
            try:
                from datetime import datetime
                # 检查是否有最新数据
                latest_data = storage_manager.get_financial_data(
                    symbol, "daily", datetime.now()
                )
                if not latest_data:
                    # 获取并保存数据
                    logger.info(f"Fetching data for {symbol}")
                    data_fetcher.fetch_and_save_stock_data(symbol)
            except Exception as e:
                logger.warning(f"Data check/fetch failed: {e}")
            
            # 步骤4: 量化分析
            logger.info(f"Running quant analysis for {symbol}")
            quant_analysis = quant_tool.generate_analysis_report(symbol)
            
            # 步骤5: 政策新闻分析
            logger.info(f"Running policy analysis for {symbol}")
            news_query = expanded.get('expanded_query', query)
            news_analysis = policy_tool.get_news_analysis(symbol, news_query)
            
            # 步骤6: 获取数据摘要
            data_summary = self._get_data_summary(symbol)
            
            # 步骤7: 生成综合投资建议
            logger.info(f"Generating investment advice for {symbol}")
            analysis_prompt = self.prompt_manager.get_analysis_prompt(
                query=query,
                symbol=symbol,
                name=stock_name,
                quant_analysis=quant_analysis,
                news_analysis=news_analysis,
                data_summary=data_summary
            )
            
            advice = ollama_client.generate(
                analysis_prompt,
                system_prompt=self.prompt_manager.get_system_prompt(),
                temperature=0.7
            )
            
            # 步骤8: 构建响应
            result = {
                'success': True,
                'query': query,
                'symbol': symbol,
                'name': stock_name,
                'stock_info': stock_info,
                'quant_analysis': quant_analysis,
                'news_analysis': news_analysis,
                'data_summary': data_summary,
                'advice': advice,
                'expanded_query': expanded.get('expanded_query', query)
            }
            
            logger.info(f"Successfully processed query for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'处理查询时发生错误: {str(e)}',
                'query': query
            }
    
    def process_query_stream(self, query: str):
        """
        流式处理用户查询（生成器）
        
        Args:
            query: 用户查询
        
        Yields:
            处理结果片段
        """
        # 先进行非流式处理获取所有数据
        result = self.process_query(query)
        
        if not result.get('success'):
            yield f"错误: {result.get('error', '未知错误')}\n"
            return
        
        # 流式生成最终建议
        symbol = result['symbol']
        name = result['name']
        quant_analysis = result['quant_analysis']
        news_analysis = result['news_analysis']
        data_summary = result['data_summary']
        
        analysis_prompt = self.prompt_manager.get_analysis_prompt(
            query=query,
            symbol=symbol,
            name=name,
            quant_analysis=quant_analysis,
            news_analysis=news_analysis,
            data_summary=data_summary
        )
        
        # 先输出分析结果
        yield f"## {name} ({symbol}) 投资分析\n\n"
        yield f"### 量化分析\n{quant_analysis}\n\n"
        yield f"### 新闻政策分析\n{news_analysis}\n\n"
        yield f"### 综合投资建议\n\n"
        
        # 流式生成建议
        for chunk in ollama_client.generate_stream(
            analysis_prompt,
            system_prompt=self.prompt_manager.get_system_prompt(),
            temperature=0.7
        ):
            yield chunk


# 全局Agent实例
investment_agent = InvestmentAgent()

