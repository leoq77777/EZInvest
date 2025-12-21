"""
RL检索Agent - 使用神经网络策略选择工具
"""
import numpy as np
from typing import Dict, Any, Optional, List
import logging
import torch
import torch.nn as nn
import torch.optim as optim

logger = logging.getLogger(__name__)


class PolicyNetwork(nn.Module):
    """策略网络 - 输入状态，输出动作概率"""
    
    def __init__(self, state_dim: int = 15, action_dim: int = 5, hidden_dim: int = 64):
        """
        初始化策略网络
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            hidden_dim: 隐藏层维度
        """
        super(PolicyNetwork, self).__init__()
        
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, action_dim)
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax(dim=-1)
        
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        Args:
            state: 状态张量 [batch_size, state_dim]
        
        Returns:
            动作概率分布 [batch_size, action_dim]
        """
        x = self.relu(self.fc1(state))
        x = self.relu(self.fc2(x))
        x = self.softmax(self.fc3(x))
        return x


class RLRetrievalAgent:
    """
    RL检索Agent - 使用策略梯度方法学习工具选择策略
    """
    
    def __init__(
        self,
        state_dim: int = 15,
        action_dim: int = 5,
        hidden_dim: int = 64,
        learning_rate: float = 0.001,
        device: Optional[str] = None
    ):
        """
        初始化Agent
        
        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            hidden_dim: 隐藏层维度
            learning_rate: 学习率
            device: 设备（'cuda'或'cpu'）
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # 设置设备
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        # 创建策略网络
        self.policy_net = PolicyNetwork(state_dim, action_dim, hidden_dim).to(self.device)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        
        # 训练历史
        self.training_history = {
            'episodes': [],
            'rewards': [],
            'losses': []
        }
        
        logger.info(f"RLRetrievalAgent initialized on {self.device}")
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """
        选择动作
        
        Args:
            state: 状态向量
            training: 是否在训练模式（影响探索策略）
        
        Returns:
            动作索引
        """
        # 转换为张量
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        # 获取动作概率
        with torch.no_grad():
            action_probs = self.policy_net(state_tensor)
        
        # 选择动作
        if training:
            # 训练模式：使用概率采样（探索）
            action = torch.multinomial(action_probs, 1).item()
        else:
            # 测试模式：选择概率最高的动作（利用）
            action = torch.argmax(action_probs, dim=1).item()
        
        return action
    
    def update_policy(
        self,
        states: List[np.ndarray],
        actions: List[int],
        rewards: List[float],
        gamma: float = 0.99
    ) -> float:
        """
        更新策略（REINFORCE算法）
        
        Args:
            states: 状态序列
            actions: 动作序列
            rewards: 奖励序列
            gamma: 折扣因子
        
        Returns:
            损失值
        """
        if len(states) == 0:
            return 0.0
        
        # 计算折扣奖励
        discounted_rewards = []
        G = 0
        for reward in reversed(rewards):
            G = reward + gamma * G
            discounted_rewards.insert(0, G)
        
        # 归一化奖励
        discounted_rewards = np.array(discounted_rewards)
        discounted_rewards = (discounted_rewards - discounted_rewards.mean()) / (discounted_rewards.std() + 1e-8)
        
        # 转换为张量
        states_tensor = torch.FloatTensor(np.array(states)).to(self.device)
        actions_tensor = torch.LongTensor(actions).to(self.device)
        rewards_tensor = torch.FloatTensor(discounted_rewards).to(self.device)
        
        # 前向传播
        action_probs = self.policy_net(states_tensor)
        
        # 计算对数概率
        log_probs = torch.log(action_probs.gather(1, actions_tensor.unsqueeze(1)).squeeze(1))
        
        # 计算损失（负的加权对数概率）
        loss = -(log_probs * rewards_tensor).mean()
        
        # 反向传播
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item()
    
    def save(self, filepath: str):
        """
        保存模型
        
        Args:
            filepath: 保存路径
        """
        torch.save({
            'policy_net_state_dict': self.policy_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'training_history': self.training_history
        }, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load(self, filepath: str):
        """
        加载模型
        
        Args:
            filepath: 加载路径
        """
        checkpoint = torch.load(filepath, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.training_history = checkpoint.get('training_history', {
            'episodes': [],
            'rewards': [],
            'losses': []
        })
        logger.info(f"Model loaded from {filepath}")
    
    def get_training_stats(self) -> Dict[str, Any]:
        """
        获取训练统计信息
        
        Returns:
            训练统计信息
        """
        if not self.training_history['episodes']:
            return {
                'total_episodes': 0,
                'avg_reward': 0.0,
                'avg_loss': 0.0
            }
        
        return {
            'total_episodes': len(self.training_history['episodes']),
            'avg_reward': np.mean(self.training_history['rewards']) if self.training_history['rewards'] else 0.0,
            'avg_loss': np.mean(self.training_history['losses']) if self.training_history['losses'] else 0.0,
            'last_reward': self.training_history['rewards'][-1] if self.training_history['rewards'] else 0.0,
            'last_loss': self.training_history['losses'][-1] if self.training_history['losses'] else 0.0
        }

