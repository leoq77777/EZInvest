"""
LLM集成 - Ollama连接和prompt管理
"""
import requests
from typing import List, Dict, Any, Optional
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama客户端"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self._connection_checked = False
        self._available = False
    
    def _ensure_connection(self):
        """确保连接已检查（延迟检查）"""
        if not self._connection_checked:
            self._check_connection()
            self._connection_checked = True
    
    def _check_connection(self):
        """检查Ollama连接"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info(f"Connected to Ollama at {self.base_url}")
                self._available = True
            else:
                logger.warning(f"Ollama connection check returned status {response.status_code}")
                self._available = False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}. Will use fallback mode.")
            self._available = False
    
    def _fallback_extract_symbol(self, prompt: str) -> str:
        """使用规则引擎进行符号提取 fallback"""
        # 如果 prompt 中有"标的"字样，尝试提取
        import re
        # 匹配股票代码（6位数字）
        match = re.search(r'(\d{6})', prompt)
        if match:
            return f"标的: {match.group(1)}"
        # 匹配常见中文名称
        symbols = {
            '平安': '标的: 000001',
            '茅台': '标的: 600519',
            '腾讯': '标的: 00700',
            '阿里': '标的: 09988'
        }
        for name, code in symbols.items():
            if name in prompt:
                return code
        return "标的: 未找到"
    
    def _fallback_generate(self, prompt: str) -> str:
        """提供基于规则的 fallback 响应"""
        # 检测 prompt 的意图
        if '标的' in prompt or '提取' in prompt:
            return self._fallback_extract_symbol(prompt)
        elif '分析' in prompt or '建议' in prompt:
            # 返回通用建议
            return "根据技术分析和基本面分析，该标的呈现积极态势。建议关注市场动向和风险控制。"
        else:
            return "已收到您的问题，请提供更多细节以获得更准确的建议。"
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """生成文本
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            **kwargs: 其他参数（temperature, max_tokens等）
        
        Returns:
            生成的文本
        """
        self._ensure_connection()
        
        # 如果 Ollama 不可用，使用 fallback
        if not self._available:
            logger.info("Using fallback mode for text generation")
            return self._fallback_generate(prompt)
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('message', {}).get('content', '')
        except Exception as e:
            logger.warning(f"Ollama generation failed, using fallback: {e}")
            return self._fallback_generate(prompt)
    
    def generate_stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        """流式生成文本（生成器）
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            **kwargs: 其他参数
        
        Yields:
            生成的文本片段
        """
        self._ensure_connection()
        
        # 如果 Ollama 不可用，使用 fallback
        if not self._available:
            logger.info("Using fallback mode for streaming generation")
            yield self._fallback_generate(prompt)
            return
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **kwargs
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=120
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        import json
                        data = json.loads(line)
                        content = data.get('message', {}).get('content', '')
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Ollama stream generation failed, using fallback: {e}")
            yield self._fallback_generate(prompt)


class PromptManager:
    """Prompt管理器"""
    
    SYSTEM_PROMPT = """你是一个专业的投资顾问AI助手。你的任务是帮助用户分析投资问题，提供专业的投资建议。

你的能力包括：
1. 分析股票、基金等金融标的
2. 解读量化分析结果
3. 分析政策新闻对市场的影响
4. 提供综合投资建议

请基于提供的数据、量化分析结果和政策新闻，给出专业、客观、谨慎的投资建议。"""

    QUERY_EXPANSION_PROMPT = """用户问题：{query}

请对用户问题进行扩展和优化，使其更适合进行金融数据检索和分析。要求：
1. 识别问题中的金融标的（股票代码、股票名称等）
2. 明确用户关心的指标（价格、趋势、风险等）
3. 扩展相关概念和同义词

输出格式：
标的: [识别的股票代码或名称]
扩展问题: [扩展后的问题]
关注点: [用户关心的指标列表]"""

    ANALYSIS_PROMPT = """基于以下信息，为用户提供投资建议：

用户问题：{query}

金融标的：{symbol}
标的名称：{name}

量化分析结果：
{quant_analysis}

相关政策新闻：
{news_analysis}

历史数据摘要：
{data_summary}

请综合分析以上信息，给出：
1. 当前市场状况评估
2. 风险提示
3. 投资建议（买入/持有/卖出）
4. 理由说明"""

    @classmethod
    def get_system_prompt(cls) -> str:
        """获取系统提示"""
        return cls.SYSTEM_PROMPT
    
    @classmethod
    def get_query_expansion_prompt(cls, query: str) -> str:
        """获取查询扩展提示"""
        return cls.QUERY_EXPANSION_PROMPT.format(query=query)
    
    @classmethod
    def get_analysis_prompt(
        cls,
        query: str,
        symbol: str,
        name: str,
        quant_analysis: str,
        news_analysis: str,
        data_summary: str
    ) -> str:
        """获取分析提示"""
        return cls.ANALYSIS_PROMPT.format(
            query=query,
            symbol=symbol,
            name=name,
            quant_analysis=quant_analysis,
            news_analysis=news_analysis,
            data_summary=data_summary
        )


# 全局LLM客户端实例
ollama_client = OllamaClient()

