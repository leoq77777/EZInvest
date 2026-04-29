import json
import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage
from app.agent.llm import get_llm
from app.agent.tools.market_data import market_data_tool
from app.agent.tools.web_scraper import web_scraper_tool
from app.agent.tools.retriever import retriever_tool
from app.agent.tools.calculator import financial_calculator_tool
from app.agent.tools.sentiment import sentiment_analyzer_tool
from app.agent.prompts import SYSTEM_PROMPT, REASONER_PROMPT, SUMMARIZE_PROMPT

logger = logging.getLogger(__name__)

# Tool mapping for easier execution
TOOLS = {
    "market_data": market_data_tool,
    "web_scraper": web_scraper_tool,
    "retriever": retriever_tool,
    "calculator": financial_calculator_tool,
    "sentiment_analyzer": sentiment_analyzer_tool,
}

async def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """Execute a tool by name with arguments."""
    if name not in TOOLS:
        return f"Error: Tool '{name}' not found."
    
    tool_func = TOOLS[name]
    try:
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**args)
        else:
            # Run sync tools in a thread pool to avoid blocking
            return await asyncio.to_thread(tool_func, **args)
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return f"Error executing tool: {str(e)}"

async def run_agent_stream(
    message: str, session_id: str
) -> AsyncGenerator[dict, None]:
    """Stream SSE events through a Cyclic ReAct (Reasoning & Acting) loop."""
    llm = get_llm()
    observations = []
    max_iterations = 8
    
    # ── Phase 0: Initial Thought ──────────────────────────────────────────
    yield {
        "type": "thought",
        "data": {"content": "正在启动投研智能体，准备进行多轮深度分析..."}
    }

    for i in range(max_iterations):
        # ── Phase 1: Reasoning ─────────────────────────────────────────────
        obs_summary = json.dumps(observations, ensure_ascii=False)
        reasoning_prompt = REASONER_PROMPT.format(
            query=message, 
            observations=obs_summary
        )
        
        logger.info(f"Iteration {i+1}: Reasoning...")
        
        try:
            response = await llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=reasoning_prompt),
            ])
            
            # Remove potential markdown fences
            content = response.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
        except Exception as e:
            logger.error(f"Reasoning parse error: {e}. Content: {response.content}")
            yield {
                "type": "thought",
                "data": {"content": "推理过程解析异常，正在尝试自我修正..."}
            }
            # Fallback to simple summary if reasoning fails
            data = {"type": "finish", "thought": "Something went wrong in reasoning, finalizing now."}

        # Handle Clarification
        if data.get("type") == "clarification":
            yield {
                "type": "token",
                "data": {"content": f"⚠️ **需进一步确认**：\n\n{data.get('message')}"}
            }
            return

        # Handle Finish
        if data.get("type") == "finish":
            yield {
                "type": "thought",
                "data": {"content": "所有调研已完成，正在为您生成最终投研报告..."}
            }
            
            final_prompt = SUMMARIZE_PROMPT.format(
                query=message,
                step_results=obs_summary
            )
            
            summary_response = await llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=final_prompt),
            ])
            
            # Stream the summary as tokens
            yield {
                "type": "token",
                "data": {"content": summary_response.content}
            }
            return

        # Handle Action
        if data.get("type") == "action":
            tool_name = data.get("tool")
            tool_args = data.get("tool_args", {})
            thought = data.get("thought", "执行下一步调研...")
            
            yield {
                "type": "thought",
                "data": {"content": f"第 {i+1} 步：{thought}"}
            }
            
            # Emit a mock plan update for the UI to show current progress
            yield {
                "type": "thought", 
                "data": {"content": f"正在使用 {tool_name} 获取数据..."}
            }
            
            result = await execute_tool(tool_name, tool_args)
            observations.append({
                "step": i + 1,
                "tool": tool_name,
                "thought": thought,
                "observation": result
            })
            
            # Optionally yield a small update
            logger.info(f"Iteration {i+1}: Action {tool_name} completed.")

    # Final Fallback if max iterations reached
    yield {
        "type": "token",
        "data": {"content": "由于调研步骤较多，已达到最大循环次数。以上是目前搜集到的核心信息。"}
    }

async def run_agent(message: str, session_id: str) -> dict:
    """Sync wrapper for run_agent_stream."""
    full_content = ""
    async for event in run_agent_stream(message, session_id):
        if event["type"] == "token":
            full_content += event["data"]["content"]
    return {"content": full_content}
