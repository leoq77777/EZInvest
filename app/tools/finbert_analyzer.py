"""
FinBERT金融文本分析器 - 专门用于金融领域的情感分析和文本分类
"""
import logging
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# 延迟加载FinBERT模型
_finbert_model = None
_finbert_tokenizer = None
_finbert_loaded = False


def _get_finbert_model():
    """延迟加载FinBERT模型"""
    global _finbert_model, _finbert_tokenizer, _finbert_loaded
    
    if _finbert_loaded:
        return _finbert_model, _finbert_tokenizer
    
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        
        model_name = "yiyanghkust/finbert-tone"
        logger.info(f"Loading FinBERT model: {model_name}")
        
        _finbert_tokenizer = AutoTokenizer.from_pretrained(model_name)
        _finbert_model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _finbert_model.eval()  # 设置为评估模式
        
        # 如果可用，使用GPU
        if torch.cuda.is_available():
            _finbert_model = _finbert_model.cuda()
            logger.info("FinBERT loaded on GPU")
        else:
            logger.info("FinBERT loaded on CPU")
        
        _finbert_loaded = True
        logger.info("FinBERT model loaded successfully")
        return _finbert_model, _finbert_tokenizer
    except ImportError:
        logger.warning("transformers library not available, FinBERT will not be used")
        return None, None
    except Exception as e:
        logger.error(f"Failed to load FinBERT model: {e}")
        return None, None


class FinBERTAnalyzer:
    """FinBERT金融文本分析器"""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._ensure_model_loaded()
    
    def _ensure_model_loaded(self):
        """确保模型已加载"""
        if self.model is None or self.tokenizer is None:
            self.model, self.tokenizer = _get_finbert_model()
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        分析文本情感
        
        Args:
            text: 待分析文本
        
        Returns:
            情感分析结果，包含：
            - label: 情感标签 (positive/negative/neutral)
            - score: 置信度分数
            - sentiment_score: 数值化情感分数 (-1到1)
        """
        if not self.model or not self.tokenizer:
            # Fallback到简单规则
            return self._fallback_sentiment(text)
        
        try:
            import torch
            
            # 截断文本（FinBERT最大长度512）
            max_length = 512
            if len(text) > max_length:
                text = text[:max_length]
            
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
                padding=True
            )
            
            # 移动到GPU（如果可用）
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # 预测
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # 获取标签和分数
            labels = ["positive", "negative", "neutral"]
            scores = predictions[0].cpu().numpy()
            
            # 找到最高分
            max_idx = scores.argmax()
            label = labels[max_idx]
            score = float(scores[max_idx])
            
            # 计算数值化情感分数 (-1: negative, 0: neutral, 1: positive)
            sentiment_score = float(scores[0] - scores[1])  # positive - negative
            
            return {
                "label": label,
                "score": score,
                "sentiment_score": sentiment_score,
                "probabilities": {
                    "positive": float(scores[0]),
                    "negative": float(scores[1]),
                    "neutral": float(scores[2])
                }
            }
        except Exception as e:
            logger.error(f"FinBERT sentiment analysis failed: {e}")
            return self._fallback_sentiment(text)
    
    def _fallback_sentiment(self, text: str) -> Dict[str, Any]:
        """简单的fallback情感分析"""
        text_lower = text.lower()
        
        positive_words = ['涨', '升', '利好', '增长', '盈利', '收益', '上涨', '突破', '买入', '推荐']
        negative_words = ['跌', '降', '利空', '亏损', '下跌', '风险', '卖出', '警告']
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            label = "positive"
            sentiment_score = min(0.7, positive_count / 10)
        elif negative_count > positive_count:
            label = "negative"
            sentiment_score = -min(0.7, negative_count / 10)
        else:
            label = "neutral"
            sentiment_score = 0.0
        
        return {
            "label": label,
            "score": 0.6,
            "sentiment_score": sentiment_score,
            "probabilities": {
                "positive": 0.33 if label == "positive" else 0.33,
                "negative": 0.33 if label == "negative" else 0.33,
                "neutral": 0.34 if label == "neutral" else 0.33
            }
        }
    
    def analyze_earnings_call(self, transcript: str) -> Dict[str, Any]:
        """
        分析财报电话会议文本
        
        Args:
            transcript: 电话会议文本
        
        Returns:
            分析结果，包含：
            - overall_sentiment: 整体情感
            - key_points: 关键点列表
            - sentiment_by_section: 分段情感分析
        """
        if not transcript:
            return {
                "overall_sentiment": "neutral",
                "sentiment_score": 0.0,
                "key_points": [],
                "sentiment_by_section": []
            }
        
        # 分段分析（按句子或段落）
        sentences = transcript.split('。')[:20]  # 限制分析前20句
        
        sentiments = []
        for sentence in sentences:
            if sentence.strip():
                sentiment = self.analyze_sentiment(sentence.strip())
                sentiments.append({
                    "text": sentence.strip(),
                    "sentiment": sentiment
                })
        
        # 计算整体情感
        if sentiments:
            avg_sentiment_score = sum(s['sentiment']['sentiment_score'] for s in sentiments) / len(sentiments)
            
            if avg_sentiment_score > 0.2:
                overall_sentiment = "positive"
            elif avg_sentiment_score < -0.2:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"
        else:
            overall_sentiment = "neutral"
            avg_sentiment_score = 0.0
        
        # 提取关键点（情感强烈的句子）
        key_points = [
            s for s in sentiments 
            if abs(s['sentiment']['sentiment_score']) > 0.3
        ][:5]  # 最多5个关键点
        
        return {
            "overall_sentiment": overall_sentiment,
            "sentiment_score": avg_sentiment_score,
            "key_points": key_points,
            "sentiment_by_section": sentiments[:10]  # 返回前10段
        }
    
    def batch_analyze(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        批量分析文本情感
        
        Args:
            texts: 文本列表
        
        Returns:
            情感分析结果列表
        """
        return [self.analyze_sentiment(text) for text in texts]


# 全局FinBERT分析器实例
finbert_analyzer = FinBERTAnalyzer()

