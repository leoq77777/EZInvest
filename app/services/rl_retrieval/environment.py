"""
RL检索环境 - 定义状态、动作和奖励
"""
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime
from app.services.data_fetcher import data_fetcher
from app.services.quant_tool import quant_tool
from app.services.policy_tool import policy_tool
from app.tools.rag import get_rag_tool

logger = logging.getLogger(__name__)


class RetrievalEnvironment:
    """
    强化学习检索环境
    
    状态空间:
    - 查询特征（长度、关键词、类型等）
    - 历史工具使用记录
    - 数据质量反馈
    
    动作空间:
    - 选择工具: data_fetcher, quant_tool, policy_tool, rag_tool
    
    奖励函数:
    - 数据相关性（基于检索结果质量）
    - 响应时间（负奖励）
    - 用户满意度（如果有反馈）
    """
    
    # 工具列表
    TOOLS = {
        0: 'data_fetcher',      # 数据获取工具
        1: 'quant_tool',         # 量化分析工具
        2: 'policy_tool',        # 政策分析工具
        3: 'rag_tool',           # RAG检索工具
        4: 'none'                # 不选择任何工具
    }
    
    TOOL_NAMES = {v: k for k, v in TOOLS.items()}
    
    def __init__(self, max_steps: int = 5):
        """
        初始化环境
        
        Args:
            max_steps: 最大步骤数
        """
        self.max_steps = max_steps
        self.current_step = 0
        self.query = None
        self.symbol = None
        self.state_history = []
        self.action_history = []
        self.reward_history = []
        self.tool_results = {}
        self.reset()
    
    def reset(self, query: Optional[str] = None, symbol: Optional[str] = None) -> np.ndarray:
        """
        重置环境
        
        Args:
            query: 用户查询
            symbol: 股票代码（可选）
        
        Returns:
            初始状态向量
        """
        self.current_step = 0
        self.query = query or ""
        self.symbol = symbol
        self.state_history = []
        self.action_history = []
        self.reward_history = []
        self.tool_results = {}
        
        return self._get_state()
    
    def _get_state(self) -> np.ndarray:
        """
        获取当前状态向量
        
        Returns:
            状态向量（归一化到0-1）
        """
        state_features = []
        
        # 1. 查询特征（5维）
        if self.query:
            query_len = len(self.query)
            state_features.extend([
                min(query_len / 100, 1.0),  # 查询长度（归一化）
                1.0 if any(kw in self.query for kw in ['价格', 'price', '涨', '跌']) else 0.0,  # 价格相关
                1.0 if any(kw in self.query for kw in ['分析', 'analysis', '指标']) else 0.0,  # 分析相关
                1.0 if any(kw in self.query for kw in ['新闻', 'news', '政策']) else 0.0,  # 新闻相关
                1.0 if self.symbol else 0.0  # 是否有股票代码
            ])
        else:
            state_features.extend([0.0] * 5)
        
        # 2. 历史工具使用（4维，每个工具的使用次数）
        tool_usage = [0.0] * 4
        for action in self.action_history:
            if action < 4:  # 排除'none'
                tool_usage[action] += 1.0
        # 归一化
        max_usage = max(tool_usage) if max(tool_usage) > 0 else 1.0
        tool_usage = [u / max_usage for u in tool_usage]
        state_features.extend(tool_usage)
        
        # 3. 数据质量反馈（4维，每个工具的结果质量）
        quality_scores = []
        for tool_idx in range(4):
            tool_name = self.TOOLS[tool_idx]
            if tool_name in self.tool_results:
                # 简单质量评分：基于结果是否为空
                result = self.tool_results[tool_name]
                quality = 1.0 if result and len(str(result)) > 10 else 0.0
                quality_scores.append(quality)
            else:
                quality_scores.append(0.0)
        state_features.extend(quality_scores)
        
        # 4. 步骤信息（2维）
        state_features.extend([
            self.current_step / self.max_steps,  # 当前步骤比例
            1.0 if self.current_step >= self.max_steps - 1 else 0.0  # 是否接近结束
        ])
        
        # 总共15维状态向量
        state_vector = np.array(state_features, dtype=np.float32)
        
        # 确保维度正确
        if len(state_vector) < 15:
            state_vector = np.pad(state_vector, (0, 15 - len(state_vector)), 'constant')
        elif len(state_vector) > 15:
            state_vector = state_vector[:15]
        
        return state_vector
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        执行动作
        
        Args:
            action: 动作索引（0-4）
        
        Returns:
            (next_state, reward, done, info)
        """
        if action not in self.TOOLS:
            action = 4  # 默认none
        
        tool_name = self.TOOLS[action]
        self.action_history.append(action)
        
        # 执行工具
        result = None
        execution_time = 0.0
        error = None
        
        try:
            import time
            start_time = time.time()
            
            if tool_name == 'data_fetcher' and self.symbol:
                result = data_fetcher.get_stock_info(self.symbol)
            elif tool_name == 'quant_tool' and self.symbol:
                result = quant_tool.generate_analysis_report(self.symbol)
            elif tool_name == 'policy_tool' and self.symbol:
                result = policy_tool.get_news_analysis(self.symbol, self.query)
            elif tool_name == 'rag_tool' and self.query:
                results = get_rag_tool().search(self.query, top_k=3)
                result = results if results else None
            else:
                result = None
            
            execution_time = time.time() - start_time
            
        except Exception as e:
            error = str(e)
            logger.warning(f"Tool {tool_name} execution failed: {e}")
            result = None
        
        # 保存结果
        self.tool_results[tool_name] = result
        
        # 计算奖励
        reward = self._calculate_reward(action, result, execution_time, error)
        
        # 更新步骤
        self.current_step += 1
        done = self.current_step >= self.max_steps
        
        # 获取下一个状态
        next_state = self._get_state()
        
        # 保存历史
        self.state_history.append(next_state)
        self.reward_history.append(reward)
        
        info = {
            'tool': tool_name,
            'result': result,
            'execution_time': execution_time,
            'error': error,
            'step': self.current_step
        }
        
        return next_state, reward, done, info
    
    def _calculate_reward(self, action: int, result: Any, execution_time: float, error: Optional[str]) -> float:
        """
        计算奖励
        
        Args:
            action: 动作
            result: 工具执行结果
            execution_time: 执行时间
            error: 错误信息
        
        Returns:
            奖励值
        """
        reward = 0.0
        
        # 1. 基础奖励：如果选择了none，小负奖励
        if action == 4:  # none
            reward -= 0.1
            return reward
        
        # 2. 错误惩罚
        if error:
            reward -= 1.0
            return reward
        
        # 3. 结果质量奖励
        if result:
            # 根据结果类型和质量评分
            if isinstance(result, dict):
                # 字典结果：检查是否有有效数据
                if len(result) > 0:
                    reward += 0.5
                if 'error' not in result:
                    reward += 0.3
            elif isinstance(result, list):
                # 列表结果：检查长度
                if len(result) > 0:
                    reward += 0.5
                    reward += min(len(result) / 10.0, 0.3)  # 更多结果更好
            elif isinstance(result, str):
                # 字符串结果：检查长度
                if len(result) > 50:
                    reward += 0.5
                    reward += min(len(result) / 500.0, 0.3)  # 更长内容更好
            else:
                reward += 0.2  # 有结果但类型未知
        else:
            # 无结果：小负奖励
            reward -= 0.3
        
        # 4. 时间惩罚（执行时间越长，奖励越少）
        time_penalty = min(execution_time / 5.0, 0.2)  # 最多惩罚0.2
        reward -= time_penalty
        
        # 5. 工具选择合理性奖励（基于查询类型）
        if self.query:
            query_lower = self.query.lower()
            tool_name = self.TOOLS[action]
            
            # 价格相关查询 -> data_fetcher
            if any(kw in query_lower for kw in ['价格', 'price', '涨', '跌', '行情']):
                if tool_name == 'data_fetcher':
                    reward += 0.2
            
            # 分析相关查询 -> quant_tool
            if any(kw in query_lower for kw in ['分析', 'analysis', '指标', '技术']):
                if tool_name == 'quant_tool':
                    reward += 0.2
            
            # 新闻相关查询 -> policy_tool
            if any(kw in query_lower for kw in ['新闻', 'news', '政策', '消息']):
                if tool_name == 'policy_tool':
                    reward += 0.2
            
            # 一般查询 -> rag_tool
            if tool_name == 'rag_tool' and not any([
                '价格' in query_lower, '分析' in query_lower, '新闻' in query_lower
            ]):
                reward += 0.1
        
        # 归一化奖励到[-1, 1]
        reward = max(-1.0, min(1.0, reward))
        
        return reward
    
    def get_available_tools(self) -> List[int]:
        """
        获取可用工具列表（基于当前状态）
        
        Returns:
            可用工具索引列表
        """
        available = []
        
        # 如果有股票代码，data_fetcher和quant_tool可用
        if self.symbol:
            available.extend([0, 1, 2])  # data_fetcher, quant_tool, policy_tool
        
        # 如果有查询，rag_tool可用
        if self.query:
            available.append(3)  # rag_tool
        
        # none总是可用
        available.append(4)
        
        return list(set(available)) if available else [4]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取环境摘要
        
        Returns:
            环境摘要信息
        """
        return {
            'query': self.query,
            'symbol': self.symbol,
            'steps': self.current_step,
            'actions_taken': len(self.action_history),
            'total_reward': sum(self.reward_history),
            'tools_used': [self.TOOLS[a] for a in self.action_history],
            'results_count': len(self.tool_results)
        }

