"""
量化分析工具 - 金融技术指标和强化学习
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta
from app.database.storage import storage_manager
from app.database.mysql_client import SessionLocal, FinancialData
import json

logger = logging.getLogger(__name__)

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib not available, some technical indicators will be unavailable")


class QuantTool:
    """量化分析工具"""
    
    def __init__(self):
        self.talib_available = TALIB_AVAILABLE
    
    def _get_stock_dataframe(self, symbol: str, days: int = 100) -> Optional[pd.DataFrame]:
        """从数据库获取股票数据并转换为DataFrame"""
        db = SessionLocal()
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            results = db.query(FinancialData).filter(
                FinancialData.symbol == symbol,
                FinancialData.data_type == "daily",
                FinancialData.date >= start_date,
                FinancialData.date <= end_date
            ).order_by(FinancialData.date).all()
            
            if not results:
                return None
            
            data_list = []
            for result in results:
                data = json.loads(result.data)
                data['date'] = result.date
                data_list.append(data)
            
            df = pd.DataFrame(data_list)
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            
            return df
        finally:
            db.close()
    
    def calculate_technical_indicators(self, symbol: str) -> Dict[str, Any]:
        """计算技术指标"""
        df = self._get_stock_dataframe(symbol)
        if df is None or df.empty:
            return {"error": "No data available"}
        
        # 确保有必要的列
        if 'close' not in df.columns or 'volume' not in df.columns:
            return {"error": "Missing required data columns"}
        
        results = {}
        
        # 基础统计
        results['basic_stats'] = {
            'current_price': float(df['close'].iloc[-1]),
            'price_change': float(df['close'].iloc[-1] - df['close'].iloc[0]),
            'price_change_percent': float((df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100),
            'max_price': float(df['close'].max()),
            'min_price': float(df['close'].min()),
            'avg_price': float(df['close'].mean()),
            'volatility': float(df['close'].std()),
        }
        
        # 移动平均线
        results['moving_averages'] = {
            'ma5': float(df['close'].rolling(5).mean().iloc[-1]) if len(df) >= 5 else None,
            'ma10': float(df['close'].rolling(10).mean().iloc[-1]) if len(df) >= 10 else None,
            'ma20': float(df['close'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else None,
            'ma60': float(df['close'].rolling(60).mean().iloc[-1]) if len(df) >= 60 else None,
        }
        
        # RSI (相对强弱指标)
        if self.talib_available and len(df) >= 14:
            try:
                rsi = talib.RSI(df['close'].values, timeperiod=14)
                results['rsi'] = {
                    'current': float(rsi[-1]),
                    'signal': 'overbought' if rsi[-1] > 70 else 'oversold' if rsi[-1] < 30 else 'neutral'
                }
            except:
                results['rsi'] = self._calculate_rsi_manual(df['close'])
        else:
            results['rsi'] = self._calculate_rsi_manual(df['close'])
        
        # MACD
        if self.talib_available and len(df) >= 26:
            try:
                macd, signal, hist = talib.MACD(df['close'].values)
                results['macd'] = {
                    'macd': float(macd[-1]),
                    'signal': float(signal[-1]),
                    'histogram': float(hist[-1]),
                    'trend': 'bullish' if hist[-1] > 0 else 'bearish'
                }
            except:
                results['macd'] = self._calculate_macd_manual(df['close'])
        else:
            results['macd'] = self._calculate_macd_manual(df['close'])
        
        # 布林带
        if len(df) >= 20:
            results['bollinger_bands'] = self._calculate_bollinger_bands(df['close'])
        
        # 成交量分析
        if 'volume' in df.columns:
            results['volume_analysis'] = {
                'avg_volume': float(df['volume'].mean()),
                'current_volume': float(df['volume'].iloc[-1]),
                'volume_ratio': float(df['volume'].iloc[-1] / df['volume'].mean()) if df['volume'].mean() > 0 else 0
            }
        
        # 趋势分析
        results['trend'] = self._analyze_trend(df)
        
        return results
    
    def _calculate_rsi_manual(self, prices: pd.Series, period: int = 14) -> Dict[str, Any]:
        """手动计算RSI"""
        if len(prices) < period + 1:
            return {'current': None, 'signal': 'insufficient_data'}
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
        
        if current_rsi is None:
            signal = 'insufficient_data'
        elif current_rsi > 70:
            signal = 'overbought'
        elif current_rsi < 30:
            signal = 'oversold'
        else:
            signal = 'neutral'
        
        return {'current': current_rsi, 'signal': signal}
    
    def _calculate_macd_manual(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Any]:
        """手动计算MACD"""
        if len(prices) < slow:
            return {'macd': None, 'signal': None, 'histogram': None, 'trend': 'insufficient_data'}
        
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None,
            'signal': float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else None,
            'histogram': float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None,
            'trend': 'bullish' if histogram.iloc[-1] > 0 else 'bearish' if not pd.isna(histogram.iloc[-1]) else 'insufficient_data'
        }
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, Any]:
        """计算布林带"""
        if len(prices) < period:
            return {'upper': None, 'middle': None, 'lower': None, 'position': 'insufficient_data'}
        
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        current_price = prices.iloc[-1]
        upper_band = upper.iloc[-1]
        lower_band = lower.iloc[-1]
        
        if pd.isna(upper_band) or pd.isna(lower_band):
            position = 'insufficient_data'
        elif current_price > upper_band:
            position = 'above_upper'
        elif current_price < lower_band:
            position = 'below_lower'
        else:
            position = 'within_bands'
        
        return {
            'upper': float(upper_band) if not pd.isna(upper_band) else None,
            'middle': float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None,
            'lower': float(lower_band) if not pd.isna(lower_band) else None,
            'position': position
        }
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析趋势"""
        if len(df) < 20:
            return {'direction': 'insufficient_data', 'strength': None}
        
        prices = df['close']
        
        # 计算短期和长期均线
        short_ma = prices.rolling(5).mean()
        long_ma = prices.rolling(20).mean()
        
        # 判断趋势方向
        if short_ma.iloc[-1] > long_ma.iloc[-1]:
            direction = 'uptrend'
        elif short_ma.iloc[-1] < long_ma.iloc[-1]:
            direction = 'downtrend'
        else:
            direction = 'sideways'
        
        # 计算趋势强度（基于价格变化率）
        price_change = (prices.iloc[-1] - prices.iloc[-20]) / prices.iloc[-20] * 100
        strength = abs(price_change)
        
        return {
            'direction': direction,
            'strength': float(strength),
            'short_ma': float(short_ma.iloc[-1]) if not pd.isna(short_ma.iloc[-1]) else None,
            'long_ma': float(long_ma.iloc[-1]) if not pd.isna(long_ma.iloc[-1]) else None
        }
    
    def generate_analysis_report(self, symbol: str) -> str:
        """生成量化分析报告"""
        indicators = self.calculate_technical_indicators(symbol)
        
        if 'error' in indicators:
            return f"无法获取{symbol}的数据进行分析。"
        
        report = f"## {symbol} 量化分析报告\n\n"
        
        # 基础统计
        if 'basic_stats' in indicators:
            stats = indicators['basic_stats']
            report += f"### 基础统计\n"
            report += f"- 当前价格: {stats['current_price']:.2f}\n"
            report += f"- 价格变化: {stats['price_change']:.2f} ({stats['price_change_percent']:.2f}%)\n"
            report += f"- 最高价: {stats['max_price']:.2f}\n"
            report += f"- 最低价: {stats['min_price']:.2f}\n"
            report += f"- 平均价格: {stats['avg_price']:.2f}\n"
            report += f"- 波动率: {stats['volatility']:.2f}\n\n"
        
        # 技术指标
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi['current']:
                report += f"### RSI指标\n"
                report += f"- 当前RSI: {rsi['current']:.2f}\n"
                report += f"- 信号: {rsi['signal']}\n\n"
        
        if 'macd' in indicators:
            macd = indicators['macd']
            if macd['macd']:
                report += f"### MACD指标\n"
                report += f"- MACD: {macd['macd']:.4f}\n"
                report += f"- 信号线: {macd['signal']:.4f}\n"
                report += f"- 趋势: {macd['trend']}\n\n"
        
        if 'trend' in indicators:
            trend = indicators['trend']
            report += f"### 趋势分析\n"
            report += f"- 方向: {trend['direction']}\n"
            report += f"- 强度: {trend['strength']:.2f}%\n\n"
        
        # 投资建议（基于指标）
        report += f"### 技术分析总结\n"
        signals = []
        
        if 'rsi' in indicators and indicators['rsi'].get('current'):
            rsi_val = indicators['rsi']['current']
            if rsi_val > 70:
                signals.append("RSI显示超买，可能存在回调风险")
            elif rsi_val < 30:
                signals.append("RSI显示超卖，可能存在反弹机会")
        
        if 'macd' in indicators:
            if indicators['macd'].get('trend') == 'bullish':
                signals.append("MACD显示看涨趋势")
            elif indicators['macd'].get('trend') == 'bearish':
                signals.append("MACD显示看跌趋势")
        
        if 'trend' in indicators:
            if indicators['trend']['direction'] == 'uptrend':
                signals.append("价格处于上升趋势")
            elif indicators['trend']['direction'] == 'downtrend':
                signals.append("价格处于下降趋势")
        
        if signals:
            report += "\n".join(f"- {s}" for s in signals)
        else:
            report += "- 需要更多数据进行分析"
        
        return report


# 全局量化工具实例
quant_tool = QuantTool()

