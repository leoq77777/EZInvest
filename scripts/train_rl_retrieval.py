"""
RL检索训练脚本 - 实际训练时需要运行此脚本

注意：此脚本需要：
1. 准备大量训练数据（查询-股票代码对）
2. 配置训练超参数
3. 足够的计算资源

使用方法：
    python scripts/train_rl_retrieval.py --episodes 1000 --data_path ./data/training_data.json
"""
import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.rl_retrieval.trainer import RLTrainer
from app.services.rl_retrieval.agent import RLRetrievalAgent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Train RL Retrieval Agent')
    parser.add_argument('--episodes', type=int, default=100, help='Number of training episodes')
    parser.add_argument('--data_path', type=str, default=None, help='Path to training data JSON file')
    parser.add_argument('--model_path', type=str, default='./models/rl_retrieval_agent.pt', help='Path to save model')
    parser.add_argument('--save_interval', type=int, default=10, help='Save model every N episodes')
    parser.add_argument('--use_ray', action='store_true', help='Use Ray for distributed training')
    parser.add_argument('--num_workers', type=int, default=1, help='Number of Ray workers')
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("RL Retrieval Training Script")
    logger.info("="*60)
    logger.info(f"Episodes: {args.episodes}")
    logger.info(f"Model path: {args.model_path}")
    logger.info(f"Use Ray: {args.use_ray}")
    
    # 创建Agent和Trainer
    agent = RLRetrievalAgent()
    trainer = RLTrainer(agent=agent, use_ray=args.use_ray, num_workers=args.num_workers)
    
    # 准备训练数据
    if args.data_path:
        import json
        with open(args.data_path, 'r', encoding='utf-8') as f:
            training_data = json.load(f)
        logger.info(f"Loaded {len(training_data)} training samples from {args.data_path}")
    else:
        training_data = trainer.prepare_training_data()
        logger.info(f"Using default training data: {len(training_data)} samples")
    
    # 训练
    logger.info("Starting training...")
    results = trainer.train(
        num_episodes=args.episodes,
        training_data=training_data,
        save_interval=args.save_interval,
        model_path=args.model_path
    )
    
    logger.info("="*60)
    logger.info("Training Results")
    logger.info("="*60)
    logger.info(f"Episodes: {results['episodes']}")
    logger.info(f"Average Reward: {results['avg_reward']:.4f}")
    logger.info(f"Average Loss: {results['avg_loss']:.4f}")
    logger.info(f"Final Reward: {results['final_reward']:.4f}")
    logger.info(f"Model saved to: {args.model_path}")
    
    # 评估（可选）
    if len(training_data) > 0:
        logger.info("Evaluating agent...")
        eval_results = trainer.evaluate(training_data[:10])  # 评估前10个样本
        logger.info(f"Evaluation - Avg Reward: {eval_results['avg_reward']:.4f}")
        logger.info(f"Tool Distribution: {eval_results['tool_distribution']}")


if __name__ == "__main__":
    main()

