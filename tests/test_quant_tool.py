"""
量化工具测试
"""
import pytest
from app.services.quant_tool import quant_tool
from app.database.storage import storage_manager
from datetime import datetime, timedelta


class TestQuantTool:
    """量化工具测试"""
    
    @pytest.fixture
    def sample_data(self):
        """创建测试数据"""
        symbol = "TEST_QUANT"
        base_price = 100.0
        
        # 创建30天的测试数据
        for i in range(30):
            date = datetime.now() - timedelta(days=30-i)
            # 模拟价格波动
            price_change = (i % 10 - 5) * 2  # -10 到 +10的波动
            data = {
                "open": base_price + price_change,
                "close": base_price + price_change + 1,
                "high": base_price + price_change + 2,
                "low": base_price + price_change - 1,
                "volume": 1000000 + i * 10000,
                "turnover": 100000000 + i * 1000000,
                "amplitude": 2.0,
                "change_percent": price_change / base_price * 100
            }
            
            storage_manager.save_financial_data(
                symbol=symbol,
                market="测试市场",
                data_type="daily",
                date=date,
                data=data
            )
        
        return symbol
    
    @pytest.mark.unit
    def test_calculate_technical_indicators(self, sample_data):
        """测试技术指标计算"""
        indicators = quant_tool.calculate_technical_indicators(sample_data)
        
        assert "error" not in indicators
        assert "basic_stats" in indicators
        assert "moving_averages" in indicators
        assert "rsi" in indicators
        assert "macd" in indicators
        assert "trend" in indicators
    
    @pytest.mark.unit
    def test_basic_stats(self, sample_data):
        """测试基础统计"""
        indicators = quant_tool.calculate_technical_indicators(sample_data)
        stats = indicators["basic_stats"]
        
        assert "current_price" in stats
        assert "price_change" in stats
        assert "price_change_percent" in stats
        assert "max_price" in stats
        assert "min_price" in stats
        assert "avg_price" in stats
        assert "volatility" in stats
    
    @pytest.mark.unit
    def test_moving_averages(self, sample_data):
        """测试移动平均线"""
        indicators = quant_tool.calculate_technical_indicators(sample_data)
        ma = indicators["moving_averages"]
        
        assert "ma5" in ma
        assert "ma10" in ma
        assert "ma20" in ma
    
    @pytest.mark.unit
    def test_rsi_calculation(self, sample_data):
        """测试RSI计算"""
        indicators = quant_tool.calculate_technical_indicators(sample_data)
        rsi = indicators["rsi"]
        
        assert "current" in rsi
        assert "signal" in rsi
        if rsi["current"]:
            assert 0 <= rsi["current"] <= 100
    
    @pytest.mark.unit
    def test_generate_analysis_report(self, sample_data):
        """测试生成分析报告"""
        report = quant_tool.generate_analysis_report(sample_data)
        
        assert isinstance(report, str)
        assert len(report) > 0
        assert "量化分析报告" in report or "分析" in report
    
    @pytest.mark.unit
    def test_no_data_handling(self):
        """测试无数据情况"""
        indicators = quant_tool.calculate_technical_indicators("NONEXISTENT")
        
        assert "error" in indicators

