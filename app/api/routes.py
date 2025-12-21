"""
API路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from typing import Optional
from app.services.agent import investment_agent
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str
    stream: bool = False
    
    @validator('query')
    def validate_query(cls, v):
        """验证查询字符串"""
        if not v or not v.strip():
            raise ValueError('查询不能为空')
        if len(v) > 1000:
            raise ValueError('查询长度不能超过1000字符')
        return v.strip()


class QueryResponse(BaseModel):
    """查询响应模型"""
    success: bool
    query: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    advice: Optional[str] = None
    quant_analysis: Optional[str] = None
    news_analysis: Optional[str] = None
    error: Optional[str] = None


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    处理投资查询
    
    Args:
        request: 查询请求
    
    Returns:
        查询响应
    """
    try:
        result = investment_agent.process_query(request.query)
        
        if result.get('success'):
            return QueryResponse(
                success=True,
                query=result['query'],
                symbol=result.get('symbol'),
                name=result.get('name'),
                advice=result.get('advice'),
                quant_analysis=result.get('quant_analysis'),
                news_analysis=result.get('news_analysis')
            )
        else:
            return QueryResponse(
                success=False,
                query=result.get('query', request.query),
                error=result.get('error', '未知错误')
            )
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/query/stream")
async def query_stream(request: QueryRequest):
    """
    流式处理投资查询
    
    Args:
        request: 查询请求
    
    Yields:
        响应文本片段
    """
    from fastapi.responses import StreamingResponse
    
    def generate():
        try:
            for chunk in investment_agent.process_query_stream(request.query):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: 错误: {str(e)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}

